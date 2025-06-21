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
SSEProvider (1 connection)                    RTSP Cameras
       ↕
All Components
```

**Why This Architecture**:

- **Centralized SSE Real-time Updates**: Single SSE connection via React Context, shared across all components (prevents 79+ connection spam)
- **SSE Proxy Pattern**: Frontend → Next.js API → FastAPI SSE avoids CORS issues
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

### Real-time Event System Rules (CRITICAL - Performance Impact)

1. **NEVER create individual EventSource connections** - Each component using `new EventSource("/api/events")` creates separate connections
2. **ALWAYS use centralized SSE system** - Single connection via `<SSEProvider>` in app layout
3. **Use specialized hooks for event subscriptions**:
   - `useCameraSSE(cameraId, callbacks)` - Camera-specific events
   - `useDashboardSSE(callbacks)` - Global dashboard events  
   - `useSSESubscription(filter, callback)` - Custom event filtering
4. **No console.log spam** - SSE connections should be silent after initial establishment
5. **Connection sharing principle** - All components share one SSE connection, never create multiple
6. **Event filtering at component level** - Filter by camera_id or event type in hooks, not in API
7. **Proper cleanup** - Hooks handle subscription/unsubscription automatically

**Why This Matters**: Multiple EventSource connections caused 79+ simultaneous connections with rapid cycling. Centralized system achieves 99% connection reduction while maintaining same real-time functionality.

**Files in Centralized SSE System**:
- `/src/contexts/sse-context.tsx` - Single connection management
- `/src/hooks/use-camera-sse.ts` - Specialized event hooks
- Components use hooks, never direct EventSource connections

**SSE Event Structure (CRITICAL)**:
- **ALWAYS use proper event structure**: `{ type, data: {...}, timestamp }`
- ✅ Correct: `event.data.camera_id`, `event.data.image_count`, `event.data.status`
- ❌ Wrong: `event.camera_id` (data directly on event object)
- All events MUST nest data under the `data` property for consistency

### Corruption Detection System Rules (CRITICAL - Quality Control)

1. **NEVER bypass corruption integration** - All image captures must go through corruption detection pipeline
2. **ALWAYS use WorkerCorruptionIntegration.evaluate_with_retry()** - Never call RTSPCapture.capture_image() directly
3. **Use per-camera heavy detection settings** - Respect `corruption_detection_heavy` flag from database
4. **NEVER skip corruption scoring** - Every captured image must receive a corruption score (0-100)
5. **Proper retry logic** - Failed corruption checks trigger automatic retry when auto-discard enabled
6. **Database logging required** - All corruption evaluations must be logged to `corruption_logs` table
7. **SSE events for corruption** - Broadcast corruption events for real-time UI updates
8. **Graceful degradation** - System continues if corruption detection fails, with error logging

**Corruption Detection Integration Pattern**:
```python
# ✅ CORRECT - Corruption-aware capture
success, message, file_path, corruption_details = self.corruption_integration.evaluate_with_retry(
    camera_id, rtsp_url, capture_func, timelapse_id
)

