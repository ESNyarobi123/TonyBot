-- ═══════════════════════════════════════════════════════════════
-- ERICKsky Signal Engine - Migration 002
-- Adds: news_events table (Upgrade 7 — Offline News Database)
-- Run once on the production database:
--   psql $DATABASE_URL -f migration_002_news_events.sql
-- ═══════════════════════════════════════════════════════════════

-- ─── news_events ──────────────────────────────────────────────────────────────
-- Stores high-impact economic calendar events fetched by the weekly 
-- NewsUpdater Celery task. The news_filter reads from here instead of 
-- making live API calls during signal scanning (avoids 429 errors).
CREATE TABLE IF NOT EXISTS news_events (
    id          BIGSERIAL    PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    currency    VARCHAR(10)  NOT NULL,
    impact      VARCHAR(20)  NOT NULL DEFAULT 'High',
    event_time  TIMESTAMPTZ  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (title, event_time)
);

CREATE INDEX IF NOT EXISTS idx_news_events_currency   ON news_events (currency);
CREATE INDEX IF NOT EXISTS idx_news_events_event_time ON news_events (event_time);
CREATE INDEX IF NOT EXISTS idx_news_events_impact     ON news_events (impact);

-- ─── signals table additions (Upgrade 4/5/6/9 metadata fields) ───────────────
-- Store regime, M15 confirmation and pattern data inside the existing 
-- filters_passed JSONB column — no schema change needed.

-- Optional: add explicit convenience columns for dashboard queries
ALTER TABLE signals
    ADD COLUMN IF NOT EXISTS m15_confirmed  BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS m15_score      SMALLINT    DEFAULT 0,
    ADD COLUMN IF NOT EXISTS market_regime  VARCHAR(20) DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS pattern_names  JSONB       DEFAULT '[]';

-- ─── bot_state seed entries ───────────────────────────────────────────────────
INSERT INTO bot_state (key, value) VALUES
    ('performance_report', NULL),
    ('news_db_last_updated', NULL)
ON CONFLICT (key) DO NOTHING;

-- Verify
DO $$
BEGIN
    RAISE NOTICE 'Migration 002 applied successfully.';
    RAISE NOTICE 'Tables: news_events created.';
    RAISE NOTICE 'Columns: signals.m15_confirmed, m15_score, market_regime, pattern_names added.';
END
$$;
