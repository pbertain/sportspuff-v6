-- sportspuff-v6 Database Schema
-- PostgreSQL database design for sports teams and stadiums

-- Create database (run this separately)
-- CREATE DATABASE sportspuff_v6;

-- Enable UUID extension for better primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Stadiums table
CREATE TABLE stadiums (
    stadium_id INTEGER PRIMARY KEY,
    full_stadium_name VARCHAR(255) NOT NULL,
    stadium_name VARCHAR(255) NOT NULL,
    location_name VARCHAR(255),
    city_name VARCHAR(100) NOT NULL,
    full_state_name VARCHAR(100),
    state_name VARCHAR(10) NOT NULL,
    country VARCHAR(10) NOT NULL DEFAULT 'us',
    capacity INTEGER NOT NULL,
    surface VARCHAR(100),
    year_opened INTEGER,
    roof_type VARCHAR(50),
    coordinates TEXT, -- Store as text, can be parsed to lat/lng later
    stadium_type VARCHAR(100),
    baseball_distance_to_center_field_ft INTEGER,
    baseball_distance_to_center_field_m DECIMAL(10,2),
    first_sport_year VARCHAR(20),
    soccer_field_width_yd INTEGER,
    soccer_field_width_m DECIMAL(10,2),
    soccer_field_length_yd INTEGER,
    soccer_field_length_m DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Teams table
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    full_team_name VARCHAR(255) NOT NULL,
    team_name VARCHAR(255) NOT NULL,
    real_team_name VARCHAR(255) NOT NULL,
    league_id INTEGER NOT NULL,
    league_name VARCHAR(50) NOT NULL,
    division_id INTEGER,
    division_name VARCHAR(100),
    division_full_name VARCHAR(100),
    conference_id INTEGER,
    conference_name VARCHAR(100),
    conference_full_name VARCHAR(100),
    league VARCHAR(10) NOT NULL, -- NHL, NFL, MLB, NBA, MLS, WNBA
    team_league_id INTEGER,
    city_name VARCHAR(100) NOT NULL,
    state_name VARCHAR(10) NOT NULL,
    country VARCHAR(10) DEFAULT 'us',
    stadium_id INTEGER REFERENCES stadiums(stadium_id) ON DELETE SET NULL,
    orig_logo_name VARCHAR(255),
    curl_cmd TEXT, -- Logo URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leagues lookup table (normalized)
CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY,
    league_name VARCHAR(50) NOT NULL,
    league_abbreviation VARCHAR(10) NOT NULL,
    sport VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Divisions lookup table
CREATE TABLE divisions (
    division_id INTEGER PRIMARY KEY,
    division_name VARCHAR(100) NOT NULL,
    division_full_name VARCHAR(100),
    conference_id INTEGER,
    league_id INTEGER REFERENCES leagues(league_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conferences lookup table
CREATE TABLE conferences (
    conference_id INTEGER PRIMARY KEY,
    conference_name VARCHAR(100) NOT NULL,
    conference_full_name VARCHAR(100),
    league_id INTEGER REFERENCES leagues(league_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better performance
CREATE INDEX idx_teams_stadium_id ON teams(stadium_id);
CREATE INDEX idx_teams_league ON teams(league);
CREATE INDEX idx_teams_city_state ON teams(city_name, state_name);
CREATE INDEX idx_stadiums_city_state ON stadiums(city_name, state_name);
CREATE INDEX idx_stadiums_capacity ON stadiums(capacity);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_stadiums_updated_at BEFORE UPDATE ON stadiums
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial league data
INSERT INTO leagues (league_id, league_name, league_abbreviation, sport) VALUES
(1, 'mlb', 'MLB', 'Baseball'),
(2, 'mls', 'MLS', 'Soccer'),
(3, 'nba', 'NBA', 'Basketball'),
(4, 'nfl', 'NFL', 'Football'),
(5, 'nhl', 'NHL', 'Hockey'),
(6, 'wnba', 'WNBA', 'Basketball');

-- Comments for documentation
COMMENT ON TABLE stadiums IS 'Stadium information including capacity, location, and specifications';
COMMENT ON TABLE teams IS 'Team information linked to stadiums and leagues';
COMMENT ON TABLE leagues IS 'League lookup table for sports organizations';
COMMENT ON TABLE divisions IS 'Division lookup table within leagues';
COMMENT ON TABLE conferences IS 'Conference lookup table within leagues';

COMMENT ON COLUMN stadiums.coordinates IS 'GPS coordinates as text, can be parsed to separate lat/lng columns later';
COMMENT ON COLUMN teams.stadium_id IS 'Foreign key linking team to their home stadium';
COMMENT ON COLUMN teams.league IS 'League abbreviation for quick reference';
