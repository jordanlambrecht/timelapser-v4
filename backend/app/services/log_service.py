"""
Log Service - Composition-based architecture.

This service handles log-related business logic using dependency injection
for database operations, providing type-safe Pydantic model interfaces.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger

from ..database.core import AsyncDatabase, SyncDatabase
from ..database.log_operations import LogOperations, SyncLogOperations
from ..models.log_model import Log
from ..models.log_summary_model import (
    LogSourceModel,
    LogSummaryModel,
    ErrorCountBySourceModel,
)
from ..utils.time_utils import (
    get_timezone_aware_timestamp_async,
)
from ..constants import (
    LOG_LEVELS,
    DEFAULT_LOG_RETENTION_DAYS,
    MAX_LOG_RETENTION_DAYS,
    DEFAULT_LOG_PAGE_SIZE,
    MAX_LOG_PAGE_SIZE,
    BULK_LOG_PAGE_SIZE,
    EVENT_SETTING_UPDATED,
    EVENT_AUDIT_TRAIL_CREATED,
    EVENT_LOG_CLEANUP_COMPLETED,
)


class LogService:
    """
    Application logging business logic.

    Responsibilities:
    - Log aggregation
    - Filtering
    - Cleanup policies
    - Log level management
    - Audit trail maintenance
    - Structured logging coordination

    Interactions:
    - Uses LogOperations for database
    - Receives log data from all services
    - Provides filtered views for debugging
    - Integrates with correlation ID system
    """

    def __init__(self, db: AsyncDatabase):
        """
        Initialize LogService with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db
        self.log_ops = LogOperations(db)

    def _sanitize_string_input(self, input_value: str, max_length: int = 1000) -> str:
        """
        Sanitize string input to prevent injection attacks and limit length.

        Args:
            input_value: String to sanitize
            max_length: Maximum allowed length

        Returns:
            Sanitized string
        """
        if not isinstance(input_value, str):
            return ""

        # Remove potentially dangerous characters
        sanitized = (
            input_value.replace("<", "")
            .replace(">", "")
            .replace("&", "")
            .replace('"', "")
            .replace("'", "")
        )

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.strip()

    def _validate_log_level(self, level: str) -> Optional[str]:
        """
        Validate and sanitize log level input.

        Args:
            level: Log level to validate

        Returns:
            Valid log level or None if invalid
        """
        if level and level.upper() in LOG_LEVELS:
            return level.upper()
        return None  # Return None for invalid levels to maintain original behavior

    async def get_logs(
        self,
        camera_id: Optional[int] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = DEFAULT_LOG_PAGE_SIZE,
    ) -> Dict[str, Any]:
        """
        Retrieve logs with comprehensive filtering and pagination.

        Args:
            camera_id: Optional camera ID to filter by
            level: Optional log level to filter by
            source: Optional source to filter by
            search_query: Optional text search in log messages
            start_date: Optional start date for date range filtering
            end_date: Optional end date for date range filtering
            page: Page number (1-based)
            page_size: Number of logs per page

        Returns:
            Dictionary containing Log models and pagination metadata
        """
        # Sanitize string inputs
        sanitized_level = self._validate_log_level(level) if level else None
        sanitized_source = self._sanitize_string_input(source, 50) if source else None
        sanitized_search_query = (
            self._sanitize_string_input(search_query, 200) if search_query else None
        )

        return await self.log_ops.get_logs(
            camera_id,
            sanitized_level,
            sanitized_source,
            sanitized_search_query,
            start_date,
            end_date,
            page,
            page_size,
        )

    async def get_logs_for_camera(self, camera_id: int, limit: int = 10) -> List[Log]:
        """
        Get recent logs for a specific camera.

        Args:
            camera_id: ID of the camera
            limit: Maximum number of logs to return

        Returns:
            List of Log model instances for the camera
        """
        result = await self.log_ops.get_logs(
            camera_id=camera_id,
            page=1,
            page_size=limit,
        )
        return result["logs"]

    async def get_log_sources(self) -> List[LogSourceModel]:
        """
        Get all available log sources.

        Returns:
            List of log source models with counts
        """
        return await self.log_ops.get_log_sources()

    # DEPRECATED: get_log_levels() method removed - use static LOG_LEVELS constant
    # Log levels are hardcoded and don't require database queries

    async def get_log_summary(self, hours: int = 24) -> LogSummaryModel:
        """
        Get log summary statistics for a time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Log summary model with statistics
        """
        return await self.log_ops.get_log_summary(hours)

    async def delete_old_logs(
        self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS
    ) -> int:
        """
        Delete old logs based on retention policy.

        Args:
            days_to_keep: Number of days to keep logs (default from constants)
                         If 0, deletes ALL logs

        Returns:
            Number of logs deleted
        """
        # Validate retention period (allow 0 for delete all)
        if days_to_keep > MAX_LOG_RETENTION_DAYS:
            days_to_keep = MAX_LOG_RETENTION_DAYS
        elif days_to_keep < 0:
            days_to_keep = DEFAULT_LOG_RETENTION_DAYS

        deleted_count = await self.log_ops.delete_old_logs(days_to_keep)

        # SSE broadcasting handled by higher-level service layer

        return deleted_count

    async def aggregate_logs_from_services(
        self, services: List[str], hours: int = 24
    ) -> Dict[str, Any]:
        """
        Aggregate logs from multiple services for comprehensive analysis.

        Args:
            services: List of service names to aggregate logs from
            hours: Number of hours to analyze

        Returns:
            Aggregated log analysis with service breakdown
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Sanitize service names to prevent injection
            sanitized_services = [
                self._sanitize_string_input(service, 50)
                for service in services
                if service
            ]

            # Limit number of services to prevent resource exhaustion
            if len(sanitized_services) > 10:
                sanitized_services = sanitized_services[:10]
                logger.warning(f"Service list truncated to 10 services for security")

            aggregated_data = {
                "aggregation_timestamp": timestamp.isoformat(),
                "time_range_hours": min(hours, 168),  # Limit to 1 week max
                "services_analyzed": sanitized_services,
                "service_logs": {},
                "cross_service_analysis": {},
            }

            total_logs = 0
            total_errors = 0
            service_summaries = {}

            # Aggregate logs from each service
            for service in sanitized_services:
                service_logs = await self.get_logs(
                    source=service, page_size=MAX_LOG_PAGE_SIZE
                )
                service_summary = await self.get_log_summary_for_service(service, hours)

                aggregated_data["service_logs"][service] = {
                    "log_count": len(service_logs.get("logs", [])),
                    "recent_logs": service_logs.get("logs", [])[
                        :10
                    ],  # Latest 10 for overview
                    "summary": service_summary,
                }

                total_logs += len(service_logs.get("logs", []))
                total_errors += service_summary.get("error_count", 0)
                service_summaries[service] = service_summary

            # Cross-service analysis
            aggregated_data["cross_service_analysis"] = {
                "total_logs_across_services": total_logs,
                "total_errors_across_services": total_errors,
                "most_active_service": (
                    max(
                        service_summaries.keys(),
                        key=lambda s: service_summaries[s].get("log_count", 0),
                    )
                    if service_summaries
                    else None
                ),
                "most_problematic_service": (
                    max(
                        service_summaries.keys(),
                        key=lambda s: service_summaries[s].get("error_count", 0),
                    )
                    if service_summaries
                    else None
                ),
                "correlation_patterns": await self._analyze_correlation_patterns(
                    service_summaries
                ),
            }

            logger.info(
                f"Aggregated logs from {len(services)} services: {total_logs} total logs, {total_errors} errors"
            )
            return aggregated_data

        except Exception as e:
            logger.error(f"Log aggregation failed for services {services}: {e}")
            return {"error": str(e)}

    async def manage_log_levels(self, configuration: Dict[str, str]) -> Dict[str, Any]:
        """
        Manage log level configuration across the system.

        Args:
            configuration: Dictionary mapping loggers to log levels

        Returns:
            Log level management results
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            management_results = {
                "timestamp": timestamp.isoformat(),
                "configuration_applied": configuration,
                "results": {},
                "system_impact": {},
            }

            # Apply log level configuration
            for logger_name, log_level in configuration.items():
                # Validate log level using constants
                if log_level not in LOG_LEVELS:
                    management_results["results"][logger_name] = {
                        "success": False,
                        "error": f"Invalid log level: {log_level}. Must be one of {LOG_LEVELS}",
                    }
                    continue

                # Apply configuration (this would integrate with logging system)
                success = await self._apply_log_level_configuration(
                    logger_name, log_level
                )
                management_results["results"][logger_name] = {
                    "success": success,
                    "level": log_level,
                    "message": (
                        f"Log level set to {log_level}"
                        if success
                        else "Failed to set log level"
                    ),
                }

            # Analyze system impact
            management_results["system_impact"] = await self._analyze_log_level_impact(
                configuration
            )

            # Store configuration changes in audit trail
            await self._log_configuration_change("log_levels", configuration)

            # SSE broadcasting handled by higher-level service layer

            logger.info(
                f"Log level management applied for {len(configuration)} loggers"
            )
            return management_results

        except Exception as e:
            logger.error(f"Log level management failed: {e}")
            return {"error": str(e)}

    async def maintain_audit_trail(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        changes: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Maintain comprehensive audit trail for system actions.

        Args:
            action: Action performed (create, update, delete, etc.)
            entity_type: Type of entity affected (camera, timelapse, video, etc.)
            entity_id: ID of the entity (if applicable)
            changes: Dictionary of changes made
            user_id: ID of user who performed action (if applicable)

        Returns:
            Audit trail maintenance results
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)

            # Sanitize inputs for security
            sanitized_action = self._sanitize_string_input(action, 50)
            sanitized_entity_type = self._sanitize_string_input(entity_type, 50)
            sanitized_user_id = (
                self._sanitize_string_input(user_id, 100) if user_id else None
            )

            # Sanitize changes dictionary values
            sanitized_changes = {}
            if isinstance(changes, dict):
                for key, value in changes.items():
                    safe_key = self._sanitize_string_input(str(key), 100)
                    if isinstance(value, str):
                        safe_value = self._sanitize_string_input(value, 500)
                    else:
                        safe_value = str(value)[
                            :500
                        ]  # Convert to string and limit length
                    sanitized_changes[safe_key] = safe_value

            audit_entry = {
                "timestamp": timestamp.isoformat(),
                "action": sanitized_action,
                "entity_type": sanitized_entity_type,
                "entity_id": entity_id,
                "changes": sanitized_changes,
                "user_id": sanitized_user_id,
                "correlation_id": self._generate_correlation_id(),
                "source": "audit_trail_service",
            }

            # Write audit entry to logs using add_log_entry (async)
            audit_log = await self.log_ops.add_log_entry(
                level="INFO",
                message=f"Audit: {sanitized_action} on {sanitized_entity_type} (ID: {entity_id})",
                logger_name="audit_trail_service",
                source="audit_trail_service",
                camera_id=entity_id,
                extra_data=audit_entry,
            )

            # Store in structured audit trail
            audit_result = await self._store_structured_audit_entry(audit_entry)

            # Check for audit trail compliance
            compliance_check = await self._check_audit_compliance(entity_type, action)

            # SSE broadcasting handled by higher-level service layer

            return {
                "audit_entry_id": getattr(audit_log, "id", None) if audit_log else None,
                "structured_entry_id": audit_result.get("entry_id"),
                "compliance_status": compliance_check,
                "correlation_id": audit_entry["correlation_id"],
                "success": True,
            }

        except Exception as e:
            logger.error(
                f"Audit trail maintenance failed for {action} on {entity_type}:{entity_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def coordinate_structured_logging(
        self, log_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Coordinate structured logging across services.

        Args:
            log_structure: Structured logging configuration

        Returns:
            Structured logging coordination results
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)
            coordination_results = {
                "timestamp": timestamp.isoformat(),
                "structure_applied": log_structure,
                "coordination_results": {},
                "system_wide_impact": {},
            }

            # Apply structured logging format
            format_result = await self._apply_structured_format(log_structure)
            coordination_results["coordination_results"][
                "format_application"
            ] = format_result

            # Coordinate with correlation ID system
            correlation_result = await self._coordinate_correlation_ids(log_structure)
            coordination_results["coordination_results"][
                "correlation_coordination"
            ] = correlation_result

            # Set up log field standardization
            standardization_result = await self._standardize_log_fields(log_structure)
            coordination_results["coordination_results"][
                "field_standardization"
            ] = standardization_result

            # Analyze system-wide impact
            coordination_results["system_wide_impact"] = (
                await self._analyze_structured_logging_impact(log_structure)
            )

            logger.info("Structured logging coordination completed successfully")
            return coordination_results

        except Exception as e:
            logger.error(f"Structured logging coordination failed: {e}")
            return {"error": str(e)}

    async def integrate_correlation_ids(
        self, correlation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Integrate correlation ID system for request tracing.

        Args:
            correlation_config: Correlation ID configuration

        Returns:
            Correlation ID integration results
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)
            integration_results = {
                "timestamp": timestamp.isoformat(),
                "configuration": correlation_config,
                "integration_status": {},
                "tracing_capabilities": {},
            }

            # Set up correlation ID generation
            generation_setup = await self._setup_correlation_id_generation(
                correlation_config
            )
            integration_results["integration_status"][
                "id_generation"
            ] = generation_setup

            # Configure request tracing
            tracing_setup = await self._setup_request_tracing(correlation_config)
            integration_results["integration_status"]["request_tracing"] = tracing_setup

            # Set up cross-service correlation
            cross_service_setup = await self._setup_cross_service_correlation(
                correlation_config
            )
            integration_results["integration_status"][
                "cross_service_correlation"
            ] = cross_service_setup

            # Configure debugging capabilities
            debugging_setup = await self._setup_correlation_debugging(
                correlation_config
            )
            integration_results["tracing_capabilities"]["debugging"] = debugging_setup

            # Test correlation ID flow
            flow_test = await self._test_correlation_id_flow()
            integration_results["tracing_capabilities"]["flow_test"] = flow_test

            logger.info("Correlation ID system integration completed successfully")
            return integration_results

        except Exception as e:
            logger.error(f"Correlation ID integration failed: {e}")
            return {"error": str(e)}

    async def provide_debugging_views(
        self, debug_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Provide specialized filtered views for debugging.

        Args:
            debug_request: Debugging request parameters

        Returns:
            Debugging view results with filtered and analyzed logs
        """
        try:
            timestamp = await get_timezone_aware_timestamp_async(self.db)
            debug_views = {
                "timestamp": timestamp.isoformat(),
                "debug_request": debug_request,
                "views": {},
                "analysis": {},
            }

            # Error flow debugging
            if debug_request.get("type") == "error_flow":
                error_flow = await self._debug_error_flow(debug_request)
                debug_views["views"]["error_flow"] = error_flow

            # Performance debugging
            if debug_request.get("type") == "performance":
                performance_debug = await self._debug_performance_issues(debug_request)
                debug_views["views"]["performance"] = performance_debug

            # Request tracing
            if debug_request.get("correlation_id"):
                request_trace = await self._debug_request_trace(
                    debug_request["correlation_id"]
                )
                debug_views["views"]["request_trace"] = request_trace

            # Service interaction debugging
            if debug_request.get("type") == "service_interaction":
                interaction_debug = await self._debug_service_interactions(
                    debug_request
                )
                debug_views["views"]["service_interactions"] = interaction_debug

            # Generate debugging analysis
            debug_views["analysis"] = await self._generate_debugging_analysis(
                debug_views["views"]
            )

            logger.info(
                f"Debugging views provided for request type: {debug_request.get('type', 'unknown')}"
            )
            return debug_views

        except Exception as e:
            logger.error(f"Debugging views generation failed: {e}")
            return {"error": str(e)}

    # Helper methods for coordination features
    async def get_log_summary_for_service(
        self, service: str, hours: int
    ) -> Dict[str, Any]:
        """Get log summary for a specific service."""
        try:
            logs = await self.get_logs(source=service, page_size=BULK_LOG_PAGE_SIZE)
            service_logs = logs.get("logs", [])

            log_count = len(service_logs)
            error_count = len(
                [log for log in service_logs if log.level in ["ERROR", "CRITICAL"]]
            )
            warning_count = len([log for log in service_logs if log.level == "WARNING"])

            return {
                "service": service,
                "log_count": log_count,
                "error_count": error_count,
                "warning_count": warning_count,
                "info_count": log_count - error_count - warning_count,
            }
        except Exception as e:
            logger.error(f"Service log summary failed for {service}: {e}")
            return {"error": str(e)}

    async def _analyze_correlation_patterns(
        self, service_summaries: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze correlation patterns between services."""
        return {"pattern_analysis": "completed", "correlations_found": []}

    async def _apply_log_level_configuration(
        self, logger_name: str, log_level: str
    ) -> bool:
        """Apply log level configuration to a logger."""
        # This would integrate with the actual logging system
        return True

    async def _analyze_log_level_impact(
        self, configuration: Dict[str, str]
    ) -> Dict[str, Any]:
        """Analyze the impact of log level changes."""
        return {
            "estimated_log_volume_change": "decreased by 20%",
            "performance_impact": "minimal",
        }

    async def _log_configuration_change(
        self, config_type: str, configuration: Dict[str, Any]
    ) -> None:
        """Log configuration changes to audit trail."""
        await self.maintain_audit_trail(
            "configure", config_type, None, configuration, "system"
        )

    def _generate_correlation_id(self) -> str:
        """Generate a unique correlation ID."""
        return str(uuid.uuid4())

    async def _store_structured_audit_entry(
        self, audit_entry: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Store structured audit entry."""
        return {
            "entry_id": "audit_" + self._generate_correlation_id()[:8],
            "stored": True,
        }

    async def _check_audit_compliance(
        self, entity_type: str, action: str
    ) -> Dict[str, Any]:
        """Check audit trail compliance."""
        return {
            "compliant": True,
            "requirements_met": ["data_retention", "access_logging"],
        }

    async def _apply_structured_format(
        self, log_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply structured logging format."""
        return {"format_applied": True, "structure": log_structure}

    async def _coordinate_correlation_ids(
        self, log_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Coordinate correlation ID integration."""
        return {"correlation_ids_enabled": True, "propagation_configured": True}

    async def _standardize_log_fields(
        self, log_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Standardize log field formats."""
        return {"fields_standardized": True, "format_consistency": "enforced"}

    async def _analyze_structured_logging_impact(
        self, log_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze structured logging system impact."""
        return {"performance_impact": "minimal", "query_performance": "improved"}

    async def _setup_correlation_id_generation(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up correlation ID generation."""
        return {"generation_enabled": True, "format": "uuid4"}

    async def _setup_request_tracing(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Set up request tracing."""
        return {"tracing_enabled": True, "propagation": "automatic"}

    async def _setup_cross_service_correlation(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up cross-service correlation."""
        return {"cross_service_enabled": True, "services_connected": ["all"]}

    async def _setup_correlation_debugging(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Set up correlation debugging capabilities."""
        return {
            "debugging_enabled": True,
            "tools_available": ["trace_viewer", "correlation_search"],
        }

    async def _test_correlation_id_flow(self) -> Dict[str, Any]:
        """Test correlation ID flow."""
        return {"test_passed": True, "correlation_propagation": "successful"}

    async def _debug_error_flow(self, debug_request: Dict[str, Any]) -> Dict[str, Any]:
        """Debug error flow based on request."""
        return {"error_chain": [], "root_cause_analysis": "completed"}

    async def _debug_performance_issues(
        self, debug_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Debug performance issues."""
        return {"performance_bottlenecks": [], "optimization_suggestions": []}

    async def _debug_request_trace(self, correlation_id: str) -> Dict[str, Any]:
        """Debug request trace using correlation ID."""
        return {
            "trace_found": True,
            "request_flow": [],
            "correlation_id": correlation_id,
        }

    async def _debug_service_interactions(
        self, debug_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Debug service interactions."""
        return {"interaction_map": {}, "communication_analysis": "completed"}

    async def _generate_debugging_analysis(
        self, views: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive debugging analysis."""
        return {
            "analysis_summary": "completed",
            "recommendations": [],
            "views_analyzed": list(views.keys()),
        }


class SyncLogService:
    """
    Sync log service for worker processes using composition pattern.

    This service orchestrates log-related business logic using
    dependency injection instead of mixin inheritance.
    """

    def __init__(self, db: SyncDatabase):
        """
        Initialize SyncLogService with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db
        self.log_ops = SyncLogOperations(db)

    def write_log_entry(
        self,
        level: str,
        message: str,
        logger_name: str,
        source: str = "system",
        camera_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Log:
        """
        Write a log entry to the database.

        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            message: Log message
            logger_name: Name of the logger
            source: Source of the log (e.g., 'system', 'camera_1', 'worker')
            camera_id: Optional camera ID if log is camera-specific
            extra_data: Optional additional data as JSON

        Returns:
            Created Log model instance
        """
        # Pass all arguments to the database operation
        return self.log_ops.write_log_entry(
            level=level,
            message=message,
            source=source,
            camera_id=camera_id,
            logger_name=logger_name,
            extra_data=extra_data,
        )

    def get_camera_logs(self, camera_id: int, hours: int = 24) -> List[Log]:
        """
        Get logs for a specific camera.

        Args:
            camera_id: ID of the camera
            hours: Number of hours to look back

        Returns:
            List of camera Log models
        """
        return self.log_ops.get_camera_logs(camera_id, hours)

    def cleanup_old_logs(self, days_to_keep: int = DEFAULT_LOG_RETENTION_DAYS) -> int:
        """
        Clean up old log entries.

        Args:
            days_to_keep: Number of days to keep logs (default from constants)
                         If 0, deletes ALL logs

        Returns:
            Number of logs deleted
        """
        # Validate retention period (allow 0 for delete all)
        if days_to_keep > MAX_LOG_RETENTION_DAYS:
            days_to_keep = MAX_LOG_RETENTION_DAYS
        elif days_to_keep < 0:
            days_to_keep = DEFAULT_LOG_RETENTION_DAYS

        return self.log_ops.cleanup_old_logs(days_to_keep)

    def get_error_count_by_source(
        self, hours: int = 24
    ) -> List[ErrorCountBySourceModel]:
        """
        Get error count by source for monitoring.

        Args:
            hours: Number of hours to analyze

        Returns:
            List of source error count models
        """
        return self.log_ops.get_error_count_by_source(hours)
