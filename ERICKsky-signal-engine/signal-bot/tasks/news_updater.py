"""
ERICKsky Signal Engine - News Updater Task (Upgrade 7)

Fetches economic calendar from ForexFactory's JSON feed once per week
and stores high-impact events in a local PostgreSQL table.

This eliminates 429 "rate limited" errors during live scanning because
the news_filter will read from the LOCAL database, not from the API.

Schedule: every Sunday at 20:00 UTC  (via celery beat)
"""

import logging
import time
from datetime import datetime, timezone

import requests

from celery_app import celery_app
from database.db_manager import db

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────────────

SOURCES = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

HIGH_IMPACT_EVENTS = [
    "non-farm employment",
    "nonfarm",
    "interest rate decision",
    "rate decision",
    "cpi",
    "consumer price",
    "gdp",
    "pmi",
    "unemployment",
    "retail sales",
    "fomc",
    "fed chair",
    "ecb president",
    "boe governor",
    "rba governor",
    "trade balance",
    "employment change",
]

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 ERICKsky-Signal-Engine/2.0"}


# ── Celery task ───────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.update_news_database",
    queue="default",
    max_retries=3,
    default_retry_delay=300,
)
def update_news_database() -> int:
    """
    Fetch ForexFactory calendar for this week + next week,
    filter to high-impact events, and upsert into the local DB.

    Returns the number of events stored.
    """
    logger.info("NewsUpdater: starting weekly news DB refresh")
    all_events = []

    for url in SOURCES:
        try:
            response = requests.get(url, timeout=30, headers=REQUEST_HEADERS)
            response.raise_for_status()
            events = response.json()
            all_events.extend(events)
            logger.info("NewsUpdater: fetched %d events from %s", len(events), url)
            time.sleep(5)  # be polite to the server

        except requests.RequestException as exc:
            logger.error("NewsUpdater: failed to fetch %s – %s", url, exc)
        except Exception as exc:
            logger.error("NewsUpdater: unexpected error for %s – %s", url, exc)

    if not all_events:
        logger.warning("NewsUpdater: no events fetched – aborting DB update")
        return 0

    # ── Filter to high-impact + known keywords ────────────────────────────────
    high_impact = [
        event for event in all_events
        if event.get("impact", "").lower() in ("high", "red")
        and any(
            kw in event.get("title", "").lower()
            for kw in HIGH_IMPACT_EVENTS
        )
    ]

    logger.info(
        "NewsUpdater: %d high-impact events found from %d total",
        len(high_impact), len(all_events),
    )

    if not high_impact:
        logger.warning("NewsUpdater: no matching high-impact events – keeping existing data")
        return 0

    # ── Clear stale data and re-insert ───────────────────────────────────────
    try:
        db.execute_write("DELETE FROM news_events WHERE event_time > NOW()")
    except Exception as exc:
        logger.warning("NewsUpdater: could not purge old events – %s", exc)

    inserted = 0
    for event in high_impact:
        try:
            db.execute_write(
                """
                INSERT INTO news_events
                    (title, currency, impact, event_time, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (title, event_time) DO NOTHING
                """,
                (
                    event.get("title", "")[:200],
                    event.get("currency", "")[:10],
                    event.get("impact", "High"),
                    event.get("date"),
                ),
            )
            inserted += 1
        except Exception as exc:
            logger.warning("NewsUpdater: failed to insert event '%s': %s", event.get("title"), exc)

    logger.info("NewsUpdater: inserted/upserted %d events into news_events table", inserted)
    return inserted
