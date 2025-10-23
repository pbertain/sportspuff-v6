#!/usr/bin/env python3
"""
Team Colors Update Script
Updates team colors based on official team colors from usteamcolors.com
"""

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

# Team colors mapping based on usteamcolors.com
TEAM_COLORS = {
    # NFL Teams
    'Arizona Cardinals': ['#97233F', '#000000', '#FFFFFF'],
    'Atlanta Falcons': ['#A71930', '#000000', '#FFFFFF'],
    'Baltimore Ravens': ['#241773', '#000000', '#FFFFFF'],
    'Buffalo Bills': ['#00338D', '#C60C30', '#FFFFFF'],
    'Carolina Panthers': ['#0085CA', '#000000', '#FFFFFF'],
    'Chicago Bears': ['#0B162A', '#C83803', '#FFFFFF'],
    'Cincinnati Bengals': ['#FB4F14', '#000000', '#FFFFFF'],
    'Cleveland Browns': ['#311D00', '#FF3C00', '#FFFFFF'],
    'Dallas Cowboys': ['#003594', '#869397', '#FFFFFF'],
    'Denver Broncos': ['#FB4F14', '#002244', '#FFFFFF'],
    'Detroit Lions': ['#0076B6', '#B0B7BC', '#FFFFFF'],
    'Green Bay Packers': ['#203731', '#FFB612', '#FFFFFF'],
    'Houston Texans': ['#03202F', '#A71930', '#FFFFFF'],
    'Indianapolis Colts': ['#002C5F', '#FFFFFF', '#000000'],
    'Jacksonville Jaguars': ['#006778', '#9F792C', '#FFFFFF'],
    'Kansas City Chiefs': ['#E31837', '#FFB81C', '#FFFFFF'],
    'Las Vegas Raiders': ['#000000', '#A5ACAF', '#FFFFFF'],
    'Los Angeles Chargers': ['#0080C6', '#FFC20E', '#FFFFFF'],
    'Los Angeles Rams': ['#003594', '#FFA300', '#FFFFFF'],
    'Miami Dolphins': ['#008E97', '#FC4C02', '#FFFFFF'],
    'Minnesota Vikings': ['#4F2683', '#FFC62F', '#FFFFFF'],
    'New England Patriots': ['#002244', '#C60C30', '#FFFFFF'],
    'New Orleans Saints': ['#D3BC8D', '#000000', '#FFFFFF'],
    'New York Giants': ['#0B2265', '#A71930', '#FFFFFF'],
    'New York Jets': ['#125740', '#000000', '#FFFFFF'],
    'Philadelphia Eagles': ['#004C54', '#A5ACAF', '#FFFFFF'],
    'Pittsburgh Steelers': ['#FFB612', '#000000', '#FFFFFF'],
    'San Francisco 49ers': ['#AA0000', '#B3995D', '#FFFFFF'],
    'Seattle Seahawks': ['#002244', '#69BE28', '#FFFFFF'],
    'Tampa Bay Buccaneers': ['#D50A0A', '#FF7900', '#FFFFFF'],
    'Tennessee Titans': ['#0C2340', '#4B92DB', '#FFFFFF'],
    'Washington Commanders': ['#5A1414', '#FFB612', '#FFFFFF'],

    # NBA Teams
    'Atlanta Hawks': ['#E03A3E', '#C1D32F', '#FFFFFF'],
    'Boston Celtics': ['#007A33', '#BA9653', '#FFFFFF'],
    'Brooklyn Nets': ['#000000', '#FFFFFF', '#000000'],
    'Charlotte Hornets': ['#1D1160', '#00788C', '#FFFFFF'],
    'Chicago Bulls': ['#CE1141', '#000000', '#FFFFFF'],
    'Cleveland Cavaliers': ['#860038', '#FDBB30', '#FFFFFF'],
    'Dallas Mavericks': ['#00538C', '#002B5E', '#FFFFFF'],
    'Denver Nuggets': ['#0E2240', '#FEC524', '#FFFFFF'],
    'Detroit Pistons': ['#C8102E', '#1D42BA', '#FFFFFF'],
    'Golden State Warriors': ['#1D428A', '#FFC72C', '#FFFFFF'],
    'Houston Rockets': ['#CE1141', '#000000', '#FFFFFF'],
    'Indiana Pacers': ['#002D62', '#FDBB30', '#FFFFFF'],
    'Los Angeles Clippers': ['#C8102E', '#1D428A', '#FFFFFF'],
    'Los Angeles Lakers': ['#552583', '#FDB927', '#FFFFFF'],
    'Memphis Grizzlies': ['#5D76A9', '#12173F', '#FFFFFF'],
    'Miami Heat': ['#98002E', '#F9A01B', '#FFFFFF'],
    'Milwaukee Bucks': ['#00471B', '#EEE1C6', '#FFFFFF'],
    'Minnesota Timberwolves': ['#0C2340', '#236192', '#FFFFFF'],
    'New Orleans Pelicans': ['#0C2340', '#C8102E', '#FFFFFF'],
    'New York Knicks': ['#006BB6', '#F58426', '#FFFFFF'],
    'Oklahoma City Thunder': ['#007AC1', '#EF3B24', '#FFFFFF'],
    'Orlando Magic': ['#0077C0', '#C4CED4', '#FFFFFF'],
    'Philadelphia 76ers': ['#006BB6', '#ED174C', '#FFFFFF'],
    'Phoenix Suns': ['#1D1160', '#E56020', '#FFFFFF'],
    'Portland Trail Blazers': ['#E03A3E', '#000000', '#FFFFFF'],
    'Sacramento Kings': ['#5A2D81', '#63727A', '#FFFFFF'],
    'San Antonio Spurs': ['#C4CED4', '#000000', '#FFFFFF'],
    'Toronto Raptors': ['#CE1141', '#000000', '#FFFFFF'],
    'Utah Jazz': ['#002B5C', '#F9A01B', '#FFFFFF'],
    'Washington Wizards': ['#002B5C', '#E31837', '#FFFFFF'],

    # MLB Teams
    'Arizona Diamondbacks': ['#A71930', '#E3D4AD', '#FFFFFF'],
    'Atlanta Braves': ['#CE1141', '#13274F', '#FFFFFF'],
    'Baltimore Orioles': ['#DF4601', '#000000', '#FFFFFF'],
    'Boston Red Sox': ['#BD3039', '#0C2340', '#FFFFFF'],
    'Chicago Cubs': ['#0E3386', '#CC3433', '#FFFFFF'],
    'Chicago White Sox': ['#27251F', '#C4CED4', '#FFFFFF'],
    'Cincinnati Reds': ['#C6011F', '#000000', '#FFFFFF'],
    'Cleveland Guardians': ['#E31937', '#0C2340', '#FFFFFF'],
    'Colorado Rockies': ['#33006F', '#C4CED4', '#FFFFFF'],
    'Detroit Tigers': ['#0C2340', '#FA4616', '#FFFFFF'],
    'Houston Astros': ['#002D62', '#EB6E1F', '#FFFFFF'],
    'Kansas City Royals': ['#BD9B60', '#004687', '#FFFFFF'],
    'Los Angeles Angels': ['#BA0021', '#003263', '#FFFFFF'],
    'Los Angeles Dodgers': ['#005A9C', '#EF3E42', '#FFFFFF'],
    'Miami Marlins': ['#00A3E0', '#EF3340', '#FFFFFF'],
    'Milwaukee Brewers': ['#FFC52F', '#12284B', '#FFFFFF'],
    'Minnesota Twins': ['#002B5C', '#D31145', '#FFFFFF'],
    'New York Mets': ['#002D72', '#FF5910', '#FFFFFF'],
    'New York Yankees': ['#132448', '#C4CED4', '#FFFFFF'],
    'Oakland Athletics': ['#003831', '#EFB21E', '#FFFFFF'],
    'Philadelphia Phillies': ['#E81828', '#002D72', '#FFFFFF'],
    'Pittsburgh Pirates': ['#FDB827', '#27251F', '#FFFFFF'],
    'San Diego Padres': ['#2F241D', '#FFC425', '#FFFFFF'],
    'San Francisco Giants': ['#FD5A1E', '#27251F', '#FFFFFF'],
    'Seattle Mariners': ['#0C2C56', '#005C5C', '#FFFFFF'],
    'St. Louis Cardinals': ['#C41E3A', '#0C2340', '#FFFFFF'],
    'Tampa Bay Rays': ['#092C5C', '#8FBCE6', '#FFFFFF'],
    'Texas Rangers': ['#C0111F', '#003278', '#FFFFFF'],
    'Toronto Blue Jays': ['#134A8E', '#1D2D5C', '#FFFFFF'],
    'Washington Nationals': ['#AB0003', '#14225A', '#FFFFFF'],

    # NHL Teams
    'Anaheim Ducks': ['#F47A38', '#91764B', '#FFFFFF'],
    'Arizona Coyotes': ['#8C2633', '#E2D6B5', '#FFFFFF'],
    'Boston Bruins': ['#FFB81C', '#000000', '#FFFFFF'],
    'Buffalo Sabres': ['#002654', '#FCB514', '#FFFFFF'],
    'Calgary Flames': ['#C8102E', '#F1BE48', '#FFFFFF'],
    'Carolina Hurricanes': ['#CC0000', '#000000', '#FFFFFF'],
    'Chicago Blackhawks': ['#CF0A2C', '#000000', '#FFFFFF'],
    'Colorado Avalanche': ['#6F263D', '#236192', '#FFFFFF'],
    'Columbus Blue Jackets': ['#002654', '#CE1126', '#FFFFFF'],
    'Dallas Stars': ['#006847', '#8F8F8C', '#FFFFFF'],
    'Detroit Red Wings': ['#CE1126', '#FFFFFF', '#000000'],
    'Edmonton Oilers': ['#041E42', '#FF4C00', '#FFFFFF'],
    'Florida Panthers': ['#C8102E', '#041E42', '#FFFFFF'],
    'Los Angeles Kings': ['#111111', '#A2AAAD', '#FFFFFF'],
    'Minnesota Wild': ['#154734', '#DDD0C0', '#FFFFFF'],
    'Montreal Canadiens': ['#AF1E2D', '#192168', '#FFFFFF'],
    'Nashville Predators': ['#FFB81C', '#041E42', '#FFFFFF'],
    'New Jersey Devils': ['#CE1126', '#000000', '#FFFFFF'],
    'New York Islanders': ['#00539B', '#F47D30', '#FFFFFF'],
    'New York Rangers': ['#0038A8', '#CE1126', '#FFFFFF'],
    'Ottawa Senators': ['#C52032', '#C2912C', '#FFFFFF'],
    'Philadelphia Flyers': ['#F74902', '#000000', '#FFFFFF'],
    'Pittsburgh Penguins': ['#000000', '#FFB81C', '#FFFFFF'],
    'San Jose Sharks': ['#006D75', '#EA7200', '#FFFFFF'],
    'St. Louis Blues': ['#002F87', '#FCB514', '#FFFFFF'],
    'Tampa Bay Lightning': ['#002868', '#FFFFFF', '#000000'],
    'Toronto Maple Leafs': ['#003E7E', '#FFFFFF', '#000000'],
    'Vancouver Canucks': ['#001F5B', '#00843D', '#FFFFFF'],
    'Vegas Golden Knights': ['#B4975A', '#333F48', '#FFFFFF'],
    'Washington Capitals': ['#C8102E', '#041E42', '#FFFFFF'],
    'Winnipeg Jets': ['#041E42', '#004C97', '#FFFFFF']
}

