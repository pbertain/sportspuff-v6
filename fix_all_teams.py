#!/usr/bin/env python3
"""
Comprehensive fix for all team foreign key relationships
This script updates all teams in the database with correct division/conference names
based on their actual league structures.
"""

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

def fix_all_teams():
    """Fix all team division/conference relationships"""
    print("Fixing ALL team foreign key relationships...")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Comprehensive team fixes based on actual league structures
    team_fixes = [
        # MLB Teams
        ('Arizona Diamondbacks', 'West', 'NL'),
        ('Atlanta Braves', 'East', 'NL'),
        ('Baltimore Orioles', 'East', 'AL'),
        ('Boston Red Sox', 'East', 'AL'),
        ('Chicago Cubs', 'Central', 'NL'),
        ('Chicago White Sox', 'Central', 'AL'),
        ('Cincinnati Reds', 'Central', 'NL'),
        ('Cleveland Guardians', 'Central', 'AL'),
        ('Colorado Rockies', 'West', 'NL'),
        ('Detroit Tigers', 'Central', 'AL'),
        ('Houston Astros', 'West', 'AL'),
        ('Kansas City Royals', 'Central', 'AL'),
        ('Los Angeles Angels', 'West', 'AL'),
        ('Los Angeles Dodgers', 'West', 'NL'),
        ('Miami Marlins', 'East', 'NL'),
        ('Milwaukee Brewers', 'Central', 'NL'),
        ('Minnesota Twins', 'Central', 'AL'),
        ('New York Mets', 'East', 'NL'),
        ('New York Yankees', 'East', 'AL'),
        ('Oakland Athletics', 'West', 'AL'),
        ('Philadelphia Phillies', 'East', 'NL'),
        ('Pittsburgh Pirates', 'Central', 'NL'),
        ('San Diego Padres', 'West', 'NL'),
        ('San Francisco Giants', 'West', 'NL'),
        ('Seattle Mariners', 'West', 'AL'),
        ('St. Louis Cardinals', 'Central', 'NL'),
        ('Tampa Bay Rays', 'East', 'AL'),
        ('Texas Rangers', 'West', 'AL'),
        ('Toronto Blue Jays', 'East', 'AL'),
        ('Washington Nationals', 'East', 'NL'),
        
        # NFL Teams
        ('Arizona Cardinals', 'West', 'NFC'),
        ('Atlanta Falcons', 'South', 'NFC'),
        ('Baltimore Ravens', 'East', 'AFC'),
        ('Buffalo Bills', 'East', 'AFC'),
        ('Carolina Panthers', 'South', 'NFC'),
        ('Chicago Bears', 'North', 'NFC'),
        ('Cincinnati Bengals', 'North', 'AFC'),
        ('Cleveland Browns', 'North', 'AFC'),
        ('Dallas Cowboys', 'West', 'NFC'),
        ('Denver Broncos', 'West', 'AFC'),
        ('Detroit Lions', 'North', 'NFC'),
        ('Green Bay Packers', 'North', 'NFC'),
        ('Houston Texans', 'South', 'AFC'),
        ('Indianapolis Colts', 'North', 'AFC'),
        ('Jacksonville Jaguars', 'South', 'AFC'),
        ('Kansas City Chiefs', 'West', 'AFC'),
        ('Las Vegas Raiders', 'West', 'AFC'),
        ('Los Angeles Chargers', 'West', 'AFC'),
        ('Los Angeles Rams', 'West', 'NFC'),
        ('Miami Dolphins', 'South', 'AFC'),
        ('Minnesota Vikings', 'North', 'NFC'),
        ('New England Patriots', 'East', 'AFC'),
        ('New Orleans Saints', 'South', 'NFC'),
        ('New York Giants', 'East', 'NFC'),
        ('New York Jets', 'East', 'AFC'),
        ('Philadelphia Eagles', 'East', 'NFC'),
        ('Pittsburgh Steelers', 'North', 'AFC'),
        ('San Francisco 49ers', 'West', 'NFC'),
        ('Seattle Seahawks', 'West', 'NFC'),
        ('Tampa Bay Buccaneers', 'South', 'NFC'),
        ('Tennessee Titans', 'South', 'AFC'),
        ('Washington Commanders', 'East', 'NFC'),
        
        # NBA Teams
        ('Atlanta Hawks', 'Southeast', 'Western'),
        ('Boston Celtics', 'Atlantic', 'Eastern'),
        ('Brooklyn Nets', 'Atlantic', 'Eastern'),
        ('Charlotte Hornets', 'Southeast', 'Eastern'),
        ('Chicago Bulls', 'Central', 'Eastern'),
        ('Cleveland Cavaliers', 'Central', 'Eastern'),
        ('Dallas Mavericks', 'Southwest', 'Western'),
        ('Denver Nuggets', 'Northwest', 'Western'),
        ('Detroit Pistons', 'Central', 'Eastern'),
        ('Golden State Warriors', 'Pacific', 'Western'),
        ('Houston Rockets', 'Southwest', 'Western'),
        ('Indiana Pacers', 'Central', 'Eastern'),
        ('Los Angeles Clippers', 'Pacific', 'Western'),
        ('Los Angeles Lakers', 'Pacific', 'Western'),
        ('Memphis Grizzlies', 'Central', 'Western'),
        ('Miami Heat', 'Southeast', 'Eastern'),
        ('Milwaukee Bucks', 'Central', 'Eastern'),
        ('Minnesota Timberwolves', 'Northwest', 'Western'),
        ('New Orleans Pelicans', 'Southeast', 'Western'),
        ('New York Knicks', 'Atlantic', 'Eastern'),
        ('Oklahoma City Thunder', 'Northwest', 'Western'),
        ('Orlando Magic', 'Southeast', 'Eastern'),
        ('Philadelphia 76ers', 'Atlantic', 'Eastern'),
        ('Phoenix Suns', 'Pacific', 'Western'),
        ('Portland Trail Blazers', 'Pacific', 'Western'),
        ('Sacramento Kings', 'Pacific', 'Western'),
        ('San Antonio Spurs', 'Southwest', 'Western'),
        ('Toronto Raptors', 'Atlantic', 'Eastern'),
        ('Utah Jazz', 'Northwest', 'Western'),
        ('Washington Wizards', 'Atlantic', 'Eastern'),
        
        # NHL Teams
        ('Anaheim Ducks', 'Pacific', 'Western'),
        ('Boston Bruins', 'Atlantic', 'Eastern'),
        ('Buffalo Sabres', 'Atlantic', 'Eastern'),
        ('Calgary Flames', 'Central', 'Western'),
        ('Carolina Hurricanes', 'Metropolitan', 'Eastern'),
        ('Chicago Blackhawks', 'Central', 'Western'),
        ('Colorado Avalanche', 'Pacific', 'Western'),
        ('Columbus Blue Jackets', 'Metropolitan', 'Eastern'),
        ('Dallas Stars', 'Pacific', 'Western'),
        ('Detroit Red Wings', 'Central', 'Eastern'),
        ('Edmonton Oilers', 'Pacific', 'Western'),
        ('Florida Panthers', 'Metropolitan', 'Eastern'),
        ('Los Angeles Kings', 'Pacific', 'Western'),
        ('Minnesota Wild', 'Northwest', 'Western'),
        ('Montreal Canadiens', 'Atlantic', 'Eastern'),
        ('Nashville Predators', 'Central', 'Eastern'),
        ('New Jersey Devils', 'Metropolitan', 'Eastern'),
        ('New York Islanders', 'Metropolitan', 'Eastern'),
        ('New York Rangers', 'Metropolitan', 'Eastern'),
        ('Ottawa Senators', 'Atlantic', 'Eastern'),
        ('Philadelphia Flyers', 'Metropolitan', 'Eastern'),
        ('Pittsburgh Penguins', 'Metropolitan', 'Eastern'),
        ('San Jose Sharks', 'Pacific', 'Western'),
        ('Seattle Kraken', 'Pacific', 'Western'),
        ('St. Louis Blues', 'Central', 'Eastern'),
        ('Tampa Bay Lightning', 'Metropolitan', 'Eastern'),
        ('Toronto Maple Leafs', 'Atlantic', 'Eastern'),
        ('Vancouver Canucks', 'Pacific', 'Western'),
        ('Vegas Golden Knights', 'Pacific', 'Western'),
        ('Washington Capitals', 'Metropolitan', 'Eastern'),
        ('Winnipeg Jets', 'Central', 'Eastern'),
        
        # MLS Teams (no divisions, just conferences)
        ('Atlanta United FC', 'Eastern', 'Eastern'),
        ('Austin FC', 'Western', 'Western'),
        ('Charlotte FC', 'Eastern', 'Eastern'),
        ('Chicago Fire FC', 'Eastern', 'Eastern'),
        ('Colorado Rapids', 'Western', 'Western'),
        ('Columbus Crew', 'Eastern', 'Eastern'),
        ('D.C. United', 'Eastern', 'Eastern'),
        ('FC Cincinnati', 'Eastern', 'Eastern'),
        ('FC Dallas', 'Western', 'Western'),
        ('Houston Dynamo FC', 'Western', 'Western'),
        ('Inter Miami CF', 'Eastern', 'Eastern'),
        ('Los Angeles Galaxy', 'Western', 'Western'),
        ('Los Angeles FC', 'Western', 'Western'),
        ('Minnesota United FC', 'Western', 'Western'),
        ('Nashville SC', 'Eastern', 'Eastern'),
        ('New England Revolution', 'Eastern', 'Eastern'),
        ('New York City FC', 'Eastern', 'Eastern'),
        ('New York Red Bulls', 'Eastern', 'Eastern'),
        ('Orlando City SC', 'Eastern', 'Eastern'),
        ('Philadelphia Union', 'Eastern', 'Eastern'),
        ('Portland Timbers', 'Western', 'Western'),
        ('Real Salt Lake', 'Western', 'Western'),
        ('San Jose Earthquakes', 'Western', 'Western'),
        ('Seattle Sounders FC', 'Western', 'Western'),
        ('Sporting Kansas City', 'Western', 'Western'),
        ('St. Louis City SC', 'Western', 'Western'),
        ('Toronto FC', 'Eastern', 'Eastern'),
        ('Vancouver Whitecaps FC', 'Western', 'Western'),
        
        # WNBA Teams (no divisions, just conferences)
        ('Atlanta Dream', 'Eastern', 'Eastern'),
        ('Chicago Sky', 'Eastern', 'Eastern'),
        ('Connecticut Sun', 'Eastern', 'Eastern'),
        ('Dallas Wings', 'Western', 'Western'),
        ('Golden State Valkyries', 'Western', 'Western'),
        ('Indiana Fever', 'Eastern', 'Eastern'),
        ('Las Vegas Aces', 'Western', 'Western'),
        ('Los Angeles Sparks', 'Western', 'Western'),
        ('Minnesota Lynx', 'Western', 'Western'),
        ('New York Liberty', 'Eastern', 'Eastern'),
        ('Phoenix Mercury', 'Western', 'Western'),
        ('Seattle Storm', 'Western', 'Western'),
        ('Washington Mystics', 'Eastern', 'Eastern'),
        
        # IPL Teams (no divisions, just conference)
        ('Chennai Super Kings', 'IPL', 'IPL'),
        ('Delhi Capitals', 'IPL', 'IPL'),
        ('Gujarat Titans', 'IPL', 'IPL'),
        ('Kolkata Knight Riders', 'IPL', 'IPL'),
        ('Lucknow Super Giants', 'IPL', 'IPL'),
        ('Mumbai Indians', 'IPL', 'IPL'),
        ('Punjab Kings', 'IPL', 'IPL'),
        ('Rajasthan Royals', 'IPL', 'IPL'),
        ('Royal Challengers Bengaluru', 'IPL', 'IPL'),
        ('Sunrisers Hyderabad', 'IPL', 'IPL'),
    ]
    
    # Apply all fixes
    fixed_count = 0
    for team_name, division, conference in team_fixes:
        cur.execute('UPDATE teams SET division_name = %s, conference_name = %s WHERE real_team_name = %s',
                   (division, conference, team_name))
        if cur.rowcount > 0:
            print(f"Fixed {team_name}: {division}, {conference}")
            fixed_count += 1
        else:
            print(f"Team not found: {team_name}")
    
    # Commit changes
    conn.commit()
    
    # Verify results
    print(f"\nFixed {fixed_count} teams")
    
    # Check how many teams now have proper division/conference data
    cur.execute('SELECT COUNT(*) FROM teams WHERE division_name IS NOT NULL AND conference_name IS NOT NULL')
    proper_teams = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM teams')
    total_teams = cur.fetchone()[0]
    
    print(f"Teams with proper division/conference: {proper_teams}/{total_teams}")
    
    cur.close()
    conn.close()
    print("All team foreign key relationships fixed!")

if __name__ == "__main__":
    fix_all_teams()
