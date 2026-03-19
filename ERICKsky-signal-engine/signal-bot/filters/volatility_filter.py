"""
ERICKsky Signal Engine - Volatility Filter
Blocks signals when ATR is below minimum threshold (market is too quiet).
"""

import logging
from typing import Optional

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

# Minimum ATR in pips per symbol
MIN_ATR_PIPS: dict = {
    "EURUSD": 5.0,
    "GBPUSD": 7.0,
    "USDJPY": 5.0,
    "XAUUSD": 50.0,
    "USDCHF": 5.0,
    "AUDUSD": 5.0,
    "USDCAD": 5.0,
    "NZDUSD": 4.0,
}


class VolatilityFilter:
    """
    Ensures the market has enough volatility for clean trade execution.
    Uses the 14-period ATR on the primary timeframe.
    """

    def passes(
        self,
        symbol: str,
        df: Optional[pd.DataFrame] = None,
    ) -> tuple[bool, str]:
        """
        Check if ATR meets minimum requirement.

        Args:
            symbol: Trading pair
            df:     OHLCV DataFrame on primary timeframe

        Returns:
            (passed: bool, reason: str)
        """
        if df is None or df.empty or len(df) < 15:
            logger.debug(
                "Volatility filter: no data for %s, defaulting to PASS", symbol
            )
            return True, "volatility: no data (defaulting to pass)"

        atr_series = self._atr(df, period=14)
        if atr_series is None or atr_series.empty:
            return True, "volatility: ATR calc failed (defaulting to pass)"

        current_atr = atr_series.iloc[-1]
        if pd.isna(current_atr) or current_atr == 0:
            return True, "volatility: ATR is zero (defaulting to pass)"

        # Convert ATR from price units to pips
        from config.settings import PIP_VALUES
        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)
        atr_pips = current_atr / pip_size

        min_atr = MIN_ATR_PIPS.get(symbol.upper(), settings.MIN_ATR_PIPS)

        if atr_pips >= min_atr:
            logger.debug(
                "Volatility filter PASSED: %s ATR=%.1f pips (min=%.1f)",
                symbol, atr_pips, min_atr,
            )
            return True, f"ATR={atr_pips:.1f} pips OK (min {min_atr:.1f})"

        reason = (
            f"volatility too low: ATR={atr_pips:.1f} pips "
            f"(min required: {min_atr:.1f} pips)"
        )
        logger.info("Volatility filter BLOCKED for %s: %s", symbol, reason)
        return False, reason

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> Optional[pd.Series]:
        try:
            high = df["high"]
            low = df["low"]
            prev_close = df["close"].shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ], axis=1).max(axis=1)
            return tr.ewm(span=period, adjust=False).mean()
        except Exception as exc:
            logger.warning("ATR calculation failed: %s", exc)
            return None


# Module-level singleton
volatility_filter = VolatilityFilter()
