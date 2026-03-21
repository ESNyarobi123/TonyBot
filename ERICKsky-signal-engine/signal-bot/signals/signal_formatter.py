"""
ERICKsky Signal Engine — Signal Formatter  (v3.1 — Bug-Free)

Fixes applied in this version:
  v3.0 BUG 1: Strategy icons — fixed (read mtf/smc/pa/tech_direction fields)
  v3.0 BUG 2: Limit entry == market entry — fixed (layered fallback)
  v3.1 FIX A: Dead agree/total increment counters removed; single recount used
  v3.1 FIX B: _row_part closure-in-loop replaced with standalone static method
  v3.1 FIX C: `is_premium` guard logic corrected (was inverted)
  v3.1 FIX D: Dead unused session_boost variable removed
  v3.1 FIX E: _session_label if-elif chain fixed (overlapping branches / dead
               NEW YORK branch caused by wrong ordering)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from database.models import Signal
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# ── Strategy key → Signal attribute mappings ─────────────────────────────────
_SCORE_KEY_ORDER = [
    "MultiTimeframe",
    "SmartMoney",
    "PriceAction",
    "TechnicalIndicators",
]

_DIR_FIELD: Dict[str, str] = {
    "MultiTimeframe":      "mtf_direction",
    "SmartMoney":          "smc_direction",
    "PriceAction":         "pa_direction",
    "TechnicalIndicators": "tech_direction",
}

_SHORT: Dict[str, str] = {
    "MultiTimeframe":      "MTF",
    "SmartMoney":          "SMC",
    "PriceAction":         "PA ",
    "TechnicalIndicators": "TEC",
}

_EMOJI: Dict[str, str] = {
    "MultiTimeframe":      "📊",
    "SmartMoney":          "🧠",
    "PriceAction":         "🎯",
    "TechnicalIndicators": "⚙️",
}

# Fallback limit-entry pip offsets when ATR is unavailable
_PAIR_PIP_OFFSET: Dict[str, float] = {
    "EURUSD": 0.00060,
    "GBPUSD": 0.00070,
    "XAUUSD": 0.60,
    "AUDUSD": 0.00055,
    "USDJPY": 0.060,
    "USDCHF": 0.00060,
    "USDCAD": 0.00065,
    "NZDUSD": 0.00055,
}


class SignalFormatter:
    """
    Formats Signal dataclass objects into professional Telegram Markdown messages.

    Public API:
      format_signal(signal, is_premium)   → str
      format_daily_report(...)            → str
      format_alert(text)                  → str
    """

    # ── Public methods ────────────────────────────────────────────────────────

    def format_signal(self, signal: Signal, is_premium: bool = True) -> str:
        try:
            return self._build_signal(signal, is_premium)
        except Exception as exc:
            logger.exception("SignalFormatter._build_signal error: %s", exc)
            return f"⚠️ Signal formatting error: {exc}"

    def format_daily_report(
        self,
        date_str:   str,
        total:      int,
        wins:       int,
        losses:     int,
        pending:    int,
        total_pips: float,
    ) -> str:
        win_rate   = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0.0
        pips_emoji = "📈" if total_pips >= 0 else "📉"
        sign       = "+" if total_pips >= 0 else ""
        return (
            f"🔥 *ERICKsky Daily Report* 🔥\n"
            f"{'━' * 32}\n"
            f"📅 *{date_str}*\n\n"
            f"📡 *Signals Sent:* `{total}`\n"
            f"✅ *Wins:*         `{wins}`\n"
            f"❌ *Losses:*       `{losses}`\n"
            f"⏳ *Pending:*      `{pending}`\n"
            f"🎯 *Win Rate:*     `{win_rate}%`\n"
            f"{pips_emoji} *Total Pips:*   `{sign}{total_pips:.1f}`\n\n"
            f"{'━' * 32}\n"
            f"🏆 *ERICKsky Signal Engine*\n"
            f"📱 t.me/ERICKskySignals"
        )

    def format_alert(self, text: str) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"⚠️ *ERICKsky Alert*\n{text}\n🕐 {now}"

    # ── Core builder ─────────────────────────────────────────────────────────

    def _build_signal(self, signal: Signal, is_premium: bool) -> str:

        # ── Direction decorators ──────────────────────────────────────────────
        is_buy      = signal.direction == "BUY"
        dir_emoji   = "🟢" if is_buy else "🔴"
        dir_arrow   = "📈" if is_buy else "📉"
        action      = "BUY" if is_buy else "SELL"

        # ── Confidence / stars ────────────────────────────────────────────────
        score = signal.consensus_score
        if score >= 90:
            stars, conf_label, conf_emoji = "⭐⭐⭐⭐⭐", "VERY HIGH", "💎"
        elif score >= 80:
            stars, conf_label, conf_emoji = "⭐⭐⭐⭐",   "HIGH",      "🔥"
        elif score >= 70:
            stars, conf_label, conf_emoji = "⭐⭐⭐",     "MEDIUM",    "✅"
        else:
            stars, conf_label, conf_emoji = "⭐⭐",       "LOW",       "⚡"

        # ── Price helpers ─────────────────────────────────────────────────────
        pair = (signal.pair or "?").upper()

        def fmt(price: float) -> str:
            if pair == "XAUUSD":
                return f"{price:.2f}"
            if "JPY" in pair:
                return f"{price:.3f}"
            return f"{price:.5f}"

        def pips_dist(p1: float, p2: float) -> float:
            if pair == "XAUUSD":
                return abs(p1 - p2)
            pip_size = PIP_VALUES.get(pair, 0.0001)
            return abs(p1 - p2) / pip_size

        # ── Prices ───────────────────────────────────────────────────────────
        entry = float(signal.entry_price)
        sl    = float(signal.stop_loss)
        tp1   = float(signal.take_profit_1)
        tp2   = float(signal.take_profit_2) if signal.take_profit_2 else None
        tp3   = float(signal.take_profit_3) if signal.take_profit_3 else None

        sl_pips  = pips_dist(entry, sl)
        tp1_pips = pips_dist(entry, tp1)
        tp2_pips = pips_dist(entry, tp2) if tp2 else 0.0
        tp3_pips = pips_dist(entry, tp3) if tp3 else 0.0

        rr1 = tp1_pips / sl_pips if sl_pips > 0 else 0.0
        rr2 = tp2_pips / sl_pips if sl_pips > 0 else 0.0
        rr3 = tp3_pips / sl_pips if sl_pips > 0 else 0.0

        # ── Limit entry (BUG 2 FIX: layered fallback) ─────────────────────────
        lim      = self._resolve_limit_entry(signal, entry, pair, is_buy)
        lim_pips = pips_dist(entry, lim)

        # ── Strategy rows (BUG 1 FIX: reads dedicated direction fields) ────────
        agree, total_strats, rows = self._build_strategy_rows(signal, is_premium)

        # ── Valid until ───────────────────────────────────────────────────────
        window_min = getattr(signal, "entry_window_minutes", 90)
        if signal.sent_at:
            valid_until = signal.sent_at + timedelta(minutes=window_min)
            valid_str   = valid_until.strftime("%H:%M UTC")
        else:
            valid_str = f"{window_min} min"

        # ── Optional context block ─────────────────────────────────────────────
        extra_block = self._build_context_block(signal)

        # ── Trade management thresholds ───────────────────────────────────────
        be_pips    = max(round(sl_pips * 0.6), 5)
        close_pips = max(round(sl_pips),        8)

        # ── Smart entry labels ────────────────────────────────────────────────
        limit_action = "BUY LIMIT"  if is_buy else "SELL LIMIT"
        candle_rule  = "closes 🟢 bullish" if is_buy else "closes 🔴 bearish"
        chase_warn   = "chasing price UP! 📈" if is_buy else "chasing price DOWN! 📉"

        # ═════════════════════════════════════════════════════════════════════
        # MESSAGE ASSEMBLY
        # ═════════════════════════════════════════════════════════════════════
        msg = (
            f"{'🔥' * 3} *ERICKSKYBOT SIGNAL* {'🔥' * 3}\n"
            f"{'━' * 32}\n\n"
            f"{dir_emoji} *{pair}*  —  *{action}*  {dir_arrow}\n"
            f"{conf_emoji} {stars}  Score: *{score}/100*  |  {conf_label}\n\n"
        )

        if extra_block:
            msg += extra_block + "\n\n"

        # Trade setup box
        msg += (
            f"💰 *TRADE SETUP*\n"
            f"┌──────────────────────────────┐\n"
            f"│ 🎯 Entry:    `{fmt(entry)}`\n"
            f"│ 🛑 Stop Loss: `{fmt(sl)}`"
            f"  (-{sl_pips:.0f} pips)\n"
            f"│ ✅ TP1:      `{fmt(tp1)}`"
            f"  (+{tp1_pips:.0f} pips) RR 1:{rr1:.1f}\n"
        )
        if tp2:
            msg += (
                f"│ ✅ TP2:      `{fmt(tp2)}`"
                f"  (+{tp2_pips:.0f} pips) RR 1:{rr2:.1f}\n"
            )
        if tp3:
            msg += (
                f"│ 🏆 TP3:      `{fmt(tp3)}`"
                f"  (+{tp3_pips:.0f} pips) RR 1:{rr3:.1f}\n"
            )
        msg += f"└──────────────────────────────┘\n\n"

        # Smart entry guide
        msg += (
            f"📌 *SMART ENTRY GUIDE*\n"
            f"┌──────────────────────────────────┐\n"
            f"│ ⭐ *BEST:*  {limit_action} `{fmt(lim)}`\n"
            f"│      Wait for pullback"
            f" (-{lim_pips:.0f} pips) 🎯\n"
            f"│\n"
            f"│ ✅ *OK:*    Wait H1 candle close\n"
            f"│      Enter if candle {candle_rule}\n"
            f"│\n"
            f"│ ❌ *AVOID:* Market order now!\n"
            f"│      Never {chase_warn}\n"
            f"└──────────────────────────────────┘\n\n"

            f"⚠️ *ENTRY RULES:*\n"
            f"• Wait for pullback to limit zone\n"
            f"• Enter ONLY after H1 candle closes\n"
            f"• Place limit order — don't chase!\n"
            f"• Valid for next {window_min} minutes only\n\n"

            f"🏦 *Why limit entry?*\n"
            f"_Banks sweep stops BEFORE moving!_\n"
            f"_Wait for the dip = safer SL + better RR_ 📊\n\n"

            f"🔄 *TRADE MANAGEMENT:*\n"
            f"├ +{be_pips} pips → Move SL to entry ⚡\n"
            f"├ +{close_pips} pips → Close 50% position 💰\n"
            f"└ Remainder → Trail to TP2/TP3 🚀\n\n"

            f"{'━' * 32}\n"
            f"🧠 *Strategies: {agree}/{total_strats} agree*\n\n"
        )

        if rows:
            msg += "\n".join(rows) + "\n\n"

        # Footer
        msg += (
            f"{'━' * 32}\n"
            f"⏰ *Valid Until:* {valid_str}\n"
            f"💰 *Risk:* Max 1% per trade\n"
            f"📉 *SL Pips:* {sl_pips:.0f}  |  "
            f"*TP1 Pips:* {tp1_pips:.0f}\n"
            f"{'━' * 32}\n\n"
            f"🏆 *ERICKsky Signal Engine*\n"
            f"📱 t.me/ERICKskySignals\n\n"
            f"#{pair} #{action} #Forex #ERICKsky #Signals"
        )

        return msg

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_limit_entry(
        signal: Signal,
        entry:  float,
        pair:   str,
        is_buy: bool,
    ) -> float:
        """
        BUG 2 FIX — Three-layer fallback for a meaningful limit entry price.

        Priority:
          1. signal.limit_entry when it differs from market entry by ≥ 1 pip
          2. ATR × 0.40 when signal.atr_value is set
          3. Pair-specific hardcoded pip offset table
        """
        lim = getattr(signal, "limit_entry", None)
        atr = getattr(signal, "atr_value",   None)

        pip_size  = PIP_VALUES.get(pair, 0.0001)

        if lim is not None and abs(float(lim) - entry) >= pip_size:
            return float(lim)

        if atr and float(atr) > 0:
            offset = float(atr) * 0.40
            return round(entry - offset if is_buy else entry + offset, 5)

        offset = _PAIR_PIP_OFFSET.get(pair, 0.00060)
        return round(entry - offset if is_buy else entry + offset, 5)

    @staticmethod
    def _build_strategy_rows(
        signal:     Signal,
        is_premium: bool,
    ) -> Tuple[int, int, List[str]]:
        """
        BUG 1 FIX — Correct ✅/⚠️/⬜ icons using dedicated direction fields.

        FIX A: Removed the dead agree/total loop counters; a single clean
               list-comprehension recount is done after building `pairs`.
        FIX B: Replaced closure-in-loop _row_part with _format_row_part()
               static method to avoid the classic Python late-binding bug.
        FIX C: Corrected is_premium guard (was accidentally blocking premium
               users who had scores).

        Returns (agree_count, total_active, list_of_row_strings).
        """
        strategy_scores: Dict[str, int] = signal.strategy_scores or {}
        sig_dir = signal.direction

        # ── Build the (key, score, strat_dir, icon) tuples ───────────────────
        pairs: List[Tuple[str, int, str, str]] = []

        for key in _SCORE_KEY_ORDER:
            score     = int(strategy_scores.get(key, 0))
            dir_field = _DIR_FIELD.get(key, "")

            # Priority 1: dedicated Signal field (e.g. signal.mtf_direction)
            strat_dir = getattr(signal, dir_field, "NEUTRAL") if dir_field else "NEUTRAL"

            # Priority 2: strategy_directions dict fallback
            if strat_dir == "NEUTRAL" and signal.strategy_directions:
                strat_dir = signal.strategy_directions.get(key, "NEUTRAL")

            # Icon (BUG 1 FIX)
            if score == 0 or strat_dir == "NEUTRAL":
                icon = "⬜"
            elif strat_dir == sig_dir:
                icon = "✅"
            else:
                icon = "⚠️"

            pairs.append((key, score, strat_dir, icon))

        # ── FIX A: single clean recount (no duplicate counters) ───────────────
        total_active = sum(1 for _, s, _, _  in pairs if s > 0)
        agree        = sum(
            1 for _, s, d, _ in pairs
            if s > 0 and d == sig_dir
        )

        # ── FIX C: only return empty rows when there are truly no scores ──────
        if not strategy_scores:
            return agree, total_active, []

        # ── Build 2-column layout (FIX B: no closure-in-loop) ─────────────────
        rows: List[str] = []
        for i in range(0, len(pairs), 2):
            left_str  = SignalFormatter._format_row_part(pairs[i])
            if i + 1 < len(pairs):
                right_str = SignalFormatter._format_row_part(pairs[i + 1])
                rows.append(f"{left_str}   {right_str}")
            else:
                rows.append(left_str)

        return agree, total_active, rows

    @staticmethod
    def _format_row_part(p: Tuple[str, int, str, str]) -> str:
        """
        FIX B — Separate static method instead of closure inside a loop.
        Formats a single strategy row: icon + emoji + name + bar + score.
        """
        key, score, _strat_dir, icon = p
        short = _SHORT.get(key, key[:3])
        em    = _EMOJI.get(key, "📊")
        bar   = SignalFormatter._score_bar(score, width=8)
        return f"{icon} {em} *{short}* {bar} {score}/100"

    @staticmethod
    def _build_context_block(signal: Signal) -> str:
        """
        Optional context lines: regime, session, chart pattern, M15 status.
        FIX D: The unused session_boost look-up was removed.
        """
        lines: List[str] = []
        fp = signal.filters_passed or {}

        # Market regime
        regime = fp.get("regime") or getattr(signal, "market_regime", None)
        if regime:
            regime_emoji = {
                "TRENDING":   "🚀",
                "WEAK_TREND": "📊",
                "RANGING":    "⚠️",
                "VOLATILE":   "💥",
            }.get(str(regime), "📌")
            lines.append(f"{regime_emoji} *Regime:* {regime}")

        # Session — derive from current UTC hour if not stored on signal
        session_name: Optional[str] = getattr(signal, "session_name", None)
        if not session_name:
            utc_h        = datetime.now(timezone.utc).hour
            session_name = SignalFormatter._session_label(utc_h)
        if session_name:
            lines.append(f"🕐 *Session:* {session_name}")

        # Chart pattern
        pattern_list = fp.get("patterns") or []
        pattern_str  = ", ".join(
            str(p).replace("_", " ") for p in pattern_list if p
        )
        if pattern_str:
            lines.append(f"📐 *Pattern:* {pattern_str} ✅")

        # M15 entry confirmation
        m15_confirmed = fp.get("m15_confirmed")
        m15_score     = fp.get("m15_score", 0)
        if m15_confirmed is not None:
            m15_str = (
                f"✅ Confirmed (score={m15_score}/100)" if m15_confirmed
                else f"⏳ Waiting ({m15_score}/50)"
            )
            lines.append(f"📊 *M15 Entry:* {m15_str}")

        return "\n".join(lines)

    @staticmethod
    def _session_label(utc_hour: int) -> str:
        """
        Human-readable session name for the current UTC hour.

        FIX E: Corrected overlapping if-chain.  Previous version had:
          • L466 if 12≤h<16 → OVERLAP          ← correct
          • L468 if 7≤h<16  → LONDON           ← would shadow NY check below
          • L470 if 12≤h<21 → NEW YORK         ← DEAD: 7≤h<16 caught it first
          • L472 if 0≤h<8   → ASIAN            ← correct

        Fixed order: OVERLAP (most specific) → NY → LONDON → ASIAN → OFF-HOURS
        """
        if 12 <= utc_hour < 16:
            return "LONDON / NY OVERLAP 🔥"
        if 12 <= utc_hour < 21:
            return "NEW YORK 🇺🇸"
        if 7 <= utc_hour < 12:
            return "LONDON 🇬🇧"
        if 0 <= utc_hour < 7:
            return "ASIAN 🌏"
        return "OFF-HOURS 💤"

    @staticmethod
    def _score_bar(score: int, width: int = 8) -> str:
        """Unicode block bar.  score=75, width=8 → '██████░░'"""
        filled = max(0, min(width, round(score / 100 * width)))
        return "█" * filled + "░" * (width - filled)


# Module-level singleton
signal_formatter = SignalFormatter()
