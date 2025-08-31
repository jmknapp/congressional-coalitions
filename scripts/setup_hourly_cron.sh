#!/bin/bash

# Script to set up hourly cron job for congressional data updates

# Make the update script executable
chmod +x scripts/cron_hourly_update.sh

# Create logs directory
mkdir -p logs

# Get the full path to the update script
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cron_hourly_update.sh"

echo "Setting up hourly cron job..."
echo "Script path: $SCRIPT_PATH"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "cron_hourly_update.sh"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "cron_hourly_update.sh" | crontab -
fi

# Add new cron job (run every hour at minute 0)
(crontab -l 2>/dev/null; echo "0 * * * * $SCRIPT_PATH") | crontab -

echo "Hourly cron job has been set up!"
echo "The script will run every hour at the top of the hour."
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -e"
echo "  (then delete the line with cron_hourly_update.sh)"
echo ""
echo "Logs will be written to: logs/hourly_update_YYYYMMDD_HHMMSS.log"
