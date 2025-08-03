# Thumbnail Pipeline Service

## Overview

The Thumbnail Pipeline is the unified interface for all thumbnail generation
operations in Timelapser v4. It follows the **Scheduler CEO Architecture** where
the SchedulerWorker coordinates all timing decisions, and services execute tasks
when instructed.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Router Layer   │    │  Pipeline Layer  │    │  Database Layer  │
├─────────────────┤    ├──────────────────┤    ├──────────────────┤
│thumbnail_routers│───▶│ThumbnailPipeline │───▶│thumbnail_job_ops │
│                 │    │                  │    │image_operations  │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                                ↕
                    ┌──────────────────┐
                    │SchedulerWorker   │
                    │     (CEO)        │
                    └──────────────────┘
```

## 📁 Service Structure

```
thumbnail_pipeline/
├── README.md                    # This file
├── thumbnail_pipeline.py        # Main unified interface
├── services/                    # Business logic services
│   ├── job_service.py          # Job queue management
│   ├── performance_service.py  # Performance monitoring
│   ├── verification_service.py # File verification
│   └── repair_service.py       # Orphaned file repair
├── generators/                  # Image processing
│   ├── thumbnail_generator.py  # 200x150 thumbnails
│   ├── small_image_generator.py # 800x600 small images
│   └── batch_generator.py      # Batch processing
└── utils/                      # Utilities
    └── thumbnail_utils.py      # Helper functions
```

## 🔄 Ecosystem Integration

### 1. Router Integration

**File**: `/backend/app/routers/thumbnail_routers.py`

All thumbnail HTTP endpoints delegate to ThumbnailPipeline:

```python
@router.post("/thumbnails/regenerate-all")
async def start_thumbnail_regeneration(thumbnail_pipeline: ThumbnailPipelineDep):
    return await thumbnail_pipeline.start_thumbnail_regeneration_background()
```

### 2. Scheduler CEO Integration

**File**: `/backend/app/workers/scheduler_worker.py`

Individual thumbnail requests follow CEO pattern:

```python
# Correct: Routes through SchedulerService (CEO)
scheduler_result = await scheduler_service.schedule_immediate_thumbnail_generation(
    image_id=image_id, priority=JobPriority.MEDIUM
)
```

### 3. Capture Pipeline Integration

**File**: `/backend/app/services/capture_pipeline/job_coordination_service.py`

After image capture, jobs are queued (not immediately executed):

```python
# Capture creates jobs, SchedulerWorker coordinates timing
job_id = self.job_queue_service.create_thumbnail_job(
    image_id=image_id, priority=priority
)
```

### 4. Worker Processing

**File**: `/backend/app/workers/thumbnail_worker.py`

ThumbnailWorker processes jobs when SchedulerWorker determines timing:

```python
result = thumbnail_pipeline.process_image_thumbnails(image_id)
```

## 🎯 ThumbnailPipeline Interface

### Initialization

```python
# Async interface (for API endpoints)
pipeline = ThumbnailPipeline(async_database=async_db)

# Sync interface (for workers)
pipeline = ThumbnailPipeline(database=sync_db)

# Factory functions available
from .thumbnail_pipeline import create_async_thumbnail_pipeline
pipeline = create_async_thumbnail_pipeline(async_db)
```

### Key Methods

#### Job Management

```python
# Queue single job
job_id = await pipeline.queue_thumbnail_job(
    image_id=123,
    priority=ThumbnailJobPriority.MEDIUM,
    force_regenerate=False
)

# Get queue statistics
stats = await pipeline.get_job_statistics()
```

#### Bulk Operations (Router Integration)

```python
# Start bulk regeneration (returns immediately, processes in background)
response = await pipeline.start_thumbnail_regeneration_background(limit=1000)
# Returns: ThumbnailOperationResponse

# Check status
status = await pipeline.get_thumbnail_regeneration_status()
# Returns: ThumbnailRegenerationStatus

# Cancel active jobs
result = await pipeline.cancel_thumbnail_regeneration()
```

#### System Management

```python
# Verify all thumbnails exist and are valid
result = await pipeline.verify_all_thumbnails()

# Repair orphaned files (match files to database)
result = await pipeline.repair_orphaned_thumbnails()

# Clean up orphaned files
result = await pipeline.cleanup_orphaned_thumbnails(dry_run=True)

# Delete all thumbnails
result = await pipeline.delete_all_thumbnails()
```

## 🔧 Service Dependencies

### Database Operations

- **ThumbnailJobOperations**: Job queue management
- **ImageOperations**: Image metadata and thumbnail path tracking

### Sub-Services

- **ThumbnailJobService**: Queue management and statistics
- **ThumbnailVerificationService**: File integrity checking
- **ThumbnailRepairService**: Orphaned file recovery
- **ThumbnailPerformanceService**: Performance monitoring

### Generators

- **ThumbnailGenerator**: Creates 200x150 thumbnail images
- **SmallImageGenerator**: Creates 800x600 medium-sized images
- **BatchThumbnailGenerator**: Processes multiple images efficiently

## 📊 Data Models

### Response Models

```python
class ThumbnailOperationResponse(BaseModel):
    success: bool
    message: str  # User-friendly message
    operation: str  # Operation identifier
    data: Optional[Dict[str, Any]] = None  # Technical details
    timestamp: datetime

