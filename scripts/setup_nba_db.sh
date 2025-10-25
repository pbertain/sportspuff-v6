#!/bin/bash

# NBA Database Setup Script
# This script sets up the NBA tables and imports initial season data

set -e

echo "Setting up NBA database..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Database connection parameters
DB_HOST=${DB_HOST:-localhost}
DB_NAME=${DB_NAME:-sportspuff_v6}
DB_USER=${DB_USER:-postgres}

echo "Connecting to database: $DB_NAME on $DB_HOST as $DB_USER"

# Create NBA tables
echo "Creating NBA tables..."
psql -h $DB_HOST -d $DB_NAME -U $DB_USER -f database_schema_modular.sql

if [ $? -eq 0 ]; then
    echo "NBA tables created successfully"
else
    echo "Error creating NBA tables"
    exit 1
fi

# Import current season data
echo "Importing current NBA season data..."
python3 nba_data_importer.py --current-season

if [ $? -eq 0 ]; then
    echo "NBA season data imported successfully"
else
    echo "Error importing NBA season data"
    exit 1
fi

echo "NBA database setup completed!"
echo ""
echo "Next steps:"
echo "1. Run 'python3 nba_scores_updater.py' to update live scores"
echo "2. Set up cron job for automatic score updates:"
echo "   */5 * * * * cd /path/to/sportspuff-v6 && python3 nba_scores_updater.py"
