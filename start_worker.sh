#!/bin/bash

# Timelapser Worker Startup Script
# Run this from the project root directory

set -e

echo "🚀 Starting Timelapser Worker..."

# Change to backend directory
cd "$(dirname "$0")/backend"

# Ensure data directory exists
echo "📁 Ensuring data directories exist..."
mkdir -p ../data/cameras
mkdir -p ../data/videos
mkdir -p ../data/logs

# Activate virtual environment
echo "🐍 Activating Python environment..."
source venv/bin/activate

# Check if required packages are installed
echo "📦 Checking dependencies..."
python -c "import cv2, psycopg, loguru; print('✅ All dependencies available')"

# Start the worker
echo "⚡ Starting worker..."
echo "   Data directory: ../data"
echo "   Log file: ../data/worker.log"
echo "   Press Ctrl+C to stop"
echo ""

# Use exec to replace the shell process with Python (better signal handling)
exec python worker.py
