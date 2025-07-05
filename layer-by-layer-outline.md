# Timelapser v4 Target Architecture - Final Design

## API Layer (Routers)

> _FastAPI endpoints that handle HTTP requests/responses and delegate to
> services_

### camera_routers.py

- **Role**: Camera management HTTP endpoints
- **Responsibilities**: Camera CRUD operations, health status endpoints, image
  serving endpoints
- **Interactions**: Uses `CameraService` for business logic, returns Pydantic
  models, handles HTTP status codes and error responses

### video_routers.py

- **Role**: Video management and generation HTTP endpoints
- **Responsibilities**: Video metadata CRUD, manual video generation triggers,
  video file serving
- **Interactions**: Uses `VideoService` for business logic, coordinates with
  `VideoAutomationService` for generation requests

### timelapse_routers.py

- **Role**: Timelapse entity management HTTP endpoints
- **Responsibilities**: Timelapse lifecycle operations
  (start/pause/stop/complete), entity CRUD, progress tracking
- **Interactions**: Uses `TimelapseService` for business logic, broadcasts SSE
  events for real-time updates

### image_routers.py

- **Role**: Image metadata and serving HTTP endpoints
- **Responsibilities**: Image metadata queries, thumbnail serving with cascading
  fallbacks, image statistics
- **Interactions**: Uses `ImageService` for business logic, serves files
  directly from filesystem with proper headers

### corruption_routers.py

- **Role**: Corruption detection management HTTP endpoints
- **Responsibilities**: Corruption statistics, degraded mode management,
  corruption settings configuration
- **Interactions**: Uses `CorruptionService` for business logic, provides
  quality metrics and audit trail access

### settings_routers.py

- **Role**: System configuration HTTP endpoints
- **Responsibilities**: Global settings CRUD, validation, inheritance resolution
- **Interactions**: Uses `SettingsService` for business logic, handles settings
  validation and broadcasting changes

### health_routers.py

- **Role**: System health and monitoring HTTP endpoints
- **Responsibilities**: Health check aggregation, system status reporting,
  database pool monitoring, filesystem health validation
- **Interactions**: Uses `HealthChecker` for system validation, coordinates
  multiple services for comprehensive health status

### dashboard_routers.py

- **Role**: Dashboard aggregation HTTP endpoints
- **Responsibilities**: System overview metrics, health summaries, real-time
  status endpoints
- **Interactions**: Uses `StatisticsService` for aggregated data, coordinates
  multiple services for dashboard views

---

## Service Layer (Business Logic)

_Orchestration and business rules, coordinates between API and data layers_

### camera_service.py

- **Role**: Camera lifecycle and health management business logic
- **Responsibilities**: Camera creation/updates with validation, health
  monitoring coordination, capture scheduling, connectivity management
- **Interactions**: Uses `CameraOperations` for database, calls
  `ImageCaptureService` for capture coordination, broadcasts events via database
  SSE

### video_service.py

- **Role**: Video metadata and generation coordination business logic
- **Responsibilities**: Video record management, FFmpeg coordination via utils,
  generation job queue management, file lifecycle management
- **Interactions**: Uses `VideoOperations` for database, calls `ffmpeg_utils`
  for rendering, coordinates with `VideoAutomationService` for automated
  generation

### video_automation_service.py

- **Role**: Automated video generation workflow business logic
- **Responsibilities**: Scheduling triggers (per-capture/milestone/scheduled),
  job queue prioritization, automation rule evaluation, throttling logic
- **Interactions**: Uses `VideoOperations` for job queue, calls `VideoService`
  for generation, monitors `TimelapseService` for trigger conditions

### timelapse_service.py

- **Role**: Timelapse entity lifecycle business logic
- **Responsibilities**: Entity creation/completion, statistics aggregation, day
  number calculations, auto-stop management, progress tracking
- **Interactions**: Uses `TimelapseOperations` for database, coordinates with
  `CameraService` for active timelapse assignment, provides data to
  `VideoAutomationService`

### image_service.py

- **Role**: Image metadata and serving business logic
- **Responsibilities**: Image metadata management, thumbnail coordination, file
  serving with fallbacks, image statistics calculations
- **Interactions**: Uses `ImageOperations` for database, calls `thumbnail_utils`
  for processing, coordinates with `CorruptionService` for quality data

### image_capture_service.py

- **Role**: RTSP capture coordination business logic
- **Responsibilities**: Capture workflow orchestration, corruption detection
  integration, retry logic, health status updates, thumbnail generation
  coordination
- **Interactions**: Uses `rtsp_utils` for capture, `CorruptionService` for
  quality analysis, `ImageService` for metadata, `thumbnail_utils` for
  processing

### corruption_service.py

- **Role**: Image quality analysis business logic
- **Responsibilities**: Quality scoring algorithms, degraded mode logic, audit
  trail management, camera health assessment, auto-discard decisions
- **Interactions**: Uses `CorruptionOperations` for database, coordinates with
  `CameraService` for health updates, provides quality data to
  `ImageCaptureService`

