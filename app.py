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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        
        cursor.close()
        conn.close()
        
        return render_template('index.html', 
                             team_count=team_count,
                             stadium_count=stadium_count,
                             linked_count=linked_count,
                             league_stats=league_stats,
                             logo_mapping=LOGO_MAPPING,
                             db_available=True)
    
    except Exception as e:
        flash(f'Error loading dashboard: {e}', 'error')
        return render_template('index.html', 
                             team_count=0,
                             stadium_count=0,
                             linked_count=0,
                             league_stats=[],
                             logo_mapping=LOGO_MAPPING,
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
                   c.conference_name, d.division_name
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
        
        cursor.close()
        conn.close()
        
        return render_template('league_page.html', 
                             league_name=league_name,
                             organized_teams=organized_teams,
                             logo_mapping=LOGO_MAPPING)
    
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
            SELECT t.*, s.full_stadium_name, s.city_name as stadium_city, s.state_name as stadium_state
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
                WHERE l.league_abbreviation = %s
                GROUP BY d.division_id, d.division_name
                ORDER BY d.division_name
            """
            cursor.execute(divisions_query, [league_filter])
            divisions = cursor.fetchall()
        
        # Get leagues for filter dropdown
        cursor.execute("SELECT DISTINCT league FROM teams ORDER BY league")
        leagues = [row['league'] for row in cursor.fetchall()]
        
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

@app.route('/team/<int:team_id>')
def team_detail(team_id):
    """Show team details"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Database connection failed")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT t.*, s.*, s.city_name as stadium_city, s.state_name as stadium_state
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            WHERE t.team_id = %s
        """, (team_id,))
        
        team = cursor.fetchone()
        
        if not team:
            flash('Team not found', 'error')
            return redirect(url_for('teams'))
        
        cursor.close()
        conn.close()
        
        return render_template('team_detail.html', team=team)
    
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
            SELECT team_id, real_team_name, league, city_name, state_name
            FROM teams 
            WHERE stadium_id = %s
            ORDER BY league, real_team_name
        """, (stadium_id,))
        
        teams = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('stadium_detail.html', stadium=stadium, teams=teams)
    
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
            SELECT t.team_id, t.real_team_name, t.league, t.city_name, t.state_name,
                   s.full_stadium_name, s.stadium_id
            FROM teams t 
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
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
    """Template filter to get league logo from splitsp.lat"""
    if league:
        league_lower = league.lower()
        # Use correct acronym-based URLs
        if league_lower == 'mlb':
            return 'https://www.splitsp.lat/logos/mlb/mlb_logo.png'
        elif league_lower == 'nfl':
            return 'https://www.splitsp.lat/logos/nfl/nfl_logo.png'
        elif league_lower == 'nba':
            return 'https://www.splitsp.lat/logos/nba/nba_logo.png'
        elif league_lower == 'nhl':
            return 'https://www.splitsp.lat/logos/nhl/nhl_logo.png'
        elif league_lower == 'mls':
            return 'https://www.splitsp.lat/logos/mls/mls_logo.png'
        elif league_lower == 'wnba':
            return 'https://www.splitsp.lat/logos/wnba/wnba_logo.png'
        else:
            return f'https://www.splitsp.lat/logos/{league_lower}/{league_lower}_logo.png'
    return '/static/images/no-logo.png'

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
