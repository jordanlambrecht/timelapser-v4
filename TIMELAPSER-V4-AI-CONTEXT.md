# TIMELAPSER V4 - AI CONTEXT

Streamlined architectural reference for AI assistants.

**Project**: RTSP camera timelapse automation platform **Stack**: Next.js
frontend → FastAPI backend → PostgreSQL (Neon, for now) → Python Worker
**Goal**: Open-source self-hosted timelapse creation system **Package Manager**:
pnpm (not npm)

## 🏗️ SYSTEM ARCHITECTURE

```
Next.js (3000) ↔ FastAPI (8000) ↔ PostgreSQL ↔ Python Worker
       ↕                                            ↕
   SSE Events                                  RTSP Cameras
```

**Why This Architecture**:

- **SSE Real-time Updates**: Frontend → FastAPI SSE avoids CORS issues
- **Dual Database Pattern**: Async (FastAPI web requests) + Sync (Worker
  background tasks)
- **Production Ready**: Single domain, unified auth layer, consistent error
  handling

## 🚨 CONSOLIDATED CRITICAL IMPLEMENTATION RULES (DON'T BREAK THESE)

### Time Calculation Rules

1. **Always use `useCaptureSettings()` hook** to get timezone in components
2. **Never use raw `new Date()` or browser timezone** for display calculations
3. **All countdown and relative time calculations must pass timezone parameter**
4. **Time windows are calculated in database-configured timezone, not browser
   local**

### Entity-Based Architecture Rules

1. **Always create new timelapse entities** when users click "Start A New
   Timelapse"
2. **Use active_timelapse_id** for determining where new images should be
   associated
3. **Preserve completed timelapses** as permanent historical records
4. **Display both total and current statistics** on camera cards
5. **Worker processes must respect** active timelapse relationships for image
   capture

### Dashboard Enhancement Rules

1. **Auto-stop times must be validated** as future timestamps in correct
   timezone
2. **Progress borders only activate** during running timelapses with valid time
   data
3. **Capture Now requires both** online camera AND active timelapse
4. **Bulk Resume button state** must check actual paused cameras, not all
   cameras
5. **New timelapse dialog validates** all fields before allowing submission

### Video Generation Settings Rules

1. **Always use inheritance pattern**: Timelapse settings override camera
   defaults
2. **Validate FPS bounds**: Min FPS ≤ Calculated FPS ≤ Max FPS
3. **Respect time limits**: Standard mode adjusts FPS to stay within min/max
   time
4. **Use get_effective_video_settings()**: Always resolve inheritance in
   calculations
5. **Preview before generation**: Show users exact results before processing

### Thumbnail System Rules

1. **Always use separate folder structure** - Never mix thumbnails with full
   images
2. **Respect generate_thumbnails setting** - Check database setting before
   generation
3. **Use Pillow for thumbnails** - OpenCV only for RTSP capture
4. **Implement cascading fallbacks** - thumbnail → small → full → placeholder
5. **Store relative paths in database** - Never store absolute paths

### System-Wide Constraints

1. **psycopg3 connection pooling** - Both async/sync pools required
2. **Day number calculation** - Always relative to timelapse.start_date
3. **File path structure** - /data/cameras/camera-{id}/images/YYYY-MM-DD/
4. **TypeScript ↔ Pydantic sync** - Interfaces must match exactly
5. **SSE event format** - Must match existing broadcast_event() structure
6. **RTSP URL validation** - Security validation in camera.py models
7. **Query-based image retrieval** - Use LATERAL joins, no FK dependencies

### NEVER USE

- **SQLite** - PostgreSQL only, connection pooling required
- **psycopg2** - Must be psycopg3 with pools
- **Synchronous database calls in FastAPI** - Use async_db only
- **Absolute paths in database** - Store relative paths from project root
- **FK-based latest image tracking** - Use query-based LATERAL joins only
- **Non-existent image endpoints** - Never reference
  `/api/images/{id}/thumbnail`
- **Simple browser-local time calculations** - Always use timezone-aware system

## 🧠 WHY ARCHITECTURAL DECISIONS WERE MADE

**The Frontend → Next.js API → FastAPI → Database Pattern Was Initially
Questioned But Proven Optimal**:

**SSE (Server-Sent Events) Requirements**:

- Direct frontend → FastAPI SSE connections have CORS issues in production
- Browser security policies restrict cross-origin SSE connections
- Same-origin proxy via Next.js solves these issues reliably
- Alternative approaches (WebSockets, polling) add complexity without benefits

**Settings & State Management Benefits**:

- Prevents settings changes requiring page refreshes
- Enables real-time state synchronization across components
- Centralized state management through Next.js layer
- Consistent error handling and user feedback

**Production Deployment Advantages**:

- Single domain deployment (no CORS configuration needed)
- Unified authentication layer ready for implementation
- Consistent error handling across all endpoints
- Easy SSL/reverse proxy setup
- Simplified Docker deployment with service coordination

**Sync + Async Database Pattern Justification**:

- **Async (FastAPI)**: Handles concurrent web requests efficiently with
  connection pooling
- **Sync (Worker)**: Background processes need reliability for RTSP capture,
  file I/O, FFmpeg processing
- Different tools for different jobs - web API needs concurrency, background
  worker needs predictable execution
- psycopg3 pools provide optimal performance for both patterns

## 📚 EVOLUTION STORY - MAJOR ARCHITECTURAL TRANSFORMATIONS

### 🎯 Entity-Based Timelapse Revolution (June 17, 2025)

