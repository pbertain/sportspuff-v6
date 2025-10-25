-- Sportspuff v6 Modular Database Schema
-- This schema implements proper foreign key relationships with separate tables

-- Drop existing tables if they exist (in correct order due to foreign keys)
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS divisions CASCADE;
DROP TABLE IF EXISTS conferences CASCADE;
DROP TABLE IF EXISTS stadiums CASCADE;
DROP TABLE IF EXISTS leagues CASCADE;

-- Create leagues table first (no dependencies)
CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY,
    league_name_full VARCHAR(255) NOT NULL,
    league_name VARCHAR(50) NOT NULL,
    league_name_proper VARCHAR(50) NOT NULL,
    city_name VARCHAR(100),
    state_name VARCHAR(100),
    country VARCHAR(100),
    logo_filename VARCHAR(255),
    team_count INTEGER DEFAULT 0,
    conference_count INTEGER DEFAULT 0,
    division_count INTEGER DEFAULT 0,
    current_champion_id INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create stadiums table (no dependencies)
CREATE TABLE stadiums (
    stadium_id INTEGER PRIMARY KEY,
    image VARCHAR(255),
    full_stadium_name VARCHAR(255) NOT NULL,
    stadium_name VARCHAR(255),
    location_name VARCHAR(255),
    city_name VARCHAR(100),
    full_state_name VARCHAR(100),
    state_name VARCHAR(100),
    country VARCHAR(100),
    capacity INTEGER,
    surface VARCHAR(100),
    year_opened INTEGER,
    roof_type VARCHAR(100),
    coordinates VARCHAR(100),
    stadium_type VARCHAR(100),
    baseball_distance_to_center_field_ft INTEGER,
    baseball_distance_to_center_field_m DECIMAL(10, 2),
    first_sport_year INTEGER,
    soccer_field_width_yd INTEGER,
    soccer_field_width_m DECIMAL(10, 2),
    soccer_field_length_yd INTEGER,
    soccer_field_length_m DECIMAL(10, 2),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create conferences table (depends on leagues)
CREATE TABLE conferences (
    conference_id INTEGER,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    conference_name VARCHAR(100) NOT NULL,
    conference_full_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (league_id, conference_name),
    UNIQUE(league_id, conference_full_name)
);

-- Create divisions table (depends on leagues)
CREATE TABLE divisions (
    division_id INTEGER,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    division_name VARCHAR(100) NOT NULL,
    division_full_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (league_id, division_name),
    UNIQUE(league_id, division_full_name)
);

-- Create teams table last (depends on all other tables)
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    full_team_name VARCHAR(255) NOT NULL,
    team_name VARCHAR(255) NOT NULL,
    real_team_name VARCHAR(255) NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    division_name VARCHAR(100),
    conference_name VARCHAR(100),
    team_league_id INTEGER,
    city_name VARCHAR(100),
    state_name VARCHAR(100),
    country VARCHAR(100),
    stadium_id INTEGER REFERENCES stadiums(stadium_id) ON DELETE SET NULL,
    logo_filename VARCHAR(255),
    team_color_1 VARCHAR(7),
    team_color_2 VARCHAR(7),
    team_color_3 VARCHAR(7),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (league_id, division_name) REFERENCES divisions(league_id, division_name) ON DELETE SET NULL,
    FOREIGN KEY (league_id, conference_name) REFERENCES conferences(league_id, conference_name) ON DELETE SET NULL
);

-- Create indexes for better performance
CREATE INDEX idx_teams_league_id ON teams(league_id);
CREATE INDEX idx_teams_division_name ON teams(league_id, division_name);
CREATE INDEX idx_teams_conference_name ON teams(league_id, conference_name);
CREATE INDEX idx_teams_stadium_id ON teams(stadium_id);
CREATE INDEX idx_divisions_league_id ON divisions(league_id);
CREATE INDEX idx_conferences_league_id ON conferences(league_id);

-- NBA Games table (unified schedule + scores)
CREATE TABLE nba_games (
    game_id TEXT PRIMARY KEY,
    season TEXT NOT NULL,
    game_date DATE NOT NULL,
    game_time_est TEXT,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    game_status TEXT DEFAULT 'scheduled',
    game_status_text TEXT,
    current_period INTEGER,
    period_time_remaining TEXT,
    season_type TEXT NOT NULL,
    arena_name TEXT,
    is_nba_cup BOOLEAN DEFAULT FALSE,
    winner_team_id INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraints
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id) ON DELETE SET NULL,
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id) ON DELETE SET NULL,
    FOREIGN KEY (winner_team_id) REFERENCES teams(team_id) ON DELETE SET NULL
);

-- NBA Seasons metadata table
CREATE TABLE nba_seasons (
    season TEXT PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    regular_season_start DATE,
    playoffs_start DATE,
    total_games INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for NBA tables
CREATE INDEX idx_nba_games_date ON nba_games(game_date);
CREATE INDEX idx_nba_games_season ON nba_games(season);
CREATE INDEX idx_nba_games_teams ON nba_games(home_team_id, away_team_id);
CREATE INDEX idx_nba_games_status ON nba_games(game_status);
CREATE INDEX idx_nba_games_season_type ON nba_games(season_type);

-- Add comments for documentation
COMMENT ON TABLE leagues IS 'Sports leagues (MLB, NFL, NBA, NHL, MLS, WNBA, IPL)';
COMMENT ON TABLE stadiums IS 'Sports venues and stadiums';
COMMENT ON TABLE conferences IS 'League conferences (e.g., Eastern, Western, NFC, AFC)';
COMMENT ON TABLE divisions IS 'League divisions (e.g., Atlantic, Pacific, East, West)';
COMMENT ON TABLE teams IS 'Sports teams with foreign key references to leagues, divisions, conferences, and stadiums';
COMMENT ON TABLE nba_games IS 'NBA games with unified schedule and scores - tracks complete game lifecycle from scheduled to final';
COMMENT ON TABLE nba_seasons IS 'NBA season metadata including start/end dates and game counts';

COMMENT ON COLUMN teams.league_id IS 'Foreign key to leagues table';
COMMENT ON COLUMN teams.division_name IS 'Foreign key to divisions table (composite with league_id)';
COMMENT ON COLUMN teams.conference_name IS 'Foreign key to conferences table (composite with league_id)';
COMMENT ON COLUMN teams.stadium_id IS 'Foreign key to stadiums table';
