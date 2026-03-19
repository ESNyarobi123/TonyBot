"""
ERICKsky Signal Engine - Celery Application
Configures the Celery app with Redis broker and beat schedule.
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
    ],
)

celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,

    # Task routing
    task_routes={
        "tasks.scan_pair": {"queue": "signals"},
        "tasks.scan_all_pairs": {"queue": "default"},
        "tasks.daily_report": {"queue": "default"},
        "tasks.expire_old_signals": {"queue": "default"},
    },

    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=100,

    # Result expiry
    result_expires=3600,

    # Beat schedule (periodic tasks)
    beat_schedule={
        # Scan all pairs every hour during active sessions
        "scan-all-pairs-hourly": {
            "task": "tasks.scan_all_pairs",
            "schedule": crontab(minute=0),   # top of every hour
            "args": [],
            "kwargs": {"force_session": False},
        },
        # Daily report at 21:30 UTC (NY session close)
        "daily-report": {
            "task": "tasks.daily_report",
            "schedule": crontab(hour=21, minute=30),
        },
        # Expire stale pending signals every 30 minutes
        "expire-old-signals": {
            "task": "tasks.expire_old_signals",
            "schedule": crontab(minute="*/30"),
        },
    },
)
