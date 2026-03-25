"""
ERICKsky Signal Engine - Market Regime Detector (Upgrade 1)

Classifies the current market condition into one of:
  TRENDING          → Allow trend signals
  WEAK_TREND        → Allow trend signals (lower confidence)
  VOLATILE_BREAKOUT → Allow signals (BB squeeze + ADX rising = breakout imminent)
  RANGING           → Block trend signals
  VOLATILE          → Block ALL signals (ATR spike detected)

Uses 4 methods:
  1. ADX (trend strength)
  2. Bollinger Band width (squeeze/expansion)
  3. Price range vs ATR ratio
  4. H4 EMA-50 slope direction
"""

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """Detect the current market regime before generating any signal."""

    def detect(self, df_h1: pd.DataFrame, df_h4: pd.DataFrame, symbol: str) -> Dict:
        """
        Analyse H1 and H4 data and return the market regime.

        Returns:
            dict with keys:
              regime       – "TRENDING" | "WEAK_TREND" | "RANGING" | "VOLATILE"
              confidence   – float 0.0-1.0
              adx          – current ADX value
              bb_squeeze   – bool
              range_ratio  – float
              reason       – human-readable explanation
              allow_signal – bool (False blocks the trade)
        """
        close_h1 = df_h1["close"].values
        high_h1  = df_h1["high"].values
        low_h1   = df_h1["low"].values

        # ── METHOD 1: ADX (Trend Strength) ────────────────────────
        adx = self._calculate_adx(df_h1, period=14)
        adx_prev = self._calculate_adx(df_h1.iloc[:-5], period=14) if len(df_h1) > 20 else adx
        adx_rising = adx > adx_prev

        # ── METHOD 2: Bollinger Band Width ───────────────────────────────────
        bb_width = self._calculate_bb_width(close_h1, period=20, std=2.0)
        if len(close_h1) > 30:
            historical_widths = [
                self._calculate_bb_width(close_h1[:i], 20, 2.0)
                for i in range(30, len(close_h1))
            ]
            avg_bb_width = float(np.mean(historical_widths)) if historical_widths else bb_width
        else:
            avg_bb_width = bb_width

        bb_squeeze   = bb_width < avg_bb_width * 0.8
        bb_expansion = bb_width > avg_bb_width * 1.3

        # ── METHOD 3: Price Range vs ATR ─────────────────────────────────────
        atr = self._calculate_atr(df_h1, 14)
        recent_range = max(high_h1[-20:]) - min(low_h1[-20:])
        range_ratio  = recent_range / (atr * 20 + 1e-10)

        # ── METHOD 4: H4 EMA-50 Slope ────────────────────────────────────────
        ema_50    = self._ema(df_h4["close"].values, 50)
        ema_slope = (ema_50[-1] - ema_50[-5]) / (ema_50[-5] + 1e-10) * 100

        # ── SCORING ──────────────────────────────────────────────────────────
        trend_score = 0

        if adx > 30:
            trend_score += 40
        elif adx > 25:
            trend_score += 25
        elif adx < 20:
            trend_score -= 20  # Ranging

        if not bb_squeeze:
            trend_score += 20
        else:
            trend_score -= 30  # Consolidating

        if range_ratio > 1.5:
            trend_score += 20
        elif range_ratio < 1.0:
            trend_score -= 20

        if abs(ema_slope) > 0.05:
            trend_score += 20  # Strong directional slope

        # ── VOLATILITY SPIKE CHECK ────────────────────────────────────────────
        tail_df = df_h1.tail(5)
        recent_atr     = self._calculate_atr(tail_df, min(5, len(tail_df)))
        volatility_score = 100 if recent_atr > atr * 2.0 else 0

        # ── REGIME DECISION ──────────────────────────────────
        if volatility_score >= 100:
            regime     = "VOLATILE"
            confidence = 0.0
            reason     = "ATR spike detected"

        elif trend_score >= 40:
            regime     = "TRENDING"
            confidence = min(trend_score / 100, 1.0)
            reason     = f"ADX={adx:.1f}, slope={ema_slope:.3f}"

        elif bb_squeeze and adx > 20 and adx_rising:
            # 4K Vision: ADX rising above 20 during BB squeeze = breakout imminent
            regime     = "VOLATILE_BREAKOUT"
            confidence = 0.6
            reason     = f"BB squeeze + ADX rising ({adx:.1f}> 20, prev={adx_prev:.1f}) → breakout imminent"

        elif trend_score <= 0 or bb_squeeze:
            regime     = "RANGING"
            confidence = 0.3
            reason     = f"BB squeeze={bb_squeeze}, ADX={adx:.1f}"

        else:
            regime     = "WEAK_TREND"
            confidence = 0.5
            reason     = "Moderate trend"

        logger.info(
            "Market Regime %s: %s | ADX=%.1f | BB_squeeze=%s | "
            "range_ratio=%.2f | reason=%s",
            symbol, regime, adx, bb_squeeze, range_ratio, reason,
        )

        return {
            "regime":       regime,
            "confidence":   confidence,
            "adx":          adx,
            "bb_squeeze":   bb_squeeze,
            "bb_expansion": bb_expansion,
            "range_ratio":  range_ratio,
            "ema_slope":    ema_slope,
            "reason":       reason,
            "allow_signal": regime in ("TRENDING", "WEAK_TREND", "VOLATILE_BREAKOUT"),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
        """Standard exponential-smoothed ADX calculation."""
        high  = df["high"].values
        low   = df["low"].values
        close = df["close"].values

        # True Range
        tr_list = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i]  - close[i - 1]),
            )
            tr_list.append(tr)

        atr_vals = pd.Series(tr_list).ewm(span=period, adjust=False).mean().values

        # Directional Movement
        dm_plus, dm_minus = [], []
        for i in range(1, len(high)):
            up   = high[i] - high[i - 1]
            down = low[i - 1] - low[i]
            dm_plus.append(up   if up   > down and up   > 0 else 0)
            dm_minus.append(down if down > up   and down > 0 else 0)

        dmp = pd.Series(dm_plus).ewm(span=period, adjust=False).mean().values
        dmm = pd.Series(dm_minus).ewm(span=period, adjust=False).mean().values

        di_plus  = 100 * dmp / (atr_vals + 1e-10)
        di_minus = 100 * dmm / (atr_vals + 1e-10)

        dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus + 1e-10)
        adx = pd.Series(dx).ewm(span=period, adjust=False).mean().values

        return float(adx[-1])

    @staticmethod
    def _calculate_bb_width(close: np.ndarray, period: int = 20, std: float = 2.0) -> float:
        """Bollinger Band width = (upper - lower) / middle."""
        if len(close) < period:
            return 0.01
        window   = close[-period:]
        mean     = float(np.mean(window))
        std_val  = float(np.std(window))
        upper    = mean + std * std_val
        lower    = mean - std * std_val
        return (upper - lower) / (mean + 1e-10)

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range as a single float."""
        if len(df) < 2:
            return 0.0
        high  = df["high"].values
        low   = df["low"].values
        close = df["close"].values
        tr_list = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i]  - close[i - 1]),
            )
            tr_list.append(tr)
        if not tr_list:
            return 0.0
        atr_series = pd.Series(tr_list).ewm(span=min(period, len(tr_list)), adjust=False).mean()
        return float(atr_series.iloc[-1])

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        return pd.Series(values).ewm(span=period, adjust=False).mean().values


# Module-level singleton
market_regime_detector = MarketRegimeDetector()
