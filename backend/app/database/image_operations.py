"""
Image database operations module - Composition-based architecture.

This module handles all image-related database operations using dependency injection
instead of mixin inheritance, providing type-safe Pydantic model interfaces.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from loguru import logger
from psycopg.rows import class_row

from ..config import settings
from ..constants import DEFAULT_PAGE_SIZE, MAX_BULK_OPERATION_ITEMS
from ..models.image_model import Image
from ..utils.database_helpers import DatabaseUtilities
from .core import AsyncDatabase, SyncDatabase


def _compute_thumbnail_paths(
    image: Image,
) -> tuple[Optional[str], Optional[str], Optional[int], Optional[int]]:
    """
    Compute thumbnail and small image paths based on the main image path.

    Args:
        image: Base Image model

    Returns:
        Tuple of (thumbnail_path, small_path, thumbnail_size, small_size)
    """
    if not image.file_path:
        return None, None, None, None

    try:
        # Get base path structure
        base_path = Path(settings.data_directory)
        image_path = Path(image.file_path)

        # Extract components from original image path
        # Expected: data/cameras/camera-{id}/images/YYYY-MM-DD/filename.jpg
        path_parts = image_path.parts

        if len(path_parts) >= 5:
            # Build thumbnail paths following the same structure
            # data/cameras/camera-{id}/thumbnails/YYYY-MM-DD/filename.jpg
            # data/cameras/camera-{id}/small/YYYY-MM-DD/filename.jpg

            camera_dir = path_parts[-4]  # camera-{id}
            date_dir = path_parts[-2]  # YYYY-MM-DD
            filename = path_parts[-1]  # original filename

            thumbnail_path = (
                base_path / "cameras" / camera_dir / "thumbnails" / date_dir / filename
            )
            small_path = (
                base_path / "cameras" / camera_dir / "small" / date_dir / filename
            )

            # Check if files exist and get sizes
            thumbnail_size = (
                thumbnail_path.stat().st_size if thumbnail_path.exists() else None
            )
            small_size = small_path.stat().st_size if small_path.exists() else None

            return (
                str(thumbnail_path) if thumbnail_path.exists() else None,
                str(small_path) if small_path.exists() else None,
                thumbnail_size,
                small_size,
            )
    except (OSError, ValueError, AttributeError):
        # If path computation fails, return None values
        pass

    return None, None, None, None


def _row_to_image_shared(row: Dict[str, Any]) -> Image:
    """
    Shared helper function for converting database row to Image model.

    This eliminates duplicate logic between async and sync classes.
    Filters fields that belong to Image model and creates proper instance.

    Args:
        row: Database row data as dictionary

    Returns:
        Image model instance
    """
    # Filter fields that belong to Image model
    image_fields = {k: v for k, v in row.items() if k in Image.model_fields.keys()}
    return Image(**image_fields)


class ImageOperations:
    """
    Image database operations using composition pattern.

    This class receives database instance via dependency injection,
    providing type-safe Pydantic model interfaces.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        """
        Initialize ImageOperations with async database instance.

        Args:
            db: AsyncDatabase instance
        """
        self.db = db

    def _row_to_image(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model."""
        return _row_to_image_shared(row)

    def _row_to_image_with_details(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model with additional fields."""
        # Extract base image fields
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields.keys()}

        # Add additional computed fields to Image model
        details_fields = image_fields.copy()
        if "camera_name" in row:
            details_fields["camera_name"] = row["camera_name"]
        if "timelapse_status" in row:
            details_fields["timelapse_status"] = row["timelapse_status"]

        return Image(**details_fields)

    async def set_image_corruption_score(self, image_id: int, score: float) -> bool:
        """
        Update the corruption_score (quality score) for an image.

        Args:
            image_id: ID of the image to update
            score: New quality/corruption score

        Returns:
            True if update was successful
        """
        query = (
            "UPDATE images SET corruption_score = %s, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s"
        )
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (score, image_id))
                return cur.rowcount > 0

    async def get_images(
        self,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> List[Image]:
        """
        Retrieve images with pagination, ordering, and optional filtering.

        Args:
            limit: Number of items to return
            offset: Number of items to skip
            order_by: Column to order by
            order_dir: Sort direction (ASC/DESC)
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            List of Image model instances
        """
        # Build WHERE conditions
        where_conditions = {}
        if timelapse_id is not None:
            where_conditions["timelapse_id"] = timelapse_id
        if camera_id is not None:
            where_conditions["camera_id"] = camera_id

        # Enhanced query with JOINs for computed fields
        query_parts = [
            """
            SELECT 
                i.*,
                c.name as camera_name,
                t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
        """
        ]
        params = []

        # Add WHERE clause if filters provided
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"i.{field} = %s")
                params.append(value)
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        # Add ORDER BY and pagination
        query_parts.append(f"ORDER BY i.{order_by} {order_dir}")
        query_parts.append("LIMIT %s OFFSET %s")
        params.extend([limit, offset])

        query = " ".join(query_parts)

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                # Convert to Image models with computed fields populated
                images = []
                for row in results:
                    image_dict = dict(row)

                    # Create base Image from database fields
                    base_image = self._row_to_image(row)

                    # Add computed fields to the Image model
                    base_image.camera_name = image_dict.get("camera_name")
                    base_image.timelapse_status = image_dict.get("timelapse_status")

                    # Compute thumbnail paths and sizes
                    thumbnail_path, small_path, thumbnail_size, small_size = (
                        _compute_thumbnail_paths(base_image)
                    )
                    base_image.thumbnail_path = thumbnail_path
                    base_image.small_path = small_path
                    base_image.thumbnail_size = thumbnail_size
                    base_image.small_size = small_size

                    images.append(base_image)

                return images

    async def get_images_count(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> int:
        """
        Get total count of images matching the filters.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            Total count of matching images
        """
        # Build WHERE conditions
        where_conditions = {}
        if timelapse_id is not None:
            where_conditions["timelapse_id"] = timelapse_id
        if camera_id is not None:
            where_conditions["camera_id"] = camera_id

        # Build count query
        query_parts = ["SELECT COUNT(*) FROM images"]
        params = []

        # Add WHERE clause if filters provided
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"{field} = %s")
                params.append(value)
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        query = " ".join(query_parts)

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return result[0] if result else 0

    async def get_images_by_timelapse(self, timelapse_id: int) -> List[Image]:
        """Get all images for a specific timelapse."""
        query = "SELECT * FROM images WHERE timelapse_id = %s ORDER BY captured_at ASC"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def get_images_by_camera(self, camera_id: int) -> List[Image]:
        """Get all images for a specific camera."""
        query = "SELECT * FROM images WHERE camera_id = %s ORDER BY captured_at DESC"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def get_images_by_date_range(
        self, start_date: str, end_date: str
    ) -> List[Image]:
        """Get images within a specific date range."""
        query = """
        SELECT * FROM images 
        WHERE captured_at >= %s AND captured_at <= %s 
        ORDER BY captured_at DESC
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (start_date, end_date))
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def get_flagged_images(self) -> List[Image]:
        """Get all flagged images."""
        query = "SELECT * FROM images WHERE is_flagged = true ORDER BY captured_at DESC"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """
        Retrieve a specific image by ID.

        Args:
            image_id: ID of the image to retrieve

        Returns:
            Image model instance, or None if not found
        """
        query = "SELECT * FROM images WHERE id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (image_id,))
                result = await cur.fetchone()
                return self._row_to_image(result) if result else None

    async def cleanup_old_images(self, days_to_keep: int) -> int:
        """
        Delete images older than specified days (async version).

        Pure database operation - no business logic or validation.

        Args:
            days_to_keep: Number of days to keep images

        Returns:
            Number of images deleted
        """
        query = """
        DELETE FROM images
        WHERE captured_at < NOW() - INTERVAL '%s days'
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (days_to_keep,))
                return cur.rowcount or 0

    async def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image (async version for API endpoints).

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance
        """
        query = """
        INSERT INTO images (
            timelapse_id, camera_id, file_path, filename, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            corruption_score, is_flagged,
            weather_temperature, weather_conditions, weather_icon, weather_fetched_at
        ) VALUES (
            %(timelapse_id)s, %(camera_id)s, %(file_path)s, %(filename)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(corruption_score)s, %(is_flagged)s,
            %(weather_temperature)s, %(weather_conditions)s, %(weather_icon)s, %(weather_fetched_at)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, image_data)
                result = await cur.fetchone()
                return self._row_to_image(result)

    async def update_image_thumbnails(
        self, image_id: int, thumbnail_data: Dict[str, Any]
    ) -> bool:
        """
        Update thumbnail paths and sizes for an image (async version).

        Pure database operation - validation should be done in service layer.

        Args:
            image_id: ID of the image to update
            thumbnail_data: Dictionary containing thumbnail paths and sizes

        Returns:
            True if update was successful
        """
        # Build dynamic update query
        set_clauses = [f"{field} = %({field})s" for field in thumbnail_data.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        query = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %(id)s"
        thumbnail_data["id"] = image_id

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, thumbnail_data)
                return cur.rowcount > 0

    async def get_latest_image_for_camera(self, camera_id: int) -> Optional[Image]:
        """
        Get the most recent image for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Latest Image model instance, or None if no images found
        """
        query = """
        SELECT * FROM images 
        WHERE camera_id = %s 
        ORDER BY captured_at DESC 
        LIMIT 1
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                result = await cur.fetchone()
                return self._row_to_image(result) if result else None

    async def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get total count of images for a timelapse (async version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total number of images
        """
        query = "SELECT COUNT(*) FROM images WHERE timelapse_id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                result = await cur.fetchone()
                return result[0] if result else 0

    async def get_images_without_thumbnails(
        self, limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images that are missing thumbnail files (async version).

        Args:
            limit: Maximum number of images to return

        Returns:
            List of Image models missing thumbnails
        """
        query = """
        SELECT i.*
        FROM images i
        WHERE i.thumbnail_path IS NULL OR i.small_path IS NULL
        ORDER BY i.captured_at DESC
        LIMIT %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (limit,))
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def delete_image(self, image_id: int) -> bool:
        """
        Delete a specific image by ID.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if image was deleted successfully
        """
        query = "DELETE FROM images WHERE id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (image_id,))
                return cur.rowcount > 0

    async def delete_images_by_timelapse(self, timelapse_id: int) -> int:
        """
        Delete all images for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images deleted
        """
        query = "DELETE FROM images WHERE timelapse_id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                return cur.rowcount or 0

    async def calculate_day_number(
        self, timelapse_id: int, captured_at: datetime
    ) -> int:
        """
        Calculate the day number for an image within a timelapse.

        Args:
            timelapse_id: ID of the timelapse
            captured_at: When the image was captured

        Returns:
            Day number (1-based)
        """
        # Get timelapse start date
        query = "SELECT start_time FROM timelapses WHERE id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                result = await cur.fetchone()
                if not result:
                    return 1

                start_date = result["start_time"].date()
                current_date = captured_at.date()

                return DatabaseUtilities.calculate_day_number(start_date, current_date)


