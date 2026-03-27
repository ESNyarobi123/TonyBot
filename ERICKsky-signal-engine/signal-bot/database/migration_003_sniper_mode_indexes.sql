-- ═══════════════════════════════════════════════════════════════
-- Migration 003 — Sniper Mode: 15-Minute Scan Optimisation
-- ═══════════════════════════════════════════════════════════════
--
-- Context:
--   Switching from hourly scans (crontab minute=0) to 15-minute
--   sniper scans (crontab minute='*/15') increases the rate at
--   which find_duplicate_recent() and find_by_pair_today() are
--   called — up to 96 queries/pair/day instead of 24.
--
--   The existing single-column indexes (pair, status) force a
--   bitmap merge on each call.  This migration adds:
--     1. Composite index covering the exact WHERE + ORDER BY of
--        find_duplicate_recent:  (pair, direction, status, created_at)
--     2. Composite index for find_by_pair_today:  (pair, created_at)
--     3. Index on sent_at for expire_old_signals UPDATE:  (status, sent_at)
--
-- Safe to run on a live database — all operations are
-- CREATE INDEX IF NOT EXISTS (non-blocking on PG 11+).
-- ═══════════════════════════════════════════════════════════════

-- 1. Fast duplicate-signal lookup (used every 15 min per pair)
--    Covers: WHERE pair=? AND direction=? AND status='PENDING'
--            AND created_at > NOW() - INTERVAL '4 hours'
--    ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_signals_pair_dir_status_created
    ON signals (pair, direction, status, created_at DESC);

-- 2. Fast today-signals lookup (used every 15 min per pair)
--    Covers: WHERE pair=? AND DATE(created_at) = CURRENT_DATE
CREATE INDEX IF NOT EXISTS idx_signals_pair_created
    ON signals (pair, created_at DESC);

-- 3. Fast expire-old-signals UPDATE (runs every 30 min)
--    Covers: WHERE status='PENDING' AND sent_at < NOW() - INTERVAL '...'
CREATE INDEX IF NOT EXISTS idx_signals_status_sent_at
    ON signals (status, sent_at)
    WHERE status = 'PENDING';
