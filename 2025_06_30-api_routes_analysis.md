# Timelapser v4 API Routes Cross-Reference Analysis

## Frontend API Proxy Routes (70 routes)

| **Endpoint** | **Methods** | **Description** | **Parameters** |
|--------------|-------------|-----------------|----------------|
| **CAMERAS** |
| `/api/cameras` | GET, POST | List all cameras / Create camera | - |
| `/api/cameras/[id]` | GET, PUT, DELETE | Get/Update/Delete specific camera | `id` |
| `/api/cameras/[id]/capture` | GET | Get capture info | `id` |
| `/api/cameras/[id]/capture-now` | POST | Trigger immediate capture | `id` |
| `/api/cameras/[id]/complete-timelapse` | POST | Complete current timelapse | `id` |
| `/api/cameras/[id]/connectivity` | GET | Check camera connectivity | `id` |
| `/api/cameras/[id]/details` | GET | Get detailed camera info | `id` |
| `/api/cameras/[id]/health` | GET | Get camera health status | `id` |
| `/api/cameras/[id]/images/latest` | GET | Get latest image | `id` |
| `/api/cameras/[id]/latest-capture` | GET | Get latest capture info | `id` |
| `/api/cameras/[id]/latest-capture/download` | GET | Download latest capture | `id` |
| `/api/cameras/[id]/pause-timelapse` | POST | Pause current timelapse | `id` |
| `/api/cameras/[id]/resume-timelapse` | POST | Resume paused timelapse | `id` |
| `/api/cameras/[id]/start-timelapse` | POST | Start new timelapse | `id` |
| `/api/cameras/[id]/status` | GET | Get camera status | `id` |
| `/api/cameras/[id]/stop-timelapse` | POST | Stop current timelapse | `id` |
| `/api/cameras/[id]/test-connection` | POST | Test camera connection | `id` |
| `/api/cameras/[id]/timelapse-stats` | GET | Get timelapse statistics | `id` |
| **TIMELAPSES** |
| `/api/timelapses` | GET, POST | List timelapses / Create/Update timelapse | - |
| `/api/timelapses/new` | POST | Create new timelapse entity | - |
| `/api/timelapses/[id]` | GET | Get specific timelapse | `id` |
| `/api/timelapses/[id]/complete` | POST | Complete timelapse | `id` |
| `/api/timelapses/[id]/images` | GET | Get timelapse images | `id` |
| `/api/timelapses/[id]/immediate-capture` | POST | Trigger immediate capture | `id` |
| `/api/timelapses/[id]/pause` | POST | Pause timelapse | `id` |
| `/api/timelapses/[id]/start` | POST | Start timelapse | `id` |
| `/api/timelapses/[id]/status` | GET, PUT | Get/Update timelapse status | `id` |
| `/api/timelapses/[id]/videos` | GET | Get timelapse videos | `id` |
| **VIDEOS** |
| `/api/videos` | GET, POST | List videos / Generate video | - |
| `/api/videos/generate` | POST | Generate new video | - |
| `/api/videos/generation-queue` | GET | Get generation queue status | - |
| `/api/videos/[id]` | GET | Get specific video | `id` |
| `/api/videos/[id]/cancel-generation` | POST | Cancel video generation | `id` |
| `/api/videos/[id]/download` | GET | Download video file | `id` |
| `/api/videos/[id]/generation-status` | GET | Get generation status | `id` |
| **IMAGES** |
| `/api/images/[...path]` | GET | Serve image files | `path` (catch-all) |
| `/api/images/[id]/download` | GET | Download specific image | `id` |
| `/api/images/[id]/small` | GET | Get small/medium image | `id` |
| `/api/images/[id]/thumbnail` | GET | Get thumbnail image | `id` |
| `/api/images/bulk-download` | POST | Bulk download images | - |
| `/api/images/count` | GET | Get total image count | - |
| **CORRUPTION** |
| `/api/corruption/cameras/[id]/reset-degraded` | POST | Reset degraded mode | `id` |
| `/api/corruption/cameras/[id]/stats` | GET | Get corruption stats | `id` |
| `/api/corruption/logs` | GET | Get corruption logs | - |
| `/api/corruption/settings` | GET, PUT | Get/Update corruption settings | - |
| `/api/corruption/stats` | GET | Get system corruption stats | - |
| `/api/corruption/test-image` | POST | Test image corruption | - |
| **VIDEO AUTOMATION** |
| `/api/video-automation/queue/jobs` | GET | Get automation queue jobs | - |
| `/api/video-automation/queue/status` | GET | Get queue status | - |
| `/api/video-automation/trigger/manual` | POST | Trigger manual automation | - |
| **THUMBNAILS** |
| `/api/thumbnails/regenerate-all` | POST | Start bulk thumbnail regeneration | - |
| `/api/thumbnails/regenerate-all/cancel` | POST | Cancel bulk regeneration | - |
| `/api/thumbnails/regenerate-all/status` | GET | Get regeneration status | - |
| `/api/thumbnails/stats` | GET | Get thumbnail statistics | - |
| **SYSTEM** |
| `/api/dashboard` | GET | Get dashboard data | - |
| `/api/dashboard/stats` | GET | Get dashboard statistics | - |
| `/api/health` | GET | System health check | - |
| `/api/events` | GET | SSE event stream | - |
| `/api/logs` | GET | Get system logs | - |
| `/api/logs/stats` | GET | Get log statistics | - |
| `/api/settings` | GET, PUT | Get/Update system settings | - |
| `/api/settings/weather` | GET, PUT | Weather settings | - |
| `/api/settings/weather/data` | GET | Get weather data | - |
| `/api/settings/weather/refresh` | POST | Refresh weather data | - |
| `/api/settings/weather/sun-window` | GET, POST | Sunrise/sunset window | - |
| `/api/settings/weather/validate-api-key` | POST | Validate weather API key | - |
| **DEBUG/TESTING** |
| `/api/debug/images` | GET | Debug image information | - |
| `/api/tests` | GET | Test endpoints | - |

