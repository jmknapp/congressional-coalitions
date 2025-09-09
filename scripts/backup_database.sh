#!/bin/bash

# Database Backup Script for Congressional Coalitions
# Simple shell script version for manual backups

# Database configuration
DB_HOST="localhost"
DB_USER="congressional"
DB_PASS="congressional123"
DB_NAME="congressional_coalitions"

# Backup configuration
BACKUP_DIR="/home/jmknapp/congressional-coalitions/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="congressional_coalitions_backup_${TIMESTAMP}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting database backup..."
echo "Database: $DB_NAME"
echo "Backup file: $BACKUP_DIR/$BACKUP_FILE"

# Create backup with mysqldump and compress
mysqldump \
    --host="$DB_HOST" \
    --user="$DB_USER" \
    --password="$DB_PASS" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --hex-blob \
    --complete-insert \
    --extended-insert \
    --lock-tables=false \
    --no-tablespaces \
    --skip-warnings \
    "$DB_NAME" 2>/dev/null | gzip > "$BACKUP_DIR/$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ]; then
    echo "Backup completed successfully!"
    echo "Backup size: $(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)"
    echo "Backup location: $BACKUP_DIR/$BACKUP_FILE"
else
    echo "Backup failed!"
    exit 1
fi

# Optional: Clean up old backups (keep last 30 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "congressional_coalitions_backup_*.sql.gz" -mtime +30 -delete
echo "Cleanup completed."
