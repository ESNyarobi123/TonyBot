-- Migration: Add agreement_count and strategy_directions to signals table
-- This fixes the bug where agreement count shows 2/4 instead of actual 4/4

-- Add strategy_directions column (stores per-strategy direction votes)
ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS strategy_directions JSONB NOT NULL DEFAULT '{}';

-- Add agreement_count column (stores number of agreeing strategies)
ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS agreement_count INTEGER NOT NULL DEFAULT 0;

-- Update existing signals to have default values
UPDATE signals 
SET strategy_directions = '{}', 
    agreement_count = 0 
WHERE agreement_count IS NULL OR strategy_directions IS NULL;
