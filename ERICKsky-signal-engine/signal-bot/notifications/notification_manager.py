"""
ERICKsky Signal Engine - Notification Manager
High-level coordinator for all outbound notifications.
"""

import logging
from typing import Optional

from database.models import Signal
from database.repositories import SignalRepository
from notifications.telegram_bot import telegram_bot

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Coordinates signal delivery: saves to DB, sends via Telegram,
    and handles retry logic.
    """

    def dispatch_signal(self, signal: Signal) -> Optional[int]:
        """
        Save signal to DB then deliver via Telegram.

        Returns:
            The signal DB ID on success, None on DB failure.
        """
        # Step 1: persist to DB (fatal — return None if this fails)
        try:
            signal_id = SignalRepository.save(signal)
            signal.id = signal_id
        except Exception as exc:
            logger.exception("Failed to save signal for %s to DB: %s", signal.pair, exc)
            return None

        # Step 2: deliver via Telegram (non-fatal — signal already saved)
        try:
            delivered = telegram_bot.send_signal(signal)
            logger.info(
                "Signal #%d dispatched: %s %s delivered_to=%d channels",
                signal_id, signal.pair, signal.direction, delivered,
            )
        except Exception as exc:
            logger.error(
                "Signal #%d saved to DB but Telegram delivery failed for %s: %s",
                signal_id, signal.pair, exc,
            )

        return signal_id

    def send_admin_alert(self, message: str) -> None:
        """Send a plain alert to the admin."""
        try:
            telegram_bot.send_admin_message(message)
        except Exception as exc:
            logger.error("Failed to send admin alert: %s", exc)

    def send_daily_report(self) -> None:
        """Compile and send the daily performance report."""
        from datetime import date
        from database.repositories import PerformanceRepository

        today = date.today().isoformat()
        summary = PerformanceRepository.get_summary()

        total = int(summary.get("total_signals") or 0)
        wins = int(summary.get("wins") or 0)
        losses = int(summary.get("losses") or 0)
        pending = total - wins - losses
        total_pips = float(summary.get("total_pips") or 0.0)

        logger.info(
            "Sending daily report: total=%d W=%d L=%d pips=%.1f",
            total, wins, losses, total_pips,
        )
        telegram_bot.send_daily_report(today, total, wins, losses, pending, total_pips)


# Module-level singleton
notification_manager = NotificationManager()
