"""
ERICKsky Signal Engine - News Filter
Blocks signals during high-impact economic news events.
Uses a simple HTTP fetch from a free economic calendar API.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

import requests

from config import settings
from data.cache_manager import cache

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

# High-impact news event keywords
HIGH_IMPACT_KEYWORDS = [
    "nonfarm", "non-farm", "nfp", "fomc", "fed rate", "interest rate",
    "ecb", "boe", "boj", "rba", "cpi", "gdp", "unemployment", "pmi",
    "payroll", "inflation", "central bank", "monetary policy",
]


class NewsFilter:
    """
    Fetches economic calendar and blocks signals near high-impact events.
    Falls back to PASS if the API is unavailable.
    """

    CACHE_KEY = "news:high_impact"
    FOREXFACTORY_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def get_high_impact_events(self) -> List[Dict]:
        """Return list of high-impact events for this week."""
        cached = cache.get_json(self.CACHE_KEY)
        if cached is not None:
            return cached

        try:
            resp = requests.get(self.FOREXFACTORY_URL, timeout=10)
            resp.raise_for_status()
            events = resp.json()

            high_impact = [
                e for e in events
                if e.get("impact", "").lower() in ("high", "red")
            ]

            cache.set_json(self.CACHE_KEY, high_impact, ttl=settings.CACHE_TTL_NEWS)
            logger.info("News filter: fetched %d high-impact events", len(high_impact))
            return high_impact

        except Exception as exc:
            logger.warning("News filter: could not fetch calendar: %s", exc)
            return []

    def passes(self, symbol: str) -> tuple[bool, str]:
        """
        Check if symbol is free of imminent high-impact news.
        Returns (passed: bool, reason: str).
        """
        currencies = PAIR_CURRENCIES.get(symbol.upper(), ["USD"])
        now = datetime.now(timezone.utc)
        blackout = timedelta(minutes=settings.NEWS_BLACKOUT_MINUTES)

        try:
            events = self.get_high_impact_events()
        except Exception:
            logger.warning("News filter falling back to PASS (API unavailable)")
            return True, "news filter: API unavailable (defaulting to pass)"

        for event in events:
            event_time_str = event.get("date") or event.get("time") or ""
            event_currency = event.get("currency", "").upper()

            if event_currency not in currencies:
                continue

            # Parse event time
            event_time = self._parse_event_time(event_time_str)
            if event_time is None:
                continue

            # Check if within blackout window
            time_diff = abs(now - event_time)
            if time_diff <= blackout:
                title = event.get("title", "Unknown event")
                minutes_away = int(time_diff.total_seconds() / 60)
                reason = (
                    f"high-impact news '{title}' ({event_currency}) "
                    f"in {minutes_away}min"
                )
                logger.info("News filter BLOCKED: %s", reason)
                return False, reason

        return True, "no imminent high-impact news"

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
