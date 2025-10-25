# NBA Schedule and Scores Backend

This implementation adds comprehensive NBA schedule and scores functionality to the Sportspuff application using PostgreSQL with full season caching.

## Overview

The NBA backend system provides:
- Complete season schedule import and storage
- Live score updates during games
- RESTful API endpoints for schedule and scores data
- Unified game table design tracking the complete game lifecycle
- Integration with existing teams table via foreign keys

## Database Schema

### NBA Tables Added

1. **`nba_games`** - Unified schedule and scores table
   - `game_id` (TEXT PRIMARY KEY) - Unique game identifier
   - `season` (TEXT NOT NULL) - NBA season (e.g., "2024-25")
   - `game_date` (DATE NOT NULL) - Game date
   - `game_time_est` (TEXT) - Scheduled time
   - `home_team_id` (INTEGER) - FK to teams table
   - `away_team_id` (INTEGER) - FK to teams table
   - `home_score` (INTEGER DEFAULT 0) - NULL until game starts
   - `away_score` (INTEGER DEFAULT 0) - NULL until game starts
   - `game_status` (TEXT DEFAULT 'scheduled') - scheduled/live/final
   - `game_status_text` (TEXT) - Detailed status (e.g., "Q2 5:23")
   - `current_period` (INTEGER) - Quarter/period number
   - `period_time_remaining` (TEXT) - Time left in period
   - `season_type` (TEXT NOT NULL) - preseason/regular_season/playoffs/nba_cup
   - `arena_name` (TEXT) - Arena name
   - `is_nba_cup` (BOOLEAN DEFAULT FALSE) - NBA Cup game flag
   - `winner_team_id` (INTEGER) - NULL until final
   - `created_at`, `updated_at` (TIMESTAMP)

2. **`nba_seasons`** - Season metadata table
   - `season` (TEXT PRIMARY KEY) - NBA season
   - `start_date`, `end_date` (DATE) - Season dates
   - `regular_season_start`, `playoffs_start` (DATE) - Key dates
   - `total_games` (INTEGER) - Total games in season
   - `last_updated` (TIMESTAMP)

### Indexes
- `idx_nba_games_date` - For date-based queries
- `idx_nba_games_season` - For season-based queries
- `idx_nba_games_teams` - For team-based queries
- `idx_nba_games_status` - For status-based queries
- `idx_nba_games_season_type` - For season type queries

## Python Scripts

### 1. `nba_schedule_collector.py`
Enhanced NBA schedule collector with PostgreSQL support:
- Database initialization and schema creation
- Season type detection (preseason, regular, playoffs, NBA Cup)
- Team mapping from NBA API IDs to Sportspuff team IDs
- Game lifecycle tracking from scheduled to final
- Command-line interface for various operations

**Usage:**
```bash
python3 nba_schedule_collector.py --help
python3 nba_schedule_collector.py --season 2024-25 --full-schedule
python3 nba_schedule_collector.py --date 2024-12-15 --scores
python3 nba_schedule_collector.py --stats
```

### 2. `nba_data_importer.py`
NBA data importer for full season schedules:
- Fetches complete season schedule from NBA API
- Maps NBA team IDs to existing Sportspuff team IDs
- Handles duplicate games gracefully
- Updates season metadata
- Supports current season or specific season import

**Usage:**
```bash
python3 nba_data_importer.py --season 2024-25
python3 nba_data_importer.py --current-season
```

### 3. `nba_scores_updater.py`
NBA scores updater for live game data:
- Fetches live scores from NBA API
- Updates game status, scores, period information
- Determines winners when games are final
- Provides live games summary
- Can be run via systemd timer for automatic updates

**Usage:**
```bash
python3 nba_scores_updater.py
python3 nba_scores_updater.py --date 2024-12-15
python3 nba_scores_updater.py --summary
```

## API Endpoints

### 1. `GET /api/nba/schedule`
Get NBA schedule by date or team:
- `?date=YYYY-MM-DD` - Get games for specific date
- `?team_id=X` - Get games for specific team
- No parameters - Get today's games

