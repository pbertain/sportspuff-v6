#!/bin/bash
# Script to reimport teams, conferences, and divisions data
# This will update existing data while preserving external_team_id values

set -e

echo "=== Reimporting Teams, Conferences, and Divisions Data ==="

# Check if we're in the right directory
if [ ! -f "info-teams.csv" ] || [ ! -f "info-conferences.csv" ] || [ ! -f "info-divisions.csv" ]; then
    echo "Error: CSV files not found. Please run this script from the project root."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run migration to add external_team_id column if needed
echo "Step 1: Running migration to add external_team_id column..."
python3 -c "
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'sportspuff_v6'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432')
    )
    cursor = conn.cursor()
    
    # Read and execute migration
    with open('migrate_add_external_team_id.sql', 'r') as f:
        cursor.execute(f.read())
    
    conn.commit()
    cursor.close()
    conn.close()
    print('Migration completed successfully')
except Exception as e:
    print(f'Migration error (may already be applied): {e}')
"

# Run the import script
echo "Step 2: Importing data from CSV files..."
python3 import_data_modular.py

echo "=== Reimport Complete ==="

