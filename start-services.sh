#!/bin/bash

# Backend + Worker Startup Script
# Starts both the FastAPI backend and the worker process

set -e

echo "🚀 Starting Timelapser v4"

# Check if backend/.env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ ERROR: backend/.env file not found"
    echo "Please copy backend/.env.example to backend/.env and configure it"
    exit 1
fi

# Check if Node.js dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    npm install
fi

# Check if virtual environment exists for backend
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating Python virtual environment for backend..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# Function to handle cleanup
cleanup() {
    echo "🛑 Shutting down services..."
    if [ ! -z "$FASTAPI_PID" ]; then
        kill $FASTAPI_PID 2>/dev/null || true
    fi
    if [ ! -z "$WORKER_PID" ]; then
        kill $WORKER_PID 2>/dev/null || true
    fi
    if [ ! -z "$NEXTJS_PID" ]; then
        kill $NEXTJS_PID 2>/dev/null || true
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start backend API
echo "🔧 Starting backend API on port 8000..."
cd backend
source venv/bin/activate
python -m app.main &
FASTAPI_PID=$!
cd ..

# Wait a moment for FastAPI to start
sleep 3

# Start Worker
echo "⚙️ Starting capture worker..."
cd backend
source venv/bin/activate
python worker.py &
WORKER_PID=$!
cd ..

# Wait a moment for worker to start
sleep 2

# Start Next.js frontend
echo "🖥️ Starting Next.js frontend on port 3000..."
npm run dev &
NEXTJS_PID=$!

echo "✅ Services started successfully!"
echo "📊 API docs: http://localhost:8000/docs"
echo "🖥️ Next.js frontend: http://localhost:3000"
echo "📝 Logs: Check backend/logs/ and data/worker.log"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for services
wait
