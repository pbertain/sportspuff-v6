#!/bin/bash
# Sportspuff v6 Data Re-import Script
# This script re-imports data from the updated CSV files

set -e

echo "Re-importing Sportspuff v6 data..."

# Check if we're in the right directory
if [ ! -f "import_data_modular.py" ]; then
    echo "Error: import_data_modular.py not found. Please run this script from the project root."
    exit 1
fi

# Check if CSV files exist
if [ ! -f "info-leagues.csv" ] || [ ! -f "info-divisions.csv" ] || [ ! -f "info-conferences.csv" ] || [ ! -f "info-teams.csv" ] || [ ! -f "info-stadiums.csv" ]; then
    echo "Error: Required CSV files not found. Please ensure all info-*.csv files are present."
    exit 1
fi

# Run the import script
echo "Running data import..."
python3 import_data_modular.py

echo "Data re-import completed successfully!"
echo ""
echo "Updated data includes:"
echo "- All MLB divisions (AL East, AL Central, AL West, NL East, NL Central, NL West)"
echo "- All NFL divisions (AFC East, AFC North, AFC South, AFC West, NFC East, NFC North, NFC South, NFC West)"
echo "- All NBA divisions (Atlantic, Central, Southeast, Northwest, Pacific, Southwest)"
echo "- All NHL divisions (Atlantic, Metropolitan, Central, Pacific)"
echo "- Team colors for NFL, NBA, MLB, NHL teams"
