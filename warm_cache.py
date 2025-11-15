#!/usr/bin/env python3
"""
Cache warming script for Sportspuff v6
Pre-populates the cache by calling proxy endpoints for all leagues
This ensures the cache is always warm before users hit it

This script is called by systemd timer:
- Every minute during game hours (6 PM - 2 AM)
- Every 5 minutes during off-hours (2 AM - 6 PM)
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
    # Check current hour to determine if we're in game hours
    current_hour = datetime.now(timezone.utc).hour
    is_game_hours = (current_hour >= 18) or (current_hour < 2)  # 6 PM - 2 AM UTC
    
    # During off-hours, only run every 5 minutes to reduce API calls
    # Check if we should skip this run (only run on :00, :05, :10, :15, etc.)
    if not is_game_hours:
        current_minute = datetime.now(timezone.utc).minute
        if current_minute % 5 != 0:
            logger.debug(f"Skipping cache warm (off-hours, minute {current_minute} not divisible by 5)")
            return True  # Exit successfully, just skip this run
    
    logger.info(f"Starting cache warming process (game hours: {is_game_hours})")
    
    success_count = 0
    error_count = 0
    
    # During game hours, prioritize scores (they change frequently)
    # During off-hours, prioritize schedules (scores are less likely to change)
    if is_game_hours:
        logger.info("Game hours detected - warming scores more frequently")
        # Warm scores first (most important during games)
        for league in LEAGUES:
            for tz in TIMEZONES:
                try:
                    scores_url = f"{BASE_URL}/api/proxy/scores/{league}/today?tz={tz}"
                    logger.debug(f"Warming scores cache: {league} ({tz})")
                    response = requests.get(scores_url, timeout=30)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        logger.warning(f"Scores cache failed for {league} ({tz}): {response.status_code}")
                        error_count += 1
                except Exception as e:
                    logger.error(f"Error warming scores cache for {league} ({tz}): {e}")
                    error_count += 1
                
                # Also warm schedule (less frequently updated but still needed)
                try:
                    schedule_url = f"{BASE_URL}/api/proxy/schedule/{league}/today?tz={tz}"
                    logger.debug(f"Warming schedule cache: {league} ({tz})")
                    response = requests.get(schedule_url, timeout=30)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        logger.warning(f"Schedule cache failed for {league} ({tz}): {response.status_code}")
                        error_count += 1
                except Exception as e:
                    logger.error(f"Error warming schedule cache for {league} ({tz}): {e}")
                    error_count += 1
    else:
        logger.info("Off-hours detected - warming schedules (scores less critical)")
        # During off-hours, focus on schedules (scores don't change much)
        for league in LEAGUES:
            for tz in TIMEZONES:
                try:
                    schedule_url = f"{BASE_URL}/api/proxy/schedule/{league}/today?tz={tz}"
                    logger.debug(f"Warming schedule cache: {league} ({tz})")
                    response = requests.get(schedule_url, timeout=30)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        logger.warning(f"Schedule cache failed for {league} ({tz}): {response.status_code}")
                        error_count += 1
                except Exception as e:
                    logger.error(f"Error warming schedule cache for {league} ({tz}): {e}")
                    error_count += 1
                
                # Still warm scores, but less critical
                try:
                    scores_url = f"{BASE_URL}/api/proxy/scores/{league}/today?tz={tz}"
                    logger.debug(f"Warming scores cache: {league} ({tz})")
                    response = requests.get(scores_url, timeout=30)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        logger.warning(f"Scores cache failed for {league} ({tz}): {response.status_code}")
                        error_count += 1
                except Exception as e:
                    logger.error(f"Error warming scores cache for {league} ({tz}): {e}")
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

