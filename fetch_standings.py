#!/usr/bin/env python3
"""
Fetch MLB standings from the MLB Stats API and update team records in the database.
Also fetches NHL playoff series records when playoffs are active.
Runs periodically via systemd timer.
"""

import psycopg2
import requests
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'sportspuff_v6'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password')
}

MLB_STANDINGS_URL = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104"

# Map MLB team names to sportspuff real_team_name (handle differences)
MLB_NAME_OVERRIDES = {
    "D-backs": "Arizona Diamondbacks",
    "Athletics": "Oakland Athletics",
}


def fetch_mlb_standings():
    """Fetch MLB standings from the public MLB Stats API and update the database."""
    logger.info("Fetching MLB standings...")
    try:
        response = requests.get(MLB_STANDINGS_URL, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.error(f"Error fetching MLB standings: {e}")
        return False

    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        updated = 0

        for record_group in data.get('records', []):
            for team_record in record_group.get('teamRecords', []):
                team_name = team_record.get('team', {}).get('name', '')
                wins = team_record.get('wins', 0)
                losses = team_record.get('losses', 0)

                if not team_name:
                    continue

                real_name = MLB_NAME_OVERRIDES.get(team_name, team_name)

                cursor.execute("""
                    UPDATE teams SET team_wins = %s, team_losses = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE real_team_name = %s
                    AND league_id = (SELECT league_id FROM leagues WHERE league_name_proper = 'MLB')
                """, (wins, losses, real_name))

                if cursor.rowcount == 0:
                    cursor.execute("""
                        UPDATE teams SET team_wins = %s, team_losses = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE real_team_name ILIKE %s
                        AND league_id = (SELECT league_id FROM leagues WHERE league_name_proper = 'MLB')
                    """, (wins, losses, f"%{team_name}%"))

                if cursor.rowcount > 0:
                    updated += 1

        conn.commit()
        cursor.close()
        logger.info(f"Updated standings for {updated} MLB teams")
        return True

    except Exception as e:
        logger.error(f"Error updating MLB standings in database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    fetch_mlb_standings()
