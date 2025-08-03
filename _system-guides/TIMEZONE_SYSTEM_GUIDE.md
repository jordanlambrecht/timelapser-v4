# Timezone System Architecture Guide

## Overview

Timelapser v4 implements a comprehensive timezone-aware system designed for SaaS
deployment with user-configurable timezones. The system follows the industry
standard of **storing all database timestamps in UTC** while performing
**business logic and user interfaces in the user's configured timezone**.

## Core Principles

### 1. UTC Database Storage

- **All database timestamps are stored in UTC** using `TIMESTAMP(timezone=True)`
- Database migration files consistently use `sa.TIMESTAMP(timezone=True)`
- This ensures data portability and consistency across deployments

### 2. User Timezone for Business Logic

- All scheduling, time windows, and user-facing operations use the configured
  timezone
- File naming and capture sequences respect user's local time
- Daily rollover calculations happen in user timezone

### 3. Cache-Backed Configuration

- Timezone settings are stored in database and cached for performance
- Cache invalidation ensures consistency when settings change
- Async/sync variants handle different execution contexts

## Architecture Components

### Core Module: `time_utils.py`

Located at `backend/app/utils/time_utils.py`, this module provides three
categories of functions:

#### 1. Database-Aware Timezone Operations

Functions that require database settings and cache integration:

```python
# Primary timezone retrieval functions
get_timezone_from_cache_sync(settings_service) -> str
get_timezone_from_cache_async(settings_service) -> str

# Main timestamp generation functions
get_timezone_aware_timestamp_sync(settings_service) -> datetime
get_timezone_aware_timestamp_async(settings_service) -> datetime
```

#### 2. Timezone-Aware Timestamp Operations

Functions for generating timestamps in user timezone:

```python
# Date strings in user timezone
get_timezone_aware_date_sync(settings_service) -> str
get_timezone_aware_date_async(settings_service) -> str

# Filename-safe timestamps in user timezone
get_timezone_aware_timestamp_string_sync(settings_service) -> str
get_timezone_aware_timestamp_string_async(settings_service) -> str
```

#### 3. Timezone Conversion Functions

Convert between UTC (database) and user timezone:

```python
# Convert UTC database timestamps to user timezone
convert_to_db_timezone_sync(utc_timestamp, settings_service) -> datetime
convert_to_db_timezone_async(utc_timestamp, settings_service) -> datetime
```

### Cache Integration

The system uses `cache_manager.py` for performance:

```python
# Cache timezone settings to avoid repeated database queries
from app.utils.cache_manager import get_timezone_async

# Fallback mechanisms for reliability
try:
    timezone = await get_timezone_async(settings_service)
    return timezone or "UTC"
except Exception:
    return "UTC"  # Always fallback to UTC
```

## Usage Patterns

### 1. Database Storage (Always UTC)

**DO**: Store all timestamps in UTC

```python
# Database operations - always UTC
created_at = utc_now()
captured_at = utc_now()
```

**DON'T**: Store user timezone timestamps in database

```python
# ❌ Wrong - don't store user timezone in database
created_at = get_timezone_aware_timestamp_sync(settings_service)
```

### 2. Business Logic (User Timezone)

**DO**: Use timezone-aware functions for scheduling and logic

```python
# ✅ Capture scheduling in user timezone
current_time = get_timezone_aware_timestamp_sync(settings_service)
current_date = get_timezone_aware_date_sync(settings_service)

# ✅ File naming in user timezone
timestamp_str = get_timezone_aware_timestamp_string_sync(settings_service)
filename = f"capture_{timestamp_str}.jpg"
```

### 3. Frontend Display (User Timezone)

**DO**: Convert database UTC timestamps to user timezone for display

```python
# ✅ Convert UTC from database to user timezone for API response
utc_timestamp = image.captured_at  # UTC from database
user_timestamp = convert_to_db_timezone_sync(utc_timestamp, settings_service)
```

### 4. Time Window Calculations (User Timezone)

```python
# ✅ Scheduling logic in user timezone
def should_capture_now(settings_service, start_time, end_time):
    current_time = get_timezone_aware_timestamp_sync(settings_service)
    # Compare times in user timezone for intuitive behavior
    return start_time <= current_time.time() <= end_time
```

## Function Selection Guide

### Async vs Sync Variants

**Use Async versions in:**

- FastAPI route handlers
- Async service methods
- Database operations with async SQLAlchemy

**Use Sync versions in:**

- Worker processes
- Background tasks
- Non-async contexts (avoids event loop conflicts)

### Primary Functions by Use Case

| Use Case           | Function                                     | Example                                 |
| ------------------ | -------------------------------------------- | --------------------------------------- |
| Database storage   | `utc_now()`                                  | `created_at = utc_now()`                |
| Current user time  | `get_timezone_aware_timestamp_sync()`        | Scheduling decisions                    |
| File naming        | `get_timezone_aware_timestamp_string_sync()` | `capture_20240802_143022.jpg`           |
| Date rollover      | `get_timezone_aware_date_sync()`             | Daily timelapse boundaries              |
| Display conversion | `convert_to_db_timezone_sync()`              | Show UTC database time in user timezone |

