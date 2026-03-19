"""
ERICKsky Signal Engine - Strategy 2: Smart Money Concepts (SMC)

Implements four core institutional trading concepts:
  1. Order Block (OB)     — last opposing candle before a strong impulse move
  2. Fair Value Gap (FVG) — price imbalance between candle[i].high and candle[i+2].low
  3. Liquidity Zones      — equal highs/lows (stop-hunt pools) and their sweeps
  4. Market Structure     — HH/HL = bullish, LH/LL = bearish, BOS / CHoCH detection

Scoring:
  OB at price + FVG above/below + liquidity grabbed  → 100
  OB at price + price at OB                          → 75
  Unfilled FVG nearby                               → 50
  No SMC setup                                      → 0
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from strategies.base_strategy import BaseStrategy, StrategyResult
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# Scan constants
_OB_SCAN_CANDLES:  int = 50
_FVG_SCAN_CANDLES: int = 50
_LIQ_SCAN_CANDLES: int = 30
_LIQ_PROXIMITY_PIPS: int = 5    # pips to consider two highs/lows "equal"


@dataclass
class _OrderBlock:
    direction: str   # BULLISH | BEARISH
    high: float
    low: float
    idx: int         # index in the scanned window
    valid: bool = True


@dataclass
class _FVG:
    direction: str   # BULLISH | BEARISH
    top: float       # upper edge of the gap
    bottom: float    # lower edge of the gap
    idx: int
    filled: bool = False


class SmartMoneyStrategy(BaseStrategy):
    """
    Smart Money Concepts (SMC) strategy.

    Uses H4 candles for Order Block and liquidity detection (higher structure),
    and H1 candles for FVG detection (entry precision).
    Falls back to H4 for FVG if H1 is unavailable.
    """

    name = "SmartMoney"

    def analyze(
        self,
        symbol: str,
        data: Dict[str, Optional[pd.DataFrame]],
    ) -> StrategyResult:
        """Run the full SMC analysis pipeline."""
        try:
            return self._run(symbol, data)
        except Exception as exc:
            logger.exception("SMC error for %s: %s", symbol, exc)
            return self._neutral_result(self.name, f"Error: {exc}")

    # ── Main pipeline ─────────────────────────────────────────────────────────

    def _run(self, symbol: str, data: dict) -> StrategyResult:
        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)

        df_h4 = self._get_df(data, "H4")
        df_h1 = self._get_df(data, "H1")
        
        # DEBUG LOGGING - Check data availability
        logger.info(f"SMC DEBUG {symbol}: H4={df_h4.shape if df_h4 is not None else None}, H1={df_h1.shape if df_h1 is not None else None}")

        if df_h4 is None:
            logger.warning(f"SMC DEBUG {symbol}: No H4 data available!")
            return self._neutral_result(self.name, "No H4 data for SMC")

        price = float(df_h4["close"].iloc[-1])
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: Current price={price}")

        # ── 1. Order Block Detection (H4) ─────────────────────────────────────
        obs_bull, obs_bear = self._detect_order_blocks(df_h4, pip_size)
        bull_ob = self._nearest_ob(obs_bull, price, pip_size)
        bear_ob = self._nearest_ob(obs_bear, price, pip_size)
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: Order blocks found - bullish={len(obs_bull)}, bearish={len(obs_bear)}")
        logger.info(f"SMC DEBUG {symbol}: Nearest OB - bull={bull_ob is not None}, bear={bear_ob is not None}")

        # ── 2. Fair Value Gap Detection (H1 preferred, H4 fallback) ──────────
        fvg_df  = df_h1 if df_h1 is not None else df_h4
        all_fvg = self._detect_fvgs(fvg_df, pip_size)
        bull_fvg = next((f for f in all_fvg if f.direction == "BULLISH" and not f.filled), None)
        bear_fvg = next((f for f in all_fvg if f.direction == "BEARISH" and not f.filled), None)
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: FVGs found={len(all_fvg)}, bull_fvg={bull_fvg is not None}, bear_fvg={bear_fvg is not None}")

        # ── 3. Liquidity Zone Sweeps (H4) ─────────────────────────────────────
        liq_bull_sweep, liq_bear_sweep = self._detect_liquidity_sweeps(df_h4, pip_size)
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: Liquidity sweeps - bull={liq_bull_sweep}, bear={liq_bear_sweep}")

        # ── 4. Market Structure (H4) ──────────────────────────────────────────
        mkt_structure = self._market_structure(df_h4)
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: Market structure={mkt_structure}")

        # ── Scoring ───────────────────────────────────────────────────────────
        buy_score  = self._compute_score(
            ob=bull_ob, fvg=bull_fvg, liq_sweep=liq_bull_sweep,
            structure=mkt_structure, direction="BUY",
            price=price, pip_size=pip_size,
        )
        sell_score = self._compute_score(
            ob=bear_ob, fvg=bear_fvg, liq_sweep=liq_bear_sweep,
            structure=mkt_structure, direction="SELL",
            price=price, pip_size=pip_size,
        )
        
        # DEBUG
        logger.info(f"SMC DEBUG {symbol}: Buy score={buy_score}, Sell score={sell_score}")

        # FIX 4: Lower threshold from 40 to 25 for partial SMC signals
        if buy_score > sell_score and buy_score >= 25:
            direction = "BUY"
            score     = buy_score
            active_ob  = bull_ob
            active_fvg = bull_fvg
            reasoning  = (
                f"Bullish OB={bull_ob is not None} FVG={bull_fvg is not None} "
                f"LiqSweep={liq_bull_sweep} Struct={mkt_structure}"
            )
        elif sell_score > buy_score and sell_score >= 25:
            direction = "SELL"
            score     = sell_score
            active_ob  = bear_ob
            active_fvg = bear_fvg
            reasoning  = (
                f"Bearish OB={bear_ob is not None} FVG={bear_fvg is not None} "
                f"LiqSweep={liq_bear_sweep} Struct={mkt_structure}"
            )
        else:
            direction  = "NEUTRAL"
            score      = 0
            active_ob  = None
            active_fvg = None
            reasoning  = "No SMC confluence detected"
        
        # DEBUG final result
        logger.info(f"SMC DEBUG {symbol}: FINAL direction={direction}, score={score}")

        ob_meta = (
            {"direction": active_ob.direction, "high": active_ob.high, "low": active_ob.low}
            if active_ob else None
        )
        fvg_meta = (
            {"direction": active_fvg.direction, "top": active_fvg.top, "bottom": active_fvg.bottom}
            if active_fvg else None
        )

        return StrategyResult(
            strategy_name=self.name,
            score=self._safe_score(score),
            direction=direction,
            confidence=round(min(score / 100, 1.0), 2),
            reasoning=reasoning,
            metadata={
                "order_block":      ob_meta,
                "fvg":              fvg_meta,
                "liquidity":        {"bull_sweep": liq_bull_sweep, "bear_sweep": liq_bear_sweep},
                "market_structure": mkt_structure,
            },
        )

    # ── Scoring helper ────────────────────────────────────────────────────────

    def _compute_score(
        self,
        ob: Optional[_OrderBlock],
        fvg: Optional[_FVG],
        liq_sweep: bool,
        structure: str,
        direction: str,
        price: float,
        pip_size: float,
    ) -> int:
        """Accumulate score for one direction from all SMC components."""
        score = 0

        # Order Block
        if ob:
            ob_mid  = (ob.high + ob.low) / 2
            ob_dist = abs(price - ob_mid) / pip_size
            if ob_dist <= 20:
                score += 40   # price at OB — high confidence
            elif ob_dist <= 50:
                score += 20   # price approaching OB
            # Price inside the OB zone = extra bonus
            if ob.low <= price <= ob.high:
                score += 10

        # Fair Value Gap
        if fvg:
            if fvg.bottom <= price <= fvg.top:
                score += 30   # price currently inside FVG = magnet zone
            else:
                score += 15   # unfilled FVG nearby as target/support

        # Liquidity sweep — strong reversal signal
        if liq_sweep:
            score += 25

        # Market structure alignment
        if (direction == "BUY"  and structure == "BULLISH") or \
           (direction == "SELL" and structure == "BEARISH"):
            score += 15

        return min(100, score)

    # ── CONCEPT 1: Order Block Detection ─────────────────────────────────────

    def _detect_order_blocks(
        self,
        df: pd.DataFrame,
        pip_size: float,
    ) -> Tuple[List[_OrderBlock], List[_OrderBlock]]:
        """
        Scan last _OB_SCAN_CANDLES H4 candles for Order Blocks.

        Bullish OB: last BEARISH candle before 3+ consecutive bullish candles
                    where the move exceeds 50% of the OB candle's range.
        Bearish OB: last BULLISH candle before 3+ consecutive bearish candles.

        An OB is "valid" (unvisited) if price has NOT fully retraced through it.
        """
        bulls: List[_OrderBlock] = []
        bears: List[_OrderBlock] = []

        n = min(_OB_SCAN_CANDLES, len(df) - 4)
        o = df["open"].values
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values

        # FIX 4: Reduce from 3 candles to 2 for order block detection
        MIN_IMPULSE_CANDLES = 2  # was 3
        
        for i in range(n):
            candle_range = h[i] - l[i]
            if candle_range < pip_size * 2:  # FIX 4: reduced from 3 to 2 pips min
                continue  # too small to be meaningful

            # ── Bullish OB: bearish candle → 2 bullish candles (was 3) ─────────────
            if c[i] < o[i]:                                    # bearish
                if i + MIN_IMPULSE_CANDLES < len(c):
                    next_bull = all(c[i + j] > o[i + j] for j in range(1, MIN_IMPULSE_CANDLES + 1))
                    move       = c[i + MIN_IMPULSE_CANDLES] - l[i]
                    if next_bull and move > candle_range * 0.5:
                        future_slice = l[i + MIN_IMPULSE_CANDLES + 1:] if i + MIN_IMPULSE_CANDLES + 1 < len(l) else []
                        valid = len(future_slice) == 0 or float(np.min(future_slice)) > l[i]
                        bulls.append(_OrderBlock(
                            direction="BULLISH",
                            high=float(h[i]),
                            low=float(l[i]),
                            idx=i,
                            valid=valid,
                        ))

            # ── Bearish OB: bullish candle → 2 bearish candles (was 3) ─────────────
            elif c[i] > o[i]:                                  # bullish
                if i + MIN_IMPULSE_CANDLES < len(c):
                    next_bear = all(c[i + j] < o[i + j] for j in range(1, MIN_IMPULSE_CANDLES + 1))
                    move       = h[i] - c[i + MIN_IMPULSE_CANDLES]
                    if next_bear and move > candle_range * 0.5:
                        future_slice = h[i + MIN_IMPULSE_CANDLES + 1:] if i + MIN_IMPULSE_CANDLES + 1 < len(h) else []
                        valid = len(future_slice) == 0 or float(np.max(future_slice)) < h[i]
                        bears.append(_OrderBlock(
                            direction="BEARISH",
                            high=float(h[i]),
                            low=float(l[i]),
                            idx=i,
                            valid=valid,
                        ))

        return [ob for ob in bulls if ob.valid], [ob for ob in bears if ob.valid]

    def _nearest_ob(
        self,
        obs: List[_OrderBlock],
        price: float,
        pip_size: float,
        max_pips: int = 100,
    ) -> Optional[_OrderBlock]:
        """Return the nearest valid OB within max_pips of current price."""
        candidates = [
            ob for ob in obs
            if abs(price - (ob.high + ob.low) / 2) <= max_pips * pip_size
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda ob: abs(price - (ob.high + ob.low) / 2))

    # ── CONCEPT 2: Fair Value Gap Detection ──────────────────────────────────

    def _detect_fvgs(
        self,
        df: pd.DataFrame,
        pip_size: float,
        min_pips: float = 1.0,  # FIX 4: reduced from 3.0 to 1.0 pips
    ) -> List[_FVG]:
        """
        Detect Fair Value Gaps in last _FVG_SCAN_CANDLES candles.

        Bullish FVG: candle[i+2].low > candle[i].high
          → gap between top of candle 1 and bottom of candle 3 = price imbalance
        Bearish FVG: candle[i+2].high < candle[i].low
          → gap between bottom of candle 1 and top of candle 3

        FVG is "filled" when current price has crossed back through it.
        Minimum gap size = min_pips to filter noise.
        """
        fvgs: List[_FVG] = []
        n = min(_FVG_SCAN_CANDLES, len(df) - 2)
        h = df["high"].values
        l = df["low"].values
        c = df["close"].values
        min_gap = min_pips * pip_size
        current_price = float(c[-1])

        for i in range(n):
            # Bullish FVG: gap between candle[i] top and candle[i+2] bottom
            bull_gap = l[i + 2] - h[i]
            if bull_gap >= min_gap:
                filled = current_price < l[i + 2]   # price retraced into gap
                fvgs.append(_FVG(
                    direction="BULLISH",
                    top=float(l[i + 2]),
                    bottom=float(h[i]),
                    idx=i,
                    filled=filled,
                ))

            # Bearish FVG: gap between candle[i] bottom and candle[i+2] top
            bear_gap = l[i] - h[i + 2]
            if bear_gap >= min_gap:
                filled = current_price > l[i]        # price retraced into gap
                fvgs.append(_FVG(
                    direction="BEARISH",
                    top=float(l[i]),
                    bottom=float(h[i + 2]),
                    idx=i,
                    filled=filled,
                ))

        # Most recent first
        return sorted(fvgs, key=lambda f: f.idx, reverse=True)

    # ── CONCEPT 3: Liquidity Zone Sweeps ─────────────────────────────────────

    def _detect_liquidity_sweeps(
        self,
        df: pd.DataFrame,
        pip_size: float,
    ) -> Tuple[bool, bool]:
        """
        Detect liquidity sweeps in last _LIQ_SCAN_CANDLES candles.

        Equal highs within _LIQ_PROXIMITY_PIPS = sell-side liquidity pool.
        Equal lows  within _LIQ_PROXIMITY_PIPS = buy-side  liquidity pool.

        Bullish sweep: price spikes below equal lows THEN reverses back up.
        Bearish sweep: price spikes above equal highs THEN reverses back down.
        """
        n  = min(_LIQ_SCAN_CANDLES, len(df))
        h  = df["high"].values[-n:]
        l  = df["low"].values[-n:]
        c  = df["close"].values[-n:]
        prox = _LIQ_PROXIMITY_PIPS * pip_size

        current_price = float(c[-1])
        prev_price    = float(c[-6]) if len(c) >= 6 else current_price

        # Build liquidity pools (clusters of equal levels)
        high_pools: List[float] = []
        low_pools:  List[float] = []

        for i in range(len(h) - 5):
            for j in range(i + 1, min(i + 10, len(h))):
                if abs(h[i] - h[j]) <= prox:
                    high_pools.append((h[i] + h[j]) / 2)
                if abs(l[i] - l[j]) <= prox:
                    low_pools.append((l[i] + l[j]) / 2)

        # Bullish sweep: wick BELOW a low-pool then close ABOVE it
        bull_sweep = False
        for level in low_pools:
            swept    = float(np.min(l[-5:])) < level
            reversed_up = current_price > level and current_price > prev_price
            if swept and reversed_up:
                bull_sweep = True
                logger.debug("Bullish liq sweep detected at %.5f", level)
                break

        # Bearish sweep: wick ABOVE a high-pool then close BELOW it
        bear_sweep = False
        for level in high_pools:
            swept      = float(np.max(h[-5:])) > level
            reversed_dn = current_price < level and current_price < prev_price
            if swept and reversed_dn:
                bear_sweep = True
                logger.debug("Bearish liq sweep detected at %.5f", level)
                break

        return bull_sweep, bear_sweep

    # ── CONCEPT 4: Market Structure ───────────────────────────────────────────

    def _market_structure(self, df: pd.DataFrame) -> str:
        """
        Classify current market structure using swing highs and swing lows.

        Higher Highs + Higher Lows → BULLISH
        Lower  Highs + Lower  Lows → BEARISH
        Mixed                      → RANGING

        Uses a 3-bar pivot definition for swing point detection.
        """
        if len(df) < 20:
            return "RANGING"

        h = df["high"].values
        l = df["low"].values

        swing_highs: List[float] = []
        swing_lows:  List[float] = []

        for i in range(2, len(h) - 2):
            if h[i] > h[i-1] and h[i] > h[i-2] and h[i] > h[i+1] and h[i] > h[i+2]:
                swing_highs.append(float(h[i]))
            if l[i] < l[i-1] and l[i] < l[i-2] and l[i] < l[i+1] and l[i] < l[i+2]:
                swing_lows.append(float(l[i]))

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "RANGING"

        hh = swing_highs[-1] > swing_highs[-2]   # Higher High
        hl = swing_lows[-1]  > swing_lows[-2]    # Higher Low
        lh = swing_highs[-1] < swing_highs[-2]   # Lower High
        ll = swing_lows[-1]  < swing_lows[-2]    # Lower Low

        if hh and hl:
            return "BULLISH"
        if lh and ll:
            return "BEARISH"
        return "RANGING"
