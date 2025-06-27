"""
Image database operations module - Composition-based architecture.

This module handles all image-related database operations using dependency injection
instead of mixin inheritance, providing type-safe Pydantic model interfaces.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date
from loguru import logger

from .core import AsyncDatabase, SyncDatabase
from ..models.image_model import Image, ImageWithDetails


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
        # Filter fields that belong to Image model
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields}
        return Image(**image_fields)

    def _row_to_image_with_details(self, row: Dict[str, Any]) -> ImageWithDetails:
        """Convert database row to ImageWithDetails model."""
        # Extract base image fields
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields}

        # Add additional fields for ImageWithDetails
        details_fields = image_fields.copy()
        if "camera_name" in row:
            details_fields["camera_name"] = row["camera_name"]
        if "timelapse_status" in row:
            details_fields["timelapse_status"] = row["timelapse_status"]

        return ImageWithDetails(**details_fields)

    async def get_images(
        self,
        timelapse_id: Optional[int] = None,
        camera_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "captured_at",
        order_dir: str = "DESC",
    ) -> Dict[str, Any]:
        """
        Retrieve images with pagination and filtering.

        Args:
            timelapse_id: Optional timelapse ID to filter by
            camera_id: Optional camera ID to filter by
            page: Page number (1-based)
            page_size: Number of images per page
            order_by: Column to order by
            order_dir: Order direction (ASC/DESC)

        Returns:
            Dictionary containing images list (ImageWithDetails models) and pagination metadata

        Usage:
            result = await image_ops.get_images(timelapse_id=1, page=1, page_size=20)
            images = result['images']  # List[ImageWithDetails]
            total_count = result['total_count']
        """
        offset = (page - 1) * page_size

        # Build WHERE clause based on filters
        where_conditions = []
        params = []

        if timelapse_id is not None:
            where_conditions.append("i.timelapse_id = %s")
            params.append(timelapse_id)

        if camera_id is not None:
            where_conditions.append("t.camera_id = %s")
            params.append(camera_id)

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Count query for pagination
        count_query = f"""
        SELECT COUNT(*) as total_count
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        {where_clause}
        """

        # Images query with pagination
        images_query = f"""
        SELECT 
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        {where_clause}
        ORDER BY i.{order_by} {order_dir}
        LIMIT %s OFFSET %s
        """

        images_params = params + [page_size, offset]

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                # Get total count
                await cur.execute(count_query, params)
                count_result = await cur.fetchone()
                total_count = count_result[0] if count_result else 0

                # Get images
                await cur.execute(images_query, images_params)
                results = await cur.fetchall()
                images = [self._row_to_image_with_details(row) for row in results]

                # Calculate pagination metadata
                total_pages = (total_count + page_size - 1) // page_size
                has_next = page < total_pages
                has_previous = page > 1

                return {
                    "images": images,
                    "total_count": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_previous": has_previous,
                }

    async def get_image_by_id(self, image_id: int) -> Optional[ImageWithDetails]:
        """
        Retrieve a specific image by ID.

        Args:
            image_id: ID of the image to retrieve

        Returns:
            ImageWithDetails model instance, or None if not found

        Usage:
            image = await image_ops.get_image_by_id(1)
        """
        query = """
        SELECT 
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE i.id = %s
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (image_id,))
                results = await cur.fetchall()
                return self._row_to_image_with_details(results[0]) if results else None

    async def get_latest_image_for_camera(
        self, camera_id: int
    ) -> Optional[ImageWithDetails]:
        """
        Get the latest image for a specific camera.

        Args:
            camera_id: ID of the camera

        Returns:
            Latest ImageWithDetails model instance, or None if no images found

        Usage:
            image = await image_ops.get_latest_image_for_camera(1)
        """
        query = """
        SELECT 
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE c.id = %s
        ORDER BY i.captured_at DESC
        LIMIT 1
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (camera_id,))
                results = await cur.fetchall()
                return self._row_to_image_with_details(results[0]) if results else None

    async def get_latest_image_for_timelapse(
        self, timelapse_id: int
    ) -> Optional[ImageWithDetails]:
        """
        Get the latest image for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Latest ImageWithDetails model instance, or None if no images found

        Usage:
            image = await image_ops.get_latest_image_for_timelapse(1)
        """
        query = """
        SELECT 
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE i.timelapse_id = %s
        ORDER BY i.captured_at DESC
        LIMIT 1
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                results = await cur.fetchall()
                return self._row_to_image_with_details(results[0]) if results else None

    async def get_images_by_day_range(
        self, timelapse_id: int, start_day: int, end_day: int
    ) -> List[ImageWithDetails]:
        """
        Get images for a timelapse within a specific day range.

        Args:
            timelapse_id: ID of the timelapse
            start_day: Starting day number (inclusive)
            end_day: Ending day number (inclusive)

        Returns:
            List of ImageWithDetails models

        Usage:
            images = await image_ops.get_images_by_day_range(1, 1, 7)
        """
        query = """
        SELECT
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE i.timelapse_id = %s
        AND i.day_number >= %s
        AND i.day_number <= %s
        ORDER BY i.captured_at ASC
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id, start_day, end_day))
                results = await cur.fetchall()
                return [self._row_to_image_with_details(row) for row in results]

    async def get_images_by_date_range(
        self, timelapse_id: int, start_date: date, end_date: date
    ) -> List[ImageWithDetails]:
        """
        Get images for a timelapse within a specific date range.

        Args:
            timelapse_id: ID of the timelapse
            start_date: Starting date (inclusive)
            end_date: Ending date (inclusive)

        Returns:
            List of ImageWithDetails models

        Usage:
            from datetime import date
            images = await image_ops.get_images_by_date_range(1, date(2025, 6, 1), date(2025, 6, 7))
        """
        query = """
        SELECT
            i.*,
            t.name as timelapse_name,
            c.name as camera_name
        FROM images i
        JOIN timelapses t ON i.timelapse_id = t.id
        JOIN cameras c ON t.camera_id = c.id
        WHERE i.timelapse_id = %s
        AND DATE(i.captured_at) >= %s
        AND DATE(i.captured_at) <= %s
        ORDER BY i.captured_at ASC
        """
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id, start_date, end_date))
                results = await cur.fetchall()
                return [self._row_to_image_with_details(row) for row in results]

    async def delete_image(self, image_id: int) -> bool:
        """
        Delete a specific image.

        Args:
            image_id: ID of the image to delete

        Returns:
            True if image was deleted successfully

        Usage:
            success = await image_ops.delete_image(1)
        """
        query = "DELETE FROM images WHERE id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (image_id,))
                affected = cur.rowcount

                if affected and affected > 0:
                    await self.db.broadcast_event(
                        "image_deleted", {"image_id": image_id}
                    )
                    return True
                return False

    async def delete_images_by_timelapse(self, timelapse_id: int) -> int:
        """
        Delete all images for a specific timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Number of images deleted

        Usage:
            deleted_count = await image_ops.delete_images_by_timelapse(1)
        """
        query = "DELETE FROM images WHERE timelapse_id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                affected = cur.rowcount or 0

                if affected > 0:
                    await self.db.broadcast_event(
                        "images_deleted",
                        {"timelapse_id": timelapse_id, "count": affected},
                    )

                return affected

    async def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image.

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance

        Usage:
            image = await image_ops.record_captured_image({
                'timelapse_id': 1,
                'file_path': '/path/to/image.jpg',
                'day_number': 1
            })
        """
        query = """
        INSERT INTO images (
            timelapse_id, file_path, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            glitch_severity, is_flagged
        ) VALUES (
            %(timelapse_id)s, %(file_path)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(glitch_severity)s, %(is_flagged)s
        ) RETURNING *
        """

        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, image_data)
                results = await cur.fetchall()
                if results:
                    image_row = results[0]
                    image = self._row_to_image(image_row)
                    # Keep dict version for SSE event compatibility
                    await self.db.broadcast_event(
                        "image_captured", {"image": dict(image_row)}
                    )
                    return image
                raise Exception("Failed to record captured image")

    async def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get the total count of images for a timelapse.

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total image count

        Usage:
            count = await image_ops.get_image_count_by_timelapse(1)
        """
        query = "SELECT COUNT(*) as count FROM images WHERE timelapse_id = %s"
        async with self.db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (timelapse_id,))
                result = await cur.fetchone()
                return result["count"] if result else 0


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
        # Filter fields that belong to Image model
        image_fields = {k: v for k, v in row.items() if k in Image.model_fields}
        return Image(**image_fields)

    def record_captured_image(self, image_data: Dict[str, Any]) -> Image:
        """
        Record a newly captured image (sync version for worker).

        Args:
            image_data: Dictionary containing image metadata

        Returns:
            Created Image model instance

        Usage:
            image = image_ops.record_captured_image({...})
        """
        query = """
        INSERT INTO images (
            timelapse_id, file_path, file_size, captured_at,
            day_number, thumbnail_path, corruption_detected,
            glitch_severity, is_flagged
        ) VALUES (
            %(timelapse_id)s, %(file_path)s, %(file_size)s, %(captured_at)s,
            %(day_number)s, %(thumbnail_path)s, %(corruption_detected)s,
            %(glitch_severity)s, %(is_flagged)s
        ) RETURNING *
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, image_data)
                results = cur.fetchall()
                if results:
                    image_row = results[0]
                    image = self._row_to_image(image_row)
                    # Keep dict version for SSE event compatibility
                    self.db.broadcast_event(
                        "image_captured", {"image": dict(image_row)}
                    )
                    return image
                raise Exception("Failed to record captured image")

    def get_image_count_by_timelapse(self, timelapse_id: int) -> int:
        """
        Get the total count of images for a timelapse (sync version).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            Total image count

        Usage:
            count = image_ops.get_image_count_by_timelapse(1)
        """
        query = "SELECT COUNT(*) as count FROM images WHERE timelapse_id = %s"
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                result = cur.fetchone()
                return result[0] if result else 0

    def calculate_day_number(self, timelapse_id: int, captured_at: datetime) -> int:
        """
        Calculate the day number for an image within a timelapse.

        Args:
            timelapse_id: ID of the timelapse
            captured_at: When the image was captured

        Returns:
            Day number (1-based)

        Usage:
            day_num = image_ops.calculate_day_number(1, datetime.now())
        """
        query = """
        SELECT DATE(created_at) as start_date 
        FROM timelapses 
        WHERE id = %s
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (timelapse_id,))
                result = cur.fetchone()
                if result:
                    start_date = result["start_date"]
                    image_date = captured_at.date()
                    return (image_date - start_date).days + 1
                return 1

    def get_images_for_timelapse(self, timelapse_id: int) -> List[Image]:
        """
        Get all images for a specific timelapse (sync version for worker).

        Args:
            timelapse_id: ID of the timelapse

        Returns:
            List of Image model instances ordered by captured_at

        Usage:
            images = image_ops.get_images_for_timelapse(1)
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

    def cleanup_old_images(self, days_to_keep: int = 30) -> int:
        """
        Clean up old images based on retention policy.

        Args:
            days_to_keep: Number of days to keep images (default: 30)

        Returns:
            Number of images deleted

        Usage:
            deleted_count = image_ops.cleanup_old_images(7)
        """
        query = """
        DELETE FROM images
        WHERE captured_at < NOW() - INTERVAL '%s days'
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (days_to_keep,))
                affected = cur.rowcount or 0

                if affected > 0:
                    logger.info(f"Cleaned up {affected} old images")

                return affected
