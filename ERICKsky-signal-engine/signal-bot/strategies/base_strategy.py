"""
ERICKsky Signal Engine - Abstract Base Strategy
All strategies inherit from this class and implement analyze().
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class StrategyResult:
    """
    Output of a single strategy's analysis.
    score: 0-100  (0 = strong SELL, 50 = neutral, 100 = strong BUY)
    direction: BUY | SELL | NEUTRAL
    confidence: 0.0-1.0
    """
    strategy_name: str
    score: int
    direction: str
    confidence: float
    reasoning: str = ""
    metadata: Dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        return (
            0 <= self.score <= 100
            and self.direction in ("BUY", "SELL", "NEUTRAL")
            and 0.0 <= self.confidence <= 1.0
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction == "BUY" and self.score >= 60

    @property
    def is_bearish(self) -> bool:
        return self.direction == "SELL" and self.score <= 40

    @property
    def is_neutral(self) -> bool:
        return self.direction == "NEUTRAL" or 40 < self.score < 60

    def __repr__(self) -> str:
        return (
            f"<StrategyResult {self.strategy_name}: "
            f"{self.direction} score={self.score} conf={self.confidence:.2f}>"
        )


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    name: str = "BaseStrategy"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def analyze(
        self,
        symbol: str,
        data: Dict[str, Optional[pd.DataFrame]],
    ) -> StrategyResult:
        """
        Run the strategy analysis.
        Args:
            symbol: Trading pair e.g. "EURUSD"
            data:   Dict mapping interval -> OHLCV DataFrame
        Returns:
            StrategyResult with score, direction, and reasoning.
        """
        ...

    @staticmethod
    def _get_df(data: Dict[str, Optional[pd.DataFrame]], interval: str) -> Optional[pd.DataFrame]:
        df = data.get(interval)
        if df is None or df.empty or len(df) < 20:
            return None
        return df.copy()

    @staticmethod
    def _safe_score(raw: float) -> int:
        return int(max(0.0, min(100.0, round(raw))))

    @staticmethod
    def _pips(symbol: str, price_diff: float) -> float:
        from config.settings import PIP_VALUES
        pip_size = PIP_VALUES.get(symbol, 0.0001)
        return abs(price_diff) / pip_size

    @staticmethod
    def _ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _sma(series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period).mean()

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(span=period, adjust=False).mean()

    @staticmethod
    def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()
        rs = gain / loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _neutral_result(name: str, reason: str = "Insufficient data") -> StrategyResult:
        return StrategyResult(
            strategy_name=name,
            score=50,
            direction="NEUTRAL",
            confidence=0.0,
            reasoning=reason,
        )
