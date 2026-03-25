"""
ERICKsky Signal Engine - Data Fetcher  (v3 — Rate-Limit Optimised)

High-level OHLCV fetcher with serialised fetching and smart cache strategy.

Serialised Fetching Logic (8 req/min safe):
  1. Fetch DXY (H1 only)      → sleep 15s
  2. Fetch EURUSD (M15, H1)   → sleep 15s   (D1/H4 served from 4h cache)
  3. Fetch GBPUSD (M15, H1)   → sleep 15s
  4. Fetch XAUUSD (M15, H1)   → sleep 15s
  5. Fetch AUDUSD (M15, H1)

Timeframe Persistence:
  D1 & H4 → cached for 4 hours — fetched only once per 4-hour window
  H1 & M15 → cached ~50 min / ~12 min — refetched every scan cycle

Budget: 1 (DXY) + 4 pairs × 2 (H1+M15) = 9 req/hour → 216 credits/day ✅
"""

import logging
import time
from typing import Dict, Optional, List, Tuple

import pandas as pd

from config import settings
from data.twelve_data import twelve_data, CACHE_TTL_SECONDS
from data.cache_manager import cache

logger = logging.getLogger(__name__)

# Timeframes that are critical for entry signals (fetched every cycle)
_FAST_TIMEFRAMES: List[str] = ["M15", "H1"]

# Timeframes that change slowly (cached for 4 hours, skip API if fresh)
_SLOW_TIMEFRAMES: List[str] = ["H4", "D1"]

# All 4 strategy timeframes in fetch order
_ALL_TIMEFRAMES: List[str] = ["D1", "H4", "H1", "M15"]

# Delay between pair fetch batches (seconds)
_INTER_PAIR_DELAY: float = 15.0


