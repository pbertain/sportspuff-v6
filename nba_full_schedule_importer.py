#!/usr/bin/env python3
"""
NBA Full Schedule Importer

This script downloads the complete NBA season schedule with proper season type detection
and imports it into the PostgreSQL database.

Usage:
    python nba_full_schedule_importer.py --season 2025-26
"""

import sys
import os
import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class NBAFullScheduleImporter:
    """NBA full schedule importer with proper season type detection."""
    
    def __init__(self):
        """Initialize the NBA schedule importer."""
        self.season_types = {
            'preseason': {
                'months': [10],  # October
                'description': 'Preseason games'
            },
            'regular_season': {
                'months': [11, 12, 1, 2, 3, 4],  # November to April
                'description': 'Regular season games'
            },
            'all_star_break': {
                'months': [2],  # February (typically mid-February)
                'description': 'All-Star Break period'
            },
            'nba_cup': {
                'months': [11, 12],  # November-December (In-Season Tournament)
                'description': 'NBA Cup (In-Season Tournament)'
            },
            'playoffs': {
                'months': [4, 5, 6],  # April to June
                'description': 'Playoffs and Finals'
            }
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
    
    def detect_season_type(self, date_obj: datetime, game_data: Dict = None) -> Tuple[str, str]:
        """
        Detect NBA season type based on game data from NBA API.
        
        Args:
            date_obj: Date object for the game
            game_data: Game data from NBA API
            
        Returns:
            Tuple of (season_type, description)
        """
        if not game_data:
            return 'regular_season', 'Regular Season'
        
        # Use NBA API gameLabel and gameSubtype fields
        game_label = game_data.get('gameLabel', '')
        game_subtype = game_data.get('gameSubtype', '')
        
        # Check for specific game types
        if game_label == 'Preseason':
            if game_subtype == 'Global Games':
                return 'preseason', 'Preseason (Global Games)'
            else:
                return 'preseason', 'Preseason'
        
        elif game_label == 'Emirates NBA Cup':
            if game_subtype == 'in-season-knockout':
                return 'nba_cup', 'NBA Cup (Knockout Round)'
            elif game_subtype == 'in-season':
                return 'nba_cup', 'NBA Cup (Group Stage)'
            else:
                return 'nba_cup', 'NBA Cup'
        
        # Default to regular season for empty gameLabel
        else:
            return 'regular_season', 'Regular Season'
    
    def get_season_schedule(self, season: str) -> List[Dict]:
        """
        Get complete season schedule for NBA using LeagueGameFinder.
        
        Args:
            season: NBA season (e.g., '2025-26')
            
        Returns:
            List of all games in the season
        """
        logger.info(f"Fetching complete schedule for NBA season {season}")
        
        try:
            from nba_api.stats.endpoints import LeagueGameFinder
            
            # Get ALL games using LeagueGameFinder (no date restrictions)
            # This returns ~30,000 games across all seasons
            gamefinder = LeagueGameFinder()
            games_df = gamefinder.get_data_frames()[0]
            
            if games_df.empty:
                logger.warning(f"No games found from LeagueGameFinder")
                return []
            
            logger.info(f"LeagueGameFinder returned {len(games_df)} total games")
            
            # Filter to the specific season
            # NBA season IDs: 2024-25 = 22024, 2025-26 = 22025
            season_id = f"2{season.split('-')[0]}"
            season_games = games_df[games_df['SEASON_ID'] == season_id]
            
            logger.info(f"Found {len(season_games)} games for season {season} (season_id: {season_id})")
            
            if season_games.empty:
                logger.warning(f"No games found for season {season}")
                return []
            
            # Convert DataFrame to list of dictionaries
            all_games = []
            for _, row in season_games.iterrows():
                enhanced_game = self._enhance_game_data_from_row(row, season)
                if enhanced_game:
                    all_games.append(enhanced_game)
            
            logger.info(f"Processed {len(all_games)} games for season {season}")
            return all_games
            
        except Exception as e:
            logger.error(f"Error fetching season schedule: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _enhance_game_data_from_api(self, game: Dict, season: str, game_date_str: str = None) -> Optional[Dict]:
        """
        Enhance game data from NBA API scheduleleaguev2 response.
        
        Args:
            game: Raw game data from API
            season: NBA season
            game_date_str: Game date string from parent game_date object
            
        Returns:
            Enhanced game data or None if invalid
        """
        try:
            # Extract team information
            home_team = game.get('homeTeam', {})
            away_team = game.get('awayTeam', {})
            
            if not home_team or not away_team:
                logger.warning(f"No team data found for game {game.get('gameId', 'unknown')}")
                return None
            
            # Use the provided date string or try to get it from the game
            if not game_date_str:
                game_date_str = game.get('gameDate', '')
                if not game_date_str:
                    # Try to get date from other fields
                    game_date_str = game.get('gameDateTimeUTC', '')
                    if game_date_str:
                        try:
                            # Parse ISO format date
                            from datetime import datetime
                            date_obj = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
                            game_date_str = date_obj.strftime('%m/%d/%Y')
                        except:
                            logger.warning(f"Could not parse game date: {game_date_str}")
                            return None
                    else:
                        logger.warning(f"No game date found for game {game.get('gameId', 'unknown')}")
                        return None
            
            # Convert date format (MM/DD/YYYY to YYYY-MM-DD)
            try:
                # Handle different date formats
                if ' ' in game_date_str:
                    # Format: "10/02/2025 00:00:00"
                    game_date_str = game_date_str.split(' ')[0]
                
                from datetime import datetime
                game_date_obj = datetime.strptime(game_date_str, '%m/%d/%Y')
                game_date = game_date_obj.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid date format: {game_date_str}")
                return None
            
            # Detect season type
            season_type, season_description = self.detect_season_type(game_date_obj, game)
            
            # Extract arena information
            arena = game.get('arena', {})
            
            # Get team mapping
            team_mapping = self.get_team_mapping()
            
            # Map NBA team IDs to our team IDs
            home_team_id = team_mapping.get(home_team.get('teamId'))
            away_team_id = team_mapping.get(away_team.get('teamId'))
            
            if not home_team_id or not away_team_id:
                logger.warning(f"Skipping game {game.get('gameId', 'unknown')} - team mapping not found for {home_team.get('teamName', 'unknown')} or {away_team.get('teamName', 'unknown')}")
                return None
            
            enhanced_game = {
                'game_id': game.get('gameId', f"{season}_{game_date}_{home_team_id}_{away_team_id}"),
                'season': season,
                'game_date': game_date,
                'game_time_est': game.get('gameTimeEst', ''),
                'home_team_id': home_team_id,
                'away_team_id': away_team_id,
                'home_score': home_team.get('score', 0),
                'away_score': away_team.get('score', 0),
                'game_status': game.get('gameStatus', 'scheduled'),
                'game_status_text': game.get('gameStatusText', ''),
                'season_type': season_type,
                'current_period': game.get('period', 0),
                'period_time_remaining': game.get('periodTimeRemaining', ''),
                'arena_name': arena.get('name', ''),
                'is_nba_cup': season_type == 'nba_cup',
                'winner_team_id': None  # Will be set when game is final
            }
            
            return enhanced_game
            
        except Exception as e:
            logger.error(f"Error enhancing game data: {e}")
            logger.error(f"Game data: {game}")
            return None
    
    def _enhance_game_data_from_row(self, row, season: str) -> Optional[Dict]:
        """
        Enhance game data from LeagueGameFinder DataFrame row.
        
        Args:
            row: DataFrame row from LeagueGameFinder
            season: NBA season
            
        Returns:
            Enhanced game data or None if invalid
        """
        try:
            # Parse the MATCHUP string to get teams
            matchup = row.get('MATCHUP', '')
            if not matchup:
                return None
            
            # MATCHUP format: "ATL @ ORL" or "ORL vs. ATL" (with periods)
            if ' @ ' in matchup:
                away_team, home_team = matchup.split(' @ ')
            elif ' vs. ' in matchup:
                home_team, away_team = matchup.split(' vs. ')
            elif ' vs ' in matchup:
                home_team, away_team = matchup.split(' vs ')
            else:
                logger.warning(f"Could not parse matchup: {matchup}")
                return None
            
            # Convert abbreviations to full team names
            team_abbrev_to_name = {
                'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'CLE': 'Cleveland Cavaliers',
                'NOP': 'New Orleans Pelicans', 'CHI': 'Chicago Bulls', 'DAL': 'Dallas Mavericks',
                'DEN': 'Denver Nuggets', 'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets',
                'LAC': 'Los Angeles Clippers', 'LAL': 'Los Angeles Lakers', 'MIA': 'Miami Heat',
                'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves', 'BKN': 'Brooklyn Nets',
                'NYK': 'New York Knicks', 'ORL': 'Orlando Magic', 'IND': 'Indiana Pacers',
                'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns', 'POR': 'Portland Trail Blazers',
                'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs', 'OKC': 'Oklahoma City Thunder',
                'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'MEM': 'Memphis Grizzlies',
                'WAS': 'Washington Wizards', 'DET': 'Detroit Pistons', 'CHA': 'Charlotte Hornets'
            }
            
            home_team = team_abbrev_to_name.get(home_team.strip(), home_team.strip())
            away_team = team_abbrev_to_name.get(away_team.strip(), away_team.strip())
            
            # Convert date
            game_date_str = row.get('GAME_DATE', '')
            if not game_date_str:
                return None
            
            try:
                game_date_obj = datetime.strptime(game_date_str, '%Y-%m-%d')
                game_date = game_date_obj.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid date format: {game_date_str}")
                return None
            
            # Detect season type based on date
            season_type, season_description = self.detect_season_type(game_date_obj, {})
            
            enhanced_game = {
                'game_id': row.get('GAME_ID', f"{season}_{game_date}_{home_team}_{away_team}"),
                'season': season,
                'game_date': game_date,
                'game_time_est': '',  # Not available in LeagueGameFinder
                'home_team_id': None,  # Will be mapped later
                'away_team_id': None,  # Will be mapped later
                'home_team_name': home_team.strip(),
                'away_team_name': away_team.strip(),
                'home_score': row.get('PTS', 0) if row.get('WL') == 'W' else 0,
                'away_score': row.get('PTS', 0) if row.get('WL') == 'L' else 0,
                'game_status': 'final' if row.get('WL') else 'scheduled',
                'game_status_text': 'Final' if row.get('WL') else 'Scheduled',
                'season_type': season_type,
                'arena_name': '',
                'is_nba_cup': season_type == 'nba_cup',
                'winner_team_id': None  # Will be set when game is final
            }
            
            return enhanced_game
            
        except Exception as e:
            logger.error(f"Error enhancing game data from row: {e}")
            return None
    
    def _enhance_game_data(self, game: Dict, season: str, game_date_str: str = None) -> Optional[Dict]:
        """
        Enhance game data with additional information.
        
        Args:
            game: Raw game data from API
            season: NBA season
            game_date_str: Game date string from parent game_date object
            
        Returns:
            Enhanced game data or None if invalid
        """
        try:
            # Extract team information
            home_team = game.get('homeTeam', {})
            away_team = game.get('awayTeam', {})
            
            if not home_team or not away_team:
                logger.warning(f"No team data found for game {game.get('gameId', 'unknown')}")
                return None
            
            # Use the provided date string or try to get it from the game
            if not game_date_str:
                game_date_str = game.get('gameDate', '')
                if not game_date_str:
                    logger.warning(f"No game date found for game {game.get('gameId', 'unknown')}")
                    return None
            
            # Convert date format (MM/DD/YYYY to YYYY-MM-DD)
            try:
                # Handle different date formats
                if ' ' in game_date_str:
                    # Format: "10/02/2025 00:00:00"
                    game_date_str = game_date_str.split(' ')[0]
                
                game_date_obj = datetime.strptime(game_date_str, '%m/%d/%Y')
                game_date = game_date_obj.strftime('%Y-%m-%d')
            except ValueError:
                logger.warning(f"Invalid date format: {game_date_str}")
                return None
            
            # Detect season type
            season_type, season_description = self.detect_season_type(game_date_obj, game)
            
            # Extract arena information
            arena = game.get('arena', {})
            
            enhanced_game = {
                'game_id': game.get('gameId', f"{season}_{game_date}_{home_team.get('teamId', '')}_{away_team.get('teamId', '')}"),
                'season': season,
                'game_date': game_date,
                'game_time_est': game.get('gameTimeEst', ''),
                'home_team_id': home_team.get('teamId'),
                'away_team_id': away_team.get('teamId'),
                'home_score': home_team.get('score', 0),
                'away_score': away_team.get('score', 0),
                'game_status': game.get('gameStatus', 'scheduled'),
                'game_status_text': game.get('gameStatusText', ''),
                'season_type': season_type,
                'arena_name': arena.get('name', ''),
                'is_nba_cup': season_type == 'nba_cup',
                'winner_team_id': None  # Will be set when game is final
            }
            
            return enhanced_game
            
        except Exception as e:
            logger.error(f"Error enhancing game data: {e}")
            logger.error(f"Game data: {game}")
            return None
    
    def get_team_mapping(self) -> Dict[int, int]:
        """
        Get mapping of NBA team IDs to our team IDs.
        
        Returns:
            Dictionary mapping NBA team ID to our team ID
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get NBA teams from our database
            cursor.execute("""
                SELECT team_id, real_team_name 
                FROM teams 
                WHERE league_id = (SELECT league_id FROM leagues WHERE league_name_proper = 'NBA')
            """)
            
            teams = cursor.fetchall()
            
            # Create mapping from team name to our team ID
            team_name_mapping = {}
            for team in teams:
                team_name_mapping[team['real_team_name']] = team['team_id']
            
            # NBA API team ID to team name mapping (from NBA API)
            nba_team_id_to_name = {
                1610612737: "Atlanta Hawks",
                1610612738: "Boston Celtics", 
                1610612739: "Cleveland Cavaliers",
                1610612740: "New Orleans Pelicans",
                1610612741: "Chicago Bulls",
                1610612742: "Dallas Mavericks",
                1610612743: "Denver Nuggets",
                1610612744: "Golden State Warriors",
                1610612745: "Houston Rockets",
                1610612746: "Los Angeles Clippers",
                1610612747: "Los Angeles Lakers",
                1610612748: "Miami Heat",
                1610612749: "Milwaukee Bucks",
                1610612750: "Minnesota Timberwolves",
                1610612751: "Brooklyn Nets",
                1610612752: "New York Knicks",
                1610612753: "Orlando Magic",
                1610612754: "Indiana Pacers",
                1610612755: "Philadelphia 76ers",
                1610612756: "Phoenix Suns",
                1610612757: "Portland Trail Blazers",
                1610612758: "Sacramento Kings",
                1610612759: "San Antonio Spurs",
                1610612760: "Oklahoma City Thunder",
                1610612761: "Toronto Raptors",
                1610612762: "Utah Jazz",
                1610612763: "Memphis Grizzlies",
                1610612764: "Washington Wizards",
                1610612765: "Detroit Pistons",
                1610612766: "Charlotte Hornets"
            }
            
            # Create final mapping from NBA team ID to our team ID
            team_mapping = {}
            for nba_team_id, nba_team_name in nba_team_id_to_name.items():
                if nba_team_name in team_name_mapping:
                    team_mapping[nba_team_id] = team_name_mapping[nba_team_name]
            
            logger.info(f"Created team mapping for {len(team_mapping)} NBA teams")
            return team_mapping
            
        except Exception as e:
            logger.error(f"Error getting team mapping: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()
    
    def import_games(self, games: List[Dict]) -> int:
        """
        Import games into PostgreSQL database.
        
        Args:
            games: List of enhanced game data
            
        Returns:
            Number of games imported
        """
        if not games:
            return 0
        
        # Get team mapping
        team_mapping = self.get_team_mapping()
        if not team_mapping:
            logger.error("No team mapping available")
            return 0
        
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            imported_count = 0
            
            for game in games:
                try:
                    # Map NBA team names to our team IDs
                    home_team_id = team_mapping.get(game['home_team_name'])
                    away_team_id = team_mapping.get(game['away_team_name'])
                    
                    if not home_team_id or not away_team_id:
                        logger.warning(f"Skipping game {game['game_id']} - team mapping not found for {game['home_team_name']} or {game['away_team_name']}")
                        continue
                    
                    # Insert or update game
                    cursor.execute("""
                        INSERT INTO nba_games 
                        (game_id, season, game_date, game_time_est, home_team_id, away_team_id,
                         home_score, away_score, game_status, game_status_text, season_type,
                         arena_name, is_nba_cup, winner_team_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score,
                            game_status = EXCLUDED.game_status,
                            game_status_text = EXCLUDED.game_status_text,
                            season_type = EXCLUDED.season_type,
                            arena_name = EXCLUDED.arena_name,
                            is_nba_cup = EXCLUDED.is_nba_cup,
                            winner_team_id = EXCLUDED.winner_team_id,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        game['game_id'],
                        game['season'],
                        game['game_date'],
                        game['game_time_est'],
                        home_team_id,
                        away_team_id,
                        game['home_score'],
                        game['away_score'],
                        game['game_status'],
                        game['game_status_text'],
                        game['season_type'],
                        game['arena_name'],
                        game['is_nba_cup'],
                        game['winner_team_id'],
                        datetime.now(),
                        datetime.now()
                    ))
                    
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Error importing game {game.get('game_id', 'unknown')}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully imported {imported_count} games")
            return imported_count
            
        except Exception as e:
            logger.error(f"Error importing games: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Total games
            cursor.execute("SELECT COUNT(*) as count FROM nba_games")
            total_games = cursor.fetchone()['count']
            
            # Games by season
            cursor.execute("SELECT season, COUNT(*) as count FROM nba_games GROUP BY season ORDER BY season")
            games_by_season = {row['season']: row['count'] for row in cursor.fetchall()}
            
            # Games by season type
            cursor.execute("SELECT season_type, COUNT(*) as count FROM nba_games GROUP BY season_type ORDER BY season_type")
            games_by_type = {row['season_type']: row['count'] for row in cursor.fetchall()}
            
            # Date range
            cursor.execute("SELECT MIN(game_date) as min_date, MAX(game_date) as max_date FROM nba_games")
            date_range = cursor.fetchone()
            
            return {
                'total_games': total_games,
                'games_by_season': games_by_season,
                'games_by_type': games_by_type,
                'date_range': (date_range['min_date'], date_range['max_date'])
            }
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='NBA Full Schedule Importer')
    parser.add_argument('--season', default='2025-26', help='NBA season (e.g., 2025-26)')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    
    args = parser.parse_args()
    
    importer = NBAFullScheduleImporter()
    
    if args.stats:
        stats = importer.get_database_stats()
        print("\n📊 NBA Schedule Database Statistics")
        print("=" * 40)
        print(f"Total Games: {stats.get('total_games', 0)}")
        
        if stats.get('date_range'):
            print(f"Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
        
        print("\nGames by Season:")
        for season, count in stats.get('games_by_season', {}).items():
            print(f"  {season}: {count} games")
        
        print("\nGames by Season Type:")
        for season_type, count in stats.get('games_by_type', {}).items():
            print(f"  {season_type}: {count} games")
    
    else:
        logger.info(f"Downloading full schedule for season {args.season}")
        games = importer.get_season_schedule(args.season)
        
        if games:
            imported = importer.import_games(games)
            print(f"✅ Downloaded and imported {imported} games for season {args.season}")
            
            # Show stats after import
            stats = importer.get_database_stats()
            print(f"\n📊 Database now contains {stats.get('total_games', 0)} total games")
            
            print("\nGames by Season Type:")
            for season_type, count in stats.get('games_by_type', {}).items():
                print(f"  {season_type}: {count} games")
        else:
            print(f"❌ No games found for season {args.season}")


if __name__ == "__main__":
    main()