**The Problem**: Timelapses were abstract status changes rather than concrete,
trackable entities **The Transformation**: Complete paradigm shift from
status-based to entity-based architecture

**Before (Status-Based Model)**:

```text
Camera 1 → Timelapse Record (ID: 2) → Status: 'running'/'stopped'
- Same record reused indefinitely
- No historical separation between recording sessions
- Images accumulated over time without clear boundaries
- Users lost context of different recording periods
```

**After (Entity-Based Model)**:

```text
Camera 1 → Active Timelapse: "RainStorm" (ID: 2, 640 images, running)
         → Historical: "Construction Week 1" (ID: 1, 550 images, completed)
         → Historical: "Morning Routine" (ID: 3, 124 images, completed)
```

**Critical Database Schema Changes**:

```sql
-- Added active timelapse tracking
ALTER TABLE cameras ADD COLUMN active_timelapse_id INTEGER;
ALTER TABLE cameras ADD CONSTRAINT fk_active_timelapse
  FOREIGN KEY (active_timelapse_id) REFERENCES timelapses(id) ON DELETE SET NULL;

-- Expanded timelapse lifecycle
-- Status options: 'running', 'paused', 'completed', 'archived'
```

**Workflow Transformation**:

- **Old**: "Start Timelapse" changed status on existing record
- **New**: "Start A New Timelapse" creates discrete entity with unique identity
- **Result**: Historical timelapses preserved as concrete, queryable entities

### 🖼️ Image Loading System Overhaul (June 2025)

**The Problem**: FK-based latest image tracking created maintenance nightmare
**The Transformation**: Complete migration to query-based approach with
PostgreSQL LATERAL joins

**Why FK Approach Failed**:

- `cameras.last_image_id` required constant updates on every capture
- Risk of stale FK references pointing to deleted/moved images
- Multiple code paths for image serving causing confusion
- Maintenance overhead keeping FK relationships in sync

**LATERAL Join Solution**:

```sql
-- Efficient, always-accurate latest image retrieval
SELECT c.*, i.id as last_image_id, i.captured_at, i.file_path
FROM cameras c
LEFT JOIN LATERAL (
  SELECT id, captured_at, file_path, day_number
  FROM images WHERE camera_id = c.id
  ORDER BY captured_at DESC LIMIT 1
) i ON true
```

**Benefits Achieved**:

- Always accurate (no stale FK references)
- Zero maintenance (no FK updates on capture)
- PostgreSQL optimized (leverages database engine strengths)
- Simplified logic (single code path for image retrieval)

### 🌍 Timezone-Aware Time System Development (June 2025)

**The Problem**: Browser-local time calculations created inconsistency across
users and server operations **The Solution**: Sophisticated timezone-aware time
calculation system

**Architecture Overview**:

```text
UI Components ↔ Time Utilities ↔ Settings API
(Camera Cards,   (time-utils.ts)  (Database
 Countdown,      useCameraCount-   Timezone)
 Timestamps)     down Hook
```

**Key Evolution Stages**:

1. **Basic Implementation**: Database timezone storage with settings API
2. **Calculation Engine**: Centralized time utilities with timezone parameters
3. **Real-time Enhancement**: Smart countdown hooks with timezone awareness
4. **UI Refinement**: Absolute time displays with timezone abbreviations

**Real-Time Countdown Enhancements (June 16, 2025)**:

- **Updated `getSmartRefreshInterval()` in `time-utils.ts`**:
  - 0-3 seconds: 0.5-second updates (for "Now" detection)
  - **4-300 seconds (5 minutes): 1-second updates** (Real-time countdown!)
  - 301-600 seconds: 5-second updates
  - 601+ seconds: Slower intervals for distant times
- **Enhanced `useCameraCountdown()` hook** to return `lastCaptureAbsolute` and
  `nextCaptureAbsolute` values
- **Created `formatAbsoluteTimeForCounter()` function** with timezone
  abbreviations using `Intl.DateTimeFormat` with `timeZoneName: 'short'`
- **"Now" State Improvements** with pulsing cyan borders and animated text

## 🧩 COMPONENT ECOSYSTEM - HOW EVERYTHING CONNECTS

### Core Time Management Flow

```typescript
// Settings stores timezone in database
GET /api/settings → { timezone: "America/Chicago" }

// useCaptureSettings hook fetches and caches timezone
const { timezone, captureInterval } = useCaptureSettings()

// useCameraCountdown uses timezone for all calculations
const { lastCaptureRelative, nextCaptureRelative, progress } = useCameraCountdown(camera.id)

// Camera card displays timezone-aware times
<CameraCard
  camera={camera}
  lastCapture={lastCaptureRelative}    // "47 minutes ago"
  nextCapture={nextCaptureRelative}    // "4m 23s"
  absoluteTime="June 16th 13:35 (CDT)" // Timezone abbreviation
/>
```

### Image Display Ecosystem

```typescript
// Thumbnail fallback component handles all image loading
<CameraImageWithFallback camera={camera} />

// Cascading endpoint attempts:
// 1. /api/cameras/{id}/latest-thumbnail (200×150)
// 2. /api/cameras/{id}/latest-small (800×600)
// 3. /api/cameras/{id}/latest-capture (full resolution)
// 4. Placeholder if all fail

// Backend serves from separate folder structure:
// data/cameras/camera-{id}/thumbnails/YYYY-MM-DD/
// data/cameras/camera-{id}/small/YYYY-MM-DD/
// data/cameras/camera-{id}/images/YYYY-MM-DD/
```

