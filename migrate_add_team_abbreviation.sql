-- Migration: Add team_abbreviation column to teams table
-- This column stores the official team abbreviation from external APIs (e.g., Tank01 NFL API)
-- Only populated from API data, never generated/made up

-- Add the column if it doesn't exist
DO $$ 
BEGIN
    -- Add team_abbreviation column
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'teams' 
        AND column_name = 'team_abbreviation'
    ) THEN
        ALTER TABLE teams ADD COLUMN team_abbreviation VARCHAR(10);
        COMMENT ON COLUMN teams.team_abbreviation IS 'Official team abbreviation from external API (e.g., NE, NYJ, BUF). Only populated from API data, never generated.';
        RAISE NOTICE 'Added team_abbreviation column to teams table';
    ELSE
        RAISE NOTICE 'Column team_abbreviation already exists';
    END IF;
END $$;

