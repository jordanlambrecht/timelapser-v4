# Changelog

All notable changes to the Timelapser v4 project will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2025.06.20] - API Endpoint Debugging & Event System Fixes 🔧

### Bug Fixes

#### 🚨 **Critical API Endpoint Issues Resolved**

- **FIXED**: 404 error for `/api/timelapses/[id]/complete` endpoint
  - Created missing Next.js API proxy route
  - Updated backend endpoint to use query parameters correctly
  - Added proper camera_id parameter handling
- **FIXED**: 404 error for `/api/timelapses/[id]` single timelapse fetching
  - Added missing backend `GET /{timelapse_id}` endpoint
  - Created corresponding database method `get_timelapse_by_id()`
  - Implemented Next.js API proxy route

#### ⚡ **Event System Structure Corrections**

- **FIXED**: SSE event structure violations across multiple API routes
  - Corrected event data nesting to follow `{ type, data, timestamp }` structure
  - Fixed timelapses route putting data directly on event object
  - Updated videos route to use proper event structure
- **FIXED**: Invalid event types using non-approved event names
  - Changed `"video_generation_started"` to `"video_status_changed"` with
    status: "generating"
  - Changed `"video_failed"` to `"video_status_changed"` with status: "failed"
  - Ensured all events use types from `ALLOWED_EVENT_TYPES` constant

#### 🔧 **Next.js 15 Compatibility Fixes**

- **UPDATED**: All dynamic route handlers to use async params
  - Fixed route signature to `{ params }: { params: Promise<{ id: string }> }`
  - Added proper awaiting: `const { id } = await params`
  - Resolved TypeScript compilation errors

### Code Quality

#### 📚 **Enhanced Documentation & AI Context**

- **UPDATED**: AI-CONTEXT.md with new debugging patterns and constraints
  - Added API development rules and event system constraints
  - Documented systematic debugging approach for 404 errors
  - Added "DON'T BREAK THIS" warnings for event structure
- **ESTABLISHED**: Complete API development pattern documentation
  - Database method → Backend router → Frontend proxy → UI chain
  - Event emission and structure validation requirements

### Architecture

#### 🏗️ **API Architecture Improvements**

- **ENHANCED**: Backend timelapse router with missing endpoints
  - Added proper query parameter handling for completion endpoint
  - Implemented single timelapse retrieval functionality
- **IMPROVED**: Database layer with missing query methods
  - Added `get_timelapse_by_id()` for individual timelapse fetching
  - Maintained consistency with existing database patterns

## [2025.06.18] - Architecture Validation & Code Quality 🔧

### Code Quality & Architectural Compliance

#### 🔍 **Comprehensive Architecture Review**

- **VALIDATION**: Complete architectural compliance review against AI-CONTEXT
  rules
- **VERIFIED**: All changed files follow established patterns and constraints
- **CONFIRMED**: Database patterns using psycopg3 with dict_row properly
  implemented
- **VALIDATED**: Time calculation rules using useCaptureSettings() hook
  consistently
- **CHECKED**: Entity-based architecture with active_timelapse_id relationships
  intact

#### 🧹 **Production Code Cleanup**

- **REMOVED**: All console.log statements from production codebase for
  cleanliness
  - camera-card.tsx, page.tsx, settings/page.tsx, timezone-selector-combobox.tsx
  - camera-image-with-fallback.tsx and other core components
- **FIXED**: Critical bug in camera-image-with-fallback.tsx caused by
  console.log removal
- **RESTORED**: Proper return logic and error handling after cleanup

#### 🔧 **Build System & TypeScript Fixes**

- **FIXED**: Settings page syntax error ensuring correct timezone change handler
- **REFACTORED**: eventEmitter to shared module (src/lib/event-emitter.ts)
  - Resolved Next.js route export errors
  - Added comprehensive security measures and event type validation
  - Updated all API route imports to use new event-emitter module
- **EXCLUDED**: \_local-docs from TypeScript compilation to resolve build errors
- **ENSURED**: Clean TypeScript build with no errors or warnings

#### 🗄️ **Database & Backend Improvements**

- **FIXED**: All Python async/sync database cursor usages to use dict_row
  consistently
- **RESOLVED**: Python type errors in backend/app/database.py and related
  routers
- **VERIFIED**: Both AsyncDatabase and SyncDatabase classes properly using row
  factories
- **CONFIRMED**: Proper casting of database results to Dict[str, Any] types

#### 📁 **File Management**

- **ADDED**: `*.tsbuildinfo` to .gitignore (TypeScript build cache files)
- **ORGANIZED**: Proper separation of build artifacts from version control

### Technical Debt Resolution

#### ✅ **Error-Free Build State**

