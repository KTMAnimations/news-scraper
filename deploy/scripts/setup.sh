#!/bin/bash
set -e

# Setup script for news-scraper
# This script prepares the environment for first-time deployment

echo "============================================"
echo "News Scraper - Production Setup"
echo "============================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for required commands
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is required but not installed.${NC}"
        exit 1
    fi
}

echo "Checking required tools..."
check_command docker
check_command docker-compose
check_command openssl

echo -e "${GREEN}All required tools are installed.${NC}"

# Check if .env.production exists
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$DEPLOY_DIR")"

if [ ! -f "$DEPLOY_DIR/.env.production" ]; then
    echo -e "${YELLOW}Creating .env.production from template...${NC}"
    cp "$DEPLOY_DIR/.env.production.example" "$DEPLOY_DIR/.env.production"

    # Generate random secrets
    JWT_SECRET=$(openssl rand -hex 32)
    NEXTAUTH_SECRET=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -hex 16)

    # Update secrets in .env.production
    sed -i.bak "s/JWT_SECRET_KEY=CHANGE_ME.*/JWT_SECRET_KEY=$JWT_SECRET/" "$DEPLOY_DIR/.env.production"
    sed -i.bak "s/NEXTAUTH_SECRET=CHANGE_ME.*/NEXTAUTH_SECRET=$NEXTAUTH_SECRET/" "$DEPLOY_DIR/.env.production"
    sed -i.bak "s/POSTGRES_PASSWORD=CHANGE_ME/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" "$DEPLOY_DIR/.env.production"

    # Update DATABASE_URL with new password
    sed -i.bak "s|DATABASE_URL=postgresql+asyncpg://newsuser:CHANGE_ME@|DATABASE_URL=postgresql+asyncpg://newsuser:$POSTGRES_PASSWORD@|" "$DEPLOY_DIR/.env.production"
    sed -i.bak "s|DATABASE_SYNC_URL=postgresql://newsuser:CHANGE_ME@|DATABASE_SYNC_URL=postgresql://newsuser:$POSTGRES_PASSWORD@|" "$DEPLOY_DIR/.env.production"

    rm -f "$DEPLOY_DIR/.env.production.bak"

    echo -e "${GREEN}Generated secure random secrets.${NC}"
    echo -e "${YELLOW}Please review and update .env.production with your specific settings:${NC}"
    echo "  - Domain names (NEXT_PUBLIC_API_URL, etc.)"
    echo "  - Stripe keys (for billing)"
    echo "  - Email SMTP settings"
    echo "  - API keys (Twitter, Reddit, etc.)"
else
    echo -e "${GREEN}.env.production already exists.${NC}"
fi

# Create required directories
echo "Creating required directories..."
mkdir -p "$PROJECT_DIR/data/postgres"
mkdir -p "$PROJECT_DIR/data/redis"
mkdir -p "$PROJECT_DIR/data/opensearch"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/backups"

# Set permissions for OpenSearch
chmod 777 "$PROJECT_DIR/data/opensearch"

echo -e "${GREEN}Directories created.${NC}"

# Validate configuration
echo "Validating configuration..."
cd "$PROJECT_DIR"

# Check if critical values are still set to defaults
if grep -q "CHANGE_ME" "$DEPLOY_DIR/.env.production" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Some values in .env.production still contain 'CHANGE_ME'${NC}"
    echo "Please update these values before starting production:"
    grep "CHANGE_ME" "$DEPLOY_DIR/.env.production" | head -10
fi

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Review and update deploy/.env.production"
echo "2. Run: docker-compose -f deploy/docker-stack.yml --env-file deploy/.env.production up -d"
echo "3. Run: ./deploy/scripts/health-check.sh"
echo ""
