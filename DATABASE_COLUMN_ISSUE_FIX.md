# Database Column Issue Fix

## Problem
The application is experiencing a critical database error:
```
column c.generation_schedule does not exist
```

This error occurs in `/api/cameras/1/latest-image` endpoint when the video automation worker tries to check for scheduled video generation triggers.

## Root Cause Analysis

### Error Location
- **File**: `backend/app/database/video_operations.py:1081`
- **Method**: `get_scheduled_automation_timelapses()`
- **Query**: 
  ```sql
  COALESCE(t.generation_schedule, c.generation_schedule) as schedule
  ```

### Call Stack
1. Worker process starts
2. `video_automation_service.process_automation_triggers()` is called
3. `check_scheduled_triggers()` is called  
4. `video_ops.get_scheduled_automation_timelapses()` is called
5. SQL query fails because `cameras.generation_schedule` column doesn't exist

### Expected Schema
According to migration `010_add_video_automation.py`, the following columns should exist:
- `cameras.generation_schedule` (JSONB, nullable)
- `cameras.video_automation_mode` (VARCHAR)
- `timelapses.generation_schedule` (JSONB, nullable) 
- `timelapses.video_automation_mode` (VARCHAR)

## Solution

### 1. Database Diagnosis
Run the diagnostic script to check current schema:
```bash
cd backend
python3 diagnose_db_schema.py
```

### 2. Apply Missing Migration
If columns are missing, apply the repair migration:
```bash
cd backend
alembic upgrade head
```

### 3. Verify Fix
Test the problematic endpoint:
```bash
curl http://localhost:8000/api/cameras/1/latest-image
```

## Files Created/Modified

### New Migration
- `backend/alembic/versions/017_ensure_generation_schedule_columns.py`
  - Checks for missing columns and adds them if needed
  - Safe to run multiple times (idempotent)

### Diagnostic Tool  
- `backend/diagnose_db_schema.py`
  - Checks database schema for expected columns
  - Tests the problematic query
  - Provides clear status of missing columns

## Prevention
To prevent similar issues in the future:
1. Always run `alembic upgrade head` after pulling changes
2. Use the diagnostic script to verify schema before deploying
3. Include database schema checks in CI/CD pipeline

## Migration History Analysis
- `010_add_video_automation.py` - Added generation_schedule columns ✅
- `011_separate_video_generation_modes.py` - Renamed video_generation_mode ✅  
- `012_fix_settings_table_structure.py` - Only touched settings table ✅
- Subsequent migrations - No column removals found ✅

The columns should exist according to migrations, suggesting either:
1. Migration 010 was never applied to this database
2. Database schema drift occurred
3. Migration was partially applied or reverted

The repair migration `017_ensure_generation_schedule_columns.py` will resolve this safely.