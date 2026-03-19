"""
ERICKsky Signal Engine - Celery Task: Daily Report
Generates and sends daily performance summary via Telegram.
"""

import logging
from datetime import date

from celery_app import celery_app
from notifications.notification_manager import notification_manager
from database.repositories import PerformanceRepository, BotStateRepository

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.daily_report",
    queue="default",
)
def send_daily_report() -> dict:
    """Send the daily performance report to all channels."""
    logger.info("[Task] daily_report started")

    try:
        today = date.today().isoformat()
        summary = PerformanceRepository.get_summary()

        total = int(summary.get("total_signals") or 0)
        wins = int(summary.get("wins") or 0)
        losses = int(summary.get("losses") or 0)
        pending = total - wins - losses
        total_pips = float(summary.get("total_pips") or 0.0)

        notification_manager.send_daily_report()

        BotStateRepository.set("last_daily_report", today)

        result = {
            "status": "success",
            "date": today,
            "total": total,
            "wins": wins,
            "losses": losses,
            "total_pips": total_pips,
        }
        logger.info("[Task] daily_report SUCCESS: %s", result)
        return result

    except Exception as exc:
        logger.exception("[Task] daily_report error: %s", exc)
        notification_manager.send_admin_alert(f"daily_report task failed: {exc}")
        return {"status": "failed", "error": str(exc)}


@celery_app.task(
    name="tasks.expire_old_signals",
    queue="default",
)
def expire_old_signals() -> dict:
    """Mark PENDING signals older than SIGNAL_VALID_MINUTES as EXPIRED."""
    from config import settings
    from database.db_manager import db

    logger.info("[Task] expire_old_signals started")
    try:
        rows = db.execute(
            """
            UPDATE signals
            SET status = 'EXPIRED'
            WHERE status = 'PENDING'
              AND sent_at < NOW() - INTERVAL '%s minutes'
            RETURNING id
            """,
            (settings.SIGNAL_VALID_MINUTES,),
        )
        count = len(rows) if rows else 0
        logger.info("[Task] Expired %d old signals", count)
        return {"status": "success", "expired": count}
    except Exception as exc:
        logger.exception("[Task] expire_old_signals error: %s", exc)
        return {"status": "failed", "error": str(exc)}
