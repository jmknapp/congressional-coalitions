#!/bin/bash

# Setup cron job for Congressional Coalition Analysis
# This script sets up an hourly cron job to update analysis cache

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CRON_SCRIPT="$SCRIPT_DIR/cron_update_analysis.py"

echo "Setting up cron job for Congressional Coalition Analysis..."
echo "Project directory: $PROJECT_DIR"
echo "Cron script: $CRON_SCRIPT"

# Create cache directory if it doesn't exist
mkdir -p /tmp/congressional_cache

# Create cron job entry
CRON_ENTRY="0 * * * * cd $PROJECT_DIR && python3 $CRON_SCRIPT --congress 119 --chamber house >> /tmp/analysis_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "cron_update_analysis.py"; then
    echo "Cron job already exists. Updating..."
    # Remove existing entry and add new one
    (crontab -l 2>/dev/null | grep -v "cron_update_analysis.py"; echo "$CRON_ENTRY") | crontab -
else
    echo "Adding new cron job..."
    # Add new entry to existing crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

echo "Cron job configured successfully!"
echo "The analysis will run every hour and cache results for quick retrieval."
echo ""
echo "To check the cron job:"
echo "  crontab -l"
echo ""
echo "To view logs:"
echo "  tail -f /tmp/analysis_cron.log"
echo ""
echo "To test the script manually:"
echo "  cd $PROJECT_DIR && python3 $CRON_SCRIPT"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v 'cron_update_analysis.py' | crontab -"