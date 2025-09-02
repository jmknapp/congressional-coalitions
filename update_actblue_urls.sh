#!/bin/bash
# ActBlue URL Update Wrapper Script
#
# This script provides an easy way to run the ActBlue scraper with proper environment setup.
#
# Usage:
#     ./update_actblue_urls.sh test                    # Test with AOC
#     ./update_actblue_urls.sh "Member Name"           # Update specific member
#     ./update_actblue_urls.sh all                     # Update all Democratic members
#     ./update_actblue_urls.sh state CA                # Update CA Democratic members

cd "$(dirname "$0")"

# Try to use venv Python if available, otherwise system Python
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif [ -f "venv/bin/python3" ]; then
    PYTHON="venv/bin/python3"
else
    PYTHON="python3"
fi

echo "🐍 Using Python: $PYTHON"

# Check if required packages are available
if ! $PYTHON -c "import requests, bs4, mysql.connector" 2>/dev/null; then
    echo "📦 Installing required packages..."
    
    # Try to install packages
    if [ -f "venv/bin/pip" ]; then
        venv/bin/pip install -r requirements-scraper.txt
    elif [ -f "venv/bin/pip3" ]; then
        venv/bin/pip3 install -r requirements-scraper.txt
    else
        echo "❌ Could not find pip in virtual environment"
        echo "💡 Try running: pip install -r requirements-scraper.txt"
        exit 1
    fi
fi

# Run the scraper with provided arguments
case "$1" in
    "test")
        echo "🧪 Running test mode..."
        $PYTHON scripts/actblue_scraper.py --test
        ;;
    "all")
        echo "👥 Processing all Democratic members..."
        $PYTHON scripts/actblue_scraper.py --all --delay 3
        ;;
    "state")
        if [ -z "$2" ]; then
            echo "❌ Please provide state code: ./update_actblue_urls.sh state CA"
            exit 1
        fi
        echo "🗺️  Processing Democratic members from $2..."
        $PYTHON scripts/actblue_scraper.py --state "$2" --delay 3
        ;;
    "")
        echo "❌ Please provide an argument:"
        echo "   ./update_actblue_urls.sh test"
        echo "   ./update_actblue_urls.sh \"Member Name\""
        echo "   ./update_actblue_urls.sh all"
        echo "   ./update_actblue_urls.sh state CA"
        exit 1
        ;;
    *)
        echo "🎯 Processing member: $1"
        $PYTHON scripts/actblue_scraper.py "$1"
        ;;
esac
