#!/bin/bash
# Script to verify deployment status for dev and prod environments

echo "=== Sportspuff Deployment Verification ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check dev environment
echo "=== Development Environment (dev.sportspuff.org) ==="
DEV_URL="https://dev.sportspuff.org"
echo "Checking: $DEV_URL"

if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$DEV_URL" | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Dev site is accessible${NC}"
    
    # Check if it's serving content
    DEV_CONTENT=$(curl -s --max-time 5 "$DEV_URL" | head -20)
    if echo "$DEV_CONTENT" | grep -q "Sportspuff\|sportspuff"; then
        echo -e "${GREEN}✓ Dev site is serving content${NC}"
    else
        echo -e "${YELLOW}⚠ Dev site accessible but content may be missing${NC}"
    fi
else
    echo -e "${RED}✗ Dev site is not accessible${NC}"
fi

# Check prod environment
echo ""
echo "=== Production Environment (sportspuff.org) ==="
PROD_URL="https://sportspuff.org"
echo "Checking: $PROD_URL"

if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$PROD_URL" | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Prod site is accessible${NC}"
    
    # Check if it's serving content
    PROD_CONTENT=$(curl -s --max-time 5 "$PROD_URL" | head -20)
    if echo "$PROD_CONTENT" | grep -q "Sportspuff\|sportspuff"; then
        echo -e "${GREEN}✓ Prod site is serving content${NC}"
    else
        echo -e "${YELLOW}⚠ Prod site accessible but content may be missing${NC}"
    fi
else
    echo -e "${RED}✗ Prod site is not accessible${NC}"
fi

# Check API endpoints
echo ""
echo "=== API Endpoints ==="

# Dev API
DEV_API="https://api-dev.sportspuff.org"
echo "Checking dev API: $DEV_API"
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$DEV_API" | grep -q "200\|301\|302\|404"; then
    echo -e "${GREEN}✓ Dev API is responding${NC}"
else
    echo -e "${RED}✗ Dev API is not responding${NC}"
fi

# Prod API
PROD_API="https://api.sportspuff.org"
echo "Checking prod API: $PROD_API"
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$PROD_API" | grep -q "200\|301\|302\|404"; then
    echo -e "${GREEN}✓ Prod API is responding${NC}"
else
    echo -e "${RED}✗ Prod API is not responding${NC}"
fi

# Check GitHub Actions (if gh CLI is available)
echo ""
echo "=== GitHub Actions Status ==="
if command -v gh &> /dev/null; then
    echo "Recent dev branch runs:"
    gh run list --branch dev --limit 3 2>/dev/null || echo "Could not fetch dev runs"
    echo ""
    echo "Recent main branch runs:"
    gh run list --branch main --limit 3 2>/dev/null || echo "Could not fetch main runs"
else
    echo "GitHub CLI not installed. Install with: brew install gh"
    echo "Or check manually at: https://github.com/pbertain/sportspuff-v6/actions"
fi

echo ""
echo "=== Summary ==="
echo "For detailed GitHub Actions status, visit:"
echo "  https://github.com/pbertain/sportspuff-v6/actions"
echo ""
echo "To check server status manually:"
echo "  ssh ansible@host74.nird.club 'systemctl status sportspuff-v6-dev'"
echo "  ssh ansible@host74.nird.club 'systemctl status sportspuff-v6-prod'"

