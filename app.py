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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
_api_cache_lock = threading.RLock()
_refresh_locks = {}
_cache_ttl = {
    'schedule': 300,  # 5 minutes for schedules
    'scores': 61,     # 61 seconds - background thread refreshes every 60s
}

def get_cached_response(cache_key, cache_type, allow_expired=False):
    """Get cached response if still valid, or expired if allow_expired=True"""
    with _api_cache_lock:
        if cache_key in _api_cache:
            cached_data, timestamp = _api_cache[cache_key]
            ttl = _cache_ttl.get(cache_type, 60)
            age = (datetime.now(timezone.utc) - timestamp).total_seconds()
            if age < ttl or allow_expired:
                return cached_data
    return None

def set_cached_response(cache_key, data):
    """Store response in cache"""
    with _api_cache_lock:
        _api_cache[cache_key] = (data, datetime.now(timezone.utc))
        # Clean up old cache entries (keep last 100)
        if len(_api_cache) > 100:
            oldest_key = min(_api_cache.keys(), key=lambda k: _api_cache[k][1])
            del _api_cache[oldest_key]


def _normalize_timezone(tz):
    """Keep cache keys stable across old and new timezone aliases."""
    aliases = {
        'pst': 'pt',
        'est': 'et',
        'cst': 'ct',
        'mst': 'mt',
    }
    return aliases.get((tz or 'pt').lower(), tz)


def _empty_all_scores_response():
    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return {
        lg: {
            'schedule': {'date': today, 'games': []},
            'scores': {'date': today, 'scores': []}
        }
        for lg in leagues
    }


def _fetch_all_scores_for_tz(api_base_url, tz, api_date='today'):
    """Fetch all-scores data for a given timezone (no Flask request context needed)."""
    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc']
    result = {}

    def fetch_league(lg):
        schedule_url = f'{api_base_url}/api/v1/schedule/{lg}/{api_date}?tz={tz}'
        scores_url = f'{api_base_url}/api/v1/scores/{lg}/{api_date}?tz={tz}'
        league_data = {'schedule': {'games': []}, 'scores': {'scores': []}}
        try:
            r = requests.get(schedule_url, timeout=15)
            if r.status_code == 200:
                league_data['schedule'] = r.json()
        except Exception:
            pass
        try:
            r = requests.get(scores_url, timeout=15)
            if r.status_code == 200:
                league_data['scores'] = r.json()
        except Exception:
            pass
        return lg, league_data

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_league, lg): lg for lg in leagues}
        for future in as_completed(futures):
            try:
                lg, data = future.result()
                result[lg] = data
            except Exception:
                pass

    return result


def _refresh_all_scores_cache(api_base_url, api_date, tz):
    cache_key = f'all_scores:{api_date}:{tz}'
    data = _fetch_all_scores_for_tz(api_base_url, tz, api_date)
    if data:
        set_cached_response(cache_key, data)
    return data


def _refresh_cache_async(cache_key, refresh_func):
    """Start one background refresh for a cache key without blocking the request."""
    with _api_cache_lock:
        lock = _refresh_locks.setdefault(cache_key, threading.Lock())
    if not lock.acquire(blocking=False):
        return

    def refresh_and_release():
        try:
            refresh_func()
        except Exception as e:
            logger.error(f"Background refresh failed for {cache_key}: {e}", exc_info=True)
        finally:
            lock.release()

    threading.Thread(target=refresh_and_release, daemon=True).start()


def _fetch_nhl_playoff_series():
    """Fetch NHL playoff series (no Flask request context needed)."""
    try:
        response = requests.get('https://api-web.nhle.com/v1/schedule/now', timeout=10)
        response.raise_for_status()
        data = response.json()
        series_map = {}
        for week in data.get('gameWeek', []):
            for game in week.get('games', []):
                series = game.get('seriesStatus', {})
                if not series:
                    continue
                top = series.get('topSeedTeamAbbrev', '')
                bottom = series.get('bottomSeedTeamAbbrev', '')
                if top and bottom:
                    key = f"{min(top,bottom)}-{max(top,bottom)}"
                    series_map[key] = {
                        'top_seed': top,
                        'top_seed_wins': series.get('topSeedWins', 0),
                        'bottom_seed': bottom,
                        'bottom_seed_wins': series.get('bottomSeedWins', 0),
                        'round': series.get('round', 0),
                        'game_number_of_series': series.get('gameNumberOfSeries', 0),
                    }
                    series_map[top] = series_map[key]
                    series_map[bottom] = series_map[key]
        return {'series': series_map}
    except Exception:
        return None


