-- Migration: Add team record columns (wins, losses, ties) to teams table
-- These columns store current season records for teams

-- Add the columns if they don't exist
DO $$ 
BEGIN
    -- Add team_wins column
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'teams' 
        AND column_name = 'team_wins'
    ) THEN
        ALTER TABLE teams ADD COLUMN team_wins INTEGER DEFAULT 0;
        COMMENT ON COLUMN teams.team_wins IS 'Current season wins';
        RAISE NOTICE 'Added team_wins column to teams table';
    ELSE
        RAISE NOTICE 'Column team_wins already exists';
    END IF;
    
    -- Add team_losses column
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'teams' 
        AND column_name = 'team_losses'
    ) THEN
        ALTER TABLE teams ADD COLUMN team_losses INTEGER DEFAULT 0;
        COMMENT ON COLUMN teams.team_losses IS 'Current season losses';
        RAISE NOTICE 'Added team_losses column to teams table';
    ELSE
        RAISE NOTICE 'Column team_losses already exists';
    END IF;
    
    -- Add team_ties column (for NFL)
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'teams' 
        AND column_name = 'team_ties'
    ) THEN
        ALTER TABLE teams ADD COLUMN team_ties INTEGER DEFAULT 0;
        COMMENT ON COLUMN teams.team_ties IS 'Current season ties (NFL)';
        RAISE NOTICE 'Added team_ties column to teams table';
    ELSE
        RAISE NOTICE 'Column team_ties already exists';
    END IF;
END $$;

