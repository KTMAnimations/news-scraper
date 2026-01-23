"""Dead letter queue processing tasks.

This module handles failed tasks that have been moved to the dead letter queue
after exhausting all retries. It provides mechanisms for:
- Viewing failed tasks
- Retrying failed tasks manually
- Cleaning up old dead letter entries
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Any

import redis
import structlog

from backend.config import settings
from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


def get_redis_client() -> redis.Redis:
    """Get a Redis client instance."""
    return redis.from_url(str(settings.redis_url))


@celery_app.task(bind=True, max_retries=0)
def process_dead_letter(self, dead_letter_entry: dict[str, Any]) -> dict[str, Any]:
    """Process a single dead letter entry.

    This task is used for manual inspection and processing of dead letter items.

    Args:
        dead_letter_entry: The failed task entry from the DLQ

    Returns:
        Processing result
    """
    logger.info(
        "Processing dead letter entry",
        task_id=dead_letter_entry.get("task_id"),
        task_name=dead_letter_entry.get("task_name"),
        failed_at=dead_letter_entry.get("failed_at"),
    )

    return {
        "processed": True,
        "entry": dead_letter_entry,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


@celery_app.task(bind=True, max_retries=1)
def retry_dead_letter_tasks(self, max_tasks: int = 10, max_age_hours: int = 24) -> dict[str, Any]:
    """Retry tasks from the dead letter queue.

    This task is scheduled to run periodically to attempt re-processing
    of failed tasks that may succeed on retry (e.g., due to transient errors).

    Args:
        max_tasks: Maximum number of tasks to retry per run
        max_age_hours: Only retry tasks failed within this many hours

    Returns:
        Summary of retry attempts
    """
    client = get_redis_client()
    results = {
        "retried": 0,
        "skipped": 0,
        "failed": 0,
        "details": [],
    }

    try:
        # Get tasks from dead letter queue (LIFO - most recent first)
        entries = []
        for _ in range(max_tasks):
            entry = client.rpop("celery:dead_letter_queue")
            if entry is None:
                break
            entries.append(json.loads(entry))

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        for entry in entries:
            task_id = entry.get("task_id", "unknown")
            task_name = entry.get("task_name")
            failed_at = entry.get("failed_at")

            try:
                # Check if task is too old
                if failed_at:
                    failed_time = datetime.fromisoformat(failed_at.replace("Z", "+00:00"))
                    if failed_time < cutoff_time:
                        logger.debug(
                            "Skipping old dead letter task",
                            task_id=task_id,
                            failed_at=failed_at,
                        )
                        results["skipped"] += 1
                        results["details"].append({
                            "task_id": task_id,
                            "status": "skipped",
                            "reason": "too_old",
                        })
                        continue

                # Try to re-queue the task
                if task_name and task_name != "unknown":
                    task = celery_app.tasks.get(task_name)
                    if task:
                        args = entry.get("args", [])
                        kwargs = entry.get("kwargs", {})

                        # Re-queue with lower priority
                        task.apply_async(
                            args=args,
                            kwargs=kwargs,
                            queue="low",  # Retry on low priority queue
                            countdown=60,  # Wait 1 minute before executing
                        )

                        # Remove from dead letter tracking set
                        client.srem("celery:dead_letter_tasks", task_id)

                        logger.info(
                            "Dead letter task re-queued",
                            task_id=task_id,
                            task_name=task_name,
                        )

                        results["retried"] += 1
                        results["details"].append({
                            "task_id": task_id,
                            "task_name": task_name,
                            "status": "retried",
                        })
                    else:
                        logger.warning(
                            "Task not found for retry",
                            task_name=task_name,
                        )
                        results["skipped"] += 1
                        results["details"].append({
                            "task_id": task_id,
                            "status": "skipped",
                            "reason": "task_not_found",
                        })
                else:
                    results["skipped"] += 1
                    results["details"].append({
                        "task_id": task_id,
                        "status": "skipped",
                        "reason": "unknown_task",
                    })

            except Exception as retry_error:
                logger.error(
                    "Failed to retry dead letter task",
                    task_id=task_id,
                    error=str(retry_error),
                )
                results["failed"] += 1
                results["details"].append({
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(retry_error),
                })

                # Put back in queue if retry failed
                client.lpush("celery:dead_letter_queue", json.dumps(entry))

        results["processed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error("Failed to process dead letter queue", error=str(e))
        raise self.retry(exc=e, countdown=300)

    finally:
        client.close()

    return results


@celery_app.task
def get_dead_letter_stats() -> dict[str, Any]:
    """Get statistics about the dead letter queue.

    Returns:
        Statistics including queue size, task breakdown, etc.
    """
    client = get_redis_client()

    try:
        queue_length = client.llen("celery:dead_letter_queue")
        unique_tasks = client.scard("celery:dead_letter_tasks")
        total_failures = int(client.get("celery:dead_letter_count") or 0)

        # Sample recent entries to get task breakdown
        recent_entries = []
        task_counts = {}

        for i in range(min(100, queue_length)):
            entry = client.lindex("celery:dead_letter_queue", i)
            if entry:
                data = json.loads(entry)
                task_name = data.get("task_name", "unknown")
                task_counts[task_name] = task_counts.get(task_name, 0) + 1

                if i < 10:  # Only include details for most recent 10
                    recent_entries.append({
                        "task_id": data.get("task_id"),
                        "task_name": task_name,
                        "exception_type": data.get("exception_type"),
                        "failed_at": data.get("failed_at"),
                    })

        return {
            "queue_length": queue_length,
            "unique_failed_tasks": unique_tasks,
            "total_failures": total_failures,
            "task_breakdown": task_counts,
            "recent_failures": recent_entries,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    finally:
        client.close()


@celery_app.task
def cleanup_dead_letter_queue(max_age_days: int = 7) -> dict[str, Any]:
    """Clean up old entries from the dead letter queue.

    Args:
        max_age_days: Remove entries older than this many days

    Returns:
        Cleanup summary
    """
    client = get_redis_client()
    removed = 0
    kept = 0

    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        queue_length = client.llen("celery:dead_letter_queue")

        # Process all entries
        entries_to_keep = []

        for _ in range(queue_length):
            entry = client.rpop("celery:dead_letter_queue")
            if entry is None:
                break

            data = json.loads(entry)
            failed_at = data.get("failed_at")

            if failed_at:
                try:
                    failed_time = datetime.fromisoformat(failed_at.replace("Z", "+00:00"))
                    if failed_time >= cutoff_time:
                        entries_to_keep.append(entry)
                        kept += 1
                    else:
                        # Remove from tracking set
                        client.srem("celery:dead_letter_tasks", data.get("task_id"))
                        removed += 1
                except (ValueError, TypeError):
                    entries_to_keep.append(entry)
                    kept += 1
            else:
                # Keep entries without timestamp
                entries_to_keep.append(entry)
                kept += 1

        # Re-add kept entries to queue
        for entry in entries_to_keep:
            client.lpush("celery:dead_letter_queue", entry)

        logger.info(
            "Dead letter queue cleanup completed",
            removed=removed,
            kept=kept,
        )

        return {
            "removed": removed,
            "kept": kept,
            "cutoff_days": max_age_days,
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        }

    finally:
        client.close()


@celery_app.task
def retry_specific_task(task_id: str) -> dict[str, Any]:
    """Retry a specific task from the dead letter queue by ID.

    Args:
        task_id: The ID of the failed task to retry

    Returns:
        Result of the retry attempt
    """
    client = get_redis_client()

    try:
        queue_length = client.llen("celery:dead_letter_queue")

        for i in range(queue_length):
            entry = client.lindex("celery:dead_letter_queue", i)
            if entry:
                data = json.loads(entry)
                if data.get("task_id") == task_id:
                    task_name = data.get("task_name")

                    if task_name and task_name != "unknown":
                        task = celery_app.tasks.get(task_name)
                        if task:
                            args = data.get("args", [])
                            kwargs = data.get("kwargs", {})

                            # Re-queue the task
                            result = task.apply_async(
                                args=args,
                                kwargs=kwargs,
                                queue="default",
                            )

                            # Remove from DLQ
                            client.lrem("celery:dead_letter_queue", 1, entry)
                            client.srem("celery:dead_letter_tasks", task_id)

                            logger.info(
                                "Specific task retried from DLQ",
                                original_task_id=task_id,
                                new_task_id=result.id,
                            )

                            return {
                                "success": True,
                                "original_task_id": task_id,
                                "new_task_id": result.id,
                                "task_name": task_name,
                            }

        return {
            "success": False,
            "error": f"Task {task_id} not found in dead letter queue",
        }

    finally:
        client.close()
