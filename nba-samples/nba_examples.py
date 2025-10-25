#!/usr/bin/env python3
"""
NBA Data Collection Examples

This script demonstrates how to use the NBA schedule collector and analysis tools
to make decisions about data storage strategies.
"""

import sys
import os
from datetime import datetime, timedelta

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from nba_schedule_collector import NBAScheduleCollector
from nba_storage_analysis import NBADatabaseAnalysis


def example_basic_usage():
    """Demonstrate basic usage of NBA schedule collector."""
    print("🏀 NBA Schedule Collector - Basic Usage Example")
    print("=" * 50)
    
    # Initialize collector
    collector = NBAScheduleCollector()
    
    # Get today's games
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n📅 Getting games for today ({today}):")
    
    games = collector.get_live_scores(today)
    
    if games:
        for game in games:
            home_team = f"{game['home_team_city']} {game['home_team_name']}"
            away_team = f"{game['away_team_city']} {game['away_team_name']}"
            status = game['game_status_text'] or game['game_status']
            season_type = game['season_type']
            
            print(f"  {away_team} @ {home_team}")
            print(f"    Status: {status}")
            print(f"    Season Type: {season_type}")
            
            if game['home_score'] > 0 or game['away_score'] > 0:
                print(f"    Score: {away_team} {game['away_score']} - {game['home_score']} {home_team}")
            print()
    else:
        print("  No games found for today")
    
    # Show database stats
    print("\n📊 Database Statistics:")
    stats = collector.get_database_stats()
    print(f"  Total Games: {stats['total_games']}")
    print(f"  Database Size: {stats['db_size_mb']} MB")
    
    if stats['games_by_season']:
        print("  Games by Season:")
        for season, count in stats['games_by_season'].items():
            print(f"    {season}: {count} games")
    
    if stats['games_by_type']:
        print("  Games by Season Type:")
        for season_type, count in stats['games_by_type'].items():
            print(f"    {season_type}: {count} games")


def example_season_analysis():
    """Demonstrate season analysis for storage decisions."""
    print("\n\n🔍 NBA Storage Strategy Analysis")
    print("=" * 50)
    
    # Initialize analyzer
    analyzer = NBADatabaseAnalysis()
    
    # Get recommendation
    recommendation = analyzer.generate_recommendation("2024-25")
    print(recommendation)


def example_season_type_filtering():
    """Demonstrate filtering by season type."""
    print("\n\n🏆 NBA Season Type Filtering")
    print("=" * 50)
    
    collector = NBAScheduleCollector()
    
    # Get different season types
    season_types = ['preseason', 'regular_season', 'nba_cup', 'playoffs']
    season = "2024-25"
    
    for season_type in season_types:
        games = collector.get_games_by_season_type(season, season_type)
        print(f"\n{season_type.replace('_', ' ').title()}: {len(games)} games")
        
        if games:
            # Show first few games as examples
            for i, game in enumerate(games[:3]):
                home_team = f"{game['home_team_city']} {game['home_team_name']}"
                away_team = f"{game['away_team_city']} {game['away_team_name']}"
                print(f"  {i+1}. {away_team} @ {home_team} ({game['game_date']})")


def example_data_collection_workflow():
    """Demonstrate a complete data collection workflow."""
    print("\n\n🚀 Complete NBA Data Collection Workflow")
    print("=" * 50)
    
    collector = NBAScheduleCollector()
    
    # Step 1: Analyze current data needs
    print("Step 1: Analyzing data requirements...")
    analyzer = NBADatabaseAnalysis()
    volume_analysis = analyzer.analyze_data_volume("2024-25")
    
    print(f"  Season has {volume_analysis['total_games']} total games")
    print(f"  Estimated storage: {volume_analysis['sqlite_size_estimate_mb']} MB")
    
    # Step 2: Check if we need to collect data
    stats = collector.get_database_stats()
    print(f"\nStep 2: Current database status...")
    print(f"  Games in database: {stats['total_games']}")
    
    if stats['total_games'] < volume_analysis['total_games'] * 0.8:
        print("  ⚠️  Database is incomplete, collecting full season...")
        
        # Step 3: Collect full season (this would be done once)
        print("\nStep 3: Collecting full season schedule...")
        games = collector.get_season_schedule("2024-25")
        
        if games:
            stored = collector.store_games(games)
            print(f"  ✅ Stored {stored} games")
        else:
            print("  ❌ Failed to collect season schedule")
    else:
        print("  ✅ Database is up to date")
    
    # Step 4: Get current day data
    print("\nStep 4: Getting current day data...")
    today = datetime.now().strftime('%Y-%m-%d')
    today_games = collector.get_live_scores(today)
    
    if today_games:
        print(f"  Found {len(today_games)} games for today")
        
        # Show live scores
        for game in today_games:
            if game['game_status'] in ['in_progress', 'final']:
                home_team = f"{game['home_team_city']} {game['home_team_name']}"
                away_team = f"{game['away_team_city']} {game['away_team_name']}"
                print(f"    {away_team} {game['away_score']} - {game['home_score']} {home_team}")
    else:
        print("  No games scheduled for today")
    
    # Step 5: Show final stats
    print("\nStep 5: Final database statistics...")
    final_stats = collector.get_database_stats()
    print(f"  Total Games: {final_stats['total_games']}")
    print(f"  Database Size: {final_stats['db_size_mb']} MB")


def main():
    """Run all examples."""
    print("NBA Data Collection Examples")
    print("This script demonstrates various ways to collect and analyze NBA data")
    print("for making storage strategy decisions.\n")
    
    try:
        # Run examples
        example_basic_usage()
        example_season_analysis()
        example_season_type_filtering()
        example_data_collection_workflow()
        
        print("\n\n✅ All examples completed successfully!")
        print("\n💡 Next Steps:")
        print("1. Run the analysis script to get storage recommendations")
        print("2. Choose a storage strategy based on your needs")
        print("3. Implement the chosen strategy in your application")
        print("4. Monitor performance and adjust as needed")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure you have the required dependencies installed:")
        print("  - NBA API library")
        print("  - SQLite3")
        print("  - Required Python packages")


if __name__ == "__main__":
    main()