---

## Backend FastAPI Routes (95 routes)

| **Endpoint** | **Methods** | **Description** | **Parameters** |
|--------------|-------------|-----------------|----------------|
| **CAMERAS** |
| `/api/cameras` | GET, POST | List all cameras / Create camera | - |
| `/api/cameras/{camera_id}` | GET, PUT, DELETE | Get/Update/Delete specific camera | `camera_id` |
| `/api/cameras/{camera_id}/details` | GET | Comprehensive camera details (single call) | `camera_id` |
| `/api/cameras/{camera_id}/status` | GET, PUT | Get/Update camera status | `camera_id` |
| `/api/cameras/{camera_id}/health` | GET, PUT | Get/Update camera health metrics | `camera_id` |
| `/api/cameras/{camera_id}/connectivity` | GET | Get camera connectivity status | `camera_id` |
| `/api/cameras/{camera_id}/test-connection` | POST | Test RTSP connection | `camera_id` |
| `/api/cameras/{camera_id}/capture-now` | POST | Trigger manual capture | `camera_id` |
| `/api/cameras/{camera_id}/images/latest` | GET | Get latest image metadata | `camera_id` |
| `/api/cameras/{camera_id}/latest-capture` | GET | Serve latest capture file | `camera_id` |
| `/api/cameras/{camera_id}/latest-capture/download` | GET | Download latest capture | `camera_id` |
| `/api/cameras/{camera_id}/latest-thumbnail` | GET | Serve latest thumbnail | `camera_id` |
| `/api/cameras/{camera_id}/latest-small` | GET | Serve latest small image | `camera_id` |
| `/api/cameras/{camera_id}/timelapse-stats` | GET | Get timelapse statistics | `camera_id` |
| `/api/cameras/{camera_id}/start-timelapse` | POST | Start new timelapse | `camera_id` |
| `/api/cameras/{camera_id}/pause-timelapse` | POST | Pause active timelapse | `camera_id` |
| `/api/cameras/{camera_id}/resume-timelapse` | POST | Resume paused timelapse | `camera_id` |
| `/api/cameras/{camera_id}/stop-timelapse` | POST | Stop active timelapse | `camera_id` |
| `/api/cameras/{camera_id}/complete-timelapse` | POST | Complete active timelapse | `camera_id` |
| **TIMELAPSES** |
| `/api/timelapses` | GET, POST | List timelapses / Create timelapse | `camera_id` (query) |
| `/api/timelapses/new` | POST | Create new timelapse entity | `camera_id` (query) |
| `/api/timelapses/{timelapse_id}` | GET, PUT, DELETE | Get/Update/Delete timelapse | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/start` | POST | Start timelapse (deprecated) | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/pause` | POST | Pause timelapse (deprecated) | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/stop` | POST | Stop timelapse (deprecated) | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/complete` | POST | Complete timelapse (deprecated) | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/statistics` | GET | Get timelapse statistics | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/progress` | GET | Get real-time progress | `timelapse_id` |
| `/api/timelapses/{timelapse_id}/videos` | GET | **🆕 Get timelapse videos** | `timelapse_id` |
| **VIDEOS** |
| `/api/videos` | GET, POST | List videos / Create video request | `camera_id`, `timelapse_id` (query) |
| `/api/videos/generate` | POST | Generate video (main endpoint) | - |
| `/api/videos/generation-queue` | GET | Get generation queue status | - |
| `/api/videos/{video_id}` | GET, DELETE | Get/Delete specific video | `video_id` |
| `/api/videos/{video_id}/download` | GET | Download video file | `video_id` |
| `/api/videos/{video_id}/generation-status` | GET | Get generation status | `video_id` |
| `/api/videos/{video_id}/cancel-generation` | POST | Cancel video generation | `video_id` |
| **IMAGES** |
| `/api/images` | GET | List images with filtering | `camera_id`, `timelapse_id`, `limit`, `offset` |
| `/api/images/count` | GET | Get image count | `camera_id`, `timelapse_id` |
| `/api/images/{image_id}` | GET, DELETE | Get/Delete specific image | `image_id` |
| `/api/images/{image_id}/serve` | GET | Serve image with size variants | `image_id`, `size` |
| `/api/images/{image_id}/small` | GET | Serve small image variant | `image_id` |
| `/api/images/{image_id}/thumbnail` | GET | Serve thumbnail variant | `image_id` |
| `/api/images/{image_id}/regenerate-thumbnails` | POST | Force thumbnail regeneration | `image_id` |
| `/api/images/{image_id}/quality-assessment` | GET | Get quality assessment | `image_id` |
| `/api/images/camera/{camera_id}/latest` | GET | Serve latest camera image | `camera_id`, `size` |
| `/api/images/camera/{camera_id}/statistics` | GET | Get camera image statistics | `camera_id` |
| `/api/images/timelapse/{timelapse_id}/statistics` | GET | Get timelapse image statistics | `timelapse_id` |
| `/api/images/bulk/download` | POST | Bulk download as ZIP | - |
| `/api/images/{path:path}` | GET | Serve by dynamic path | `path` |
| **CORRUPTION DETECTION** |
| `/api/corruption/stats` | GET | System corruption statistics | - |
| `/api/corruption/camera/{camera_id}/stats` | GET | Camera corruption stats | `camera_id`, `days` |
| `/api/corruption/camera/{camera_id}/history` | GET | Camera corruption history | `camera_id`, `hours` |
| `/api/corruption/camera/{camera_id}/settings` | GET | Camera corruption settings | `camera_id` |
| `/api/corruption/settings` | GET | Global corruption settings | - |
| `/api/corruption/logs` | GET | Corruption detection logs | `camera_id`, `page`, `page_size`, `min_score`, `max_score` |
| `/api/corruption/health` | GET | Corruption system health | - |
| **VIDEO AUTOMATION** |
| `/api/video-automation/queue/jobs` | GET | Get generation queue jobs | `status`, `limit` |
| `/api/video-automation/queue/status` | GET | Get queue status | - |
| `/api/video-automation/trigger/manual` | POST | Trigger manual generation | - |
| `/api/video-automation/camera/{camera_id}/settings` | GET, PUT | Camera automation settings | `camera_id` |
| `/api/video-automation/timelapse/{timelapse_id}/settings` | GET, PUT | Timelapse automation settings | `timelapse_id` |
| `/api/video-automation/statistics` | GET | Automation statistics | - |
| `/api/video-automation/process-queue` | POST | Process automation queue | - |
| `/api/video-automation/health` | GET | Automation system health | - |
| **THUMBNAILS** |
| `/api/thumbnails/generate/{image_id}` | POST | Generate thumbnails for image | `image_id`, `force_regenerate` |
| `/api/thumbnails/stats` | GET | Thumbnail statistics | - |
| `/api/thumbnails/regenerate-all` | POST | Start bulk regeneration | `limit` |
| `/api/thumbnails/regenerate/status` | GET | Get regeneration status | - |
| `/api/thumbnails/cleanup` | DELETE | Cleanup orphaned thumbnails | `dry_run` |
| **SETTINGS** |
| `/api/settings` | GET, POST, PUT | Get/Create/Update settings | - |
| `/api/settings/list` | GET | Get settings as list | - |
| `/api/settings/{key}` | GET, PUT, DELETE | Get/Update/Delete setting by key | `key` |
| `/api/settings/bulk` | POST | Update multiple settings | - |
| `/api/settings/timezone/supported` | GET | Get supported timezones | - |
| `/api/settings/timezone/validate` | POST | Validate timezone | - |
| `/api/settings/timezone/current` | GET | Get current timezone | - |
| `/api/settings/timezone` | PUT | Update timezone | - |
| `/api/settings/corruption/settings` | GET | Get corruption settings | - |
| `/api/settings/weather` | GET, PUT | Weather settings | - |
| **LOGS** |
| `/api/logs` | GET | Get logs with filtering | `level`, `camera_id`, `search`, `page`, `limit`, `start_date`, `end_date` |
| `/api/logs/stats` | GET | Get log statistics | `hours` |
| `/api/logs/levels` | GET | Get available log levels | - |
| `/api/logs/sources` | GET | Get log sources | - |
| `/api/logs/recent` | GET | Get recent logs | `count`, `level` |
| `/api/logs/search` | GET | Search logs | `query`, `page`, `limit`, `camera_id`, `level` |
| `/api/logs/summary` | GET | Get log summary | `hours` |
| `/api/logs/errors` | GET | Get recent errors | `hours`, `limit` |
| `/api/logs/cleanup` | DELETE | Cleanup old logs | `days_to_keep` |
| `/api/logs/cameras/{camera_id}` | GET | Get camera logs | `camera_id`, `limit` |
| **DASHBOARD** |
| `/api/dashboard` | GET | Complete dashboard overview | - |
| `/api/dashboard/stats` | GET | Dashboard statistics | - |
| `/api/dashboard/health-score` | GET | System health score | - |
| `/api/dashboard/camera-performance` | GET | Camera performance metrics | `camera_id` |
| `/api/dashboard/quality-trends` | GET | Quality trend data | `hours`, `camera_id` |
| `/api/dashboard/storage` | GET | Storage statistics | - |
| `/api/dashboard/system-overview` | GET | System overview | - |
| `/api/dashboard/health` | GET | Dashboard health status | - |
| **HEALTH & MONITORING** |
| `/api/health` | GET | Basic health check | - |
| `/api/health/detailed` | GET | Comprehensive health check | - |
| `/api/health/database` | GET | Database health check | - |
| `/api/health/services` | GET | Services health check | - |
| `/api/health/readiness` | GET | Kubernetes readiness probe | - |
| `/api/health/liveness` | GET | Kubernetes liveness probe | - |

