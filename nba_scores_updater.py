#!/usr/bin/env python3
"""
NBA Scores Updater

This script fetches live NBA scores and updates the database with current game information.
It updates game status, scores, period information, and determines winners.

Usage:
    python nba_scores_updater.py
    python nba_scores_updater.py --date 2024-12-15
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


class NBAScoresUpdater:
    """NBA scores updater for live game data."""
    
    def __init__(self):
        """Initialize the NBA scores updater."""
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
    
    def fetch_live_scores(self, date: Optional[str] = None) -> List[Dict]:
        """
        Fetch live NBA scores from the API.
        
        Args:
            date: Date in YYYY-MM-DD format (optional, defaults to today)
            
        Returns:
            List of game dictionaries with live data
        """
        try:
            from nba_api.live.nba.endpoints import ScoreBoard
            
            logger.info(f"Fetching live scores for {date or 'today'}")
            
            # Use NBA API to get scoreboard
            scoreboard = ScoreBoard()
            data = scoreboard.get_json()
            
            # Parse JSON string response
            if isinstance(data, str):
                data = json.loads(data)
            
            games = []
            
            # Parse the response
            if 'scoreboard' in data and 'gameDate' in data['scoreboard']:
                game_date = data['scoreboard']['gameDate']
                games_data = data['scoreboard'].get('games', [])
                
                for game_data in games_data:
                    game = {
                        'GAME_ID': str(game_data.get('gameId', '')),
                        'GAME_DATE': game_date,
                        'HOME_TEAM_ID': game_data.get('homeTeam', {}).get('teamId'),
                        'VISITOR_TEAM_ID': game_data.get('awayTeam', {}).get('teamId'),
                        'HOME_TEAM_SCORE': game_data.get('homeTeam', {}).get('score', 0),
                        'VISITOR_TEAM_SCORE': game_data.get('awayTeam', {}).get('score', 0),
                        'GAME_STATUS_TEXT': game_data.get('gameStatusText', ''),
                        'PERIOD': game_data.get('period', 0),
                        'PERIOD_TIME_REMAINING': game_data.get('gameClock', '')
                    }
                    games.append(game)
            
            logger.info(f"Fetched {len(games)} games for {date or 'today'}")
            return games
            
        except Exception as e:
            logger.error(f"Error fetching live scores: {e}")
            return []
    
    def get_games_to_update(self, date: Optional[str] = None) -> List[Dict]:
        """
        Get games from database that need score updates.
        
        Args:
            date: Date in YYYY-MM-DD format (optional, defaults to today)
            
        Returns:
            List of games that need updates
        """
        conn = self.get_db_connection()
        if not conn:
            return []
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if date:
                cursor.execute("""
                    SELECT * FROM nba_games 
                    WHERE game_date = %s 
                    AND game_status IN ('scheduled', 'live', 'in-progress')
                    ORDER BY game_time_est
                """, (date,))
            else:
                cursor.execute("""
                    SELECT * FROM nba_games 
                    WHERE game_date = CURRENT_DATE 
                    AND game_status IN ('scheduled', 'live', 'in-progress')
                    ORDER BY game_time_est
                """)
            
            games = cursor.fetchall()
            return [dict(game) for game in games]
            
        except Exception as e:
            logger.error(f"Error getting games to update: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    def update_game_scores(self, api_games: List[Dict], db_games: List[Dict]) -> int:
        """
        Update game scores in the database.
        
        Args:
            api_games: Games from NBA API with live data
            db_games: Games from database
            
        Returns:
            Number of games updated
        """
        if not api_games or not db_games:
            return 0
        
        # Create mapping of API games by game ID
        api_games_map = {str(game.get('GAME_ID', '')): game for game in api_games}
        
        conn = self.get_db_connection()
        if not conn:
            return 0
        
        try:
            cursor = conn.cursor()
            updated_count = 0
            
            for db_game in db_games:
                game_id = db_game['game_id']
                api_game = api_games_map.get(game_id)
                
                if not api_game:
                    continue
                
                try:
                    # Extract live data from API
                    home_score = api_game.get('HOME_TEAM_SCORE', 0)
                    away_score = api_game.get('VISITOR_TEAM_SCORE', 0)
                    game_status = api_game.get('GAME_STATUS_TEXT', 'scheduled')
                    period = api_game.get('PERIOD', 0)
                    period_time = api_game.get('PERIOD_TIME_REMAINING', '')
                    
                    # Determine game status
                    if game_status == 'Final':
                        game_status = 'final'
                        winner_team_id = db_game['home_team_id'] if home_score > away_score else db_game['away_team_id']
                    elif 'Q' in game_status or 'OT' in game_status:
                        game_status = 'live'
                        winner_team_id = None
                    else:
                        game_status = 'scheduled'
                        winner_team_id = None
                    
                    # Update the game
                    cursor.execute("""
                        UPDATE nba_games SET
                            home_score = %s,
                            away_score = %s,
                            game_status = %s,
                            game_status_text = %s,
                            current_period = %s,
                            period_time_remaining = %s,
                            winner_team_id = %s,
                            updated_at = %s
                        WHERE game_id = %s
                    """, (
                        home_score, away_score, game_status, game_status,
                        period, period_time, winner_team_id, datetime.now(), game_id
                    ))
                    
                    updated_count += 1
                    
                    logger.info(f"Updated game {game_id}: {db_game.get('away_team_name', 'Away')} {away_score} @ {db_game.get('home_team_name', 'Home')} {home_score} - {game_status}")
                    
                except Exception as e:
                    logger.error(f"Error updating game {game_id}: {e}")
                    continue
            
            conn.commit()
            logger.info(f"Successfully updated {updated_count} games")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating game scores: {e}")
            conn.rollback()
            return 0
        finally:
            cursor.close()
            conn.close()
    
    def update_scores_for_date(self, date: Optional[str] = None) -> int:
        """
        Update scores for all games on a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format (optional, defaults to today)
            
        Returns:
            Number of games updated
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Updating scores for {date}")
        
        # Get games from database
        db_games = self.get_games_to_update(date)
        if not db_games:
            logger.info(f"No games found for {date}")
            return 0
        
        # Fetch live data from API
        api_games = self.fetch_live_scores(date)
        if not api_games:
            logger.warning(f"No live data available for {date}")
            return 0
        
        # Update scores
        updated_count = self.update_game_scores(api_games, db_games)
        
        return updated_count
    
    def get_live_games_summary(self) -> Dict:
        """
        Get summary of live games.
        
        Returns:
            Dictionary with live games summary
        """
        conn = self.get_db_connection()
        if not conn:
            return {}
        
        try:
            from psycopg2.extras import RealDictCursor
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get live games
            cursor.execute("""
                SELECT g.*, 
                       ht.real_team_name as home_team_name,
                       at.real_team_name as away_team_name
                FROM nba_games g
                LEFT JOIN teams ht ON g.home_team_id = ht.team_id
                LEFT JOIN teams at ON g.away_team_id = at.team_id
                WHERE g.game_status = 'live'
                ORDER BY g.game_date, g.game_time_est
            """)
            
            live_games = cursor.fetchall()
            
            # Get today's games count
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM nba_games 
                WHERE game_date = CURRENT_DATE
            """)
            today_games = cursor.fetchone()['count']
            
            # Get final games count for today
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM nba_games 
                WHERE game_date = CURRENT_DATE 
                AND game_status = 'final'
            """)
            final_games = cursor.fetchone()['count']
            
            return {
                'live_games': [dict(game) for game in live_games],
                'today_total': today_games,
                'today_final': final_games,
                'live_count': len(live_games)
            }
            
        except Exception as e:
            logger.error(f"Error getting live games summary: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(description='NBA Scores Updater')
    parser.add_argument('--date', help='Date in YYYY-MM-DD format (defaults to today)')
    parser.add_argument('--summary', action='store_true', help='Show live games summary')
    
    args = parser.parse_args()
    
    updater = NBAScoresUpdater()
    
    if args.summary:
        summary = updater.get_live_games_summary()
        print(f"Live Games Summary:")
        print(f"Live games: {summary.get('live_count', 0)}")
        print(f"Today's total games: {summary.get('today_total', 0)}")
        print(f"Today's final games: {summary.get('today_final', 0)}")
        
        live_games = summary.get('live_games', [])
        if live_games:
            print("\nLive Games:")
            for game in live_games:
                print(f"  {game['away_team_name']} {game['away_score']} @ {game['home_team_name']} {game['home_score']} - {game['game_status_text']}")
    
    else:
        updated_count = updater.update_scores_for_date(args.date)
        print(f"Updated {updated_count} games")


if __name__ == "__main__":
    main()
