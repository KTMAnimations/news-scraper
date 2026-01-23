# Micro-Alpha News Scraper - Deployment Guide

This guide covers deploying the Micro-Alpha News Scraper platform in both development and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Setup](#development-setup)
3. [Production Deployment](#production-deployment)
4. [Environment Configuration](#environment-configuration)
5. [Database Setup](#database-setup)
6. [SSL/TLS Configuration](#ssltls-configuration)
7. [Monitoring Setup](#monitoring-setup)
8. [Backup and Recovery](#backup-and-recovery)
9. [Scaling Guidelines](#scaling-guidelines)

---

## Prerequisites

### Required Software

| Software | Minimum Version | Purpose |
|----------|-----------------|---------|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ | Multi-container orchestration |
| Git | 2.40+ | Version control |
| Node.js | 18.x+ | Frontend build (optional) |
| Python | 3.11+ | Backend development (optional) |

### Hardware Requirements

#### Development
- **CPU**: 4 cores
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 20GB free space

#### Production (Minimum)
- **CPU**: 8 cores
- **RAM**: 32GB
- **Storage**: 100GB SSD
- **Network**: 100Mbps+ with low latency

---

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/KTMAnimations/news-scraper.git
cd news-scraper
```

### 2. Create Environment Files

Create `.env` file in the project root:

```bash
cp .env.example .env
```

Edit the `.env` file with your configuration (see [Environment Configuration](#environment-configuration)).

### 3. Start Services with Docker Compose

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Check service health
docker compose ps
```

### 4. Verify Services

| Service | URL | Expected Response |
|---------|-----|-------------------|
| API | http://localhost:8000 | `{"name": "Micro-Alpha News Scraper API", ...}` |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Frontend | http://localhost:3000 | Dashboard UI |
| WebSocket | ws://localhost:8001/ws/events | WebSocket connection |

### 5. Initialize Database

The database is automatically initialized on first startup. To run migrations manually:

```bash
# Run Alembic migrations
docker compose exec api alembic upgrade head

# Verify database tables
docker compose exec postgres psql -U newsuser -d newsdb -c "\dt"
```

### 6. Stop Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes data)
docker compose down -v
```

---

## Production Deployment

### Option A: Docker Compose (Single Server)

#### 1. Prepare Production Environment File

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    environment:
      - ENVIRONMENT=production
      - DEBUG=false
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    # Remove volume mounts for production

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        - NEXT_PUBLIC_API_URL=https://api.yourdomain.com
        - NEXT_PUBLIC_WS_URL=wss://ws.yourdomain.com
    restart: always

  # ... other services with production configs
```

#### 2. Deploy with Production Config

```bash
# Build and start with production config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Verify deployment
docker compose ps
curl -f http://localhost:8000/health
```

### Option B: Kubernetes Deployment

For production Kubernetes deployment, create the following manifests:

#### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: micro-alpha
```

#### API Deployment

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: micro-alpha
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
        - name: api
          image: your-registry/news-scraper-api:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: api-config
            - secretRef:
                name: api-secrets
          resources:
            requests:
              cpu: "500m"
              memory: "512Mi"
            limits:
              cpu: "2"
              memory: "2Gi"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
```

#### Apply Kubernetes Resources

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

### Option C: Cloud Provider Deployment

#### AWS (ECS/Fargate)

1. Create ECR repositories for each service
2. Push Docker images to ECR
3. Create ECS cluster with Fargate capacity
4. Create task definitions for each service
5. Create ECS services with load balancers
6. Configure RDS for PostgreSQL
7. Configure ElastiCache for Redis
8. Configure Amazon OpenSearch Service

#### GCP (Cloud Run / GKE)

1. Create Artifact Registry repositories
2. Push Docker images
3. Deploy to Cloud Run or GKE
4. Configure Cloud SQL for PostgreSQL
5. Configure Memorystore for Redis
6. Use Elastic Cloud for OpenSearch

---

## Environment Configuration

### Backend Environment Variables

```bash
# ===========================================
# CORE SETTINGS
# ===========================================
ENVIRONMENT=production          # development, staging, production
DEBUG=false                     # Enable debug mode
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR

# ===========================================
# DATABASE
# ===========================================
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/newsdb
DATABASE_SYNC_URL=postgresql://user:password@host:5432/newsdb

# ===========================================
# REDIS
# ===========================================
REDIS_URL=redis://host:6379/0

# ===========================================
# OPENSEARCH
# ===========================================
OPENSEARCH_URL=https://host:9200
# For AWS OpenSearch:
# OPENSEARCH_URL=https://search-domain.region.es.amazonaws.com

# ===========================================
# JWT AUTHENTICATION
# ===========================================
JWT_SECRET_KEY=your-secure-256-bit-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ===========================================
# STRIPE BILLING
# ===========================================
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ===========================================
# SEC EDGAR API
# ===========================================
SEC_USER_AGENT=YourCompany admin@yourcompany.com

# ===========================================
# SOCIAL APIs
# ===========================================
TWITTER_BEARER_TOKEN=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
STOCKTWITS_ACCESS_TOKEN=...

# ===========================================
# EMAIL (SMTP)
# ===========================================
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=alerts@yourdomain.com
SMTP_USE_TLS=true

# ===========================================
# PUSH NOTIFICATIONS (FCM)
# ===========================================
FCM_SERVER_KEY=...
FCM_PROJECT_ID=...

# ===========================================
# APPLICATION
# ===========================================
APP_URL=https://yourdomain.com
```

### Frontend Environment Variables

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_WS_URL=wss://ws.yourdomain.com
NEXT_PUBLIC_MOCK_MODE=false
NEXTAUTH_URL=https://yourdomain.com
NEXTAUTH_SECRET=your-nextauth-secret
```

### Generating Secure Secrets

```bash
# Generate JWT secret (256-bit)
openssl rand -base64 32

# Generate NextAuth secret
openssl rand -base64 32

# Generate database password
openssl rand -base64 24
```

---

## Database Setup

### TimescaleDB Installation

TimescaleDB is included in the Docker Compose setup. For manual installation:

```bash
# Install TimescaleDB extension (on existing PostgreSQL)
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

### Running Migrations

```bash
# Generate new migration
docker compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec api alembic upgrade head

# Rollback last migration
docker compose exec api alembic downgrade -1

# View migration history
docker compose exec api alembic history
```

### Creating TimescaleDB Hypertable

The events table should be converted to a hypertable:

```sql
-- Run after table creation
SELECT create_hypertable('events', 'event_time',
    chunk_time_interval => INTERVAL '1 day');

-- Enable compression (for older data)
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'event_time DESC'
);

-- Add compression policy (compress data older than 7 days)
SELECT add_compression_policy('events', INTERVAL '7 days');

-- Add retention policy (delete data older than 365 days)
SELECT add_retention_policy('events', INTERVAL '365 days');
```

### OpenSearch Index Setup

```bash
# Create events index with mappings
curl -X PUT "localhost:9200/events" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "financial_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "ticker": { "type": "keyword" },
      "headline": {
        "type": "text",
        "analyzer": "financial_analyzer"
      },
      "event_time": { "type": "date" },
      "alpha_score": { "type": "float" },
      "sentiment_label": { "type": "keyword" }
    }
  }
}'
```

---

## SSL/TLS Configuration

### Using Nginx as Reverse Proxy

Create `nginx.conf`:

```nginx
upstream api {
    server api:8000;
}

upstream websocket {
    server websocket-server:8001;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # API
    location /api/ {
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### Using Let's Encrypt with Certbot

```bash
# Install certbot
apt-get install certbot python3-certbot-nginx

# Obtain certificate
certbot --nginx -d yourdomain.com -d api.yourdomain.com

# Auto-renewal
certbot renew --dry-run
```

---

## Monitoring Setup

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | API health check |
| `GET /` | API status and version |

### Prometheus Metrics

Add Prometheus metrics collection:

```python
# In backend/api/main.py
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

### Grafana Dashboards

Import dashboards for:
- FastAPI metrics
- PostgreSQL/TimescaleDB
- Redis
- OpenSearch
- Celery tasks

### Log Aggregation

Configure log shipping to ELK stack or cloud logging:

```python
# structlog configuration for JSON output
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
```

---

## Backup and Recovery

### Database Backup

```bash
# Manual backup
docker compose exec postgres pg_dump -U newsuser newsdb > backup_$(date +%Y%m%d).sql

# Automated backup script
#!/bin/bash
BACKUP_DIR=/backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump -h localhost -U newsuser newsdb | gzip > $BACKUP_DIR/newsdb_$TIMESTAMP.sql.gz

# Keep only last 7 days
find $BACKUP_DIR -name "newsdb_*.sql.gz" -mtime +7 -delete
```

### Redis Backup

Redis is configured with append-only file (AOF):

```bash
# Manual backup
docker compose exec redis redis-cli BGSAVE

# Copy RDB file
docker cp news-scraper-redis-1:/data/dump.rdb ./redis_backup.rdb
```

### Disaster Recovery

1. **RTO (Recovery Time Objective)**: 1 hour
2. **RPO (Recovery Point Objective)**: 15 minutes

Recovery steps:
1. Provision new infrastructure
2. Restore PostgreSQL from backup
3. Restore Redis from AOF/RDB
4. Reindex OpenSearch from PostgreSQL
5. Verify service health
6. Update DNS records

---

## Scaling Guidelines

### Horizontal Scaling

#### Celery Workers

```yaml
# Increase worker replicas
celery-worker:
  deploy:
    replicas: 4
```

#### API Servers

Use load balancer with multiple API instances:

```yaml
api:
  deploy:
    replicas: 3
```

### Vertical Scaling

#### NLP Service (GPU)

```yaml
nlp-service:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Database Scaling

1. **Read Replicas**: Add PostgreSQL streaming replicas
2. **Connection Pooling**: Use PgBouncer
3. **Sharding**: Partition by ticker or time range

### Caching Strategy

1. **API Response Cache**: Cache frequent queries in Redis
2. **CDN**: Use CloudFlare or AWS CloudFront for static assets
3. **Search Cache**: OpenSearch query caching

---

## Deployment Checklist

### Pre-Deployment

- [ ] Environment variables configured
- [ ] Secrets properly secured (not in git)
- [ ] Database migrations tested
- [ ] SSL certificates obtained
- [ ] DNS records prepared
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Load testing completed

### Deployment

- [ ] Pull latest code
- [ ] Build Docker images
- [ ] Run database migrations
- [ ] Deploy services
- [ ] Verify health checks
- [ ] Test critical paths
- [ ] Monitor logs for errors

### Post-Deployment

- [ ] Verify all services healthy
- [ ] Check metrics dashboards
- [ ] Test user authentication
- [ ] Test WebSocket connections
- [ ] Verify data ingestion
- [ ] Monitor error rates
- [ ] Document any issues

---

*Last Updated: January 23, 2026*