### Real-time Update Flow

```typescript
// SSE connection established
const eventSource = new EventSource("/api/events")

// Worker broadcasts events
sync_db.broadcast_event("image_captured", {
  camera_id: 1,
  image_count: 47,
  timelapse_id: 2,
})

// Frontend receives and updates state
useRealtimeCameras() // Updates camera data
useCameraCountdown() // Refreshes countdown timers
// Camera cards re-render with new data automatically
```

### Settings Inheritance Pattern

```typescript
// Video generation settings flow
Camera defaults → Timelapse overrides → Effective settings

// Initial Copying: When a new timelapse is created, camera settings are copied to it
function createNewTimelapseWithSettings(camera_id) {
  // First get the camera's settings
  const camera = await async_db.get_camera_by_id(camera_id);

  // Create a new timelapse entity with a copy of camera settings
  const timelapseData = {
    camera_id: camera_id,
    name: `Timelapse ${new Date().toISOString().slice(0, 10)}`,
    status: 'running',
    // Copy ALL camera settings as base values
    video_generation_mode: camera.video_generation_mode,
    standard_fps: camera.standard_fps,
    target_time_seconds: camera.target_time_seconds,
    min_fps: camera.min_fps,
    max_fps: camera.max_fps,
    enable_time_limits: camera.enable_time_limits,
    min_time_seconds: camera.min_time_seconds,
    max_time_seconds: camera.max_time_seconds,
    time_window_start: camera.time_window_start,
    time_window_end: camera.time_window_end,
    // Additional fields...
  };

  return await async_db.create_timelapse(timelapseData);
}

// Timelapse Creation Dialog: Users can customize these settings
// In the creation dialog component, the form is pre-filled with camera settings
// but users can modify any fields before submission

// Effective settings resolver
function getEffectiveVideoSettings(timelapse, camera) {
  return {
    video_generation_mode: timelapse.video_generation_mode || camera.video_generation_mode,
    standard_fps: timelapse.standard_fps || camera.standard_fps,
    // ... all fields follow this pattern
  }
}

// Used in: VideoGenerationSettings component, video generation API, preview calculations
```

## ⚠️ ERROR CONTEXT - CRITICAL ISSUES RESOLVED

### CORS_ORIGINS Parsing Failure (June 16, 2025)

**Problem**: FastAPI backend failing to start with JSONDecodeError **Root
Cause**: Pydantic expected JSON array, but .env had comma-separated string

```bash
# .env file format
CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:3002

# Pydantic tried json.loads() on this string → crash
```

**Solution**: Enhanced config.py with Union type handling

```python
cors_origins: Union[str, list[str]] = ["http://localhost:3000", ...]

@property
def cors_origins_list(self) -> list[str]:
    if isinstance(self.cors_origins, str):
        return [origin.strip() for origin in self.cors_origins.split(',')]
    return self.cors_origins
```

### Image Loading Content-Length Error (Fixed)

**Problem**: Browser error "Content-Length header exceeds response Body" **Root
Cause**: FastAPI image endpoint missing proper headers **Solution**: Added
`"Content-Length": str(len(image_data_bytes))` to all image responses

### SSE Event Broadcasting Failure (Fixed)

**Problem**: Real-time dashboard updates not working **Root Cause**: Worker not
properly broadcasting events to Next.js SSE endpoint **Solution**: Fixed
`broadcast_event()` method with proper JSON formatting

```python
# Correct pattern
requests.post(url, json=data)  # NOT data=json.dumps(data)
```

### Service Coordination Issues (Fixed)

**Problem**: Services starting without dependency validation **Solution**:
Enhanced `start-services.sh` with health check retries and proper ordering

## 🚨 COMMON AI MISCONCEPTIONS TO AVOID

### 1. **"Let's optimize dashboard loading by serving images directly from database"**

❌ **Why This Breaks Everything**:

- Images aren't stored in database (only file paths)
- Bypasses thumbnail cascading fallback system (thumbnail → small → full →
  placeholder)
- Database would become massive with binary data
- Breaks separation of concerns (database for metadata, filesystem for files)
- Thumbnail system already solves performance (60x faster loading)

### 2. **"Direct frontend → FastAPI connection would be simpler than Next.js proxy"**

❌ **Why This Was Tried and Failed**:

- Creates CORS issues in production deployment
- Browser security policies restrict cross-origin SSE connections
- Requires complex CORS configuration and maintenance
- Breaks single-domain deployment benefits
- Complicates authentication layer implementation

### 3. **"FK-based latest image tracking would be simpler than LATERAL joins"**

❌ **Why This Was Abandoned**:

- Creates stale FK references when images are deleted/moved
- Requires updating `cameras.last_image_id` on every capture (maintenance
  overhead)
- Risk of FK pointing to non-existent images causing display errors
- Multiple code paths create confusion and bugs
- LATERAL joins are more performant and always accurate

### 4. **"Browser timezone calculations are simpler than database timezone"**

❌ **Why This Breaks Multi-User Systems**:

- Server-side time window calculations need consistent timezone
- Database operations require timezone context
- Real-time countdowns would show different times for different users
- Breaks scheduled operations and capture time windows
- System admin needs predictable timezone for troubleshooting

### 5. **"Status-based timelapses are simpler than entity-based"**

❌ **Why This Lacks Professional Features**:

- No historical tracking or organization ("Remember that storm footage?")
- Day numbering never resets (Day 1, Day 2, vs Day 247, Day 248)
- Users can't reference specific recording sessions
- No foundation for Timelapse Library or advanced management
- Mixing images from different recording purposes

