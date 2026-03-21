"""
ERICKsky Signal Engine - Session Strength Analyzer (Upgrade 6)

Scores signals higher during strong trading sessions (London/NY/Overlap)
and lower during weak sessions (Asian, Dead hours).

Provides:
  - Effective minimum score adjustment for consensus engine
  - Per-pair session optimality check
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class SessionStrengthAnalyzer:
    """Analyze market session strength and provide score multipliers."""

    # UTC hours for each session window
    SESSIONS: Dict[str, Dict] = {
        "ASIAN":   {"start": 0,  "end": 8,  "strength": 0.6},
        "LONDON":  {"start": 7,  "end": 16, "strength": 1.0},
        "NY":      {"start": 12, "end": 21, "strength": 1.0},
        "OVERLAP": {"start": 12, "end": 16, "strength": 1.3},  # Best!
        "DEAD":    {"start": 21, "end": 24, "strength": 0.3},
    }

    # Best performing sessions per trading pair
    PAIR_SESSION: Dict[str, List[str]] = {
        "EURUSD": ["LONDON", "OVERLAP"],
        "GBPUSD": ["LONDON", "OVERLAP"],
        "XAUUSD": ["LONDON", "OVERLAP", "NY"],
        "AUDUSD": ["ASIAN", "LONDON"],
        "USDJPY": ["ASIAN", "NY"],
        "USDCHF": ["LONDON", "OVERLAP"],
        "USDCAD": ["LONDON", "OVERLAP", "NY"],
        "NZDUSD": ["ASIAN", "LONDON"],
    }

    def analyze(self, symbol: str, utc_hour: int) -> Dict:
        """
        Determine session quality and score multiplier for *symbol* at *utc_hour*.

        Returns:
            dict with:
              sessions     – list of active session names
              multiplier   – float score multiplier
              pair_optimal – bool (this pair is suited to the current session)
              allow        – bool (multiplier >= 0.7)
              boost        – bool (multiplier > 1.0)
        """
        current_sessions: List[str] = []
        max_strength = 0.3

        for name, data in self.SESSIONS.items():
            s, e = data["start"], data["end"]
            # Handle sessions that wrap midnight
            in_session = (s <= utc_hour < e) if s < e else (utc_hour >= s or utc_hour < e)
            if in_session:
                current_sessions.append(name)
                max_strength = max(max_strength, data["strength"])

        # Check if this pair is optimally suited to the active session(s)
        best_sessions = self.PAIR_SESSION.get(symbol.upper(), [])
        pair_optimal  = any(s in current_sessions for s in best_sessions)

        # Base multiplier
        if "OVERLAP" in current_sessions:
            multiplier = 1.3
        elif "LONDON" in current_sessions or "NY" in current_sessions:
            multiplier = 1.0
        elif "ASIAN" in current_sessions:
            multiplier = 0.7
        else:
            multiplier = 0.4  # Dead zone

        # Bonus for optimal pair/session combo
        if pair_optimal:
            multiplier = min(multiplier + 0.2, 1.5)

        logger.info(
            "Session %s: sessions=%s multiplier=%.1f optimal=%s",
            symbol, current_sessions, multiplier, pair_optimal,
        )

        return {
            "sessions":    current_sessions,
            "multiplier":  multiplier,
            "pair_optimal": pair_optimal,
            "allow":       multiplier >= 0.7,
            "boost":       multiplier > 1.0,
        }


# Module-level singleton
session_strength_analyzer = SessionStrengthAnalyzer()
