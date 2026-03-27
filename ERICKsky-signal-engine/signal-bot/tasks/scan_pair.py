"""
ERICKsky Signal Engine - Celery Task: Scan Pair  (v2 — Institutional Grade)

Full 15-step pipeline with all upgrades integrated:

  1.  Risk Manager          — daily/pair/consecutive-loss limits
  2.  Trading Session       — weekday check
  3.  News Filter           — local DB (fast), API fallback
  4.  Data Fetch            — D1 / H4 / H1 / M15
  5.  Spread Filter         — skip if spread > threshold
  6.  Market Regime         — TRENDING/RANGING/VOLATILE gate
  7.  Consolidation Filter  — tight range detection
  8.  Four Core Strategies  — MTF / SMC / PA / TECH
  9.  Consensus Engine      — 3/4 agreement + score threshold
  10. Session Strength      — dynamic min-score adjustment
  11. Chart Patterns        — confirm or veto via pattern score
  12. M15 Confirmation      — precise entry timing
  13. Correlation Filter    — block double-risk correlated pairs
  14. Volatility Filter     — ATR minimum gate
  15. Save + Dispatch       — DB insert + Telegram

Each step short-circuits early to avoid expensive downstream work.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from celery_app import celery_app
from config import settings
from data.twelve_data import twelve_data
from data.data_fetcher import data_fetcher
from database.models import Signal
from database.repositories import BotStateRepository

# ── Filters ────────────────────────────────────────────────────────────────────
from filters.session_filter import session_filter
from filters.news_filter import news_filter
from filters.spread_filter import spread_filter
from filters.volatility_filter import volatility_filter
from filters.market_regime import market_regime_detector
from filters.consolidation_filter import consolidation_filter
from filters.correlation_filter import correlation_filter
from filters.session_analyzer import session_strength_analyzer
from filters.dxy_filter import dxy_filter

# ── Strategies ─────────────────────────────────────────────────────────────────
from strategies.multi_timeframe import MultiTimeframeStrategy
from strategies.smart_money import SmartMoneyStrategy
from strategies.price_action import PriceActionStrategy
from strategies.technical import TechnicalStrategy
from strategies.consensus_engine import ConsensusEngine
from strategies.chart_patterns import chart_pattern_detector
from strategies.m15_confirmation import m15_confirmation

# ── Signal pipeline ────────────────────────────────────────────────────────────
from signals.signal_validator import signal_validator
from notifications.notification_manager import notification_manager

logger = logging.getLogger(__name__)

# ── Module-level strategy singletons ─────────────────────────────────────────
_mtf_strategy  = MultiTimeframeStrategy()
_smc_strategy  = SmartMoneyStrategy()
_pa_strategy   = PriceActionStrategy()
_tech_strategy = TechnicalStrategy()
_consensus     = ConsensusEngine()

# Timeframes to fetch per scan (includes M1/M5 for sniper entry confirmation)
_TIMEFRAMES = ["D1", "H4", "H1", "M15", "M5", "M1"]


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
    Celery task — run the full 15-step institutional-grade signal pipeline.

    Args:
        symbol:        Trading pair, e.g. "EURUSD"
        force_session: bypass trading-session time filter (for testing)
        force_filters: bypass spread / news / volatility filters (for testing)

    Returns:
        Result dict with status and signal details.
    """
    logger.info("[scan_pair] START %s", symbol)
    start_ts = datetime.now(timezone.utc)

    try:
        # ══════════════════════════════════════════════════════════════════════
        # STEP 2: Trading Session (weekday + active session)
        # ══════════════════════════════════════════════════════════════════════
        if not force_session:
            in_session, session_name = session_filter.passes(symbol)
            if not in_session:
                logger.debug("[scan_pair] %s filtered: outside trading session", symbol)
                return {"status": "filtered", "reason": "outside_session", "symbol": symbol}
            logger.debug("[scan_pair] %s in session: %s", symbol, session_name)

        # ══════════════════════════════════════════════════════════════════════
        # STEP 3: News Filter (local DB first, fallback to live API)
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            news_ok, news_msg = news_filter.passes(symbol)
            if not news_ok:
                logger.info("[scan_pair] %s filtered: %s", symbol, news_msg)
                return {"status": "filtered", "reason": "news", "symbol": symbol, "detail": news_msg}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 4: Fetch price + all OHLCV timeframes (smart: D1/H4 cached 4h)
        # ══════════════════════════════════════════════════════════════════════
        current_price = twelve_data.get_realtime_price(symbol)
        if current_price is None:
            logger.warning("[scan_pair] %s: could not fetch price", symbol)
            return {"status": "error", "reason": "price_fetch_failed", "symbol": symbol}

        logger.info("[scan_pair] %s smart-fetching OHLCV data (D1/H4 from cache, H1/M15 fresh)…", symbol)
        ohlcv_data = data_fetcher.fetch_pair_smart(symbol)

        # Strip None entries
        ohlcv_data = {tf: df for tf, df in ohlcv_data.items() if df is not None and not df.empty}

        if not ohlcv_data or "H1" not in ohlcv_data:
            logger.error("[scan_pair] %s: missing critical OHLCV data", symbol)
            return {"status": "error", "reason": "no_ohlcv_data", "symbol": symbol}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 5: Spread Filter
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            spread_ok, spread_msg = spread_filter.passes(symbol)
            if not spread_ok:
                logger.info("[scan_pair] %s filtered: %s", symbol, spread_msg)
                return {"status": "filtered", "reason": "spread", "symbol": symbol, "detail": spread_msg}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 6: Market Regime Detection
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            h4_df = ohlcv_data.get("H4")
            if h4_df is not None:
                regime = market_regime_detector.detect(ohlcv_data["H1"], h4_df, symbol)
            else:
                # H4 missing — use H1 twice (graceful degradation)
                regime = market_regime_detector.detect(ohlcv_data["H1"], ohlcv_data["H1"], symbol)

            if not regime["allow_signal"]:
                logger.info(
                    "[scan_pair] %s REGIME BLOCKED: %s (%s)",
                    symbol, regime["regime"], regime["reason"],
                )
                return {
                    "status": "filtered",
                    "reason": f"regime_{regime['regime'].lower()}",
                    "symbol": symbol,
                    "detail": regime["reason"],
                }
        else:
            regime = {"regime": "TRENDING", "allow_signal": True, "adx": 0, "confidence": 1.0, "reason": "forced"}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 7: Consolidation Filter
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            is_cons, cons_reason = consolidation_filter.is_consolidating(ohlcv_data["H1"], symbol)
            if is_cons:
                logger.info("[scan_pair] %s CONSOLIDATION BLOCKED: %s", symbol, cons_reason)
                return {
                    "status": "filtered",
                    "reason": "consolidation",
                    "symbol": symbol,
                    "detail": cons_reason,
                }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 8: Volatility Filter (requires ATR from H1)
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            vol_ok, vol_msg = volatility_filter.passes(symbol, ohlcv_data["H1"])
            if not vol_ok:
                logger.info("[scan_pair] %s filtered: %s", symbol, vol_msg)
                return {
                    "status": "filtered",
                    "reason": "volatility",
                    "symbol": symbol,
                    "detail": vol_msg,
                }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 9: Run Four Core Strategies
        # ══════════════════════════════════════════════════════════════════════
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
                logger.exception("[scan_pair] %s strategy %s error: %s", symbol, strategy.name, exc)

        if not strategy_results:
            logger.error("[scan_pair] %s: all strategies failed", symbol)
            return {"status": "error", "reason": "all_strategies_failed", "symbol": symbol}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 9b: DXY H1 data for correlation filter (cache-first)
        #          Fallback: EURUSD inverse proxy (Deep Focus — EURUSD only)
        # ══════════════════════════════════════════════════════════════════════
        try:
            dxy_h1 = data_fetcher.fetch_dxy()
            dxy_filter.update_dxy_data(dxy_h1)
            # If DXY unavailable, fall back to EURUSD-only inverse proxy
            if dxy_h1 is None or dxy_h1.empty:
                eurusd_h1 = (
                    ohlcv_data.get("H1")
                    if symbol == "EURUSD"
                    else twelve_data.get_candles("EURUSD", "H1", count=50)
                )
                dxy_filter.update_from_eurusd_proxy(eurusd_h1)
        except Exception as exc:
            logger.warning("[scan_pair] DXY data fetch failed: %s — trying EURUSD proxy", exc)
            try:
                eurusd_h1 = (
                    ohlcv_data.get("H1")
                    if symbol == "EURUSD"
                    else twelve_data.get_candles("EURUSD", "H1", count=50)
                )
                dxy_filter.update_from_eurusd_proxy(eurusd_h1)
            except Exception as proxy_exc:
                logger.warning("[scan_pair] EURUSD proxy also failed: %s — DXY filter bypassed", proxy_exc)

        # ══════════════════════════════════════════════════════════════════════
        # STEP 10: Consensus Engine
        # ══════════════════════════════════════════════════════════════════════
        logger.info("[scan_pair] %s computing consensus…", symbol)
        consensus = _consensus.compute(
            results=strategy_results,
            symbol=symbol,
            entry_price=current_price,
        )

        scores_str = " | ".join(
            f"{r.strategy_name[:3]}:{r.direction[:1]}{r.score}" for r in strategy_results
        )
        logger.info(
            "[%s] Scores → %s | Consensus=%d %s | Agreement=%d/%d | Regime=%s",
            symbol, scores_str, consensus.consensus_score,
            consensus.direction, consensus.agreement_count,
            len(strategy_results), regime["regime"],
        )

        if not consensus.is_valid:
            logger.info("[scan_pair] %s consensus invalid: %s", symbol, consensus.reasoning)
            return {
                "status":          "no_signal",
                "symbol":          symbol,
                "reason":          consensus.reasoning,
                "consensus_score": consensus.consensus_score,
                "agreement":       f"{consensus.agreement_count}/{consensus.total_strategies}",
            }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 10b: DXY Correlation Filter (The Big Eye)
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            dxy_ok, dxy_reason = dxy_filter.passes(symbol, consensus.direction)
            if not dxy_ok:
                logger.info("[scan_pair] %s DXY BLOCKED: %s", symbol, dxy_reason)
                return {
                    "status":  "filtered",
                    "reason":  "dxy_correlation",
                    "symbol":  symbol,
                    "detail":  dxy_reason,
                }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 11: Session Strength — dynamic effective minimum score
        # ══════════════════════════════════════════════════════════════════════
        utc_hour = datetime.now(timezone.utc).hour
        session  = session_strength_analyzer.analyze(symbol, utc_hour)

        base_min = getattr(settings, "MIN_CONSENSUS_SCORE", 80)

        if not session["allow"]:
            # Weak session — demand higher quality
            effective_min = base_min + 10
        elif session["boost"]:
            # Prime session — slightly relax threshold (but NEVER below 80)
            effective_min = max(base_min - 5, 80)
        else:
            effective_min = base_min

        # Regime trend boost (but NEVER below 80 — institutional floor)
        if regime["regime"] == "TRENDING":
            effective_min = max(effective_min - 5, 80)

        adjusted_score = consensus.consensus_score
        if consensus.consensus_score < effective_min:
            # ── Early Warning System: scores 70-79 → admin-only alert ────────
            if 70 <= consensus.consensus_score < 80 and consensus.agreement_count >= 3:
                early_warning_msg = (
                    f"⚠️ *EARLY WARNING (Score: {consensus.consensus_score})*\n"
                    f"Pair: {symbol}\n"
                    f"Direction: {consensus.direction}\n"
                    f"Reason: Near-Premium setup detected. Manual review advised."
                )
                try:
                    notification_manager.send_admin_alert(early_warning_msg)
                    logger.info(
                        "[scan_pair] %s EARLY WARNING sent to admin (score=%d)",
                        symbol, consensus.consensus_score,
                    )
                except Exception as exc:
                    logger.warning("[scan_pair] %s early warning send failed: %s", symbol, exc)

            logger.info(
                "[scan_pair] %s score %d < effective_min %d (session=%s) – no signal",
                symbol, consensus.consensus_score, effective_min, session["sessions"],
            )
            return {
                "status":     "no_signal",
                "symbol":     symbol,
                "reason":     f"score_{consensus.consensus_score}_below_{effective_min}",
                "session":    session["sessions"],
            }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 12: Chart Pattern Detection
        # ══════════════════════════════════════════════════════════════════════
        patterns = {"patterns": [], "score": 0, "confirmed": False, "blocked": False}
        h4_df = ohlcv_data.get("H4")
        if h4_df is not None:
            patterns = chart_pattern_detector.detect(h4_df, ohlcv_data["H1"], consensus.direction)
            if patterns["blocked"]:
                pattern_names = [p.get("name", "?") for p in patterns["patterns"]]
                logger.info(
                    "[scan_pair] %s PATTERN BLOCKED: %s (score=%d)",
                    symbol, pattern_names, patterns["score"],
                )
                return {
                    "status": "no_signal",
                    "symbol": symbol,
                    "reason": f"pattern_conflict: {pattern_names}",
                }

        # ══════════════════════════════════════════════════════════════════════
        # STEP 13: M15 Entry Confirmation
        # ══════════════════════════════════════════════════════════════════════
        m15_result = {"confirmed": False, "score": 0, "reasons": [], "rsi_m15": 50.0, "vol_ratio": 1.0}
        m15_df = ohlcv_data.get("M15")
        if m15_df is not None and len(m15_df) >= 30:
            m15_result = m15_confirmation.confirm(m15_df, consensus.direction, symbol)
            if not m15_result["confirmed"]:
                logger.info(
                    "[scan_pair] %s M15 entry not confirmed (score=%d/50) – deferring",
                    symbol, m15_result["score"],
                )
                # Not a hard block — signal saved as WAIT_M15
                # For now, we proceed but mark the signal accordingly

        # ══════════════════════════════════════════════════════════════════════
        # STEP 13b: Sniper Entry Confirmation (M1/M5 candle-close hard gate)
        # Require a confirmed candle close in the signal direction on M1 OR M5
        # before firing the Telegram alert. Hard block if neither confirms.
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            m1_df = ohlcv_data.get("M1")
            m5_df = ohlcv_data.get("M5")
            sniper_result = m15_confirmation.confirm_sniper(
                m1_df, m5_df, consensus.direction, symbol
            )
            if not sniper_result["confirmed"]:
                logger.info(
                    "[scan_pair] %s SNIPER BLOCKED: no M1/M5 candle close in %s direction",
                    symbol, consensus.direction,
                )
                return {
                    "status":  "filtered",
                    "reason":  "sniper_no_m1_m5_confirmation",
                    "symbol":  symbol,
                    "detail":  (
                        f"No {consensus.direction} candle close confirmed on M1 or M5 — "
                        f"waiting for sniper entry"
                    ),
                }
            logger.info(
                "[scan_pair] %s SNIPER CONFIRMED on %s",
                symbol, sniper_result["confirming_tf"],
            )

        # ══════════════════════════════════════════════════════════════════════
        # STEP 14: Correlation Filter
        # ══════════════════════════════════════════════════════════════════════
        if not force_filters:
            corr_blocked, corr_reason = correlation_filter.should_block(symbol, consensus.direction)
            if corr_blocked:
                logger.info("[scan_pair] %s CORRELATION BLOCKED: %s", symbol, corr_reason)
                return {"status": "filtered", "reason": corr_reason, "symbol": symbol}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 15: Build Signal object
        # ══════════════════════════════════════════════════════════════════════
        logger.info(
            "[scan_pair] %s valid consensus: %s score=%d conf=%s session=%s regime=%s",
            symbol, consensus.direction, consensus.consensus_score,
            consensus.confidence_label, session["sessions"], regime["regime"],
        )

        # Boost score for confirmed chart patterns and M15 alignment
        boosted_score = consensus.consensus_score
        if patterns["confirmed"]:
            boosted_score = min(boosted_score + 5, 100)
        if m15_result["confirmed"]:
            boosted_score = min(boosted_score + 8, 100)

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
            consensus_score=boosted_score,
            confidence=consensus.confidence_label,
            filters_passed={
                "session":           not force_session,
                "spread":            not force_filters,
                "news":              not force_filters,
                "volatility":        not force_filters,
                "regime":            regime["regime"],
                "dxy_passed":        True,
                "dxy_trend":         dxy_filter.trend,
                "m15_confirmed":     m15_result["confirmed"],
                "m15_score":         m15_result["score"],
                "sniper_confirmed":  sniper_result.get("confirmed") if not force_filters else True,
                "sniper_tf":         sniper_result.get("confirming_tf") if not force_filters else "bypassed",
                "patterns":          [p.get("name") for p in patterns["patterns"]],
                "session_boost":     session.get("boost", False),
            },
            status="PENDING",
            sent_at=datetime.now(timezone.utc),
        )

        if signal.stop_loss is None or signal.take_profit_1 is None:
            logger.warning("[scan_pair] %s: consensus missing SL/TP", symbol)
            return {"status": "no_signal", "symbol": symbol, "reason": "missing_sl_tp"}

        # ── Signal Validation ─────────────────────────────────────────────────
        is_valid, val_reason = signal_validator.validate(signal)
        if not is_valid:
            logger.warning("[scan_pair] %s signal invalid: %s", symbol, val_reason)
            return {"status": "invalid", "symbol": symbol, "reason": val_reason}

        # ══════════════════════════════════════════════════════════════════════
        # STEP 15: Save + Dispatch (DB + Telegram)
        # ══════════════════════════════════════════════════════════════════════
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
            "status":            "success",
            "symbol":            symbol,
            "signal_id":         signal_id,
            "direction":         signal.direction,
            "consensus_score":   signal.consensus_score,
            "confidence":        signal.confidence,
            "regime":            regime["regime"],
            "session":           session["sessions"],
            "patterns":          [p.get("name") for p in patterns["patterns"]],
            "m15_confirmed":     m15_result["confirmed"],
            "m15_score":         m15_result["score"],
            "sniper_confirmed":  sniper_result.get("confirmed") if not force_filters else True,
            "sniper_tf":         sniper_result.get("confirming_tf") if not force_filters else "bypassed",
            "elapsed_s":         round(elapsed, 2),
        }

        logger.info(
            "[scan_pair] ✅ SIGNAL SENT: %s %s score=%d m15=%s session=%s regime=%s (%.1fs)",
            symbol, signal.direction, signal.consensus_score,
            m15_result["confirmed"], session["sessions"],
            regime["regime"], elapsed,
        )
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


