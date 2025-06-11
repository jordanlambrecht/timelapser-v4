import os
import subprocess
import logging
import re
from pathlib import Path
from typing import Tuple, Optional, Dict
import glob
from datetime import datetime, date
from database import Database

logger = logging.getLogger(__name__)


class VideoGenerator:
    def __init__(self, db: Database = None):
        self.default_framerate = 30
        self.default_quality = "medium"  # low, medium, high
        self.supported_formats = [".jpg", ".jpeg", ".png"]
        self.db = db or Database()

    def extract_date_from_filename(self, filename: str) -> Optional[date]:
        """Extract date from capture filename like 'capture_20240610_143022.jpg'"""
        try:
            # Expected format: capture_YYYYMMDD_HHMMSS.jpg
            basename = os.path.basename(filename)
            if basename.startswith("capture_") and len(basename) >= 21:
                date_str = basename[8:16]  # Extract YYYYMMDD
                return datetime.strptime(date_str, "%Y%m%d").date()
        except Exception:
            pass
        return None

    def get_image_date_range(
        self, image_files: list
    ) -> Tuple[Optional[date], Optional[date]]:
        """Get start and end dates from image filenames"""
        dates = []
        for file in image_files:
            file_date = self.extract_date_from_filename(file)
            if file_date:
                dates.append(file_date)

        if dates:
            return min(dates), max(dates)
        return None, None

    def get_quality_settings(self, quality: str) -> dict:
        """Get FFmpeg quality settings based on quality level"""
        settings = {
            "low": {"crf": 28, "preset": "fast", "scale": "1280:720"},
            "medium": {"crf": 23, "preset": "medium", "scale": "1920:1080"},
            "high": {
                "crf": 18,
                "preset": "slow",
                "scale": None,  # Keep original resolution
            },
        }
        return settings.get(quality, settings["medium"])

    def find_image_files(self, directory: Path) -> list:
        """Find all image files in directory and subdirectories, sorted by filename"""
        image_files = []

        # Check if this is a camera directory with date subdirectories
        has_date_subdirs = any(d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', d.name) for d in directory.iterdir() if d.is_dir())
        
        if directory.name.startswith('camera-') or has_date_subdirs:
            # This looks like a camera directory, search in date subdirectories
            for date_dir in directory.iterdir():
                if date_dir.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', date_dir.name):  # YYYY-MM-DD format
                    logger.info(f"Searching for images in date directory: {date_dir}")
                    for ext in self.supported_formats:
                        pattern = str(date_dir / f"*{ext}")
                        files = glob.glob(pattern)
                        image_files.extend(files)
        else:
            # Regular directory, search directly
            for ext in self.supported_formats:
                pattern = str(directory / f"*{ext}")
                files = glob.glob(pattern)
                image_files.extend(files)

        # Sort by filename (which includes timestamp)
        image_files.sort()

        logger.info(f"Found {len(image_files)} image files in {directory}")
        return image_files

    def generate_video(
        self,
        images_directory: str,
        output_path: str,
        framerate: int = None,
        quality: str = None,
    ) -> Tuple[bool, str]:
        """
        Generate MP4 video from images in directory

        Returns:
            (success: bool, message: str)
        """
        try:
            images_dir = Path(images_directory)
            if not images_dir.exists():
                return False, f"Images directory does not exist: {images_directory}"

            # Find image files
            image_files = self.find_image_files(images_dir)
            if len(image_files) < 2:
                return (
                    False,
                    f"Need at least 2 images to create video, found {len(image_files)}",
                )

            # Set defaults
            framerate = framerate or self.default_framerate
            quality = quality or self.default_quality
            quality_settings = self.get_quality_settings(quality)

            # Prepare output directory
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Generating video from {len(image_files)} images")
            logger.info(f"Output: {output_path}")
            logger.info(f"Settings: {framerate}fps, quality={quality}")

            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-framerate",
                str(framerate),
                "-pattern_type",
                "glob",
                "-i",
                str(images_dir / "*.jpg"),  # Input pattern
                "-c:v",
                "libx264",  # Video codec
                "-pix_fmt",
                "yuv420p",  # Pixel format for compatibility
                "-crf",
                str(quality_settings["crf"]),  # Quality
                "-preset",
                quality_settings["preset"],  # Encoding speed
            ]

            # Add scaling if specified
            if quality_settings["scale"]:
                cmd.extend(["-vf", f"scale={quality_settings['scale']}"])

            # Add output path
            cmd.append(str(output_path))

            # Log the command (without full paths for readability)
            cmd_str = " ".join(cmd).replace(str(images_dir.parent), "...")
            logger.info(f"FFmpeg command: {cmd_str}")

            # Execute FFmpeg
            start_time = datetime.now()
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode != 0:
                error_msg = f"FFmpeg failed: {result.stderr}"
                logger.error(error_msg)
                return False, error_msg

            # Check if output file was created
            if not output_path.exists():
                return False, "Output video file was not created"

            file_size = output_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)

            success_msg = (
                f"Video generated successfully in {duration:.1f}s. "
                f"File size: {file_size_mb:.1f}MB"
            )
            logger.info(success_msg)

            return True, success_msg

        except subprocess.TimeoutExpired:
            return False, "Video generation timed out (5 minutes)"
        except Exception as e:
            error_msg = f"Video generation failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def test_ffmpeg_available(self) -> Tuple[bool, str]:
        """Test if FFmpeg is available on the system"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # Extract version info
                version_line = result.stdout.split("\n")[0]
                return True, f"FFmpeg available: {version_line}"
            else:
                return False, "FFmpeg command failed"

        except FileNotFoundError:
            return False, "FFmpeg not found. Please install FFmpeg."
        except Exception as e:
            return False, f"Error testing FFmpeg: {str(e)}"

    def generate_video_from_timelapse(
        self,
        timelapse_id: int,
        output_directory: str,
        video_name: str = None,
        framerate: int = None,
        quality: str = None,
        day_start: int = None,
        day_end: int = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Generate video from a specific timelapse using database-tracked images

        Args:
            timelapse_id: ID of the timelapse to generate video from
            output_directory: Where to save the video
            video_name: Optional custom name for the video
            framerate: Video framerate (default: 30)
            quality: Video quality level (low/medium/high)
            day_start: Optional start day filter (e.g., generate from day 10)
            day_end: Optional end day filter (e.g., generate until day 50)

        Returns:
            (success: bool, message: str, video_id: Optional[int])
        """
        video_id = None

        try:
            # Set defaults
            framerate = framerate or self.default_framerate
            quality = quality or self.default_quality

            # Get timelapse images from database
            images = self.db.get_timelapse_images(timelapse_id, day_start, day_end)

            if len(images) < 2:
                return (
                    False,
                    f"Need at least 2 images for video, found {len(images)} for timelapse {timelapse_id}",
                    None,
                )

            # Get day range statistics
            day_stats = self.db.get_timelapse_day_range(timelapse_id)
            max_day = day_stats["max_day"]

            # Get camera info (for naming)
            camera_id = images[0]["camera_id"] if images else None
            if not camera_id:
                return False, "No camera ID found for timelapse", None

            # Get camera name
            cameras = self.db.get_active_cameras()
            camera = next((c for c in cameras if c["id"] == camera_id), None)
            camera_name = camera["name"] if camera else f"Camera-{camera_id}"

            # Generate video name if not provided
            if not video_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                day_range = (
                    f"_days{day_start}-{day_end}"
                    if day_start or day_end
                    else f"_day1-{max_day}"
                )
                video_name = f"{camera_name}_timelapse{day_range}_{timestamp}"

            # Prepare output path
            output_dir = Path(output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_name}.mp4"

            # Create video record in database
            settings = {
                "framerate": framerate,
                "quality": quality,
                "timelapse_id": timelapse_id,
                "day_start": day_start,
                "day_end": day_end,
                "output_directory": str(output_directory),
            }

            video_id = self.db.create_video_record(
                camera_id=camera_id, name=video_name, settings=settings
            )

            if not video_id:
                return False, "Failed to create video record in database", None

            logger.info(f"Created video record {video_id} for timelapse {timelapse_id}")
            logger.info(
                f"Processing {len(images)} images from days {day_start or 1} to {day_end or max_day}"
            )

            # Create temporary directory with sequential image files
            import tempfile
            import shutil

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Copy images to temp directory with sequential naming for FFmpeg
                for i, image in enumerate(images):
                    src_path = Path(image["file_path"])
                    if not src_path.exists():
                        logger.warning(f"Image file not found: {src_path}")
                        continue

                    # Use sequential naming: frame_000001.jpg, frame_000002.jpg, etc.
                    ext = src_path.suffix
                    dst_path = temp_path / f"frame_{i+1:06d}{ext}"
                    shutil.copy2(src_path, dst_path)

                # Count actual copied files
                copied_files = list(temp_path.glob("frame_*"))
                if len(copied_files) < 2:
                    return (
                        False,
                        f"Only {len(copied_files)} valid image files found",
                        video_id,
                    )

                logger.info(f"Copied {len(copied_files)} images to temporary directory")

                # Get date range from first and last images
                start_date = datetime.fromisoformat(
                    str(images[0]["captured_at"])
                ).date()
                end_date = datetime.fromisoformat(str(images[-1]["captured_at"])).date()

                # Update record with initial metadata
                self.db.update_video_record(
                    video_id,
                    image_count=len(copied_files),
                    images_start_date=start_date,
                    images_end_date=end_date,
                )

                # Generate the video using the temporary directory
                success, message = self.generate_video(
                    images_directory=str(temp_path),
                    output_path=str(output_path),
                    framerate=framerate,
                    quality=quality,
                )

                if success:
                    # Get file size
                    file_size = (
                        output_path.stat().st_size if output_path.exists() else 0
                    )

                    # Calculate duration (images / framerate)
                    duration_seconds = len(copied_files) / framerate

                    # Update record with success
                    self.db.update_video_record(
                        video_id,
                        status="completed",
                        file_path=str(output_path),
                        file_size=file_size,
                        duration_seconds=duration_seconds,
                    )

                    success_msg = f"Timelapse video generated: {video_name}.mp4 ({len(copied_files)} images, {duration_seconds:.1f}s)"
                    logger.info(f"Video {video_id} completed: {success_msg}")
                    return True, success_msg, video_id

                else:
                    # Update record with failure
                    self.db.update_video_record(video_id, status="failed")
                    logger.error(f"Video {video_id} generation failed: {message}")
                    return False, f"Video generation failed: {message}", video_id

        except Exception as e:
            error_msg = f"Timelapse video generation failed: {str(e)}"
            logger.error(error_msg)

            # Update record with failure if we have video_id
            if video_id:
                try:
                    self.db.update_video_record(video_id, status="failed")
                except Exception:
                    pass  # Don't fail on cleanup failure

            return False, error_msg, video_id

    def generate_video_with_tracking(
        self,
        camera_id: int,
        camera_name: str,
        images_directory: str,
        output_directory: str,
        video_name: str = None,
        framerate: int = None,
        quality: str = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Generate video with full database tracking

        Returns:
            (success: bool, message: str, video_id: Optional[int])
        """
        video_id = None

        try:
            # Set defaults
            framerate = framerate or self.default_framerate
            quality = quality or self.default_quality

            if not video_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                video_name = f"{camera_name}_timelapse_{timestamp}"

            # Prepare output path
            output_dir = Path(output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_name}.mp4"

            # Find images and get metadata
            images_dir = Path(images_directory)
            image_files = self.find_image_files(images_dir)

            if len(image_files) < 2:
                return (
                    False,
                    f"Need at least 2 images to create video, found {len(image_files)}",
                    None,
                )

            # Get date range from images
            start_date, end_date = self.get_image_date_range(image_files)

            # Create video record in database
            settings = {
                "framerate": framerate,
                "quality": quality,
                "input_directory": str(images_directory),
                "output_directory": str(output_directory),
            }

            video_id = self.db.create_video_record(
                camera_id=camera_id, name=video_name, settings=settings
            )

            if not video_id:
                return False, "Failed to create video record in database", None

            logger.info(f"Created video record {video_id}, starting generation...")

            # Update record with initial metadata
            self.db.update_video_record(
                video_id,
                image_count=len(image_files),
                images_start_date=start_date,
                images_end_date=end_date,
            )

            # Check if we need to handle subdirectories (camera folder with date subdirs)
            has_date_subdirs = any(d.is_dir() and re.match(r'\d{4}-\d{2}-\d{2}', d.name) for d in images_dir.iterdir() if d.is_dir())
            
            success = False
            message = ""
            
            if has_date_subdirs:
                # Handle camera directory with date subdirectories
                # Copy all images to temporary directory with sequential naming
                import tempfile
                import shutil

                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # Copy images to temp directory with sequential naming for FFmpeg
                    for i, image_file in enumerate(image_files):
                        src_path = Path(image_file)
                        if not src_path.exists():
                            logger.warning(f"Image file not found: {src_path}")
                            continue

                        # Use sequential naming: frame_000001.jpg, frame_000002.jpg, etc.
                        ext = src_path.suffix
                        dst_path = temp_path / f"frame_{i+1:06d}{ext}"
                        shutil.copy2(src_path, dst_path)

                    # Count actual copied files
                    copied_files = list(temp_path.glob("frame_*"))
                    if len(copied_files) < 2:
                        return (
                            False,
                            f"Only {len(copied_files)} valid image files found",
                            video_id,
                        )

                    logger.info(f"Copied {len(copied_files)} images to temporary directory for FFmpeg")

                    # Generate the video using the temporary directory
                    success, message = self.generate_video(
                        images_directory=str(temp_path),
                        output_path=str(output_path),
                        framerate=framerate,
                        quality=quality,
                    )
            else:
                # Regular directory, generate directly
                success, message = self.generate_video(
                    images_directory=str(images_directory),
                    output_path=str(output_path),
                    framerate=framerate,
                    quality=quality,
                )

            if success:
                # Get file size
                file_size = output_path.stat().st_size if output_path.exists() else 0

                # Calculate estimated duration (images / framerate)
                duration_seconds = len(image_files) / framerate

                # Update record with success
                self.db.update_video_record(
                    video_id,
                    status="completed",
                    file_path=str(output_path),
                    file_size=file_size,
                    duration_seconds=duration_seconds,
                )

                logger.info(f"Video {video_id} completed successfully")
                return True, f"Video generated successfully: {video_name}.mp4", video_id

            else:
                # Update record with failure
                self.db.update_video_record(video_id, status="failed")

                logger.error(f"Video {video_id} generation failed: {message}")
                return False, f"Video generation failed: {message}", video_id

        except Exception as e:
            error_msg = f"Video generation with tracking failed: {str(e)}"
            logger.error(error_msg)

            # Update record with failure if we have video_id
            if video_id:
                try:
                    self.db.update_video_record(video_id, status="failed")
                except Exception:
                    pass  # Don't fail on cleanup failure

            return False, error_msg, video_id


def main():
    """Test function for video generation"""
    import sys
    from dotenv import load_dotenv

    # Load environment
    load_dotenv("../.env.local")

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    generator = VideoGenerator()

    # Test FFmpeg availability
    ffmpeg_ok, ffmpeg_msg = generator.test_ffmpeg_available()
    print(f"FFmpeg test: {ffmpeg_msg}")

    if not ffmpeg_ok:
        print("❌ FFmpeg not available. Please install it first.")
        sys.exit(1)

    # Test video generation if directory provided
    if len(sys.argv) > 1:
        images_dir = sys.argv[1]

        if len(sys.argv) > 2 and sys.argv[2] == "--with-db":
            # Test database integration
            output_dir = sys.argv[3] if len(sys.argv) > 3 else "/Users/jordanlambrecht/dev-local/timelapser-v4/data/videos"

            print(f"\n📹 Generating video with database tracking...")
            print(f"   Images: {images_dir}")
            print(f"   Output: {output_dir}")

            success, message, video_id = generator.generate_video_with_tracking(
                camera_id=1,
                camera_name="TestCamera",
                images_directory=images_dir,
                output_directory=output_dir,
            )

            if success:
                print(f"✅ {message}")
                print(f"   Video ID: {video_id}")
            else:
                print(f"❌ {message}")
                if video_id:
                    print(f"   Video ID: {video_id} (marked as failed)")
        else:
            # Test basic generation
            output_file = sys.argv[2] if len(sys.argv) > 2 else "test_timelapse.mp4"

            print(f"\n📹 Generating video (basic mode): {images_dir}")
            success, message = generator.generate_video(images_dir, output_file)

            if success:
                print(f"✅ {message}")
            else:
                print(f"❌ {message}")
    else:
        print("\nUsage:")
        print("  Basic: python video_generator.py <images_directory> [output_file]")
        print(
            "  With DB: python video_generator.py <images_directory> --with-db [output_directory]"
        )
        print("\nExamples:")
        print("  python video_generator.py /Users/jordanlambrecht/dev-local/timelapser-v4/data/cameras/camera-1/images/2025-06-10/")
        print(
            "  python video_generator.py /Users/jordanlambrecht/dev-local/timelapser-v4/data/cameras/camera-1/images/2025-06-10/ --with-db /Users/jordanlambrecht/dev-local/timelapser-v4/data/videos"
        )


if __name__ == "__main__":
    main()
