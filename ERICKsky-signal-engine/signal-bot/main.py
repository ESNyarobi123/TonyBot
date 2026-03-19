"""
ERICKsky Signal Engine - Main Entry Point
Initialises all services and starts the scheduler loop.
"""

import logging
import signal
import sys
import time
from datetime import datetime, timezone

from utils.logger import setup_logging
from config.settings import validate_settings
from database.db_manager import db
from data.cache_manager import cache
from data.data_fetcher import data_fetcher
from notifications.telegram_bot import telegram_bot
from database.repositories import BotStateRepository
from scheduler import build_scheduler

logger = logging.getLogger(__name__)


def startup_checks() -> bool:
    """Verify all external services are reachable before starting."""
    logger.info("Running startup checks...")

    # Database
    if not db.health_check():
        logger.critical("PostgreSQL is not reachable. Aborting.")
        return False
    logger.info("[OK] PostgreSQL connected")

    # Redis
    if not cache.health_check():
        logger.critical("Redis is not reachable. Aborting.")
        return False
    logger.info("[OK] Redis connected")

    # Telegram (non-blocking — warn only)
    import asyncio
    try:
        ok = asyncio.get_event_loop().run_until_complete(telegram_bot.test_connection())
        if ok:
            logger.info("[OK] Telegram bot connected")
        else:
            logger.warning("[WARN] Telegram bot not reachable — signals won't be delivered")
    except Exception as exc:
        logger.warning("[WARN] Telegram check failed: %s", exc)

    return True


def run() -> None:
    """Main entry point."""
    setup_logging()

    logger.info("=" * 60)
    logger.info("  ERICKsky Signal Engine  v1.0.0")
    logger.info("  Starting at %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 60)

    # Validate required env vars
    try:
        validate_settings()
    except ValueError as exc:
        logger.critical("Configuration error: %s", exc)
        sys.exit(1)

    # Initialise connection pools
    db.initialize()
    cache.initialize()

    # Startup health checks
    if not startup_checks():
        sys.exit(1)

    # Mark bot as running
    BotStateRepository.set("bot_running", "true")
    BotStateRepository.set("last_scan_at", datetime.now(timezone.utc).isoformat())

    # Pre-warm cache
    try:
        logger.info("Pre-loading OHLCV cache...")
        data_fetcher.preload_cache()
    except Exception as exc:
        logger.warning("Cache preload failed (non-fatal): %s", exc)

    # Build and start APScheduler
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started. Running signal scans every %dmin.", 60)

    # Run an initial scan immediately
    from tasks.scan_pair import scan_all_pairs
    logger.info("Running initial scan for all pairs...")
    scan_all_pairs.delay()

    # Graceful shutdown handler
    def _shutdown(signum, frame):
        logger.info("Shutdown signal received (%s)", signum)
        scheduler.shutdown(wait=False)
        BotStateRepository.set("bot_running", "false")
        db.close()
        cache.close()
        logger.info("ERICKsky Signal Engine stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("ERICKsky Signal Engine is RUNNING. Press Ctrl+C to stop.")

    # Keep main thread alive
    while True:
        time.sleep(30)


if __name__ == "__main__":
    run()
