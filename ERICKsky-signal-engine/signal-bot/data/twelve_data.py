"""
ERICKsky Signal Engine - Twelve Data API Client  (v3 — Rate-Limit Safe)

Direct REST implementation with intelligent Redis caching strategy and
strict rate-limit compliance for the Twelve Data **Free Plan** (8 req/min).

Rate-limit strategy:
  • Global threading lock ensures one API call at a time.
  • Mandatory 15-second gap between consecutive API requests.
  • 429 "Too Many Requests" triggers a 65-second pause + retry (max 3).

Cache TTL per timeframe (persistence-aware):
  M15 → 12 min  | H1 → 50 min  | H4 → 4 hours  | D1 → 4 hours
  D1/H4 are fetched at most once per 4-hour window to save credits.

Hourly API budget (optimised):
  1 DXY(H1) + 4 pairs × 2 (H1+M15) = 9 API calls/hour
  9 × 24 = 216 credits/day  —  well within 800 daily limit ✅
"""

import logging
import threading
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
    "DXY":    "USDX",      # US Dollar Index (for DXY correlation filter)
}

TIMEFRAME_MAP: Dict[str, str] = {
    "M1":  "1min",
    "M5":  "5min",
    "M15": "15min",
    "H1":  "1h",
    "H4":  "4h",
    "D1":  "1day",
}

# Cache TTL in seconds per timeframe
# D1/H4: persist for 4 hours (14400 s) — only re-fetch once per 4h window
# H1/M15: shorter TTL — refetched every scan cycle
CACHE_TTL_SECONDS: Dict[str, int] = {
    "M1":      1 * 60,     # 60 s    — new candle every 1 min
    "M5":      5 * 60,     # 300 s   — new candle every 5 min
    "M15":    12 * 60,     # 720 s   — new candle every 15 min
    "H1":     50 * 60,     # 3000 s  — new candle every 60 min
    "H4":    4 * 3600,     # 14400 s — fetch once per 4-hour window
    "D1":    4 * 3600,     # 14400 s — fetch once per 4-hour window
    # Legacy lowercase aliases
    "1min":    1 * 60,
    "5min":    5 * 60,
    "15min":  12 * 60,
    "1h":     50 * 60,
    "4h":    4 * 3600,
    "1day":  4 * 3600,
}

PRICE_CACHE_TTL: int   = 30     # seconds — real-time price cache
_RATE_LIMIT_GAP: float = 15.0   # seconds between consecutive API calls
_429_PAUSE:      float = 65.0   # seconds to pause on 429 "Too Many Requests"
_MAX_RETRIES:    int   = 3      # max retries per request (including 429)
BASE_URL:        str   = "https://api.twelvedata.com"


