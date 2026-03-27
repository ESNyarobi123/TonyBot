"""
ERICKsky Signal Engine - M15 Entry Confirmation (Upgrade 4)

Never enter on an H1 signal alone.
Validates entry timing with M15 data using:
  - EMA 9/21 alignment
  - RSI position (oversold/overbought favored)
  - Candle body strength
  - Volume surge confirmation
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_CONFIRM_THRESHOLD = 50  # minimum score to mark CONFIRMED


class M15Confirmation:
    """Confirm or defer an H1 signal using M15 price action."""

    def confirm(self, df_m15: pd.DataFrame, direction: str, symbol: str) -> Dict:
        """
        Score M15 context for the given signal direction.

        Returns:
            dict with:
              confirmed  – bool
              score      – int (0-100)
              reasons    – list[str]
              rsi_m15    – float
              vol_ratio  – float
        """
        close  = df_m15["close"].values
        high   = df_m15["high"].values
        low    = df_m15["low"].values
        open_  = df_m15["open"].values
        volume = df_m15["volume"].values if "volume" in df_m15.columns else np.ones(len(close))

        ema9  = self._ema(close, 9)
        ema21 = self._ema(close, 21)

        current = float(close[-1])
        rsi     = self._rsi(close, 14)

        avg_vol   = float(np.mean(volume[-20:])) if len(volume) >= 20 else float(np.mean(volume))
        vol_ratio = float(volume[-1]) / (avg_vol + 1e-10)

        candle_range = float(high[-1] - low[-1])
        candle_body  = float(abs(close[-1] - open_[-1]))
        body_ratio   = candle_body / (candle_range + 1e-10)

        score: int     = 0
        reasons: List[str] = []

        if direction == "BUY":
            # EMA alignment
            if current > ema9[-1] > ema21[-1]:
                score += 35
                reasons.append("M15 EMA bullish alignment")
            elif current > ema9[-1]:
                score += 20
                reasons.append("M15 above EMA9")

            # RSI
            rsi_val = float(rsi[-1])
            if 40 <= rsi_val <= 65:
                score += 25
                reasons.append(f"RSI={rsi_val:.0f} bullish zone")
            elif rsi_val < 40:
                score += 35  # Oversold bounce
                reasons.append(f"RSI={rsi_val:.0f} oversold – bounce expected")

            # Candle body
            if close[-1] > open_[-1] and body_ratio > 0.6:
                score += 20
                reasons.append("Strong bullish candle body")

            # Volume
            if vol_ratio > 1.3:
                score += 20
                reasons.append(f"High volume ×{vol_ratio:.1f}")

        else:  # SELL
            # EMA alignment
            if current < ema9[-1] < ema21[-1]:
                score += 35
                reasons.append("M15 EMA bearish alignment")
            elif current < ema9[-1]:
                score += 20
                reasons.append("M15 below EMA9")

            # RSI
            rsi_val = float(rsi[-1])
            if 35 <= rsi_val <= 60:
                score += 25
                reasons.append(f"RSI={rsi_val:.0f} bearish zone")
            elif rsi_val > 60:
                score += 35  # Overbought
                reasons.append(f"RSI={rsi_val:.0f} overbought – drop expected")

            # Candle body
            if close[-1] < open_[-1] and body_ratio > 0.6:
                score += 20
                reasons.append("Strong bearish candle body")

            # Volume
            if vol_ratio > 1.3:
                score += 20
                reasons.append(f"High volume ×{vol_ratio:.1f}")

        confirmed = score >= _CONFIRM_THRESHOLD

        logger.info(
            "M15 Confirmation %s %s: score=%d confirmed=%s reasons=%s",
            symbol, direction, score, confirmed, reasons,
        )

        return {
            "confirmed":  confirmed,
            "score":      score,
            "reasons":    reasons,
            "rsi_m15":    float(rsi[-1]),
            "vol_ratio":  vol_ratio,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        return pd.Series(values).ewm(span=period, adjust=False).mean().values

    @staticmethod
    def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
        series = pd.Series(close)
        delta  = series.diff()
        gain   = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
        loss   = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
        rs     = gain / loss.replace(0, float("nan"))
        return (100 - (100 / (1 + rs))).values


    def confirm_sniper(
        self,
        m1_df: Optional[pd.DataFrame],
        m5_df: Optional[pd.DataFrame],
        direction: str,
        symbol: str,
    ) -> Dict:
        """
        Sniper entry confirmation: require a confirmed candle close in the
        signal direction on M1 or M5 before firing the Telegram alert.

        Checks the last fully-closed candle (iloc[-2]) on each timeframe.
        Returns confirmed=True if at least one timeframe agrees.

        Returns:
            dict with:
              confirmed     – bool  (True = alert may fire)
              m1_confirmed  – bool
              m5_confirmed  – bool
              confirming_tf – str | None  ("M1" | "M5" | None)
        """
        m1_ok = self._check_candle_close(m1_df, direction, "M1", symbol)
        m5_ok = self._check_candle_close(m5_df, direction, "M5", symbol)

        confirmed = m1_ok or m5_ok
        confirming_tf: Optional[str] = None
        if m1_ok:
            confirming_tf = "M1"
        elif m5_ok:
            confirming_tf = "M5"

        logger.info(
            "[Sniper Confirmation] %s %s → M1=%s M5=%s confirmed=%s",
            symbol, direction,
            "YES" if m1_ok else "no",
            "YES" if m5_ok else "no",
            confirmed,
        )

        return {
            "confirmed":     confirmed,
            "m1_confirmed":  m1_ok,
            "m5_confirmed":  m5_ok,
            "confirming_tf": confirming_tf,
        }

    def _check_candle_close(
        self,
        df: Optional[pd.DataFrame],
        direction: str,
        tf_label: str,
        symbol: str,
    ) -> bool:
        """
        Return True if the last confirmed closed candle on `df` closes
        in the signal direction.

        Uses iloc[-2] (second-to-last row) as the most recently CLOSED
        candle; iloc[-1] may still be forming.
        """
        if df is None or len(df) < 2:
            logger.debug(
                "[Sniper %s] %s — insufficient data (len=%d)",
                tf_label, symbol, 0 if df is None else len(df),
            )
            return False

        last_close = float(df["close"].iloc[-2])
        last_open  = float(df["open"].iloc[-2])

        if direction == "BUY":
            result = last_close > last_open
        else:
            result = last_close < last_open

        logger.info(
            "[Sniper %s] %s %s: open=%.5f close=%.5f → %s",
            tf_label, symbol, direction,
            last_open, last_close,
            "CONFIRMED" if result else "not confirmed",
        )
        return result


# Module-level singleton
m15_confirmation = M15Confirmation()
