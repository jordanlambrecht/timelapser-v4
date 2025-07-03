# Timelapser v4 Caching Strategy Guide

> Last Updated: July 3rd, 2025

## 🎯 Overview

This guide defines when and how to use different caching strategies in
Timelapser v4. Each strategy solves different problems and they work together to
provide optimal performance.

## 📚 The Three Caching Strategies

### 1. **Server-Sent Events (SSE)** - Real-time Updates

**What**: WebSocket-like connection for server-to-client updates **When**: Data
changes frequently and users need immediate updates **How**: Centralized SSE
connection broadcasts events when data changes

### 2. **Cache-Control Headers** - Prevent Repeat Requests

**What**: HTTP headers telling browsers how long to cache responses **When**:
Content doesn't change often or never changes **How**: Browser serves from cache
without hitting server

### 3. **ETags** - Validate Cached Content

**What**: Content fingerprints for cache validation  
**When**: Content changes occasionally and you want automatic invalidation
**How**: Server compares ETags to determine if cached content is still valid

---

## 🎲 Decision Matrix

| Content Type          | Update Frequency     | Strategy             | Why                                  |
| --------------------- | -------------------- | -------------------- | ------------------------------------ |
| **Camera status**     | Every 30s-5min       | SSE                  | Users need immediate status updates  |
| **Image counts**      | Every capture        | SSE                  | Real-time progress is core UX        |
| **Images/thumbnails** | Never (immutable)    | Long Cache-Control   | Load once, cache forever             |
| **System settings**   | Hours to days        | Cache-Control + ETag | Fresh when changed, cached when not  |
| **Video files**       | Never after creation | Long Cache-Control   | Large files, never change            |
| **Dashboard stats**   | Every few minutes    | SSE                  | Real-time monitoring is key value    |
| **User preferences**  | Rarely               | Cache-Control + ETag | Personal settings need to be current |

---

## 🚀 Strategy Details

### SSE Strategy: Real-time Updates

**Use When:**

- Data changes every few seconds to minutes
- Users expect immediate updates
- Multiple users need synchronized state
- Data is relatively small (< 1MB)

**Implementation:**

```python
# In services layer
class CameraService:
    async def update_camera_status(self, camera_id: int, status: str):
        # Update database
        updated_camera = await self.camera_ops.update_status(camera_id, status)

        # Broadcast SSE event
        await self.broadcast_event("camera_status_changed", {
            "data": {
                "camera_id": camera_id,
                "status": status,
                "timestamp": timezone_utils.utc_now().isoformat()
            }
        })

        return updated_camera
```

```typescript
// In frontend components
const { cameras } = useRealtimeCameras() // Updates via SSE
useCameraSSE(cameraId, {
  onStatusChanged: (data) => {
    setCameraStatus(data.status) // Immediate UI update
  },
})
```

**Examples in Timelapser:**

- Camera online/offline status
- Image capture counts
- Timelapse progress
- Video generation status
- System health alerts

---

### Cache-Control Strategy: Prevent Requests

**Use When:**

- Content never changes (immutable)
- Content changes predictably (daily/weekly)
- Large files that are expensive to transfer
- Static resources

**Implementation:**

```python
# For immutable content (images, videos)
@router.get("/images/{id}/thumbnail")
async def serve_thumbnail(id: int):
    return FileResponse(
        image_path,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable"  # 1 year
        }
    )

# For semi-static content (settings)
@router.get("/settings")
async def get_settings():
    return ResponseFormatter.success(
        data=settings,
        headers={
            "Cache-Control": "private, max-age=300"  # 5 minutes
        }
    )
```

**Cache-Control Directives:**

```python
# Never cache (for development/debugging)
"Cache-Control": "no-store"

# Always validate with server
"Cache-Control": "no-cache"

# Cache for specific time
"Cache-Control": "max-age=3600"  # 1 hour

# Cache forever (immutable content)
"Cache-Control": "public, max-age=31536000, immutable"

# Private cache only (user-specific data)
"Cache-Control": "private, max-age=1800"  # 30 minutes
```

**Examples in Timelapser:**

- Captured images (never change)
- Generated videos (immutable once created)
- Thumbnails (generated once, never change)
- Static assets (CSS, JS, images)

