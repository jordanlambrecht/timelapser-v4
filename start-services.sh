#!/bin/bash

# Backend + Worker Startup Script with Health Checks
# Starts all services with proper coordination and health monitoring

set -e

echo "🚀 Starting Timelapser v4 with health checks"

# Function to check if a service is healthy
check_service_health() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1

    echo "⏳ Waiting for $service_name to be healthy at $url..."

    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$url" >/dev/null 2>&1; then
            echo "✅ $service_name is healthy"
            return 0
        fi

        echo "   Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 2
        ((attempt++))
    done

    echo "❌ $service_name failed to become healthy after $max_attempts attempts"
    return 1
}

# Check if backend/.env exists
if [ ! -f "backend/.env" ]; then
    echo "❌ ERROR: backend/.env file not found"
    echo "Please copy backend/.env.example to backend/.env and configure it"
    exit 1
fi

# Check if Node.js dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node.js dependencies..."
    pnpm install
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
        echo "🔧 FastAPI stopped"
    fi
    if [ ! -z "$WORKER_PID" ]; then
        kill $WORKER_PID 2>/dev/null || true
        echo "⚙️ Worker stopped"
    fi
    if [ ! -z "$NEXTJS_PID" ]; then
        kill $NEXTJS_PID 2>/dev/null || true
        echo "🖥️ Next.js stopped"
    fi
    echo "✅ All services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Create data directories
mkdir -p data/cameras data/videos data/logs

# Start backend API
echo "🔧 Starting FastAPI backend on port 8000..."
cd backend
source venv/bin/activate
python -m app.main &
FASTAPI_PID=$!
cd ..

# Wait for FastAPI to be healthy
if ! check_service_health "http://localhost:8000/health" "FastAPI"; then
    echo "❌ FastAPI failed to start properly"
    cleanup
    exit 1
fi

# Start Worker
echo "⚙️ Starting capture worker..."
cd backend
source venv/bin/activate
python worker.py &
WORKER_PID=$!
cd ..

# Give worker a moment to initialize
sleep 3
echo "✅ Worker started"

# Start Next.js frontend
echo "🖥️ Starting Next.js frontend on port 3000..."
pnpm run dev &
NEXTJS_PID=$!

# Wait for Next.js to be healthy
if ! check_service_health "http://localhost:3000/api/health" "Next.js"; then
    echo "⚠️ Next.js may not be fully ready, but continuing..."
fi

echo ""
echo "✅ All services started successfully!"
echo "🔗 Service Status:"
echo "   📊 FastAPI backend: http://localhost:8000/docs"
echo "   🖥️ Next.js frontend: http://localhost:3000"
echo "   ❤️ Health check: http://localhost:3000/api/health"
echo "   📈 API health: http://localhost:8000/api/health"
echo "   📝 Logs: backend/logs/ and data/worker.log"
echo ""
echo "📊 Quick health check:"
curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo "Backend health check failed"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for services
wait
