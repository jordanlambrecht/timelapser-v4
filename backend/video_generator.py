# backend/video_generator.py

import os
import subprocess
import logging
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Union
import glob
from datetime import datetime, date
from app.database import SyncDatabase

logger = logging.getLogger(__name__)


class VideoGenerator:
    """
    Advanced video generator for timelapse creation with overlay support.
    
    This class handles the generation of MP4 videos from sequences of images,
    with support for:
    - Dynamic day overlays using FFmpeg drawtext and subtitle systems
    - Multiple quality settings (low, medium, high)
    - Configurable framerates and output formats
    - Database integration for timelapse tracking
    - RTSP capture integration
    - ASS subtitle format for precise overlay timing
    
    The generator supports both simple static overlays and complex dynamic
    overlays that change per frame based on capture metadata.
    
    Attributes:
        default_framerate (int): Default video framerate (30 fps)
        default_quality (str): Default quality setting ('medium')
        supported_formats (List[str]): Supported image formats
        db (Optional[SyncDatabase]): Database connection for timelapse data
        default_overlay_settings (dict): Default overlay configuration
    """
    
    def __init__(self, db: Optional[SyncDatabase] = None):
        """
        Initialize the VideoGenerator with optional database connection.
        
        Args:
            db (Optional[SyncDatabase]): Database instance for timelapse data.
                                       If None, database-dependent features will be disabled.
        
        Sets up default video generation parameters and overlay settings including:
        - 30fps default framerate
        - Medium quality preset
        - Support for JPG, JPEG, PNG formats
        - Bottom-right positioned day overlays with white text
        """
        self.default_framerate = 30
        self.default_quality = "medium"  # low, medium, high
        self.supported_formats = [".jpg", ".jpeg", ".png"]
        self.db = db  # Use the provided database instance

        # Day overlay default settings
        self.default_overlay_settings = {
            "enabled": True,
            "position": "bottom-right",  # top-left, top-right, bottom-left, bottom-right, center
            "font_size": 48,
            "font_color": "white",
            "background_color": "black@0.5",  # Semi-transparent black background
            "padding": 20,  # Pixels from edge
            "format": "Day {day}",  # Template: {day}, {day_of_total}, {date}, etc.
        }

    def get_overlay_position(
        self, position: str, font_size: int, padding: int
    ) -> Tuple[str, str]:
        """
        Convert position name to FFmpeg x,y coordinates.
        
        Args:
            position (str): Position name (top-left, top-right, bottom-left, 
                          bottom-right, center)
            font_size (int): Font size for text positioning calculations
            padding (int): Padding in pixels from screen edges
            
        Returns:
            Tuple[str, str]: FFmpeg x,y coordinate strings for text positioning
        """
        positions = {
            "top-left": (str(padding), str(padding)),
            "top-right": (f"w-text_w-{padding}", str(padding)),
            "bottom-left": (str(padding), f"h-text_h-{padding}"),
            "bottom-right": (f"w-text_w-{padding}", f"h-text_h-{padding}"),
            "center": ("(w-text_w)/2", "(h-text_h)/2"),
        }
        return positions.get(position, positions["bottom-right"])

    def create_day_overlay_filter(
        self, images: list, overlay_settings: Optional[dict] = None
    ) -> Optional[str]:
        """
        Create FFmpeg drawtext filter for day overlays

        Args:
            images: List of image dictionaries with day_number
            overlay_settings: Overlay configuration

        Returns:
            FFmpeg filter string
        """
        if not overlay_settings:
            overlay_settings = self.default_overlay_settings.copy()

        if not overlay_settings.get("enabled", True):
            return None

        # Get position coordinates
        x, y = self.get_overlay_position(
            overlay_settings.get("position", "bottom-right"),
            overlay_settings.get("font_size", 48),
            overlay_settings.get("padding", 20),
        )

        # Build drawtext filter
        font_size = overlay_settings.get("font_size", 48)
        font_color = overlay_settings.get("font_color", "white")
        bg_color = overlay_settings.get("background_color", "black@0.5")
        text_format = overlay_settings.get("format", "Day {day}")

        # Create dynamic text based on frame number
        # We'll map frame numbers to day numbers using a text file approach
        if len(images) > 0:
            min_day = min(img.get("day_number", 1) for img in images)
            max_day = max(img.get("day_number", 1) for img in images)

            # For now, use a simple linear mapping approach
            # More complex mapping will be added later with subtitle files
            if min_day == max_day:
                # All images from same day
                display_text = text_format.format(
                    day=min_day, day_of_total=f"{min_day}"
                )
            else:
                # Multiple days - use frame-based calculation
                # This is a simplified approach; more sophisticated mapping will be added
                total_days = max_day - min_day + 1
                display_text = f"Day {min_day}-{max_day}"
        else:
            display_text = "Day 1"

        # Build the drawtext filter
        filter_parts = [
            f"drawtext=text='{display_text}'",
            f"fontsize={font_size}",
            f"fontcolor={font_color}",
            f"x={x}",
            f"y={y}",
        ]

        # Add background box if specified
        if bg_color and bg_color != "none":
            filter_parts.extend(["box=1", f"boxcolor={bg_color}", "boxborderw=5"])

        return ":".join(filter_parts)

    def create_dynamic_day_overlay(
        self, images: list, overlay_settings: Optional[dict] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create dynamic day overlay that changes per frame using ASS subtitles.
        
        This method generates a temporary ASS subtitle file where each frame
        can display different text based on the image metadata. This allows
        for precise day numbering that changes throughout the video.
        
        Args:
            images (list): List of image dictionaries containing day_number
                          and capture metadata
            overlay_settings (Optional[dict]): Overlay configuration settings.
                                             Uses default_overlay_settings if None.
        
        Returns:
            Tuple[Optional[str], Optional[str]]: 
                - Path to temporary subtitle file (or None if disabled)
                - FFmpeg subtitle filter string (or None if disabled)
                
        Note:
            The temporary subtitle file must be cleaned up by the caller
            after video generation is complete.
        """
        import tempfile

        if not overlay_settings:
            overlay_settings = self.default_overlay_settings.copy()

        if not overlay_settings.get("enabled", True) or not images:
            return None, None

        # Create temporary subtitle file for dynamic text
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False)

        try:
            # Write ASS subtitle format header
            temp_file.write(
                """[Script Info]
Title: Day Overlay
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,{alignment},20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".format(
                    font_size=overlay_settings.get("font_size", 48),
                    alignment=self._get_ass_alignment(
                        overlay_settings.get("position", "bottom-right")
                    ),
                )
            )

            # Calculate frame duration in seconds
            framerate = 30  # We'll get this from the actual generation call
            frame_duration = 1.0 / framerate

            # Write subtitle entries for each frame/image
            for i, image in enumerate(images):
                start_time = i * frame_duration
                end_time = (i + 1) * frame_duration
                day_number = image.get("day_number", 1)

                # Format time as HH:MM:SS.cc
                start_str = self._seconds_to_ass_time(start_time)
                end_str = self._seconds_to_ass_time(end_time)

                # Format text
                text_format = overlay_settings.get("format", "Day {day}")
                display_text = text_format.format(day=day_number)

                # Write subtitle line
                temp_file.write(
                    f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{display_text}\n"
                )

            temp_file.close()

            # Create subtitle filter
            subtitle_filter = f"subtitles={temp_file.name}"

            return temp_file.name, subtitle_filter

        except Exception as e:
            logger.error(f"Failed to create dynamic overlay: {e}")
            temp_file.close()
            try:
                os.unlink(temp_file.name)
            except:
                pass
            return None, None

    def _get_ass_alignment(self, position: str) -> int:
        """
        Convert position name to ASS subtitle alignment number.
        
        ASS subtitles use numeric alignment values (1-9) corresponding to
        a 3x3 grid, where 1 is bottom-left and 9 is top-right.
        
        Args:
            position (str): Position name (e.g., 'bottom-right', 'center')
            
        Returns:
            int: ASS alignment number (1-9), defaults to 3 (bottom-right)
        """
        alignments = {
            "bottom-left": 1,
            "bottom-center": 2,
            "bottom-right": 3,
            "center-left": 4,
            "center": 5,
            "center-right": 6,
            "top-left": 7,
            "top-center": 8,
            "top-right": 9,
        }
        return alignments.get(position, 3)  # Default to bottom-right

    def _seconds_to_ass_time(self, seconds: float) -> str:
        """
        Convert seconds to ASS time format (H:MM:SS.cc).
        
        ASS subtitle format requires time in H:MM:SS.cc format where
        cc represents centiseconds (hundredths of a second).
        
        Args:
            seconds (float): Time in seconds
            
        Returns:
            str: Time formatted as H:MM:SS.cc for ASS subtitles
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

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
        has_date_subdirs = any(
            d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}", d.name)
            for d in directory.iterdir()
            if d.is_dir()
        )

        if directory.name.startswith("camera-") or has_date_subdirs:
            # This looks like a camera directory, search in date subdirectories
            for date_dir in directory.iterdir():
                if date_dir.is_dir() and re.match(
                    r"\d{4}-\d{2}-\d{2}", date_dir.name
                ):  # YYYY-MM-DD format
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
        images_directory: Union[str, Path],
        output_path: Union[str, Path],
        framerate: Optional[int] = None,
        quality: Optional[str] = None,
        overlay_settings: Optional[dict] = None,
        day_overlay_data: Optional[list] = None,
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

            # Build video filters
            filters = []

            # Add scaling if specified
            if quality_settings["scale"]:
                filters.append(f"scale={quality_settings['scale']}")

            # Add day overlay if enabled
            subtitle_file = None
            try:
                if (
                    overlay_settings
                    and overlay_settings.get("enabled", True)
                    and day_overlay_data
                ):
                    logger.info("Adding day overlay to video")

                    # Create dynamic overlay with subtitle file
                    subtitle_file, subtitle_filter = self.create_dynamic_day_overlay(
                        day_overlay_data, overlay_settings
                    )

                    if subtitle_filter:
                        filters.append(subtitle_filter)
                        logger.info(f"Added overlay filter: {subtitle_filter}")
                    else:
                        # Fallback to simple static overlay
                        static_overlay = self.create_day_overlay_filter(
                            day_overlay_data, overlay_settings
                        )
                        if static_overlay:
                            filters.append(static_overlay)
                            logger.info(f"Added static overlay: {static_overlay}")

                elif overlay_settings and overlay_settings.get("enabled", True):
                    # Use default overlay even without day data
                    logger.info("Adding default day overlay")
                    default_overlay = self.create_day_overlay_filter(
                        [], overlay_settings
                    )
                    if default_overlay:
                        filters.append(default_overlay)

            except Exception as e:
                logger.warning(f"Failed to add overlay, continuing without: {e}")

            # Apply filters if any
            if filters:
                cmd.extend(["-vf", ",".join(filters)])
                logger.info(f"Applied video filters: {filters}")

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

            # Cleanup subtitle file if created
            if subtitle_file:
                try:
                    os.unlink(subtitle_file)
                except:
                    pass

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

    def generate_video_from_timelapse_with_overlays(
        self,
        timelapse_id: int,
        output_directory: Union[str, Path],
        video_name: Optional[str] = None,
        framerate: Optional[int] = None,
        quality: Optional[str] = None,
        day_start: Optional[int] = None,
        day_end: Optional[int] = None,
        overlay_settings: Optional[dict] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Generate video from a specific timelapse with overlay support

        Args:
            timelapse_id: ID of the timelapse to generate video from
            output_directory: Where to save the video
            video_name: Optional custom name for the video
            framerate: Video framerate (default: 30)
            quality: Video quality level (low/medium/high)
            day_start: Optional start day filter
            day_end: Optional end day filter
            overlay_settings: Day overlay configuration

        Returns:
            (success: bool, message: str, video_id: Optional[int])
        """
        video_id = None

        try:
            # Ensure database is available
            if not self.db:
                return (
                    False,
                    "Database connection required for timelapse video generation",
                    None,
                )

            # Type assertion for the rest of the method
            db = self.db

            # Set defaults
            framerate = framerate or self.default_framerate
            quality = quality or self.default_quality

            # Get timelapse images from database
            images = db.get_timelapse_images(timelapse_id, day_start, day_end)

            if len(images) < 2:
                return (
                    False,
                    f"Need at least 2 images for video, found {len(images)} for timelapse {timelapse_id}",
                    None,
                )

            # Get day range statistics
            day_stats = db.get_timelapse_day_range(timelapse_id)
            max_day = day_stats["max_day"]

            # Get camera info (for naming)
            camera_id = images[0]["camera_id"] if images else None
            if not camera_id:
                return False, "No camera ID found for timelapse", None

            # Get camera name
            cameras = db.get_active_cameras()
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
                overlay_suffix = (
                    "_overlay"
                    if overlay_settings and overlay_settings.get("enabled")
                    else ""
                )
                video_name = (
                    f"{camera_name}_timelapse{day_range}{overlay_suffix}_{timestamp}"
                )

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
                "overlay_settings": overlay_settings,  # Store overlay settings
            }

            video_id = db.create_video_record(
                camera_id=camera_id, name=video_name, settings=settings
            )

            if not video_id:
                return False, "Failed to create video record in database", None

            logger.info(f"Created video record {video_id} for timelapse {timelapse_id}")
            logger.info(
                f"Processing {len(images)} images from days {day_start or 1} to {day_end or max_day}"
            )

            # Log overlay settings
            if overlay_settings and overlay_settings.get("enabled"):
                logger.info(f"Overlay enabled: {overlay_settings}")

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
                db.update_video_record(
                    video_id,
                    image_count=len(copied_files),
                    images_start_date=start_date,
                    images_end_date=end_date,
                )

                # Generate the video using the temporary directory with overlays
                success, message = self.generate_video(
                    images_directory=str(temp_path),
                    output_path=str(output_path),
                    framerate=framerate,
                    quality=quality,
                    overlay_settings=overlay_settings,
                    day_overlay_data=images,  # Pass the image data with day numbers
                )

                if success:
                    # Get file size
                    file_size = (
                        output_path.stat().st_size if output_path.exists() else 0
                    )

                    # Calculate duration (images / framerate)
                    duration_seconds = len(copied_files) / framerate

                    # Update record with success
                    db.update_video_record(
                        video_id,
                        status="completed",
                        file_path=str(output_path),
                        file_size=file_size,
                        duration_seconds=duration_seconds,
                    )

                    success_msg = f"Timelapse video with overlays generated: {video_name}.mp4 ({len(copied_files)} images, {duration_seconds:.1f}s)"
                    logger.info(f"Video {video_id} completed: {success_msg}")
                    return True, success_msg, video_id

                else:
                    # Update record with failure
                    db.update_video_record(video_id, status="failed")
                    logger.error(f"Video {video_id} generation failed: {message}")
                    return False, f"Video generation failed: {message}", video_id

        except Exception as e:
            error_msg = f"Timelapse video generation with overlays failed: {str(e)}"
            logger.error(error_msg)

            # Update record with failure if we have video_id
            if video_id and self.db:
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

    print("✅ Day overlay system is ready!")
    print("📋 Available features:")
    print("  • Dynamic day overlays (Day 1, Day 2, etc.)")
    print("  • Configurable position and styling")
    print("  • ASS subtitle format for precise timing")
    print("  • Database integration with timelapse tracking")


if __name__ == "__main__":
    main()