---

### ETag Strategy: Smart Cache Validation

**Use When:**

- Content changes occasionally (hours to days)
- You want automatic cache invalidation
- Content is moderate size (not huge files)
- Freshness matters but some delay is acceptable

**Implementation:**

```python
# Generate ETag in service
class SettingsService:
    async def get_settings_with_etag(self) -> tuple[dict, str]:
        settings = await self.settings_ops.get_all_settings()
        etag = f'"{settings.updated_at.timestamp()}"'
        return settings, etag

# Use ETag in router
@router.get("/settings")
async def get_settings(request: Request, settings_service: SettingsServiceDep):
    settings, etag = await settings_service.get_settings_with_etag()

    # Check if client has current version
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)  # Not Modified

    return ResponseFormatter.success(
        data=settings,
        headers={
            "ETag": etag,
            "Cache-Control": "private, max-age=300"  # 5 min cache + validation
        }
    )
```

**ETag Generation Strategies:**

```python
# Timestamp-based (most common)
etag = f'"{content.updated_at.timestamp()}"'

# Hash-based (for content without timestamps)
import hashlib
etag = f'"{hashlib.md5(json.dumps(content).encode()).hexdigest()}"'

# Version-based (if you track versions)
etag = f'"{content.id}-{content.version}"'
```

**Examples in Timelapser:**

- System settings/configuration
- Camera settings
- User preferences
- Timelapse metadata
- Video generation settings

---

## 🏗️ Cache Infrastructure Implementation

Timelapser v4 implements a sophisticated two-layer caching system with ETag
support, TTL management, and SSE integration. The implementation is split across
two key files that work together to provide optimal performance.

### Architecture Overview

```
cache_manager.py          cache_invalidation.py
     ↓                           ↓
Infrastructure            Business Logic
- MemoryCache             - Event Handlers
- ETag Utilities          - SSE Integration
- Decorators              - Smart Invalidation
- TTL Management          - Cache Coherency
```

**Design Principle**: Separation of concerns - infrastructure vs. business logic

---

### 📦 Core Classes Reference

#### `CacheEntry` (cache_manager.py)

Individual cache entry with TTL and ETag support.

```python
class CacheEntry:
    def __init__(self, data: Any, ttl_seconds: int, etag: Optional[str] = None)
    def is_expired(self) -> bool
    def get_age_seconds(self) -> int
    def has_etag(self) -> bool
```

**When to use**: Automatically used by MemoryCache - no direct usage needed.

#### `MemoryCache` (cache_manager.py)

Thread-safe in-memory cache with TTL support and ETag integration.

```python
class MemoryCache:
    # Basic operations
    async def get(self, key: str) -> Optional[Any]
    async def set(self, key: str, value: Any, ttl_seconds: int = 60, etag: Optional[str] = None)
    async def delete(self, key: str) -> bool

    # ETag operations
    async def get_with_etag(self, key: str) -> tuple[Optional[Any], Optional[str]]

    # Bulk operations
    async def delete_by_prefix(self, prefix: str) -> int
    async def get_entries_by_prefix(self, prefix: str) -> Dict[str, Any]

    # Maintenance
    async def cleanup_expired(self) -> int
    async def clear(self) -> None
    async def get_stats(self) -> Dict[str, Any]
```

**When to use**:

- Use global `cache` instance for direct cache operations
- Prefer decorators for function-level caching
- Use prefix operations for bulk cache management

#### `CacheInvalidationService` (cache_invalidation.py)

Coordinates cache invalidation with SSE events for maintaining cache coherency.

```python
class CacheInvalidationService:
    # Entity-specific invalidation
    async def invalidate_latest_image_cache(camera_id: int)
    async def invalidate_camera_status_cache(camera_id: int)
    async def invalidate_timelapse_cache(timelapse_id: int)
    async def invalidate_settings_cache(setting_key: Optional[str] = None)

    # ETag-aware invalidation
    async def invalidate_with_etag_validation(cache_key: str, current_etag: str, force: bool = False)
    async def invalidate_settings_with_etag(settings_data: Union[dict, Any], setting_key: Optional[str] = None)
    async def invalidate_image_metadata_cache(image_id: int, updated_at: Optional[datetime] = None)

    # SSE event integration
    async def handle_sse_event(event_type: str, event_data: Dict[str, Any])
    async def handle_sse_event_with_etag(event_type: str, event_data: Dict[str, Any], force_invalidation: bool = False)
```

