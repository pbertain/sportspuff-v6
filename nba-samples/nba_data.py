#!/usr/bin/env python3
"""
NBA Data Fetcher

This module provides data fetching functionality for NBA schedules, scores, and standings.
It uses the nba_api library to fetch data from the official NBA API.
"""

import sys
import os
import signal
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'dependencies', 'nba_api', 'src'))

from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import scoreboardv2, leaguestandingsv3, scheduleleaguev2
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class NBADataFetcher:
    """Fetches NBA data from the official NBA Stats API."""
    
    def __init__(self):
        """Initialize the NBA data fetcher."""
        pass
    
    def _timeout_handler(self, signum, frame):
        """Handle timeout for NBA API calls."""
        raise TimeoutError("NBA API call timed out")
    
    def _call_with_timeout(self, func, timeout_seconds=3):
        """Call a function with a timeout."""
        signal.signal(signal.SIGALRM, self._timeout_handler)
        signal.alarm(timeout_seconds)
        try:
            result = func()
            return result
        finally:
            signal.alarm(0)
    
    def get_season_info(self, games: List[Dict], date_obj: datetime) -> Tuple[str, int]:
        """
        Get NBA season type and week info from games data.
        
        Args:
            games: List of game dictionaries from the API
            date_obj: Date object for the query
            
        Returns:
            Tuple of (season_type, week_number)
        """
        if not games:
            return "Off Season", 0
        
        # Determine NBA season (e.g., "2024-25" for dates between Oct 2024 and June 2025)
        if date_obj.month >= 10:  # October onwards
            season = f"{date_obj.year}-{str(date_obj.year + 1)[-2:]}"
        else:  # January to September
            season = f"{date_obj.year - 1}-{str(date_obj.year)[-2:]}"
        
        # Determine season type based on month
        if date_obj.month in [10, 11, 12, 1, 2, 3, 4, 5, 6]:
            if date_obj.month in [10]:  # October
                season_type = "Preseason"
            elif date_obj.month in [11, 12, 1, 2, 3, 4]:  # November to April
                season_type = "Regular Season"
            elif date_obj.month in [5, 6]:  # May to June
                season_type = "Playoffs"
            else:
                season_type = "Regular Season"
        else:
            season_type = "Off Season"
        
        # Calculate week number from season start (October 1st)
        if date_obj.month >= 10:
            season_start = datetime(date_obj.year, 10, 1)
        else:
            season_start = datetime(date_obj.year - 1, 10, 1)
        
        days_since_start = (date_obj - season_start).days
        week_num = (days_since_start // 7) + 1
        week_num = max(1, week_num)
        
        return season_type, week_num
    
    def get_schedule(self, date: Optional[str] = None) -> List[Dict]:
        """
        Get NBA schedule for specified date or current games.
        
        Args:
            date: Date in YYYY-MM-DD format (optional)
            
        Returns:
            List of game dictionaries
        """
        try:
            # Determine the correct season based on the date
            if date:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                year = date_obj.year
                month = date_obj.month
            else:
                now = datetime.now()
                year = now.year
                month = now.month
            
            # NBA season spans two calendar years (e.g., 2024-25 runs Oct 2024 to June 2025)
            if month >= 10:  # October onwards
                season = f"{year}-{str(year + 1)[-2:]}"
            elif month <= 6:  # January to June (still previous season)
                season = f"{year - 1}-{str(year)[-2:]}"
            else:  # July to September (off season, use previous season)
                season = f"{year - 1}-{str(year)[-2:]}"
            
            # Get schedule for the determined season with timeout
            def get_schedule_data():
                schedule_data = scheduleleaguev2.ScheduleLeagueV2(season=season)
                return schedule_data.get_dict()
            
            data = self._call_with_timeout(get_schedule_data, timeout_seconds=15)
            
            if 'leagueSchedule' in data and 'gameDates' in data['leagueSchedule']:
                game_dates = data['leagueSchedule']['gameDates']
                
                if date is None:
                    # Get today's games
                    target_date = datetime.now().strftime('%m/%d/%Y')
                else:
                    # Convert YYYY-MM-DD to MM/DD/YYYY format
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    target_date = date_obj.strftime('%m/%d/%Y')
                
                # Find games for the specified date
                target_games = []
                for game_date in game_dates:
                    game_date_str = game_date.get('gameDate', '')
                    if game_date_str.startswith(target_date):
                        target_games.extend(game_date.get('games', []))
                
                return target_games
            else:
                return []
                
        except TimeoutError as e:
            print(f"NBA API timeout: {e}")
            return []
        except Exception as e:
            print(f"Error fetching NBA schedule: {e}")
            return []
    
    def get_scores(self, date: Optional[str] = None) -> List[Dict]:
        """
        Get NBA scores for specified date.
        
        Args:
            date: Date in YYYY-MM-DD format (optional)
            
        Returns:
            List of game dictionaries with scores
        """
        try:
            if date is None:
                # Try live scoreboard first for today with timeout
                def get_scoreboard_data():
                    scoreboard_data = scoreboard.ScoreBoard()
                    return scoreboard_data.get_dict()['scoreboard']['games']
                
                games = self._call_with_timeout(get_scoreboard_data, timeout_seconds=10)
                
                if games:
                    return games
            
            # Fallback to schedule for any date
            return self.get_schedule(date)
            
        except TimeoutError as e:
            print(f"NBA API timeout: {e}")
            return []
        except Exception as e:
            print(f"Error fetching NBA scores: {e}")
            return []
    
    def get_standings(self, date: Optional[str] = None) -> List[Dict]:
        """
        Get NBA standings.
        
        Args:
            date: Date in YYYY-MM-DD format (optional)
            
        Returns:
            List of team standings dictionaries
        """
        try:
            if date:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                year = date_obj.year
                month = date_obj.month
            else:
                now = datetime.now()
                year = now.year
                month = now.month
            
            # NBA season spans two calendar years (e.g., 2024-25 runs Oct 2024 to June 2025)
            if month >= 10:  # October onwards
                season = f"{year}-{str(year + 1)[-2:]}"
            elif month <= 6:  # January to June (still previous season)
                season = f"{year - 1}-{str(year)[-2:]}"
            else:  # July to September (off season, use previous season)
                season = f"{year - 1}-{str(year)[-2:]}"
            
            standings_data = leaguestandingsv3.LeagueStandingsV3(season=season, season_type='Regular Season')
            data = standings_data.get_dict()
            
            if 'resultSets' in data and data['resultSets']:
                standings = data['resultSets'][0]['rowSet']
                headers = data['resultSets'][0]['headers']
                
                # Create formatted standings list
                formatted_standings = []
                for team in standings:
                    # Find indices for key fields
                    team_city_idx = headers.index('TeamCity')
                    team_name_idx = headers.index('TeamName')
                    wins_idx = headers.index('WINS')
                    losses_idx = headers.index('LOSSES')
                    
                    team_city = team[team_city_idx]
                    team_name = team[team_name_idx]
                    wins = team[wins_idx]
                    losses = team[losses_idx]
                    
                    formatted_team = {
                        'team': f"{team_city} {team_name}",
                        'wins': int(wins),
                        'losses': int(losses),
                        'ties': 0,  # NBA doesn't have ties
                        'pct': self._calculate_pct(wins, losses, 0),
                        'gb': 0.0,  # Games back calculation would need more complex logic
                        'division': '',  # Would need to determine from team
                        'conference': '',  # Would need to determine from team
                        'team_city': team_city,
                        'team_name': team_name
                    }
                    formatted_standings.append(formatted_team)
                
                return formatted_standings
            else:
                return []
        except Exception as e:
            print(f"Error fetching NBA standings: {e}")
            return []
    
    def _calculate_pct(self, wins: int, losses: int, ties: int) -> float:
        """Calculate winning percentage."""
        total_games = wins + losses + ties
        if total_games == 0:
            return 0.0
        return (wins + (ties * 0.5)) / total_games
    
    def get_team_record(self, team_name: str, standings: Dict) -> str:
        """
        Get team record from standings data.
        
        Args:
            team_name: Name of the team
            standings: Standings data from API
            
        Returns:
            Formatted record string (e.g., "[ 85- 77]")
        """
        if not standings:
            return "[  0-  0]"
        
        # standings is now a dictionary of team records
        return standings.get(team_name, "[  0-  0]")
