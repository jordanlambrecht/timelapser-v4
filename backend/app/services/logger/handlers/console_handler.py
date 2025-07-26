"""
Console Handler for the Logger Service.

This handler outputs logs to console with emoji support, color formatting,
and proper level-based styling. It provides immediate visual feedback
for development and production monitoring.
"""

import sys
from typing import Dict, Any, Optional
from datetime import datetime

from ....enums import LogLevel, LogSource


class ConsoleHandler:
    """
    Console handler that outputs logs to stdout with emoji support and color formatting.
    
    Features:
    - Color-coded log levels (using ANSI color codes)
    - Emoji support for visual clarity
    - Proper timestamp formatting
    - Level-based filtering
    - Health status tracking
    """
    
    # ANSI color codes for different log levels
    COLORS = {
        LogLevel.DEBUG: "\033[36m",      # Cyan
        LogLevel.INFO: "\033[32m",       # Green
        LogLevel.WARNING: "\033[33m",    # Yellow
        LogLevel.ERROR: "\033[31m",      # Red
        LogLevel.CRITICAL: "\033[35m",   # Magenta
    }
    
    # Reset color code
    RESET = "\033[0m"
    
    # Bold text
    BOLD = "\033[1m"
    
    # Dim text
    DIM = "\033[2m"
    
    def __init__(
        self, 
        min_level: LogLevel = LogLevel.DEBUG,
        use_colors: bool = True,
        include_timestamp: bool = True,
        include_source: bool = True
    ):
        """
        Initialize the console handler.
        
        Args:
            min_level: Minimum log level to output (default: DEBUG)
            use_colors: Whether to use ANSI colors (default: True)
            include_timestamp: Whether to include timestamps (default: True)
            include_source: Whether to include source information (default: True)
        """
        self.min_level = min_level
        self.use_colors = use_colors
        self.include_timestamp = include_timestamp
        self.include_source = include_source
        self._healthy = True
        
        # Check if stdout supports colors (for production environments)
        if not sys.stdout.isatty():
            self.use_colors = False
    
    def handle(
        self, 
        message: str, 
        level: LogLevel, 
        source: LogSource,
        logger_name: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Handle console output for a log entry.
        
        Args:
            message: The formatted log message
            level: Log level
            source: Log source
            logger_name: Optional logger name
            timestamp: Optional timestamp (defaults to now)
        """
        try:
            # Check if we should output this log level
            if not self._should_log_level(level):
                return
            
            # Use current time if timestamp not provided
            if timestamp is None:
                timestamp = datetime.now()
            
            # Build console output
            output_parts = []
            
            # Add timestamp if enabled
            if self.include_timestamp:
                timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if self.use_colors:
                    output_parts.append(f"{self.DIM}[{timestamp_str}]{self.RESET}")
                else:
                    output_parts.append(f"[{timestamp_str}]")
            
            # Add log level with color
            level_str = self._format_level(level)
            output_parts.append(level_str)
            
            # Add source if enabled
            if self.include_source:
                source_str = self._format_source(source, logger_name)
                output_parts.append(source_str)
            
            # Add the message
            output_parts.append(message)
            
            # Combine and output
            formatted_output = " ".join(output_parts)
            print(formatted_output, file=sys.stdout)
            
            # Flush for immediate output
            sys.stdout.flush()
            
        except Exception as e:
            # Don't break the application if console output fails
            self._healthy = False
            # Fallback to basic print
            try:
                print(f"[CONSOLE_HANDLER_ERROR] {message}", file=sys.stderr)
                print(f"[CONSOLE_HANDLER_ERROR] Handler error: {e}", file=sys.stderr)
            except:
                pass  # If even stderr fails, give up silently
    
    def _should_log_level(self, level: LogLevel) -> bool:
        """
        Check if the given log level should be output.
        
        Args:
            level: Log level to check
            
        Returns:
            True if level should be logged
        """
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        
        return level_order.get(level, 0) >= level_order.get(self.min_level, 0)
    
    def _format_level(self, level: LogLevel) -> str:
        """
        Format the log level with appropriate colors and styling.
        
        Args:
            level: Log level to format
            
        Returns:
            Formatted level string
        """
        level_name = level.value
        
        if self.use_colors:
            color = self.COLORS.get(level, "")
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                # Make errors bold for visibility
                return f"{color}{self.BOLD}[{level_name}]{self.RESET}"
            else:
                return f"{color}[{level_name}]{self.RESET}"
        else:
            return f"[{level_name}]"
    
    def _format_source(self, source: LogSource, logger_name: Optional[str] = None) -> str:
        """
        Format the source and logger name information.
        
        Args:
            source: Log source
            logger_name: Optional logger name
            
        Returns:
            Formatted source string
        """
        if logger_name:
            source_str = f"{source.value}:{logger_name}"
        else:
            source_str = source.value
        
        if self.use_colors:
            return f"{self.DIM}({source_str}){self.RESET}"
        else:
            return f"({source_str})"
    
    def set_min_level(self, level: LogLevel) -> None:
        """
        Update the minimum log level for console output.
        
        Args:
            level: New minimum log level
        """
        self.min_level = level
    
    def is_healthy(self) -> bool:
        """
        Check if the console handler is in a healthy state.
        
        Returns:
            True if handler is healthy
        """
        return self._healthy
    
    def reset_health(self) -> None:
        """
        Reset the health status of the handler.
        
        This can be called if console output issues are resolved.
        """
        self._healthy = True


class DevConsoleHandler(ConsoleHandler):
    """
    Enhanced console handler specifically for development environments.
    
    Includes additional debugging features:
    - More detailed source information
    - Context data preview
    - Enhanced emoji and color usage
    """
    
    def __init__(self, **kwargs):
        """Initialize development console handler with enhanced defaults."""
        super().__init__(
            min_level=LogLevel.DEBUG,  # Show all logs in dev
            use_colors=True,
            include_timestamp=True,
            include_source=True,
            **kwargs
        )
    
    def handle(
        self, 
        message: str, 
        level: LogLevel, 
        source: LogSource,
        logger_name: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enhanced handle method that includes context preview for development.
        
        Args:
            message: The formatted log message
            level: Log level
            source: Log source
            logger_name: Optional logger name
            timestamp: Optional timestamp
            context: Optional context data to preview
        """
        # Call parent handler first
        super().handle(message, level, source, logger_name, timestamp)
        
        # Add context preview for development (if context is significant)
        if context and len(context) > 0 and self._should_show_context(context):
            context_preview = self._format_context_preview(context)
            if context_preview:
                if self.use_colors:
                    print(f"  {self.DIM}↳ {context_preview}{self.RESET}", file=sys.stdout)
                else:
                    print(f"  ↳ {context_preview}", file=sys.stdout)
                sys.stdout.flush()
    
    def _should_show_context(self, context: Dict[str, Any]) -> bool:
        """
        Determine if context should be shown for this log entry.
        
        Args:
            context: Context dictionary
            
        Returns:
            True if context should be displayed
        """
        # Show context for errors and warnings
        # Skip context for very basic/common entries
        if not context:
            return False
        
        # Skip if only timestamp or very basic info
        basic_keys = {"timestamp", "level", "source", "logger_name"}
        interesting_keys = set(context.keys()) - basic_keys
        
        return len(interesting_keys) > 0
    
    def _format_context_preview(self, context: Dict[str, Any]) -> str:
        """
        Format context data for preview display.
        
        Args:
            context: Context dictionary
            
        Returns:
            Formatted context preview string
        """
        try:
            # Show most interesting context items (limit to avoid noise)
            preview_items = []
            
            # Prioritize certain keys
            priority_keys = ["error", "exception", "camera_id", "job_id", "image_id", "worker_name"]
            
            for key in priority_keys:
                if key in context:
                    value = context[key]
                    preview_items.append(f"{key}={value}")
                    if len(preview_items) >= 3:  # Limit preview length
                        break
            
            # Add other interesting keys if we have room
            if len(preview_items) < 3:
                for key, value in context.items():
                    if key not in priority_keys and key not in {"timestamp", "level", "source", "logger_name"}:
                        preview_items.append(f"{key}={value}")
                        if len(preview_items) >= 3:
                            break
            
            return ", ".join(preview_items) if preview_items else ""
            
        except Exception:
            return "context_preview_error"


class ProductionConsoleHandler(ConsoleHandler):
    """
    Console handler optimized for production environments.
    
    Features:
    - Higher minimum log level (INFO by default)
    - No colors (safe for log aggregation)
    - Structured output format
    - Minimal performance impact
    """
    
    def __init__(self, **kwargs):
        """Initialize production console handler with production defaults."""
        super().__init__(
            min_level=LogLevel.INFO,   # Hide debug logs in production
            use_colors=False,          # No colors for log aggregation
            include_timestamp=True,
            include_source=True,
            **kwargs
        )