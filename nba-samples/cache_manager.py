#!/usr/bin/env python3
"""
Cache Manager for Sportspuff

Handles data caching using SQLite for efficient storage and retrieval.
Supports games, standings, and API usage tracking.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CacheManager:
    """Manages data caching using SQLite database."""
    
    def __init__(self, db_path: str = "local/data/sportspuff.db"):
        """
        Initialize the cache manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Games table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL,
                    game_date DATE NOT NULL,
                    home_team TEXT NOT NULL,
                    away_team TEXT NOT NULL,
                    home_score INTEGER DEFAULT 0,
                    away_score INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'scheduled',
                    period TEXT,
                    game_time TEXT,
                    season_type TEXT,
                    week INTEGER,
                    series_info TEXT,
                    current_inning INTEGER,
                    inning_state TEXT,
                    period_descriptor TEXT,
                    clock_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add new columns if they don't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN current_inning INTEGER")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN inning_state TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
                
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN period_descriptor TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
                
            try:
                cursor.execute("ALTER TABLE games ADD COLUMN clock_info TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Standings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sport TEXT NOT NULL,
                    team TEXT NOT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    ties INTEGER DEFAULT 0,
                    pct REAL DEFAULT 0.0,
                    gb REAL DEFAULT 0.0,
                    division TEXT,
                    conference TEXT,
                    season TEXT,
                    season_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # API usage tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    calls_made INTEGER DEFAULT 1,
                    date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Cache metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def cache_games(self, sport: str, games: List[Dict], game_date: str) -> None:
        """
        Cache games data.
        
        Args:
            sport: Sport name (mlb, nba, nfl, wnba, nhl)
            games: List of game dictionaries
            game_date: Date in YYYY-MM-DD format
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear existing games for this sport and date to prevent duplicates
            cursor.execute("DELETE FROM games WHERE sport = ? AND game_date = ?", (sport, game_date))
            
            for game in games:
                # Map different field names to standard format
                if sport.lower() == 'nba':
                    # NBA has nested team objects
                    home_team_obj = game.get('homeTeam', {})
                    away_team_obj = game.get('awayTeam', {})
                    home_team = f"{home_team_obj.get('teamCity', '')} {home_team_obj.get('teamName', '')}".strip()
                    away_team = f"{away_team_obj.get('teamCity', '')} {away_team_obj.get('teamName', '')}".strip()
                    home_score = home_team_obj.get('score', 0)
                    away_score = away_team_obj.get('score', 0)
                    status = game.get('gameStatusText', 'scheduled')
                    game_time = game.get('gameTimeEst', '')
                    game_id = game.get('gameId', f"{sport}_{game_date}_{home_team}_{away_team}")
                else:
                    # Other sports use standard field names
                    home_team = game.get('home_team') or game.get('home_name') or game.get('home') or ''
                    away_team = game.get('away_team') or game.get('away_name') or game.get('away') or ''
                    home_score = game.get('home_score', 0)
                    away_score = game.get('away_score', 0)
                    status = game.get('status', 'scheduled')
                    game_time = game.get('game_time') or game.get('game_datetime', '')
                    game_id = game.get('id') or game.get('game_id') or f"{sport}_{game_date}_{home_team}_{away_team}"
                
                cursor.execute("""
                    INSERT OR REPLACE INTO games 
                    (id, sport, game_date, home_team, away_team, home_score, away_score, 
                     status, period, game_time, season_type, week, series_info, 
                     current_inning, inning_state, period_descriptor, clock_info, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_id,
                    sport,
                    game_date,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    status,
                    game.get('period', ''),
                    game_time,
                    game.get('season_type', ''),
                    game.get('week', 0),
                    json.dumps(game.get('series_info', {})),
                    game.get('current_inning'),
                    game.get('inning_state'),
                    json.dumps(game.get('periodDescriptor', {})),
                    json.dumps(game.get('clock', {})),
                    datetime.now().isoformat()
                ))
            
            conn.commit()
            logger.info(f"Cached {len(games)} {sport.upper()} games for {game_date}")
    
    def cache_standings(self, sport: str, standings: List[Dict], season: str, season_type: str = 'regular') -> None:
        """
        Cache standings data.
        
        Args:
            sport: Sport name
            standings: List of team standings
            season: Season year
            season_type: Type of season (regular, playoff, preseason)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clear old standings for this sport/season
            cursor.execute("""
                DELETE FROM standings 
                WHERE sport = ? AND season = ? AND season_type = ?
            """, (sport, season, season_type))
            
            for team in standings:
                cursor.execute("""
                    INSERT INTO standings 
                    (sport, team, wins, losses, ties, pct, gb, division, conference, season, season_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sport,
                    team.get('team', ''),
                    team.get('wins', 0),
                    team.get('losses', 0),
                    team.get('ties', 0),
                    team.get('pct', 0.0),
                    team.get('gb', 0.0),
                    team.get('division', ''),
                    team.get('conference', ''),
                    season,
                    season_type
                ))
            
            conn.commit()
            logger.info(f"Cached {len(standings)} {sport.upper()} standings for {season} {season_type}")
    
    def get_games(self, sport: str, game_date: str) -> List[Dict]:
        """
        Get cached games for a specific sport and date.
        
        Args:
            sport: Sport name
            game_date: Date in YYYY-MM-DD format
            
        Returns:
            List of game dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM games 
                WHERE sport = ? AND game_date = ? 
                AND home_team != '' AND away_team != ''
                ORDER BY game_time
            """, (sport, game_date))
            
            games = []
            for row in cursor.fetchall():
                game = dict(row)
                if game.get('series_info'):
                    game['series_info'] = json.loads(game['series_info'])
                if game.get('period_descriptor'):
                    game['periodDescriptor'] = json.loads(game['period_descriptor'])
                if game.get('clock_info'):
                    game['clock'] = json.loads(game['clock_info'])
                games.append(game)
            
            return games
    
    def get_standings(self, sport: str, season: str, season_type: str = 'regular') -> List[Dict]:
        """
        Get cached standings for a specific sport and season.
        
        Args:
            sport: Sport name
            season: Season year
            season_type: Type of season
            
        Returns:
            List of standings dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM standings 
                WHERE sport = ? AND season = ? AND season_type = ?
                ORDER BY wins DESC, pct DESC
            """, (sport, season, season_type))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def is_data_fresh(self, sport: str, data_type: str, max_age_minutes: int = 30) -> bool:
        """
        Check if cached data is fresh enough.
        
        Args:
            sport: Sport name
            data_type: Type of data (games, standings)
            max_age_minutes: Maximum age in minutes
            
        Returns:
            True if data is fresh, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if data_type == 'games':
                cursor.execute("""
                    SELECT MAX(updated_at) FROM games WHERE sport = ?
                """, (sport,))
            elif data_type == 'standings':
                cursor.execute("""
                    SELECT MAX(created_at) FROM standings WHERE sport = ?
                """, (sport,))
            else:
                return False
            
            result = cursor.fetchone()
            if not result or not result[0]:
                return False
            
            last_update = datetime.fromisoformat(result[0])
            age = datetime.now() - last_update
            
            return age.total_seconds() < (max_age_minutes * 60)
    
    def record_api_call(self, service: str, endpoint: str, calls: int = 1) -> None:
        """
        Record API call usage.
        
        Args:
            service: API service name
            endpoint: API endpoint called
            calls: Number of calls made
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            cursor.execute("""
                INSERT INTO api_usage (service, endpoint, calls_made, date)
                VALUES (?, ?, ?, ?)
            """, (service, endpoint, calls, today))
            
            conn.commit()
    
    def purge_old_data(self, days_to_keep: int = 7) -> None:
        """
        Purge old data to prevent database bloat.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Purge old games
            cursor.execute("DELETE FROM games WHERE game_date < ?", (cutoff_date,))
            games_deleted = cursor.rowcount
            
            # Purge old API usage records
            cursor.execute("DELETE FROM api_usage WHERE date < ?", (cutoff_date,))
            usage_deleted = cursor.rowcount
            
            conn.commit()
            logger.info(f"Purged {games_deleted} old games and {usage_deleted} old API usage records")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get total games count
            cursor.execute("SELECT COUNT(*) FROM games")
            total_games = cursor.fetchone()[0]
            
            # Get games by sport
            cursor.execute("SELECT sport, COUNT(*) FROM games GROUP BY sport")
            games_by_sport = dict(cursor.fetchall())
            
            # Get date range
            cursor.execute("SELECT MIN(game_date), MAX(game_date) FROM games")
            date_range = cursor.fetchone()
            
            # Get database size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'total_games': total_games,
                'games_by_sport': games_by_sport,
                'date_range': date_range,
                'db_size_mb': round(db_size / (1024 * 1024), 2)
            }

    def get_api_usage_today(self, service: str) -> int:
        """
        Get today's API usage for a service.
        
        Args:
            service: API service name
            
        Returns:
            Number of calls made today
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            cursor.execute("""
                SELECT SUM(calls_made) FROM api_usage 
                WHERE service = ? AND date = ?
            """, (service, today))
            
            result = cursor.fetchone()
            return result[0] or 0
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """
        Clean up old cached data.
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Clean up old games
            cursor.execute("""
                DELETE FROM games WHERE game_date < ?
            """, (cutoff_date,))
            
            # Clean up old API usage
            cursor.execute("""
                DELETE FROM api_usage WHERE date < ?
            """, (cutoff_date,))
            
            conn.commit()
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
