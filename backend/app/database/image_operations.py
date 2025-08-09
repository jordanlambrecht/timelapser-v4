"""
Image database operations module - Composition-based architecture.

This module handles all image-related database operations using dependency
injection instead of mixin inheritance, providing type-safe Pydantic model
interfaces.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg

from ..constants import DEFAULT_PAGE_SIZE, MAX_BULK_OPERATION_ITEMS
from ..models.image_model import Image
from ..utils.cache_invalidation import CacheInvalidationService
from ..utils.cache_manager import (
    cache,
    cached_response,
    generate_composite_etag,
)
from ..utils.database_helpers import DatabaseBusinessLogic
from ..utils.time_utils import utc_now
from .core import AsyncDatabase, SyncDatabase
from .exceptions import ImageOperationError


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


class ImageQueryBuilder:
    """
    Optimized query builder for image operations.

    IMPORTANT: For optimal performance, ensure these indexes exist:
    - CREATE INDEX idx_images_timelapse_id ON images(timelapse_id);
    - CREATE INDEX idx_images_camera_id ON images(camera_id);
    - CREATE INDEX idx_images_captured_at ON images(captured_at DESC);
    - CREATE INDEX idx_images_is_flagged ON images(is_flagged)
      WHERE is_flagged = true;
    - CREATE INDEX idx_images_thumbnail_paths ON images(thumbnail_path,
      small_path);
    - CREATE INDEX idx_images_composite ON images(camera_id, captured_at DESC);
    - CREATE INDEX idx_images_timelapse_captured ON images(timelapse_id,
      captured_at ASC);
    - CREATE INDEX idx_images_corruption_score ON images(corruption_score)
      WHERE corruption_score IS NOT NULL;
    - CREATE INDEX idx_images_file_paths ON images(file_path, thumbnail_path,
      small_path, overlay_path);

    Centralizes query construction to eliminate duplication and improve
    performance.
    """

    @staticmethod
    def build_images_query(
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        include_details: bool = True,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build optimized query for retrieving images using named parameters.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID
            include_details: Whether to include JOIN data
            order_by: Column to order by
            order_dir: Sort direction
            limit: Optional limit
            offset: Optional offset

        Returns:
            Tuple of (query_string, named_parameters_dict)
        """
        # Validate order_by and order_dir to prevent SQL injection
        allowed_order_fields = [
            "id",
            "captured_at",
            "created_at",
            "camera_id",
            "timelapse_id",
            "file_size",
            "corruption_score",
            "is_flagged",
        ]
        if order_by not in allowed_order_fields:
            order_by = "captured_at"

        allowed_directions = ["ASC", "DESC"]
        if order_dir.upper() not in allowed_directions:
            order_dir = "DESC"
        else:
            order_dir = order_dir.upper()
        # Base fields
        if include_details:
            fields = ["i.*", "c.name as camera_name", "t.status as timelapse_status"]
            joins = [
                "LEFT JOIN cameras c ON i.camera_id = c.id",
                "LEFT JOIN timelapses t ON i.timelapse_id = t.id",
            ]
        else:
            fields = ["i.*"]
            joins = []

        # Build WHERE conditions with named parameters
        where_clauses = []
        params = {}

        if timelapse_id is not None:
            where_clauses.append("i.timelapse_id = %(timelapse_id)s")
            params["timelapse_id"] = timelapse_id

        if camera_id is not None:
            where_clauses.append("i.camera_id = %(camera_id)s")
            params["camera_id"] = camera_id

        # Build query with named parameters
        query_parts = [
            f"SELECT {', '.join(fields)} FROM {' '.join(['images i'] + joins)}"
        ]

        if where_clauses:
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        query_parts.append(f"ORDER BY i.{order_by} {order_dir}")

        if limit is not None:
            query_parts.append("LIMIT %(limit)s")
            params["limit"] = limit

        if offset is not None:
            query_parts.append("OFFSET %(offset)s")
            params["offset"] = offset

        query = " ".join(query_parts)
        return query, params

    @staticmethod
    def build_images_by_ids_query(
        image_ids: List[int], include_details: bool = True
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build optimized query for retrieving images by IDs using ANY() for
        better performance.

        Args:
            image_ids: List of image IDs
            include_details: Whether to include JOIN data

        Returns:
            Tuple of (query_string, named_parameters_dict)
        """
        if not image_ids:
            return "SELECT 1 WHERE FALSE", {}

        if include_details:
            fields = ["i.*", "c.name as camera_name", "t.status as timelapse_status"]
            joins = [
                "LEFT JOIN cameras c ON i.camera_id = c.id",
                "LEFT JOIN timelapses t ON i.timelapse_id = t.id",
            ]
        else:
            fields = ["i.*"]
            joins = []

        # Use ANY() for better performance with large ID lists
        where_clause = "i.id = ANY(%(image_ids)s)"

        query_parts = [
            f"SELECT {', '.join(fields)} FROM {' '.join(['images i'] + joins)}"
        ]
        query_parts.append(f"WHERE {where_clause}")
        query_parts.append("ORDER BY i.captured_at DESC")

        query = " ".join(query_parts)
        return query, {"image_ids": image_ids}

    @staticmethod
    def build_count_query(
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        is_flagged: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build optimized count query for images using named parameters.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID
            is_flagged: Optional filter by flagged status
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Tuple of (query_string, named_parameters_dict)
        """
        where_clauses = []
        params = {}

        if timelapse_id is not None:
            where_clauses.append("timelapse_id = %(timelapse_id)s")
            params["timelapse_id"] = timelapse_id

        if camera_id is not None:
            where_clauses.append("camera_id = %(camera_id)s")
            params["camera_id"] = camera_id

        if is_flagged is not None:
            where_clauses.append("is_flagged = %(is_flagged)s")
            params["is_flagged"] = is_flagged

        if start_date:
            where_clauses.append("captured_at >= %(start_date)s")
            params["start_date"] = start_date

        if end_date:
            where_clauses.append("captured_at <= %(end_date)s")
            params["end_date"] = end_date

        # Build count query with named parameters
        query_parts = ["SELECT COUNT(*) as total FROM images"]

        if where_clauses:
            query_parts.append(f"WHERE {' AND '.join(where_clauses)}")

        query = " ".join(query_parts)
        return query, params

    @staticmethod
    def build_date_range_query(
        start_date: str, end_date: str, include_details: bool = True
    ) -> tuple[str, Dict[str, Any]]:
        """
        Build optimized date range query using named parameters and proper indexing.

        Args:
            start_date: Start date for range filter
            end_date: End date for range filter
            include_details: Whether to include JOIN data

        Returns:
            Tuple of (query_string, named_parameters_dict)
        """
        if include_details:
            fields = ["i.*", "c.name as camera_name", "t.status as timelapse_status"]
            joins = [
                "LEFT JOIN cameras c ON i.camera_id = c.id",
                "LEFT JOIN timelapses t ON i.timelapse_id = t.id",
            ]
        else:
            fields = ["i.*"]
            joins = []

        query_parts = [
            f"SELECT {', '.join(fields)} FROM {' '.join(['images i'] + joins)}"
        ]
        query_parts.append(
            "WHERE i.captured_at >= %(start_date)s AND i.captured_at <= %(end_date)s"
        )
        query_parts.append("ORDER BY i.captured_at DESC")

        params = {"start_date": start_date, "end_date": end_date}

        query = " ".join(query_parts)
        return query, params


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
        # CacheInvalidationService is a static utility - no instance needed

    async def _clear_image_caches(
        self,
        image_id: Optional[int] = None,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Clear caches related to images using sophisticated cache system."""
        # Clear image-related caches using advanced cache manager
        cache_patterns = [
            "image:get_images",
            "image:get_images_count",
            "image:get_images_by_timelapse",
            "image:get_images_by_camera",
            "image:get_flagged_images",
            "image:get_latest_image_for_camera",
            "image:get_images_without_thumbnails",
        ]

        if image_id:
            cache_patterns.extend(
                [f"image:get_image_by_id:{image_id}", f"image:metadata:{image_id}"]
            )

            # Use ETag-aware invalidation if timestamp provided
            if updated_at:
                etag = generate_composite_etag(image_id, updated_at)
                await CacheInvalidationService.invalidate_with_etag_validation(
                    f"image:metadata:{image_id}", etag
                )

        if timelapse_id:
            cache_patterns.extend(
                [
                    f"image:by_timelapse:{timelapse_id}",
                    f"image:count_by_timelapse:{timelapse_id}",
                ]
            )

        if camera_id:
            cache_patterns.extend(
                [f"image:by_camera:{camera_id}", f"image:latest_for_camera:{camera_id}"]
            )

        # Clear cache patterns using advanced cache manager
        for pattern in cache_patterns:
            await cache.delete(pattern)

    def _row_to_image(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model."""
        return _row_to_image_shared(row)

    def _row_to_image_with_details(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model with additional fields."""
        # Extract only valid Image model fields
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields.keys()}

        # Create base Image model
        image = Image(**image_fields)

        # Add computed fields as attributes (not part of the model constructor)
        if "camera_name" in row:
            image.camera_name = row["camera_name"]
        if "timelapse_status" in row:
            image.timelapse_status = row["timelapse_status"]

        return image

    async def set_image_corruption_score(self, image_id: int, score: float) -> bool:
        """
        Update the corruption_score (quality score) for an image using named parameters.

        Args:
            image_id: ID of the image to update
            score: New quality/corruption score

        Returns:
            True if update was successful
        """
        query = (
            "UPDATE images SET corruption_score = %(score)s, "
            "updated_at = %(updated_at)s WHERE id = %(image_id)s"
        )
        params = {
            "score": score,
            "updated_at": utc_now(),
            "image_id": image_id,
        }
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                success = cur.rowcount > 0

                # Clear related caches after successful update
                if success:
                    await self._clear_image_caches(image_id=image_id)

                return success

    @cached_response(ttl_seconds=120, key_prefix="image")
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

        Optimized version using ImageQueryBuilder and caching for better performance.

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
        # Use optimized query builder with named parameters
        query, params = ImageQueryBuilder.build_images_query(
            timelapse_id=timelapse_id,
            camera_id=camera_id,
            include_details=True,
            order_by=order_by,
            order_dir=order_dir,
            limit=limit,
            offset=offset,
        )

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                # Convert to Image models with computed fields
                images = []
                for row in results:
                    image_dict = dict(row)
                    base_image = self._row_to_image(row)

                    # Add computed fields
                    base_image.camera_name = image_dict.get("camera_name")
                    base_image.timelapse_status = image_dict.get("timelapse_status")

                    images.append(base_image)

                return images

    @cached_response(ttl_seconds=300, key_prefix="image")
    async def get_images_count(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> int:
        """
        Get total count of images matching the filters.

        Optimized version using ImageQueryBuilder and caching.

        Args:
            timelapse_id: Optional filter by timelapse ID
            camera_id: Optional filter by camera ID

        Returns:
            Total count of matching images
        """
        # Use optimized query builder with named parameters
        query, params = ImageQueryBuilder.build_count_query(
            timelapse_id=timelapse_id, camera_id=camera_id
        )

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                count = result[0] if result else 0
                return count

    @cached_response(ttl_seconds=180, key_prefix="image")
    async def get_images_by_timelapse(self, timelapse_id: int) -> List[Image]:
        """Get all images for a specific timelapse using named parameters."""
        query = "SELECT * FROM images WHERE timelapse_id = %(timelapse_id)s ORDER BY captured_at ASC"
        params = {"timelapse_id": timelapse_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    @cached_response(ttl_seconds=180, key_prefix="image")
    async def get_images_by_camera(self, camera_id: int) -> List[Image]:
        """Get all images for a specific camera using named parameters."""
        query = "SELECT * FROM images WHERE camera_id = %(camera_id)s ORDER BY captured_at DESC"
        params = {"camera_id": camera_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    @cached_response(ttl_seconds=300, key_prefix="image")
    async def get_images_by_date_range(
        self, start_date: str, end_date: str
    ) -> List[Image]:
        """Get images within a specific date range using optimized query builder."""
        query, params = ImageQueryBuilder.build_date_range_query(
            start_date=start_date, end_date=end_date, include_details=True
        )
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()

                # Convert to Image models with computed fields
                images = []
                for row in results:
                    image_dict = dict(row)
                    base_image = self._row_to_image(row)

                    # Add computed fields
                    base_image.camera_name = image_dict.get("camera_name")
                    base_image.timelapse_status = image_dict.get("timelapse_status")

                    images.append(base_image)

                return images

    @cached_response(ttl_seconds=120, key_prefix="image")
    async def get_flagged_images(self) -> List[Image]:
        """Get all flagged images using optimized boolean index."""
        query = "SELECT * FROM images WHERE is_flagged = true ORDER BY captured_at DESC"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query)
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    @cached_response(ttl_seconds=300, key_prefix="image")
    async def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """
        Retrieve a specific image by ID using named parameters.

        Args:
            image_id: ID of the image to retrieve

        Returns:
            Image model instance, or None if not found
        """
        query = "SELECT * FROM images WHERE id = %(image_id)s"
        params = {"image_id": image_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return self._row_to_image(result) if result else None

    async def cleanup_old_images(self, days_to_keep: int) -> int:
        """
        Delete images older than specified days using optimized INTERVAL syntax.

        Pure database operation - no business logic or validation.

        Args:
            days_to_keep: Number of days to keep images

        Returns:
            Number of images deleted
        """
        query = """
        DELETE FROM images
        WHERE captured_at < %(now)s - INTERVAL '1 day' * %(days)s
        """
        params = {"now": utc_now(), "days": days_to_keep}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                deleted_count = cur.rowcount or 0

                # Clear related caches after deletion
                if deleted_count > 0:
                    await self._clear_image_caches()

                return deleted_count

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
            timelapse_id, camera_id, file_path, file_name, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            corruption_score, is_flagged, corruption_details,
            weather_temperature, weather_conditions, weather_icon, weather_fetched_at,
            has_valid_overlay
        ) VALUES (
            %(timelapse_id)s, %(camera_id)s, %(file_path)s, %(file_name)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(corruption_score)s, %(is_flagged)s, %(corruption_details)s,
            %(weather_temperature)s, %(weather_conditions)s, %(weather_icon)s, %(weather_fetched_at)s,
            %(has_valid_overlay)s
        ) RETURNING *
        """

        # Serialize corruption_details to JSON if present
        if (
            "corruption_details" in image_data
            and image_data["corruption_details"] is not None
        ):
            image_data["corruption_details"] = json.dumps(
                image_data["corruption_details"]
            )

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, image_data)
                result = await cur.fetchone()
                image = self._row_to_image(result)

                # Clear related caches after successful creation
                await self._clear_image_caches(
                    image_id=image.id, timelapse_id=image.timelapse_id
                )

                return image

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
        set_clauses.append("updated_at = %(updated_at)s")

        query = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %(id)s"
        thumbnail_data["id"] = image_id
        thumbnail_data["updated_at"] = utc_now()

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, thumbnail_data)
                success = cur.rowcount > 0

                # Clear related caches after successful update
                if success:
                    await self._clear_image_caches(image_id=image_id)

                return success

    @cached_response(ttl_seconds=60, key_prefix="image")
    async def get_latest_image_for_camera(self, camera_id: int) -> Optional[Image]:
        """
        Get the most recent image for a specific camera using named parameters.

        Args:
            camera_id: ID of the camera

        Returns:
            Latest Image model instance, or None if no images found
        """
        query = """
        SELECT * FROM images
        WHERE camera_id = %(camera_id)s
        ORDER BY captured_at DESC
        LIMIT 1
        """
        params = {"camera_id": camera_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return self._row_to_image(result) if result else None

    @cached_response(ttl_seconds=300, key_prefix="image")
    async def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get total count of images for a timelapse using named parameters.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total number of images
        """
        query = "SELECT COUNT(*) FROM images WHERE timelapse_id = %(timelapse_id)s"
        params = {"timelapse_id": timelapse_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                return result[0] if result else 0

    @cached_response(ttl_seconds=60, key_prefix="image")
    async def get_images_without_thumbnails(
        self, limit: int = MAX_BULK_OPERATION_ITEMS
    ) -> List[Image]:
        """
        Get images that are missing thumbnail files using named parameters.

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
        LIMIT %(limit)s
        """
        params = {"limit": limit}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [self._row_to_image(row) for row in results]

    async def delete_image(self, image_id: int) -> bool:
        """
        Delete a specific image by ID using named parameters.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if image was deleted successfully
        """
        query = "DELETE FROM images WHERE id = %(image_id)s"
        params = {"image_id": image_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                success = cur.rowcount > 0

                # Clear related caches after successful deletion
                if success:
                    await self._clear_image_caches(image_id=image_id)

                return success

    async def delete_images_by_timelapse(self, timelapse_id: int) -> int:
        """
        Delete all images for a specific timelapse using named parameters.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images deleted
        """
        query = "DELETE FROM images WHERE timelapse_id = %(timelapse_id)s"
        params = {"timelapse_id": timelapse_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                deleted_count = cur.rowcount or 0

                # Clear related caches after deletion
                if deleted_count > 0:
                    await self._clear_image_caches(timelapse_id=timelapse_id)

                return deleted_count

    async def calculate_day_number(
        self, timelapse_id: int, captured_at: datetime
    ) -> int:
        """
        Calculate the day number for an image within a timelapse.

        Note: This method still exists for compatibility but delegates
        business logic to the utility layer.

        Args:
            timelapse_id: ID of the timelapse
            captured_at: When the image was captured

        Returns:
            Day number (1-based)
        """
        # Get timelapse start date (database operation)
        query = "SELECT start_time FROM timelapses WHERE id = %(timelapse_id)s"
        params = {"timelapse_id": timelapse_id}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                result = await cur.fetchone()
                if not result:
                    return 1

                start_date = result["start_time"].date()
                current_date = captured_at.date()

                # Delegate calculation to business logic utility
                return DatabaseBusinessLogic.calculate_image_day_number(
                    start_date, current_date
                )


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
            timelapse_id, camera_id, file_path, file_name, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            corruption_score, is_flagged, corruption_details,
            weather_temperature, weather_conditions, weather_icon, weather_fetched_at,
            has_valid_overlay
        ) VALUES (
            %(timelapse_id)s, %(camera_id)s, %(file_path)s, %(file_name)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(corruption_score)s, %(is_flagged)s, %(corruption_details)s,
            %(weather_temperature)s, %(weather_conditions)s, %(weather_icon)s, %(weather_fetched_at)s,
            %(has_valid_overlay)s
        ) RETURNING *
        """

        # Serialize corruption_details to JSON if present
        if (
            "corruption_details" in image_data
            and image_data["corruption_details"] is not None
        ):
            image_data["corruption_details"] = json.dumps(
                image_data["corruption_details"]
            )

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, image_data)
                result = cur.fetchone()
                return self._row_to_image(result)

    def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get total count of images for a timelapse using named parameters (sync version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total number of images
        """
        query = "SELECT COUNT(*) FROM images WHERE timelapse_id = %(timelapse_id)s"
        params = {"timelapse_id": timelapse_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
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
        # Use optimized query builder with named parameters for consistency
        query, params = ImageQueryBuilder.build_images_query(
            timelapse_id=timelapse_id,
            camera_id=camera_id,
            include_details=True,
            order_by=order_by,
            order_dir=order_dir,
            limit=limit,
            offset=offset,
        )

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

                    # Note: Thumbnail path computation moved to service layer for better performance
                    # Database layer should not perform file system operations

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
        # Use optimized query builder with named parameters
        query, params = ImageQueryBuilder.build_count_query(
            timelapse_id=timelapse_id, camera_id=camera_id
        )

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return result[0] if result else 0

    def get_images_by_timelapse(self, timelapse_id: int) -> List[Image]:
        """Get all images for a specific timelapse using named parameters (sync version)."""
        query = "SELECT * FROM images WHERE timelapse_id = %(timelapse_id)s ORDER BY captured_at ASC"
        params = {"timelapse_id": timelapse_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_images_by_camera(self, camera_id: int) -> List[Image]:
        """
        Get all images for a specific camera using named parameters
        (sync version).
        """
        query = "SELECT * FROM images WHERE camera_id = %(camera_id)s ORDER BY captured_at DESC"
        params = {"camera_id": camera_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def get_images_by_date_range(self, start_date: str, end_date: str) -> List[Image]:
        """Get images within a specific date range using optimized query builder (sync version)."""
        query, params = ImageQueryBuilder.build_date_range_query(
            start_date=start_date, end_date=end_date, include_details=True
        )
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

                # Convert to Image models with computed fields
                images = []
                for row in results:
                    image_dict = dict(row)
                    base_image = self._row_to_image(row)

                    # Add computed fields
                    base_image.camera_name = image_dict.get("camera_name")
                    base_image.timelapse_status = image_dict.get("timelapse_status")

                    images.append(base_image)

                return images

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
        Get all images for a specific timelapse using named parameters (sync version for worker).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            List of Image model instances ordered by captured_at
        """
        query = """
        SELECT * FROM images
        WHERE timelapse_id = %(timelapse_id)s
        ORDER BY captured_at ASC
        """
        params = {"timelapse_id": timelapse_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [self._row_to_image(row) for row in results]

    def cleanup_old_images(self, days_to_keep: int) -> int:
        """
        Delete images older than specified days using optimized INTERVAL syntax (sync version).

        Pure database operation - no business logic or validation.

        Args:
            days_to_keep: Number of days to keep images

        Returns:
            Number of images deleted
        """
        query = """
        DELETE FROM images
        WHERE captured_at < %(now)s - INTERVAL '1 day' * %(days)s
        """
        params = {"now": utc_now(), "days": days_to_keep}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
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
        set_clauses.append("updated_at = %(updated_at)s")
        thumbnail_data["updated_at"] = utc_now()

        query = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %(id)s"
        thumbnail_data["id"] = image_id

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, thumbnail_data)
                return cur.rowcount > 0

    def update_image_overlay_status(
        self,
        image_id: int,
        overlay_path: str,
        has_valid_overlay: bool,
        overlay_updated_at: datetime,
    ) -> bool:
        """
        Update overlay status and path for an image.

        Args:
            image_id: ID of the image to update
            overlay_path: Path to the overlay image file
            has_valid_overlay: Whether the overlay was successfully generated
            overlay_updated_at: Timestamp when overlay was generated

        Returns:
            True if update was successful
        """
        query = """
            UPDATE images
            SET overlay_path = %(overlay_path)s,
                has_valid_overlay = %(has_valid_overlay)s,
                overlay_updated_at = %(overlay_updated_at)s,
                updated_at = %(updated_at)s
            WHERE id = %(image_id)s
        """

        params = {
            "image_id": image_id,
            "overlay_path": overlay_path,
            "has_valid_overlay": has_valid_overlay,
            "overlay_updated_at": overlay_updated_at,
            "updated_at": utc_now(),
        }

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount > 0

    def get_image_by_id(self, image_id: int) -> Optional[Image]:
        """Get a specific image by ID using named parameters (sync version)."""
        query = "SELECT * FROM images WHERE id = %(image_id)s"
        params = {"image_id": image_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return self._row_to_image(result) if result else None

    def get_all_file_paths(self) -> set:
        """
        Get all file paths referenced in the images table.

        Returns:
            Set of all file paths (file_path, thumbnail_path, small_path, overlay_path)
        """
        try:
            file_paths = set()
            query = """
                SELECT file_path, thumbnail_path, small_path, overlay_path
                FROM images
                WHERE file_path IS NOT NULL
            """

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    rows = cur.fetchall()

                    for row in rows:
                        # Add all non-null paths to the set
                        for path_field in [
                            "file_path",
                            "thumbnail_path",
                            "small_path",
                            "overlay_path",
                        ]:
                            if row.get(path_field):
                                file_paths.add(row[path_field])

            return file_paths

        except (psycopg.Error, KeyError, ValueError):
            raise ImageOperationError(
                "Database error retrieving file paths from images table",
                operation="get_all_file_paths",
                details={},
            )
            # logger.error(
            #     "Error getting all file paths",
            #     exception=e,
            #     emoji=LogEmoji.WARNING,
            #     extra_context={
            #         "operation": "get_all_file_paths",
            #         "error_type": type(e).__name__,
            #     },
            # )
            return set()

    def delete_image(self, image_id: int) -> None:
        """
        Delete an image record from the database using named parameters.

        Args:
            image_id: The ID of the image to delete.
        """
        query = "DELETE FROM images WHERE id = %(image_id)s"
        params = {"image_id": image_id}
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
        # logger.info(
        #     f"Deleted image record with ID: {image_id}",
        #     emoji=LogEmoji.CLEANUP,
        #     extra_context={
        #         "image_id": image_id,
        #         "operation": "delete_image"
        #     }
        # )

    def get_images_with_small_thumbnails_by_timelapse(
        self, timelapse_id: int
    ) -> List[Image]:
        """
        Get all images with small thumbnail paths for a specific timelapse (sync).

        This method is used for "latest" mode cleanup to find images that have
        small thumbnails that need to be removed except for the most recent one.

        Args:
            timelapse_id: ID of the timelapse to get images for

        Returns:
            List of Image objects that have small_path values
        """
        query = """
            SELECT * FROM images
            WHERE timelapse_id = %(timelapse_id)s
            AND small_path IS NOT NULL
            ORDER BY captured_at DESC
        """
        params = {"timelapse_id": timelapse_id}

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [Image(**dict(row)) for row in results] if results else []

    def clear_small_path(self, image_id: int) -> bool:
        """
        Clear only the small image path for a specific image (sync).

        This is used in "latest" mode to remove small_path references
        for older images while keeping their regular thumbnails.

        Args:
            image_id: ID of the image to update

        Returns:
            True if update successful
        """
        query = """
            UPDATE images
            SET small_path = NULL,
                small_size = NULL,
                updated_at = %(updated_at)s
            WHERE id = %(image_id)s
        """
        params = {"updated_at": utc_now(), "image_id": image_id}

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount > 0


class AsyncImageOperations(ImageOperations):
    """
    Extended async image operations with additional specialized methods.

    This class extends the main ImageOperations class to provide additional
    specialized async methods for bulk operations and advanced queries.
    """

    def _row_to_image(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model."""
        return _row_to_image_shared(row)

    def _row_to_image_with_details(self, row: Dict[str, Any]) -> Image:
        """Convert database row to Image model with additional fields."""
        # Extract only valid Image model fields
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields.keys()}

        # Create base Image model
        image = Image(**image_fields)

        # Add computed fields as attributes (not part of the model constructor)
        if "camera_name" in row:
            image.camera_name = row["camera_name"]
        if "timelapse_status" in row:
            image.timelapse_status = row["timelapse_status"]

        return image

    @cached_response(ttl_seconds=300, key_prefix="image")
    async def get_images_by_ids(self, image_ids: List[int]) -> List[Image]:
        """
        Get images by specific IDs with details.

        Uses sophisticated caching with 5-minute TTL for performance.

        Args:
            image_ids: List of image IDs to retrieve

        Returns:
            List of Image models
        """
        # Use ANY() for better performance with large ID lists
        query = """
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.id = ANY(%(image_ids)s)
            ORDER BY i.captured_at DESC
        """
        params = {"image_ids": image_ids}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
        # Use ANY() for better performance with large ID lists
        query = """
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.camera_id = ANY(%(camera_ids)s)
            ORDER BY i.captured_at DESC
            LIMIT %(limit)s
        """
        params = {"camera_ids": camera_ids, "limit": limit}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
        # Use ANY() for better performance with large ID lists
        query = """
            SELECT i.*, c.name as camera_name, t.status as timelapse_status
            FROM images i
            LEFT JOIN cameras c ON i.camera_id = c.id
            LEFT JOIN timelapses t ON i.timelapse_id = t.id
            WHERE i.timelapse_id = ANY(%(timelapse_ids)s)
            ORDER BY i.captured_at DESC
            LIMIT %(limit)s
        """
        params = {"timelapse_ids": timelapse_ids, "limit": limit}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
            LIMIT %(limit)s
        """
        params = {"limit": limit}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
            SET thumbnail_path = %(thumbnail_path)s,
                small_path = %(small_path)s,
                thumbnail_size = %(thumbnail_size)s,
                small_size = %(small_size)s,
                updated_at = %(updated_at)s
            WHERE id = %(image_id)s
        """
        params = {
            "thumbnail_path": thumbnail_path,
            "small_path": small_path,
            "thumbnail_size": thumbnail_size,
            "small_size": small_size,
            "updated_at": utc_now(),
            "image_id": image_id,
        }

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
                updated_at = %(updated_at)s
            WHERE id = %(image_id)s
        """
        params = {"updated_at": utc_now(), "image_id": image_id}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
                updated_at = %(updated_at)s
            WHERE thumbnail_path IS NOT NULL OR small_path IS NOT NULL
        """
        params = {"updated_at": utc_now()}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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

    async def get_images_with_small_thumbnails_by_timelapse(
        self, timelapse_id: int
    ) -> List[Image]:
        """
        Get all images with small thumbnail paths for a specific timelapse.

        This method is used for "latest" mode cleanup to find images that have
        small thumbnails that need to be removed except for the most recent one.

        Args:
            timelapse_id: ID of the timelapse to get images for

        Returns:
            List of Image objects that have small_path values
        """
        query = """
            SELECT * FROM images
            WHERE timelapse_id = %(timelapse_id)s
            AND small_path IS NOT NULL
            ORDER BY captured_at DESC
        """
        params = {"timelapse_id": timelapse_id}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [Image(**dict(row)) for row in results] if results else []

    async def clear_small_path(self, image_id: int) -> bool:
        """
        Clear only the small image path for a specific image.

        This is used in "latest" mode to remove small_path references
        for older images while keeping their regular thumbnails.

        Args:
            image_id: ID of the image to update

        Returns:
            True if update successful
        """
        query = """
            UPDATE images
            SET small_path = NULL,
                small_size = NULL,
                updated_at = %(updated_at)s
            WHERE id = %(image_id)s
        """
        params = {"updated_at": utc_now(), "image_id": image_id}

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                return cur.rowcount > 0

    async def get_image_statistics(
        self, camera_id: Optional[int] = None, timelapse_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive image statistics using consistent named parameters.

        Args:
            camera_id: Optional camera ID to filter by
            timelapse_id: Optional timelapse ID to filter by

        Returns:
            Dictionary with comprehensive image statistics
        """
        # Build WHERE clause with named parameters
        where_conditions = []
        params: Dict[str, Any] = {"now": utc_now()}

        if camera_id:
            where_conditions.append("camera_id = %(camera_id)s")
            params["camera_id"] = camera_id

        if timelapse_id:
            where_conditions.append("timelapse_id = %(timelapse_id)s")
            params["timelapse_id"] = timelapse_id

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        query = f"""
            SELECT
                COUNT(*) as total_images,
                COUNT(*) FILTER (WHERE captured_at >= %(now)s - INTERVAL '24 hours') as last_24h_images,
                COUNT(*) FILTER (WHERE captured_at >= %(now)s - INTERVAL '7 days') as last_7d_images,
                COALESCE(SUM(file_size), 0) as total_file_size,
                COALESCE(AVG(file_size), 0) as average_file_size,
                COUNT(*) FILTER (WHERE is_flagged = true) as flagged_images,
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
        LIMIT %(limit)s
        """
        params = {"limit": limit}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
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
        # Use optimized query builder with named parameters for consistency
        query, params = ImageQueryBuilder.build_images_query(
            timelapse_id=timelapse_id,
            camera_id=camera_id,
            include_details=False,  # This method only returns base fields
            order_by=order_by,
            order_dir=order_dir,
            limit=limit,
            offset=offset,
        )

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
        # Validate order_by to prevent SQL injection
        allowed_order_fields = ["id", "captured_at", "created_at", "camera_id"]
        if order_by not in allowed_order_fields:
            order_by = "captured_at"

        allowed_directions = ["ASC", "DESC"]
        if order_dir.upper() not in allowed_directions:
            order_dir = "DESC"

        query = f"""
        SELECT i.id, i.file_path, i.camera_id, i.captured_at, i.created_at
        FROM images i
        ORDER BY i.{order_by} {order_dir}
        LIMIT %(limit)s OFFSET %(offset)s
        """
        params = {"limit": limit, "offset": offset}
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                results = await cur.fetchall()
                return [dict(row) for row in results]

    async def batch_update_images(self, updates: List[Dict[str, Any]]) -> int:
        """
        Efficiently batch update multiple images using connection batching.

        Args:
            updates: List of update dictionaries, each containing:
                    - image_id: ID of image to update
                    - fields: Dictionary of field->value updates

        Returns:
            Number of images successfully updated
        """
        if not updates:
            return 0

        # Simple batch update without external dependencies
        success_count = 0
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                for update in updates:
                    image_id = update.get("image_id")
                    fields = update.get("fields", {})

                    if not image_id or not fields:
                        continue

                    # Build update query with named parameters
                    set_clauses = [f"{field} = %({field})s" for field in fields.keys()]
                    set_clauses.append("updated_at = %(updated_at)s")

                    query = f"UPDATE images SET {', '.join(set_clauses)} WHERE id = %(image_id)s"

                    # Prepare parameters with named keys
                    update_params = fields.copy()
                    update_params.update(
                        {"updated_at": utc_now(), "image_id": image_id}
                    )

                    await cur.execute(query, update_params)
                    if cur.rowcount > 0:
                        success_count += 1

        # Clear related caches after successful batch update
        if success_count > 0:
            await self._clear_image_caches()

        return success_count

    async def batch_get_images_by_ids(
        self, image_ids: List[int], chunk_size: int = 100
    ) -> List[Image]:
        """
        Efficiently retrieve images by IDs using chunking for large datasets.

        Args:
            image_ids: List of image IDs to retrieve
            chunk_size: Size of chunks for batch processing

        Returns:
            List of Image models
        """
        if not image_ids:
            return []

        all_images = []

        # Process in chunks to avoid query size limits
        for i in range(0, len(image_ids), chunk_size):
            chunk = image_ids[i : i + chunk_size]

            # Use optimized query builder with named parameters
            query, params = ImageQueryBuilder.build_images_by_ids_query(
                chunk, include_details=True
            )

            async with self.db.get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(query, params)
                    results = await cur.fetchall()

                    for row in results:
                        image_dict = dict(row)
                        base_image = self._row_to_image(row)

                        # Add computed fields
                        base_image.camera_name = image_dict.get("camera_name")
                        base_image.timelapse_status = image_dict.get("timelapse_status")

                        all_images.append(base_image)

        return all_images