### 6. **"Store thumbnails in same folders as full images for simplicity"**

❌ **Why This Breaks Video Generation**:

- FFmpeg scans entire folders - would include thumbnails in videos
- Complicates cleanup policies (different retention for different sizes)
- Breaks backup strategies (can backup full images, skip regeneratable
  thumbnails)
- Makes bulk operations more complex (regeneration, deletion)
- Separate folders enable different access patterns

### 7. **"Simplify by using one database connection type instead of async/sync"**

❌ **Why Both Are Required**:

- FastAPI endpoints need async for concurrent web request handling
- Worker background tasks need sync for reliable RTSP capture and file I/O
- psycopg3 pools are optimized for each use case
- Different tools for different jobs - concurrency vs reliability
- Connection pool separation prevents resource conflicts

## 🗄️ DATABASE SCHEMA

**Core Relationships**:

```
cameras (1) ──► timelapses (many) ──► images (many)
timelapses (1) ──► videos (many)
```

**Key Tables**:

- `cameras`: RTSP config, health status, time windows, video settings
- `timelapses`: Recording sessions with entity-based architecture
- `images`: Captures linked to timelapse, day_number calculation
- `videos`: Generated MP4s with overlay settings
- `settings`: Global config including timezone

**Critical Pattern - Query-Based Image Retrieval**:

```sql
-- NO FK dependencies, uses LATERAL joins for performance
SELECT c.*, i.id as last_image_id, i.captured_at
FROM cameras c
LEFT JOIN LATERAL (
  SELECT id, captured_at, file_path, day_number
  FROM images WHERE camera_id = c.id
  ORDER BY captured_at DESC LIMIT 1
) i ON true
```

**Day Number Logic:**

```python
day_number = (current_date - timelapse.start_date).days + 1
# Day 1 = first day of timelapse, Day 47 = 47th day, etc.
```

## 🎯 ENTITY-BASED TIMELAPSE ARCHITECTURE

**CRITICAL PARADIGM**: Timelapses are discrete entities, NOT status changes

**Entity Creation**: Each "Start A New Timelapse" creates a new record **Active
Tracking**: `cameras.active_timelapse_id` → current recording session
**Historical Records**: Completed timelapses preserved as concrete entities
**Dual Statistics**: Camera cards show "Total: 1,250, Current: 47 images"

**Database Fields**:

```sql
-- cameras table
active_timelapse_id INTEGER REFERENCES timelapses(id)

-- timelapses table
status ENUM ('running', 'paused', 'completed', 'archived')
name VARCHAR(255)
auto_stop_at TIMESTAMP WITH TIME ZONE
time_window_start TIME
time_window_end TIME
use_custom_time_window BOOLEAN
```

## 🌍 TIMEZONE-AWARE TIME SYSTEM

**NEVER use browser local time** - All calculations use database-configured
timezone

**Core Files**:

- `/src/lib/time-utils.ts` - Central time calculations
- `/src/hooks/use-camera-countdown.ts` - Smart countdown with timezone support

**Key Functions**:

```typescript
getConfiguredTimezone() // Gets timezone from settings with fallback
formatRelativeTime(date, timezone) // Timezone-aware relative formatting
useCameraCountdown() // Real-time countdown with 1-second updates under 5 min
```

**Display Pattern**: Relative time + absolute time + timezone abbreviation
Example: `"Next: 4m 23s"` + `"June 16th 13:35 (CDT)"`

## 🖼️ THUMBNAIL SYSTEM

**Separate Folder Structure**:

```
data/cameras/camera-{id}/
├── images/YYYY-MM-DD/          # Full resolution (1920×1080)
├── thumbnails/YYYY-MM-DD/      # 200×150 for dashboard
└── small/YYYY-MM-DD/           # 800×600 medium quality
```

**Cascading Fallback**: thumbnail → small → full → placeholder  
**Technology**: Pillow for thumbnails (superior to OpenCV for web images)  
**User Control**: `settings.generate_thumbnails` toggle

**Performance Improvements**:

- **Before**: 1920×1080 full images (~500KB each, ~5-10 seconds total)
- **After**: 200×150 thumbnails (~8KB each, ~200ms total)
- **Improvement**: **~60x faster dashboard loading** 🚀

**Pillow-Based Thumbnail Processing**:

```python
# /backend/thumbnail_processor.py - New optimized processor
class ThumbnailProcessor:
    def generate_thumbnail_pil(self, pil_image, size, quality):
        # Use Pillow's optimized thumbnail method with LANCZOS
        thumb_image.thumbnail(size, Image.Resampling.LANCZOS)
        # Progressive JPEG with optimization
        final_image.save(output, format='JPEG', quality=quality,
                        optimize=True, progressive=True)
```

## 🎬 VIDEO GENERATION SETTINGS

**Dual Mode System**:

- **Standard FPS**: User sets FPS (e.g., 24), system calculates duration
- **Target Time**: User sets duration (e.g., 120s), system calculates FPS

**Settings Inheritance**: Camera defaults → Timelapse overrides  
**Smart Validation**: FPS bounds, time limits, automatic adjustment

**Camera to Timelapse Settings Flow**:

1. Each camera has its own video generation settings (fps, time targets, etc.)
2. When a new timelapse is created, it **copies all camera settings as initial
   values**
3. In the timelapse creation dialog, users can override any of these settings
4. Modified settings apply only to that specific timelapse
5. Camera settings remain unchanged for future timelapses

