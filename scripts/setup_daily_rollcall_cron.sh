#!/bin/bash

# Script to set up daily cron job for roll call and bill metadata updates

# Make the update script executable
chmod +x scripts/run_daily_rollcall_update.sh

# Create logs directory
mkdir -p logs

# Get the full path to the update script
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_daily_rollcall_update.sh"

echo "Setting up daily roll call update cron job..."
echo "Script path: $SCRIPT_PATH"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_daily_rollcall_update.sh"; then
    echo "Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "run_daily_rollcall_update.sh" | crontab -
fi

# Add new cron job (run daily at 6 AM)
(crontab -l 2>/dev/null; echo "0 6 * * * $SCRIPT_PATH") | crontab -

echo "Daily roll call update cron job has been set up!"
echo "The script will run daily at 6:00 AM."
echo ""
echo "To view current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -e"
echo "  (then delete the line with run_daily_rollcall_update.sh)"
echo ""
echo "Logs will be written to: logs/daily_rollcall_update_YYYYMMDD_HHMMSS.log"
echo ""
echo "Current cron jobs:"
crontab -l
