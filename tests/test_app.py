#!/usr/bin/env python3
"""Current-state smoke and contract tests for Sportspuff v6."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import psycopg2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Keep tests isolated from the production cache warmer.
os.environ.setdefault("DISABLE_BACKGROUND_CACHE_REFRESH", "1")
os.environ.setdefault("SPORTSPUFF_API_BASE_URL", "https://api.sportspuff.net")

from app import (  # noqa: E402
    DB_CONFIG,
    LOGO_MAPPING,
    app,
    get_db_connection,
    _empty_all_scores_response,
    _fetch_all_scores_for_tz,
    _fetch_api_json,
    _fetch_nfl_standings,
    _normalize_timezone,
    _should_skip_live_api_fetch,
)


class FakeCursor:
    def __init__(self, fetchone_values=None, fetchall_values=None):
        self.fetchone_values = list(fetchone_values or [])
        self.fetchall_values = list(fetchall_values or [])
        self.executed = []
        self.closed = False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        if self.fetchone_values:
            return self.fetchone_values.pop(0)
        return None

    def fetchall(self):
        if self.fetchall_values:
            return self.fetchall_values.pop(0)
        return []

    def close(self):
        self.closed = True


def fake_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


class TestPageSmoke(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_fallback_catalog_loads_with_theme_switcher(self):
        with patch("app.get_db_connection", return_value=None):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Catalog fallback active", response.data)
        self.assertIn(b'id="tournament-theme-select"', response.data)
        self.assertIn(b"static/js/tournament-theme.js", response.data)
        self.assertIn(b"All 12 leagues", response.data)

    def test_api_docs_page_loads(self):
        response = self.client.get("/api")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"API Endpoints", response.data)
        self.assertIn(b"/api/v1/teams", response.data)

    def test_event_league_pages_load_without_database(self):
        for league, title in [("WC", "World Cup"), ("ATP", "ATP Tour"), ("WTA", "WTA Tour"), ("CYCLING", "Cycling")]:
            with self.subTest(league=league), patch("app.get_db_connection") as db:
                response = self.client.get(f"/league/{league}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(title.encode(), response.data)
        self.assertIn(b"id=\"event-date-picker\"", response.data)
        self.assertIn(b"id=\"event-data-freshness\"", response.data)
        self.assertIn(b"id=\"cycling-standings-panel\"", response.data)
        db.assert_not_called()

    def test_tour_de_france_page_loads_without_database(self):
        with patch("app.get_db_connection") as db:
            response = self.client.get("/league/cycling/tour-de-france")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tour de France", response.data)
        self.assertIn(b"id=\"tdf-summary-panel\"", response.data)
        self.assertIn(b"const TOUR_API_SLUG = \"tour-de-france\";", response.data)
        self.assertIn(b"/api/proxy/cycling/${encodeURIComponent(TOUR_API_SLUG)}/", response.data)
        db.assert_not_called()

    def test_vuelta_page_loads_without_database(self):
        with patch("app.get_db_connection") as db:
            response = self.client.get("/league/cycling/vuelta")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"La Vuelta a Espa\xc3\xb1a", response.data)
        self.assertIn(b"id=\"tdf-summary-panel\"", response.data)
        self.assertIn(b"const TOUR_API_SLUG = \"vuelta\";", response.data)
        self.assertIn(b"/api/proxy/cycling/${encodeURIComponent(TOUR_API_SLUG)}/", response.data)
        db.assert_not_called()

    def test_regular_league_page_exposes_schedule_module(self):
        cursor = FakeCursor(
            fetchone_values=[{"league_name_proper": "NFL", "league_name": "nfl"}],
            fetchall_values=[
                [
                    {
                        "team_id": 1,
                        "real_team_name": "Buffalo Bills",
                        "city_name": "Buffalo",
                        "state_name": "NY",
                        "country": "us",
                        "logo_filename": "bills.png",
                        "team_color_1": "#00338D",
                        "team_color_2": "#ffffff",
                        "team_color_3": "#C60C30",
                        "team_wins": 13,
                        "team_losses": 4,
                        "team_ties": 0,
                        "s_stadium_id": None,
                        "full_stadium_name": None,
                        "stadium_city": None,
                        "stadium_state": None,
                        "conference_name": "AFC",
                        "division_name": "East",
                        "team_league": "NFL",
                    }
                ]
            ],
        )

        with patch("app.get_db_connection", return_value=fake_connection(cursor)), patch("app._fetch_nfl_standings", return_value={}):
            response = self.client.get("/league/NFL")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="league-date-picker"', response.data)
        self.assertIn(b'id="league-timezone-select"', response.data)
        self.assertIn(b'id="league-schedule-context"', response.data)
        self.assertIn(b'id="league-schedule-freshness"', response.data)
        self.assertIn(b"/api/proxy/schedule/", response.data)
        self.assertIn(b"/api/proxy/scores/", response.data)
        self.assertIn(b"/api/season-info/", response.data)
        self.assertIn(b"function cricketInningsText", response.data)
        self.assertIn(b"function formatCricketOvers", response.data)
        self.assertIn(b"function worldCupPenaltyText", response.data)

    def test_static_logo_route_redirects_to_splitsp_lat(self):
        response = self.client.get("/static/logos/mlb/mlb_logo.png")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            "https://www.splitsp.lat/logos/mlb/mlb_logo.png",
        )


class TestLocalApiContracts(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_api_v1_teams_returns_envelope_and_filters(self):
        cursor = FakeCursor(
            fetchone_values=[{"total": 1}],
            fetchall_values=[
                [
                    {
                        "team_id": 1,
                        "real_team_name": "Indiana Pacers",
                        "team_abbreviation": "IND",
                        "league": "NBA",
                        "city_name": "Indianapolis",
                        "state_name": "IN",
                        "country": "us",
                        "team_wins": 50,
                        "team_losses": 32,
                        "team_ties": None,
                        "stadium_id": 10,
                        "stadium_name": "Gainbridge Fieldhouse",
                        "stadium_city": "Indianapolis",
                        "stadium_state": "IN",
                    }
                ]
            ],
        )

        with patch("app.get_db_connection", return_value=fake_connection(cursor)):
            response = self.client.get("/api/v1/teams?league=nba&linked=true&limit=5")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["limit"], 5)
        self.assertEqual(data["filters"]["league"], "nba")
        self.assertEqual(data["filters"]["linked"], "true")
        self.assertEqual(data["teams"][0]["team_abbreviation"], "IND")

    def test_api_v1_stadiums_returns_envelope_and_filters(self):
        cursor = FakeCursor(
            fetchone_values=[{"total": 1}],
            fetchall_values=[
                [
                    {
                        "stadium_id": 10,
                        "full_stadium_name": "Gainbridge Fieldhouse",
                        "city_name": "Indianapolis",
                        "state_name": "IN",
                        "country": "us",
                        "team_count": 1,
                    }
                ]
            ],
        )

        with patch("app.get_db_connection", return_value=fake_connection(cursor)):
            response = self.client.get("/api/v1/stadiums?city=indy&has_teams=true")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["filters"]["city"], "indy")
        self.assertEqual(data["filters"]["has_teams"], "true")
        self.assertEqual(data["stadiums"][0]["team_count"], 1)

    def test_api_v1_database_failure_returns_500(self):
        with patch("app.get_db_connection", return_value=None):
            response = self.client.get("/api/v1/teams")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "Database connection failed")


class TestLiveDataProxyHelpers(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_timezone_aliases_normalize_for_cache_keys(self):
        self.assertEqual(_normalize_timezone("pst"), "pt")
        self.assertEqual(_normalize_timezone("est"), "et")
        self.assertEqual(_normalize_timezone("America/Los_Angeles"), "America/Los_Angeles")

    def test_empty_all_scores_response_contains_all_homepage_leagues(self):
        data = _empty_all_scores_response()

        self.assertEqual(
            set(data),
            {"mlb", "nba", "nfl", "nhl", "mls", "wnba", "ipl", "mlc", "wc", "atp", "wta", "cycling"},
        )
        self.assertEqual(data["atp"]["schedule"]["games"], [])
        self.assertEqual(data["cycling"]["scores"]["scores"], [])

    def test_all_scores_today_falls_back_to_empty_shape_without_network(self):
        with (
            patch("app.get_cached_response", return_value=None),
            patch("app._refresh_cache_async") as refresh,
            patch("app._fetch_league_schedule_and_scores", return_value={"schedule": {"games": []}, "scores": {"scores": []}}),
        ):
            response = self.client.get("/api/proxy/all-scores/today?tz=pst")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("wc", data)
        self.assertIn("cycling", data)
        refresh.assert_called_once()

    @patch("app.requests.get")
    def test_api_json_retries_fallback_host_after_primary_502(self, mock_get):
        primary = MagicMock(status_code=502, text="bad gateway")
        fallback = MagicMock(status_code=200)
        fallback.json.return_value = {"games": [{"game_id": "wc1"}]}
        mock_get.side_effect = [primary, fallback]

        data = _fetch_api_json("/api/v1/schedule/wc/2026-06-11?tz=pt", api_base_url="https://api.sportspuff.net")

        self.assertEqual(data["games"][0]["game_id"], "wc1")
        self.assertEqual(mock_get.call_args_list[0].args[0], "https://api.sportspuff.net/api/v1/schedule/wc/2026-06-11?tz=pt")
        self.assertEqual(mock_get.call_args_list[1].args[0], "https://api-dev.sportspuff.net/api/v1/schedule/wc/2026-06-11?tz=pt")

    @patch("app.requests.get")
    def test_all_scores_fetch_uses_fallback_for_wc_schedule(self, mock_get):
        def response_for(url, **kwargs):
            if "api.sportspuff.net/api/v1/schedule/wc/" in url:
                response = MagicMock(status_code=502, text="bad gateway")
                return response
            if "api-dev.sportspuff.net/api/v1/schedule/wc/" in url:
                response = MagicMock(status_code=200)
                response.json.return_value = {"sport": "wc", "date": "2026-06-11", "games": [{"game_id": "2391728"}]}
                return response
            response = MagicMock(status_code=200)
            if "/scores/" in url:
                response.json.return_value = {"scores": []}
            else:
                response.json.return_value = {"games": []}
            return response

        mock_get.side_effect = response_for

        data = _fetch_all_scores_for_tz("https://api.sportspuff.net", "pt", "2026-06-11")

        self.assertEqual(data["wc"]["schedule"]["games"][0]["game_id"], "2391728")


class TestTournamentThemeAssets(unittest.TestCase):
    def test_theme_script_is_valid_javascript_when_node_is_available(self):
        script = PROJECT_ROOT / "static/js/tournament-theme.js"
        if not script.exists():
            self.fail("static/js/tournament-theme.js not found")

        try:
            result = subprocess.run(
                ["node", "--check", str(script)],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.skipTest("node is not installed")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_tournament_manifest_references_existing_available_assets(self):
        manifest_path = PROJECT_ROOT / "static/images/events/tennis/tournament-assets.json"
        manifest = json.loads(manifest_path.read_text())

        self.assertEqual(manifest["version"], 1)
        self.assertEqual(manifest["base_path"], "/static/images/events/tennis")

        base_dir = manifest_path.parent
        available = [t for t in manifest["tournaments"] if t["available"]]
        self.assertGreaterEqual(len(available), 4)
        for tournament in available:
            self.assertTrue(tournament["ball"], tournament)
            self.assertTrue((base_dir / tournament["ball"]).exists(), tournament)

    def test_active_event_assets_are_local_and_documented(self):
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()
        inventory = (PROJECT_ROOT / "docs/EVENT_ASSET_INVENTORY.md").read_text()
        expected_assets = [
            "static/images/events/tennis/balls/tennis-ball-us-open-navy.svg",
            "static/images/events/tennis/balls/tennis-ball-australian-open-blue.svg",
            "static/images/events/wc/world-cup-2026-mark.svg",
        ]

        for asset in expected_assets:
            self.assertTrue((PROJECT_ROOT / asset).exists(), asset)
            self.assertIn(f"/{asset}", index_template)
            self.assertIn(asset, inventory)
        self.assertIn("https://www.splitsp.lat/logos/cycling/tdf/tdf_logo.png", index_template)
        self.assertIn("https://www.splitsp.lat/logos/cycling/tdf/tdf_logo.png", inventory)
        self.assertTrue((PROJECT_ROOT / "static/images/events/cycling/tour-de-france-mark.svg").exists())

    def test_world_cup_team_balls_use_fifa_country_codes(self):
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn('WC_TEAM_BALL_BASE_URL = "https://www.splitsp.lat/logos/wc/teamballs"', index_template)
        for team_name, code in [
            ("Germany", "ger"),
            ("Spain", "esp"),
            ("England", "eng"),
            ("Scotland", "sco"),
            ("South Africa", "rsa"),
            ("South Korea", "kor"),
            ("Czech Republic", "cze"),
            ("Congo DR", "cod"),
            ("Saudi Arabia", "ksa"),
            ("Switzerland", "sui"),
            ("Curaçao", "cuw"),
        ]:
            self.assertIn(f'"{team_name}": "{code}"', index_template)
        self.assertIn('${code}_ball_logo.png', index_template)
        self.assertIn("isWorldCup ? getWorldCupTeamAbbrev(game.visitor_team)", index_template)
        self.assertIn("(isTennis || isWorldCup) ? null : findTeamData(game.visitor_team, gameLeague)", index_template)
        self.assertIn("lower === 'wc' ? 'World Cup'", index_template)
        self.assertNotIn('SOU_ball_logo.png', index_template)
        self.assertNotIn('ENG_ball_logo.png', index_template)

    def test_homepage_league_dropdown_stays_above_scorecards(self):
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn('class="scores-controls d-flex justify-content-center gap-3 mb-3 flex-wrap"', index_template)
        self.assertIn(".scores-controls", index_template)
        self.assertIn("z-index: 2000", index_template)
        self.assertIn("#leagues-menu", index_template)
        self.assertIn("z-index: 3000", index_template)

    def test_shared_footer_exposes_expected_theme_options(self):
        footer = (PROJECT_ROOT / "templates/shared_footer.html").read_text()

        self.assertIn('id="tournament-theme-select"', footer)
        self.assertIn("site-footer-theme-control", footer)
        self.assertIn("site-footer-deployment", footer)
        self.assertIn("deployment_info.tag or deployment_info.deployed_at", footer)
        header = (PROJECT_ROOT / "templates/shared_header.html").read_text()
        self.assertIn('class="collapse navbar-collapse navbar-main-panel"', header)
        self.assertNotIn('id="tournament-theme-select"', header)

        for theme in [
            "baseball",
            "basketball",
            "cricket",
            "cycling",
            "football",
            "hockey",
            "soccer",
            "tennis",
            "atp",
            "wta",
            "wimbledon",
            "roland-garros",
            "us-open",
            "australian-open",
        ]:
            self.assertIn(f'value="{theme}"', footer)

    def test_admin_template_exposes_deployment_metadata(self):
        admin_template = (PROJECT_ROOT / "templates/admin.html").read_text()

        self.assertIn("admin-deployment-card", admin_template)
        self.assertIn("deployment_info.tag or deployment_info.deployed_at", admin_template)
        self.assertIn("Open GitHub Run", admin_template)

    def test_shared_header_links_to_event_leagues(self):
        header = (PROJECT_ROOT / "templates/shared_header.html").read_text()

        for league in ["ATP", "CYCLING", "WC", "WTA"]:
            self.assertIn(f"league_name='{league}'", header)

    def test_shared_header_league_dropdown_is_alphabetical(self):
        header = (PROJECT_ROOT / "templates/shared_header.html").read_text()
        expected = ["ATP", "CYCLING", "IPL", "MLB", "MLC", "MLS", "NBA", "NFL", "NHL", "WC", "WNBA", "WTA"]

        positions = [header.index(f"league_name='{league}'") for league in expected]
        self.assertEqual(positions, sorted(positions))

    def test_tennis_renderers_accept_api_player_and_tournament_fields(self):
        event_template = (PROJECT_ROOT / "templates/event_league_page.html").read_text()
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()

        for snippet in ["home_player", "away_player", "player1", "player2", "tournament_name", "competition_name"]:
            self.assertIn(snippet, event_template)
            self.assertIn(snippet, index_template)

    def test_sport_theme_css_and_script_support_all_sport_groups(self):
        css = (PROJECT_ROOT / "static/css/main.css").read_text()
        script = (PROJECT_ROOT / "static/js/tournament-theme.js").read_text()

        for theme in ["baseball", "basketball", "cricket", "cycling", "football", "hockey", "soccer", "tennis"]:
            self.assertIn(f'body[data-sport-theme="{theme}"]', css)
            self.assertIn(f"'{theme}'", script)
        self.assertIn("document.body.dataset.sportTheme", script)
        self.assertIn("body[data-sport-theme]::before", css)
        self.assertIn("navbar-main-panel", css)

    def test_ipl_standings_accounts_for_no_results(self):
        template = (PROJECT_ROOT / "templates/league_page.html").read_text()

        self.assertIn("no_result ?? t.no_results ?? t.nr ?? t.noResult", template)
        self.assertIn("(wins * 2) + noResults", template)
        self.assertIn("${wins}W-${losses}L-${noResults}NR", template)
        self.assertIn("NR", template)

    def test_mlc_standings_use_single_column_cards_and_playoff_line(self):
        template = (PROJECT_ROOT / "templates/league_page.html").read_text()

        self.assertIn("id=\"mlc-cards-container\"", template)
        self.assertIn("Playoff Qualification Line", template)
        self.assertIn("mergedRows", template)
        self.assertIn("Object.values(teamLookup)", template)

    def test_homepage_fetches_wc_and_mlc_records_and_uses_compact_live_period_status(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn("fetch('/api/wc/team-records')", template)
        self.assertIn("fetch('/api/mlc/team-records')", template)
        self.assertIn("function formatTimedPeriodStatus", template)
        self.assertIn("return `${periodPrefix}${period} ${clock}`", template)
        self.assertIn("/api/proxy/scores/wc/today?tz=${timezone}&fresh=1", template)
        self.assertIn("function resolvedOffseasonChampion", template)
        self.assertIn("league-empty-champion-row", template)
        self.assertIn("findLeagueTeamData(champion.abbreviation, leagueUpper)", template)
        self.assertIn("function cricketInningsText", template)
        self.assertIn("cricket_home_runs", template)
        self.assertIn("home_shootout_score", template)
        self.assertIn("visitor_shootout_score", template)
        self.assertIn("box_score", template)
        self.assertIn("game.result", template)

    def test_league_page_has_nfl_grid_and_mls_record_fallback(self):
        template = (PROJECT_ROOT / "templates/league_page.html").read_text()
        app_source = (PROJECT_ROOT / "app.py").read_text()

        self.assertIn("nfl_division_grid", template)
        self.assertIn("{{ slot.conference }}", template)
        self.assertIn("{{ slot.division }}", template)
        self.assertIn("[('AFC', 'East'), ('AFC', 'West'), ('NFC', 'East'), ('NFC', 'West')]", app_source)
        self.assertIn("[('AFC', 'North'), ('AFC', 'South'), ('NFC', 'North'), ('NFC', 'South')]", app_source)
        self.assertIn("{{ team.team_wins }}W-{{ team.team_ties or 0 }}D-{{ team.team_losses }}L", template)

    def test_league_page_expands_mlb_league_names_and_enriches_mlc_schedule_records(self):
        template = (PROJECT_ROOT / "templates/league_page.html").read_text()

        self.assertIn("American League", template)
        self.assertIn("National League", template)
        self.assertIn("fetch('/api/mlc/team-records')", template)
        self.assertIn("league-schedule-record", template)
        self.assertIn("formatTimedPeriodStatus", template)

    def test_league_page_standings_records_and_readable_card_lines(self):
        template = (PROJECT_ROOT / "templates/league_page.html").read_text()
        app_source = (PROJECT_ROOT / "app.py").read_text()
        contrast_script = (PROJECT_ROOT / "static/js/contrast.js").read_text()

        self.assertIn("def _fetch_league_standings", app_source)
        self.assertIn("league_name == 'NBA'", app_source)
        self.assertIn("league_name == 'NHL'", app_source)
        self.assertIn("Pts {{ team.standings_points", template)
        self.assertIn("class=\"team-record-line\"", template)
        self.assertIn("class=\"stadium-info\"", template)
        self.assertIn("class=\"location-info\"", template)
        self.assertIn(".team-name, .team-record-line, .stadium-info, .location-info", contrast_script)

    def test_event_page_groups_tennis_and_uses_world_cup_empty_copy(self):
        template = (PROJECT_ROOT / "templates/event_league_page.html").read_text()

        self.assertIn("function renderTennisGroups", template)
        self.assertIn("event-league-tournament-banner", template)
        self.assertIn("No matches on", template)
        self.assertIn("event-soccer-ball", template)

    def test_event_page_renders_world_cup_group_standings(self):
        template = (PROJECT_ROOT / "templates/event_league_page.html").read_text()
        css = (PROJECT_ROOT / "static/css/main.css").read_text()

        self.assertIn('id="wc-standings-panel"', template)
        self.assertIn('id="wc-marquee"', template)
        self.assertIn("function worldCupGroupsFromStandings", template)
        self.assertIn("function renderWorldCupStandings", template)
        self.assertIn("function renderWorldCupKnockout", template)
        self.assertIn("function normalizeWorldCupBracket", template)
        self.assertIn("function mergeWorldCupTeams", template)
        self.assertIn("data?.groups", template)
        self.assertIn("data?.teams", template)
        self.assertIn("flatByGroup", template)
        self.assertIn("validWorldCupGroups", template)
        self.assertIn("'ABCDEFGHIJKL'", template)
        self.assertIn("worldCupGroupName(team.group)", template)
        self.assertIn("worldCupGroupName(group.group)", template)
        self.assertIn("/api/proxy/standings/${league}", template)
        for column in ["#</th>", "Team</th>", "W-D-L</th>", "Pts</th>", "Groups A-F", "Groups G-L", "wc-team-badge", "wc-bracket-winner-banner", "wc-bracket-layout"]:
            self.assertIn(column, template)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr))", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", css)
        self.assertIn("grid-template-columns: 1fr", css)
        self.assertIn("WC_TEAM_CODES", template)
        self.assertIn("worldCupTeamCode(team)", template)
        self.assertIn("const teamUrl = teamCode ? `/team/wc/${encodeURIComponent(teamCode)}` : ''", template)
        self.assertIn("wc-team-code-link", template)
        self.assertIn("wc-advancing-team", template)
        self.assertIn("wc-knockout-panel", template)
        self.assertIn("wc-bracket", template)
        self.assertIn("wc-bracket-column", template)
        self.assertIn("wc-bracket-match", template)
        self.assertIn("wc-bracket-connectors", template)
        self.assertIn("fetch('/api/proxy/world-cup/bracket')", template)
        self.assertIn(".wc-team-link", css)
        self.assertIn(".wc-team-code-link", css)
        self.assertIn(".wc-advancing-team", css)
        self.assertIn(".wc-knockout-panel", css)
        self.assertIn(".wc-bracket-column-title", css)
        self.assertIn(".wc-bracket-match", css)

    @patch("app.set_cached_response")
    @patch("app.get_cached_response", return_value=None)
    @patch("app._fetch_api_json")
    def test_world_cup_team_page_uses_standard_code_ball_logo(self, mock_fetch, _mock_cache, _mock_set_cache):
        standings_data = {
            "teams": [
                {
                    "team_name": "Mexico",
                    "abbreviation": "MEX",
                    "group": "A",
                    "group_rank": 1,
                    "matches": 1,
                    "wins": 1,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 2,
                    "goals_against": 0,
                    "goal_difference": 2,
                    "points": 3,
                    "record": "1-0-0",
                },
                {
                    "team_name": "South Korea",
                    "abbreviation": "KOR",
                    "group": "A",
                    "group_rank": 2,
                    "matches": 1,
                    "wins": 1,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 1,
                    "goals_against": 0,
                    "goal_difference": 1,
                    "points": 3,
                    "record": "1-0-0",
                },
                {
                    "team_name": "South Africa",
                    "abbreviation": "RSA",
                    "group": "A",
                    "group_rank": 3,
                    "matches": 1,
                    "wins": 0,
                    "draws": 0,
                    "losses": 1,
                    "goals_for": 0,
                    "goals_against": 1,
                    "goal_difference": -1,
                    "points": 0,
                    "record": "0-0-1",
                },
                {
                    "team_name": "Czech Republic",
                    "abbreviation": "CZE",
                    "group": "A",
                    "group_rank": 4,
                    "matches": 1,
                    "wins": 0,
                    "draws": 0,
                    "losses": 1,
                    "goals_for": 0,
                    "goals_against": 2,
                    "goal_difference": -2,
                    "points": 0,
                    "record": "0-0-1",
                }
            ]
        }
        schedule_games = [
            {
                "game_date": "2026-06-11",
                "game_status": "final",
                "is_final": True,
                "home_team": "South Africa",
                "home_team_abbrev": "RSA",
                "home_score": 2,
                "visitor_team": "Mexico",
                "visitor_team_abbrev": "MEX",
                "visitor_score": 1,
                "game_type": "group_matchday_1",
            },
            {
                "game_date": "2026-06-18",
                "game_status": "scheduled",
                "is_final": False,
                "home_team": "South Korea",
                "home_team_abbrev": "KOR",
                "home_score": None,
                "visitor_team": "South Africa",
                "visitor_team_abbrev": "RSA",
                "visitor_score": None,
                "game_type": "group_matchday_2",
            },
            {
                "game_date": "2026-06-24",
                "game_status": "scheduled",
                "is_final": False,
                "home_team": "South Africa",
                "home_team_abbrev": "RSA",
                "home_score": None,
                "visitor_team": "Czech Republic",
                "visitor_team_abbrev": "CZE",
                "visitor_score": None,
                "game_type": "group_matchday_3",
            },
        ]

        def fake_fetch(path, timeout=15):
            if path == "/api/v1/standings/wc":
                return standings_data
            date = path.split("/api/v1/schedule/wc/", 1)[1].split("?", 1)[0]
            return {"games": [game for game in schedule_games if game["game_date"] == date]}

        mock_fetch.side_effect = fake_fetch

        response = app.test_client().get("/team/wc/rsa")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("South Africa", html)
        self.assertIn("Group A Standings", html)
        for label in ["Games Played", "Wins", "Draws", "Losses", "Goals For", "Goals Against", "Goal Difference", "Points"]:
            self.assertIn(label, html)
        for column in ["GP</th>", "W</th>", "D</th>", "L</th>", "F</th>", "A</th>", "GD</th>", "P</th>"]:
            self.assertIn(column, html)
        self.assertIn("Mexico", html)
        self.assertIn("South Korea", html)
        self.assertIn('class="is-current-team"', html)
        self.assertIn("https://www.splitsp.lat/logos/wc/teamballs/rsa_ball_logo.png", html)
        self.assertIn("3 matches", html)
        self.assertIn("Mexico <span>1 - 2</span> South Africa", html)
        self.assertIn("Czech Republic <span>vs</span> South Africa", html)
        self.assertIn("group matchday 3", html)
        self.assertGreaterEqual(mock_fetch.call_count, 2)

    @patch("app._fetch_api_json")
    def test_proxy_standings_exposes_world_cup_groups(self, mock_fetch):
        mock_fetch.return_value = {
            "groups": [
                {
                    "group": "A",
                    "teams": [
                        {
                            "group_rank": 1,
                            "team_name": "Mexico",
                            "abbreviation": "MEX",
                            "matches": 1,
                            "wins": 1,
                            "draws": 0,
                            "losses": 0,
                            "goals_for": 2,
                            "goals_against": 0,
                            "goal_difference": 2,
                            "points": 3,
                            "record": "1-0-0",
                        }
                    ],
                }
            ],
            "teams": [],
            "knockout_bracket": {"sides": {"left": [], "right": []}},
        }
        with patch("app.get_cached_response", return_value=None) as mock_cache, patch("app.set_cached_response") as mock_set_cache:
            response = app.test_client().get("/api/proxy/standings/wc")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["groups"][0]["group"], "A")
        self.assertEqual(data["groups"][0]["teams"][0]["team_name"], "Mexico")
        mock_fetch.assert_called_once_with("/api/v1/standings/wc", timeout=15)
        mock_cache.assert_called_once_with("standings:wc:groups-v3", "schedule")
        self.assertEqual(mock_set_cache.call_args.args[0], "standings:wc:groups-v3")

    @patch("app._fetch_api_json")
    def test_proxy_standings_normalizes_swapped_world_cup_groups(self, mock_fetch):
        mock_fetch.return_value = {
            "groups": [
                {
                    "group": "C",
                    "teams": [
                        {"group_rank": 1, "team_name": "United States", "abbreviation": "USA", "points": 4},
                        {"group_rank": 2, "team_name": "Paraguay", "abbreviation": "PAR", "points": 3},
                        {"group_rank": 3, "team_name": "Australia", "abbreviation": "AUS", "points": 1},
                        {"group_rank": 4, "team_name": "Turkey", "abbreviation": "TUR", "points": 0},
                    ],
                },
                {
                    "group": "D",
                    "teams": [
                        {"group_rank": 1, "team_name": "Brazil", "abbreviation": "BRA", "points": 6},
                        {"group_rank": 2, "team_name": "Morocco", "abbreviation": "MAR", "points": 3},
                        {"group_rank": 3, "team_name": "Scotland", "abbreviation": "SCO", "points": 1},
                        {"group_rank": 4, "team_name": "Haiti", "abbreviation": "HAI", "points": 1},
                    ],
                },
                {
                    "group": "K",
                    "teams": [
                        {"group_rank": 1, "team_name": "England", "abbreviation": "ENG", "points": 4},
                        {"group_rank": 2, "team_name": "Croatia", "abbreviation": "CRO", "points": 3},
                        {"group_rank": 3, "team_name": "Ghana", "abbreviation": "GHA", "points": 1},
                        {"group_rank": 4, "team_name": "Panama", "abbreviation": "PAN", "points": 0},
                    ],
                },
                {
                    "group": "L",
                    "teams": [
                        {"group_rank": 1, "team_name": "Portugal", "abbreviation": "POR", "points": 4},
                        {"group_rank": 2, "team_name": "Colombia", "abbreviation": "COL", "points": 4},
                        {"group_rank": 3, "team_name": "DR Congo", "abbreviation": "COD", "points": 1},
                        {"group_rank": 4, "team_name": "Uzbekistan", "abbreviation": "UZB", "points": 0},
                    ],
                },
            ],
            "teams": [],
        }
        with patch("app.get_cached_response", return_value=None), patch("app.set_cached_response"):
            response = app.test_client().get("/api/proxy/standings/wc")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        groups = {group["group"]: [team["abbreviation"] for team in group["teams"]] for group in data["groups"]}
        self.assertEqual(groups["C"], ["BRA", "MAR", "SCO", "HAI"])
        self.assertEqual(groups["D"], ["USA", "PAR", "AUS", "TUR"])
        self.assertEqual(groups["K"], ["POR", "COL", "COD", "UZB"])
        self.assertEqual(groups["L"], ["ENG", "CRO", "GHA", "PAN"])

    @patch("app._fetch_api_json")
    def test_proxy_world_cup_bracket_exposes_knockout_bracket(self, mock_fetch):
        mock_fetch.return_value = {
            "sport": "wc",
            "knockout_bracket": {
                "format": "round_of_32",
                "rounds": [
                    {
                        "name": "Round of 32",
                        "matches": [
                            {
                                "match_number": 1,
                                "home_team": "Mexico",
                                "away_team": "Argentina",
                                "game_id": "wc-k1",
                                "game_status": "scheduled",
                            }
                        ],
                    }
                ],
            },
            "available": True,
        }

        with patch("app.get_cached_response", return_value=None) as mock_cache, patch("app.set_cached_response") as mock_set_cache:
            response = app.test_client().get("/api/proxy/world-cup/bracket")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["knockout_bracket"]["format"], "round_of_32")
        self.assertEqual(data["knockout_bracket"]["rounds"][0]["name"], "Round of 32")
        mock_fetch.assert_called_once_with("/api/v1/world-cup/bracket", timeout=15)
        mock_cache.assert_called_once_with("world_cup_bracket", "schedule")
        self.assertEqual(mock_set_cache.call_args.args[0], "world_cup_bracket")

    @patch("app._fetch_api_json")
    def test_proxy_tour_de_france_exposes_bundle(self, mock_fetch):
        mock_fetch.return_value = {
            "race": "Tour de France",
            "year": 2026,
            "current_stage": {"stage": {"stage_number": 3, "stage_name": "Valenciennes"}},
            "stages": [],
            "latest_classifications": {"gc": []},
            "teams": [],
            "riders": [],
            "meta": {"source_updated_at": "2026-07-07T18:00:00Z"},
        }

        with patch("app.get_cached_response", return_value=None) as mock_cache, patch("app.set_cached_response") as mock_set_cache:
            response = app.test_client().get("/api/proxy/cycling/tour-de-france/2026")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["race"], "Tour de France")
        self.assertEqual(data["year"], 2026)
        mock_fetch.assert_called_once_with("/api/v1/cycling/tour-de-france/2026", timeout=20)
        mock_cache.assert_called_once_with("cycling_tour_de_france:2026", "schedule")
        self.assertEqual(mock_set_cache.call_args.args[0], "cycling_tour_de_france:2026")

    @patch("app._fetch_api_json")
    def test_proxy_vuelta_exposes_bundle_from_la_vuelta_feed(self, mock_fetch):
        mock_fetch.return_value = {
            "race": "La Vuelta a España",
            "year": 2026,
            "stages": [],
            "latest_classifications": {"gc": []},
            "teams": [],
            "riders": [],
            "meta": {"source_updated_at": "2026-07-07T18:00:00Z"},
        }

        with patch("app.get_cached_response", return_value=None) as mock_cache, patch("app.set_cached_response") as mock_set_cache:
            response = app.test_client().get("/api/proxy/cycling/vuelta/2026")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["race"], "La Vuelta a España")
        self.assertEqual(data["year"], 2026)
        mock_fetch.assert_called_once_with("/api/v1/cycling/la-vuelta/2026", timeout=20)
        mock_cache.assert_called_once_with("cycling_vuelta:2026", "schedule")
        self.assertEqual(mock_set_cache.call_args.args[0], "cycling_vuelta:2026")

    @patch("app._fetch_api_json")
    def test_proxy_tour_de_france_exposes_stage_results(self, mock_fetch):
        mock_fetch.return_value = {
            "race": "Tour de France",
            "year": 2026,
            "stage_number": 4,
            "stage_results": [{"rank": 1, "rider_name": "Mads Pedersen"}],
            "classification_rows": [{"classification_type": "stage", "rank": 1, "rider_name": "Mads Pedersen"}],
            "meta": {"source_updated_at": "2026-07-07T18:00:00Z"},
        }

        with patch("app.get_cached_response", return_value=None) as mock_cache, patch("app.set_cached_response") as mock_set_cache:
            response = app.test_client().get("/api/proxy/cycling/tour-de-france/2026/stages/4")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["stage_number"], 4)
        self.assertEqual(data["stage_results"][0]["rider_name"], "Mads Pedersen")
        mock_fetch.assert_called_once_with("/api/v1/cycling/tour-de-france/2026/stages/4", timeout=20)
        mock_cache.assert_called_once_with("cycling_tour_de_france:2026:stage:4", "schedule")
        self.assertEqual(mock_set_cache.call_args.args[0], "cycling_tour_de_france:2026:stage:4")

    def test_tour_de_france_template_formats_rider_names_and_three_column_boards(self):
        template = (PROJECT_ROOT / "templates/tour_de_france_page.html").read_text()
        css = (PROJECT_ROOT / "static/css/main.css").read_text()

        for snippet in [
            "function slugToFullName(slug)",
            "function buildRiderLookup(data)",
            "function classificationValue(row, boardType, index)",
            "function riderSlugFromUrl(value)",
            "function riderDisplayName(name, slug = '', url = '')",
            "function renderRiderName(name, options = {})",
            "function isPlaceholderStageResult(row)",
            "function stageResultRows(stageDetail)",
            "function stageTimeText(stage, schedule, timeValue)",
            "classification_rows",
            "function renderStageResults(stageDetail)",
            "let TOUR_SELECTED_STAGE_KEY = null;",
            "const TOUR_API_SLUG =",
            "document.getElementById('tdf-stages-panel').addEventListener('click'",
            "King of the Mountains (KOM)",
            "buildRiderLookup(data);",
            "function stageRaceType(stage, schedule)",
            "function stageWindowText(stage, schedule)",
            "function stageStatusText(stage, schedule)",
            "id=\"tdf-timezone-select\"",
            "function zonedStageDateTime(dateValue, timeValue, sourceTimeZone = 'Europe/Paris')",
            "function tourDisplayTimeZone()",
        ]:
            self.assertIn(snippet, template)

        self.assertLess(
            template.index("if (TOUR_SELECTED_STAGE_KEY)"),
            template.index("const current = TOUR_PAYLOAD?.current_stage || {}"),
        )

        for snippet in [
            ".tdf-board-grid {",
            "grid-template-columns: repeat(3, minmax(0, 1fr));",
            ".tdf-board-meta",
            ".tdf-rider-link",
            ".tdf-stage-card.is-selected",
        ]:
            self.assertIn(snippet, css)

    def test_homepage_uses_active_event_branding_for_banners(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        for snippet in [
            "const EVENT_BRANDING",
            "function activeEventContext",
            "event-brand-wimbledon",
            "event-brand-roland-garros",
            "event-brand-tour-de-france",
            "event-brand-world-cup",
            "activeEventContext(lower, pickedDate)",
            "activeEventContext(leagueLower, pickedDate)",
        ]:
            self.assertIn(snippet, template)

    def test_world_cup_homepage_team_links_use_team_pages(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn("if (league === 'WC')", template)
        self.assertIn("return code ? `/team/wc/${code}`", template)

    def test_world_cup_and_cycling_rendering_uses_api_contract_fields(self):
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()
        event_template = (PROJECT_ROOT / "templates/event_league_page.html").read_text()

        for snippet in [
            "function renderCyclingStandings(data)",
            "EVENT_MODE === 'world-cup' || EVENT_MODE === 'cycling'",
            "const rank = game.cycling_rank;",
            "GC ${rank}",
            "const worldCupWinner = isWorldCupKnockout ? worldCupWinnerLabel(game) : '';",
            "function wireWorldCupBracketConnectors(root)",
            "wc-bracket-column",
            "wc-bracket-connectors",
            "wc-bracket-winner-banner",
            "wc-bracket-layout",
            "wc-groups-split",
            "wc-team-badge",
            "function worldCupBracketContentScore",
            "function chooseWorldCupBracketSource",
            "function worldCupBracketScoreValue",
            "function worldCupBracketTeamLabel",
            "function worldCupTeamMatchesLabel",
            "wc-bracket-team-score",
            "wc-bracket-team-logo",
            "match?.visitor_team",
            "const visitorScore = Number(worldCupBracketScoreValue(game, 'visitor'));",
            "World Cup Champion",
            "https://splitsp.lat/logos/wc/wc-trophy.png",
            "winner-star.png",
        ]:
            self.assertIn(snippet, event_template)

        for snippet in [
            "const explicitWinner = String(game?.wc_winner || game?.winner || '').trim();",
        ]:
            self.assertIn(snippet, index_template)

    def test_cycling_uses_uci_branding(self):
        index_template = (PROJECT_ROOT / "templates/index.html").read_text()
        event_template = (PROJECT_ROOT / "templates/event_league_page.html").read_text()
        css = (PROJECT_ROOT / "static/css/main.css").read_text()
        app_source = (PROJECT_ROOT / "app.py").read_text()

        self.assertIn("https://www.splitsp.lat/logos/cycling/uci/uci-logo.png", index_template)
        self.assertIn("https://www.splitsp.lat/logos/cycling/uci/uci-logo.png", app_source)
        self.assertIn("https://www.splitsp.lat/logos/cycling/uci/uci-logo-125-years.png", app_source)
        self.assertIn("banner_logo_url", event_template)
        self.assertIn("cycling-anniversary-banner", event_template)
        self.assertIn("tdf-feature-link", event_template)
        self.assertIn("tour_de_france_page", event_template)
        self.assertIn("vuelta_page", event_template)
        self.assertIn("tour_de_france_page", app_source)
        self.assertIn("vuelta_page", app_source)
        self.assertIn("api/proxy/cycling/tour-de-france", app_source)
        self.assertIn("api/proxy/cycling/tour-de-france/<int:year>/stages/<int:stage_number>", app_source)
        self.assertIn("api/proxy/cycling/vuelta", app_source)
        self.assertIn("api/proxy/cycling/vuelta/<int:year>/stages/<int:stage_number>", app_source)
        self.assertIn("cycling-anniversary-banner", css)
        self.assertIn(".tdf-feature-link", css)
        self.assertIn(".tdf-stage-grid", css)
        self.assertIn("wc-bracket-column", css)
        self.assertIn("wc-bracket-connectors", css)
        self.assertIn("wc-bracket-layout", css)
        self.assertIn("wc-bracket-winner-banner", css)
        self.assertIn("wc-groups-split", css)
        self.assertIn("https://www.uci.org/the-uci-celebrates-its-125th-anniversary/7cSGKuFPEiLx1fVHx7YCDe", app_source)

        for snippet in [
            "function cyclingRaceTypeText(game)",
            "function cyclingDistanceText(game)",
            "function cyclingStageTimeText(dateValue, timeValue)",
            "function cyclingStageWindowText(game)",
            "function zonedStageDateTime(dateValue, timeValue, sourceTimeZone = 'Europe/Paris')",
            "function timezoneValueToIana(value)",
            "images/branding/favicon-32x32.png",
            "images/branding/apple-touch-icon.png",
        ]:
            self.assertIn(snippet, index_template)
            self.assertIn(snippet, event_template)

    def test_shared_header_dropdown_stays_above_page_content(self):
        css = (PROJECT_ROOT / "static/css/main.css").read_text()

        self.assertIn(".navbar", css)
        self.assertIn("z-index: 6000", css)
        self.assertIn("overflow: visible", css)
        self.assertIn(".navbar-nav .dropdown-menu", css)
        self.assertIn("z-index: 6200", css)

    def test_homepage_groups_tennis_and_skips_team_logos_for_players(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn("function homepageTennisTournamentName", template)
        self.assertIn("homepage-tennis-tournament-divider", template)
        self.assertIn("leagueName === 'ATP' || leagueName === 'WTA'", template)
        self.assertIn("function tennisPlayerRank(side)", template)
        self.assertIn("function tennisPlayerLabel(side)", template)
        self.assertIn("const visitorTeamData = (isTennis || isWorldCup) ? null : findTeamData", template)
        self.assertIn("const visitorLogo = isTennis ? ''", template)
        self.assertIn("${isTennis ? '' : `", template)

    def test_homepage_offseason_champion_banners_are_overridden_for_nba_and_nhl(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn("teamName: 'Knicks'", template)
        self.assertIn("teamName: 'Hurricanes'", template)
        self.assertIn("suffix: 'won the championship'", template)
        self.assertIn("suffix: 'won the Stanley Cup'", template)
        self.assertIn("/static/images/logos/nba/new_york_knicks_logo.png", template)
        self.assertIn("/static/images/logos/nhl/carolina_hurricanes_logo.png", template)
        self.assertIn("function resolvedOffseasonChampion", template)
        self.assertIn("const logo = eventContext?.asset || LEAGUE_LOGOS[upper] || ''", template)
        self.assertIn("league-empty-champion-logo", template)

    def test_homepage_cricket_score_renderer_accepts_native_innings_fields(self):
        template = (PROJECT_ROOT / "templates/index.html").read_text()

        self.assertIn("function cricketInningsText", template)
        self.assertIn("function formatCricketOvers", template)
        self.assertIn("function worldCupPenaltyText", template)
        self.assertIn("function worldCupCloneTeamRecords", template)
        self.assertIn("function worldCupWinnerSide", template)
        self.assertIn("game._wcTournamentRecord", template)
        self.assertIn("cricket_home_runs", template)
        self.assertIn("cricket_away_overs", template)
        self.assertIn("home_shootout_score", template)
        self.assertIn("visitor_shootout_score", template)

    @patch("app._should_skip_live_api_fetch", return_value=False)
    @patch("app.requests.get")
    def test_fetch_nfl_standings_keys_by_name_and_abbreviation(self, mock_get, _mock_skip):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "teams": [
                {"team_name": "Buffalo Bills", "abbreviation": "BUF", "wins": "13", "losses": "4", "ties": "0"}
            ]
        }
        mock_get.return_value = response

        records = _fetch_nfl_standings("https://api.example.test")

        self.assertEqual(records["Buffalo Bills"], {"wins": 13, "losses": 4, "ties": 0})
        self.assertEqual(records["BUF"], {"wins": 13, "losses": 4, "ties": 0})

    @patch("app._fetch_api_json")
    @patch("app.requests.get")
    def test_mlc_season_info_falls_back_to_schedule_and_standings_when_endpoint_is_stale(self, mock_get, mock_fetch_api_json):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "year": 2026,
            "current_phase": "Off Season",
            "season_types": [],
        }
        mock_get.return_value = response
        mock_fetch_api_json.side_effect = [
            {"games": [{"game_id": "mlc-1"}]},
            {"teams": [{"team_name": "Texas Super Kings", "matches": 1, "wins": 1, "losses": 0}]},
        ]

        data = app.test_client().get("/api/season-info/MLC").get_json()

        self.assertEqual(data["current_phase"], "Regular Season")
        self.assertEqual(data["season_types"][0]["display"], "Regular Season underway")

    def test_nfl_live_fetches_are_skipped_during_offseason_today(self):
        self.assertTrue(_should_skip_live_api_fetch("NFL", "today"))
        self.assertFalse(_should_skip_live_api_fetch("NFL", "2026-09-10"))


class TestDatabaseAndConfig(unittest.TestCase):
    def test_database_connection_config_has_required_keys(self):
        for key in ["host", "database", "user", "password"]:
            self.assertIn(key, DB_CONFIG)

    @patch("psycopg2.connect")
    def test_database_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        self.assertEqual(get_db_connection(), mock_conn)
        mock_connect.assert_called_once()

    @patch("psycopg2.connect")
    def test_database_connection_failure(self, mock_connect):
        mock_connect.side_effect = psycopg2.Error("Connection failed")

        self.assertIsNone(get_db_connection())

    def test_logo_mapping_is_dictionary(self):
        self.assertIsInstance(LOGO_MAPPING, dict)

    def test_required_project_files_exist(self):
        required_files = [
            "app.py",
            "requirements.txt",
            "static/css/main.css",
            "templates/index.html",
            "templates/shared_header.html",
            "templates/shared_footer.html",
            ".github/workflows/test-and-deploy.yml",
            "ansible/playbooks/deploy.yml",
        ]

        for file_path in required_files:
            self.assertTrue((PROJECT_ROOT / file_path).exists(), file_path)

    def test_current_deployment_group_vars(self):
        dev_config = (PROJECT_ROOT / "ansible/group_vars/dev.yml").read_text()
        prod_config = (PROJECT_ROOT / "ansible/group_vars/prod.yml").read_text()

        self.assertIn('service_name: "sportspuff-v6-dev"', dev_config)
        self.assertIn("app_port: 34081", dev_config)
        self.assertIn('branch: "dev"', dev_config)
        self.assertIn('service_name: "sportspuff-v6-prod"', prod_config)
        self.assertIn("app_port: 34080", prod_config)
        self.assertIn('branch: "main"', prod_config)
        env_template = (PROJECT_ROOT / "ansible/roles/sportspuff-app/templates/.env.j2").read_text()
        self.assertIn("SPORTSPUFF_DEPLOYMENT_TAG", env_template)
        self.assertIn("SPORTSPUFF_DEPLOYMENT_RUN_URL", env_template)


if __name__ == "__main__":
    unittest.main()
