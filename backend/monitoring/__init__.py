"""Monitoring and observability module for News Scraper.

This module provides:
- Prometheus metrics collection
- OpenTelemetry distributed tracing
- Custom business metrics
"""

from .metrics import (
    MetricsManager,
    get_metrics,
    setup_metrics,
    # Metric instances
    events_ingested_counter,
    events_by_type_counter,
    events_by_ticker_counter,
    high_alpha_events_counter,
    scraper_events_counter,
    scraper_errors_counter,
    scraper_rate_limited_counter,
    sentiment_analysis_counter,
    sentiment_analysis_errors_counter,
    nlp_processing_histogram,
    event_processing_histogram,
    event_processing_errors_counter,
    database_connection_errors_counter,
    database_query_histogram,
    celery_task_counter,
    celery_queue_gauge,
    websocket_connections_gauge,
    alpha_score_histogram,
)
from .tracing import (
    TracingManager,
    setup_tracing,
    get_tracer,
    trace_async,
    trace_sync,
)

__all__ = [
    # Metrics
    "MetricsManager",
    "get_metrics",
    "setup_metrics",
    "events_ingested_counter",
    "events_by_type_counter",
    "events_by_ticker_counter",
    "high_alpha_events_counter",
    "scraper_events_counter",
    "scraper_errors_counter",
    "scraper_rate_limited_counter",
    "sentiment_analysis_counter",
    "sentiment_analysis_errors_counter",
    "nlp_processing_histogram",
    "event_processing_histogram",
    "event_processing_errors_counter",
    "database_connection_errors_counter",
    "database_query_histogram",
    "celery_task_counter",
    "celery_queue_gauge",
    "websocket_connections_gauge",
    "alpha_score_histogram",
    # Tracing
    "TracingManager",
    "setup_tracing",
    "get_tracer",
    "trace_async",
    "trace_sync",
]