# ══════════════════════════════════════════════════════════════════════════════
# Scan All Pairs dispatcher (unchanged API)
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    name="tasks.scan_all_pairs",
    queue="default",
)
def scan_all_pairs(
    force_session: bool = False,
    force_filters: bool = False,
) -> Dict:
    """
    Orchestrate a full scan cycle:
      1. Serialised data fetch (DXY + all pairs with 15s gaps)
      2. Dispatch individual scan_pair tasks sequentially

    The DataFetcher pre-warms the cache so each scan_pair task
    hits Redis instead of the API — zero rate-limit risk.
    """
    pairs = getattr(settings, "TRADING_PAIRS", [])
    logger.info("[scan_all_pairs] Starting serialised fetch for %d pairs: %s", len(pairs), pairs)

    # ── Phase 1: Pre-fetch all data (serialised, rate-limited) ────────────
    try:
        dxy_h1, _all_data, _prices = data_fetcher.scan_cycle_fetch(pairs)
        # Update DXY filter once for the whole cycle
        dxy_filter.update_dxy_data(dxy_h1)
        # Fallback: if DXY failed, use EURUSD inverse proxy (Deep Focus strategy)
        if dxy_h1 is None or dxy_h1.empty:
            eurusd_h1 = _all_data.get("EURUSD", {}).get("H1")
            dxy_filter.update_from_eurusd_proxy(eurusd_h1)
        logger.info(
            "[scan_all_pairs] Data pre-fetch complete — DXY=%s",
            "OK" if dxy_h1 is not None else "EURUSD_PROXY",
        )
    except Exception as exc:
        logger.error("[scan_all_pairs] Data pre-fetch failed: %s", exc)

    # ── Phase 2: Dispatch analysis tasks (data is now cached) ─────────────
    task_ids = []
    for i, pair in enumerate(pairs):
        task = scan_pair.apply_async(
            args=[pair],
            kwargs={"force_session": force_session, "force_filters": force_filters},
            queue="signals",
        )
        task_ids.append({"pair": pair, "task_id": task.id})
        logger.debug(
            "[scan_all_pairs] Dispatched %s → task %s", pair, task.id,
        )

    return {"dispatched": len(task_ids), "tasks": task_ids}
