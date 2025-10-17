#!/usr/bin/env python3
"""
Data import script for sportspuff-v6
Imports teams and stadiums data from CSV files into PostgreSQL
"""

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
from datetime import datetime
import sys

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'database': 'sportspuff_v6',
    'user': 'postgres',
    'password': 'password'  # Change this to your PostgreSQL password
}

def connect_to_db():
    """Connect to PostgreSQL database"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def import_stadiums(cursor, conn):
    """Import stadiums data from CSV"""
    print("Importing stadiums...")
    
    # Read CSV
    df = pd.read_csv('final_stadiums.csv')
    
    # Clean and prepare data
    df = df.fillna('')  # Replace NaN with empty strings
    
    # Convert year_opened to integer, handling NaN
    df['year_opened'] = pd.to_numeric(df['year_opened'], errors='coerce').fillna(0).astype(int)
    df.loc[df['year_opened'] == 0, 'year_opened'] = None
    
    # Prepare data for insertion
    stadiums_data = []
    for _, row in df.iterrows():
        stadium_data = (
            int(row['stadium_id']),
            row['full_stadium_name'],
            row['stadium_name'],
            row['location_name'] if pd.notna(row['location_name']) else None,
            row['city_name'],
            row['full_state_name'] if pd.notna(row['full_state_name']) else None,
            row['state_name'],
            row['country'],
            int(row['capacity']),
            row['surface'] if pd.notna(row['surface']) else None,
            int(row['year_opened']) if pd.notna(row['year_opened']) and row['year_opened'] != 0 else None,
            row['roof_type'] if pd.notna(row['roof_type']) else None,
            row['coordinates'] if pd.notna(row['coordinates']) else None,
            row['stadium_type'] if pd.notna(row['stadium_type']) else None,
            int(row['baseball_distance_to_center_field_ft']) if pd.notna(row['baseball_distance_to_center_field_ft']) else None,
            float(row['baseball_distance_to_center_field_m']) if pd.notna(row['baseball_distance_to_center_field_m']) else None,
            row['first_sport_year'] if pd.notna(row['first_sport_year']) else None,
            int(row['soccer_field_width_yd']) if pd.notna(row['soccer_field_width_yd']) else None,
            float(row['soccer_field_width_m']) if pd.notna(row['soccer_field_width_m']) else None,
            int(row['soccer_field_length_yd']) if pd.notna(row['soccer_field_length_yd']) else None,
            float(row['soccer_field_length_m']) if pd.notna(row['soccer_field_length_m']) else None
        )
        stadiums_data.append(stadium_data)
    
    # Insert data
    insert_query = """
    INSERT INTO stadiums (
        stadium_id, full_stadium_name, stadium_name, location_name,
        city_name, full_state_name, state_name, country, capacity,
        surface, year_opened, roof_type, coordinates, stadium_type,
        baseball_distance_to_center_field_ft, baseball_distance_to_center_field_m,
        first_sport_year, soccer_field_width_yd, soccer_field_width_m,
        soccer_field_length_yd, soccer_field_length_m
    ) VALUES %s
    ON CONFLICT (stadium_id) DO UPDATE SET
        full_stadium_name = EXCLUDED.full_stadium_name,
        stadium_name = EXCLUDED.stadium_name,
        location_name = EXCLUDED.location_name,
        city_name = EXCLUDED.city_name,
        full_state_name = EXCLUDED.full_state_name,
        state_name = EXCLUDED.state_name,
        country = EXCLUDED.country,
        capacity = EXCLUDED.capacity,
        surface = EXCLUDED.surface,
        year_opened = EXCLUDED.year_opened,
        roof_type = EXCLUDED.roof_type,
        coordinates = EXCLUDED.coordinates,
        stadium_type = EXCLUDED.stadium_type,
        baseball_distance_to_center_field_ft = EXCLUDED.baseball_distance_to_center_field_ft,
        baseball_distance_to_center_field_m = EXCLUDED.baseball_distance_to_center_field_m,
        first_sport_year = EXCLUDED.first_sport_year,
        soccer_field_width_yd = EXCLUDED.soccer_field_width_yd,
        soccer_field_width_m = EXCLUDED.soccer_field_width_m,
        soccer_field_length_yd = EXCLUDED.soccer_field_length_yd,
        soccer_field_length_m = EXCLUDED.soccer_field_length_m,
        updated_at = CURRENT_TIMESTAMP
    """
    
    execute_values(cursor, insert_query, stadiums_data)
    conn.commit()
    print(f"Successfully imported {len(stadiums_data)} stadiums")

def import_teams(cursor, conn):
    """Import teams data from CSV"""
    print("Importing teams...")
    
    # Read CSV
    df = pd.read_csv('leagues-and-teams.csv')
    
    # Clean and prepare data
    df = df.fillna('')  # Replace NaN with empty strings
    
    # Handle stadium_id - convert NaN to None for teams without stadiums
    df['stadium_id'] = pd.to_numeric(df['stadium_id'], errors='coerce')
    
    # Prepare data for insertion
    teams_data = []
    for _, row in df.iterrows():
        team_data = (
            int(row['team_id']),
            row['full_team_name'],
            row['team_name'],
            row['real_team_name'],
            int(row['league_id']),
            row['league_name'],
            int(row['division_id']) if pd.notna(row['division_id']) else None,
            row['division_name'] if pd.notna(row['division_name']) else None,
            row['division_full_name'] if pd.notna(row['division_full_name']) else None,
            int(row['conference_id']) if pd.notna(row['conference_id']) else None,
            row['conference_name'] if pd.notna(row['conference_name']) else None,
            row['conference_full_name'] if pd.notna(row['conference_full_name']) else None,
            row['league'],
            int(row['team_league_id']),
            row['city_name'],
            row['state_name'],
            row['country'] if pd.notna(row['country']) else 'us',
            int(row['stadium_id']) if pd.notna(row['stadium_id']) else None,
            row['orig_logo_name'] if pd.notna(row['orig_logo_name']) else None,
            row['curl_cmd'] if pd.notna(row['curl_cmd']) else None
        )
        teams_data.append(team_data)
    
    # Insert data
    insert_query = """
    INSERT INTO teams (
        team_id, full_team_name, team_name, real_team_name,
        league_id, league_name, division_id, division_name, division_full_name,
        conference_id, conference_name, conference_full_name, league,
        team_league_id, city_name, state_name, country, stadium_id,
        orig_logo_name, curl_cmd
    ) VALUES %s
    ON CONFLICT (team_id) DO UPDATE SET
        full_team_name = EXCLUDED.full_team_name,
        team_name = EXCLUDED.team_name,
        real_team_name = EXCLUDED.real_team_name,
        league_id = EXCLUDED.league_id,
        league_name = EXCLUDED.league_name,
        division_id = EXCLUDED.division_id,
        division_name = EXCLUDED.division_name,
        division_full_name = EXCLUDED.division_full_name,
        conference_id = EXCLUDED.conference_id,
        conference_name = EXCLUDED.conference_name,
        conference_full_name = EXCLUDED.conference_full_name,
        league = EXCLUDED.league,
        team_league_id = EXCLUDED.team_league_id,
        city_name = EXCLUDED.city_name,
        state_name = EXCLUDED.state_name,
        country = EXCLUDED.country,
        stadium_id = EXCLUDED.stadium_id,
        orig_logo_name = EXCLUDED.orig_logo_name,
        curl_cmd = EXCLUDED.curl_cmd,
        updated_at = CURRENT_TIMESTAMP
    """
    
    execute_values(cursor, insert_query, teams_data)
    conn.commit()
    print(f"Successfully imported {len(teams_data)} teams")

def verify_import(cursor):
    """Verify the import was successful"""
    print("\nVerifying import...")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM stadiums")
    stadium_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM teams")
    team_count = cursor.fetchone()[0]
    
    print(f"Stadiums imported: {stadium_count}")
    print(f"Teams imported: {team_count}")
    
    # Check relationships
    cursor.execute("""
        SELECT COUNT(*) FROM teams t 
        JOIN stadiums s ON t.stadium_id = s.stadium_id
    """)
    linked_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM teams WHERE stadium_id IS NULL")
    unlinked_count = cursor.fetchone()[0]
    
    print(f"Teams linked to stadiums: {linked_count}")
    print(f"Teams without stadiums: {unlinked_count}")
    
    # Show sample data
    print("\nSample teams with stadiums:")
    cursor.execute("""
        SELECT t.real_team_name, s.full_stadium_name, s.city_name, s.state_name
        FROM teams t 
        JOIN stadiums s ON t.stadium_id = s.stadium_id
        LIMIT 5
    """)
    
    for row in cursor.fetchall():
        print(f"  {row[0]} -> {row[1]} ({row[2]}, {row[3]})")

def main():
    """Main import function"""
    print("Starting sportspuff-v6 data import...")
    
    # Check if CSV files exist
    if not os.path.exists('final_stadiums.csv') or not os.path.exists('leagues-and-teams.csv'):
        print("Error: CSV files not found. Please run analyze_excel.py first.")
        sys.exit(1)
    
    # Connect to database
    conn = connect_to_db()
    if not conn:
        print("Failed to connect to database. Please check your connection settings.")
        sys.exit(1)
    
    try:
        cursor = conn.cursor()
        
        # Import data
        import_stadiums(cursor, conn)
        import_teams(cursor, conn)
        
        # Verify import
        verify_import(cursor)
        
        print("\nData import completed successfully!")
        
    except Exception as e:
        print(f"Error during import: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
