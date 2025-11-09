#!/usr/bin/env python3
"""
Test script for Stadium Image Fetcher

This script performs basic tests and validation before running the main fetcher.
"""

import os
import csv
import sys
from fetch_stadium_images import StadiumImageFetcher

def test_csv_files():
    """Test if all required CSV files exist and are readable"""
    required_files = ['info-teams.csv', 'info-stadiums.csv', 'info-leagues.csv']
    
    print("🧪 Testing CSV file availability...")
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Missing required file: {file}")
            return False
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                row_count = sum(1 for _ in reader)
                print(f"✅ {file}: {row_count} rows")
        except Exception as e:
            print(f"❌ Error reading {file}: {e}")
            return False
    
    return True

def test_dependencies():
    """Test if all required dependencies are available"""
    print("\n🧪 Testing dependencies...")
    
    try:
        import requests
        print("✅ requests library available")
    except ImportError:
        print("❌ requests library not found. Install with: pip install requests")
        return False
    
    try:
        from PIL import Image
        print("✅ Pillow (PIL) library available")
    except ImportError:
        print("❌ Pillow library not found. Install with: pip install Pillow")
        return False
    
    return True

def test_data_loading():
    """Test data loading functionality"""
    print("\n🧪 Testing data loading...")
    
    try:
        fetcher = StadiumImageFetcher()
        teams, stadiums, leagues = fetcher.load_data()
        
        if not teams:
            print("❌ No teams data loaded")
            return False
        
        if not stadiums:
            print("❌ No stadiums data loaded")
            return False
        
        if not leagues:
            print("❌ No leagues data loaded")
            return False
        
        print(f"✅ Loaded {len(teams)} teams, {len(stadiums)} stadiums, {len(leagues)} leagues")
        
        # Test stadium mapping
        stadium_mapping = fetcher.get_stadium_team_mapping(teams, stadiums, leagues)
        print(f"✅ Created mapping for {len(stadium_mapping)} unique stadiums")
        
        # Show breakdown by league
        league_counts = {}
        for stadium_data in stadium_mapping.values():
            league = stadium_data['league']
            league_counts[league] = league_counts.get(league, 0) + 1
        
        print("📊 Stadiums per league:")
        for league, count in sorted(league_counts.items()):
            print(f"   {league.upper()}: {count} stadiums")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during data loading test: {e}")
        return False

def test_directory_creation():
    """Test directory creation"""
    print("\n🧪 Testing directory creation...")
    
    try:
        fetcher = StadiumImageFetcher()
        test_leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl']
        
        for league in test_leagues:
            league_dir = os.path.join(fetcher.base_dir, league)
            os.makedirs(league_dir, exist_ok=True)
            
            if os.path.exists(league_dir):
                print(f"✅ Created directory: {league_dir}")
            else:
                print(f"❌ Failed to create directory: {league_dir}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error during directory creation test: {e}")
        return False

def show_sample_stadiums():
    """Show a sample of stadiums that will be processed"""
    print("\n📋 Sample stadiums to be processed:")
    
    try:
        fetcher = StadiumImageFetcher()
        teams, stadiums, leagues = fetcher.load_data()
        stadium_mapping = fetcher.get_stadium_team_mapping(teams, stadiums, leagues)
        
        # Show first 3 stadiums from each league
        league_samples = {}
        for stadium_data in stadium_mapping.values():
            league = stadium_data['league']
            if league not in league_samples:
                league_samples[league] = []
            if len(league_samples[league]) < 3:
                league_samples[league].append(stadium_data)
        
        for league in sorted(league_samples.keys()):
            print(f"\n{league.upper()}:")
            for i, stadium_data in enumerate(league_samples[league], 1):
                stadium = stadium_data['stadium']
                teams_list = [team['real_team_name'] for team in stadium_data['teams']]
                clean_name = fetcher.clean_stadium_name(stadium['full_stadium_name'])
                print(f"  {i}. {stadium['full_stadium_name']}")
                print(f"     File: {clean_name}_img.png")
                print(f"     Teams: {', '.join(teams_list)}")
        
    except Exception as e:
        print(f"❌ Error showing sample stadiums: {e}")

def main():
    """Main test function"""
    print("🏟️  Stadium Image Fetcher - Test Suite")
    print("=" * 50)
    
    # Run all tests
    tests = [
        ("CSV Files", test_csv_files),
        ("Dependencies", test_dependencies),
        ("Data Loading", test_data_loading),
        ("Directory Creation", test_directory_creation)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        if not test_func():
            all_passed = False
            print(f"\n❌ {test_name} test FAILED!")
            break
        else:
            print(f"✅ {test_name} test PASSED!")
    
    if all_passed:
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 50)
        
        show_sample_stadiums()
        
        print("\n" + "=" * 50)
        print("🚀 Ready to run the main script!")
        print("Run: python fetch_stadium_images.py")
        print("=" * 50)
        
        return 0
    else:
        print("\n" + "=" * 50)
        print("❌ TESTS FAILED!")
        print("Please fix the issues above before running the main script.")
        print("=" * 50)
        return 1

if __name__ == "__main__":
    sys.exit(main())