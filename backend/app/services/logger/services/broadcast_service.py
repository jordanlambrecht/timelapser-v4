"""
SSE Broadcast Service for the Logger Service.

This service handles real-time broadcasting of log events via Server-Sent Events (SSE).
It integrates with the existing SSE infrastructure to provide live log monitoring
and alerting capabilities.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
from enum import Enum

from ....enums import LogLevel, LogSource, LoggerName, SSEPriority, SSEEvent
from ....database.sse_events_operations import SSEEventsOperations, SyncSSEEventsOperations


class LogEventType(str, Enum):
    """Log event types for SSE broadcasting."""
    
    REQUEST_LOG = "request_log"
    ERROR_LOG = "error_log"
    WORKER_LOG = "worker_log"
    SYSTEM_LOG = "system_log"
    CAPTURE_LOG = "capture_log"
    LOG_HEALTH = "log_health"


class SSEBroadcastService:
    """
    Service for broadcasting log events via Server-Sent Events.
    
    Features:
    - Real-time log event broadcasting
    - Configurable event filtering and priority
    - Integration with existing SSE infrastructure
    - Health monitoring and error handling
    - Async/sync dual support for different contexts
    """
    
    def __init__(
        self, 
        sse_ops: SSEEventsOperations, 
        sync_sse_ops: SyncSSEEventsOperations,
        enable_debug_events: bool = False,
        max_event_queue_size: int = 1000
    ):
        """
        Initialize the SSE broadcast service.
        
        Args:
            sse_ops: Async SSE operations instance
            sync_sse_ops: Sync SSE operations instance
            enable_debug_events: Whether to broadcast DEBUG level events
            max_event_queue_size: Maximum size of event queue
        """
        self.sse_ops = sse_ops
        self.sync_sse_ops = sync_sse_ops
        self.enable_debug_events = enable_debug_events
        self.max_event_queue_size = max_event_queue_size
        
        # Health tracking
        self._healthy = True
        self._last_broadcast_error = None
        self._total_broadcasts = 0
        self._failed_broadcasts = 0
        
        # Event queue for batching (if needed)
        self._event_queue = []
        self._queue_lock = asyncio.Lock()
    
    async def broadcast_log_event(
        self,
        event_type: str,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        context: Optional[Dict[str, Any]] = None,
        priority: SSEPriority = SSEPriority.NORMAL,
        camera_id: Optional[int] = None
    ) -> bool:
        """
        Broadcast a log event via SSE.
        
        Args:
            event_type: Type of log event
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            context: Optional context data
            priority: SSE priority level
            camera_id: Optional camera ID
            
        Returns:
            True if broadcast was successful
        """
        try:
            # Check if we should broadcast this event
            if not self._should_broadcast_event(level, source, priority):
                return True  # Not an error, just filtered out
            
            # Create SSE event data
            event_data = self._create_event_data(
                event_type, message, level, source, logger_name, context, camera_id
            )
            
            # Determine SSE event type based on log characteristics
            sse_event_type = self._map_to_sse_event_type(event_type, level, source)
            
            # Broadcast via SSE
            success = await self._broadcast_sse_event(
                sse_event_type, event_data, priority
            )
            
            # Update statistics
            self._total_broadcasts += 1
            if not success:
                self._failed_broadcasts += 1
                self._healthy = False
            
            return success
            
        except Exception as e:
            self._last_broadcast_error = str(e)
            self._failed_broadcasts += 1
            self._healthy = False
            print(f"SSEBroadcastService.broadcast_log_event failed: {e}")
            return False
    
    def _should_broadcast_event(
        self, 
        level: LogLevel, 
        source: LogSource, 
        priority: SSEPriority
    ) -> bool:
        """
        Determine if a log event should be broadcasted.
        
        Args:
            level: Log level
            source: Log source
            priority: SSE priority
            
        Returns:
            True if event should be broadcasted
        """
        # Skip DEBUG events unless explicitly enabled
        if level == LogLevel.DEBUG and not self.enable_debug_events:
            return False
        
        # Always broadcast high priority events
        if priority in [SSEPriority.HIGH, SSEPriority.CRITICAL]:
            return True
        
        # Always broadcast errors and warnings
        if level in [LogLevel.ERROR, LogLevel.CRITICAL, LogLevel.WARNING]:
            return True
        
        # Broadcast important system events
        if source == LogSource.SYSTEM and level == LogLevel.INFO:
            return True
        
        # Broadcast camera-related events (important for monitoring)
        if source == LogSource.CAMERA:
            return True
        
        # Skip low priority system logs
        if source == LogSource.SYSTEM and priority == SSEPriority.LOW:
            return False
        
        # Default: broadcast normal and high priority events
        return priority in [SSEPriority.NORMAL, SSEPriority.HIGH, SSEPriority.CRITICAL]
    
    def _create_event_data(
        self,
        event_type: str,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        context: Optional[Dict[str, Any]],
        camera_id: Optional[int]
    ) -> Dict[str, Any]:
        """
        Create structured event data for SSE broadcasting.
        
        Args:
            event_type: Type of log event
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            context: Context data
            camera_id: Camera ID
            
        Returns:
            Structured event data dictionary
        """
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "message": message,
            "level": level.value,
            "source": source.value,
            "logger_name": logger_name.value,
        }
        
        # Add camera ID if present
        if camera_id is not None:
            event_data["camera_id"] = camera_id
        
        # Add context data if present (with size limit)
        if context:
            # Limit context size to prevent oversized events
            event_data["context"] = self._limit_context_size(context)
        
        return event_data
    
    def _limit_context_size(self, context: Dict[str, Any], max_size: int = 1000) -> Dict[str, Any]:
        """
        Limit context data size for SSE events.
        
        Args:
            context: Original context data
            max_size: Maximum approximate size in characters
            
        Returns:
            Limited context data
        """
        try:
            import json
            
            # Try to serialize context to check size
            context_json = json.dumps(context, separators=(',', ':'))
            
            if len(context_json) <= max_size:
                return context
            
            # If too large, include only essential keys
            essential_keys = [
                "error", "exception", "camera_id", "job_id", "image_id", 
                "worker_name", "status", "retry_count", "file_path"
            ]
            
            limited_context = {}
            for key in essential_keys:
                if key in context:
                    limited_context[key] = context[key]
                    # Check size after each addition
                    limited_json = json.dumps(limited_context, separators=(',', ':'))
                    if len(limited_json) > max_size:
                        # Remove the last addition and break
                        del limited_context[key]
                        break
            
            # Add truncation indicator
            limited_context["_truncated"] = True
            
            return limited_context
            
        except Exception:
            # If JSON serialization fails, return minimal context
            return {"_context_error": True}
    
    def _map_to_sse_event_type(
        self, 
        event_type: str, 
        level: LogLevel, 
        source: LogSource
    ) -> SSEEvent:
        """
        Map log event characteristics to SSE event types.
        
        Args:
            event_type: Log event type
            level: Log level
            source: Log source
            
        Returns:
            Mapped SSE event type
        """
        # Error events
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            if source == LogSource.CAMERA:
                return SSEEvent.CAMERA_HEALTH_CHANGED
            elif source == LogSource.WORKER:
                return SSEEvent.THUMBNAIL_WORKER_ERROR  # Generic worker error
            else:
                return SSEEvent.SYSTEM_ERROR
        
        # Warning events  
        if level == LogLevel.WARNING:
            return SSEEvent.SYSTEM_WARNING
        
        # Source-specific events
        if source == LogSource.CAMERA:
            if "capture" in event_type.lower():
                return SSEEvent.IMAGE_CAPTURED
            else:
                return SSEEvent.CAMERA_HEALTH_CHANGED
        
        if source == LogSource.WORKER:
            if "thumbnail" in event_type.lower():
                return SSEEvent.THUMBNAIL_WORKER_PERFORMANCE
            else:
                return SSEEvent.WORKER_STARTED  # Generic worker event
        
        # Default to system events
        return SSEEvent.SYSTEM_WARNING  # Generic system event
    
    async def _broadcast_sse_event(
        self, 
        sse_event_type: SSEEvent, 
        event_data: Dict[str, Any], 
        priority: SSEPriority
    ) -> bool:
        """
        Broadcast event via SSE infrastructure.
        
        Args:
            sse_event_type: SSE event type
            event_data: Event data
            priority: Priority level
            
        Returns:
            True if broadcast was successful
        """
        try:
            # Use the existing SSE operations to broadcast
            await self.sse_ops.add_sse_event(
                event_type=sse_event_type.value,
                data=event_data,
                priority=priority.value,
                source="logger_service",
                # Add any additional metadata for the SSE system
                metadata={
                    "log_broadcast": True,
                    "broadcast_timestamp": datetime.now().isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            print(f"SSEBroadcastService._broadcast_sse_event failed: {e}")
            return False
    
    def broadcast_log_event_sync(
        self,
        event_type: str,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        context: Optional[Dict[str, Any]] = None,
        priority: SSEPriority = SSEPriority.NORMAL,
        camera_id: Optional[int] = None
    ) -> bool:
        """
        Synchronous version of broadcast_log_event for worker contexts.
        
        Args:
            event_type: Type of log event
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            context: Optional context data
            priority: SSE priority level
            camera_id: Optional camera ID
            
        Returns:
            True if broadcast was successful
        """
        try:
            # Check if we should broadcast this event
            if not self._should_broadcast_event(level, source, priority):
                return True  # Not an error, just filtered out
            
            # Create SSE event data
            event_data = self._create_event_data(
                event_type, message, level, source, logger_name, context, camera_id
            )
            
            # Determine SSE event type
            sse_event_type = self._map_to_sse_event_type(event_type, level, source)
            
            # Broadcast via sync SSE operations
            success = self._broadcast_sse_event_sync(
                sse_event_type, event_data, priority
            )
            
            # Update statistics
            self._total_broadcasts += 1
            if not success:
                self._failed_broadcasts += 1
                self._healthy = False
            
            return success
            
        except Exception as e:
            self._last_broadcast_error = str(e)
            self._failed_broadcasts += 1
            self._healthy = False
            print(f"SSEBroadcastService.broadcast_log_event_sync failed: {e}")
            return False
    
    def _broadcast_sse_event_sync(
        self, 
        sse_event_type: SSEEvent, 
        event_data: Dict[str, Any], 
        priority: SSEPriority
    ) -> bool:
        """
        Synchronous broadcast event via SSE infrastructure.
        
        Args:
            sse_event_type: SSE event type
            event_data: Event data
            priority: Priority level
            
        Returns:
            True if broadcast was successful
        """
        try:
            # Use the sync SSE operations to broadcast
            self.sync_sse_ops.write_sse_event(
                event_type=sse_event_type.value,
                data=event_data,
                priority=priority.value,
                source="logger_service",
                metadata={
                    "log_broadcast": True,
                    "broadcast_timestamp": datetime.now().isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            print(f"SSEBroadcastService._broadcast_sse_event_sync failed: {e}")
            return False
    
    def is_healthy(self) -> bool:
        """
        Check if the SSE broadcast service is healthy.
        
        Returns:
            True if service is healthy
        """
        return self._healthy
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get SSE broadcast service statistics.
        
        Returns:
            Dictionary containing service statistics
        """
        return {
            "healthy": self._healthy,
            "total_broadcasts": self._total_broadcasts,
            "failed_broadcasts": self._failed_broadcasts,
            "success_rate": (
                (self._total_broadcasts - self._failed_broadcasts) / self._total_broadcasts
                if self._total_broadcasts > 0 else 1.0
            ),
            "last_broadcast_error": self._last_broadcast_error,
            "enable_debug_events": self.enable_debug_events,
            "max_event_queue_size": self.max_event_queue_size,
            "current_queue_size": len(self._event_queue)
        }
    
    def reset_health(self) -> None:
        """Reset the health status of the service."""
        self._healthy = True
        self._last_broadcast_error = None
    
    def set_debug_events_enabled(self, enabled: bool) -> None:
        """
        Enable or disable DEBUG level event broadcasting.
        
        Args:
            enabled: Whether to broadcast DEBUG events
        """
        self.enable_debug_events = enabled