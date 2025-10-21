#!/usr/bin/env python3
"""
Sportspuff v6 Data Import Script
Updated to handle all CSV columns including logo_filename
"""

import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        load_dotenv()
        
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

def import_stadiums(conn):
    """Import stadiums from CSV with all columns"""
    print("Importing stadiums...")
    
    try:
        # Read stadiums CSV
        df = pd.read_csv('final_stadiums.csv')
        
        cursor = conn.cursor()
        
        # Clear existing stadiums
        cursor.execute("DELETE FROM stadiums")
        
        # Import stadiums with all columns
        for _, row in df.iterrows():
            # Handle empty/null values and convert numpy types to Python types
            def safe_numeric(value):
                if pd.isna(value) or value == '':
                    return None
                try:
                    result = pd.to_numeric(value, errors='coerce')
                    return int(result) if pd.notna(result) and not pd.isna(result) else None
                except:
                    return None
            
            def safe_decimal(value):
                if pd.isna(value) or value == '':
                    return None
                try:
                    result = pd.to_numeric(value, errors='coerce')
                    return float(result) if pd.notna(result) and not pd.isna(result) else None
                except:
                    return None
            
            capacity = safe_numeric(row.get('capacity', ''))
            year_opened = safe_numeric(row.get('year_opened', ''))
            baseball_distance_ft = safe_numeric(row.get('baseball_distance_to_center_field_ft', ''))
            baseball_distance_m = safe_decimal(row.get('baseball_distance_to_center_field_m', ''))
            first_sport_year = safe_numeric(row.get('first_sport_year', ''))
            soccer_width_yd = safe_numeric(row.get('soccer_field_width_yd', ''))
            soccer_width_m = safe_decimal(row.get('soccer_field_width_m', ''))
            soccer_length_yd = safe_numeric(row.get('soccer_field_length_yd', ''))
            soccer_length_m = safe_decimal(row.get('soccer_field_length_m', ''))
            
            insert_query = """
                INSERT INTO stadiums (
                    stadium_id, image, full_stadium_name, stadium_name, location_name,
                    city_name, full_state_name, state_name, country, capacity, surface,
                    year_opened, roof_type, coordinates, stadium_type,
                    baseball_distance_to_center_field_ft, baseball_distance_to_center_field_m,
                    first_sport_year, soccer_field_width_yd, soccer_field_width_m,
                    soccer_field_length_yd, soccer_field_length_m
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (stadium_id) DO UPDATE SET
                    image = EXCLUDED.image,
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
            
            cursor.execute(insert_query, (
                row.get('stadium_id'),
                row.get('image'),
                row.get('full_stadium_name'),
                row.get('stadium_name'),
                row.get('location_name'),
                row.get('city_name'),
                row.get('full_state_name'),
                row.get('state_name'),
                row.get('country'),
                capacity,
                row.get('surface'),
                year_opened,
                row.get('roof_type'),
                row.get('coordinates'),
                row.get('stadium_type'),
                baseball_distance_ft,
                baseball_distance_m,
                first_sport_year,
                soccer_width_yd,
                soccer_width_m,
                soccer_length_yd,
                soccer_length_m
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} stadiums")
        return True
        
    except Exception as e:
        print(f"Error during stadium import: {e}")
        conn.rollback()
        return False

def import_divisions_and_conferences(conn):
    """Import divisions and conferences from teams data"""
    print("Importing divisions and conferences...")
    
    try:
        df = pd.read_csv('leagues-and-teams.csv', encoding='latin-1')
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute("DELETE FROM teams")
        cursor.execute("DELETE FROM divisions")
        cursor.execute("DELETE FROM conferences")
        conn.commit()
        
        # Get unique divisions - include all divisions including Unaffiliated
        divisions = df[['league_id', 'division_id', 'division_name', 'division_full_name']].drop_duplicates()
        divisions = divisions.dropna(subset=['division_id', 'division_name'])
        
        for _, row in divisions.iterrows():
            cursor.execute("""
                INSERT INTO divisions (division_id, league_id, division_name, division_full_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (league_id, division_full_name) DO UPDATE SET
                    division_id = EXCLUDED.division_id,
                    division_name = EXCLUDED.division_name
            """, (int(row['division_id']), int(row['league_id']), row['division_name'], row['division_full_name']))
        
        # Get unique conferences - include all conferences including Unaffiliated
        conferences = df[['league_id', 'conference_id', 'conference_name', 'conference_full_name']].drop_duplicates()
        conferences = conferences.dropna(subset=['conference_id', 'conference_name'])
        
        for _, row in conferences.iterrows():
            cursor.execute("""
                INSERT INTO conferences (conference_id, league_id, conference_name, conference_full_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (conference_id) DO UPDATE SET
                    league_id = EXCLUDED.league_id,
                    conference_name = EXCLUDED.conference_name,
                    conference_full_name = EXCLUDED.conference_full_name
            """, (int(row['conference_id']), int(row['league_id']), row['conference_name'], row['conference_full_name']))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(divisions)} divisions and {len(conferences)} conferences")
        return True
        
    except Exception as e:
        print(f"Error during divisions/conferences import: {e}")
        conn.rollback()
        return False

def import_teams(conn):
    """Import teams from CSV with all columns including logo_filename"""
    print("Importing teams...")
    
    try:
        # Read teams CSV
        df = pd.read_csv('leagues-and-teams.csv', encoding='latin-1')
        
        cursor = conn.cursor()
        
        # Import teams with all columns
        for _, row in df.iterrows():
            # Handle stadium_id - set to NULL if 0 or NaN
            stadium_id = row.get('stadium_id')
            if pd.isna(stadium_id) or stadium_id == 0:
                stadium_id = None
            else:
                try:
                    stadium_id = int(stadium_id)
                except:
                    stadium_id = None
            
            insert_query = """
                INSERT INTO teams (
                    team_id, full_team_name, team_name, real_team_name, league_id, league_name,
                    division_id, division_name, division_full_name, conference_id, conference_name,
                    conference_full_name, league, team_league_id, city_name, state_name, country,
                    stadium_id, logo_filename
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
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
                    logo_filename = EXCLUDED.logo_filename,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            cursor.execute(insert_query, (
                row.get('team_id'),
                row.get('full_team_name'),
                row.get('team_name'),
                row.get('real_team_name'),
                row.get('league_id'),
                row.get('league_name'),
                row.get('division_id'),
                row.get('division_name'),
                row.get('division_full_name'),
                row.get('conference_id'),
                row.get('conference_name'),
                row.get('conference_full_name'),
                row.get('league'),
                row.get('team_league_id'),
                row.get('city_name'),
                row.get('state_name'),
                row.get('country'),
                stadium_id,
                row.get('logo_filename')
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} teams")
        return True
        
    except Exception as e:
        print(f"Error during team import: {e}")
        conn.rollback()
        return False

def verify_import(conn):
    """Verify the import results"""
    print("\nVerifying import...")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Count stadiums
        cursor.execute("SELECT COUNT(*) as count FROM stadiums")
        stadium_count = cursor.fetchone()['count']
        
        # Count teams
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        team_count = cursor.fetchone()['count']
        
        # Count teams with stadiums
        cursor.execute("SELECT COUNT(*) as count FROM teams WHERE stadium_id IS NOT NULL")
        linked_count = cursor.fetchone()['count']
        
        # Count teams without stadiums
        cursor.execute("SELECT COUNT(*) as count FROM teams WHERE stadium_id IS NULL")
        unlinked_count = cursor.fetchone()['count']
        
        # Show league breakdown
        cursor.execute("SELECT league, COUNT(*) as team_count FROM teams GROUP BY league ORDER BY league")
        league_stats = cursor.fetchall()
        
        print(f"Stadiums imported: {stadium_count}")
        print(f"Teams imported: {team_count}")
        print(f"Teams linked to stadiums: {linked_count}")
        print(f"Teams without stadiums: {unlinked_count}")
        
        print(f"\nLeague breakdown:")
        for stat in league_stats:
            print(f"  {stat['league']}: {stat['team_count']} teams")
        
        # Show sample teams with stadiums
        cursor.execute("""
            SELECT t.real_team_name, s.full_stadium_name, s.city_name, s.state_name, t.logo_filename
            FROM teams t
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            WHERE t.stadium_id IS NOT NULL
            LIMIT 5
        """)
        sample_teams = cursor.fetchall()
        
        print(f"\nSample teams with stadiums:")
        for team in sample_teams:
            print(f"  {team['real_team_name']} -> {team['full_stadium_name']} ({team['city_name']}, {team['state_name']}) - Logo: {team['logo_filename']}")
        
        cursor.close()
        
    except Exception as e:
        print(f"Error during verification: {e}")

def main():
    """Main import function"""
    print("Starting sportspuff-v6 data import...")
    
    # Check if CSV files exist
    if not os.path.exists('final_stadiums.csv'):
        print("Error: final_stadiums.csv not found")
        return False
    
    if not os.path.exists('leagues-and-teams.csv'):
        print("Error: leagues-and-teams.csv not found")
        return False
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Please check your connection settings.")
        return False
    
    try:
        # Import stadiums
        if not import_stadiums(conn):
            return False
        
        # Import divisions and conferences first
        if not import_divisions_and_conferences(conn):
            return False
        
        # Import teams
        if not import_teams(conn):
            return False
        
        # Verify import
        verify_import(conn)
        
        print("\nData import completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during import: {e}")
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
