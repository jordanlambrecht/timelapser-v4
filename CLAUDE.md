# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

Timelapser v4 is a comprehensive time-lapse automation platform designed for
RTSP camera ecosystems. The system automatically captures images from multiple
camera feeds at predefined intervals and generates time-lapse videos using
FFmpeg with customizable settings.

**Architecture**: Next.js (3000) ↔ FastAPI (8000) ↔ PostgreSQL ↔ Python Worker
**Package Manager**: pnpm (not npm) **Database**: PostgreSQL (Neon:
muddy-math-60649735)

## Development Specifications

- We use python3 not python
- We are using psycopg3 not psycopg2
- We are using sqlalchemy, pydantic, fastapi

## Settings Context Architecture

**CRITICAL**: The global settings context is the single source of truth for ALL
application settings. Never use page-specific hooks or prop drilling for
settings.

### Core Implementation

```typescript
// ✅ CORRECT - Use global context directly
const { captureInterval, timezone, saving, updateSetting } = useSettings()

// ✅ CORRECT - Component receives no props
<CaptureSettingsCard />

// ❌ WRONG - Prop drilling
<CaptureSettingsCard captureInterval={...} setCaptureInterval={...} />
```

### Available Hooks

1. **`useSettings()`** - Complete settings access with all properties and
   setters
2. **`useCaptureSettings()`** - Lightweight hook for core settings (interval,
   timezone)
3. **`useSettingsActions()`** - Actions only (save, update, refetch)
4. **`useWeatherSettings()`** - Weather-specific settings subset

### Settings Categories

- **Core**: captureInterval, timezone, generateThumbnails, imageCaptureType
- **Weather**: weatherEnabled, sunriseSunsetEnabled, latitude, longitude,
  openWeatherApiKey
- **Logging**: logRetentionDays, maxLogFileSize, enableDebugLogging, logLevel,
  etc.
- **Corruption**: corruptionDetectionEnabled, corruptionScoreThreshold, etc.

### Key Features

- **Automatic caching** - 5-minute TTL with force refresh capability
- **Toast notifications** - Built-in save success/error feedback
- **Type safety** - Complete TypeScript interfaces
- **Real-time updates** - All components automatically reflect changes
- **Bulk operations** - `saveAllSettings()` handles all categories
- **Change detection** - Only modified settings are saved
- **Error handling** - Graceful fallbacks and user feedback

### Architecture Rules

1. **ALL settings components must use context directly** - No props
2. **Wrap app with `<SettingsProvider>`** - Required for context access
3. **Use appropriate hook for use case** - Don't over-fetch with `useSettings()`
4. **Settings page coordinates saves** - Individual components don't save
5. **Always handle loading/saving states** - Provide user feedback

## Development Commands

### ALL

```bash
./start-services.sh                                   # Start all services for both frontend and backend with health monitoring
```

### Frontend (Next.js)

```bash
pnpm dev              # Start Next.js dev server with Turbopack
pnpm build            # Build production bundle
pnpm start            # Start production server
pnpm lint             # Run ESLint
```

### Backend (FastAPI + Worker)

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000    # FastAPI dev server
python worker.py                                       # Background worker
checks
```

### Database

```bash
cd backend
alembic upgrade head                    # Apply migrations
alembic revision --autogenerate -m ""   # Generate migration
```

## Alembic Migration Notes

- In order to migrate alembic, You must start a venv in ./backend, cd to the
  backend,and run alembic upgrade head from there.

## Real-Time Event System (SSE)

**Architecture**: PostgreSQL LISTEN/NOTIFY → FastAPI SSE → Next.js Proxy →
Frontend

### Event-Driven SSE Implementation

The system uses PostgreSQL's native LISTEN/NOTIFY for truly event-driven
real-time updates:

1. **Service Layer** - Creates events in `sse_events` table when actions occur
2. **PostgreSQL Trigger** - Automatically sends NOTIFY when events inserted
3. **SSE Router** - Uses psycopg3 async LISTEN to wait for notifications
4. **Frontend Proxy** - Next.js API route streams to client
5. **Centralized Context** - Single SSE connection shared across all components

### Key Benefits

- **Zero Polling** - No constant database queries or `asyncio.sleep()` loops
- **Instant Updates** - Events delivered immediately via PostgreSQL
  notifications
- **Zero Load When Idle** - No database activity when no events occur
- **Highly Scalable** - PostgreSQL handles notification distribution efficiently

### Critical Files

- `backend/app/routers/sse_routers.py` - LISTEN/NOTIFY SSE endpoint
- `backend/alembic/versions/019_create_weather_table.py` - Weather data table
- `backend/app/database/sse_events_operations.py` - Event database operations
- `src/contexts/sse-context.tsx` - Frontend centralized connection
- `src/app/api/events/route.ts` - Next.js SSE proxy

### Service Integration

All service methods must create SSE events when actions occur:

```python
# ✅ CORRECT - Composition pattern
class VideoOperations:
    def __init__(self, db: AsyncDatabase | SyncDatabase):
        self.db = db

    def get_videos(self):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM videos")
                return cur.fetchall()

