"""Strategies package for ERICKsky Signal Engine."""
# Core strategies
from strategies.multi_timeframe import MultiTimeframeStrategy
from strategies.smart_money import SmartMoneyStrategy
from strategies.price_action import PriceActionStrategy
from strategies.technical import TechnicalStrategy
from strategies.consensus_engine import ConsensusEngine
# Institutional upgrades
from strategies.m15_confirmation import m15_confirmation
from strategies.chart_patterns import chart_pattern_detector

__all__ = [
    "MultiTimeframeStrategy",
    "SmartMoneyStrategy",
    "PriceActionStrategy",
    "TechnicalStrategy",
    "ConsensusEngine",
    "m15_confirmation",
    "chart_pattern_detector",
]
