"""
ERICKsky Signal Engine - Session Filter (Institutional Grade)

Strict trading window enforcement:
  1. Block weekends (Saturday & Sunday — market closed)
  2. Block Asian session (21:00 UTC – 06:00 UTC) — low-volume false breakouts
  3. Only allow signal generation between 06:00 UTC and 18:00 UTC
     (9:00 AM – 9:00 PM EAT — London + NY overlap window)

Log: [Outside High-Liquidity Window: Scan Aborted]
"""

import logging
from datetime import datetime, timezone

from config import settings

logger = logging.getLogger(__name__)

# Weekday constants (Monday=0 ... Sunday=6)
_WEEKEND = {5, 6}  # Saturday=5, Sunday=6


class SessionFilter:
    """
    Institutional-grade session filter.
    Only allows signals during the high-liquidity London/NY window (06:00–18:00 UTC).
    Blocks weekends and Asian session entirely.
    """

    def is_active(self) -> tuple[bool, str]:
        """
        Check if bot should be active (weekday + session window check).
        Returns (is_active: bool, reason: str).
        """
        now = datetime.now(timezone.utc)

        if now.weekday() >= 5:
            logger.info(
                f"WEEKEND BLOCK: "
                f"{now.strftime('%A %Y-%m-%d %H:%M')} UTC"
                f" — no trading on weekends"
            )
            return False, "weekend - market closed"

        # Strict trading window check
        trading_start = getattr(settings, "STRICT_TRADING_START_UTC", 6)
        trading_end = getattr(settings, "STRICT_TRADING_END_UTC", 18)

        if not (trading_start <= now.hour < trading_end):
            reason = (
                f"[Outside High-Liquidity Window: Scan Aborted] "
                f"UTC {now.hour:02d}:{now.minute:02d} outside "
                f"{trading_start:02d}:00–{trading_end:02d}:00 window"
            )
            logger.info(reason)
            return False, reason

        return True, f"weekday ({now.strftime('%A')}) in trading window"

    @staticmethod
    def is_active_session(now: datetime = None) -> bool:
        """Returns True only during weekday high-liquidity hours."""
        if now is None:
            now = datetime.now(timezone.utc)
        if now.weekday() in _WEEKEND:
            return False
        trading_start = getattr(settings, "STRICT_TRADING_START_UTC", 6)
        trading_end = getattr(settings, "STRICT_TRADING_END_UTC", 18)
        return trading_start <= now.hour < trading_end

    @staticmethod
    def current_session(now: datetime = None) -> str:
        """Return session label based on current UTC hour."""
        if now is None:
            now = datetime.now(timezone.utc)
        if now.weekday() in _WEEKEND:
            return "WEEKEND"
        hour = now.hour
        asian_start = getattr(settings, "ASIAN_SESSION_START_UTC", 21)
        asian_end = getattr(settings, "ASIAN_SESSION_END_UTC", 6)
        if hour >= asian_start or hour < asian_end:
            return "ASIAN"
        trading_start = getattr(settings, "STRICT_TRADING_START_UTC", 6)
        trading_end = getattr(settings, "STRICT_TRADING_END_UTC", 18)
        if trading_start <= hour < trading_end:
            return "ACTIVE"
        return "OFF_HOURS"

    def passes(self, symbol: str = "") -> tuple[bool, str]:
        """
        Full session gate:
          1. Block weekends
          2. Block Asian session (21:00–06:00 UTC)
          3. Only allow 06:00–18:00 UTC window

        Returns (passed: bool, reason: str).
        """
        now = datetime.now(timezone.utc)
        day_name = now.strftime("%A")
        hour = now.hour

        # 1. Weekend block
        if now.weekday() in _WEEKEND:
            reason = f"weekend ({day_name}) — market closed"
            logger.info("Session filter BLOCKED: %s", reason)
            return False, reason

        # 2. Asian session block (21:00 UTC – 06:00 UTC)
        asian_start = getattr(settings, "ASIAN_SESSION_START_UTC", 21)
        asian_end = getattr(settings, "ASIAN_SESSION_END_UTC", 6)
        if hour >= asian_start or hour < asian_end:
            reason = (
                f"[Outside High-Liquidity Window: Scan Aborted] "
                f"Asian session ({day_name} {hour:02d}:{now.minute:02d} UTC) — "
                f"blocked to avoid low-volume false breakouts"
            )
            logger.info("Session filter BLOCKED: %s", reason)
            return False, reason

        # 3. Strict trading window (06:00 – 18:00 UTC)
        trading_start = getattr(settings, "STRICT_TRADING_START_UTC", 6)
        trading_end = getattr(settings, "STRICT_TRADING_END_UTC", 18)
        if not (trading_start <= hour < trading_end):
            reason = (
                f"[Outside High-Liquidity Window: Scan Aborted] "
                f"{day_name} {hour:02d}:{now.minute:02d} UTC — "
                f"outside {trading_start:02d}:00–{trading_end:02d}:00 window"
            )
            logger.info("Session filter BLOCKED: %s", reason)
            return False, reason

        logger.debug(
            "Session filter PASSED: %s UTC %02d:%02d (high-liquidity window)",
            day_name, hour, now.minute,
        )
        return True, f"weekday ({day_name}) in high-liquidity window"


# Module-level singleton
session_filter = SessionFilter()
