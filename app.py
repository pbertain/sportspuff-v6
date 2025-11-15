#!/usr/bin/env python3
"""
Sportspuff-v6 Web Application
Flask-based CRUD interface for managing teams and stadiums
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import requests
import logging
from datetime import datetime, timezone
from functools import wraps
from dotenv import load_dotenv

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Simple cache for API responses
_api_cache = {}
_cache_ttl = {
    'schedule': 300,  # 5 minutes for schedules
    'scores': 30,     # 30 seconds for scores (increased to reduce API calls since API can be slow)
}

def get_cached_response(cache_key, cache_type):
    """Get cached response if still valid"""
    if cache_key in _api_cache:
        cached_data, timestamp = _api_cache[cache_key]
        ttl = _cache_ttl.get(cache_type, 60)
        if (datetime.now(timezone.utc) - timestamp).total_seconds() < ttl:
            return cached_data
    return None

def set_cached_response(cache_key, data):
    """Store response in cache"""
    _api_cache[cache_key] = (data, datetime.now(timezone.utc))
    # Clean up old cache entries (keep last 100)
    if len(_api_cache) > 100:
        oldest_key = min(_api_cache.keys(), key=lambda k: _api_cache[k][1])
        del _api_cache[oldest_key]

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Enable CORS for API proxy routes
CORS(app, resources={r"/api/proxy/*": {"origins": "*"}})

# API configuration - use environment variable or default to production
API_BASE_URL = os.getenv('SPORTSPUFF_API_BASE_URL', 'https://api.sportspuff.org')
logger.info(f"API_BASE_URL configured as: {API_BASE_URL}")

# Load logo mapping
LOGO_MAPPING = {}
try:
    with open('logo_mapping.json', 'r') as f:
        LOGO_MAPPING = json.load(f)
except FileNotFoundError:
    print("Logo mapping not found. Run create_logo_mapping.py to generate it.")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'sportspuff_v6'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

def get_db_connection():
    """Get database connection"""
    try:
        logger.info(f"Attempting database connection with config: host={DB_CONFIG['host']}, database={DB_CONFIG['database']}, user={DB_CONFIG['user']}")
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info("Database connection successful")
        return conn
    except psycopg2.Error as e:
        # Log the error
        logger.error(f'Database connection error: {e}', exc_info=True)
        # Only flash if we're in a request context
        try:
            flash(f'Database connection error: {e}', 'error')
        except RuntimeError:
            # Outside request context, just print the error
            print(f'Database connection error: {e}')
        return None

@app.route('/')
def index():
    """Home page with overview statistics"""
    conn = get_db_connection()
    if not conn:
        logger.warning("get_db_connection() returned None - database unavailable")
        # Fallback data when database is not available
        return render_template('index.html', 
                             team_count=0,
                             stadium_count=0,
                             linked_count=0,
                             league_stats=[],
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors={},
                             API_BASE_URL=API_BASE_URL,
                             db_available=False)
    
    logger.info("Database connection obtained, executing queries")
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) as count FROM teams")
        team_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM stadiums")
        stadium_count = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count FROM teams t 
            JOIN stadiums s ON t.stadium_id = s.stadium_id
        """)
        linked_count = cursor.fetchone()['count']
        
        # Get league breakdown
        cursor.execute("""
            SELECT l.league_name_proper as league, COUNT(t.team_id) as count 
            FROM leagues l
            LEFT JOIN teams t ON l.league_id = t.league_id
            GROUP BY l.league_id, l.league_name_proper
            ORDER BY count DESC
        """)
        league_stats = cursor.fetchall()
        
        # Get team colors and logos for all leagues (for scores display)
        # Use full_team_name for proper capitalization and spacing
        cursor.execute("""
            SELECT t.full_team_name, t.real_team_name, t.team_color_1, t.team_color_2, t.team_color_3, 
                   t.logo_filename, t.team_abbreviation, l.league_name, l.league_name_proper
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE LOWER(l.league_name_proper) IN ('nba', 'nhl', 'mlb', 'nfl', 'mls', 'wnba')
            AND t.team_color_1 IS NOT NULL
        """)
        all_teams = cursor.fetchall()
        
        # Create a mapping of league -> team name -> colors and logo
        # Use full_team_name as primary key (has proper capitalization and spaces)
        # Also create variations for common name differences (e.g., "LA Clippers" vs "Los Angeles Clippers")
        team_colors = {}
        for team in all_teams:
            league_proper = team['league_name_proper']
            if league_proper not in team_colors:
                team_colors[league_proper] = {}
            
            # Build logo URL using splitsp.lat format: {team_name}_logo.png
            logo_url = '/static/images/no-logo.png'
            if team['logo_filename']:
                league_lower = team['league_name'].lower()
                # Use splitsp.lat for all logos
                logo_url = f'https://www.splitsp.lat/logos/{league_lower}/{team["logo_filename"]}'
            
            # Get team abbreviation - use from database if available, otherwise generate
            abbrev = team.get('team_abbreviation')
            if not abbrev:
                abbrev = get_team_abbreviation(team['real_team_name'], league_proper)
            
            # Use real_team_name as primary key (has spaces between words)
            full_name = team['full_team_name']
            real_name = team['real_team_name']
            
            team_data = {
                'color_1': team['team_color_1'],
                'color_2': team['team_color_2'],
                'color_3': team['team_color_3'],
                'logo_url': logo_url,
                'abbreviation': abbrev,
                'full_team_name': full_name,  # Store full team name as backup
                'real_team_name': real_name   # Store real team name for display (has spaces)
            }
            
            # Map real_team_name (primary) - this has spaces between words
            team_colors[league_proper][real_name] = team_data
            
            # Also map full_team_name for backward compatibility
            if full_name and full_name != real_name:
                team_colors[league_proper][full_name] = team_data
            
            # Map common variations using real_team_name (which has spaces)
            # Los Angeles variations
            if 'Los Angeles' in real_name:
                # Map "LA Clippers" to "Los Angeles Clippers"
                team_colors[league_proper][real_name.replace('Los Angeles', 'LA')] = team_data
            elif real_name.startswith('LA '):
                # Map "Los Angeles Clippers" to "LA Clippers"
                team_colors[league_proper][real_name.replace('LA ', 'Los Angeles ')] = team_data
            
            # New York variations
            if 'New York' in real_name:
                team_colors[league_proper][real_name.replace('New York', 'NY')] = team_data
            elif real_name.startswith('NY '):
                team_colors[league_proper][real_name.replace('NY ', 'New York ')] = team_data
            
            # San Francisco variations
            if 'San Francisco' in real_name:
                team_colors[league_proper][real_name.replace('San Francisco', 'SF')] = team_data
            elif real_name.startswith('SF '):
                team_colors[league_proper][real_name.replace('SF ', 'San Francisco ')] = team_data
            
            # NFL-specific mappings: Map abbreviations and common variations
            if league_proper == 'NFL':
                # NFL team abbreviation mappings (API often returns abbreviations)
                nfl_abbrev_map = {
                    'ARI': 'Arizona Cardinals',
                    'ATL': 'Atlanta Falcons',
                    'BAL': 'Baltimore Ravens',
                    'BUF': 'Buffalo Bills',
                    'CAR': 'Carolina Panthers',
                    'CHI': 'Chicago Bears',
                    'CIN': 'Cincinnati Bengals',
                    'CLE': 'Cleveland Browns',
                    'DAL': 'Dallas Cowboys',
                    'DEN': 'Denver Broncos',
                    'DET': 'Detroit Lions',
                    'GB': 'Green Bay Packers',
                    'HOU': 'Houston Texans',
                    'IND': 'Indianapolis Colts',
                    'JAX': 'Jacksonville Jaguars',
                    'KC': 'Kansas City Chiefs',
                    'LV': 'Las Vegas Raiders',
                    'LAC': 'Los Angeles Chargers',
                    'LAR': 'Los Angeles Rams',
                    'MIA': 'Miami Dolphins',
                    'MIN': 'Minnesota Vikings',
                    'NE': 'New England Patriots',
                    'NO': 'New Orleans Saints',
                    'NYG': 'New York Giants',
                    'NYJ': 'New York Jets',
                    'PHI': 'Philadelphia Eagles',
                    'PIT': 'Pittsburgh Steelers',
                    'SF': 'San Francisco 49ers',
                    'SEA': 'Seattle Seahawks',
                    'TB': 'Tampa Bay Buccaneers',
                    'TEN': 'Tennessee Titans',
                    'WSH': 'Washington Commanders',
                    'WAS': 'Washington Commanders'  # Alternative abbreviation
                }
                
                # Map abbreviations to real team name (which has spaces)
                for abbrev, mapped_name in nfl_abbrev_map.items():
                    if mapped_name == real_name or mapped_name == full_name:
                        # Map abbreviation to this team
                        team_colors[league_proper][abbrev] = team_data
                        # Also map just the team name part (e.g., "Cardinals", "Eagles")
                        team_name_only = real_name.split()[-1]  # Last word
                        if team_name_only:
                            team_colors[league_proper][team_name_only] = team_data
                            # Also map "City Team" format (e.g., "Arizona Cardinals")
                            city_part = ' '.join(real_name.split()[:-1])
                            if city_part:
                                team_colors[league_proper][f"{city_part} {team_name_only}"] = team_data
                                # Map common city abbreviations
                                if city_part == 'New England':
                                    team_colors[league_proper]['NE Patriots'] = team_data
                                    team_colors[league_proper]['New England'] = team_data
                                elif city_part == 'Kansas City':
                                    team_colors[league_proper]['KC Chiefs'] = team_data
                                    team_colors[league_proper]['Kansas City'] = team_data
                                elif city_part == 'Tampa Bay':
                                    team_colors[league_proper]['TB Buccaneers'] = team_data
                                    team_colors[league_proper]['Tampa Bay'] = team_data
                                elif city_part == 'Green Bay':
                                    team_colors[league_proper]['GB Packers'] = team_data
                                    team_colors[league_proper]['Green Bay'] = team_data
                                elif city_part == 'Las Vegas':
                                    team_colors[league_proper]['LV Raiders'] = team_data
                                    team_colors[league_proper]['Las Vegas'] = team_data
                                elif 'Los Angeles' in city_part:
                                    team_colors[league_proper][full_name.replace('Los Angeles', 'LA')] = team_data
                                    if 'Chargers' in full_name:
                                        team_colors[league_proper]['LAC'] = team_data
                                    elif 'Rams' in full_name:
                                        team_colors[league_proper]['LAR'] = team_data
        
        # Keep nba_team_colors for backward compatibility
        nba_team_colors = team_colors.get('NBA', {})
        
        cursor.close()
        conn.close()
        
        return render_template('index.html', 
                             team_count=team_count,
                             stadium_count=stadium_count,
                             linked_count=linked_count,
                             league_stats=league_stats,
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors=nba_team_colors,
                             team_colors=team_colors,
                             API_BASE_URL=API_BASE_URL,
                             db_available=True)
    
    except Exception as e:
        logger.error(f'Error loading dashboard: {e}', exc_info=True)
        flash(f'Error loading dashboard: {e}', 'error')
        if conn:
            try:
                conn.close()
            except:
                pass
        return render_template('index.html', 
                             team_count=0,
                             stadium_count=0,
                             linked_count=0,
                             league_stats=[],
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors={},
                             team_colors={'NBA': {}, 'NHL': {}},
                             API_BASE_URL=API_BASE_URL,
                             db_available=False)

