# Database Layer

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
