#!/bin/bash

# Kill any existing app.py processes
echo "Stopping any existing server processes..."
pkill -f "python.*app.py" || true

# Wait a moment for processes to fully stop
sleep 2

# Start the server in the background
echo "Starting the server in the background..."
cd /home/jmknapp/congressional-coalitions
nohup venv/bin/python app.py > server.log 2>&1 &

# Get the process ID
SERVER_PID=$!
echo "Server started with PID: $SERVER_PID"
echo "Server logs will be written to server.log"
echo "Server should be available at http://localhost:5000"
