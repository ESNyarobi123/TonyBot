"""
ERICKsky Signal Engine - Structured Logging Setup
"""

import logging
import sys
from config import settings


def setup_logging() -> None:
    """Configure root logger with level, format, and handlers."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
        if settings.APP_ENV == "production"
        else "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "httpx", "telegram", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("ERICKsky").setLevel(level)
    logging.info("Logging initialised at level=%s env=%s", settings.LOG_LEVEL, settings.APP_ENV)
