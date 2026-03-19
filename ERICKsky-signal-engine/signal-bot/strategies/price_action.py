"""
ERICKsky Signal Engine - Strategy 3: Price Action + Key Levels

Four components:
  1. Dynamic Support/Resistance — swing points clustered within 15 pips,
     scored by touch count; S/R flip zones treated as strongest
  2. Candlestick Patterns (H1) — exact wick/body ratios for Hammer,
     Shooting Star, Bullish/Bearish Engulfing, Morning/Evening Star, Pin Bar
  3. Breakout + Retest — monitors strong levels (3+ touches), detects
     close-beyond break, then retest within 5 candles
  4. Trendline Detection — linear regression through last 3 swing lows/highs

Scoring:
  Strong level + pattern + breakout retest  → 100
  Strong level + pattern                   → 80
  Pattern at level                         → 65
  Pattern only                             → 40
  No setup                                 → 0
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base_strategy import BaseStrategy, StrategyResult
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# Configuration constants
_SR_LOOKBACK_CANDLES: int = 100    # H4 lookback for S/R levels
_CLUSTER_PIPS:        int = 15     # pips to cluster into single zone
_AT_LEVEL_PIPS:       int = 10     # pips = "price is at the level"
_BREAK_PIPS:          int = 5      # pips beyond level = valid breakout
_RETEST_PIPS:         int = 8      # pips tolerance for retest
_RETEST_MAX_CANDLES:  int = 5      # max candles after break to retest
_STRONG_LEVEL_TOUCHES: int = 3     # min touches to classify as "strong"


@dataclass
class _SRLevel:
    price:    float
    touches:  int
    is_flip:  bool = False     # former S flipped to R or vice-versa
    zone_type: str = "UNKNOWN" # SUPPORT | RESISTANCE


class PriceActionStrategy(BaseStrategy):
    """
    Price Action strategy: dynamic S/R + candlestick patterns +
    breakout/retest + trendline detection.
    """

    name = "PriceAction"

    def analyze(
        self,
        symbol: str,
        data: Dict[str, Optional[pd.DataFrame]],
    ) -> StrategyResult:
        """Run the full PA analysis pipeline."""
        try:
            return self._run(symbol, data)
        except Exception as exc:
            logger.exception("PA error for %s: %s", symbol, exc)
            return self._neutral_result(self.name, f"Error: {exc}")

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def _run(self, symbol: str, data: dict) -> StrategyResult:
        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)

        df_h4 = self._get_df(data, "H4")   # S/R levels source
        df_h1 = self._get_df(data, "H1")   # pattern + breakout source

        if df_h1 is None:
            return self._neutral_result(self.name, "No H1 data")

        price = float(df_h1["close"].iloc[-1])

        # ── COMPONENT 1: Dynamic S/R Levels (H4) ──────────────────────────────
        sr_df       = df_h4 if df_h4 is not None else df_h1
        levels      = self._build_sr_levels(sr_df, pip_size)
        nearest_sup = self._nearest_level(levels, price, "SUPPORT",    pip_size)
        nearest_res = self._nearest_level(levels, price, "RESISTANCE", pip_size)
        at_support  = nearest_sup is not None and abs(price - nearest_sup.price) <= _AT_LEVEL_PIPS * pip_size
        at_resist   = nearest_res is not None and abs(price - nearest_res.price) <= _AT_LEVEL_PIPS * pip_size
        strong_sup  = at_support  and (nearest_sup.touches  >= _STRONG_LEVEL_TOUCHES or nearest_sup.is_flip)
        strong_res  = at_resist   and (nearest_res.touches >= _STRONG_LEVEL_TOUCHES or nearest_res.is_flip)

        # ── COMPONENT 2: Candlestick Patterns (H1) ───────────────────────────
        pattern, pattern_dir = self._detect_patterns(df_h1, pip_size)

        # ── COMPONENT 3: Breakout + Retest (H1) ──────────────────────────────
        bo_retest, bo_dir = self._detect_breakout_retest(df_h1, levels, pip_size)

        # ── COMPONENT 4: Trendline (H1) ──────────────────────────────────────
        tl_dir = self._trendline_direction(df_h1)

        # ── Scoring ───────────────────────────────────────────────────────────
        buy_score, sell_score = self._score(
            strong_sup=strong_sup, strong_res=strong_res,
            pattern=pattern, pattern_dir=pattern_dir,
            bo_retest=bo_retest, bo_dir=bo_dir,
            tl_dir=tl_dir,
        )

        if buy_score > sell_score and buy_score >= 40:
            direction = "BUY"
            score     = buy_score
            reasoning = (
                f"StrongSup={strong_sup} Pattern={pattern}({pattern_dir}) "
                f"BORtest={bo_retest}({bo_dir}) TL={tl_dir}"
            )
        elif sell_score > buy_score and sell_score >= 40:
            direction = "SELL"
            score     = sell_score
            reasoning = (
                f"StrongRes={strong_res} Pattern={pattern}({pattern_dir}) "
                f"BORtest={bo_retest}({bo_dir}) TL={tl_dir}"
            )
        else:
            direction = "NEUTRAL"
            score     = 0
            reasoning = f"No PA setup. Pattern={pattern} TL={tl_dir}"

        return StrategyResult(
            strategy_name=self.name,
            score=self._safe_score(score),
            direction=direction,
            confidence=round(min(score / 100, 1.0), 2),
            reasoning=reasoning,
            metadata={
                "key_level":         nearest_sup.price if (direction == "BUY"  and nearest_sup) else
                                     (nearest_res.price if (direction == "SELL" and nearest_res) else None),
                "pattern":           pattern,
                "breakout_retest":   bo_retest,
                "nearest_support":   round(nearest_sup.price,  5) if nearest_sup else None,
                "nearest_resistance":round(nearest_res.price, 5) if nearest_res else None,
            },
        )

    # ── Scoring helper ────────────────────────────────────────────────────────

    def _score(
        self,
        strong_sup: bool, strong_res: bool,
        pattern: str, pattern_dir: str,
        bo_retest: bool, bo_dir: str,
        tl_dir: str,
    ) -> Tuple[int, int]:
        """Return (buy_score, sell_score) based on component signals."""
        buy  = 0
        sell = 0

        # Breakout + retest (highest priority)
        if bo_retest and bo_dir == "BUY":
            buy  += 50
        elif bo_retest and bo_dir == "SELL":
            sell += 50

        # Strong level + pattern
        if strong_sup and pattern_dir == "BUY":
            buy  += 35
        elif strong_sup:
            buy  += 20

        if strong_res and pattern_dir == "SELL":
            sell += 35
        elif strong_res:
            sell += 20

        # Pattern alone
        if pattern_dir == "BUY"  and not strong_sup:
            buy  += 20
        if pattern_dir == "SELL" and not strong_res:
            sell += 20

        # Trendline direction
        if tl_dir == "UP":
            buy  += 10
        elif tl_dir == "DOWN":
            sell += 10

        return min(100, buy), min(100, sell)

    # ── COMPONENT 1: Dynamic S/R Levels ──────────────────────────────────────

    def _build_sr_levels(
        self,
        df: pd.DataFrame,
        pip_size: float,
    ) -> List[_SRLevel]:
        """
        Build clustered S/R levels from last _SR_LOOKBACK_CANDLES H4 candles.

        Algorithm:
        1. Find all swing highs (resistance) and swing lows (support)
        2. Cluster pivots within _CLUSTER_PIPS into a single zone
        3. Score each zone by number of touches
        4. Flag S/R flips (former support now acting as resistance or vice versa)
        """
        n    = min(_SR_LOOKBACK_CANDLES, len(df))
        sub  = df.tail(n)
        h    = sub["high"].values
        l    = sub["low"].values
        c    = sub["close"].values
        prox = _CLUSTER_PIPS * pip_size

        raw_highs: List[float] = []
        raw_lows:  List[float] = []

        for i in range(2, n - 2):
            if h[i] == max(h[max(0, i-2):i+3]):
                raw_highs.append(float(h[i]))
            if l[i] == min(l[max(0, i-2):i+3]):
                raw_lows.append(float(l[i]))

        def cluster(prices: List[float]) -> List[Tuple[float, int]]:
            if not prices:
                return []
            prices = sorted(prices)
            zones: List[Tuple[float, int]] = []
            group = [prices[0]]
            for p in prices[1:]:
                if p - group[-1] <= prox:
                    group.append(p)
                else:
                    zones.append((float(np.mean(group)), len(group)))
                    group = [p]
            zones.append((float(np.mean(group)), len(group)))
            return zones

        support_zones    = cluster(raw_lows)
        resistance_zones = cluster(raw_highs)
        price_now        = float(c[-1])

        levels: List[_SRLevel] = []

        for lvl, touches in support_zones:
            # S/R flip: was resistance, now below price (acting as support)
            is_flip = any(abs(lvl - r) <= prox for r, _ in resistance_zones)
            levels.append(_SRLevel(
                price=lvl, touches=touches, is_flip=is_flip, zone_type="SUPPORT"
            ))

        for lvl, touches in resistance_zones:
            is_flip = any(abs(lvl - s) <= prox for s, _ in support_zones)
            levels.append(_SRLevel(
                price=lvl, touches=touches, is_flip=is_flip, zone_type="RESISTANCE"
            ))

        return levels

    def _nearest_level(
        self,
        levels: List[_SRLevel],
        price: float,
        zone_type: str,
        pip_size: float,
        max_pips: int = 50,
    ) -> Optional[_SRLevel]:
        """Return nearest S/R level of the given type within max_pips."""
        candidates = [
            lv for lv in levels
            if lv.zone_type == zone_type
            and abs(price - lv.price) <= max_pips * pip_size
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda lv: abs(price - lv.price))

    # ── COMPONENT 2: Candlestick Patterns ─────────────────────────────────────

    def _detect_patterns(
        self,
        df: pd.DataFrame,
        pip_size: float,
    ) -> Tuple[str, str]:
        """
        Detect H1 candlestick patterns using exact wick/body ratio rules.
        Returns (pattern_name, direction).

        Bullish patterns:
          Hammer      — lower wick > 2× body, upper wick < 0.3× body, body in upper 30%
          Pin Bar     — same as Hammer
          Bull Engulf — green body fully engulfs previous red body
          Morning Star— [red][small][green closing above red midpoint]

        Bearish patterns:
          Shooting Star — upper wick > 2× body, lower wick < 0.3× body
          Pin Bar Bear  — upper wick version of hammer
          Bear Engulf   — red body fully engulfs previous green body
          Evening Star  — opposite of morning star
        """
        if len(df) < 3:
            return "NONE", "NEUTRAL"

        c0 = df.iloc[-1]   # current (most recent)
        c1 = df.iloc[-2]   # previous
        c2 = df.iloc[-3]   # two bars ago

        o0, h0, l0, c0v = float(c0["open"]), float(c0["high"]), float(c0["low"]),  float(c0["close"])
        o1, h1, l1, c1v = float(c1["open"]), float(c1["high"]), float(c1["low"]),  float(c1["close"])
        o2, h2, l2, c2v = float(c2["open"]), float(c2["high"]), float(c2["low"]),  float(c2["close"])

        body0  = abs(c0v - o0)
        rng0   = h0 - l0
        upper0 = h0 - max(o0, c0v)
        lower0 = min(o0, c0v) - l0

        if rng0 < pip_size:       # micro-candle — skip
            return "NONE", "NEUTRAL"

        # ── Bullish Engulfing ─────────────────────────────────────────────────
        if (c1v < o1 and c0v > o0                   # prev red, curr green
                and c0v > o1 and o0 < c1v):         # curr body engulfs prev body
            return "BULLISH_ENGULFING", "BUY"

        # ── Bearish Engulfing ─────────────────────────────────────────────────
        if (c1v > o1 and c0v < o0                   # prev green, curr red
                and c0v < o1 and o0 > c1v):         # curr body engulfs prev body
            return "BEARISH_ENGULFING", "SELL"

        # ── Hammer / Bullish Pin Bar ──────────────────────────────────────────
        # lower wick > 2× body, upper wick < 0.3× body, body in upper 30% of range
        if (body0 > 0
                and lower0 > 2 * body0
                and upper0 < 0.3 * body0
                and (c0v - l0) / rng0 >= 0.7):      # body in top 30% of range
            return "HAMMER", "BUY"

        # ── Shooting Star / Bearish Pin Bar ───────────────────────────────────
        if (body0 > 0
                and upper0 > 2 * body0
                and lower0 < 0.3 * body0
                and (h0 - c0v) / rng0 >= 0.7):
            return "SHOOTING_STAR", "SELL"

        # ── Morning Star (3-candle bullish reversal) ──────────────────────────
        body1 = abs(c1v - o1)
        body2 = abs(c2v - o2)
        ms_c1_red   = c2v < o2                            # first candle red
        ms_c2_small = body1 < body2 * 0.3                # second candle small body
        ms_c3_green = c0v > o0                            # third candle green
        ms_c3_above = c0v > (o2 + c2v) / 2               # closes above midpoint of first
        if ms_c1_red and ms_c2_small and ms_c3_green and ms_c3_above:
            return "MORNING_STAR", "BUY"

        # ── Evening Star (3-candle bearish reversal) ──────────────────────────
        es_c1_green = c2v > o2
        es_c2_small = body1 < body2 * 0.3
        es_c3_red   = c0v < o0
        es_c3_below = c0v < (o2 + c2v) / 2
        if es_c1_green and es_c2_small and es_c3_red and es_c3_below:
            return "EVENING_STAR", "SELL"

        return "NONE", "NEUTRAL"

    # ── COMPONENT 3: Breakout + Retest ───────────────────────────────────────

    def _detect_breakout_retest(
        self,
        df: pd.DataFrame,
        levels: List[_SRLevel],
        pip_size: float,
    ) -> Tuple[bool, str]:
        """
        Detect a breakout-and-retest setup.

        Algorithm:
        1. Look back up to 10 candles for a close beyond a strong level (≥ 3 touches)
           by more than _BREAK_PIPS
        2. After the breakout candle, check if price returned within _RETEST_PIPS
           within _RETEST_MAX_CANDLES
        3. A pattern confirmation at retest = STRONG signal
        Returns (detected: bool, direction: "BUY"|"SELL"|"NONE").
        """
        if len(df) < _RETEST_MAX_CANDLES + 3:
            return False, "NONE"

        strong_levels = [lv for lv in levels if lv.touches >= _STRONG_LEVEL_TOUCHES or lv.is_flip]
        if not strong_levels:
            return False, "NONE"

        break_dist  = _BREAK_PIPS   * pip_size
        retest_dist = _RETEST_PIPS  * pip_size
        closes      = df["close"].values
        lows        = df["low"].values
        highs       = df["high"].values
        n           = len(closes)

        for lv in strong_levels:
            level_price = lv.price

            # Check last 10 candles for a breakout
            scan_start = max(0, n - 10 - _RETEST_MAX_CANDLES)
            for i in range(scan_start, n - _RETEST_MAX_CANDLES):
                close_i = closes[i]

                # Bullish breakout: close above level by > break_dist
                if close_i > level_price + break_dist:
                    # Look for retest in next _RETEST_MAX_CANDLES candles
                    for j in range(i + 1, min(i + _RETEST_MAX_CANDLES + 1, n)):
                        if abs(lows[j] - level_price) <= retest_dist:
                            logger.debug(
                                "Bullish breakout+retest at %.5f (candle %d, retest %d)",
                                level_price, i, j,
                            )
                            return True, "BUY"

                # Bearish breakout: close below level by > break_dist
                if close_i < level_price - break_dist:
                    for j in range(i + 1, min(i + _RETEST_MAX_CANDLES + 1, n)):
                        if abs(highs[j] - level_price) <= retest_dist:
                            logger.debug(
                                "Bearish breakout+retest at %.5f (candle %d, retest %d)",
                                level_price, i, j,
                            )
                            return True, "SELL"

        return False, "NONE"

    # ── COMPONENT 4: Trendline Detection ─────────────────────────────────────

    def _trendline_direction(self, df: pd.DataFrame) -> str:
        """
        Connect last 3 swing lows  → uptrend line direction.
        Connect last 3 swing highs → downtrend line direction.
        Returns "UP" | "DOWN" | "FLAT".

        Uses linear regression slope over the last 3 swing points.
        If both trendlines are present, whichever has the stronger slope wins.
        """
        if len(df) < 20:
            return "FLAT"

        h = df["high"].values
        l = df["low"].values

        swing_h_idx: List[int] = []
        swing_l_idx: List[int] = []

        for i in range(2, len(h) - 2):
            if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
                swing_h_idx.append(i)
            if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
                swing_l_idx.append(i)

        up_slope   = 0.0
        down_slope = 0.0

        if len(swing_l_idx) >= 3:
            pts = swing_l_idx[-3:]
            xs  = np.array(pts, dtype=float)
            ys  = np.array([float(l[i]) for i in pts])
            up_slope = float(np.polyfit(xs, ys, 1)[0])

        if len(swing_h_idx) >= 3:
            pts = swing_h_idx[-3:]
            xs  = np.array(pts, dtype=float)
            ys  = np.array([float(h[i]) for i in pts])
            down_slope = float(np.polyfit(xs, ys, 1)[0])

        if abs(up_slope) < 1e-10 and abs(down_slope) < 1e-10:
            return "FLAT"
        if up_slope > 0 and up_slope >= abs(down_slope):
            return "UP"
        if down_slope < 0 and abs(down_slope) >= abs(up_slope):
            return "DOWN"
        return "FLAT"
