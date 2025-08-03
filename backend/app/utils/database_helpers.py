# backend/app/utils/database_helpers.py
"""
Database Helper Functions

Common database operation patterns and utilities to reduce duplication
between AsyncDatabase and SyncDatabase classes.
"""
import asyncio
import json
import os
import time
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, Union

import psutil

from ..enums import LoggerName, LogSource
from ..services.logger.logger_service import get_service_logger
from .time_utils import utc_now

logger = get_service_logger(LoggerName.SYSTEM, LogSource.DATABASE)


class DatabaseQueryBuilder:
    """
    Helper class for building dynamic SQL queries.

    Provides methods to build common query patterns with proper parameterization
    and security considerations.
    """

    @staticmethod
    def build_select_query(
        table_name: str,
        fields: Optional[List[str]] = None,
        joins: Optional[List[str]] = None,
        where_clauses: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a SELECT query with dynamic conditions.

        Args:
            table_name: Primary table name
            fields: List of fields to select (defaults to *)
            joins: List of JOIN clauses
            where_clauses: List of WHERE clause strings (parameterized)
            params: Dict of parameters for WHERE clause
            order_by: ORDER BY clause
            limit: LIMIT value
            offset: OFFSET value

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        select_clause = ", ".join(fields) if fields else "*"
        query_parts = [f"SELECT {select_clause} FROM {table_name}"]
        if joins:
            query_parts.extend(joins)
        if where_clauses:
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")
        if order_by:
            query_parts.append(f"ORDER BY {order_by}")
        if limit is not None:
            query_parts.append(f"LIMIT %(limit)s")
            if params is not None:
                params["limit"] = limit
        if offset is not None:
            query_parts.append(f"OFFSET %(offset)s")
            if params is not None:
                params["offset"] = offset
        return " ".join(query_parts), params or {}

    @staticmethod
    def build_update_query(
        table_name: str,
        updates: Dict[str, Any],
        where_conditions: Dict[str, Any],
        allowed_fields: Optional[set[str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build an UPDATE query with dynamic fields and conditions.

        Args:
            table_name: Table to update
            updates: Dictionary of field updates
            where_conditions: Dictionary of WHERE conditions
            allowed_fields: Optional set of allowed fields for security

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        # Filter updates by allowed fields if specified
        if allowed_fields:
            filtered_updates = {
                field: value
                for field, value in updates.items()
                if field in allowed_fields
            }
        else:
            filtered_updates = updates.copy()

        if not filtered_updates:
            raise ValueError("No valid fields to update")

        # Build SET clauses
        set_clauses = []
        params = {}

        for field, value in filtered_updates.items():
            set_clauses.append(f"{field} = %({field})s")
            params[field] = value

        # Always update timestamp
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        # Build WHERE clauses
        where_clauses = []
        for field, value in where_conditions.items():
            where_key = f"where_{field}"
            where_clauses.append(f"{field} = %({where_key})s")
            params[where_key] = value

        query = f"""
            UPDATE {table_name}
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(where_clauses)}
        """

        return query, params

    @staticmethod
    def build_insert_query(
        table_name: str,
        data: Dict[str, Any],
        allowed_fields: Optional[set[str]] = None,
        returning_field: str = "id",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build an INSERT query with dynamic fields.

        Args:
            table_name: Table to insert into
            data: Dictionary of field values
            allowed_fields: Optional set of allowed fields for security
            returning_field: Field to return after insert

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        # Filter data by allowed fields if specified
        if allowed_fields:
            filtered_data = {
                field: value for field, value in data.items() if field in allowed_fields
            }
        else:
            filtered_data = data.copy()

        if not filtered_data:
            raise ValueError("No valid fields to insert")

        fields = list(filtered_data.keys())
        placeholders = [f"%({field})s" for field in fields]

        query = f"""
            INSERT INTO {table_name} ({', '.join(fields)})
            VALUES ({', '.join(placeholders)})
            RETURNING {returning_field}
        """

        return query, filtered_data


class DatabaseStatsHelper:
    """
    Helper class for common database statistics and aggregation operations.
    """

    @staticmethod
    def build_stats_query(
        base_table: str,
        metrics: Dict[str, str],
        joins: Optional[List[str]] = None,
        where_conditions: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build a statistics aggregation query.

        Args:
            base_table: Primary table for stats
            metrics: Dict mapping result field names to SQL expressions
            joins: List of JOIN clauses
            where_conditions: Dict of WHERE conditions
            group_by: List of GROUP BY fields

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        # Build SELECT clause with metrics
        select_parts = []
        for result_field, sql_expression in metrics.items():
            select_parts.append(f"{sql_expression} as {result_field}")

        if group_by:
            select_parts.extend(group_by)

        query_parts = [f"SELECT {', '.join(select_parts)} FROM {base_table}"]
        params = {}

        # Add JOINs
        if joins:
            query_parts.extend(joins)

        # Add WHERE conditions
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"{field} = %({field})s")
                params[field] = value

            if where_clauses:
                query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        # Add GROUP BY
        if group_by:
            query_parts.append(f"GROUP BY {', '.join(group_by)}")

        return " ".join(query_parts), params


class CameraDataProcessor:
    """
    Utility class for processing camera data from database rows.

    Separates data transformation logic from database operations
    for better performance and maintainability.
    """

    @staticmethod
    def prepare_camera_statistics(row_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare camera statistics fields from database row data.

        Args:
            row_data: Raw database row data

        Returns:
            Dictionary with processed statistics fields
        """
        stats = {}

        # Image count statistics
        stats["image_count_lifetime"] = row_data.get("total_images", 0)
        stats["image_count_active_timelapse"] = (
            row_data.get("active_timelapse_images", 0)
            if row_data.get("timelapse_status") in ["running", "paused"]
            else 0
        )

        # Video and timelapse counts
        stats["total_videos"] = 0  # Populated by service layer if needed
        stats["timelapse_count"] = row_data.get("total_timelapses", 0)

        # Current timelapse info
        stats["current_timelapse_name"] = row_data.get("timelapse_name")

        # Legacy field compatibility
        stats["total_images"] = row_data.get("total_images", 0)
        stats["current_timelapse_images"] = (
            row_data.get("active_timelapse_images", 0)
            if row_data.get("timelapse_status") in ["running", "paused"]
            else 0
        )

        # Computed fields that require service layer calculation
        stats["first_capture_at"] = None
        stats["avg_capture_interval_minutes"] = None
        stats["days_since_first_capture"] = None

        return stats

    @staticmethod
    def extract_camera_base_fields(
        row_data: Dict[str, Any], camera_model_fields: Set[str]
    ) -> Dict[str, Any]:
        """
        Extract only the fields that belong to the Camera model from row data.

        Args:
            row_data: Raw database row data
            camera_model_fields: Set of valid Camera model field names

        Returns:
            Dictionary with only Camera model fields
        """
        return {k: v for k, v in row_data.items() if k in camera_model_fields}


class DatabaseUtilities:
    """
    Collection of utility functions for common database operations.
    """

    @staticmethod
    def serialize_json_field(value: Any) -> str:
        """
        Safely serialize a value to JSON for database storage.

        Args:
            value: Value to serialize

        Returns:
            JSON string or empty object if serialization fails
        """
        try:
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            elif value is None:
                return "{}"
            else:
                return json.dumps(value)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize value to JSON: {e}")
            return "{}"

    @staticmethod
    def deserialize_json_field(value: Union[str, dict, None]) -> dict:
        """
        Safely deserialize a JSON field from database.

        Args:
            value: JSON string or dict from database

        Returns:
            Parsed dictionary or empty dict if parsing fails
        """
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        try:
            return json.loads(value) if value else {}
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to deserialize JSON field: {e}")
            return {}

    @staticmethod
    def calculate_day_number(
        start_date: date, current_date: Optional[date] = None
    ) -> int:
        """
        Calculate day number relative to a start date.

        Args:
            start_date: Reference start date
            current_date: Date to calculate for (defaults to today)

        Returns:
            1-based day number
        """
        if current_date is None:
            current_date = utc_now().date()  # Use timezone-aware current date

        return max(1, (current_date - start_date).days + 1)

    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """
        Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    @staticmethod
    def calculate_success_rate(
        consecutive_failures: int, max_failures: int = 10
    ) -> float:
        """
        Calculate success rate percentage based on consecutive failures.

        Args:
            consecutive_failures: Number of consecutive failures
            max_failures: Maximum failures before 0% success rate

        Returns:
            Success rate percentage (0.0 to 100.0)
        """
        if consecutive_failures == 0:
            return 100.0

        if consecutive_failures >= max_failures:
            return 0.0

        # Calculate reduction based on max_failures
        reduction_per_failure = 100.0 / max_failures
        reduction = consecutive_failures * reduction_per_failure
        return max(0.0, 100.0 - reduction)

    @staticmethod
    def build_pagination_info(
        total_count: int, page: int, per_page: int
    ) -> Dict[str, Any]:
        """
        Build pagination information dictionary.

        Args:
            total_count: Total number of items
            page: Current page (1-based)
            per_page: Items per page

        Returns:
            Dictionary with pagination info
        """
        total_pages = (total_count + per_page - 1) // per_page

        return {
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "start_index": (page - 1) * per_page + 1 if total_count > 0 else 0,
            "end_index": min(page * per_page, total_count),
        }


class CommonQueries:
    """
    Collection of commonly used SQL queries that can be shared between
    async and sync database classes.
    """

    # Camera queries
    CAMERA_WITH_TIMELAPSE = """
        SELECT
            c.*,
            t.status as timelapse_status,
            t.id as timelapse_id,
            t.name as timelapse_name
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
        WHERE c.id = %(camera_id)s
    """

    # Optimized query that replaces LATERAL JOIN with window function for better performance
    CAMERAS_WITH_LAST_IMAGE = """
        SELECT
            c.*,
            t.status as timelapse_status,
            t.id as timelapse_id,
            t.name as timelapse_name,
            li.id as last_image_id,
            li.captured_at as last_image_captured_at,
            li.file_path as last_image_file_path,
            li.file_size as last_image_file_size,
            li.day_number as last_image_day_number,
            li.thumbnail_path as last_image_thumbnail_path,
            li.thumbnail_size as last_image_thumbnail_size,
            li.small_path as last_image_small_path,
            li.small_size as last_image_small_size
        FROM cameras c
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id
        LEFT JOIN (
            SELECT DISTINCT ON (camera_id)
                camera_id, id, captured_at, file_path, file_size, day_number,
                thumbnail_path, thumbnail_size, small_path, small_size
            FROM images
            ORDER BY camera_id, captured_at DESC
        ) li ON li.camera_id = c.id
        ORDER BY c.id
    """

    # Timelapse queries
    TIMELAPSE_WITH_CAMERA = """
        SELECT t.*, c.name as camera_name
        FROM timelapses t
        JOIN cameras c ON t.camera_id = c.id
        WHERE t.id = %(timelapse_id)s
    """

    RUNNING_TIMELAPSES = """
        SELECT
            c.*,
            t.id as timelapse_id,
            t.status as timelapse_status,
            t.name as timelapse_name,
            t.use_custom_time_window,
            t.time_window_start as custom_time_window_start,
            t.time_window_end as custom_time_window_end
        FROM cameras c
        INNER JOIN timelapses t ON c.active_timelapse_id = t.id
        WHERE c.status = 'active' AND t.status = 'running'
        ORDER BY c.id
    """

    # Statistics queries
    CAMERA_STATS = """
        SELECT
            COUNT(*) as total_images,
            COUNT(CASE WHEN captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 1 END) as last_24h_images,
            SUM(COALESCE(file_size, 0)) as total_file_size,
            AVG(EXTRACT(EPOCH FROM (captured_at - LAG(captured_at) OVER (ORDER BY captured_at)))/60) as avg_interval_minutes
        FROM images
        WHERE camera_id = %(camera_id)s
    """

    SYSTEM_HEALTH_CAMERAS = """
        SELECT
            COUNT(*) as total_cameras,
            COUNT(CASE WHEN health_status = 'online' THEN 1 END) as online_cameras,
            COUNT(CASE WHEN health_status = 'offline' THEN 1 END) as offline_cameras,
            COUNT(CASE WHEN status = 'active' THEN 1 END) as active_cameras
        FROM cameras
    """

    SYSTEM_HEALTH_TIMELAPSES = """
        SELECT
            COUNT(CASE WHEN status = 'running' THEN 1 END) as running_timelapses,
            COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_timelapses
        FROM timelapses
    """

    # Optimized image queries - replaced LATERAL JOIN with window function
    LATEST_IMAGE_FOR_CAMERA = """
        SELECT
            i.*,
            c.name as camera_name
        FROM (
            SELECT
                id, captured_at, file_path, file_size, day_number,
                thumbnail_path, thumbnail_size, small_path, small_size,
                camera_id, timelapse_id, created_at,
                ROW_NUMBER() OVER (PARTITION BY camera_id ORDER BY captured_at DESC) as rn
            FROM images
            WHERE camera_id = %(camera_id)s
        ) i
        JOIN cameras c ON i.camera_id = c.id
        WHERE i.rn = 1
    """


class SettingsManager:
    """
    Centralized manager for application settings operations.

    Eliminates duplication between AsyncDatabase and SyncDatabase classes
    by providing common settings query logic and type conversion.
    """

    @staticmethod
    def get_settings_dict_query() -> str:
        """Get SQL query for retrieving all settings as key-value pairs"""
        return "SELECT key, value FROM settings"

    @staticmethod
    def create_or_update_setting_query(key: str, value: str) -> tuple[str, dict]:
        """Build upsert query for settings"""
        query = """
            INSERT INTO settings (key, value)
            VALUES (%(key)s, %(value)s)
            ON CONFLICT (key)
            DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, key, value, created_at, updated_at
        """
        params = {"key": key, "value": value}
        return query, params

    @staticmethod
    def process_settings_rows(rows: List[Dict[str, Any]]) -> Dict[str, str]:
        """Convert settings rows to key-value dictionary"""
        return {row["key"]: row["value"] for row in rows}


class DatabaseValidationMixin:
    """
    Mixin class for common database validation patterns.
    """

    def validate_foreign_key(
        self, table_name: str, field_name: str, value: int, cursor
    ) -> bool:
        """
        Validate that a foreign key reference exists.

        Args:
            table_name: Referenced table name
            field_name: Referenced field name (usually 'id')
            value: Value to check
            cursor: Database cursor

        Returns:
            True if reference exists, False otherwise
        """
        cursor.execute(
            f"SELECT 1 FROM {table_name} WHERE {field_name} = %s LIMIT 1", (value,)
        )
        return cursor.fetchone() is not None

    def validate_unique_constraint(
        self,
        table_name: str,
        field_name: str,
        value: Any,
        exclude_id: Optional[int],
        cursor,
    ) -> bool:
        """
        Validate that a field value is unique (excluding a specific record).

        Args:
            table_name: Table to check
            field_name: Field to check for uniqueness
            value: Value to check
            exclude_id: Optional ID to exclude from check (for updates)
            cursor: Database cursor

        Returns:
            True if value is unique, False otherwise
        """
        if exclude_id:
            cursor.execute(
                f"SELECT 1 FROM {table_name} WHERE {field_name} = %s AND id != %s LIMIT 1",
                (value, exclude_id),
            )
        else:
            cursor.execute(
                f"SELECT 1 FROM {table_name} WHERE {field_name} = %s LIMIT 1", (value,)
            )
        return cursor.fetchone() is None


class DatabaseQueryCache:
    """
    Simple in-memory cache for database query results.

    Provides caching for frequently accessed data with TTL expiration.
    Useful for optimizing repeated queries to relatively static data.
    """

    def __init__(self, default_ttl_seconds: int = 300):  # 5 minutes default
        """
        Initialize cache with default TTL.

        Args:
            default_ttl_seconds: Default time-to-live for cache entries
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl_seconds

    def _get_cache_key(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key from query and parameters."""
        if params:
            # Sort params for consistent key generation
            param_str = json.dumps(params, sort_keys=True, default=str)
            return f"{hash(query)}:{hash(param_str)}"
        return str(hash(query))

    def get(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Get cached result for query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cached result or None if not found/expired
        """
        cache_key = self._get_cache_key(query, params)

        if cache_key not in self.cache:
            return None

        entry = self.cache[cache_key]

        # Check if expired
        if time.time() > entry["expires_at"]:
            del self.cache[cache_key]
            return None

        return entry["data"]

    def set(
        self,
        query: str,
        result: Any,
        params: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """
        Cache query result.

        Args:
            query: SQL query string
            result: Query result to cache
            params: Query parameters
            ttl_seconds: Time-to-live override
        """
        cache_key = self._get_cache_key(query, params)
        ttl = ttl_seconds or self.default_ttl

        self.cache[cache_key] = {
            "data": result,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
        }

    def invalidate(self, pattern: Optional[str] = None) -> int:
        """
        Invalidate cache entries.

        Args:
            pattern: Optional pattern to match keys (simple substring match)

        Returns:
            Number of entries invalidated
        """
        if pattern is None:
            # Clear all
            count = len(self.cache)
            self.cache.clear()
            return count

        # Remove entries matching pattern
        keys_to_remove = [key for key in self.cache.keys() if pattern in key]

        for key in keys_to_remove:
            del self.cache[key]

        return len(keys_to_remove)

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self.cache.items()
            if current_time > entry["expires_at"]
        ]

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()
        expired_count = sum(
            1 for entry in self.cache.values() if current_time > entry["expires_at"]
        )

        return {
            "total_entries": len(self.cache),
            "expired_entries": expired_count,
            "active_entries": len(self.cache) - expired_count,
            "cache_size_bytes": len(str(self.cache).encode("utf-8")),
        }


# Global cache instance for database operations
# Can be used across different database operation classes
database_cache = DatabaseQueryCache(default_ttl_seconds=300)  # 5 minutes


class DatabaseBusinessLogic:
    """
    Business logic utilities that should be moved out of database operations.

    This class centralizes business logic that was previously scattered
    across database operation classes, improving separation of concerns.
    """

    @staticmethod
    def validate_setting_data(
        key: str, value: str, max_key_length: int = 255, max_value_length: int = 10000
    ) -> tuple[bool, Optional[str]]:
        """
        Validate setting data before database operations.

        Extracted from database layer to improve separation of concerns.

        Args:
            key: Setting key
            value: Setting value
            max_key_length: Maximum allowed key length
            max_value_length: Maximum allowed value length

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not key or not key.strip():
            return False, "Setting key cannot be empty"

        if len(key) > max_key_length:
            return False, f"Setting key cannot exceed {max_key_length} characters"

        if value is None:
            return False, "Setting value cannot be None"

        if len(value) > max_value_length:
            return False, f"Setting value too long (max {max_value_length} characters)"

        return True, None

    @staticmethod
    def calculate_image_day_number(start_date: date, captured_date: date) -> int:
        """
        Calculate the day number for an image within a timelapse.

        Extracted from database layer to improve separation of concerns.

        Args:
            start_date: Timelapse start date
            captured_date: Date when image was captured

        Returns:
            Day number (1-based)
        """
        return DatabaseUtilities.calculate_day_number(start_date, captured_date)

    @staticmethod
    def validate_pagination_params(
        page: int, page_size: int, max_page_size: int = 1000
    ) -> tuple[int, int]:
        """
        Validate and normalize pagination parameters.

        Args:
            page: Page number (1-based)
            page_size: Items per page
            max_page_size: Maximum allowed page size

        Returns:
            Tuple of (normalized_page, normalized_page_size)
        """
        # Ensure minimum values
        page = max(1, page)
        page_size = max(1, min(max_page_size, page_size))

        return page, page_size

    @staticmethod
    def validate_id_list(
        ids: List[int], max_count: int = 1000
    ) -> tuple[bool, Optional[str]]:
        """
        Validate list of IDs for bulk operations.

        Args:
            ids: List of IDs to validate
            max_count: Maximum allowed count

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not ids:
            return False, "ID list cannot be empty"

        if len(ids) > max_count:
            return False, f"Too many IDs (max {max_count})"

        if not all(isinstance(id_val, int) and id_val > 0 for id_val in ids):
            return False, "All IDs must be positive integers"

        return True, None


class DatabaseConnectionBatcher:
    """
    Utility for batching related database operations within a single connection.

    Reduces connection overhead by reusing connections for multiple related queries.
    Provides both async and sync context managers for batch operations.
    """

    def __init__(self, db_instance):
        """
        Initialize batcher with database instance.

        Args:
            db_instance: AsyncDatabase or SyncDatabase instance
        """
        self.db = db_instance
        self._results = []

    async def execute_batch_async(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple operations in a single async connection.

        Args:
            operations: List of operation dictionaries with 'query' and 'params' keys

        Returns:
            List of results from each operation
        """
        results = []

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                for operation in operations:
                    query = operation["query"]
                    params = operation.get("params", ())
                    operation_type = operation.get("type", "fetchall")

                    await cur.execute(query, params)

                    if operation_type == "fetchone":
                        result = await cur.fetchone()
                    elif operation_type == "fetchall":
                        result = await cur.fetchall()
                    elif operation_type == "rowcount":
                        result = cur.rowcount
                    else:
                        result = None

                    results.append(result)

        return results

    def execute_batch_sync(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple operations in a single sync connection.

        Args:
            operations: List of operation dictionaries with 'query' and 'params' keys

        Returns:
            List of results from each operation
        """
        results = []

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                for operation in operations:
                    query = operation["query"]
                    params = operation.get("params", ())
                    operation_type = operation.get("type", "fetchall")

                    cur.execute(query, params)

                    if operation_type == "fetchone":
                        result = cur.fetchone()
                    elif operation_type == "fetchall":
                        result = cur.fetchall()
                    elif operation_type == "rowcount":
                        result = cur.rowcount
                    else:
                        result = None

                    results.append(result)

        return results


class BatchQueryBuilder:
    """
    Helper for building efficient batch operations.

    Provides utilities for common batch patterns like bulk inserts,
    bulk updates, and related data fetching.
    """

    @staticmethod
    def build_bulk_insert(
        table_name: str, data_list: List[Dict[str, Any]], returning_field: str = "id"
    ) -> Dict[str, Any]:
        """
        Build bulk insert operation.

        Args:
            table_name: Target table name
            data_list: List of data dictionaries to insert
            returning_field: Field to return after insert

        Returns:
            Operation dictionary for batch execution
        """
        if not data_list:
            return {"query": "", "params": (), "type": "fetchall"}

        # Get fields from first item (assuming all items have same structure)
        fields = list(data_list[0].keys())

        # Build values clauses and parameters
        values_clauses = []
        params = []

        for item in data_list:
            placeholders = ", ".join(["%s"] * len(fields))
            values_clauses.append(f"({placeholders})")
            params.extend([item[field] for field in fields])

        values_sql = ", ".join(values_clauses)
        fields_sql = ", ".join(fields)

        query = f"""
            INSERT INTO {table_name} ({fields_sql})
            VALUES {values_sql}
            RETURNING {returning_field}
        """

        return {"query": query, "params": params, "type": "fetchall"}

    @staticmethod
    def build_bulk_update(
        table_name: str, updates: List[Dict[str, Any]], id_field: str = "id"
    ) -> List[Dict[str, Any]]:
        """
        Build bulk update operations.

        Args:
            table_name: Target table name
            updates: List of update dictionaries (must include id_field)
            id_field: Primary key field name

        Returns:
            List of operation dictionaries for batch execution
        """
        operations = []

        for update_data in updates:
            if id_field not in update_data:
                continue

            record_id = update_data[id_field]
            fields_to_update = {k: v for k, v in update_data.items() if k != id_field}

            if not fields_to_update:
                continue

            # Build SET clauses
            set_clauses = [f"{field} = %s" for field in fields_to_update.keys()]
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")

            query = f"""
                UPDATE {table_name}
                SET {', '.join(set_clauses)}
                WHERE {id_field} = %s
            """

            params = list(fields_to_update.values()) + [record_id]

            operations.append({"query": query, "params": params, "type": "rowcount"})

        return operations

    @staticmethod
    def build_related_data_fetch(
        primary_table: str,
        related_tables: List[Dict[str, str]],
        primary_ids: List[int],
        primary_id_field: str = "id",
    ) -> List[Dict[str, Any]]:
        """
        Build operations to fetch related data for multiple primary records.

        Args:
            primary_table: Main table name
            related_tables: List of related table configs
            primary_ids: List of primary record IDs
            primary_id_field: Primary key field name

        Returns:
            List of operation dictionaries for batch execution
        """
        operations = []

        if not primary_ids:
            return operations

        # Build primary table query
        placeholders = ", ".join(["%s"] * len(primary_ids))
        primary_query = f"""
            SELECT * FROM {primary_table}
            WHERE {primary_id_field} IN ({placeholders})
            ORDER BY {primary_id_field}
        """

        operations.append(
            {"query": primary_query, "params": primary_ids, "type": "fetchall"}
        )

        # Build related table queries
        for related_config in related_tables:
            table_name = related_config["table"]
            foreign_key = related_config["foreign_key"]
            select_fields = related_config.get("fields", "*")

            related_query = f"""
                SELECT {select_fields} FROM {table_name}
                WHERE {foreign_key} IN ({placeholders})
                ORDER BY {foreign_key}
            """

            operations.append(
                {"query": related_query, "params": primary_ids, "type": "fetchall"}
            )

        return operations


class DatabaseOperationBase:
    """
    Base class for database operations with common patterns.

    Provides shared functionality across all database operation classes
    to reduce duplication and ensure consistency.
    """

    def __init__(self, db_instance):
        """
        Initialize with database instance.

        Args:
            db_instance: AsyncDatabase or SyncDatabase instance
        """
        self.db = db_instance
        self._model_cache = {}

    def _get_model_fields(self, model_class) -> set:
        """
        Get field names for a Pydantic model with caching.

        Args:
            model_class: Pydantic model class

        Returns:
            Set of field names
        """
        model_name = model_class.__name__
        if model_name not in self._model_cache:
            self._model_cache[model_name] = set(model_class.model_fields.keys())
        return self._model_cache[model_name]

    def _filter_model_fields(
        self, row_data: Dict[str, Any], model_class
    ) -> Dict[str, Any]:
        """
        Filter row data to only include fields that belong to the model.

        Args:
            row_data: Raw database row data
            model_class: Pydantic model class

        Returns:
            Filtered dictionary with only model fields
        """
        model_fields = self._get_model_fields(model_class)
        return {k: v for k, v in row_data.items() if k in model_fields}

    def _validate_pagination(
        self, page: int, page_size: int, max_page_size: int = 1000
    ) -> tuple[int, int, int]:
        """
        Validate and normalize pagination parameters.

        Args:
            page: Page number (1-based)
            page_size: Items per page
            max_page_size: Maximum allowed page size

        Returns:
            Tuple of (page, page_size, offset)
        """
        page, page_size = DatabaseBusinessLogic.validate_pagination_params(
            page, page_size, max_page_size
        )
        offset = (page - 1) * page_size
        return page, page_size, offset

    def _build_where_clause(
        self, conditions: Dict[str, Any], table_alias: str = ""
    ) -> tuple[str, list]:
        """
        Build WHERE clause from conditions dictionary.

        Args:
            conditions: Dictionary of field: value pairs
            table_alias: Optional table alias prefix

        Returns:
            Tuple of (where_clause, params_list)
        """
        if not conditions:
            return "", []

        where_clauses = []
        params = []

        prefix = f"{table_alias}." if table_alias else ""

        for field, value in conditions.items():
            if value is not None:
                where_clauses.append(f"{prefix}{field} = %s")
                params.append(value)

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        return where_clause, params

    def _build_order_clause(
        self, order_by: str, order_dir: str = "ASC", table_alias: str = ""
    ) -> str:
        """
        Build ORDER BY clause with validation.

        Args:
            order_by: Column name to order by
            order_dir: Sort direction (ASC/DESC)
            table_alias: Optional table alias prefix

        Returns:
            ORDER BY clause string
        """
        # Validate order direction
        order_dir = order_dir.upper()
        if order_dir not in ["ASC", "DESC"]:
            order_dir = "ASC"

        prefix = f"{table_alias}." if table_alias else ""
        return f"ORDER BY {prefix}{order_by} {order_dir}"

    def _handle_db_error(self, error: Exception, operation: str) -> None:
        """
        Standardized database error handling.

        Args:
            error: Exception that occurred
            operation: Description of the operation that failed
        """
        logger.error(f"Database error in {operation}: {error}")
        # Could add more sophisticated error handling here
        # like converting specific database errors to business exceptions


class AsyncDatabaseOperationBase(DatabaseOperationBase):
    """
    Base class for async database operations.

    Extends DatabaseOperationBase with async-specific functionality.
    """

    async def _execute_with_cache(
        self,
        query: str,
        params: tuple = (),
        cache_key: Optional[str] = None,
        ttl_seconds: int = 300,
    ) -> Any:
        """
        Execute query with optional caching.

        Args:
            query: SQL query to execute
            params: Query parameters
            cache_key: Optional cache key override
            ttl_seconds: Cache TTL in seconds

        Returns:
            Query result
        """
        global database_cache

        # Check cache first if key provided
        if cache_key:
            cached_result = database_cache.get(
                query, {str(i): v for i, v in enumerate(params)} if params else None
            )
            if cached_result is not None:
                return cached_result

        # Execute query
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchall()

        # Cache result if key provided
        if cache_key:
            database_cache.set(
                query,
                result,
                {str(i): v for i, v in enumerate(params)} if params else None,
                ttl_seconds,
            )

        return result


class SyncDatabaseOperationBase(DatabaseOperationBase):
    """
    Base class for sync database operations.

    Extends DatabaseOperationBase with sync-specific functionality.
    """

    def _execute_with_cache(
        self,
        query: str,
        params: tuple = (),
        cache_key: Optional[str] = None,
        ttl_seconds: int = 300,
    ) -> Any:
        """
        Execute query with optional caching (sync version).

        Args:
            query: SQL query to execute
            params: Query parameters
            cache_key: Optional cache key override
            ttl_seconds: Cache TTL in seconds

        Returns:
            Query result
        """
        global database_cache

        # Check cache first if key provided
        if cache_key:
            cached_result = database_cache.get(
                query, {str(i): v for i, v in enumerate(params)} if params else None
            )
            if cached_result is not None:
                return cached_result

        # Execute query
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchall()

        # Cache result if key provided
        if cache_key:
            database_cache.set(
                query,
                result,
                {str(i): v for i, v in enumerate(params)} if params else None,
                ttl_seconds,
            )

        return result


class DatabaseErrorHandler:
    """
    Standardized error handling for database operations.

    Provides consistent error handling patterns across all database operations
    with proper logging and error transformation.
    """

    @staticmethod
    def handle_connection_error(error: Exception, operation: str) -> None:
        """
        Handle database connection errors.

        Args:
            error: The connection error that occurred
            operation: Description of the operation that failed
        """
        logger.error(f"Database connection error in {operation}: {error}")
        # Could raise custom ConnectionError here

    @staticmethod
    def handle_query_error(error: Exception, operation: str, query: str) -> None:
        """
        Handle database query errors.

        Args:
            error: The query error that occurred
            operation: Description of the operation that failed
            query: The SQL query that failed
        """
        logger.error(f"Database query error in {operation}: {error}")
        logger.debug(f"Failed query: {query}")
        # Could raise custom QueryError here

    @staticmethod
    def handle_validation_error(
        error: str, operation: str, data: Dict[str, Any]
    ) -> None:
        """
        Handle data validation errors.

        Args:
            error: The validation error message
            operation: Description of the operation that failed
            data: The data that failed validation
        """
        logger.warning(f"Validation error in {operation}: {error}")
        logger.debug(f"Invalid data: {data}")
        # Could raise custom ValidationError here

    @staticmethod
    def handle_not_found_error(
        operation: str, entity_type: str, entity_id: Any
    ) -> None:
        """
        Handle entity not found errors.

        Args:
            operation: Description of the operation that failed
            entity_type: Type of entity that was not found
            entity_id: ID of the entity that was not found
        """
        logger.info(
            f"Entity not found in {operation}: {entity_type} with ID {entity_id}"
        )
        # Could raise custom NotFoundError here


class DatabaseTransactionManager:
    """
    Transaction management utilities for database operations.

    Provides consistent transaction handling patterns with proper
    rollback and error handling.
    """

    def __init__(self, db_instance):
        """
        Initialize transaction manager.

        Args:
            db_instance: AsyncDatabase or SyncDatabase instance
        """
        self.db = db_instance

    async def execute_in_transaction_async(
        self, operations: List[Callable[..., Awaitable[Any]]]
    ) -> List[Any]:
        """
        Execute multiple operations in a single async transaction.

        Args:
            operations: List of callable operations to execute

        Returns:
            List of results from each operation

        Raises:
            Exception: If any operation fails, transaction is rolled back
        """
        results = []

        async with self.db.get_connection() as conn:
            async with conn.transaction():
                try:
                    for operation in operations:
                        result = await operation(conn)
                        results.append(result)
                except Exception as e:
                    logger.error(f"Transaction failed, rolling back: {e}")
                    raise

        return results

    def execute_in_transaction_sync(
        self, operations: List[Callable[..., Any]]
    ) -> List[Any]:
        """
        Execute multiple operations in a single sync transaction.

        Args:
            operations: List of callable operations to execute

        Returns:
            List of results from each operation

        Raises:
            Exception: If any operation fails, transaction is rolled back
        """
        results = []

        with self.db.get_connection() as conn:
            with conn.transaction():
                try:
                    for operation in operations:
                        if callable(operation):
                            result = operation(conn)
                            results.append(result)
                        else:
                            raise ValueError(f"Operation is not callable: {operation}")
                except Exception as e:
                    logger.error(f"Transaction failed, rolling back: {e}")
                    raise

        return results


class DatabaseValidator:
    """
    Common validation patterns for database operations.

    Provides reusable validation methods that can be used across
    all database operation classes.
    """

    @staticmethod
    def validate_id(entity_id: int, entity_type: str = "entity") -> bool:
        """
        Validate entity ID.

        Args:
            entity_id: ID to validate
            entity_type: Type of entity for error messages

        Returns:
            True if valid

        Raises:
            ValueError: If ID is invalid
        """
        if not isinstance(entity_id, int) or entity_id <= 0:
            raise ValueError(f"Invalid {entity_type} ID: {entity_id}")
        return True

    @staticmethod
    def validate_id_list(
        entity_ids: List[int], entity_type: str = "entity", max_count: int = 1000
    ) -> bool:
        """
        Validate list of entity IDs.

        Args:
            entity_ids: List of IDs to validate
            entity_type: Type of entity for error messages
            max_count: Maximum allowed count

        Returns:
            True if valid

        Raises:
            ValueError: If any ID is invalid or list is too long
        """
        if not entity_ids:
            raise ValueError(f"Empty {entity_type} ID list")

        if len(entity_ids) > max_count:
            raise ValueError(f"Too many {entity_type} IDs (max {max_count})")

        for entity_id in entity_ids:
            DatabaseValidator.validate_id(entity_id, entity_type)

        return True

    @staticmethod
    def validate_pagination_params(
        page: int, page_size: int, max_page_size: int = 1000
    ) -> tuple[int, int]:
        """
        Validate pagination parameters.

        Args:
            page: Page number (1-based)
            page_size: Items per page
            max_page_size: Maximum allowed page size

        Returns:
            Tuple of validated (page, page_size)

        Raises:
            ValueError: If parameters are invalid
        """
        if page < 1:
            raise ValueError("Page number must be >= 1")

        if page_size < 1:
            raise ValueError("Page size must be >= 1")

        if page_size > max_page_size:
            raise ValueError(f"Page size too large (max {max_page_size})")

        return page, page_size

    @staticmethod
    def validate_string_field(
        value: str, field_name: str, max_length: int = 255, required: bool = True
    ) -> bool:
        """
        Validate string field.

        Args:
            value: String value to validate
            field_name: Name of field for error messages
            max_length: Maximum allowed length
            required: Whether field is required

        Returns:
            True if valid

        Raises:
            ValueError: If string is invalid
        """
        if required and (not value or not value.strip()):
            raise ValueError(f"{field_name} is required")

        if value and len(value) > max_length:
            raise ValueError(f"{field_name} too long (max {max_length} characters)")

        return True


class ConnectionPoolMonitor:
    """
    Advanced connection pool monitoring and health management.

    Provides comprehensive monitoring, alerting, and automatic recovery
    for database connection pools.
    """

    def __init__(self, pool_instance, pool_name: str = "default"):
        """
        Initialize connection pool monitor.

        Args:
            pool_instance: AsyncDatabaseCore or SyncDatabaseCore instance
            pool_name: Name for this pool instance
        """
        self.pool = pool_instance
        self.pool_name = pool_name
        self.metrics_history = []
        self.health_alerts = []
        self.last_health_check = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5

    async def collect_comprehensive_metrics(self) -> Dict[str, Any]:
        """
        Collect comprehensive pool metrics including health status.

        Returns:
            Dictionary with detailed pool metrics and health indicators
        """
        metrics = {
            "timestamp": time.time(),
            "pool_name": self.pool_name,
            "collection_time": utc_now().isoformat(),
        }

        # Get basic pool stats
        if hasattr(self.pool, "get_pool_stats"):
            pool_stats = await self.pool.get_pool_stats()
            metrics.update(pool_stats)

        # Perform health check
        health_result = await self.pool.health_check(timeout=3.0)
        metrics["health"] = health_result

        # Calculate performance metrics
        if self.metrics_history:
            recent_metrics = self.metrics_history[-10:]  # Last 10 measurements
            response_times = [
                m.get("health", {}).get("response_time_ms", 0)
                for m in recent_metrics
                if m.get("health", {}).get("response_time_ms")
            ]

            if response_times:
                metrics["performance"] = {
                    "avg_response_time_ms": sum(response_times) / len(response_times),
                    "min_response_time_ms": min(response_times),
                    "max_response_time_ms": max(response_times),
                    "response_time_trend": self._calculate_trend(response_times),
                }

        # Update health status tracking
        self._update_health_tracking(health_result)

        # Store in history (keep last 100 measurements)
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)

        return metrics

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values."""
        if len(values) < 2:
            return "stable"

        recent_avg = sum(values[-3:]) / len(values[-3:])
        older_avg = (
            sum(values[:-3]) / len(values[:-3]) if len(values) > 3 else recent_avg
        )

        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"

    def _update_health_tracking(self, health_result: Dict[str, Any]) -> None:
        """Update health tracking and generate alerts if needed."""
        is_healthy = health_result.get("status") == "healthy"

        if is_healthy:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

            # Generate alert for consecutive failures
            if self.consecutive_failures >= self.max_consecutive_failures:
                alert = {
                    "timestamp": time.time(),
                    "severity": "critical",
                    "message": f"Pool {self.pool_name} has {self.consecutive_failures} consecutive failures",
                    "health_result": health_result,
                }
                self.health_alerts.append(alert)
                logger.error(f"Critical pool health alert: {alert['message']}")

        self.last_health_check = time.time()

    def get_alerts(
        self, since_timestamp: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get health alerts since a specific timestamp.

        Args:
            since_timestamp: Optional timestamp to filter alerts

        Returns:
            List of alert dictionaries
        """
        if since_timestamp is None:
            return self.health_alerts.copy()

        return [
            alert
            for alert in self.health_alerts
            if alert["timestamp"] >= since_timestamp
        ]

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get summarized health status for the pool.

        Returns:
            Dictionary with health summary and recommendations
        """
        if not self.metrics_history:
            return {"status": "no_data", "message": "No metrics collected yet"}

        latest_metrics = self.metrics_history[-1]
        health = latest_metrics.get("health", {})

        summary = {
            "pool_name": self.pool_name,
            "status": health.get("status", "unknown"),
            "last_check": (
                datetime.fromtimestamp(self.last_health_check).isoformat()
                if self.last_health_check
                else None
            ),
            "consecutive_failures": self.consecutive_failures,
            "total_alerts": len(self.health_alerts),
            "recent_alerts": len(
                [a for a in self.health_alerts if a["timestamp"] > time.time() - 3600]
            ),  # Last hour
        }

        # Add recommendations
        recommendations = []

        if self.consecutive_failures > 2:
            recommendations.append("Consider checking database server health")

        if latest_metrics.get("performance", {}).get("avg_response_time_ms", 0) > 1000:
            recommendations.append(
                "High response times detected - consider pool size optimization"
            )

        if latest_metrics.get("success_rate", 100) < 95:
            recommendations.append("Low success rate - investigate connection issues")

        summary["recommendations"] = recommendations

        return summary


class ConnectionPoolOptimizer:
    """
    Connection pool configuration optimization and tuning.

    Analyzes pool performance and suggests optimal configurations
    based on usage patterns and performance metrics.
    """

    @staticmethod
    def analyze_pool_performance(
        metrics_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze pool performance metrics to identify optimization opportunities.

        Args:
            metrics_history: List of historical metrics from ConnectionPoolMonitor

        Returns:
            Analysis results with optimization recommendations
        """
        if not metrics_history:
            return {"status": "insufficient_data"}

        analysis = {
            "analysis_timestamp": time.time(),
            "metrics_analyzed": len(metrics_history),
            "time_range_hours": (
                (metrics_history[-1]["timestamp"] - metrics_history[0]["timestamp"])
                / 3600
                if len(metrics_history) > 1
                else 0
            ),
        }

        # Analyze response times
        response_times = [
            m.get("health", {}).get("response_time_ms", 0)
            for m in metrics_history
            if m.get("health", {}).get("response_time_ms")
        ]

        if response_times:
            analysis["response_time_analysis"] = {
                "avg_ms": sum(response_times) / len(response_times),
                "min_ms": min(response_times),
                "max_ms": max(response_times),
                "p95_ms": ConnectionPoolOptimizer._percentile(response_times, 95),
                "p99_ms": ConnectionPoolOptimizer._percentile(response_times, 99),
            }

        # Analyze success rates
        success_rates = [
            m.get("success_rate", 100) for m in metrics_history if "success_rate" in m
        ]

        if success_rates:
            analysis["reliability_analysis"] = {
                "avg_success_rate": sum(success_rates) / len(success_rates),
                "min_success_rate": min(success_rates),
                "periods_below_95": len([r for r in success_rates if r < 95]),
            }

        # Generate recommendations
        recommendations = []

        if analysis.get("response_time_analysis", {}).get("p95_ms", 0) > 500:
            recommendations.append(
                {
                    "type": "performance",
                    "priority": "high",
                    "suggestion": "Consider increasing pool size - high response times detected",
                    "metric": f"P95 response time: {analysis['response_time_analysis']['p95_ms']:.2f}ms",
                }
            )

        if analysis.get("reliability_analysis", {}).get("avg_success_rate", 100) < 98:
            recommendations.append(
                {
                    "type": "reliability",
                    "priority": "critical",
                    "suggestion": "Investigate connection stability - low success rate detected",
                    "metric": f"Average success rate: {analysis['reliability_analysis']['avg_success_rate']:.2f}%",
                }
            )

        analysis["recommendations"] = recommendations

        return analysis

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile value from a list of numbers."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100.0) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    @staticmethod
    def suggest_pool_configuration(
        current_config: Dict[str, Any], performance_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Suggest optimal pool configuration based on performance analysis.

        Args:
            current_config: Current pool configuration
            performance_analysis: Results from analyze_pool_performance

        Returns:
            Suggested configuration changes
        """
        suggestions = {
            "analysis_basis": performance_analysis.get("analysis_timestamp"),
            "current_config": current_config,
            "suggested_changes": [],
        }

        # Analyze response time patterns
        response_analysis = performance_analysis.get("response_time_analysis", {})
        reliability_analysis = performance_analysis.get("reliability_analysis", {})

        current_max_size = current_config.get("max_size", 10)
        current_min_size = current_config.get("min_size", 2)

        # Suggest max_size adjustments
        if response_analysis.get("p95_ms", 0) > 1000:
            new_max_size = min(current_max_size * 2, 50)  # Cap at 50
            suggestions["suggested_changes"].append(
                {
                    "parameter": "max_size",
                    "current_value": current_max_size,
                    "suggested_value": new_max_size,
                    "reason": f"High P95 response time ({response_analysis['p95_ms']:.2f}ms) suggests pool saturation",
                }
            )
        elif response_analysis.get("avg_ms", 0) < 50 and current_max_size > 10:
            new_max_size = max(current_max_size // 2, 5)
            suggestions["suggested_changes"].append(
                {
                    "parameter": "max_size",
                    "current_value": current_max_size,
                    "suggested_value": new_max_size,
                    "reason": f"Low response times ({response_analysis['avg_ms']:.2f}ms) suggest oversized pool",
                }
            )

        # Suggest min_size adjustments
        if (
            reliability_analysis.get("periods_below_95", 0)
            > len(performance_analysis.get("metrics_analyzed", [])) * 0.1
        ):
            new_min_size = min(current_min_size + 2, current_max_size // 2)
            suggestions["suggested_changes"].append(
                {
                    "parameter": "min_size",
                    "current_value": current_min_size,
                    "suggested_value": new_min_size,
                    "reason": "Frequent reliability issues suggest need for more persistent connections",
                }
            )

        return suggestions


class ConnectionRetryStrategy:
    """
    Intelligent connection retry strategy with exponential backoff.

    Provides resilient connection handling with configurable retry policies
    and circuit breaker functionality.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry strategy.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            exponential_base: Base for exponential backoff calculation
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

        self.failure_count = 0
        self.last_failure_time = None
        self.circuit_breaker_open = False
        self.circuit_breaker_open_time = None
        self.circuit_breaker_timeout = 300  # 5 minutes

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a specific retry attempt.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            # Add ±25% jitter
            jitter_amount = delay * 0.25
            delay += random.uniform(-jitter_amount, jitter_amount)

        return max(0, delay)

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """
        Determine if operation should be retried.

        Args:
            attempt: Current attempt number (0-based)
            error: Exception that occurred

        Returns:
            True if should retry, False otherwise
        """
        # Check circuit breaker
        if self.circuit_breaker_open and self.circuit_breaker_open_time is not None:
            if (
                time.time() - self.circuit_breaker_open_time
                > self.circuit_breaker_timeout
            ):
                self.circuit_breaker_open = False
                self.failure_count = 0
                logger.info("Circuit breaker reset - allowing retry attempts")
            else:
                logger.warning("Circuit breaker open - blocking retry attempts")
                return False

        # Check retry limits
        if attempt >= self.max_retries:
            return False

        # Check if error is retryable
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            OSError,
        )

        # Add psycopg errors if available
        try:
            import psycopg

            retryable_errors += (
                psycopg.OperationalError,
                psycopg.InterfaceError,
            )
        except ImportError:
            pass

        is_retryable = isinstance(error, retryable_errors)

        if is_retryable:
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit breaker if too many failures
            if self.failure_count >= 10:
                self.circuit_breaker_open = True
                self.circuit_breaker_open_time = time.time()
                logger.error("Circuit breaker opened due to excessive failures")
                return False

        return is_retryable

    async def execute_with_retry(
        self, operation: Callable[..., Awaitable[Any]], *args, **kwargs
    ) -> Any:
        """
        Execute operation with retry logic.

        Args:
            operation: Async callable to execute
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation

        Returns:
            Result of successful operation

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)
                # Reset failure tracking on success
                self.failure_count = max(0, self.failure_count - 1)
                return result

            except Exception as e:
                last_exception = e

                if not self.should_retry(attempt, e):
                    break

                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{self.max_retries + 1}), "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        if last_exception is not None:
            logger.error(
                f"Operation failed after {self.max_retries + 1} attempts: {last_exception}"
            )
            raise last_exception
        else:
            raise RuntimeError("Operation failed but no exception was captured")


class GracefulDegradationHandler:
    """
    Handles graceful degradation when database connections fail.

    Provides fallback mechanisms and degraded service capabilities
    when the database becomes unavailable or unstable.
    """

    def __init__(
        self, enable_cache_fallback: bool = True, enable_readonly_mode: bool = True
    ):
        """
        Initialize graceful degradation handler.

        Args:
            enable_cache_fallback: Whether to use cache as fallback
            enable_readonly_mode: Whether to enable read-only degraded mode
        """
        self.enable_cache_fallback = enable_cache_fallback
        self.enable_readonly_mode = enable_readonly_mode
        self.degraded_mode_active = False
        self.degraded_mode_start_time = None
        self.failed_operations_count = 0
        self.degradation_threshold = 5  # Failed operations before degradation
        self.recovery_check_interval = 60  # Seconds between recovery attempts
        self.last_recovery_attempt = None

    def should_trigger_degradation(self, consecutive_failures: int) -> bool:
        """
        Determine if graceful degradation should be triggered.

        Args:
            consecutive_failures: Number of consecutive failures

        Returns:
            True if degradation should be triggered
        """
        return (
            consecutive_failures >= self.degradation_threshold
            and not self.degraded_mode_active
        )

    def trigger_degraded_mode(
        self, reason: str = "Database connectivity issues"
    ) -> None:
        """
        Activate degraded mode with limited functionality.

        Args:
            reason: Reason for entering degraded mode
        """
        if not self.degraded_mode_active:
            self.degraded_mode_active = True
            self.degraded_mode_start_time = time.time()
            logger.warning(f"Entering degraded mode: {reason}")

    def attempt_recovery(self) -> bool:
        """
        Attempt to recover from degraded mode.

        Returns:
            True if recovery should be attempted
        """
        current_time = time.time()

        if not self.degraded_mode_active:
            return False

        if (
            self.last_recovery_attempt is None
            or current_time - self.last_recovery_attempt > self.recovery_check_interval
        ):
            self.last_recovery_attempt = current_time
            return True

        return False

    def exit_degraded_mode(self) -> None:
        """Exit degraded mode and restore full functionality."""
        if self.degraded_mode_active and self.degraded_mode_start_time is not None:
            degraded_duration = time.time() - self.degraded_mode_start_time
            self.degraded_mode_active = False
            self.degraded_mode_start_time = None
            self.failed_operations_count = 0
            logger.info(f"Exiting degraded mode after {degraded_duration:.2f}s")

    async def execute_with_degradation(
        self,
        operation: Callable[..., Awaitable[Any]],
        fallback_operation: Optional[Callable[..., Awaitable[Any]]] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute operation with graceful degradation support.

        Args:
            operation: Primary operation to execute
            fallback_operation: Optional fallback operation for degraded mode
            *args: Arguments for operations
            **kwargs: Keyword arguments for operations

        Returns:
            Result from primary or fallback operation

        Raises:
            Exception if both primary and fallback operations fail
        """
        try:
            # If in degraded mode, try recovery first
            if self.degraded_mode_active and self.attempt_recovery():
                try:
                    result = await operation(*args, **kwargs)
                    self.exit_degraded_mode()
                    return result
                except Exception:
                    # Recovery failed, continue with fallback
                    pass

            # Normal operation or degraded mode without recovery
            if not self.degraded_mode_active:
                try:
                    result = await operation(*args, **kwargs)
                    self.failed_operations_count = 0  # Reset on success
                    return result
                except Exception as e:
                    self.failed_operations_count += 1

                    if self.should_trigger_degradation(self.failed_operations_count):
                        self.trigger_degraded_mode(f"Operation failure: {e}")

                    # Fall through to degraded handling
                    if not fallback_operation:
                        raise

            # Execute fallback operation in degraded mode
            if fallback_operation and self.degraded_mode_active:
                logger.info("Executing fallback operation in degraded mode")
                return await fallback_operation(*args, **kwargs)

            # No fallback available
            raise RuntimeError(
                "Database unavailable and no fallback operation provided"
            )

        except Exception as e:
            logger.error(f"Operation failed in graceful degradation handler: {e}")
            raise

    def get_degradation_status(self) -> Dict[str, Any]:
        """
        Get current degradation status and metrics.

        Returns:
            Dictionary with degradation status information
        """
        status = {
            "degraded_mode_active": self.degraded_mode_active,
            "failed_operations_count": self.failed_operations_count,
            "degradation_threshold": self.degradation_threshold,
        }

        if self.degraded_mode_active and self.degraded_mode_start_time is not None:
            status.update(
                {
                    "degraded_duration_seconds": time.time()
                    - self.degraded_mode_start_time,
                    "last_recovery_attempt": (
                        datetime.fromtimestamp(self.last_recovery_attempt).isoformat()
                        if self.last_recovery_attempt
                        else None
                    ),
                }
            )

        return status


class ConnectionPoolHealthAggregator:
    """
    Aggregates health metrics from multiple connection pools and provides
    system-wide database health monitoring.
    """

    def __init__(self):
        """Initialize the health aggregator."""
        self.registered_pools = {}
        self.system_alerts = []
        self.last_system_check = None

    def register_pool(self, pool_name: str, monitor: ConnectionPoolMonitor) -> None:
        """
        Register a connection pool for monitoring.

        Args:
            pool_name: Unique name for the pool
            monitor: ConnectionPoolMonitor instance
        """
        self.registered_pools[pool_name] = monitor
        logger.info(f"Registered connection pool '{pool_name}' for health monitoring")

    def unregister_pool(self, pool_name: str) -> None:
        """
        Unregister a connection pool from monitoring.

        Args:
            pool_name: Name of the pool to unregister
        """
        if pool_name in self.registered_pools:
            del self.registered_pools[pool_name]
            logger.info(f"Unregistered connection pool '{pool_name}'")

    async def collect_system_health(self) -> Dict[str, Any]:
        """
        Collect aggregated health metrics from all registered pools.

        Returns:
            System-wide health metrics and status
        """
        system_health = {
            "timestamp": time.time(),
            "collection_time": utc_now().isoformat(),
            "pools": {},
            "system_status": "unknown",
            "total_pools": len(self.registered_pools),
        }

        healthy_pools = 0
        total_response_time = 0
        response_time_count = 0

        # Collect metrics from each pool
        for pool_name, monitor in self.registered_pools.items():
            try:
                pool_metrics = await monitor.collect_comprehensive_metrics()
                system_health["pools"][pool_name] = pool_metrics

                # Track system-wide metrics
                if pool_metrics.get("health", {}).get("status") == "healthy":
                    healthy_pools += 1

                response_time = pool_metrics.get("health", {}).get("response_time_ms")
                if response_time:
                    total_response_time += response_time
                    response_time_count += 1

            except Exception as e:
                system_health["pools"][pool_name] = {"status": "error", "error": str(e)}
                logger.error(f"Failed to collect metrics for pool '{pool_name}': {e}")

        # Calculate system status
        if healthy_pools == len(self.registered_pools):
            system_health["system_status"] = "healthy"
        elif healthy_pools > 0:
            system_health["system_status"] = "degraded"
        else:
            system_health["system_status"] = "unhealthy"

        # Add aggregated metrics
        system_health["aggregated_metrics"] = {
            "healthy_pool_percentage": (
                healthy_pools / max(len(self.registered_pools), 1)
            )
            * 100,
            "average_response_time_ms": (
                total_response_time / response_time_count
                if response_time_count > 0
                else 0
            ),
        }

        self.last_system_check = time.time()

        # Generate system-level alerts
        self._check_system_alerts(system_health)

        return system_health

    def _check_system_alerts(self, system_health: Dict[str, Any]) -> None:
        """Check for system-level alert conditions."""
        healthy_percentage = system_health.get("aggregated_metrics", {}).get(
            "healthy_pool_percentage", 100
        )

        if healthy_percentage < 50:
            alert = {
                "timestamp": time.time(),
                "severity": "critical",
                "message": f"System database health critical: {healthy_percentage:.1f}% pools healthy",
                "system_status": system_health.get("system_status"),
            }
            self.system_alerts.append(alert)
            logger.warning(alert["message"])
        elif healthy_percentage < 80:
            alert = {
                "timestamp": time.time(),
                "severity": "warning",
                "message": f"System database health degraded: {healthy_percentage:.1f}% pools healthy",
                "system_status": system_health.get("system_status"),
            }
            self.system_alerts.append(alert)
            logger.warning(alert["message"])

    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a high-level summary of system database health.

        Returns:
            Dictionary with system health summary
        """
        if not self.registered_pools:
            return {"status": "no_pools_registered"}

        summary = {
            "total_pools": len(self.registered_pools),
            "last_check": (
                datetime.fromtimestamp(self.last_system_check).isoformat()
                if self.last_system_check
                else None
            ),
            "system_alerts_count": len(self.system_alerts),
            "recent_alerts_count": len(
                [a for a in self.system_alerts if a["timestamp"] > time.time() - 3600]
            ),
        }

        # Get individual pool summaries
        pool_summaries = {}
        for pool_name, monitor in self.registered_pools.items():
            pool_summaries[pool_name] = monitor.get_health_summary()

        summary["pools"] = pool_summaries

        return summary


# Global instances for connection pool management
global_pool_aggregator = ConnectionPoolHealthAggregator()
global_degradation_handler = GracefulDegradationHandler()


class DatabaseBenchmark:
    """
    Database operation benchmarking and performance profiling utility.

    Provides tools for measuring and analyzing database operation performance
    to identify bottlenecks and optimization opportunities.
    """

    def __init__(self):
        """Initialize the benchmark utility."""
        self.benchmarks = {}
        self.operation_history = []
        self.max_history_size = 1000

    async def benchmark_operation(
        self,
        operation_name: str,
        operation: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> tuple[Any, Dict[str, Any]]:
        """
        Benchmark a database operation and collect performance metrics.

        Args:
            operation_name: Name identifier for the operation
            operation: Async callable to benchmark
            *args: Arguments to pass to operation
            **kwargs: Keyword arguments to pass to operation

        Returns:
            Tuple of (operation_result, benchmark_metrics)
        """
        start_time = time.time()
        start_memory = self._get_memory_usage()

        # Initialize variables
        success = False
        error = None
        result = None

        try:
            result = await operation(*args, **kwargs)
            success = True
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()

            metrics = {
                "operation_name": operation_name,
                "timestamp": start_time,
                "duration_ms": (end_time - start_time) * 1000,
                "memory_delta_mb": (end_memory - start_memory) / 1024 / 1024,
                "success": success,
                "error": error,
                "args_count": len(args),
                "kwargs_count": len(kwargs),
            }

            self._record_benchmark(metrics)

        return result, metrics

    def _get_memory_usage(self) -> float:
        """Get current memory usage in bytes."""
        try:

            process = psutil.Process(os.getpid())
            return process.memory_info().rss
        except ImportError:
            # psutil not available, return 0
            return 0.0

    def _record_benchmark(self, metrics: Dict[str, Any]) -> None:
        """Record benchmark metrics in history."""
        operation_name = metrics["operation_name"]

        # Update operation-specific benchmarks
        if operation_name not in self.benchmarks:
            self.benchmarks[operation_name] = {
                "total_calls": 0,
                "total_duration_ms": 0,
                "min_duration_ms": float("inf"),
                "max_duration_ms": 0,
                "success_count": 0,
                "error_count": 0,
                "last_call": None,
            }

        bench = self.benchmarks[operation_name]
        bench["total_calls"] += 1
        bench["total_duration_ms"] += metrics["duration_ms"]
        bench["min_duration_ms"] = min(bench["min_duration_ms"], metrics["duration_ms"])
        bench["max_duration_ms"] = max(bench["max_duration_ms"], metrics["duration_ms"])
        bench["last_call"] = metrics["timestamp"]

        if metrics["success"]:
            bench["success_count"] += 1
        else:
            bench["error_count"] += 1

        # Add to operation history
        self.operation_history.append(metrics)
        if len(self.operation_history) > self.max_history_size:
            self.operation_history.pop(0)

    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Dictionary with operation statistics
        """
        if operation_name not in self.benchmarks:
            return {"status": "no_data"}

        bench = self.benchmarks[operation_name]

        stats = {
            "operation_name": operation_name,
            "total_calls": bench["total_calls"],
            "average_duration_ms": bench["total_duration_ms"] / bench["total_calls"],
            "min_duration_ms": bench["min_duration_ms"],
            "max_duration_ms": bench["max_duration_ms"],
            "success_rate": (bench["success_count"] / bench["total_calls"]) * 100,
            "error_rate": (bench["error_count"] / bench["total_calls"]) * 100,
            "last_call": datetime.fromtimestamp(bench["last_call"]).isoformat(),
        }

        # Calculate percentiles from recent history
        recent_operations = [
            op
            for op in self.operation_history[-100:]  # Last 100 operations
            if op["operation_name"] == operation_name and op["success"]
        ]

        if recent_operations:
            durations = [op["duration_ms"] for op in recent_operations]
            durations.sort()

            stats["recent_performance"] = {
                "sample_size": len(durations),
                "p50_ms": self._percentile(durations, 50),
                "p95_ms": self._percentile(durations, 95),
                "p99_ms": self._percentile(durations, 99),
            }

        return stats

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value from a list of numbers."""
        if not data:
            return 0.0

        index = (percentile / 100.0) * (len(data) - 1)

        if index.is_integer():
            return data[int(index)]
        else:
            lower = data[int(index)]
            upper = data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all operation performance metrics.

        Returns:
            Dictionary with performance summary across all operations
        """
        summary = {
            "timestamp": time.time(),
            "total_operations": len(self.benchmarks),
            "total_calls": sum(b["total_calls"] for b in self.benchmarks.values()),
            "history_size": len(self.operation_history),
        }

        if self.benchmarks:
            # Calculate aggregate metrics
            all_durations = []
            total_errors = 0
            total_calls = 0

            for bench in self.benchmarks.values():
                total_calls += bench["total_calls"]
                total_errors += bench["error_count"]
                # Approximate average for each operation
                avg_duration = bench["total_duration_ms"] / bench["total_calls"]
                all_durations.extend([avg_duration] * bench["total_calls"])

            summary.update(
                {
                    "overall_success_rate": ((total_calls - total_errors) / total_calls)
                    * 100,
                    "overall_error_rate": (total_errors / total_calls) * 100,
                    "average_duration_ms": sum(all_durations) / len(all_durations),
                }
            )

            # Find slowest and fastest operations
            operations_by_avg_duration = [
                (name, bench["total_duration_ms"] / bench["total_calls"])
                for name, bench in self.benchmarks.items()
            ]
            operations_by_avg_duration.sort(key=lambda x: x[1])

            summary["fastest_operation"] = {
                "name": operations_by_avg_duration[0][0],
                "avg_duration_ms": operations_by_avg_duration[0][1],
            }
            summary["slowest_operation"] = {
                "name": operations_by_avg_duration[-1][0],
                "avg_duration_ms": operations_by_avg_duration[-1][1],
            }

        return summary

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate performance optimization recommendations.

        Returns:
            List of optimization recommendations
        """
        recommendations = []

        for operation_name, bench in self.benchmarks.items():
            avg_duration = bench["total_duration_ms"] / bench["total_calls"]
            error_rate = (bench["error_count"] / bench["total_calls"]) * 100

            # Slow operation recommendation
            if avg_duration > 1000:  # Slower than 1 second
                recommendations.append(
                    {
                        "type": "performance",
                        "severity": "high",
                        "operation": operation_name,
                        "issue": f"Slow average response time: {avg_duration:.2f}ms",
                        "suggestion": "Consider query optimization, indexing, or connection pooling improvements",
                    }
                )
            elif avg_duration > 500:  # Slower than 500ms
                recommendations.append(
                    {
                        "type": "performance",
                        "severity": "medium",
                        "operation": operation_name,
                        "issue": f"Moderate response time: {avg_duration:.2f}ms",
                        "suggestion": "Monitor for potential optimization opportunities",
                    }
                )

            # High error rate recommendation
            if error_rate > 5:  # More than 5% errors
                recommendations.append(
                    {
                        "type": "reliability",
                        "severity": "critical",
                        "operation": operation_name,
                        "issue": f"High error rate: {error_rate:.1f}%",
                        "suggestion": "Investigate error causes and implement proper error handling",
                    }
                )
            elif error_rate > 1:  # More than 1% errors
                recommendations.append(
                    {
                        "type": "reliability",
                        "severity": "medium",
                        "operation": operation_name,
                        "issue": f"Elevated error rate: {error_rate:.1f}%",
                        "suggestion": "Monitor error patterns and consider adding retry logic",
                    }
                )

        return recommendations

    def clear_benchmarks(self) -> None:
        """Clear all benchmark data."""
        self.benchmarks.clear()
        self.operation_history.clear()
        logger.info("Database benchmarks cleared")


# Global benchmark instance
global_database_benchmark = DatabaseBenchmark()
