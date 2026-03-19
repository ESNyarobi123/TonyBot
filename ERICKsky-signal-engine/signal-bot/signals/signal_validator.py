"""
ERICKsky Signal Engine - Signal Validator
Final validation pass before a signal is saved and sent.
"""

import logging
from typing import Optional, Tuple

from database.models import Signal
from config import settings

logger = logging.getLogger(__name__)


class SignalValidator:
    """
    Validates a Signal object for internal consistency and risk parameters
    before it is persisted and dispatched to Telegram.
    """

    def validate(self, signal: Signal) -> Tuple[bool, str]:
        """
        Run all validation checks.

        Returns:
            (is_valid: bool, reason: str)
        """
        checks = [
            self._check_required_fields(signal),
            self._check_price_logic(signal),
            self._check_risk_reward(signal),
            self._check_consensus_score(signal),
            self._check_confidence(signal),
        ]

        for passed, reason in checks:
            if not passed:
                logger.warning("Signal validation FAILED: %s", reason)
                return False, reason

        logger.debug("Signal validation PASSED for %s %s", signal.pair, signal.direction)
        return True, "all checks passed"

    @staticmethod
    def _check_required_fields(signal: Signal) -> Tuple[bool, str]:
        if not signal.pair:
            return False, "missing pair"
        if signal.direction not in ("BUY", "SELL"):
            return False, f"invalid direction: {signal.direction}"
        if not signal.entry_price or signal.entry_price <= 0:
            return False, f"invalid entry price: {signal.entry_price}"
        if not signal.stop_loss or signal.stop_loss <= 0:
            return False, f"invalid stop loss: {signal.stop_loss}"
        if not signal.take_profit_1 or signal.take_profit_1 <= 0:
            return False, f"invalid TP1: {signal.take_profit_1}"
        return True, "required fields OK"

    @staticmethod
    def _check_price_logic(signal: Signal) -> Tuple[bool, str]:
        entry = signal.entry_price
        sl = signal.stop_loss
        tp1 = signal.take_profit_1

        if signal.direction == "BUY":
            if sl >= entry:
                return False, f"BUY: SL ({sl}) must be below entry ({entry})"
            if tp1 <= entry:
                return False, f"BUY: TP1 ({tp1}) must be above entry ({entry})"
        else:
            if sl <= entry:
                return False, f"SELL: SL ({sl}) must be above entry ({entry})"
            if tp1 >= entry:
                return False, f"SELL: TP1 ({tp1}) must be below entry ({entry})"

        # Validate TP2 > TP1 (BUY) or TP2 < TP1 (SELL)
        if signal.take_profit_2:
            if signal.direction == "BUY" and signal.take_profit_2 <= tp1:
                return False, "BUY: TP2 must be above TP1"
            if signal.direction == "SELL" and signal.take_profit_2 >= tp1:
                return False, "SELL: TP2 must be below TP1"

        return True, "price logic OK"

    @staticmethod
    def _check_risk_reward(signal: Signal) -> Tuple[bool, str]:
        entry = signal.entry_price
        sl = signal.stop_loss
        tp1 = signal.take_profit_1

        sl_distance = abs(entry - sl)
        tp_distance = abs(tp1 - entry)

        if sl_distance == 0:
            return False, "SL distance is zero"

        rr_ratio = tp_distance / sl_distance

        # Minimum 1:1 risk/reward
        if rr_ratio < 0.8:
            return False, f"insufficient R:R ratio ({rr_ratio:.2f}), minimum 0.8"

        return True, f"R:R ratio {rr_ratio:.2f} OK"

    @staticmethod
    def _check_consensus_score(signal: Signal) -> Tuple[bool, str]:
        if signal.consensus_score < settings.MIN_CONSENSUS_SCORE:
            return False, (
                f"consensus score {signal.consensus_score} "
                f"below minimum {settings.MIN_CONSENSUS_SCORE}"
            )
        return True, f"consensus score {signal.consensus_score} OK"

    @staticmethod
    def _check_confidence(signal: Signal) -> Tuple[bool, str]:
        valid_levels = ("LOW", "MEDIUM", "HIGH", "VERY_HIGH")
        if signal.confidence not in valid_levels:
            return False, f"invalid confidence level: {signal.confidence}"
        return True, f"confidence {signal.confidence} OK"


# Module-level singleton
signal_validator = SignalValidator()