def _fetch_mls_standings(api_base_url):
    """Fetch MLS standings (no Flask request context needed)."""
    try:
        response = requests.get(f'{api_base_url}/api/v1/standings/mls', timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        teams = {}
        for t in data.get('teams', []):
            abbrev = t.get('abbreviation', '')
            name = t.get('team_name', abbrev)
            teams[name] = {
                'wins': t.get('wins', 0),
                'losses': t.get('losses', 0),
                'draws': t.get('draws', 0),
                'points': t.get('points', 0)
            }
            if abbrev:
                teams[abbrev] = teams[name]
        return {'teams': teams}
    except Exception:
        return None


def _fetch_wnba_standings(api_base_url):
    """Fetch WNBA standings from sportspuff-api keyed by team name."""
    try:
        response = requests.get(f'{api_base_url}/api/v1/standings/wnba', timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        records = {}
        for t in data.get('teams', []):
            name = t.get('team_name')
            if not name:
                continue
            records[name] = {
                'wins': t.get('wins', 0),
                'losses': t.get('losses', 0),
                'games_back': t.get('games_back', '-'),
            }
        return records
    except Exception:
        return None


def _background_cache_refresh(api_base_url):
    """Background thread: refresh cache every 60 seconds."""
    timezones = ['pt', 'et', 'ct', 'mt']
    while True:
        try:
            for tz in timezones:
                _refresh_all_scores_cache(api_base_url, 'today', tz)

            nhl_data = _fetch_nhl_playoff_series()
            if nhl_data:
                set_cached_response('nhl_playoff_series', nhl_data)

            mls_data = _fetch_mls_standings(api_base_url)
            if mls_data:
                set_cached_response('mls_team_records', mls_data)

            logger.info("Background cache refresh complete")
        except Exception as e:
            logger.error(f"Background cache refresh error: {e}")

        time.sleep(60)


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Enable CORS for API proxy routes
CORS(app, resources={r"/api/proxy/*": {"origins": "*"}})

# API configuration - use environment variable or default to production
API_BASE_URL = os.getenv('SPORTSPUFF_API_BASE_URL', 'https://api.sportspuff.net')
logger.info(f"API_BASE_URL configured as: {API_BASE_URL}")

# Start background cache refresh thread (avoid duplicate in Flask reloader)
if os.getenv('DISABLE_BACKGROUND_CACHE_REFRESH') != '1' and (
    not os.environ.get('WERKZEUG_RUN_MAIN') or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
):
    _cache_thread = threading.Thread(target=_background_cache_refresh, args=(API_BASE_URL,), daemon=True)
    _cache_thread.start()
    logger.info("Background cache refresh thread started (60s interval)")

@app.context_processor
def inject_globals():
    return {'API_BASE_URL': API_BASE_URL}

SEASON_DATES = {
    'MLB': {
        'year': 2026,
        'types': [
            {'name': 'Spring Training', 'start': '2026-02-20', 'end': '2026-03-25'},
            {'name': 'Regular Season', 'start': '2026-03-26', 'end': '2026-09-27'},
            {'name': 'Postseason', 'start': '2026-09-29', 'end': '2026-11-01'},
        ]
    },
    'NBA': {
        'year': 2026,
        'types': [
            {'name': 'Preseason', 'start': '2025-10-05', 'end': '2025-10-17'},
            {'name': 'Regular Season', 'start': '2025-10-19', 'end': '2026-04-12'},
            {'name': 'Play-In', 'start': '2026-04-14', 'end': '2026-04-17'},
            {'name': 'Playoffs', 'start': '2026-04-18', 'end': '2026-06-19'},
        ]
    },
    'NFL': {
        'year': 2026,
        'types': [
            {'name': 'Preseason', 'start': '2026-08-06', 'end': '2026-08-28'},
            {'name': 'Regular Season', 'start': '2026-09-10', 'end': '2027-01-03'},
            {'name': 'Playoffs', 'start': '2027-01-09', 'end': '2027-01-31'},
            {'name': 'Super Bowl', 'start': '2027-02-07', 'end': '2027-02-07'},
        ]
    },
    'NHL': {
        'year': 2026,
        'types': [
            {'name': 'Preseason', 'start': '2025-09-21', 'end': '2025-10-03'},
            {'name': 'Regular Season', 'start': '2025-10-07', 'end': '2026-04-17'},
            {'name': 'Playoffs', 'start': '2026-04-19', 'end': '2026-06-20'},
        ]
    },
    'MLS': {
        'year': 2026,
        'types': [
            {'name': 'Regular Season', 'start': '2026-02-21', 'end': '2026-10-04'},
            {'name': 'Playoffs', 'start': '2026-10-20', 'end': '2026-12-13'},
        ]
    },
    'IPL': {
        'year': 2026,
        'types': [
            {'name': 'Group Stage', 'start': '2026-03-22', 'end': '2026-05-18'},
            {'name': 'Playoffs', 'start': '2026-05-20', 'end': '2026-05-31'},
        ]
    },
    'MLC': {
        'year': 2026,
        'types': [
            {'name': 'Regular Season', 'start': '2026-07-01', 'end': '2026-07-27'},
            {'name': 'Playoffs', 'start': '2026-07-28', 'end': '2026-08-02'},
        ]
    },
}

@app.route('/api/season-info/<league>')
def season_info(league):
    """Return season date info for any league"""
    league_upper = league.upper()
    if league_upper in ('IPL', 'MLC', 'WNBA'):
        try:
            cache_key = f'season_info:{league_upper}'
            cached = get_cached_response(cache_key, 'schedule')
            if cached:
                return jsonify(cached)
            response = requests.get(f'{API_BASE_URL}/api/v1/season-info/{league.lower()}', timeout=10)
            response.raise_for_status()
            data = response.json()
            fmt = lambda d: datetime.strptime(d, '%Y-%m-%d').strftime('%b %-d') if d else ''
            for st in data.get('season_types', []):
                st['display'] = f"{st['name']}: {fmt(st.get('start_date',''))} - {fmt(st.get('end_date',''))}"
            set_cached_response(cache_key, data)
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error fetching season info for {league}: {e}")
            return jsonify({'year': datetime.now().year, 'season_types': []}), 200
    data = SEASON_DATES.get(league_upper)
    if not data:
        return jsonify({'year': datetime.now().year, 'season_types': []}), 200
    now = datetime.now().strftime('%Y-%m-%d')
    current_phase = 'Off Season'
    season_types = []
    for t in data['types']:
        if t['start'] <= now <= t['end']:
            current_phase = t['name']
        start_fmt = datetime.strptime(t['start'], '%Y-%m-%d').strftime('%b %-d')
        end_fmt = datetime.strptime(t['end'], '%Y-%m-%d').strftime('%b %-d')
        season_types.append({
            'name': t['name'],
            'start_date': t['start'],
            'end_date': t['end'],
            'display': f"{t['name']}: {start_fmt} - {end_fmt}"
        })
    return jsonify({
        'year': data['year'],
        'current_phase': current_phase,
        'season_types': season_types
    })

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
            WHERE LOWER(l.league_name_proper) IN ('nba', 'nhl', 'mlb', 'nfl', 'mls', 'wnba', 'ipl', 'mlc')
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
                   t.team_wins, t.team_losses, t.team_ties,
                   s.stadium_id as s_stadium_id, s.full_stadium_name, s.city_name as stadium_city, s.state_name as stadium_state,
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
                'India Premier League', 'Major League Cricket'
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
            
            team['abbreviation'] = get_team_abbreviation(team['real_team_name'], league_name)
            organized_teams[conference][division].append(team)

        # For MLB (and other leagues with standings), sort teams within each division by wins desc
        # and compute Games Behind (GB)
        if league_name == 'MLB':
            for conference in organized_teams:
                for division in organized_teams[conference]:
                    teams_list = organized_teams[conference][division]
                    teams_list.sort(key=lambda t: (t.get('team_wins') or 0), reverse=True)
                    if teams_list and teams_list[0].get('team_wins') is not None:
                        leader_wins = teams_list[0].get('team_wins') or 0
                        leader_losses = teams_list[0].get('team_losses') or 0
                        for team in teams_list:
                            tw = team.get('team_wins') or 0
                            tl = team.get('team_losses') or 0
                            gb = ((leader_wins - tw) + (tl - leader_losses)) / 2.0
                            team['games_behind'] = '-' if gb == 0 else f'{gb:.1f}'.rstrip('0').rstrip('.')

        # For MLS, sort teams within each conference by points (3*W + 1*T) desc
        if league_name == 'MLS':
            for conference in organized_teams:
                for division in organized_teams[conference]:
                    teams_list = organized_teams[conference][division]
                    for team in teams_list:
                        w = team.get('team_wins') or 0
                        t = team.get('team_ties') or 0
                        team['mls_points'] = w * 3 + t
                    teams_list.sort(key=lambda t: (t.get('mls_points') or 0), reverse=True)

        # For WNBA, fetch live records from sportspuff-api and sort by wins desc
        if league_name == 'WNBA':
            wnba_records = _fetch_wnba_standings(API_BASE_URL) or {}
            for conference in organized_teams:
                for division in organized_teams[conference]:
                    teams_list = organized_teams[conference][division]
                    for team in teams_list:
                        rec = wnba_records.get(team['real_team_name'])
                        if rec:
                            team['team_wins'] = rec['wins']
                            team['team_losses'] = rec['losses']
                            team['games_behind'] = rec['games_back']
                    teams_list.sort(key=lambda t: (t.get('team_wins') or 0), reverse=True)

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

    wnba_abbrev_map = {
        'Atlanta Dream': 'ATL', 'Chicago Sky': 'CHI', 'Connecticut Sun': 'CON',
        'Dallas Wings': 'DAL', 'Golden State Valkyries': 'GSV', 'Indiana Fever': 'IND',
        'Las Vegas Aces': 'LV', 'Los Angeles Sparks': 'LA', 'Minnesota Lynx': 'MIN',
        'New York Liberty': 'NYL', 'Phoenix Mercury': 'PHX', 'Portland Fire': 'POR',
        'Seattle Storm': 'SEA', 'Toronto Tempo': 'TOR', 'Washington Mystics': 'WAS'
    }

    ipl_abbrev_map = {
        'Chennai Super Kings': 'CSK', 'Delhi Capitals': 'DC', 'Gujarat Titans': 'GT',
        'Kolkata Knight Riders': 'KKR', 'Lucknow Super Giants': 'LSG',
        'Mumbai Indians': 'MI', 'Punjab Kings': 'PBKS', 'Rajasthan Royals': 'RR',
        'Royal Challengers Bengaluru': 'RCB', 'Sunrisers Hyderabad': 'SRH'
    }

    mlc_abbrev_map = {
        'Los Angeles Knight Riders': 'LAKR', 'MI New York': 'MINY',
        'San Francisco Unicorns': 'SFU', 'Seattle Orcas': 'SEA',
        'Texas Super Kings': 'TSK', 'Washington Freedom': 'WSH'
    }

    mls_abbrev_map = {
        'Atlanta United FC': 'ATL', 'Austin FC': 'ATX', 'CF Montréal': 'MTL',
        'Charlotte FC': 'CLT', 'Chicago Fire FC': 'CHI', 'Colorado Rapids': 'COL',
        'Columbus Crew': 'CLB', 'D.C. United': 'DC', 'FC Cincinnati': 'CIN',
        'FC Dallas': 'DAL', 'Houston Dynamo FC': 'HOU', 'Inter Miami CF': 'MIA',
        'Los Angeles FC': 'LAFC', 'Los Angeles Galaxy': 'LA', 'Minnesota United FC': 'MIN',
        'Nashville SC': 'NSH', 'New England Revolution': 'NE', 'New York City FC': 'NYC',
        'New York Red Bulls': 'RBNY', 'Orlando City SC': 'ORL', 'Philadelphia Union': 'PHI',
        'Portland Timbers': 'POR', 'Real Salt Lake': 'RSL', 'San Diego FC': 'SD',
        'San Jose Earthquakes': 'SJ', 'Seattle Sounders FC': 'SEA',
        'Sporting Kansas City': 'SKC', 'St. Louis City SC': 'STL',
        'Toronto FC': 'TOR', 'Vancouver Whitecaps FC': 'VAN'
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
    elif league.upper() == 'WNBA':
        abbrev_map = wnba_abbrev_map
    elif league.upper() == 'IPL':
        abbrev_map = ipl_abbrev_map
    elif league.upper() == 'MLC':
        abbrev_map = mlc_abbrev_map
    elif league.upper() == 'MLS':
        abbrev_map = mls_abbrev_map
    
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
    linked_filter = request.args.get('linked', '').lower()

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

        if linked_filter == 'true':
            where_conditions.append("t.stadium_id IS NOT NULL")
        elif linked_filter == 'false':
            where_conditions.append("t.stadium_id IS NULL")

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

@app.route('/stadiums/<path:filename>')
def serve_stadium_image(filename):
    """Serve stadium images from the stadiums directory"""
    import os
    # Check if file exists in stadiums directory
    stadiums_dir = os.path.join(os.path.dirname(__file__), 'stadiums')
    file_path = os.path.join(stadiums_dir, filename)
    if os.path.exists(file_path):
        return send_from_directory(stadiums_dir, filename)
    else:
        # Try with subdirectories (e.g., stadiums/nba/stadium.jpg)
        for root, dirs, files in os.walk(stadiums_dir):
            for file in files:
                if file == filename or filename in file:
                    return send_from_directory(root, file)
        # Return 404 if not found
        from flask import abort
        abort(404)

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
    """Template filter to get league logo from splitsp.lat"""
    if league:
        league_lower = league.lower()
        return f'https://www.splitsp.lat/logos/{league_lower}/{league_lower}_logo.png'
    return 'https://www.splitsp.lat/logos/sportspuff/sportspuff-logo.png'

@app.route('/api/proxy/all-scores/<date>')
def proxy_all_scores(date):
    """Aggregated endpoint: fetch schedule+scores for all leagues in one request."""
    tz = _normalize_timezone(request.args.get('tz', 'pt'))
    api_date = 'today' if date.lower() == 'today' else date

    cache_key = f'all_scores:{api_date}:{tz}'
    cached = get_cached_response(cache_key, 'scores')
    if cached:
        return jsonify(cached)

    expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
    if expired_cache:
        _refresh_cache_async(
            cache_key,
            lambda: _refresh_all_scores_cache(API_BASE_URL, api_date, tz)
        )
        return jsonify(expired_cache)

    if api_date == 'today':
        _refresh_cache_async(
            cache_key,
            lambda: _refresh_all_scores_cache(API_BASE_URL, api_date, tz)
        )
        logger.warning(f"No all-scores cache available for {tz}; warming asynchronously")
        return jsonify(_empty_all_scores_response()), 200

    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc']
    result = {}

    def fetch_league(lg):
        api_base = API_BASE_URL
        schedule_url = f'{api_base}/api/v1/schedule/{lg}/{api_date}?tz={tz}'
        scores_url = f'{api_base}/api/v1/scores/{lg}/{api_date}?tz={tz}'
        league_data = {'schedule': {'games': []}, 'scores': {'scores': []}}
        try:
            r = requests.get(schedule_url, timeout=15)
            if r.status_code == 200:
                league_data['schedule'] = r.json()
        except:
            pass
        try:
            r = requests.get(scores_url, timeout=15)
            if r.status_code == 200:
                league_data['scores'] = r.json()
        except:
            pass
        return lg, league_data

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_league, lg): lg for lg in leagues}
        for future in as_completed(futures):
            try:
                lg, data = future.result()
                result[lg] = data
            except:
                pass

    set_cached_response(cache_key, result)
    return jsonify(result)

@app.route('/api/proxy/schedule/<league>/<date>')
def proxy_schedule(league, date):
    """Proxy schedule API requests to avoid CORS issues with caching"""
    try:
        # Get timezone from query parameter, default to 'pt'
        tz = _normalize_timezone(request.args.get('tz', 'pt'))

        if date.lower() == 'today':
            cache_key = f'schedule:{league}:today:{tz}'
            api_date = 'today'
        else:
            cache_key = f'schedule:{league}:{date}:{tz}'
            api_date = date

        cached_response = get_cached_response(cache_key, 'schedule')
        if cached_response:
            return jsonify(cached_response)
        
        # Fetch from API with timezone parameter
        api_base = API_BASE_URL
        url = f'{api_base}/api/v1/schedule/{league}/{api_date}?tz={tz}'
        logger.info(f"Fetching schedule from: {url} (timeout=20s)")
        try:
            # Use shorter timeout to avoid nginx 502 errors
            # Nginx typically has 60s timeout, so we use 20s to leave buffer
            response = requests.get(url, timeout=20, verify=True, allow_redirects=True)
            logger.info(f"Schedule API response status: {response.status_code}, length: {len(response.content)}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching schedule from {url} after 20s")
            # Return cached response if available, even if expired
            expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached schedule due to timeout")
                return jsonify(expired_cache)
            # Return empty structure instead of error - frontend can handle this
            logger.warning("No cache available, returning empty schedule")
            return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'games': []}), 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception fetching schedule: {e}", exc_info=True)
            # Return cached response if available, even if expired
            expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached schedule due to request exception")
                return jsonify(expired_cache)
            # Return empty structure instead of error
            logger.warning("No cache available, returning empty schedule")
            return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'games': []}), 200
        
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
        logger.error(f"Timeout proxying schedule request")
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached schedule after outer timeout")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty schedule")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'games': []}), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying schedule request: {e}")
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached schedule after outer request exception")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty schedule")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'games': []}), 200
    except Exception as e:
        logger.error(f"Unexpected error in proxy_schedule: {e}", exc_info=True)
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached schedule after unexpected error")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty schedule")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'games': []}), 200

