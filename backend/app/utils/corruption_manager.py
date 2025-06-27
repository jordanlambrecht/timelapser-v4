# backend/app/utils/corruption_manager.py
"""
Corruption Manager

Centralized corruption detection database operations to eliminate duplication
between AsyncDatabase and SyncDatabase classes.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .database_helpers import DatabaseUtilities


class CorruptionManager:
    """
    Centralized manager for corruption detection database operations.

    This class consolidates all corruption-related database operations that were
    duplicated between AsyncDatabase and SyncDatabase classes.
    """

    @staticmethod
    def get_corruption_queries():
        """Get common corruption-related SQL queries"""
        return {
            "log_corruption_detection": """
                INSERT INTO corruption_logs (
                    camera_id, image_id, corruption_score, fast_score, heavy_score,
                    detection_details, action_taken, processing_time_ms
                ) VALUES (
                    %(camera_id)s, %(image_id)s, %(corruption_score)s, %(fast_score)s,
                    %(heavy_score)s, %(detection_details)s, %(action_taken)s, %(processing_time_ms)s
                )
                RETURNING *
            """,
            "get_corruption_logs": """
                SELECT
                    cl.*,
                    c.name as camera_name,
                    i.file_path as image_file_path
                FROM corruption_logs cl
                JOIN cameras c ON cl.camera_id = c.id
                LEFT JOIN images i ON cl.image_id = i.id
                WHERE (%(camera_id)s IS NULL OR cl.camera_id = %(camera_id)s)
                ORDER BY cl.created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """,
            "get_corruption_stats": """
                SELECT
                    COUNT(*) as total_evaluations,
                    COUNT(CASE WHEN corruption_score < %(threshold)s THEN 1 END) as low_quality_count,
                    COUNT(CASE WHEN action_taken = 'discarded' THEN 1 END) as discarded_count,
                    COUNT(CASE WHEN action_taken = 'retried' THEN 1 END) as retry_count,
                    AVG(corruption_score) as avg_corruption_score,
                    AVG(processing_time_ms) as avg_processing_time
                FROM corruption_logs
                WHERE camera_id = %(camera_id)s
                AND created_at >= %(start_date)s
            """,
            "get_recent_corruption_issues": """
                SELECT
                    cl.*,
                    i.file_path as image_file_path
                FROM corruption_logs cl
                LEFT JOIN images i ON cl.image_id = i.id
                WHERE cl.camera_id = %(camera_id)s
                AND cl.corruption_score < %(threshold)s
                AND cl.created_at >= %(start_date)s
                ORDER BY cl.created_at DESC
                LIMIT %(limit)s
            """,
            "update_camera_corruption_stats": """
                UPDATE cameras
                SET
                    lifetime_glitch_count = lifetime_glitch_count + 1,
                    consecutive_corruption_failures = CASE
                        WHEN %(action_taken)s = 'discarded' THEN consecutive_corruption_failures + 1
                        ELSE 0
                    END,
                    last_degraded_at = CASE
                        WHEN %(action_taken)s = 'discarded' THEN CURRENT_TIMESTAMP
                        ELSE last_degraded_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %(camera_id)s
                RETURNING consecutive_corruption_failures, lifetime_glitch_count
            """,
            "check_degraded_mode_trigger": """
                SELECT
                    consecutive_corruption_failures,
                    COUNT(*) as recent_failure_count,
                    COUNT(CASE WHEN action_taken = 'discarded' THEN 1 END) as recent_discarded_count
                FROM cameras c
                LEFT JOIN corruption_logs cl ON c.id = cl.camera_id
                    AND cl.created_at >= %(time_window_start)s
                WHERE c.id = %(camera_id)s
                GROUP BY c.id, consecutive_corruption_failures
            """,
            "reset_camera_degraded_mode": """
                UPDATE cameras
                SET
                    consecutive_corruption_failures = 0,
                    degraded_mode_active = false,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %(camera_id)s
                RETURNING *
            """,
            "get_camera_corruption_settings": """
                SELECT
                    corruption_detection_heavy,
                    degraded_mode_active,
                    consecutive_corruption_failures,
                    lifetime_glitch_count,
                    last_degraded_at
                FROM cameras
                WHERE id = %(camera_id)s
            """,
        }

    @staticmethod
    def prepare_corruption_log_data(
        camera_id: int,
        image_id: Optional[int],
        corruption_score: int,
        fast_score: Optional[int],
        heavy_score: Optional[int],
        detection_details: Dict[str, Any],
        action_taken: str,
        processing_time_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Prepare corruption log data for database insertion.

        Args:
            camera_id: ID of the camera
            image_id: ID of the image (if any)
            corruption_score: Overall corruption score (0-100)
            fast_score: Fast detection score
            heavy_score: Heavy detection score
            detection_details: Detailed detection results
            action_taken: Action taken (saved, discarded, retried)
            processing_time_ms: Processing time in milliseconds

        Returns:
            Dictionary of prepared corruption log data
        """
        return {
            "camera_id": camera_id,
            "image_id": image_id,
            "corruption_score": corruption_score,
            "fast_score": fast_score,
            "heavy_score": heavy_score,
            "detection_details": DatabaseUtilities.serialize_json_field(
                detection_details
            ),
            "action_taken": action_taken,
            "processing_time_ms": processing_time_ms,
        }

    @staticmethod
    def process_corruption_log_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a corruption log database row for API response.

        Args:
            row: Raw database row

        Returns:
            Processed corruption log dictionary
        """
        if not row:
            return {}

        # Convert row to dict if needed
        log_entry = dict(row) if hasattr(row, "keys") else row

        # Deserialize JSON fields
        if "detection_details" in log_entry:
            log_entry["detection_details"] = DatabaseUtilities.deserialize_json_field(
                log_entry["detection_details"]
            )

        # Format timestamps
        for field in ["created_at"]:
            if field in log_entry and log_entry[field]:
                if isinstance(log_entry[field], datetime):
                    log_entry[field] = log_entry[field].isoformat()

        # Add quality label
        score = log_entry.get("corruption_score", 100)
        log_entry["quality_label"] = CorruptionManager.get_quality_label(score)

        return log_entry

    @staticmethod
    def get_quality_label(score: int) -> str:
        """
        Get quality label for corruption score.

        Args:
            score: Corruption score (0-100)

        Returns:
            Quality label string
        """
        if score >= 90:
            return "excellent"
        elif score >= 70:
            return "good"
        elif score >= 50:
            return "fair"
        elif score >= 30:
            return "poor"
        else:
            return "critical"

    @staticmethod
    def validate_corruption_data(
        corruption_data: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Validate corruption detection data before database operations.

        Args:
            corruption_data: Corruption data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Required fields
        required_fields = ["camera_id", "corruption_score", "action_taken"]
        for field in required_fields:
            if field not in corruption_data:
                return False, f"Missing required field: {field}"

        # Validate camera_id
        try:
            camera_id = int(corruption_data["camera_id"])
            if camera_id <= 0:
                return False, "camera_id must be a positive integer"
        except (ValueError, TypeError):
            return False, "camera_id must be a valid integer"

        # Validate corruption_score
        try:
            score = int(corruption_data["corruption_score"])
            if score < 0 or score > 100:
                return False, "corruption_score must be between 0 and 100"
        except (ValueError, TypeError):
            return False, "corruption_score must be a valid integer"

        # Validate action_taken
        valid_actions = {"saved", "discarded", "retried"}
        if corruption_data["action_taken"] not in valid_actions:
            return (
                False,
                f"Invalid action_taken. Must be one of: {', '.join(valid_actions)}",
            )

        # Validate optional scores
        for score_field in ["fast_score", "heavy_score"]:
            if (
                score_field in corruption_data
                and corruption_data[score_field] is not None
            ):
                try:
                    score = int(corruption_data[score_field])
                    if score < 0 or score > 100:
                        return False, f"{score_field} must be between 0 and 100"
                except (ValueError, TypeError):
                    return False, f"{score_field} must be a valid integer"

        return True, None

    @staticmethod
    def check_degraded_mode_conditions(
        consecutive_failures: int,
        recent_failure_count: int,
        recent_discarded_count: int,
        time_window_minutes: int,
        total_recent_evaluations: int,
        degraded_config: Dict[str, Any],
    ) -> bool:
        """
        Check if camera should enter degraded mode based on corruption statistics.

        Args:
            consecutive_failures: Number of consecutive failures
            recent_failure_count: Number of failures in time window
            recent_discarded_count: Number of discarded images in time window
            time_window_minutes: Time window in minutes
            total_recent_evaluations: Total evaluations in time window
            degraded_config: Degraded mode configuration

        Returns:
            True if camera should enter degraded mode
        """
        # Extract configuration with defaults
        consecutive_threshold = degraded_config.get("consecutive_threshold", 10)
        failure_percentage = degraded_config.get("failure_percentage", 50)
        min_evaluations = degraded_config.get("min_evaluations", 5)

        # Check consecutive failures threshold
        if consecutive_failures >= consecutive_threshold:
            return True

        # Check failure percentage in time window
        if total_recent_evaluations >= min_evaluations:
            failure_rate = (recent_discarded_count / total_recent_evaluations) * 100
            if failure_rate >= failure_percentage:
                return True

        return False

    @staticmethod
    def get_global_corruption_settings_query() -> str:
        """Get query for global corruption detection settings"""
        return """
            SELECT key, value FROM settings
            WHERE key IN (
                'corruption_detection_enabled',
                'corruption_score_threshold',
                'corruption_auto_discard_enabled',
                'corruption_auto_disable_degraded',
                'corruption_degraded_consecutive_threshold',
                'corruption_degraded_time_window_minutes',
                'corruption_degraded_failure_percentage'
            )
        """

    @staticmethod
    def process_corruption_settings(
        settings_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Process corruption settings from database rows.

        Args:
            settings_rows: List of settings key-value rows

        Returns:
            Processed settings dictionary
        """
        settings_dict = {row["key"]: row["value"] for row in settings_rows}

        # Convert string values to appropriate types
        processed = {}

        # Boolean settings
        bool_settings = [
            "corruption_detection_enabled",
            "corruption_auto_discard_enabled",
            "corruption_auto_disable_degraded",
        ]
        for key in bool_settings:
            processed[key] = settings_dict.get(key, "true").lower() == "true"

        # Integer settings
        int_settings = {
            "corruption_score_threshold": 70,
            "corruption_degraded_consecutive_threshold": 10,
            "corruption_degraded_time_window_minutes": 30,
            "corruption_degraded_failure_percentage": 50,
        }
        for key, default in int_settings.items():
            try:
                processed[key] = int(settings_dict.get(key, default))
            except (ValueError, TypeError):
                processed[key] = default

        return processed

    @staticmethod
    def build_corruption_stats_summary(
        camera_id: int, days_back: int = 7
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build query for corruption statistics summary.

        Args:
            camera_id: ID of the camera
            days_back: Number of days to look back

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        query = """
            SELECT
                COUNT(*) as total_evaluations,
                COUNT(CASE WHEN corruption_score < 70 THEN 1 END) as flagged_count,
                COUNT(CASE WHEN action_taken = 'discarded' THEN 1 END) as discarded_count,
                COUNT(CASE WHEN action_taken = 'retried' THEN 1 END) as retry_count,
                AVG(corruption_score) as avg_score,
                MIN(corruption_score) as min_score,
                MAX(corruption_score) as max_score,
                AVG(processing_time_ms) as avg_processing_time,
                COUNT(CASE WHEN heavy_score IS NOT NULL THEN 1 END) as heavy_detection_count
            FROM corruption_logs
            WHERE camera_id = %(camera_id)s
            AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%(days_back)s days'
        """

        params = {"camera_id": camera_id, "days_back": days_back}

        return query, params
