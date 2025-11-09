#!/usr/bin/env python3
"""
Migration script to add new columns to stadiums table
Adds: full_alt_name, alt_name, image_name
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'sportspuff_v6'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def run_migration():
    """Run the migration to add new columns"""
    print("Running migration to add new columns to stadiums table...")
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Add full_alt_name column
        print("Adding full_alt_name column...")
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='stadiums' AND column_name='full_alt_name'
                ) THEN
                    ALTER TABLE stadiums ADD COLUMN full_alt_name VARCHAR(255);
                END IF;
            END $$;
        """)
        
        # Add alt_name column
        print("Adding alt_name column...")
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='stadiums' AND column_name='alt_name'
                ) THEN
                    ALTER TABLE stadiums ADD COLUMN alt_name VARCHAR(255);
                END IF;
            END $$;
        """)
        
        # Add image_name column
        print("Adding image_name column...")
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name='stadiums' AND column_name='image_name'
                ) THEN
                    ALTER TABLE stadiums ADD COLUMN image_name VARCHAR(500);
                END IF;
            END $$;
        """)
        
        conn.commit()
        
        # Verify columns were added
        print("\nVerifying columns were added...")
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = 'stadiums' 
            AND column_name IN ('full_alt_name', 'alt_name', 'image_name')
            ORDER BY column_name;
        """)
        
        results = cursor.fetchall()
        if results:
            print("\nColumns successfully added:")
            for row in results:
                print(f"  - {row[0]}: {row[1]}({row[2]})")
        else:
            print("Warning: No columns found (they may have already existed)")
        
        cursor.close()
        conn.close()
        
        print("\nMigration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False

if __name__ == "__main__":
    success = run_migration()
    exit(0 if success else 1)