# Service Layer
class VideoService:
    def __init__(self, db: AsyncDatabase):
        self.video_ops = VideoOperations(db)
```

### Dual Database Pattern

- **AsyncDatabase**: FastAPI endpoints requiring concurrent request handling
- **SyncDatabase**: Worker processes requiring reliable RTSP capture and file
  I/O
- **Connection Pooling**: psycopg3 pools for both patterns

### Entity-Based Timelapse Architecture

Timelapses are discrete entities, NOT status changes:

- Each "Start A New Timelapse" creates a new database record
- `cameras.active_timelapse_id` tracks current recording session
- Completed timelapses preserved as historical records
- Dual statistics: "Total: 1,250, Current: 47 images"

### Real-time Event System (SSE)

**CRITICAL**: Use centralized SSE system to prevent connection spam.

```typescript
// ✅ CORRECT - Use centralized hooks
const { cameras } = useRealtimeCameras()
useCameraSSE(cameraId, {
  onImageCaptured: (data) => {
    /* handle event */
  },
})

// ❌ WRONG - Creates individual connections
const eventSource = new EventSource("/api/events")
```

### Timezone-Aware Time System

**NEVER** use browser local time. All calculations use database-configured
timezone.

```typescript
// ✅ CORRECT
const { timezone } = useCaptureSettings()
const { nextCaptureRelative } = useCameraCountdown(camera.id)

// ❌ WRONG
const now = new Date() // Browser local time
```

### Thumbnail System

Separate folder structure with cascading fallbacks:

```
data/cameras/camera-{id}/
├── images/YYYY-MM-DD/          # Full resolution
├── thumbnails/YYYY-MM-DD/      # 200×150 for dashboard
└── small/YYYY-MM-DD/           # 800×600 medium quality
```

## Critical Implementation Rules

### Database Operations

1. **Always use composition pattern** - No mixin inheritance
2. **Cursor-based SQL execution** - `with conn.cursor() as cur:`
3. **Query-based image retrieval** - Use LATERAL joins, no FK dependencies
4. **psycopg3 connection pooling** - Both async/sync pools required

### Settings & State Management

1. **Always use `useCaptureSettings()` hook** - Never fetch settings directly in
   components
2. **Settings context provides single source of truth** - Automatic caching with
   5-minute TTL
3. **All settings-dependent components must be wrapped** with
   `<SettingsProvider>`

### Path Management

1. **NEVER use hardcoded absolute paths** - Use config-driven paths from
   `settings.data_directory`
2. **Store relative paths in database** - Never store absolute paths
3. **Use `pathlib.Path` for cross-platform compatibility**
4. **Avoid using os.paths directly and rely on our config settings
   base_directory = settings.data_directory and our file_helpers.py**

### Video Generation Settings

1. **Dual mode system**:
   - `video_generation_mode`: Controls FPS calculation ('standard', 'target')
   - `video_automation_mode`: Controls when videos are generated ('manual',
     'per_capture', 'scheduled', 'milestone')
2. **Settings inheritance**: Timelapse settings override camera defaults
3. **Always use `get_effective_video_settings()`** for calculations

### Corruption Detection System

1. **NEVER bypass corruption integration** - All captures go through
   `WorkerCorruptionIntegration.evaluate_with_retry()`
2. **Per-camera heavy detection settings** - Respect
   `corruption_detection_heavy` flag
3. **Database logging required** - All evaluations logged to `corruption_logs`
   table
4. **SSE events for corruption** - Real-time UI updates

### File Structure & Organization

#### Backend Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI application entry
│   ├── config.py                # Centralized configuration
│   ├── database/                # Modular database operations
│   │   ├── core.py             # Base database classes
│   │   ├── *_operations.py     # Entity-specific operations
│   ├── models/                  # Pydantic models
│   ├── routers/                 # FastAPI route handlers
│   ├── services/                # Business logic layer
│   └── utils/                   # Shared utilities
├── worker.py                    # Background worker process
└── alembic/                     # Database migrations
```

#### Frontend Structure