## Validation and Error Handling

### Timezone Validation

```python
def validate_timezone(timezone_str: str) -> bool:
    """Validate IANA timezone identifiers"""
    try:
        ZoneInfo(timezone_str)
        return True
    except Exception:
        return False
```

### Fallback Strategy

The system implements comprehensive fallback mechanisms:

1. **Invalid timezone** → Falls back to UTC
2. **Cache failure** → Direct settings service access
3. **Settings service failure** → Falls back to UTC
4. **Database unavailable** → Falls back to UTC

This ensures the system remains functional even during partial failures.

## Multi-Tenant Considerations

### Current State (Single-Tenant)

- One global timezone setting for the entire application
- Stored in `settings` table as `timezone` key
- Cached globally for performance

### Future SaaS Evolution

For true multi-tenant SaaS, the system will need:

```python
# Per-user timezone settings
user_timezone = get_user_timezone(user_id)
org_timezone = get_org_timezone(org_id)
default_timezone = get_system_default()

# Session-based caching
cache_key = f"timezone:{user_id}"
```

## Integration Points

### Services Using Timezone System

- **Capture Pipeline**: File naming, scheduling decisions
- **Video Pipeline**: Timestamp overlays, sequence generation
- **Overlay System**: Date/time generators
- **Weather Service**: Time-based weather fetching
- **Statistics Service**: Daily/hourly aggregations
- **Logger Service**: Log timestamps in user timezone

### Database Models

All models with timestamps use `TIMESTAMP(timezone=True)`:

- `images.captured_at`
- `timelapses.created_at`, `started_at`, `completed_at`
- `videos.created_at`
- `scheduled_jobs.next_run_time`, `last_run_time`
- `weather.fetched_at`

## Best Practices

### 1. Consistency Rules

- **Database operations**: Always use UTC (`utc_now()`)
- **Business logic**: Always use timezone-aware functions
- **File operations**: Use timezone-aware timestamps for naming
- **API responses**: Convert UTC to user timezone before sending

### 2. Performance Guidelines

- Cache timezone settings when possible
- Use appropriate async/sync variants for context
- Batch timezone conversions when processing multiple timestamps

### 3. Error Handling

- Always provide UTC fallback for critical operations
- Log timezone validation failures
- Handle cache misses gracefully

## Testing Considerations

### Unit Tests

- Test with multiple timezone configurations
- Verify UTC storage in database
- Test fallback mechanisms
- Validate timezone conversion accuracy

### Integration Tests

- Test scheduling across timezone boundaries
- Verify file naming consistency
- Test cache invalidation scenarios

This architecture provides a robust foundation for timezone-aware operations
while maintaining simplicity and performance. The system is designed to scale
from single-tenant to multi-tenant SaaS deployment with minimal architectural
changes.

## ✅ **Recent Enhancements**

### DST Transition Protection

**Added: February 2025**

New functions in `time_utils.py` protect against daylight saving time issues:

```python
# Detect DST transitions to prevent scheduling issues
is_transition, transition_type = is_dst_transition(datetime_obj, "America/Chicago")

# Get safe capture time that avoids DST problems
safe_time = get_safe_capture_time(target_time, timezone_str)
```

**Integration**: DST detection is now integrated into
`CaptureTimingService.calculate_next_capture_time()` to automatically adjust
scheduled captures during DST transitions.

### Database Timezone Validation

**Added: February 2025**

Application startup now validates database timezone configuration:

```python
# Validates database is configured for UTC storage
is_valid, db_timezone = validate_database_timezone_config()
```

**Integration**: Validation runs at FastAPI startup (`main.py:90`) and logs
warnings if database timezone is misconfigured.

### Timezone Change Audit Logging

**Added: February 2025**

All timezone changes are now logged for audit and debugging:

```python
# Logs timezone changes with source tracking
log_timezone_change(old_tz, new_tz, source="settings_api")
```

**Integration**: Automatically triggered when timezone settings are changed via
`SettingsService.set_setting()`.

### Cache Consistency Monitoring

**Added: February 2025**

System can now validate timezone cache health:

```python
# Validates cache consistency and data integrity
result = validate_timezone_cache_consistency()
```

**Monitoring**: Returns detailed status including cache health, validation
results, and any issues found.

## 🧪 **Testing**

A test script is available to verify all timezone fixes:

```bash
cd backend
python3 test_timezone_fixes.py
```

This validates:

- ✅ DST detection and safe time calculation
- ✅ Database timezone validation
- ✅ Timezone change logging
- ✅ Cache consistency monitoring

## 🚨 **Production Recommendations**

### Immediate Actions

1. **Monitor startup logs** for database timezone warnings
2. **Test DST transitions** in your deployment timezone
3. **Review timezone change logs** for unexpected modifications
4. **Run cache validation** periodically for health monitoring

### Future Enhancements

1. **Distributed cache validation** across multiple worker nodes
2. **Real-time DST transition alerts** for operations teams
3. **Automated timezone misconfiguration alerts**
4. **Per-user timezone settings** for multi-tenant deployment