@app.route('/admin')
def admin_panel():
    """Admin panel showing statistics and management options"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message='Database connection failed')
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get team count
        cursor.execute("SELECT COUNT(*) as team_count FROM teams")
        team_count = cursor.fetchone()['team_count']
        
        # Get stadium count
        cursor.execute("SELECT COUNT(*) as stadium_count FROM stadiums")
        stadium_count = cursor.fetchone()['stadium_count']
        
        # Get linked teams count (teams with stadiums)
        cursor.execute("SELECT COUNT(*) as linked_count FROM teams WHERE stadium_id IS NOT NULL")
        linked_count = cursor.fetchone()['linked_count']
        
        cursor.close()
        conn.close()
        
        return render_template('admin.html', 
                             team_count=team_count,
                             stadium_count=stadium_count,
                             linked_count=linked_count,
                             logo_mapping=LOGO_MAPPING)
    
    except Exception as e:
        return render_template('error.html', message=str(e))

@app.route('/league/<league_name>')
def league_page(league_name):
    """League page showing teams organized by divisions"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message='Database connection failed')
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get teams for this league organized by divisions (exclude ALL placeholder league teams)
        teams_query = """
            SELECT t.team_id, t.real_team_name, t.city_name, t.state_name, t.country,
                   t.logo_filename, t.team_color_1, t.team_color_2, t.team_color_3,
                   s.full_stadium_name, s.city_name as stadium_city, s.state_name as stadium_state,
                   c.conference_name, d.division_name,
                   l.league_name_proper as team_league
            FROM teams t
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            LEFT JOIN conferences c ON t.conference_id = c.conference_id
            LEFT JOIN divisions d ON t.division_id = d.division_id
            WHERE l.league_name_proper = %s 
            AND t.real_team_name NOT IN (
                'Major League Baseball', 'National Football League', 'National Basketball Association',
                'National Hockey League', 'Major League Soccer', 'Women''s National Basketball League',
                'India Premier League'
            )
            ORDER BY COALESCE(c.conference_name, 'No Conference'), COALESCE(d.division_name, 'No Division'), t.real_team_name
        """
        cursor.execute(teams_query, [league_name])
        teams = cursor.fetchall()
        
        # Organize teams by conference and division
        organized_teams = {}
        for team in teams:
            conference = team['conference_name'] or 'No Conference'
            division = team['division_name'] or 'No Division'
            
            if conference not in organized_teams:
                organized_teams[conference] = {}
            if division not in organized_teams[conference]:
                organized_teams[conference][division] = []
            
            organized_teams[conference][division].append(team)
        
        # Get league info including champion details
        league_query = """
            SELECT l.league_name_proper, l.league_name, l.logo_filename, l.team_count,
                   l.current_champion_id, c.real_team_name as champion_name, c.logo_filename as champion_logo,
                   c.team_color_1 as champion_color_1, c.team_color_2 as champion_color_2, c.team_color_3 as champion_color_3
            FROM leagues l
            LEFT JOIN teams c ON l.current_champion_id = c.team_id
            WHERE LOWER(l.league_name_proper) = LOWER(%s)
        """
        cursor.execute(league_query, [league_name])
        league_info = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return render_template('league_page.html', 
                             league_name=league_name,
                             organized_teams=organized_teams,
                             logo_mapping=LOGO_MAPPING,
                             league_info=league_info)
    
    except Exception as e:
        return render_template('error.html', message=str(e))

