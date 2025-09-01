#!/bin/bash

# Hourly update script for congressional sponsors and co-sponsors
# This script should be run from cron every hour

# Set the working directory
cd /home/jmknapp/congressional-coalitions

# Set up logging
LOG_DIR="/home/jmknapp/congressional-coalitions/logs"
mkdir -p "$LOG_DIR"

# Create log file with timestamp
LOG_FILE="$LOG_DIR/hourly_update_$(date +%Y%m%d_%H%M%S).log"

# API key (you may want to move this to an environment variable)
API_KEY="ZsV6bo6tacezcFF8zhz63LknnHlu9XDNn7n8udeC"

echo "Starting hourly update at $(date)" | tee -a "$LOG_FILE"

# Run the update script
venv/bin/python scripts/load_house_sponsors_cosponsors.py \
    --congress 119 \
    --limit 200 \
    --skip-processed \
    --api-key "$API_KEY" \
    2>&1 | tee -a "$LOG_FILE"

# Check exit status
if [ $? -eq 0 ]; then
    echo "Hourly update completed successfully at $(date)" | tee -a "$LOG_FILE"
else
    echo "Hourly update failed at $(date)" | tee -a "$LOG_FILE"
    # You could add email notification here if needed
fi

# Pre-calculate ideological profiles (runs after sponsor/cosponsor updates)
echo "Starting ideological profile pre-calculation at $(date)" | tee -a "$LOG_FILE"

venv/bin/python scripts/precalculate_ideology.py 2>&1 | tee -a "$LOG_FILE"

# Check exit status for ideological calculation
if [ $? -eq 0 ]; then
    echo "Ideological profile pre-calculation completed successfully at $(date)" | tee -a "$LOG_FILE"
else
    echo "Ideological profile pre-calculation failed at $(date)" | tee -a "$LOG_FILE"
fi

# Clean up old log files (keep last 7 days)
find "$LOG_DIR" -name "hourly_update_*.log" -mtime +7 -delete

echo "Hourly update script finished at $(date)" | tee -a "$LOG_FILE"
