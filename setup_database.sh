#!/bin/bash

# Setup PostgreSQL database for sportspuff-v6
# This script avoids interactive password prompts

set -e

DB_NAME="sportspuff_v6"
DB_USER="postgres"
DB_PASSWORD="sportspuff2024!"

echo "Setting up PostgreSQL database..."

# Start PostgreSQL if not running
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Wait for PostgreSQL to be ready
sleep 5

# Set postgres user password using environment variable
export PGPASSWORD=""
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$DB_PASSWORD';" || echo "Password already set"

# Create database
sudo -u postgres createdb $DB_NAME || echo "Database already exists"

# Create application user
sudo -u postgres createuser -s $DB_USER || echo "User already exists"

# Grant privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" || echo "Privileges already granted"

# Run database schema
if [ -f "database_schema.sql" ]; then
    echo "Running database schema..."
    sudo -u postgres psql -d $DB_NAME -f database_schema.sql || echo "Schema already applied"
else
    echo "Warning: database_schema.sql not found"
fi

# Import data
if [ -f "import_data.py" ]; then
    echo "Importing data..."
    export DB_HOST="localhost"
    export DB_NAME="$DB_NAME"
    export DB_USER="$DB_USER"
    export DB_PASSWORD="$DB_PASSWORD"
    python3 import_data.py || echo "Data import failed or already imported"
else
    echo "Warning: import_data.py not found"
fi

echo "Database setup complete!"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo "Password: $DB_PASSWORD"