- **TypeScript**: Zero compilation errors or warnings
- **Python**: All type errors resolved in backend code
- **Linting**: Clean code following established patterns
- **Imports**: All module references properly updated

#### 🛡️ **Security & Performance**

- **Enhanced**: SSE event emitter with input sanitization
- **Improved**: Event type validation and size limits
- **Optimized**: Database connection patterns following best practices

### Migration Notes

- **Breaking Change**: eventEmitter moved to src/lib/event-emitter.ts
- **Build Requirement**: TypeScript build cache files now properly ignored
- **Development**: Clean build environment with no console.log pollution

## [2025.06.17] - Video Generation Settings System 🎬

### Major Feature Implementation

#### 🎯 **Complete Video Generation Settings System**

- **MAJOR FEATURE**: Comprehensive dual-mode video generation system with
  intelligent FPS calculation
- **Added**: Two distinct generation modes - Standard FPS and Target Time with
  smart switching
- **Enhanced**: Camera-level defaults with timelapse-level override capability
- **Implemented**: Real-time preview calculations showing exact video results
  before generation
- **Created**: Professional-grade video configuration with validation and user
  guidance
- **Impact**: Full creative control over timelapse video output with intelligent
  automation

#### 🗄️ **Database Schema Enhancements**

- **Added to cameras table**: Complete video generation field set

  - `video_generation_mode` ENUM ('standard', 'target') DEFAULT 'standard'
  - `standard_fps` INTEGER DEFAULT 24 - Target frames per second
  - `enable_time_limits` BOOLEAN DEFAULT false - Enable duration constraints
  - `min_time_seconds` INTEGER DEFAULT 60 - Minimum video duration
  - `max_time_seconds` INTEGER DEFAULT 300 - Maximum video duration
  - `target_time_seconds` INTEGER DEFAULT 120 - Exact target duration
  - `min_fps` REAL DEFAULT 1.0 - Minimum allowed FPS
  - `max_fps` REAL DEFAULT 60.0 - Maximum allowed FPS

- **Added to timelapses table**: Nullable video generation fields for
  inheritance

  - Complete override capability for per-timelapse customization
  - Settings inheritance: Camera defaults → Timelapse overrides
  - Backward compatible with existing timelapses

- **Created**: Video generation mode ENUM type with proper constraints
- **Applied**: Database migration successfully with data preservation

#### 🚀 **Dual-Mode Video Generation Logic**

**Standard FPS Mode Implementation**:

- **User Control**: Set desired FPS (1-60) with professional defaults
- **Optional Time Limits**: Enable min/max duration constraints with automatic
  FPS adjustment
- **Smart Adjustment**: System automatically modifies FPS to respect time limits
- **Real-time Preview**: "24 FPS → 744 images = 31.0 seconds" instant
  calculation
- **Use Case**: Professional framerates with optional duration control

**Target Time Mode Implementation**:

- **Precise Control**: Set exact target video duration in seconds
- **Automatic Calculation**: FPS = image_count / target_time with bounds
  enforcement
- **Quality Bounds**: Min/max FPS limits prevent unusable framerates
- **Real-time Preview**: "120s target → 744 images = 6.2 FPS" instant feedback
- **Use Case**: Presentations and content with specific timing requirements

#### 🔧 **Backend Architecture Enhancements**

**Video Calculation Engine**:

- **Added**: `/backend/video_calculations.py` - Complete video generation
  calculation logic
- **Implemented**: `calculate_video_settings()` function with dual-mode support
- **Enhanced**: Smart FPS adjustment algorithms with bounds checking
- **Created**: Comprehensive validation with edge case handling
- **Added**: Real-time preview calculation for UI integration

**Enhanced API Endpoints**:

- **Added**: `GET/PATCH /api/cameras/{id}/video-settings` - Camera video
  configuration
- **Added**: `GET /api/cameras/{id}/video-preview` - Real-time preview
  calculations
- **Added**: `GET/PATCH /api/timelapses/{id}/video-settings` - Per-timelapse
  overrides
- **Added**: `GET /api/timelapses/{id}/video-preview` - Inheritance-aware
  preview
- **Enhanced**: All endpoints with comprehensive validation and error handling

**Database Integration**:

- **Enhanced**: Camera and Timelapse Pydantic models with video generation
  fields
- **Added**: `get_effective_video_settings()` method for inheritance resolution
- **Added**: `copy_camera_video_settings_to_timelapse()` for defaults copying
- **Improved**: Type safety between frontend TypeScript and backend Python
  models

### Frontend Implementation Excellence

#### 🎨 **VideoGenerationSettings Component**

**Comprehensive React Component**
(`/src/components/video-generation-settings.tsx`):

- **Mode Toggle**: Intuitive switching between Standard FPS and Target Time
  modes
- **Standard FPS Interface**: FPS input with optional time limits toggle and
  min/max controls
