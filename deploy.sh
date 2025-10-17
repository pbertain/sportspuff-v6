#!/bin/bash

# Sportspuff v6 Deployment Script
# Usage: ./deploy.sh [dev|prod]

set -e

ENVIRONMENT=${1:-dev}
PLAYBOOK_DIR="ansible/playbooks"
INVENTORY_FILE="ansible/inventory"

echo "🚀 Deploying Sportspuff v6 to $ENVIRONMENT environment..."

# Check if Ansible is installed
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Ansible is not installed. Please install Ansible first."
    echo "   On macOS: brew install ansible"
    echo "   On Ubuntu: sudo apt-get install ansible"
    exit 1
fi

# Check if inventory file exists
if [ ! -f "$INVENTORY_FILE" ]; then
    echo "❌ Inventory file not found: $INVENTORY_FILE"
    exit 1
fi

# Check if playbook exists
if [ ! -f "$PLAYBOOK_DIR/deploy.yml" ]; then
    echo "❌ Deploy playbook not found: $PLAYBOOK_DIR/deploy.yml"
    exit 1
fi

# Validate environment
if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    echo "❌ Invalid environment. Use 'dev' or 'prod'"
    exit 1
fi

echo "📋 Running deployment playbook for $ENVIRONMENT..."

# Run the deployment
ansible-playbook \
    -i ansible/inventory \
    -u ansible \
    --private-key ~/.ssh/keys/nirdclub__id_ed25519 \
    ansible/playbooks/deploy.yml \
    -e "target_env=$ENVIRONMENT"

echo "✅ Deployment to $ENVIRONMENT completed!"
echo ""
echo "🌐 Application should be available at:"
if [ "$ENVIRONMENT" = "dev" ]; then
    echo "   http://host74.nird.club:34181"
else
    echo "   http://host74.nird.club:34180"
fi
echo ""
echo "📊 To check service status:"
echo "   ssh ansible@host74.nird.club 'sudo systemctl status sportspuff-v6-$ENVIRONMENT'"
