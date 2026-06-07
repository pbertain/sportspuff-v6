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
    _normalize_timezone,
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

    def test_index_demo_mode_loads_with_theme_switcher(self):
        with patch("app.get_db_connection", return_value=None):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Database Not Available", response.data)
        self.assertIn(b'id="tournament-theme-select"', response.data)
        self.assertIn(b"static/js/tournament-theme.js", response.data)
        self.assertIn(b"All 12 leagues", response.data)

    def test_api_docs_page_loads(self):
        response = self.client.get("/api")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"API Endpoints", response.data)
        self.assertIn(b"/api/v1/teams", response.data)

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
        with patch("app.get_cached_response", return_value=None), patch("app._refresh_cache_async") as refresh:
            response = self.client.get("/api/proxy/all-scores/today?tz=pst")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("wc", data)
        self.assertIn("cycling", data)
        refresh.assert_called_once()


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

    def test_shared_header_exposes_expected_theme_options(self):
        header = (PROJECT_ROOT / "templates/shared_header.html").read_text()

        for theme in ["atp", "wta", "wimbledon", "roland-garros", "us-open", "australian-open"]:
            self.assertIn(f'value="{theme}"', header)


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


if __name__ == "__main__":
    unittest.main()