- **Target Time Interface**: Duration input with FPS bounds configuration
- **Real-time Preview**: Live calculations showing exact video results
- **Smart Validation**: Comprehensive form validation with helpful error
  messages
- **State Management**: React Hook Form integration with proper error handling

**Advanced UI Features**:

- **Conditional Rendering**: UI adapts based on selected mode and enabled
  options
- **Live Calculations**: Instant preview updates as user types
- **Validation Feedback**: Real-time error indication with correction guidance
- **Professional Design**: Clean, intuitive interface following design system
  patterns

#### 🔄 **Settings Inheritance & Integration**

**Camera Details Page Integration**:

- **Settings Sidebar**: VideoGenerationSettings component integrated into camera
  details
- **API Integration**: PATCH requests for settings updates with proper error
  handling
- **Real-time Sync**: Changes immediately reflected in preview calculations
- **Toast Notifications**: Success/error feedback for all configuration
  operations

**Inheritance System**:

- **Visual Indicators**: Clear display when timelapse inherits camera defaults
- **Override Capability**: Timelapse settings override camera defaults when
  specified
- **Reset Functionality**: Easy restoration to camera defaults
- **Inheritance Resolution**: Automatic calculation of effective settings

### User Experience & Workflow

#### 🎯 **Intuitive User Workflows**

**Casual User Experience (Standard FPS Mode)**:

1. Set desired FPS (default 24 for professional look)
2. Optionally enable time limits for duration control
3. System handles calculations and adjustments automatically
4. Preview shows exact video duration before generation
5. Generate video with predictable, professional results

**Advanced User Experience (Target Time Mode)**:

1. Set exact target duration required (e.g., 120 seconds for presentation)
2. Configure FPS bounds for quality control (e.g., 6-30 FPS)
3. System calculates optimal FPS within constraints
4. Preview shows calculated FPS and confirms exact timing
5. Generate video with precise duration requirements

**Professional Features**:

- **Real-time Feedback**: Always see exact results before committing to
  generation
- **Smart Defaults**: Professional settings work immediately without
  configuration
- **Progressive Disclosure**: Advanced options available when needed
- **Validation Guidance**: Clear error messages with specific correction
  suggestions

#### 📊 **Example Calculations & Results**

**Standard FPS Mode Examples**:

- 744 images @ 24 FPS → 31.0 seconds (professional cinematic look)
- 1440 images @ 12 FPS → 120.0 seconds (smooth motion overview)
- 300 images @ 10 FPS → 30.0 seconds (quick daily summary)

**Target Time Mode Examples**:

- 744 images → 120s target → 6.2 FPS (presentation timing)
- 1440 images → 60s target → 24.0 FPS (fast overview)
- 300 images → 30s target → 10.0 FPS (time-constrained summary)

### Technical Implementation Details

#### 🔧 **Calculation Logic & Validation**

**Smart FPS Adjustment (Standard Mode)**:

```python
if enable_time_limits:
    calculated_duration = image_count / standard_fps
    if calculated_duration < min_time_seconds:
        adjusted_fps = image_count / min_time_seconds
    elif calculated_duration > max_time_seconds:
        adjusted_fps = image_count / max_time_seconds
    # Clamp to user-defined FPS bounds
    final_fps = max(min_fps, min(max_fps, adjusted_fps))
```

**Precise Duration Calculation (Target Mode)**:

```python
calculated_fps = image_count / target_time_seconds
# Enforce quality bounds
final_fps = max(min_fps, min(max_fps, calculated_fps))
actual_duration = image_count / final_fps
```

**Comprehensive Validation**:

- FPS bounds validation (min_fps ≤ max_fps, positive values)
- Time limits validation (min_time ≤ max_time, positive values)
- Image count validation (must have images to generate video)
- Mode-specific field requirements and cross-validation

#### 🗄️ **Database Schema Details**

**Migration Applied Successfully**:

- All video generation fields added with proper types and constraints
- Default values set for backward compatibility
- ENUM type created for video generation modes
- Foreign key relationships maintained with proper cascading

**Data Model Integration**:

- Pydantic models updated with complete video generation field set
- TypeScript interfaces synchronized with backend models
- API serialization/deserialization working correctly
- Database queries optimized for settings retrieval and updates

### Testing & Validation

#### ✅ **Comprehensive Testing Completed**

**Database & Migration**:

- ✅ Migration applied successfully to existing database
- ✅ All video generation fields created with correct types
- ✅ Default values working for existing cameras and timelapses
- ✅ ENUM constraints properly enforced

**Backend API**:

- ✅ All video settings endpoints returning correct data
- ✅ Preview calculations accurate with real image counts
- ✅ Settings inheritance working correctly (camera → timelapse)
- ✅ Validation preventing invalid configurations

