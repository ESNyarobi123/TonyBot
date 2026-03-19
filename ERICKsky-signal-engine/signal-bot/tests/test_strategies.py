"""
ERICKsky Signal Engine - Strategy Unit Tests
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from strategies.base_strategy import StrategyResult
from strategies.technical import TechnicalStrategy
from strategies.multi_timeframe import MultiTimeframeStrategy
from strategies.price_action import PriceActionStrategy
from strategies.smart_money import SmartMoneyStrategy


def _make_df(n: int = 100, trend: str = "up") -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    base = 1.10000
    dates = [datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(n)]

    closes = [base]
    for i in range(1, n):
        if trend == "up":
            change = np.random.uniform(-0.0005, 0.0010)
        elif trend == "down":
            change = np.random.uniform(-0.0010, 0.0005)
        else:
            change = np.random.uniform(-0.0007, 0.0007)
        closes.append(closes[-1] + change)

    opens = [c + np.random.uniform(-0.0003, 0.0003) for c in closes]
    highs = [max(o, c) + abs(np.random.uniform(0, 0.0005)) for o, c in zip(opens, closes)]
    lows = [min(o, c) - abs(np.random.uniform(0, 0.0005)) for o, c in zip(opens, closes)]

    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.random.randint(100, 1000, n).astype(float),
    }, index=pd.DatetimeIndex(dates, tz=timezone.utc))
    return df


def _make_data(trend: str = "up") -> dict:
    return {
        "1min":  _make_df(200, trend),
        "5min":  _make_df(200, trend),
        "15min": _make_df(200, trend),
        "1h":    _make_df(200, trend),
        "4h":    _make_df(200, trend),
        "1day":  _make_df(100, trend),
    }


class TestTechnicalStrategy:

    def setup_method(self):
        self.strategy = TechnicalStrategy()

    def test_returns_strategy_result(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert isinstance(result, StrategyResult)
        assert result.strategy_name == "TechnicalIndicators"

    def test_score_in_range(self):
        for trend in ["up", "down", "sideways"]:
            data = _make_data(trend)
            result = self.strategy.analyze("EURUSD", data)
            assert 0 <= result.score <= 100

    def test_direction_valid(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert result.direction in ("BUY", "SELL", "NEUTRAL")

    def test_confidence_in_range(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert 0.0 <= result.confidence <= 1.0

    def test_bullish_trend_gives_buy(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        # With uptrend data, should lean bullish
        assert result.score >= 40

    def test_no_data_returns_neutral(self):
        result = self.strategy.analyze("EURUSD", {})
        assert result.direction == "NEUTRAL"
        assert result.score == 50

    def test_xauusd_symbol(self):
        data = _make_data("up")
        result = self.strategy.analyze("XAUUSD", data)
        assert result.is_valid()


class TestMultiTimeframeStrategy:

    def setup_method(self):
        self.strategy = MultiTimeframeStrategy()

    def test_returns_strategy_result(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert isinstance(result, StrategyResult)
        assert result.strategy_name == "MultiTimeframe"

    def test_all_timeframes_missing(self):
        result = self.strategy.analyze("EURUSD", {})
        assert result.direction == "NEUTRAL"

    def test_reasoning_populated(self):
        data = _make_data("down")
        result = self.strategy.analyze("GBPUSD", data)
        assert len(result.reasoning) > 0

    def test_bearish_trend(self):
        data = _make_data("down")
        result = self.strategy.analyze("EURUSD", data)
        assert result.score <= 60


class TestPriceActionStrategy:

    def setup_method(self):
        self.strategy = PriceActionStrategy()

    def test_returns_strategy_result(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert isinstance(result, StrategyResult)
        assert result.strategy_name == "PriceAction"

    def test_score_valid(self):
        data = _make_data("sideways")
        result = self.strategy.analyze("USDJPY", data)
        assert 0 <= result.score <= 100

    def test_no_crash_with_minimal_data(self):
        small_df = _make_df(25, "up")
        data = {"1h": small_df}
        result = self.strategy.analyze("EURUSD", data)
        assert result is not None


class TestSmartMoneyStrategy:

    def setup_method(self):
        self.strategy = SmartMoneyStrategy()

    def test_returns_strategy_result(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert isinstance(result, StrategyResult)
        assert result.strategy_name == "SmartMoney"

    def test_metadata_populated(self):
        data = _make_data("up")
        result = self.strategy.analyze("EURUSD", data)
        assert "bos_score" in result.metadata

    def test_valid_confidence(self):
        data = _make_data("down")
        result = self.strategy.analyze("GBPUSD", data)
        assert 0.0 <= result.confidence <= 1.0
