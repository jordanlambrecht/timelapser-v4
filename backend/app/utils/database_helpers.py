# backend/app/utils/database_helpers.py
"""
Database Helper Functions

Common database operation patterns and utilities to reduce duplication
between AsyncDatabase and SyncDatabase classes.
"""

from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, date
import json
from loguru import logger


class DatabaseQueryBuilder:
    """
    Helper class for building dynamic SQL queries.

    Provides methods to build common query patterns with proper parameterization
    and security considerations.
    """

    # @staticmethod
    # def build_select_query(
    #     table_name: str,
    #     fields: List[str] = None,
    #     joins: List[str] = None,
    #     where_conditions: Dict[str, Any] = None,
    #     order_by: str = None,
    #     limit: int = None,
    #     offset: int = None,
    # ) -> Tuple[str, Dict[str, Any]]:
    #     """
    #     Build a SELECT query with dynamic conditions.

    #     Args:
    #         table_name: Primary table name
    #         fields: List of fields to select (defaults to *)
    #         joins: List of JOIN clauses
    #         where_conditions: Dictionary of WHERE conditions
    #         order_by: ORDER BY clause
    #         limit: LIMIT value
    #         offset: OFFSET value

    #     Returns:
    #         Tuple of (query_string, parameters_dict)
    #     """
    #     # Build SELECT clause
    #     if fields:
    #         select_clause = ", ".join(fields)
    #     else:
    #         select_clause = "*"

    #     query_parts = [f"SELECT {select_clause} FROM {table_name}"]
    #     params = {}

    #     # Add JOINs
    #     if joins:
    #         query_parts.extend(joins)

    #     # Add WHERE conditions
    #     if where_conditions:
    #         where_clauses = []
    #         for field, value in where_conditions.items():
    #             if value is not None:
    #                 where_clauses.append(f"{field} = %({field})s")
    #                 params[field] = value
    #             else:
    #                 where_clauses.append(f"{field} IS NULL")

    #         if where_clauses:
    #             query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

    #     # Add ORDER BY
    #     if order_by:
    #         query_parts.append(f"ORDER BY {order_by}")

    #     # Add LIMIT and OFFSET
    #     if limit:
    #         query_parts.append(f"LIMIT {limit}")
    #     if offset:
    #         query_parts.append(f"OFFSET {offset}")

    #     return " ".join(query_parts), params

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
            current_date = date.today()

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

        # Each failure reduces success rate by 10%
        reduction = min(consecutive_failures * 10, 100)
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

    CAMERAS_WITH_IMAGES_LATERAL = """
        SELECT 
            c.*,
            t.status as timelapse_status,
            t.id as timelapse_id,
            t.name as timelapse_name,
            i.id as last_image_id,
            i.captured_at as last_image_captured_at,
            i.file_path as last_image_file_path,
            i.file_size as last_image_file_size,
            i.day_number as last_image_day_number,
            i.thumbnail_path as last_image_thumbnail_path,
            i.thumbnail_size as last_image_thumbnail_size,
            i.small_path as last_image_small_path,
            i.small_size as last_image_small_size
        FROM cameras c 
        LEFT JOIN timelapses t ON c.active_timelapse_id = t.id 
        LEFT JOIN LATERAL (
            SELECT id, captured_at, file_path, file_size, day_number,
                   thumbnail_path, thumbnail_size, small_path, small_size
            FROM images 
            WHERE camera_id = c.id 
            ORDER BY captured_at DESC 
            LIMIT 1
        ) i ON true
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

    # Image queries
    LATEST_IMAGE_FOR_CAMERA = """
        SELECT 
            i.*,
            c.name as camera_name
        FROM cameras c
        LEFT JOIN LATERAL (
            SELECT id, captured_at, file_path, file_size, day_number,
                   thumbnail_path, thumbnail_size, small_path, small_size,
                   camera_id, timelapse_id, created_at
            FROM images 
            WHERE camera_id = c.id 
            ORDER BY captured_at DESC 
            LIMIT 1
        ) i ON true
        WHERE c.id = %(camera_id)s AND i.id IS NOT NULL
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
