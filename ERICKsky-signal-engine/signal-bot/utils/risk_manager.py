"""
ERICKsky Signal Engine - Risk Manager (DISABLED)

Risk management has been disabled. The bot runs freely without
consecutive-loss limits, cooling-off periods, or daily caps.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class RiskManager:
    """Risk manager disabled — all signals are always allowed."""

    def check_limits(self, symbol: str) -> Tuple[bool, str]:
        """Always allow signals — no risk limits enforced."""
        return True, "within risk limits"


# Module-level singleton
risk_manager = RiskManager()
