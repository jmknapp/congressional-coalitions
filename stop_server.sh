#!/bin/bash

# Kill any existing app.py processes
echo "Stopping any existing server processes..."
pkill -f "python.*app.py" || true