def update_team_colors(conn):
    """Update team colors in the database"""
    print("Updating team colors...")
    
    try:
        cursor = conn.cursor()
        
        # Get all teams from database
        cursor.execute("SELECT team_id, real_team_name FROM teams")
        teams = cursor.fetchall()
        
        updated_count = 0
        
        for team_id, real_team_name in teams:
            if real_team_name in TEAM_COLORS:
                colors = TEAM_COLORS[real_team_name]
                cursor.execute("""
                    UPDATE teams 
                    SET team_color_1 = %s, team_color_2 = %s, team_color_3 = %s
                    WHERE team_id = %s
                """, (colors[0], colors[1], colors[2], team_id))
                updated_count += 1
                print(f"Updated {real_team_name}: {colors[0]}, {colors[1]}, {colors[2]}")
            else:
                print(f"No colors found for: {real_team_name}")
        
        conn.commit()
        cursor.close()
        print(f"Successfully updated {updated_count} teams with colors")
        return True
        
    except Exception as e:
        print(f"Error updating team colors: {e}")
        conn.rollback()
        return False

def main():
    """Main function"""
    print("Starting team colors update...")
    
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    try:
        success = update_team_colors(conn)
        if success:
            print("Team colors update completed successfully!")
        else:
            print("Team colors update completed with errors!")
        
        return success
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
