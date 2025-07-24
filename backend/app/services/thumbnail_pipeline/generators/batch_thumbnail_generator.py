# backend/app/services/thumbnail_pipeline/generators/batch_thumbnail_generator.py
"""
Batch Thumbnail Generator Component

Specialized component for bulk thumbnail and small image generation operations.
Optimized for processing multiple images efficiently with progress tracking.
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from .thumbnail_generator import ThumbnailGenerator
from .small_image_generator import SmallImageGenerator


class BatchThumbnailGenerator:
    """
    Component responsible for bulk thumbnail and small image generation.
    
    Optimized for:
    - Processing multiple images concurrently
    - Progress tracking and reporting
    - Memory-efficient batch operations
    - Error handling and recovery
    """

    def __init__(
        self,
        thumbnail_generator: Optional[ThumbnailGenerator] = None,
        small_generator: Optional[SmallImageGenerator] = None,
        max_workers: int = 4,
        batch_size: int = 10
    ):
        """
        Initialize batch thumbnail generator.

        Args:
            thumbnail_generator: Thumbnail generator instance
            small_generator: Small image generator instance
            max_workers: Maximum number of concurrent worker threads
            batch_size: Number of images to process in each batch
        """
        self.thumbnail_generator = thumbnail_generator or ThumbnailGenerator()
        self.small_generator = small_generator or SmallImageGenerator()
        self.max_workers = max(1, min(max_workers, 8))  # Limit to reasonable range
        self.batch_size = max(1, batch_size)
        
        logger.debug(f"✅ BatchThumbnailGenerator initialized (workers={self.max_workers}, batch_size={self.batch_size})")

    def generate_batch_thumbnails(
        self,
        image_tasks: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
        include_small_images: bool = True,
        force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Generate thumbnails and small images for a batch of images.

        Args:
            image_tasks: List of dicts with 'source_path', 'thumbnail_path', 'small_path', 'image_id'
            progress_callback: Optional callback function for progress updates
            include_small_images: Whether to generate small images in addition to thumbnails
            force_regenerate: Whether to overwrite existing files

        Returns:
            Dict containing batch processing results and statistics
        """
        try:
            total_tasks = len(image_tasks)
            if total_tasks == 0:
                return {
                    "success": True,
                    "total_tasks": 0,
                    "completed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "results": [],
                }

            logger.info(f"🔄 Starting batch thumbnail generation for {total_tasks} images")

            # Process in batches to manage memory usage
            all_results = []
            total_completed = 0
            total_failed = 0
            total_skipped = 0

            for batch_start in range(0, total_tasks, self.batch_size):
                batch_end = min(batch_start + self.batch_size, total_tasks)
                batch_tasks = image_tasks[batch_start:batch_end]
                
                logger.debug(f"Processing batch {batch_start // self.batch_size + 1}: images {batch_start + 1}-{batch_end}")

                # Process current batch
                batch_results = self._process_batch(
                    batch_tasks,
                    include_small_images,
                    force_regenerate
                )

                # Update counters
                for result in batch_results:
                    if result["success"]:
                        total_completed += 1
                    else:
                        if result.get("skipped"):
                            total_skipped += 1
                        else:
                            total_failed += 1

                all_results.extend(batch_results)

                # Call progress callback
                if progress_callback:
                    progress_callback(
                        batch_end,
                        total_tasks,
                        {
                            "completed": total_completed,
                            "failed": total_failed,
                            "skipped": total_skipped,
                            "current_batch": batch_start // self.batch_size + 1,
                            "total_batches": (total_tasks + self.batch_size - 1) // self.batch_size,
                        }
                    )

            logger.info(f"✅ Batch thumbnail generation completed: {total_completed} completed, {total_failed} failed, {total_skipped} skipped")

            return {
                "success": True,
                "total_tasks": total_tasks,
                "completed": total_completed,
                "failed": total_failed,
                "skipped": total_skipped,
                "results": all_results,
            }

        except Exception as e:
            logger.error(f"❌ Batch thumbnail generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_tasks": len(image_tasks),
                "completed": 0,
                "failed": len(image_tasks),
                "skipped": 0,
                "results": [],
            }

    def _process_batch(
        self,
        batch_tasks: List[Dict[str, Any]],
        include_small_images: bool,
        force_regenerate: bool
    ) -> List[Dict[str, Any]]:
        """
        Process a single batch of thumbnail generation tasks.

        Args:
            batch_tasks: List of image tasks for this batch
            include_small_images: Whether to generate small images
            force_regenerate: Whether to overwrite existing files

        Returns:
            List of processing results for the batch
        """
        batch_results = []

        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in batch_tasks:
                future = executor.submit(
                    self._process_single_image,
                    task,
                    include_small_images,
                    force_regenerate
                )
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    batch_results.append(result)
                except Exception as e:
                    logger.error(f"❌ Task failed for image {task.get('image_id', 'unknown')}: {e}")
                    batch_results.append({
                        "success": False,
                        "error": str(e),
                        "image_id": task.get("image_id"),
                        "source_path": task.get("source_path"),
                    })

        return batch_results

    def _process_single_image(
        self,
        task: Dict[str, Any],
        include_small_images: bool,
        force_regenerate: bool
    ) -> Dict[str, Any]:
        """
        Process thumbnail generation for a single image.

        Args:
            task: Image task with paths and metadata
            include_small_images: Whether to generate small images
            force_regenerate: Whether to overwrite existing files

        Returns:
            Dict containing processing result
        """
        try:
            image_id = task.get("image_id")
            source_path = task.get("source_path")
            thumbnail_path = task.get("thumbnail_path")
            small_path = task.get("small_path")

            if not source_path or not thumbnail_path:
                return {
                    "success": False,
                    "error": "Missing required paths in task",
                    "image_id": image_id,
                    "task": task,
                }
            
            # Ensure source_path is a string for type safety
            if not isinstance(source_path, str):
                return {
                    "success": False,
                    "error": f"Invalid source_path type: {type(source_path)}",
                    "image_id": image_id,
                    "task": task,
                }

            results = {
                "success": True,
                "image_id": image_id,
                "source_path": source_path,
                "thumbnail_generated": False,
                "small_generated": False,
                "errors": [],
            }

            # Generate thumbnail
            if thumbnail_path:
                thumbnail_result = self.thumbnail_generator.generate_thumbnail(
                    source_path=source_path,
                    output_path=thumbnail_path,
                    force_regenerate=force_regenerate
                )

                if thumbnail_result["success"]:
                    results["thumbnail_generated"] = thumbnail_result.get("generated", False)
                    results["thumbnail_path"] = thumbnail_result["output_path"]
                    results["thumbnail_size"] = thumbnail_result.get("file_size")
                else:
                    results["errors"].append(f"Thumbnail: {thumbnail_result.get('error', 'Unknown error')}")

            # Generate small image if requested
            if include_small_images and small_path:
                small_result = self.small_generator.generate_small_image(
                    source_path=source_path,
                    output_path=small_path,
                    force_regenerate=force_regenerate
                )

                if small_result["success"]:
                    results["small_generated"] = small_result.get("generated", False)
                    results["small_path"] = small_result["output_path"]
                    results["small_size"] = small_result.get("file_size")
                else:
                    results["errors"].append(f"Small image: {small_result.get('error', 'Unknown error')}")

            # Determine overall success
            if results["errors"]:
                results["success"] = False
                results["error"] = "; ".join(results["errors"])

            # Check if anything was actually generated
            if not results["thumbnail_generated"] and not results["small_generated"]:
                results["skipped"] = True

            return results

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "image_id": task.get("image_id"),
                "source_path": task.get("source_path"),
            }

    def estimate_batch_time(self, image_tasks: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Estimate processing time for a batch of images.

        Args:
            image_tasks: List of image tasks to estimate

        Returns:
            Dict containing time estimates
        """
        try:
            if not image_tasks:
                return {"total_time": 0.0, "per_image": 0.0, "parallel_time": 0.0}

            # Estimate time per image (assuming average image size)
            avg_thumbnail_time = 0.5  # seconds
            avg_small_time = 1.0  # seconds
            avg_time_per_image = avg_thumbnail_time + avg_small_time

            total_sequential_time = len(image_tasks) * avg_time_per_image
            
            # Account for parallelization
            parallel_time = total_sequential_time / self.max_workers
            
            # Add batch overhead
            batch_overhead = (len(image_tasks) / self.batch_size) * 0.1  # 0.1s per batch
            estimated_total = parallel_time + batch_overhead

            return {
                "total_time": estimated_total,
                "per_image": avg_time_per_image,
                "parallel_time": parallel_time,
                "sequential_time": total_sequential_time,
                "batches": (len(image_tasks) + self.batch_size - 1) // self.batch_size,
            }

        except Exception as e:
            logger.error(f"Failed to estimate batch time: {e}")
            return {"total_time": 0.0, "per_image": 0.0, "parallel_time": 0.0}

    def get_batch_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistics from batch processing results.

        Args:
            results: List of processing results

        Returns:
            Dict containing batch statistics
        """
        try:
            if not results:
                return {
                    "total_processed": 0,
                    "success_rate": 0.0,
                    "thumbnails_generated": 0,
                    "smalls_generated": 0,
                    "total_errors": 0,
                }

            total_processed = len(results)
            successful = sum(1 for r in results if r.get("success", False))
            thumbnails_generated = sum(1 for r in results if r.get("thumbnail_generated", False))
            smalls_generated = sum(1 for r in results if r.get("small_generated", False))
            total_errors = sum(1 for r in results if r.get("errors"))

            success_rate = (successful / total_processed) * 100 if total_processed > 0 else 0.0

            return {
                "total_processed": total_processed,
                "successful": successful,
                "success_rate": success_rate,
                "thumbnails_generated": thumbnails_generated,
                "smalls_generated": smalls_generated,
                "total_errors": total_errors,
                "error_rate": ((total_processed - successful) / total_processed) * 100 if total_processed > 0 else 0.0,
            }

        except Exception as e:
            logger.error(f"Failed to calculate batch statistics: {e}")
            return {"error": str(e)}