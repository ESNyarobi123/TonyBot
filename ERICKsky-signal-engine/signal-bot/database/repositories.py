"""
ERICKsky Signal Engine - Database Repositories
All DB read/write operations in one place.
"""

import json
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any

from database.db_manager import db
from database.models import Signal, Subscriber, PairPerformance, TelegramChannel, BotState

logger = logging.getLogger(__name__)


# ─── Signal Repository ────────────────────────────────────────────────────────

class SignalRepository:

    @staticmethod
    def save(signal: Signal) -> int:
        """Insert a new signal and return its ID."""
        query = """
            INSERT INTO signals (
                pair, direction, entry_price, stop_loss,
                take_profit_1, take_profit_2, take_profit_3,
                timeframe, strategy_scores, consensus_score,
                confidence, filters_passed, status, sent_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s::jsonb, %s,
                %s, %s::jsonb, %s, %s
            ) RETURNING id
        """
        params = (
            signal.pair, signal.direction, signal.entry_price, signal.stop_loss,
            signal.take_profit_1, signal.take_profit_2, signal.take_profit_3,
            signal.timeframe,
            json.dumps(signal.strategy_scores),
            signal.consensus_score,
            signal.confidence,
            json.dumps(signal.filters_passed),
            signal.status,
            signal.sent_at or datetime.utcnow(),
        )
        signal_id = db.execute_write(query, params)
        logger.info("Signal saved: id=%s %s %s", signal_id, signal.pair, signal.direction)
        return signal_id

    @staticmethod
    def find_by_id(signal_id: int) -> Optional[Signal]:
        row = db.execute_one("SELECT * FROM signals WHERE id = %s", (signal_id,))
        return SignalRepository._row_to_signal(row) if row else None

    @staticmethod
    def find_pending() -> List[Signal]:
        rows = db.execute(
            "SELECT * FROM signals WHERE status = 'PENDING' ORDER BY created_at DESC"
        )
        return [SignalRepository._row_to_signal(r) for r in rows]

    @staticmethod
    def find_by_pair_today(pair: str) -> List[Signal]:
        rows = db.execute(
            "SELECT * FROM signals WHERE pair = %s AND DATE(created_at) = CURRENT_DATE",
            (pair,),
        )
        return [SignalRepository._row_to_signal(r) for r in rows]

    @staticmethod
    def find_duplicate_recent(symbol: str, direction: str, hours: int = 4) -> List[Signal]:
        """Find signals with same pair+direction within last N hours."""
        rows = db.execute(
            """
            SELECT * FROM signals 
            WHERE pair = %s 
            AND direction = %s
            AND created_at > NOW() - INTERVAL '%s hours'
            AND status = 'PENDING'
            ORDER BY created_at DESC
            """,
            (symbol, direction, str(hours)),
        )
        return [SignalRepository._row_to_signal(r) for r in rows]

    @staticmethod
    def count_today() -> int:
        row = db.execute_one(
            "SELECT COUNT(*) AS cnt FROM signals WHERE DATE(created_at) = CURRENT_DATE"
        )
        return row["cnt"] if row else 0

    @staticmethod
    def update_status(
        signal_id: int,
        status: str,
        pips_result: Optional[float] = None,
        closed_at: Optional[datetime] = None,
    ) -> None:
        db.execute_write(
            """
            UPDATE signals
            SET status = %s, pips_result = %s, closed_at = %s
            WHERE id = %s
            """,
            (status, pips_result, closed_at or datetime.utcnow(), signal_id),
        )

    @staticmethod
    def get_recent(limit: int = 20) -> List[Signal]:
        rows = db.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT %s", (limit,)
        )
        return [SignalRepository._row_to_signal(r) for r in rows]

    @staticmethod
    def _row_to_signal(row: dict) -> Signal:
        return Signal(
            id=row["id"],
            pair=row["pair"],
            direction=row["direction"],
            entry_price=float(row["entry_price"]),
            stop_loss=float(row["stop_loss"]),
            take_profit_1=float(row["take_profit_1"]),
            take_profit_2=float(row["take_profit_2"]) if row.get("take_profit_2") else None,
            take_profit_3=float(row["take_profit_3"]) if row.get("take_profit_3") else None,
            timeframe=row["timeframe"],
            strategy_scores=row["strategy_scores"] or {},
            consensus_score=row["consensus_score"],
            confidence=row["confidence"],
            filters_passed=row["filters_passed"] or {},
            status=row["status"],
            pips_result=float(row["pips_result"]) if row.get("pips_result") else None,
            sent_at=row.get("sent_at"),
            closed_at=row.get("closed_at"),
            created_at=row.get("created_at"),
        )


# ─── Subscriber Repository ────────────────────────────────────────────────────

