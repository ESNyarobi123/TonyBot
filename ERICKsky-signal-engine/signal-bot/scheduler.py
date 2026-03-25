"""
ERICKsky Signal Engine - APScheduler Setup
Handles in-process scheduling as a backup to Celery Beat.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import settings

logger = logging.getLogger(__name__)


def _dispatch_scans() -> None:
    """Trigger Celery scan tasks for all configured pairs."""
    from filters.session_filter import SessionFilter
    from tasks.scan_pair import scan_all_pairs
    
    is_active, reason = SessionFilter().is_active()
    
    if not is_active:
        logger.info(f"Scan SKIPPED: {reason}")
        return
    
    logger.info("Scheduler: dispatching scans at %s UTC", datetime.now(timezone.utc).strftime("%H:%M"))
    scan_all_pairs.delay()


def _expire_signals() -> None:
    from tasks.daily_report import expire_old_signals
    expire_old_signals.delay()


def _daily_report() -> None:
    from tasks.daily_report import send_daily_report
    send_daily_report.delay()


def build_scheduler() -> BackgroundScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = BackgroundScheduler(timezone="UTC")

    # Scan every SCAN_INTERVAL_MINUTES minutes
    scheduler.add_job(
        func=_dispatch_scans,
        trigger=IntervalTrigger(minutes=settings.SCAN_INTERVAL_MINUTES),
        id="scan_all_pairs",
        name="Scan all trading pairs",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # Expire stale signals every 30 minutes
    scheduler.add_job(
        func=_expire_signals,
        trigger=IntervalTrigger(minutes=30),
        id="expire_signals",
        name="Expire old pending signals",
        replace_existing=True,
    )

    # Daily report at 21:30 UTC
    scheduler.add_job(
        func=_daily_report,
        trigger=CronTrigger(hour=21, minute=30, timezone="UTC"),
        id="daily_report",
        name="Send daily performance report",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: scan_interval=%dmin, daily_report=21:30 UTC",
        settings.SCAN_INTERVAL_MINUTES,
    )
    return scheduler
