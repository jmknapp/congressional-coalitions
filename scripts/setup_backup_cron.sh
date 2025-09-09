#!/bin/bash

# Setup automated database backups with cron
# This script sets up daily backups at 2 AM

BACKUP_SCRIPT="/home/jmknapp/congressional-coalitions/scripts/backup_database.py"
CRON_JOB="0 2 * * * cd /home/jmknapp/congressional-coalitions && python3 $BACKUP_SCRIPT >> /home/jmknapp/congressional-coalitions/backups/logs/cron_backup.log 2>&1"

echo "Setting up automated database backups..."

# Create backup directory and logs directory
mkdir -p /home/jmknapp/congressional-coalitions/backups/logs

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "backup_database.py"; then
    echo "Backup cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "backup_database.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Automated backup setup completed!"
echo "Backups will run daily at 2:00 AM"
echo "Logs will be saved to: /home/jmknapp/congressional-coalitions/backups/logs/cron_backup.log"
echo ""
echo "To view current cron jobs: crontab -l"
echo "To remove backup cron job: crontab -e (then delete the backup line)"