@app.route('/api/nfl/team-records')
def nfl_team_records():
    """Fetch NFL team records from sportspuff-api standings, keyed by full name and abbreviation."""
    try:
        cache_key = 'nfl_team_records'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached), 200

        response = requests.get(f'{API_BASE_URL}/api/v1/standings/nfl', timeout=10)
        response.raise_for_status()
        data = response.json()

        team_records = {}
        for team in data.get('teams', []):
            name = team.get('team_name', '').strip()
            abv = team.get('abbreviation', '').strip()
            record = {
                'wins': int(team.get('wins') or 0),
                'losses': int(team.get('losses') or 0),
                'ties': int(team.get('ties') or 0),
            }
            if name:
                team_records[name] = record
            if abv:
                team_records[abv] = record

        result = {'teams': team_records}
        set_cached_response(cache_key, result)
        logger.info(f"Fetched records for {len(data.get('teams', []))} NFL teams from sportspuff-api")
        return jsonify(result), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching NFL team records: {e}")
        return jsonify({'teams': {}}), 200
    except Exception as e:
        logger.error(f"Unexpected error fetching NFL team records: {e}", exc_info=True)
        return jsonify({'teams': {}}), 200

@app.route('/api/wnba/season-info')
def wnba_season_info():
    """Fetch WNBA season info (dates for preseason, regular season, postseason) from sportspuff-api."""
    try:
        year = request.args.get('year', datetime.now().year)
        cache_key = f'wnba_season_info:{year}'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached)

        response = requests.get(f'{API_BASE_URL}/api/v1/season-info/wnba', timeout=10)
        response.raise_for_status()
        data = response.json()
        set_cached_response(cache_key, data)
        return jsonify(data)

    except Exception as e:
        logger.error(f"Error fetching WNBA season info: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 200

@app.route('/api/cricket/standings/<league>')
def cricket_standings(league):
    """Fetch cricket standings from Sportspuff API"""
    league_lower = league.lower()
    if league_lower not in ('ipl', 'mlc'):
        return jsonify({'standings': []}), 400
    try:
        cache_key = f'cricket_standings:{league_lower}'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached)

        response = requests.get(f'{API_BASE_URL}/api/v1/standings/{league_lower}', timeout=10)
        response.raise_for_status()
        data = response.json()

        # API returns rows under 'teams'; frontend expects 'standings'
        if 'standings' not in data:
            data['standings'] = data.get('teams', [])
        data.setdefault('available', bool(data['standings']))

        set_cached_response(cache_key, data)
        return jsonify(data)

    except Exception as e:
        logger.error(f"Error fetching {league} standings: {e}")
        return jsonify({'standings': [], 'available': False}), 200

