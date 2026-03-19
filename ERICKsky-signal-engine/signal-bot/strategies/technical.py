"""
ERICKsky Signal Engine - Strategy 4: Technical Indicators

Uses four indicator groups on H1 data:
  1. Trend   — EMA 9/21/50/200 stack + fresh crossover detection
  2. Momentum— RSI 14 (oversold/overbought + bullish divergence)
                MACD (12,26,9) histogram direction + zero-line cross
  3. Volatility — ATR 14 (minimum thresholds per pair)
                  Bollinger Bands (20, 2.0) squeeze + band touch
  4. Volume  — tick-volume vs 20-period average; >1.5× = strong move

Scoring:
  EMA aligned + RSI extreme + MACD + volume  → 100
  EMA + RSI + MACD                           → 80
  EMA + RSI                                  → 60
  EMA only                                   → 40
  No alignment                               → 0
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base_strategy import BaseStrategy, StrategyResult
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# Minimum ATR in pips per symbol for the volatility filter
_MIN_ATR_PIPS: Dict[str, float] = {
    "EURUSD": 10.0,
    "GBPUSD": 12.0,
    "USDJPY": 10.0,
    "XAUUSD": 100.0,   # gold in 0.1 pip units
    "DEFAULT": 10.0,
}


class TechnicalStrategy(BaseStrategy):
    """
    Multi-indicator confluence strategy (H1 primary).

    Evaluates EMA stack, RSI with divergence, MACD histogram,
    ATR volatility gate, Bollinger Bands, and volume quality.
    Returns ATR in metadata for the consensus engine's SL/TP calculation.
    """

    name = "TechnicalIndicators"

    def analyze(
        self,
        symbol: str,
        data: Dict[str, Optional[pd.DataFrame]],
    ) -> StrategyResult:
        """Run the full technical analysis on H1 data."""
        try:
            return self._run(symbol, data)
        except Exception as exc:
            logger.exception("Technical error for %s: %s", symbol, exc)
            return self._neutral_result(self.name, f"Error: {exc}")

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def _run(self, symbol: str, data: dict) -> StrategyResult:
        df = self._get_df(data, "H1")
        if df is None:
            return self._neutral_result(self.name, "No H1 data")

        pip_size   = PIP_VALUES.get(symbol.upper(), 0.0001)
        min_atr_px = _MIN_ATR_PIPS.get(symbol.upper(), _MIN_ATR_PIPS["DEFAULT"]) * pip_size

        close  = df["close"]
        high   = df["high"]
        low    = df["low"]
        volume = df["volume"] if "volume" in df.columns else pd.Series(dtype=float)

        # ── INDICATOR 1: EMA Stack ─────────────────────────────────────────────
        ema_align, ema_score, ema_cross = self._ema_stack(close)

        # ── INDICATOR 2a: RSI ─────────────────────────────────────────────────
        rsi_val, rsi_signal, rsi_divergence = self._rsi_analysis(close, high, low)

        # ── INDICATOR 2b: MACD ────────────────────────────────────────────────
        macd_signal, macd_hist, macd_cross_zero = self._macd_analysis(close)

        # ── INDICATOR 3a: ATR (volatility gate) ───────────────────────────────
        atr_val = float(self._atr(df, 14).iloc[-1])
        atr_ok  = atr_val >= min_atr_px

        # ── INDICATOR 3b: Bollinger Bands ─────────────────────────────────────
        bb_signal, bb_squeeze = self._bollinger_analysis(close)

        # ── INDICATOR 4: Volume ───────────────────────────────────────────────
        vol_quality = self._volume_quality(volume)

        # ── Score accumulation ────────────────────────────────────────────────
        buy_score, sell_score = self._compute_scores(
            ema_align=ema_align,
            ema_score=ema_score,
            ema_cross=ema_cross,
            rsi_val=rsi_val,
            rsi_signal=rsi_signal,
            rsi_divergence=rsi_divergence,
            macd_signal=macd_signal,
            macd_cross_zero=macd_cross_zero,
            bb_signal=bb_signal,
            bb_squeeze=bb_squeeze,
            vol_quality=vol_quality,
            atr_ok=atr_ok,
        )

        # ── Direction decision ────────────────────────────────────────────────
        if not atr_ok:
            return StrategyResult(
                strategy_name=self.name,
                score=0,
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"ATR too low ({atr_val / pip_size:.1f} pips < minimum)",
                metadata={"atr": round(atr_val, 5), "rsi": round(rsi_val, 1),
                          "ema_alignment": ema_align, "volume_quality": vol_quality},
            )

        if buy_score > sell_score and buy_score >= 40:
            direction = "BUY"
            score     = buy_score
        elif sell_score > buy_score and sell_score >= 40:
            direction = "SELL"
            score     = sell_score
        else:
            direction = "NEUTRAL"
            score     = 0

        reasoning = (
            f"EMA={ema_align}(cross={ema_cross}) RSI={rsi_val:.0f}({rsi_signal}) "
            f"MACD={macd_signal}(x0={macd_cross_zero}) BB={bb_signal} "
            f"Vol={vol_quality} ATR={atr_val/pip_size:.0f}pips"
        )

        return StrategyResult(
            strategy_name=self.name,
            score=self._safe_score(score),
            direction=direction,
            confidence=round(min(score / 100, 1.0), 2),
            reasoning=reasoning,
            metadata={
                "atr":            round(atr_val, 5),
                "rsi":            round(rsi_val, 1),
                "macd_signal":    macd_signal,
                "ema_alignment":  ema_align,
                "volume_quality": vol_quality,
                "bb_squeeze":     bb_squeeze,
            },
        )

    # ── Score computation ─────────────────────────────────────────────────────

    def _compute_scores(
        self,
        ema_align: str, ema_score: int, ema_cross: bool,
        rsi_val: float, rsi_signal: str, rsi_divergence: bool,
        macd_signal: str, macd_cross_zero: bool,
        bb_signal: str, bb_squeeze: bool,
        vol_quality: str, atr_ok: bool,
    ) -> Tuple[int, int]:
        """Accumulate buy/sell scores from all indicator signals."""
        buy  = 0
        sell = 0

        # ── EMA Stack ─────────────────────────────────────────────────────────
        if ema_align in ("STRONG_UP", "WEAK_UP"):
            buy  += ema_score
        elif ema_align in ("STRONG_DOWN", "WEAK_DOWN"):
            sell += ema_score

        if ema_cross:   # fresh crossover = extra +20
            if ema_align in ("STRONG_UP", "WEAK_UP"):
                buy  += 20
            else:
                sell += 20

        # ── RSI ───────────────────────────────────────────────────────────────
        if rsi_signal == "OVERSOLD":
            buy  += 20    # < 30
        elif rsi_signal == "BULL_BUILDING":
            buy  += 10    # 30–45
        elif rsi_signal == "OVERBOUGHT":
            sell += 20    # > 70
        elif rsi_signal == "BEAR_BUILDING":
            sell += 10    # 55–70

        if rsi_divergence:
            buy  += 30    # bullish divergence = high-value signal

        # ── MACD ──────────────────────────────────────────────────────────────
        if macd_signal == "BUY":
            buy  += 15
        elif macd_signal == "SELL":
            sell += 15

        if macd_cross_zero:           # histogram crossing zero = entry trigger
            if macd_signal == "BUY":
                buy  += 10
            else:
                sell += 10

        # ── Bollinger Bands ───────────────────────────────────────────────────
        if bb_signal == "BUY":
            buy  += 15    # price at lower band + RSI < 40
        elif bb_signal == "SELL":
            sell += 15    # price at upper band + RSI > 60

        # ── Volume quality ────────────────────────────────────────────────────
        if vol_quality == "HIGH":
            if buy > sell:
                buy  += 10
            else:
                sell += 10

        return min(100, buy), min(100, sell)

    # ── INDICATOR 1: EMA Stack ────────────────────────────────────────────────

    def _ema_stack(
        self,
        close: pd.Series,
    ) -> Tuple[str, int, bool]:
        """
        Analyse EMA 9/21/50/200 stack on H1.

        Scoring:
          EMA9 > EMA21 > EMA50 (above EMA200)  → STRONG_UP   score=100
          EMA9 > EMA21 only                    → WEAK_UP     score=60
          EMA9 < EMA21 < EMA50                 → STRONG_DOWN score=100
          EMA9 < EMA21 only                    → WEAK_DOWN   score=60
          Mixed                                → NEUTRAL     score=0

        Also detects fresh EMA9/EMA21 crossover in last 2 bars.
        Price > EMA200 = bullish bias applied.
        """
        n = len(close)
        ema9  = self._ema(close, 9)
        ema21 = self._ema(close, 21)
        ema50 = self._ema(close, 50)
        ema200 = self._ema(close, min(200, n - 1))

        e9   = float(ema9.iloc[-1]);  e9p  = float(ema9.iloc[-2])
        e21  = float(ema21.iloc[-1]); e21p = float(ema21.iloc[-2])
        e50  = float(ema50.iloc[-1])
        e200 = float(ema200.iloc[-1])
        pr   = float(close.iloc[-1])

        above_200 = pr > e200
        fresh_cross = (e9p <= e21p and e9 > e21) or (e9p >= e21p and e9 < e21)

        if e9 > e21 > e50 and above_200:
            return "STRONG_UP", 100, fresh_cross
        if e9 > e21 > e50:
            return "WEAK_UP", 80, fresh_cross
        if e9 > e21 and above_200:
            return "WEAK_UP", 60, fresh_cross
        if e9 > e21:
            return "WEAK_UP", 50, fresh_cross
        if e9 < e21 < e50 and not above_200:
            return "STRONG_DOWN", 100, fresh_cross
        if e9 < e21 < e50:
            return "WEAK_DOWN", 80, fresh_cross
        if e9 < e21 and not above_200:
            return "WEAK_DOWN", 60, fresh_cross
        if e9 < e21:
            return "WEAK_DOWN", 50, fresh_cross
        return "NEUTRAL", 0, False

    # ── INDICATOR 2a: RSI with Divergence ─────────────────────────────────────

    def _rsi_analysis(
        self,
        close: pd.Series,
        high: pd.Series,
        low: pd.Series,
        period: int = 14,
        lookback: int = 20,
    ) -> Tuple[float, str, bool]:
        """
        RSI 14 analysis with bullish divergence detection.

        Signals:
          < 30 → OVERSOLD       (BUY)
          30–45→ BULL_BUILDING  (mild BUY)
          45–55→ NEUTRAL
          55–70→ BEAR_BUILDING  (mild SELL)
          > 70 → OVERBOUGHT     (SELL)

        Divergence:
          Price makes new low in last lookback bars,
          RSI makes a higher low → BULLISH DIVERGENCE (+30 score bonus).
        """
        rsi    = self._rsi(close, period)
        rsi_now = float(rsi.iloc[-1]) if not rsi.empty else 50.0

        if rsi_now < 30:
            signal = "OVERSOLD"
        elif rsi_now < 45:
            signal = "BULL_BUILDING"
        elif rsi_now > 70:
            signal = "OVERBOUGHT"
        elif rsi_now > 55:
            signal = "BEAR_BUILDING"
        else:
            signal = "NEUTRAL"

        # Bullish divergence: price new low, RSI higher low
        divergence = False
        if len(close) >= lookback + 5 and len(rsi) >= lookback + 5:
            price_window = low.values[-lookback:]
            rsi_window   = rsi.values[-lookback:]
            price_min_idx = int(np.argmin(price_window))
            prev_min_idx  = int(np.argmin(price_window[:-5])) if lookback > 5 else 0

            if (price_min_idx > prev_min_idx
                    and price_window[price_min_idx] < price_window[prev_min_idx]
                    and rsi_window[price_min_idx]   > rsi_window[prev_min_idx]):
                divergence = True
                logger.debug("Bullish RSI divergence detected")

        return rsi_now, signal, divergence

    # ── INDICATOR 2b: MACD ────────────────────────────────────────────────────

    def _macd_analysis(
        self,
        close: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[str, float, bool]:
        """
        MACD (12,26,9) on H1.

        Returns (signal: BUY|SELL|NEUTRAL, histogram_value, crossed_zero).
        - Histogram > 0 and growing      → BUY momentum increasing
        - Histogram crosses zero (+)     → fresh BUY trigger
        - Histogram < 0 and falling      → SELL momentum increasing
        - Histogram crosses zero (-)     → fresh SELL trigger
        """
        if len(close) < slow + signal:
            return "NEUTRAL", 0.0, False

        ema_fast    = self._ema(close, fast)
        ema_slow    = self._ema(close, slow)
        macd_line   = ema_fast - ema_slow
        sig_line    = self._ema(macd_line, signal)
        hist        = macd_line - sig_line

        h_now  = float(hist.iloc[-1])
        h_prev = float(hist.iloc[-2]) if len(hist) > 1 else h_now

        cross_zero = (h_prev <= 0 < h_now) or (h_prev >= 0 > h_now)

        if h_now > 0:
            direction = "BUY"
        elif h_now < 0:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        return direction, h_now, cross_zero

    # ── INDICATOR 3b: Bollinger Bands ─────────────────────────────────────────

    def _bollinger_analysis(
        self,
        close: pd.Series,
        period: int = 20,
        std_mult: float = 2.0,
    ) -> Tuple[str, bool]:
        """
        Bollinger Bands (20, 2.0) on H1.

        Signals:
          Price ≤ lower band + RSI < 40  → BUY
          Price ≥ upper band + RSI > 60  → SELL
          Band width < 1% of mid         → squeeze = breakout incoming

        Returns (signal: BUY|SELL|NEUTRAL, is_squeeze).
        """
        if len(close) < period + 2:
            return "NEUTRAL", False

        sma   = close.rolling(period).mean()
        std   = close.rolling(period).std()
        upper = sma + std_mult * std
        lower = sma - std_mult * std
        mid   = sma

        price    = float(close.iloc[-1])
        upper_v  = float(upper.iloc[-1])
        lower_v  = float(lower.iloc[-1])
        _mid_raw = float(mid.iloc[-1])
        mid_v    = _mid_raw if _mid_raw != 0 else 1.0

        width    = (upper_v - lower_v) / mid_v if mid_v != 0 else 0
        squeeze  = width < 0.01

        rsi = self._rsi(close, 14)
        rsi_now = float(rsi.iloc[-1]) if not rsi.empty else 50.0

        if price <= lower_v and rsi_now < 40:
            return "BUY", squeeze
        if price >= upper_v and rsi_now > 60:
            return "SELL", squeeze
        return "NEUTRAL", squeeze

    # ── INDICATOR 4: Volume ───────────────────────────────────────────────────

    def _volume_quality(
        self,
        volume: pd.Series,
        period: int = 20,
        high_mult: float = 1.5,
        low_mult: float = 0.7,
    ) -> str:
        """
        Classify volume quality vs 20-period average.
          > 1.5× average → HIGH   (strong move confirmation)
          < 0.7× average → LOW    (weak, treat signal with caution)
          else           → MEDIUM
        """
        if not isinstance(volume, pd.Series) or len(volume) < period + 1:
            return "MEDIUM"

        vol_avg = float(volume.rolling(period).mean().iloc[-1])
        if vol_avg <= 0:
            return "MEDIUM"

        ratio = float(volume.iloc[-1]) / vol_avg
        if ratio >= high_mult:
            return "HIGH"
        if ratio <= low_mult:
            return "LOW"
        return "MEDIUM"
