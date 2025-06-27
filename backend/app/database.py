"""
Database Layer for Timelapser v4 - Modular Bridge

This module provides backward compatibility by re-exporting the modular database classes.
The actual implementation has been split into focused modules within the database package.

The module implements two main database classes:
- AsyncDatabase: For use with FastAPI endpoints requiring async operations
- SyncDatabase: For use with worker processes requiring synchronous operations

Features:
- Connection pooling with configurable pool sizes
- Automatic transaction management with rollback on errors
- Comprehensive CRUD operations for all entities (cameras, timelapses, images, videos, settings)
- Real-time event broadcasting via Server-Sent Events (SSE)
- Health monitoring and statistics collection
- Time window and scheduling management
- Video generation settings and metadata handling
- Thumbnail and image size variant management
- Corruption detection and quality control
- Modular architecture for maintainability

Database Schema Entities:
- cameras: Camera configuration and status
- timelapses: Timelapse sessions and metadata
- images: Captured image records with thumbnails
- videos: Generated video files and settings
- settings: Application configuration key-value pairs
- logs: System and camera event logs
- corruption_logs: Image quality detection logs
- video_generation_jobs: Video automation queue

Connection Management:
- Uses psycopg3 with connection pooling for performance
- Configurable pool sizes via settings
- Automatic connection health checks and recovery
- Context managers for safe connection handling

Event System:
- Broadcasts real-time updates to frontend via SSE
- Supports camera status changes, image captures, and timelapse events
- Integrates with Next.js frontend for live dashboard updates

Modular Architecture:
The database operations are now organized into focused modules:
- camera_operations: Camera CRUD and health monitoring
- timelapse_operations: Timelapse lifecycle management
- image_operations: Image recording and retrieval
- video_operations: Video records and generation jobs
- settings_operations: Settings CRUD operations
- corruption_operations: Corruption detection logging
- statistics_operations: System health aggregation
- log_operations: Log retrieval and filtering

Authors: Timelapser Development Team
Version: 4.0
License: Private
"""

# Import the modular database classes
from .database import AsyncDatabase, SyncDatabase

# Export the classes for backward compatibility
__all__ = ["AsyncDatabase", "SyncDatabase"]

# Optional: Provide access to individual operation modules for advanced usage
from .database import (
    camera_operations,
    timelapse_operations,
    image_operations,
    video_operations,
    settings_operations,
    corruption_operations,
    statistics_operations,
    log_operations,
)
