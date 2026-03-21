"""
ERICKsky Signal Engine - Performance Analyzer Task (Upgrade 8)

Weekly self-learning engine:
  - Analyses win/loss records from the last 28 days
  - Calculates correlation between each strategy score and win outcome
  - Derives suggested new strategy weights
  - Identifies best performing UTC hours and currency pairs
  - Saves report to bot_state and sends summary to admin via Telegram

Schedule: every Sunday at 21:00 UTC  (via celery beat)
"""

import json
import logging
from datetime import datetime, timezone

import pandas as pd

from celery_app import celery_app
from database.db_manager import db

logger = logging.getLogger(__name__)

_STRATEGY_COLS  = ["s1_score", "s2_score", "s3_score", "s4_score"]
_STRATEGY_NAMES = ["MTF", "SMC", "PA", "TECH"]

# Weight bounds: never let any single strategy dominate too heavily
_W_MIN = 0.15
_W_MAX = 0.40


# ── Celery task ───────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.weekly_performance_analysis",
    queue="default",
)
def weekly_performance_analysis() -> dict:
    """
    Analyse recent signal outcomes and derive improved strategy weights.
    Sends a Telegram summary to admin and saves the report to bot_state.

    Returns the performance report dict.
    """
    logger.info("PerformanceAnalyzer: starting weekly analysis")

    # ── Fetch signals from the last 28 days ──────────────────────────────────
    rows = db.execute(
        """
        SELECT
            pair,
            direction,
            consensus_score,
            strategy_scores,
            status,
            pips_result,
            created_at,
            EXTRACT(HOUR FROM created_at AT TIME ZONE 'UTC') AS hour_utc
        FROM signals
        WHERE created_at > NOW() - INTERVAL '28 days'
          AND status IN ('WIN', 'LOSS')
        ORDER BY created_at
        """
    )

    if len(rows) < 10:
        msg = f"PerformanceAnalyzer: not enough data ({len(rows)} signals) – skipping"
        logger.info(msg)
        return {"status": "skipped", "reason": msg}

    # ── Build DataFrame ───────────────────────────────────────────────────────
    df = pd.DataFrame(rows)
    df["won"] = (df["status"] == "WIN").astype(float)

    # Unpack JSON strategy_scores into separate columns
    # strategy_scores is stored as {"MultiTimeframe": N, "SmartMoney": N, ...}
    name_map = {
        "MultiTimeframe":      "s1_score",
        "SmartMoney":          "s2_score",
        "PriceAction":         "s3_score",
        "TechnicalIndicators": "s4_score",
    }
    for full_name, col in name_map.items():
        df[col] = df["strategy_scores"].apply(
            lambda d: float(d.get(full_name, 50)) if isinstance(d, dict) else 50.0
        )

    # ── Strategy weight analysis ─────────────────────────────────────────────
    correlations = {}
    for col, name in zip(_STRATEGY_COLS, _STRATEGY_NAMES):
        if col in df.columns:
            corr = float(df[col].corr(df["won"]))
            correlations[name] = corr
            logger.info("Strategy %s win-correlation: %.3f", name, corr)
        else:
            correlations[name] = 0.0

    # Derive normalised weights (bounded)
    raw_weights = {n: max(0.01, c) for n, c in correlations.items()}
    total_raw   = sum(raw_weights.values())
    new_weights = {}
    for name, raw in raw_weights.items():
        bounded = max(_W_MIN, min(_W_MAX, raw / total_raw))
        new_weights[name] = round(bounded, 2)

    # Re-normalise to sum to 1.0
    weight_sum = sum(new_weights.values())
    new_weights = {k: round(v / weight_sum, 2) for k, v in new_weights.items()}

    logger.info("PerformanceAnalyzer: suggested new weights = %s", new_weights)

    # ── Best performing UTC hours ─────────────────────────────────────────────
    df["hour_utc"] = pd.to_numeric(df["hour_utc"], errors="coerce")
    hourly    = df.groupby("hour_utc")["won"].mean()
    best_hours = [int(h) for h in hourly[hourly > 0.6].index.tolist()]

    # ── Best pairs ────────────────────────────────────────────────────────────
    pair_stats = (
        df.groupby("pair")["won"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "win_rate", "count": "total"})
        .to_dict(orient="index")
    )

    overall_win_rate = float(df["won"].mean())

    # ── Build and save report ─────────────────────────────────────────────────
    report = {
        "updated_at":        datetime.now(timezone.utc).isoformat(),
        "signals_analyzed":  len(df),
        "overall_win_rate":  round(overall_win_rate, 3),
        "new_weights":       new_weights,
        "best_hours_utc":    best_hours,
        "pair_performance":  pair_stats,
        "correlations":      {k: round(v, 3) for k, v in correlations.items()},
    }

    try:
        report_json = json.dumps(report, default=str)
        db.execute_write(
            """
            INSERT INTO bot_state (key, value, updated_at)
            VALUES ('performance_report', %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """,
            (report_json,),
        )
        logger.info("PerformanceAnalyzer: report saved to bot_state")
    except Exception as exc:
        logger.error("PerformanceAnalyzer: failed to save report – %s", exc)

    # ── Send Telegram summary to admin ────────────────────────────────────────
    try:
        from notifications.notification_manager import notification_manager
        pairs_summary = "\n".join(
            f"  {pair}: {stats['win_rate']*100:.1f}% ({int(stats['total'])} sig)"
            for pair, stats in sorted(
                pair_stats.items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True,
            )
        )
        weights_summary = " | ".join(
            f"{k}={v}" for k, v in new_weights.items()
        )
        message = (
            f"📊 *Weekly Performance Report*\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 Signals analyzed: `{len(df)}`\n"
            f"🎯 Overall win rate: `{overall_win_rate*100:.1f}%`\n"
            f"⏰ Best hours UTC: `{best_hours}`\n\n"
            f"📈 *Pair Performance:*\n`{pairs_summary}`\n\n"
            f"⚖️ *Suggested weights:*\n`{weights_summary}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 ERICKsky Signal Engine"
        )
        notification_manager.send_admin_alert(message)
    except Exception as exc:
        logger.warning("PerformanceAnalyzer: Telegram report failed – %s", exc)

    return report
