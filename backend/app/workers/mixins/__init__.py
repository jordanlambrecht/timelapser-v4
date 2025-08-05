# backend/app/workers/mixins/__init__.py
"""
Shared mixins and utilities for Timelapser worker components.

This package provides common functionality used across multiple workers,
reducing code duplication and improving maintainability.

ARCHITECTURE NOTE:
These mixins are designed to eliminate the 800+ lines of duplicated code
found across ThumbnailWorker and OverlayWorker while maintaining the
CEO architecture pattern where SchedulerWorker makes all timing decisions.
"""

from .job_processing_mixin import JobProcessingMixin
from .retry_manager import RetryManager
from .sse_broadcaster import SSEBroadcaster
from .job_batch_processor import JobBatchProcessor
from .startup_recovery_mixin import StartupRecoveryMixin
from .settings_helper_mixin import SettingsHelperMixin

__all__ = [
    "JobProcessingMixin",
    "RetryManager",
    "SSEBroadcaster",
    "JobBatchProcessor",
    "StartupRecoveryMixin",
    "SettingsHelperMixin",
]
