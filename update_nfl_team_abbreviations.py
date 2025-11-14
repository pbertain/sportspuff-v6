#!/usr/bin/env python3
"""
Update NFL team abbreviations from Tank01 API
Only updates abbreviations if provided by the API - never generates/makes up abbreviations
Matches teams by teamCity + teamName to real_team_name or full_team_name
"""

import os
import sys
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection from environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '5432'),
            database=os.getenv('DB_NAME', 'sportspuff_v6'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', '')
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def fetch_nfl_teams_from_api():
    """Fetch NFL teams from Tank01 API"""
    url = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLTeams"
    querystring = {
        "sortBy": "standings",
        "rosters": "false",
        "schedules": "false",
        "topPerformers": "true",
        "teamStats": "true",
        "teamStatsSeason": "2024"
    }
    headers = {
        "x-rapidapi-key": os.getenv('RAPIDAPI_KEY', ''),
        "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        data = response.json()
        
        if data.get('statusCode') == 200 and 'body' in data:
            return data['body']
        else:
            print(f"Unexpected API response: {data}")
            return []
    except Exception as e:
        print(f"Error fetching NFL teams from API: {e}")
        return []

def normalize_team_name(city, team_name):
    """Normalize team name to match database format"""
    # Combine city and team name
    full_name = f"{city} {team_name}".strip()
    return full_name

def match_team(api_team, db_teams):
    """Match API team to database team"""
    api_full_name = normalize_team_name(api_team['teamCity'], api_team['teamName'])
    api_abbrev = api_team.get('teamAbv', '').strip()
    
    if not api_abbrev:
        return None, None
    
    # Try to match by real_team_name or full_team_name
    for db_team in db_teams:
        db_real_name = (db_team.get('real_team_name') or '').strip()
        db_full_name = (db_team.get('full_team_name') or '').strip()
        
        # Exact match
        if (db_real_name.lower() == api_full_name.lower() or 
            db_full_name.lower() == api_full_name.lower()):
            return db_team['team_id'], api_abbrev
        
        # Try matching just the team name part (e.g., "Patriots")
        if api_team['teamName'].lower() in db_real_name.lower() or api_team['teamName'].lower() in db_full_name.lower():
            # Also check if city matches
            if api_team['teamCity'].lower() in db_real_name.lower() or api_team['teamCity'].lower() in db_full_name.lower():
                return db_team['team_id'], api_abbrev
    
    return None, None

def update_team_abbreviations(conn, api_teams):
    """Update team abbreviations in database"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all NFL teams from database
    cursor.execute("""
        SELECT team_id, real_team_name, full_team_name, team_abbreviation
        FROM teams
        WHERE league = 'NFL' OR league_name = 'NFL'
        ORDER BY team_id
    """)
    db_teams = cursor.fetchall()
    
    print(f"Found {len(db_teams)} NFL teams in database")
    print(f"Found {len(api_teams)} teams from API")
    
    updated_count = 0
    not_found = []
    
    for api_team in api_teams:
        team_id, abbrev = match_team(api_team, db_teams)
        
        if team_id and abbrev:
            # Check if abbreviation is different
            cursor.execute("""
                SELECT team_abbreviation FROM teams WHERE team_id = %s
            """, (team_id,))
            current_abbrev = cursor.fetchone()
            current_abbrev = current_abbrev['team_abbreviation'] if current_abbrev else None
            
            if current_abbrev != abbrev:
                cursor.execute("""
                    UPDATE teams 
                    SET team_abbreviation = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE team_id = %s
                """, (abbrev, team_id))
                team_name = next((t['real_team_name'] for t in db_teams if t['team_id'] == team_id), 'Unknown')
                print(f"Updated {team_name} (ID: {team_id}): {current_abbrev} -> {abbrev}")
                updated_count += 1
            else:
                team_name = next((t['real_team_name'] for t in db_teams if t['team_id'] == team_id), 'Unknown')
                print(f"No change for {team_name} (ID: {team_id}): {abbrev}")
        else:
            api_full = normalize_team_name(api_team['teamCity'], api_team['teamName'])
            not_found.append(f"{api_full} ({api_team.get('teamAbv', 'N/A')})")
    
    conn.commit()
    cursor.close()
    
    print(f"\nSummary:")
    print(f"  Updated: {updated_count} teams")
    if not_found:
        print(f"  Not found in database: {len(not_found)} teams")
        for team in not_found:
            print(f"    - {team}")
    
    return updated_count

def main():
    """Main function"""
    print("Fetching NFL teams from Tank01 API...")
    api_teams = fetch_nfl_teams_from_api()
    
    if not api_teams:
        print("No teams found from API. Exiting.")
        sys.exit(1)
    
    print(f"Connecting to database...")
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    try:
        print("Updating team abbreviations...")
        updated = update_team_abbreviations(conn, api_teams)
        print(f"\nSuccessfully updated {updated} team abbreviations")
    except Exception as e:
        print(f"Error updating abbreviations: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    main()