**Response:**
```json
[
  {
    "game_id": "0022400015",
    "season": "2024-25",
    "game_date": "2024-12-15",
    "game_time_est": "20:00",
    "home_team_id": 1013,
    "away_team_id": 1015,
    "home_score": 110,
    "away_score": 105,
    "game_status": "final",
    "game_status_text": "Final",
    "current_period": 4,
    "season_type": "regular_season",
    "arena_name": "State Farm Arena",
    "home_team_name": "Atlanta Hawks",
    "away_team_name": "Boston Celtics"
  }
]
```

### 2. `GET /api/nba/scores/live`
Get all live NBA games:
- Returns only games with status 'live'
- Includes current scores and period information

### 3. `GET /api/nba/scores/today`
Get today's NBA games and scores:
- Returns all games for current date
- Includes all game statuses (scheduled, live, final)

## Deployment Scripts

### 1. `scripts/setup_nba_db.sh`
Complete NBA database setup:
- Creates NBA tables using schema
- Imports current season data
- Sets up initial configuration

**Usage:**
```bash
./scripts/setup_nba_db.sh
```

### 2. `scripts/update_nba_scores.sh`
NBA scores update script for systemd:
- Updates live scores for today's games
- Deployed automatically via Ansible as systemd service
- Provides logging and error handling

**Usage:**
```bash
./scripts/update_nba_scores.sh
```

**Systemd Timer Setup:**
The NBA scores updater runs automatically via systemd timer (deployed via Ansible):
```bash
# Check timer status
systemctl status nba-scores-updater.timer

# Check service logs
journalctl -u nba-scores-updater.service -f

# Manual timer control
systemctl start nba-scores-updater.timer
systemctl stop nba-scores-updater.timer
systemctl enable nba-scores-updater.timer
```

## Dependencies

Added to `requirements.txt`:
- `requests==2.31.0` - For NBA API calls
- `nba_api==1.2.1` - NBA API library (optional, can use direct API calls)

## Integration Points

1. **Teams Table Integration**: NBA games reference existing teams via `home_team_id` and `away_team_id` foreign keys
2. **Database Connection**: Uses existing PostgreSQL connection pattern from `app.py`
3. **Environment Variables**: Leverages existing `.env` configuration
4. **Flask App**: NBA API endpoints added to existing Flask application

## Team Mapping

The system maps NBA API team IDs to Sportspuff team IDs:
- NBA API uses numeric IDs (e.g., 1610612737 for Atlanta Hawks)
- Sportspuff uses custom team IDs from teams table
- Mapping is created dynamically based on team names
- Supports all 30 NBA teams

## Season Type Detection

Automatic detection of NBA season types:
- **Preseason**: October games
- **Regular Season**: November-April games
- **NBA Cup**: November-December In-Season Tournament games
- **All-Star Break**: Mid-February period
- **Playoffs**: April-June games
- **Off Season**: July-September

## Data Storage Strategy

**Full Caching Approach:**
- Complete season schedules imported upfront (~1,230 games)
- Live scores updated on-demand during games
- Minimal API calls during live updates
- Fast query performance with proper indexing

## Testing

To test the implementation:

1. **Database Setup:**
   ```bash
   ./scripts/setup_nba_db.sh
   ```

2. **Import Season Data:**
   ```bash
   python3 nba_data_importer.py --current-season
   ```

3. **Update Live Scores:**
   ```bash
   python3 nba_scores_updater.py
   ```

4. **Test API Endpoints:**
   ```bash
   curl http://localhost:5000/api/nba/scores/today
   curl http://localhost:5000/api/nba/scores/live
   ```

## Future Enhancements

- Extend to other sports (MLB, NFL, NHL, etc.)
- Add frontend display pages
- Implement push notifications for live games
- Add game statistics and player data
- Create team-specific schedule pages
- Add playoff bracket visualization

## Notes

- Full caching strategy means ~2-5MB storage for complete season
- Scores update on-demand when games are live
- Unified table keeps implementation simple
- No frontend changes in this phase - backend only
- Can extend to other sports using similar patterns
