#!/usr/bin/env python3
"""
Unit tests for Sportspuff v6
Tests Flask application, database operations, and deployment readiness
"""

import unittest
import os
import sys
import tempfile
import json
from unittest.mock import patch, MagicMock
import psycopg2
from psycopg2.extras import RealDictCursor

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app
from app import app, get_db_connection, LOGO_MAPPING

class TestFlaskApp(unittest.TestCase):
    """Test Flask application functionality"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_index_page_loads(self):
        """Test that the index page loads successfully"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchone.return_value = {'count': 10}
            mock_cursor.fetchall.return_value = [{'league': 'nfl', 'count': 5}]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Sportspuff v6', response.data)
    
    def test_teams_page_loads(self):
        """Test that the teams page loads successfully"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchone.return_value = {'count': 10}
            mock_cursor.fetchall.return_value = [
                {'team_id': 1, 'real_team_name': 'Test Team', 'league': 'nfl', 
                 'city_name': 'Test City', 'state_name': 'TS', 'full_stadium_name': 'Test Stadium',
                 'stadium_city': 'Test City', 'stadium_state': 'TS'}
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/teams')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Teams', response.data)
    
    def test_stadiums_page_loads(self):
        """Test that the stadiums page loads successfully"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchone.return_value = {'count': 5}
            mock_cursor.fetchall.return_value = [
                {'stadium_id': 1, 'full_stadium_name': 'Test Stadium', 'city_name': 'Test City',
                 'state_name': 'TS', 'capacity': 50000, 'team_count': 2}
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/stadiums')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Stadiums', response.data)
    
    def test_api_teams_endpoint(self):
        """Test the teams API endpoint"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchall.return_value = [
                {'team_id': 1, 'real_team_name': 'Test Team', 'league': 'nfl',
                 'city_name': 'Test City', 'state_name': 'TS', 'full_stadium_name': 'Test Stadium'}
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/api/teams')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
    
    def test_api_stadiums_endpoint(self):
        """Test the stadiums API endpoint"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchall.return_value = [
                {'stadium_id': 1, 'full_stadium_name': 'Test Stadium', 'capacity': 50000}
            ]
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/api/stadiums')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
    
    def test_team_detail_page(self):
        """Test team detail page"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchone.return_value = {
                'team_id': 1, 'real_team_name': 'Test Team', 'league': 'nfl',
                'city_name': 'Test City', 'state_name': 'TS', 'full_stadium_name': 'Test Stadium',
                'stadium_city': 'Test City', 'stadium_state': 'TS', 'capacity': 50000
            }
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/team/1')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test Team', response.data)
    
    def test_stadium_detail_page(self):
        """Test stadium detail page"""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock(spec=RealDictCursor)
            mock_cursor.fetchone.return_value = {
                'stadium_id': 1, 'full_stadium_name': 'Test Stadium', 'capacity': 50000,
                'city_name': 'Test City', 'state_name': 'TS'
            }
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            response = self.app.get('/stadium/1')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Test Stadium', response.data)
    
    def test_logo_serving(self):
        """Test logo file serving"""
        # Create a temporary logo file for testing
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_file.write(b'fake logo data')
            tmp_path = tmp_file.name
        
        try:
            # Test logo serving
            response = self.app.get(f'/static/logos/test_logo.png')
            # This will return 404 since the file doesn't exist, but the route should work
            self.assertEqual(response.status_code, 404)
        finally:
            # Clean up
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

class TestDatabaseOperations(unittest.TestCase):
    """Test database operations"""
    
    def test_database_connection_config(self):
        """Test database configuration is properly set"""
        from app import DB_CONFIG
        
        self.assertIn('host', DB_CONFIG)
        self.assertIn('database', DB_CONFIG)
        self.assertIn('user', DB_CONFIG)
        self.assertIn('password', DB_CONFIG)
    
    @patch('psycopg2.connect')
    def test_database_connection_success(self, mock_connect):
        """Test successful database connection"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        conn = get_db_connection()
        self.assertEqual(conn, mock_conn)
        mock_connect.assert_called_once()
    
    @patch('psycopg2.connect')
    def test_database_connection_failure(self, mock_connect):
        """Test database connection failure"""
        mock_connect.side_effect = psycopg2.Error("Connection failed")
        
        conn = get_db_connection()
        self.assertIsNone(conn)