**Standard FPS Mode**:

```text
User sets desired FPS (e.g., 24 FPS)
Optional: Enable time limits with min/max seconds
System calculates: duration = image_count / fps
If duration violates limits: automatically adjust FPS within bounds
Preview shows: "24 FPS → 744 images = 31.0 seconds"
```

**Target Time Mode**:

```text
User sets exact target duration (e.g., 120 seconds)
System calculates: fps = image_count / target_time
Auto-clamp FPS between min_fps and max_fps bounds
Preview shows: "120s target → 744 images = 6.2 FPS"
Result: Exact duration with calculated optimal FPS
```

## 🎬 VIDEO OVERLAY SYSTEM

### Day Overlay Format

```python
# ASS Subtitle Format with Dynamic Text
"Dialogue: 0,0:00:00.00,0:00:00.03,Default,,0,0,0,,Day 1"
"Dialogue: 0,0:00:00.03,0:00:00.07,Default,,0,0,0,,Day 2"
# Each frame gets accurate day number from image.day_number
```

### Settings Structure

```python
overlay_settings = {
    "enabled": True,
    "position": "bottom-right",  # top-left, top-right, etc.
    "font_size": 48,
    "font_color": "white",
    "background_color": "black@0.5",
    "format": "Day {day}"  # Template string
}
```

## 📁 FILE STRUCTURE

```
timelapser-v4/
├── backend/                    # FastAPI + Python Worker
│   ├── app/
│   │   ├── main.py            # FastAPI app with lifespan
│   │   ├── database.py        # Async/Sync connection pools
│   │   ├── models/            # Pydantic models
│   │   └── routers/           # API endpoints
│   ├── worker.py              # Background RTSP capture
│   └── requirements.txt
├── src/                       # Next.js frontend
│   ├── app/                   # App Router pages
│   ├── components/            # React components
│   └── lib/                   # API client + hooks
├── data/                      # File storage
│   ├── cameras/              # Images organized by camera/date
│   └── videos/               # Generated timelapses
└── start-services.sh         # Coordinated startup with health checks
```

## 🔄 KEY WORKFLOWS

**Image Capture**:

1. Worker captures RTSP frame every 5 minutes using OpenCV
2. Save to filesystem:
   `/data/cameras/camera-{id}/images/YYYY-MM-DD/capture_YYYYMMDD_HHMMSS.jpg`
3. Generate thumbnails (if enabled) using Pillow with separate folders
4. Record in database: `sync_db.record_captured_image()` with active timelapse
   relationship
5. Update camera health: `sync_db.update_camera_health()`
6. Broadcast SSE event: `sync_db.notify_image_captured()` for real-time UI

**Day Number Calculation**:

```python
day_number = (current_date - timelapse.start_date).days + 1
# Day 1 = first day of timelapse, Day 47 = 47th day
```

**Video Generation**:

1. Get timelapse images: `sync_db.get_timelapse_images()` with day_number
2. Apply video settings with inheritance: `get_effective_video_settings()`
3. FFmpeg with ASS overlays: "Day 1", "Day 2" using day_number from database
4. Save MP4 to `/data/videos/` with metadata

**Real-time Updates (SSE)**:

```
Worker Process:
sync_db.broadcast_event() → POST to Next.js /api/events

Frontend:
useRealtimeCameras() → EventSource('/api/sse') → Live UI updates
```

**Event Types**:

- `image_captured` - New image captured
- `camera_status_changed` - Online/offline status
- `timelapse_started/stopped/paused` - Timelapse state changes

**Timelapse Creation Workflow**:

1. User clicks "Start A New Timelapse" → Opens configuration dialog
2. Dialog pre-fills with camera's settings as defaults
3. User can customize any settings specifically for this timelapse
4. On submit → Creates new timelapse with customized settings
5. Settings only apply to this timelapse, camera settings remain unchanged

## 🚀 CURRENT SYSTEM STATUS (Fully Functional)

### ✅ REAL-TIME FEATURES (Working)

- **Live Dashboard Updates** - No manual refresh needed
- **Camera Health Monitoring** - Real-time online/offline status
- **Image Capture Events** - Watch capture counts update live
- **Timelapse Status Changes** - Start/stop reflects immediately
- **SSE Connection Health** - Visual indicator for live updates
- **Error Broadcasting** - Failed captures show immediately

### ✅ CORE FUNCTIONALITY (Production Ready)

- **RTSP Camera Management** - Add, edit, delete cameras with validation
- **Time Window Controls** - Capture only during specified hours
- **Automated Image Capture** - Scheduled captures every 5 minutes
  (configurable)
- **Health Monitoring** - Automatic offline detection and recovery
- **Video Generation** - FFmpeg integration with quality settings
- **Database Tracking** - Complete image and video metadata
- **Day Number Tracking** - Proper day counting for overlay generation

### 🔧 DEVELOPMENT PATTERNS

**Database Connections**:

```python
# CRITICAL: psycopg3 with connection pooling (not psycopg2)
AsyncConnectionPool(min_size=2, max_size=10)  # FastAPI
ConnectionPool(min_size=2, max_size=10)       # Worker

# Usage patterns
async_db = AsyncDatabase()  # FastAPI endpoints only
sync_db = SyncDatabase()    # Worker processes only
```

**API Response Pattern**:

```python
# FastAPI endpoints return Pydantic models directly
@router.get("/cameras", response_model=List[CameraWithLastImage])
async def list_cameras():
    return await async_db.get_cameras_with_images()
```

**TypeScript ↔ Pydantic Sync**:

