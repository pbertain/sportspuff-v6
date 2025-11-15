#!/usr/bin/env python3
"""
Cache warming script for Sportspuff v6
Pre-populates the cache by calling proxy endpoints for all leagues
This ensures the cache is always warm before users hit it
"""

import os
import sys
import requests
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Leagues to warm cache for
LEAGUES = ['nba', 'nhl', 'nfl', 'mlb', 'mls', 'wnba']
TIMEZONES = ['pst', 'est', 'cst', 'mst']  # Common timezones

# Base URL for the Flask app (running locally)
# Default to dev port, but can be overridden via environment variable
# For prod, set CACHE_WARMER_BASE_URL=http://localhost:34180
BASE_URL = os.getenv('CACHE_WARMER_BASE_URL', 'http://localhost:34181')

def warm_cache():
    """Warm the cache by calling proxy endpoints"""
    logger.info("Starting cache warming process")
    
    success_count = 0
    error_count = 0
    
    for league in LEAGUES:
        for tz in TIMEZONES:
            # Warm schedule cache
            try:
                schedule_url = f"{BASE_URL}/api/proxy/schedule/{league}/today?tz={tz}"
                logger.info(f"Warming schedule cache: {league} ({tz})")
                response = requests.get(schedule_url, timeout=30)
                if response.status_code == 200:
                    logger.info(f"✓ Schedule cache warmed for {league} ({tz})")
                    success_count += 1
                else:
                    logger.warning(f"✗ Schedule cache failed for {league} ({tz}): {response.status_code}")
                    error_count += 1
            except Exception as e:
                logger.error(f"✗ Error warming schedule cache for {league} ({tz}): {e}")
                error_count += 1
            
            # Warm scores cache
            try:
                scores_url = f"{BASE_URL}/api/proxy/scores/{league}/today?tz={tz}"
                logger.info(f"Warming scores cache: {league} ({tz})")
                response = requests.get(scores_url, timeout=30)
                if response.status_code == 200:
                    logger.info(f"✓ Scores cache warmed for {league} ({tz})")
                    success_count += 1
                else:
                    logger.warning(f"✗ Scores cache failed for {league} ({tz}): {response.status_code}")
                    error_count += 1
            except Exception as e:
                logger.error(f"✗ Error warming scores cache for {league} ({tz}): {e}")
                error_count += 1
    
    logger.info(f"Cache warming complete: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    try:
        success = warm_cache()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error in cache warming: {e}", exc_info=True)
        sys.exit(1)

