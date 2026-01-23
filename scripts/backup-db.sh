#!/bin/bash
# =============================================================================
# TimescaleDB Backup Script
# =============================================================================
# This script creates compressed backups of the TimescaleDB database with
# timestamp-based naming and automatic rotation (keeps last 7 days).
#
# Usage:
#   ./backup-db.sh [options]
#
# Options:
#   -h, --host       Database host (default: localhost)
#   -p, --port       Database port (default: 5432)
#   -U, --user       Database user (default: newsuser)
#   -d, --database   Database name (default: newsdb)
#   -o, --output     Backup output directory (default: /backups)
#   -r, --retention  Number of days to retain backups (default: 7)
#   --help           Show this help message
#
# Environment Variables (override defaults):
#   PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
#   BACKUP_DIR, BACKUP_RETENTION_DAYS
# =============================================================================

set -euo pipefail

# Color output for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_USER="${PGUSER:-newsuser}"
DB_NAME="${PGDATABASE:-newsdb}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# Timestamp format for backup files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/newsdb_backup_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${LOG_FILE}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "${LOG_FILE}"
}

show_help() {
    head -30 "$0" | tail -25
    exit 0
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            DB_HOST="$2"
            shift 2
            ;;
        -p|--port)
            DB_PORT="$2"
            shift 2
            ;;
        -U|--user)
            DB_USER="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        -o|--output)
            BACKUP_DIR="$2"
            BACKUP_FILE="${BACKUP_DIR}/newsdb_backup_${TIMESTAMP}.sql.gz"
            LOG_FILE="${BACKUP_DIR}/backup.log"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

log_info "=== Starting TimescaleDB Backup ==="
log_info "Host: ${DB_HOST}:${DB_PORT}"
log_info "Database: ${DB_NAME}"
log_info "Output: ${BACKUP_FILE}"
log_info "Retention: ${RETENTION_DAYS} days"

# Check if pg_dump is available
if ! command -v pg_dump &> /dev/null; then
    log_error "pg_dump command not found. Please install PostgreSQL client tools."
    exit 1
fi

# Check database connectivity
log_info "Checking database connectivity..."
if ! PGPASSWORD="${PGPASSWORD:-newspass}" pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" &> /dev/null; then
    log_error "Cannot connect to database at ${DB_HOST}:${DB_PORT}"
    exit 1
fi
log_info "Database connection verified."

# Create backup with pg_dump
log_info "Creating database backup..."
BACKUP_START=$(date +%s)

# Use pg_dump with compression
# --no-owner: Don't output ownership commands (useful for restoring to different user)
# --no-acl: Don't output privilege commands
# --format=custom is better for large DBs, but we use plain for compatibility
# Using gzip compression for smaller file sizes
if PGPASSWORD="${PGPASSWORD:-newspass}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --no-owner \
    --no-acl \
    --verbose \
    2>> "${LOG_FILE}" | gzip > "${BACKUP_FILE}"; then

    BACKUP_END=$(date +%s)
    BACKUP_DURATION=$((BACKUP_END - BACKUP_START))
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

    log_info "Backup completed successfully!"
    log_info "Duration: ${BACKUP_DURATION} seconds"
    log_info "File size: ${BACKUP_SIZE}"
else
    log_error "Backup failed!"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Verify backup file exists and is not empty
if [[ ! -s "${BACKUP_FILE}" ]]; then
    log_error "Backup file is empty or does not exist!"
    exit 1
fi

# Rotate old backups (delete files older than retention period)
log_info "Rotating old backups (keeping last ${RETENTION_DAYS} days)..."
DELETED_COUNT=0
while IFS= read -r -d '' old_backup; do
    rm -f "${old_backup}"
    log_info "Deleted old backup: $(basename "${old_backup}")"
    ((DELETED_COUNT++))
done < <(find "${BACKUP_DIR}" -name "newsdb_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -print0 2>/dev/null)

if [[ ${DELETED_COUNT} -gt 0 ]]; then
    log_info "Removed ${DELETED_COUNT} old backup(s)."
else
    log_info "No old backups to remove."
fi

# List current backups
log_info "Current backups in ${BACKUP_DIR}:"
ls -lh "${BACKUP_DIR}"/newsdb_backup_*.sql.gz 2>/dev/null | while read line; do
    log_info "  ${line}"
done

# Calculate total backup storage used
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" 2>/dev/null | cut -f1)
log_info "Total backup storage used: ${TOTAL_SIZE}"

log_info "=== Backup Complete ==="

# Output JSON summary for programmatic use
cat << EOF
{
    "status": "success",
    "timestamp": "${TIMESTAMP}",
    "file": "${BACKUP_FILE}",
    "size": "${BACKUP_SIZE}",
    "duration_seconds": ${BACKUP_DURATION},
    "retention_days": ${RETENTION_DAYS},
    "deleted_old_backups": ${DELETED_COUNT}
}
EOF
