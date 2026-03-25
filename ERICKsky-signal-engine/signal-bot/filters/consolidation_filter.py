"""
ERICKsky Signal Engine - Consolidation Filter (Upgrade 2)

Works alongside the Market Regime Detector for extra precision.
Detects when price is stuck in a tight consolidation zone and
blocks trend signals to avoid false breakouts.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ConsolidationFilter:
    """Detect tight consolidation zones to avoid false-breakout signals."""

    LOOKBACK = 20  # candles to examine

    # Per-symbol ratio thresholds (below this = consolidating)
    _RATIO_THRESHOLD: Dict[str, float] = {
        "XAUUSD": 0.92,  # Relaxed for Gold — wider ranges are normal
    }
    _DEFAULT_RATIO_THRESHOLD: float = 1.1

    def is_consolidating(self, df_h1: pd.DataFrame, symbol: str) -> Tuple[bool, str]:
        """
        Determine whether price is currently consolidating.

        Returns:
            (True, reason_str)  → block signal
            (False, reason_str) → allow signal
        """
        close = df_h1["close"].values
        high  = df_h1["high"].values
        low   = df_h1["low"].values

        lb = self.LOOKBACK

        # ── Range analysis ────────────────────────────────────────────────────
        recent_high = float(max(high[-lb:]))
        recent_low  = float(min(low[-lb:]))
        price_range = recent_high - recent_low

        # Mean True Range over the same lookback
        tr_vals = []
        start   = max(1, len(close) - lb)
        for i in range(start, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i]  - close[i - 1]),
            )
            tr_vals.append(tr)

        atr = float(pd.Series(tr_vals).mean()) if tr_vals else 0.001

        # Expected range for a trending market = ATR × lookback × 0.4
        expected = atr * lb * 0.4
        ratio    = price_range / (expected + 1e-10)

        # ── Bollinger Band squeeze ─────────────────────────────────────────────
        bb_std   = float(np.std(close[-lb:]))
        bb_mean  = float(np.mean(close[-lb:]))
        bb_width = (bb_std * 4) / (bb_mean + 1e-10)

        # ── Decision logic ────────────────────────────────────────────────────
        ratio_threshold = self._RATIO_THRESHOLD.get(symbol.upper(), self._DEFAULT_RATIO_THRESHOLD)
        is_tight_range = ratio < ratio_threshold
        is_bb_squeeze  = bb_width < 0.004

        current     = float(close[-1])
        zone_center = (recent_high + recent_low) / 2
        near_center = (
            abs(current - zone_center) / (price_range + 1e-10) < 0.3
        )

        if is_tight_range and is_bb_squeeze:
            reason = (
                f"Tight consolidation: range={price_range:.5f}, "
                f"ratio={ratio:.2f}, BB_width={bb_width:.4f}"
            )
            logger.info("CONSOLIDATION %s: %s", symbol, reason)
            return True, reason

        if is_tight_range and near_center:
            reason = f"Price in consolidation center: ratio={ratio:.2f}"
            logger.info("CONSOLIDATION %s: %s", symbol, reason)
            return True, reason

        return False, f"trending ratio={ratio:.2f}"


# Module-level singleton
consolidation_filter = ConsolidationFilter()
