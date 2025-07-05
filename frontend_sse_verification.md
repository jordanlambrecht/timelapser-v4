# Frontend SSE Integration Verification

## ✅ Correctly Configured Components

### 1. **SSE Context** (`/src/contexts/sse-context.tsx`)
- ✅ Connects to `/api/events` endpoint
- ✅ Handles reconnection with exponential backoff
- ✅ Provides subscription mechanism for components
- ✅ Parses JSON events correctly

### 2. **SSE Hooks** (`/src/hooks/use-camera-sse.ts`)
- ✅ Expects correct event types: `image_captured`, `camera_status_changed`, `timelapse_status_changed`
- ✅ Expects correct data structure: `event.type`, `event.data.camera_id`
- ✅ Provides camera-specific and dashboard-wide event subscriptions

### 3. **Next.js SSE Proxy** (`/src/app/api/events/route.ts`)
- ✅ Connects to FastAPI SSE endpoint
- ✅ Streams events to frontend clients
- ✅ Handles connection errors and heartbeats
- ✅ No HTTP POST endpoint (correct!)

### 4. **Component Integration**
- ✅ `SSEProvider` wrapped around app in layout.tsx
- ✅ Camera components use `useCameraSSE` hook
- ✅ No direct EventSource connections (follows centralized pattern)

## ❌ Critical Integration Issue Found

### Problem: Next.js API Routes Using Old Event Emitter

**13 API routes** are still using `eventEmitter.emit()` instead of the database-driven approach:

```typescript
// ❌ WRONG - Old pattern that won't reach frontend
eventEmitter.emit({
  type: "camera_status_changed",
  data: { camera_id: responseData.camera_id, status: "active" },
  timestamp: new Date().toISOString(),
})
```

These events are emitted to the old event emitter system, but:
- Frontend SSE connects to `/api/events` which streams from database
- These events never reach the database
- **Result: Frontend won't receive these events!**

### Affected Routes:
1. `/api/cameras/route.ts`
2. `/api/cameras/[id]/route.ts`
3. `/api/cameras/[id]/capture/route.ts`
4. `/api/cameras/[id]/capture-now/route.ts`
5. `/api/timelapses/route.ts`
6. `/api/timelapses/[id]/route.ts`
7. `/api/timelapses/[id]/start/route.ts`
8. `/api/timelapses/[id]/pause/route.ts`
9. `/api/timelapses/[id]/complete/route.ts`
10. `/api/timelapses/new/route.ts`
11. `/api/videos/route.ts`
12. `/api/corruption/cameras/[id]/reset-degraded/route.ts`
13. `/api/logs/cleanup/route.ts`

## 🔧 Required Fix

These Next.js API routes need to be updated to **remove** the `eventEmitter.emit()` calls because:

1. **Backend already creates SSE events** - When the FastAPI endpoints are called, they create database SSE events
2. **Double events would occur** - If Next.js also created events, there would be duplicates
3. **Next.js routes are just proxies** - They should only forward requests to FastAPI

### Solution:

Remove all `eventEmitter.emit()` calls from Next.js API routes. The events are already created by the backend services when they process the requests.

Example fix:
```typescript
// ✅ CORRECT - Remove event emission, let backend handle it
export async function POST(request: Request, { params }: Params) {
  const response = await fastApiClient(`/api/timelapses/${params.id}/start`, {
    method: "POST",
  })
  
  // Remove this block - backend already creates the event
  // eventEmitter.emit({ ... })
  
  return response
}
```

## Event Flow Summary

### Current (Broken) Flow:
1. Frontend → Next.js API route → FastAPI
2. FastAPI creates database SSE event ✅
3. Next.js route ALSO emits to eventEmitter ❌
4. Frontend SSE reads from database (misses eventEmitter events)

### Correct Flow:
1. Frontend → Next.js API route → FastAPI
2. FastAPI creates database SSE event ✅
3. Frontend SSE reads from database ✅
4. Events delivered correctly!

## Verification After Fix

To verify the fix works:
1. Remove `eventEmitter.emit()` calls from all 13 routes
2. Start services
3. Test an action (e.g., start timelapse)
4. Check browser console for SSE events
5. Verify UI updates in real-time

The frontend SSE infrastructure is correctly set up - it just needs the Next.js routes cleaned up to remove the redundant event emissions.