class TwelveDataClient:
    """
    Singleton REST client for Twelve Data API.
    All OHLCV requests pass through Redis cache before hitting the network.

    Rate-limit safety:
      • A threading.Lock serialises all outgoing API calls.
      • A mandatory 15-second gap is enforced between calls.
      • HTTP 429 triggers a 65-second cooldown + retry.
    """

    _instance: Optional["TwelveDataClient"] = None

    def __new__(cls) -> "TwelveDataClient":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._api_lock = threading.Lock()
            inst._last_api_call: float = 0.0
            cls._instance = inst
        return cls._instance

    # ── Rate-limit gate ────────────────────────────────────────────────────────

    def _wait_for_rate_limit(self) -> None:
        """Block until at least _RATE_LIMIT_GAP seconds have elapsed since the last API call."""
        elapsed = time.monotonic() - self._last_api_call
        remaining = _RATE_LIMIT_GAP - elapsed
        if remaining > 0:
            logger.debug("[Rate Limiter] Waiting %.1fs before next API call…", remaining)
            time.sleep(remaining)

    def _stamp_api_call(self) -> None:
        """Record the timestamp of the current API call."""
        self._last_api_call = time.monotonic()

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
            symbol:        e.g. "EURUSD", "XAUUSD", "DXY"
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

        # 2. Fetch from API (serialised + rate-limited)
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
        Uses the rate-limit gate like all other API calls.
        """
        from data.cache_manager import cache

        cache_key = f"price:{symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            return float(cached)

        td_symbol = SYMBOL_MAP.get(symbol.upper(), symbol)

        with self._api_lock:
            self._wait_for_rate_limit()
            try:
                resp = requests.get(
                    f"{BASE_URL}/price",
                    params={
                        "symbol": td_symbol,
                        "apikey": settings.TWELVE_DATA_API_KEY,
                    },
                    timeout=10,
                )
                self._stamp_api_call()

                # Handle 429
                if resp.status_code == 429:
                    logger.warning(
                        "[Rate Limit Hit: Pausing for 65 seconds...] "
                        "price request for %s", symbol,
                    )
                    time.sleep(_429_PAUSE)
                    resp = requests.get(
                        f"{BASE_URL}/price",
                        params={
                            "symbol": td_symbol,
                            "apikey": settings.TWELVE_DATA_API_KEY,
                        },
                        timeout=10,
                    )
                    self._stamp_api_call()

                resp.raise_for_status()
                data = resp.json()

                if "price" not in data:
                    logger.error("No 'price' key in response for %s: %s", symbol, data)
                    return None

                price = float(data["price"])
                cache.set(cache_key, price, ttl=PRICE_CACHE_TTL)
                logger.info("[Data Success: %s price fetched successfully] → %.5f", symbol, price)
                return price

            except Exception as exc:
                logger.error("Failed to get realtime price for %s: %s", symbol, exc)
                return None

    # ── Internal API fetch (rate-limited + 429 recovery) ─────────────────────

    def _fetch_from_api(
        self,
        symbol: str,
        timeframe: str,
        count: int,
    ) -> Optional[pd.DataFrame]:
        """
        Make the actual REST request with rate-limit serialisation and
        robust 429-recovery retry logic.

        On HTTP 429:
          1. Log: [Rate Limit Hit: Pausing for 65 seconds...]
          2. Sleep exactly 65 seconds
          3. Retry (up to _MAX_RETRIES total attempts)

        On success:
          Log: [Data Success: {pair} {timeframe} fetched successfully]
        """
        td_symbol   = SYMBOL_MAP.get(symbol.upper(), symbol)
        td_interval = TIMEFRAME_MAP.get(timeframe, timeframe)

        for attempt in range(1, _MAX_RETRIES + 1):
            with self._api_lock:
                self._wait_for_rate_limit()
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
                    self._stamp_api_call()

                    # ── 429 Recovery ──────────────────────────────────────────
                    if resp.status_code == 429:
                        logger.warning(
                            "[Rate Limit Hit: Pausing for 65 seconds...] "
                            "%s/%s attempt %d/%d",
                            symbol, timeframe, attempt, _MAX_RETRIES,
                        )
                        time.sleep(_429_PAUSE)
                        continue  # retry from top of loop (re-acquires lock)

                    resp.raise_for_status()
                    data = resp.json()

                    # API-level error (e.g. invalid symbol, exhausted quota)
                    if data.get("status") == "error":
                        code = data.get("code", 0)
                        msg = data.get("message", "unknown error")
                        # Twelve Data returns code 429 inside JSON too
                        if code == 429 or "Too many" in str(msg):
                            logger.warning(
                                "[Rate Limit Hit: Pausing for 65 seconds...] "
                                "%s/%s (JSON-level 429) attempt %d/%d",
                                symbol, timeframe, attempt, _MAX_RETRIES,
                            )
                            time.sleep(_429_PAUSE)
                            continue
                        logger.error(
                            "Twelve Data error for %s/%s: %s",
                            symbol, timeframe, msg,
                        )
                        return None

                    values = data.get("values")
                    if not values:
                        logger.warning(
                            "Empty 'values' for %s/%s (attempt %d/%d)",
                            symbol, timeframe, attempt, _MAX_RETRIES,
                        )
                        time.sleep(5)
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
                        "[Data Success: %s %s fetched successfully] "
                        "%d candles [%s → %s]",
                        symbol, timeframe, len(df),
                        df.index[0].strftime("%Y-%m-%d %H:%M"),
                        df.index[-1].strftime("%Y-%m-%d %H:%M"),
                    )
                    return df

                except requests.exceptions.Timeout:
                    self._stamp_api_call()
                    logger.warning(
                        "Timeout fetching %s/%s (attempt %d/%d)",
                        symbol, timeframe, attempt, _MAX_RETRIES,
                    )
                    time.sleep(min(2 ** attempt, 30))

                except requests.exceptions.HTTPError as exc:
                    self._stamp_api_call()
                    status = exc.response.status_code if exc.response is not None else 0
                    if status == 429:
                        logger.warning(
                            "[Rate Limit Hit: Pausing for 65 seconds...] "
                            "%s/%s HTTP 429 (attempt %d/%d)",
                            symbol, timeframe, attempt, _MAX_RETRIES,
                        )
                        time.sleep(_429_PAUSE)
                        continue
                    logger.error("HTTP error for %s/%s: %s", symbol, timeframe, exc)
                    if status and 400 <= status < 500:
                        return None  # client error — no point retrying
                    time.sleep(min(2 ** attempt, 30))

                except Exception as exc:
                    self._stamp_api_call()
                    logger.exception(
                        "Unexpected error fetching %s/%s (attempt %d/%d): %s",
                        symbol, timeframe, attempt, _MAX_RETRIES, exc,
                    )
                    if attempt == _MAX_RETRIES:
                        return None
                    time.sleep(min(2 ** attempt, 30))

        logger.error(
            "All %d attempts exhausted for %s/%s — giving up",
            _MAX_RETRIES, symbol, timeframe,
        )
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
        return results

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch symbol metadata via symbol search endpoint."""
        td_symbol = SYMBOL_MAP.get(symbol.upper(), symbol)
        with self._api_lock:
            self._wait_for_rate_limit()
            try:
                resp = requests.get(
                    f"{BASE_URL}/symbol_search",
                    params={"symbol": td_symbol, "apikey": settings.TWELVE_DATA_API_KEY},
                    timeout=10,
                )
                self._stamp_api_call()
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict) and "data" in data:
                    return data["data"][0] if data["data"] else None
                return None
            except Exception as exc:
                self._stamp_api_call()
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
