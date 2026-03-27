"""
ERICKsky Signal Engine - Celery Application  (v2 — Institutional Grade)

Adds new periodic tasks:
  • update-news-weekly        — Sunday 20:00 UTC (local news DB refresh)
  • weekly-performance-analysis — Sunday 21:00 UTC (self-learning engine)

Task routing updated for new tasks.
"""

from celery import Celery
from celery.schedules import crontab

from config import settings

celery_app = Celery(
    "erickskybot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "tasks.scan_pair",
        "tasks.daily_report",
        "tasks.news_updater",
        "tasks.performance_analyzer",
        "tasks.data_maintenance",
    ],
)

celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,

    # ── Task routing ──────────────────────────────────────────────────────────
    task_routes={
        "tasks.scan_pair":                   {"queue": "signals"},
        "tasks.scan_all_pairs":              {"queue": "default"},
        "tasks.daily_report":                {"queue": "default"},
        "tasks.expire_old_signals":          {"queue": "default"},
        "tasks.update_news_database":        {"queue": "default"},
        "tasks.weekly_performance_analysis": {"queue": "default"},
        "tasks.clean_m1_m5_cache":           {"queue": "default"},
    },

    # ── Worker settings ───────────────────────────────────────────────────────
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,

    # ── Result expiry ─────────────────────────────────────────────────────────
    result_expires=3600,

    # ── Beat schedule (periodic tasks) ───────────────────────────────────────
    beat_schedule={
        # Scan all pairs every 15 minutes (Sniper Mode — EURUSD & XAUUSD)
        "scan-all-pairs-15min": {
            "task":     "tasks.scan_all_pairs",
            "schedule": crontab(minute="*/15"),
            "args":     [],
            "kwargs":   {"force_session": False},
        },

        # Daily performance report at 21:30 UTC (NY session close)
        "daily-report": {
            "task":     "tasks.daily_report",
            "schedule": crontab(hour=21, minute=30),
        },

        # Expire stale pending signals every 30 minutes
        "expire-old-signals": {
            "task":     "tasks.expire_old_signals",
            "schedule": crontab(minute="*/30"),
        },

        # ── NEW: Refresh local news DB every Sunday at 20:00 UTC ─────────────
        "update-news-weekly": {
            "task":     "tasks.update_news_database",
            "schedule": crontab(hour=20, minute=0, day_of_week="sunday"),
        },

        # ── NEW: Run self-learning performance analysis every Sunday 21:00 UTC
        "weekly-performance-analysis": {
            "task":     "tasks.weekly_performance_analysis",
            "schedule": crontab(hour=21, minute=0, day_of_week="sunday"),
        },

        # ── Sniper Mode: purge M1/M5 Redis OHLCV cache daily at 00:05 UTC ──────
        # Keeps Redis lean — M1/M5 data is only needed for the current session
        "clean-m1-m5-cache-daily": {
            "task":     "tasks.clean_m1_m5_cache",
            "schedule": crontab(hour=0, minute=5),
        },
    },
)
