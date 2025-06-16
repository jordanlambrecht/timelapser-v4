# Changelog

All notable changes to the Timelapser v4 project will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.06.16] - Timezone System & Backend Startup Fixes 🌍

### Major Improvements

#### 🚨 **Backend Startup Issue Fixed**

- **CRITICAL FIX**: Resolved JSONDecodeError preventing FastAPI backend startup
- **Root Cause**: Pydantic Settings trying to parse comma-separated CORS_ORIGINS
  as JSON array
- **Solution**: Enhanced backend configuration to handle both string and list
  formats
- **Impact**: Application now starts reliably without configuration changes

#### 🌍 **Comprehensive Timezone-Aware Time System**

- **MAJOR FEATURE**: Implemented sophisticated timezone-aware time calculations
  throughout UI
- **Added**: Centralized time utilities in `/src/lib/time-utils.ts` with
  timezone support
- **Added**: Smart countdown hook `/src/hooks/use-camera-countdown.ts` with
  settings integration
- **Added**: Advanced timezone selector components with browser timezone
  detection
- **Enhanced**: All camera cards, timestamps, and countdowns now use
  database-configured timezone
- **Impact**: Accurate time displays regardless of user's browser timezone

#### 🔔 **Standardized Toast Notification System**

- **IMPROVEMENT**: Centralized user feedback system across all components
- **Replaced**: Inconsistent alert() calls and direct DOM manipulation
- **Added**: Success, error, and info toasts for all major user actions
- **Enhanced**: Professional user experience with consistent feedback patterns

### Backend Changes

#### Configuration & Environment

- **Modified**: `/backend/app/config.py` to use `Union[str, list[str]]` for
  cors_origins
- **Added**: `cors_origins_list` property for flexible CORS configuration
  parsing
- **Updated**: `/backend/app/main.py` to use new cors_origins_list property
- **Enhanced**: Robust environment variable handling prevents startup failures

#### API Enhancements

- **Enhanced**: `/backend/app/routers/settings.py` with timezone setting support
- **Added**: Database migration for settings table including timezone field
- **Improved**: Settings API endpoint provides timezone configuration to
  frontend

### Frontend Changes

#### Time System Components

- **Added**: `/src/lib/time-utils.ts` - Complete timezone-aware time utilities

  - `getConfiguredTimezone()` - Settings-aware timezone detection
  - `formatRelativeTime()` - Timezone-correct relative time formatting
  - `formatCountdown()` - Smart countdown with timezone support
  - `isWithinTimeWindow()` - Timezone-aware time window calculations

- **Added**: `/src/hooks/use-camera-countdown.ts` - Smart countdown management
  - `useCameraCountdown()` - Main hook for camera time displays
  - `useCaptureSettings()` - Fetches timezone and capture interval from API
  - Smart refresh intervals based on proximity to next capture

#### UI Components

- **Added**: `/src/components/timezone-selector-combobox.tsx` - Advanced
  timezone picker
- **Added**: `/src/components/timezone-selector.tsx` - Simple timezone selection
- **Added**: `/src/components/suspicious-timestamp-warning.tsx` - Timezone
  mismatch warnings
- **Enhanced**: `/src/lib/toast.ts` - Centralized notification system

#### Updated Components (Timezone-Aware)

- **Updated**: `/src/components/camera-card.tsx` - Uses timezone-aware countdown
  hook
- **Updated**: `/src/app/cameras/[id]/page.tsx` - Timezone-aware timestamp
  displays
- **Updated**: `/src/app/settings/page.tsx` - Timezone configuration interface
- **Updated**: `/src/app/logs/page.tsx` - Timezone-aware log timestamp display
- **Updated**: `/src/components/timelapse-modal.tsx` - Timezone-aware time
  formatting
- **Updated**: All major components to use centralized toast notification system

### Dependencies

- **Added**: `react-timezone-select` ^3.2.8 - Advanced timezone selection
  component
- **Added**: `cmdk` ^1.1.1 - Command menu for improved timezone picker UX

### Bug Fixes

- **Fixed**: TypeScript errors in camera-card.tsx related to TimeWindow
  interface usage
- **Fixed**: Backend startup failures due to CORS_ORIGINS parsing errors
- **Fixed**: Inconsistent time displays across different user timezones
- **Fixed**: Alert dialogs and DOM manipulation replaced with proper toast
  notifications

### Technical Improvements

- **Architecture**: All time calculations now use database-configured timezone
  vs browser local
- **Performance**: Smart refresh intervals reduce unnecessary countdown updates
- **Reliability**: Robust backend configuration prevents environment variable
  parsing failures
- **User Experience**: Consistent professional feedback through centralized
  toast system
- **Maintainability**: Centralized time utilities eliminate duplicate time
  calculation code

### Migration Notes

- **Breaking Change**: Components should now use `useCaptureSettings()` hook
  instead of hardcoded timezones
- **Environment**: Backend supports both comma-separated and JSON array formats
  for CORS_ORIGINS
- **UI Patterns**: All user actions should use toast notifications instead of
  alert() calls

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
