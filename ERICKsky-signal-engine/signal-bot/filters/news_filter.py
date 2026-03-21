"""
ERICKsky Signal Engine - News Filter (Upgrade 7 update)

Updated to read from the LOCAL news_events PostgreSQL table first.
Falls back to live ForexFactory API fetch only when the local table is empty.

This eliminates 429 "too many requests" errors during active scanning.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

import requests

from config import settings
from data.cache_manager import cache
from database.db_manager import db

logger = logging.getLogger(__name__)

# Currency codes mapped to trading pairs
PAIR_CURRENCIES: Dict[str, List[str]] = {
    "EURUSD": ["EUR", "USD"],
    "GBPUSD": ["GBP", "USD"],
    "USDJPY": ["USD", "JPY"],
    "XAUUSD": ["USD", "XAU"],
    "USDCHF": ["USD", "CHF"],
    "AUDUSD": ["AUD", "USD"],
    "USDCAD": ["USD", "CAD"],
    "NZDUSD": ["NZD", "USD"],
}

# High-impact news event keywords (live-fetch fallback)
HIGH_IMPACT_KEYWORDS = [
    "nonfarm", "non-farm", "nfp", "fomc", "fed rate", "interest rate",
    "ecb", "boe", "boj", "rba", "cpi", "gdp", "unemployment", "pmi",
    "payroll", "inflation", "central bank", "monetary policy",
]


class NewsFilter:
    """
    Blocks signals during high-impact economic news windows.

    Priority:
      1. Query local news_events table (populated by weekly NewsUpdater task)
      2. Fall back to live ForexFactory API if local table is empty
      3. Default to PASS if both sources fail
    """

    CACHE_KEY          = "news:high_impact"
    FOREXFACTORY_URL   = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    BLACKOUT_MINUTES   = getattr(settings, "NEWS_BLACKOUT_MINUTES", 30)

    # ── Public API ────────────────────────────────────────────────────────────

    def passes(self, symbol: str) -> Tuple[bool, str]:
        """
        Check if symbol is free of imminent high-impact news.

        Returns (passed: bool, reason: str).
        """
        currencies = PAIR_CURRENCIES.get(symbol.upper(), ["USD"])
        now        = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=self.BLACKOUT_MINUTES)

        # ── 1. Try local database first ───────────────────────────────────────
        try:
            db_result = self._check_local_db(currencies, now, window_end)
            if db_result is not None:
                return db_result
        except Exception as exc:
            logger.warning("NewsFilter: local DB check failed – %s", exc)

        # ── 2. Fall back to live API ──────────────────────────────────────────
        try:
            events = self._get_live_events()
            blackout = timedelta(minutes=self.BLACKOUT_MINUTES)

            for event in events:
                event_currency = event.get("currency", "").upper()
                if event_currency not in currencies:
                    continue

                event_time = self._parse_event_time(event.get("date") or event.get("time") or "")
                if event_time is None:
                    continue

                time_diff = abs(now - event_time)
                if time_diff <= blackout:
                    title       = event.get("title", "Unknown event")
                    minutes_away = int(time_diff.total_seconds() / 60)
                    reason = (
                        f"high-impact news '{title}' ({event_currency}) "
                        f"in {minutes_away}min [live source]"
                    )
                    logger.info("NewsFilter BLOCKED: %s", reason)
                    return False, reason

            return True, "no imminent high-impact news (live source)"

        except Exception as exc:
            logger.warning("NewsFilter: live API unavailable (%s) – defaulting to PASS", exc)
            return True, "news filter: both sources unavailable (defaulting to pass)"

    def has_upcoming_news(self, symbol: str, minutes: int = 30) -> Tuple[bool, str]:
        """Alias compatible with new scan_pair integration style."""
        self.BLACKOUT_MINUTES = minutes
        return self.passes(symbol)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_local_db(
        self,
        currencies: List[str],
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[Tuple[bool, str]]:
        """
        Query the local news_events table.
        Returns None if the table has no relevant rows (fall through to API).
        """
        # First check table is populated at all
        count_row = db.execute_one(
            "SELECT COUNT(*) AS cnt FROM news_events WHERE event_time > NOW()"
        )
        if not count_row or int(count_row["cnt"]) == 0:
            logger.debug("NewsFilter: local news_events table empty – falling back to live API")
            return None  # signal to caller to use live API

        # Query events in the blackout window for the relevant currencies
        rows = db.execute(
            """
            SELECT title, currency, event_time
            FROM news_events
            WHERE currency = ANY(%s)
              AND event_time BETWEEN %s AND %s
              AND impact = 'High'
            ORDER BY event_time
            LIMIT 1
            """,
            (currencies, window_start, window_end),
        )

        if rows:
            event = rows[0]
            reason = (
                f"High-impact news: {event['title']} "
                f"({event['currency']}) at {event['event_time']} [local DB]"
            )
            logger.info("NewsFilter BLOCKED: %s", reason)
            return False, reason

        return True, "no upcoming high-impact news (local DB)"

    def _get_live_events(self) -> List[Dict]:
        """Fetch and cache live ForexFactory events."""
        cached = cache.get_json(self.CACHE_KEY)
        if cached is not None:
            return cached

        resp = requests.get(self.FOREXFACTORY_URL, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        high_impact = [
            e for e in events
            if e.get("impact", "").lower() in ("high", "red")
        ]

        cache.set_json(self.CACHE_KEY, high_impact, ttl=getattr(settings, "CACHE_TTL_NEWS", 3600))
        logger.info("NewsFilter: live fetch – %d high-impact events cached", len(high_impact))
        return high_impact

    @staticmethod
    def _parse_event_time(time_str: str) -> Optional[datetime]:
        """Parse various date/time formats from economic calendar APIs."""
        if not time_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%m-%d-%Y %I:%M%p",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None


# Module-level singleton
news_filter = NewsFilter()
