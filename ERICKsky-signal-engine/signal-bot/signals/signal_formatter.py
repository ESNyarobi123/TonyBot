"""
ERICKsky Signal Engine - Signal Formatter

Produces professional Telegram Markdown messages for every signal type.
Uses ParseMode.MARKDOWN for better formatting.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from database.models import Signal
from config import settings
from config.settings import PIP_VALUES

logger = logging.getLogger(__name__)

# ── Display mappings ──────────────────────────────────────────────────────────
_DIR_EMOJI: Dict[str, str] = {"BUY": "🟢", "SELL": "🔴"}
_CONF_STARS: Dict[str, str] = {
    "VERY_HIGH": "⭐⭐⭐⭐",
    "HIGH":      "⭐⭐⭐",
    "MEDIUM":    "⭐⭐",
    "LOW":       "⭐",
}
_STRATEGY_EMOJI: Dict[str, str] = {
    "MultiTimeframe":      "📊",
    "SmartMoney":          "🧠",
    "PriceAction":         "🎯",
    "TechnicalIndicators": "⚙️",
}
_STRATEGY_SHORT: Dict[str, str] = {
    "MultiTimeframe":      "MTF",
    "SmartMoney":          "SMC",
    "PriceAction":         "PA",
    "TechnicalIndicators": "TECH",
}


class SignalFormatter:
    """
    Formats Signal database objects into professional Telegram Markdown messages.

    Public methods:
      format_signal(signal, is_premium) → str
      format_daily_report(...)          → str
      format_alert(text)                → str
    """

    def format_signal(self, signal: Signal, is_premium: bool = True) -> str:
        """
        Format a full signal message with professional template.

        Args:
            signal:     Signal ORM object
            is_premium: Include strategy score breakdown (default True)

        Returns:
            Markdown-formatted string ready for Telegram sendMessage.
        """
        try:
            return self._build_signal(signal, is_premium)
        except Exception as exc:
            logger.exception("SignalFormatter error: %s", exc)
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
        """Format a concise daily performance report."""
        win_rate   = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0.0
        pips_emoji = "📈" if total_pips >= 0 else "📉"
        sign       = "+" if total_pips >= 0 else ""

        return (
            f"🔥 *ERICKsky Daily Report* 🔥\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *{date_str}*\n\n"
            f"📡 *Signals Sent:* `{total}`\n"
            f"✅ *Wins:* `{wins}`\n"
            f"❌ *Losses:* `{losses}`\n"
            f"⏳ *Pending:* `{pending}`\n"
            f"🎯 *Win Rate:* `{win_rate}%`\n"
            f"{pips_emoji} *Total Pips:* `{sign}{total_pips:.1f}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 *ERICKsky Signal Engine*\n"
            f"� t.me/ERICKskySignals"
        )

    def format_alert(self, text: str) -> str:
        """Format a simple admin alert message."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"⚠️ *ERICKsky Alert*\n{text}\n🕐 {now}"

    # ── Internal builder ──────────────────────────────────────────────────────

    def _build_signal(self, signal: Signal, is_premium: bool) -> str:
        direction = signal.direction or "BUY"
        pair      = (signal.pair or "?").upper()
        pip_size  = PIP_VALUES.get(pair, 0.0001)

        emoji   = _DIR_EMOJI.get(direction, "⚪")
        stars   = _CONF_STARS.get(signal.confidence or "LOW", "⭐")
        
        # Calculate valid until time (using entry_window_minutes if available)
        window_minutes = getattr(signal, 'entry_window_minutes', 90)
        valid_until = signal.sent_at + timedelta(minutes=window_minutes)
        valid_str = valid_until.strftime("%H:%M UTC")
        
        # Price formatting: all pairs use 5 decimals now
        fmt = "{:.5f}"

        entry = float(signal.entry_price)
        sl    = float(signal.stop_loss)
        tp1   = float(signal.take_profit_1)
        tp2   = float(signal.take_profit_2) if signal.take_profit_2 else None
        tp3   = float(signal.take_profit_3) if signal.take_profit_3 else None

        # Smart entry values (new fields) - with fallback calculation
        limit_entry = getattr(signal, 'limit_entry', None)
        entry_zone_low = getattr(signal, 'entry_zone_low', None)
        entry_zone_high = getattr(signal, 'entry_zone_high', None)
        market_entry = getattr(signal, 'market_entry', entry)
        atr_value = getattr(signal, 'atr_value', None)

        # Fallback: calculate smart entry if fields are missing OR limit equals entry
        if (limit_entry is None or limit_entry == entry) and atr_value:
            if direction == "BUY":
                limit_entry = round(entry - (atr_value * 0.40), 5)
                entry_zone_low = round(entry - (atr_value * 0.5), 5)
                entry_zone_high = round(entry + (atr_value * 0.1), 5)
            else:  # SELL
                limit_entry = round(entry + (atr_value * 0.40), 5)
                entry_zone_low = round(entry - (atr_value * 0.1), 5)
                entry_zone_high = round(entry + (atr_value * 0.5), 5)
        
        # Ultimate fallback: use hardcoded ATR if atr_value is missing
        if limit_entry is None or limit_entry == entry:
            atr = 0.0015  # Default ATR ~15 pips
            if direction == "BUY":
                limit_entry = round(entry - (atr * 0.40), 5)
            else:  # SELL
                limit_entry = round(entry + (atr * 0.40), 5)

        # Pip calculations
        sl_pips  = abs(entry - sl) / pip_size
        tp1_pips = abs(tp1 - entry) / pip_size
        tp2_pips = abs(tp2 - entry) / pip_size if tp2 else None
        tp3_pips = abs(tp3 - entry) / pip_size if tp3 else None

        sl_sign  = "-" if direction == "BUY" else "+"
        tp_sign  = "+" if direction == "BUY" else "-"

        # Use agreement_count directly from consensus result
        agreement = signal.agreement_count or 0
        total_strategies = len(signal.strategy_scores) if signal.strategy_scores else 4

        # Build the professional template
        lines = [
            f"🔥 *PREMIUM SIGNAL* 🔥",
            f"",
            f"┌─────────────────────────┐",
            f"│  {emoji} *{pair} — {direction}*",
            f"│  Score: {signal.consensus_score} | {signal.confidence} {stars}",
            f"└─────────────────────────┘",
            f"",
            f"💰 *TRADE SETUP:*",
        ]
        
        # Entry zone or single entry
        if entry_zone_low and entry_zone_high:
            lines.append(f"├ Entry Zone: `{fmt.format(entry_zone_low)}` – `{fmt.format(entry_zone_high)}`")
        else:
            lines.append(f"├ Entry:     `{fmt.format(entry)}`")
            
        lines += [
            f"├ Stop Loss:  `{fmt.format(sl)}` ({sl_sign}{sl_pips:.0f} pips)",
            f"├ TP1:        `{fmt.format(tp1)}` ({tp_sign}{tp1_pips:.0f} pips)",
        ]

        if tp2:
            lines.append(f"├ TP2:        `{fmt.format(tp2)}` ({tp_sign}{tp2_pips:.0f} pips)")

        if tp3:
            lines.append(f"└ TP3:        `{fmt.format(tp3)}` ({tp_sign}{tp3_pips:.0f} pips)")
        else:
            lines[-1] = lines[-1].replace("├", "└")

        # SMART ENTRY GUIDE section - always show with calculated or fallback values
        lines += [
            f"",
            f"📌 *SMART ENTRY GUIDE:*",
            f"┌─────────────────────────────────┐",
        ]
        
        # Determine action and rules based on direction
        if direction == "BUY":
            action = "BUY LIMIT"
            candle_rule = "closes bullish ↑"
            avoid_msg = "chasing price up!"
        else:
            action = "SELL LIMIT"
            candle_rule = "closes bearish ↓"
            avoid_msg = "chasing price down!"

        # Format prices for display
        if limit_entry:
            limit_str = fmt.format(limit_entry)
            zone_str = f"{fmt.format(entry_zone_low)} – {fmt.format(entry_zone_high)}" if entry_zone_low and entry_zone_high else "See entry zone above"
        else:
            # Ultimate fallback - use entry price
            limit_str = fmt.format(entry)
            zone_str = "Use entry price above"
        
        # Build box content
        lines += [
            f"│ ⭐ BEST:  {action} {limit_str}",
            f"│    (Wait for pullback here!)    │",
            f"│                                 │",
            f"│ ✅ OK:    Wait H1 candle close  │",
            f"│    Enter if candle {candle_rule} │",
            f"│                                 │",
            f"│ ❌ AVOID: Market order now!     │",
            f"│    Never {avoid_msg}   │",
            f"└─────────────────────────────────┘",
        ]
        
        # Entry rules section
        lines += [
            f"",
            f"⚠️ *ENTRY RULES:*",
            f"- Wait for pullback to zone first",
            f"- Enter ONLY if candle closes {direction.lower()}",
            f"- Place limit order – don't chase!",
            f"- Valid for next {window_minutes} minutes only",
            f"",
            f"📊 *Why limit entry?*",
            f"Banks sweep stops BEFORE moving!",
            f"Wait for the dip = safer SL + better RR",
            f"",
            f"🧠 *Strategies zinakubaliana:* {agreement}/{total_strategies}",
        ]

        # Strategy breakdown with checkmarks
        strategy_scores = signal.strategy_scores or {}
        if strategy_scores:
            strategy_lines = []
            
            # Define a helper function to get icon
            def _get_icon(strat_dir, sig_dir, score):
                if score == 0 or strat_dir == "NEUTRAL":
                    return "⬜"
                elif strat_dir == sig_dir:
                    return "✅"
                else:
                    return "⚠️"
            
            for name, score in strategy_scores.items():
                short_name = _STRATEGY_SHORT.get(name, name[:4])
                emoji = _STRATEGY_EMOJI.get(name, "📊")
                
                # Get individual direction from signal fields
                if name == "MultiTimeframe":
                    strategy_dir = getattr(signal, 'mtf_direction', "NEUTRAL")
                elif name == "SmartMoney":
                    strategy_dir = getattr(signal, 'smc_direction', "NEUTRAL")
                elif name == "PriceAction":
                    strategy_dir = getattr(signal, 'pa_direction', "NEUTRAL")
                elif name == "TechnicalIndicators":
                    strategy_dir = getattr(signal, 'tech_direction', "NEUTRAL")
                else:
                    strategy_dir = signal.strategy_directions.get(name) if signal.strategy_directions else None
                
                # Checkmark based on whether strategy direction matches signal direction
                check = _get_icon(strategy_dir, signal.direction, score)
                    
                bar = self._score_bar(int(score))
                strategy_lines.append(f"{emoji} *{short_name}:* {check} | {bar} {score}")
            
            # Format in 2 columns
            for i in range(0, len(strategy_lines), 2):
                if i + 1 < len(strategy_lines):
                    lines.append(f"{strategy_lines[i]}    {strategy_lines[i+1]}")
                else:
                    lines.append(strategy_lines[i])

        lines += [
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"⏰ *Valid Until:* {valid_str}",
            f"💰 *Risk:* 1% max per trade",
            f"━━━━━━━━━━━━━━━━━━━━━",
            f"🏆 *ERICKsky Signal Engine*",
            f"📱 t.me/ERICKskySignals",
            f"",
            f"#FOREX #{pair} #{direction}",
        ]

        return "\n".join(lines)

    @staticmethod
    def _score_bar(score: int, width: int = 5) -> str:
        """Return a Unicode block bar representing score/100."""
        filled = max(0, min(width, round(score / 100 * width)))
        return "█" * filled + "░" * (width - filled)


signal_formatter = SignalFormatter()
