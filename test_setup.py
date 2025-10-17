#!/usr/bin/env python3
"""
Test script for sportspuff-v6
Verifies database setup and data integrity
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'sportspuff_v6'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

def test_database_connection():
    """Test database connection"""
    print("🔌 Testing database connection...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Connected to PostgreSQL: {version[0]}")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_tables_exist():
    """Test that all required tables exist"""
    print("\n📋 Testing table existence...")
    required_tables = ['teams', 'stadiums', 'leagues', 'divisions', 'conferences']
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        for table in required_tables:
            cursor.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}');")
            exists = cursor.fetchone()[0]
            if exists:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                return False
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error checking tables: {e}")
        return False

def test_data_integrity():
    """Test data integrity and relationships"""
    print("\n🔍 Testing data integrity...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test team count
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        team_count = cursor.fetchone()['count']
        print(f"📊 Teams in database: {team_count}")
        
        # Test stadium count
        cursor.execute("SELECT COUNT(*) as count FROM stadiums")
        stadium_count = cursor.fetchone()['count']
        print(f"🏟️  Stadiums in database: {stadium_count}")
        
        # Test relationships
        cursor.execute("""
            SELECT COUNT(*) as count FROM teams t 
            JOIN stadiums s ON t.stadium_id = s.stadium_id
        """)
        linked_count = cursor.fetchone()['count']
        print(f"🔗 Teams linked to stadiums: {linked_count}")
        
        # Test for orphaned stadium references
        cursor.execute("""
            SELECT COUNT(*) as count FROM teams t 
            WHERE t.stadium_id IS NOT NULL 
            AND NOT EXISTS (SELECT 1 FROM stadiums s WHERE s.stadium_id = t.stadium_id)
        """)
        orphaned_count = cursor.fetchone()['count']
        if orphaned_count == 0:
            print("✅ No orphaned stadium references")
        else:
            print(f"⚠️  {orphaned_count} teams have invalid stadium references")
        
        # Test league distribution
        cursor.execute("""
            SELECT league, COUNT(*) as count 
            FROM teams 
            GROUP BY league 
            ORDER BY count DESC
        """)
        league_stats = cursor.fetchall()
        print("\n📈 Teams by league:")
        for stat in league_stats:
            print(f"   {stat['league'].upper()}: {stat['count']} teams")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing data integrity: {e}")
        return False

def test_sample_queries():
    """Test sample queries that the web app will use"""
    print("\n🔍 Testing sample queries...")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test team search
        cursor.execute("""
            SELECT t.real_team_name, s.full_stadium_name
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            WHERE t.real_team_name ILIKE '%Lakers%'
            LIMIT 1
        """)
        lakers = cursor.fetchone()
        if lakers:
            print(f"✅ Found Lakers: {lakers['real_team_name']} -> {lakers['full_stadium_name']}")
        else:
            print("⚠️  Lakers not found (may not be in dataset)")
        
        # Test stadium capacity query
        cursor.execute("""
            SELECT full_stadium_name, capacity 
            FROM stadiums 
            ORDER BY capacity DESC 
            LIMIT 3
        """)
        largest_stadiums = cursor.fetchall()
        print("🏟️  Largest stadiums:")
        for stadium in largest_stadiums:
            print(f"   {stadium['full_stadium_name']}: {stadium['capacity']:,} capacity")
        
        # Test league filter
        cursor.execute("""
            SELECT COUNT(*) as count FROM teams WHERE league = 'nfl'
        """)
        nfl_count = cursor.fetchone()['count']
        print(f"🏈 NFL teams: {nfl_count}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error testing sample queries: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Running Sportspuff v6 Tests\n")
    
    tests = [
        test_database_connection,
        test_tables_exist,
        test_data_integrity,
        test_sample_queries
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your Sportspuff v6 setup is ready.")
        print("\n🚀 Next steps:")
        print("   1. Run: python3 app.py")
        print("   2. Open: http://localhost:5000")
        print("   3. Start building your sports app!")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("   1. Ensure PostgreSQL is running")
        print("   2. Check your .env file configuration")
        print("   3. Run the setup script: ./setup.sh")

if __name__ == "__main__":
    main()