**Frontend Integration**:

- ✅ VideoGenerationSettings component rendering correctly
- ✅ Real-time calculations updating as user types
- ✅ Form validation providing helpful error messages
- ✅ API integration with proper error handling and success feedback

**Real-world Validation**:

- ✅ Tested with 744 images showing accurate FPS/duration calculations
- ✅ Standard FPS mode producing expected video durations
- ✅ Target Time mode calculating correct FPS within bounds
- ✅ Settings inheritance working seamlessly between cameras and timelapses

### Benefits Achieved

#### User Experience Benefits

- ✅ **Creative Control**: Users can achieve specific visual goals (cinematic
  24fps vs quick overview)
- ✅ **Time Management**: Target time mode perfect for presentations with exact
  timing needs
- ✅ **Quality Assurance**: FPS bounds prevent choppy or overly fast videos
- ✅ **Flexibility**: Simple defaults for casual use, advanced options for
  professionals
- ✅ **Predictability**: Real-time preview eliminates surprises in video
  generation

#### Technical Benefits

- ✅ **Type Safety**: Complete TypeScript/Pydantic model synchronization
- ✅ **Data Integrity**: Database constraints prevent invalid configurations
- ✅ **Performance**: Efficient calculations with minimal UI lag
- ✅ **Maintainability**: Clean separation between calculation, API, and UI
  layers
- ✅ **Extensibility**: Foundation ready for advanced video generation features

#### Professional Features

- ✅ **Settings Management**: Enterprise-grade defaults and overrides system
- ✅ **Real-time Feedback**: Professional UI with immediate calculation results
- ✅ **Comprehensive Validation**: Error prevention with helpful user guidance
- ✅ **Integration**: Seamless connection with existing timelapse and video
  systems

### Future Enhancement Foundation

**Architecture Ready For**:

- **Video Templates**: Save/load settings as named presets
- **Batch Operations**: Apply settings to multiple timelapses simultaneously
- **Advanced Overlays**: Position, styling, and content configuration
- **Export Profiles**: Multiple output formats with different settings
- **Analytics**: Track which settings produce optimal results

**Video Generation Settings System** provides complete foundation for
professional-grade timelapse video creation with full user control and
intelligent automation.

### Migration Notes

#### For Developers

- **Database Schema**: All new video generation fields are backward compatible
- **API Usage**: New endpoints available, existing endpoints unchanged
- **Frontend**: VideoGenerationSettings component ready for integration
- **Calculation Logic**: Use video_calculations.py for all video generation math

#### For Users

- **Seamless**: Existing functionality preserved and enhanced
- **Enhanced Control**: New video generation options available in camera
  settings
- **Better Results**: Intelligent FPS calculation produces higher quality videos
- **Professional Output**: Settings enable both quick overviews and cinematic
  timelapses

---

## [2025.12.17] - Entity-Based Timelapse Architecture 🎯

### Revolutionary Architecture Transformation

#### 🏗️ **Complete Paradigm Shift: Status-Based → Entity-Based Timelapses**

- **MAJOR ARCHITECTURAL CHANGE**: Transformed timelapses from abstract status
  changes to concrete, trackable entities
- **Revolutionized Workflow**: Each "Start A New Timelapse" now creates
  discrete, permanent entities instead of reusing existing records
- **Enhanced User Experience**: Clear separation between total camera activity
  and current timelapse session
- **Historical Preservation**: All timelapses become permanent historical
  records with unique identity
- **Impact**: Foundation for professional-grade timelapse management with
  advanced organization capabilities

#### 🗄️ **Database Schema Evolution**

- **Added**: `active_timelapse_id INTEGER` to cameras table with proper foreign
  key constraints
- **Enhanced**: Timelapse status options to include 'completed' and 'archived'
  states
- **Implemented**: Unique constraint ensuring only one active timelapse per
  camera
- **Migration**: Successfully applied with complete backward compatibility and
  data preservation
- **Validation**: Existing timelapses preserved and functioning seamlessly

#### 📊 **Enhanced Camera Statistics & Display**

- **NEW FEATURE**: Dual image count display showing total vs current timelapse
  statistics
- **Added**: Real-time statistics automatically refresh with SSE events
- **Enhanced**: Camera cards now display "Images - Total: 1,250, Current: 47"
  format
- **Improved**: Clear visual separation between overall camera activity and
  active session
- **Impact**: Users can track both historical accumulation and current progress
  simultaneously

### Backend Architecture Enhancements

#### 🚀 **New Entity-Based API Endpoints**

- **Added**: `POST /api/timelapses/new` - Creates fresh timelapse entities with
  unique identity
- **Added**: `GET /api/cameras/{id}/timelapse-stats` - Returns total vs current
  image statistics efficiently