class DataFetcher:
    """
    Fetches OHLCV data for trading pairs across multiple timeframes.
    Uses Redis cache to minimise API calls with smart persistence:
      • D1/H4: served from cache if < 4 hours old (no API hit)
      • H1/M15: always fresh-fetched each scan cycle

    All API calls are serialised through the TwelveDataClient rate-limit
    gate (15s gap + 429 recovery), so no threading concerns here.
    """

    # ── Single-pair fetch (cache-aware) ────────────────────────────────────────

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

    # ── Smart single-pair fetch (slow TFs from cache, fast TFs from API) ──────

    def fetch_pair_smart(
        self,
        symbol: str,
        count_fast: int = 100,
        count_slow: int = 200,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Smart fetch for one pair:
          • D1/H4 → serve from cache if still valid (4h TTL); API only on miss.
          • H1/M15 → always fetch fresh from API (critical for entry).

        Returns:
            Dict[timeframe -> DataFrame]  e.g. {"D1": df, "H4": df, "H1": df, "M15": df}
        """
        result: Dict[str, Optional[pd.DataFrame]] = {}

        # 1. Slow timeframes — prefer cache (4-hour persistence)
        for tf in _SLOW_TIMEFRAMES:
            cached = cache.get_ohlcv(symbol, tf)
            if cached is not None and not cached.empty:
                logger.debug(
                    "[Smart Fetch] %s/%s served from cache (%d rows)",
                    symbol, tf, len(cached),
                )
                result[tf] = cached
            else:
                logger.info("[Smart Fetch] %s/%s cache miss — fetching from API", symbol, tf)
                df = twelve_data.get_candles(symbol, tf, count=count_slow)
                result[tf] = df

        # 2. Fast timeframes — always fetch fresh
        for tf in _FAST_TIMEFRAMES:
            count = count_fast if tf == "M15" else count_slow
            df = twelve_data.get_candles(symbol, tf, count=count)
            result[tf] = df

        available = sum(1 for v in result.values() if v is not None)
        logger.info(
            "[Smart Fetch] %s complete: %d/%d timeframes available",
            symbol, available, len(result),
        )
        return result

    # ── DXY fetch ──────────────────────────────────────────────────────────────

    def fetch_dxy(self, count: int = 50) -> Optional[pd.DataFrame]:
        """
        Fetch DXY H1 data for the DXY correlation filter.
        Respects the same cache + rate-limit pipeline.

        Returns H1 DataFrame or None.
        """
        logger.info("[DXY Fetch] Fetching DXY H1 data…")
        df = twelve_data.get_candles("DXY", "H1", count=count)
        if df is not None and not df.empty:
            logger.info(
                "[Data Success: DXY H1 fetched successfully] %d candles", len(df),
            )
        else:
            logger.warning("[DXY Fetch] Failed to fetch DXY H1 data")
        return df

    # ── Full scan-cycle orchestrator ──────────────────────────────────────────

    def scan_cycle_fetch(
        self,
        pairs: Optional[List[str]] = None,
    ) -> Tuple[
        Optional[pd.DataFrame],                     # DXY H1
        Dict[str, Dict[str, Optional[pd.DataFrame]]],  # pair → {tf → df}
        Dict[str, Optional[float]],                  # pair → current price
    ]:
        """
        Serialised full-cycle data fetch with mandatory 15s gaps.

        Flow:
          1. Fetch DXY (H1)               → sleep 15s
          2. For each trading pair:
             a. Fetch price (cached 30s)
             b. Smart-fetch D1/H4/H1/M15  → sleep 15s

        Returns:
            (dxy_h1_df, all_pair_data, prices)
        """
        if pairs is None:
            pairs = settings.TRADING_PAIRS

        logger.info(
            "═══ SCAN CYCLE FETCH START: DXY + %d pairs ═══", len(pairs),
        )
        cycle_start = time.monotonic()

        # ── Step 1: DXY ──────────────────────────────────────────────────────
        dxy_h1 = self.fetch_dxy()

        # The 15s delay is enforced inside TwelveDataClient via _RATE_LIMIT_GAP,
        # but we add an explicit inter-pair pause for clarity and safety.
        if pairs:
            logger.debug("[Scan Cycle] Sleeping %.0fs after DXY fetch…", _INTER_PAIR_DELAY)
            time.sleep(_INTER_PAIR_DELAY)

        # ── Step 2: Each pair ────────────────────────────────────────────────
        all_data: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}
        prices: Dict[str, Optional[float]] = {}

        for i, pair in enumerate(pairs):
            logger.info("[Scan Cycle] Fetching %s (%d/%d)…", pair, i + 1, len(pairs))

            # 2a. Price
            prices[pair] = twelve_data.get_realtime_price(pair)

            # 2b. Smart multi-TF data
            all_data[pair] = self.fetch_pair_smart(pair)

            # 2c. Inter-pair delay (skip after last pair)
            if i < len(pairs) - 1:
                logger.debug(
                    "[Scan Cycle] Sleeping %.0fs before next pair…",
                    _INTER_PAIR_DELAY,
                )
                time.sleep(_INTER_PAIR_DELAY)

        elapsed = time.monotonic() - cycle_start
        api_calls_est = 1 + len(pairs) * 2  # DXY + (H1+M15 per pair, D1/H4 cached)
        logger.info(
            "═══ SCAN CYCLE FETCH COMPLETE: %d pairs in %.0fs "
            "(~%d API calls, D1/H4 from cache) ═══",
            len(pairs), elapsed, api_calls_est,
        )

        return dxy_h1, all_data, prices

    # ── Legacy helpers ─────────────────────────────────────────────────────────

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
        Uses the serialised scan_cycle_fetch for safe rate limiting.
        """
        logger.info(
            "Pre-loading cache for DXY + %d pairs (serialised, rate-limited)…",
            len(settings.TRADING_PAIRS),
        )
        dxy_h1, all_data, prices = self.scan_cycle_fetch()

        total_tfs = sum(
            sum(1 for v in pair_data.values() if v is not None)
            for pair_data in all_data.values()
        )
        logger.info(
            "Cache pre-load complete: DXY=%s, %d pair-timeframes cached",
            "OK" if dxy_h1 is not None else "FAIL", total_tfs,
        )

    def invalidate_pair(self, symbol: str) -> None:
        """Remove all cached OHLCV for a specific pair."""
        cache.invalidate_ohlcv(symbol)
        logger.info("Cache invalidated for %s", symbol)


# Module-level singleton
data_fetcher = DataFetcher()
