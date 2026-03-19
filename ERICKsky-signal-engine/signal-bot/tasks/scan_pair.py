"""
ERICKsky Signal Engine - Celery Task: Scan Pair

Exact scan flow with ordered fast-fail filters:

  1.  Trading session check    — only scan during London/NY/Tokyo overlap
  2.  Spread filter            — skip if spread > max_pips for the pair
  3.  News filter              — skip if high-impact news within ±30 min
  4.  Volatility filter        — skip if ATR < minimum threshold
  5a. MultiTimeframe strategy  ─┐
  5b. SmartMoney strategy       ├─ run all 4 in parallel
  5c. PriceAction strategy      │
  5d. TechnicalIndicators strat ┘
  6.  Consensus Engine         — 3/4 vote + score >= 75
  7.  Signal validation        — price logic, R:R >= 1.5
  8.  Dispatch                 — save to DB + Telegram

Each filter step returns early with {"status": "filtered", "reason": ...}
so expensive operations (API calls, strategy computation) are skipped.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from celery_app import celery_app
from config import settings
from data.twelve_data import twelve_data
from filters.session_filter import session_filter
from filters.spread_filter import spread_filter
from filters.news_filter import news_filter
from filters.volatility_filter import volatility_filter
from strategies.multi_timeframe import MultiTimeframeStrategy
from strategies.smart_money import SmartMoneyStrategy
from strategies.price_action import PriceActionStrategy
from strategies.technical import TechnicalStrategy
from strategies.consensus_engine import ConsensusEngine
from signals.signal_validator import signal_validator
from notifications.notification_manager import notification_manager
from database.models import Signal
from database.repositories import BotStateRepository

logger = logging.getLogger(__name__)

# ── Module-level singletons (instantiated once per worker process) ─────────────
_mtf_strategy   = MultiTimeframeStrategy()
_smc_strategy   = SmartMoneyStrategy()
_pa_strategy    = PriceActionStrategy()
_tech_strategy  = TechnicalStrategy()
_consensus      = ConsensusEngine()

# Timeframes to fetch per scan (D1/H4/H1 for strategies)
_TIMEFRAMES = ["D1", "H4", "H1"]


@celery_app.task(
    name="tasks.scan_pair",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    queue="signals",
    acks_late=True,
    reject_on_worker_lost=True,
)
def scan_pair(
    self,
    symbol: str,
    force_session: bool = False,
    force_filters: bool = False,
) -> Dict:
    """
    Celery task — run the full signal pipeline for a single trading pair.

    Args:
        symbol:        e.g. "EURUSD"
        force_session: bypass trading session time filter (for testing)
        force_filters: bypass spread/news/volatility filters (for testing)

    Returns:
        Result dict with status and signal details.
    """
    logger.info("[scan_pair] START %s", symbol)
    start_ts = datetime.now(timezone.utc)

    try:
        # ── FAST-FAIL FILTER 1: Trading Session ───────────────────────────────
        if not force_session:
            in_session, session_name = session_filter.passes(symbol)
            if not in_session:
                logger.debug("[scan_pair] %s filtered: outside trading session", symbol)
                return {
                    "status": "filtered",
                    "reason": "outside_session",
                    "symbol": symbol,
                }
            logger.debug("[scan_pair] %s in session: %s", symbol, session_name)

        # ── FAST-FAIL FILTER 2: Spread ────────────────────────────────────────
        if not force_filters:
            current_price = twelve_data.get_realtime_price(symbol)
            if current_price is None:
                logger.warning("[scan_pair] %s: could not fetch price for spread check", symbol)
                return {"status": "error", "reason": "price_fetch_failed", "symbol": symbol}

            spread_ok, spread_msg = spread_filter.passes(symbol)
            if not spread_ok:
                logger.info("[scan_pair] %s filtered: %s", symbol, spread_msg)
                return {"status": "filtered", "reason": "spread", "symbol": symbol, "detail": spread_msg}
        else:
            current_price = twelve_data.get_realtime_price(symbol)

        # ── FAST-FAIL FILTER 3: Economic News ────────────────────────────────
        if not force_filters:
            news_ok, news_msg = news_filter.passes(symbol)
            if not news_ok:
                logger.info("[scan_pair] %s filtered: %s", symbol, news_msg)
                return {"status": "filtered", "reason": "news", "symbol": symbol, "detail": news_msg}

        # ── DATA FETCH: All timeframes in one pass ────────────────────────────
        logger.info("[scan_pair] %s fetching OHLCV data…", symbol)
        ohlcv_data: Dict = {}
        for tf in _TIMEFRAMES:
            df = twelve_data.get_candles(symbol, tf, count=200)
            if df is not None and not df.empty:
                ohlcv_data[tf] = df
            else:
                logger.warning("[scan_pair] %s: empty/missing %s candles", symbol, tf)

        if not ohlcv_data:
            logger.error("[scan_pair] %s: no OHLCV data fetched", symbol)
            return {"status": "error", "reason": "no_ohlcv_data", "symbol": symbol}

        # ── FAST-FAIL FILTER 4: Volatility (requires ATR from H1) ────────────
        if not force_filters:
            h1_df = ohlcv_data.get("H1")
            if h1_df is not None:
                vol_ok, vol_msg = volatility_filter.passes(symbol, h1_df)
                if not vol_ok:
                    logger.info("[scan_pair] %s filtered: %s", symbol, vol_msg)
                    return {
                        "status": "filtered",
                        "reason": "volatility",
                        "symbol": symbol,
                        "detail": vol_msg,
                    }

        # ── STRATEGIES: Run all 4 ─────────────────────────────────────────────
        logger.info("[scan_pair] %s running strategies…", symbol)
        strategy_results = []

        for strategy in (_mtf_strategy, _smc_strategy, _pa_strategy, _tech_strategy):
            try:
                result = strategy.analyze(symbol, ohlcv_data)
                strategy_results.append(result)
                logger.debug(
                    "[scan_pair] %s %s → %s score=%d",
                    symbol, strategy.name, result.direction, result.score,
                )
            except Exception as exc:
                logger.exception(
                    "[scan_pair] %s strategy %s error: %s",
                    symbol, strategy.name, exc,
                )

        if not strategy_results:
            logger.error("[scan_pair] %s: all strategies failed", symbol)
            return {"status": "error", "reason": "all_strategies_failed", "symbol": symbol}

        # ── CONSENSUS ENGINE ──────────────────────────────────────────────────
        logger.info("[scan_pair] %s computing consensus…", symbol)
        consensus = _consensus.compute(
            results=strategy_results,
            symbol=symbol,
            entry_price=current_price,
        )

        # DEBUG: Always log strategy scores (even when no signal)
        strategy_scores_str = " | ".join(
            f"{r.strategy_name[:3]}:{r.direction[:1]}{r.score}"
            for r in strategy_results
        )
        logger.info(
            "[%s] Scores → %s | Consensus=%d %s | Agreement=%d/%d",
            symbol, strategy_scores_str, consensus.consensus_score,
            consensus.direction, consensus.agreement_count, len(strategy_results)
        )

        if not consensus.is_valid:
            logger.info(
                "[scan_pair] %s consensus invalid: %s", symbol, consensus.reasoning
            )
            return {
                "status": "no_signal",
                "symbol": symbol,
                "reason": consensus.reasoning,
                "consensus_score": consensus.consensus_score,
                "agreement": f"{consensus.agreement_count}/{consensus.total_strategies}",
            }

        # ── SIGNAL GENERATION (builds Signal object from consensus) ───────────
        logger.info(
            "[scan_pair] %s valid consensus: %s score=%d confidence=%s",
            symbol, consensus.direction, consensus.consensus_score, consensus.confidence_label,
        )

        signal = Signal(
            pair=symbol,
            direction=consensus.direction,
            entry_price=round(current_price, 5),
            stop_loss=round(consensus.sl_price, 5) if consensus.sl_price else None,
            take_profit_1=round(consensus.tp1_price, 5) if consensus.tp1_price else None,
            take_profit_2=round(consensus.tp2_price, 5) if consensus.tp2_price else None,
            take_profit_3=None,
            timeframe="H1",
            strategy_scores={r.strategy_name: r.score for r in strategy_results},
            consensus_score=consensus.consensus_score,
            confidence=consensus.confidence_label,
            filters_passed={
                "session": not force_session,
                "spread": not force_filters,
                "news": not force_filters,
                "volatility": not force_filters,
            },
            status="PENDING",
            sent_at=datetime.now(timezone.utc),
        )

        if signal.stop_loss is None or signal.take_profit_1 is None:
            logger.warning("[scan_pair] %s: consensus missing SL/TP levels", symbol)
            return {"status": "no_signal", "symbol": symbol, "reason": "missing_sl_tp"}

        # ── SIGNAL VALIDATION ─────────────────────────────────────────────────
        is_valid, reason = signal_validator.validate(signal)
        if not is_valid:
            logger.warning("[scan_pair] %s signal invalid: %s", symbol, reason)
            return {"status": "invalid", "symbol": symbol, "reason": reason}

        # ── DISPATCH (save + Telegram) ────────────────────────────────────────
        signal_id = notification_manager.dispatch_signal(signal)
        if not signal_id:
            logger.error("[scan_pair] %s dispatch failed", symbol)
            return {"status": "dispatch_failed", "symbol": symbol}

        # Update last-scan timestamp
        try:
            BotStateRepository.set("last_scan_at", start_ts.isoformat())
        except Exception as exc:
            logger.warning("[scan_pair] BotStateRepository update failed: %s", exc)

        elapsed = (datetime.now(timezone.utc) - start_ts).total_seconds()
        result = {
            "status":          "success",
            "symbol":          symbol,
            "signal_id":       signal_id,
            "direction":       signal.direction,
            "consensus_score": signal.consensus_score,
            "confidence":      signal.confidence,
            "elapsed_s":       round(elapsed, 2),
        }
        logger.info("[scan_pair] SUCCESS %s → %s", symbol, result)
        return result

    except Exception as exc:
        logger.exception("[scan_pair] Unhandled error for %s: %s", symbol, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            try:
                notification_manager.send_admin_alert(
                    f"scan_pair failed for {symbol} after max retries: {exc}"
                )
            except Exception:
                pass
            return {"status": "failed", "symbol": symbol, "error": str(exc)}


@celery_app.task(
    name="tasks.scan_all_pairs",
    queue="default",
)
def scan_all_pairs(
    force_session: bool = False,
    force_filters: bool = False,
) -> Dict:
    """
    Dispatch individual scan_pair tasks for all configured trading pairs.

    Returns a summary dict with task IDs for monitoring.
    """
    pairs = getattr(settings, "TRADING_PAIRS", [])
    logger.info("[scan_all_pairs] Dispatching %d pairs: %s", len(pairs), pairs)

    task_ids = []
    for i, pair in enumerate(pairs):
        # Stagger tasks by 15s to respect Twelve Data API limit (8 calls/min)
        countdown = i * 15
        task = scan_pair.apply_async(
            args=[pair],
            kwargs={
                "force_session": force_session,
                "force_filters": force_filters,
            },
            queue="signals",
            countdown=countdown,
        )
        task_ids.append({"pair": pair, "task_id": task.id})
        logger.debug("[scan_all_pairs] Dispatched %s → task %s (start in %ds)", pair, task.id, countdown)

    return {"dispatched": len(task_ids), "tasks": task_ids}
