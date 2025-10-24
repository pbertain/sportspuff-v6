#!/usr/bin/env python3
"""
Update specific team colors based on detailed feedback
"""

import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
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

def update_specific_team_colors():
    """Update specific team colors based on detailed feedback"""
    print("Updating specific team colors based on feedback...")
    
    # Read CSV file
    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        print(f"Loaded CSV with {len(df)} teams")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Specific team color updates based on feedback
    team_color_updates = {
        # MLS
        "CF Montréal": ["#000000", "#0020A0", "#FFFFFF"],  # Black, Blue, White
        
        # WNBA
        "Indiana Fever": ["#002C5F", "#FDBB30", "#FFFFFF"],  # Navy blue, Gold, White
        "Chicago Sky": ["#418FDE", "#000000", "#FFFFFF"],  # Light blue, Black, White
        "New York Liberty": ["#6C5CE7", "#FDBB30", "#FFFFFF"],  # Purple, Gold, White
        "Washington Mystics": ["#C8102E", "#002C5F", "#FFFFFF"],  # Red, Navy, White
        "Los Angeles Sparks": ["#702F8A", "#FDBB30", "#FFFFFF"],  # Purple background, Yellow text, White
        "Golden State Valkyries": ["#1D428A", "#FFC72C", "#FFFFFF"],  # Warriors blue, Gold, White
        "Dallas Wings": ["#00538C", "#C8102E", "#FFFFFF"],  # Mavericks blue, Red, White
        "Atlanta Dream": ["#C8102E", "#1E3A8A", "#FFFFFF"],  # Red background, Blue text, White
        "Minnesota Lynx": ["#236192", "#00A651", "#FFFFFF"],  # Blue background, Green text, White
        
        # IPL
        "Rajasthan Royals": ["#FF69B4", "#800080", "#FFFFFF"],  # Pink background, Purple, White
        "Punjab Kings": ["#DC143C", "#FFD700", "#FFFFFF"],  # Red background, Yellow text, White
        "Lucknow Super Giants": ["#FF4500", "#0066CC", "#00CC66"],  # Orange/Red, Blue, Green
        "Gujarat Titans": ["#D2B48C", "#0066CC", "#2F4F4F"],  # Tan/Sand background, Blue font, Dark slate
    }
    
    print(f"Updating {len(team_color_updates)} teams with improved colors...")
    
    updated_count = 0
    for team_name, colors in team_color_updates.items():
        mask = df['real_team_name'] == team_name
        if mask.any():
            df.loc[mask, 'team_color_1'] = colors[0]
            df.loc[mask, 'team_color_2'] = colors[1]
            df.loc[mask, 'team_color_3'] = colors[2]
            print(f"Updated {team_name}: {colors[0]}, {colors[1]}, {colors[2]}")
            updated_count += 1
        else:
            print(f"Team '{team_name}' not found in CSV")
    
    # Save updated CSV
    try:
        df.to_csv('info-teams.csv', index=False, encoding='utf-8-sig')
        print(f"\nSuccessfully updated CSV with {updated_count} teams")
        return True
    except Exception as e:
        print(f"Error saving CSV: {e}")
        return False

def update_database_with_colors():
    """Update the database with the new team colors"""
    print("Updating database with new team colors...")
    conn = get_db_connection()
    if not conn:
        return False

    try:
        df = pd.read_csv('info-teams.csv', encoding='utf-8-sig')
        cursor = conn.cursor()
        
        updated_count = 0
        for _, row in df.iterrows():
            team_id = int(row['team_id'])
            team_color_1 = row.get('team_color_1') if pd.notna(row.get('team_color_1')) else None
            team_color_2 = row.get('team_color_2') if pd.notna(row.get('team_color_2')) else None
            team_color_3 = row.get('team_color_3') if pd.notna(row.get('team_color_3')) else None

            cursor.execute("""
                UPDATE teams
                SET team_color_1 = %s, team_color_2 = %s, team_color_3 = %s
                WHERE team_id = %s
            """, (team_color_1, team_color_2, team_color_3, team_id))
            updated_count += cursor.rowcount
        
        conn.commit()
        cursor.close()
        print(f"Successfully updated {updated_count} teams in database")
        return True
    except Exception as e:
        print(f"Error updating database: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Starting specific team color updates...")
    
    if update_specific_team_colors():
        print("Team color updates completed successfully!")
        if update_database_with_colors():
            print("Database updated successfully!")
        else:
            print("Database update failed!")
    else:
        print("Team color updates failed!")

if __name__ == "__main__":
    main()