---

## 🔍 DATABASE SCHEMA VALIDATION (June 30, 2025)

**✅ Entity Architecture Confirmed**: Database schema validates the entity-based architecture:
- `cameras.active_timelapse_id` → `timelapses.id` (one-to-many)
- `images.timelapse_id` → `timelapses.id` (many-to-one) 
- `videos.timelapse_id` → `timelapses.id` (many-to-one)

**✅ Video Automation Infrastructure Complete**: Full automation schema exists:
- Camera automation fields: `video_automation_mode`, `video_generation_mode`, `standard_fps`, etc.
- Timelapse inheritance fields: Mirror automation settings for override capability
- Job queue table: `video_generation_jobs` with workflow management fields

**✅ Corruption Detection Active**: Complete corruption system in database:
- `corruption_logs` table with detailed tracking
- Camera-level corruption fields and degraded mode support

**🎯 Implementation Priority Update**: Database schema confirms many "missing" backend routes likely just need frontend proxies.

---

| **Frontend Route** | **Backend Route** | **Methods** | **Status** |
|-------------------|-------------------|-------------|------------|
| **CAMERAS** |
| `/api/cameras` | `/api/cameras` | GET, POST | ✅ Match |
| `/api/cameras/[id]` | `/api/cameras/{camera_id}` | GET, PUT, DELETE | ✅ Match |
| `/api/cameras/[id]/details` | `/api/cameras/{camera_id}/details` | GET | ✅ Match |
| `/api/cameras/[id]/connectivity` | `/api/cameras/{camera_id}/connectivity` | GET | ✅ Match |
| `/api/cameras/[id]/health` | `/api/cameras/{camera_id}/health` | GET | ✅ Match |
| `/api/cameras/[id]/status` | `/api/cameras/{camera_id}/status` | GET | ✅ Match |
| `/api/cameras/[id]/test-connection` | `/api/cameras/{camera_id}/test-connection` | POST | ✅ Match |
| `/api/cameras/[id]/capture-now` | `/api/cameras/{camera_id}/capture-now` | POST | ✅ Match |
| `/api/cameras/[id]/images/latest` | `/api/cameras/{camera_id}/images/latest` | GET | ✅ Match |
| `/api/cameras/[id]/latest-capture` | `/api/cameras/{camera_id}/latest-capture` | GET | ✅ Match |
| `/api/cameras/[id]/latest-capture/download` | `/api/cameras/{camera_id}/latest-capture/download` | GET | ✅ Match |
| `/api/cameras/[id]/timelapse-stats` | `/api/cameras/{camera_id}/timelapse-stats` | GET | ✅ Match |
| `/api/cameras/[id]/start-timelapse` | `/api/cameras/{camera_id}/start-timelapse` | POST | ✅ Match |
| `/api/cameras/[id]/pause-timelapse` | `/api/cameras/{camera_id}/pause-timelapse` | POST | ✅ Match |
| `/api/cameras/[id]/resume-timelapse` | `/api/cameras/{camera_id}/resume-timelapse` | POST | ✅ Match |
| `/api/cameras/[id]/stop-timelapse` | `/api/cameras/{camera_id}/stop-timelapse` | POST | ✅ Match |
| `/api/cameras/[id]/complete-timelapse` | `/api/cameras/{camera_id}/complete-timelapse` | POST | ✅ Match |
| **TIMELAPSES** |
| `/api/timelapses` | `/api/timelapses` | GET, POST | ✅ Match |
| `/api/timelapses/new` | `/api/timelapses/new` | POST | ✅ Match |
| `/api/timelapses/[id]` | `/api/timelapses/{timelapse_id}` | GET | ✅ Match |
| `/api/timelapses/[id]/complete` | `/api/timelapses/{timelapse_id}/complete` | POST | ✅ Match |
| `/api/timelapses/[id]/pause` | `/api/timelapses/{timelapse_id}/pause` | POST | ✅ Match |
| `/api/timelapses/[id]/start` | `/api/timelapses/{timelapse_id}/start` | POST | ✅ Match |
| `/api/timelapses/[id]/videos` | `/api/timelapses/{timelapse_id}/videos` | GET | ✅ **NEW MATCH** |
| **VIDEOS** |
| `/api/videos` | `/api/videos` | GET, POST | ✅ Match |
| `/api/videos/generate` | `/api/videos/generate` | POST | ✅ Match |
| `/api/videos/generation-queue` | `/api/videos/generation-queue` | GET | ✅ Match |
| `/api/videos/[id]` | `/api/videos/{video_id}` | GET | ✅ Match |
| `/api/videos/[id]/download` | `/api/videos/{video_id}/download` | GET | ✅ Match |
| `/api/videos/[id]/generation-status` | `/api/videos/{video_id}/generation-status` | GET | ✅ Match |
| `/api/videos/[id]/cancel-generation` | `/api/videos/{video_id}/cancel-generation` | POST | ✅ Match |
| **IMAGES** |
| `/api/images/[id]/small` | `/api/images/{image_id}/small` | GET | ✅ Match |
| `/api/images/[id]/thumbnail` | `/api/images/{image_id}/thumbnail` | GET | ✅ Match |
| `/api/images/count` | `/api/images/count` | GET | ✅ Match |
| **CORRUPTION** |
| `/api/corruption/cameras/[id]/stats` | `/api/corruption/camera/{camera_id}/stats` | GET | ✅ Match |
| `/api/corruption/logs` | `/api/corruption/logs` | GET | ✅ Match |
| `/api/corruption/settings` | `/api/corruption/settings` | GET | ✅ Match |
| `/api/corruption/stats` | `/api/corruption/stats` | GET | ✅ Match |
| **VIDEO AUTOMATION** |
| `/api/video-automation/queue/jobs` | `/api/video-automation/queue/jobs` | GET | ✅ Match |
| `/api/video-automation/queue/status` | `/api/video-automation/queue/status` | GET | ✅ Match |
| `/api/video-automation/trigger/manual` | `/api/video-automation/trigger/manual` | POST | ✅ Match |
| **THUMBNAILS** |
| `/api/thumbnails/regenerate-all` | `/api/thumbnails/regenerate-all` | POST | ✅ Match |
| `/api/thumbnails/stats` | `/api/thumbnails/stats` | GET | ✅ Match |
| **SETTINGS** |
| `/api/settings` | `/api/settings` | GET, PUT | ✅ Match |
| `/api/settings/weather` | `/api/settings/weather` | GET, PUT | ✅ Match |
| **SYSTEM** |
| `/api/dashboard` | `/api/dashboard` | GET | ✅ Match |
| `/api/dashboard/stats` | `/api/dashboard/stats` | GET | ✅ Match |
| `/api/health` | `/api/health` | GET | ✅ Match |
| `/api/events` | *SSE endpoint* | GET | ✅ Special |
| `/api/logs` | `/api/logs` | GET | ✅ Match |
| `/api/logs/stats` | `/api/logs/stats` | GET | ✅ Match |

