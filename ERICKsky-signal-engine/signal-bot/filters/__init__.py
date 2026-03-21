"""Filters package for ERICKsky Signal Engine."""
# Core (original)
from filters.session_filter import session_filter
from filters.spread_filter import spread_filter
from filters.news_filter import news_filter
from filters.volatility_filter import volatility_filter
# Institutional upgrades
from filters.market_regime import market_regime_detector
from filters.consolidation_filter import consolidation_filter
from filters.correlation_filter import correlation_filter
from filters.session_analyzer import session_strength_analyzer

__all__ = [
    "session_filter",
    "spread_filter",
    "news_filter",
    "volatility_filter",
    "market_regime_detector",
    "consolidation_filter",
    "correlation_filter",
    "session_strength_analyzer",
]
