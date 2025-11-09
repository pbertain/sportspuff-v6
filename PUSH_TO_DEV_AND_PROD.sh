#!/bin/bash
# Script to push changes to dev, then merge to main/prod
# Run this script manually after reviewing changes

set -e  # Exit on error

echo "=== Push Changes to Dev and Prod ==="
echo ""
echo "This script will:"
echo "1. Show current git status"
echo "2. Commit changes (if any uncommitted)"
echo "3. Push to dev branch"
echo "4. Merge dev to main"
echo "5. Push to main branch"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Show current status
echo "=== Current Git Status ==="
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""
git status --short
echo ""

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "You have uncommitted changes."
    read -p "Commit these changes? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Staging all changes..."
        git add -A
        
        echo "Enter commit message (or press Enter for default):"
        read -r COMMIT_MSG
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="Fix logo URLs, team detail URLs, and sync dev with prod"
        fi
        
        git commit -m "$COMMIT_MSG"
        echo "✓ Changes committed"
    else
        echo "Skipping commit. Please commit manually first."
        exit 1
    fi
else
    echo "✓ No uncommitted changes"
fi

# Determine which branch we're on and what to do
if [ "$CURRENT_BRANCH" = "dev" ]; then
    echo ""
    echo "=== Pushing to Dev Branch ==="
    read -p "Push to origin/dev? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin dev
        echo "✓ Pushed to dev branch"
        echo "GitHub Actions will auto-deploy to dev.sportspuff.org"
    else
        echo "Skipping push to dev"
    fi
    
    echo ""
    echo "=== Merging Dev to Main ==="
    read -p "Merge dev into main and push? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Switching to main branch..."
        git checkout main
        git pull origin main
        
        echo "Merging dev into main..."
        git merge dev -m "Merge dev into main - $(date +%Y-%m-%d)"
        
        echo "Pushing to main..."
        git push origin main
        echo "✓ Pushed to main branch"
        echo "GitHub Actions will auto-deploy to sportspuff.org"
        
        echo ""
        echo "Switching back to dev branch..."
        git checkout dev
    else
        echo "Skipping merge to main"
    fi
    
elif [ "$CURRENT_BRANCH" = "main" ]; then
    echo ""
    echo "You're on main branch."
    read -p "Push to origin/main? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push origin main
        echo "✓ Pushed to main branch"
        echo "GitHub Actions will auto-deploy to sportspuff.org"
    fi
    
    echo ""
    echo "To also update dev, run:"
    echo "  git checkout dev"
    echo "  git merge main"
    echo "  git push origin dev"
    
else
    echo ""
    echo "You're on branch: $CURRENT_BRANCH"
    echo "To push to dev/main, first switch to the appropriate branch:"
    echo "  git checkout dev    # or git checkout main"
    echo "Then run this script again"
fi

echo ""
echo "=== Done ==="
echo ""
echo "Check deployment status at:"
echo "  https://github.com/pbertain/sportspuff-v6/actions"