def get_team_abbreviation(team_name, league):
    """Get three-letter abbreviation for a team based on league and team name"""
    # NFL abbreviations
    nfl_abbrev_map = {
        'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
        'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
        'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
        'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
        'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
        'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
        'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
        'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
        'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
        'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
        'Tennessee Titans': 'TEN', 'Washington Commanders': 'WSH'
    }
    # Also map common variations
    nfl_abbrev_map['New York Jets'] = 'NYJ'
    nfl_abbrev_map['New England Patriots'] = 'NE'
    
    # NBA abbreviations (common 3-letter abbreviations)
    nba_abbrev_map = {
        'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
        'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
        'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
        'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
        'LA Clippers': 'LAC', 'Los Angeles Clippers': 'LAC', 'Los Angeles Lakers': 'LAL',
        'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL',
        'Minnesota Timberwolves': 'MIN', 'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK',
        'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI',
        'Phoenix Suns': 'PHX', 'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC',
        'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA',
        'Washington Wizards': 'WAS'
    }
    
    # NHL abbreviations
    nhl_abbrev_map = {
        'Anaheim Ducks': 'ANA', 'Arizona Coyotes': 'ARI', 'Boston Bruins': 'BOS',
        'Buffalo Sabres': 'BUF', 'Calgary Flames': 'CGY', 'Carolina Hurricanes': 'CAR',
        'Chicago Blackhawks': 'CHI', 'Colorado Avalanche': 'COL', 'Columbus Blue Jackets': 'CBJ',
        'Dallas Stars': 'DAL', 'Detroit Red Wings': 'DET', 'Edmonton Oilers': 'EDM',
        'Florida Panthers': 'FLA', 'Los Angeles Kings': 'LAK', 'Minnesota Wild': 'MIN',
        'Montreal Canadiens': 'MTL', 'Nashville Predators': 'NSH', 'New Jersey Devils': 'NJD',
        'New York Islanders': 'NYI', 'New York Rangers': 'NYR', 'Ottawa Senators': 'OTT',
        'Philadelphia Flyers': 'PHI', 'Pittsburgh Penguins': 'PIT', 'San Jose Sharks': 'SJS',
        'Seattle Kraken': 'SEA', 'St. Louis Blues': 'STL', 'Tampa Bay Lightning': 'TBL',
        'Toronto Maple Leafs': 'TOR', 'Vegas Golden Knights': 'VGK', 'Vancouver Canucks': 'VAN',
        'Washington Capitals': 'WSH', 'Winnipeg Jets': 'WPG'
    }
    
    # MLB abbreviations
    mlb_abbrev_map = {
        'Arizona Diamondbacks': 'ARI', 'Atlanta Braves': 'ATL', 'Baltimore Orioles': 'BAL',
        'Boston Red Sox': 'BOS', 'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CWS',
        'Cincinnati Reds': 'CIN', 'Cleveland Guardians': 'CLE', 'Colorado Rockies': 'COL',
        'Detroit Tigers': 'DET', 'Houston Astros': 'HOU', 'Kansas City Royals': 'KC',
        'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD', 'Miami Marlins': 'MIA',
        'Milwaukee Brewers': 'MIL', 'Minnesota Twins': 'MIN', 'New York Mets': 'NYM',
        'New York Yankees': 'NYY', 'Oakland Athletics': 'OAK', 'Philadelphia Phillies': 'PHI',
        'Pittsburgh Pirates': 'PIT', 'San Diego Padres': 'SD', 'San Francisco Giants': 'SF',
        'Seattle Mariners': 'SEA', 'St. Louis Cardinals': 'STL', 'Tampa Bay Rays': 'TB',
        'Texas Rangers': 'TEX', 'Toronto Blue Jays': 'TOR', 'Washington Nationals': 'WSH'
    }
    
    # Select the appropriate map based on league
    abbrev_map = {}
    if league.upper() == 'NFL':
        abbrev_map = nfl_abbrev_map
    elif league.upper() == 'NBA':
        abbrev_map = nba_abbrev_map
    elif league.upper() == 'NHL':
        abbrev_map = nhl_abbrev_map
    elif league.upper() == 'MLB':
        abbrev_map = mlb_abbrev_map
    
    # Try exact match first
    if team_name in abbrev_map:
        return abbrev_map[team_name]
    
    # Try case-insensitive match
    for key, abbrev in abbrev_map.items():
        if key.lower() == team_name.lower():
            return abbrev
    
    # Fallback: Generate abbreviation from team name (first letter of each word, max 3)
    words = team_name.split()
    if len(words) >= 2:
        # Take first letter of first two words, or first three letters of first word
        abbrev = (words[0][0] + words[1][0] + (words[2][0] if len(words) > 2 else words[0][1] if len(words[0]) > 1 else '')).upper()
        return abbrev[:3]
    elif len(words) == 1:
        # Single word: take first 3 letters
        return words[0][:3].upper()
    
    return ''

