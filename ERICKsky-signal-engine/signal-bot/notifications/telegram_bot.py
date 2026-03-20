"""
ERICKsky Signal Engine - Telegram Bot
Handles message delivery to channels and individual subscribers.
"""

import asyncio
import logging
from typing import List, Optional

from telegram import Bot
from telegram.error import TelegramError, Forbidden, ChatMigrated
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from config import settings
from database.models import Signal
from database.repositories import SubscriberRepository, ChannelRepository
from signals.signal_formatter import signal_formatter

logger = logging.getLogger(__name__)


class TelegramBot:
    """Async Telegram Bot wrapper for signal delivery."""

    def __init__(self) -> None:
        self._bot: Optional[Bot] = None

    @property
    def bot(self) -> Bot:
        if self._bot is None:
            if not settings.TELEGRAM_BOT_TOKEN:
                raise ValueError("TELEGRAM_BOT_TOKEN is not configured")
            proxy_url = getattr(settings, "TELEGRAM_PROXY_URL", None)
            if proxy_url:
                logger.info("Telegram using proxy: %s", proxy_url)
                request = HTTPXRequest(proxy=proxy_url)
                self._bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, request=request)
            else:
                self._bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        return self._bot

    # ── Public API ────────────────────────────────────────────────────────────

    def send_signal(self, signal: Signal) -> int:
        """
        Send a signal to all configured channels and active subscribers.
        Returns the count of successful deliveries.
        """
        return asyncio.get_event_loop().run_until_complete(
            self._send_signal_async(signal)
        )

    def send_admin_message(self, text: str) -> bool:
        """Send a plain text message to the admin chat."""
        return asyncio.get_event_loop().run_until_complete(
            self._send_text_async(settings.TELEGRAM_ADMIN_CHAT_ID, text)
        )

    def send_daily_report(
        self,
        date_str: str,
        total: int,
        wins: int,
        losses: int,
        pending: int,
        total_pips: float,
    ) -> None:
        text = signal_formatter.format_daily_report(
            date_str, total, wins, losses, pending, total_pips
        )
        asyncio.get_event_loop().run_until_complete(
            self._broadcast_async(text, premium_only=False)
        )

    # ── Async internals ───────────────────────────────────────────────────────

    async def _send_signal_async(self, signal: Signal) -> int:
        sent = 0

        # 1. Send to channels
        channels = ChannelRepository.find_active()
        for channel in channels:
            is_premium = channel.type == "PREMIUM"
            text = signal_formatter.format_signal(signal, is_premium=is_premium)
            ok = await self._send_text_async(channel.chat_id, text)
            if ok:
                sent += 1

        # 2. Send to individual premium subscribers
        if settings.TELEGRAM_PREMIUM_CHANNEL:
            premium_text = signal_formatter.format_signal(signal, is_premium=True)
            await self._send_text_async(
                settings.TELEGRAM_PREMIUM_CHANNEL, premium_text
            )

        # 3. Send basic version to free channel
        if settings.TELEGRAM_FREE_CHANNEL:
            free_text = signal_formatter.format_signal(signal, is_premium=False)
            ok = await self._send_text_async(settings.TELEGRAM_FREE_CHANNEL, free_text)
            if ok:
                sent += 1

        # 4. Notify admin with full template
        admin_text = signal_formatter.format_signal(signal, is_premium=True)
        await self._send_text_async(settings.TELEGRAM_ADMIN_CHAT_ID, admin_text)

        return sent

    async def _broadcast_async(self, text: str, premium_only: bool = False) -> int:
        sent = 0
        subscribers = (
            SubscriberRepository.find_premium_active()
            if premium_only
            else SubscriberRepository.find_active()
        )
        for sub in subscribers:
            ok = await self._send_text_async(sub.telegram_chat_id, text)
            if ok:
                sent += 1
                SubscriberRepository.increment_signals_received(sub.telegram_chat_id)
        return sent

    async def _send_text_async(self, chat_id: str, text: str) -> bool:
        if not chat_id:
            return False
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            logger.debug("Message sent to %s", chat_id)
            return True
        except Forbidden:
            logger.warning("Bot blocked by user/channel: %s", chat_id)
            # Auto-deactivate subscriber
            SubscriberRepository.deactivate(chat_id)
            return False
        except ChatMigrated as exc:
            logger.warning("Chat migrated to %s", exc.new_chat_id)
            return False
        except TelegramError as exc:
            logger.error("Telegram error sending to %s: %s", chat_id, exc)
            return False
        except Exception as exc:
            logger.exception("Unexpected error sending to %s: %s", chat_id, exc)
            return False

    async def test_connection(self) -> bool:
        """Verify bot token and connectivity."""
        try:
            me = await self.bot.get_me()
            logger.info("Telegram bot connected: @%s (%s)", me.username, me.id)
            return True
        except Exception as exc:
            logger.error("Telegram bot connection failed: %s", exc)
            return False


# Module-level singleton
telegram_bot = TelegramBot()
