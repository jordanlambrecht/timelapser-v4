# backend/app/utils/video_record_manager.py
"""
Video Record Manager

Centralized video database operations to eliminate duplication between
AsyncDatabase and SyncDatabase classes.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from .database_helpers import DatabaseQueryBuilder, DatabaseUtilities


class VideoRecordManager:
    """
    Centralized manager for video database operations.

    This class consolidates all video-related database operations that were
    duplicated between AsyncDatabase and SyncDatabase classes.
    """

    @staticmethod
    def get_video_queries():
        """Get common video-related SQL queries"""
        return {
            "get_video_by_id": """
                SELECT 
                    v.*,
                    t.name as timelapse_name,
                    c.name as camera_name
                FROM videos v
                JOIN timelapses t ON v.timelapse_id = t.id
                JOIN cameras c ON t.camera_id = c.id
                WHERE v.id = %(video_id)s
            """,
            "get_videos_for_timelapse": """
                SELECT * FROM videos 
                WHERE timelapse_id = %(timelapse_id)s 
                ORDER BY created_at DESC
            """,
            "get_pending_videos": """
                SELECT v.*, t.name as timelapse_name 
                FROM videos v
                JOIN timelapses t ON v.timelapse_id = t.id
                WHERE v.status = 'pending'
                ORDER BY v.created_at ASC
            """,
            "update_video_status": """
                UPDATE videos 
                SET status = %(status)s, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %(video_id)s
                RETURNING *
            """,
            "update_video_progress": """
                UPDATE videos 
                SET progress = %(progress)s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %(video_id)s
                RETURNING *
            """,
            "delete_video": """
                DELETE FROM videos 
                WHERE id = %(video_id)s
                RETURNING *
            """,
        }

    @staticmethod
    def prepare_video_data(
        timelapse_id: int,
        name: str,
        video_type: str = "manual",
        settings: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Prepare video data for database insertion.

        Args:
            timelapse_id: ID of the timelapse
            name: Video name
            video_type: Type of video (manual, daily, etc.)
            settings: Video generation settings
            **kwargs: Additional fields

        Returns:
            Dictionary of prepared video data
        """
        # Base video data
        video_data = {
            "timelapse_id": timelapse_id,
            "name": name,
            "video_type": video_type,
            "status": "pending",
            "progress": 0,
            "settings": DatabaseUtilities.serialize_json_field(settings or {}),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        # Add any additional fields
        video_data.update(kwargs)

        return video_data

    @staticmethod
    def build_create_video_query(
        video_data: Dict[str, Any],
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build INSERT query for creating a video record.

        Args:
            video_data: Video data dictionary

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        allowed_fields = {
            "timelapse_id",
            "name",
            "video_type",
            "status",
            "progress",
            "settings",
            "file_path",
            "file_size",
            "duration",
            "fps",
            "resolution",
            "total_frames",
            "error_message",
            "created_at",
            "updated_at",
        }

        return DatabaseQueryBuilder.build_insert_query(
            table_name="videos",
            data=video_data,
            allowed_fields=allowed_fields,
            returning_field="*",
        )

    @staticmethod
    def build_update_video_query(
        video_id: int, updates: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build UPDATE query for updating a video record.

        Args:
            video_id: ID of the video to update
            updates: Dictionary of fields to update

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        allowed_fields = {
            "name",
            "status",
            "progress",
            "file_path",
            "file_size",
            "duration",
            "fps",
            "resolution",
            "total_frames",
            "error_message",
        }

        return DatabaseQueryBuilder.build_update_query(
            table_name="videos",
            updates=updates,
            where_conditions={"id": video_id},
            allowed_fields=allowed_fields,
        )

    @staticmethod
    def process_video_row(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a video database row for API response.

        Args:
            row: Raw database row

        Returns:
            Processed video dictionary
        """
        if not row:
            return {}

        # Convert row to dict if needed
        video = dict(row) if hasattr(row, "keys") else row

        # Deserialize JSON fields
        if "settings" in video:
            video["settings"] = DatabaseUtilities.deserialize_json_field(
                video["settings"]
            )

        # Format timestamps
        for field in ["created_at", "updated_at"]:
            if field in video and video[field]:
                if isinstance(video[field], datetime):
                    video[field] = video[field].isoformat()

        # Calculate derived fields
        if video.get("status") == "completed" and video.get("file_size"):
            video["file_size_formatted"] = DatabaseUtilities.format_file_size(
                video["file_size"]
            )

        return video

    @staticmethod
    def validate_video_data(video_data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate video data before database operations.

        Args:
            video_data: Video data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Required fields
        required_fields = ["timelapse_id", "name"]
        for field in required_fields:
            if field not in video_data or video_data[field] is None:
                return False, f"Missing required field: {field}"

        # Validate timelapse_id is positive integer
        try:
            timelapse_id = int(video_data["timelapse_id"])
            if timelapse_id <= 0:
                return False, "timelapse_id must be a positive integer"
        except (ValueError, TypeError):
            return False, "timelapse_id must be a valid integer"

        # Validate name is non-empty string
        name = video_data.get("name", "").strip()
        if not name:
            return False, "Video name cannot be empty"
        if len(name) > 255:
            return False, "Video name cannot exceed 255 characters"

        # Validate video_type if provided
        valid_video_types = {
            "manual",
            "daily",
            "weekly",
            "range",
            "continuous",
            "recent",
        }
        if "video_type" in video_data:
            if video_data["video_type"] not in valid_video_types:
                return (
                    False,
                    f"Invalid video_type. Must be one of: {', '.join(valid_video_types)}",
                )

        # Validate status if provided
        valid_statuses = {"pending", "processing", "completed", "failed", "cancelled"}
        if "status" in video_data:
            if video_data["status"] not in valid_statuses:
                return (
                    False,
                    f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
                )

        # Validate progress if provided
        if "progress" in video_data:
            try:
                progress = float(video_data["progress"])
                if progress < 0 or progress > 100:
                    return False, "Progress must be between 0 and 100"
            except (ValueError, TypeError):
                return False, "Progress must be a valid number"

        return True, None

    @staticmethod
    def get_video_statistics_query() -> str:
        """Get query for video statistics"""
        return """
            SELECT 
                COUNT(*) as total_videos,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_videos,
                COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_videos,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_videos,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN file_size END), 0) as total_file_size,
                COALESCE(AVG(CASE WHEN status = 'completed' THEN duration END), 0) as avg_duration
            FROM videos
        """

    @staticmethod
    def get_effective_video_settings_logic(
        timelapse_settings: Optional[Dict[str, Any]],
        camera_settings: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply settings inheritance logic for video generation.

        Args:
            timelapse_settings: Timelapse-specific video settings
            camera_settings: Camera default video settings

        Returns:
            Effective video settings with inheritance applied
        """
        # Default settings
        defaults = {
            "fps": 30,
            "quality": "high",
            "resolution": "original",
            "max_duration": 60,
            "min_duration": 5,
            "overlay_enabled": True,
            "overlay_position": "bottom_right",
            "overlay_font_size": 24,
        }

        # Apply inheritance: defaults -> camera -> timelapse
        effective_settings = defaults.copy()

        if camera_settings:
            effective_settings.update(camera_settings)

        if timelapse_settings:
            effective_settings.update(timelapse_settings)

        return effective_settings
