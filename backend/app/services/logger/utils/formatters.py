"""
Log Message Formatters for the Logger Service.

This module provides message formatting utilities that enhance log messages
with consistent formatting, emoji support, and context integration.
"""

import re
from typing import Dict, Any, Optional
from datetime import datetime

from ....enums import LogLevel, LogSource, LoggerName, LogEmoji


class LogMessageFormatter:
    """
    Formatter for log messages that provides consistent formatting across all handlers.
    
    Features:
    - Emoji standardization and enhancement
    - Message template processing
    - Context data integration
    - Level-specific formatting
    - Source-aware formatting
    """
    
    # Standard emoji patterns for different log types
    EMOJI_PATTERNS = {
        # Request/Response patterns
        "incoming": "📥",
        "outgoing": "📤", 
        "request": "📥",
        "response": "📤",
        
        # Status patterns
        "success": "✅",
        "completed": "✅",
        "failed": "💥",
        "error": "💥",
        "warning": "⚠️",
        "info": "ℹ️",
        "debug": "🔍",
        
        # Work patterns
        "processing": "🔄",
        "working": "🔄",
        "job": "🔄",
        "task": "🔄",
        "running": "▶️",
        "stopped": "⏹️",
        "paused": "⏸️",
        "resumed": "▶️",
        
        # Camera/Video patterns
        "camera": "📹",
        "video": "🎥",
        "image": "🖼️",
        "capture": "📸",
        "thumbnail": "🖼️",
        "overlay": "🎨",
        
        # System patterns
        "system": "⚙️",
        "startup": "🚀",
        "shutdown": "🔌",
        "health": "💓",
        "cleanup": "🧹",
        "maintenance": "🔧",
        
        # Database patterns
        "database": "🗄️",
        "storage": "💾",
        "backup": "💾",
        
        # Network patterns
        "network": "🌐",
        "connection": "🔗",
        "disconnected": "🔌",
        
        # Worker patterns
        "worker": "👷",
        "scheduler": "⏰",
        "queue": "📋"
    }
    
    def __init__(self, enable_emoji_enhancement: bool = True):
        """
        Initialize the log message formatter.
        
        Args:
            enable_emoji_enhancement: Whether to auto-add emojis to messages
        """
        self.enable_emoji_enhancement = enable_emoji_enhancement
    
    def format_message(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        context: Optional[Dict[str, Any]] = None,
        emoji: Optional[LogEmoji] = None
    ) -> str:
        """
        Format a log message with consistent styling and emoji enhancement.
        
        Args:
            message: Original log message
            level: Log level
            source: Log source
            logger_name: Logger name
            context: Optional context data
            emoji: Optional type-safe emoji (overrides auto-suggestion)
            
        Returns:
            Formatted log message
        """
        try:
            # Start with the original message
            formatted_message = message.strip()
            
            # Handle emoji addition
            if not self._has_emoji(formatted_message):
                # Use provided emoji or suggest one if enhancement is enabled
                chosen_emoji = emoji
                if chosen_emoji is None and self.enable_emoji_enhancement:
                    chosen_emoji = self._suggest_emoji_enum(formatted_message, level, source, logger_name, context)
                
                if chosen_emoji:
                    formatted_message = f"{chosen_emoji.value} {formatted_message}"
            
            # Apply level-specific formatting
            formatted_message = self._apply_level_formatting(formatted_message, level)
            
            # Apply source-specific enhancements
            formatted_message = self._apply_source_formatting(formatted_message, source, logger_name)
            
            # Integrate context data if present
            if context:
                formatted_message = self._integrate_context(formatted_message, context)
            
            return formatted_message
            
        except Exception as e:
            # If formatting fails, return original message
            print(f"LogMessageFormatter.format_message failed: {e}")
            return message
    
    def _has_emoji(self, message: str) -> bool:
        """
        Check if message already contains emoji.
        
        Args:
            message: Message to check
            
        Returns:
            True if message contains emoji
        """
        # Simple check for common emoji patterns
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
        return bool(emoji_pattern.search(message))
    
    def _suggest_emoji_enum(
        self,
        message: str,
        level: LogLevel,
        source: LogSource,
        logger_name: LoggerName,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[LogEmoji]:
        """
        Suggest an appropriate LogEmoji enum for the message.
        
        Args:
            message: Log message
            level: Log level
            source: Log source
            logger_name: Logger name
            context: Context data
            
        Returns:
            Suggested LogEmoji enum or None
        """
        message_lower = message.lower()
        
        # Check for direct pattern matches first (map to LogEmoji enums)
        if "request" in message_lower or "incoming" in message_lower:
            return LogEmoji.INCOMING
        elif "response" in message_lower or "outgoing" in message_lower:
            return LogEmoji.OUTGOING
        elif "success" in message_lower or "completed" in message_lower:
            return LogEmoji.SUCCESS
        elif "failed" in message_lower or "error" in message_lower:
            return LogEmoji.FAILED
        elif "processing" in message_lower or "working" in message_lower:
            return LogEmoji.PROCESSING
        elif "capture" in message_lower:
            return LogEmoji.CAPTURE
        elif "camera" in message_lower:
            return LogEmoji.CAMERA
        elif "video" in message_lower:
            return LogEmoji.VIDEO
        elif "image" in message_lower:
            return LogEmoji.IMAGE
        elif "thumbnail" in message_lower:
            return LogEmoji.THUMBNAIL
        elif "health" in message_lower:
            return LogEmoji.HEALTH
        elif "cleanup" in message_lower:
            return LogEmoji.CLEANUP
        elif "startup" in message_lower:
            return LogEmoji.STARTUP
        elif "shutdown" in message_lower:
            return LogEmoji.SHUTDOWN
        
        # Level-based emoji suggestions
        if level == LogLevel.ERROR:
            return LogEmoji.ERROR
        elif level == LogLevel.CRITICAL:
            return LogEmoji.CRITICAL
        elif level == LogLevel.WARNING:
            return LogEmoji.WARNING
        elif level == LogLevel.DEBUG:
            return LogEmoji.DEBUG
        elif level == LogLevel.INFO:
            return LogEmoji.INFO
        
        # Source-based emoji suggestions
        if source == LogSource.CAMERA:
            return LogEmoji.CAMERA
        elif source == LogSource.WORKER:
            return LogEmoji.WORKER
        elif source == LogSource.SYSTEM:
            return LogEmoji.SYSTEM
        elif source == LogSource.API:
            return LogEmoji.INCOMING
        elif source == LogSource.DATABASE:
            return LogEmoji.DATABASE
        elif source == LogSource.SCHEDULER:
            return LogEmoji.SCHEDULER
        
        # Logger name-based suggestions
        logger_lower = logger_name.value.lower()
        if "capture" in logger_lower:
            return LogEmoji.CAPTURE
        elif "thumbnail" in logger_lower:
            return LogEmoji.THUMBNAIL
        elif "video" in logger_lower:
            return LogEmoji.VIDEO
        elif "scheduler" in logger_lower:
            return LogEmoji.SCHEDULER
        elif "health" in logger_lower:
            return LogEmoji.HEALTH
        elif "error" in logger_lower:
            return LogEmoji.ERROR
        
        # Context-based suggestions
        if context:
            if "camera_id" in context:
                return LogEmoji.CAMERA
            elif "job_id" in context:
                return LogEmoji.JOB
            elif "error" in context or "exception" in context:
                return LogEmoji.ERROR
        
        # Default: no emoji suggestion
        return None
    
    def _apply_level_formatting(self, message: str, level: LogLevel) -> str:
        """
        Apply level-specific formatting to the message.
        
        Args:
            message: Message to format
            level: Log level
            
        Returns:
            Formatted message
        """
        # For now, no special level formatting beyond emoji
        # This could be extended for special formatting per level
        return message
    
    def _apply_source_formatting(self, message: str, source: LogSource, logger_name: LoggerName) -> str:
        """
        Apply source-specific formatting enhancements.
        
        Args:
            message: Message to format
            source: Log source
            logger_name: Logger name
            
        Returns:
            Formatted message
        """
        # Add worker name to worker messages if not already present
        if source == LogSource.WORKER and not message.startswith("["):
            worker_name = logger_name.value.replace("_worker", "").replace("_", " ").title()
            if worker_name.lower() not in message.lower():
                message = f"[{worker_name}] {message}"
        
        return message
    
    def _integrate_context(self, message: str, context: Dict[str, Any]) -> str:
        """
        Integrate important context data into the message.
        
        Args:
            message: Message to enhance
            context: Context data
            
        Returns:
            Enhanced message with context
        """
        # Add camera ID if present and not already in message
        if "camera_id" in context and "camera" not in message.lower():
            camera_id = context["camera_id"]
            message = f"{message} (Camera {camera_id})"
        
        # Add job ID for worker logs if present
        if "job_id" in context and "job" not in message.lower():
            job_id = context["job_id"]
            message = f"{message} (Job {job_id})"
        
        # Add error information for error contexts
        if "error" in context and "error" not in message.lower():
            error_msg = str(context["error"])[:50]  # Limit length
            if error_msg:
                message = f"{message} - {error_msg}"
        
        return message
    
    def format_structured_message(
        self,
        template: str,
        **template_vars
    ) -> str:
        """
        Format a structured message using a template.
        
        Args:
            template: Message template with placeholders
            **template_vars: Variables to substitute in template
            
        Returns:
            Formatted message
        """
        try:
            return template.format(**template_vars)
        except Exception as e:
            print(f"LogMessageFormatter.format_structured_message failed: {e}")
            return template
    
    def create_performance_message(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a standardized performance log message.
        
        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation was successful
            additional_info: Additional performance metrics
            
        Returns:
            Formatted performance message
        """
        status_emoji = "✅" if success else "💥"
        
        if duration_ms < 100:
            duration_str = f"{duration_ms:.1f}ms"
        elif duration_ms < 1000:
            duration_str = f"{duration_ms:.0f}ms"
        else:
            duration_str = f"{duration_ms/1000:.1f}s"
        
        message = f"{status_emoji} {operation} completed in {duration_str}"
        
        if additional_info:
            info_parts = []
            for key, value in additional_info.items():
                info_parts.append(f"{key}={value}")
            if info_parts:
                message += f" ({', '.join(info_parts)})"
        
        return message
    
    def create_error_message(
        self,
        operation: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a standardized error log message.
        
        Args:
            operation: Operation that failed
            error: Exception object
            context: Additional error context
            
        Returns:
            Formatted error message
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        message = f"💥 {operation} failed: {error_type} - {error_msg}"
        
        if context:
            context_parts = []
            for key, value in context.items():
                if key not in ["error", "exception"]:  # Don't duplicate error info
                    context_parts.append(f"{key}={value}")
            if context_parts:
                message += f" ({', '.join(context_parts)})"
        
        return message
    
    def create_status_message(
        self,
        component: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a standardized status log message.
        
        Args:
            component: Component name
            status: Status description
            details: Additional status details
            
        Returns:
            Formatted status message
        """
        # Choose emoji based on status
        status_lower = status.lower()
        if "start" in status_lower or "active" in status_lower:
            emoji = "▶️"
        elif "stop" in status_lower or "inactive" in status_lower:
            emoji = "⏹️"
        elif "healthy" in status_lower or "ok" in status_lower:
            emoji = "💓"
        elif "error" in status_lower or "failed" in status_lower:
            emoji = "💥"
        elif "warning" in status_lower:
            emoji = "⚠️"
        else:
            emoji = "ℹ️"
        
        message = f"{emoji} {component} {status}"
        
        if details:
            detail_parts = []
            for key, value in details.items():
                detail_parts.append(f"{key}={value}")
            if detail_parts:
                message += f" ({', '.join(detail_parts)})"
        
        return message