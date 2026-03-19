"""
ERICKsky Signal Engine - Twelve Data API Client
Direct REST implementation with intelligent Redis caching strategy.

Cache TTL per timeframe (new candle cadence – small buffer):
  M15 → 12 min  | H1 → 50 min  | H4 → 200 min  | D1 → 1200 min

Daily API budget with caching:
  4 pairs × 4 timeframes = 16 requests max per full scan
  With cache hits → ~4 fresh requests per scan
  24 scans × 4 = 96 requests/day — well within free-tier 800 limit ✅
"""

import logging
import time
from typing import Optional, Dict, Any, List

import pandas as pd
import requests

from config import settings

logger = logging.getLogger(__name__)

# ── Exact mappings as specified ────────────────────────────────────────────────

SYMBOL_MAP: Dict[str, str] = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "XAUUSD": "XAU/USD",  # Gold
    "AUDUSD": "AUD/USD",  # Active pair
    "USDCHF": "USD/CHF",
    "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD",
}

TIMEFRAME_MAP: Dict[str, str] = {
    "M15": "15min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1day",
}

# Cache TTL in seconds per timeframe (slightly under new-candle interval)
CACHE_TTL_SECONDS: Dict[str, int] = {
    "M15":    12 * 60,     # 720 s   — new candle every 15 min
    "H1":     50 * 60,     # 3000 s  — new candle every 60 min
    "H4":    200 * 60,     # 12000 s — new candle every 240 min
    "D1":   1200 * 60,     # 72000 s — new candle every 1440 min
    # Legacy lowercase aliases
    "15min":  12 * 60,
    "1h":     50 * 60,
    "4h":    200 * 60,
    "1day": 1200 * 60,
}

PRICE_CACHE_TTL: int = 30    # seconds — real-time price cache
_REQUEST_DELAY:  float = 0.5  # seconds between requests (rate-limit buffer)
BASE_URL:        str = "https://api.twelvedata.com"


