-- Updated Sportspuff v6 Database Schema
-- This schema matches the updated CSV format with all columns

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create leagues table
CREATE TABLE IF NOT EXISTS leagues (
    league_id SERIAL PRIMARY KEY,
    league_name VARCHAR(100) NOT NULL,
    league_abbreviation VARCHAR(10) NOT NULL UNIQUE,
    headquarters_city VARCHAR(100),
    headquarters_state VARCHAR(50),
    headquarters_country VARCHAR(50),
    founded_year INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create conferences table
CREATE TABLE IF NOT EXISTS conferences (
    conference_id SERIAL PRIMARY KEY,
    league_id INTEGER REFERENCES leagues(league_id) ON DELETE CASCADE,
    conference_name VARCHAR(100) NOT NULL,
    conference_full_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(league_id, conference_name)
);

-- Create divisions table
CREATE TABLE IF NOT EXISTS divisions (
    division_id SERIAL PRIMARY KEY,
    league_id INTEGER REFERENCES leagues(league_id) ON DELETE CASCADE,
    division_name VARCHAR(100) NOT NULL,
    division_full_name VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(league_id, division_name)
);

-- Create stadiums table with all columns from CSV
CREATE TABLE IF NOT EXISTS stadiums (
    stadium_id SERIAL PRIMARY KEY,
    image VARCHAR(500),
    full_stadium_name VARCHAR(200) NOT NULL,
    stadium_name VARCHAR(200),
    location_name VARCHAR(200),
    city_name VARCHAR(100) NOT NULL,
    full_state_name VARCHAR(100),
    state_name VARCHAR(50),
    country VARCHAR(50),
    capacity INTEGER,
    surface VARCHAR(100),
    year_opened INTEGER,
    roof_type VARCHAR(100),
    coordinates VARCHAR(200),
    stadium_type VARCHAR(100),
    baseball_distance_to_center_field_ft INTEGER,
    baseball_distance_to_center_field_m DECIMAL(5,2),
    first_sport_year INTEGER,
    soccer_field_width_yd INTEGER,
    soccer_field_width_m DECIMAL(5,2),
    soccer_field_length_yd INTEGER,
    soccer_field_length_m DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create teams table with all columns from CSV
CREATE TABLE IF NOT EXISTS teams (
    team_id SERIAL PRIMARY KEY,
    full_team_name VARCHAR(200),
    team_name VARCHAR(200),
    real_team_name VARCHAR(200) NOT NULL,
    league_id INTEGER REFERENCES leagues(league_id) ON DELETE CASCADE,
    league_name VARCHAR(100),
    division_id INTEGER REFERENCES divisions(division_id) ON DELETE SET NULL,
    division_name VARCHAR(100),
    division_full_name VARCHAR(200),
    conference_id INTEGER REFERENCES conferences(conference_id) ON DELETE SET NULL,
    conference_name VARCHAR(100),
    conference_full_name VARCHAR(200),
    league VARCHAR(100) NOT NULL,
    team_league_id INTEGER,
    city_name VARCHAR(100),
    state_name VARCHAR(50),
    country VARCHAR(50),
    stadium_id INTEGER REFERENCES stadiums(stadium_id) ON DELETE SET NULL,
    logo_filename VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_teams_league ON teams(league);
CREATE INDEX IF NOT EXISTS idx_teams_stadium_id ON teams(stadium_id);
CREATE INDEX IF NOT EXISTS idx_teams_division_name ON teams(division_name);
CREATE INDEX IF NOT EXISTS idx_teams_conference_name ON teams(conference_name);
CREATE INDEX IF NOT EXISTS idx_stadiums_city ON stadiums(city_name);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers to automatically update updated_at
CREATE TRIGGER update_leagues_updated_at BEFORE UPDATE ON leagues FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_conferences_updated_at BEFORE UPDATE ON conferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_divisions_updated_at BEFORE UPDATE ON divisions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_stadiums_updated_at BEFORE UPDATE ON stadiums FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert initial leagues data
INSERT INTO leagues (league_name, league_abbreviation, headquarters_city, headquarters_state, headquarters_country, founded_year) VALUES
('Major League Baseball', 'MLB', 'New York', 'NY', 'USA', 1903),
('National Football League', 'NFL', 'New York', 'NY', 'USA', 1920),
('National Basketball Association', 'NBA', 'New York', 'NY', 'USA', 1946),
('National Hockey League', 'NHL', 'New York', 'NY', 'USA', 1917),
('Major League Soccer', 'MLS', 'New York', 'NY', 'USA', 1993),
('Women''s National Basketball Association', 'WNBA', 'New York', 'NY', 'USA', 1996),
('Indian Premier League', 'IPL', 'Mumbai', 'MH', 'India', 2008)
ON CONFLICT (league_abbreviation) DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE leagues IS 'Professional sports leagues';
COMMENT ON TABLE conferences IS 'League conferences/divisions';
COMMENT ON TABLE divisions IS 'League divisions within conferences';
COMMENT ON TABLE stadiums IS 'Sports venues and stadiums';
COMMENT ON TABLE teams IS 'Professional sports teams';