---

## 🔍 POTENTIAL MATCHES (Different Names, Same Function)

### Likely Functional Matches

| **Frontend Route** | **Potential Backend Match** | **Evidence** | **Action Needed** |
|-------------------|---------------------------|--------------|-------------------|
| `/api/cameras/[id]/capture` | `/api/cameras/{camera_id}/latest-capture` | Both serve camera capture data | Rename frontend route |
| `/api/timelapses/[id]/images` | `/api/images?timelapse_id={id}` | Backend supports timelapse_id filter | **Use nested resource instead** |
| `/api/timelapses/[id]/status` | `/api/timelapses/{timelapse_id}` (GET/PUT) | Status is part of main timelapse object | Use main endpoint |
| `/api/images/[...path]` | `/api/images/{path:path}` | Same catch-all functionality, different syntax | ✅ Already matches |
| `/api/images/[id]/download` | `/api/images/{image_id}/serve` | Both serve image files | Standardize naming |
| `/api/images/bulk-download` | `/api/images/bulk/download` | Same functionality, different path format | Fix path format |

### Confirmed Matches (Initially Missed)

| **Frontend Route** | **Backend Route** | **Status** |
|-------------------|-------------------|------------|
| `/api/thumbnails/regenerate-all/status` | `/api/thumbnails/regenerate/status` | ⚠️ Minor path difference |

