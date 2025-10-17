#!/usr/bin/env python3
"""
Test runner for Sportspuff v6
Runs all tests and provides deployment readiness report
"""

import unittest
import sys
import os
import subprocess
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_flask_tests():
    """Run Flask application tests"""
    print("🧪 Running Flask Application Tests...")
    
    # Set test environment
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DB_NAME'] = 'sportspuff_v6_test'
    
    # Import and run tests
    from tests.test_app import run_tests
    return run_tests()

def run_database_tests():
    """Run database connectivity tests"""
    print("🗄️  Running Database Tests...")
    
    try:
        import psycopg2
        from app import DB_CONFIG
        
        # Test database connection
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Test basic queries
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def run_deployment_tests():
    """Run deployment readiness tests"""
    print("🚀 Running Deployment Readiness Tests...")
    
    tests_passed = 0
    total_tests = 0
    
    # Test Ansible files
    ansible_files = [
        'ansible/inventory',
        'ansible/playbooks/deploy.yml',
        'ansible/group_vars/all.yml',
        'ansible/group_vars/dev.yml',
        'ansible/group_vars/prod.yml'
    ]
    
    for file_path in ansible_files:
        total_tests += 1
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
            tests_passed += 1
        else:
            print(f"❌ {file_path} missing")
    
    # Test GitHub workflows
    workflow_files = [
        '.github/workflows/deploy-dev.yml',
        '.github/workflows/deploy-prod.yml'
    ]
    
    for file_path in workflow_files:
        total_tests += 1
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
            tests_passed += 1
        else:
            print(f"❌ {file_path} missing")
    
    # Test required Python files
    python_files = [
        'app.py',
        'import_data.py',
        'create_logo_mapping.py',
        'test_setup.py'
    ]
    
    for file_path in python_files:
        total_tests += 1
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
            tests_passed += 1
        else:
            print(f"❌ {file_path} missing")
    
    return tests_passed, total_tests

def run_static_analysis():
    """Run static code analysis"""
    print("🔍 Running Static Analysis...")
    
    try:
        # Check for common Python issues
        result = subprocess.run([
            'python', '-m', 'py_compile', 'app.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ app.py compiles successfully")
            return True
        else:
            print(f"❌ app.py compilation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Static analysis failed: {e}")
        return False

def generate_deployment_report():
    """Generate comprehensive deployment readiness report"""
    print("\n" + "="*60)
    print("📊 SPORTSPUFF V6 DEPLOYMENT READINESS REPORT")
    print("="*60)
    
    # Run all test suites
    flask_success = run_flask_tests()
    db_success = run_database_tests()
    static_success = run_static_analysis()
    
    # Run deployment tests
    deployment_passed, deployment_total = run_deployment_tests()
    deployment_success = deployment_passed == deployment_total
    
    # Calculate overall score
    total_tests = 4  # flask, db, static, deployment
    passed_tests = sum([flask_success, db_success, static_success, deployment_success])
    score = (passed_tests / total_tests) * 100
    
    print(f"\n📈 DEPLOYMENT READINESS SCORE: {score:.1f}%")
    print(f"✅ Tests Passed: {passed_tests}/{total_tests}")
    
    # Detailed results
    print("\n📋 DETAILED RESULTS:")
    print(f"  Flask Application: {'✅ PASS' if flask_success else '❌ FAIL'}")
    print(f"  Database Connection: {'✅ PASS' if db_success else '❌ FAIL'}")
    print(f"  Static Analysis: {'✅ PASS' if static_success else '❌ FAIL'}")
    print(f"  Deployment Files: {'✅ PASS' if deployment_success else '❌ FAIL'}")
    print(f"  Deployment Files: {deployment_passed}/{deployment_total} files present")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if score == 100:
        print("  🎉 All tests passed! Ready for deployment.")
    else:
        if not flask_success:
            print("  🔧 Fix Flask application issues before deployment")
        if not db_success:
            print("  🔧 Verify database configuration and connectivity")
        if not static_success:
            print("  🔧 Fix code compilation issues")
        if not deployment_success:
            print("  🔧 Ensure all deployment files are present")
    
    print("\n🚀 DEPLOYMENT COMMANDS:")
    print("  Manual deployment:")
    print("    ./deploy.sh dev    # Deploy to development")
    print("    ./deploy.sh prod   # Deploy to production")
    print("  Automatic deployment:")
    print("    git push origin dev    # Auto-deploy to dev")
    print("    git push origin main   # Auto-deploy to prod")
    
    return score == 100

def main():
    """Main test runner"""
    print("🏟️  Sportspuff v6 Test Suite")
    print("="*40)
    
    # Change to project directory
    os.chdir(project_root)
    
    # Run all tests
    ready_for_deployment = generate_deployment_report()
    
    # Exit with appropriate code
    sys.exit(0 if ready_for_deployment else 1)

if __name__ == '__main__':
    main()
