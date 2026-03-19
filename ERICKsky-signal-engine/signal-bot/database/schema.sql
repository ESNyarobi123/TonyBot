-- ═══════════════════════════════════════════════════
-- ERICKsky Signal Engine - PostgreSQL Schema
-- ═══════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── signals ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id                BIGSERIAL PRIMARY KEY,
    pair              VARCHAR(10)     NOT NULL,
    direction         VARCHAR(4)      NOT NULL CHECK (direction IN ('BUY', 'SELL')),
    entry_price       DECIMAL(10, 5)  NOT NULL,
    stop_loss         DECIMAL(10, 5)  NOT NULL,
    take_profit_1     DECIMAL(10, 5)  NOT NULL,
    take_profit_2     DECIMAL(10, 5),
    take_profit_3     DECIMAL(10, 5),
    timeframe         VARCHAR(5)      NOT NULL,
    strategy_scores   JSONB           NOT NULL DEFAULT '{}',
    consensus_score   INTEGER         NOT NULL CHECK (consensus_score BETWEEN 0 AND 100),
    confidence        VARCHAR(10)     NOT NULL CHECK (confidence IN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')),
    filters_passed    JSONB           NOT NULL DEFAULT '{}',
    status            VARCHAR(10)     NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'WIN', 'LOSS', 'EXPIRED')),
    pips_result       DECIMAL(6, 1),
    sent_at           TIMESTAMPTZ,
    closed_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals (pair);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals (status);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_direction ON signals (direction);

-- ─── subscribers ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscribers (
    id                        BIGSERIAL PRIMARY KEY,
    telegram_chat_id          VARCHAR(50)  NOT NULL UNIQUE,
    username                  VARCHAR(100),
    full_name                 VARCHAR(200),
    plan                      VARCHAR(20)  NOT NULL DEFAULT 'FREE'
                                CHECK (plan IN ('FREE', 'BASIC', 'PREMIUM')),
    subscribed_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at                TIMESTAMPTZ,
    is_active                 BOOLEAN      NOT NULL DEFAULT TRUE,
    total_signals_received    INTEGER      NOT NULL DEFAULT 0,
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscribers_chat_id ON subscribers (telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_subscribers_plan ON subscribers (plan);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers (is_active);

-- ─── pair_performance ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pair_performance (
    id            BIGSERIAL PRIMARY KEY,
    pair          VARCHAR(10)   NOT NULL,
    date          DATE          NOT NULL,
    signals_sent  INTEGER       NOT NULL DEFAULT 0,
    wins          INTEGER       NOT NULL DEFAULT 0,
    losses        INTEGER       NOT NULL DEFAULT 0,
    win_rate      DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    total_pips    DECIMAL(8, 1) NOT NULL DEFAULT 0.0,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (pair, date)
);

CREATE INDEX IF NOT EXISTS idx_pair_perf_pair ON pair_performance (pair);
CREATE INDEX IF NOT EXISTS idx_pair_perf_date ON pair_performance (date DESC);

-- ─── telegram_channels ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS telegram_channels (
    id                  BIGSERIAL PRIMARY KEY,
    channel_name        VARCHAR(100) NOT NULL,
    chat_id             VARCHAR(50)  NOT NULL UNIQUE,
    type                VARCHAR(20)  NOT NULL DEFAULT 'FREE'
                          CHECK (type IN ('FREE', 'PREMIUM')),
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    subscribers_count   INTEGER      NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ─── bot_state ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_state (
    id          BIGSERIAL PRIMARY KEY,
    key         VARCHAR(50) NOT NULL UNIQUE,
    value       TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default bot state
INSERT INTO bot_state (key, value) VALUES
    ('bot_running', 'true'),
    ('last_scan_at', NULL),
    ('signals_today', '0'),
    ('version', '1.0.0')
ON CONFLICT (key) DO NOTHING;

-- ─── Helper function: update pair_performance after signal resolution ─────────
CREATE OR REPLACE FUNCTION update_pair_performance()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status IN ('WIN', 'LOSS') AND OLD.status = 'PENDING' THEN
        INSERT INTO pair_performance (pair, date, signals_sent, wins, losses, win_rate, total_pips)
        VALUES (
            NEW.pair,
            DATE(NEW.created_at),
            1,
            CASE WHEN NEW.status = 'WIN' THEN 1 ELSE 0 END,
            CASE WHEN NEW.status = 'LOSS' THEN 1 ELSE 0 END,
            CASE WHEN NEW.status = 'WIN' THEN 100.0 ELSE 0.0 END,
            COALESCE(NEW.pips_result, 0)
        )
        ON CONFLICT (pair, date) DO UPDATE SET
            signals_sent = pair_performance.signals_sent + 1,
            wins         = pair_performance.wins + CASE WHEN NEW.status = 'WIN' THEN 1 ELSE 0 END,
            losses       = pair_performance.losses + CASE WHEN NEW.status = 'LOSS' THEN 1 ELSE 0 END,
            win_rate     = ROUND(
                             (pair_performance.wins + CASE WHEN NEW.status = 'WIN' THEN 1 ELSE 0 END)::decimal /
                             NULLIF(pair_performance.signals_sent + 1, 0) * 100,
                             2
                           ),
            total_pips   = pair_performance.total_pips + COALESCE(NEW.pips_result, 0);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_pair_performance
    AFTER UPDATE OF status ON signals
    FOR EACH ROW
    EXECUTE FUNCTION update_pair_performance();
