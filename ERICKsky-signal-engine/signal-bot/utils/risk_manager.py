"""
ERICKsky Signal Engine - Risk Manager (Upgrade 9)

Enforces hard limits on signal frequency and consecutive losses
to protect the account from over-trading and drawdown spirals.

Limits enforced:
  max_signals_per_day         = 5
  max_signals_per_pair_per_day = 2
  max_consecutive_losses      = 3  → cooling-off period
  daily_loss_alert_pips        = 50 → admin Telegram alert
"""

import logging
from datetime import date, datetime, timezone
from typing import Tuple

from database.db_manager import db

logger = logging.getLogger(__name__)


class RiskManager:
    """Enforce daily and consecutive-loss trading limits."""

    LIMITS = {
        "max_signals_per_day":          5,
        "max_signals_per_pair_per_day": 2,
        "max_consecutive_losses":       3,
        "daily_loss_alert_pips":        50,
    }

    def check_limits(self, symbol: str) -> Tuple[bool, str]:
        """
        Verify the signal is within all risk limits.

        Returns:
            (True,  "within risk limits")           → allow signal
            (False, "reason string")                 → block signal
        """
        today = date.today()

        # ── 1. Total signals today ────────────────────────────────────────────
        try:
            row = db.execute_one(
                """
                SELECT COUNT(*) AS cnt
                FROM signals
                WHERE DATE(created_at AT TIME ZONE 'UTC') = %s
                  AND status IN ('PENDING', 'WIN', 'LOSS')
                """,
                (today,),
            )
            total_today = int(row["cnt"]) if row else 0
        except Exception as exc:
            logger.warning("RiskManager: DB query failed for total_today – %s", exc)
            total_today = 0

        if total_today >= self.LIMITS["max_signals_per_day"]:
            reason = f"Daily signal limit reached ({total_today}/{self.LIMITS['max_signals_per_day']})"
            logger.info("RiskManager BLOCKED %s: %s", symbol, reason)
            return False, reason

        # ── 2. Signals for this pair today ────────────────────────────────────
        try:
            row = db.execute_one(
                """
                SELECT COUNT(*) AS cnt
                FROM signals
                WHERE pair = %s
                  AND DATE(created_at AT TIME ZONE 'UTC') = %s
                """,
                (symbol, today),
            )
            pair_today = int(row["cnt"]) if row else 0
        except Exception as exc:
            logger.warning("RiskManager: DB query failed for pair_today – %s", exc)
            pair_today = 0

        if pair_today >= self.LIMITS["max_signals_per_pair_per_day"]:
            reason = (
                f"{symbol} pair limit reached today "
                f"({pair_today}/{self.LIMITS['max_signals_per_pair_per_day']})"
            )
            logger.info("RiskManager BLOCKED %s: %s", symbol, reason)
            return False, reason

        # ── 3. Consecutive losses check ───────────────────────────────────────
        try:
            rows = db.execute(
                """
                SELECT status FROM signals
                WHERE status IN ('WIN', 'LOSS')
                ORDER BY created_at DESC
                LIMIT 5
                """,
            )
            recent_statuses = [r["status"] for r in rows]
        except Exception as exc:
            logger.warning("RiskManager: DB query failed for consecutive losses – %s", exc)
            recent_statuses = []

        consecutive_losses = 0
        for s in recent_statuses:
            if s == "LOSS":
                consecutive_losses += 1
            else:
                break

        if consecutive_losses >= self.LIMITS["max_consecutive_losses"]:
            reason = (
                f"Max consecutive losses reached "
                f"({consecutive_losses}) – cooling-off period active!"
            )
            logger.warning("RiskManager BLOCKED %s: %s", symbol, reason)
            # Optionally alert admin
            self._maybe_alert_admin(consecutive_losses)
            return False, reason

        # ── 4. Daily pips loss alert (non-blocking) ────────────────────────────
        try:
            row = db.execute_one(
                """
                SELECT COALESCE(SUM(pips_result), 0) AS daily_pips
                FROM signals
                WHERE DATE(created_at AT TIME ZONE 'UTC') = %s
                  AND status IN ('WIN', 'LOSS')
                """,
                (today,),
            )
            daily_pips = float(row["daily_pips"]) if row else 0.0
            if daily_pips <= -self.LIMITS["daily_loss_alert_pips"]:
                self._maybe_alert_admin(
                    None,
                    f"⚠️ Daily pips loss alert: {daily_pips:.1f} pips today!",
                )
        except Exception as exc:
            logger.debug("RiskManager: daily pips check failed – %s", exc)

        logger.debug("RiskManager OK: %s (today=%d, pair=%d, consec_loss=%d)",
                     symbol, total_today, pair_today, consecutive_losses)
        return True, "within risk limits"

    @staticmethod
    def _maybe_alert_admin(consecutive_losses=None, custom_msg=None):
        """Fire-and-forget admin Telegram alert (non-critical)."""
        try:
            from notifications.notification_manager import notification_manager
            if custom_msg:
                msg = custom_msg
            else:
                msg = (
                    f"🛑 *Risk Manager Alert*\n"
                    f"Consecutive losses: {consecutive_losses}\n"
                    f"Bot entering cooling-off period.\n"
                    f"Please review open positions."
                )
            notification_manager.send_admin_alert(msg)
        except Exception:
            pass  # never let alerting break the main flow


# Module-level singleton
risk_manager = RiskManager()
