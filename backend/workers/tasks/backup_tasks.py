"""Backup tasks for database maintenance and disaster recovery."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from backend.config import settings
from backend.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)
def backup_database_task(self, backup_dir: str | None = None) -> dict[str, Any]:
    """Create a compressed backup of the TimescaleDB database.

    This task executes the backup-db.sh script which:
    - Creates a pg_dump backup of the database
    - Compresses the backup with gzip
    - Timestamps the backup file
    - Rotates old backups (keeps last 7 days by default)

    Args:
        backup_dir: Optional backup directory override. Defaults to /backups.

    Returns:
        Dictionary containing backup status and metadata.
    """
    backup_dir = backup_dir or os.getenv("BACKUP_DIR", "/backups")
    script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "backup-db.sh"

    # Fallback to container path if local path doesn't exist
    if not script_path.exists():
        script_path = Path("/app/scripts/backup-db.sh")

    logger.info(
        "Starting database backup task",
        backup_dir=backup_dir,
        script_path=str(script_path),
    )

    # Parse database URL to extract connection parameters
    db_url = str(settings.database_url)
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    # We need to extract these for the backup script

    try:
        # Extract database connection details from URL
        # Remove driver prefix
        db_url_clean = db_url.replace("postgresql+asyncpg://", "postgresql://")

        # Parse using urllib
        from urllib.parse import urlparse
        parsed = urlparse(db_url_clean)

        db_host = parsed.hostname or "postgres"
        db_port = str(parsed.port or 5432)
        db_user = parsed.username or "newsuser"
        db_pass = parsed.password or "newspass"
        db_name = parsed.path.lstrip("/") or "newsdb"

        # Set environment variables for the script
        env = os.environ.copy()
        env.update({
            "PGHOST": db_host,
            "PGPORT": db_port,
            "PGUSER": db_user,
            "PGPASSWORD": db_pass,
            "PGDATABASE": db_name,
            "BACKUP_DIR": backup_dir,
            "BACKUP_RETENTION_DAYS": os.getenv("BACKUP_RETENTION_DAYS", "7"),
        })

        # Ensure backup directory exists
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        # Execute the backup script
        result = subprocess.run(
            [str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            logger.error(
                "Backup script failed",
                returncode=result.returncode,
                stderr=result.stderr,
            )
            raise Exception(f"Backup script failed: {result.stderr}")

        # Parse the JSON output from the script
        import json
        output_lines = result.stdout.strip().split("\n")
        # The last part should be the JSON summary
        json_output = ""
        in_json = False
        for line in output_lines:
            if line.strip().startswith("{"):
                in_json = True
            if in_json:
                json_output += line

        if json_output:
            backup_result = json.loads(json_output)
        else:
            backup_result = {
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            "Database backup completed successfully",
            backup_file=backup_result.get("file"),
            size=backup_result.get("size"),
            duration=backup_result.get("duration_seconds"),
        )

        return {
            "task": "backup_database",
            "status": "success",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **backup_result,
        }

    except subprocess.TimeoutExpired:
        logger.error("Backup script timed out")
        raise self.retry(exc=Exception("Backup timed out"), countdown=300)

    except json.JSONDecodeError as e:
        logger.warning("Could not parse backup script JSON output", error=str(e))
        # Backup may still have succeeded
        return {
            "task": "backup_database",
            "status": "success",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "note": "Backup completed but JSON output could not be parsed",
        }

    except Exception as e:
        logger.error("Database backup failed", error=str(e))
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True)
def cleanup_old_backups_task(
    self,
    backup_dir: str | None = None,
    retention_days: int = 7
) -> dict[str, Any]:
    """Clean up old backup files beyond retention period.

    This task can be run independently to manage backup storage.

    Args:
        backup_dir: Directory containing backups. Defaults to /backups.
        retention_days: Number of days to retain backups. Defaults to 7.

    Returns:
        Dictionary containing cleanup results.
    """
    backup_dir = backup_dir or os.getenv("BACKUP_DIR", "/backups")
    backup_path = Path(backup_dir)

    logger.info(
        "Starting backup cleanup task",
        backup_dir=backup_dir,
        retention_days=retention_days,
    )

    if not backup_path.exists():
        logger.warning("Backup directory does not exist", backup_dir=backup_dir)
        return {
            "task": "cleanup_old_backups",
            "status": "skipped",
            "reason": "Backup directory does not exist",
        }

    deleted_files = []
    total_freed_bytes = 0
    cutoff_time = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)

    for backup_file in backup_path.glob("newsdb_backup_*.sql.gz"):
        file_mtime = backup_file.stat().st_mtime
        if file_mtime < cutoff_time:
            file_size = backup_file.stat().st_size
            try:
                backup_file.unlink()
                deleted_files.append(backup_file.name)
                total_freed_bytes += file_size
                logger.info("Deleted old backup", file=backup_file.name)
            except OSError as e:
                logger.error("Failed to delete backup", file=backup_file.name, error=str(e))

    # Calculate remaining backups
    remaining_backups = list(backup_path.glob("newsdb_backup_*.sql.gz"))

    result = {
        "task": "cleanup_old_backups",
        "status": "success",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "freed_bytes": total_freed_bytes,
        "freed_mb": round(total_freed_bytes / (1024 * 1024), 2),
        "remaining_backups": len(remaining_backups),
    }

    logger.info(
        "Backup cleanup completed",
        deleted_count=len(deleted_files),
        freed_mb=result["freed_mb"],
    )

    return result


@celery_app.task(bind=True)
def verify_backup_task(self, backup_file: str) -> dict[str, Any]:
    """Verify integrity of a backup file.

    This task checks that a backup file:
    - Exists and is readable
    - Is a valid gzip file
    - Contains valid SQL when decompressed (basic check)

    Args:
        backup_file: Path to the backup file to verify.

    Returns:
        Dictionary containing verification results.
    """
    import gzip

    logger.info("Verifying backup file", backup_file=backup_file)

    backup_path = Path(backup_file)

    if not backup_path.exists():
        return {
            "task": "verify_backup",
            "status": "failed",
            "reason": "Backup file does not exist",
            "file": backup_file,
        }

    try:
        file_size = backup_path.stat().st_size

        # Check if file is empty
        if file_size == 0:
            return {
                "task": "verify_backup",
                "status": "failed",
                "reason": "Backup file is empty",
                "file": backup_file,
            }

        # Try to decompress and read a portion of the file
        with gzip.open(backup_path, "rt") as f:
            # Read first 1KB to verify it's valid SQL
            header = f.read(1024)

            # Basic sanity check - should contain SQL-like content
            sql_indicators = ["--", "CREATE", "INSERT", "TABLE", "SET", "SELECT"]
            if not any(indicator in header.upper() for indicator in sql_indicators):
                return {
                    "task": "verify_backup",
                    "status": "warning",
                    "reason": "File may not contain valid SQL",
                    "file": backup_file,
                    "size_bytes": file_size,
                }

        logger.info("Backup verification passed", backup_file=backup_file)

        return {
            "task": "verify_backup",
            "status": "success",
            "file": backup_file,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    except gzip.BadGzipFile:
        return {
            "task": "verify_backup",
            "status": "failed",
            "reason": "Invalid gzip file",
            "file": backup_file,
        }
    except Exception as e:
        logger.error("Backup verification failed", error=str(e))
        return {
            "task": "verify_backup",
            "status": "failed",
            "reason": str(e),
            "file": backup_file,
        }


@celery_app.task(bind=True)
def list_backups_task(self, backup_dir: str | None = None) -> dict[str, Any]:
    """List all available database backups.

    Args:
        backup_dir: Directory containing backups. Defaults to /backups.

    Returns:
        Dictionary containing list of backup files and metadata.
    """
    backup_dir = backup_dir or os.getenv("BACKUP_DIR", "/backups")
    backup_path = Path(backup_dir)

    if not backup_path.exists():
        return {
            "task": "list_backups",
            "status": "success",
            "backup_dir": backup_dir,
            "backups": [],
            "total_count": 0,
        }

    backups = []
    total_size = 0

    for backup_file in sorted(
        backup_path.glob("newsdb_backup_*.sql.gz"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    ):
        stat = backup_file.stat()
        backups.append({
            "name": backup_file.name,
            "path": str(backup_file),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat(),
        })
        total_size += stat.st_size

    return {
        "task": "list_backups",
        "status": "success",
        "backup_dir": backup_dir,
        "backups": backups,
        "total_count": len(backups),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
    }
