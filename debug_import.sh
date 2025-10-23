#!/bin/bash

echo "=== Sportspuff Data Import Debug Script ==="
echo ""

# Check if we're in the right directory
echo "Current directory: $(pwd)"
echo ""

# Check if virtual environment exists
echo "Checking virtual environment..."
if [ -d "/opt/sportspuff-v6-prod/venv" ]; then
    echo "✓ Virtual environment exists"
else
    echo "✗ Virtual environment missing"
    exit 1
fi

# Check Python version
echo ""
echo "Python version in venv:"
/opt/sportspuff-v6-prod/venv/bin/python --version

# Check if pandas and numpy are installed
echo ""
echo "Checking pandas and numpy versions..."
/opt/sportspuff-v6-prod/venv/bin/python -c "
try:
    import pandas as pd
    import numpy as np
    print(f'✓ pandas: {pd.__version__}')
    print(f'✓ numpy: {np.__version__}')
except ImportError as e:
    print(f'✗ Import error: {e}')
"

# Check if CSV files exist
echo ""
echo "Checking CSV files..."
for file in info-leagues.csv info-stadiums.csv info-conferences.csv info-divisions.csv info-teams.csv; do
    if [ -f "$file" ]; then
        echo "✓ $file exists"
        echo "  Size: $(wc -l < $file) lines"
    else
        echo "✗ $file missing"
    fi
done

# Check database connection
echo ""
echo "Testing database connection..."
/opt/sportspuff-v6-prod/venv/bin/python -c "
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM teams;')
    team_count = cur.fetchone()[0]
    print(f'✓ Database connection successful')
    print(f'✓ Teams in database: {team_count}')
    
    # Check if team colors exist
    cur.execute('SELECT COUNT(*) FROM teams WHERE team_color_1 IS NOT NULL;')
    colored_teams = cur.fetchone()[0]
    print(f'✓ Teams with colors: {colored_teams}')
    
    cur.close()
    conn.close()
except Exception as e:
    print(f'✗ Database error: {e}')
"

# Try to run the import script with verbose output
echo ""
echo "Attempting to run import script..."
cd /opt/sportspuff-v6-prod
/opt/sportspuff-v6-prod/venv/bin/python import_data_modular.py