- **Added**: `POST /api/timelapses/{id}/complete` - Marks timelapses as
  permanent historical records
- **Enhanced**: Existing endpoints with active timelapse relationship support
- **Improved**: Type safety between Pydantic models and database schema

#### 🔧 **Enhanced Database Methods**

- **Implemented**: `create_new_timelapse()` method for discrete entity creation
- **Added**: `get_camera_timelapse_stats()` with efficient query patterns
- **Enhanced**: `complete_timelapse()` for proper entity lifecycle management
- **Updated**: Worker integration to respect active timelapse relationships
- **Optimized**: Database queries with proper foreign key relationships

#### 📦 **Pydantic Model Updates**

- **Enhanced**: Camera models with active_timelapse_id and statistics fields
- **Added**: Support for nested timelapse relationship data
- **Improved**: Type safety for entity-based workflow patterns
- **Validated**: Frontend-backend model synchronization maintained

### Frontend Architecture Changes

#### 🎨 **Camera Card Enhancement**

- **Transformed**: "Start" button to "Start A New Timelapse" with entity
  creation
- **Enhanced**: Real-time dual statistics display (total vs current images)
- **Improved**: Visual context for users about overall camera activity vs
  current session
- **Added**: Current timelapse name display when available
- **Impact**: More intuitive and informative user interface

#### 🔄 **Workflow Transformation**

- **Before**: "Start/Stop" toggled status on same reusable timelapse record
- **After**: "Start A New Timelapse" creates fresh entity → Record → Complete →
  Preserve history
- **Enhanced**: Real-time updates show both total and current statistics
- **Improved**: Clear understanding of timelapse boundaries and purpose

#### 🎯 **User Experience Evolution**

- **Historical Context**: Users can reference specific timelapses: "Storm
  documentation from June"
- **Clear Boundaries**: Each timelapse has defined start/completion with
  preserved settings
- **Professional Organization**: Foundation for advanced timelapse library and
  management
- **Intuitive Workflow**: Natural progression from creation → recording →
  completion → history

### Database Relationship Transformation

#### 🔗 **New Relationship Patterns**

```sql
-- Enhanced camera-timelapse relationship
cameras.active_timelapse_id → timelapses.id (FK with proper constraints)
timelapses.status: 'running' | 'paused' | 'completed' | 'archived'
images.timelapse_id → Clear association with specific timelapse entities
```

#### 📈 **Query Pattern Evolution**

- **Before**: Simple status checks and image counts
- **After**: Complex relationship queries with total vs current statistics
- **Enhanced**: Efficient aggregation queries for dual count display
- **Optimized**: PostgreSQL relationship handling with proper indexing

### User Experience Transformation

#### Before Entity-Based Architecture

- Single reusable timelapse per camera with status changes
- No historical separation between recording sessions
- Images accumulated indefinitely without clear boundaries
- Basic "Start/Stop" functionality with no organization
- No way to reference specific recording periods

#### After Entity-Based Architecture

- ✅ **Discrete Timelapse Entities**: Each session becomes a permanent,
  identifiable record
- ✅ **Historical Preservation**: All timelapses maintained as concrete
  historical records
- ✅ **Clear Organization**: Separate counting and tracking for total vs current
  activity
- ✅ **Professional Workflow**: Create → Record → Complete → Preserve lifecycle
- ✅ **Enhanced Context**: Users can reference and organize specific recording
  sessions
- ✅ **Foundation Ready**: Architecture supports advanced features like
  Timelapse Library

### Advanced Feature Enablement

#### 🎬 **Timelapse Library Foundation**

- **Database Structure**: Concrete entities ready for library interface
  implementation
- **Historical Data**: All timelapses preserved with names, dates, and
  statistics
- **Query Capability**: Efficient retrieval of completed timelapses for
  management
- **Organization Ready**: Foundation for filtering, searching, and organizing
  timelapses

#### 🎯 **Targeted Video Generation**

- **Specific Targeting**: Generate videos from individual historical timelapses
- **Clear Scope**: Each timelapse has defined image boundaries and settings
- **Enhanced Control**: Users can create videos from specific recording sessions
- **Quality Consistency**: Each timelapse preserves its capture settings and
  context

#### 🧹 **Granular Cleanup & Management**

- **Per-Timelapse Deletion**: Remove specific recording sessions without
  affecting others
- **Retention Policies**: Apply different cleanup rules to different timelapse
  types
- **Archive Management**: Move old timelapses to archived status while
  preserving data
- **Storage Optimization**: Targeted cleanup based on timelapse age, size, or
  usage

### Migration Success & Validation

#### 🔄 **Seamless Migration**

- **Data Preservation**: All existing timelapses converted to entity-based
  format
- **Backward Compatibility**: No disruption to existing functionality during
  transition