# ❌ WRONG - Direct capture bypasses corruption detection  
success, message, file_path = self.capture.capture_image(...)
```

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
- **Non-existent image endpoints** - Never reference `/api/images/{id}/thumbnail`
- **Simple browser-local time calculations** - Always use timezone-aware system
- **Individual EventSource connections** - Creates connection spam (79+ connections), use centralized SSE system only
- **Direct RTSP capture calls** - Always use corruption detection wrapper
- **eventEmitter for corruption events** - Use SSE subscriptions only
- **Manual corruption scoring** - Use CorruptionController.evaluate_frame()
- **Hardcoded corruption thresholds** - Load from database settings

## 🛡️ CORRUPTION DETECTION SYSTEM ARCHITECTURE

**Purpose**: Automatically detect and handle corrupted images from RTSP cameras to ensure professional-quality timelapses.

### **Core Components Architecture**
```
RTSP Capture → CorruptionController → FastDetector + HeavyDetector → ScoreCalculator → ActionHandler → Database + Events
```

**Component Breakdown**:
- **CorruptionController**: Central orchestrator managing the detection pipeline
- **FastDetector**: Lightweight heuristic checks (1-5ms) - always enabled
- **HeavyDetector**: Computer vision analysis (20-100ms) - per-camera optional  
- **ScoreCalculator**: Weighted scoring algorithm (0-100 scale)
- **ActionHandler**: Retry/discard logic based on corruption scores
- **HealthMonitor**: Camera degraded mode tracking

### **Integration Architecture**
```
Worker.capture_from_camera() → WorkerCorruptionIntegration.evaluate_with_retry() → CorruptionController.evaluate_frame() → Database.log_corruption_detection() → SSE Events
```

**Critical Integration Points**:
1. **Worker Integration**: `AsyncTimelapseWorker.__init__()` initializes corruption detection
2. **Capture Pipeline**: Every image capture goes through corruption evaluation
3. **Database Logging**: All evaluations logged to `corruption_logs` table
4. **Real-time Events**: Corruption events broadcast via SSE system
5. **Per-Camera Settings**: Heavy detection enabled/disabled per camera

### **Scoring Algorithm**
```
Starting Score: 100 (Perfect Image)
Final Score = max(0, Starting Score - Total Penalties)

Score Ranges:
- 90-100: Excellent quality (save)
- 70-89:  Good quality (save)  
- 50-69:  Acceptable quality (save)
- 30-49:  Poor quality (flag for review)
- 0-29:   Severely corrupted (auto-discard candidate)

