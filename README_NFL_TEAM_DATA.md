# NFL Team Data Updater

This script (`fetch_nfl_team_data.py`) fetches NFL team data from the RapidAPI and updates the database with:
- `external_team_id` (from API's `teamID`)
- Team records: Wins-Losses-Ties (W-L-T)
- Matches teams using `teamCity + teamName` with database `real_team_name`

## Execution Options

### Option 1: Manual Execution (Recommended for Testing)

Run the script manually when needed:

```bash
# On the server
cd /opt/sportspuff-v6-prod  # or /opt/sportspuff-v6-dev
source venv/bin/activate
python fetch_nfl_team_data.py
```

Or from your local machine (if you have database access):

```bash
python3 fetch_nfl_team_data.py
```

### Option 2: Automated via Systemd Timer (Recommended for Production)

The script is configured to run automatically via systemd timer. It will:
- Run daily at 2:00 AM (after games typically finish)
- Run on system boot (with 5 minute delay)
- Randomize start time within 30 minutes to avoid API rate limits

**Setup:**
The systemd service and timer are automatically deployed via Ansible. After deployment, you can manage them manually:

```bash
# Check timer status
sudo systemctl status nfl-team-data-updater.timer

# Check service status (last run)
sudo systemctl status nfl-team-data-updater.service

# View logs
sudo journalctl -u nfl-team-data-updater.service -n 50

# Manually trigger a run
sudo systemctl start nfl-team-data-updater.service

# Enable/disable timer
sudo systemctl enable nfl-team-data-updater.timer
sudo systemctl disable nfl-team-data-updater.timer
```

### Option 3: Cron Job (Alternative)

If you prefer cron over systemd, add to crontab:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2:00 AM
0 2 * * * cd /opt/sportspuff-v6-prod && /opt/sportspuff-v6-prod/venv/bin/python /opt/sportspuff-v6-prod/fetch_nfl_team_data.py >> /var/log/nfl-team-data-updater.log 2>&1
```

## Environment Variables

The script uses these environment variables (from `.env` file):

- `RAPIDAPI_KEY`: Your RapidAPI key (defaults to provided key)
- `RAPIDAPI_HOST`: API host (defaults to `tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com`)
- `NFL_API_URL`: Optional custom API URL (defaults to `getNFLDFS` endpoint)
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`: Database connection settings

## How It Works

1. **Fetches team data** from RapidAPI `getNFLDFS` endpoint
2. **Extracts unique teams** from DFS player data
3. **Maps abbreviations** to full team names (e.g., "PHI" → "Philadelphia Eagles")
4. **Attempts to fetch records** from standings/teams endpoints (if available)
5. **Matches teams** with database using `real_team_name`
6. **Updates database** with `external_team_id` and W-L-T records

## Troubleshooting

### Script fails to match teams
- Check that `real_team_name` in database matches format: "City Name" (e.g., "Philadelphia Eagles")
- Review logs for unmatched teams: `sudo journalctl -u nfl-team-data-updater.service`

### Records show 0-0-0
- The API endpoint may not provide W-L-T records in the DFS response
- The script will attempt to fetch from alternative endpoints (`getNFLStandings`, `getNFLTeams`, etc.)
- If no records are found, they default to 0-0-0 and can be updated later

### API rate limits
- The timer includes a 30-minute randomization delay to avoid rate limits
- If you hit rate limits, increase the delay or reduce frequency

## Current Status

- ✅ Script created and ready
- ✅ Systemd service/timer templates created
- ✅ Ansible deployment tasks added
- ⏳ **Not yet deployed** - will be set up on next Ansible deployment
- ⏳ **Manual run recommended first** to test and verify

## Next Steps

1. **Test manually** on dev environment first
2. **Verify** that teams are matched correctly
3. **Check** that `external_team_id` and records are populated
4. **Deploy** via Ansible to enable automatic daily updates