### settings_service.py

- **Role**: System configuration business logic
- **Responsibilities**: Settings validation, inheritance resolution, change
  propagation, timezone management, feature flag coordination
- **Interactions**: Uses `SettingsOperations` for database, provides
  configuration data to all other services, broadcasts configuration changes

### statistics_service.py

- **Role**: System-wide metrics aggregation business logic
- **Responsibilities**: Cross-service statistics compilation, health overview
  generation, performance metrics calculation, dashboard data preparation
- **Interactions**: Coordinates with all domain services to collect statistics,
  uses `StatisticsOperations` for complex queries, provides aggregated views

### log_service.py

- **Role**: Application logging business logic
- **Responsibilities**: Log aggregation, filtering, cleanup policies, log level
  management, audit trail maintenance, structured logging coordination
- **Interactions**: Uses `LogOperations` for database, receives log data from
  all services, provides filtered views for debugging, integrates with
  correlation ID system

---

## Infrastructure Layer (Cross-Cutting Concerns)

_Middleware, error handling, health monitoring, and database management_

### middleware/error_handling.py

- **Role**: Centralized error handling and correlation tracking
- **Responsibilities**: Exception catching and formatting, correlation ID
  generation and propagation, structured error logging, HTTP error response
  standardization
- **Interactions**: Intercepts all HTTP requests, coordinates with
  `StructuredLogger`, provides error context to all services

### middleware/logging.py

- **Role**: Request/response logging middleware
- **Responsibilities**: Request/response lifecycle logging, performance
  tracking, audit trail creation, log correlation management
- **Interactions**: Works with error handling middleware, feeds data to
  `LogService`, provides debugging context

### health/health_checker.py

- **Role**: System health monitoring coordination
- **Responsibilities**: Database connectivity validation, filesystem health
  checks, external dependency monitoring, service health aggregation
- **Interactions**: Uses all database pools for connectivity tests, coordinates
  with services for health status, provides data to health endpoints

### database/pool_manager.py

- **Role**: Enhanced database connection pool management
- **Responsibilities**: Pool lifecycle management, connection monitoring, pool
  metrics collection, connection health validation, pool configuration
  optimization
- **Interactions**: Manages async and sync database pools, provides metrics to
  monitoring systems, coordinates with health checks

### logging/structured_logger.py

- **Role**: Structured logging coordination
- **Responsibilities**: Log format standardization, correlation ID integration,
  log level management, structured data serialization
- **Interactions**: Used by all services and middleware, coordinates with
  external logging systems, provides debugging capabilities

---

## Data Access Layer (Database Operations)

_Pure database CRUD operations using composition pattern with psycopg3 pools_

### camera_operations.py

- **Role**: Camera table database operations
- **Responsibilities**: Camera CRUD, health status updates, connectivity
  tracking, automation settings management, corruption statistics updates
- **Interactions**: Receives database instance via dependency injection,
  provides data to `CameraService`, uses psycopg3 connection pools

### video_operations.py

- **Role**: Videos and video generation jobs table operations
- **Responsibilities**: Video metadata CRUD, generation job queue operations,
  file path management, video statistics queries, job status tracking
- **Interactions**: Receives database instance via dependency injection,
  provides data to `VideoService` and `VideoAutomationService`

### timelapse_operations.py

- **Role**: Timelapses table database operations
- **Responsibilities**: Timelapse entity CRUD, image count aggregation, day
  range calculations, auto-stop management, progress queries
- **Interactions**: Receives database instance via dependency injection,
  provides data to `TimelapseService`, supports entity-based architecture

### image_operations.py

- **Role**: Images table database operations
- **Responsibilities**: Image metadata CRUD, file path management, day number
  calculations, corruption score storage, thumbnail path tracking
- **Interactions**: Receives database instance via dependency injection,
  provides data to `ImageService`, supports LATERAL join queries for latest
  images

### corruption_operations.py

- **Role**: Corruption logs table database operations
- **Responsibilities**: Corruption audit trail CRUD, score aggregation, degraded
  mode tracking, quality statistics queries, health assessments
- **Interactions**: Receives database instance via dependency injection,
  provides data to `CorruptionService`, maintains detailed quality audit trail

### settings_operations.py

- **Role**: Settings table database operations
- **Responsibilities**: Configuration CRUD, inheritance resolution queries,
  validation support, bulk updates, feature flag management
- **Interactions**: Receives database instance via dependency injection,
  provides configuration data to `SettingsService` and all other services

### statistics_operations.py

- **Role**: Cross-table aggregation database operations
- **Responsibilities**: Complex statistical queries, performance metrics
  calculation, health overview queries, dashboard data aggregation
- **Interactions**: Receives database instance via dependency injection,
  performs complex JOINs across multiple tables, provides data to
  `StatisticsService`

### log_operations.py

- **Role**: Logs table database operations
- **Responsibilities**: Log entry CRUD, filtering queries, cleanup operations,
  audit trail maintenance, performance log analysis
