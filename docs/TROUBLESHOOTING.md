# Micro-Alpha News Scraper - Troubleshooting Guide

This guide provides solutions to common issues encountered when deploying and operating the Micro-Alpha News Scraper platform.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Docker & Container Issues](#docker--container-issues)
3. [Database Issues](#database-issues)
4. [API Issues](#api-issues)
5. [WebSocket Issues](#websocket-issues)
6. [Celery & Task Queue Issues](#celery--task-queue-issues)
7. [NLP & Sentiment Analysis Issues](#nlp--sentiment-analysis-issues)
8. [Search Issues](#search-issues)
9. [Authentication Issues](#authentication-issues)
10. [Frontend Issues](#frontend-issues)
11. [Performance Issues](#performance-issues)
12. [Data Ingestion Issues](#data-ingestion-issues)

---

## Quick Diagnostics

### Health Check Commands

```bash
# Check all service statuses
docker compose ps

# Check API health
curl -f http://localhost:8000/health

# Check database connectivity
docker compose exec postgres pg_isready -U newsuser -d newsdb

# Check Redis connectivity
docker compose exec redis redis-cli ping

# Check OpenSearch health
curl -f http://localhost:9200/_cluster/health

# Check Celery worker status
docker compose exec celery-worker celery -A backend.workers.celery_app inspect active
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f celery-worker
docker compose logs -f postgres

# Last N lines
docker compose logs --tail=100 api
```

---

## Docker & Container Issues

### Issue: Containers won't start

**Symptoms:**
- `docker compose up` fails
- Containers exit immediately after starting

**Solutions:**

1. **Check Docker resources:**
   ```bash
   # Ensure Docker has enough resources
   docker system df
   docker system prune -f  # Clean up unused resources
   ```

2. **Check for port conflicts:**
   ```bash
   # Check if ports are in use
   lsof -i :8000  # API
   lsof -i :3000  # Frontend
   lsof -i :5432  # PostgreSQL
   lsof -i :6379  # Redis
   lsof -i :9200  # OpenSearch
   ```

3. **Check container logs for errors:**
   ```bash
   docker compose logs api 2>&1 | head -50
   ```

### Issue: "No space left on device"

**Solutions:**

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove all unused resources
docker system prune -a --volumes
```

### Issue: Container exits with code 137

**Cause:** Out of memory (OOM killed)

**Solutions:**

1. Increase Docker memory allocation in Docker Desktop settings
2. Reduce memory usage in docker-compose.yml:
   ```yaml
   services:
     opensearch:
       environment:
         - "OPENSEARCH_JAVA_OPTS=-Xms256m -Xmx256m"
   ```

### Issue: Network connectivity between containers

**Solutions:**

```bash
# Verify network exists
docker network ls | grep news-scraper

# Recreate network
docker compose down
docker network rm news-scraper-network
docker compose up -d

# Test connectivity between containers
docker compose exec api ping postgres
```

---

## Database Issues

### Issue: "Connection refused" to PostgreSQL

**Symptoms:**
- API fails to start
- Error: `could not connect to server: Connection refused`

**Solutions:**

1. **Wait for PostgreSQL to be ready:**
   ```bash
   # Check if PostgreSQL is healthy
   docker compose ps postgres

   # Wait for ready state
   docker compose exec postgres pg_isready -U newsuser -d newsdb
   ```

2. **Check PostgreSQL logs:**
   ```bash
   docker compose logs postgres | tail -50
   ```

3. **Verify connection string:**
   ```bash
   # Test connection manually
   docker compose exec postgres psql -U newsuser -d newsdb -c "SELECT 1;"
   ```

### Issue: "Relation does not exist" errors

**Cause:** Database migrations not run

**Solutions:**

```bash
# Run migrations
docker compose exec api alembic upgrade head

# Check migration status
docker compose exec api alembic current

# If migrations are corrupted, recreate
docker compose exec api alembic stamp head
docker compose exec api alembic upgrade head
```

### Issue: "asyncpg" connection errors in Celery

**Cause:** Celery uses sync code but asyncpg is async-only

**Solution:** Use sync database URL for Celery tasks:

```python
# In backend/config.py, ensure DATABASE_SYNC_URL is set
database_sync_url: str = "postgresql://user:password@localhost:5432/newsdb"
```

### Issue: TimescaleDB extension not found

**Solutions:**

```sql
-- Connect to database
docker compose exec postgres psql -U newsuser -d newsdb

-- Create extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Verify installation
\dx timescaledb
```

### Issue: Slow database queries

**Solutions:**

1. **Check for missing indexes:**
   ```sql
   -- Find slow queries
   SELECT query, calls, mean_time, total_time
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

2. **Add appropriate indexes:**
   ```sql
   -- Common indexes for events table
   CREATE INDEX IF NOT EXISTS idx_events_ticker ON events(ticker);
   CREATE INDEX IF NOT EXISTS idx_events_event_time ON events(event_time DESC);
   CREATE INDEX IF NOT EXISTS idx_events_alpha ON events(alpha_score) WHERE alpha_score > 0.5;
   ```

3. **Analyze tables:**
   ```sql
   ANALYZE events;
   ANALYZE users;
   ```

---

## API Issues

### Issue: 500 Internal Server Error

**Solutions:**

1. **Check API logs:**
   ```bash
   docker compose logs api --tail=100 | grep -i error
   ```

2. **Enable debug mode temporarily:**
   ```bash
   # In .env
   DEBUG=true
   LOG_LEVEL=DEBUG

   # Restart API
   docker compose restart api
   ```

3. **Check for missing environment variables:**
   ```bash
   docker compose exec api python -c "from backend.config import settings; settings.print_status()"
   ```

### Issue: CORS errors in browser

**Symptoms:**
- Browser console shows CORS errors
- API works via curl but not from frontend

**Solutions:**

1. **Check CORS configuration in main.py:**
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000", "https://yourdomain.com"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Verify frontend URL matches allowed origins**

### Issue: 429 Too Many Requests

**Cause:** Rate limiting triggered

**Solutions:**

1. **Check rate limit headers in response:**
   ```bash
   curl -i http://localhost:8000/api/v1/events
   # Look for X-RateLimit-* headers
   ```

2. **Adjust rate limits for development:**
   ```python
   # In backend/api/middleware/rate_limiter.py
   TIER_LIMITS = {
       "anonymous": 60,  # Increase for development
   }
   ```

### Issue: 401 Unauthorized on valid token

**Solutions:**

1. **Check token expiration:**
   ```bash
   # Decode JWT (don't share secrets!)
   echo "YOUR_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq .
   ```

2. **Verify JWT secret matches:**
   ```bash
   # Check both services use same secret
   docker compose exec api env | grep JWT_SECRET_KEY
   docker compose exec websocket-server env | grep JWT_SECRET_KEY
   ```

3. **Check clock synchronization** (important for JWT exp validation)

---

## WebSocket Issues

### Issue: WebSocket connection fails

**Symptoms:**
- Connection closes immediately
- Error: `WebSocket connection failed`

**Solutions:**

1. **Check WebSocket server is running:**
   ```bash
   docker compose ps websocket-server
   docker compose logs websocket-server
   ```

2. **Test WebSocket manually:**
   ```bash
   # Using websocat
   websocat ws://localhost:8001/ws/events

   # Using curl (check upgrade)
   curl -i -N \
     -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: dGVzdA==" \
     http://localhost:8001/ws/events
   ```

3. **Check Redis pub/sub:**
   ```bash
   # Subscribe to channel
   docker compose exec redis redis-cli SUBSCRIBE events:all

   # In another terminal, publish test message
   docker compose exec redis redis-cli PUBLISH events:all '{"test": true}'
   ```

### Issue: WebSocket disconnects frequently

**Solutions:**

1. **Add keepalive/heartbeat:**
   ```javascript
   // Client-side
   setInterval(() => {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify({ action: "ping" }));
     }
   }, 30000);
   ```

2. **Check proxy timeouts** (if using nginx):
   ```nginx
   location /ws/ {
       proxy_read_timeout 300s;
       proxy_send_timeout 300s;
   }
   ```

### Issue: Events not appearing in real-time

**Cause:** Redis pub/sub not connected or events not being published

**Solutions:**

1. **Verify events are being published:**
   ```bash
   # Monitor Redis pub/sub
   docker compose exec redis redis-cli MONITOR | grep -i publish
   ```

2. **Check Celery task is publishing:**
   ```bash
   docker compose logs celery-worker | grep -i "publish\|redis"
   ```

---

## Celery & Task Queue Issues

### Issue: Tasks not being executed

**Symptoms:**
- Events not being scraped
- Tasks stuck in queue

**Solutions:**

1. **Check Celery worker status:**
   ```bash
   docker compose exec celery-worker celery -A backend.workers.celery_app inspect active
   docker compose exec celery-worker celery -A backend.workers.celery_app inspect reserved
   ```

2. **Check task queue lengths:**
   ```bash
   docker compose exec redis redis-cli LLEN celery
   docker compose exec redis redis-cli LLEN critical
   docker compose exec redis redis-cli LLEN high
   ```

3. **Restart workers:**
   ```bash
   docker compose restart celery-worker celery-beat
   ```

### Issue: "Task not found" errors

**Cause:** Task module not imported

**Solutions:**

1. **Verify task imports in celery_app.py:**
   ```python
   celery_app.autodiscover_tasks([
       'backend.workers.tasks.scraping_tasks',
       'backend.workers.tasks.storage_tasks',
       # ... all task modules
   ])
   ```

2. **Check for import errors:**
   ```bash
   docker compose exec celery-worker python -c "from backend.workers.tasks.scraping_tasks import *"
   ```

### Issue: Celery Beat not scheduling tasks

**Solutions:**

1. **Check beat schedule:**
   ```bash
   docker compose logs celery-beat | grep -i "scheduler\|schedule"
   ```

2. **Verify schedule configuration:**
   ```python
   # In backend/workers/celery_app.py
   celery_app.conf.beat_schedule = {
       'scrape-sec-every-10s': {
           'task': 'backend.workers.tasks.scraping_tasks.scrape_sec_filings',
           'schedule': 10.0,
       },
   }
   ```

3. **Remove stale schedule file:**
   ```bash
   docker compose exec celery-beat rm -f celerybeat-schedule
   docker compose restart celery-beat
   ```

### Issue: "Event loop already running" in Celery

**Cause:** Mixing async and sync code incorrectly

**Solution:** Use sync database sessions in Celery tasks:

```python
# In Celery tasks, use:
from backend.storage.timescale import get_sync_session

def my_task():
    with get_sync_session() as session:
        # Sync database operations
        pass
```

---

## NLP & Sentiment Analysis Issues

### Issue: FinBERT model not loading

**Symptoms:**
- Sentiment analysis falling back to simple method
- Error: `Model not found`

**Solutions:**

1. **Check model cache:**
   ```bash
   docker compose exec nlp-service ls -la /app/models
   ```

2. **Manually download model:**
   ```bash
   docker compose exec nlp-service python -c "
   from transformers import AutoModelForSequenceClassification, AutoTokenizer
   AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')
   AutoTokenizer.from_pretrained('ProsusAI/finbert')
   "
   ```

3. **Check HuggingFace cache permissions:**
   ```bash
   docker compose exec nlp-service chmod -R 755 /app/models
   ```

### Issue: Sentiment analysis is slow

**Solutions:**

1. **Enable GPU (if available):**
   ```yaml
   # In docker-compose.yml
   nlp-service:
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu]
   ```

2. **Batch sentiment requests:**
   ```python
   # Process multiple texts at once
   results = sentiment_service.analyze_batch(texts)
   ```

3. **Use simpler model for low-priority events:**
   ```python
   if event.urgency == "LOW":
       return simple_sentiment(text)
   else:
       return finbert_sentiment(text)
   ```

### Issue: Incorrect sentiment on financial text

**Solutions:**

1. **Verify FinBERT is being used (not fallback):**
   ```bash
   docker compose logs celery-worker | grep -i "sentiment\|finbert"
   ```

2. **Check for text preprocessing issues:**
   - Remove HTML tags before analysis
   - Handle special characters
   - Truncate very long texts

---

## Search Issues

### Issue: OpenSearch not returning results

**Solutions:**

1. **Check index exists:**
   ```bash
   curl http://localhost:9200/_cat/indices
   ```

2. **Check document count:**
   ```bash
   curl http://localhost:9200/events/_count
   ```

3. **Verify data is being indexed:**
   ```bash
   docker compose logs celery-worker | grep -i "opensearch\|index"
   ```

4. **Reindex from database:**
   ```bash
   docker compose exec api python -c "
   from backend.storage.opensearch import reindex_all_events
   import asyncio
   asyncio.run(reindex_all_events())
   "
   ```

### Issue: OpenSearch out of disk space

**Solutions:**

1. **Check disk usage:**
   ```bash
   curl http://localhost:9200/_cat/allocation?v
   ```

2. **Delete old indices:**
   ```bash
   curl -X DELETE http://localhost:9200/events-2024*
   ```

3. **Reduce replica count:**
   ```bash
   curl -X PUT http://localhost:9200/events/_settings -H 'Content-Type: application/json' -d'
   {
     "number_of_replicas": 0
   }'
   ```

### Issue: Search returns irrelevant results

**Solutions:**

1. **Check field mappings:**
   ```bash
   curl http://localhost:9200/events/_mapping | jq
   ```

2. **Test query directly:**
   ```bash
   curl -X GET "localhost:9200/events/_search" -H 'Content-Type: application/json' -d'
   {
     "query": {
       "multi_match": {
         "query": "apple earnings",
         "fields": ["headline^2", "summary", "content"]
       }
     }
   }'
   ```

---

## Authentication Issues

### Issue: JWT token invalid after restart

**Cause:** JWT_SECRET_KEY changed

**Solutions:**

1. **Ensure consistent secret across restarts:**
   ```bash
   # Generate and store a permanent secret
   openssl rand -base64 32 > .jwt_secret

   # In .env
   JWT_SECRET_KEY=$(cat .jwt_secret)
   ```

2. **All existing tokens will be invalid after key change** - users must re-login

### Issue: "User not found" with valid token

**Cause:** User deleted or database mismatch

**Solutions:**

1. **Verify user exists:**
   ```sql
   SELECT * FROM users WHERE id = 'user-uuid-here';
   ```

2. **Check token payload:**
   ```python
   from jose import jwt
   payload = jwt.decode(token, options={"verify_signature": False})
   print(payload)  # Check 'sub' field
   ```

### Issue: Password reset emails not sending

**Solutions:**

1. **Check email configuration:**
   ```bash
   docker compose exec api python -c "
   from backend.config import settings
   print(f'Email configured: {settings.email_configured}')
   print(f'SMTP Host: {settings.smtp_host}')
   "
   ```

2. **Test SMTP connection:**
   ```python
   import smtplib
   server = smtplib.SMTP(host, port)
   server.starttls()
   server.login(username, password)
   ```

---

## Frontend Issues

### Issue: Frontend shows "API Error"

**Solutions:**

1. **Check API URL configuration:**
   ```bash
   # In frontend container
   docker compose exec frontend env | grep NEXT_PUBLIC_API_URL
   ```

2. **Verify API is accessible from frontend container:**
   ```bash
   docker compose exec frontend curl http://api:8000/health
   ```

3. **Check browser network tab** for actual error response

### Issue: Real-time updates not working

**Solutions:**

1. **Check WebSocket connection in browser:**
   - Open DevTools > Network > WS tab
   - Look for connection status

2. **Verify WebSocket URL:**
   ```javascript
   console.log(process.env.NEXT_PUBLIC_WS_URL);
   ```

3. **Check for proxy/firewall blocking WebSocket**

### Issue: Styles not loading / UI broken

**Solutions:**

1. **Rebuild frontend:**
   ```bash
   docker compose build frontend --no-cache
   docker compose up -d frontend
   ```

2. **Clear browser cache**

3. **Check for TailwindCSS build errors:**
   ```bash
   docker compose logs frontend | grep -i "tailwind\|postcss\|error"
   ```

---

## Performance Issues

### Issue: High memory usage

**Solutions:**

1. **Identify memory hogs:**
   ```bash
   docker stats --no-stream
   ```

2. **Reduce OpenSearch heap:**
   ```yaml
   opensearch:
     environment:
       - "OPENSEARCH_JAVA_OPTS=-Xms256m -Xmx256m"
   ```

3. **Limit Celery worker concurrency:**
   ```yaml
   celery-worker:
     command: celery -A backend.workers.celery_app worker -c 2
   ```

### Issue: Slow API responses

**Solutions:**

1. **Enable query logging:**
   ```python
   # In database config
   engine = create_engine(url, echo=True)
   ```

2. **Add database connection pooling:**
   ```python
   engine = create_async_engine(
       url,
       pool_size=20,
       max_overflow=10,
       pool_pre_ping=True,
   )
   ```

3. **Add API response caching:**
   ```python
   from fastapi_cache import FastAPICache
   from fastapi_cache.backends.redis import RedisBackend

   @router.get("/events")
   @cache(expire=60)
   async def get_events():
       ...
   ```

### Issue: Event processing backlog

**Solutions:**

1. **Scale Celery workers:**
   ```bash
   docker compose up -d --scale celery-worker=4
   ```

2. **Prioritize critical tasks:**
   ```python
   @celery_app.task(queue='critical', priority=9)
   def scrape_sec_filings():
       ...
   ```

3. **Monitor queue lengths:**
   ```bash
   watch -n 1 'docker compose exec redis redis-cli LLEN celery'
   ```

---

## Data Ingestion Issues

### Issue: SEC filings not being scraped

**Solutions:**

1. **Check SEC_USER_AGENT:**
   ```bash
   docker compose exec celery-worker env | grep SEC_USER_AGENT
   ```
   - Must include valid email address
   - Format: `Company Name admin@company.com`

2. **Check SEC rate limits:**
   - SEC allows 10 requests/second
   - May be blocked if exceeding

3. **Test SEC API manually:**
   ```bash
   curl -A "YourCompany admin@yourcompany.com" \
     "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=only&count=40&output=atom"
   ```

### Issue: Social scraping returning empty results

**Solutions:**

1. **Check API credentials:**
   ```bash
   docker compose exec celery-worker env | grep -i "reddit\|stocktwits\|twitter"
   ```

2. **Verify APIs are accessible:**
   ```bash
   # Test StockTwits
   curl "https://api.stocktwits.com/api/2/streams/trending.json"
   ```

3. **Check for API rate limiting** in logs

### Issue: Duplicate events being stored

**Solutions:**

1. **Verify deduplication is working:**
   ```python
   # Check for duplicate headlines
   SELECT headline, COUNT(*)
   FROM events
   GROUP BY headline
   HAVING COUNT(*) > 1;
   ```

2. **Check deduplication logic:**
   - Events are deduplicated by ticker + headline hash
   - Check hash generation in storage task

---

## Getting Help

If issues persist:

1. **Collect diagnostic information:**
   ```bash
   # System info
   docker compose version
   docker version

   # Service status
   docker compose ps

   # Recent logs
   docker compose logs --tail=500 > logs.txt

   # Configuration (redact secrets!)
   docker compose config > config.txt
   ```

2. **Check GitHub Issues:**
   https://github.com/KTMAnimations/news-scraper/issues

3. **Open a new issue** with:
   - Description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Diagnostic information

---

*Last Updated: January 23, 2026*
