# backend/app/workers/utils/__init__.py
"""
Scheduler Worker Utility Classes

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This utils module contains SHARED UTILITIES used by all scheduler components:

┌─ SHARED UTILITIES LAYER ─────────────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ SchedulerTimeUtils ──────┐  ┌─ JobIdGenerator ─────┐  ┌─ SchedulerJobTemplate ─┐ │
│  │ • Timezone caching         │  │ • Consistent job IDs │  │ • Common job patterns  │ │
│  │ • Time calculations        │  │ • Naming conventions │  │ • Standard config      │ │
│  │ • Settings integration     │  │ • Type-specific IDs  │  │ • Template methods     │ │
│  └────────────────────────────┘  └──────────────────────┘  └────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ (Used by all scheduler components)
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     SCHEDULER COMPONENT ECOSYSTEM                                   │
│                                                                                     │
│  • SchedulerWorker (main coordinator)                                              │
│  • ImmediateJobManager (immediate jobs)                                            │
│  • StandardJobManager (recurring jobs)                                             │
│  • AutomationEvaluator (trigger evaluation)                                        │
└─────────────────────────────────────────────────────────────────────────────────────┘

DESIGN PRINCIPLES:
• DRY (Don't Repeat Yourself): Eliminates duplication across scheduler components
• Single Responsibility: Each utility class has one clear purpose
• Dependency Injection: Utilities injected into components that need them
• Consistent API: All utilities follow similar initialization and usage patterns

REFACTORING BENEFIT:
• Original code had timezone setup duplicated 7+ times
• Job ID generation was inconsistent across different job types
• Common job scheduling patterns were repeated in multiple places
• Now all shared logic is centralized and reusable
"""

from .scheduler_time_utils import SchedulerTimeUtils
from .job_id_generator import JobIdGenerator
from .scheduler_job_template import SchedulerJobTemplate
from .worker_status_builder import WorkerStatusBuilder

__all__ = [
    "SchedulerTimeUtils",
    "JobIdGenerator",
    "SchedulerJobTemplate",
    "WorkerStatusBuilder",
]
