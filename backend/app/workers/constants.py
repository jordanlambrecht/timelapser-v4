"""
Worker-specific constants for Timelapser v4.

This file consolidates all magic numbers used in workers to improve maintainability
and make configuration changes easier.
"""

# Time Conversion Constants
SECONDS_PER_HOUR = 3600
MILLISECONDS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60

# Worker Sleep/Retry Intervals (in seconds)
WORKER_ERROR_RETRY_SECONDS = 300  # 5 minutes
WORKER_SHORT_SLEEP_SECONDS = 5  # Short sleep for quick retries

# Cache TTL Constants (in seconds)
SCHEDULER_CACHE_TTL_SECONDS = 300  # 5 minutes for scheduler settings cache

# Cleanup Worker Specific
CLEANUP_ERROR_RETRY_MINUTES = 5
CLEANUP_INTERVAL_HOURS_DEFAULT = 6

# Job Processing Constants
JOB_PROCESSING_MISFIRE_GRACE_TIME = 30  # seconds
JOB_BATCH_TIMEOUT_MULTIPLIER = 1000  # Convert seconds to milliseconds

# Weather Worker Specific
WEATHER_STALENESS_CHECK_HOURS = 1.0  # Check if weather data is older than 1 hour
WEATHER_SSE_CLEANUP_HOURS = 24  # Keep 24 hours of SSE events

# Scheduler Worker Specific
SCHEDULER_JOB_EXECUTION_TRACKING_TIME_PRECISION = (
    2  # Decimal places for execution time logging
)

# Performance Tracking
PERFORMANCE_TIME_CONVERSION_MULTIPLIER = (
    1000  # Convert seconds to milliseconds for performance metrics
)

# Scheduler-Specific Constants
SCHEDULER_IMMEDIATE_JOB_DELAY_SECONDS = 2  # Default delay for immediate jobs
SCHEDULER_MISFIRE_GRACE_TIME_SECONDS = 30  # APScheduler misfire grace time
WEATHER_STARTUP_DELAY_SECONDS = 5  # Weather startup job delay
WEATHER_CATCHUP_INTERVAL_MINUTES = 15  # Weather catchup job interval
AUTOMATION_TRIGGER_INTERVAL_MINUTES = 5  # Automation trigger evaluation interval
TIMELAPSE_SYNC_INTERVAL_MINUTES = 5  # Timelapse sync interval
SSE_CLEANUP_INTERVAL_HOURS = 6  # SSE cleanup interval
