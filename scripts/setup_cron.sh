#!/bin/bash

# Setup cron jobs for daily congressional data updates

# Get the current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up cron jobs for congressional data updates..."
echo "Project directory: $PROJECT_DIR"

# Create the cron job entry
CRON_JOB="0 2 * * * cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python $PROJECT_DIR/scripts/update_sponsors_cosponsors_daily.py --congress 119 --max-bills 50 --api-key ZsV6bo6tacezcFF8zhz63LknnHlu9XDNn7n8udeC >> $PROJECT_DIR/logs/daily_update.log 2>&1"

echo "Cron job to be added:"
echo "$CRON_JOB"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "update_sponsors_cosponsors_daily.py"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "update_sponsors_cosponsors_daily.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Cron job added successfully!"
echo ""
echo "Current cron jobs:"
crontab -l

echo ""
echo "The daily update will run at 2:00 AM every day."
echo "Logs will be written to: $PROJECT_DIR/logs/daily_update.log"
echo ""
echo "To manually run the update:"
echo "cd $PROJECT_DIR && venv/bin/python scripts/update_sponsors_cosponsors_daily.py --congress 119 --max-bills 50 --api-key ZsV6bo6tacezcFF8zhz63LknnHlu9XDNn7n8udeC"