- **Interactions**: Receives database instance via dependency injection,
  provides data to `LogService`, supports log rotation and cleanup

---

## Utility Layer (Pure Functions)

_Stateless helper functions with no external dependencies or side effects_

### thumbnail_utils.py

- **Role**: Image processing utilities
- **Responsibilities**: Thumbnail generation using Pillow, multiple size
  variants, quality optimization, format conversion, error handling
- **Interactions**: Called by `ImageCaptureService` and `ImageService`, operates
  on image files, returns processed image data and metadata

### ffmpeg_utils.py

- **Role**: Video rendering utilities
- **Responsibilities**: FFmpeg command generation, overlay creation, quality
  settings management, progress tracking, error handling
- **Interactions**: Called by `VideoService` for actual video rendering,
  operates on image sequences, returns video files and metadata

### rtsp_utils.py

- **Role**: RTSP stream capture utilities
- **Responsibilities**: OpenCV RTSP connection, frame capture, connection
  testing, timeout handling, stream validation
- **Interactions**: Called by `ImageCaptureService` for actual image capture,
  handles camera connectivity, returns image data

### timezone_utils.py

- **Role**: Timezone-aware datetime utilities
- **Responsibilities**: Database timezone integration, timestamp formatting,
  timezone validation, sync/async datetime helpers
- **Interactions**: Used by all services for consistent datetime handling,
  integrates with `SettingsService` for timezone configuration

### time_utils.py

- **Role**: Time calculation and formatting utilities
- **Responsibilities**: Relative time formatting, countdown calculations, time
  window validation, duration calculations
- **Interactions**: Used by frontend via API for consistent time display,
  supports real-time countdown features

### file_utils.py

- **Role**: File system operation utilities
- **Responsibilities**: Path validation, directory creation, file serving,
  cleanup operations, security validation, health check file operations
- **Interactions**: Used by multiple services for file operations, ensures
  consistent path handling and security, supports health monitoring

### error_utils.py

- **Role**: Error handling and formatting utilities
- **Responsibilities**: Exception formatting, error code standardization, error
  message templating, debugging context extraction
- **Interactions**: Used by middleware and services for consistent error
  handling, supports correlation ID tracking

### health_utils.py

- **Role**: Health check utilities
- **Responsibilities**: Service availability testing, dependency validation,
  performance metric calculation, status aggregation algorithms
- **Interactions**: Used by `HealthChecker` for validation logic, provides
  reusable health check patterns

### pool_utils.py

- **Role**: Database pool monitoring utilities
- **Responsibilities**: Pool metric calculation, connection lifecycle tracking,
  performance analysis, pool optimization recommendations
- **Interactions**: Used by `PoolManager` for monitoring, provides pool health
  insights, supports performance optimization

---

## Integration Layer (Orchestration)

_System coordination and external integrations_

### worker.py

- **Role**: Background process orchestration
- **Responsibilities**: Scheduled image capture coordination, health monitoring,
  service coordination, graceful shutdown, signal handling
- **Interactions**: Uses multiple services (`CameraService`,
  `ImageCaptureService`, `VideoAutomationService`), runs independently of API,
  maintains system operation

### corruption_detection/

- **Role**: Computer vision integration
- **Responsibilities**: Fast/heavy detection algorithms, scoring calculation,
  pattern recognition, performance optimization
- **Interactions**: Called by `CorruptionService`, integrates with OpenCV and
  other CV libraries, provides quality analysis

### weather/

- **Role**: External weather API integration
- **Responsibilities**: OpenWeather API integration, sunrise/sunset
  calculations, weather data caching, location management
- **Interactions**: Integrates with capture scheduling, provides environmental
  context, supports time window calculations

---

## Architecture Principles

### **Dependency Flow**

```
API Layer → Service Layer → Data Access Layer → Database
     ↓           ↓              ↓
Utility Layer ← Utility Layer ← Utility Layer
```

### **Composition Pattern**

- All services receive database instances via dependency injection
- No mixin inheritance, clean type safety
- Services own their database operations classes
- Clear separation between business logic and data access

### **Event Broadcasting**

- Services broadcast events via database SSE system
- Real-time updates flow from worker through services to frontend
- Centralized event management through single SSE connection

### **Settings Inheritance**

- Global settings → Camera settings → Timelapse settings
- Resolution happens in service layer
- Database stores all levels, services resolve effective values

### **Error Handling**

- Services handle business logic errors
- Operations handle database errors
- Utilities handle implementation errors
- Consistent error propagation up the stack
- Correlation IDs for request tracing
- Structured error logging with context

### **Health Monitoring**

- Proactive health checks for all system dependencies
- Database pool health monitoring and metrics
- Filesystem accessibility validation
- External service dependency tracking
- Health endpoint aggregation for monitoring systems

### **Database Pool Management**

- Enhanced connection pooling with monitoring
- Pool metrics collection for performance analysis
- Connection lifecycle tracking and optimization
- Health-aware connection management
- Graceful degradation during pool exhaustion