@app.route('/teams')
def teams():
    """List all teams with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    league_filter = request.args.get('league', '')
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    if not conn:
        # Return empty teams list when database is not available
        return render_template('teams.html', 
                             teams=[],
                             pagination=None,
                             league_filter=league_filter,
                             search=search,
                             logo_mapping=LOGO_MAPPING,
                             db_available=False)
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query with filters
        where_conditions = []
        params = []
        
        if league_filter:
            where_conditions.append("l.league_name_proper = %s")
            params.append(league_filter)
        
        if search:
            where_conditions.append("(t.real_team_name ILIKE %s OR t.city_name ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as count 
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            {where_clause}
        """
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['count']
        
        # Get teams with pagination
        offset = (page - 1) * per_page
        teams_query = f"""
            SELECT t.*, s.full_stadium_name, s.city_name as stadium_city, s.state_name as stadium_state,
                   l.league_name_proper as league
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            {where_clause}
            ORDER BY t.real_team_name
            LIMIT %s OFFSET %s
        """
        cursor.execute(teams_query, params + [per_page, offset])
        teams = cursor.fetchall()
        
        # Add abbreviations to each team
        for team in teams:
            team['abbreviation'] = get_team_abbreviation(team['real_team_name'], team.get('league', ''))
        
        # Get divisions for the selected league
        divisions = []
        if league_filter:
            divisions_query = """
                SELECT d.division_name as division, COUNT(t.team_id) as team_count
                FROM divisions d
                JOIN leagues l ON d.league_id = l.league_id
                LEFT JOIN teams t ON d.division_id = t.division_id
                WHERE l.league_name_proper = %s
                GROUP BY d.division_id, d.division_name
                ORDER BY d.division_name
            """
            cursor.execute(divisions_query, [league_filter])
            divisions = cursor.fetchall()
        
        # Get leagues for filter dropdown
        cursor.execute("SELECT league_name_proper FROM leagues ORDER BY league_name_proper")
        leagues = [row['league_name_proper'] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        return render_template('teams.html', 
                             teams=teams,
                             leagues=leagues,
                             divisions=divisions,
                             current_league=league_filter,
                             search=search,
                             page=page,
                             total_pages=total_pages,
                             total_count=total_count,
                             logo_mapping=LOGO_MAPPING)
    
    except Exception as e:
        flash(f'Error loading teams: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/stadiums')
def stadiums():
    """List all stadiums with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Database connection failed")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Build query with search filter
        where_clause = ""
        params = []
        
        if search:
            where_clause = "WHERE (full_stadium_name ILIKE %s OR city_name ILIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM stadiums {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['count']
        
        # Get stadiums with pagination
        offset = (page - 1) * per_page
        stadiums_query = f"""
            SELECT s.*, COUNT(t.team_id) as team_count
            FROM stadiums s
            LEFT JOIN teams t ON s.stadium_id = t.stadium_id
            {where_clause}
            GROUP BY s.stadium_id
            ORDER BY s.full_stadium_name
            LIMIT %s OFFSET %s
        """
        # Note: s.image field contains stadium image path if available (may be relative path like 'stadiums/league/stadium_name_img.png')
        cursor.execute(stadiums_query, params + [per_page, offset])
        stadiums = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Calculate pagination
        total_pages = (total_count + per_page - 1) // per_page
        
        return render_template('stadiums.html', 
                             stadiums=stadiums,
                             search=search,
                             page=page,
                             total_pages=total_pages,
                             total_count=total_count)
    
    except Exception as e:
        flash(f'Error loading stadiums: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/team/<league_name>/<team_name>')
def team_detail_by_name(league_name, team_name):
    """Show team details by league and team name"""
    conn = get_db_connection()
    if not conn:
        return render_template("error.html", message="Database connection failed")

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT t.team_id, t.full_team_name, t.team_name, t.real_team_name, t.league_id,
                   t.division_id, t.conference_id, t.team_league_id, t.city_name, t.state_name,
                   t.country, t.stadium_id, t.logo_filename,
                   t.team_color_1, t.team_color_2, t.team_color_3,
                   s.stadium_id as s_stadium_id, s.full_stadium_name, s.stadium_name, s.city_name as stadium_city, 
                   s.state_name as stadium_state, s.capacity, s.surface, s.roof_type, s.year_opened,
                   s.location_name, s.coordinates, s.country as s_country, s.baseball_distance_to_center_field_ft,
                   s.baseball_distance_to_center_field_m, s.soccer_field_length_yd, s.soccer_field_width_yd,
                   s.soccer_field_length_m, s.soccer_field_width_m, s.stadium_type, s.first_sport_year,
                   l.league_name_proper as team_league,
                   conf.conference_name, div.division_name
            FROM teams t
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            LEFT JOIN conferences conf ON t.conference_id = conf.conference_id
            LEFT JOIN divisions div ON t.division_id = div.division_id
            WHERE LOWER(l.league_name_proper) = LOWER(%s)
            AND LOWER(REPLACE(t.real_team_name, ' ', '_')) = LOWER(%s)
        """, (league_name, team_name))

        team = cursor.fetchone()

        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams'))

        cursor.close()
        conn.close()

        return render_template('team_detail_horizontal.html', team=team)

    except Exception as e:
        flash(f'Error loading team: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/team/<int:team_id>')
