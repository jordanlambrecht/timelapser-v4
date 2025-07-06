# Timelapser V4: Video Automation & Weather Integration Implementation Plan

## Overview

This document outlines the implementation of the logic behind rendering the
actual timelapse videos:

1. **Automated Timelapse Video Construction** - Multiple trigger modes for
   automated video generation

Follow the established AI-CONTEXT architectural patterns: entity-based
timelapses, settings inheritance, timezone-aware calculations, and psycopg3
connection pooling.

🎯 Core Design Principles Video Automation Modes:

Per-Capture: Generate after each image (with throttling) Scheduled: Time-based
triggers (daily/weekly/custom) Milestone: Trigger at image count thresholds
(100, 500, 1000) Manual: Existing user-initiated generation

🏗️ Architectural Compliance The plan strictly follows your AI-CONTEXT laws:

✅ Entity-based timelapses - Respects active_timelapse_id relationships ✅
Settings inheritance - Camera defaults → timelapse overrides pattern ✅
Timezone-aware - All calculations use useCaptureSettings() hook ✅ psycopg3
pools - Async for FastAPI, sync for worker processes ✅ SSE events - Real-time
updates for automation and weather

## 🎬 Feature 1: Automated Video Construction

### Current State Analysis

The existing system mentions generation modes in documentation but lacks
comprehensive automation. Current video generation is primarily manual with
basic FFmpeg integration.

### Proposed Automation Modes

#### 1. Manual Mode (Current)

- **Trigger**: User-initiated only
- **Use Case**: Full user control, on-demand generation
- **Implementation**: No changes to existing functionality

#### 2. Per-Capture Mode

- **Trigger**: After each successful image capture
- **Throttling**: Max 1 video per 5 minutes to prevent system overload
- **Priority**: Low queue priority
- **Use Case**: Always-current timelapses for monitoring

#### 3. Scheduled Mode (Batch)

- **Trigger**: Time-based using APScheduler
- **Options**: Hourly, Daily, weekly, etc
- **Timezone**: Uses database timezone setting (AI-CONTEXT compliant)
- **Use Case**: Regular daily/weekly summaries

#### 4. Milestone Mode

- **Trigger**: After reaching specific image counts (100, 500, 1000, etc.)
- **Configuration**: Multiple thresholds per timelapse
- **Reset Behavior**: Cumulative or reset count options
- **Use Case**: Progress milestones, project checkpoints

### Video Generation Types

#### Continuous Timelapses

- **Content**: All available images from timelapse start
- **Update Strategy**: Regenerate entire video with new images
- **Performance**: Optimized for incremental additions

#### Daily Timelapses

- **Content**: Images from specific day only
- **Generation**: Automatic at day end or manual
- **Use Case**: Daily progress summaries

#### Range Timelapses

- **Content**: User-defined date range
- **Trigger**: Manual only
- **Use Case**: Custom period summaries

#### Recent Timelapses

- **Content**: Last N images or last N days
- **Rolling Window**: Maintains fixed duration
- **Use Case**: "Last 24 hours" summaries

## 📊 Database Schema Changes

### Video Automation Tables

```sql
-- Video generation automation settings
ALTER TABLE cameras ADD COLUMN video_generation_mode VARCHAR(20) DEFAULT 'manual';
-- Options: 'manual', 'per_capture', 'scheduled', 'milestone'

ALTER TABLE cameras ADD COLUMN generation_schedule JSONB;
-- Example: {"type": "daily", "time": "18:00", "timezone": "America/Chicago"}

ALTER TABLE cameras ADD COLUMN milestone_config JSONB;
-- Example: {"thresholds": [100, 500, 1000], "enabled": true}

-- Timelapse inheritance (AI-CONTEXT pattern)
ALTER TABLE timelapses ADD COLUMN video_generation_mode VARCHAR(20);
ALTER TABLE timelapses ADD COLUMN generation_schedule JSONB;
ALTER TABLE timelapses ADD COLUMN milestone_config JSONB;

-- Video generation job queue
CREATE TABLE video_generation_jobs (
    id SERIAL PRIMARY KEY,
    timelapse_id INTEGER REFERENCES timelapses(id) ON DELETE CASCADE,
    trigger_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    video_path VARCHAR(500),
    settings JSONB
);

-- Index for efficient queue processing
CREATE INDEX idx_video_jobs_status_created ON video_generation_jobs(status, created_at);
```

## ⚙️ Implementation Architecture

### Video Automation Service

```python
class VideoAutomationService:
    def __init__(self, db_pool, weather_service):
        self.db = db_pool
        self.weather_service = weather_service
        self.queue = VideoQueue(db_pool)

    async def process_automation_triggers(self):
        """Main automation loop - called by worker"""
        # Check scheduled triggers
        await self._process_scheduled_triggers()

        # Check milestone triggers
        await self._process_milestone_triggers()

        # Process video generation queue
        await self.queue.process_pending_jobs()

    async def trigger_per_capture_generation(self, camera_id: int):
        """Called after each image capture"""
        camera = await self.db.get_camera_with_settings(camera_id)
        if camera.video_generation_mode == 'per_capture':
            # Apply throttling
            last_generation = await self.db.get_last_generation_time(camera_id)
            if self._should_throttle(last_generation):
                return

            # Queue video generation
            await self.queue.add_job(
                timelapse_id=camera.active_timelapse_id,
                trigger_type='per_capture',
                priority='low'
            )

    async def _process_scheduled_triggers(self):
        """Process time-based automation triggers"""
        cameras = await self.db.get_cameras_with_scheduled_generation()
        current_time = datetime.now(self.timezone)

        for camera in cameras:
            schedule = camera.generation_schedule
            if self._should_trigger_scheduled(schedule, current_time):
                await self.queue.add_job(
                    timelapse_id=camera.active_timelapse_id,
                    trigger_type='scheduled',
                    priority='medium'
                )
```

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

- [ ] Database schema migrations

- [ ] Basic VideoAutomationService with manual triggers
- [ ] Core API endpoints

### Phase 2: Worker Integration (Weeks 3-4)

- [ ] Video automation triggers in worker loop
- [ ] Video generation queue processing
- [ ] Enhanced SSE event broadcasting

### Phase 3: Frontend Components (Weeks 5-6)

- [ ] Video automation configuration interface
- [ ] Enhanced camera settings with new sections
- [ ] Dashboard updates for automation status
- [ ] Real-time queue monitoring

### Phase 4: Advanced Features (Weeks 7-8)

- [ ] Video queue management and prioritization

- [ ] Milestone-based automation
- [ ] Performance optimization and testing

### Phase 5: Polish & Documentation (Week 9)

- [ ] Comprehensive testing of all features
- [ ] User documentation and guides
- [ ] Performance monitoring and optimization
- [ ] Security audit and validation
- [ ] Production deployment preparation

## 🔒 Security Considerations

### Video Generation Security

- Rate limiting: Maximum 5 concurrent generations per user
- Job timeout limits (30 minutes maximum)
- Disk space validation before starting generation
- Priority system prevents resource exhaustion

## 📊 Performance Optimization

### Video Generation Performance

- Priority queue system (manual > milestone > scheduled > per_capture)
- Resource monitoring to prevent system overload
- Intelligent throttling based on system resources
- Cleanup of old generation jobs

### Database Optimization

- Indexes on frequently queried weather and location fields
- Efficient cache expiration cleanup
- Connection pool monitoring for performance

This implementation plan transforms Timelapser V4 into a comprehensive automated
content creation platform while maintaining strict adherence to the established
architectural patterns and AI-CONTEXT compliance requirements.
