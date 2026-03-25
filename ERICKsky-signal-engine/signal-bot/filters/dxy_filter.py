"""
ERICKsky Signal Engine — DXY Global Filter (The Big Eye)

Fetches DXY (Dollar Index) H1 data and determines USD strength/weakness
using EMA 21. Blocks signals on USD pairs that conflict with DXY trend.

Fallback: If DXY data is unavailable, uses the *inverse* of EURUSD H1 trend
as a proxy for Dollar Strength:
  - EURUSD Bearish (Price < EMA 21) → Dollar Strong (DXY proxy = BULLISH)
  - EURUSD Bullish (Price > EMA 21) → Dollar Weak   (DXY proxy = BEARISH)

Dual-Pair Confirmation: Cross-checks EURUSD with GBPUSD for higher certainty:
  - Both EURUSD & GBPUSD Bearish → DXY BULLISH (USD Strength) — confirmed
  - Both EURUSD & GBPUSD Bullish → DXY BEARISH (USD Weakness) — confirmed
  - Disagreement → fall back to EURUSD-only proxy

Rules for USD Pairs (EURUSD, GBPUSD, AUDUSD, NZDUSD):
  - DXY Bullish (USD strong) → BLOCK all BUY signals
  - DXY Bearish (USD weak)   → BLOCK all SELL signals

Log: [DXY Correlation Filter: Signal Blocked due to USD Strength/Weakness]
"""

import logging
from typing import Optional, Tuple

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)


