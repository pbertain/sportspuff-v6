#!/usr/bin/env python3
"""
NBA Schedule and Scores Collector for PostgreSQL

This script provides comprehensive NBA data collection including:
1. Complete season schedules with season type detection
2. Live scores and game status
3. Season type classification (Preseason, Regular Season, All-Star Break, NBA Cup, Post Season)
4. PostgreSQL database storage for efficient querying

Usage:
    python nba_schedule_collector.py --help
    python nba_schedule_collector.py --season 2024-25 --full-schedule
    python nba_schedule_collector.py --date 2024-12-15 --scores
"""

import sys
import os
import argparse
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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


class NBAScheduleCollector:
    """Enhanced NBA schedule collector with season type detection and PostgreSQL storage."""
    
    def __init__(self):
        """Initialize the NBA schedule collector."""
        self.fetcher = None  # Will be initialized when needed
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
    
    def get_db_connection(self):
        """Get PostgreSQL database connection."""
        try:
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
    
    def _init_database(self):
        """Initialize the NBA schedule database with enhanced schema."""
        conn = self.get_db_connection()
        if not conn:
            logger.error("Could not connect to database for initialization")
            return
        
        try:
            cursor = conn.cursor()
            
            # NBA Games table (unified schedule + scores)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nba_games (
                    game_id TEXT PRIMARY KEY,
                    season TEXT NOT NULL,
                    game_date DATE NOT NULL,
                    game_time_est TEXT,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    home_score INTEGER DEFAULT 0,
                    away_score INTEGER DEFAULT 0,
                    game_status TEXT DEFAULT 'scheduled',
                    game_status_text TEXT,
                    current_period INTEGER,
                    period_time_remaining TEXT,
                    season_type TEXT NOT NULL,
                    arena_name TEXT,
                    is_nba_cup BOOLEAN DEFAULT FALSE,
                    winner_team_id INTEGER,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Foreign key constraints
                    FOREIGN KEY (home_team_id) REFERENCES teams(team_id) ON DELETE SET NULL,
                    FOREIGN KEY (away_team_id) REFERENCES teams(team_id) ON DELETE SET NULL,
                    FOREIGN KEY (winner_team_id) REFERENCES teams(team_id) ON DELETE SET NULL
                )
            """)
            
            # NBA Seasons metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nba_seasons (
                    season TEXT PRIMARY KEY,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    regular_season_start DATE,
                    playoffs_start DATE,
                    total_games INTEGER DEFAULT 0,
                    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_date ON nba_games(game_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_season ON nba_games(season)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_teams ON nba_games(home_team_id, away_team_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_status ON nba_games(game_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nba_games_season_type ON nba_games(season_type)")
            
            conn.commit()
            logger.info("NBA database schema initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
    
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
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT team_id, real_team_name 
                FROM teams 
                WHERE league_id = 3
                ORDER BY real_team_name
            """)
            
            teams = cursor.fetchall()
            mapping = {}
            
            # Create mapping based on team names
            nba_team_mapping = {
                'Atlanta Hawks': 1013,
                'Boston Celtics': 1015,
                'Brooklyn Nets': 1113,
                'Charlotte Hornets': 1124,
                'Chicago Bulls': 1027,
                'Cleveland Cavaliers': 1035,
                'Dallas Mavericks': 1050,
                'Denver Nuggets': 1095,
                'Detroit Pistons': 1052,
                'Golden State Warriors': 1060,
                'Houston Rockets': 1075,
                'Indiana Pacers': 1068,
                'Los Angeles Clippers': 1084,
                'Los Angeles Lakers': 1130,
                'Memphis Grizzlies': 1140,
                'Miami Heat': 1007,
                'Milwaukee Bucks': 1023,
                'Minnesota Timberwolves': 1090,
                'New Orleans Pelicans': 1122,
                'New York Knicks': 1176,
                'Oklahoma City Thunder': 1044,
                'Orlando Magic': 1065,
                'Philadelphia 76ers': 1088,
                'Phoenix Suns': 1107,
                'Portland Trail Blazers': 1141,
                'Sacramento Kings': 1060,
                'San Antonio Spurs': 1075,
                'Toronto Raptors': 1084,
                'Utah Jazz': 1130,
                'Washington Wizards': 1140
            }
            
            for team in teams:
                team_name = team['real_team_name']
                if team_name in nba_team_mapping:
                    mapping[nba_team_mapping[team_name]] = team['team_id']
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error getting team mapping: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()
    
    def save_games_to_db(self, games: List[Dict], season: str) -> int:
        """
        Save games to PostgreSQL database.
        
        Args:
            games: List of game dictionaries
            season: NBA season (e.g., "2024-25")
            
        Returns:
            Number of games saved
        """
        if not games:
            return 0
        
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            team_mapping = self.get_team_mapping()
            saved_count = 0
            
            for game in games:
                try:
                    # Extract game data
                    game_id = game.get('gameId', '')
                    game_date = datetime.strptime(game.get('gameDate', ''), '%Y-%m-%d').date()
                    game_time = game.get('gameTimeUTC', '')
                    
                    # Get team information
                    home_team = game.get('homeTeam', {})
                    away_team = game.get('awayTeam', {})
                    
                    home_team_id = team_mapping.get(home_team.get('teamId'))
                    away_team_id = team_mapping.get(away_team.get('teamId'))
                    
                    # Get scores and status
                    home_score = game.get('homeTeam', {}).get('score', 0)
                    away_score = game.get('awayTeam', {}).get('score', 0)
                    game_status = game.get('gameStatus', 'scheduled')
                    game_status_text = game.get('gameStatusText', '')
                    
                    # Detect season type
                    season_type, _ = self.detect_season_type(datetime.combine(game_date, datetime.min.time()), game)
                    
                    # Get arena information
                    arena_name = game.get('arena', {}).get('name', '')
                    
                    # Insert or update game
                    cursor.execute("""
                        INSERT INTO nba_games (
                            game_id, season, game_date, game_time_est,
                            home_team_id, away_team_id, home_score, away_score,
                            game_status, game_status_text, season_type, arena_name,
                            is_nba_cup, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (game_id) DO UPDATE SET
                            home_score = EXCLUDED.home_score,
                            away_score = EXCLUDED.away_score,
                            game_status = EXCLUDED.game_status,
                            game_status_text = EXCLUDED.game_status_text,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        game_id, season, game_date, game_time,
                        home_team_id, away_team_id, home_score, away_score,
                        game_status, game_status_text, season_type, arena_name,
                        season_type == 'nba_cup', datetime.now()
                    ))
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving game {game.get('gameId', 'unknown')}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully saved {saved_count} games to database")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error saving games to database: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def get_games_by_date(self, date: str) -> List[Dict]:
        """
        Get NBA games for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of game dictionaries
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT g.*, 
                       ht.real_team_name as home_team_name,
                       at.real_team_name as away_team_name
                FROM nba_games g
                LEFT JOIN teams ht ON g.home_team_id = ht.team_id
                LEFT JOIN teams at ON g.away_team_id = at.team_id
                WHERE g.game_date = %s
                ORDER BY g.game_time_est
            """, (date,))
            
            games = cursor.fetchall()
            return [dict(game) for game in games]
            
        except Exception as e:
            logger.error(f"Error getting games by date: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    def get_live_games(self) -> List[Dict]:
        """
        Get all live NBA games.
        
        Returns:
            List of live game dictionaries
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT g.*, 
                       ht.real_team_name as home_team_name,
                       at.real_team_name as away_team_name
                FROM nba_games g
                LEFT JOIN teams ht ON g.home_team_id = ht.team_id
                LEFT JOIN teams at ON g.away_team_id = at.team_id
                WHERE g.game_status IN ('live', 'in-progress')
                ORDER BY g.game_date, g.game_time_est
            """)
            
            games = cursor.fetchall()
            return [dict(game) for game in games]
            
        except Exception as e:
            logger.error(f"Error getting live games: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    def get_database_stats(self) -> Dict:
        """
        Get database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get total games count
            cursor.execute("SELECT COUNT(*) as total_games FROM nba_games")
            total_games = cursor.fetchone()['total_games']
            
            # Get games by status
            cursor.execute("""
                SELECT game_status, COUNT(*) as count 
                FROM nba_games 
                GROUP BY game_status
            """)
            status_counts = {row['game_status']: row['count'] for row in cursor.fetchall()}
            
            # Get games by season type
            cursor.execute("""
                SELECT season_type, COUNT(*) as count 
                FROM nba_games 
                GROUP BY season_type
            """)
            season_type_counts = {row['season_type']: row['count'] for row in cursor.fetchall()}
            
            return {
                'total_games': total_games,
                'status_counts': status_counts,
                'season_type_counts': season_type_counts
            }
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(description='NBA Schedule and Scores Collector')
    parser.add_argument('--season', help='NBA season (e.g., 2024-25)')
    parser.add_argument('--date', help='Date in YYYY-MM-DD format')
    parser.add_argument('--full-schedule', action='store_true', help='Download full season schedule')
    parser.add_argument('--scores', action='store_true', help='Get live scores')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    
    args = parser.parse_args()
    
    collector = NBAScheduleCollector()
    
    if args.stats:
        stats = collector.get_database_stats()
        print(f"Database Statistics:")
        print(f"Total games: {stats.get('total_games', 0)}")
        print(f"Status counts: {stats.get('status_counts', {})}")
        print(f"Season type counts: {stats.get('season_type_counts', {})}")
    
    elif args.date:
        games = collector.get_games_by_date(args.date)
        print(f"Games for {args.date}: {len(games)}")
        for game in games:
            print(f"  {game['away_team_name']} @ {game['home_team_name']} - {game['game_status']}")
    
    elif args.scores:
        live_games = collector.get_live_games()
        print(f"Live games: {len(live_games)}")
        for game in live_games:
            print(f"  {game['away_team_name']} {game['away_score']} @ {game['home_team_name']} {game['home_score']} - {game['game_status_text']}")
    
    else:
        print("Use --help for usage information")


if __name__ == "__main__":
    main()
