"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

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
    },

    # Task routing
    task_routes={
        "backend.workers.tasks.scraping_tasks.scrape_sec_filings": {"queue": "critical"},
        "backend.workers.tasks.nlp_tasks.analyze_sentiment": {"queue": "high"},
        "backend.workers.tasks.scoring_tasks.calculate_alpha": {"queue": "high"},
        "backend.workers.tasks.alerting_tasks.send_alert": {"queue": "critical"},
        "backend.workers.tasks.scraping_tasks.scrape_news": {"queue": "default"},
        "backend.workers.tasks.scraping_tasks.scrape_social": {"queue": "default"},
        "backend.workers.tasks.scraping_tasks.backfill_data": {"queue": "low"},
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
            "schedule": 3600.0,
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
    },
)
