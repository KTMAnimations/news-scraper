#!/bin/bash
set -e

# Deployment script for news-scraper
# Usage: ./deploy.sh [version]

VERSION=${1:-latest}
REGISTRY=${REGISTRY:-"your-registry.com"}

echo "=== Deploying news-scraper version: $VERSION ==="

# Pull latest images
echo "Pulling images..."
docker pull ${REGISTRY}/news-scraper-api:${VERSION}
docker pull ${REGISTRY}/news-scraper-frontend:${VERSION}

# Update stack
echo "Updating Docker stack..."
export VERSION=${VERSION}
export REGISTRY=${REGISTRY}

docker stack deploy -c /opt/news-scraper/docker-stack.yml news-scraper --with-registry-auth

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Health check
echo "Running health checks..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null; then
        echo "API is healthy!"
        break
    fi
    echo "Waiting for API... ($i/30)"
    sleep 2
done

# Check frontend
for i in {1..30}; do
    if curl -sf http://localhost:3000 > /dev/null; then
        echo "Frontend is healthy!"
        break
    fi
    echo "Waiting for frontend... ($i/30)"
    sleep 2
done

echo "=== Deployment complete ==="
docker stack services news-scraper
