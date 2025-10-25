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
    conference_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    conference_name VARCHAR(100) NOT NULL,
    conference_full_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create divisions table (depends on leagues)
CREATE TABLE divisions (
    division_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    division_name VARCHAR(100) NOT NULL,
    division_full_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create teams table last (depends on all other tables)
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    full_team_name VARCHAR(255) NOT NULL,
    team_name VARCHAR(255) NOT NULL,
    real_team_name VARCHAR(255) NOT NULL,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id) ON DELETE CASCADE,
    division_id INTEGER REFERENCES divisions(division_id) ON DELETE SET NULL,
    conference_id INTEGER REFERENCES conferences(conference_id) ON DELETE SET NULL,
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
);

-- Create indexes for better performance
CREATE INDEX idx_teams_league_id ON teams(league_id);
CREATE INDEX idx_teams_division_id ON teams(division_id);
CREATE INDEX idx_teams_conference_id ON teams(conference_id);
CREATE INDEX idx_teams_stadium_id ON teams(stadium_id);
CREATE INDEX idx_divisions_league_id ON divisions(league_id);
CREATE INDEX idx_conferences_league_id ON conferences(league_id);


-- Add comments for documentation
COMMENT ON TABLE leagues IS 'Sports leagues (MLB, NFL, NBA, NHL, MLS, WNBA, IPL)';
COMMENT ON TABLE stadiums IS 'Sports venues and stadiums';
COMMENT ON TABLE conferences IS 'League conferences (e.g., Eastern, Western, NFC, AFC)';
COMMENT ON TABLE divisions IS 'League divisions (e.g., Atlantic, Pacific, East, West)';
COMMENT ON TABLE teams IS 'Sports teams with foreign key references to leagues, divisions, conferences, and stadiums';

COMMENT ON COLUMN teams.league_id IS 'Foreign key to leagues table';
COMMENT ON COLUMN teams.division_id IS 'Foreign key to divisions table';
COMMENT ON COLUMN teams.conference_id IS 'Foreign key to conferences table';
COMMENT ON COLUMN teams.stadium_id IS 'Foreign key to stadiums table';
