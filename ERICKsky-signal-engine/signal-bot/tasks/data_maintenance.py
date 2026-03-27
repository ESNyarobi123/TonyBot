"""
ERICKsky Signal Engine - Celery Task: Data Maintenance

Sniper Mode housekeeping tasks:
  • clean_m1_m5_cache — purge M1 and M5 OHLCV data from Redis daily
    to keep memory consumption low when running high-frequency scans.

M1/M5 candles are fetched fresh every 15-minute scan cycle and only
need to persist for that cycle's confirmation check.  Purging at
00:05 UTC ensures a clean slate at the start of each trading day
without interrupting active London/NY sessions.

Redis key patterns purged:
  candles:{pair}:M1   candles:{pair}:M5    (twelve_data client)
  ohlcv:{pair}:M1     ohlcv:{pair}:M5      (cache_manager client)
"""

import logging

from celery_app import celery_app
from config import settings
from data.cache_manager import cache

logger = logging.getLogger(__name__)

# Timeframes to purge
_SNIPER_TFS = ["M1", "M5"]

# Both key-prefix conventions used across the codebase
_KEY_PREFIXES = ["candles", "ohlcv"]


@celery_app.task(
    name="tasks.clean_m1_m5_cache",
    queue="default",
)
def clean_m1_m5_cache() -> dict:
    """
    Purge M1 and M5 OHLCV entries from Redis for all configured
    trading pairs.

    Runs daily at 00:05 UTC (before London pre-session activity).
    Each scan cycle re-fetches fresh M1/M5 candles anyway, so
    purging overnight has zero impact on signal quality.

    Returns:
        dict with status, pairs_processed, keys_deleted counts.
    """
    logger.info("[clean_m1_m5_cache] Starting M1/M5 Redis cache purge…")

    pairs = getattr(settings, "TRADING_PAIRS", [])
    total_deleted = 0
    pairs_processed = 0

    for pair in pairs:
        pair_deleted = 0
        for prefix in _KEY_PREFIXES:
            for tf in _SNIPER_TFS:
                key = f"{prefix}:{pair}:{tf}"
                try:
                    if cache.exists(key):
                        cache.delete(key)
                        pair_deleted += 1
                        logger.debug(
                            "[clean_m1_m5_cache] Deleted key: %s", key
                        )
                except Exception as exc:
                    logger.warning(
                        "[clean_m1_m5_cache] Failed to delete %s: %s", key, exc
                    )

        # Also sweep any wildcard remnants via pattern flush
        for tf in _SNIPER_TFS:
            for prefix in _KEY_PREFIXES:
                deleted = cache.flush_pattern(f"{prefix}:{pair}:{tf}*")
                pair_deleted += deleted

        if pair_deleted:
            logger.info(
                "[clean_m1_m5_cache] %s: %d keys removed", pair, pair_deleted
            )
        total_deleted += pair_deleted
        pairs_processed += 1

    result = {
        "status":          "success",
        "pairs_processed": pairs_processed,
        "keys_deleted":    total_deleted,
    }
    logger.info(
        "[clean_m1_m5_cache] Complete — %d pairs, %d keys deleted",
        pairs_processed, total_deleted,
    )
    return result
