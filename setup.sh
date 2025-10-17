#!/bin/bash

# Sportspuff v6 Setup Script
# This script sets up the database and imports the data

echo "🏟️  Setting up Sportspuff v6..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed. Please install PostgreSQL first."
    echo "   On macOS: brew install postgresql"
    echo "   On Ubuntu: sudo apt-get install postgresql postgresql-contrib"
    exit 1
fi

# Check if Python dependencies are installed
if ! python3 -c "import psycopg2, pandas, flask" &> /dev/null; then
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your database credentials before continuing."
    echo "   Database password, host, and other settings need to be configured."
    read -p "Press Enter after updating .env file..."
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

echo "🗄️  Setting up database..."

# Create database
echo "Creating database: $DB_NAME"
createdb -h $DB_HOST -U $DB_USER $DB_NAME 2>/dev/null || echo "Database may already exist"

# Run schema creation
echo "Creating database schema..."
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f database_schema.sql

# Import data
echo "📊 Importing data..."
python3 import_data.py

echo "✅ Setup complete!"
echo ""
echo "🚀 To start the web application:"
echo "   python3 app.py"
echo ""
echo "🌐 The application will be available at: http://localhost:5000"
echo ""
echo "📋 Next steps:"
echo "   1. Start the web application"
echo "   2. Browse teams and stadiums"
echo "   3. Test the API endpoints"
echo "   4. Plan your schedule/standings integration"
