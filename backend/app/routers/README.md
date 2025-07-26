# Routers API Endpoints

This document provides an overview of all available API endpoints defined in the
routers of the Timelapser backend. Each router is responsible for a specific
domain of the application. For detailed request/response schemas, refer to the
source code or OpenAPI docs.

Last Updated: July 26th 2025

---

## Routers and Their Endpoints

### camera_crop_router.py

- `GET /api/cameras/{camera_id}/crop-settings` - Get crop/rotation settings for
  a camera
- `PUT /api/cameras/{camera_id}/crop-settings` - Update crop/rotation settings
  for a camera
- `DELETE /api/cameras/{camera_id}/crop-settings` - Disable crop/rotation
  settings for a camera
- `GET /api/cameras/{camera_id}/source-resolution` - Get camera source
  resolution
- `POST /api/cameras/{camera_id}/detect-resolution` - Detect camera source
  resolution
- `POST /api/cameras/{camera_id}/test-crop-settings` - Test camera crop settings

### camera_routers.py

- `GET /cameras` - List cameras
- `GET /cameras/{camera_id}` - Get camera details
- `POST /cameras` - Create camera
- `PUT /cameras/{camera_id}` - Update camera
- `DELETE /cameras/{camera_id}` - Delete camera
- `GET /cameras/{camera_id}/details` - Get extended camera details
- `GET /cameras/{camera_id}/status` - Get camera status
- `PUT /cameras/{camera_id}/status` - Update camera status
- `GET /cameras/{camera_id}/images/latest` - Get latest image for camera
- `GET /cameras/{camera_id}/latest-image/thumbnail` - Get latest image thumbnail
- `GET /cameras/{camera_id}/latest-image/small` - Get latest image small
- `GET /cameras/{camera_id}/latest-image/full` - Get latest image full
- `GET /cameras/{camera_id}/latest-image/download` - Download latest image

### corruption_routers.py

- `GET /corruption/stats` - Get corruption system stats
- `GET /corruption/camera/{camera_id}/stats` - Get camera corruption stats
- `GET /corruption/camera/{camera_id}/history` - Get camera corruption history
- `GET /corruption/settings` - Get corruption settings
- `PUT /corruption/settings` - Update corruption settings
- `GET /corruption/logs` - Get corruption logs

### dashboard_routers.py

- `GET /dashboard` - Get dashboard overview
- `GET /dashboard/stats` - Get dashboard stats
- `GET /dashboard/health` - Get dashboard health

### health_routers.py

- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed health check
- `GET /health/database` - Database health check
- `GET /health/filesystem` - Filesystem health check
- `GET /health/system` - System metrics check
- `GET /health/application` - Application metrics check
- `GET /health/readiness` - Readiness probe
- `GET /health/liveness` - Liveness probe

### image_routers.py

- `GET /images/count` - Get image count
- `GET /images/{image_id}` - Get image metadata
- `GET /images/{image_id}/serve` - Serve image file
- `DELETE /images/{image_id}` - Delete image
- `POST /images/batch` - Batch image request
- `POST /images/bulk/download` - Bulk image download
- `GET /images/{image_id}/small` - Get small image
- `GET /images/{image_id}/thumbnail` - Get image thumbnail

### log_routers.py

- `GET /logs/stats` - Get log stats
- `GET /logs` - Get logs
- `GET /logs/sources` - Get log sources
- `GET /logs/search` - Search logs
- `DELETE /logs/cleanup` - Cleanup old logs
- `GET /logs/cameras/{camera_id}` - Get camera logs

### monitoring_routers.py

- `GET /monitoring/cache/stats` - Get cache statistics
- `POST /monitoring/cache/clear` - Clear all cache
- `POST /monitoring/cache/cleanup` - Cleanup expired cache
- `GET /monitoring/performance/latest-image` - Get latest image performance

### overlay_routers.py