class SubscriberRepository:

    @staticmethod
    def save(subscriber: Subscriber) -> int:
        query = """
            INSERT INTO subscribers (
                telegram_chat_id, username, full_name, plan,
                subscribed_at, expires_at, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (telegram_chat_id) DO UPDATE SET
                username  = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                is_active = EXCLUDED.is_active
            RETURNING id
        """
        return db.execute_write(
            query,
            (
                subscriber.telegram_chat_id,
                subscriber.username,
                subscriber.full_name,
                subscriber.plan,
                subscriber.subscribed_at or datetime.utcnow(),
                subscriber.expires_at,
                subscriber.is_active,
            ),
        )

    @staticmethod
    def find_active() -> List[Subscriber]:
        rows = db.execute(
            "SELECT * FROM subscribers WHERE is_active = TRUE ORDER BY created_at DESC"
        )
        return [SubscriberRepository._row_to_subscriber(r) for r in rows]

    @staticmethod
    def find_premium_active() -> List[Subscriber]:
        rows = db.execute(
            """
            SELECT * FROM subscribers
            WHERE is_active = TRUE AND plan = 'PREMIUM'
              AND (expires_at IS NULL OR expires_at > NOW())
            """
        )
        return [SubscriberRepository._row_to_subscriber(r) for r in rows]

    @staticmethod
    def find_by_chat_id(chat_id: str) -> Optional[Subscriber]:
        row = db.execute_one(
            "SELECT * FROM subscribers WHERE telegram_chat_id = %s", (chat_id,)
        )
        return SubscriberRepository._row_to_subscriber(row) if row else None

    @staticmethod
    def increment_signals_received(chat_id: str) -> None:
        db.execute_write(
            """
            UPDATE subscribers
            SET total_signals_received = total_signals_received + 1
            WHERE telegram_chat_id = %s
            """,
            (chat_id,),
        )

    @staticmethod
    def deactivate(chat_id: str) -> None:
        db.execute_write(
            "UPDATE subscribers SET is_active = FALSE WHERE telegram_chat_id = %s",
            (chat_id,),
        )

    @staticmethod
    def _row_to_subscriber(row: dict) -> Subscriber:
        return Subscriber(
            id=row["id"],
            telegram_chat_id=row["telegram_chat_id"],
            username=row.get("username"),
            full_name=row.get("full_name"),
            plan=row["plan"],
            subscribed_at=row.get("subscribed_at"),
            expires_at=row.get("expires_at"),
            is_active=row["is_active"],
            total_signals_received=row.get("total_signals_received", 0),
            created_at=row.get("created_at"),
        )


# ─── Channel Repository ───────────────────────────────────────────────────────

class ChannelRepository:

    @staticmethod
    def find_active() -> List[TelegramChannel]:
        rows = db.execute("SELECT * FROM telegram_channels WHERE is_active = TRUE")
        return [
            TelegramChannel(
                id=r["id"],
                channel_name=r["channel_name"],
                chat_id=r["chat_id"],
                type=r["type"],
                is_active=r["is_active"],
                subscribers_count=r["subscribers_count"],
                created_at=r.get("created_at"),
            )
            for r in rows
        ]


# ─── BotState Repository ──────────────────────────────────────────────────────

class BotStateRepository:

    @staticmethod
    def get(key: str) -> Optional[str]:
        row = db.execute_one(
            "SELECT value FROM bot_state WHERE key = %s", (key,)
        )
        return row["value"] if row else None

    @staticmethod
    def set(key: str, value: str) -> None:
        db.execute_write(
            """
            INSERT INTO bot_state (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (key, value),
        )


# ─── Performance Repository ───────────────────────────────────────────────────

class PerformanceRepository:

    @staticmethod
    def get_summary() -> Dict[str, Any]:
        row = db.execute_one(
            """
            SELECT
                COUNT(*)                                        AS total_signals,
                SUM(CASE WHEN status = 'WIN'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN status = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                ROUND(
                    SUM(CASE WHEN status = 'WIN' THEN 1 ELSE 0 END)::decimal /
                    NULLIF(SUM(CASE WHEN status IN ('WIN','LOSS') THEN 1 ELSE 0 END), 0) * 100,
                    2
                )                                               AS win_rate,
                SUM(COALESCE(pips_result, 0))                   AS total_pips
            FROM signals
            WHERE DATE(created_at) = CURRENT_DATE
            """
        )
        return dict(row) if row else {}

    @staticmethod
    def get_by_pair() -> List[Dict[str, Any]]:
        rows = db.execute(
            """
            SELECT pair, win_rate, total_pips, signals_sent
            FROM pair_performance
            WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY win_rate DESC
            """
        )
        return [dict(r) for r in rows]