- **Real-time Validation**: Current system shows successful entity relationships
- **User Transparency**: Migration completed without user intervention required

#### ✅ **Current System Status**

```text
Camera 1: active_timelapse_id: 2 → "RainStorm" (640 images, running)
Camera 5: active_timelapse_id: 5 → Unnamed timelapse (0 images, running)
```

- **Validated**: Entity relationships working correctly in production
- **Performance**: No degradation from enhanced relationship queries
- **Functionality**: All existing features enhanced, none broken
- **Reliability**: System stable with new architecture patterns

### Technical Benefits Achieved

#### 🎯 **Architectural Excellence**

- ✅ **Professional Data Model**: Concrete entities instead of abstract status
  flags
- ✅ **Scalable Foundation**: Architecture supports unlimited advanced features
- ✅ **Clear Relationships**: Proper database design with enforced constraints
- ✅ **Maintainable Code**: Entity-based patterns easier to understand and
  extend

#### 📊 **Enhanced Capabilities**

- ✅ **Rich Statistics**: Total vs current tracking with real-time updates
- ✅ **Historical Analysis**: Foundation for analytics and reporting features
- ✅ **Flexible Organization**: Support for complex timelapse management
  workflows
- ✅ **Future-Proof Design**: Ready for enterprise-grade features and scaling

#### 🔧 **Development Benefits**

- ✅ **Type Safety**: Strong typing between frontend and backend models
- ✅ **Clear APIs**: Entity-based endpoints with intuitive naming and behavior
- ✅ **Testing Ready**: Concrete entities easier to test and validate
- ✅ **Documentation**: Self-documenting architecture with clear entity
  relationships

### Critical Implementation Notes

#### 🚨 **DON'T BREAK THIS** - Entity-Based Architecture Rules

1. **Always create new timelapse entities** when users click "Start A New
   Timelapse"
2. **Use active_timelapse_id** for determining where new images should be
   associated
3. **Preserve completed timelapses** as permanent historical records
4. **Display both total and current statistics** on camera cards for context
5. **Worker processes must respect** active timelapse relationships for image
   capture

#### 🎯 **Future Development Guidelines**

- **Build on Entity Foundation**: All new timelapse features should leverage the
  entity-based architecture
- **Preserve History**: Never delete or modify completed timelapse entities
- **Maintain Relationships**: Always use proper foreign key relationships for
  data integrity
- **Extend Thoughtfully**: New features should enhance rather than complicate
  the entity model

### Components Enhanced for Entity-Based Architecture

- `camera-card.tsx` - **Dual image count displays with total vs current
  statistics**
- Backend: `cameras.py`, `timelapses.py`, `database.py` - **Entity-based CRUD
  operations with enhanced relationships**
- Worker: `worker.py` - **Active timelapse relationship handling for proper
  image association**
- API: Multiple endpoints - **Enhanced with entity creation, statistics, and
  lifecycle management**
- Frontend: Dashboard and camera management - **Entity-aware user interface
  patterns**

---

## [2025.12.16] - Dashboard Refactoring & Enhanced Timelapse Control 🎯

### Major Dashboard Improvements

#### 🎨 **Complete Camera Card UI Overhaul**

- **MAJOR FEATURE**: Comprehensive dashboard camera card refactoring with
  enhanced user experience
- **Refactored**: CombinedStatusBadge from complex `cva` patterns to clean
  Next.js conditional logic
- **Enhanced**: Start button changed to "Start A New Timelapse" with
  configuration dialog
- **Improved**: Bulk operations simplified to intelligent "Resume" with
  conditional enable state
- **Added**: Visual progress border overlay showing capture progress in
  real-time
- **Impact**: More intuitive, powerful, and visually appealing timelapse
  management

#### ⚡ **Advanced Timelapse Configuration System**

- **NEW FEATURE**: Comprehensive timelapse creation dialog with advanced options
- **Added**: Custom timelapse naming with intelligent auto-generated defaults
- **Added**: Per-timelapse time window overrides (independent of camera
  defaults)
- **Added**: Auto-stop functionality with date/time scheduling and timezone
  awareness
- **Enhanced**: Form validation with comprehensive error handling and user
  feedback
- **Impact**: Full control over timelapse parameters without requiring camera
  setting changes

#### 📸 **Instant Capture Control**

- **NEW FEATURE**: "Capture Now" functionality for immediate image capture
- **Added**: Hamburger menu integration with conditional visibility (online
  camera + active timelapse)
- **Implemented**: Backend API endpoint `/api/cameras/{id}/capture-now` with
  validation
- **Enhanced**: Real-time feedback via SSE events and toast notifications
- **Impact**: Immediate capture capability for testing and critical moments

#### 🎨 **Visual Progress & Feedback Enhancements**