```
src/
├── app/                         # Next.js App Router
│   ├── api/                    # API routes (proxy to FastAPI)
│   └── pages/                  # Application pages
├── components/                  # React components
│   ├── ui/                     # Design system (Radix UI)
│   └── feature components      # Business logic components
├── contexts/                    # React Context providers
├── hooks/                       # Custom React hooks
├── lib/                         # Utilities & services
└── types/                       # TypeScript definitions
```

## Common Patterns

### API Development Chain

Complete chain required for new endpoints:

1. Database method in `*_operations.py`
2. Service method in `*_service.py`
3. Backend router in `*_routers.py`
4. Frontend proxy in `/src/app/api/`

### Component Development

```typescript
// Always use existing hooks for data fetching
const { cameras, isLoading } = useRealtimeCameras()
const { timezone } = useCaptureSettings()

// Follow established patterns for new components
const NewComponent = () => {
  // 1. Use existing hooks for data
  // 2. Handle loading states
  // 3. Use toast notifications for feedback
  // 4. Follow timezone-aware time display patterns
}
```

### SSE Event Structure

```typescript
// ✅ CORRECT event structure
{
  type: "image_captured",
  data: {
    camera_id: number,
    image_count: number,
    timelapse_id: number
  },
  timestamp: string
}
```

## Environment Variables

### Backend (.env)

```bash
DATABASE_URL=postgresql://user:pass@host/db
CORS_ORIGINS=http://localhost:3000,http://localhost:3001  # Comma-separated
ENVIRONMENT=development
```

### Frontend

```bash
NEXT_PUBLIC_FASTAPI_URL=http://localhost:8000
```

## Key Dependencies

### Backend

- FastAPI 0.115.12
- psycopg[binary,pool] 3.2.9 (CRITICAL: psycopg3 with pools)
- Pydantic 2.11.5
- OpenCV 4.11.0.86 (RTSP capture)
- Pillow 11.2.1 (thumbnail generation)

### Frontend

- Next.js 15.3.3
- React 19.1.0
- Radix UI (component primitives)
- Tailwind CSS 4.1.10
- TypeScript 5.8.3

## Health Checks & Debugging

### Service Health

```bash
curl http://localhost:3000/api/health    # Frontend + Backend
curl http://localhost:8000/api/health    # Backend only
./start-services.sh                      # Coordinated startup
```

### SSE Connection

Browser console should show: "✅ SSE connected successfully"

### Database

```bash
psql $DATABASE_URL -c "SELECT * FROM cameras WHERE health_status = 'offline';"
```

## Anti-Patterns to Avoid

1. **Individual SSE connections** - Creates 79+ connection spam
2. **FK-based latest image tracking** - Use LATERAL joins instead
3. **Browser timezone calculations** - Always use database timezone
4. **Status-based timelapses** - Use entity-based architecture
5. **Mixing thumbnails with full images** - Separate folder structure required
6. **Hardcoded paths** - Use config-driven path management
7. **Bypassing corruption detection** - All captures must go through pipeline

## Production Considerations

- **File permissions**: Use 0o644 for files, 0o755 for directories
- **Connection monitoring**: Monitor psycopg3 pool utilization
- **Backup strategy**: Separate database and file system backups
- **Environment-specific configuration**: Use appropriate CORS_ORIGINS and
  DATABASE_URL
- **Health monitoring**: Monitor disk space, memory usage, and worker status

<!--

title: Python Standards
description: Prompts Copilot to compare the codebase to the expected standards
the user has. tags: [refactor, optimize, cleanup, maintainability, python]

---

-->

# Python Code Writing Expectations

These are the personal preferences I have for writing python code. Please
heavily scrutinize and check the entire codebase, file by file, to ensure that
these standards are met:

As an expert Python developer, your primary objective is to demonstrate your
expertise in creating clean, readable, and well-documented code with a focus on
modularity and pythonic principles.

- Please check entire codebase and file tree before making complex decisions. If
  you are unsure what a component or import does, please ask before proceeding.
- I am a big fan of
  '[DRY](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself)' and
  '[KISS](https://en.wikipedia.org/wiki/KISS_principle)' principles. Please keep
  code as simple as possible and avoid unnecessary complexity.
- I am also a big fan of
  '[Seperation of Concerns](https://en.wikipedia.org/wiki/Separation_of_concerns)'.
  Please keep code modular and avoid large monolithic files. If there is an
  agnostic function that we are writing that can be used in multiple places,
  please move it to a separate file and import it where needed.
- If you are writing a new component, please ensure that it is reusable and
  modular. Avoid hardcoding values and instead use props to pass in data.
