#!/usr/bin/env python3
"""
Sportspuff v6 Modular Data Import Script
Imports data from separate CSV files with proper foreign key relationships
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
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

def safe_numeric(value):
    """Safely convert value to integer, handling NaN and empty strings"""
    if pd.isna(value) or value == '' or value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def safe_decimal(value):
    """Safely convert value to decimal, handling NaN and empty strings"""
    if pd.isna(value) or value == '' or value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def import_leagues(conn):
    """Import leagues from info-leagues.csv"""
    print("Importing leagues...")
    
    try:
        df = pd.read_csv('info-leagues.csv', encoding='utf-8-sig')  # Handle BOM
        print(f"CSV columns: {list(df.columns)}")
        
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO leagues (
                    league_id, league_name_full, league_name, league_name_proper,
                    city_name, state_name, country, logo_filename, team_count,
                    conference_count, division_count, current_champion_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (league_id) DO UPDATE SET
                    league_name_full = EXCLUDED.league_name_full,
                    league_name = EXCLUDED.league_name,
                    league_name_proper = EXCLUDED.league_name_proper,
                    city_name = EXCLUDED.city_name,
                    state_name = EXCLUDED.state_name,
                    country = EXCLUDED.country,
                    logo_filename = EXCLUDED.logo_filename,
                    team_count = EXCLUDED.team_count,
                    conference_count = EXCLUDED.conference_count,
                    division_count = EXCLUDED.division_count,
                    current_champion_id = EXCLUDED.current_champion_id
            """, (
                int(row['league_id']),
                row['league_name_full'],
                row['league_name'],
                row['league_name_proper'],
                row['city_name'],
                row['state_name'],
                row['country'],
                row['logo_filename'],
                safe_numeric(row.get('team_count')),
                safe_numeric(row.get('conference_count')),
                safe_numeric(row.get('division_count')),
                safe_numeric(row.get('current_champion_id'))
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} leagues")
        return True
        
    except Exception as e:
        print(f"Error during leagues import: {e}")
        conn.rollback()
        return False

