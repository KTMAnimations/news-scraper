#!/bin/bash
set -e

# Database backup script for news-scraper
# Usage: ./backup.sh
# Requires: restic, B2/S3 credentials

BACKUP_NAME="news-scraper-$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/tmp/backups"
RESTIC_REPOSITORY=${RESTIC_REPOSITORY:-"b2:your-bucket:news-scraper-backups"}

# Create backup directory
mkdir -p ${BACKUP_DIR}

echo "=== Starting backup: ${BACKUP_NAME} ==="

# Backup PostgreSQL/TimescaleDB
echo "Backing up PostgreSQL..."
docker exec $(docker ps -qf "name=postgres") \
    pg_dump -U newsuser -d newsdb -Fc > ${BACKUP_DIR}/postgres.dump

# Backup Redis (RDB snapshot)
echo "Backing up Redis..."
docker exec $(docker ps -qf "name=redis") redis-cli BGSAVE
sleep 5
docker cp $(docker ps -qf "name=redis"):/data/dump.rdb ${BACKUP_DIR}/redis.rdb

# Compress backups
echo "Compressing backups..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz -C ${BACKUP_DIR} postgres.dump redis.rdb

# Upload to remote storage using restic
echo "Uploading to remote storage..."
restic -r ${RESTIC_REPOSITORY} backup ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz \
    --tag "database" \
    --tag "$(date +%Y-%m-%d)"

# Cleanup local backup files
rm -rf ${BACKUP_DIR}

# Prune old backups (keep 7 daily, 4 weekly, 3 monthly)
echo "Pruning old backups..."
restic -r ${RESTIC_REPOSITORY} forget \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 3 \
    --prune

echo "=== Backup complete: ${BACKUP_NAME} ==="
