"""
ERICKsky Signal Engine - Consensus Engine Unit Tests
"""

import pytest
from strategies.base_strategy import StrategyResult
from strategies.consensus_engine import ConsensusEngine, ConsensusResult
from config import settings


def _make_result(name: str, score: int, direction: str, confidence: float = 0.8) -> StrategyResult:
    return StrategyResult(
        strategy_name=name,
        score=score,
        direction=direction,
        confidence=confidence,
        reasoning=f"{name} test",
    )


class TestConsensusEngine:

    def setup_method(self):
        self.engine = ConsensusEngine()

    def test_empty_results_returns_invalid(self):
        result = self.engine.compute([])
        assert result.is_valid is False
        assert result.direction == "NEUTRAL"

    def test_all_buy_signals(self):
        results = [
            _make_result("MultiTimeframe", 85, "BUY"),
            _make_result("SmartMoney", 90, "BUY"),
            _make_result("PriceAction", 80, "BUY"),
            _make_result("TechnicalIndicators", 78, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert consensus.direction == "BUY"
        assert consensus.consensus_score >= settings.MIN_CONSENSUS_SCORE
        assert consensus.agreement_count == 4

    def test_all_sell_signals(self):
        results = [
            _make_result("MultiTimeframe", 15, "SELL"),
            _make_result("SmartMoney", 20, "SELL"),
            _make_result("PriceAction", 18, "SELL"),
            _make_result("TechnicalIndicators", 22, "SELL"),
        ]
        consensus = self.engine.compute(results)
        assert consensus.direction == "SELL"
        assert consensus.agreement_count == 4

    def test_mixed_signals_neutral(self):
        results = [
            _make_result("MultiTimeframe", 70, "BUY"),
            _make_result("SmartMoney", 30, "SELL"),
            _make_result("PriceAction", 50, "NEUTRAL"),
            _make_result("TechnicalIndicators", 48, "NEUTRAL"),
        ]
        consensus = self.engine.compute(results)
        assert consensus.direction == "NEUTRAL"
        assert consensus.is_valid is False

    def test_confidence_label_very_high(self):
        results = [
            _make_result("MultiTimeframe", 92, "BUY"),
            _make_result("SmartMoney", 95, "BUY"),
            _make_result("PriceAction", 90, "BUY"),
            _make_result("TechnicalIndicators", 88, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert consensus.confidence_label in ("HIGH", "VERY_HIGH")

    def test_confidence_label_low(self):
        results = [
            _make_result("MultiTimeframe", 55, "BUY", 0.3),
            _make_result("SmartMoney", 52, "BUY", 0.2),
        ]
        consensus = self.engine.compute(results)
        # Low scores below MIN_CONSENSUS_SCORE → not valid
        assert consensus.is_valid is False

    def test_score_in_range(self):
        results = [
            _make_result("MultiTimeframe", 80, "BUY"),
            _make_result("SmartMoney", 85, "BUY"),
            _make_result("PriceAction", 75, "BUY"),
            _make_result("TechnicalIndicators", 70, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert 0 <= consensus.consensus_score <= 100

    def test_strategy_scores_captured(self):
        results = [
            _make_result("MultiTimeframe", 82, "BUY"),
            _make_result("SmartMoney", 88, "BUY"),
            _make_result("PriceAction", 76, "BUY"),
            _make_result("TechnicalIndicators", 71, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert "MultiTimeframe" in consensus.strategy_scores
        assert "SmartMoney" in consensus.strategy_scores
        assert consensus.strategy_scores["MultiTimeframe"] == 82

    def test_minimum_consensus_threshold(self):
        # Signals just below threshold should not be valid
        score = settings.MIN_CONSENSUS_SCORE - 5
        results = [
            _make_result("MultiTimeframe", score, "BUY"),
            _make_result("SmartMoney", score, "BUY"),
            _make_result("PriceAction", score, "BUY"),
            _make_result("TechnicalIndicators", score, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert consensus.is_valid is False

    def test_weighted_score_calculation(self):
        results = [
            _make_result("MultiTimeframe", 80, "BUY"),
            _make_result("SmartMoney", 80, "BUY"),
            _make_result("PriceAction", 80, "BUY"),
            _make_result("TechnicalIndicators", 80, "BUY"),
        ]
        consensus = self.engine.compute(results)
        # All scores 80, weighted average should be ~80
        assert 70 <= consensus.weighted_score <= 90

    def test_partial_strategies(self):
        results = [
            _make_result("MultiTimeframe", 85, "BUY"),
            _make_result("SmartMoney", 88, "BUY"),
        ]
        consensus = self.engine.compute(results)
        assert isinstance(consensus, ConsensusResult)
        assert consensus.total_strategies == 2
