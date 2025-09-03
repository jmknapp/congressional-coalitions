#!/bin/bash

# Immediate script to discover and add new bills
# This script discovers and adds new bills that have been introduced recently

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DISCOVERY_SCRIPT="$SCRIPT_DIR/enhanced_daily_update.py"

echo "🔍 Discovering new bills introduced since Congress came back in session..."
echo "Project directory: $PROJECT_DIR"
echo "Discovery script: $DISCOVERY_SCRIPT"

# Change to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists
if [[ ! -d "venv" ]]; then
    echo "❌ Virtual environment not found. Please create one first:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate

# Check if required script exists
if [[ ! -f "$DISCOVERY_SCRIPT" ]]; then
    echo "❌ Discovery script not found: $DISCOVERY_SCRIPT"
    exit 1
fi

echo "🚀 Running bill discovery script..."
echo "   This will discover bills introduced in the last 7 days"
echo "   and add them to the database if they don't exist."
echo ""

# Run the discovery script with verbose output
python3 "$DISCOVERY_SCRIPT" \
    --congress 119 \
    --max-bills 200

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Bill discovery completed successfully!"
    echo ""
    echo "To check what bills were added, you can:"
    echo "  1. Check the database directly"
    echo "  2. View the application to see new bills"
    echo "  3. Check logs for details"
else
    echo ""
    echo "❌ Bill discovery failed. Check the output above for errors."
    echo ""
    echo "Common issues:"
    echo "  - Missing Congress.gov API key"
    echo "  - Database connection problems"
    echo "  - Rate limiting from Congress.gov API"
fi

echo ""
echo "To set up automatic daily discovery, run:"
echo "  chmod +x scripts/setup_daily_bill_discovery.sh"
echo "  ./scripts/setup_daily_bill_discovery.sh"
