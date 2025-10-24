#!/usr/bin/env python3
"""
Update info-teams.csv with team colors from the database
This script reads the current CSV, gets colors from the database, and writes back an updated CSV
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

def update_csv_with_colors():
    """Update info-teams.csv with team colors from database"""
    print("Updating info-teams.csv with team colors...")
    
    # Read the current CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='latin-1')
        print(f"Loaded CSV with {len(df)} teams")
        print(f"Current columns: {list(df.columns)}")
        
        # Check if color columns already exist
        color_columns = ['team_color_1', 'team_color_2', 'team_color_3']
        for col in color_columns:
            if col not in df.columns:
                df[col] = None
                print(f"Added column: {col}")
        
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return False
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get team colors from database
        cursor.execute("""
            SELECT team_id, real_team_name, team_color_1, team_color_2, team_color_3
            FROM teams
            ORDER BY team_id
        """)
        team_colors = cursor.fetchall()
        
        # Create a mapping of team_id to colors
        color_map = {}
        for team in team_colors:
            color_map[team['team_id']] = {
                'team_color_1': team['team_color_1'],
                'team_color_2': team['team_color_2'],
                'team_color_3': team['team_color_3']
            }
        
        print(f"Retrieved colors for {len(color_map)} teams from database")
        
        # Update the DataFrame with colors
        updated_count = 0
        for index, row in df.iterrows():
            team_id = row['team_id']
            if team_id in color_map:
                colors = color_map[team_id]
                df.at[index, 'team_color_1'] = colors['team_color_1']
                df.at[index, 'team_color_2'] = colors['team_color_2']
                df.at[index, 'team_color_3'] = colors['team_color_3']
                updated_count += 1
        
        print(f"Updated {updated_count} teams with colors")
        
        # Write the updated CSV back to file
        df.to_csv('info-teams.csv', index=False, encoding='utf-8-sig')
        print("Successfully updated info-teams.csv with team colors")
        
        # Show some examples
        print("\nSample teams with colors:")
        sample_teams = df[df['team_color_1'].notna()].head(5)
        for _, team in sample_teams.iterrows():
            print(f"  {team['real_team_name']}: {team['team_color_1']}, {team['team_color_2']}, {team['team_color_3']}")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error updating CSV: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Starting CSV color update...")
    
    if update_csv_with_colors():
        print("\nCSV update completed successfully!")
        print("You can now manually add colors for MLS, WNBA, and IPL teams in the CSV file.")
        print("Then run the import script to update the database.")
    else:
        print("\nCSV update failed!")

if __name__ == "__main__":
    main()
