# Timelapser v4 - Modern RTSP Timelapse Platform

A comprehensive time-lapse automation platform for RTSP camera ecosystems with FastAPI backend, connection pooling, Pydantic validation, and modern architecture.

## 🚀 Architecture

### Backend Stack
- **FastAPI** - Modern Python API with automatic OpenAPI documentation
- **Pydantic** - Data validation and serialization
- **PostgreSQL** - Database with connection pooling (psycopg3)
- **Alembic** - Database migration management
- **Python Worker** - Background RTSP capture and processing

### Frontend Stack  
- **Next.js 14** - React framework with App Router and Server Components
- **TypeScript** - Type safety matching backend Pydantic models
- **Tailwind CSS** - Utility-first styling

### Key Improvements
- ✅ **Connection Pooling** - Efficient database connections for long-running processes
- ✅ **Input Validation** - Pydantic models prevent injection attacks and data corruption
- ✅ **OpenAPI Documentation** - Auto-generated API docs at `/docs`
- ✅ **Type Safety** - TypeScript interfaces match Pydantic models exactly
- ✅ **Database Migrations** - Alembic for schema version control
- ✅ **Modern Patterns** - Server Components, proper error handling, structured logging

## 📋 Prerequisites

- **Node.js 18+** and **npm/pnpm**
- **Python 3.11+**
- **PostgreSQL database** (Neon recommended)
- **FFmpeg** for video processing
- **RTSP camera streams**

## 🛠️ Quick Setup

### 1. Clone and Install Dependencies

```bash
cd /path/to/timelapser-v4

# Install Next.js dependencies
npm install

# Setup FastAPI backend
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 2. Environment Configuration

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit with your actual values
nano backend/.env
```

Required environment variables:
```env
DATABASE_URL=postgresql://user:pass@host:port/dbname
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000
```

### 3. Database Setup

The database schema is already created in your Neon instance. For future migrations:

```bash
cd backend
source venv/bin/activate
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### 4. Start Services

**Option A: Automatic Startup (Recommended)**
```bash
./start-services.sh
```

**Option B: Manual Startup**
```bash
# Terminal 1: Backend API
cd backend
source venv/bin/activate
python -m app.main

# Terminal 2: Worker Process  
cd backend
source venv/bin/activate
python worker.py

# Terminal 3: Next.js Frontend
npm run dev
```

## 🎯 Access Points

- **Frontend Dashboard**: http://localhost:3000
- **FastAPI Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## 📚 API Documentation

### Camera Management
```bash
# List all cameras
GET /api/cameras

# Create camera with validation
POST /api/cameras
{
  "name": "Front Door", 
  "rtsp_url": "rtsp://192.168.1.100:554/stream",
  "status": "active",
  "use_time_window": true,
  "time_window_start": "06:00:00",
  "time_window_end": "18:00:00"
}

# Update camera
PUT /api/cameras/{id}

# Delete camera
DELETE /api/cameras/{id}
```

### Timelapse Control
```bash
# Start timelapse
PUT /api/timelapses/{camera_id}
{"status": "running"}

