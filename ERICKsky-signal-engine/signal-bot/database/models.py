"""
ERICKsky Signal Engine - Data Models (dataclasses, not ORM)
Lightweight Python representations of DB rows.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any


@dataclass
class Signal:
    pair: str
    direction: str                          # BUY | SELL
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    timeframe: str
    strategy_scores: Dict[str, int]         # {mtf: 80, smc: 90, pa: 75, tech: 85}
    consensus_score: int                    # 0–100
    confidence: str                         # LOW|MEDIUM|HIGH|VERY_HIGH
    filters_passed: Dict[str, bool]
    status: str = "PENDING"                 # PENDING|WIN|LOSS|EXPIRED
    pips_result: Optional[float] = None
    sent_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pair": self.pair,
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "stop_loss": float(self.stop_loss),
            "take_profit_1": float(self.take_profit_1),
            "take_profit_2": float(self.take_profit_2) if self.take_profit_2 else None,
            "take_profit_3": float(self.take_profit_3) if self.take_profit_3 else None,
            "timeframe": self.timeframe,
            "strategy_scores": self.strategy_scores,
            "consensus_score": self.consensus_score,
            "confidence": self.confidence,
            "filters_passed": self.filters_passed,
            "status": self.status,
            "pips_result": self.pips_result,
        }


@dataclass
class Subscriber:
    telegram_chat_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    plan: str = "FREE"                      # FREE|BASIC|PREMIUM
    subscribed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True
    total_signals_received: int = 0
    created_at: Optional[datetime] = None
    id: Optional[int] = None

    @property
    def is_premium(self) -> bool:
        return self.plan == "PREMIUM" and self.is_active

    @property
    def display_name(self) -> str:
        return self.full_name or self.username or f"User {self.telegram_chat_id}"


@dataclass
class PairPerformance:
    pair: str
    date: date
    signals_sent: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pips: float = 0.0
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class TelegramChannel:
    channel_name: str
    chat_id: str
    type: str = "FREE"                      # FREE|PREMIUM
    is_active: bool = True
    subscribers_count: int = 0
    created_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class BotState:
    key: str
    value: Optional[str]
    updated_at: Optional[datetime] = None
    id: Optional[int] = None


@dataclass
class OHLCV:
    """Single OHLCV candle representation."""
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open