**When to use**:

- Call from service layer when data changes
- Use ETag-aware methods for smart invalidation
- Integrate with SSE events for real-time cache coherency

---

### 🏷️ ETag Utilities Reference

Complete set of ETag generation and validation utilities for different content
types.

#### Timestamp-Based ETags (Most Common)

```python
def generate_timestamp_etag(obj: Any, timestamp_field: str = "updated_at") -> str
```

**Usage**:

```python
# For database models with updated_at
etag = generate_timestamp_etag(camera)  # Uses camera.updated_at

# For dictionaries
etag = generate_timestamp_etag({"updated_at": datetime.now()})

# Custom timestamp field
etag = generate_timestamp_etag(video, "modified_at")
```

**When to use**: Settings, configuration, any content with timestamps

#### Content Hash ETags

```python
def generate_content_hash_etag(content: Union[str, dict, list], algorithm: str = "md5") -> str
```

**Usage**:

```python
# For content without timestamps
etag = generate_content_hash_etag({"key": "value"})

# Different algorithms
etag = generate_content_hash_etag(file_content, "sha256")
```

**When to use**: Static content, configuration without timestamps

#### Composite ETags

```python
def generate_composite_etag(obj_id: Union[int, str], timestamp: Optional[datetime] = None, version: Optional[Union[int, str]] = None) -> str
```

**Usage**:

```python
# ID + timestamp (common for images)
etag = generate_composite_etag(image.id, image.updated_at)

# ID + version
etag = generate_composite_etag("config", version="v2.1")
```

**When to use**: Images, versioned content, entity-specific caching

#### Collection ETags

```python
def generate_collection_etag(items: list, count_field: Optional[str] = None) -> str
```

**Usage**:

```python
# For image collections
etag = generate_collection_etag(images)  # count + latest timestamp

# With explicit count field
etag = generate_collection_etag(results, "total_count")
```

**When to use**: Image lists, paginated results, dynamic collections

#### ETag Validation

```python
def validate_etag_match(request_etag: Optional[str], current_etag: str) -> bool
def extract_etag_from_headers(headers: dict) -> Optional[str]
```

**Usage**:

```python
# In routers for 304 responses
request_etag = extract_etag_from_headers(request.headers)
if validate_etag_match(request_etag, current_etag):
    return Response(status_code=304)
```

---

### 🎯 Decorators and Utilities

#### Basic Caching Decorator

```python
@cached_response(ttl_seconds=60, key_prefix="")
async def expensive_function(param1, param2):
    return await some_expensive_operation(param1, param2)
```

**Features**:

- Automatic cache key generation from function name and parameters
- TTL-based expiration
- Service instance filtering (skips `self` parameters)

**When to use**: Simple function-level caching without ETag needs

#### ETag-Aware Caching Decorator

```python
@cached_response_with_etag(ttl_seconds=300, etag_generator=generate_timestamp_etag)
async def get_settings_with_cache():
    settings = await settings_service.get_all_settings()
    return settings
```

**Features**:

- All basic caching features
- ETag generation and storage
- Cache validation support

**When to use**: Functions returning content that changes occasionally

#### Global Cache Functions

```python
# Statistics and monitoring
stats = await get_cache_stats()
await cleanup_expired_cache()

# Bulk operations
await delete_cache_by_prefix("setting:")
entries = await get_cache_entries_by_prefix("latest_image:")

# Maintenance
await clear_cache()
```

---

### 🔄 Integration Patterns

#### Pattern 1: Service Layer Caching

