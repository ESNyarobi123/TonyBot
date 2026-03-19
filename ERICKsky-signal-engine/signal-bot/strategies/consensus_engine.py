"""
ERICKsky Signal Engine - Consensus Engine

Weighted voting across all 4 strategies to produce a final tradeable signal.

Rules:
  1. Minimum 3 out of 4 strategies must agree on direction (BUY or SELL)
  2. Weighted consensus score must be >= MIN_CONSENSUS_SCORE (default 75)
  3. SL/TP levels are calculated using ATR 14 from TechnicalIndicators metadata

Strategy weights (sum to 1.0):
  MultiTimeframe      → 0.25
  SmartMoney          → 0.30
  PriceAction         → 0.25
  TechnicalIndicators → 0.20

Confidence labels:
  VERY_HIGH → weighted score >= 88
  HIGH      → weighted score >= 75
  MEDIUM    → weighted score >= 60
  LOW       → below 60 (not issued)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from strategies.base_strategy import StrategyResult
from config import settings
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
MIN_AGREEMENT:         int   = 3      # out of 4 strategies
MIN_CONSENSUS_SCORE:   int   = getattr(settings, "MIN_CONSENSUS_SCORE", 75)

# ATR-based SL/TP multipliers (FIXED: tighter SL, better RR)
_SL_ATR_MULT:  float = 1.0   # stop loss = 1.0 × ATR (tighter)
_TP1_ATR_MULT: float = 1.5   # TP1 = 1.5 × ATR (1:1.5 RR)
_TP2_ATR_MULT: float = 2.0   # TP2 = 2.0 × ATR (1:2.0 RR)
_TP3_ATR_MULT: float = 3.0   # TP3 = 3.0 × ATR (1:3.0 RR)

# Confidence label thresholds (FIXED: higher quality signals)
_CONFIDENCE_MAP: List[Tuple[int, str]] = [
    (90, "VERY_HIGH"),  # 4/4 strategies or very strong 3/4
    (80, "HIGH"),       # strong 3/4 agreement
    (65, "MEDIUM"),     # weak 3/4 (minimum viable)
    (0,  "LOW"),        # < 65 = skip!
]


@dataclass
class ConsensusResult:
    """
    Final output of the Consensus Engine.

    Fields:
      direction          — BUY | SELL | NEUTRAL
      consensus_score    — 0-100 weighted average of agreeing strategies
      confidence_label   — VERY_HIGH | HIGH | MEDIUM | LOW
      weighted_score     — raw float weighted score before rounding
      strategy_scores    — per-strategy individual scores
      strategy_directions— per-strategy direction votes
      agreement_count    — number of strategies agreeing with final direction
      total_strategies   — total strategies evaluated
      sl_price           — ATR-based stop loss price (None if no position)
      tp1_price          — first take-profit price
      tp2_price          — second take-profit price
      atr_pips           — ATR expressed in pips (for display)
      reasoning          — human-readable explanation
      is_valid           — True when all validity gates pass
    """

    direction:           str
    consensus_score:     int
    confidence_label:    str
    weighted_score:      float
    strategy_scores:     Dict[str, int]
    strategy_directions: Dict[str, str]
    agreement_count:     int
    total_strategies:    int
    sl_price:            Optional[float] = None
    tp1_price:           Optional[float] = None
    tp2_price:           Optional[float] = None
    tp3_price:           Optional[float] = None  # NEW: 3rd take profit
    atr_pips:            Optional[float] = None
    reasoning:           str             = ""
    is_valid:            bool            = False


class ConsensusEngine:
    """
    Consensus Engine — aggregates all 4 strategy results.

    Algorithm:
    1. Collect directional votes (ignore NEUTRAL results)
    2. Check minimum agreement gate (>= 3/4)
    3. Compute weighted score from agreeing strategies only
    4. Apply minimum score gate (>= 75)
    5. Extract ATR from TechnicalIndicators metadata for SL/TP
    6. Assign confidence label
    """

    WEIGHTS: Dict[str, float] = {
        "MultiTimeframe":      0.25,
        "SmartMoney":          0.30,
        "PriceAction":         0.25,
        "TechnicalIndicators": 0.20,
    }

    def compute(
        self,
        results:       List[StrategyResult],
        symbol:        str  = "EURUSD",
        entry_price:   Optional[float] = None,
    ) -> ConsensusResult:
        """
        Compute the final consensus signal from a list of strategy results.

        Args:
            results:     List of StrategyResult (up to 4, one per strategy)
            symbol:      Trading symbol, used for pip-value SL/TP calculation
            entry_price: Current market price for SL/TP offset calculation

        Returns:
            ConsensusResult with all fields populated.
        """
        _empty = ConsensusResult(
            direction="NEUTRAL", consensus_score=0, confidence_label="LOW",
            weighted_score=0.0, strategy_scores={}, strategy_directions={},
            agreement_count=0, total_strategies=0, is_valid=False,
            reasoning="No strategy results",
        )

        if not results:
            return _empty

        strategy_scores     = {r.strategy_name: r.score for r in results}
        strategy_directions = {r.strategy_name: r.direction for r in results}

        # ── STEP 1: Directional vote count ────────────────────────────────────
        buy_results  = [r for r in results if r.direction == "BUY"]
        sell_results = [r for r in results if r.direction == "SELL"]
        buy_count    = len(buy_results)
        sell_count   = len(sell_results)

        if buy_count >= sell_count and buy_count > 0:
            dominant_dir      = "BUY"
            agreeing_results  = buy_results
            agreement_count   = buy_count
        elif sell_count > buy_count:
            dominant_dir      = "SELL"
            agreeing_results  = sell_results
            agreement_count   = sell_count
        else:
            logger.info("Consensus: tied vote (BUY=%d SELL=%d) → NEUTRAL", buy_count, sell_count)
            return ConsensusResult(
                direction="NEUTRAL", consensus_score=0, confidence_label="LOW",
                weighted_score=0.0, strategy_scores=strategy_scores,
                strategy_directions=strategy_directions,
                agreement_count=0, total_strategies=len(results),
                is_valid=False,
                reasoning=f"Tied: BUY={buy_count} SELL={sell_count}",
            )

        # ── STEP 2: HARD CHECK - Minimum agreement MUST be 3/4 ───────────────
        # BUG FIX: Never allow 2/4 agreement signals regardless of score!
        if agreement_count < 3:
            logger.warning(
                "🚫 HARD BLOCK: %s has only %d/%d agreement (need 3/4). "
                "Signal REJECTED regardless of score!",
                dominant_dir, agreement_count, len(results)
            )
            return ConsensusResult(
                direction="NEUTRAL", consensus_score=0, confidence_label="LOW",
                weighted_score=0.0, strategy_scores=strategy_scores,
                strategy_directions=strategy_directions,
                agreement_count=agreement_count, total_strategies=len(results),
                is_valid=False,
                reasoning=(
                    f"🚫 HARD BLOCK: {agreement_count}/4 agreement insufficient "
                    f"(minimum 3/4 required)"
                ),
            )

        # ── STEP 3: Weighted score from agreeing strategies ───────────────────
        total_weight  = 0.0
        weighted_sum  = 0.0
        for r in agreeing_results:
            w = self.WEIGHTS.get(r.strategy_name, 0.25)
            weighted_sum  += r.score * w
            total_weight  += w

        if total_weight == 0:
            return _empty

        weighted_score  = weighted_sum / total_weight
        consensus_score = int(round(min(100.0, max(0.0, weighted_score))))

        # ── STEP 4: Minimum score gate ────────────────────────────────────────
        if consensus_score < MIN_CONSENSUS_SCORE:
            logger.info(
                "Consensus: score %d < min %d for %s → rejected",
                consensus_score, MIN_CONSENSUS_SCORE, dominant_dir,
            )
            return ConsensusResult(
                direction="NEUTRAL", consensus_score=consensus_score,
                confidence_label="LOW", weighted_score=round(weighted_score, 2),
                strategy_scores=strategy_scores,
                strategy_directions=strategy_directions,
                agreement_count=agreement_count, total_strategies=len(results),
                is_valid=False,
                reasoning=(
                    f"Score {consensus_score} below minimum {MIN_CONSENSUS_SCORE}"
                ),
            )

        # ── STEP 5: ATR-based SL/TP ───────────────────────────────────────────
        sl_price, tp1_price, tp2_price, tp3_price, atr_pips = self._calculate_sl_tp(
            results=results,
            symbol=symbol,
            direction=dominant_dir,
            entry_price=entry_price,
        )

        # ── STEP 6: Confidence label ──────────────────────────────────────────
        confidence_label = self._confidence_label(consensus_score)

        # ── Build reasoning ───────────────────────────────────────────────────
        vote_summary = " | ".join(
            f"{r.strategy_name}={r.direction}({r.score})" for r in results
        )
        reasoning = (
            f"{dominant_dir} confirmed {agreement_count}/{len(results)} | "
            f"score={consensus_score} | {confidence_label} | {vote_summary}"
        )

        logger.info(
            "Consensus: %s score=%d confidence=%s agreement=%d/%d",
            dominant_dir, consensus_score, confidence_label,
            agreement_count, len(results),
        )

        return ConsensusResult(
            direction=dominant_dir,
            consensus_score=consensus_score,
            confidence_label=confidence_label,
            weighted_score=round(weighted_score, 2),
            strategy_scores=strategy_scores,
            strategy_directions=strategy_directions,
            agreement_count=agreement_count,
            total_strategies=len(results),
            sl_price=sl_price,
            tp1_price=tp1_price,
            tp2_price=tp2_price,
            tp3_price=tp3_price,  # NEW
            atr_pips=atr_pips,
            reasoning=reasoning,
            is_valid=True,
        )

    # ── SL/TP calculation ─────────────────────────────────────────────────────

    def _calculate_sl_tp(
        self,
        results:     List[StrategyResult],
        symbol:      str,
        direction:   str,
        entry_price: Optional[float],
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Calculate ATR-based SL and TP levels (3 TPs for better RR).

        Returns (sl_price, tp1_price, tp2_price, tp3_price, atr_in_pips).
        """
        if entry_price is None or entry_price <= 0:
            return None, None, None, None

        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)

        # Extract ATR from TechnicalIndicators metadata
        atr_value: Optional[float] = None
        for r in results:
            if r.strategy_name == "TechnicalIndicators" and r.metadata:
                raw = r.metadata.get("atr")
                if raw and float(raw) > 0:
                    atr_value = float(raw)
                    break

        if atr_value is None:
            atr_value = 15 * pip_size   # fallback: 15 pips

        atr_pips = round(atr_value / pip_size, 1)

        sl_offset  = _SL_ATR_MULT  * atr_value
        tp1_offset = _TP1_ATR_MULT * atr_value
        tp2_offset = _TP2_ATR_MULT * atr_value
        tp3_offset = _TP3_ATR_MULT * atr_value  # NEW: 3rd TP

        if direction == "BUY":
            sl_price  = entry_price - sl_offset
            tp1_price = entry_price + tp1_offset
            tp2_price = entry_price + tp2_offset
            tp3_price = entry_price + tp3_offset  # NEW
        else:  # SELL
            sl_price  = entry_price + sl_offset
            tp1_price = entry_price - tp1_offset
            tp2_price = entry_price - tp2_offset
            tp3_price = entry_price - tp3_offset  # NEW

        decimals = 5  # All pairs now use 5 decimals (no USDJPY)
        return (
            round(sl_price,  decimals),
            round(tp1_price, decimals),
            round(tp2_price, decimals),
            round(tp3_price, decimals),  # NEW: TP3
            atr_pips,
        )

    # ── Confidence label ──────────────────────────────────────────────────────

    @staticmethod
    def _confidence_label(score: int) -> str:
        """Map consensus score to confidence label."""
        for threshold, label in _CONFIDENCE_MAP:
            if score >= threshold:
                return label
        return "LOW"