```typescript
// Interfaces MUST match Pydantic models exactly
interface Camera extends CameraBase {
  id: number
  health_status: "online" | "offline" | "unknown"
  active_timelapse_id: number | null
  total_images: number
  current_timelapse_images: number
}
```

**Environment Variables (.env)**:

```bash
# Backend - CRITICAL: Comma-separated for CORS_ORIGINS
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
DATABASE_URL=postgresql://user:pass@host/db

# Frontend
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000
```

**Starting System**:

```bash
./start-services.sh  # Coordinated startup with health checks
```

**Component Patterns**:

```typescript
// Always use timezone-aware hooks
const { lastCaptureRelative, nextCaptureRelative } = useCameraCountdown(camera.id)

// Image display with fallback
<CameraImageWithFallback camera={camera} />

// Toast notifications for user feedback
toast.success("Settings saved")
toast.error("Failed: " + error.message)
```

## 🎯 CURRENT STATUS

**Production Ready**: All core features functional with real-time updates  
**Architecture Validated**: Next.js → FastAPI → Database pattern proven
optimal  
**Recent Enhancements**: Entity-based timelapses, thumbnail system, enhanced
timezone display  
**Ready For**: Docker deployment, advanced video features, cloud integration

### ✅ WORKING FEATURES

- Camera management with health monitoring
- RTSP image capture with time windows
- Entity-based timelapse recording
- Video generation with day overlays
- Real-time SSE dashboard updates
- Timezone-aware time calculations
- Thumbnail system with cascading fallbacks
- Video generation settings with dual modes

### 🔧 KEY DEPENDENCIES

```python
# Backend (requirements.txt)
fastapi==0.115.12
psycopg[binary,pool]==3.2.9  # CRITICAL: psycopg3 with pools
pydantic==2.11.5
opencv-python==4.11.0.86    # RTSP capture
Pillow                       # Thumbnail generation
apscheduler==3.11.0         # Background jobs
```

```json
// Frontend (package.json)
"next": "15.3.3"
"react": "19.1.0"
"@radix-ui/*": "UI components"
"tailwindcss": "4.1.10"
"lucide-react": "Icons"
```

### 📋 CRITICAL API ENDPOINTS

```python
# Camera Management
GET /api/cameras                    # List with LATERAL join for latest images
POST /api/cameras                   # Create with RTSP validation
PATCH /api/cameras/{id}             # Update settings
GET /api/cameras/{id}/latest-capture # Full resolution image

# Thumbnail System
GET /api/cameras/{id}/latest-thumbnail # 200×150 thumbnail
GET /api/cameras/{id}/latest-small     # 800×600 medium

# Timelapse Control (Entity-Based)
POST /api/timelapses/new            # Create NEW entity (not status change)
POST /api/timelapses/{id}/complete  # Mark as historical record
GET /api/cameras/{id}/timelapse-stats # Total vs current image counts

# Real-time Events
GET /api/events                     # SSE connection
POST /api/events                    # Broadcast from worker

# Settings & Health
GET /api/settings                   # Global config including timezone
GET /api/health                     # System health with DB connectivity
```

## 🔧 DEVELOPMENT WORKFLOW PATTERNS

### Safe Feature Addition Process

1. **Database Changes**: Always use Alembic migrations, never direct schema
   changes
2. **TypeScript Sync**: Update Pydantic models first, then TypeScript interfaces
3. **Backward Compatibility**: Ensure existing API endpoints continue working
4. **SSE Integration**: Add new event types to both backend and frontend
5. **Testing**: Validate with `./diagnostic-test.sh` before deployment

### Alembic Migration Patterns

```bash
# Generate migration from model changes
cd backend && alembic revision --autogenerate -m "Add new feature"

# Review generated migration before applying
# Edit migration file if needed for complex changes

# Apply to database
alembic upgrade head

# For production: Always backup database before migrations
```

### Database Query Optimization Guidelines

```python
# Always use LATERAL joins for related data
SELECT c.*, t.name as active_timelapse_name
FROM cameras c
LEFT JOIN LATERAL (
  SELECT name FROM timelapses WHERE id = c.active_timelapse_id
) t ON true

# Avoid N+1 queries - fetch related data in single query
# Use async_db for web requests, sync_db for worker processes
# Index foreign keys and frequently queried columns
```

### Component Development Patterns

```typescript
// Always use existing hooks for data fetching
const { cameras, isLoading } = useRealtimeCameras()
const { timezone } = useCaptureSettings()

// Follow established patterns for new components
const NewComponent = () => {
  // 1. Use existing hooks for data
  // 2. Handle loading states
  // 3. Use toast notifications for feedback
  // 4. Follow timezone-aware time display patterns
}
```

### Debugging Workflow

```bash
# Check service health first
curl http://localhost:3000/api/health
curl http://localhost:8000/api/health

# Monitor logs for specific issues
tail -f data/worker.log | grep ERROR
tail -f data/worker.log | grep "camera_id: {id}"

# Verify SSE connections
# Browser console should show: "✅ SSE connected successfully"

# Database debugging
psql $DATABASE_URL -c "SELECT * FROM cameras WHERE health_status = 'offline';"
```

## 🐛 ENHANCED TROUBLESHOOTING

### Service Startup Issues

```bash
# Use the enhanced startup script with health checks
./start-services.sh

# If startup fails, check individual components:
# 1. Check ports aren't in use
lsof -i :3000,8000

# 2. Verify environment variables
cat backend/.env

# 3. Check Python dependencies
cd backend && source venv/bin/activate && pip list | grep -E "(psycopg|fastapi|opencv)"

# 4. Verify Node.js dependencies
npm list | grep -E "(next|react)"
```