class SyncImageOperations:
    """
    Sync image database operations for worker processes.

    Uses sync database methods for worker process compatibility.
    """

    def __init__(self, db: SyncDatabase) -> None:
        """
        Initialize SyncImageOperations with sync database instance.

        Args:
            db: SyncDatabase instance
        """
        self.db = db

    def _row_to_image(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model."""
        return _row_to_image_shared(row)

    def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image (sync version for worker).

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance
        """
        query = """
        INSERT INTO images (
            timelapse_id, camera_id, file_path, filename, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            corruption_score, is_flagged,
            weather_temperature, weather_conditions, weather_icon, weather_fetched_at
        ) VALUES (
            %(timelapse_id)s, %(camera_id)s, %(file_path)s, %(filename)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(corruption_score)s, %(is_flagged)s,
            %(weather_temperature)s, %(weather_conditions)s, %(weather_icon)s, %(weather_fetched_at)s
        ) RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, image_data)
                result = cur.fetchone()
                return self._row_to_image(result)

    def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get total count of images for a timelapse (sync version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total number of images
        """
        query = "SELECT COUNT(*) FROM images WHERE timelapse_id = %s"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                result = cur.fetchone()
                return result[0] if result else 0

    def get_images(
        self,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> List[Image]:
        """
        Retrieve images with pagination, ordering, and optional filtering (sync version).

        Args:
            limit: Number of items to return
            offset: Number of items to skip
            order_by: Column to order by
            order_dir: Sort direction (ASC/DESC)
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            List of Image model instances
        """
        # Build WHERE conditions
        where_conditions = {}
        if timelapse_id is not None:
            where_conditions["timelapse_id"] = timelapse_id
        if camera_id is not None:
            where_conditions["camera_id"] = camera_id

        # Enhanced query with JOINs for computed fields (sync version)
        query_parts = [
            """
            SELECT 
                i.*,
                c.name as camera_name,
                t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
        """
        ]
        params = []

        # Add WHERE clause if filters provided
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"i.{field} = %s")
                params.append(value)
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        # Add ORDER BY and pagination
        query_parts.append(f"ORDER BY i.{order_by} {order_dir}")
        query_parts.append("LIMIT %s OFFSET %s")
        params.extend([limit, offset])

        query = " ".join(query_parts)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

                # Convert to Image models with computed fields populated
                images = []
                for row in results:
                    image_dict = dict(row)

                    # Create base Image from database fields
                    base_image = self._row_to_image(row)

                    # Add computed fields to the Image model
                    base_image.camera_name = image_dict.get("camera_name")
                    base_image.timelapse_status = image_dict.get("timelapse_status")

                    # Compute thumbnail paths and sizes
                    thumbnail_path, small_path, thumbnail_size, small_size = (
                        _compute_thumbnail_paths(base_image)
                    )
                    base_image.thumbnail_path = thumbnail_path
                    base_image.small_path = small_path
                    base_image.thumbnail_size = thumbnail_size
                    base_image.small_size = small_size

                    images.append(base_image)

                return images

    def get_images_count(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> int:
        """
        Get total count of images matching the filters (sync version).

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            Total count of matching images
        """
        # Build WHERE conditions
        where_conditions = {}
        if timelapse_id is not None:
            where_conditions["timelapse_id"] = timelapse_id
        if camera_id is not None:
            where_conditions["camera_id"] = camera_id

        # Build count query
        query_parts = ["SELECT COUNT(*) FROM images"]
        params = []

        # Add WHERE clause if filters provided
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"{field} = %s")
                params.append(value)
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        query = " ".join(query_parts)

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return result[0] if result else 0

    def get_images_by_timelapse(self, timelapse_id: int) -> List[Image]:
        """Get all images for a specific timelapse (sync version)."""
        query = "SELECT * FROM images WHERE timelapse_id = %s ORDER BY captured_at ASC"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_images_by_camera(self, camera_id: int) -> List[Image]:
        """Get all images for a specific camera (sync version)."""
        query = "SELECT * FROM images WHERE camera_id = %s ORDER BY captured_at DESC"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (camera_id,))
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_images_by_date_range(self, start_date: str, end_date: str) -> List[Image]:
        """Get images within a specific date range (sync version)."""
        query = """
        SELECT * FROM images 
        WHERE captured_at >= %s AND captured_at <= %s 
        ORDER BY captured_at DESC
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (start_date, end_date))
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_flagged_images(self) -> List[Image]:
        """Get all flagged images (sync version)."""
        query = "SELECT * FROM images WHERE is_flagged = true ORDER BY captured_at DESC"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_images_for_timelapse(self, timelapse_id: int) -> List[Image]:
        """
        Get all images for a specific timelapse (sync version for worker).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            List of Image model instances ordered by captured_at
        """
        query = """
        SELECT * FROM images
        WHERE timelapse_id = %s
        ORDER BY captured_at ASC
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def cleanup_old_images(self, days_to_keep: int) -> int:
        """
        Delete images older than specified days (sync version).

        Pure database operation - no business logic or validation.

        Args:
            days_to_keep: Number of days to keep images

        Returns:
            Number of images deleted
        """
        query = """
        DELETE FROM images
        WHERE captured_at < NOW() - INTERVAL '%s days'
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (days_to_keep,))
                return cur.rowcount or 0

    def update_image_thumbnails(
        self, image_id: int, thumbnail_data: Dict[str, Any]
    ) -> bool:
        """
        Update thumbnail paths and sizes for an image (sync version).

        Pure database operation - validation should be done in service layer.

        Args:
            image_id: ID of the image to update
            thumbnail_data: Dictionary containing thumbnail paths and sizes

        Returns:
            True if update was successful
        """
        # Build dynamic update query
        set_clauses = [f"{field} = %({field})s" for field in thumbnail_data.keys()]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")

        query = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %(id)s"
        thumbnail_data["id"] = image_id

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, thumbnail_data)
                return cur.rowcount > 0

    def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """Get a specific image by ID."""
        query = "SELECT * FROM images WHERE id = %s"
        with self.db.get_connection() as conn:
            with conn.cursor(row_factory=class_row(Image)) as cur:
                cur.execute(query, (image_id,))
                return cur.fetchone()

    def delete_image(self, image_id: int) -> None:
        """
        Delete an image record from the database.

        Args:
            image_id: The ID of the image to delete.
        """
        query = "DELETE FROM images WHERE id = %s"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (image_id,))
        logger.info(f"🗑️ Deleted image record with ID: {image_id}")


class AsyncImageOperations:
    """Async image database operations for FastAPI endpoints."""

    def __init__(self, db: AsyncDatabase):
        """Initialize AsyncImageOperations with async database instance."""
        self.db = db

    def _row_to_image_with_details(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model with additional fields."""
        # Extract base image fields
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields.keys()}

        # Add additional computed fields to Image model
        details_fields = image_fields.copy()
        if "camera_name" in row:
            details_fields["camera_name"] = row["camera_name"]
        if "timelapse_status" in row:
            details_fields["timelapse_status"] = row["timelapse_status"]

        return Image(**details_fields)

    async def get_images_by_ids(self, image_ids: List[int]) -> List[Image]:
        """
        Get images by specific IDs with details.

        Args:
            image_ids: List of image IDs to retrieve

        Returns:
            List of Image models
        """
        placeholders = ",".join(["%s" for _ in image_ids])
        query = f"""
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.id IN ({placeholders})
            ORDER BY i.captured_at DESC
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, image_ids)
                results = await cur.fetchall()
                return [self._row_to_image_with_details(dict(row)) for row in results]

    async def get_images_by_cameras(
        self, camera_ids: List[int], limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images from specific cameras with details.

        Args:
            camera_ids: List of camera IDs
            limit: Maximum number of images to return

        Returns:
            List of Image models
        """
        placeholders = ",".join(["%s" for _ in camera_ids])
        query = f"""
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.camera_id IN ({placeholders})
            ORDER BY i.captured_at DESC
            LIMIT %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, camera_ids + [limit])
                results = await cur.fetchall()
                return [self._row_to_image_with_details(dict(row)) for row in results]

    async def get_images_by_timelapses(
        self, timelapse_ids: List[int], limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images from specific timelapses with details.

        Args:
            timelapse_ids: List of timelapse IDs
            limit: Maximum number of images to return

        Returns:
            List of Image models
        """
        placeholders = ",".join(["%s" for _ in timelapse_ids])
        query = f"""
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.timelapse_id IN ({placeholders})
            ORDER BY i.captured_at DESC
            LIMIT %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, timelapse_ids + [limit])
                results = await cur.fetchall()
                return [self._row_to_image_with_details(dict(row)) for row in results]

    async def get_images_with_thumbnails(
        self, limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images that have thumbnail paths for verification.

        Args:
            limit: Maximum number of images to return

        Returns:
            List of Image models that have thumbnail references
        """
        query = """
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.thumbnail_path IS NOT NULL OR i.small_path IS NOT NULL
            ORDER BY i.captured_at DESC
            LIMIT %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (limit,))
                results = await cur.fetchall()
                return [self._row_to_image_with_details(dict(row)) for row in results]

    async def update_thumbnail_paths(
        self,
        image_id: int,
        thumbnail_path: Optional[str] = None,
        small_path: Optional[str] = None,
        thumbnail_size: Optional[int] = None,
        small_size: Optional[int] = None,
    ) -> bool:
        """
        Update thumbnail and small image paths for an image.

        Args:
            image_id: ID of the image to update
            thumbnail_path: Path to the thumbnail file
            small_path: Path to the small image file
            thumbnail_size: Size of thumbnail file in bytes
            small_size: Size of small file in bytes

        Returns:
            True if update successful
        """
        query = """
            UPDATE images 
            SET thumbnail_path = %s, 
                small_path = %s,
                thumbnail_size = %s,
                small_size = %s,
                updated_at = NOW()
            WHERE id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query,
                    (thumbnail_path, small_path, thumbnail_size, small_size, image_id),
                )
                return cur.rowcount > 0

    async def clear_thumbnail_paths(self, image_id: int) -> bool:
        """
        Clear thumbnail and small image paths for an image.

        Args:
            image_id: ID of the image to update

        Returns:
            True if update successful
        """
        query = """
            UPDATE images 
            SET thumbnail_path = NULL, 
                small_path = NULL,
                thumbnail_size = NULL,
                small_size = NULL,
                updated_at = NOW()
            WHERE id = %s
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (image_id,))
                return cur.rowcount > 0

    async def clear_all_thumbnail_paths(self) -> int:
        """
        Clear thumbnail and small image paths for all images.

        Returns:
            Number of images updated
        """
        query = """
            UPDATE images
            SET thumbnail_path = NULL,
                small_path = NULL,
                thumbnail_size = NULL,
                small_size = NULL,
                updated_at = NOW()
            WHERE thumbnail_path IS NOT NULL OR small_path IS NOT NULL
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                return cur.rowcount

    async def get_all_thumbnail_paths(self) -> List[Dict[str, str]]:
        """
        Get all thumbnail and small image paths from the database.

        Returns:
            List of dictionaries with thumbnail_path and small_path
        """
        query = """
            SELECT
                thumbnail_path,
                small_path
            FROM images
            WHERE thumbnail_path IS NOT NULL OR small_path IS NOT NULL
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                return [dict(row) for row in results] if results else []

    async def get_thumbnail_coverage_statistics(self) -> Dict[str, int]:
        """
        Get statistics about thumbnail coverage across all images.

        Returns:
            Dictionary with thumbnail coverage counts
        """
        query = """
            SELECT
                COUNT(*) as total_images,
                COUNT(thumbnail_path) as images_with_thumbnails,
                COUNT(small_path) as images_with_small,
                COUNT(*) - COUNT(thumbnail_path) as images_without_thumbnails
            FROM images
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                result = await cur.fetchone()
                return (
                    dict(result)
                    if result
                    else {
                        "total_images": 0,
                        "images_with_thumbnails": 0,
                        "images_with_small": 0,
                        "images_without_thumbnails": 0,
                    }
                )

    async def get_image_statistics(
        self, camera_id: Optional[int] = None, timelapse_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive image statistics.

        Args:
            camera_id: Optional camera ID to filter by
            timelapse_id: Optional timelapse ID to filter by

        Returns:
            Dictionary with comprehensive image statistics
        """
        # Build WHERE clause based on filters
        where_conditions = []
        params = []

        if camera_id:
            where_conditions.append("camera_id = %s")
            params.append(camera_id)

        if timelapse_id:
            where_conditions.append("timelapse_id = %s")
            params.append(timelapse_id)

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        query = f"""
            SELECT
                COUNT(*) as total_images,
                COUNT(CASE WHEN captured_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 1 END) as last_24h_images,
                COUNT(CASE WHEN captured_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 1 END) as last_7d_images,
                SUM(COALESCE(file_size, 0)) as total_file_size,
                AVG(COALESCE(file_size, 0)) as average_file_size,
                COUNT(CASE WHEN is_flagged = true THEN 1 END) as flagged_images,
                AVG(CASE WHEN corruption_score IS NOT NULL THEN corruption_score ELSE 100 END) as avg_quality_score,
                MIN(captured_at) as first_image_at,
                MAX(captured_at) as last_image_at,
                COUNT(DISTINCT camera_id) as unique_cameras,
                COUNT(DISTINCT timelapse_id) as unique_timelapses
            FROM images
            {where_clause}
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()

                if result:
                    stats = dict(result)
                    # Convert None values to appropriate defaults
                    stats["total_file_size"] = stats.get("total_file_size") or 0
                    stats["average_file_size"] = float(
                        stats.get("average_file_size") or 0.0
                    )
                    stats["avg_quality_score"] = float(
                        stats.get("avg_quality_score") or 100.0
                    )
                    return stats

                # Return default stats if no result
                return {
                        "total_images": 0,
                        "last_24h_images": 0,
                        "last_7d_images": 0,
                        "total_file_size": 0,
                        "average_file_size": 0.0,
                        "flagged_images": 0,
                        "avg_quality_score": 100.0,
                        "first_image_at": None,
                        "last_image_at": None,
                        "unique_cameras": 0,
                        "unique_timelapses": 0,
                    }

    async def get_images_without_thumbnails(
        self, limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images that are missing thumbnail files (async version for AsyncImageOperations).

        Args:
            limit: Maximum number of images to return

        Returns:
            List of Image models missing thumbnails
        """
        query = """
        SELECT i.*
        FROM images i
        WHERE i.thumbnail_path IS NULL OR i.small_path IS NULL
        ORDER BY i.captured_at DESC
        LIMIT %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (limit,))
                results = await cur.fetchall()
                return [_row_to_image_shared(dict(row)) for row in results]

    async def get_images(
        self,
        limit: int = MAX_BULK_OPERATION_ITEMS,
        offset: int = 0,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> List[Image]:
        """
        Retrieve all images with pagination, ordering, and optional filtering
        (for AsyncImageOperations).

        Args:
            limit: Number of items to return
            offset: Number of items to skip
            order_by: Column to order by
            order_dir: Sort direction (ASC/DESC)
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            List of Image model instances
        """
        # Build WHERE conditions
        where_conditions = {}
        if timelapse_id is not None:
            where_conditions["timelapse_id"] = timelapse_id
        if camera_id is not None:
            where_conditions["camera_id"] = camera_id

        # Build query
        query_parts = ["SELECT i.* FROM images i"]
        params = []

        # Add WHERE clause if filters provided
        if where_conditions:
            where_clauses = []
            for field, value in where_conditions.items():
                where_clauses.append(f"i.{field} = %s")
                params.append(value)
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        # Add ORDER BY and pagination
        query_parts.append(f"ORDER BY i.{order_by} {order_dir}")
        query_parts.append("LIMIT %s OFFSET %s")
        params.extend([limit, offset])

        query = " ".join(query_parts)

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [_row_to_image_shared(dict(row)) for row in results]

    async def get_images_for_regeneration(
        self,
        limit: int = MAX_BULK_OPERATION_ITEMS,
        offset: int = 0,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all images for thumbnail regeneration without Pydantic validation issues.
        Returns raw dictionaries instead of Image models to avoid day_number validation.

        Args:
            limit: Number of items to return
            offset: Number of items to skip
            order_by: Column to order by
            order_dir: Sort direction (ASC/DESC)

        Returns:
            List of dictionaries with image data (not validated models)
        """
        query = f"""
        SELECT i.id, i.file_path, i.camera_id, i.captured_at, i.created_at
        FROM images i
        ORDER BY i.{order_by} {order_dir}
        LIMIT %s OFFSET %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (limit, offset))
                results = await cur.fetchall()
                return [dict(row) for row in results]
