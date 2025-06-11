#!/bin/bash

# Setup script for Python worker
echo "Setting up Python worker environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "python-worker/venv" ]; then
    echo "Creating Python virtual environment..."
    cd python-worker
    python3 -m venv venv
    cd ..
fi

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
cd python-worker
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Python worker setup complete!"
echo "To run the worker:"
echo "  cd python-worker"
echo "  source venv/bin/activate" 
echo "  python main.py"