### SSE Event Issues (Fixed)

```bash
# Test SSE connection directly
curl http://localhost:3000/api/events

# Test event broadcasting (should return success)
curl -X POST http://localhost:3000/api/events \
  -H "Content-Type: application/json" \
  -d '{"type":"test_event","message":"test"}'

# Check worker logs for event broadcasting
tail -f data/worker.log | grep "Broadcasted SSE event"
```

### Database Connection Issues (Fixed)

```bash
# Test comprehensive health (should return "healthy")
curl http://localhost:8000/api/health

# Check Neon database connectivity
psql "postgresql://neondb_owner:npg_JYrHT0d7Gpzo@ep-polished-wind-a81rqv6u-pooler.eastus2.azure.neon.tech/neondb?sslmode=require" -c "SELECT 1;"
```

## 🔒 SECURITY & FILE SYSTEM PATTERNS

### RTSP URL Validation (CRITICAL)

```python
# Pydantic model in camera.py handles RTSP validation
class CameraBase(BaseModel):
    rtsp_url: str

    @validator('rtsp_url')
    def validate_rtsp_url(cls, v):
        if not v.startswith(('rtsp://', 'http://', 'https://')):
            raise ValueError('Invalid RTSP URL format')
        # Additional validation for security
        return v
```

### File Path Security Patterns

```python
# NEVER use user input directly in file paths
# Always use predefined patterns with validation

# CORRECT pattern:
def get_image_path(camera_id: int, date: str, filename: str):
    # Validate inputs
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        raise ValueError("Invalid date format")
    if not re.match(r'^capture_\d{8}_\d{6}\.jpg$', filename):
        raise ValueError("Invalid filename format")

    return f"data/cameras/camera-{camera_id}/images/{date}/{filename}"

# NEVER do this:
# return f"data/{user_input_path}"  # Path traversal vulnerability
```

### Directory Structure Security

```text
data/
├── cameras/camera-{id}/           # Camera ID must be integer, validated
│   ├── images/YYYY-MM-DD/         # Date format strictly validated
│   ├── thumbnails/YYYY-MM-DD/     # Separate folders prevent confusion
│   └── small/YYYY-MM-DD/
├── videos/                        # Generated videos with metadata
└── logs/                          # Application logs, not user data
```

### File Permission Patterns

```python
# Always set proper file permissions
os.chmod(filepath, 0o644)  # Read/write owner, read others

# For directories
os.makedirs(directory, mode=0o755, exist_ok=True)  # Standard directory permissions

# NEVER use 0o777 permissions - security risk
```

### Input Sanitization

```python
# Sanitize all user inputs before database/filesystem operations
def sanitize_camera_name(name: str) -> str:
    # Remove special characters, limit length
    return re.sub(r'[^a-zA-Z0-9\s\-_]', '', name)[:50]

# Validate numeric inputs
def validate_camera_id(camera_id: int) -> int:
    if not isinstance(camera_id, int) or camera_id <= 0:
        raise ValueError("Invalid camera ID")
    return camera_id
```

## 📈 PERFORMANCE & RESOURCE MANAGEMENT

### Connection Pool Monitoring

```python
# Monitor connection pool usage
@router.get("/api/health/connections")
async def connection_health():
    return {
        "async_pool": {
            "size": async_db.pool.get_size(),
            "available": async_db.pool.get_available(),
            "idle": async_db.pool.get_idle_size()
        },
        "sync_pool": {
            "size": sync_db.pool.get_size(),
            "available": sync_db.pool.get_available()
        }
    }
```

### Memory Management for Image Processing

```python
# Always close OpenCV resources
cap = cv2.VideoCapture(rtsp_url)
try:
    ret, frame = cap.read()
    # Process frame
finally:
    cap.release()  # CRITICAL: Always release capture resources

# For Pillow image processing
with Image.open(image_path) as img:
    # Process image
    thumbnail = img.copy()
    thumbnail.thumbnail((200, 150), Image.Resampling.LANCZOS)
# Image automatically closed after with block
```

### File Handle Management

```python
# Always use context managers for file operations
with open(filepath, 'wb') as f:
    f.write(image_data)

# For database operations
with sync_db.get_connection() as conn:
    # Database operations
    pass
# Connection automatically returned to pool
```

### Performance Optimization Guidelines

```python
# Batch database operations when possible
def record_multiple_images(images: List[ImageData]):
    with sync_db.get_connection() as conn:
        conn.executemany(
            "INSERT INTO images (camera_id, file_path, captured_at) VALUES (?, ?, ?)",
            [(img.camera_id, img.file_path, img.captured_at) for img in images]
        )

# Use database indexes for frequently queried columns
# Index on: camera_id, captured_at, timelapse_id
# Composite index on: (camera_id, captured_at) for latest image queries
```

### Resource Cleanup Patterns

```python
# Cleanup old files based on retention policies
def cleanup_old_images(days_to_keep: int = 30):
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    # Remove files older than cutoff
    for camera_dir in Path("data/cameras").iterdir():
        for date_dir in camera_dir.iterdir():
            if date_dir.is_dir():
                date_obj = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if date_obj < cutoff_date:
                    shutil.rmtree(date_dir)

    # Remove database records for deleted files
    with sync_db.get_connection() as conn:
        conn.execute(
            "DELETE FROM images WHERE captured_at < ?",
            (cutoff_date,)
        )
```

