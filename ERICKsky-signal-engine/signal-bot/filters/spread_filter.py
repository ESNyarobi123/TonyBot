"""
ERICKsky Signal Engine - Spread Filter
Blocks signals when the bid/ask spread is too wide (poor execution conditions).
"""

import logging
from typing import Dict, Optional

from config import settings

logger = logging.getLogger(__name__)

# Typical maximum acceptable spreads in pips per pair
DEFAULT_MAX_SPREADS: Dict[str, float] = {
    "EURUSD": 2.0,
    "GBPUSD": 2.5,
    "XAUUSD": 30.0,
    "AUDUSD": 2.0,  # NEW: Active pair, tight spread
    "USDCHF": 2.5,
    "USDCAD": 2.5,
    "NZDUSD": 3.0,
    "EURGBP": 2.5,
    "EURJPY": 2.5,
    "GBPJPY": 3.5,
}


class SpreadFilter:
    """
    Checks current spread against maximum allowed threshold.
    Falls back to permissive if spread data is unavailable.
    """

    def passes(
        self,
        symbol: str,
        current_spread_pips: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Check if the current spread is acceptable.

        Args:
            symbol:               Trading pair (e.g. "EURUSD")
            current_spread_pips:  Current spread in pips (None = use default check)

        Returns:
            (passed: bool, reason: str)
        """
        max_spread = DEFAULT_MAX_SPREADS.get(
            symbol.upper(), settings.MAX_SPREAD_PIPS
        )

        if current_spread_pips is None:
            # No live spread data available — use session-based heuristic
            # (spreads widen during off-hours; session filter already handles this)
            logger.debug(
                "Spread filter: no live spread for %s, defaulting to PASS", symbol
            )
            return True, "spread: no live data (defaulting to pass)"

        if current_spread_pips <= max_spread:
            logger.debug(
                "Spread filter PASSED: %s spread=%.1f pips (max=%.1f)",
                symbol, current_spread_pips, max_spread,
            )
            return True, f"spread {current_spread_pips:.1f} pips OK (max {max_spread:.1f})"

        reason = (
            f"spread too wide: {current_spread_pips:.1f} pips "
            f"(max allowed: {max_spread:.1f} pips)"
        )
        logger.info("Spread filter BLOCKED for %s: %s", symbol, reason)
        return False, reason

    @staticmethod
    def estimate_spread_from_ohlcv(
        symbol: str, bid: float, ask: float
    ) -> Optional[float]:
        """Convert bid/ask prices to spread in pips."""
        from config.settings import PIP_VALUES
        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)
        if pip_size == 0:
            return None
        return (ask - bid) / pip_size


# Module-level singleton
spread_filter = SpreadFilter()
