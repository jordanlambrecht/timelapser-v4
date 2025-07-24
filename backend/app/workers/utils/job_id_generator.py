# backend/app/workers/utils/job_id_generator.py
"""
Job ID Generator

ARCHITECTURE RELATIONSHIPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ROLE: Ensures CONSISTENT job ID naming across ALL scheduler components

┌─ JobIdGenerator (this file) ─────────────────────────────────────────────────────────┐
│                                                                                      │
│  ┌─ TIMELAPSE JOBS ────────────┐     ┌─ IMMEDIATE JOBS ──────────────────────────── │
│  │ • timelapse_capture_{id}    │     │ • immediate_capture_{cam}_{timelapse}       │ │
│  │                             │     │ • immediate_video_{timelapse}               │ │
│  │                             │     │ • immediate_overlay_{image}                 │ │
│  │                             │     │ • immediate_thumbnail_{image}               │ │
│  └─────────────────────────────┘     └─────────────────────────────────────────────┘ │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ (Used by all job creators)
                                            ▼

┌─ JOB ID CONSUMERS ──────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  • SchedulerWorker → timelapse_capture() for recurring captures                    │
│  • ImmediateJobManager → immediate_*() for on-demand operations                    │
│  • StandardJobManager → Uses standard job IDs (health, weather, etc.)             │
│  • AutomationEvaluator → milestone/scheduled job ID generation                     │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

PROBLEM SOLVED:
• Original code had inconsistent job ID formats across different components
• Job ID conflicts occurred when different managers created similar job types
• No central authority for job naming conventions
• Difficult to identify job types from scheduler registry

DESIGN PATTERN: Static Utility Class
• Pure functions (no state)
• Type-specific ID generation methods
• Consistent naming conventions across all job types
• Easy to extend for new job types

NAMING CONVENTIONS:
• {job_type}_{primary_identifier}[_{secondary_identifier}]
• Always lowercase with underscores
• Primary identifier first (e.g., timelapse_id, camera_id)
• Predictable format for debugging and monitoring
"""


class JobIdGenerator:
    """Generates consistent job IDs for different job types."""

    @staticmethod
    def timelapse_capture(timelapse_id: int) -> str:
        """Generate job ID for timelapse capture jobs."""
        return f"timelapse_capture_{timelapse_id}"

    @staticmethod
    def immediate_capture(camera_id: int, timelapse_id: int) -> str:
        """Generate job ID for immediate capture jobs."""
        return f"immediate_capture_{camera_id}_{timelapse_id}"

    @staticmethod
    def immediate_video(timelapse_id: int) -> str:
        """Generate job ID for immediate video generation jobs."""
        return f"immediate_video_{timelapse_id}"

    @staticmethod
    def immediate_overlay(image_id: int) -> str:
        """Generate job ID for immediate overlay generation jobs."""
        return f"immediate_overlay_{image_id}"

    @staticmethod
    def immediate_thumbnail(image_id: int) -> str:
        """Generate job ID for immediate thumbnail generation jobs."""
        return f"immediate_thumbnail_{image_id}"
