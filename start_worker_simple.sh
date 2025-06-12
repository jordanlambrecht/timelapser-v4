#!/bin/bash

# Simple Timelapser Worker Startup
cd "$(dirname "$0")/backend"

# Ensure data directory exists
mkdir -p ../data

echo "🚀 Starting Timelapser Worker (Fixed Data Directory)..."
echo "📁 Data directory: ../data/"

# Start the worker with the backend venv
exec ./venv/bin/python worker.py
