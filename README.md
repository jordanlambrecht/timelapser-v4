# Timelapser v4

A comprehensive time-lapse automation platform for RTSP camera ecosystems designed for **long-running timelapses** (days to months).

## ✅ Complete Features

### 📹 **RTSP Image Capture**
- ✅ **Automated image capture** from RTSP streams every configurable interval
- ✅ **Concurrent camera processing** (up to 4 cameras simultaneously)
- ✅ **Retry logic** for failed captures (3 attempts with delays)
- ✅ **Organized file storage** by camera and date (`/data/cameras/camera-{id}/images/YYYY-MM-DD/`)
- ✅ **Comprehensive logging** to database and files

### 🎬 **Video Generation System**
- ✅ **FFmpeg integration** with quality settings (low/medium/high)
- ✅ **Database-tracked generation** with full metadata
- ✅ **Flexible input sources** - single day or entire camera history
- ✅ **Multiple quality presets** with resolution scaling
- ✅ **Background job processing** via Python worker
- ✅ **API-triggered generation** via web interface

### 🌐 **Web Interface**
- ✅ **Camera management** - Add/remove RTSP cameras
- ✅ **Timelapse controls** - Start/stop captures per camera
- ✅ **Video generation** - One-click video creation from captured images
- ✅ **Video management** - List, download, and delete generated videos
- ✅ **Settings configuration** - Capture intervals (1 second to 24 hours)
- ✅ **Real-time status** - Live camera and video generation status

### 🔄 **Background Processing**
- ✅ **Scheduled image capture** based on configurable intervals
- ✅ **Automatic video generation** request processing
- ✅ **Dynamic configuration updates** without restart
- ✅ **Health monitoring** and error recovery
- ✅ **Graceful shutdown** handling

### 🗄️ **Database Schema**
- ✅ **cameras** - Camera configuration and status
- ✅ **timelapses** - Timelapse status per camera  
- ✅ **videos** - Generated video metadata and tracking
- ✅ **settings** - Global configuration parameters
- ✅ **logs** - Capture attempts and system events

## 🚀 Quick Start

### 1. Web Interface
```bash
cd /Users/jordanlambrecht/dev-local/timelapser-v4
npm install
npm run dev
```
**Access at**: http://localhost:3000

### 2. Python Worker (Background Processing)
```bash
# Setup (one-time)
./setup-worker.sh

# Start background worker
./run-worker.sh
```

## 🎯 Usage Workflow

### **Long-Running Timelapses**
1. **Add Camera**: Enter RTSP URL in web interface
2. **Start Timelapse**: Click "Start" - begins capturing images every 5 minutes (configurable)
3. **Let it Run**: Camera captures images automatically for days/weeks/months
4. **Generate Video**: Click "Generate Video" to create MP4 from all captured images
5. **Download**: Download the final timelapse video

### **Video Management**
- **Generate Videos**: Create MP4s from any camera's captured images
- **Quality Options**: Low (720p), Medium (1080p), High (original resolution)
- **Framerate Control**: 1-60 fps (default 30 fps)
- **Download/Delete**: Manage generated videos through web interface

## 📊 API Endpoints

### Camera Management
- `GET /api/cameras` - List all cameras
- `POST /api/cameras` - Add new camera
- `DELETE /api/cameras/[id]` - Remove camera

### Timelapse Control  
- `GET /api/timelapses` - List timelapse status
- `POST /api/timelapses` - Start/stop timelapses

### Video Operations
- `GET /api/videos` - List all videos (with filtering)
- `POST /api/videos` - Generate new video from camera images
- `GET /api/videos/[id]` - Get video details
- `DELETE /api/videos/[id]` - Delete video and file
- `GET /api/videos/[id]/download` - Download video file

### Configuration
- `GET /api/settings` - Get current settings
- `PUT /api/settings` - Update settings (capture intervals, etc.)
- `GET /api/logs` - View capture and system logs

## 📁 File Organization

```
timelapser-v4/
├── src/                          # Next.js web application
│   ├── app/api/                 # API routes
│   └── app/page.tsx             # Main dashboard
├── python-worker/               # RTSP capture & video generation
│   ├── main.py                  # Background worker scheduler
│   ├── capture.py               # RTSP image capture
│   ├── video_generator.py       # FFmpeg video generation
│   └── database.py              # Database integration
├── data/                        # Generated content
│   ├── cameras/                 # Per-camera image storage
│   │   └── camera-{id}/images/YYYY-MM-DD/
│   ├── videos/                  # Generated MP4 files
│   └── worker.log               # Background worker logs
└── README.md
```

## ⚙️ Configuration

### Environment Variables (.env.local)
```env
DATABASE_URL="postgresql://neondb_owner:npg_JYrHT0d7Gpzo@ep-polished-wind-a81rqv6u-pooler.eastus2.azure.neon.tech/neondb?sslmode=require"
NEON_PROJECT_ID="muddy-math-60649735"
```

### Default Settings
- **Capture Interval**: 300 seconds (5 minutes)
- **Max Concurrent Cameras**: 4
- **Video Quality**: Medium (1080p, CRF 23)
- **Default Framerate**: 30 fps
- **Retry Attempts**: 3 per failed capture

## 🧪 Testing

### Test Camera Connection
```bash
cd python-worker && source venv/bin/activate
python test_camera.py [camera_id]
```

### Test Video Generation
```bash
cd python-worker && source venv/bin/activate
python video_generator.py ../data/cameras/camera-1/images/2025-06-10/ --with-db ../data/videos
```

### Monitor Worker Logs
```bash
tail -f data/worker.log
```

## 🚨 Troubleshooting

### **Camera Issues**
- **"Failed to open RTSP stream"**: Check RTSP URL format and camera accessibility
- **"Connection timeout"**: Verify network connectivity and camera credentials

### **Video Generation Issues**  
- **"Need at least 2 images"**: Ensure timelapse has been running and capturing images
- **"FFmpeg not found"**: Install FFmpeg system-wide

### **Worker Issues**
- **Database connection failures**: Verify DATABASE_URL in .env.local
- **No capturing**: Check if timelapses are set to "running" status

## 🏗️ Architecture

**Multi-Service Design:**
- **Next.js Frontend**: Web dashboard and API endpoints
- **Python Worker**: Background RTSP capture and video generation  
- **PostgreSQL**: Metadata, configuration, and logging
- **FFmpeg**: High-quality video generation
- **File System**: Organized image and video storage

**Optimized for Long-Running Operations:**
- Handles network interruptions and camera failures
- Automatic retry logic and error recovery
- Dynamic configuration updates without restart
- Comprehensive logging and status tracking
- Efficient concurrent processing

## 🎯 Use Cases

- **Construction Monitoring**: Daily progress documentation over months
- **Environmental Tracking**: Weather patterns, seasonal changes, scientific observation
- **Event Documentation**: Long-duration events with time-compressed playback
- **Security Enhancement**: Extended surveillance with rapid time period review
- **Creative Projects**: Artistic timelapses with precise timing control

## 🔮 Future Enhancements

- **Docker Deployment**: Complete containerized setup
- **Cloud Storage**: S3-compatible storage integration
- **Advanced Scheduling**: Time windows, camera-specific intervals
- **Real-time Previews**: Live camera feeds in web interface
- **Mobile App**: iOS/Android companion app
- **Multi-user Support**: User authentication and permissions

---

**Built for reliability and designed to run unattended for months while creating stunning timelapses from your RTSP camera infrastructure.**
