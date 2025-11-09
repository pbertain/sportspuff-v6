#!/bin/bash
# Script to merge latest changes from main into dev branch

set -e  # Exit on error

echo "=== Merging main into dev branch ==="
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "Error: Not in a git repository"
    exit 1
fi

# Fetch latest changes
echo "1. Fetching latest changes from remote..."
git fetch origin

# Show current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""

# Check if there are uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "Warning: You have uncommitted changes!"
    echo "Please commit or stash them before merging."
    echo ""
    echo "To stash: git stash"
    echo "To commit: git add . && git commit -m 'Your message'"
    exit 1
fi

# Switch to dev branch
echo "2. Switching to dev branch..."
if git show-ref --verify --quiet refs/heads/dev; then
    git checkout dev
else
    echo "Dev branch doesn't exist locally. Creating it from origin/dev..."
    git checkout -b dev origin/dev 2>/dev/null || git checkout -b dev
fi

# Pull latest dev
echo "3. Pulling latest dev branch..."
git pull origin dev || echo "Note: Could not pull dev (may not exist on remote)"

# Merge main into dev
echo "4. Merging main into dev..."
git merge origin/main -m "Merge main into dev - $(date +%Y-%m-%d)" || {
    echo ""
    echo "Merge conflict detected!"
    echo "Please resolve conflicts manually, then:"
    echo "  git add ."
    echo "  git commit -m 'Resolve merge conflicts'"
    echo "  git push origin dev"
    exit 1
}

# Show what was merged
echo ""
echo "=== Merge Summary ==="
git log --oneline HEAD~1..HEAD

# Ask if user wants to push
echo ""
read -p "Push dev branch to remote? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "5. Pushing dev branch to remote..."
    git push origin dev
    echo ""
    echo "✓ Dev branch updated and pushed!"
    echo "GitHub Actions should automatically deploy to dev.sportspuff.org"
else
    echo "Skipping push. You can push manually with: git push origin dev"
fi

echo ""
echo "=== Done ==="

