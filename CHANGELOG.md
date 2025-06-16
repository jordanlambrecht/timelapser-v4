# Changelog

All notable changes to the Timelapser v4 project will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.12.16] - Image Loading System Overhaul 🎯

### Major Improvements

#### 🔄 **Image Loading System Complete Rewrite**

- **BREAKING CHANGE**: Migrated from foreign key based to query-based image
  retrieval
- **Removed**: `cameras.last_image_id` foreign key column from database schema
- **Added**: PostgreSQL LATERAL join queries for efficient latest image
  retrieval
- **Fixed**: All image loading 404 errors and display issues
- **Performance**: Optimized database queries using PostgreSQL strengths

#### 🐛 **Critical Bug Fixes**

- **Fixed**: JSON parse error when loading camera images on details page
- **Fixed**: 404 errors from non-existent `/api/images/{id}/thumbnail` endpoint
- **Fixed**: Stale foreign key references causing inconsistent image display
- **Fixed**: Camera card placeholder issues on dashboard
- **Fixed**: "Image Not Available" errors on camera details page

### Backend Changes

#### Database Layer

- **Removed**: `cameras.last_image_id` column and all FK relationships for
  latest images
- **Enhanced**: `AsyncDatabase.get_cameras_with_images()` with LATERAL join
  implementation
- **Enhanced**: `AsyncDatabase.get_camera_with_images_by_id()` with LATERAL join
- **Enhanced**: `AsyncDatabase.get_latest_image_for_camera()` with query-based
  approach
- **Enhanced**: `SyncDatabase.get_latest_image_for_camera()` for worker
  compatibility
- **Simplified**: `SyncDatabase.record_captured_image()` - removed FK update
  logic
- **Optimized**: All database methods now use efficient PostgreSQL LATERAL joins

#### API Endpoints

- **Fixed**: FastAPI `/api/cameras/{id}/latest-capture` endpoint error handling
- **Standardized**: All image serving through consistent, tested endpoints
- **Removed**: References to non-existent thumbnail endpoints

#### Data Models

- **Updated**: Pydantic `Camera` model - removed `last_image_id` field
- **Enhanced**: `CameraWithLatestImage` interface with proper nested image data
- **Improved**: `transform_camera_with_image_row()` function for LATERAL join
  data

### Frontend Changes

#### UI Components

- **Fixed**: Camera card image loading to use consistent endpoint
- **Fixed**: Camera details page image display and metadata
- **Improved**: Error handling with graceful fallback to placeholder images
- **Optimized**: Real-time image updates via SSE with cache-busting

#### API Integration

- **Standardized**: All image requests use `/api/cameras/{id}/latest-capture`
- **Removed**: Attempts to use non-existent thumbnail endpoints
- **Fixed**: Camera details page data fetching (removed binary data JSON
  parsing)
- **Enhanced**: TypeScript interfaces to match new query-based data structure

#### User Experience

- **Improved**: Consistent image display across dashboard and details pages
- **Enhanced**: Real-time image updates work reliably without 404 errors
- **Added**: Proper loading states and error handling for image display
- **Fixed**: Placeholder images show correctly when no captures exist

### Technical Debt Reduction

#### Code Simplification

- **Removed**: Complex FK maintenance logic from worker processes
- **Eliminated**: Multiple code paths for image serving
- **Simplified**: Database operations with single query pattern
- **Reduced**: Maintenance overhead by eliminating FK synchronization

#### Performance Improvements

- **Optimized**: Database queries using PostgreSQL LATERAL joins
- **Improved**: Real-time updates without unnecessary data refetching
- **Enhanced**: SSE event handling for image capture notifications
- **Streamlined**: API response patterns with consistent data structure

### Migration Notes

#### For Developers

- **Database Schema**: The `cameras.last_image_id` column has been removed
- **API Usage**: Always use `/api/cameras/{id}/latest-capture` for image serving
- **Query Patterns**: Use LATERAL joins for latest image retrieval
- **TypeScript**: Update interfaces to remove FK references

#### For Users

- **Transparent**: No user-facing changes required
- **Improved**: Image loading is now more reliable and consistent
- **Enhanced**: Real-time updates work without page refreshes
- **Better**: Error handling when cameras have no captured images

### Benefits Achieved

#### Reliability

- ✅ **Always Accurate**: No stale FK references, always returns actual latest
  image
- ✅ **Error Resilient**: Graceful handling of missing/deleted images
- ✅ **Consistent**: Single code path for all image retrieval and display
- ✅ **Real-time Compatible**: Works seamlessly with SSE refresh system

#### Performance

- ✅ **PostgreSQL Optimized**: LATERAL joins leverage database engine strengths
- ✅ **Reduced Overhead**: No FK updates needed on every capture operation
- ✅ **Efficient Queries**: Single query retrieves camera and latest image data
- ✅ **Faster Updates**: Real-time image refresh without full data reload

#### Maintainability

- ✅ **Zero Maintenance**: No FK synchronization required
- ✅ **Simplified Logic**: Easier to understand and debug
- ✅ **Self-Healing**: Automatically finds latest image even after deletions
- ✅ **Future-Proof**: Robust foundation for additional features

### Testing

#### Validation Completed

- ✅ **Dashboard Image Display**: All camera cards show latest images correctly
- ✅ **Camera Details Page**: Latest images display without JSON parse errors
- ✅ **Real-time Updates**: SSE events trigger image refresh properly
- ✅ **Error Handling**: Graceful fallback when no images exist
- ✅ **Database Performance**: LATERAL join queries perform efficiently
- ✅ **Cross-browser Compatibility**: Image loading works across modern browsers

#### Edge Cases Tested

- ✅ **No Images**: Proper placeholder display for cameras without captures
- ✅ **Image Deletion**: System handles missing image files gracefully
- ✅ **Network Issues**: Timeout and retry logic for image loading
- ✅ **Large Datasets**: Performance with cameras having thousands of images
- ✅ **Concurrent Users**: Multiple users accessing images simultaneously

---

## Previous Releases

### [2025.06.16] - Initial System Fixes

- Fixed SSE event broadcasting system
- Enhanced service coordination and health checks
- Resolved database connection pool issues
- Added comprehensive diagnostic tools
- Implemented real-time dashboard updates

### [2025.06.10] - Core System Implementation

- Initial implementation of RTSP camera capture system
- Database schema design and implementation
- FastAPI backend with async/sync database patterns
- Next.js frontend with TypeScript integration
- Video generation with FFmpeg
- Day overlay system for timelapse videos
