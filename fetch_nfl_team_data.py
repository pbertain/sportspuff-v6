#!/usr/bin/env python3
"""
Fetch NFL team data from API and update database with:
- external_team_id (from teamID)
- Wins-Losses-Ties record
- Match teams using teamCity + teamName with real_team_name
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import os
from dotenv import load_dotenv
import logging
from typing import Dict, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'sportspuff_v6'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def fetch_nfl_teams_from_api() -> Optional[list]:
    """
    Fetch NFL team data from API
    Returns list of team dictionaries with teamID, teamCity, teamName, wins, loss, tie, etc.
    """
    # TODO: Replace with actual API endpoint
    # This is a placeholder - you'll need to provide the actual API URL
    api_url = os.getenv('NFL_API_URL', 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams')
    
    try:
        logger.info(f"Fetching NFL teams from: {api_url}")
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse ESPN API response format
        teams = []
        if 'sports' in data:
            for sport in data['sports']:
                if 'leagues' in sport:
                    for league in sport['leagues']:
                        if 'teams' in league:
                            for team_data in league['teams']:
                                team = team_data.get('team', {})
                                record = team.get('record', {})
                                
                                teams.append({
                                    'teamID': str(team.get('id', '')),
                                    'teamAbv': team.get('abbreviation', ''),
                                    'teamCity': team.get('location', ''),
                                    'teamName': team.get('name', ''),
                                    'wins': str(record.get('items', [{}])[0].get('stats', [{}])[0].get('value', '0') if record.get('items') else '0'),
                                    'loss': str(record.get('items', [{}])[0].get('stats', [{}])[1].get('value', '0') if record.get('items') and len(record.get('items', [{}])[0].get('stats', [])) > 1 else '0'),
                                    'tie': str(record.get('items', [{}])[0].get('stats', [{}])[2].get('value', '0') if record.get('items') and len(record.get('items', [{}])[0].get('stats', [])) > 2 else '0'),
                                    'conference': team.get('conference', ''),
                                    'conferenceAbv': team.get('conference', ''),
                                    'division': team.get('division', ''),
                                    'nflComLogo1': team.get('logos', [{}])[0].get('href', '') if team.get('logos') else '',
                                    'espnLogo1': team.get('logos', [{}])[0].get('href', '') if team.get('logos') else ''
                                })
        
        # Alternative: If API returns flat list format
        if not teams and isinstance(data, list):
            teams = data
        
        logger.info(f"Fetched {len(teams)} NFL teams from API")
        return teams
        
    except Exception as e:
        logger.error(f"Error fetching NFL teams from API: {e}")
        # For testing, return sample data matching your format
        logger.warning("Using sample data for testing")
        return [{
            'teamID': '27',
            'teamAbv': 'PHI',
            'teamCity': 'Philadelphia',
            'teamName': 'Eagles',
            'wins': '6',
            'loss': '2',
            'tie': '0',
            'conference': 'National Football Conference',
            'conferenceAbv': 'NFC',
            'division': 'East',
            'nflComLogo1': 'https://res.cloudinary.com/nflleague/image/private/f_auto/league/puhrqgj71gobgdkdo6uq',
            'espnLogo1': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nfl/500/phi.png'
        }]

def normalize_team_name(city: str, name: str) -> str:
    """Normalize team name for matching: 'City Name'"""
    city = city.strip() if city else ''
    name = name.strip() if name else ''
    return f"{city} {name}".strip()

def match_team(api_team: Dict, db_teams: list) -> Optional[Dict]:
    """
    Match API team data with database team using real_team_name
    Returns matched database team record or None
    """
    api_full_name = normalize_team_name(api_team.get('teamCity', ''), api_team.get('teamName', ''))
    
    # Try exact match first
    for db_team in db_teams:
        db_name = db_team.get('real_team_name', '').strip()
        if db_name.lower() == api_full_name.lower():
            return db_team
    
    # Try partial match (handle variations like "New York" vs "NY")
    api_parts = api_full_name.lower().split()
    for db_team in db_teams:
        db_name = db_team.get('real_team_name', '').strip().lower()
        db_parts = db_name.split()
        
        # Match if last word matches and city matches (allowing abbreviations)
        if len(api_parts) >= 2 and len(db_parts) >= 2:
            if api_parts[-1] == db_parts[-1]:  # Team name matches
                # Check if cities match (allowing for "New York" vs "NY")
                api_city = ' '.join(api_parts[:-1])
                db_city = ' '.join(db_parts[:-1])
                
                # Handle common abbreviations
                city_map = {
                    'ny': 'new york',
                    'la': 'los angeles',
                    'sf': 'san francisco',
                    'kc': 'kansas city'
                }
                
                api_city_normalized = city_map.get(api_city, api_city)
                db_city_normalized = city_map.get(db_city, db_city)
                
                if api_city_normalized == db_city_normalized or api_city in db_city or db_city in api_city:
                    return db_team
    
    logger.warning(f"Could not match API team: {api_full_name}")
    return None

def update_team_in_db(conn, team_id: int, external_team_id: str, wins: int, losses: int, ties: int):
    """Update team in database with external_team_id and record"""
    try:
        cursor = conn.cursor()
        
        # First, check if we need to add columns for ties
        # For now, we'll store wins/losses/ties in a JSON field or separate columns
        # Check if team_wins, team_losses, team_ties columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'teams' 
            AND column_name IN ('team_wins', 'team_losses', 'team_ties')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Update external_team_id
        cursor.execute("""
            UPDATE teams 
            SET external_team_id = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE team_id = %s
        """, (external_team_id, team_id))
        
        # If columns exist, update record
        if 'team_wins' in existing_columns:
            cursor.execute("""
                UPDATE teams 
                SET team_wins = %s,
                    team_losses = %s,
                    team_ties = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE team_id = %s
            """, (wins, losses, ties, team_id))
        
        conn.commit()
        cursor.close()
        logger.info(f"Updated team_id {team_id}: external_team_id={external_team_id}, record={wins}-{losses}-{ties}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating team {team_id}: {e}")
        conn.rollback()
        return False

def main():
    """Main function to fetch and update NFL team data"""
    logger.info("Starting NFL team data fetch and update...")
    
    # Get database connection
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return False
    
    try:
        # Fetch NFL teams from API
        api_teams = fetch_nfl_teams_from_api()
        if not api_teams:
            logger.error("No teams fetched from API")
            return False
        
        # Get all NFL teams from database
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT team_id, real_team_name, full_team_name, external_team_id
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE LOWER(l.league_name_proper) = 'nfl'
        """)
        db_teams = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(db_teams)} NFL teams in database")
        
        # Match and update teams
        updated_count = 0
        matched_count = 0
        
        for api_team in api_teams:
            matched_team = match_team(api_team, db_teams)
            if matched_team:
                matched_count += 1
                team_id = matched_team['team_id']
                external_team_id = api_team.get('teamID', '')
                wins = int(api_team.get('wins', 0) or 0)
                losses = int(api_team.get('loss', 0) or 0)
                ties = int(api_team.get('tie', 0) or 0)
                
                if update_team_in_db(conn, team_id, external_team_id, wins, losses, ties):
                    updated_count += 1
                else:
                    logger.warning(f"Failed to update team_id {team_id}")
            else:
                logger.warning(f"Could not match: {api_team.get('teamCity', '')} {api_team.get('teamName', '')}")
        
        logger.info(f"Matched {matched_count}/{len(api_teams)} teams, updated {updated_count} teams")
        
        # Show summary
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT COUNT(*) as total,
                   COUNT(external_team_id) as with_external_id
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE LOWER(l.league_name_proper) = 'nfl'
        """)
        summary = cursor.fetchone()
        cursor.close()
        
        logger.info(f"NFL teams summary: {summary['total']} total, {summary['with_external_id']} with external_team_id")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        conn.close()
        return False

if __name__ == '__main__':
    main()