class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and validation"""
    
    def test_logo_mapping_structure(self):
        """Test logo mapping has correct structure"""
        # LOGO_MAPPING should be a dict
        self.assertIsInstance(LOGO_MAPPING, dict)
        
        # If there are entries, they should have the correct structure
        for team_id, logo_data in LOGO_MAPPING.items():
            self.assertIn('team_name', logo_data)
            self.assertIn('league', logo_data)
            self.assertIn('logo_path', logo_data)
            self.assertIn('logo_url', logo_data)
    
    def test_required_files_exist(self):
        """Test that required files exist"""
        required_files = [
            'app.py',
            'database_schema.sql',
            'import_data.py',
            'requirements.txt',
            'static/css/main.css'
        ]
        
        for file_path in required_files:
            self.assertTrue(os.path.exists(file_path), f"Required file {file_path} not found")
    
    def test_templates_exist(self):
        """Test that all HTML templates exist"""
        template_dir = 'templates'
        required_templates = [
            'index.html',
            'teams.html',
            'stadiums.html',
            'team_detail.html',
            'stadium_detail.html',
            'error.html'
        ]
        
        for template in required_templates:
            template_path = os.path.join(template_dir, template)
            self.assertTrue(os.path.exists(template_path), f"Template {template} not found")

class TestDeploymentReadiness(unittest.TestCase):
    """Test deployment readiness"""
    
    def test_ansible_files_exist(self):
        """Test that Ansible deployment files exist"""
        ansible_files = [
            'ansible/inventory',
            'ansible/playbooks/deploy.yml',
            'ansible/group_vars/all.yml',
            'ansible/group_vars/dev.yml',
            'ansible/group_vars/prod.yml',
            'ansible/roles/sportspuff-app/tasks/main.yml',
            'ansible/roles/systemd-service/tasks/main.yml'
        ]
        
        for file_path in ansible_files:
            self.assertTrue(os.path.exists(file_path), f"Ansible file {file_path} not found")
    
    def test_github_workflows_exist(self):
        """Test that GitHub Actions workflows exist"""
        workflow_files = [
            '.github/workflows/deploy-dev.yml',
            '.github/workflows/deploy-prod.yml'
        ]
        
        for file_path in workflow_files:
            self.assertTrue(os.path.exists(file_path), f"Workflow file {file_path} not found")
    
    def test_environment_variables_defined(self):
        """Test that environment variables are properly defined"""
        from app import DB_CONFIG
        
        # Check that all required DB config keys are present
        required_keys = ['host', 'database', 'user', 'password']
        for key in required_keys:
            self.assertIn(key, DB_CONFIG)
    
    def test_static_files_structure(self):
        """Test that static files are properly structured"""
        static_dirs = ['static/css']
        
        for static_dir in static_dirs:
            self.assertTrue(os.path.exists(static_dir), f"Static directory {static_dir} not found")
        
        # Check for main CSS file
        self.assertTrue(os.path.exists('static/css/main.css'), "Main CSS file not found")
    
    def test_logos_directory_structure(self):
        """Test that logos directory has proper structure"""
        logos_dir = 'logos'
        expected_league_dirs = ['mlb', 'nfl', 'nba', 'nhl', 'mls', 'wnba']
        
        if os.path.exists(logos_dir):
            for league_dir in expected_league_dirs:
                league_path = os.path.join(logos_dir, league_dir)
                self.assertTrue(os.path.exists(league_path), f"League directory {league_dir} not found")

class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation"""
    
    def test_port_configurations(self):
        """Test that port configurations are correct"""
        # Read dev and prod configurations
        with open('ansible/group_vars/dev.yml', 'r') as f:
            dev_config = f.read()
            self.assertIn('app_port: 34181', dev_config)
        
        with open('ansible/group_vars/prod.yml', 'r') as f:
            prod_config = f.read()
            self.assertIn('app_port: 34180', prod_config)
    
    def test_service_names(self):
        """Test that service names are properly configured"""
        with open('ansible/group_vars/dev.yml', 'r') as f:
            dev_config = f.read()
            self.assertIn('service_name: sportspuff-v6-dev', dev_config)
        
        with open('ansible/group_vars/prod.yml', 'r') as f:
            prod_config = f.read()
            self.assertIn('service_name: sportspuff-v6-prod', prod_config)

def run_tests():
    """Run all tests"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestFlaskApp,
        TestDatabaseOperations,
        TestDataIntegrity,
        TestDeploymentReadiness,
        TestConfigurationValidation
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return success/failure
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