### Weather Settings Breakdown

| **Frontend Route** | **Potential Backend Match** | **Notes** |
|-------------------|---------------------------|-----------|
| `/api/settings/weather/data` | `/api/settings/weather` (GET) | Same data, different endpoint |
| `/api/settings/weather/validate-api-key` | `/api/settings/timezone/validate` pattern | Could use similar validation pattern |
| `/api/settings/weather/refresh` | `/api/settings/weather` (PUT) | Refresh could be a PUT operation |
| `/api/settings/weather/sun-window` | Backend may handle this in main weather settings | Need to check implementation |

---

## ❌ NO MATCHES

### Frontend Routes with No Backend Match

| **Frontend Route** | **Methods** | **Issue** | **Priority** |
|-------------------|-------------|-----------|--------------|
| `/api/timelapses/[id]/images` | GET | Missing backend endpoint | **VERY HIGH** - DB ready |
| `/api/timelapses/[id]/immediate-capture` | POST | Missing backend endpoint | **MEDIUM** |
| `/api/timelapses/[id]/status` | GET, PUT | Missing backend endpoint | **LOW** - Use main endpoint |
| `/api/corruption/cameras/[id]/reset-degraded` | POST | Missing backend endpoint | **MEDIUM** |
| `/api/corruption/test-image` | POST | Missing backend endpoint | **LOW** |
| `/api/settings/weather/data` | GET | Missing backend endpoint | **MEDIUM** |
| `/api/settings/weather/refresh` | POST | Missing backend endpoint | **MEDIUM** |
| `/api/settings/weather/sun-window` | GET, POST | Missing backend endpoint | **MEDIUM** |
| `/api/settings/weather/validate-api-key` | POST | Missing backend endpoint | **MEDIUM** |
| `/api/thumbnails/regenerate-all/cancel` | POST | Missing backend endpoint | **LOW** |
| `/api/debug/images` | GET | Missing backend endpoint | **LOW** |
| `/api/tests` | GET | Missing backend endpoint | **LOW** |

