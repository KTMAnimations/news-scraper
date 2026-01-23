"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure, task_retry

from backend.config import settings

# Create Celery app
celery_app = Celery(
    "news_scraper",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=[
        "backend.workers.tasks.scraping_tasks",
        "backend.workers.tasks.nlp_tasks",
        "backend.workers.tasks.scoring_tasks",
        "backend.workers.tasks.alerting_tasks",
        "backend.workers.tasks.storage_tasks",
        "backend.workers.tasks.backfill_tasks",
        "backend.workers.tasks.enrichment_tasks",
        "backend.workers.tasks.backup_tasks",
        "backend.workers.tasks.social_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task result settings
    result_expires=3600,  # 1 hour
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task

    # Queue settings
    task_default_queue="default",
    task_queues={
        "critical": {
            "exchange": "critical",
            "routing_key": "critical",
        },
        "high": {
            "exchange": "high",
            "routing_key": "high",
        },
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "low": {
            "exchange": "low",
            "routing_key": "low",
        },
        "dead_letter": {
            "exchange": "dead_letter",
            "routing_key": "dead_letter",
        },
    },

    # Dead letter queue configuration
    task_reject_on_worker_lost=True,
    task_acks_late=True,  # Acknowledge tasks after completion for reliability

    # Task routing
    task_routes={
        "backend.workers.tasks.scraping_tasks.scrape_sec_filings": {"queue": "critical"},
        "backend.workers.tasks.nlp_tasks.analyze_sentiment": {"queue": "high"},
        "backend.workers.tasks.scoring_tasks.calculate_alpha": {"queue": "high"},
        "backend.workers.tasks.alerting_tasks.send_alert": {"queue": "critical"},
        "backend.workers.tasks.alerting_tasks.send_email_alert_task": {"queue": "high"},
        "backend.workers.tasks.scraping_tasks.scrape_news": {"queue": "default"},
        "backend.workers.tasks.scraping_tasks.scrape_social": {"queue": "default"},
        "backend.workers.tasks.scraping_tasks.check_otc_tiers": {"queue": "default"},
        "backend.workers.tasks.scraping_tasks.backfill_data": {"queue": "low"},
        "backend.workers.tasks.storage_tasks.index_event_opensearch_task": {"queue": "default"},
        "backend.workers.tasks.storage_tasks.store_and_index_task": {"queue": "default"},
        "backend.workers.tasks.storage_tasks.store_index_and_alert_task": {"queue": "default"},
        "backend.workers.tasks.backfill_tasks.backfill_historical_data": {"queue": "low"},
        "backend.workers.tasks.enrichment_tasks.enrich_with_market_data_task": {"queue": "default"},
        "backend.workers.tasks.dead_letter.process_dead_letter": {"queue": "dead_letter"},
        "backend.workers.tasks.backup_tasks.backup_database_task": {"queue": "low"},
        "backend.workers.tasks.backup_tasks.cleanup_old_backups_task": {"queue": "low"},
        # Social tasks routing
        "backend.workers.tasks.social_tasks.scrape_twitter_tickers": {"queue": "default"},
        "backend.workers.tasks.social_tasks.scrape_twitter_influencers": {"queue": "default"},
        "backend.workers.tasks.social_tasks.get_twitter_trending_tickers": {"queue": "default"},
        "backend.workers.tasks.social_tasks.aggregate_ticker_sentiment": {"queue": "high"},
        "backend.workers.tasks.social_tasks.aggregate_trending_sentiment": {"queue": "default"},
        "backend.workers.tasks.social_tasks.scheduled_twitter_scrape": {"queue": "default"},
        "backend.workers.tasks.social_tasks.scheduled_sentiment_aggregation": {"queue": "default"},
        "backend.workers.tasks.social_tasks.scheduled_influencer_scrape": {"queue": "default"},
    },

    # Worker settings
    worker_prefetch_multiplier=4,
    worker_concurrency=4,

    # Beat schedule (periodic tasks)
    beat_schedule={
        "scrape-sec-filings-every-10-seconds": {
            "task": "backend.workers.tasks.scraping_tasks.scrape_sec_filings",
            "schedule": 10.0,
        },
        "scrape-news-every-minute": {
            "task": "backend.workers.tasks.scraping_tasks.scrape_news",
            "schedule": 60.0,
        },
        "scrape-social-every-2-minutes": {
            "task": "backend.workers.tasks.scraping_tasks.scrape_social",
            "schedule": 120.0,
        },
        "check-otc-tier-changes-every-hour": {
            "task": "backend.workers.tasks.scraping_tasks.check_otc_tiers",
            "schedule": 3600.0,  # 60 minutes - monitors OTC Markets for tier upgrades/downgrades
        },
        "send-daily-digest-morning": {
            "task": "backend.workers.tasks.alerting_tasks.aggregate_daily_digest",
            "schedule": crontab(hour=9, minute=0),  # 9 AM UTC daily
        },
        "cleanup-old-alerts-nightly": {
            "task": "backend.workers.tasks.alerting_tasks.cleanup_old_alerts",
            "schedule": crontab(hour=3, minute=0),  # 3 AM UTC daily
        },
        "refresh-ticker-knowledge-base-daily": {
            "task": "backend.workers.tasks.nlp_tasks.refresh_knowledge_base",
            "schedule": crontab(hour=6, minute=0),  # 6 AM UTC daily
        },
        "process-dead-letter-queue-hourly": {
            "task": "backend.workers.tasks.dead_letter.retry_dead_letter_tasks",
            "schedule": crontab(minute=0),  # Every hour at :00
        },
        # Database backup - runs daily at 2 AM UTC
        "backup-database-daily": {
            "task": "backend.workers.tasks.backup_tasks.backup_database_task",
            "schedule": crontab(hour=2, minute=0),  # 2 AM UTC daily
        },
        # Cleanup old backups - runs daily at 2:30 AM UTC (after backup completes)
        "cleanup-old-backups-daily": {
            "task": "backend.workers.tasks.backup_tasks.cleanup_old_backups_task",
            "schedule": crontab(hour=2, minute=30),  # 2:30 AM UTC daily
        },
        # Twitter scraping - every 3 minutes (rate limit aware)
        "scrape-twitter-every-3-minutes": {
            "task": "backend.workers.tasks.social_tasks.scheduled_twitter_scrape",
            "schedule": 180.0,  # 3 minutes
        },
        # Twitter influencer scraping - every 10 minutes
        "scrape-twitter-influencers-every-10-minutes": {
            "task": "backend.workers.tasks.social_tasks.scheduled_influencer_scrape",
            "schedule": 600.0,  # 10 minutes
        },
        # Sentiment aggregation for trending - every 5 minutes
        "aggregate-trending-sentiment-every-5-minutes": {
            "task": "backend.workers.tasks.social_tasks.scheduled_sentiment_aggregation",
            "schedule": 300.0,  # 5 minutes
        },
    },
)


# ============================================================================
# Dead Letter Queue Signal Handlers
# ============================================================================

import json
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None,
                        kwargs=None, traceback=None, einfo=None, **kw):
    """Handle task failures by routing to dead letter queue after max retries.

    This signal is triggered when a task fails and has exhausted all retries.
    Failed tasks are stored in Redis for later analysis and potential retry.
    """
    import redis

    try:
        # Get retry count from task request
        retries = getattr(sender.request, 'retries', 0) if sender else 0
        max_retries = getattr(sender, 'max_retries', 3) if sender else 3

        # Only send to DLQ if max retries exceeded
        if retries >= max_retries:
            client = redis.from_url(str(settings.redis_url))

            dead_letter_entry = {
                "task_id": task_id,
                "task_name": sender.name if sender else "unknown",
                "args": list(args) if args else [],
                "kwargs": kwargs if kwargs else {},
                "exception": str(exception),
                "exception_type": type(exception).__name__ if exception else "Unknown",
                "traceback": str(einfo) if einfo else None,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "retries": retries,
                "original_queue": getattr(sender.request, 'delivery_info', {}).get('routing_key', 'unknown')
                                  if sender and hasattr(sender, 'request') else 'unknown',
            }

            # Store in Redis list for dead letter queue
            client.lpush("celery:dead_letter_queue", json.dumps(dead_letter_entry))

            # Also track in a set for unique task tracking
            client.sadd("celery:dead_letter_tasks", task_id)

            # Increment failure counter for monitoring
            client.incr("celery:dead_letter_count")

            client.close()

            logger.warning(
                "Task moved to dead letter queue",
                task_id=task_id,
                task_name=sender.name if sender else "unknown",
                exception=str(exception),
                retries=retries,
            )

    except Exception as dlq_error:
        logger.error(
            "Failed to move task to dead letter queue",
            task_id=task_id,
            error=str(dlq_error),
        )


@task_retry.connect
def handle_task_retry(sender=None, request=None, reason=None, einfo=None, **kw):
    """Log task retries for monitoring purposes."""
    logger.info(
        "Task retry scheduled",
        task_id=request.id if request else "unknown",
        task_name=sender.name if sender else "unknown",
        reason=str(reason),
        retries=request.retries if request else 0,
    )
