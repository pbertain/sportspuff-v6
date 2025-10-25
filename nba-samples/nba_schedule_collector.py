#!/usr/bin/env python3
"""
NBA Schedule and Scores Collector

This script provides comprehensive NBA data collection including:
1. Complete season schedules with season type detection
2. Live scores and game status
3. Season type classification (Preseason, Regular Season, All-Star Break, NBA Cup, Post Season)
4. SQLite database storage for efficient querying

Usage:
    python scripts/nba_schedule_collector.py --help
    python scripts/nba_schedule_collector.py --season 2024-25 --full-schedule
    python scripts/nba_schedule_collector.py --date 2024-12-15 --scores
"""

import sys
import os
import argparse
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.nba_data import NBADataFetcher
from utils.cache_manager import CacheManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NBAScheduleCollector:
    """Enhanced NBA schedule collector with season type detection and database storage."""
    
    def __init__(self, db_path: str = "local/data/nba_schedule.db"):
        """
        Initialize the NBA schedule collector.
        
        Args:
            db_path: Path to SQLite database for NBA schedule data
        """
        self.db_path = db_path
        self.fetcher = NBADataFetcher()
        self.cache = CacheManager()
        self._ensure_db_directory()
        self._init_database()
        
        # NBA season type definitions
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
            },
            'off_season': {
                'months': [7, 8, 9],  # July to September
                'description': 'Off season'
            }
        }
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_database(self):
        """Initialize the NBA schedule database with enhanced schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Enhanced games table for NBA schedule
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nba_games (
                    game_id TEXT PRIMARY KEY,
                    season TEXT NOT NULL,
                    game_date DATE NOT NULL,
                    game_time_est TEXT,
                    home_team_id INTEGER,
                    home_team_city TEXT NOT NULL,
                    home_team_name TEXT NOT NULL,
                    home_team_tricode TEXT,
                    away_team_id INTEGER,
                    away_team_city TEXT NOT NULL,
                    away_team_name TEXT NOT NULL,
                    away_team_tricode TEXT,
                    home_score INTEGER DEFAULT 0,
                    away_score INTEGER DEFAULT 0,
                    game_status TEXT DEFAULT 'scheduled',
                    game_status_text TEXT,
                    season_type TEXT NOT NULL,
                    week INTEGER,
                    series_info TEXT,
                    arena_name TEXT,
                    arena_city TEXT,
                    arena_state TEXT,
                    game_type TEXT DEFAULT 'regular',
                    is_nba_cup BOOLEAN DEFAULT FALSE,
                    is_all_star BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Season metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nba_seasons (
                    season TEXT PRIMARY KEY,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    preseason_start DATE,
                    regular_season_start DATE,
                    all_star_break_start DATE,
                    all_star_break_end DATE,
                    nba_cup_start DATE,
                    nba_cup_end DATE,
                    playoffs_start DATE,
                    playoffs_end DATE,
                    total_games INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Team information table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nba_teams (
                    team_id INTEGER PRIMARY KEY,
                    team_city TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    team_tricode TEXT NOT NULL,
                    conference TEXT,
                    division TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_date ON nba_games(game_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_season ON nba_games(season)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_season_type ON nba_games(season_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_teams ON nba_games(home_team_id, away_team_id)")
            
            conn.commit()
    
    def detect_season_type(self, date_obj: datetime, game_data: Dict = None) -> Tuple[str, str]:
        """
        Detect NBA season type based on date and game data.
        
        Args:
            date_obj: Date object for the game
            game_data: Optional game data for additional context
            
        Returns:
            Tuple of (season_type, description)
        """
        month = date_obj.month
        
        # Check for specific NBA events
        if game_data:
            # Check for NBA Cup (In-Season Tournament)
            if game_data.get('gameType') == 'tournament' or game_data.get('isNBAcup'):
                return 'nba_cup', 'NBA Cup (In-Season Tournament)'
            
            # Check for All-Star Game
            if game_data.get('gameType') == 'allstar' or game_data.get('isAllStar'):
                return 'all_star_break', 'All-Star Game'
        
        # Determine season type based on month
        if month in [10]:
            return 'preseason', 'Preseason'
        elif month in [11, 12, 1, 2, 3, 4]:
            # Check for All-Star Break (typically mid-February)
            if month == 2 and 10 <= date_obj.day <= 20:
                return 'all_star_break', 'All-Star Break'
            # Check for NBA Cup period (November-December)
            elif month in [11, 12]:
                return 'nba_cup', 'NBA Cup Period'
            else:
                return 'regular_season', 'Regular Season'
        elif month in [5, 6]:
            return 'playoffs', 'Playoffs'
        else:
            return 'off_season', 'Off Season'
    
    def get_season_schedule(self, season: str) -> List[Dict]:
        """
        Get complete season schedule for NBA.
        
        Args:
            season: NBA season (e.g., '2024-25')
            
        Returns:
            List of all games in the season
        """
        logger.info(f"Fetching complete schedule for NBA season {season}")
        
        try:
            # Get the full season schedule
            schedule_data = self.fetcher.get_schedule()
            
            if not schedule_data:
                logger.warning(f"No schedule data found for season {season}")
                return []
            
            # Process and enhance the schedule data
            enhanced_games = []
            for game in schedule_data:
                enhanced_game = self._enhance_game_data(game, season)
                if enhanced_game:
                    enhanced_games.append(enhanced_game)
            
            logger.info(f"Processed {len(enhanced_games)} games for season {season}")
            return enhanced_games
            
        except Exception as e:
            logger.error(f"Error fetching season schedule: {e}")
            return []
    
    def _enhance_game_data(self, game: Dict, season: str) -> Optional[Dict]:
        """
        Enhance game data with additional information.
        
        Args:
            game: Raw game data from API
            season: NBA season
            
        Returns:
            Enhanced game data or None if invalid
        """
        try:
            # Extract team information
            home_team = game.get('homeTeam', {})
            away_team = game.get('awayTeam', {})
            
            if not home_team or not away_team:
                return None
            
            # Parse game date
            game_date_str = game.get('gameDate', '')
            if not game_date_str:
                return None
            
            # Convert date format (MM/DD/YYYY to YYYY-MM-DD)
            try:
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
                'home_team_city': home_team.get('teamCity', ''),
                'home_team_name': home_team.get('teamName', ''),
                'home_team_tricode': home_team.get('teamTricode', ''),
                'away_team_id': away_team.get('teamId'),
                'away_team_city': away_team.get('teamCity', ''),
                'away_team_name': away_team.get('teamName', ''),
                'away_team_tricode': away_team.get('teamTricode', ''),
                'home_score': home_team.get('score', 0),
                'away_score': away_team.get('score', 0),
                'game_status': game.get('gameStatus', 'scheduled'),
                'game_status_text': game.get('gameStatusText', ''),
                'season_type': season_type,
                'season_description': season_description,
                'week': game.get('week', 0),
                'series_info': json.dumps(game.get('series', {})),
                'arena_name': arena.get('name', ''),
                'arena_city': arena.get('city', ''),
                'arena_state': arena.get('state', ''),
                'game_type': game.get('gameType', 'regular'),
                'is_nba_cup': season_type == 'nba_cup',
                'is_all_star': season_type == 'all_star_break'
            }
            
            return enhanced_game
            
        except Exception as e:
            logger.error(f"Error enhancing game data: {e}")
            return None
    
    def store_games(self, games: List[Dict]) -> int:
        """
        Store games in the database.
        
        Args:
            games: List of enhanced game data
            
        Returns:
            Number of games stored
        """
        if not games:
            return 0
        
        stored_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for game in games:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO nba_games 
                        (game_id, season, game_date, game_time_est, home_team_id, home_team_city, 
                         home_team_name, home_team_tricode, away_team_id, away_team_city, 
                         away_team_name, away_team_tricode, home_score, away_score, 
                         game_status, game_status_text, season_type, week, series_info, 
                         arena_name, arena_city, arena_state, game_type, is_nba_cup, 
                         is_all_star, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game['game_id'],
                        game['season'],
                        game['game_date'],
                        game['game_time_est'],
                        game['home_team_id'],
                        game['home_team_city'],
                        game['home_team_name'],
                        game['home_team_tricode'],
                        game['away_team_id'],
                        game['away_team_city'],
                        game['away_team_name'],
                        game['away_team_tricode'],
                        game['home_score'],
                        game['away_score'],
                        game['game_status'],
                        game['game_status_text'],
                        game['season_type'],
                        game['week'],
                        game['series_info'],
                        game['arena_name'],
                        game['arena_city'],
                        game['arena_state'],
                        game['game_type'],
                        game['is_nba_cup'],
                        game['is_all_star'],
                        datetime.now().isoformat()
                    ))
                    stored_count += 1
                except Exception as e:
                    logger.error(f"Error storing game {game.get('game_id', 'unknown')}: {e}")
            
            conn.commit()
        
        logger.info(f"Stored {stored_count} games in database")
        return stored_count
    
    def get_games_by_date(self, date: str) -> List[Dict]:
        """
        Get games for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of games for the date
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM nba_games 
                WHERE game_date = ? 
                ORDER BY game_time_est
            """, (date,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_games_by_season_type(self, season: str, season_type: str) -> List[Dict]:
        """
        Get games by season type.
        
        Args:
            season: NBA season (e.g., '2024-25')
            season_type: Type of season (preseason, regular_season, playoffs, etc.)
            
        Returns:
            List of games for the season type
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM nba_games 
                WHERE season = ? AND season_type = ? 
                ORDER BY game_date, game_time_est
            """, (season, season_type))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_live_scores(self, date: str = None) -> List[Dict]:
        """
        Get live scores for games.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
            
        Returns:
            List of games with current scores
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # First try to get from database
        games = self.get_games_by_date(date)
        
        # If no games in database or we want fresh data, fetch from API
        if not games:
            logger.info(f"No games found in database for {date}, fetching from API")
            api_games = self.fetcher.get_scores(date)
            
            if api_games:
                # Enhance and store the games
                enhanced_games = []
                season = self._get_season_from_date(date)
                
                for game in api_games:
                    enhanced_game = self._enhance_game_data(game, season)
                    if enhanced_game:
                        enhanced_games.append(enhanced_game)
                
                if enhanced_games:
                    self.store_games(enhanced_games)
                    games = enhanced_games
        
        return games
    
    def _get_season_from_date(self, date: str) -> str:
        """Get NBA season from date."""
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        year = date_obj.year
        month = date_obj.month
        
        if month >= 10:
            return f"{year}-{str(year + 1)[-2:]}"
        else:
            return f"{year - 1}-{str(year)[-2:]}"
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total games
            cursor.execute("SELECT COUNT(*) FROM nba_games")
            total_games = cursor.fetchone()[0]
            
            # Games by season
            cursor.execute("SELECT season, COUNT(*) FROM nba_games GROUP BY season")
            games_by_season = dict(cursor.fetchall())
            
            # Games by season type
            cursor.execute("SELECT season_type, COUNT(*) FROM nba_games GROUP BY season_type")
            games_by_type = dict(cursor.fetchall())
            
            # Date range
            cursor.execute("SELECT MIN(game_date), MAX(game_date) FROM nba_games")
            date_range = cursor.fetchone()
            
            # Database size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'total_games': total_games,
                'games_by_season': games_by_season,
                'games_by_type': games_by_type,
                'date_range': date_range,
                'db_size_mb': round(db_size / (1024 * 1024), 2)
            }


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='NBA Schedule and Scores Collector')
    parser.add_argument('--season', help='NBA season (e.g., 2024-25)')
    parser.add_argument('--date', help='Specific date (YYYY-MM-DD)')
    parser.add_argument('--full-schedule', action='store_true', help='Download full season schedule')
    parser.add_argument('--scores', action='store_true', help='Get live scores')
    parser.add_argument('--season-type', help='Filter by season type (preseason, regular_season, playoffs, etc.)')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--db-path', default='local/data/nba_schedule.db', help='Database path')
    
    args = parser.parse_args()
    
    collector = NBAScheduleCollector(args.db_path)
    
    if args.stats:
        stats = collector.get_database_stats()
        print("\n📊 NBA Schedule Database Statistics")
        print("=" * 40)
        print(f"Total Games: {stats['total_games']}")
        print(f"Database Size: {stats['db_size_mb']} MB")
        print(f"Date Range: {stats['date_range'][0]} to {stats['date_range'][1]}")
        
        print("\nGames by Season:")
        for season, count in stats['games_by_season'].items():
            print(f"  {season}: {count} games")
        
        print("\nGames by Season Type:")
        for season_type, count in stats['games_by_type'].items():
            print(f"  {season_type}: {count} games")
    
    elif args.full_schedule and args.season:
        logger.info(f"Downloading full schedule for season {args.season}")
        games = collector.get_season_schedule(args.season)
        
        if games:
            stored = collector.store_games(games)
            print(f"✅ Downloaded and stored {stored} games for season {args.season}")
        else:
            print(f"❌ No games found for season {args.season}")
    
    elif args.date:
        if args.scores:
            logger.info(f"Getting live scores for {args.date}")
            games = collector.get_live_scores(args.date)
            
            if games:
                print(f"\n🏀 NBA Games for {args.date}")
                print("=" * 50)
                
                for game in games:
                    home_team = f"{game['home_team_city']} {game['home_team_name']}"
                    away_team = f"{game['away_team_city']} {game['away_team_name']}"
                    status = game['game_status_text'] or game['game_status']
                    season_type = game['season_type']
                    
                    print(f"{away_team} @ {home_team}")
                    print(f"  Status: {status}")
                    print(f"  Season Type: {season_type}")
                    
                    if game['home_score'] > 0 or game['away_score'] > 0:
                        print(f"  Score: {away_team} {game['away_score']} - {game['home_score']} {home_team}")
                    
                    if game['game_time_est']:
                        print(f"  Time: {game['game_time_est']}")
                    
                    print()
            else:
                print(f"No games found for {args.date}")
        else:
            games = collector.get_games_by_date(args.date)
            print(f"Found {len(games)} games for {args.date}")
    
    elif args.season_type and args.season:
        games = collector.get_games_by_season_type(args.season, args.season_type)
        print(f"Found {len(games)} {args.season_type} games for season {args.season}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
