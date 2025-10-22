#!/bin/bash
# Sportspuff v6 Modular Database Setup Script
# This script sets up the new modular database structure with proper foreign keys

set -e

echo "Setting up Sportspuff v6 Modular Database..."

# Check if we're running as the correct user
if [ "$USER" != "postgres" ]; then
    echo "This script must be run as the postgres user"
    echo "Please run: sudo -u postgres $0"
    exit 1
fi

# Check if database exists
if psql -lqt | cut -d \| -f 1 | grep -qw sportspuff_v6; then
    echo "Database sportspuff_v6 already exists"
    echo "Do you want to recreate it? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "Dropping existing database..."
        dropdb sportspuff_v6
    else
        echo "Using existing database"
    fi
fi

# Create database if it doesn't exist
if ! psql -lqt | cut -d \| -f 1 | grep -qw sportspuff_v6; then
    echo "Creating database sportspuff_v6..."
    createdb sportspuff_v6
fi

# Run the modular schema
echo "Creating modular database schema..."
psql -d sportspuff_v6 -f database_schema_modular.sql

# Import the modular data
echo "Importing modular data..."
python3 import_data_modular.py

echo "Modular database setup completed successfully!"
echo ""
echo "Database structure:"
echo "- leagues: Contains all sports leagues"
echo "- stadiums: Contains all sports venues"
echo "- conferences: Contains league conferences (references leagues)"
echo "- divisions: Contains league divisions (references leagues)"
echo "- teams: Contains all teams (references leagues, divisions, conferences, stadiums)"
echo ""
echo "Foreign key relationships:"
echo "- teams.league_id -> leagues.league_id"
echo "- teams.division_id -> divisions.division_id"
echo "- teams.conference_id -> conferences.conference_id"
echo "- teams.stadium_id -> stadiums.stadium_id"
echo "- divisions.league_id -> leagues.league_id"
echo "- conferences.league_id -> leagues.league_id"
