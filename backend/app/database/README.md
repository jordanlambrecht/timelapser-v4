# Database Layer

## Exception-Based Logging Architecture

The database layer implements a **clean exception-based logging pattern** to
eliminate circular imports and maintain separation of concerns between data
access and logging.

### Core Principles

1. **Database Operations**: Pure data access that raises specific exceptions (no
   logging)
2. **Service Layer**: Business logic that catches exceptions and handles logging
3. **Clean Dependencies**: `Database → Exceptions → Services → Logger` (no
   circular imports)

### Implementation Steps

#### Step 1: Import Domain-Specific Exception

```python
# At the top of your operations file:
from .exceptions import CameraOperationError  # Replace with appropriate exception
```

**Available Exceptions:**

- `SettingsOperationError` - settings_operations.py ✅ **IMPLEMENTED**
- `CameraOperationError` - camera_operations.py
- `ImageOperationError` - image_operations.py
- `VideoOperationError` - video_operations.py
- `TimelapseOperationError` - timelapse_operations.py
- `LogOperationError` - log_operations.py
- `SSEOperationError` - sse_events_operations.py
- `HealthOperationError` - health_operations.py
- `StatisticsOperationError` - statistics_operations.py
- `OverlayOperationError` - overlay_operations.py
- `CorruptionOperationError` - corruption_operations.py
- `RecoveryOperationError` - recovery_operations.py
- `WeatherOperationError` - weather_operations.py
- `ScheduledJobOperationError` - scheduled_job_operations.py
- `ThumbnailOperationError` - thumbnail_job_operations.py

#### Step 2: Remove Logger Imports and Calls

```python
# Remove these:
from ...services.logger import get_service_logger
logger = get_service_logger(LoggerName.CAMERA_SERVICE, LogSource.SYSTEM)

# Remove all logger calls:
logger.error(f"Failed to get camera: {e}")
```

#### Step 3: Replace Logger Calls with Exceptions

```python
# Replace this pattern:
try:
    # database operation
    return result
except (psycopg.Error, KeyError, ValueError) as e:
    logger.error(f"Failed to get camera: {e}")
    raise

# With this pattern:
try:
    # database operation
    return result
except (psycopg.Error, KeyError, ValueError) as e:
    raise CameraOperationError(
        f"Failed to get camera: {e}",
        operation="get_camera",
        details={"camera_id": camera_id}
    ) from e
```

#### Step 4: Update Corresponding Service Layer

The service layer should catch these exceptions and log them:

```python
# In camera_service.py:
from ..database.camera_operations import CameraOperationError

async def get_camera(self, camera_id: int) -> Camera:
    try:
        result = await self.camera_ops.get_camera(camera_id)
        logger.info(f"✅ Retrieved camera {camera_id}")
        return result
    except CameraOperationError as e:
        logger.error(f"❌ Database error retrieving camera {camera_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error retrieving camera {camera_id}: {e}")
        raise
```

### Benefits

- ✅ **No Circular Imports** - Clean dependency hierarchy
- ✅ **Better Testability** - Database operations isolated from logging
- ✅ **Specific Error Context** - Domain-specific exceptions with detailed
  information
- ✅ **Centralized Logging** - All logging happens at the service layer
- ✅ **Maintainable** - Clear separation between data access and business logic

### Reference Implementation

See **`settings_operations.py`** and **`settings_service.py`** for a complete
example of this pattern.

---

## Cache Integration Template

This template shows how to integrate cache_manager.py and cache_invalidation.py
systems into database operation files.

## Step 1: Update Imports

```python
# Replace this:
from ..utils.database_helpers import DatabaseQueryCache

# With this:
from ..utils.cache_manager import (
    cache,
    cached_response,
    generate_timestamp_etag,
    generate_composite_etag,
    generate_collection_etag
)
from ..utils.cache_invalidation import CacheInvalidationService
```

## Step 2: Update Class Initialization

```python
# Replace this:
def __init__(self, db: AsyncDatabase) -> None:
    self.db = db
    self.cache = DatabaseQueryCache()

# With this:
def __init__(self, db: AsyncDatabase) -> None:
    self.db = db
    self.cache_invalidation = CacheInvalidationService()
```

## Step 3: Add Caching Decorators

```python
# Add decorators to frequently-used methods:
@cached_response(ttl_seconds=60, key_prefix="entity_type")
async def get_entities(self) -> List[Entity]:

# Choose appropriate TTL based on data volatility:
# - 30s: Highly dynamic data (active jobs, real-time status)
# - 60s: Moderately dynamic data (cameras, basic lists)
# - 300s: Relatively static data (settings, configurations)
```

## Step 4: Update Cache Invalidation Methods

```python
# Replace basic invalidation:
def _clear_entity_caches(self, entity_id: int) -> None:
    patterns_to_clear = [f"entity:{entity_id}", "all_entities"]
    for pattern in patterns_to_clear:
        self.cache.invalidate(pattern)

# With sophisticated invalidation:
async def _clear_entity_caches(self, entity_id: int, updated_at: Optional[datetime] = None) -> None:
    # Use event-driven cache invalidation
    await self.cache_invalidation.invalidate_entity_cache(entity_id)

    # Clear specific cache patterns
    cache_patterns = [
        f"entity_type:get_entities",
        f"entity_type:get_entity_by_id:{entity_id}",
    ]

    for pattern in cache_patterns:
        await cache.delete(pattern)

    # Use ETag-aware invalidation if timestamp provided
    if updated_at:
        etag = generate_composite_etag(entity_id, updated_at)
        await self.cache_invalidation.invalidate_with_etag_validation(
            f"entity:metadata:{entity_id}", etag
        )
```

## Step 5: Update Cache Clearing Calls

```python
# Replace synchronous calls:
self._clear_entity_caches(entity_id)

# With asynchronous calls:
await self._clear_entity_caches(entity_id, updated_at=current_time)
```

## Benefits of This Integration

1. **Performance**: Advanced TTL-based caching reduces database load
2. **Intelligence**: ETag-aware invalidation prevents unnecessary cache clearing
3. **Real-time**: Event-driven invalidation via SSE events
4. **Consistency**: Sophisticated cache coherency management
5. **Observability**: Built-in cache statistics and monitoring

## Files Already Integrated

- ✅ `camera_operations.py` - Camera data caching with ETag support
- ✅ `image_operations.py` - Image collection caching with event-driven
  invalidation

## Files Remaining for Integration

- `scheduled_job_operations.py`
- `settings_operations.py`
- `statistics_operations.py`
- `overlay_job_operations.py`
- `thumbnail_job_operations.py`
- `log_operations.py`
- `overlay_operations.py`
- `weather_operations.py`
- `sse_events_operations.py`
- `health_operations.py`
- `recovery_operations.py`

Each file should follow this template for consistent integration.