## 🚀 PRODUCTION DEPLOYMENT CONSIDERATIONS

### Environment Configuration

```bash
# Production .env differences
DATABASE_URL=postgresql://prod_user:secure_pass@prod_host/prod_db
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
ENVIRONMENT=production

# Development .env
DATABASE_URL=postgresql://neondb_owner:...@neon.tech/neondb
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
ENVIRONMENT=development
```

### Docker Deployment Preparation

```dockerfile
# Dockerfile patterns for production
FROM python:3.11-slim

# Install system dependencies for OpenCV and image processing
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgl1-mesa-glx

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Run as non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1
```

### Backup Strategies

```bash
# Database backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# File system backup (images and videos)
tar -czf images_backup_$(date +%Y%m%d).tar.gz data/cameras/
tar -czf videos_backup_$(date +%Y%m%d).tar.gz data/videos/

# Exclude thumbnails from backups (regeneratable)
tar --exclude='*/thumbnails/*' --exclude='*/small/*' -czf images_only_backup.tar.gz data/cameras/
```

### Monitoring & Alerting Patterns

```python
# Production monitoring endpoints
@router.get("/api/health/detailed")
async def detailed_health():
    return {
        "database": await check_database_health(),
        "disk_space": get_disk_usage(),
        "memory_usage": get_memory_usage(),
        "active_cameras": get_active_camera_count(),
        "recent_errors": get_recent_error_count(),
        "worker_status": check_worker_health()
    }

# Critical metrics to monitor:
# - Database connection pool utilization
# - Disk space in data/ directory
# - Memory usage during image processing
# - RTSP connection failure rates
# - SSE connection count and stability
```

### Production Service Management

```bash
# Systemd service for production
# /etc/systemd/system/timelapser-worker.service
[Unit]
Description=Timelapser Worker Process
After=network.target

[Service]
Type=simple
User=timelapser
WorkingDirectory=/opt/timelapser
ExecStart=/opt/timelapser/venv/bin/python worker.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/timelapser

[Install]
WantedBy=multi-user.target
```

### SSL/HTTPS Configuration

```nginx
# Nginx configuration for production
server {
    listen 443 ssl;
    server_name yourdomain.com;

    # SSL certificates
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/private.key;

    # Frontend (Next.js)
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE connections need special handling
    location /api/events {
        proxy_pass http://localhost:3000/api/events;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_cache off;
    }
}
```

## 🔍 TROUBLESHOOTING

**Health Checks**:

- Frontend + Backend: `http://localhost:3000/api/health`
- Backend Only: `http://localhost:8000/api/health`
- Comprehensive: `./diagnostic-test.sh`

**Common Issues**:

- **Service startup**: Use `./start-services.sh` with health coordination
- **SSE events**: Check browser console for "Dashboard SSE event" messages
- **Image loading**: Verify thumbnail fallback chain working
- **Timezone display**: Ensure database timezone setting matches expectations

### 🧪 TESTING PATTERNS

**Validate Core Functionality**:

```bash
# 1. Start system
./start-services.sh

# 2. Add camera with valid RTSP URL
# 3. Start new timelapse (creates entity)
# 4. Watch real-time dashboard updates
# 5. Verify files: data/cameras/camera-{id}/images/YYYY-MM-DD/
```

**SSE Event Testing**:

- Browser console should show: "✅ SSE connected successfully"
- Dashboard events: "Dashboard SSE event: image_captured"
- Image counts update in real-time without refresh

**Database Validation**:

```sql
-- Verify entity-based architecture
SELECT c.id, c.active_timelapse_id, t.name, t.status
FROM cameras c
LEFT JOIN timelapses t ON c.active_timelapse_id = t.id;

-- Check image associations
SELECT COUNT(*) as total_images,
       COUNT(CASE WHEN t.status = 'running' THEN 1 END) as current_images
FROM images i
LEFT JOIN timelapses t ON i.timelapse_id = t.id
WHERE i.camera_id = {camera_id};
```

### 🎨 RECENT DASHBOARD ENHANCEMENTS

**Camera Card Features**:

- **Progress borders**: Animated egg-timer effect showing capture progress
- **Dual statistics**: "Images - Total: 1,250, Current: 47" display
- **Capture Now**: Manual capture trigger (hamburger menu)
- **Enhanced status badges**: Simplified logic with switch statements
- **New timelapse dialog**: Advanced configuration with auto-stop, custom time
  windows

**Real-time Countdown**:

- **Smart refresh intervals**: 1-second updates when under 5 minutes
- **Absolute time display**: Date/time context under countdowns
- **Timezone abbreviations**: CDT, UTC, etc. using Intl API
- **"Now" state feedback**: Pulsing cyan effects during capture

## 📞 SUPPORT & MAINTENANCE

### Regular Maintenance Tasks

- Monitor disk usage in `data/` directory
- Review logs for recurring errors (`tail -f data/worker.log`)
- Run diagnostic script weekly: `./diagnostic-test.sh`
- Update dependencies monthly
- Backup database schema and critical settings
- Test disaster recovery procedures

### Health Check Schedule

```bash
# Daily automated health check
curl -f http://localhost:3000/api/health || echo "System unhealthy"

# Weekly comprehensive diagnostic
./diagnostic-test.sh

# Monthly deep health analysis
curl -s http://localhost:8000/api/health/stats | python3 -m json.tool
```

---

**Last Updated**: December 17, 2025  
**System Status**: ✅ Fully Operational - All Critical Features Working
