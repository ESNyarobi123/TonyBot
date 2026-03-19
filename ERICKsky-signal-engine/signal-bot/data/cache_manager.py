"""
ERICKsky Signal Engine - Redis Cache Manager
Provides transparent caching for OHLCV data and signals.
"""

import json
import logging
import pickle
from typing import Any, Optional

import redis
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Thread-safe Redis cache manager with serialization support."""

    _instance: Optional["CacheManager"] = None
    _redis: Optional[redis.Redis] = None

    def __new__(cls) -> "CacheManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self) -> None:
        """Connect to Redis."""
        if self._redis is not None:
            return
        try:
            self._redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=False,   # We handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            self._redis.ping()
            logger.info(
                "Redis connected: %s:%s/%s",
                settings.REDIS_HOST,
                settings.REDIS_PORT,
                settings.REDIS_DB,
            )
        except redis.RedisError as exc:
            logger.critical("Redis connection failed: %s", exc)
            raise

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            self.initialize()
        return self._redis

    # ─── Generic cache ops ────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value (auto-deserialised)."""
        try:
            raw = self.redis.get(key)
            if raw is None:
                return None
            return pickle.loads(raw)
        except Exception as exc:
            logger.warning("Cache GET error for key '%s': %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Store a value with TTL (seconds)."""
        try:
            serialised = pickle.dumps(value)
            self.redis.setex(key, ttl, serialised)
            return True
        except Exception as exc:
            logger.warning("Cache SET error for key '%s': %s", key, exc)
            return False

    def delete(self, key: str) -> None:
        """Remove a key."""
        try:
            self.redis.delete(key)
        except Exception as exc:
            logger.warning("Cache DELETE error for key '%s': %s", key, exc)

    def exists(self, key: str) -> bool:
        try:
            return bool(self.redis.exists(key))
        except Exception:
            return False

    def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted."""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as exc:
            logger.warning("Cache flush_pattern error '%s': %s", pattern, exc)
            return 0

    # ─── OHLCV-specific helpers ───────────────────────────────────────────────

    @staticmethod
    def _ohlcv_key(symbol: str, interval: str) -> str:
        return f"ohlcv:{symbol}:{interval}"

    def get_ohlcv(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Retrieve cached OHLCV DataFrame."""
        key = self._ohlcv_key(symbol, interval)
        return self.get(key)

    def set_ohlcv(self, symbol: str, interval: str, df: pd.DataFrame) -> bool:
        """Cache an OHLCV DataFrame with timeframe-appropriate TTL."""
        key = self._ohlcv_key(symbol, interval)
        ttl = settings.CACHE_TTL_MAP.get(interval, 3600)
        return self.set(key, df, ttl)

    def invalidate_ohlcv(self, symbol: str) -> None:
        """Remove all cached OHLCV for a symbol."""
        self.flush_pattern(f"ohlcv:{symbol}:*")

    # ─── Signal-specific helpers ──────────────────────────────────────────────

    @staticmethod
    def _signal_key(pair: str) -> str:
        return f"signal:last:{pair}"

    def get_last_signal(self, pair: str) -> Optional[dict]:
        return self.get(self._signal_key(pair))

    def set_last_signal(self, pair: str, signal_data: dict) -> bool:
        return self.set(
            self._signal_key(pair), signal_data, ttl=settings.CACHE_TTL_SIGNAL
        )

    # ─── Scan lock (prevent duplicate scans) ─────────────────────────────────

    def acquire_scan_lock(self, pair: str, ttl: int = 300) -> bool:
        """
        Try to acquire a scan lock for a pair.
        Returns True if lock was acquired, False if already locked.
        """
        lock_key = f"lock:scan:{pair}"
        result = self.redis.set(lock_key, "1", ex=ttl, nx=True)
        return result is True

    def release_scan_lock(self, pair: str) -> None:
        self.delete(f"lock:scan:{pair}")

    # ─── Generic JSON store (for small dicts) ────────────────────────────────

    def get_json(self, key: str) -> Optional[Any]:
        try:
            raw = self.redis.get(key)
            if raw is None:
                return None
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.warning("Cache get_json error for key '%s': %s", key, exc)
            return None

    def set_json(self, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as exc:
            logger.warning("Cache set_json error for key '%s': %s", key, exc)
            return False

    # ─── Health check ─────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        try:
            return self.redis.ping()
        except Exception:
            return False

    def close(self) -> None:
        if self._redis:
            self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")


# Module-level singleton
cache = CacheManager()
