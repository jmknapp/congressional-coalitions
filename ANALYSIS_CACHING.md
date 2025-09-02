# Analysis Caching System

## Overview

The Congressional Coalition Tracker now uses a sophisticated caching system to provide fast analysis results. Instead of running analysis on-demand from the UI (which could take 30+ seconds), analysis is pre-computed hourly and cached for instant retrieval.

## How It Works

### 1. **Persistent File-Based Cache**
- Uses Flask-Caching with filesystem backend
- Cache directory: `/tmp/congressional_cache`
- Survives app restarts (unlike in-memory cache)
- Analysis results cached for 6 hours

### 2. **Cron-Based Updates**
- Hourly cron job runs analysis automatically
- Script: `scripts/cron_update_analysis.py`
- Logs to: `/tmp/analysis_cron.log`
- Ensures cache is always fresh

### 3. **Smart API Endpoint**
- `/api/analysis/<congress>/<chamber>` endpoint checks cache first
- If cached results exist, serves instantly
- If no cache, runs fresh analysis and caches results
- Includes metadata about cache status and timestamps

## Files Modified

### `app.py`
- Changed cache from `simple` (in-memory) to `filesystem` (persistent)
- Enhanced `/api/analysis/<congress>/<chamber>` endpoint with cache logic
- Added cache metadata (cached status, timestamps)

### `scripts/cron_update_analysis.py` (New)
- Standalone script for cron execution
- Makes HTTP requests to Flask app to trigger analysis
- Clears old cache and generates fresh results
- Comprehensive logging and error handling
- No dependency on complex imports (pandas, etc.)

### `scripts/setup_cron.sh` (New)
- Automates cron job installation
- Creates hourly schedule: `0 * * * *`
- Provides helpful management commands

## Usage

### Manual Analysis Update
```bash
cd /home/jmknapp/congressional-coalitions
python3 scripts/cron_update_analysis.py --congress 119 --chamber house
```

### Check Cron Job Status
```bash
crontab -l  # View installed cron jobs
tail -f /tmp/analysis_cron.log  # View logs
```

### Clear Cache Manually
```bash
curl http://localhost:5000/api/cache/clear
```

### Test Cache Status
```bash
curl "http://localhost:5000/api/analysis/119/house" | grep '"cached"'
```

## Benefits

### 🚀 **Performance**
- **Before**: 30-40 seconds for analysis
- **After**: < 1 second for cached results

### 🔄 **Reliability**
- Analysis runs automatically every hour
- No more timeouts on UI analysis requests
- Persistent cache survives server restarts

### 📊 **User Experience**
- Instant loading of analysis results
- No more waiting for complex calculations
- Analysis always up-to-date (max 1 hour old)

### 🔧 **Maintainability**
- Centralized analysis execution
- Comprehensive logging
- Easy to monitor and debug

## Cache Lifecycle

1. **Hour 0:00** - Cron job runs
2. **Clear** existing cache
3. **Generate** fresh analysis (30-40 seconds)
4. **Cache** results for 6 hours
5. **Serve** instant results for next hour
6. **Repeat** every hour

## Monitoring

### Check if cache is working:
```bash
# Should show "cached": true for subsequent requests
curl -s "http://localhost:5000/api/analysis/119/house" | grep cached
```

### Monitor cron execution:
```bash
# View recent log entries
tail -20 /tmp/analysis_cron.log

# Follow live updates
tail -f /tmp/analysis_cron.log
```

### Verify cron job is scheduled:
```bash
crontab -l | grep cron_update_analysis
```

## Troubleshooting

### Analysis not updating?
- Check if Flask app is running: `curl http://localhost:5000/api/summary`
- Check cron job logs: `tail /tmp/analysis_cron.log`
- Verify cron service: `systemctl status cron`

### Cache not persisting?
- Check cache directory: `ls -la /tmp/congressional_cache/`
- Verify filesystem cache in `app.py` config

### Performance issues?
- Old cache automatically expires after 6 hours
- Manual cache clear: `curl http://localhost:5000/api/cache/clear`
- Check disk space: `df -h /tmp`

## Configuration

### Change cache duration:
Edit timeout values in:
- `app.py`: Line 441 (cache.set timeout)
- `scripts/cron_update_analysis.py`: Comments and logs

### Change analysis frequency:
```bash
crontab -e  # Edit cron schedule
# Current: 0 * * * * (every hour)
# Daily: 0 6 * * * (6 AM daily)
# Every 30 min: */30 * * * *
```

## Security Notes

- Cache files stored in `/tmp` (temporary directory)
- No sensitive data in cache (only analysis results)
- HTTP requests to localhost only (not exposed externally)
- Logs may contain analysis metadata but no personal info
