"""
ERICKsky Signal Engine - Correlation Filter (Upgrade 3)

Prevents sending two highly-correlated pair signals in the same direction
within a 2-hour window.  Avoids doubling risk on essentially the same move.

Correlation map (static, based on historical averages):
  EURUSD ↔ GBPUSD  85%
  AUDUSD ↔ XAUUSD  70%
  EURUSD ↔ AUDUSD  65%
"""

import logging
from typing import Tuple

from database.db_manager import db

logger = logging.getLogger(__name__)


class CorrelationFilter:
    """Block correlated pair signals that would double-up directional risk."""

    # (pair_a, pair_b, correlation_coefficient)
    CORRELATION_GROUPS = [
        ("EURUSD", "GBPUSD", 0.85),
        ("AUDUSD", "XAUUSD", 0.70),
        ("EURUSD", "AUDUSD", 0.65),
    ]

    def should_block(self, symbol: str, direction: str) -> Tuple[bool, str]:
        """
        Check whether a pending signal for *symbol* in *direction*
        conflicts with a recently-sent correlated-pair signal.

        Returns:
            (True, reason)   → block the new signal
            (False, reason)  → safe to proceed
        """
        try:
            # Fetch PENDING signals sent in the last 2 hours
            rows = db.execute(
                """
                SELECT pair, direction
                FROM signals
                WHERE status = 'PENDING'
                  AND created_at > NOW() - INTERVAL '2 hours'
                """,
            )
            recent_signals = {r["pair"]: r["direction"] for r in rows}
        except Exception as exc:
            logger.warning("CorrelationFilter DB query failed: %s – defaulting to PASS", exc)
            return False, "correlation filter unavailable"

        symbol = symbol.upper()

        for pair_a, pair_b, corr in self.CORRELATION_GROUPS:
            correlated_pair = None

            if symbol == pair_a and pair_b in recent_signals:
                correlated_pair = pair_b
            elif symbol == pair_b and pair_a in recent_signals:
                correlated_pair = pair_a

            if correlated_pair:
                other_dir = recent_signals[correlated_pair]
                if other_dir == direction:
                    reason = (
                        f"{symbol} correlates {corr * 100:.0f}% with "
                        f"{correlated_pair} (already {direction})"
                    )
                    logger.info("CORRELATION BLOCK %s: %s", symbol, reason)
                    return True, reason

        return False, "no correlation conflict"


# Module-level singleton (db is injected via import)
correlation_filter = CorrelationFilter()
