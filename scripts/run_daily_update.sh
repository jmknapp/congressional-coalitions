#!/usr/bin/env ksh
# scripts/run_daily_update.sh
# Purpose: daily job wrapper with persistent counter, exclusive lock, and logging.
# Shell   : ksh (KornShell)

# -----------------------------
# Config (edit as you like)
# -----------------------------
# Resolve paths relative to this script
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

STATE_FILE="$SCRIPT_DIR/.run_daily_update.counter"
LOCK_NAME=".run_daily_update.lock"   # file (flock) or dir (mkdir) based on availability
LOCK_PATH="$SCRIPT_DIR/$LOCK_NAME"

LOG_DIR="$PROJECT_ROOT/logs"
DATE_TAG=$(date '+%F')
LOG_FILE="$LOG_DIR/daily_${DATE_TAG}.log"
KEEP_LOG_DAYS=14                     # auto-prune logs older than N days (set 0 to disable)

# If your job needs a venv or PATH tweaks, do them here:
# export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
# . "$PROJECT_ROOT/myenv/bin/activate"  # example for Python venv

# -----------------------------
# Helpers
# -----------------------------
log() {
  # timestamp + level + message
  # usage: log INFO "message"
  typeset LEVEL="$1"; shift
  typeset MSG="$*"
  printf '%s [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$LEVEL" "$MSG"
}

die() {
  log ERROR "$*"
  exit 1
}

# Ensure log dir, then redirect all output to LOG_FILE (keeps console if you use 'tee')
mkdir -p "$LOG_DIR" || die "Cannot create log dir: $LOG_DIR"
# To log only to file:
exec >>"$LOG_FILE" 2>&1
# If you prefer to see live output in console too, replace the line above with:
# exec > >(tee -a "$LOG_FILE") 2>&1

log INFO "------------------------------------------------------------"
log INFO "Starting daily update script"
log INFO "Project root: $PROJECT_ROOT"
log INFO "Script dir  : $SCRIPT_DIR"
log INFO "Log file    : $LOG_FILE"

# Prune old logs (optional)
if [ "${KEEP_LOG_DAYS:-0}" -gt 0 ]; then
  find "$LOG_DIR" -type f -name 'daily_*.log' -mtime +"$KEEP_LOG_DAYS" -print -delete \
    | while read f; do log INFO "Pruned old log: $f"; done
fi

# -----------------------------
# Single-instance lock
# -----------------------------
CLEANUP_LOCK() {
  # Release flock FD 9 if in use
  if [ -n "$USED_FLOCK" ]; then
    # shellcheck disable=SC3045
    exec 9>&-  # close FD 9
    USED_FLOCK=""
    # leaving the lockfile itself is typical with flock; it’s just a handle
  fi
  # Remove mkdir-style lock dir if we created it
  if [ -n "$USED_MKDIR_LOCK" ] && [ -d "$LOCK_PATH" ]; then
    rmdir "$LOCK_PATH" 2>/dev/null
    USED_MKDIR_LOCK=""
  fi
}
trap CLEANUP_LOCK EXIT INT TERM

USED_FLOCK=""
USED_MKDIR_LOCK=""

if command -v flock >/dev/null 2>&1; then
  # flock-based lock on a file
  log INFO "Acquiring flock lock on $LOCK_PATH"
  exec 9>"$LOCK_PATH" || die "Cannot open lock file: $LOCK_PATH"
  # shellcheck disable=SC3045
  flock -n 9 || { log WARN "Another instance is running; exiting."; exit 1; }
  USED_FLOCK="1"
else
  # mkdir-based fallback (atomic on POSIX filesystems)
  log INFO "Acquiring mkdir lock at $LOCK_PATH"
  if ! mkdir "$LOCK_PATH" 2>/dev/null; then
    log WARN "Another instance is running; exiting."
    exit 1
  fi
  USED_MKDIR_LOCK="1"
fi

# -----------------------------
# Persistent run counter
# -----------------------------
typeset -i RUN_NUM=0
if [ -r "$STATE_FILE" ]; then
  # Robust read that won’t kill the script if empty or invalid
  if IFS= read RUN_NUM < "$STATE_FILE"; then
    case "$RUN_NUM" in
      ''|*[!0-9]*) RUN_NUM=0 ;;  # sanitize non-numeric
    esac
  else
    RUN_NUM=0
  fi
fi

RUN_NUM=$((RUN_NUM + 1))
# Atomic write
printf '%d\n' "$RUN_NUM" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE" \
  || die "Failed to update counter at $STATE_FILE"
log INFO "Run counter: #$RUN_NUM"

# -----------------------------
# Your daily update steps
# -----------------------------
start_epoch=$(date +%s)

# Example step 1: ensure repo up-to-date (safe if not a git repo)
if [ -d "$PROJECT_ROOT/.git" ] && command -v git >/dev/null 2>&1; then
  log INFO "Updating git repository"
  ( cd "$PROJECT_ROOT" && git fetch --all --prune && git pull --ff-only ) \
    || die "git update failed"
else
  log INFO "Skipping git update (no .git or git not installed)"
fi

# Example step 2: database/ETL/cron work — replace with your real tasks
# ------------------------------------------------------------
# Put your actual commands below. Some common patterns:
# log INFO "Running ETL job"
# "$PROJECT_ROOT/venv/bin/python3" "$PROJECT_ROOT/scripts/etl_daily.py" --date "$DATE_TAG" || die "ETL failed"

# log INFO "Generating reports"
# php "$PROJECT_ROOT/scripts/make_reports.php" --date "$DATE_TAG" || die "Report generation failed"

# log INFO "Rotating artifacts"
# "$PROJECT_ROOT/scripts/rotate_artifacts.ksh" || die "Rotation failed"
# ------------------------------------------------------------

# Example step 3: sanity checks (optional)
# log INFO "Checking disk space"
# df -h / | sed '1!b; s/^/DISK: /'  # sample, tweak as needed

# -----------------------------
# Done
# -----------------------------
elapsed=$(( $(date +%s) - start_epoch ))
log INFO "Completed run #$RUN_NUM in ${elapsed}s"
log INFO "------------------------------------------------------------"
exit 0

