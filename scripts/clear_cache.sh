#!/bin/sh

# Clear server cache by calling the API endpoint.
# Usage:
#   scripts/clear_cache.sh                     # uses http://localhost:5000
#   scripts/clear_cache.sh http://localhost:8000
#   BASE_URL=http://my-host:5000 scripts/clear_cache.sh

# Determine base URL from arg 1, then BASE_URL env, then default
if [ -n "${1-}" ]; then
    BASE_URL="$1"
else
    BASE_URL="${BASE_URL:-http://localhost:5000}"
fi

URL="${BASE_URL%/}/api/cache/clear"

echo "Clearing cache via: $URL"

# Perform request and capture body + status code without requiring jq
OUTPUT=$(curl -sS -w "\n%{http_code}" -X GET "$URL" -H "Accept: application/json" || true)
STATUS=$(printf '%s' "$OUTPUT" | tail -n1)
BODY=$(printf '%s' "$OUTPUT" | sed '$d')

if [ "$STATUS" -ge 200 ] && [ "$STATUS" -lt 300 ]; then
    echo "$BODY"
    echo "Cache cleared successfully."
    exit 0
else
    echo "Request failed with HTTP $STATUS" >&2
    echo "$BODY" >&2
    exit 1
fi