```python
class CameraService:
    @cached_response(ttl_seconds=60, key_prefix="camera")
    async def get_camera_with_latest_image(self, camera_id: int):
        camera = await self.camera_ops.get_camera_by_id(camera_id)
        latest_image = await self.image_ops.get_latest_image_for_camera(camera_id)
        return {**camera, "latest_image": latest_image}

    async def update_camera_status(self, camera_id: int, status: str):
        # Update database
        updated = await self.camera_ops.update_status(camera_id, status)

        # Invalidate cache
        await cache_invalidation.invalidate_camera_status_cache(camera_id)

        # Broadcast SSE
        await self.broadcast_event("camera_status_changed", {...})

        return updated
```

#### Pattern 2: ETag-Aware Settings

```python
class SettingsService:
    async def get_settings_with_etag(self) -> tuple[dict, str]:
        settings = await self.settings_ops.get_all_settings()
        etag = generate_timestamp_etag(settings)
        return settings, etag

    async def update_setting(self, key: str, value: str):
        # Update database
        updated = await self.settings_ops.update_setting(key, value)

        # ETag-aware cache invalidation
        await cache_invalidation.invalidate_settings_with_etag(updated, key)

        return updated
```

#### Pattern 3: SSE Integration

```python
# In service layer
await cache_invalidation.handle_sse_event("image_captured", {
    "camera_id": camera_id,
    "image_data": image_data,
    "total_count": total_count
})

# For ETag-aware invalidation
await cache_invalidation.handle_sse_event_with_etag("settings_updated", {
    "setting_key": "timezone",
    "settings_data": settings
})
```

---

### 🎨 Usage Guidelines

#### When to Use Each Component

| Component                         | Use Case                          | Example                 |
| --------------------------------- | --------------------------------- | ----------------------- |
| `@cached_response`                | Simple function caching           | Latest image lookup     |
| `@cached_response_with_etag`      | Content that changes occasionally | Settings, configuration |
| `cache.set()`                     | Manual cache management           | Custom cache logic      |
| `cache_invalidation.invalidate_*` | Data changes                      | After database updates  |
| ETag utilities                    | HTTP cache validation             | Router ETag headers     |

#### Cache Key Naming Convention

```python
# Entity-specific: "entity_type:operation:id"
"camera:get_latest_image:123"
"timelapse:get_status:456"

# Setting-specific: "setting:key"
"setting:timezone"
"setting:capture_interval"

# Operation-specific: "operation:params"
"dashboard:get_stats"
"batch:get_images:camera_123"
```

#### Performance Considerations

```python
# ✅ Good: Reasonable TTLs
@cached_response(ttl_seconds=300)  # 5 minutes for settings

# ❌ Avoid: Very short TTLs (defeats purpose)
@cached_response(ttl_seconds=5)   # Too short for most use cases

# ✅ Good: ETag validation for changing content
etag = generate_timestamp_etag(content)

# ❌ Avoid: Hash ETags for frequently changing content
etag = generate_content_hash_etag(realtime_data)  # Too expensive
```

---

## 🛠️ Implementation Guidelines

### Router Layer (HTTP Headers)

```python
# ✅ Routers handle HTTP caching headers
@router.get("/cameras/{id}/thumbnail")
async def serve_thumbnail(id: int, request: Request):
    image, etag = await image_service.get_image_with_etag(id)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    return FileResponse(
        image.thumbnail_path,
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=31536000"
        }
    )
```

### Service Layer (ETag Generation + SSE)

```python
# ✅ Services generate ETags and broadcast SSE
class CameraService:
    async def get_camera_with_etag(self, camera_id: int) -> tuple[dict, str]:
        camera = await self.camera_ops.get_camera_by_id(camera_id)
        etag = f'"{camera.updated_at.timestamp()}"'
        return camera, etag

    async def update_camera(self, camera_id: int, data: dict):
        updated = await self.camera_ops.update_camera(camera_id, data)

        # SSE broadcast for real-time updates
        await self.broadcast_event("camera_updated", {"data": updated})

        return updated
```

### Database Layer (Stay Pure)

```python
# ✅ Database operations don't know about caching
class CameraOperations:
    async def get_camera_by_id(self, camera_id: int) -> dict:
        # Pure data access, no HTTP concerns
        return await self.fetch_one(
            "SELECT * FROM cameras WHERE id = %s",
            (camera_id,)
        )
```

---

## 📊 Performance Impact

### Without Caching