def team_detail(team_id):
    """Show team details"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Database connection failed")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT t.team_id, t.full_team_name, t.team_name, t.real_team_name, t.league_id,
                   t.division_id, t.conference_id, t.team_league_id, t.city_name, t.state_name,
                   t.country, t.stadium_id, t.logo_filename,
                   t.team_color_1, t.team_color_2, t.team_color_3,
                   s.stadium_id as s_stadium_id, s.full_stadium_name, s.stadium_name, s.city_name as stadium_city, 
                   s.state_name as stadium_state, s.capacity, s.surface, s.roof_type, s.year_opened,
                   s.location_name, s.coordinates, s.country as s_country, s.baseball_distance_to_center_field_ft,
                   s.baseball_distance_to_center_field_m, s.soccer_field_length_yd, s.soccer_field_width_yd,
                   s.soccer_field_length_m, s.soccer_field_width_m, s.stadium_type, s.first_sport_year,
                   l.league_name_proper as team_league,
                   conf.conference_name, div.division_name
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            LEFT JOIN conferences conf ON t.conference_id = conf.conference_id
            LEFT JOIN divisions div ON t.division_id = div.division_id
            WHERE t.team_id = %s
        """, (team_id,))
        
        team = cursor.fetchone()
        
        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams'))
        
        cursor.close()
        conn.close()
        
        return render_template('team_detail_horizontal.html', team=team)
    
    except Exception as e:
        flash(f'Error loading team: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/stadium/<int:stadium_id>')
