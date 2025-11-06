#!/usr/bin/env python3
"""
Sportspuff-v6 Web Application
Flask-based CRUD interface for managing teams and stadiums
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import requests
from datetime import datetime, timezone
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Simple cache for API responses
_api_cache = {}
_cache_ttl = {
    'schedule': 300,  # 5 minutes for schedules
    'scores': 5,      # 5 seconds for scores (games update very frequently)
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
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
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
        # Fallback data when database is not available
        return render_template('index.html', 
                             team_count=0,
                             stadium_count=0,
                             linked_count=0,
                             league_stats=[],
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors={},
                             db_available=False)
    
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
        
        # Get team colors and logos for NBA (for scores display)
        cursor.execute("""
            SELECT t.real_team_name, t.team_color_1, t.team_color_2, t.team_color_3, 
                   t.logo_filename, l.league_name
            FROM teams t
            JOIN leagues l ON t.league_id = l.league_id
            WHERE LOWER(l.league_name_proper) = 'nba'
            AND t.team_color_1 IS NOT NULL
        """)
        nba_teams = cursor.fetchall()
        
        # Create a mapping of team name to colors and logo
        # Also create variations for common name differences (e.g., "LA Clippers" vs "Los Angeles Clippers")
        nba_team_colors = {}
        for team in nba_teams:
            # Build logo URL - use local static/images/logos if available, otherwise splitsp.lat
            logo_url = '/static/images/no-logo.png'
            if team['logo_filename']:
                league_lower = team['league_name'].lower()
                # Try local first, fallback to splitsp.lat
                logo_url = f'/static/images/logos/{league_lower}/{team["logo_filename"]}'
            
            team_data = {
                'color_1': team['team_color_1'],
                'color_2': team['team_color_2'],
                'color_3': team['team_color_3'],
                'logo_url': logo_url
            }
            
            # Map exact name
            nba_team_colors[team['real_team_name']] = team_data
            
            # Map common variations
            team_name = team['real_team_name']
            if 'Los Angeles' in team_name:
                # Map "LA Clippers" to "Los Angeles Clippers"
                nba_team_colors[team_name.replace('Los Angeles', 'LA')] = team_data
            elif team_name.startswith('LA '):
                # Map "Los Angeles Clippers" to "LA Clippers"
                nba_team_colors[team_name.replace('LA ', 'Los Angeles ')] = team_data
        
        cursor.close()
        conn.close()
        
        return render_template('index.html', 
                             team_count=team_count,
                             stadium_count=stadium_count,
                             linked_count=linked_count,
                             league_stats=league_stats,
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors=nba_team_colors,
                             db_available=True)
    
    except Exception as e:
        flash(f'Error loading dashboard: {e}', 'error')
        return render_template('index.html', 
                             team_count=0,
                             stadium_count=0,
                             linked_count=0,
                             league_stats=[],
                             logo_mapping=LOGO_MAPPING,
                             nba_team_colors={},
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
                SELECT l.league_name, t.logo_filename 
                FROM teams t 
                LEFT JOIN leagues l ON t.league_id = l.league_id 
                WHERE t.team_id = %s
            """, [team_id])
            team = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if team and team['logo_filename']:
                league = team['league_name'].lower()
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
        # For "today", use actual date for cache key but pass "today" to API
        # API only accepts "today" as a keyword, not date strings
        if date.lower() == 'today':
            actual_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            cache_key = f'schedule:{league}:{actual_date}'
            api_date = 'today'  # API only accepts "today", not date strings
        else:
            cache_key = f'schedule:{league}:{date}'
            api_date = date
        
        # Check cache first - but verify it's for today's date
        cached_response = get_cached_response(cache_key, 'schedule')
        if cached_response:
            # Verify the cached data is for today (check response date field)
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if cached_date == today_date:
                return jsonify(cached_response)
            # If cached date doesn't match today, clear it and fetch fresh
        
        # Fetch from API
        url = f'https://api.sportspuff.org/api/v1/schedule/{league}/{api_date}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Cache the response
        set_cached_response(cache_key, data)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/proxy/scores/<league>/<date>')
def proxy_scores(league, date):
    """Proxy scores API requests to avoid CORS issues with very short caching"""
    try:
        # For "today", use actual date for cache key but pass "today" to API
        # API only accepts "today" as a keyword, not date strings
        if date.lower() == 'today':
            actual_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            cache_key = f'scores:{league}:{actual_date}'
            api_date = 'today'  # API only accepts "today", not date strings
        else:
            cache_key = f'scores:{league}:{date}'
            api_date = date
        
        # Check cache only if very recent (< 5 seconds) - otherwise always fetch fresh
        cached_response = get_cached_response(cache_key, 'scores')
        if cached_response:
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            # Only use cache if it's from today AND very recent (< 5 seconds)
            if cached_date == today_date:
                # Use cache if very recent (handled by get_cached_response with 5s TTL)
                # Otherwise continue to fetch fresh
                pass
        
        # Always fetch fresh scores (cache is just for rapid consecutive requests)
        url = f'https://api.sportspuff.org/api/v1/scores/{league}/{api_date}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Cache the response (very short TTL - 5 seconds)
        set_cached_response(cache_key, data)
        
        return jsonify(data)
    except Exception as e:
        # If API fails, try to return cached response as fallback only if very recent
        if 'cached_response' in locals() and cached_response:
            cached_date = cached_response.get('date', '')
            today_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            if cached_date == today_date:
                return jsonify(cached_response)
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
