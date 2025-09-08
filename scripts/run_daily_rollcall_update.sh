#!/bin/bash

# Daily roll call and bill metadata update script
# This script should be run from cron daily

# Set the working directory
cd /home/jmknapp/congressional-coalitions

# Set up logging
LOG_DIR="/home/jmknapp/congressional-coalitions/logs"
mkdir -p "$LOG_DIR"

# Create log file with timestamp
LOG_FILE="$LOG_DIR/daily_rollcall_update_$(date +%Y%m%d_%H%M%S).log"

echo "Starting daily roll call and bill update at $(date)" | tee -a "$LOG_FILE"

# Run the roll call and bill update script
venv/bin/python scripts/daily_rollcall_bill_update.py \
    --congress 119 \
    --chamber house \
    --days-back 7 \
    2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ $? -eq 0 ]; then
    echo "Daily roll call and bill update completed successfully at $(date)" | tee -a "$LOG_FILE"
else
    echo "Daily roll call and bill update failed at $(date)" | tee -a "$LOG_FILE"
    # You could add email notification here if needed
fi

# Clean up old log files (keep last 14 days)
find "$LOG_DIR" -name "daily_rollcall_update_*.log" -mtime +14 -delete

echo "Daily roll call update script finished at $(date)" | tee -a "$LOG_FILE"
