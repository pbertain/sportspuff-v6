#!/usr/bin/env python3
"""
Update team colors in database from CSV file
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

def update_team_colors():
    """Update team colors in database from CSV"""
    print("Updating team colors in database...")
    
    # Read CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        updated_count = 0
        for _, row in df.iterrows():
            team_id = int(row['team_id'])
            color_1 = row['team_color_1'] if pd.notna(row['team_color_1']) else None
            color_2 = row['team_color_2'] if pd.notna(row['team_color_2']) else None
            color_3 = row['team_color_3'] if pd.notna(row['team_color_3']) else None
            
            # Update team colors
            cursor.execute("""
                UPDATE teams 
                SET team_color_1 = %s, team_color_2 = %s, team_color_3 = %s
                WHERE team_id = %s
            """, (color_1, color_2, color_3, team_id))
            
            if cursor.rowcount > 0:
                updated_count += 1
        
        conn.commit()
        cursor.close()
        
        print(f"Successfully updated {updated_count} teams with colors")
        
        # Show summary
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT l.league_name_proper, COUNT(t.team_id) as total_teams,
                   COUNT(CASE WHEN t.team_color_1 IS NOT NULL THEN 1 END) as teams_with_colors
            FROM leagues l
            LEFT JOIN teams t ON l.league_id = t.league_id
            GROUP BY l.league_name_proper
            ORDER BY l.league_name_proper
        """)
        
        results = cursor.fetchall()
        print("\nTeam color summary:")
        for row in results:
            print(f"  {row['league_name_proper']}: {row['teams_with_colors']}/{row['total_teams']} teams with colors")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Starting team color database update...")
    
    if update_team_colors():
        print("\nTeam color database update completed successfully!")
    else:
        print("\nTeam color database update failed!")

if __name__ == "__main__":
    main()
