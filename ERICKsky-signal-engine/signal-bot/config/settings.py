"""
ERICKsky Signal Engine - Central Configuration
All settings loaded from environment variables via python-dotenv.
"""

import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


# ─── Database ─────────────────────────────────────────────────────────────────

DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
DB_NAME: str = os.getenv("DB_NAME", "erickskybot")
DB_USER: str = os.getenv("DB_USER", "erickskybot")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

DATABASE_URL: str = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ─── Redis ────────────────────────────────────────────────────────────────────

REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

REDIS_URL: str = (
    f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    if REDIS_PASSWORD
    else f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
)

# ─── Twelve Data ──────────────────────────────────────────────────────────────

TWELVE_DATA_API_KEY: str = os.getenv("TWELVE_DATA_API_KEY", "")
TWELVE_DATA_BASE_URL: str = os.getenv(
    "TWELVE_DATA_BASE_URL", "https://api.twelvedata.com"
)

# ─── Telegram ─────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_FREE_CHANNEL: str = os.getenv("TELEGRAM_FREE_CHANNEL", "")
TELEGRAM_PREMIUM_CHANNEL: str = os.getenv("TELEGRAM_PREMIUM_CHANNEL", "")
TELEGRAM_ADMIN_CHAT_ID: str = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
TELEGRAM_PROXY_URL: str = os.getenv("TELEGRAM_PROXY_URL", "")  # e.g. socks5://user:pass@host:port

# ─── Trading Configuration ────────────────────────────────────────────────────

_pairs_raw: str = os.getenv("TRADING_PAIRS", "EURUSD,GBPUSD,USDJPY,XAUUSD")
TRADING_PAIRS: List[str] = [p.strip() for p in _pairs_raw.split(",") if p.strip()]

SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "60"))
MIN_CONSENSUS_SCORE: int = int(os.getenv("MIN_CONSENSUS_SCORE", "65"))
SIGNAL_VALID_MINUTES: int = int(os.getenv("SIGNAL_VALID_MINUTES", "240"))
MAX_SIGNALS_PER_PAIR_PER_DAY: int = int(
    os.getenv("MAX_SIGNALS_PER_PAIR_PER_DAY", "3")
)
RISK_REWARD_RATIO: float = float(os.getenv("RISK_REWARD_RATIO", "2.0"))

# Timeframes used for analysis
TIMEFRAMES: List[str] = ["1min", "5min", "15min", "1h", "4h", "1day"]
PRIMARY_TIMEFRAME: str = "1h"
TREND_TIMEFRAME: str = "4h"
ENTRY_TIMEFRAME: str = "15min"

# Number of candles to fetch per timeframe
CANDLE_LOOKBACK: int = 200

# ─── Session Windows (UTC hours) ──────────────────────────────────────────────

LONDON_START: int = int(os.getenv("LONDON_START", "7"))
LONDON_END: int = int(os.getenv("LONDON_END", "16"))
NEWYORK_START: int = int(os.getenv("NEWYORK_START", "12"))
NEWYORK_END: int = int(os.getenv("NEWYORK_END", "21"))
ASIAN_START: int = int(os.getenv("ASIAN_START", "0"))
ASIAN_END: int = int(os.getenv("ASIAN_END", "9"))

# ─── Strategy Weights (must sum to 100) ───────────────────────────────────────

STRATEGY_WEIGHT_MULTI_TIMEFRAME: int = int(
    os.getenv("STRATEGY_WEIGHT_MULTI_TIMEFRAME", "25")
)
STRATEGY_WEIGHT_SMART_MONEY: int = int(
    os.getenv("STRATEGY_WEIGHT_SMART_MONEY", "30")
)
STRATEGY_WEIGHT_PRICE_ACTION: int = int(
    os.getenv("STRATEGY_WEIGHT_PRICE_ACTION", "25")
)
STRATEGY_WEIGHT_TECHNICAL: int = int(
    os.getenv("STRATEGY_WEIGHT_TECHNICAL", "20")
)

# ─── Filter Thresholds ────────────────────────────────────────────────────────

# Minimum ATR (in pips) for volatility filter
MIN_ATR_PIPS: float = 5.0

# Maximum spread (in pips) allowed
MAX_SPREAD_PIPS: float = 3.0

# News blackout window in minutes (before/after high-impact news)
NEWS_BLACKOUT_MINUTES: int = 30

# ─── Risk Management ──────────────────────────────────────────────────────────

# Stop loss in pips per pair type
SL_PIPS_FOREX: float = 20.0
SL_PIPS_GOLD: float = 150.0

# Take profit multipliers
TP1_MULTIPLIER: float = 1.0   # 1:1
TP2_MULTIPLIER: float = 2.0   # 1:2
TP3_MULTIPLIER: float = 3.0   # 1:3

# ─── Pip Values ───────────────────────────────────────────────────────────────

PIP_VALUES: dict = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.1,
    "USDCHF": 0.0001,
    "AUDUSD": 0.0001,
    "USDCAD": 0.0001,
    "NZDUSD": 0.0001,
    "EURGBP": 0.0001,
    "EURJPY": 0.01,
    "GBPJPY": 0.01,
}

# ─── Cache TTL (seconds) ──────────────────────────────────────────────────────

CACHE_TTL_OHLCV_1MIN: int = 60
CACHE_TTL_OHLCV_5MIN: int = 300
CACHE_TTL_OHLCV_15MIN: int = 900
CACHE_TTL_OHLCV_1H: int = 3600
CACHE_TTL_OHLCV_4H: int = 14400
CACHE_TTL_OHLCV_1D: int = 86400
CACHE_TTL_SIGNAL: int = 1800
CACHE_TTL_NEWS: int = 600

CACHE_TTL_MAP: dict = {
    "1min": CACHE_TTL_OHLCV_1MIN,
    "5min": CACHE_TTL_OHLCV_5MIN,
    "15min": CACHE_TTL_OHLCV_15MIN,
    "1h": CACHE_TTL_OHLCV_1H,
    "4h": CACHE_TTL_OHLCV_4H,
    "1day": CACHE_TTL_OHLCV_1D,
}

# ─── Celery ───────────────────────────────────────────────────────────────────

CELERY_BROKER_URL: str = REDIS_URL
CELERY_RESULT_BACKEND: str = REDIS_URL
CELERY_TASK_SERIALIZER: str = "json"
CELERY_RESULT_SERIALIZER: str = "json"
CELERY_ACCEPT_CONTENT: List[str] = ["json"]
CELERY_TIMEZONE: str = "UTC"
CELERY_ENABLE_UTC: bool = True

# ─── Logging ──────────────────────────────────────────────────────────────────

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
APP_ENV: str = os.getenv("APP_ENV", "production")
TIMEZONE: str = os.getenv("TIMEZONE", "UTC")

# ─── Validation ───────────────────────────────────────────────────────────────

def validate_settings() -> None:
    """Raise ValueError if critical settings are missing."""
    required = {
        "TWELVE_DATA_API_KEY": TWELVE_DATA_API_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "DB_PASSWORD": DB_PASSWORD,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