Weighted Combination (when Heavy Detection enabled):
Final Score = (Fast_Score * 30%) + (Heavy_Score * 70%)
```

### **Fast Detection Checks (Always Enabled)**
- **File Size Validation**: 25KB minimum, 10MB maximum
- **Pixel Statistics**: Mean intensity, variance, uniformity analysis
- **Basic Validity**: Image dimensions, channel count, data type verification
- **Performance**: 1-5ms per image

### **Heavy Detection Checks (Per-Camera Optional)**  
- **Blur Detection**: Laplacian variance analysis (threshold: 100)
- **Edge Analysis**: Canny edge detection with density measurement (1%-50% range)
- **Noise Detection**: Median filter comparison for noise ratio (max 30%)
- **Histogram Analysis**: Entropy calculation for color distribution (min 3.0)
- **Pattern Detection**: 8x8 block uniformity for JPEG corruption (max 80%)
- **Performance**: 20-100ms per image

### **Database Schema (Corruption Tables)**
```sql
-- Corruption detection logs
CREATE TABLE corruption_logs (
    id SERIAL PRIMARY KEY,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE CASCADE,
    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
    corruption_score INTEGER NOT NULL CHECK (corruption_score >= 0 AND corruption_score <= 100),
    fast_score INTEGER CHECK (fast_score >= 0 AND fast_score <= 100),
    heavy_score INTEGER CHECK (heavy_score >= 0 AND heavy_score <= 100),
    detection_details JSONB NOT NULL,
    action_taken VARCHAR(50) NOT NULL, -- 'saved', 'discarded', 'retried'
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Additional fields in existing tables
ALTER TABLE images ADD COLUMN corruption_score INTEGER DEFAULT 100;
ALTER TABLE images ADD COLUMN is_flagged BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN corruption_detection_heavy BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN degraded_mode_active BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN consecutive_corruption_failures INTEGER DEFAULT 0;
ALTER TABLE cameras ADD COLUMN lifetime_glitch_count INTEGER DEFAULT 0;
```

### **SSE Events for Corruption Detection**
```typescript
// Corruption detection event
{
  type: "image_corruption_detected",
  data: {
    camera_id: number,
    corruption_score: number,
    is_corrupted: boolean,
    action_taken: string,
    failed_checks: string[],
    processing_time_ms: number
  },
  timestamp: string
}

// Camera degraded mode event  
{
  type: "camera_degraded_mode_triggered", 
  data: {
    camera_id: number,
    consecutive_failures: number,
    degraded_mode_active: boolean
  },
  timestamp: string
}

// Corruption reset event
{
  type: "camera_corruption_reset",
  data: {
    camera_id: number,
    degraded_mode_reset: boolean
  },
  timestamp: string
}
```

### **File Structure for Corruption Detection**
```
backend/
├── corruption_detection/
│   ├── __init__.py
│   ├── controller.py          # CorruptionController main class
│   ├── fast_detector.py       # FastDetector implementation
│   ├── heavy_detector.py      # HeavyDetector implementation  
│   ├── score_calculator.py    # Scoring algorithms
│   ├── action_handler.py      # Retry/discard logic
│   └── health_monitor.py      # Degraded mode tracking
├── worker_corruption_integration.py  # Worker integration wrapper
└── app/
    ├── models/corruption.py    # Pydantic models
    └── routers/corruption.py   # API endpoints

frontend/
├── src/
│   ├── components/
│   │   ├── corruption-indicator.tsx    # UI indicators
│   │   └── corruption-settings-card.tsx  # Settings UI
│   ├── hooks/
│   │   └── use-corruption-stats.ts     # SSE-based corruption hooks
│   └── types/
│       └── corruption.ts              # TypeScript interfaces
```

### **Performance Specifications**
```
Fast Detection: < 5ms per image
Heavy Detection: < 100ms per image  
Database Logging: < 10ms per result
Total Overhead: < 110ms per capture (when heavy enabled)

Memory Usage:
- Fast Detection: < 1MB working memory
- Heavy Detection: < 5MB working memory

Throughput Impact:
- Baseline (no detection): ~200ms per capture
- With Fast Only: ~205ms per capture (+2.5%)
- With Fast + Heavy: ~300ms per capture (+50%)
```

### **Configuration Hierarchy**
```
Global App Settings (Base Defaults)
├── corruption_detection_enabled: true
├── corruption_score_threshold: 70
├── corruption_auto_discard_enabled: false
└── corruption_auto_disable_degraded: false

Per-Camera Settings (Overrides)  
└── corruption_detection_heavy: false (per camera)
```

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

### API Endpoint 404 Debugging Pattern (June 20, 2025)

**Problem**: Multiple 404 errors for timelapse endpoints and event structure
violations **Root Cause**: Missing API endpoints and incorrect SSE event
structure

**Systematic Debugging Approach**:

1. **Start with error message** - Identify the failing endpoint (e.g.,
   `/api/timelapses/[id]/complete`)
2. **Check frontend structure** - Verify Next.js API route exists at
   `/src/app/api/`
3. **Check backend structure** - Verify FastAPI endpoint exists at
   `/backend/app/routers/`
4. **Check database methods** - Verify required database methods exist in
   `/backend/app/database.py`
5. **Verify event structure** - Ensure all events follow
   `{ type, data, timestamp }` format

**Specific Issues Fixed**:

- Missing `/api/timelapses/[id]/complete` endpoint (both frontend and backend
  connectivity)
- Missing `/api/timelapses/[id]` GET endpoint for single timelapse retrieval
- Added `get_timelapse_by_id()` database method for single timelapse queries
- Fixed SSE event structure violations (data directly on event object instead of
  nested under `data`)
- Updated invalid event types to use approved `ALLOWED_EVENT_TYPES`
- Fixed Next.js 15 async params compatibility (params must be awaited)

**Pattern Recognition**:

- API development requires **complete chain**: Database method → Backend router
  → Frontend proxy → UI
- Missing any link in this chain causes 404 errors
- Event structure violations break real-time updates silently

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

### 8. **"Each component should handle its own real-time events with EventSource"**

❌ **Why This Causes Connection Spam**:

- Creates 79+ simultaneous SSE connections (dashboard + each camera card + modals)
- Rapid connection cycling every 500ms with aggressive reconnection timers
- Massive performance impact and console spam
- Server overload handling multiple connections from same client
- Duplicates event handling logic across components
- **Solution**: Centralized SSE via React Context with single shared connection

**Real Example**: Camera dashboard with 10 cameras = 12+ connections (dashboard + 10 cards + modals). Fixed with SSEProvider pattern achieving 99% connection reduction.

### 9. **"Corruption detection can be added as an optional post-processing step"**

❌ **Why This Defeats the Purpose**:

- Corruption detection must happen **during capture pipeline** to enable retry logic
- Post-processing can't retry failed captures - the moment is gone
- Auto-discard functionality requires real-time evaluation during capture
- Database integrity requires corruption scoring before image record creation  
- **Solution**: Integrate corruption detection into `WorkerCorruptionIntegration.evaluate_with_retry()`

### 10. **"We can simplify by using the same corruption threshold for all cameras"**

❌ **Why Per-Camera Settings Are Essential**:

- Different camera hardware has different noise/quality characteristics
- Indoor vs outdoor cameras have vastly different corruption patterns
- Heavy detection (computer vision) may be too slow for high-frequency captures on some cameras
- Camera-specific corruption_detection_heavy settings allow fine-tuned performance
- **Solution**: Load per-camera settings from database and respect individual camera configurations

### 11. **"Fast detection is enough - heavy detection is just unnecessary overhead"**

❌ **Why Both Detection Levels Are Needed**:

- Fast detection catches obvious corruption (file size, basic pixel issues) but misses subtle problems
- Heavy detection catches blur, noise, compression artifacts that fast detection can't detect  
- Weighted scoring (30% fast + 70% heavy) provides comprehensive quality assessment
- Per-camera enablement allows optimization - enable heavy detection only where needed
- Professional timelapses require thorough quality control, not just basic file validation
- **Solution**: Use both detection levels with per-camera heavy detection configuration

### 12. **"Corruption events should use direct eventEmitter for better performance"**

❌ **Why This Breaks the SSE Architecture**:

- Creates the same connection spam problem that was solved for regular camera events
- Bypasses the centralized SSE system that achieves 99% connection reduction
- eventEmitter is for internal component state, not real-time data synchronization
- Corruption events must follow the same `{ type, data: {...}, timestamp }` structure
- **Solution**: Use `useSSESubscription` for corruption events like all other real-time updates

## 🗄️ DATABASE SCHEMA

**Core Relationships**:

```
cameras (1) ──► timelapses (many) ──► images (many)
timelapses (1) ──► videos (many)
cameras (1) ──► corruption_logs (many)
images (1) ──► corruption_logs (0..1)
```

**Key Tables**:

- `cameras`: RTSP config, health status, time windows, video settings, corruption settings
- `timelapses`: Recording sessions with entity-based architecture
- `images`: Captures linked to timelapse, day_number calculation, corruption scores
- `videos`: Generated MP4s with overlay settings
- `settings`: Global config including timezone and corruption detection settings
- `corruption_logs`: Detailed corruption detection audit trail with scores and actions

**Corruption Detection Schema**:

```sql
-- Corruption detection audit trail
CREATE TABLE corruption_logs (
    id SERIAL PRIMARY KEY,
    camera_id INTEGER REFERENCES cameras(id) ON DELETE CASCADE,
    image_id INTEGER REFERENCES images(id) ON DELETE CASCADE,
    corruption_score INTEGER NOT NULL CHECK (corruption_score >= 0 AND corruption_score <= 100),
    fast_score INTEGER CHECK (fast_score >= 0 AND fast_score <= 100),
    heavy_score INTEGER CHECK (heavy_score >= 0 AND heavy_score <= 100),
    detection_details JSONB NOT NULL,
    action_taken VARCHAR(50) NOT NULL, -- 'saved', 'discarded', 'retried'
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Corruption fields in existing tables
ALTER TABLE images ADD COLUMN corruption_score INTEGER DEFAULT 100;
ALTER TABLE images ADD COLUMN is_flagged BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN corruption_detection_heavy BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN degraded_mode_active BOOLEAN DEFAULT false;
ALTER TABLE cameras ADD COLUMN consecutive_corruption_failures INTEGER DEFAULT 0;
ALTER TABLE cameras ADD COLUMN lifetime_glitch_count INTEGER DEFAULT 0;
```

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

**Image Capture (with Corruption Detection)**:

1. Worker captures RTSP frame every 5 minutes using OpenCV
2. **Corruption Detection Pipeline**:
   - Fast Detection: File size, pixel statistics, uniformity (1-5ms)
   - Heavy Detection: Blur, edge, noise, histogram analysis (20-100ms, if enabled)
   - Score Calculation: Weighted scoring algorithm (0-100 scale)
   - Action Decision: Save, retry, or discard based on score vs threshold
3. **Retry Logic**: If corruption score < threshold and auto-discard enabled, retry once
4. Save to filesystem: `/data/cameras/camera-{id}/images/YYYY-MM-DD/capture_YYYYMMDD_HHMMSS.jpg`
5. Generate thumbnails (if enabled) using Pillow with separate folders
6. **Corruption Logging**: Record evaluation results in `corruption_logs` table
7. Record in database: `sync_db.record_captured_image()` with corruption score and timelapse relationship
8. Update camera health and corruption stats: `sync_db.update_camera_health()` + `sync_db.update_camera_corruption_stats()`
9. **Degraded Mode Check**: Monitor consecutive failures and trigger degraded mode if thresholds exceeded
10. Broadcast SSE events: `sync_db.broadcast_event()` with corruption details for real-time UI

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
- **Centralized SSE System** - Single connection shared across all components (99% connection reduction)
- **SSE Connection Health** - Visual indicator for live updates
- **Error Broadcasting** - Failed captures show immediately
- **Corruption Detection Events** - Real-time corruption score updates
- **Degraded Mode Alerts** - Live camera quality issue notifications
- **Quality Statistics Updates** - System-wide corruption stats refresh automatically

### ✅ CORE FUNCTIONALITY (Production Ready)

- **RTSP Camera Management** - Add, edit, delete cameras with validation
- **Time Window Controls** - Capture only during specified hours
- **Automated Image Capture** - Scheduled captures every 5 minutes (configurable) with corruption detection
- **Image Quality Control** - Automatic corruption detection with fast and heavy analysis modes
- **Intelligent Retry Logic** - Corrupted images automatically retried when auto-discard enabled
- **Camera Health Monitoring** - Automatic offline detection, recovery, and degraded mode tracking
- **Per-Camera Quality Settings** - Individual heavy detection configuration for optimal performance
- **Quality Score Database** - Complete corruption audit trail with 0-100 scoring system
- **Degraded Mode Protection** - Automatic camera management when quality issues persist
- **Video Generation** - FFmpeg integration with quality settings
- **Database Tracking** - Complete image and video metadata with corruption scores
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

# Corruption Detection System
GET /api/corruption/stats           # System-wide corruption statistics
GET /api/corruption/cameras/{id}/stats # Per-camera corruption details
GET /api/corruption/logs            # Corruption detection audit logs
POST /api/corruption/cameras/{id}/reset-degraded # Reset camera degraded mode
GET /api/corruption/settings        # Global corruption detection settings
PATCH /api/corruption/settings      # Update corruption detection settings

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

### Real-time Event Patterns (SSE)

```typescript
// Camera-specific real-time events
import { useCameraSSE } from "@/hooks/use-camera-sse"

const CameraComponent = ({ camera }) => {
  useCameraSSE(camera.id, {
    onImageCaptured: (data) => {
      // Handle new image captured
      setImageKey(Date.now()) // Force refresh
    },
    onStatusChanged: (data) => {
      // Handle camera status change
    },
    onTimelapseStatusChanged: (data) => {
      // Handle timelapse start/stop/pause
    },
  })
}

// Dashboard-wide events
import { useDashboardSSE } from "@/hooks/use-camera-sse"

const DashboardComponent = () => {
  useDashboardSSE({
    onCameraAdded: (data) => {
      setCameras(prev => [data.camera, ...prev])
    },
    onVideoGenerated: (data) => {
      setVideos(prev => [data.video, ...prev])
    },
  })
}

// Custom event filtering
import { useSSESubscription } from "@/contexts/sse-context"

const ModalComponent = () => {
  useSSESubscription(
    (event) => event.type === "thumbnail_regeneration_progress",
    (event) => {
      setProgress(event.progress) // ✅ Data directly on event object
    },
    [isOpen] // Dependencies for subscription
  )
}

// NEVER do this (creates individual connections):
// ❌ const eventSource = new EventSource("/api/events")
// ❌ Multiple EventSource connections per component
// ✅ Always use the centralized SSE hooks above
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

## 🔍 ARCHITECTURE VALIDATION & CODE QUALITY (June 18, 2025)

### Comprehensive Codebase Review Results

**Validation Scope**: All recently changed files reviewed for compliance with
AI-CONTEXT architectural rules and patterns.

**✅ Database Pattern Compliance**:

- All backend Python code properly uses `psycopg3` with `dict_row` for both
  async and sync connection pools
- Type-safe dictionary-style database access implemented consistently
- No raw SQL cursor usage without proper row factory configuration

**✅ Time Calculation & Timezone Compliance**:

- Frontend consistently uses `useCaptureSettings()` hook for timezone-aware
  calculations
- All countdown and time display components properly pass timezone parameters
- No raw `new Date()` or browser timezone usage in production code

**✅ Entity-Based Architecture Compliance**:

- All API routes follow entity-based patterns for timelapse creation and
  management
- Worker processes respect `active_timelapse_id` relationships for image capture
- Entity lifecycle workflows (new/paused/stopped/completed/archived) properly
  implemented

**✅ Event System Architecture**:

- SSE event emitter refactored to shared module at `src/lib/event-emitter.ts`
- Security measures and type validation implemented for all event types
- Singleton pattern properly implemented with proper cleanup and error handling

**✅ Type Safety**:

- TypeScript models and interfaces updated to match Pydantic changes
- All API endpoints use consistent type definitions

**✅ Build System & Development Environment**:

- `.tsbuildinfo` files properly excluded from git tracking (added to
  `.gitignore`)
- TypeScript configuration excludes documentation directories from compilation
- Build cache management follows best practices

**✅ Code Quality Improvements**:

- Removed all production `console.log` statements for cleaner output
- Fixed critical bugs discovered during log statement removal
- Resolved all TypeScript and Python type errors
- Enhanced error handling and user feedback systems

### API Development & Event System Rules

1. **SSE Event Structure is SACRED** - All events MUST follow exact `SSEEvent`
   interface: `{ type, data, timestamp }`
   - **NEVER** put data directly on the event object (e.g.,
     `{ type, camera_id, status }`)
   - **ALWAYS** nest under data property:
     `{ type, data: { camera_id, status }, timestamp }`
   - Violating this breaks the entire real-time system
2. **Event Types Must Be Pre-Approved** - Only use event types from
   `ALLOWED_EVENT_TYPES` constant in event-emitter.ts
   - Don't create new event types without adding them to the allowed list
   - Use existing types like `"video_status_changed"` instead of custom ones
     like `"video_failed"`
3. **API Endpoint Completeness Pattern** - When adding new endpoints, BOTH
   pieces are required:
   - Backend FastAPI endpoint in `/backend/app/routers/`
   - Frontend Next.js proxy route in `/src/app/api/`
   - Missing either piece causes 404 errors that are hard to debug
4. **Database Method Dependency** - Router endpoints that call database methods
   require the method to exist
   - Check `/backend/app/database.py` for required methods like
     `get_timelapse_by_id()`
   - Follow naming patterns: `get_*`, `create_*`, `update_*`, `complete_*`
5. **Next.js 15 Async Params** - All dynamic route parameters are now Promises
   - **ALWAYS** await params: `const { id } = await params`
   - Route signature: `{ params }: { params: Promise<{ id: string }> }`

### System-Wide Constraints