def import_stadiums(conn):
    """Import stadiums from info-stadiums.csv"""
    print("Importing stadiums...")
    
    try:
        df = pd.read_csv('info-stadiums.csv', encoding='utf-8-sig')  # Handle BOM
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO stadiums (
                    stadium_id, image, full_stadium_name, stadium_name, location_name,
                    city_name, full_state_name, state_name, country, capacity, surface,
                    year_opened, roof_type, coordinates, stadium_type,
                    baseball_distance_to_center_field_ft, baseball_distance_to_center_field_m,
                    first_sport_year, soccer_field_width_yd, soccer_field_width_m,
                    soccer_field_length_yd, soccer_field_length_m
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    soccer_field_length_m = EXCLUDED.soccer_field_length_m
            """, (
                int(row['stadium_id']),
                row.get('image'),
                row['full_stadium_name'],
                row.get('stadium_name'),
                row.get('location_name'),
                row.get('city_name'),
                row.get('full_state_name'),
                row.get('state_name'),
                row.get('country'),
                safe_numeric(row.get('capacity')),
                row.get('surface'),
                safe_numeric(row.get('year_opened')),
                row.get('roof_type'),
                row.get('coordinates'),
                row.get('stadium_type'),
                safe_numeric(row.get('baseball_distance_to_center_field_ft')),
                safe_decimal(row.get('baseball_distance_to_center_field_m')),
                safe_numeric(row.get('first_sport_year')),
                safe_numeric(row.get('soccer_field_width_yd')),
                safe_decimal(row.get('soccer_field_width_m')),
                safe_numeric(row.get('soccer_field_length_yd')),
                safe_decimal(row.get('soccer_field_length_m'))
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} stadiums")
        return True
        
    except Exception as e:
        print(f"Error during stadiums import: {e}")
        conn.rollback()
        return False

def import_conferences(conn):
    """Import conferences from info-conferences.csv"""
    print("Importing conferences...")
    
    try:
        df = pd.read_csv('info-conferences.csv', encoding='utf-8-sig')  # Handle BOM
        # Remove duplicates based on league_id and conference_name
        df = df.drop_duplicates(subset=['league_id', 'conference_name'])
        print(f"Importing {len(df)} unique conferences")
        
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO conferences (conference_id, league_id, conference_name, conference_full_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (league_id, conference_name) DO UPDATE SET
                    conference_id = EXCLUDED.conference_id,
                    conference_full_name = EXCLUDED.conference_full_name
            """, (
                int(row['conference_id']),
                int(row['league_id']),
                row['conference_name'],
                row['conference_full_name']
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} conferences")
        return True
        
    except Exception as e:
        print(f"Error during conferences import: {e}")
        conn.rollback()
        return False

def import_divisions(conn):
    """Import divisions from info-divisions.csv"""
    print("Importing divisions...")
    
    try:
        df = pd.read_csv('info-divisions.csv', encoding='utf-8-sig')  # Handle BOM
        # Remove duplicates based on league_id and division_name
        df = df.drop_duplicates(subset=['league_id', 'division_name'])
        print(f"Importing {len(df)} unique divisions")
        
        cursor = conn.cursor()
        
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO divisions (division_id, league_id, conference_id, division_name, division_full_name)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (league_id, division_name) DO UPDATE SET
                    division_id = EXCLUDED.division_id,
                    conference_id = EXCLUDED.conference_id,
                    division_full_name = EXCLUDED.division_full_name
            """, (
                int(row['division_id']),
                int(row['league_id']),
                safe_numeric(row.get('conference_id')),
                row['division_name'],
                row['division_full_name']
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} divisions")
        return True
        
    except Exception as e:
        print(f"Error during divisions import: {e}")
        conn.rollback()
        return False

def import_teams(conn):
    """Import teams from info-teams.csv"""
    print("Importing teams...")
    
    try:
        df = pd.read_csv('info-teams.csv', encoding='latin-1')  # Use latin-1 for teams
        cursor = conn.cursor()
        
        # Get division and conference mappings
        cursor.execute("SELECT division_id, division_name, league_id FROM divisions")
        division_map = {(row[2], row[0]): row[1] for row in cursor.fetchall()}
        
        cursor.execute("SELECT conference_id, conference_name, league_id FROM conferences")
        conference_map = {(row[2], row[0]): row[1] for row in cursor.fetchall()}
        
        for _, row in df.iterrows():
            # Handle stadium_id - set to NULL if 0 or NaN
            stadium_id = safe_numeric(row.get('stadium_id'))
            if stadium_id == 0:
                stadium_id = None
            
            # Get division and conference names from IDs
            league_id = int(row['league_id'])
            division_id = safe_numeric(row.get('division_id'))
            conference_id = safe_numeric(row.get('conference_id'))
            
            division_name = division_map.get((league_id, division_id)) if division_id else None
            conference_name = conference_map.get((league_id, conference_id)) if conference_id else None
            
            cursor.execute("""
                INSERT INTO teams (
                    team_id, full_team_name, team_name, real_team_name, league_id,
                    division_name, conference_name, team_league_id, city_name, state_name,
                    country, stadium_id, logo_filename, team_color_1, team_color_2, team_color_3
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (team_id) DO UPDATE SET
                    full_team_name = EXCLUDED.full_team_name,
                    team_name = EXCLUDED.team_name,
                    real_team_name = EXCLUDED.real_team_name,
                    league_id = EXCLUDED.league_id,
                    division_name = EXCLUDED.division_name,
                    conference_name = EXCLUDED.conference_name,
                    team_league_id = EXCLUDED.team_league_id,
                    city_name = EXCLUDED.city_name,
                    state_name = EXCLUDED.state_name,
                    country = EXCLUDED.country,
                    stadium_id = EXCLUDED.stadium_id,
                    logo_filename = EXCLUDED.logo_filename,
                    team_color_1 = EXCLUDED.team_color_1,
                    team_color_2 = EXCLUDED.team_color_2,
                    team_color_3 = EXCLUDED.team_color_3
            """, (
                int(row['team_id']),
                row['full_team_name'],
                row['team_name'],
                row['real_team_name'],
                league_id,
                division_name,
                conference_name,
                safe_numeric(row.get('team_league_id')),
                row.get('city_name'),
                row.get('state_name'),
                row.get('country'),
                stadium_id,
                row.get('logo_filename'),
                None,  # team_color_1 - will be updated later
                None,  # team_color_2 - will be updated later
                None   # team_color_3 - will be updated later
            ))
        
        conn.commit()
        cursor.close()
        print(f"Successfully imported {len(df)} teams")
        return True
        
    except Exception as e:
        print(f"Error during teams import: {e}")
        conn.rollback()
        return False

def verify_import(conn):
    """Verify the import by checking counts and relationships"""
    print("\nVerifying import...")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get counts
        cursor.execute("SELECT COUNT(*) as count FROM leagues")
        leagues_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM stadiums")
        stadiums_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM conferences")
        conferences_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM divisions")
        divisions_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        teams_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM teams WHERE stadium_id IS NOT NULL")
        linked_teams_count = cursor.fetchone()['count']
        
        # Get league breakdown
        cursor.execute("""
            SELECT l.league_name_proper, COUNT(t.team_id) as team_count
            FROM leagues l
            LEFT JOIN teams t ON l.league_id = t.league_id
            GROUP BY l.league_id, l.league_name_proper
            ORDER BY l.league_name_proper
        """)
        league_breakdown = cursor.fetchall()
        
        cursor.close()
        
        print(f"Leagues imported: {leagues_count}")
        print(f"Stadiums imported: {stadiums_count}")
        print(f"Conferences imported: {conferences_count}")
        print(f"Divisions imported: {divisions_count}")
        print(f"Teams imported: {teams_count}")
        print(f"Teams linked to stadiums: {linked_teams_count}")
        print(f"Teams without stadiums: {teams_count - linked_teams_count}")
        
        print("\nLeague breakdown:")
        for league in league_breakdown:
            print(f"  {league['league_name_proper']}: {league['team_count']} teams")
        
        return True
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False

def main():
    """Main import function"""
    print("Starting sportspuff-v6 modular data import...")
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        # Import in dependency order
        success = True
        
        # 1. Import leagues first (no dependencies)
        if not import_leagues(conn):
            success = False
        
        # 2. Import stadiums (no dependencies)
        if not import_stadiums(conn):
            success = False
        
        # 3. Import conferences (depends on leagues)
        if not import_conferences(conn):
            success = False
        
        # 4. Import divisions (depends on leagues)
        if not import_divisions(conn):
            success = False
        
        # 5. Import teams last (depends on all others)
        if not import_teams(conn):
            success = False
        
        # 6. Verify import
        if success:
            verify_import(conn)
            print("\nData import completed successfully!")
        else:
            print("\nData import completed with errors!")
        
        return success
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
