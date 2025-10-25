#!/usr/bin/env python3
"""
Fix team division and conference names by mapping IDs to names
This script reads the CSV files and updates the database with correct mappings
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

def fix_team_mappings():
    """Fix team division and conference mappings"""
    print("Fixing team division and conference mappings...")
    
    # Read CSV files
    try:
        teams_df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        divisions_df = pd.read_csv('info-divisions.csv', encoding='utf-8-sig')
        conferences_df = pd.read_csv('info-conferences.csv', encoding='utf-8-sig')
        
        print(f"Loaded {len(teams_df)} teams, {len(divisions_df)} divisions, {len(conferences_df)} conferences")
        
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return False
    
    # Create mapping dictionaries
    division_map = {}
    for _, row in divisions_df.iterrows():
        key = (int(row['league_id']), int(row['division_id']))
        division_map[key] = row['division_name']
    
    conference_map = {}
    for _, row in conferences_df.iterrows():
        key = (int(row['league_id']), int(row['conference_id']))
        conference_map[key] = row['conference_name']
    
    print(f"Created division map with {len(division_map)} entries")
    print(f"Created conference map with {len(conference_map)} entries")
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Update teams with correct division and conference names
        updated_count = 0
        for _, team in teams_df.iterrows():
            team_id = int(team['team_id'])
            league_id = int(team['league_id'])
            division_id = int(team['division_id']) if pd.notna(team['division_id']) else None
            conference_id = int(team['conference_id']) if pd.notna(team['conference_id']) else None
            
            # Get division name
            division_name = None
            if division_id:
                division_name = division_map.get((league_id, division_id))
            
            # Get conference name
            conference_name = None
            if conference_id:
                conference_name = conference_map.get((league_id, conference_id))
            
            # Update the team
            cursor.execute("""
                UPDATE teams 
                SET division_name = %s, conference_name = %s
                WHERE team_id = %s
            """, (division_name, conference_name, team_id))
            
            if cursor.rowcount > 0:
                updated_count += 1
        
        conn.commit()
        cursor.close()
        
        print(f"Successfully updated {updated_count} teams")
        
        # Verify the updates
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT l.league_name_proper, d.division_name, COUNT(t.team_id) as team_count
            FROM leagues l
            LEFT JOIN divisions d ON l.league_id = d.league_id
            LEFT JOIN teams t ON l.league_id = t.league_id AND d.division_name = t.division_name
            GROUP BY l.league_name_proper, d.division_name
            ORDER BY l.league_name_proper, d.division_name
        """)
        
        results = cursor.fetchall()
        print("\nUpdated team counts by division:")
        for row in results:
            if row['team_count'] > 0:
                print(f"  {row['league_name_proper']} - {row['division_name']}: {row['team_count']} teams")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error updating teams: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Starting team mapping fix...")
    
    if fix_team_mappings():
        print("\nTeam mapping fix completed successfully!")
    else:
        print("\nTeam mapping fix failed!")

if __name__ == "__main__":
    main()