class ThumbnailRegenerationStatus(BaseModel):
    active: bool  # Is regeneration currently running?
    progress: int  # 0-100 percentage
    total: int  # Total jobs in this session
    completed: int  # Jobs completed
    errors: int  # Jobs that failed
    status_message: str  # Current status
    started_at: Optional[datetime] = None
```

### Job Models

```python
class ThumbnailGenerationResult(BaseModel):
    success: bool
    image_id: int
    timelapse_id: Optional[int] = None
    thumbnail_path: Optional[str] = None
    small_path: Optional[str] = None
    processing_time_ms: int = 0
    error: Optional[str] = None
```

## 🚦 Relationship with Other Systems

### ImageService Separation

**File**: `/backend/app/services/image_service.py`

**ImageService Responsibilities** (metadata & serving only):

- ✅ `serve_image_file()` - serves with cascading fallbacks
- ✅ `get_image_by_id()` - metadata retrieval
- ✅ `prepare_image_for_serving()` - file path resolution

**ThumbnailPipeline Responsibilities** (generation & management):

- ✅ All thumbnail generation operations
- ✅ Job queue management
- ✅ Bulk operations
- ✅ System maintenance

### Router Boundaries

- **thumbnail_routers.py**: All generation, management, bulk operations
- **image_routers.py**: Only serving existing files (no generation)

### Worker Integration

- **CaptureWorker**: Triggers job creation via JobCoordinationService
- **ThumbnailWorker**: Processes jobs using
  ThumbnailPipeline.process_image_thumbnails()
- **SchedulerWorker**: Coordinates timing of all thumbnail operations

## ⚡ Key Patterns

### 1. Scheduler CEO Compliance

```python
# ✅ Individual requests route through CEO
await scheduler_service.schedule_immediate_thumbnail_generation(image_id)

# ❌ Don't bypass CEO for individual requests
await thumbnail_pipeline.queue_thumbnail_job(image_id)  # Wrong for individual requests!
```

### 2. Sync vs Async Interfaces

```python
# API endpoints use async interface
async def endpoint(thumbnail_pipeline: ThumbnailPipelineDep):
    return await thumbnail_pipeline.start_thumbnail_regeneration_background()

# Workers use sync interface
def worker_method(self):
    return self.thumbnail_pipeline.queue_thumbnail_job_sync(image_id)
```

### 3. Type-Safe Responses

```python
# ✅ Always return Pydantic models
return ThumbnailOperationResponse(
    success=True,
    message="Operation completed",
    operation="verify_all",
    timestamp=utc_now()
)

# ❌ Don't return raw dicts
return {"success": True, "message": "Done"}  # Wrong!
```

## 🔍 Common Operations

### Debugging Job Queue Issues

```python
# Check queue status
stats = await thumbnail_pipeline.get_job_statistics()
print(f"Pending: {stats.get('pending_jobs', 0)}")
print(f"Processing: {stats.get('processing_jobs', 0)}")

# Check regeneration status
status = await thumbnail_pipeline.get_thumbnail_regeneration_status()
print(f"Active: {status.active}, Progress: {status.progress}%")
```

### Adding New Bulk Operations

1. Add method to `ThumbnailPipeline` class
2. Use existing sub-services (`verification_service`, `repair_service`, etc.)
3. Return `ThumbnailOperationResponse` with proper error handling
4. Add corresponding router endpoint

### Testing Pipeline Operations

```python
# Mock the pipeline in tests
mock_pipeline = Mock(spec=ThumbnailPipeline)
mock_pipeline.start_thumbnail_regeneration_background.return_value = ThumbnailOperationResponse(
    success=True, message="Test", operation="test", timestamp=utc_now()
)
```

## ⚠️ Important Notes

### File System Structure

Files are organized by timelapse within camera directories:

```
data/
├── cameras/
│   └── camera-{id}/                    # Database camera.id
│       └── timelapse-{id}/            # Database timelapse.id
│           ├── frames/                # Captured images
│           │   ├── timelapse-{id}_20250422_143022.jpg
│           │   └── timelapse-{id}_20250423_064512.jpg
│           ├── thumbnails/            # Generated thumbnails
│           │   ├── timelapse-{id}_thumb_20250422_143022.jpg  # 200×150
│           │   └── timelapse-{id}_thumb_20250423_064512.jpg
│           ├── smalls/                # Generated small images
│           │   ├── timelapse-{id}_small_20250422_143022.jpg  # 800×600
│           │   └── timelapse-{id}_small_20250423_064512.jpg
│           ├── overlays/              # Generated overlays
│           └── videos/                # Generated videos
```

### Database Integration

- Image records track `thumbnail_path` and `small_path`
- Job queue tracks generation status and priority
- Statistics track performance and success rates

### Background Processing

- Bulk operations return immediately with session IDs
- Actual processing happens in background via job queue
- Status endpoints provide real-time progress updates
- SSE events broadcast progress to frontend

---

The ThumbnailPipeline serves as the **single source of truth** for all thumbnail
operations while maintaining clean integration with the broader Timelapser
ecosystem through the Scheduler CEO architecture.
