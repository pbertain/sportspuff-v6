#!/usr/bin/env python3
"""
Fix foreign key relationships in teams CSV
This script maps the correct division_id and conference_id values
based on what's actually in the database.
"""

import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv

def get_db_connection():
    """Get database connection"""
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )

def fix_team_foreign_keys():
    """Fix division_id and conference_id in teams CSV"""
    print("Fixing foreign key relationships in teams CSV...")
    
    # Read teams CSV
    df = pd.read_csv('info-teams.csv', encoding='latin-1')
    print(f"Loaded {len(df)} teams from CSV")
    
    # Get database connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get correct division mappings
    cursor.execute("SELECT division_id, league_id, division_name FROM divisions")
    division_map = {}
    for div_id, league_id, div_name in cursor.fetchall():
        division_map[(league_id, div_name.strip())] = div_id
    
    # Get correct conference mappings  
    cursor.execute("SELECT conference_id, league_id, conference_name FROM conferences")
    conference_map = {}
    for conf_id, league_id, conf_name in cursor.fetchall():
        conference_map[(league_id, conf_name.strip())] = conf_id
    
    print(f"Found {len(division_map)} divisions and {len(conference_map)} conferences in database")
    
    # Manual mapping for teams based on their actual divisions/conferences
    # This is based on the real league structures
    
    team_fixes = {
        # NHL Teams
        'Anaheim Ducks': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Arizona Cardinals': {'division_id': 404, 'conference_id': 110},  # West, NFC
        'Arizona Diamondbacks': {'division_id': 103, 'conference_id': 103},  # West, NL
        'Atlanta Braves': {'division_id': 104, 'conference_id': 103},  # East, NL
        'Atlanta Falcons': {'division_id': 403, 'conference_id': 110},  # South, NFC
        'Atlanta Hawks': {'division_id': 303, 'conference_id': 107},  # Southeast, Western
        'Baltimore Orioles': {'division_id': 101, 'conference_id': 102},  # East, AL
        'Baltimore Ravens': {'division_id': 401, 'conference_id': 109},  # East, AFC
        'Boston Bruins': {'division_id': 501, 'conference_id': 112},  # Atlantic, Eastern
        'Boston Celtics': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'Boston Red Sox': {'division_id': 101, 'conference_id': 102},  # East, AL
        'Brooklyn Nets': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'Buffalo Bills': {'division_id': 401, 'conference_id': 109},  # East, AFC
        'Buffalo Sabres': {'division_id': 501, 'conference_id': 112},  # Atlantic, Eastern
        'Calgary Flames': {'division_id': 503, 'conference_id': 113},  # Central, Western
        'Carolina Hurricanes': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Carolina Panthers': {'division_id': 403, 'conference_id': 110},  # South, NFC
        'Charlotte Hornets': {'division_id': 303, 'conference_id': 107},  # Southeast, Western
        'Chicago Bears': {'division_id': 402, 'conference_id': 110},  # North, NFC
        'Chicago Blackhawks': {'division_id': 503, 'conference_id': 113},  # Central, Western
        'Chicago Bulls': {'division_id': 302, 'conference_id': 107},  # Central, Western
        'Chicago Cubs': {'division_id': 102, 'conference_id': 103},  # Central, NL
        'Chicago White Sox': {'division_id': 102, 'conference_id': 102},  # Central, AL
        'Cincinnati Bengals': {'division_id': 402, 'conference_id': 109},  # North, AFC
        'Cincinnati Reds': {'division_id': 102, 'conference_id': 103},  # Central, NL
        'Cleveland Browns': {'division_id': 402, 'conference_id': 109},  # North, AFC
        'Cleveland Cavaliers': {'division_id': 302, 'conference_id': 106},  # Central, Eastern
        'Cleveland Guardians': {'division_id': 102, 'conference_id': 102},  # Central, AL
        'Colorado Avalanche': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Colorado Rockies': {'division_id': 103, 'conference_id': 103},  # West, NL
        'Columbus Blue Jackets': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Dallas Cowboys': {'division_id': 404, 'conference_id': 110},  # West, NFC
        'Dallas Mavericks': {'division_id': 306, 'conference_id': 107},  # Southwest, Western
        'Dallas Stars': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Denver Broncos': {'division_id': 404, 'conference_id': 109},  # West, AFC
        'Denver Nuggets': {'division_id': 304, 'conference_id': 107},  # Northwest, Western
        'Detroit Lions': {'division_id': 402, 'conference_id': 110},  # North, NFC
        'Detroit Pistons': {'division_id': 302, 'conference_id': 106},  # Central, Eastern
        'Detroit Red Wings': {'division_id': 503, 'conference_id': 112},  # Central, Eastern
        'Detroit Tigers': {'division_id': 102, 'conference_id': 102},  # Central, AL
        'Edmonton Oilers': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Florida Panthers': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Golden State Warriors': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'Green Bay Packers': {'division_id': 402, 'conference_id': 110},  # North, NFC
        'Houston Astros': {'division_id': 103, 'conference_id': 102},  # West, AL
        'Houston Rockets': {'division_id': 306, 'conference_id': 107},  # Southwest, Western
        'Houston Texans': {'division_id': 403, 'conference_id': 109},  # South, AFC
        'Indiana Pacers': {'division_id': 302, 'conference_id': 106},  # Central, Eastern
        'Indianapolis Colts': {'division_id': 402, 'conference_id': 109},  # North, AFC
        'Jacksonville Jaguars': {'division_id': 403, 'conference_id': 109},  # South, AFC
        'Kansas City Chiefs': {'division_id': 404, 'conference_id': 109},  # West, AFC
        'Kansas City Royals': {'division_id': 102, 'conference_id': 102},  # Central, AL
        'Los Angeles Clippers': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'Las Vegas Raiders': {'division_id': 404, 'conference_id': 109},  # West, AFC
        'Los Angeles Angels': {'division_id': 103, 'conference_id': 102},  # West, AL
        'Los Angeles Chargers': {'division_id': 404, 'conference_id': 109},  # West, AFC
        'Los Angeles Dodgers': {'division_id': 103, 'conference_id': 103},  # West, NL
        'Los Angeles Kings': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Los Angeles Lakers': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'Los Angeles Rams': {'division_id': 404, 'conference_id': 110},  # West, NFC
        'Memphis Grizzlies': {'division_id': 302, 'conference_id': 107},  # Central, Western
        'Miami Dolphins': {'division_id': 403, 'conference_id': 109},  # South, AFC
        'Miami Heat': {'division_id': 303, 'conference_id': 106},  # Southeast, Eastern
        'Miami Marlins': {'division_id': 104, 'conference_id': 103},  # East, NL
        'Milwaukee Brewers': {'division_id': 102, 'conference_id': 103},  # Central, NL
        'Milwaukee Bucks': {'division_id': 302, 'conference_id': 106},  # Central, Eastern
        'Minnesota Timberwolves': {'division_id': 304, 'conference_id': 107},  # Northwest, Western
        'Minnesota Twins': {'division_id': 102, 'conference_id': 102},  # Central, AL
        'Minnesota Vikings': {'division_id': 402, 'conference_id': 110},  # North, NFC
        'Minnesota Wild': {'division_id': 304, 'conference_id': 113},  # Northwest, Western
        'Montreal Canadiens': {'division_id': 501, 'conference_id': 112},  # Atlantic, Eastern
        'Nashville Predators': {'division_id': 503, 'conference_id': 112},  # Central, Eastern
        'New England Patriots': {'division_id': 401, 'conference_id': 109},  # East, AFC
        'New Jersey Devils': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'New Orleans Pelicans': {'division_id': 303, 'conference_id': 107},  # Southeast, Western
        'New Orleans Saints': {'division_id': 403, 'conference_id': 110},  # South, NFC
        'New York Giants': {'division_id': 401, 'conference_id': 110},  # East, NFC
        'New York Islanders': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'New York Jets': {'division_id': 401, 'conference_id': 109},  # East, AFC
        'New York Knicks': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'New York Mets': {'division_id': 104, 'conference_id': 103},  # East, NL
        'New York Rangers': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'New York Yankees': {'division_id': 101, 'conference_id': 102},  # East, AL
        'Oakland Athletics': {'division_id': 103, 'conference_id': 102},  # West, AL
        'Oklahoma City Thunder': {'division_id': 304, 'conference_id': 107},  # Northwest, Western
        'Orlando Magic': {'division_id': 303, 'conference_id': 106},  # Southeast, Eastern
        'Ottawa Senators': {'division_id': 501, 'conference_id': 112},  # Atlantic, Eastern
        'Philadelphia 76ers': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'Philadelphia Eagles': {'division_id': 401, 'conference_id': 110},  # East, NFC
        'Philadelphia Flyers': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Philadelphia Phillies': {'division_id': 104, 'conference_id': 103},  # East, NL
        'Phoenix Suns': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'Pittsburgh Penguins': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Pittsburgh Pirates': {'division_id': 102, 'conference_id': 103},  # Central, NL
        'Pittsburgh Steelers': {'division_id': 402, 'conference_id': 109},  # North, AFC
        'Portland Trail Blazers': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'Sacramento Kings': {'division_id': 305, 'conference_id': 107},  # Pacific, Western
        'St. Louis Blues': {'division_id': 503, 'conference_id': 112},  # Central, Eastern
        'St. Louis Cardinals': {'division_id': 102, 'conference_id': 103},  # Central, NL
        'San Antonio Spurs': {'division_id': 306, 'conference_id': 107},  # Southwest, Western
        'San Diego Padres': {'division_id': 103, 'conference_id': 103},  # West, NL
        'San Francisco 49ers': {'division_id': 404, 'conference_id': 110},  # West, NFC
        'San Francisco Giants': {'division_id': 103, 'conference_id': 103},  # West, NL
        'San Jose Sharks': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Seattle Mariners': {'division_id': 103, 'conference_id': 102},  # West, AL
        'Seattle Seahawks': {'division_id': 404, 'conference_id': 110},  # West, NFC
        'Tampa Bay Buccaneers': {'division_id': 403, 'conference_id': 110},  # South, NFC
        'Tampa Bay Lightning': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Tampa Bay Rays': {'division_id': 101, 'conference_id': 102},  # East, AL
        'Tennessee Titans': {'division_id': 403, 'conference_id': 109},  # South, AFC
        'Texas Rangers': {'division_id': 103, 'conference_id': 102},  # West, AL
        'Toronto Blue Jays': {'division_id': 101, 'conference_id': 102},  # East, AL
        'Toronto Maple Leafs': {'division_id': 501, 'conference_id': 112},  # Atlantic, Eastern
        'Toronto Raptors': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'Utah Jazz': {'division_id': 304, 'conference_id': 107},  # Northwest, Western
        'Vancouver Canucks': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Vegas Golden Knights': {'division_id': 504, 'conference_id': 113},  # Pacific, Western
        'Washington Capitals': {'division_id': 502, 'conference_id': 112},  # Metropolitan, Eastern
        'Washington Commanders': {'division_id': 401, 'conference_id': 110},  # East, NFC
        'Washington Nationals': {'division_id': 104, 'conference_id': 103},  # East, NL
        'Washington Wizards': {'division_id': 301, 'conference_id': 106},  # Atlantic, Eastern
        'Winnipeg Jets': {'division_id': 503, 'conference_id': 112},  # Central, Eastern
    }
    
    # Apply fixes
    fixed_count = 0
    for idx, row in df.iterrows():
        team_name = row['real_team_name']
        if team_name in team_fixes:
            old_div = row['division_id']
            old_conf = row['conference_id']
            
            df.at[idx, 'division_id'] = team_fixes[team_name]['division_id']
            df.at[idx, 'conference_id'] = team_fixes[team_name]['conference_id']
            
            print(f"Fixed {team_name}: div {old_div}→{team_fixes[team_name]['division_id']}, conf {old_conf}→{team_fixes[team_name]['conference_id']}")
            fixed_count += 1
    
    # Save updated CSV
    df.to_csv('info-teams-fixed.csv', index=False, encoding='utf-8')
    print(f"\nFixed {fixed_count} teams")
    print("Saved updated CSV as 'info-teams-fixed.csv'")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    fix_team_foreign_keys()