- For larger projects, we should have a centralized config file where variable
  inputs can be easily swapped out rather than hardcoding values in multiple
  places. This will make it easier to maintain and update the codebase in the
  future. This is the
  [Single Source of Truth](https://en.wikipedia.org/wiki/Single_source_of_truth).
- This principle is extremely important. If you generate code, at the end of the
  response, check back over the code you just wrote. See if you notice any bugs,
  or if there is a significantly simpler or better solution to the problem, such
  as using a relevant library. If you notice anything you missed, write a new
  section entitled "Review" in which you point out what you missed and correct
  the code. If you can't find anything you missed, don't write a "Review"
  section - instead, completely leave out the "Review" section and just stop
  generating code.
- code should be fully defined and ready for the user to test with all features
  implemented.
  - Do not include line item comments that say things such as '<-- changed this
    line' or '<-- added this line' that highlight changes you made to the code
- Write clear and maintainable code.
- Comment complex logic.
- If writing a large number of documents, at the end please provide a list of
  mkdir and touch commands to help expediate the process of creating the folders
  and files.
- Assume that the end goal for all projects is an open-source mass release.
  Codebases should not be written specifically to run on my computer, and a
  wider audience should always be considered in code design choices.
- if a better approach is viable but undiscussed, always recommend the better
  approach as an alternative.
- Do not write any logic that impeeds, manipulates, or affects SIGTERM
- Any code that affects SIGINT should have a clear shutdown path if needed.
  Graceful shutdown is always preferred, but if graceful shutdown fails it
  should be terminated

## Python Specific

- Use f-strings for string formatting
- Double check for and avoid circular imports
- Be sure to follow Python's official style guide (PEP8)
- Use type hints for function parameters and return types.
- As you proceed with the project, make use of libraries such as os, sys, shutl,
  and any other libraries found in your local requirements.txt file as needed to
  complete your assignment.
- Use shebangs at the top of your Python files to specify the interpreter, e.g.,
  `#!/usr/bin/env python3`.
- Add a single-line comment at the top of each file that denotes the file's
  relative path and filename.
- Log outputs should contain emojis and use log levels (DEBUG, INFO, WARNING,
  ERROR)
- Config files should be yaml
- Unless otherwise stated, there should be one entry point file: `main.py`. It
  should be kept simple and short.
- Typically, things should be divided (besides main.py) into three folder:
  src/core, src/utils, src/services. This is, of course, just a baseline and
  every project will have different needs
- Files should be short and maintainable. Code should be split into different
  files when it makes sense
- Add async/await for I/O operations
- Avoid creating overly tight coupling
- Use pathlib instead of os.path
- Create Type hints We want to typically implement dependency injections rather
  than global variers and want our config constants closer to a global wiki that
  you can publish to and request definitions from.Dependency injections is a
  solution for managing global state and scope without the insanity of
  apparently undeclared variables showing up with crucial info or functionality.

The context of a single class only has access to what it requests and those
types are clearly listed in the constructor (or properties). The available
implementations are also typically registered centrally so you can find the set
of choices.

## Deterimination

If there is a logical reason for not following any of the above requirements,
you are not obligated to comply. If you choose to not follow one of the rules,
simply mention that you recognize where the rule should be applied but you are
not doing it because of XYZ reason.

### Dataclasses vs. Dictionaries

When to use Dicts:

- If a dictionary will do the job, then it is usually the better choice, though
  in some cases using a dataclass can significantly improve readability.
- Use dicts when the "keys" (or attribute names) are meant to be code.
- a dict for when you make one object, and you use it for looking things up.
  "Map" really does describes the job better
- custom init method
- custom new method
- various patterns that use inheritance
- if you want different names for the attributes, including implementing
  encapsulation

When to use Dataclasses: -If you need "methods", then a class or dataclass is
likely to be the better option.

- a dataclass (or some kind of class) when you're gonna make a bunch of objects.
  Accessing attributes with a dot really is better than brackets

When to use pydantic:

- Descrecionary, but remain concistant should it be implemented

## Responses

- Respond simulating an experienced Python programmer with a meticulous approach
  to writing code, and your responses should reflect your expertise and
  attention to detail.
- Your responses should be concise, logical, and to-the-point, showcasing your
  proficiency in Python development and adhering to best practices. Provide
  completely implemented code for each class, function, or program section, and
  use text-based flow diagrams when necessary to describe the process and
  algorithm behavior, ensuring you use the correct design patterns.
- Avoid being overly verbose with your responses

### When to Use Each Pattern

**Use Pydantic models directly when:**

Returning structured data (objects, lists of objects) Complex response schemas
Need strong typing for frontend

**Use ResponseFormatter when:**

Simple success/error messages Operations that don't return data Standardized
message responses

## When asked to Refactor Code

Please refactor the following `{{language_name}}` code.

**Primary Goals for Refactoring:**

- Improve overall readability and maintainability.
- Enhance performance if obvious bottlenecks exist.
- Ensure adherence to common best practices and idiomatic patterns for
  `{{language_name}}`.
- Simplify complex logic or structures.

**Specific Instructions/Constraints:**

- Focus on: `{{specific_focus_area_e.g., "reducing nesting depth"}}`
- Ensure that:
  `{{specific_requirement_e.g., "all public functions have JSDoc comments"}}`
- Avoid:
  `{{specific_thing_to_avoid_e.g., "using third-party libraries for this task"}}`
- Please check entire codebase and file tree before making decisions. If you are
  unsure what a component or import does, please ask before proceeding.
- Determine if the file needs to be refactored before proceeding. If it is
  already optimal, do not refactor.
- My general coding instructions (from `general_copilot_instructions.md`) should
  also be followed.
- - **Clarity and Readability:** Break complex logic into smaller,
    self-contained functions with clear, descriptive names.
- - **Modularity:** Ensure code is structured for reusability and separation of
    concerns. Follow the single responsibility principle.
- - **Consistency:** Apply consistent formatting and naming conventions
    throughout the code. Avoid using trailing semicolons unless required by the
    language.
- - **Performance Improvements:** Identify and implement optimizations to
    enhance performance without overcomplicating the code.
- - **Best Practices:** Adhere to industry and language best practices, avoiding
    anti-patterns and deprecated features.
- - **Innovative Solutions:** Suggest more modern or efficient approaches to
    achieve functionality while maintaining simplicity.
- - **Minimalism:** Eliminate redundant, unused, or overly complex code. Focus
    on simplicity and maintainability.
- - **Comments and Documentation:** Ensure the refactored code is
    self-explanatory. Add comments or documentation only where absolutely
    necessary for clarity.

```{{language_name_lowercase}}
{{paste_or_select_code_to_refactor_here}}
```

**Expected Output:**

1.  The complete refactored code block.
2.  A concise, bullet-point lists detailing:
    - The key changes made.
    - The reasoning behind each significant change, especially in relation to
      the stated goals.
    - Any trade-offs considered, if applicable.
    - A list of errors you found prefixed with either a checkmark emoji or a red
      cross emoji representing if you were able to fix that error.
3.  If the code is already optimal, please state that no refactoring is needed
    and explain why.

```


FastAPI Router Rules for Timelapser Backend
Use Dependency Injection for Services

Always inject service dependencies (e.g., VideoServiceDep) into endpoints, not raw database connections.
Entity Existence Validation

Use validate_entity_exists from router_helpers to check if an entity exists before performing actions (e.g., before updating, deleting, or returning an entity).
Pass the appropriate service method (not direct DB access) to validate_entity_exists.
Standardized Error Handling

Decorate all endpoints with @handle_exceptions("operation description") for consistent error logging and HTTP error responses.
Standardized Response Formatting

Use ResponseFormatter.success() and ResponseFormatter.error() (or create_success_response/create_error_response) for all API responses.
Avoid returning raw dicts or Pydantic models directly unless required by FastAPI for OpenAPI docs.
Business Logic Separation

Move all business logic (e.g., settings inheritance, validation, filename cleaning) to helpers or service classes (e.g., VideoSettingsHelper, FileHelpers).
Routers should only orchestrate calls and handle HTTP-specific logic.
File and Path Handling

Use helpers from file_helpers.py for all file path validation, file serving, and filename cleaning.
Never manipulate file paths or serve files directly in the router.
Consistent Use of Constants

Use constants (e.g., VIDEO_STATUSES, DEFAULT_FPS, VIDEO_QUALITIES) from your constants.py for all validation and default values.
OpenAPI and Pydantic Models

Always use Pydantic models for request bodies and response models for OpenAPI documentation and validation.
Error and Logging Middleware

Register error handling and request logging middleware globally in your FastAPI app (not in routers).
Do not handle logging or error formatting manually in routers.
No Direct Database Access in Routers

Routers should never access the database directly; always go through a service or manager layer.
Keep Routers Thin

Routers should only:
Parse/validate input
Call service/helper methods
Format and return responses
Consistent Naming and Structure

Use consistent naming for endpoints, parameters, and response fields across all routers.
```
