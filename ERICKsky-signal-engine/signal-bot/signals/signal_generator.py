"""
ERICKsky Signal Engine - Signal Generator
Orchestrates strategy analysis, filtering, and signal object creation.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from config import settings
from data.data_fetcher import data_fetcher
from database.models import Signal
from database.repositories import SignalRepository
from strategies.multi_timeframe import MultiTimeframeStrategy
from strategies.smart_money import SmartMoneyStrategy
from strategies.price_action import PriceActionStrategy
from strategies.technical import TechnicalStrategy
from strategies.consensus_engine import ConsensusEngine, ConsensusResult
from strategies.market_context import MarketContextBuilder
from filters.news_filter import NewsFilter
from filters.session_filter import SessionFilter
from filters.spread_filter import SpreadFilter
from filters.volatility_filter import VolatilityFilter
from config.settings import BREAKEVEN_TRIGGER_PCT, BREAKEVEN_BUFFER_PIPS, PIP_VALUES as _PIP_VALUES

logger = logging.getLogger(__name__)


class SignalGenerator:
    """
    Main orchestrator: fetches data, runs 4 strategies, applies filters,
    and produces a validated Signal object ready for delivery.
    """

    def __init__(self) -> None:
        # Strategies
        self.strategies = [
            MultiTimeframeStrategy(),
            SmartMoneyStrategy(),
            PriceActionStrategy(),
            TechnicalStrategy(),
        ]
        self.consensus = ConsensusEngine()

        # Filters
        self.news_filter = NewsFilter()
        self.session_filter = SessionFilter()
        self.spread_filter = SpreadFilter()
        self.volatility_filter = VolatilityFilter()

    def generate(
        self,
        symbol: str,
        force_session: bool = False,
    ) -> Optional[Signal]:
        """
        Full pipeline: data -> strategies -> consensus -> filters -> Signal.

        Args:
            symbol:        Trading pair to scan
            force_session: Skip session filter (for testing)

        Returns:
            Signal object if all checks pass, None otherwise.
        """
        logger.info("=== Generating signal for %s ===", symbol)

        # ── 1. Session filter ─────────────────────────────────────────────────
        if not force_session:
            session_ok, session_reason = self.session_filter.passes(symbol)
            if not session_ok:
                logger.info("Signal skipped (%s): %s", symbol, session_reason)
                return None

        # ── 2. Fetch multi-timeframe data ─────────────────────────────────────
        data = data_fetcher.get_multi_timeframe(
            symbol,
            timeframes=[
                settings.ENTRY_TIMEFRAME,   # "15min"
                settings.PRIMARY_TIMEFRAME, # "1h"
                settings.TREND_TIMEFRAME,   # "4h"
                "1day",                     # D1 for trend context
            ],
        )

        # Add uppercase aliases so strategies can find "D1", "H4", "H1", "M15"
        _ALIASES = {"1day": "D1", "4h": "H4", "1h": "H1", "15min": "M15"}
        for api_key, alias in _ALIASES.items():
            if api_key in data and data[api_key] is not None:
                data[alias] = data[api_key]

        primary_df = data.get(settings.PRIMARY_TIMEFRAME)
        if primary_df is None or primary_df.empty:
            logger.warning("No primary data for %s, skipping", symbol)
            return None

        # ── 3. Volatility filter ──────────────────────────────────────────────
        vol_ok, vol_reason = self.volatility_filter.passes(symbol, primary_df)

        # ── 4. News filter ────────────────────────────────────────────────────
        news_ok, news_reason = self.news_filter.passes(symbol)

        # ── 5. Spread filter ──────────────────────────────────────────────────
        spread_ok, spread_reason = self.spread_filter.passes(symbol)

        filters_passed = {
            "session": True,
            "volatility": vol_ok,
            "news": news_ok,
            "spread": spread_ok,
        }

        if not all([vol_ok, news_ok, spread_ok]):
            blocking = [k for k, v in filters_passed.items() if not v]
            logger.info("Signal blocked for %s. Failed filters: %s", symbol, blocking)
            return None

        # ── 6. Build SharedMarketContext (ONCE for all strategies) ────────────
        ctx = None
        try:
            ctx = MarketContextBuilder().build(symbol, data)
            logger.info(
                f"SharedMarketContext built for {symbol}: "
                f"SMC_setup={ctx.complete_smc_setup}({ctx.smc_setup_direction}:{ctx.smc_setup_score:.0f})"
            )
        except Exception as exc:
            logger.warning(f"Failed to build MarketContext for {symbol}: {exc}")
        
        # ── 7. Run all 4 strategies (WITH shared context) ─────────────────────
        results = []
        for strategy in self.strategies:
            try:
                result = strategy.analyze(symbol, data, ctx)
                if result.is_valid():
                    results.append(result)
                    logger.debug(
                        "%s: %s score=%d conf=%.2f",
                        strategy.name, result.direction, result.score, result.confidence,
                    )
            except Exception as exc:
                logger.error("Strategy %s failed for %s: %s", strategy.name, symbol, exc)

        if not results:
            logger.warning("All strategies failed for %s", symbol)
            return None

        # ── 7. Consensus voting ───────────────────────────────────────────────
        consensus = self.consensus.compute(results)
        logger.info(
            "Consensus for %s: direction=%s score=%d valid=%s",
            symbol, consensus.direction, consensus.consensus_score, consensus.is_valid,
        )

        if not consensus.is_valid:
            logger.info(
                "Consensus not met for %s (score=%d, direction=%s)",
                symbol, consensus.consensus_score, consensus.direction,
            )
            return None

        # ── 8. Check duplicate signals (BUG FIX 3) ────────────────────────────
        # Check if same pair+direction signal was sent in last 4 hours
        duplicates = SignalRepository.find_duplicate_recent(
            symbol, consensus.direction, hours=4
        )
        if duplicates:
            logger.warning(
                "🚫 DUPLICATE BLOCK: %s %s already sent in last 4 hours (id=%s). "
                "Skipping to avoid spam!",
                symbol, consensus.direction, duplicates[0].id
            )
            return None

        # Also check max signals per day limit
        existing_today = SignalRepository.find_by_pair_today(symbol)
        same_direction = [
            s for s in existing_today
            if s.direction == consensus.direction and s.status == "PENDING"
        ]
        if len(same_direction) >= settings.MAX_SIGNALS_PER_PAIR_PER_DAY:
            logger.info(
                "Max signals/day reached for %s %s", symbol, consensus.direction
            )
            return None

        # ── 9. Calculate entry, SL, TP ────────────────────────────────────────
        current_price = data_fetcher.get_latest_price(symbol)
        if not current_price:
            current_price = float(primary_df["close"].iloc[-1])

        entry, sl, tp1, tp2, tp3, atr = self._calculate_levels(
            symbol, consensus.direction, current_price, primary_df
        )

        # ── 9b. Calculate Smart Entry (NEW) ────────────────────────────────
        smart_entry = self._calculate_smart_entry(
            consensus.direction, entry, atr, symbol
        )
        
        # Debug logging for smart entry
        logger.info(
            f"Smart entry: entry={entry:.5f} limit={smart_entry['limit_entry']:.5f} "
            f"atr={atr:.5f} zone_low={smart_entry['entry_zone_low']:.5f} "
            f"zone_high={smart_entry['entry_zone_high']:.5f}"
        )

        # ── 10. Build Signal object ────────────────────────────────────────────
        # Get individual strategy directions for debugging
        strategy_dirs = consensus.strategy_directions if consensus.strategy_directions else {}
        logger.info(f"Strategy directions: {strategy_dirs}")
        
        # Map individual strategy directions from results
        mtf_dir = "NEUTRAL"
        smc_dir = "NEUTRAL"
        pa_dir = "NEUTRAL"
        tech_dir = "NEUTRAL"
        
        for r in results:
            if r.strategy_name == "MultiTimeframe":
                mtf_dir = r.direction
            elif r.strategy_name == "SmartMoney":
                smc_dir = r.direction
            elif r.strategy_name == "PriceAction":
                pa_dir = r.direction
            elif r.strategy_name == "TechnicalIndicators":
                tech_dir = r.direction
        
        # ── 10b. Calculate breakeven trigger (ACTIVE MANAGEMENT) ──────────
        be_trigger_pct = BREAKEVEN_TRIGGER_PCT  # 0.50
        pip_size = _PIP_VALUES.get(symbol.upper(), 0.0001)
        tp1_dist = abs(tp1 - entry)
        if consensus.direction == "BUY":
            be_trigger_price = round(entry + tp1_dist * be_trigger_pct, 5)
            be_sl_price = round(entry + BREAKEVEN_BUFFER_PIPS * pip_size, 5)
        else:
            be_trigger_price = round(entry - tp1_dist * be_trigger_pct, 5)
            be_sl_price = round(entry - BREAKEVEN_BUFFER_PIPS * pip_size, 5)

        signal = Signal(
            pair=symbol,
            direction=consensus.direction,
            entry_price=round(entry, 5),
            stop_loss=round(sl, 5),
            take_profit_1=round(tp1, 5),
            take_profit_2=round(tp2, 5) if tp2 else None,
            take_profit_3=round(tp3, 5) if tp3 else None,
            timeframe=settings.PRIMARY_TIMEFRAME,
            order_type="LIMIT",  # Changed to LIMIT for smart entry
            strategy_scores={r.strategy_name: r.score for r in results},
            strategy_directions=consensus.strategy_directions,
            agreement_count=consensus.agreement_count,
            consensus_score=consensus.consensus_score,
            confidence=consensus.confidence_label,
            filters_passed=filters_passed,
            status="PENDING",
            sent_at=datetime.now(timezone.utc),
            # Smart Entry Fields (NEW)
            market_entry=smart_entry["market_entry"],
            limit_entry=smart_entry["limit_entry"],
            entry_zone_high=smart_entry["entry_zone_high"],
            entry_zone_low=smart_entry["entry_zone_low"],
            entry_recommendation=smart_entry["entry_recommendation"],
            candle_confirmation=smart_entry["candle_confirmation"],
            entry_window_minutes=smart_entry["entry_window_minutes"],
            atr_value=smart_entry["atr_value"],
            # Individual strategy directions (NEW)
            mtf_direction=mtf_dir,
            smc_direction=smc_dir,
            pa_direction=pa_dir,
            tech_direction=tech_dir,
        )

        logger.info(
            "Signal GENERATED: %s %s @ %.5f SL=%.5f TP1=%.5f [%s]",
            symbol, consensus.direction, entry, sl, tp1, consensus.confidence_label,
        )
        return signal

    def _calculate_levels(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        df: pd.DataFrame,
    ) -> tuple:
        """Calculate SL and TP levels using ATR. Returns (entry, sl, tp1, tp2, tp3, atr)."""
        from config.settings import PIP_VALUES

        pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)

        # ATR-based SL
        high = df["high"]
        low = df["low"]
        prev_close = df["close"].shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(span=14, adjust=False).mean().iloc[-1]

        # Use 1.5x ATR for SL
        sl_distance = atr * 1.5

        if direction == "BUY":
            sl = entry_price - sl_distance
            tp1 = entry_price + sl_distance * settings.TP1_MULTIPLIER
            tp2 = entry_price + sl_distance * settings.TP2_MULTIPLIER
            tp3 = entry_price + sl_distance * settings.TP3_MULTIPLIER
        else:
            sl = entry_price + sl_distance
            tp1 = entry_price - sl_distance * settings.TP1_MULTIPLIER
            tp2 = entry_price - sl_distance * settings.TP2_MULTIPLIER
            tp3 = entry_price - sl_distance * settings.TP3_MULTIPLIER

        return entry_price, sl, tp1, tp2, tp3, atr

    def _calculate_smart_entry(
        self,
        direction: str,
        entry_price: float,
        atr: float,
        symbol: str,
    ) -> dict:
        """
        Calculate optimal limit entry zone to avoid stop hunts.
        
        TIER 1: LIMIT ENTRY (Primary - Safest)
        - For BUY: Place limit below market (atr * 0.35)
        - For SELL: Place limit above market (atr * 0.35)
        
        This is where banks often finish their stop hunt before going in true direction.
        """
        pip = 0.0001  # Standard pip size
        
        if direction == "BUY":
            # Optimal limit entry (below market for pullback)
            limit_entry = round(entry_price - (atr * 0.35), 5)
            # Entry zone (acceptable range)
            entry_zone_low = round(entry_price - (atr * 0.5), 5)
            entry_zone_high = round(entry_price + (atr * 0.1), 5)
            recommendation = (
                f"Place BUY LIMIT at {limit_entry}\n"
                f"Or wait for pullback to zone:\n"
                f"{entry_zone_low} – {entry_zone_high}"
            )
        else:  # SELL
            limit_entry = round(entry_price + (atr * 0.35), 5)
            entry_zone_low = round(entry_price - (atr * 0.1), 5)
            entry_zone_high = round(entry_price + (atr * 0.5), 5)
            recommendation = (
                f"Place SELL LIMIT at {limit_entry}\n"
                f"Or wait for rally to zone:\n"
                f"{entry_zone_low} – {entry_zone_high}"
            )
        
        return {
            "market_entry": round(entry_price, 5),
            "limit_entry": limit_entry,
            "entry_zone_high": entry_zone_high,
            "entry_zone_low": entry_zone_low,
            "entry_recommendation": recommendation,
            "entry_window_minutes": 90,
            "candle_confirmation": True,
            "atr_value": atr,
        }


# Module-level singleton
signal_generator = SignalGenerator()