- `GET /presets` - Fetch overlay presets
- `GET /presets/{preset_id}` - Fetch overlay preset
- `POST /presets` - Create overlay preset
- `PUT /presets/{preset_id}` - Update overlay preset
- `DELETE /presets/{preset_id}` - Delete overlay preset
- `GET /config/{timelapse_id}` - Fetch timelapse overlay configuration
- `POST /config/{timelapse_id}` - Create timelapse overlay configuration

### settings_routers.py

- `GET /settings` - Get settings
- `GET /settings/list` - Get settings list
- `GET /settings/{key}` - Get setting
- `POST /settings` - Create setting
- `PUT /settings` - Update setting from body
- `PUT /settings/{key}` - Update setting
- `DELETE /settings/{key}` - Delete setting
- `POST /settings/bulk` - Update multiple settings
- `GET /settings/weather` - Get weather settings
- `PUT /settings/weather` - Update weather setting
- `POST /settings/weather/refresh` - Refresh weather data

### sse_routers.py

- `GET /events` - SSE event stream
- `GET /events/stats` - Get SSE event statistics
- `POST /events/cleanup` - Cleanup old SSE events

### thumbnail_routers.py

- `POST /thumbnails/generate/{image_id}` - Generate thumbnail for image
- `GET /thumbnails/stats` - Get thumbnail statistics
- `POST /thumbnails/regenerate-all` - Start thumbnail regeneration
- `POST /thumbnails/regenerate` - Start thumbnail regeneration (deprecated)
- `GET /thumbnails/regenerate-all/status` - Get thumbnail regeneration status
- `POST /thumbnails/regenerate-all/cancel` - Cancel thumbnail regeneration
- `DELETE /thumbnails/delete-all` - Delete all thumbnails
- `POST /thumbnails/verify` - Verify all thumbnails
- `POST /thumbnails/repair` - Repair orphaned thumbnails
- `DELETE /thumbnails/cleanup` - Cleanup orphaned thumbnails

### timelapse_routers.py

- `POST /timelapses/new` - Create new timelapse
- `POST /timelapses` - Create timelapse
- `GET /timelapses` - Get timelapses
- `GET /timelapses/statistics` - Get timelapse library statistics
- `GET /timelapses/{timelapse_id}` - Get timelapse details
- `PUT /timelapses/{timelapse_id}` - Update timelapse
- `DELETE /timelapses/{timelapse_id}` - Delete timelapse
- `GET /timelapses/{timelapse_id}/statistics` - Get statistics for timelapse
- `GET /timelapses/{timelapse_id}/progress` - Get progress for timelapse
- `GET /timelapses/{timelapse_id}/videos` - Get videos for timelapse
- `GET /timelapses/{timelapse_id}/images` - Get images for timelapse
- `GET /timelapses/{timelapse_id}/thumbnails/stats` - Get thumbnail stats for
  timelapse
- `POST /timelapses/{timelapse_id}/thumbnails/verify` - Verify thumbnails for
  timelapse
- `DELETE /timelapses/{timelapse_id}/thumbnails` - Delete thumbnails for
  timelapse

### video_automation_routers.py

- Endpoints for video automation configuration, job queue, manual triggers, and
  stats (see OpenAPI docs for full list)

### video_routers.py

- `GET /videos` - Get videos
- `GET /videos/{video_id}` - Get video details
- `POST /videos` - Create video
- `DELETE /videos/{video_id}` - Delete video
- `GET /videos/{video_id}/download` - Download video file
- `POST /videos/generate` - Generate video
- `GET /videos/generation-queue` - Get video generation queue
- `POST /videos/{video_id}/cancel-generation` - Cancel video generation

---

## How to Use

- All endpoints are accessible via the FastAPI backend.
- For request/response details, see the OpenAPI documentation at `/docs` when
  the backend is running.
- Routers are organized for separation of concerns and maintainability.

---

## Notes

- For business logic, see the corresponding service files.
- For database access, see the database folder.
- For utility functions, see the utils folder.

---

This README is auto-generated for quick reference. For updates, re-run the
endpoint extraction or review the router source files.
