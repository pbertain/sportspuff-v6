#!/usr/bin/env python3
"""
Comprehensive team mapping fix - handles ID mismatches between CSV files
This script creates proper mappings based on team names and league context
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    """Get database connection using environment variables"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'sportspuff_v6'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD')
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def create_comprehensive_mappings():
    """Create comprehensive team mappings based on known team-division relationships"""
    
    # Manual mappings based on known team-division relationships
    team_mappings = {
        # MLB Teams
        'Baltimore Orioles': {'league_id': 1, 'division_name': 'East', 'conference_name': 'AL'},
        'Boston Red Sox': {'league_id': 1, 'division_name': 'East', 'conference_name': 'AL'},
        'New York Yankees': {'league_id': 1, 'division_name': 'East', 'conference_name': 'AL'},
        'Tampa Bay Rays': {'league_id': 1, 'division_name': 'East', 'conference_name': 'AL'},
        'Toronto Blue Jays': {'league_id': 1, 'division_name': 'East', 'conference_name': 'AL'},
        
        'Chicago White Sox': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'AL'},
        'Cleveland Guardians': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'AL'},
        'Detroit Tigers': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'AL'},
        'Kansas City Royals': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'AL'},
        'Minnesota Twins': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'AL'},
        
        'Houston Astros': {'league_id': 1, 'division_name': 'West', 'conference_name': 'AL'},
        'Los Angeles Angels': {'league_id': 1, 'division_name': 'West', 'conference_name': 'AL'},
        'Oakland Athletics': {'league_id': 1, 'division_name': 'West', 'conference_name': 'AL'},
        'Seattle Mariners': {'league_id': 1, 'division_name': 'West', 'conference_name': 'AL'},
        'Texas Rangers': {'league_id': 1, 'division_name': 'West', 'conference_name': 'AL'},
        
        'Atlanta Braves': {'league_id': 1, 'division_name': 'East', 'conference_name': 'NL'},
        'Miami Marlins': {'league_id': 1, 'division_name': 'East', 'conference_name': 'NL'},
        'New York Mets': {'league_id': 1, 'division_name': 'East', 'conference_name': 'NL'},
        'Philadelphia Phillies': {'league_id': 1, 'division_name': 'East', 'conference_name': 'NL'},
        'Washington Nationals': {'league_id': 1, 'division_name': 'East', 'conference_name': 'NL'},
        
        'Chicago Cubs': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'NL'},
        'Cincinnati Reds': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'NL'},
        'Milwaukee Brewers': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'NL'},
        'Pittsburgh Pirates': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'NL'},
        'St. Louis Cardinals': {'league_id': 1, 'division_name': 'Central', 'conference_name': 'NL'},
        
        'Arizona Diamondbacks': {'league_id': 1, 'division_name': 'West', 'conference_name': 'NL'},
        'Colorado Rockies': {'league_id': 1, 'division_name': 'West', 'conference_name': 'NL'},
        'Los Angeles Dodgers': {'league_id': 1, 'division_name': 'West', 'conference_name': 'NL'},
        'San Diego Padres': {'league_id': 1, 'division_name': 'West', 'conference_name': 'NL'},
        'San Francisco Giants': {'league_id': 1, 'division_name': 'West', 'conference_name': 'NL'},
        
        # NFL Teams - AFC
        'Buffalo Bills': {'league_id': 4, 'division_name': 'East', 'conference_name': 'AFC'},
        'Miami Dolphins': {'league_id': 4, 'division_name': 'East', 'conference_name': 'AFC'},
        'New England Patriots': {'league_id': 4, 'division_name': 'East', 'conference_name': 'AFC'},
        'New York Jets': {'league_id': 4, 'division_name': 'East', 'conference_name': 'AFC'},
        
        'Baltimore Ravens': {'league_id': 4, 'division_name': 'North', 'conference_name': 'AFC'},
        'Cincinnati Bengals': {'league_id': 4, 'division_name': 'North', 'conference_name': 'AFC'},
        'Cleveland Browns': {'league_id': 4, 'division_name': 'North', 'conference_name': 'AFC'},
        'Pittsburgh Steelers': {'league_id': 4, 'division_name': 'North', 'conference_name': 'AFC'},
        
        'Houston Texans': {'league_id': 4, 'division_name': 'South', 'conference_name': 'AFC'},
        'Indianapolis Colts': {'league_id': 4, 'division_name': 'South', 'conference_name': 'AFC'},
        'Jacksonville Jaguars': {'league_id': 4, 'division_name': 'South', 'conference_name': 'AFC'},
        'Tennessee Titans': {'league_id': 4, 'division_name': 'South', 'conference_name': 'AFC'},
        
        'Denver Broncos': {'league_id': 4, 'division_name': 'West', 'conference_name': 'AFC'},
        'Kansas City Chiefs': {'league_id': 4, 'division_name': 'West', 'conference_name': 'AFC'},
        'Las Vegas Raiders': {'league_id': 4, 'division_name': 'West', 'conference_name': 'AFC'},
        'Los Angeles Chargers': {'league_id': 4, 'division_name': 'West', 'conference_name': 'AFC'},
        
        # NFL Teams - NFC
        'Dallas Cowboys': {'league_id': 4, 'division_name': 'East', 'conference_name': 'NFC'},
        'New York Giants': {'league_id': 4, 'division_name': 'East', 'conference_name': 'NFC'},
        'Philadelphia Eagles': {'league_id': 4, 'division_name': 'East', 'conference_name': 'NFC'},
        'Washington Commanders': {'league_id': 4, 'division_name': 'East', 'conference_name': 'NFC'},
        
        'Chicago Bears': {'league_id': 4, 'division_name': 'North', 'conference_name': 'NFC'},
        'Detroit Lions': {'league_id': 4, 'division_name': 'North', 'conference_name': 'NFC'},
        'Green Bay Packers': {'league_id': 4, 'division_name': 'North', 'conference_name': 'NFC'},
        'Minnesota Vikings': {'league_id': 4, 'division_name': 'North', 'conference_name': 'NFC'},
        
        'Atlanta Falcons': {'league_id': 4, 'division_name': 'South', 'conference_name': 'NFC'},
        'Carolina Panthers': {'league_id': 4, 'division_name': 'South', 'conference_name': 'NFC'},
        'New Orleans Saints': {'league_id': 4, 'division_name': 'South', 'conference_name': 'NFC'},
        'Tampa Bay Buccaneers': {'league_id': 4, 'division_name': 'South', 'conference_name': 'NFC'},
        
        'Arizona Cardinals': {'league_id': 4, 'division_name': 'West', 'conference_name': 'NFC'},
        'Los Angeles Rams': {'league_id': 4, 'division_name': 'West', 'conference_name': 'NFC'},
        'San Francisco 49ers': {'league_id': 4, 'division_name': 'West', 'conference_name': 'NFC'},
        'Seattle Seahawks': {'league_id': 4, 'division_name': 'West', 'conference_name': 'NFC'},
        
        # NBA Teams - Eastern Conference
        'Boston Celtics': {'league_id': 3, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Brooklyn Nets': {'league_id': 3, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'New York Knicks': {'league_id': 3, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Philadelphia 76ers': {'league_id': 3, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Toronto Raptors': {'league_id': 3, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        
        'Chicago Bulls': {'league_id': 3, 'division_name': 'Central', 'conference_name': 'Eastern'},
        'Cleveland Cavaliers': {'league_id': 3, 'division_name': 'Central', 'conference_name': 'Eastern'},
        'Detroit Pistons': {'league_id': 3, 'division_name': 'Central', 'conference_name': 'Eastern'},
        'Indiana Pacers': {'league_id': 3, 'division_name': 'Central', 'conference_name': 'Eastern'},
        'Milwaukee Bucks': {'league_id': 3, 'division_name': 'Central', 'conference_name': 'Eastern'},
        
        'Atlanta Hawks': {'league_id': 3, 'division_name': 'Southeast', 'conference_name': 'Eastern'},
        'Charlotte Hornets': {'league_id': 3, 'division_name': 'Southeast', 'conference_name': 'Eastern'},
        'Miami Heat': {'league_id': 3, 'division_name': 'Southeast', 'conference_name': 'Eastern'},
        'Orlando Magic': {'league_id': 3, 'division_name': 'Southeast', 'conference_name': 'Eastern'},
        'Washington Wizards': {'league_id': 3, 'division_name': 'Southeast', 'conference_name': 'Eastern'},
        
        # NBA Teams - Western Conference
        'Denver Nuggets': {'league_id': 3, 'division_name': 'Northwest', 'conference_name': 'Western'},
        'Minnesota Timberwolves': {'league_id': 3, 'division_name': 'Northwest', 'conference_name': 'Western'},
        'Oklahoma City Thunder': {'league_id': 3, 'division_name': 'Northwest', 'conference_name': 'Western'},
        'Portland Trail Blazers': {'league_id': 3, 'division_name': 'Northwest', 'conference_name': 'Western'},
        'Utah Jazz': {'league_id': 3, 'division_name': 'Northwest', 'conference_name': 'Western'},
        
        'Dallas Mavericks': {'league_id': 3, 'division_name': 'Southwest', 'conference_name': 'Western'},
        'Houston Rockets': {'league_id': 3, 'division_name': 'Southwest', 'conference_name': 'Western'},
        'Memphis Grizzlies': {'league_id': 3, 'division_name': 'Southwest', 'conference_name': 'Western'},
        'New Orleans Pelicans': {'league_id': 3, 'division_name': 'Southwest', 'conference_name': 'Western'},
        'San Antonio Spurs': {'league_id': 3, 'division_name': 'Southwest', 'conference_name': 'Western'},
        
        'Golden State Warriors': {'league_id': 3, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Los Angeles Clippers': {'league_id': 3, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Los Angeles Lakers': {'league_id': 3, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Phoenix Suns': {'league_id': 3, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Sacramento Kings': {'league_id': 3, 'division_name': 'Pacific', 'conference_name': 'Western'},
        
        # NHL Teams - Eastern Conference
        'Boston Bruins': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Buffalo Sabres': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Detroit Red Wings': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Florida Panthers': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Montreal Canadiens': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Ottawa Senators': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Tampa Bay Lightning': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        'Toronto Maple Leafs': {'league_id': 5, 'division_name': 'Atlantic', 'conference_name': 'Eastern'},
        
        'Carolina Hurricanes': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'Columbus Blue Jackets': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'New Jersey Devils': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'New York Islanders': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'New York Rangers': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'Philadelphia Flyers': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'Pittsburgh Penguins': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        'Washington Capitals': {'league_id': 5, 'division_name': 'Metropolitan', 'conference_name': 'Eastern'},
        
        # NHL Teams - Western Conference
        'Chicago Blackhawks': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'Colorado Avalanche': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'Dallas Stars': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'Minnesota Wild': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'Nashville Predators': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'St. Louis Blues': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        'Winnipeg Jets': {'league_id': 5, 'division_name': 'Central', 'conference_name': 'Western'},
        
        'Anaheim Ducks': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Calgary Flames': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Edmonton Oilers': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Los Angeles Kings': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'San Jose Sharks': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Seattle Kraken': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Vancouver Canucks': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        'Vegas Golden Knights': {'league_id': 5, 'division_name': 'Pacific', 'conference_name': 'Western'},
        
        # MLS Teams
        'Atlanta United FC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Austin FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'CF Montréal': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Charlotte FC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Chicago Fire FC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Colorado Rapids': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Columbus Crew': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'D.C. United': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'FC Cincinnati': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'FC Dallas': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Houston Dynamo FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Inter Miami CF': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Los Angeles Galaxy': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Los Angeles FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Minnesota United FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Nashville SC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'New England Revolution': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'New York City FC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'New York Red Bulls': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Orlando City SC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Philadelphia Union': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Portland Timbers': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Real Salt Lake': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'San Diego FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'San Jose Earthquakes': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Seattle Sounders FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Sporting Kansas City': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'St. Louis City SC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        'Toronto FC': {'league_id': 2, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Vancouver Whitecaps FC': {'league_id': 2, 'division_name': 'Western', 'conference_name': 'Western'},
        
        # WNBA Teams
        'Atlanta Dream': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Chicago Sky': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Connecticut Sun': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Indiana Fever': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'New York Liberty': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        'Washington Mystics': {'league_id': 6, 'division_name': 'Eastern', 'conference_name': 'Eastern'},
        
        'Dallas Wings': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Golden State Valkyries': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Las Vegas Aces': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Los Angeles Sparks': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Minnesota Lynx': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Phoenix Mercury': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        'Seattle Storm': {'league_id': 6, 'division_name': 'Western', 'conference_name': 'Western'},
        
        # IPL Teams
        'Chennai Super Kings': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Delhi Capitals': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Gujarat Titans': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Kolkata Knight Riders': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Lucknow Super Giants': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Mumbai Indians': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Punjab Kings': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Rajasthan Royals': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Royal Challengers Bengaluru': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
        'Sunrisers Hyderabad': {'league_id': 7, 'division_name': 'IPL', 'conference_name': 'IPL'},
    }
    
    return team_mappings

def fix_all_team_mappings():
    """Fix all team division and conference mappings using comprehensive mappings"""
    print("Fixing all team mappings with comprehensive data...")
    
    # Get comprehensive mappings
    team_mappings = create_comprehensive_mappings()
    print(f"Created mappings for {len(team_mappings)} teams")
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Update teams with correct division and conference names
        updated_count = 0
        for team_name, mapping in team_mappings.items():
            cursor.execute("""
                UPDATE teams 
                SET division_name = %s, conference_name = %s
                WHERE real_team_name = %s AND league_id = %s
            """, (mapping['division_name'], mapping['conference_name'], team_name, mapping['league_id']))
            
            if cursor.rowcount > 0:
                updated_count += 1
                print(f"Updated {team_name}: {mapping['division_name']} / {mapping['conference_name']}")
        
        conn.commit()
        cursor.close()
        
        print(f"\nSuccessfully updated {updated_count} teams")
        
        # Verify the updates
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT l.league_name_proper, d.division_name, COUNT(t.team_id) as team_count
            FROM leagues l
            LEFT JOIN divisions d ON l.league_id = d.league_id
            LEFT JOIN teams t ON l.league_id = t.league_id AND d.division_name = t.division_name
            GROUP BY l.league_name_proper, d.division_name
            HAVING COUNT(t.team_id) > 0
            ORDER BY l.league_name_proper, d.division_name
        """)
        
        results = cursor.fetchall()
        print("\nUpdated team counts by division:")
        for row in results:
            print(f"  {row['league_name_proper']} - {row['division_name']}: {row['team_count']} teams")
        
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error updating teams: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """Main function"""
    print("Starting comprehensive team mapping fix...")
    
    if fix_all_team_mappings():
        print("\nComprehensive team mapping fix completed successfully!")
    else:
        print("\nComprehensive team mapping fix failed!")

if __name__ == "__main__":
    main()
