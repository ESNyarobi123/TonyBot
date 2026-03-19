"""
ERICKsky Signal Engine - Session Filter
Blocks signals only on weekends (Saturday & Sunday — market closed).
Scans run 24/7 Monday through Friday regardless of session time.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Weekday constants (Monday=0 ... Sunday=6)
_WEEKEND = {5, 6}  # Saturday=5, Sunday=6


class SessionFilter:
    """
    Allows signals any time Monday–Friday.
    Blocks signals on Saturday and Sunday (Forex market closed).
    """

    @staticmethod
    def is_active_session(now: datetime = None) -> bool:
        """Returns True on any weekday (Mon–Fri)."""
        if now is None:
            now = datetime.now(timezone.utc)
        return now.weekday() not in _WEEKEND

    @staticmethod
    def current_session(now: datetime = None) -> str:
        """Return WEEKDAY or WEEKEND."""
        if now is None:
            now = datetime.now(timezone.utc)
        return "WEEKEND" if now.weekday() in _WEEKEND else "WEEKDAY"

    def passes(self, symbol: str = "") -> tuple[bool, str]:
        """
        Allow any weekday scan regardless of hour.
        Block Saturday and Sunday.
        Returns (passed: bool, reason: str).
        """
        now = datetime.now(timezone.utc)
        day_name = now.strftime("%A")

        if now.weekday() in _WEEKEND:
            reason = f"weekend ({day_name}) — market closed"
            logger.info("Session filter BLOCKED: %s", reason)
            return False, reason

        logger.debug("Session filter PASSED: %s UTC %02d:%02d", day_name, now.hour, now.minute)
        return True, f"weekday ({day_name})"


# Module-level singleton
session_filter = SessionFilter()
