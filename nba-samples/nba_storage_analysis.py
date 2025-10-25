#!/usr/bin/env python3
"""
NBA Database Storage Analysis

This script analyzes NBA data collection patterns to help decide whether to store
complete season schedules in SQLite database vs. fetching on-demand.

It provides:
1. Data volume analysis
2. API call frequency analysis  
3. Storage requirements estimation
4. Performance comparison recommendations
"""

import sys
import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import argparse

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.nba_data import NBADataFetcher
from utils.api_usage_tracker import APIUsageTracker


class NBADatabaseAnalysis:
    """Analyzes NBA data patterns for storage strategy decisions."""
    
    def __init__(self, db_path: str = "local/data/nba_schedule.db"):
        self.db_path = db_path
        self.fetcher = NBADataFetcher()
        self.api_tracker = APIUsageTracker()
    
    def analyze_data_volume(self, season: str = "2024-25") -> Dict:
        """
        Analyze NBA data volume for a season.
        
        Args:
            season: NBA season to analyze
            
        Returns:
            Dictionary with volume analysis
        """
        print(f"📊 Analyzing data volume for NBA season {season}")
        
        # Get sample schedule data
        try:
            schedule_data = self.fetcher.get_schedule()
            
            if not schedule_data:
                return {"error": "No schedule data available"}
            
            # Calculate estimates
            total_games = len(schedule_data)
            
            # Estimate data size per game (JSON)
            sample_game = schedule_data[0] if schedule_data else {}
            game_json_size = len(json.dumps(sample_game))
            
            # Calculate storage requirements
            total_json_size = total_games * game_json_size
            sqlite_size_estimate = total_games * 500  # Estimated SQLite row size
            
            # Season breakdown
            season_types = {}
            for game in schedule_data:
                game_date_str = game.get('gameDate', '')
                if game_date_str:
                    try:
                        game_date = datetime.strptime(game_date_str, '%m/%d/%Y')
                        month = game_date.month
                        
                        if month == 10:
                            season_type = 'preseason'
                        elif month in [11, 12, 1, 2, 3, 4]:
                            season_type = 'regular_season'
                        elif month in [5, 6]:
                            season_type = 'playoffs'
                        else:
                            season_type = 'off_season'
                        
                        season_types[season_type] = season_types.get(season_type, 0) + 1
                    except ValueError:
                        continue
            
            return {
                'total_games': total_games,
                'game_json_size_bytes': game_json_size,
                'total_json_size_mb': round(total_json_size / (1024 * 1024), 2),
                'sqlite_size_estimate_mb': round(sqlite_size_estimate / (1024 * 1024), 2),
                'season_types': season_types,
                'games_per_month': self._calculate_games_per_month(schedule_data)
            }
            
        except Exception as e:
            return {"error": f"Analysis failed: {e}"}
    
    def _calculate_games_per_month(self, schedule_data: List[Dict]) -> Dict:
        """Calculate games per month."""
        monthly_games = {}
        
        for game in schedule_data:
            game_date_str = game.get('gameDate', '')
            if game_date_str:
                try:
                    game_date = datetime.strptime(game_date_str, '%m/%d/%Y')
                    month_key = f"{game_date.year}-{game_date.month:02d}"
                    monthly_games[month_key] = monthly_games.get(month_key, 0) + 1
                except ValueError:
                    continue
        
        return monthly_games
    
    def analyze_api_usage_patterns(self) -> Dict:
        """
        Analyze API usage patterns for NBA data.
        
        Returns:
            Dictionary with API usage analysis
        """
        print("🔍 Analyzing API usage patterns")
        
        # Get API usage data
        try:
            api_usage = self.api_tracker.get_usage_summary()
            nba_usage = api_usage.get('nba', {})
            
            # Calculate patterns
            daily_calls = nba_usage.get('daily_calls', 0)
            hourly_calls = nba_usage.get('hourly_calls', 0)
            
            # Estimate API limits (NBA Stats API is generally free but has rate limits)
            estimated_daily_limit = 1000  # Conservative estimate
            estimated_hourly_limit = 100
            
            usage_percentage_daily = (daily_calls / estimated_daily_limit) * 100
            usage_percentage_hourly = (hourly_calls / estimated_hourly_limit) * 100
            
            return {
                'daily_calls': daily_calls,
                'hourly_calls': hourly_calls,
                'estimated_daily_limit': estimated_daily_limit,
                'estimated_hourly_limit': estimated_hourly_limit,
                'daily_usage_percentage': round(usage_percentage_daily, 2),
                'hourly_usage_percentage': round(usage_percentage_hourly, 2),
                'is_within_limits': usage_percentage_daily < 80 and usage_percentage_hourly < 80
            }
            
        except Exception as e:
            return {"error": f"API usage analysis failed: {e}"}
    
    def compare_storage_strategies(self, season: str = "2024-25") -> Dict:
        """
        Compare different storage strategies.
        
        Args:
            season: NBA season to analyze
            
        Returns:
            Dictionary with strategy comparison
        """
        print(f"⚖️  Comparing storage strategies for season {season}")
        
        volume_analysis = self.analyze_data_volume(season)
        api_analysis = self.analyze_api_usage_patterns()
        
        if "error" in volume_analysis or "error" in api_analysis:
            return {"error": "Analysis failed"}
        
        # Strategy 1: On-demand fetching
        on_demand_strategy = {
            'name': 'On-Demand Fetching',
            'storage_required_mb': 0,
            'api_calls_per_day': 3,  # Yesterday, today, tomorrow
            'api_calls_per_season': 3 * 365,  # Rough estimate
            'response_time': '2-5 seconds',
            'reliability': 'Medium (depends on API availability)',
            'maintenance': 'Low',
            'pros': [
                'No storage overhead',
                'Always fresh data',
                'No data synchronization issues'
            ],
            'cons': [
                'Slower response times',
                'API dependency',
                'Rate limiting concerns',
                'Network dependency'
            ]
        }
        
        # Strategy 2: Full season caching
        full_season_strategy = {
            'name': 'Full Season Caching',
            'storage_required_mb': volume_analysis['sqlite_size_estimate_mb'],
            'api_calls_per_day': 0,  # Only initial load
            'api_calls_per_season': 1,  # One-time season load
            'response_time': '< 100ms',
            'reliability': 'High (local data)',
            'maintenance': 'Medium (season updates)',
            'pros': [
                'Fast response times',
                'No API dependency for queries',
                'Offline capability',
                'Consistent performance'
            ],
            'cons': [
                'Storage overhead',
                'Data freshness concerns',
                'Initial load time',
                'Season transition complexity'
            ]
        }
        
        # Strategy 3: Hybrid approach
        hybrid_strategy = {
            'name': 'Hybrid Approach',
            'storage_required_mb': volume_analysis['sqlite_size_estimate_mb'] * 0.3,  # Cache recent data
            'api_calls_per_day': 1,  # Update current day
            'api_calls_per_season': 30,  # Periodic updates
            'response_time': '< 500ms',
            'reliability': 'High',
            'maintenance': 'Medium',
            'pros': [
                'Balanced approach',
                'Good performance',
                'Fresh data for current games',
                'Reduced API dependency'
            ],
            'cons': [
                'Complex implementation',
                'Cache invalidation logic',
                'Storage management'
            ]
        }
        
        # Calculate cost-benefit scores
        strategies = [on_demand_strategy, full_season_strategy, hybrid_strategy]
        
        for strategy in strategies:
            # Calculate score based on multiple factors
            score = 0
            
            # Response time score (lower is better)
            if strategy['response_time'] == '< 100ms':
                score += 30
            elif strategy['response_time'] == '< 500ms':
                score += 20
            else:
                score += 10
            
            # Reliability score
            if strategy['reliability'] == 'High':
                score += 25
            elif strategy['reliability'] == 'Medium':
                score += 15
            
            # Storage efficiency score (lower storage is better)
            if strategy['storage_required_mb'] < 10:
                score += 20
            elif strategy['storage_required_mb'] < 50:
                score += 15
            else:
                score += 10
            
            # API efficiency score (fewer calls is better)
            if strategy['api_calls_per_day'] == 0:
                score += 25
            elif strategy['api_calls_per_day'] <= 1:
                score += 20
            else:
                score += 10
            
            strategy['score'] = score
        
        return {
            'strategies': strategies,
            'recommendation': max(strategies, key=lambda x: x['score']),
            'analysis_data': {
                'volume': volume_analysis,
                'api_usage': api_analysis
            }
        }
    
    def generate_recommendation(self, season: str = "2024-25") -> str:
        """
        Generate a storage strategy recommendation.
        
        Args:
            season: NBA season to analyze
            
        Returns:
            Recommendation string
        """
        comparison = self.compare_storage_strategies(season)
        
        if "error" in comparison:
            return "❌ Analysis failed - unable to generate recommendation"
        
        recommendation = comparison['recommendation']
        volume_data = comparison['analysis_data']['volume']
        api_data = comparison['analysis_data']['api_usage']
        
        recommendation_text = f"""
🎯 NBA Storage Strategy Recommendation

Based on analysis of season {season}:

📊 Data Volume:
   • Total Games: {volume_data['total_games']:,}
   • Storage Required: {recommendation['storage_required_mb']} MB
   • Games by Type: {volume_data['season_types']}

🔌 API Usage:
   • Daily Calls: {api_data['daily_calls']}
   • Within Limits: {'✅ Yes' if api_data['is_within_limits'] else '⚠️  No'}

🏆 Recommended Strategy: {recommendation['name']}
   • Score: {recommendation['score']}/100
   • Response Time: {recommendation['response_time']}
   • Reliability: {recommendation['reliability']}

✅ Pros:
{chr(10).join(f'   • {pro}' for pro in recommendation['pros'])}

⚠️  Cons:
{chr(10).join(f'   • {con}' for con in recommendation['cons'])}

💡 Implementation Notes:
"""
        
        if recommendation['name'] == 'Full Season Caching':
            recommendation_text += f"""
   • Download complete season schedule once at season start
   • Store in SQLite database with proper indexing
   • Update scores/game status periodically
   • Consider archiving old seasons to manage storage
"""
        elif recommendation['name'] == 'Hybrid Approach':
            recommendation_text += f"""
   • Cache recent 30 days of games
   • Fetch current day data on-demand
   • Update cache daily with new games
   • Archive old data periodically
"""
        else:
            recommendation_text += f"""
   • Implement robust error handling for API failures
   • Add caching layer for frequently accessed data
   • Consider rate limiting and retry logic
   • Monitor API usage closely
"""
        
        return recommendation_text


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='NBA Database Storage Analysis')
    parser.add_argument('--season', default='2024-25', help='NBA season to analyze')
    parser.add_argument('--analysis', choices=['volume', 'api', 'compare', 'recommend'], 
                       default='recommend', help='Type of analysis to run')
    parser.add_argument('--output', help='Output file for results (JSON format)')
    
    args = parser.parse_args()
    
    analyzer = NBADatabaseAnalysis()
    
    if args.analysis == 'volume':
        result = analyzer.analyze_data_volume(args.season)
        print(json.dumps(result, indent=2))
    
    elif args.analysis == 'api':
        result = analyzer.analyze_api_usage_patterns()
        print(json.dumps(result, indent=2))
    
    elif args.analysis == 'compare':
        result = analyzer.compare_storage_strategies(args.season)
        print(json.dumps(result, indent=2))
    
    elif args.analysis == 'recommend':
        recommendation = analyzer.generate_recommendation(args.season)
        print(recommendation)
    
    if args.output:
        with open(args.output, 'w') as f:
            if args.analysis == 'recommend':
                f.write(recommendation)
            else:
                json.dump(result, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
