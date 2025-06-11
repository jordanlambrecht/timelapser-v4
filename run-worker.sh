#!/bin/bash

# Run script for Python worker
echo "Starting Timelapser Python Worker..."

cd python-worker

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run setup-worker.sh first"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Verify dependencies
python -c "import cv2, psycopg, apscheduler" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Missing dependencies. Please run setup-worker.sh first"
    exit 1
fi

echo "✅ Environment ready, starting worker..."
echo "📋 Logs will be written to ../data/worker.log"
echo "🛑 Press Ctrl+C to stop"
echo ""

# Run the worker
python main.py