```bash
Dashboard load: 20 API calls × 100ms = 2 seconds
Thumbnail grid: 50 images × 45KB = 2.25MB every load
Settings page: API call every render
```

### With Optimal Caching

```bash
Dashboard load: Real-time via SSE (0 API calls after initial)
Thumbnail grid: 2.25MB first load, then 0 bytes (cached)
Settings page: 5-minute cache + instant invalidation when changed
```

---

## ⚠️ Common Pitfalls

### 1. **Caching Real-time Data**

```python
# ❌ DON'T cache frequently changing data
headers = {"Cache-Control": "max-age=3600"}  # Camera status cached 1 hour?!

# ✅ Use SSE for real-time data
await self.broadcast_event("status_changed", data)
```

### 2. **Not Caching Immutable Content**

```python
# ❌ Thumbnails download every time
return FileResponse(path)  # No caching headers

# ✅ Cache forever since they never change
return FileResponse(path, headers={
    "Cache-Control": "public, max-age=31536000, immutable"
})
```

### 3. **ETag Without Cache-Control**

```python
# ❌ ETag validation on every request (still slow)
headers = {"ETag": etag}

# ✅ Short cache + ETag validation when expired
headers = {
    "ETag": etag,
    "Cache-Control": "max-age=300"
}
```

### 4. **SSE Event Spam**

```python
# ❌ Broadcasting every database change
await self.broadcast_event("image_count_changed", count)  # Every second!

# ✅ Throttle or batch updates
if count % 10 == 0:  # Every 10th image
    await self.broadcast_event("image_count_changed", count)
```

---

## 🎯 Timelapser-Specific Rules

### Images & Media Files

```python
# Rule: Always use long cache for immutable content
"Cache-Control": "public, max-age=31536000, immutable"
# Why: Images never change after creation, massive bandwidth savings
```

### Camera Data

```python
# Rule: Use SSE for status, counts, health
# Why: Users need real-time monitoring for timelapse operations
```

### Settings & Configuration

```python
# Rule: 5-minute cache + ETag validation
"Cache-Control": "private, max-age=300"
"ETag": f'"{settings.updated_at.timestamp()}"'
# Why: Fresh when changed, cached when stable
```

### Dashboard & Stats

```python
# Rule: SSE for live data, short cache for expensive aggregations
# Why: Real-time monitoring is core value proposition
```

### Video Files

```python
# Rule: Long cache with ETag for large files
"Cache-Control": "public, max-age=86400"  # 1 day
"ETag": f'"{video.file_hash}"'
# Why: Large files, don't change, but may be regenerated
```

---

## 🚦 Implementation Checklist

### For Each New Endpoint

1. **Identify content type and update frequency**

   - Real-time (seconds/minutes) → SSE
   - Occasional (hours/days) → Cache + ETag
   - Never → Long cache

2. **Add appropriate headers in router**

   - Include Cache-Control directive
   - Add ETag if content can change
   - Set proper max-age values

3. **Implement SSE broadcasting in service if needed**

   - Broadcast when data changes
   - Include relevant data in event
   - Use consistent event naming

4. **Test caching behavior**
   - Verify cache headers in browser dev tools
   - Test 304 responses for ETags
   - Confirm SSE events fire correctly

### Browser Testing

```bash
# Check cache headers
curl -I http://localhost:8000/api/images/123/thumbnail

# Test ETag validation
curl -H "If-None-Match: \"abc123\"" http://localhost:8000/api/settings

# Verify SSE connection
# Browser dev tools → Network → Filter by EventSource
```

---

## 🎓 Summary

**The Three-Layer Approach:**

1. **SSE** for data users care about immediately
2. **Cache-Control** for content that doesn't change often
3. **ETags** for automatic cache invalidation when content does change

**Golden Rules:**

- Images/media: Long cache (immutable)
- Real-time data: SSE (immediate updates)
- Settings/config: Short cache + ETag (fresh but efficient)
- Never cache what changes frequently without SSE
- Always cache what never changes

**Implementation:**

- Routers set HTTP headers
- Services generate ETags and broadcast SSE
- Database stays pure (no caching concerns)

This strategy provides blazing-fast performance while maintaining real-time
accuracy where it matters most.