def stadium_detail(stadium_id):
    """Show stadium details"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Database connection failed")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get stadium info
        cursor.execute("SELECT * FROM stadiums WHERE stadium_id = %s", (stadium_id,))
        stadium = cursor.fetchone()
        
        if not stadium:
            flash('Stadium not found', 'error')
            return redirect(url_for('stadiums'))
        
        # Get teams using this stadium
        cursor.execute("""
            SELECT t.team_id, t.real_team_name, t.city_name, t.state_name,
                   t.team_color_1, t.team_color_2, t.team_color_3,
                   s.full_stadium_name,
                   l.league_name_proper
            FROM teams t
            LEFT JOIN leagues l ON t.league_id = l.league_id
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            WHERE t.stadium_id = %s
            ORDER BY l.league_name_proper, t.real_team_name
        """, (stadium_id,))
        
        teams = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('stadium_detail_horizontal.html', stadium=stadium, teams=teams)
    
    except Exception as e:
        flash(f'Error loading stadium: {e}', 'error')
        return render_template('error.html', message=str(e))

@app.route('/api/teams')
def api_teams():
    """API endpoint for teams data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT t.team_id, t.real_team_name, l.league_name_proper as league, t.city_name, t.state_name,
                   s.full_stadium_name, s.stadium_id
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            ORDER BY t.real_team_name
        """)
        
        teams = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify([dict(team) for team in teams])
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stadiums')
def api_stadiums():
    """API endpoint for stadiums data"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT s.*, COUNT(t.team_id) as team_count
            FROM stadiums s
            LEFT JOIN teams t ON s.stadium_id = t.stadium_id
            GROUP BY s.stadium_id
            ORDER BY s.full_stadium_name
        """)
        
        stadiums = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify([dict(stadium) for stadium in stadiums])
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/static/logos/<path:filename>')
def serve_logo(filename):
    """Serve logo files from splitsp.lat"""
    # Redirect to splitsp.lat for logos
    from flask import redirect
    return redirect(f'https://www.splitsp.lat/logos/{filename}', code=302)


@app.template_filter('get_logo')
def get_logo(team_id):
    """Template filter to get team logo from splitsp.lat using logo_filename column"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT l.league_name_proper, t.logo_filename 
                FROM teams t 
                LEFT JOIN leagues l ON t.league_id = l.league_id 
                WHERE t.team_id = %s
            """, [team_id])
            team = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if team and team['logo_filename']:
                league = team['league_name_proper'].lower()
                logo_filename = team['logo_filename']
                return f'https://www.splitsp.lat/logos/{league}/{logo_filename}'
        except:
            pass
    
    return '/static/images/no-logo.png'

@app.template_filter('get_league_logo')
def get_league_logo(league):
    """Template filter to get league logo - try local first, then splitsp.lat"""
    if league:
        league_lower = league.lower()
        # Try local first
        local_logo = f'/static/images/logos/{league_lower}/{league_lower}_logo.png'
        # For now, use splitsp.lat as fallback
        # Use correct acronym-based URLs
        if league_lower == 'mlb':
            return 'https://www.splitsp.lat/logos/mlb/mlb_logo.png'
        elif league_lower == 'nfl':
            return 'https://www.splitsp.lat/logos/nfl/nfl_logo.png'
        elif league_lower == 'nba':
            return '/static/images/logos/nba/nba_logo.png'
        elif league_lower == 'nhl':
            return 'https://www.splitsp.lat/logos/nhl/nhl_logo.png'
        elif league_lower == 'mls':
            return 'https://www.splitsp.lat/logos/mls/mls_logo.png'
        elif league_lower == 'wnba':
            return 'https://www.splitsp.lat/logos/wnba/wnba_logo.png'
        else:
            return f'https://www.splitsp.lat/logos/{league_lower}/{league_lower}_logo.png'
    return '/static/images/no-logo.png'

@app.route('/api/proxy/schedule/<league>/<date>')
def proxy_schedule(league, date):
    """Proxy schedule API requests to avoid CORS issues with caching"""
    try:
        # Get timezone from query parameter, default to 'pst'
        tz = request.args.get('tz', 'pst')
        
        # For "today", use actual date for cache key but pass "today" to API
        # API only accepts "today" as a keyword, not date strings
        if date.lower() == 'today':
            actual_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            cache_key = f'schedule:{league}:{actual_date}:{tz}'
            api_date = 'today'  # API only accepts "today", not date strings
        else:
            cache_key = f'schedule:{league}:{date}:{tz}'
            api_date = date
        
        # Check cache first - but verify it's for today's date
        # Use cache more aggressively since API can be slow
        cached_response = get_cached_response(cache_key, 'schedule')
        if cached_response:
            # Verify the cached data is for today (check response date field)
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if cached_date == today_date:
                logger.info(f"Returning cached schedule for {league} from {cached_date}")
                return jsonify(cached_response)
            # If cached date doesn't match today, clear it and fetch fresh
        
        # Fetch from API with timezone parameter
        api_base = os.getenv('SPORTSPUFF_API_BASE_URL', '')
        if not api_base:
            # Try to get from default API_BASE_URL if defined
            try:
                api_base = API_BASE_URL
            except NameError:
                api_base = None
        if not api_base:
            logger.error("SPORTSPUFF_API_BASE_URL not configured")
            return jsonify({'error': 'API base URL not configured'}), 500
        url = f'{api_base}/api/v1/schedule/{league}/{api_date}?tz={tz}'
        logger.info(f"Fetching schedule from: {url} (timeout=60s)")
        try:
            # Use a longer timeout and verify SSL
            response = requests.get(url, timeout=60, verify=True, allow_redirects=True)
            logger.info(f"Schedule API response status: {response.status_code}, length: {len(response.content)}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching schedule from {url} after 60s")
            return jsonify({'error': 'API request timed out after 60 seconds'}), 500
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception fetching schedule: {e}", exc_info=True)
            return jsonify({'error': f'API request failed: {str(e)}'}), 500
        
        # Check if response is successful
        if response.status_code != 200:
            error_msg = f'API returned status {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                error_msg = f'API returned status {response.status_code}: {response.text[:200]}'
            logger.error(f"Error proxying schedule request: {error_msg}")
            return jsonify({'error': error_msg}), response.status_code if response.status_code < 500 else 500
        
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON from schedule API: {e}, response text: {response.text[:500]}")
            return jsonify({'error': 'Invalid JSON response from API'}), 500
        
        # Check for API errors in response
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"API returned error: {data['error']}")
            return jsonify(data), 500
        
        # Cache the response
        set_cached_response(cache_key, data)
        
        return jsonify(data)
    except requests.exceptions.Timeout:
        logger.error(f"Timeout proxying schedule request to {url}")
        return jsonify({'error': 'API request timed out'}), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying schedule request: {e}")
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in proxy_schedule: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/nfl/team-records')
def nfl_team_records():
    """Fetch NFL team records from Tank01 API"""
    try:
        rapidapi_key = os.getenv('RAPIDAPI_KEY', '')
        if not rapidapi_key:
            logger.warning("RAPIDAPI_KEY not set, cannot fetch NFL team records")
            # Return empty records instead of 500 - frontend can handle this gracefully
            return jsonify({'teams': {}}), 200
        
        url = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLTeams"
        querystring = {
            "sortBy": "standings",
            "rosters": "false",
            "schedules": "false",
            "topPerformers": "true",
            "teamStats": "true",
            "teamStatsSeason": "2024"
        }
        headers = {
            "x-rapidapi-key": rapidapi_key,
            "x-rapidapi-host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
        }
        
        logger.info("Fetching NFL team records from Tank01 API")
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('statusCode') == 200 and 'body' in data:
            teams = data['body']
            # Create a mapping of team name to record
            # Team name format: teamCity + " " + teamName (e.g., "New England Patriots")
            team_records = {}
            for team in teams:
                team_city = team.get('teamCity', '')
                team_name = team.get('teamName', '')
                full_team_name = f"{team_city} {team_name}".strip()
                
                # Get record values (API returns as strings)
                wins = int(team.get('wins', 0)) if team.get('wins') else 0
                loss = int(team.get('loss', 0)) if team.get('loss') else 0
                tie = int(team.get('tie', 0)) if team.get('tie') else 0
                
                # Store by full team name
                team_records[full_team_name] = {
                    'wins': wins,
                    'losses': loss,
                    'ties': tie
                }
                
                # Also store by abbreviation if available
                team_abv = team.get('teamAbv', '').strip()
                if team_abv:
                    team_records[team_abv] = {
                        'wins': wins,
                        'losses': loss,
                        'ties': tie
                    }
            
            logger.info(f"Fetched records for {len(team_records)} NFL teams")
            return jsonify({'teams': team_records}), 200
        else:
            logger.error(f"Unexpected API response: {data}")
            # Return empty records instead of 500 - frontend can handle this gracefully
            return jsonify({'teams': {}}), 200
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching NFL team records: {e}")
        # Return empty records instead of 500 - frontend can handle this gracefully
        return jsonify({'teams': {}}), 200
    except Exception as e:
        logger.error(f"Unexpected error fetching NFL team records: {e}", exc_info=True)
        # Return empty records instead of 500 - frontend can handle this gracefully
        return jsonify({'teams': {}}), 200

@app.route('/api/proxy/scores/<league>/<date>')
def proxy_scores(league, date):
    """Proxy scores API requests to avoid CORS issues with very short caching"""
    try:
        # Get timezone from query parameter, default to 'pst'
        tz = request.args.get('tz', 'pst')
        
        # For "today", use actual date for cache key but pass "today" to API
        # API only accepts "today" as a keyword, not date strings
        if date.lower() == 'today':
            actual_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            cache_key = f'scores:{league}:{actual_date}:{tz}'
            api_date = 'today'  # API only accepts "today", not date strings
        else:
            cache_key = f'scores:{league}:{date}:{tz}'
            api_date = date
        
        # Check cache - use it if available and from today
        # Cache TTL is 5 seconds, so we'll use it if very recent
        cached_response = get_cached_response(cache_key, 'scores')
        if cached_response:
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            # Only use cache if it's from today AND very recent (< 5 seconds)
            if cached_date == today_date:
                logger.info(f"Returning cached scores for {league} from {cached_date}")
                return jsonify(cached_response)
        
        # Always fetch fresh scores (cache is just for rapid consecutive requests)
        api_base = os.getenv('SPORTSPUFF_API_BASE_URL', '')
        if not api_base:
            # Try to get from default API_BASE_URL if defined
            try:
                api_base = API_BASE_URL
            except NameError:
                api_base = None
        if not api_base:
            logger.error("SPORTSPUFF_API_BASE_URL not configured")
            return jsonify({'error': 'API base URL not configured'}), 500
        url = f'{api_base}/api/v1/scores/{league}/{api_date}?tz={tz}'
        logger.info(f"Fetching scores from: {url} (timeout=60s)")
        try:
            # Use a longer timeout and verify SSL
            response = requests.get(url, timeout=60, verify=True, allow_redirects=True)
            logger.info(f"Scores API response status: {response.status_code}, length: {len(response.content)}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching scores from {url} after 60s")
            # Try cached response as fallback
            if 'cached_response' in locals() and cached_response:
                cached_date = cached_response.get('date', '')
                today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                if cached_date == today_date:
                    logger.info("Returning cached scores as fallback after timeout")
                    return jsonify(cached_response)
            return jsonify({'error': 'API request timed out after 60 seconds'}), 500
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception fetching scores: {e}", exc_info=True)
            # Try cached response as fallback
            if 'cached_response' in locals() and cached_response:
                cached_date = cached_response.get('date', '')
                today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                if cached_date == today_date:
                    logger.info("Returning cached scores as fallback after request exception")
                    return jsonify(cached_response)
            return jsonify({'error': f'API request failed: {str(e)}'}), 500
        
        # Check if response is successful
        if response.status_code != 200:
            error_msg = f'API returned status {response.status_code}'
            try:
                error_data = response.json()
                error_msg = error_data.get('error', error_msg)
            except:
                error_msg = f'API returned status {response.status_code}: {response.text[:200]}'
            logger.error(f"Error proxying scores request: {error_msg}")
            # If API fails, try to return cached response as fallback only if very recent
            if 'cached_response' in locals() and cached_response:
                cached_date = cached_response.get('date', '')
                today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                if cached_date == today_date:
                    logger.info("Returning cached scores as fallback")
                    return jsonify(cached_response)
            return jsonify({'error': error_msg}), response.status_code if response.status_code < 500 else 500
        
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Failed to parse JSON from scores API: {e}, response text: {response.text[:500]}")
            # Try cached response as fallback
            if 'cached_response' in locals() and cached_response:
                cached_date = cached_response.get('date', '')
                today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                if cached_date == today_date:
                    logger.info("Returning cached scores as fallback after JSON parse error")
                    return jsonify(cached_response)
            return jsonify({'error': 'Invalid JSON response from API'}), 500
        
        # Check for API errors in response
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"API returned error: {data['error']}")
            # Try cached response as fallback
            if 'cached_response' in locals() and cached_response:
                cached_date = cached_response.get('date', '')
                today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                if cached_date == today_date:
                    logger.info("Returning cached scores as fallback")
                    return jsonify(cached_response)
            return jsonify(data), 500
        
        # Cache the response (very short TTL - 5 seconds)
        set_cached_response(cache_key, data)
        
        return jsonify(data)
    except requests.exceptions.Timeout:
        logger.error(f"Timeout proxying scores request to {url}")
        # Try cached response as fallback
        if 'cached_response' in locals() and cached_response:
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if cached_date == today_date:
                logger.info("Returning cached scores as fallback after timeout")
                return jsonify(cached_response)
        return jsonify({'error': 'API request timed out'}), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying scores request: {e}")
        # If API fails, try to return cached response as fallback only if very recent
        if 'cached_response' in locals() and cached_response:
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if cached_date == today_date:
                logger.info("Returning cached scores as fallback")
                return jsonify(cached_response)
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in proxy_scores: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/team-colors/<league>')
def get_team_colors(league):
    """Get team colors for a league, mapping team names to colors"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get teams with colors for the specified league
        cursor.execute("""
            SELECT t.real_team_name, t.team_color_1, t.team_color_2, t.team_color_3
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE LOWER(l.league_name_proper) = LOWER(%s)
            AND t.team_color_1 IS NOT NULL
        """, (league,))
        
        teams = cursor.fetchall()
        
        # Create a mapping of team name to colors
        color_map = {}
        for team in teams:
            color_map[team['real_team_name']] = {
                'color_1': team['team_color_1'],
                'color_2': team['team_color_2'],
                'color_3': team['team_color_3']
            }
        
        cursor.close()
        conn.close()
        
        return jsonify(color_map)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import sys
    port = 5000  # Default port
    
    # Check for port argument
    if len(sys.argv) > 1 and sys.argv[1] == '--port':
        try:
            port = int(sys.argv[2])
        except (IndexError, ValueError):
            print("Invalid port argument, using default port 5000")
    
    app.run(debug=True, host='0.0.0.0', port=port)
