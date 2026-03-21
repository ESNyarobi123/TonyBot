"""
ERICKsky Signal Engine - Chart Pattern Detector (Upgrade 5)

Detects major reversal & continuation patterns that CONFIRM or BLOCK signals.

Patterns detected:
  Double Top / Double Bottom
  Head & Shoulders (basic)
  Triangle (ascending / descending / symmetrical)
  Breakout Retest (very high-conviction confirmation)
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from scipy.stats import linregress  # type: ignore
    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False

logger = logging.getLogger(__name__)


class ChartPatternDetector:
    """Detect chart patterns on H4 and H1 data to confirm or block a signal."""

    def detect(
        self,
        df_h4: pd.DataFrame,
        df_h1: pd.DataFrame,
        direction: str,
    ) -> Dict:
        """
        Detect patterns and return a composite score.

        Returns:
            dict with:
              patterns   – list of pattern dicts
              score      – int  (positive = confirms, negative = conflicts)
              confirmed  – bool (score > 0)
              blocked    – bool (score <= -30)
        """
        patterns_found: List[Dict] = []
        pattern_score = 0

        # ── Double Top/Bottom ────────────────────────────────────────────────
        dt = self._detect_double_top(df_h4)
        if dt.get("found"):
            patterns_found.append(dt)
            if dt["direction"] == direction:
                pattern_score += 30
            else:
                pattern_score -= 40

        db_ = self._detect_double_bottom(df_h4)
        if db_.get("found"):
            patterns_found.append(db_)
            if db_["direction"] == direction:
                pattern_score += 30
            else:
                pattern_score -= 40

        # ── Head & Shoulders ─────────────────────────────────────────────────
        hs = self._detect_head_shoulders(df_h4)
        if hs.get("found"):
            patterns_found.append(hs)
            if hs["direction"] == direction:
                pattern_score += 35
            else:
                pattern_score -= 45

        # ── Triangle ─────────────────────────────────────────────────────────
        tri = self._detect_triangle(df_h1)
        if tri.get("found"):
            patterns_found.append(tri)
            if tri.get("breakout_direction") == direction:
                pattern_score += 25
            elif tri.get("type") == "SYMMETRICAL":
                pattern_score += 0  # neutral
            else:
                pattern_score -= 30

        # ── Breakout Retest ───────────────────────────────────────────────────
        br = self._detect_breakout_retest(df_h1, direction)
        if br.get("found"):
            patterns_found.append(br)
            pattern_score += 40  # Strong confirmation

        pattern_names = [p.get("name", "?") for p in patterns_found]
        logger.info(
            "ChartPatterns: %s | score=%d | dir=%s",
            pattern_names, pattern_score, direction,
        )

        return {
            "patterns":  patterns_found,
            "score":     pattern_score,
            "confirmed": pattern_score > 0,
            "blocked":   pattern_score <= -30,
        }

    # ── Pattern detectors ─────────────────────────────────────────────────────

    def _detect_double_top(self, df: pd.DataFrame) -> Dict:
        highs = df["high"].values
        lows  = df["low"].values
        close = df["close"].values

        swing_highs = self._find_swing_highs(highs, window=3)
        if len(swing_highs) < 2:
            return {"found": False}

        h1_idx, h1_val = swing_highs[-2]
        h2_idx, h2_val = swing_highs[-1]

        # Tops within 0.15% of each other
        if abs(h1_val - h2_val) / (h1_val + 1e-10) > 0.0015:
            return {"found": False}

        # Neckline = lowest low between peaks
        if h2_idx > h1_idx and h2_idx <= len(lows):
            neckline = float(min(lows[h1_idx:h2_idx]))
        else:
            return {"found": False}

        # Price has broken below neckline
        if close[-1] < neckline * 0.999:
            target = neckline - (h1_val - neckline)
            return {
                "found":     True,
                "name":      "DOUBLE_TOP",
                "direction": "SELL",
                "neckline":  neckline,
                "target":    target,
            }
        return {"found": False}

    def _detect_double_bottom(self, df: pd.DataFrame) -> Dict:
        lows  = df["low"].values
        highs = df["high"].values
        close = df["close"].values

        swing_lows = self._find_swing_lows(lows, window=3)
        if len(swing_lows) < 2:
            return {"found": False}

        l1_idx, l1_val = swing_lows[-2]
        l2_idx, l2_val = swing_lows[-1]

        if abs(l1_val - l2_val) / (l1_val + 1e-10) > 0.0015:
            return {"found": False}

        if l2_idx > l1_idx and l2_idx <= len(highs):
            neckline = float(max(highs[l1_idx:l2_idx]))
        else:
            return {"found": False}

        if close[-1] > neckline * 1.001:
            target = neckline + (neckline - l1_val)
            return {
                "found":     True,
                "name":      "DOUBLE_BOTTOM",
                "direction": "BUY",
                "neckline":  neckline,
                "target":    target,
            }
        return {"found": False}

    def _detect_head_shoulders(self, df: pd.DataFrame) -> Dict:
        """Basic Head & Shoulders (bearish) detection."""
        highs = df["high"].values
        close = df["close"].values

        swing_highs = self._find_swing_highs(highs, window=3)
        if len(swing_highs) < 3:
            return {"found": False}

        ls_idx, ls_val  = swing_highs[-3]  # left shoulder
        head_idx, h_val = swing_highs[-2]  # head
        rs_idx, rs_val  = swing_highs[-1]  # right shoulder

        # Head must be the highest
        if not (h_val > ls_val and h_val > rs_val):
            return {"found": False}

        # Shoulders roughly equal (within 1%)
        if abs(ls_val - rs_val) / (ls_val + 1e-10) > 0.01:
            return {"found": False}

        # Simplified neckline = average valley between shoulders
        neckline = (highs[ls_idx] + highs[rs_idx]) / 2 * 0.97

        if close[-1] < neckline:
            target = neckline - (h_val - neckline)
            return {
                "found":     True,
                "name":      "HEAD_AND_SHOULDERS",
                "direction": "SELL",
                "neckline":  neckline,
                "target":    target,
            }
        return {"found": False}

    def _detect_triangle(self, df: pd.DataFrame) -> Dict:
        """Triangle patterns using linear regression on the last 30 candles."""
        if not _SCIPY_AVAILABLE:
            return {"found": False}

        highs = df["high"].values[-30:]
        lows  = df["low"].values[-30:]
        close = df["close"].values[-30:]
        x     = np.arange(len(highs), dtype=float)

        try:
            h_slope = linregress(x, highs).slope
            l_slope = linregress(x, lows).slope
        except Exception:
            return {"found": False}

        # Descending triangle (bearish)
        if h_slope < -0.0001 and abs(l_slope) < 0.00005:
            support = float(np.mean(lows[-5:]))
            if close[-1] < support * 0.999:
                return {
                    "found":              True,
                    "name":               "DESCENDING_TRIANGLE",
                    "type":               "DESCENDING",
                    "breakout_direction": "SELL",
                }

        # Ascending triangle (bullish)
        elif l_slope > 0.0001 and abs(h_slope) < 0.00005:
            resistance = float(np.mean(highs[-5:]))
            if close[-1] > resistance * 1.001:
                return {
                    "found":              True,
                    "name":               "ASCENDING_TRIANGLE",
                    "type":               "ASCENDING",
                    "breakout_direction": "BUY",
                }

        # Symmetrical triangle
        elif h_slope < -0.00005 and l_slope > 0.00005:
            return {
                "found":              True,
                "name":               "SYMMETRICAL_TRIANGLE",
                "type":               "SYMMETRICAL",
                "breakout_direction": "UNKNOWN",
            }

        return {"found": False}

    def _detect_breakout_retest(self, df: pd.DataFrame, direction: str) -> Dict:
        """Detect a classic breakout-then-retest of a key level."""
        close = df["close"].values
        high  = df["high"].values
        low   = df["low"].values

        lookback = 20

        try:
            if direction == "SELL":
                level  = float(max(high[-lookback - 5:-5]))
                broke  = close[-5] > level
                retested = close[-1] < level and min(close[-3:]) < level

            else:  # BUY
                level  = float(min(low[-lookback - 5:-5]))
                broke  = close[-5] < level
                retested = close[-1] > level and max(close[-3:]) > level

            if broke and retested:
                return {
                    "found":     True,
                    "name":      "BREAKOUT_RETEST",
                    "level":     level,
                    "direction": direction,
                }
        except (ValueError, IndexError):
            pass

        return {"found": False}

    # ── Utility helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _find_swing_highs(highs: np.ndarray, window: int = 3) -> list:
        """Return list of (index, value) tuples for local swing highs."""
        result = []
        for i in range(window, len(highs) - window):
            is_high = all(
                highs[i] >= highs[i - j] and highs[i] >= highs[i + j]
                for j in range(1, window + 1)
            )
            if is_high:
                result.append((i, float(highs[i])))
        return result

    @staticmethod
    def _find_swing_lows(lows: np.ndarray, window: int = 3) -> list:
        """Return list of (index, value) tuples for local swing lows."""
        result = []
        for i in range(window, len(lows) - window):
            is_low = all(
                lows[i] <= lows[i - j] and lows[i] <= lows[i + j]
                for j in range(1, window + 1)
            )
            if is_low:
                result.append((i, float(lows[i])))
        return result


# Module-level singleton
chart_pattern_detector = ChartPatternDetector()
