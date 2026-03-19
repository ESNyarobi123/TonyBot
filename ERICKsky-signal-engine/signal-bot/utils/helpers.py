"""
ERICKsky Signal Engine - Utility Helpers
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from config.settings import PIP_VALUES


def pips_between(symbol: str, price_a: float, price_b: float) -> float:
    """Return the absolute pip distance between two prices."""
    pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)
    return abs(price_a - price_b) / pip_size


def price_to_pips(symbol: str, price_diff: float) -> float:
    """Convert a price difference to pips (signed)."""
    pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)
    return price_diff / pip_size


def pips_to_price(symbol: str, pips: float) -> float:
    """Convert pips to a price difference."""
    pip_size = PIP_VALUES.get(symbol.upper(), 0.0001)
    return pips * pip_size


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def dict_hash(d: Dict[str, Any]) -> str:
    """Deterministic short hash of a dict (for cache keys)."""
    serialised = json.dumps(d, sort_keys=True, default=str)
    return hashlib.md5(serialised.encode()).hexdigest()[:12]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


def format_price(symbol: str, price: float) -> str:
    """Format a price with the correct decimal places for a symbol."""
    if symbol.upper() in ("USDJPY", "EURJPY", "GBPJPY"):
        return f"{price:.3f}"
    if symbol.upper() == "XAUUSD":
        return f"{price:.2f}"
    return f"{price:.5f}"
