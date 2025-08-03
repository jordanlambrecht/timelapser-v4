# backend/app/workers/utils/scheduler_time_utils.py
"""
Scheduler Time Utils

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Centralized timezone and time utilities for ALL scheduler operations

┌─ SchedulerTimeUtils (this file) ─────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ TIMEZONE CACHING ──────┐     ┌─ TIME CALCULATIONS ─────────────────────────────┐ │
│  │ • ZoneInfo caching       │     │ • Timezone-aware datetime creation             │ │
│  │ • Settings integration   │     │ • Current time with correct timezone           │ │
│  │ • Cache invalidation     │     │ • Eliminates timezone setup duplication        │ │
│  └──────────────────────────┘     └─────────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ (Used by all components)
                                            ▼

┌─ CONSUMERS ─────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  • SchedulerWorker → Uses for timezone-aware scheduling                            │
│  • ImmediateJobManager → Uses for timestamp operations                             │
│  • StandardJobManager → Uses for cron job scheduling                               │
│  • AutomationEvaluator → Uses for time-based trigger evaluation                   │
│  • SchedulerJobTemplate → Uses for consistent time handling                        │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

PROBLEM SOLVED:
• Original SchedulerWorker had timezone setup code duplicated 7+ times
• Each component was independently fetching timezone settings
• No caching meant repeated database calls for the same timezone info
• Time calculations were inconsistent across different scheduler operations

DESIGN PATTERN: Cached Service Utility
• Settings service injection for configuration access
• Lazy loading with cache invalidation support
• Thread-safe timezone handling
• Consistent API across all scheduler time operations
"""

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ...services.settings_service import SyncSettingsService
from ...utils.time_utils import create_timezone_aware_datetime


class SchedulerTimeUtils:
    """Centralized time utilities with caching for scheduler operations."""

    def __init__(self, settings_service: SyncSettingsService):
        """Initialize with settings service for timezone access."""
        self.settings_service = settings_service
        self._cached_timezone: Optional[ZoneInfo] = None

    def get_timezone(self) -> ZoneInfo:
        """Get configured timezone with caching."""
        if self._cached_timezone is None:
            from ...constants import DEFAULT_TIMEZONE
            settings = self.settings_service.get_all_settings()
            timezone_str = settings.get("timezone", DEFAULT_TIMEZONE)
            self._cached_timezone = ZoneInfo(timezone_str)
        return self._cached_timezone

    def clear_timezone_cache(self) -> None:
        """Clear cached timezone (call when settings change)."""
        self._cached_timezone = None

    def get_current_time(self) -> datetime:
        """Get current timezone-aware datetime."""
        timezone = self.get_timezone()
        # Get the timezone string from the cached ZoneInfo object
        timezone_str = str(timezone)
        return create_timezone_aware_datetime(timezone_str)