# Stop timelapse  
PUT /api/timelapses/{camera_id}
{"status": "stopped"}
```

### Video Generation
```bash
# Generate video
POST /api/videos
{
  "camera_id": 1,
  "name": "Construction Progress",
  "settings": {"quality": "high", "framerate": 30}
}
```

## 🏗️ Project Structure

```
timelapser-v4/
├── backend/                  # Python backend
│   ├── app/
│   │   ├── main.py          # FastAPI application
│   │   ├── config.py        # Settings management
│   │   ├── database.py      # Connection pooling
│   │   ├── models/          # Pydantic models
│   │   └── routers/         # API endpoints
│   ├── alembic/             # Database migrations
│   ├── worker.py            # Background worker
│   └── requirements.txt     # Python dependencies
├── src/                     # Next.js frontend
│   ├── app/                 # App Router pages
│   ├── components/          # React components
│   └── lib/
│       └── fastapi-client.ts # API client
├── data/                    # File storage
│   ├── cameras/            # Captured images
│   └── videos/             # Generated timelapses
└── start-services.sh       # Startup script
```

## 🔧 Configuration

### Camera Settings
- **Time Windows**: Only capture during specified hours (e.g., daylight only)
- **Health Monitoring**: Automatic offline detection and alerts  
- **Custom Intervals**: Per-camera capture frequency
- **RTSP Validation**: URL format validation prevents injection attacks

### System Settings
- **Capture Interval**: Global default (5 minutes)
- **Concurrent Cameras**: Max simultaneous captures (4)
- **Health Checks**: Camera monitoring frequency (2 minutes)
- **Connection Pooling**: Database efficiency settings

## 📊 Features

### ✅ Core Features
- **Multi-Camera Support** - Manage dozens of RTSP cameras
- **Automated Capture** - Background image collection with scheduling
- **Video Generation** - FFmpeg integration for high-quality timelapses
- **Health Monitoring** - Real-time camera status and alerts
- **Time Windows** - Smart capture scheduling (daylight only, etc.)
- **Day Numbering** - Track "Day 1", "Day 47" progression for overlays

### ✅ Technical Features  
- **Connection Pooling** - Efficient database resource management
- **Input Validation** - Pydantic prevents malicious input
- **Type Safety** - End-to-end TypeScript/Python type matching
- **Error Recovery** - Robust retry logic and graceful failures
- **OpenAPI Docs** - Auto-generated API documentation
- **Database Migrations** - Version-controlled schema changes

### ✅ User Experience
- **Server Components** - Fast page loads with Next.js App Router
- **Real-time Status** - Live camera health and capture indicators
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Easy Setup** - Single script deployment with validation

## 🔒 Security Features

- **RTSP URL Validation** - Prevents injection attacks
- **Input Sanitization** - All API inputs validated by Pydantic
- **Connection Security** - Pooled connections with proper cleanup
- **File Path Validation** - Prevents directory traversal
- **Error Handling** - No sensitive data leaked in error messages

## 📈 Performance Optimizations

- **Database Indexes** - Optimized queries for large datasets
- **Connection Pooling** - Reduced connection overhead
- **Concurrent Processing** - Multi-threaded image capture
- **Server Components** - Reduced client-side JavaScript
- **File Organization** - Efficient directory structure for storage

## 🐛 Troubleshooting

### Common Issues

**FastAPI won't start:**
```bash
# Check database connection
cd backend && source venv/bin/activate
python -c "from app.database import async_db; print('DB connection OK')"
```

**Camera capture failing:**
```bash
# Test RTSP URL manually
ffmpeg -i "rtsp://your-camera-url" -frames:v 1 test.jpg
```

**Worker not capturing:**
```bash
# Check worker logs
tail -f data/worker.log

# Verify camera time windows
curl http://localhost:8000/api/cameras
```

### Logs Location
- **Worker**: `data/worker.log`
- **FastAPI**: `data/api.log` (if configured)
- **Next.js**: Console output

## 🚀 Production Deployment

### Docker Setup (Coming Soon)
- Multi-container setup with docker-compose
- Environment-based configuration
- Health checks and auto-restart
- Volume management for persistent data

### Scaling Considerations
- Database connection pool sizing
- Worker concurrency limits
- File storage management
- Network bandwidth planning

## 🎯 Next Steps

High-priority features on the roadmap:
- **Day Overlay System** - Video overlays showing "Day 1", "Day 47", etc.
- **Docker Deployment** - Complete containerization
- **Storage Management** - Automatic cleanup and archival
- **Real-time Updates** - WebSocket integration for live status
- **Advanced Monitoring** - Metrics and alerting system

## 🤝 Development

### Adding New Features
1. Create Pydantic models in `backend/app/models/`
2. Add database methods in `database.py`
3. Create API routes in `routers/`
4. Update TypeScript interfaces in `fastapi-client.ts`
5. Build frontend components

### Database Changes
```bash
# Create migration
cd backend
alembic revision --autogenerate -m "add new feature"

# Apply migration
alembic upgrade head
```

---

**Built for long-running timelapses** - From days to months of continuous capture, with enterprise-grade reliability and modern development practices.
