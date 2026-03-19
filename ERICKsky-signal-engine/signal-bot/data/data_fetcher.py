"""
ERICKsky Signal Engine - Data Fetcher
High-level OHLCV fetcher with Redis caching integration.
"""

import logging
import time
from typing import Dict, Optional, List

import pandas as pd

from config import settings
from data.twelve_data import twelve_data
from data.cache_manager import cache

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Fetches OHLCV data for trading pairs across multiple timeframes.
    Uses Redis cache to minimise API calls.
    """

    def get_ohlcv(
        self,
        symbol: str,
        interval: str,
        outputsize: int = settings.CANDLE_LOOKBACK,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Return OHLCV DataFrame for (symbol, interval).
        Checks cache first; fetches from API on cache miss or force_refresh.
        """
        if not force_refresh:
            cached = cache.get_ohlcv(symbol, interval)
            if cached is not None and not cached.empty:
                logger.debug("Cache HIT: %s/%s (%d rows)", symbol, interval, len(cached))
                return cached

        logger.debug("Cache MISS: fetching %s/%s from Twelve Data", symbol, interval)
        df = twelve_data.get_ohlcv(symbol, interval, outputsize)

        if df is not None and not df.empty:
            cache.set_ohlcv(symbol, interval, df)
            logger.info(
                "Fetched & cached %d candles for %s/%s", len(df), symbol, interval
            )
        else:
            logger.warning("No data returned for %s/%s", symbol, interval)

        return df

    def get_multi_timeframe(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None,
        outputsize: int = settings.CANDLE_LOOKBACK,
        force_refresh: bool = False,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch OHLCV for a symbol across multiple timeframes.

        Returns:
            Dict mapping interval -> DataFrame (or None on failure).
        """
        if timeframes is None:
            timeframes = settings.TIMEFRAMES

        result: Dict[str, Optional[pd.DataFrame]] = {}
        for interval in timeframes:
            result[interval] = self.get_ohlcv(symbol, interval, outputsize, force_refresh)

        available = sum(1 for df in result.values() if df is not None)
        logger.info(
            "Multi-TF fetch for %s: %d/%d timeframes available",
            symbol, available, len(timeframes),
        )
        return result

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Return the latest market price for a symbol."""
        price_key = f"price:{symbol}"
        cached_price = cache.get_json(price_key)
        if cached_price is not None:
            return float(cached_price)

        price = twelve_data.get_price(symbol)
        if price:
            cache.set_json(price_key, price, ttl=30)  # very short TTL for price
        return price

    def get_all_pairs_data(
        self,
        timeframes: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
        """
        Fetch multi-timeframe data for all configured trading pairs.

        Returns:
            Dict[pair -> Dict[interval -> DataFrame]]
        """
        if timeframes is None:
            timeframes = [
                settings.PRIMARY_TIMEFRAME,
                settings.TREND_TIMEFRAME,
                settings.ENTRY_TIMEFRAME,
            ]

        all_data: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}
        for pair in settings.TRADING_PAIRS:
            logger.info("Fetching data for %s ...", pair)
            all_data[pair] = self.get_multi_timeframe(
                pair, timeframes, force_refresh=force_refresh
            )
        return all_data

    def preload_cache(self) -> None:
        """
        Pre-warm the cache for all pairs and timeframes.
        Called at startup to ensure first scan has data available.
        Fetches only the 4 timeframes used by strategies to stay within
        the Twelve Data Basic plan limit of 8 credits/minute.
        """
        critical_tfs = ["15min", "1h", "4h", "1day"]
        logger.info(
            "Pre-loading cache for %d pairs x %d timeframes (rate-limited)...",
            len(settings.TRADING_PAIRS), len(critical_tfs),
        )
        for i, pair in enumerate(settings.TRADING_PAIRS):
            # Check if this pair already has fresh cached data
            cached = cache.get_ohlcv(pair, "1h")
            if cached is not None and not cached.empty:
                logger.info("Pre-loading %s ... (cache hit, skipping API fetch)", pair)
                continue
            logger.info("Pre-loading %s ... (cache miss, fetching from API)", pair)
            self.get_multi_timeframe(pair, timeframes=critical_tfs, force_refresh=True)
            if i < len(settings.TRADING_PAIRS) - 1:
                logger.info("Waiting 65s before next pair to respect API rate limit...")
                time.sleep(65)
        logger.info("Cache pre-load complete")

    def invalidate_pair(self, symbol: str) -> None:
        """Remove all cached OHLCV for a specific pair."""
        cache.invalidate_ohlcv(symbol)
        logger.info("Cache invalidated for %s", symbol)


# Module-level singleton
data_fetcher = DataFetcher()
