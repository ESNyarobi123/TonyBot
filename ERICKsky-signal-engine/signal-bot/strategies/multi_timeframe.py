"""
ERICKsky Signal Engine - Strategy 1: Multi-Timeframe Analysis (MTF)

Top-down approach across three timeframes:
  D1  → Establish primary trend direction using EMA 50 and EMA 200
  H4  → Identify key support/resistance zones (last 3 swing points)
        and detect Bollinger Band squeeze breakouts
  H1  → Time entry with EMA 9/21 crossover, RSI, MACD histogram, volume

Scoring matrix:
  D1 trend + H4 zone + H1 entry all agree  → 100
  D1 + H4 agree, H1 partial                → 75
  D1 trend only                            → 50
  Conflicting signals                      → 0
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base_strategy import BaseStrategy, StrategyResult
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# Zone proximity: within 20 pips = "price is at the zone"
_ZONE_PROXIMITY_PIPS: int = 20


class MultiTimeframeStrategy(BaseStrategy):
    """
    Multi-Timeframe (MTF) confluence strategy.

    Implements a strict top-down flow:
    1. D1 must confirm a clear trend (not ranging)
    2. H4 must place price near a key support or resistance zone
       (or show a Bollinger squeeze breakout)
    3. H1 entry trigger must fire in the same direction
    """

    name = "MultiTimeframe"

    def analyze(
        self,
        symbol: str,
        data: Dict[str, Optional[pd.DataFrame]],
    ) -> StrategyResult:
        """Run the full MTF pipeline for the given symbol."""
        try:
            return self._run(symbol, data)
        except Exception as exc:
            logger.exception("MTF error for %s: %s", symbol, exc)
            return self._neutral_result(self.name, f"Error: {exc}")

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def _run(self, symbol: str, data: dict) -> StrategyResult:
        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)

        df_d1 = self._get_df(data, "D1")
        df_h4 = self._get_df(data, "H4")
        df_h1 = self._get_df(data, "H1")

        # ── STEP 1: D1 Trend Direction ────────────────────────────────────────
        d1_trend, d1_score = self._d1_trend(df_d1)

        if d1_trend == "RANGING":
            return StrategyResult(
                strategy_name=self.name,
                score=0,
                direction="NEUTRAL",
                confidence=0.0,
                reasoning="D1 price is ranging between EMA50/200 — no trade",
                metadata={"d1_trend": "RANGING", "h4_zone": "NONE", "h1_signal": "NONE"},
            )

        d1_direction = "BUY" if "UP" in d1_trend else "SELL"

        # ── STEP 2: H4 Zone ───────────────────────────────────────────────────
        h4_zone, h4_detail = self._h4_zone(df_h4, symbol, pip_size, d1_trend)

        # ── STEP 3: H1 Entry Trigger ──────────────────────────────────────────
        h1_signal, h1_detail = self._h1_entry(df_h1)

        # ── Scoring ───────────────────────────────────────────────────────────
        h4_aligns = (
            (h4_zone == "SUPPORT"    and d1_direction == "BUY")  or
            (h4_zone == "RESISTANCE" and d1_direction == "SELL") or
            (h4_zone == "BREAKOUT")
        )
        h1_aligns = h1_signal == d1_direction

        if h4_aligns and h1_aligns:
            raw_score  = 100
            confidence = 1.0
            reasoning  = (
                f"D1={d1_trend} → H4={h4_zone} → H1={h1_signal} "
                f"[full 3-TF confluence ✓]"
            )
        elif h4_aligns and not h1_aligns:
            raw_score  = 75
            confidence = 0.75
            reasoning  = (
                f"D1={d1_trend} + H4={h4_zone} aligned; "
                f"H1={h1_signal} not yet triggered"
            )
        elif not h4_aligns and h1_aligns:
            raw_score  = 50
            confidence = 0.50
            reasoning  = (
                f"D1={d1_trend} + H1={h1_signal}; "
                f"H4 price not at a key zone (H4={h4_zone})"
            )
        else:
            raw_score  = 0
            d1_direction = "NEUTRAL"
            confidence = 0.0
            reasoning  = (
                f"Conflicting: D1={d1_trend}, H4={h4_zone}, H1={h1_signal}"
            )

        # Scale by D1 strength (STRONG=100pts, WEAK=65pts → factor 0.65–1.0)
        final_score = int(raw_score * d1_score / 100)

        return StrategyResult(
            strategy_name=self.name,
            score=self._safe_score(final_score),
            direction=d1_direction,
            confidence=round(confidence, 2),
            reasoning=reasoning,
            metadata={
                "d1_trend":  d1_trend,
                "d1_score":  d1_score,
                "h4_zone":   h4_zone,
                "h4_detail": h4_detail,
                "h1_signal": h1_signal,
                "h1_detail": h1_detail,
            },
        )

    # ── STEP 1: D1 Trend ─────────────────────────────────────────────────────

    def _d1_trend(
        self, df: Optional[pd.DataFrame]
    ) -> Tuple[str, int]:
        """
        Classify daily trend using EMA 50 and EMA 200.

        Returns (trend_label, trend_strength_score).
          STRONG_UP   → price above both EMAs       → score 100
          WEAK_UP     → price above EMA50 only      → score 65
          STRONG_DOWN → price below both EMAs       → score 100
          WEAK_DOWN   → price below EMA50 only      → score 65
          RANGING     → price between EMAs          → score 0
        """
        if df is None or len(df) < 50:
            return "RANGING", 0

        close  = df["close"]
        ema50  = self._ema(close, 50)
        ema200 = self._ema(close, min(200, len(close) - 1))

        price = float(close.iloc[-1])
        e50   = float(ema50.iloc[-1])
        e200  = float(ema200.iloc[-1])

        if price > e50 and price > e200:
            return "STRONG_UP", 100
        if price > e50 and price < e200:
            return "WEAK_UP", 65
        if price < e50 and price < e200:
            return "STRONG_DOWN", 100
        if price < e50 and price > e200:
            return "WEAK_DOWN", 65
        return "RANGING", 0

    # ── STEP 2: H4 Zone ──────────────────────────────────────────────────────

    def _h4_zone(
        self,
        df: Optional[pd.DataFrame],
        symbol: str,
        pip_size: float,
        d1_trend: str,
    ) -> Tuple[str, dict]:
        """
        Identify whether price is at a key H4 zone.

        Algorithm:
        - Find last 3 swing highs and last 3 swing lows
        - Resistance = average of last 3 swing highs
        - Support    = average of last 3 swing lows
        - "At zone"  = within 20 pips of the level
        - Also detect Bollinger Band squeeze breakout
        """
        if df is None or len(df) < 30:
            return "NONE", {}

        close = df["close"]
        high  = df["high"]
        low   = df["low"]
        price = float(close.iloc[-1])

        # Swing points (local extremes over 5-bar window)
        swing_highs = self._swing_highs(high, window=5)
        swing_lows  = self._swing_lows(low,  window=5)

        resistance = float(np.mean(swing_highs[-3:])) if len(swing_highs) >= 1 else None
        support    = float(np.mean(swing_lows[-3:]))  if len(swing_lows)  >= 1 else None

        prox = _ZONE_PROXIMITY_PIPS * pip_size

        # Bollinger squeeze overrides zone logic
        bb_squeeze, bb_direction = self._bb_squeeze(close)
        detail: dict = {
            "support":       round(support,    5) if support    else None,
            "resistance":    round(resistance, 5) if resistance else None,
            "bb_squeeze":    bb_squeeze,
            "bb_direction":  bb_direction,
        }

        if bb_squeeze and bb_direction in ("UP", "DOWN"):
            return "BREAKOUT", detail

        # Zone proximity checks aligned with D1 trend
        if support and abs(price - support) <= prox:
            if "UP" in d1_trend:
                return "SUPPORT", detail

        if resistance and abs(price - resistance) <= prox:
            if "DOWN" in d1_trend:
                return "RESISTANCE", detail

        return "NONE", detail

    def _swing_highs(self, high: pd.Series, window: int = 5) -> List[float]:
        """Return list of swing high prices (local maxima)."""
        result = []
        arr = high.values
        for i in range(window, len(arr) - window):
            if arr[i] == arr[i - window: i + window + 1].max():
                result.append(float(arr[i]))
        return result

    def _swing_lows(self, low: pd.Series, window: int = 5) -> List[float]:
        """Return list of swing low prices (local minima)."""
        result = []
        arr = low.values
        for i in range(window, len(arr) - window):
            if arr[i] == arr[i - window: i + window + 1].min():
                result.append(float(arr[i]))
        return result

    def _bb_squeeze(
        self,
        close: pd.Series,
        period: int = 20,
        std_mult: float = 2.0,
    ) -> Tuple[bool, str]:
        """
        Detect Bollinger Band squeeze (band width < 0.5% of mid-band).
        Returns (is_squeeze, breakout_direction).
        Breakout direction is determined by whether price is above/below mid-band.
        """
        if len(close) < period + 5:
            return False, "NONE"

        sma   = close.rolling(period).mean()
        std   = close.rolling(period).std()
        upper = sma + std_mult * std
        lower = sma - std_mult * std
        width = (upper - lower) / sma.replace(0, np.nan)

        squeeze = bool(float(width.iloc[-1]) < 0.005)
        if not squeeze:
            return False, "NONE"

        direction = "UP" if float(close.iloc[-1]) > float(sma.iloc[-1]) else "DOWN"
        return True, direction

    # ── STEP 3: H1 Entry Trigger ──────────────────────────────────────────────

    def _h1_entry(
        self, df: Optional[pd.DataFrame]
    ) -> Tuple[str, dict]:
        """
        Detect H1 entry signal.

        Checks:
        - EMA 9 crosses above/below EMA 21
        - RSI confirmation (< 40 oversold → BUY, > 60 overbought → SELL)
        - MACD histogram direction
        - Volume above 20-period average = strong signal
        """
        if df is None or len(df) < 30:
            return "NONE", {}

        close  = df["close"]
        volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

        ema9  = self._ema(close, 9)
        ema21 = self._ema(close, 21)
        rsi   = self._rsi(close, 14)

        e9_curr  = float(ema9.iloc[-1])
        e21_curr = float(ema21.iloc[-1])
        e9_prev  = float(ema9.iloc[-2])
        e21_prev = float(ema21.iloc[-2])
        rsi_val  = float(rsi.iloc[-1]) if not rsi.empty else 50.0

        cross_buy  = e9_prev <= e21_prev and e9_curr > e21_curr
        cross_sell = e9_prev >= e21_prev and e9_curr < e21_curr
        above      = e9_curr > e21_curr
        below      = e9_curr < e21_curr

        macd_hist = self._macd_histogram(close)
        macd_bull = macd_hist is not None and macd_hist > 0
        macd_bear = macd_hist is not None and macd_hist < 0

        # Volume confirmation
        vol_strong = False
        if isinstance(volume, pd.Series) and len(volume) >= 21:
            vol_avg    = float(volume.rolling(20).mean().iloc[-1])
            vol_strong = bool(vol_avg > 0 and float(volume.iloc[-1]) > vol_avg * 1.5)

        buy_pts  = 0
        sell_pts = 0

        if cross_buy:
            buy_pts += 2      # fresh cross = stronger signal
        elif above:
            buy_pts += 1

        if cross_sell:
            sell_pts += 2
        elif below:
            sell_pts += 1

        if rsi_val < 40:
            buy_pts += 2      # oversold = BUY confirmation
        elif rsi_val > 60:
            sell_pts += 2
        elif 40 <= rsi_val <= 60:
            pass              # neutral RSI — no extra points

        if macd_bull:
            buy_pts += 1
        if macd_bear:
            sell_pts += 1

        if vol_strong:
            if buy_pts > sell_pts:
                buy_pts += 1
            elif sell_pts > buy_pts:
                sell_pts += 1

        detail = {
            "ema9":       round(e9_curr,  5),
            "ema21":      round(e21_curr, 5),
            "rsi":        round(rsi_val,  1),
            "macd_hist":  round(float(macd_hist), 6) if macd_hist else 0.0,
            "cross_buy":  cross_buy,
            "cross_sell": cross_sell,
            "vol_strong": vol_strong,
        }

        if buy_pts >= 2 and buy_pts > sell_pts:
            return "BUY", detail
        if sell_pts >= 2 and sell_pts > buy_pts:
            return "SELL", detail
        return "NONE", detail

    def _macd_histogram(
        self,
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Optional[float]:
        """Return the latest MACD histogram value, or None if insufficient data."""
        if len(close) < slow + signal:
            return None
        ema_fast    = self._ema(close, fast)
        ema_slow    = self._ema(close, slow)
        macd_line   = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        return float((macd_line - signal_line).iloc[-1])
