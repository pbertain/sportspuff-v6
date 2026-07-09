#!/usr/bin/env python3
"""
Sportspuff-v6 Web Application
Flask-based CRUD interface for managing teams and stadiums
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, Response
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
import csv
import requests
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from functools import wraps, lru_cache
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

WC_TEAM_CODES_BY_NAME = {
    'Algeria': 'alg',
    'Argentina': 'arg',
    'Australia': 'aus',
    'Austria': 'aut',
    'Belgium': 'bel',
    'Bosnia and Herzegovina': 'bih',
    'Bosnia-Herzegovina': 'bih',
    'Brazil': 'bra',
    'Cabo Verde': 'cpv',
    'Cape Verde': 'cpv',
    'Canada': 'can',
    'Colombia': 'col',
    'Congo DR': 'cod',
    'DR Congo': 'cod',
    'Democratic Republic of the Congo': 'cod',
    'Croatia': 'cro',
    'Curaçao': 'cuw',
    'Curacao': 'cuw',
    'Czech Republic': 'cze',
    'Czechia': 'cze',
    "Côte d'Ivoire": 'civ',
    "Cote d'Ivoire": 'civ',
    'Ivory Coast': 'civ',
    'Ecuador': 'ecu',
    'Egypt': 'egy',
    'England': 'eng',
    'France': 'fra',
    'Germany': 'ger',
    'Ghana': 'gha',
    'Haiti': 'hai',
    'IR Iran': 'irn',
    'Iran': 'irn',
    'Iraq': 'irq',
    'Japan': 'jpn',
    'Jordan': 'jor',
    'Korea Republic': 'kor',
    'South Korea': 'kor',
    'Mexico': 'mex',
    'Morocco': 'mar',
    'Netherlands': 'ned',
    'New Zealand': 'nzl',
    'Norway': 'nor',
    'Panama': 'pan',
    'Paraguay': 'par',
    'Portugal': 'por',
    'Qatar': 'qat',
    'Saudi Arabia': 'ksa',
    'Scotland': 'sco',
    'Senegal': 'sen',
    'South Africa': 'rsa',
    'Spain': 'esp',
    'Sweden': 'swe',
    'Switzerland': 'sui',
    'Tunisia': 'tun',
    'Türkiye': 'tur',
    'Turkey': 'tur',
    'USA': 'usa',
    'United States': 'usa',
    'Uruguay': 'uru',
    'Uzbekistan': 'uzb',
}

WC_TEAM_BALL_BASE_URL = 'https://www.splitsp.lat/logos/wc/teamballs'
WC_GROUP_STAGE_START = '2026-06-11'
WC_GROUP_STAGE_END = '2026-06-27'
WC_CANONICAL_GROUPS = {
    'A': {'MEX', 'RSA', 'KOR', 'CZE'},
    'B': {'CAN', 'BIH', 'QAT', 'SUI'},
    'C': {'BRA', 'MAR', 'HAI', 'SCO'},
    'D': {'USA', 'PAR', 'AUS', 'TUR'},
    'E': {'GER', 'CUW', 'CIV', 'ECU'},
    'F': {'NED', 'JPN', 'SWE', 'TUN'},
    'G': {'BEL', 'EGY', 'IRN', 'NZL'},
    'H': {'ESP', 'CPV', 'KSA', 'URU'},
    'I': {'FRA', 'SEN', 'IRQ', 'NOR'},
    'J': {'ARG', 'ALG', 'AUT', 'JOR'},
    'K': {'POR', 'COD', 'UZB', 'COL'},
    'L': {'ENG', 'CRO', 'GHA', 'PAN'},
}
WC_CANONICAL_GROUP_BY_CODE = {
    code: group
    for group, codes in WC_CANONICAL_GROUPS.items()
    for code in codes
}
WC_CANONICAL_GROUP_BY_NAME = {
    'mexico': 'A',
    'south africa': 'A',
    'south korea': 'A',
    'czech republic': 'A',
    'czechia': 'A',
    'canada': 'B',
    'bosnia and herzegovina': 'B',
    'bosnia-herzegovina': 'B',
    'qatar': 'B',
    'switzerland': 'B',
    'brazil': 'C',
    'morocco': 'C',
    'haiti': 'C',
    'scotland': 'C',
    'united states': 'D',
    'usa': 'D',
    'paraguay': 'D',
    'australia': 'D',
    'turkey': 'D',
    'türkiye': 'D',
    'germany': 'E',
    'curacao': 'E',
    'curaçao': 'E',
    'ivory coast': 'E',
    'ecuador': 'E',
    'netherlands': 'F',
    'japan': 'F',
    'sweden': 'F',
    'tunisia': 'F',
    'belgium': 'G',
    'egypt': 'G',
    'iran': 'G',
    'new zealand': 'G',
    'spain': 'H',
    'cape verde': 'H',
    'saudi arabia': 'H',
    'uruguay': 'H',
    'france': 'I',
    'senegal': 'I',
    'iraq': 'I',
    'norway': 'I',
    'argentina': 'J',
    'algeria': 'J',
    'austria': 'J',
    'jordan': 'J',
    'portugal': 'K',
    'dr congo': 'K',
    'uzbekistan': 'K',
    'colombia': 'K',
    'england': 'L',
    'croatia': 'L',
    'ghana': 'L',
    'panama': 'L',
}


def _clean_csv_value(value):
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _csv_int(value):
    cleaned = _clean_csv_value(value)
    if cleaned is None:
        return None
    try:
        return int(float(cleaned))
    except (TypeError, ValueError):
        return None


def _csv_path(filename):
    return os.path.join(os.path.dirname(__file__), filename)


@lru_cache(maxsize=1)
def _read_csv_rows(filename):
    with open(_csv_path(filename), newline='', encoding='utf-8-sig') as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def _build_team_colors(rows):
    team_colors = {}
    for team in rows:
        league_proper = team.get('league_name_proper')
        if not league_proper:
            continue
        team_colors.setdefault(league_proper, {})

        logo_filename = team.get('logo_filename')
        league_lower = (team.get('league_name') or league_proper).lower()
        logo_url = '/static/images/no-logo.png'
        if logo_filename:
            logo_url = f'https://www.splitsp.lat/logos/{league_lower}/{logo_filename}'

        real_name = team.get('real_team_name') or ''
        full_name = team.get('full_team_name') or real_name
        abbrev = team.get('team_abbreviation') or get_team_abbreviation(real_name, league_proper)
        team_data = {
            'color_1': team.get('team_color_1'),
            'color_2': team.get('team_color_2'),
            'color_3': team.get('team_color_3'),
            'logo_url': logo_url,
            'abbreviation': abbrev,
            'full_team_name': full_name,
            'real_team_name': real_name,
        }

        team_colors[league_proper][real_name] = team_data
        if full_name and full_name != real_name:
            team_colors[league_proper][full_name] = team_data

        if 'Los Angeles' in real_name:
            team_colors[league_proper][real_name.replace('Los Angeles', 'LA')] = team_data
        elif real_name.startswith('LA '):
            team_colors[league_proper][real_name.replace('LA ', 'Los Angeles ')] = team_data

        if 'New York' in real_name:
            team_colors[league_proper][real_name.replace('New York', 'NY')] = team_data
        elif real_name.startswith('NY '):
            team_colors[league_proper][real_name.replace('NY ', 'New York ')] = team_data

        if 'San Francisco' in real_name:
            team_colors[league_proper][real_name.replace('San Francisco', 'SF')] = team_data
        elif real_name.startswith('SF '):
            team_colors[league_proper][real_name.replace('SF ', 'San Francisco ')] = team_data

        if league_proper == 'NFL':
            nfl_abbrev_map = {
                'ARI': 'Arizona Cardinals', 'ATL': 'Atlanta Falcons', 'BAL': 'Baltimore Ravens',
                'BUF': 'Buffalo Bills', 'CAR': 'Carolina Panthers', 'CHI': 'Chicago Bears',
                'CIN': 'Cincinnati Bengals', 'CLE': 'Cleveland Browns', 'DAL': 'Dallas Cowboys',
                'DEN': 'Denver Broncos', 'DET': 'Detroit Lions', 'GB': 'Green Bay Packers',
                'HOU': 'Houston Texans', 'IND': 'Indianapolis Colts', 'JAX': 'Jacksonville Jaguars',
                'KC': 'Kansas City Chiefs', 'LV': 'Las Vegas Raiders', 'LAC': 'Los Angeles Chargers',
                'LAR': 'Los Angeles Rams', 'MIA': 'Miami Dolphins', 'MIN': 'Minnesota Vikings',
                'NE': 'New England Patriots', 'NO': 'New Orleans Saints', 'NYG': 'New York Giants',
                'NYJ': 'New York Jets', 'PHI': 'Philadelphia Eagles', 'PIT': 'Pittsburgh Steelers',
                'SF': 'San Francisco 49ers', 'SEA': 'Seattle Seahawks', 'TB': 'Tampa Bay Buccaneers',
                'TEN': 'Tennessee Titans', 'WSH': 'Washington Commanders', 'WAS': 'Washington Commanders',
            }
            for abbrev_key, mapped_name in nfl_abbrev_map.items():
                if mapped_name != real_name and mapped_name != full_name:
                    continue
                team_colors[league_proper][abbrev_key] = team_data
                team_name_only = real_name.split()[-1] if real_name else ''
                if not team_name_only:
                    continue
                team_colors[league_proper][team_name_only] = team_data
                city_part = ' '.join(real_name.split()[:-1])
                if city_part:
                    team_colors[league_proper][f"{city_part} {team_name_only}"] = team_data
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
    return team_colors


@lru_cache(maxsize=1)
def _fallback_catalog():
    leagues = {
        _csv_int(row.get('league_id')): {
            'league_name': (row.get('league_name') or '').lower(),
            'league_name_proper': row.get('league_name_proper'),
            'current_champion_id': _csv_int(row.get('current_champion_id')),
        }
        for row in _read_csv_rows('info-leagues.csv')
    }
    conferences = {
        _csv_int(row.get('conference_id')): _clean_csv_value(row.get('conference_name'))
        for row in _read_csv_rows('info-conferences.csv')
    }
    divisions = {
        _csv_int(row.get('division_id')): _clean_csv_value(row.get('division_name'))
        for row in _read_csv_rows('info-divisions.csv')
    }
    stadiums_by_id = {}
    for row in _read_csv_rows('info-stadiums.csv'):
        stadium_id = _csv_int(row.get('stadium_id'))
        if stadium_id is None:
            continue
        stadiums_by_id[stadium_id] = {
            'stadium_id': stadium_id,
            'full_stadium_name': row.get('full_stadium_name'),
            'stadium_name': row.get('stadium_name'),
            'location_name': row.get('location_name'),
            'city_name': row.get('city_name'),
            'full_state_name': row.get('full_state_name'),
            'state_name': row.get('state_name'),
            'country': row.get('country'),
            'capacity': _csv_int(row.get('capacity')),
            'surface': _clean_csv_value(row.get('surface')),
            'year_opened': _csv_int(row.get('year_opened')),
            'roof_type': _clean_csv_value(row.get('roof_type')),
            'team_count': 0,
        }

    teams = []
    teams_by_id = {}
    teams_by_lookup = {}
    teams_by_league = {}
    teams_by_stadium = {}
    league_counts = {}
    for row in _read_csv_rows('info-teams.csv'):
        league_id = _csv_int(row.get('league_id'))
        league = leagues.get(league_id)
        if not league:
            continue
        team_id = _csv_int(row.get('team_id'))
        stadium_id = _csv_int(row.get('stadium_id'))
        stadium = stadiums_by_id.get(stadium_id)
        real_team_name = row.get('real_team_name')
        league_name_proper = league['league_name_proper']
        team = {
            'team_id': team_id,
            'full_team_name': row.get('full_team_name'),
            'team_name': row.get('team_name'),
            'real_team_name': real_team_name,
            'league_id': league_id,
            'division_id': _csv_int(row.get('division_id')),
            'conference_id': _csv_int(row.get('conference_id')),
            'team_league_id': _csv_int(row.get('team_league_id')),
            'city_name': row.get('city_name'),
            'state_name': row.get('state_name'),
            'country': row.get('country'),
            'stadium_id': stadium_id,
            'logo_filename': row.get('logo_filename'),
            'team_color_1': row.get('team_color_1'),
            'team_color_2': row.get('team_color_2'),
            'team_color_3': row.get('team_color_3'),
            'team_abbreviation': get_team_abbreviation(real_team_name, league_name_proper),
            'team_league': league_name_proper,
            'league_name': league['league_name'],
            'league_name_proper': league_name_proper,
            'conference_name': conferences.get(_csv_int(row.get('conference_id'))),
            'division_name': divisions.get(_csv_int(row.get('division_id'))),
            'team_wins': None,
            'team_losses': None,
            'team_ties': None,
            's_stadium_id': stadium_id,
            'full_stadium_name': stadium.get('full_stadium_name') if stadium else None,
            'stadium_city': stadium.get('city_name') if stadium else None,
            'stadium_state': stadium.get('state_name') if stadium else None,
            'capacity': stadium.get('capacity') if stadium else None,
            'surface': stadium.get('surface') if stadium else None,
            'roof_type': stadium.get('roof_type') if stadium else None,
            'year_opened': stadium.get('year_opened') if stadium else None,
            'location_name': stadium.get('location_name') if stadium else None,
        }
        teams.append(team)
        if team_id is not None:
            teams_by_id[team_id] = team
        teams_by_lookup[(league_name_proper.lower(), real_team_name.replace(' ', '_').lower())] = team
        teams_by_league.setdefault(league_name_proper, []).append(team)
        league_counts[league_name_proper] = league_counts.get(league_name_proper, 0) + 1
        if stadium_id is not None:
            teams_by_stadium.setdefault(stadium_id, []).append(team)
            if stadium_id in stadiums_by_id:
                stadiums_by_id[stadium_id]['team_count'] += 1

    league_stats = [
        {'league': league_name, 'count': count}
        for league_name, count in sorted(league_counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        'teams': teams,
        'team_count': len(teams),
        'stadium_count': len(stadiums_by_id),
        'linked_count': sum(1 for team in teams if team.get('stadium_id') is not None),
        'league_stats': league_stats,
        'team_colors': _build_team_colors(teams),
        'teams_by_id': teams_by_id,
        'teams_by_lookup': teams_by_lookup,
        'teams_by_league': teams_by_league,
        'stadiums_by_id': stadiums_by_id,
        'teams_by_stadium': teams_by_stadium,
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


def _configured_api_base_urls(api_base_url=None):
    """Return primary API host followed by configured fallbacks."""
    fallback_hosts = os.getenv('SPORTSPUFF_API_FALLBACK_BASE_URLS', 'https://api-dev.sportspuff.net')
    candidates = [api_base_url or API_BASE_URL]
    candidates.extend(host.strip() for host in fallback_hosts.split(',') if host.strip())

    seen = set()
    ordered = []
    for host in candidates:
        normalized = host.rstrip('/')
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _fetch_api_json(path, timeout=15, api_base_url=None):
    """Fetch JSON from the primary API, retrying fallback hosts on upstream failure."""
    last_error = None
    for api_base in _configured_api_base_urls(api_base_url):
        url = f"{api_base}{path}"
        try:
            response = requests.get(url, timeout=timeout, verify=True, allow_redirects=True)
            if response.status_code == 200:
                return response.json()
            last_error = requests.exceptions.HTTPError(
                f"API returned status {response.status_code}: {response.text[:200]}"
            )
            logger.warning(f"API request failed from {url}: status {response.status_code}")
        except (requests.exceptions.RequestException, ValueError) as e:
            last_error = e
            logger.warning(f"API request failed from {url}: {e}")

    if isinstance(last_error, requests.exceptions.RequestException):
        raise last_error
    raise requests.exceptions.RequestException(str(last_error or "API request failed"))


def _empty_all_scores_response():
    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc', 'wc', 'atp', 'wta', 'cycling']
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return {
        lg: {
            'schedule': {'date': today, 'games': []},
            'scores': {'date': today, 'scores': []}
        }
        for lg in leagues
    }


def _fetch_league_schedule_and_scores(lg, api_date, tz, api_base_url=None, timeout=15, include_scores=True):
    if _should_skip_live_api_fetch(lg, api_date):
        today = _iso_today() if api_date == 'today' else api_date
        return {
            'schedule': {'date': today, 'games': []},
            'scores': {'date': today, 'scores': []},
        }
    league_data = {'schedule': {'games': []}, 'scores': {'scores': []}}
    try:
        league_data['schedule'] = _fetch_api_json(
            f'/api/v1/schedule/{lg}/{api_date}?tz={tz}',
            timeout=timeout,
            api_base_url=api_base_url,
        )
    except Exception:
        pass
    if include_scores:
        try:
            league_data['scores'] = _fetch_api_json(
                f'/api/v1/scores/{lg}/{api_date}?tz={tz}',
                timeout=timeout,
                api_base_url=api_base_url,
            )
        except Exception:
            pass
    return league_data


def _fetch_all_scores_for_tz(api_base_url, tz, api_date='today'):
    """Fetch all-scores data for a given timezone (no Flask request context needed)."""
    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc', 'wc', 'atp', 'wta', 'cycling']
    result = {}

    def fetch_league(lg):
        return lg, _fetch_league_schedule_and_scores(lg, api_date, tz, api_base_url=api_base_url)

    with ThreadPoolExecutor(max_workers=12) as executor:
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
    if os.getenv('DISABLE_BACKGROUND_CACHE_REFRESH') == '1':
        return

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


def _fetch_nfl_standings(api_base_url):
    """Fetch NFL standings keyed by team name and abbreviation."""
    if _should_skip_live_api_fetch('NFL', 'today'):
        return {}
    try:
        response = requests.get(f'{api_base_url}/api/v1/standings/nfl', timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        records = {}
        for t in data.get('teams', []):
            name = (t.get('team_name') or '').strip()
            abbrev = (t.get('abbreviation') or '').strip()
            record = {
                'wins': int(t.get('wins') or 0),
                'losses': int(t.get('losses') or 0),
                'ties': int(t.get('ties') or 0),
            }
            if name:
                records[name] = record
            if abbrev:
                records[abbrev] = record
        return records
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


def _fetch_league_standings(api_base_url, league):
    """Fetch standings keyed by team name and abbreviation for record-based league pages."""
    try:
        response = requests.get(f'{api_base_url}/api/v1/standings/{league.lower()}', timeout=10)
        if response.status_code != 200:
            return None
        data = response.json()
        records = {}
        for t in data.get('teams', []) or data.get('standings', []):
            name = (t.get('team_name') or t.get('name') or '').strip()
            abbrev = (t.get('abbreviation') or t.get('team_abbreviation') or '').strip()
            record = {
                'wins': int(t.get('wins') or 0),
                'losses': int(t.get('losses') or 0),
                'ties': int(t.get('ties') or t.get('draws') or t.get('otl') or t.get('overtime_losses') or 0),
                'points': t.get('points'),
                'games_back': t.get('games_back') if t.get('games_back') not in (None, '') else t.get('gb'),
            }
            if record['points'] in (None, ''):
                record['points'] = (record['wins'] * 2) + record['ties']
            else:
                record['points'] = int(record['points'] or 0)
            if name:
                records[name] = record
            if abbrev:
                records[abbrev] = record
        return records
    except Exception:
        return None


def _fetch_team_records_map(api_base_url, league):
    """Fetch standings keyed by team name/abbreviation for homepage record display."""
    league_lower = str(league or '').lower()
    try:
        data = _fetch_api_json(f'/api/v1/standings/{league_lower}', timeout=10, api_base_url=api_base_url)
        rows = list((data or {}).get('teams') or (data or {}).get('standings') or [])
        records = {}
        for row in rows:
            name = (row.get('team_name') or row.get('name') or '').strip()
            abbrev = (row.get('abbreviation') or row.get('team_abbreviation') or '').strip()
            wins = int(row.get('wins') or 0)
            losses = int(row.get('losses') or 0)
            draws = int(row.get('draws') or row.get('ties') or 0)
            no_result = int(row.get('no_result') or row.get('no_results') or row.get('nr') or row.get('noResult') or 0)
            record = {
                'wins': wins,
                'losses': losses,
                'ties': draws,
                'draws': draws,
                'no_result': no_result,
                'points': row.get('points'),
                'record': row.get('record'),
            }
            if league_lower == 'wc':
                record['record'] = record['record'] or f'{wins}-{draws}-{losses}'
            elif league_lower in ('ipl', 'mlc'):
                record['record'] = record['record'] or f'{wins}-{losses}-{no_result}'
            else:
                record['record'] = record['record'] or f'{wins}-{losses}'
            if name:
                records[name] = record
            if abbrev:
                records[abbrev] = record
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


def _format_deployment_timestamp(value):
    raw = str(value or '').strip()
    if not raw:
        return ''

    normalized = raw.replace('Z', '+00:00')
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return raw

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed_utc = parsed.astimezone(timezone.utc)
    return parsed_utc.strftime('%b %d, %Y %I:%M %p UTC').replace(' 0', ' ')


DEPLOYMENT_TAG = os.getenv('SPORTSPUFF_DEPLOYMENT_TAG', '').strip()
DEPLOYMENT_SHA = os.getenv('SPORTSPUFF_DEPLOYMENT_SHA', '').strip()
DEPLOYMENT_RUN_ID = os.getenv('SPORTSPUFF_DEPLOYMENT_RUN_ID', '').strip()
DEPLOYMENT_RUN_NUMBER = os.getenv('SPORTSPUFF_DEPLOYMENT_RUN_NUMBER', '').strip()
DEPLOYMENT_RUN_URL = os.getenv('SPORTSPUFF_DEPLOYMENT_RUN_URL', '').strip()
DEPLOYMENT_AT = _format_deployment_timestamp(os.getenv('SPORTSPUFF_DEPLOYED_AT', ''))

if not DEPLOYMENT_TAG and DEPLOYMENT_RUN_ID:
    DEPLOYMENT_TAG = f"run-{DEPLOYMENT_RUN_ID}"

DEPLOYMENT_INFO = {
    'tag': DEPLOYMENT_TAG,
    'sha': DEPLOYMENT_SHA[:7] if DEPLOYMENT_SHA else '',
    'run_id': DEPLOYMENT_RUN_ID,
    'run_number': DEPLOYMENT_RUN_NUMBER,
    'run_url': DEPLOYMENT_RUN_URL,
    'deployed_at': DEPLOYMENT_AT,
}

# Start background cache refresh thread (avoid duplicate in Flask reloader)
if os.getenv('DISABLE_BACKGROUND_CACHE_REFRESH') != '1' and (
    not os.environ.get('WERKZEUG_RUN_MAIN') or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
):
    _cache_thread = threading.Thread(target=_background_cache_refresh, args=(API_BASE_URL,), daemon=True)
    _cache_thread.start()
    logger.info("Background cache refresh thread started (60s interval)")

@app.context_processor
def inject_globals():
    return {'API_BASE_URL': API_BASE_URL, 'deployment_info': DEPLOYMENT_INFO}

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
            {'name': 'Playoffs', 'start': '2026-04-19', 'end': '2026-06-19'},
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


def _iso_today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _league_is_in_active_window(league, date_value=None):
    league_upper = (league or '').upper()
    season = SEASON_DATES.get(league_upper)
    if not season:
        return True
    probe = _iso_today() if not date_value or date_value == 'today' else date_value
    return any(window['start'] <= probe <= window['end'] for window in season.get('types', []))


def _should_skip_live_api_fetch(league, api_date='today'):
    return (league or '').upper() == 'NFL' and api_date == 'today' and not _league_is_in_active_window('NFL')

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
            if (
                league_upper == 'MLC'
                and data.get('current_phase') in (None, '', 'Off Season', 'Offseason')
                and not data.get('season_types')
            ):
                schedule = _fetch_api_json(f'/api/v1/schedule/{league.lower()}/today?tz=pt', timeout=10)
                standings = _fetch_api_json(f'/api/v1/standings/{league.lower()}', timeout=10)
                schedule_games = list((schedule or {}).get('games') or [])
                standings_rows = list((standings or {}).get('teams') or (standings or {}).get('standings') or [])
                has_live_rows = any(
                    (int(team.get('matches') or 0) > 0)
                    or (int(team.get('wins') or 0) > 0)
                    or (int(team.get('losses') or 0) > 0)
                    for team in standings_rows
                )
                if schedule_games or has_live_rows:
                    data['current_phase'] = 'Regular Season'
                    data['season_types'] = [{
                        'name': 'Regular Season',
                        'display': 'Regular Season underway',
                    }]
            fmt = lambda d: datetime.strptime(d, '%Y-%m-%d').strftime('%b %-d') if d else ''
            for st in data.get('season_types', []):
                st['display'] = st.get('display') or f"{st['name']}: {fmt(st.get('start_date',''))} - {fmt(st.get('end_date',''))}"
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
        fallback = _fallback_catalog()
        return render_template(
            'index.html',
            team_count=fallback['team_count'],
            stadium_count=fallback['stadium_count'],
            linked_count=fallback['linked_count'],
            league_stats=fallback['league_stats'],
            logo_mapping=LOGO_MAPPING,
            nba_team_colors=fallback['team_colors'].get('NBA', {}),
            team_colors=fallback['team_colors'],
            API_BASE_URL=API_BASE_URL,
            db_available=False,
            using_fallback_catalog=True,
        )
    
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
        team_colors = _build_team_colors(all_teams)
        
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
                             db_available=True,
                             using_fallback_catalog=False)
    
    except Exception as e:
        logger.error(f'Error loading dashboard: {e}', exc_info=True)
        flash(f'Error loading dashboard: {e}', 'error')
        if conn:
            try:
                conn.close()
            except:
                pass
        fallback = _fallback_catalog()
        return render_template(
            'index.html',
            team_count=fallback['team_count'],
            stadium_count=fallback['stadium_count'],
            linked_count=fallback['linked_count'],
            league_stats=fallback['league_stats'],
            logo_mapping=LOGO_MAPPING,
            nba_team_colors=fallback['team_colors'].get('NBA', {}),
            team_colors=fallback['team_colors'],
            API_BASE_URL=API_BASE_URL,
            db_available=False,
            using_fallback_catalog=True,
        )

@app.route('/admin')
def admin_panel():
    """Admin panel showing statistics and management options"""
    conn = get_db_connection()
    if not conn:
        fallback_teams = [dict(team) for team in _fallback_catalog()['teams_by_league'].get(league_upper, [])]
        if fallback_teams:
            return _render_regular_league_page(league_upper, fallback_teams)
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


def _render_regular_league_page(league_name, teams):
    organized_teams = {}
    for team in teams:
        conference = team.get('conference_name') or 'No Conference'
        division = team.get('division_name') or 'No Division'
        organized_teams.setdefault(conference, {}).setdefault(division, [])
        team['abbreviation'] = team.get('abbreviation') or team.get('team_abbreviation') or get_team_abbreviation(team['real_team_name'], league_name)
        organized_teams[conference][division].append(team)

    nfl_division_grid = []

    def _record_for_team(records, team):
        return records.get(team['real_team_name']) or records.get(team.get('abbreviation'))

    def _apply_records(records, include_points=False):
        for conference in organized_teams:
            for division in organized_teams[conference]:
                for team in organized_teams[conference][division]:
                    rec = _record_for_team(records, team)
                    if not rec:
                        continue
                    team['team_wins'] = rec.get('wins', team.get('team_wins'))
                    team['team_losses'] = rec.get('losses', team.get('team_losses'))
                    team['team_ties'] = rec.get('ties', team.get('team_ties') or 0)
                    if include_points:
                        team['standings_points'] = rec.get('points')

    def _sort_by_record_with_gb():
        for conference in organized_teams:
            for division in organized_teams[conference]:
                teams_list = organized_teams[conference][division]
                teams_list.sort(
                    key=lambda t: (
                        -(t.get('team_wins') or 0),
                        (t.get('team_losses') or 0),
                        -(t.get('team_ties') or 0),
                        t.get('real_team_name') or '',
                    )
                )
                if teams_list and teams_list[0].get('team_wins') is not None:
                    leader_wins = teams_list[0].get('team_wins') or 0
                    leader_losses = teams_list[0].get('team_losses') or 0
                    for team in teams_list:
                        tw = team.get('team_wins') or 0
                        tl = team.get('team_losses') or 0
                        gb = ((leader_wins - tw) + (tl - leader_losses)) / 2.0
                        team['games_behind'] = '-' if gb == 0 else f'{gb:.1f}'.rstrip('0').rstrip('.')

    def _sort_by_points():
        for conference in organized_teams:
            for division in organized_teams[conference]:
                teams_list = organized_teams[conference][division]
                for team in teams_list:
                    if team.get('standings_points') is None:
                        team['standings_points'] = ((team.get('team_wins') or 0) * 2) + (team.get('team_ties') or 0)
                teams_list.sort(
                    key=lambda t: (
                        -(t.get('standings_points') or 0),
                        -(t.get('team_wins') or 0),
                        (t.get('team_losses') or 0),
                        t.get('real_team_name') or '',
                    )
                )

    if league_name == 'MLB':
        _sort_by_record_with_gb()
    if league_name == 'NBA':
        _apply_records(_fetch_league_standings(API_BASE_URL, 'nba') or {})
        _sort_by_record_with_gb()
    if league_name == 'NHL':
        _apply_records(_fetch_league_standings(API_BASE_URL, 'nhl') or {}, include_points=True)
        _sort_by_points()
    if league_name == 'MLS':
        mls_records = (_fetch_mls_standings(API_BASE_URL) or {}).get('teams', {})
        for conference in organized_teams:
            for division in organized_teams[conference]:
                teams_list = organized_teams[conference][division]
                for team in teams_list:
                    rec = mls_records.get(team['real_team_name']) or mls_records.get(team['abbreviation'])
                    if rec:
                        team['team_wins'] = int(rec.get('wins') or team.get('team_wins') or 0)
                        team['team_losses'] = int(rec.get('losses') or team.get('team_losses') or 0)
                        team['team_ties'] = int(rec.get('draws') or team.get('team_ties') or 0)
                        team['mls_points'] = int(rec.get('points') or ((team['team_wins'] * 3) + team['team_ties']))
                    else:
                        team['mls_points'] = (team.get('team_wins') or 0) * 3 + (team.get('team_ties') or 0)
                teams_list.sort(key=lambda t: (t.get('mls_points') or 0), reverse=True)
    if league_name == 'NFL':
        _apply_records(_fetch_nfl_standings(API_BASE_URL) or {})
        _sort_by_record_with_gb()
        nfl_order = [
            [('AFC', 'East'), ('AFC', 'West'), ('NFC', 'East'), ('NFC', 'West')],
            [('AFC', 'North'), ('AFC', 'South'), ('NFC', 'North'), ('NFC', 'South')],
        ]
        nfl_division_grid = [
            [
                {
                    'conference': conference,
                    'division': division,
                    'teams': organized_teams.get(conference, {}).get(division, []),
                }
                for conference, division in row
            ]
            for row in nfl_order
        ]
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

    return render_template(
        'league_page.html',
        league_name=league_name,
        organized_teams=organized_teams,
        nfl_division_grid=nfl_division_grid,
        logo_mapping=LOGO_MAPPING,
        league_info=None,
    )

@app.route('/league/<league_name>')
def league_page(league_name):
    """League page showing teams or event/tour schedules."""
    league_upper = league_name.upper()
    event_leagues = {
        'WC': {
            'display_name': 'World Cup',
            'subtitle': 'Tournament fixtures, groups, and knockout rounds',
            'logo_url': 'https://www.splitsp.lat/logos/wc/wc-logo.png',
            'accent': '#00824A',
            'mode': 'world-cup',
        },
        'ATP': {
            'display_name': 'ATP Tour',
            'subtitle': 'Men\'s tour matches and active tournaments',
            'logo_url': 'https://www.splitsp.lat/logos/atp/atp-logo.png',
            'accent': '#003DA5',
            'mode': 'tennis',
        },
        'WTA': {
            'display_name': 'WTA Tour',
            'subtitle': 'Women\'s tour matches and active tournaments',
            'logo_url': 'https://www.splitsp.lat/logos/wta/wta-logo.png',
            'accent': '#A01469',
            'mode': 'tennis',
        },
        'CYCLING': {
            'display_name': 'Cycling',
            'subtitle': 'Race calendar, stages, and daily events',
            'logo_url': 'https://www.splitsp.lat/logos/cycling/uci/uci-logo.png',
            'accent': '#F5E814',
            'mode': 'cycling',
            'banner_logo_url': 'https://www.splitsp.lat/logos/cycling/uci/uci-logo-125-years.png',
            'banner_link': 'https://www.uci.org/the-uci-celebrates-its-125th-anniversary/7cSGKuFPEiLx1fVHx7YCDe',
            'banner_text': 'UCI celebrates 125 years',
        },
    }
    if league_upper in event_leagues:
        return render_template(
            'event_league_page.html',
            league_name=league_upper,
            league_config=event_leagues[league_upper],
            wc_team_codes=WC_TEAM_CODES_BY_NAME,
            API_BASE_URL=API_BASE_URL,
        )

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

        cursor.close()
        conn.close()

        return _render_regular_league_page(league_upper, teams)
    
    except Exception as e:
        return render_template('error.html', message=str(e))


@app.route('/league/cycling/tour-de-france')
@app.route('/league/cycling/tour-de-france/<int:year>')
def tour_de_france_page(year=None):
    """Detailed Tour de France page backed by sportspuff-api."""
    return render_template(
        'tour_de_france_page.html',
        year=int(year or datetime.now().year),
        API_BASE_URL=API_BASE_URL,
    )

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


def _wc_team_code_for_name(team_name):
    clean_name = ' '.join(str(team_name or '').split())
    return WC_TEAM_CODES_BY_NAME.get(clean_name, '')


def _wc_team_ball_logo_url(team_code):
    return f"{WC_TEAM_BALL_BASE_URL}/{team_code.lower()}_ball_logo.png"


def _wc_teams_from_standings(data):
    teams = list(data.get('teams') or [])
    if teams:
        return teams

    for group in data.get('groups') or []:
        for team in group.get('teams') or []:
            with_group = dict(team)
            with_group.setdefault('group', group.get('group'))
            teams.append(with_group)
    return teams


def _wc_schedule_dates(start=WC_GROUP_STAGE_START, end=WC_GROUP_STAGE_END):
    dates = []
    cursor = datetime.strptime(start, '%Y-%m-%d').date()
    last = datetime.strptime(end, '%Y-%m-%d').date()
    while cursor <= last:
        dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    return dates


def _normalize_wc_name(value):
    return ' '.join(str(value or '').lower().replace('-', ' ').split())


def _canonical_wc_group_for_team(team):
    abbrev = str(team.get('abbreviation') or team.get('team_abbreviation') or '').strip().upper()
    if abbrev in WC_CANONICAL_GROUP_BY_CODE:
        return WC_CANONICAL_GROUP_BY_CODE[abbrev]
    return WC_CANONICAL_GROUP_BY_NAME.get(_normalize_wc_name(team.get('team_name') or team.get('name')))


def _normalize_wc_standings(data):
    if not isinstance(data, dict):
        return data

    normalized = dict(data)
    teams = []
    for team in _wc_teams_from_standings(data):
        row = dict(team)
        canonical_group = _canonical_wc_group_for_team(row)
        if canonical_group:
            row['group'] = canonical_group
        teams.append(row)

    if teams:
        normalized['teams'] = teams
        groups = []
        for group_name in 'ABCDEFGHIJKL':
            group_teams = [dict(team) for team in teams if str(team.get('group') or '').upper() == group_name]
            if not group_teams:
                continue
            group_teams.sort(
                key=lambda team: (
                    int(team.get('group_rank') or 999),
                    -int(team.get('points') or 0),
                    -int(team.get('goal_difference') or 0),
                    -int(team.get('goals_for') or 0),
                    str(team.get('team_name') or ''),
                )
            )
            groups.append({'group': group_name, 'teams': group_teams})
        normalized['groups'] = groups

    return normalized


def _wc_standard_code_for_name(team_name, fallback_abbrev=''):
    return _wc_team_code_for_name(team_name) or str(fallback_abbrev or '').strip().lower()


def _wc_game_involves_team(game, team):
    selected_code = str(team.get('standard_code') or '').lower()
    selected_name = _normalize_wc_name(team.get('team_name'))
    home_code = _wc_standard_code_for_name(game.get('home_team'), game.get('home_team_abbrev'))
    visitor_code = _wc_standard_code_for_name(game.get('visitor_team'), game.get('visitor_team_abbrev'))
    return (
        home_code == selected_code or
        visitor_code == selected_code or
        _normalize_wc_name(game.get('home_team')) == selected_name or
        _normalize_wc_name(game.get('visitor_team')) == selected_name
    )


def _fetch_wc_team_games(team):
    games = []

    def fetch_day(date):
        cache_key = f'schedule:wc:{date}:pt'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return cached.get('games', [])
        data = _fetch_api_json(f'/api/v1/schedule/wc/{date}?tz=pt', timeout=15)
        if isinstance(data, dict) and 'error' not in data:
            set_cached_response(cache_key, data)
            return data.get('games', [])
        return []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch_day, date) for date in _wc_schedule_dates()]
        for future in as_completed(futures):
            try:
                games.extend(game for game in future.result() if _wc_game_involves_team(game, team))
            except Exception as e:
                logger.warning(f"Unable to fetch a World Cup schedule date for {team.get('team_name')}: {e}")

    games.sort(key=lambda game: game.get('game_time') or game.get('game_date') or '')
    return games


@app.route('/team/wc/<team_code>')
def world_cup_team_detail(team_code):
    """Show a World Cup team page backed by sportspuff-api standings data."""
    requested_code = str(team_code or '').strip().lower()
    if not requested_code:
        flash('World Cup team not found', 'error')
        return redirect(url_for('league_page', league_name='WC'))

    try:
        standings = _fetch_api_json('/api/v1/standings/wc', timeout=15)
        standings = _normalize_wc_standings(standings if isinstance(standings, dict) else {})
        teams = _wc_teams_from_standings(standings if isinstance(standings, dict) else {})
        selected_team = None

        for team in teams:
            standard_code = _wc_team_code_for_name(team.get('team_name')) or str(team.get('abbreviation') or '').lower()
            if standard_code.lower() == requested_code or str(team.get('abbreviation') or '').lower() == requested_code:
                selected_team = dict(team)
                selected_team['standard_code'] = standard_code.lower()
                break

        if not selected_team:
            flash('World Cup team not found', 'error')
            return redirect(url_for('league_page', league_name='WC'))

        selected_group = str(selected_team.get('group') or '').strip()
        group_teams = [
            dict(team)
            for team in teams
            if str(team.get('group') or '').strip().upper() == selected_group.upper()
        ]
        group_teams.sort(key=lambda team: (
            int(team.get('group_rank') or 999),
            str(team.get('team_name') or '')
        ))

        selected_team['ball_logo_url'] = _wc_team_ball_logo_url(selected_team['standard_code'])
        selected_team['team_league'] = 'World Cup'
        team_games = _fetch_wc_team_games(selected_team)

        return render_template(
            'world_cup_team_detail.html',
            team=selected_team,
            group_teams=group_teams,
            team_games=team_games,
        )
    except Exception as e:
        logger.error(f"Error loading World Cup team {team_code}: {e}", exc_info=True)
        return render_template('error.html', message=str(e))

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
        fallback = _fallback_catalog()
        filtered = [dict(team) for team in fallback['teams']]
        if league_filter:
            filtered = [team for team in filtered if team.get('league_name_proper', '').lower() == league_filter.lower()]
        if search:
            needle = search.lower()
            filtered = [
                team for team in filtered
                if needle in (team.get('real_team_name') or '').lower()
                or needle in (team.get('city_name') or '').lower()
            ]
        if linked_filter == 'true':
            filtered = [team for team in filtered if team.get('stadium_id') is not None]
        elif linked_filter == 'false':
            filtered = [team for team in filtered if team.get('stadium_id') is None]
        total_count = len(filtered)
        offset = (page - 1) * per_page
        page_rows = filtered[offset: offset + per_page]
        leagues = sorted(fallback['teams_by_league'].keys())
        return render_template(
            'teams.html',
            teams=page_rows,
            leagues=leagues,
            divisions=[],
            current_league=league_filter,
            league_filter=league_filter,
            search=search,
            page=page,
            total_pages=(total_count + per_page - 1) // per_page,
            total_count=total_count,
            logo_mapping=LOGO_MAPPING,
            db_available=False,
        )

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
        fallback = _fallback_catalog()
        rows = list(fallback['stadiums_by_id'].values())
        if search:
            needle = search.lower()
            rows = [
                stadium for stadium in rows
                if needle in (stadium.get('full_stadium_name') or '').lower()
                or needle in (stadium.get('city_name') or '').lower()
            ]
        total_count = len(rows)
        offset = (page - 1) * per_page
        return render_template(
            'stadiums.html',
            stadiums=rows[offset: offset + per_page],
            search=search,
            page=page,
            total_pages=(total_count + per_page - 1) // per_page,
            total_count=total_count,
        )
    
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
        team = _fallback_catalog()['teams_by_lookup'].get((league_name.lower(), team_name.lower()))
        if team:
            return render_template('team_detail_horizontal.html', team=team)
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
        team = _fallback_catalog()['teams_by_id'].get(team_id)
        if team:
            return render_template('team_detail_horizontal.html', team=team)
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
        fallback = _fallback_catalog()
        stadium = fallback['stadiums_by_id'].get(stadium_id)
        if stadium:
            return render_template(
                'stadium_detail_horizontal.html',
                stadium=stadium,
                teams=fallback['teams_by_stadium'].get(stadium_id, []),
            )
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


# --- /api/v1/ — versioned, envelope-shaped local data endpoints ---------------
def _clamp_limit(raw, default=200, hard_max=500):
    try:
        n = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, hard_max))

def _clamp_offset(raw):
    try:
        n = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        n = 0
    return max(0, n)


@app.route('/api/v1/teams')
def api_v1_teams():
    """Versioned teams endpoint with envelope + filters.

    Query params: league, linked (true/false), search, limit, offset.
    """
    league = request.args.get('league', '').strip()
    linked = request.args.get('linked', '').strip().lower()
    search = request.args.get('search', '').strip()
    limit = _clamp_limit(request.args.get('limit'))
    offset = _clamp_offset(request.args.get('offset'))

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        wheres, params = [], []
        if league:
            wheres.append("LOWER(l.league_name_proper) = LOWER(%s)")
            params.append(league)
        if linked == 'true':
            wheres.append("t.stadium_id IS NOT NULL")
        elif linked == 'false':
            wheres.append("t.stadium_id IS NULL")
        if search:
            wheres.append("(t.real_team_name ILIKE %s OR t.city_name ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

        cursor.execute(f"""
            SELECT COUNT(*) AS total
            FROM teams t
            LEFT JOIN leagues l ON t.league_id = l.league_id
            {where_clause}
        """, params)
        total = cursor.fetchone()['total']

        cursor.execute(f"""
            SELECT t.team_id, t.real_team_name, t.team_abbreviation,
                   l.league_name_proper AS league,
                   t.city_name, t.state_name, t.country,
                   t.team_wins, t.team_losses, t.team_ties,
                   t.stadium_id, s.full_stadium_name AS stadium_name,
                   s.city_name AS stadium_city, s.state_name AS stadium_state
            FROM teams t
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            {where_clause}
            ORDER BY l.league_name_proper, t.real_team_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = [dict(r) for r in cursor.fetchall()]

        cursor.close()
        conn.close()
        return jsonify({
            'count': len(rows),
            'total': total,
            'limit': limit,
            'offset': offset,
            'filters': {'league': league or None, 'linked': linked or None, 'search': search or None},
            'teams': rows,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/stadiums')
def api_v1_stadiums():
    """Versioned stadiums endpoint with envelope + filters.

    Query params: city, has_teams (true/false), search, limit, offset.
    """
    city = request.args.get('city', '').strip()
    has_teams = request.args.get('has_teams', '').strip().lower()
    search = request.args.get('search', '').strip()
    limit = _clamp_limit(request.args.get('limit'))
    offset = _clamp_offset(request.args.get('offset'))

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        wheres, params = [], []
        if city:
            wheres.append("s.city_name ILIKE %s")
            params.append(f'%{city}%')
        if search:
            wheres.append("(s.full_stadium_name ILIKE %s OR s.city_name ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

        having_clause = ""
        if has_teams == 'true':
            having_clause = "HAVING COUNT(t.team_id) > 0"
        elif has_teams == 'false':
            having_clause = "HAVING COUNT(t.team_id) = 0"

        cursor.execute(f"""
            SELECT COUNT(*) AS total FROM (
                SELECT s.stadium_id
                FROM stadiums s
                LEFT JOIN teams t ON s.stadium_id = t.stadium_id
                {where_clause}
                GROUP BY s.stadium_id
                {having_clause}
            ) sub
        """, params)
        total = cursor.fetchone()['total']

        cursor.execute(f"""
            SELECT s.stadium_id, s.full_stadium_name, s.city_name, s.state_name, s.country,
                   COUNT(t.team_id) AS team_count
            FROM stadiums s
            LEFT JOIN teams t ON s.stadium_id = t.stadium_id
            {where_clause}
            GROUP BY s.stadium_id
            {having_clause}
            ORDER BY s.full_stadium_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = [dict(r) for r in cursor.fetchall()]

        cursor.close()
        conn.close()
        return jsonify({
            'count': len(rows),
            'total': total,
            'limit': limit,
            'offset': offset,
            'filters': {'city': city or None, 'has_teams': has_teams or None, 'search': search or None},
            'stadiums': rows,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- /curl/v1/ — terminal-friendly text variants of the v1 endpoints ----------
def _truncate(s, n):
    s = (s or '')
    return s if len(s) <= n else s[:n - 1] + '…'

def _text_response(body):
    return Response(body, mimetype='text/plain; charset=utf-8')


@app.route('/api')
def api_docs():
    """Docs page listing v6-owned API endpoints."""
    return render_template('api_docs.html')


@app.route('/curl/v1/teams')
def curl_v1_teams():
    """Plain-text columnar listing of teams. Same filters as /api/v1/teams."""
    league = request.args.get('league', '').strip()
    linked = request.args.get('linked', '').strip().lower()
    search = request.args.get('search', '').strip()
    limit = _clamp_limit(request.args.get('limit'))
    offset = _clamp_offset(request.args.get('offset'))

    conn = get_db_connection()
    if not conn:
        return _text_response('error: database connection failed\n'), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        wheres, params = [], []
        if league:
            wheres.append("LOWER(l.league_name_proper) = LOWER(%s)")
            params.append(league)
        if linked == 'true':
            wheres.append("t.stadium_id IS NOT NULL")
        elif linked == 'false':
            wheres.append("t.stadium_id IS NULL")
        if search:
            wheres.append("(t.real_team_name ILIKE %s OR t.city_name ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

        cursor.execute(f"""
            SELECT l.league_name_proper AS league,
                   t.team_abbreviation AS abbr,
                   t.real_team_name AS team,
                   t.city_name AS city,
                   COALESCE(s.full_stadium_name, '-') AS stadium
            FROM teams t
            LEFT JOIN stadiums s ON t.stadium_id = s.stadium_id
            LEFT JOIN leagues l ON t.league_id = l.league_id
            {where_clause}
            ORDER BY l.league_name_proper, t.real_team_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        out = ['{:<6} {:<6} {:<32} {:<22} {}'.format('LEAGUE', 'ABBR', 'TEAM', 'CITY', 'STADIUM')]
        out.append('-' * 100)
        for r in rows:
            out.append('{:<6} {:<6} {:<32} {:<22} {}'.format(
                _truncate(r['league'], 6),
                _truncate(r['abbr'] or '-', 6),
                _truncate(r['team'], 32),
                _truncate(r['city'] or '-', 22),
                _truncate(r['stadium'], 40),
            ))
        out.append('')
        out.append(f'{len(rows)} teams (limit={limit}, offset={offset})')
        return _text_response('\n'.join(out) + '\n')
    except Exception as e:
        return _text_response(f'error: {e}\n'), 500


@app.route('/curl/v1/stadiums')
def curl_v1_stadiums():
    """Plain-text columnar listing of stadiums. Same filters as /api/v1/stadiums."""
    city = request.args.get('city', '').strip()
    has_teams = request.args.get('has_teams', '').strip().lower()
    search = request.args.get('search', '').strip()
    limit = _clamp_limit(request.args.get('limit'))
    offset = _clamp_offset(request.args.get('offset'))

    conn = get_db_connection()
    if not conn:
        return _text_response('error: database connection failed\n'), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        wheres, params = [], []
        if city:
            wheres.append("s.city_name ILIKE %s")
            params.append(f'%{city}%')
        if search:
            wheres.append("(s.full_stadium_name ILIKE %s OR s.city_name ILIKE %s)")
            params.extend([f'%{search}%', f'%{search}%'])
        where_clause = ("WHERE " + " AND ".join(wheres)) if wheres else ""

        having_clause = ""
        if has_teams == 'true':
            having_clause = "HAVING COUNT(t.team_id) > 0"
        elif has_teams == 'false':
            having_clause = "HAVING COUNT(t.team_id) = 0"

        cursor.execute(f"""
            SELECT s.stadium_id AS id, s.full_stadium_name AS stadium,
                   s.city_name AS city, s.state_name AS state,
                   COUNT(t.team_id) AS teams
            FROM stadiums s
            LEFT JOIN teams t ON s.stadium_id = t.stadium_id
            {where_clause}
            GROUP BY s.stadium_id
            {having_clause}
            ORDER BY s.full_stadium_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        out = ['{:<5} {:<40} {:<22} {:<6} {}'.format('ID', 'STADIUM', 'CITY', 'STATE', 'TEAMS')]
        out.append('-' * 88)
        for r in rows:
            out.append('{:<5} {:<40} {:<22} {:<6} {}'.format(
                r['id'],
                _truncate(r['stadium'], 40),
                _truncate(r['city'] or '-', 22),
                _truncate((r['state'] or '-').upper(), 6),
                r['teams'],
            ))
        out.append('')
        out.append(f'{len(rows)} stadiums (limit={limit}, offset={offset})')
        return _text_response('\n'.join(out) + '\n')
    except Exception as e:
        return _text_response(f'error: {e}\n'), 500


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

    fallback_team = _fallback_catalog()['teams_by_id'].get(_csv_int(team_id))
    if fallback_team and fallback_team.get('logo_filename'):
        return f"https://www.splitsp.lat/logos/{fallback_team['team_league'].lower()}/{fallback_team['logo_filename']}"

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
        data = _empty_all_scores_response()
        data['wc'] = _fetch_league_schedule_and_scores(
            'wc',
            api_date,
            tz,
            api_base_url=API_BASE_URL,
            timeout=5,
            include_scores=False,
        )
        logger.warning(f"No all-scores cache available for {tz}; returning WC-first fallback while warming cache")
        return jsonify(data), 200

    leagues = ['mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc', 'wc', 'atp', 'wta', 'cycling']
    result = {}

    def fetch_league(lg):
        return lg, _fetch_league_schedule_and_scores(lg, api_date, tz)

    with ThreadPoolExecutor(max_workers=12) as executor:
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

        if _should_skip_live_api_fetch(league, api_date):
            return jsonify({'date': _iso_today(), 'games': []}), 200

        cached_response = get_cached_response(cache_key, 'schedule')
        if cached_response:
            return jsonify(cached_response)
        
        try:
            data = _fetch_api_json(f'/api/v1/schedule/{league}/{api_date}?tz={tz}', timeout=20)
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching schedule for {league}/{api_date} after 20s")
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

@app.route('/api/proxy/standings/<league>')
def proxy_standings(league):
    """Proxy standings API requests to avoid CORS issues with caching."""
    league_lower = league.lower()
    if league_lower not in ('mlb', 'nba', 'nfl', 'nhl', 'mls', 'wnba', 'ipl', 'mlc', 'wc', 'cycling'):
        return jsonify({'teams': [], 'standings': [], 'available': False}), 400

    # World Cup standings changed shape to include full group data; version the key
    # so deployments do not keep serving older truncated group payloads.
    cache_key = f'standings:{league_lower}:groups-v3' if league_lower == 'wc' else f'standings:{league_lower}'
    cached_response = get_cached_response(cache_key, 'schedule')
    if cached_response:
        return jsonify(cached_response)

    try:
        data = _fetch_api_json(f'/api/v1/standings/{league_lower}', timeout=15)
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Standings API returned error for {league_lower}: {data['error']}")
            return jsonify(data), 500

        if league_lower == 'wc':
            data = _normalize_wc_standings(data)

        set_cached_response(cache_key, data)
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying standings for {league_lower}: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached standings due to request exception")
            return jsonify(expired_cache)
        return jsonify({'teams': [], 'standings': [], 'groups': [], 'available': False}), 200
    except Exception as e:
        logger.error(f"Unexpected error proxying standings for {league_lower}: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached standings due to unexpected error")
            return jsonify(expired_cache)
        return jsonify({'teams': [], 'standings': [], 'groups': [], 'available': False}), 200


@app.route('/api/proxy/cycling/tour-de-france')
@app.route('/api/proxy/cycling/tour-de-france/<int:year>')
def proxy_cycling_tour_de_france(year=None):
    """Proxy the Tour de France detail bundle."""
    suffix = str(int(year)) if year else 'current'
    cache_key = f'cycling_tour_de_france:{suffix}'
    cached_response = get_cached_response(cache_key, 'schedule')
    if cached_response:
        return jsonify(cached_response)

    path = f'/api/v1/cycling/tour-de-france/{int(year)}' if year else '/api/v1/cycling/tour-de-france'
    try:
        data = _fetch_api_json(path, timeout=20)
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Tour de France API returned error: {data['error']}")
            return jsonify(data), 500
        set_cached_response(cache_key, data)
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying Tour de France bundle: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached Tour de France bundle due to request exception")
            return jsonify(expired_cache)
    except Exception as e:
        logger.error(f"Unexpected error proxying Tour de France bundle: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached Tour de France bundle due to unexpected error")
            return jsonify(expired_cache)

    return jsonify({
        'race': 'Tour de France',
        'year': int(year or datetime.now().year),
        'stages': [],
        'latest_classifications': {},
        'teams': [],
        'riders': [],
        'available': False,
        'meta': {},
    }), 200


@app.route('/api/proxy/world-cup/bracket')
def proxy_world_cup_bracket():
    """Proxy the World Cup knockout bracket."""
    cache_key = 'world_cup_bracket'
    cached_response = get_cached_response(cache_key, 'schedule')
    if cached_response:
        return jsonify(cached_response)

    try:
        data = _fetch_api_json('/api/v1/world-cup/bracket', timeout=15)
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"World Cup bracket API returned error: {data['error']}")
            return jsonify(data), 500
        set_cached_response(cache_key, data)
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error proxying World Cup bracket: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached World Cup bracket due to request exception")
            return jsonify(expired_cache)
        return jsonify({'sport': 'wc', 'knockout_bracket': {}, 'available': False}), 200
    except Exception as e:
        logger.error(f"Unexpected error proxying World Cup bracket: {e}", exc_info=True)
        expired_cache = get_cached_response(cache_key, 'schedule', allow_expired=True)
        if expired_cache:
            logger.warning("Returning expired cached World Cup bracket due to unexpected error")
            return jsonify(expired_cache)
        return jsonify({'sport': 'wc', 'knockout_bracket': {}, 'available': False}), 200

@app.route('/api/nfl/team-records')
def nfl_team_records():
    """Fetch NFL team records from sportspuff-api standings, keyed by full name and abbreviation."""
    try:
        cache_key = 'nfl_team_records'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached), 200

        if _should_skip_live_api_fetch('NFL', 'today'):
            return jsonify({'teams': {}}), 200

        team_records = _fetch_nfl_standings(API_BASE_URL) or {}

        result = {'teams': team_records}
        set_cached_response(cache_key, result)
        logger.info(f"Fetched records for {len(team_records)} NFL team keys from sportspuff-api")
        return jsonify(result), 200

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching NFL team records: {e}")
        return jsonify({'teams': {}}), 200
    except Exception as e:
        logger.error(f"Unexpected error fetching NFL team records: {e}", exc_info=True)
        return jsonify({'teams': {}}), 200


@app.route('/api/wc/team-records')
def wc_team_records():
    """Fetch World Cup team records from sportspuff-api standings."""
    try:
        cache_key = 'wc_team_records'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached), 200

        team_records = _fetch_team_records_map(API_BASE_URL, 'wc') or {}
        result = {'teams': team_records}
        set_cached_response(cache_key, result)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Unexpected error fetching WC team records: {e}", exc_info=True)
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


@app.route('/api/mlc/team-records')
def mlc_team_records():
    """Fetch MLC team records from sportspuff-api standings."""
    try:
        cache_key = 'mlc_team_records'
        cached = get_cached_response(cache_key, 'schedule')
        if cached:
            return jsonify(cached), 200

        team_records = _fetch_team_records_map(API_BASE_URL, 'mlc') or {}
        result = {'teams': team_records}
        set_cached_response(cache_key, result)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Unexpected error fetching MLC team records: {e}", exc_info=True)
        return jsonify({'teams': {}}), 200

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
        force_fresh = request.args.get('fresh') == '1'

        if date.lower() == 'today':
            cache_key = f'scores:{league}:today:{tz}'
            api_date = 'today'
        else:
            cache_key = f'scores:{league}:{date}:{tz}'
            api_date = date

        if _should_skip_live_api_fetch(league, api_date):
            return jsonify({'date': _iso_today(), 'scores': []}), 200

        cached_response = None if force_fresh else get_cached_response(cache_key, 'scores')
        if cached_response:
            return jsonify(cached_response)

        try:
            data = _fetch_api_json(f'/api/v1/scores/{league}/{api_date}?tz={tz}', timeout=20)
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching scores for {league}/{api_date} after 20s")
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

        # Check for API errors in response
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"API returned error: {data['error']}")
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
