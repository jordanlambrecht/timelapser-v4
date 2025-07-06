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

## Settings Context Architecture

**CRITICAL**: The global settings context is the single source of truth for ALL application settings. Never use page-specific hooks or prop drilling for settings.

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

1. **`useSettings()`** - Complete settings access with all properties and setters
2. **`useCaptureSettings()`** - Lightweight hook for core settings (interval, timezone)
3. **`useSettingsActions()`** - Actions only (save, update, refetch)
4. **`useWeatherSettings()`** - Weather-specific settings subset

### Settings Categories

- **Core**: captureInterval, timezone, generateThumbnails, imageCaptureType
- **Weather**: weatherEnabled, sunriseSunsetEnabled, latitude, longitude, openWeatherApiKey
- **Logging**: logRetentionDays, maxLogFileSize, enableDebugLogging, logLevel, etc.
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

## Real-Time Event System (SSE)

**Architecture**: PostgreSQL LISTEN/NOTIFY → FastAPI SSE → Next.js Proxy → Frontend

### Event-Driven SSE Implementation

The system uses PostgreSQL's native LISTEN/NOTIFY for truly event-driven real-time updates:

1. **Service Layer** - Creates events in `sse_events` table when actions occur
2. **PostgreSQL Trigger** - Automatically sends NOTIFY when events inserted
3. **SSE Router** - Uses psycopg3 async LISTEN to wait for notifications
4. **Frontend Proxy** - Next.js API route streams to client
5. **Centralized Context** - Single SSE connection shared across all components

### Key Benefits

- **Zero Polling** - No constant database queries or `asyncio.sleep()` loops
- **Instant Updates** - Events delivered immediately via PostgreSQL notifications
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
await self.sse_ops.create_event(
    event_type="timelapse_started",
    event_data={"camera_id": camera_id, "timelapse_id": timelapse_id},
    priority="normal",
    source="api"
)
```

[... rest of the existing content remains unchanged ...]