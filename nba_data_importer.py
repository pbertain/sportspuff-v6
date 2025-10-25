#!/usr/bin/env python3
"""
NBA Data Importer

This script imports full NBA season schedules into the PostgreSQL database.
It fetches data from the NBA API and maps it to the existing teams table.

Usage:
    python nba_data_importer.py --season 2024-25
    python nba_data_importer.py --current-season
"""

import sys
import os
import argparse
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class NBADataImporter:
    """NBA data importer for full season schedules."""
    
    def __init__(self):
        """Initialize the NBA data importer."""
        self.base_url = "https://stats.nba.com/stats"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nba.com/',
            'Origin': 'https://www.nba.com'
        }
    
    def get_db_connection(self):
        """Get PostgreSQL database connection."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'sportspuff_v6'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD')
            )
            return conn
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            return None
    
    def get_team_mapping(self) -> Dict[int, int]:
        """
        Get mapping from NBA team IDs to Sportspuff team IDs.
        
        Returns:
            Dictionary mapping NBA team_id to Sportspuff team_id
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT team_id, real_team_name 
                FROM teams 
                WHERE league_id = 3
                ORDER BY real_team_name
            """)
            
            teams = cursor.fetchall()
            mapping = {}
            
            # NBA team ID mapping (from NBA API to our team names)
            nba_team_mapping = {
                1610612737: 'Atlanta Hawks',      # ATL
                1610612738: 'Boston Celtics',      # BOS
                1610612751: 'Brooklyn Nets',       # BKN
                1610612766: 'Charlotte Hornets',   # CHA
                1610612741: 'Chicago Bulls',       # CHI
                1610612739: 'Cleveland Cavaliers', # CLE
                1610612742: 'Dallas Mavericks',    # DAL
                1610612743: 'Denver Nuggets',      # DEN
                1610612765: 'Detroit Pistons',     # DET
                1610612744: 'Golden State Warriors', # GSW
                1610612745: 'Houston Rockets',     # HOU
                1610612754: 'Indiana Pacers',      # IND
                1610612746: 'Los Angeles Clippers', # LAC
                1610612747: 'Los Angeles Lakers',  # LAL
                1610612763: 'Memphis Grizzlies',   # MEM
                1610612748: 'Miami Heat',          # MIA
                1610612749: 'Milwaukee Bucks',     # MIL
                1610612750: 'Minnesota Timberwolves', # MIN
                1610612740: 'New Orleans Pelicans', # NOP
                1610612752: 'New York Knicks',    # NYK
                1610612760: 'Oklahoma City Thunder', # OKC
                1610612753: 'Orlando Magic',      # ORL
                1610612755: 'Philadelphia 76ers', # PHI
                1610612756: 'Phoenix Suns',       # PHX
                1610612757: 'Portland Trail Blazers', # POR
                1610612758: 'Sacramento Kings',   # SAC
                1610612759: 'San Antonio Spurs',  # SAS
                1610612761: 'Toronto Raptors',    # TOR
                1610612762: 'Utah Jazz',          # UTA
                1610612764: 'Washington Wizards'  # WAS
            }
            
            # Create mapping from NBA team ID to our team ID
            for team in teams:
                team_name = team['real_team_name']
                for nba_id, nba_name in nba_team_mapping.items():
                    if team_name == nba_name:
                        mapping[nba_id] = team['team_id']
                        break
            
            logger.info(f"Created team mapping for {len(mapping)} NBA teams")
            return mapping
            
        except Exception as e:
            logger.error(f"Error getting team mapping: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()
    
    def fetch_season_schedule(self, season: str) -> List[Dict]:
        """
        Fetch NBA season schedule from the API.
        
        Args:
            season: NBA season (e.g., "2024-25")
            
        Returns:
            List of game dictionaries
        """
        try:
            from nba_api.stats.endpoints import LeagueGameFinder
            
            logger.info(f"Fetching NBA schedule for season {season}")
            
            # Use NBA API to get games
            game_finder = LeagueGameFinder(season_nullable=season)
            games_df = game_finder.get_data_frames()[0]
            
            # Group games by GAME_ID to get both teams
            games_by_id = {}
            for _, row in games_df.iterrows():
                game_id = str(row['GAME_ID'])
                matchup = row['MATCHUP']
                
                if game_id not in games_by_id:
                    # First team for this game
                    games_by_id[game_id] = {
                        'GAME_ID': game_id,
                        'GAME_DATE': row['GAME_DATE'],
                        'HOME_TEAM_ID': None,
                        'VISITOR_TEAM_ID': None,
                        'ARENA_NAME': '',  # Not available in this endpoint
                        'GAME_TIME': '20:00'  # Default time
                    }
                
                # Determine if this team is home or away
                if ' @ ' in matchup:
                    # Format: "TEAM @ HOME" - this team is away
                    games_by_id[game_id]['VISITOR_TEAM_ID'] = row['TEAM_ID']
                elif ' vs. ' in matchup:
                    # Format: "TEAM vs. OPPONENT" - this team is home
                    games_by_id[game_id]['HOME_TEAM_ID'] = row['TEAM_ID']
            
            # Convert back to list
            final_games = list(games_by_id.values())
            
            logger.info(f"Fetched {len(final_games)} games for season {season}")
            return final_games
            
        except Exception as e:
            logger.error(f"Error fetching season schedule: {e}")
            return []
    
    def detect_season_type(self, date_obj: datetime, game_data: Dict = None) -> str:
        """
        Detect NBA season type based on date and game data.
        
        Args:
            date_obj: Date object for the game
            game_data: Optional game data for additional context
            
        Returns:
            Season type string
        """
        month = date_obj.month
        
        # Check for specific NBA events
        if game_data:
            # Check for NBA Cup (In-Season Tournament)
            if game_data.get('gameType') == 'tournament' or game_data.get('isNBAcup'):
                return 'nba_cup'
            
            # Check for All-Star Game
            if game_data.get('gameType') == 'allstar' or game_data.get('isAllStar'):
                return 'all_star_break'
        
        # Determine season type based on month
        if month in [10]:
            return 'preseason'
        elif month in [11, 12, 1, 2, 3, 4]:
            # Check for All-Star Break (typically mid-February)
            if month == 2 and 10 <= date_obj.day <= 20:
                return 'all_star_break'
            # Check for NBA Cup period (November-December)
            elif month in [11, 12]:
                return 'nba_cup'
            else:
                return 'regular_season'
        elif month in [5, 6]:
            return 'playoffs'
        else:
            return 'off_season'
    
    def import_season_schedule(self, season: str) -> int:
        """
        Import full season schedule into the database.
        
        Args:
            season: NBA season (e.g., "2024-25")
            
        Returns:
            Number of games imported
        """
        # Fetch schedule from API
        games = self.fetch_season_schedule(season)
        if not games:
            logger.error("No games fetched from API")
            return 0
        
        # Get team mapping
        team_mapping = self.get_team_mapping()
        if not team_mapping:
            logger.error("No team mapping available")
            return 0
        
        # Connect to database
        conn = self.get_db_connection()
        if not conn:
            logger.error("Could not connect to database")
            return 0
        
        try:
            cursor = conn.cursor()
            imported_count = 0
            
            for game in games:
                try:
                    # Extract game data
                    game_id = str(game.get('GAME_ID', ''))
                    game_date = datetime.strptime(game.get('GAME_DATE', ''), '%Y-%m-%d').date()
                    game_time = game.get('GAME_TIME', '')
                    
                    # Get team information
                    home_team_id = team_mapping.get(game.get('HOME_TEAM_ID'))
                    away_team_id = team_mapping.get(game.get('VISITOR_TEAM_ID'))
                    
                    if not home_team_id or not away_team_id:
                        logger.warning(f"Skipping game {game_id} - team mapping not found")
                        continue
                    
                    # Get arena information
                    arena_name = game.get('ARENA_NAME', '')
                    
                    # Detect season type
                    season_type = self.detect_season_type(datetime.combine(game_date, datetime.min.time()), game)
                    
                    # Check if it's NBA Cup
                    is_nba_cup = season_type == 'nba_cup'
                    
                    # Insert game
                    cursor.execute("""
                        INSERT INTO nba_games (
                            game_id, season, game_date, game_time_est,
                            home_team_id, away_team_id, season_type, arena_name,
                            is_nba_cup, created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (game_id) DO UPDATE SET
                            updated_at = EXCLUDED.updated_at
                    """, (
                        game_id, season, game_date, game_time,
                        home_team_id, away_team_id, season_type, arena_name,
                        is_nba_cup, datetime.now(), datetime.now()
                    ))
                    
                    imported_count += 1
                    
                    if imported_count % 100 == 0:
                        logger.info(f"Imported {imported_count} games...")
                    
                except Exception as e:
                    logger.error(f"Error importing game {game.get('GAME_ID', 'unknown')}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully imported {imported_count} games for season {season}")
            
            # Update season metadata
            self.update_season_metadata(season, imported_count)
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing season schedule: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def update_season_metadata(self, season: str, total_games: int):
        """
        Update season metadata in the database.
        
        Args:
            season: NBA season (e.g., "2024-25")
            total_games: Total number of games imported
        """
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            # Calculate season dates
            season_year = int(season.split('-')[0])
            start_date = datetime(season_year, 10, 1).date()  # October 1st
            end_date = datetime(season_year + 1, 6, 30).date()  # June 30th
            regular_season_start = datetime(season_year, 10, 25).date()  # Approximate
            playoffs_start = datetime(season_year + 1, 4, 15).date()  # Approximate
            
            cursor.execute("""
                INSERT INTO nba_seasons (
                    season, start_date, end_date, regular_season_start,
                    playoffs_start, total_games, last_updated
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (season) DO UPDATE SET
                    total_games = EXCLUDED.total_games,
                    last_updated = EXCLUDED.last_updated
            """, (
                season, start_date, end_date, regular_season_start,
                playoffs_start, total_games, datetime.now()
            ))
            
            conn.commit()
            logger.info(f"Updated season metadata for {season}")
            
        except Exception as e:
            logger.error(f"Error updating season metadata: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
    def get_current_season(self) -> str:
        """
        Get the current NBA season.
        
        Returns:
            Current season string (e.g., "2024-25")
        """
        now = datetime.now()
        if now.month >= 10:  # October onwards
            return f"{now.year}-{str(now.year + 1)[-2:]}"
        else:  # January to September
            return f"{now.year - 1}-{str(now.year)[-2:]}"


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(description='NBA Data Importer')
    parser.add_argument('--season', help='NBA season (e.g., 2024-25)')
    parser.add_argument('--current-season', action='store_true', help='Import current season')
    
    args = parser.parse_args()
    
    importer = NBADataImporter()
    
    if args.current_season:
        season = importer.get_current_season()
        print(f"Importing current season: {season}")
    elif args.season:
        season = args.season
    else:
        print("Please specify --season or --current-season")
        return
    
    print(f"Starting import for NBA season {season}...")
    imported_count = importer.import_season_schedule(season)
    print(f"Import completed. {imported_count} games imported.")


if __name__ == "__main__":
    main()
