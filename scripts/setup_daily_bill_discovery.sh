#!/bin/bash

# Setup daily cron job for discovering new bills
# This script sets up a daily cron job to discover and add new bills

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DAILY_SCRIPT="$SCRIPT_DIR/enhanced_daily_update.py"

echo "Setting up daily cron job for new bill discovery..."
echo "Project directory: $PROJECT_DIR"
echo "Daily script: $DAILY_SCRIPT"

# Create cache directory if it doesn't exist
mkdir -p /tmp/congressional_cache

# Create daily cron job entry (runs at 6 AM daily)
CRON_ENTRY="0 6 * * * cd $PROJECT_DIR && venv/bin/python $DAILY_SCRIPT --congress 119 --max-bills 100 >> /tmp/enhanced_bill_discovery.log 2>&1"

# Check if daily cron job already exists
if crontab -l 2>/dev/null | grep -q "enhanced_daily_update.py\|update_sponsors_cosponsors_daily.py"; then
    echo "Daily bill discovery cron job already exists. Updating..."
    # Remove existing entry and add new one
    (crontab -l 2>/dev/null | grep -v "enhanced_daily_update.py\|update_sponsors_cosponsors_daily.py"; echo "$CRON_ENTRY") | crontab -
else
    echo "Adding new daily bill discovery cron job..."
    # Add new entry to existing crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

echo "Daily bill discovery cron job configured successfully!"
echo "The job will run daily at 6 AM to discover and add new bills."
echo ""
echo "To check the cron jobs:"
echo "  crontab -l"
echo ""
echo "To view daily discovery logs:"
echo "  tail -f /tmp/enhanced_bill_discovery.log"
echo ""
echo "To test the script manually:"
echo "  cd $PROJECT_DIR && venv/bin/python $DAILY_SCRIPT --congress 119 --max-bills 50"
echo ""
echo "To remove the daily job:"
echo "  crontab -l | grep -v 'enhanced_daily_update.py' | crontab -"
