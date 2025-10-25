#!/bin/bash

# NBA Scores Update Script
# This script updates live NBA scores and can be run via cron

set -e

echo "Updating NBA scores..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Update scores for today
echo "Updating scores for $(date +%Y-%m-%d)..."
python3 nba_scores_updater.py

if [ $? -eq 0 ]; then
    echo "NBA scores updated successfully"
else
    echo "Error updating NBA scores"
    exit 1
fi

echo "NBA scores update completed!"
