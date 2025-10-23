#!/bin/bash
# Fix pandas/numpy compatibility issue
# This script reinstalls pandas and numpy with compatible versions

set -e

echo "Fixing pandas/numpy compatibility issue..."

# Check if we're in the right directory
if [ ! -d "/opt/sportspuff-v6-prod/venv" ]; then
    echo "Error: Virtual environment not found at /opt/sportspuff-v6-prod/venv"
    exit 1
fi

# Uninstall pandas and numpy
echo "Uninstalling pandas and numpy..."
/opt/sportspuff-v6-prod/venv/bin/pip uninstall -y pandas numpy

# Reinstall with compatible versions
echo "Installing compatible pandas and numpy versions..."
/opt/sportspuff-v6-prod/venv/bin/pip install numpy==1.24.3 pandas==1.5.3

echo "Pandas/numpy compatibility fix completed!"
echo ""
echo "Now you can run the data import:"
echo "sudo -u postgres ./reimport_data.sh"