### Backend Routes with No Frontend Proxy

| **Backend Route** | **Methods** | **Category** | **Priority** |
|-------------------|-------------|--------------|--------------|
| `/api/cameras/{camera_id}/latest-thumbnail` | GET | Missing frontend proxy | **MEDIUM** |
| `/api/cameras/{camera_id}/latest-small` | GET | Missing frontend proxy | **MEDIUM** |
| `/api/cameras/{camera_id}/status` | PUT | Frontend only has GET | **HIGH** |
| `/api/cameras/{camera_id}/health` | PUT | Frontend only has GET | **HIGH** |
| `/api/timelapses/{timelapse_id}` | PUT, DELETE | Frontend missing | **HIGH** |
| `/api/timelapses/{timelapse_id}/stop` | POST | Frontend missing | **MEDIUM** |
| `/api/timelapses/{timelapse_id}/statistics` | GET | Frontend missing | **MEDIUM** |
| `/api/timelapses/{timelapse_id}/progress` | GET | Frontend missing | **MEDIUM** |
| `/api/videos/{video_id}` | DELETE | Frontend missing | **MEDIUM** |
| `/api/images` | GET | Frontend missing main list | **HIGH** |
| `/api/images/{image_id}` | GET, DELETE | Frontend missing | **HIGH** |
| `/api/images/{image_id}/serve` | GET | Frontend missing | **HIGH** |
| `/api/images/{image_id}/regenerate-thumbnails` | POST | Frontend missing | **MEDIUM** |
| `/api/images/{image_id}/quality-assessment` | GET | Frontend missing | **MEDIUM** |
| `/api/images/camera/{camera_id}/latest` | GET | Frontend missing | **MEDIUM** |
| `/api/images/camera/{camera_id}/statistics` | GET | Frontend missing | **MEDIUM** |
| `/api/images/timelapse/{timelapse_id}/statistics` | GET | Frontend missing | **MEDIUM** |
| `/api/corruption/camera/{camera_id}/history` | GET | Frontend missing | **MEDIUM** |
| `/api/corruption/camera/{camera_id}/settings` | GET | Frontend missing | **MEDIUM** |
| `/api/corruption/health` | GET | Frontend missing | **MEDIUM** |
| `/api/video-automation/camera/{camera_id}/settings` | GET, PUT | Frontend missing | **VERY HIGH** - DB ready |
| `/api/video-automation/timelapse/{timelapse_id}/settings` | GET, PUT | Frontend missing | **VERY HIGH** - DB ready |
| `/api/video-automation/statistics` | GET | Frontend missing | **MEDIUM** |
| `/api/video-automation/process-queue` | POST | Frontend missing | **LOW** |
| `/api/video-automation/health` | GET | Frontend missing | **MEDIUM** |
| `/api/thumbnails/generate/{image_id}` | POST | Frontend missing | **MEDIUM** |
| `/api/thumbnails/cleanup` | DELETE | Frontend missing | **LOW** |
| `/api/settings/list` | GET | Frontend missing | **LOW** |
| `/api/settings/{key}` | GET, PUT, DELETE | Frontend missing | **MEDIUM** |
| `/api/settings/bulk` | POST | Frontend missing | **MEDIUM** |
| `/api/settings/timezone/*` | All methods | Complete subsection missing | **MEDIUM** |
| `/api/settings/corruption/settings` | GET | Frontend missing | **MEDIUM** |
| **LOGS** (Most endpoints) | Various | Most log endpoints missing | **MEDIUM** |
| **DASHBOARD** (Advanced) | Various | Advanced dashboard endpoints missing | **MEDIUM** |
| **HEALTH** (Detailed) | Various | Detailed health endpoints missing | **LOW** |