class DXYFilter:
    """
    Dollar Index correlation filter.
    Prevents trades that fight the dominant USD trend.
    Falls back to EURUSD inverse proxy if DXY data is unavailable.
    """

    def __init__(self) -> None:
        self._dxy_trend: Optional[str] = None  # "BULLISH" | "BEARISH" | None
        self._dxy_price: Optional[float] = None
        self._dxy_ema: Optional[float] = None
        self._source: str = "none"  # "DXY" | "EURUSD_PROXY" | "none"

    # ── Public API ─────────────────────────────────────────────────────────────

    def update_dxy_data(self, dxy_h1_df: Optional[pd.DataFrame]) -> None:
        """
        Refresh the cached DXY trend from H1 candle data.
        Call this once per scan cycle before checking individual pairs.
        If DXY data is None/empty, the trend stays as-is (may be set by proxy).
        """
        if dxy_h1_df is None or dxy_h1_df.empty:
            logger.warning(
                "[DXY Filter] No DXY H1 data available — "
                "will use EURUSD proxy if provided"
            )
            return

        self._apply_ema_trend(dxy_h1_df, source="DXY")

    def update_from_eurusd_proxy(self, eurusd_h1_df: Optional[pd.DataFrame]) -> None:
        """
        Fallback: derive Dollar Strength from the INVERSE of EURUSD H1 trend.
          EURUSD Bearish → USD Strong → DXY proxy = BULLISH
          EURUSD Bullish → USD Weak   → DXY proxy = BEARISH

        Only used when DXY data is unavailable.
        """
        if self._source == "DXY":
            return

        if eurusd_h1_df is None or eurusd_h1_df.empty:
            logger.warning("[DXY Filter] EURUSD proxy data also unavailable — filter disabled")
            self._dxy_trend = None
            self._dxy_price = None
            self._dxy_ema = None
            self._source = "none"
            return

        logger.info("[DXY Proxy] Using EURUSD inverse correlation")
        self._apply_ema_trend(eurusd_h1_df, source="EURUSD_PROXY")

        # Invert: EURUSD Bullish = USD Weak = DXY BEARISH, and vice versa
        if self._dxy_trend == "BULLISH":
            self._dxy_trend = "BEARISH"
        elif self._dxy_trend == "BEARISH":
            self._dxy_trend = "BULLISH"

        logger.info(
            "[DXY Proxy] EURUSD proxy inverted → USD trend=%s (source=EURUSD_PROXY)",
            self._dxy_trend,
        )

    def update_from_dual_proxy(
        self,
        eurusd_h1_df: Optional[pd.DataFrame],
        gbpusd_h1_df: Optional[pd.DataFrame],
    ) -> None:
        """
        Dual-Pair Proxy: Cross-check EURUSD and GBPUSD H1 trends for
        higher-certainty USD strength/weakness detection.

          Both Bearish → USD Strong  → DXY proxy = BULLISH (confirmed)
          Both Bullish → USD Weak    → DXY proxy = BEARISH (confirmed)
          Disagreement → fall back to EURUSD-only proxy

        Only used when DXY data is unavailable.
        """
        if self._source == "DXY":
            return

        # If GBPUSD data is missing, fall back to single-pair proxy
        if gbpusd_h1_df is None or gbpusd_h1_df.empty:
            logger.info("[DXY Proxy] GBPUSD data unavailable — falling back to EURUSD-only proxy")
            self.update_from_eurusd_proxy(eurusd_h1_df)
            return

        if eurusd_h1_df is None or eurusd_h1_df.empty:
            logger.warning("[DXY Proxy] EURUSD data unavailable — trying GBPUSD-only proxy")
            # Use GBPUSD as single proxy (same inverse logic as EURUSD)
            self._apply_ema_trend(gbpusd_h1_df, source="GBPUSD_PROXY")
            if self._dxy_trend == "BULLISH":
                self._dxy_trend = "BEARISH"
            elif self._dxy_trend == "BEARISH":
                self._dxy_trend = "BULLISH"
            logger.info(
                "[DXY Proxy] GBPUSD proxy inverted → USD trend=%s",
                self._dxy_trend,
            )
            return

        # Both pairs available — derive trends separately
        eurusd_trend = self._get_ema_trend(eurusd_h1_df)
        gbpusd_trend = self._get_ema_trend(gbpusd_h1_df)

        logger.info(
            "[DXY Proxy] Using EURUSD/GBPUSD inverse correlation — "
            "EURUSD=%s, GBPUSD=%s",
            eurusd_trend, gbpusd_trend,
        )

        if eurusd_trend == gbpusd_trend:
            # Both agree — high confidence
            # Both Bearish = USD Strong = DXY BULLISH
            # Both Bullish = USD Weak = DXY BEARISH
            if eurusd_trend == "BEARISH":
                self._dxy_trend = "BULLISH"
            else:
                self._dxy_trend = "BEARISH"
            self._source = "DUAL_PROXY"
            logger.info(
                "[DXY Proxy] Dual confirmation ✅ → USD trend=%s "
                "(EURUSD=%s, GBPUSD=%s agree)",
                self._dxy_trend, eurusd_trend, gbpusd_trend,
            )
        else:
            # Disagreement — fall back to EURUSD-only (higher liquidity)
            logger.info(
                "[DXY Proxy] EURUSD/GBPUSD disagree (%s vs %s) — "
                "using EURUSD-only proxy",
                eurusd_trend, gbpusd_trend,
            )
            self.update_from_eurusd_proxy(eurusd_h1_df)

    # ── Internal EMA calculation ──────────────────────────────────────────────

    def _get_ema_trend(self, df: pd.DataFrame) -> str:
        """Return 'BULLISH' or 'BEARISH' based on EMA 21 for a given pair DataFrame."""
        close = df["close"].astype(float)
        ema_period = getattr(settings, "DXY_EMA_PERIOD", 21)
        ema = close.ewm(span=ema_period, adjust=False).mean()
        return "BULLISH" if float(close.iloc[-1]) > float(ema.iloc[-1]) else "BEARISH"

    def _apply_ema_trend(self, df: pd.DataFrame, source: str) -> None:
        """Compute EMA 21 trend from a close-price DataFrame."""
        close = df["close"].astype(float)
        ema_period = getattr(settings, "DXY_EMA_PERIOD", 21)

        ema = close.ewm(span=ema_period, adjust=False).mean()
        current_price = float(close.iloc[-1])
        current_ema = float(ema.iloc[-1])

        self._dxy_price = current_price
        self._dxy_ema = current_ema
        self._source = source

        if current_price > current_ema:
            self._dxy_trend = "BULLISH"
        else:
            self._dxy_trend = "BEARISH"

        logger.info(
            "[DXY Filter] %s H1: price=%.5f EMA%d=%.5f → trend=%s",
            source, current_price, ema_period, current_ema, self._dxy_trend,
        )

    def passes(
        self,
        symbol: str,
        direction: str,
    ) -> Tuple[bool, str]:
        """
        Check whether a signal on `symbol` in `direction` is allowed
        given the current DXY trend.

        Returns:
            (passed: bool, reason: str)
        """
        usd_pairs = getattr(settings, "DXY_USD_PAIRS", [])

        # Not a USD pair → always pass
        if symbol.upper() not in usd_pairs:
            return True, "non-USD pair — DXY filter not applicable"

        # No DXY data → pass with warning
        if self._dxy_trend is None:
            logger.debug("[DXY Filter] No DXY trend data — allowing %s %s", symbol, direction)
            return True, "DXY data unavailable — filter bypassed"

        # DXY Bullish (USD strong) → block BUY on inverse USD pairs
        if self._dxy_trend == "BULLISH" and direction == "BUY":
            reason = (
                f"[DXY Correlation Filter: Signal Blocked due to USD Strength] "
                f"DXY={self._dxy_price:.3f} > EMA21={self._dxy_ema:.3f} → "
                f"BUY {symbol} blocked (USD is strong)"
            )
            logger.warning(reason)
            return False, reason

        # DXY Bearish (USD weak) → block SELL on inverse USD pairs
        if self._dxy_trend == "BEARISH" and direction == "SELL":
            reason = (
                f"[DXY Correlation Filter: Signal Blocked due to USD Weakness] "
                f"DXY={self._dxy_price:.3f} < EMA21={self._dxy_ema:.3f} → "
                f"SELL {symbol} blocked (USD is weak)"
            )
            logger.warning(reason)
            return False, reason

        # Signal aligns with DXY trend
        trend_label = "Weakness" if self._dxy_trend == "BEARISH" else "Strength"
        return True, f"DXY {self._dxy_trend} — {direction} {symbol} allowed (USD {trend_label})"

    @property
    def trend(self) -> Optional[str]:
        """Current DXY trend: BULLISH | BEARISH | None."""
        return self._dxy_trend

    @property
    def dxy_status_label(self) -> str:
        """Human-readable status for Telegram template."""
        if self._dxy_trend is None:
            return "⚠️ Unavailable"
        if self._dxy_trend == "BULLISH":
            return "🟢 USD Strong (DXY Bullish)"
        return "🔴 USD Weak (DXY Bearish)"


# Module-level singleton
dxy_filter = DXYFilter()