- **NEW FEATURE**: Animated progress border overlay on Next Capture boxes
- **Implemented**: SVG-based "egg timer" effect showing capture interval
  progress (0-100%)
- **Added**: Smooth transitions with glow effects when approaching capture time
- **Enhanced**: Visual coordination with existing "Now" state pulsing effects
- **Impact**: Rich visual feedback for capture timing and system state

### Database Schema Enhancements

#### 🗄️ **Auto-Stop & Enhanced Configuration**

- **Added**: `auto_stop_at TIMESTAMP WITH TIME ZONE` - Scheduled timelapse
  termination
- **Added**: `name VARCHAR(255)` - Custom timelapse naming
- **Added**: `time_window_start TIME` - Per-timelapse time window override
- **Added**: `time_window_end TIME` - Per-timelapse time window override
- **Added**: `use_custom_time_window BOOLEAN` - Enable per-timelapse time
  windows
- **Migration**: Database migration applied and documented

### Backend Changes

#### API & Database Enhancements

- **Enhanced**: `create_or_update_timelapse()` method with configuration
  parameter support
- **Added**: Auto-stop time handling with proper timezone awareness
- **Added**: Custom time window processing independent of camera settings
- **Implemented**: `/api/cameras/{id}/capture-now` endpoint with camera
  validation
- **Enhanced**: Timelapse API endpoints to handle new configuration fields
- **Improved**: Type safety between Pydantic models and database schema

#### Event Broadcasting

- **Added**: "capture_now_requested" SSE event type for immediate capture
  requests
- **Enhanced**: Real-time event broadcasting for new timelapse configuration
  changes
- **Improved**: Event validation and error handling for capture requests

### Frontend Changes

#### New Components

- **Added**: `/src/components/new-timelapse-dialog.tsx` - Advanced timelapse
  configuration dialog
  - Custom naming with auto-generated intelligent defaults
  - Time window override controls with validation
  - Auto-stop date/time picker with timezone support
  - Comprehensive form validation and error handling
- **Added**: `/src/components/ui/progress-border.tsx` - Animated SVG progress
  visualization
  - Smooth path animation following rounded rectangle border
  - Configurable colors and stroke width
  - Glow effects at high progress percentages

#### Enhanced Existing Components

- **Refactored**: `/src/components/ui/combined-status-badge.tsx` to use clean
  Next.js patterns
  - Removed complex `cva` abstraction layers
  - Implemented direct conditional logic with switch statements
  - Improved maintainability and debugging capability
- **Enhanced**: `/src/components/camera-card.tsx` with multiple improvements
  - Progress border integration with real-time capture progress
  - Capture Now menu item with conditional visibility
  - Enhanced status display logic for inactive timelapses
  - Improved button layout and expanded "Start A New Timelapse" text
- **Updated**: `/src/app/page.tsx` (dashboard) with intelligent bulk operations
  - Smart "Resume" button with conditional enable state
  - Tooltip feedback when no cameras can be resumed
  - Enhanced bulk operation logic and user feedback

#### Data Flow & State Management

- **Enhanced**: `/src/hooks/use-camera-countdown.ts` with progress calculation
  support
  - Added `captureProgress` return value (0-100 percentage)
  - Real-time progress calculation based on capture intervals
  - Integration with existing countdown timer infrastructure

### User Experience Improvements

#### Before Dashboard Refactoring

- Generic "Start" button with immediate execution
- Bulk "Start/Resume All" options without intelligence
- No visual progress indication for capture timing
- Basic status badges with maintenance complexity
- No immediate capture capability
- Limited timelapse configuration options

#### After Dashboard Refactoring

- ✅ **Intelligent Timelapse Creation**: Configuration dialog with naming, time
  windows, auto-stop
- ✅ **Smart Bulk Operations**: Conditional "Resume" button with helpful
  tooltips
- ✅ **Visual Progress Feedback**: Animated borders showing real-time capture
  progress
- ✅ **Simplified Architecture**: Cleaner status badge logic with better
  maintainability
- ✅ **Immediate Control**: Capture Now functionality for instant image capture
- ✅ **Enhanced Configurability**: Per-timelapse settings independent of camera
  defaults
- ✅ **Professional UX**: Comprehensive validation, error handling, and user
  feedback

### Technical Improvements

#### Code Quality & Maintainability

- **Simplified**: Status badge logic from complex abstractions to clear
  conditional patterns
- **Enhanced**: Form validation with timezone-aware date/time handling
- **Improved**: Component reusability with proper TypeScript interfaces
- **Optimized**: Progress calculation using existing countdown timer
  infrastructure

#### Integration & Compatibility