@app.route('/api/ipl/standings')
def ipl_standings():
    """Redirect to generic cricket standings endpoint"""
    return cricket_standings('ipl')

@app.route('/api/mls/team-records')
def mls_team_records():
    """Fetch MLS team records from sportspuff-api standings endpoint"""
    try:
        cache_key = 'mls_team_records'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached)

        response = requests.get(f'{API_BASE_URL}/api/v1/standings/mls', timeout=10)
        if response.status_code != 200:
            return jsonify({'teams': {}}), 200

        data = response.json()
        teams = {}
        for t in data.get('teams', []):
            abbrev = t.get('abbreviation', '')
            name = t.get('team_name', abbrev)
            teams[name] = {
                'wins': t.get('wins', 0),
                'losses': t.get('losses', 0),
                'draws': t.get('draws', 0),
                'points': t.get('points', 0)
            }
            if abbrev:
                teams[abbrev] = teams[name]

        result = {'teams': teams}
        set_cached_response(cache_key, result)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching MLS team records: {e}")
        return jsonify({'teams': {}}), 200

# --- API status / health check ------------------------------------------------
@app.route('/api/status-check')
def api_status_check():
    """Proxy the sportspuff-api status payload (see /api/v1/status contract)."""
    try:
        resp = requests.get(f'{API_BASE_URL}/api/v1/status', timeout=10)
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.exceptions.RequestException as e:
        return jsonify({
            'unreachable': True,
            'error': type(e).__name__,
            'api_base_url': API_BASE_URL,
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'summary': {'error': 0, 'warning': 0, 'ok': 0},
            'upstreams': [],
            'results': [],
        })
    except ValueError:
        return jsonify({
            'unreachable': True,
            'error': 'Invalid JSON from API',
            'api_base_url': API_BASE_URL,
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'summary': {'error': 0, 'warning': 0, 'ok': 0},
            'upstreams': [],
            'results': [],
        })