class TwelveDataClient:
    """
    Singleton REST client for Twelve Data API.
    All OHLCV requests pass through Redis cache before hitting the network.
    """

    _instance: Optional["TwelveDataClient"] = None

    def __new__(cls) -> "TwelveDataClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── Primary interface ─────────────────────────────────────────────────────

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        count: int = 200,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles for a symbol/timeframe pair.
        Checks Redis cache first; falls back to the Twelve Data REST API.

        Args:
            symbol:        e.g. "EURUSD", "XAUUSD"
            timeframe:     "M15" | "H1" | "H4" | "D1"
            count:         number of candles to request
            force_refresh: bypass cache and always hit the API

        Returns:
            DataFrame with columns [open, high, low, close, volume]
            sorted ascending by DatetimeIndex (UTC), or None on failure.
        """
        from data.cache_manager import cache

        cache_key = f"candles:{symbol}:{timeframe}"

        # 1. Check Redis cache
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached is not None and isinstance(cached, pd.DataFrame) and not cached.empty:
                logger.debug("Cache HIT: %s/%s (%d candles)", symbol, timeframe, len(cached))
                return cached

        # 2. Fetch from API
        logger.info("API FETCH: %s/%s count=%d", symbol, timeframe, count)
        df = self._fetch_from_api(symbol, timeframe, count)

        if df is None:
            return None

        # 3. Store in cache with timeframe-appropriate TTL
        ttl = CACHE_TTL_SECONDS.get(timeframe, 3600)
        cache.set(cache_key, df, ttl=ttl)
        logger.debug("Cached %s/%s TTL=%ds", symbol, timeframe, ttl)

        return df

    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """
        Fetch current market price.
        Cached for PRICE_CACHE_TTL (30) seconds to avoid hammering the API.
        """
        from data.cache_manager import cache

        cache_key = f"price:{symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            return float(cached)

        td_symbol = SYMBOL_MAP.get(symbol.upper(), symbol)
        try:
            resp = requests.get(
                f"{BASE_URL}/price",
                params={
                    "symbol": td_symbol,
                    "apikey": settings.TWELVE_DATA_API_KEY,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

            if "price" not in data:
                logger.error("No 'price' key in response for %s: %s", symbol, data)
                return None

            price = float(data["price"])
            cache.set(cache_key, price, ttl=PRICE_CACHE_TTL)
            return price

        except Exception as exc:
            logger.error("Failed to get realtime price for %s: %s", symbol, exc)
            return None

    # ── Internal API fetch ────────────────────────────────────────────────────

    def _fetch_from_api(
        self,
        symbol: str,
        timeframe: str,
        count: int,
        retries: int = 3,
    ) -> Optional[pd.DataFrame]:
        """
        Make the actual REST request with exponential-backoff retry logic.
        Parses JSON response into a clean, typed DataFrame.
        """
        td_symbol   = SYMBOL_MAP.get(symbol.upper(), symbol)
        td_interval = TIMEFRAME_MAP.get(timeframe, timeframe)

        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(
                    f"{BASE_URL}/time_series",
                    params={
                        "symbol":     td_symbol,
                        "interval":   td_interval,
                        "outputsize": count,
                        "apikey":     settings.TWELVE_DATA_API_KEY,
                        "format":     "JSON",
                        "order":      "ASC",
                        "timezone":   "UTC",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()

                # API-level error (e.g. invalid symbol, exhausted quota)
                if data.get("status") == "error":
                    msg = data.get("message", "unknown error")
                    logger.error("Twelve Data error for %s/%s: %s", symbol, timeframe, msg)
                    return None

                values = data.get("values")
                if not values:
                    logger.warning("Empty 'values' for %s/%s (attempt %d)", symbol, timeframe, attempt)
                    time.sleep(_REQUEST_DELAY * attempt)
                    continue

                # Parse to DataFrame
                df = pd.DataFrame(values)
                df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
                df.set_index("datetime", inplace=True)
                df.sort_index(ascending=True, inplace=True)

                for col in ["open", "high", "low", "close", "volume"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                if "volume" not in df.columns:
                    df["volume"] = 0.0

                df.dropna(subset=["open", "high", "low", "close"], inplace=True)

                logger.info(
                    "Fetched %d candles for %s/%s [%s→%s]",
                    len(df), symbol, timeframe,
                    df.index[0].strftime("%Y-%m-%d %H:%M"),
                    df.index[-1].strftime("%Y-%m-%d %H:%M"),
                )

                time.sleep(_REQUEST_DELAY)
                return df

            except requests.exceptions.Timeout:
                logger.warning(
                    "Timeout fetching %s/%s (attempt %d/%d)", symbol, timeframe, attempt, retries
                )
                time.sleep(2 ** attempt)

            except requests.exceptions.HTTPError as exc:
                logger.error("HTTP error for %s/%s: %s", symbol, timeframe, exc)
                if exc.response is not None and exc.response.status_code < 500:
                    return None  # 4xx client error — no point retrying
                time.sleep(2 ** attempt)

            except Exception as exc:
                logger.exception(
                    "Unexpected error fetching %s/%s (attempt %d): %s",
                    symbol, timeframe, attempt, exc,
                )
                if attempt == retries:
                    return None
                time.sleep(2 ** attempt)

        logger.error("All %d attempts exhausted for %s/%s", retries, symbol, timeframe)
        return None

    # ── Backwards-compatible aliases ──────────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 200,
    ) -> Optional[pd.DataFrame]:
        """Backwards-compatible wrapper — prefers get_candles()."""
        _rev = {v: k for k, v in TIMEFRAME_MAP.items()}
        tf = _rev.get(interval, interval)
        return self.get_candles(symbol, tf, outputsize)

    def get_price(self, symbol: str) -> Optional[float]:
        """Backwards-compatible alias for get_realtime_price()."""
        return self.get_realtime_price(symbol)

    def get_multiple_ohlcv(
        self,
        symbols: List[str],
        interval: str,
        outputsize: int = 200,
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """Fetch OHLCV for multiple symbols sequentially (rate-limit safe)."""
        results: Dict[str, Optional[pd.DataFrame]] = {}
        for symbol in symbols:
            results[symbol] = self.get_ohlcv(symbol, interval, outputsize)
            time.sleep(_REQUEST_DELAY)
        return results

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch symbol metadata via symbol search endpoint."""
        td_symbol = SYMBOL_MAP.get(symbol.upper(), symbol)
        try:
            resp = requests.get(
                f"{BASE_URL}/symbol_search",
                params={"symbol": td_symbol, "apikey": settings.TWELVE_DATA_API_KEY},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"][0] if data["data"] else None
            return None
        except Exception as exc:
            logger.error("Failed to get symbol info for %s: %s", symbol, exc)
            return None

    def is_available(self) -> bool:
        """Verify API connectivity with a lightweight price call."""
        try:
            price = self.get_realtime_price("EURUSD")
            return price is not None and price > 0
        except Exception:
            return False


# Module-level singleton
twelve_data = TwelveDataClient()