- **Maintains**: All existing timezone-aware time system functionality
- **Preserves**: SSE real-time update architecture and event broadcasting
- **Uses**: Established toast notification patterns for user feedback
- **Respects**: Database query optimization patterns (LATERAL joins)
- **Follows**: Existing TypeScript/Pydantic model synchronization

### Migration Notes

#### For Developers

- **Database Schema**: New timelapse fields are optional and backward compatible
- **API Changes**: Enhanced endpoints maintain backward compatibility
- **Component Updates**: CombinedStatusBadge simplified but interface unchanged
- **New Features**: Progress borders and capture now are additive enhancements

#### For Users

- **Seamless**: All existing functionality preserved and enhanced
- **Enhanced**: More powerful timelapse creation with better defaults
- **Improved**: Visual feedback and progress indication
- **Added**: New capture control options without complexity

### Benefits Achieved

#### User Experience

- ✅ **Intuitive Controls**: Clear separation between creation and management
  actions
- ✅ **Visual Feedback**: Real-time progress indication and state visualization
- ✅ **Flexible Configuration**: Per-timelapse settings without global camera
  changes
- ✅ **Professional Interface**: Comprehensive validation and error handling

#### Technical Excellence

- ✅ **Maintainable Code**: Simplified patterns with better debugging capability
- ✅ **Performance Optimized**: Leverages existing infrastructure without
  duplication
- ✅ **Type Safety**: End-to-end TypeScript/Pydantic model synchronization
- ✅ **Future Ready**: Extensible architecture for additional dashboard features

### Testing & Validation

#### UI/UX Testing

- ✅ **Configuration Dialog**: All form fields validate correctly with timezone
  awareness
- ✅ **Progress Borders**: Smooth animation with accurate percentage
  calculations
- ✅ **Bulk Operations**: Smart enable/disable logic with helpful user feedback
- ✅ **Capture Now**: Immediate execution with proper error handling

#### Technical Validation

- ✅ **Database Schema**: All new fields created successfully with proper types
- ✅ **API Endpoints**: Enhanced timelapse creation and capture now
  functionality working
- ✅ **Real-time Updates**: SSE events broadcasting correctly for new features
- ✅ **Cross-browser**: Progress animations and dialog functionality tested
  across modern browsers

---

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

#### ⏱️ **Timezone Display & Countdown Timer Enhancements**

- **ENHANCEMENT**: Refined timezone display system with real-time countdown
  improvements
- **Added**: Absolute time displays underneath relative countdown timers for
  temporal context
- **Enhanced**: Real-time per-second countdown updates when under 5 minutes (was
  updating every 5 seconds)
- **Improved**: Timezone abbreviations (CDT, UTC, etc.) instead of full timezone
  names to save UI space
- **Added**: Enhanced visual feedback for "Now" state with pulsing cyan effects
- **Implemented**: Smart conditional display logic (absolute times hidden during
  "Now" state)
- **Impact**: Smoother countdown experience with rich temporal context and
  compact timezone display

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

#### Countdown Timer & Display Enhancements

- **Enhanced**: `/src/lib/time-utils.ts` - Improved `getSmartRefreshInterval()`
  for real-time countdown
  - 0-3 seconds: 0.5-second updates (for "Now" detection)
  - 4-300 seconds: 1-second updates (real-time countdown under 5 minutes)
  - 301+ seconds: Progressive slower intervals for distant times
- **Enhanced**: `/src/lib/time-utils.ts` - Added
  `formatAbsoluteTimeForCounter()` function
  - Displays date and time in configured timezone
  - Uses timezone abbreviations via `Intl.DateTimeFormat` with
    `timeZoneName: 'short'`
  - Automatic DST handling (CDT/CST, EDT/EST, etc.)
  - Year display only when different from current year
- **Enhanced**: `/src/hooks/use-camera-countdown.ts` - Added absolute time
  returns
  - `lastCaptureAbsolute` and `nextCaptureAbsolute` values
  - Smart conditional display logic for "Now" states
- **Enhanced**: `/src/components/camera-card.tsx` - Integrated absolute time
  displays
  - Absolute timestamps shown beneath relative countdown timers
  - Pulsing cyan visual effects for "Now" state
  - Smart hiding of absolute times during capture moments
  - Enhanced visual feedback with coordinated color coding

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
- **Fixed**: Countdown timers updating every 5 seconds when under 5 minutes (now
  updates every second)
- **Fixed**: Lack of temporal context for relative timestamps (added absolute
  time displays)
- **Fixed**: UI space consumption by full timezone names (replaced with compact
  abbreviations)

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
- **Real-time UX**: Smooth per-second countdown progression for imminent
  captures
- **Timezone Display**: Automatic DST-aware abbreviation generation using Intl
  API
- **Visual Feedback**: Enhanced "Now" state indication with coordinated pulsing
  effects
- **Conditional UI**: Smart display logic shows information only when relevant

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
