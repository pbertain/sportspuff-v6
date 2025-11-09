# Dev Environment Sync Instructions

## Issues Fixed

### 1. Logo URLs ✅
- **Fixed**: Logo URLs now use `https://www.splitsp.lat/logos/{league}/{team_name}_logo.png` format
- **Changed in**: `app.py` - `get_logo()` filter and team colors mapping

### 2. Team Detail URLs ✅
- **Fixed**: Changed from `/team/{team_id}` to `/team/{league}/{team_name}` format
- **Changed in**: 
  - `templates/teams.html`
  - `templates/stadium_detail.html`

### 3. Dev Environment Behind Prod
- **Status**: Dev branch needs to be synced with main branch
- **Solution**: Use the `merge_main_to_dev.sh` script (see below)

## How to Sync Dev with Prod

### Option 1: Using the Merge Script (Recommended)
```bash
./merge_main_to_dev.sh
```

This script will:
1. Fetch latest changes
2. Switch to dev branch
3. Merge main into dev
4. Push to remote (with confirmation)

### Option 2: Manual Git Commands
```bash
# Fetch latest
git fetch origin

# Switch to dev
git checkout dev

# Pull latest dev (if exists)
git pull origin dev

# Merge main into dev
git merge origin/main

# Push to remote
git push origin dev
```

### Option 3: GitHub Web Interface
1. Go to: https://github.com/pbertain/sportspuff-v6
2. Create a Pull Request: `main` → `dev`
3. Merge the PR
4. GitHub Actions will auto-deploy

## Verification

After syncing, verify:
1. Check GitHub Actions: https://github.com/pbertain/sportspuff-v6/actions
2. Verify dev site: https://dev.sportspuff.org
3. Run verification script: `./verify_deployment.sh`

## Files That May Need Updates in Dev

If dev still shows old versions after sync, these files may need manual updates:
- `templates/stadiums.html` - Stadium listing page
- `templates/teams.html` - Teams listing page (already fixed)
- `templates/team_detail_horizontal.html` - Team detail page
- Any other templates that were updated in main but not in dev

## GitHub Actions Deployment

- **Dev branch** → Auto-deploys to dev.sportspuff.org (port 34181)
- **Main branch** → Auto-deploys to sportspuff.org (port 34180)

Check deployment status at: https://github.com/pbertain/sportspuff-v6/actions


