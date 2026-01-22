#!/bin/bash

# Health check script for news-scraper
# Checks all services and reports their status

echo "============================================"
echo "News Scraper - Health Check"
echo "============================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
API_URL="${API_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
OPENSEARCH_URL="${OPENSEARCH_URL:-http://localhost:9200}"

check_service() {
    local name=$1
    local check_cmd=$2
    local status

    if eval "$check_cmd" > /dev/null 2>&1; then
        echo -e "[$GREEN OK $NC] $name"
        return 0
    else
        echo -e "[$RED FAIL $NC] $name"
        return 1
    fi
}

failures=0

echo ""
echo "Checking core services..."
echo "--------------------------"

# API Health
if check_service "API Server" "curl -sf ${API_URL}/health"; then
    :
else
    ((failures++))
fi

# Frontend
if check_service "Frontend" "curl -sf ${FRONTEND_URL}"; then
    :
else
    ((failures++))
fi

# PostgreSQL/TimescaleDB
if check_service "PostgreSQL/TimescaleDB" "pg_isready -h ${POSTGRES_HOST} -p ${POSTGRES_PORT}"; then
    :
else
    ((failures++))
fi

# Redis
if check_service "Redis" "redis-cli -h ${REDIS_HOST} -p ${REDIS_PORT} ping"; then
    :
else
    ((failures++))
fi

# OpenSearch
if check_service "OpenSearch" "curl -sf ${OPENSEARCH_URL}/_cluster/health"; then
    :
else
    ((failures++))
fi

echo ""
echo "Checking worker services..."
echo "----------------------------"

# Celery Workers
worker_count=$(docker ps --filter "name=celery-worker" --format "{{.Names}}" 2>/dev/null | wc -l)
if [ "$worker_count" -gt 0 ]; then
    echo -e "[$GREEN OK $NC] Celery Workers (${worker_count} running)"
else
    echo -e "[$YELLOW WARN $NC] Celery Workers (none running)"
    ((failures++))
fi

# Celery Beat
if docker ps --filter "name=celery-beat" --format "{{.Names}}" | grep -q beat; then
    echo -e "[$GREEN OK $NC] Celery Beat Scheduler"
else
    echo -e "[$YELLOW WARN $NC] Celery Beat Scheduler (not running)"
    ((failures++))
fi

echo ""
echo "Checking API endpoints..."
echo "--------------------------"

# Auth endpoint
if check_service "Auth API" "curl -sf ${API_URL}/api/v1/auth/me -o /dev/null -w '%{http_code}' | grep -q '401'"; then
    :
else
    ((failures++))
fi

# Events endpoint (may require auth)
if curl -sf "${API_URL}/api/v1/events/latest" > /dev/null 2>&1 || \
   curl -sf "${API_URL}/api/v1/events/latest" -o /dev/null -w '%{http_code}' 2>&1 | grep -q '401'; then
    echo -e "[$GREEN OK $NC] Events API"
else
    echo -e "[$RED FAIL $NC] Events API"
    ((failures++))
fi

echo ""
echo "Checking Docker containers..."
echo "-----------------------------"

# List all containers and their status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | head -20

echo ""
echo "============================================"

if [ $failures -eq 0 ]; then
    echo -e "${GREEN}All health checks passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}$failures check(s) failed.${NC}"
    echo "Review the output above and check logs with: docker-compose logs -f <service>"
    exit 1
fi