@app.route('/api-status')
def api_status():
    """Status page showing the health of the sportspuff-api endpoints."""
    return render_template('api_status.html', API_BASE_URL=API_BASE_URL)

@app.route('/api/mlb/team-records')
def mlb_team_records():
    """Fetch MLB team records from database (populated by fetch_standings.py)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'teams': {}}), 200
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT t.real_team_name, t.team_wins, t.team_losses
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE l.league_name_proper = 'MLB'
            AND t.team_wins IS NOT NULL
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        team_records = {}
        for row in rows:
            team_records[row['real_team_name']] = {
                'wins': row['team_wins'] or 0,
                'losses': row['team_losses'] or 0
            }
        return jsonify({'teams': team_records}), 200
    except Exception as e:
        logger.error(f"Error fetching MLB team records: {e}")
        return jsonify({'teams': {}}), 200

@app.route('/api/nhl/playoff-series')
def nhl_playoff_series():
    """Fetch NHL playoff series records from NHL API schedule data"""
    try:
        cache_key = 'nhl_playoff_series'
        cached = get_cached_response(cache_key, 'scores')
        if cached:
            return jsonify(cached)

        response = requests.get('https://api-web.nhle.com/v1/schedule/now', timeout=10)
        response.raise_for_status()
        data = response.json()

        series_map = {}
        for week in data.get('gameWeek', []):
            for game in week.get('games', []):
                series = game.get('seriesStatus', {})
                if not series:
                    continue
                top = series.get('topSeedTeamAbbrev', '')
                bottom = series.get('bottomSeedTeamAbbrev', '')
                if top and bottom:
                    key = f"{min(top,bottom)}-{max(top,bottom)}"
                    series_map[key] = {
                        'top_seed': top,
                        'top_seed_wins': series.get('topSeedWins', 0),
                        'bottom_seed': bottom,
                        'bottom_seed_wins': series.get('bottomSeedWins', 0),
                        'round': series.get('round', 0),
                        'game_number_of_series': series.get('gameNumberOfSeries', 0),
                    }
                    series_map[top] = series_map[key]
                    series_map[bottom] = series_map[key]

        result = {'series': series_map}
        set_cached_response(cache_key, result)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error fetching NHL playoff series: {e}")
        return jsonify({'series': {}}), 200

@app.route('/api/proxy/scores/<league>/<date>')
def proxy_scores(league, date):
    """Proxy scores API requests to avoid CORS issues with very short caching"""
    try:
        # Get timezone from query parameter, default to 'pt'
        tz = _normalize_timezone(request.args.get('tz', 'pt'))

        if date.lower() == 'today':
            cache_key = f'scores:{league}:today:{tz}'
            api_date = 'today'
        else:
            cache_key = f'scores:{league}:{date}:{tz}'
            api_date = date

        cached_response = get_cached_response(cache_key, 'scores')
        if cached_response:
            return jsonify(cached_response)

        # Only fetch fresh scores if cache is expired or missing
        api_base = API_BASE_URL
        url = f'{api_base}/api/v1/scores/{league}/{api_date}?tz={tz}'
        logger.info(f"Fetching scores from: {url} (timeout=20s)")
        try:
            # Use shorter timeout to avoid nginx 502 errors
            # Nginx typically has 60s timeout, so we use 20s to leave buffer
            response = requests.get(url, timeout=20, verify=True, allow_redirects=True)
            logger.info(f"Scores API response status: {response.status_code}, length: {len(response.content)}")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching scores from {url} after 20s")
            # Return cached response if available, even if expired
            expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached scores due to timeout")
                return jsonify(expired_cache)
            # Return empty structure instead of error - frontend can handle this
            logger.warning("No cache available, returning empty scores")
            return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'scores': []}), 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Request exception fetching scores: {e}", exc_info=True)
            # Return cached response if available, even if expired
            expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached scores due to request exception")
                return jsonify(expired_cache)
            # Return empty structure instead of error
            logger.warning("No cache available, returning empty scores")
            return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'scores': []}), 200
        
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
        logger.error(f"Timeout proxying scores request")
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached scores after outer timeout")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty scores")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'scores': []}), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying scores request: {e}")
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached scores after outer request exception")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty scores")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'scores': []}), 200
    except Exception as e:
        logger.error(f"Unexpected error in proxy_scores: {e}", exc_info=True)
        # Try to return expired cached response if available
        try:
            expired_cache = get_cached_response(cache_key, 'scores', allow_expired=True)
            if expired_cache:
                logger.warning("Returning expired cached scores after unexpected error")
                return jsonify(expired_cache)
        except:
            pass
        # Return empty structure instead of error
        logger.warning("No cache available, returning empty scores")
        return jsonify({'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'), 'scores': []}), 200

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
