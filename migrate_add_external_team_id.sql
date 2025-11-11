-- Migration: Add external_team_id column to teams table
-- This column stores external API team IDs (e.g., from ESPN, API-Football, etc.)

-- Add the column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'teams' 
        AND column_name = 'external_team_id'
    ) THEN
        ALTER TABLE teams ADD COLUMN external_team_id VARCHAR(100);
        COMMENT ON COLUMN teams.external_team_id IS 'External API team ID (e.g., from ESPN, API-Football, etc.)';
        RAISE NOTICE 'Added external_team_id column to teams table';
    ELSE
        RAISE NOTICE 'Column external_team_id already exists';
    END IF;
END $$;