---

## 🔧 RECOMMENDED FIXES

### 1. Path Standardization
```bash
# Frontend changes needed:
/api/images/bulk-download → /api/images/bulk/download
/api/thumbnails/regenerate-all/status → /api/thumbnails/regenerate/status
```

### 2. Implement Nested Resources (RECOMMENDED)
```typescript
// Use nested resources for entity relationships:
GET /api/timelapses/{id}/videos   // ✅ IMPLEMENTED
GET /api/timelapses/{id}/images   // TODO: Implement next
```

### 3. Rename for Clarity
```bash
# Frontend route renames:
/api/cameras/[id]/capture → /api/cameras/[id]/latest-capture
/api/images/[id]/download → /api/images/[id]/serve
```

### 4. Add Missing Frontend Proxies (High Priority)
```bash
# Critical missing proxies:
PUT /api/cameras/[id]/status
PUT /api/cameras/[id]/health  
PUT /api/timelapses/[id]
DELETE /api/timelapses/[id]
GET /api/images
DELETE /api/videos/[id]
```

### 5. Add Missing Backend Endpoints (High Priority)
```bash
# Critical missing endpoints:
GET /api/timelapses/{id}/images
POST /api/corruption/cameras/{id}/reset-degraded
POST /api/timelapses/{id}/immediate-capture
```

---

## 📊 SUMMARY

**Current Status:**
- **✅ Matching Routes**: ~48 properly connected routes (**includes recent implementation**)
- **🔧 Easy Fixes**: ~8 routes needing minor path/naming changes  
- **🔄 Parameter Consolidation**: ~4 routes that should use query parameters
- **❌ Frontend Missing Backend**: ~11 frontend routes need backend endpoints
- **❌ Backend Missing Frontend**: ~35 backend routes need frontend proxies

**Total Match Rate**: ~74% of routes are connected or easily fixable!

**Next Implementation Priority** (Database-Validated):
1. ✅ **`/api/timelapses/{id}/videos`** - **COMPLETED** ✅
2. 🔄 **`/api/timelapses/{id}/images`** - Database ready, next to implement
3. 🔄 **Video automation frontend proxies** - Backend fully implemented, just needs frontend
4. 🔄 **Missing PUT/DELETE operations** - Add to frontend
5. 🔄 **Advanced dashboard/logging** - Add frontend proxies

The main gaps remaining are in advanced dashboard endpoints, detailed logging, health monitoring, and some corruption management features.