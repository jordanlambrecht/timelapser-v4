import os
import psycopg
from psycopg.rows import dict_row
from datetime import datetime
from typing import List, Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.connection_string = os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError("DATABASE_URL environment variable is required")

    def get_connection(self):
        """Get a database connection"""
        try:
            conn = psycopg.connect(
                self.connection_string, row_factory=dict_row
            )
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def get_active_cameras(self) -> List[Dict]:
        """Get all active cameras"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT c.*, t.status as timelapse_status 
                        FROM cameras c 
                        LEFT JOIN timelapses t ON c.id = t.camera_id 
                        WHERE c.status = 'active'
                        ORDER BY c.id
                    """
                    )
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch active cameras: {e}")
            return []

    def get_running_timelapses(self) -> List[Dict]:
        """Get cameras with running timelapses"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT c.*, t.status as timelapse_status 
                        FROM cameras c 
                        INNER JOIN timelapses t ON c.id = t.camera_id 
                        WHERE c.status = 'active' AND t.status = 'running'
                        ORDER BY c.id
                    """
                    )
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch running timelapses: {e}")
            return []

    def get_capture_interval(self) -> int:
        """Get the current capture interval in seconds"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT value FROM settings WHERE key = 'capture_interval'"
                    )
                    result = cur.fetchone()
                    return int(result["value"]) if result else 300
        except Exception as e:
            logger.error(f"Failed to fetch capture interval: {e}")
            return 300  # Default to 5 minutes

    def log_capture_attempt(self, camera_id: int, success: bool, message: str = ""):
        """Log a capture attempt"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    level = "INFO" if success else "ERROR"
                    log_message = (
                        f"Image capture {'successful' if success else 'failed'}"
                    )
                    if message:
                        log_message += f": {message}"

                    cur.execute(
                        """
                        INSERT INTO logs (level, message, camera_id, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (level, log_message, camera_id, datetime.now()),
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to log capture attempt: {e}")

    def update_camera_last_capture(self, camera_id: int):
        """Update camera's last capture timestamp"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE cameras 
                        SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """,
                        (camera_id,),
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to update camera timestamp: {e}")

    def create_logs_table_if_not_exists(self):
        """Create logs table if it doesn't exist"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS logs (
                            id SERIAL PRIMARY KEY,
                            level VARCHAR(20) NOT NULL,
                            message TEXT NOT NULL,
                            camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
                            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """
                    )
                    conn.commit()
                    logger.info("Logs table created/verified")
        except Exception as e:
            logger.error(f"Failed to create logs table: {e}")

    def create_video_record(self, camera_id: int, name: str, settings: dict) -> Optional[int]:
        """Create a new video record and return its ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO videos (camera_id, name, status, settings)
                        VALUES (%s, %s, 'generating', %s)
                        RETURNING id
                    """, (camera_id, name, json.dumps(settings)))
                    conn.commit()
                    video_id = cur.fetchone()['id']
                    logger.info(f"Created video record {video_id} for camera {camera_id}")
                    return video_id
        except Exception as e:
            logger.error(f"Failed to create video record: {e}")
            return None

    def update_video_record(self, video_id: int, **kwargs):
        """Update video record with provided fields"""
        try:
            # Build dynamic update query
            valid_fields = ['name', 'file_path', 'status', 'settings', 'image_count', 
                           'file_size', 'duration_seconds', 'images_start_date', 'images_end_date']
            
            updates = []
            values = []
            for field, value in kwargs.items():
                if field in valid_fields:
                    updates.append(f"{field} = %s")
                    # Convert dict to JSON string for settings field
                    if field == 'settings' and isinstance(value, dict):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
            
            if not updates:
                return
                
            values.append(video_id)
            query = f"UPDATE videos SET {', '.join(updates)} WHERE id = %s"
            
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, values)
                    conn.commit()
                    logger.info(f"Updated video record {video_id}")
        except Exception as e:
            logger.error(f"Failed to update video record {video_id}: {e}")

    def get_camera_videos(self, camera_id: int) -> List[Dict]:
        """Get all videos for a specific camera"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM videos 
                        WHERE camera_id = %s 
                        ORDER BY created_at DESC
                    """, (camera_id,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch videos for camera {camera_id}: {e}")
            return []

    def get_video_by_id(self, video_id: int) -> Optional[Dict]:
        """Get a specific video by ID"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM videos WHERE id = %s", (video_id,))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Failed to fetch video {video_id}: {e}")
            return None

    def get_pending_video_generations(self) -> List[Dict]:
        """Get videos that are pending generation (status = 'generating')"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM videos 
                        WHERE status = 'generating'
                        ORDER BY created_at ASC
                    """)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch pending video generations: {e}")
            return []

    def update_camera_health(self, camera_id: int, success: bool):
        """Update camera health status based on capture success"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if success:
                        # Reset failure count and mark as online
                        cur.execute("""
                            UPDATE cameras 
                            SET health_status = 'online',
                                last_capture_at = CURRENT_TIMESTAMP,
                                last_capture_success = true,
                                consecutive_failures = 0,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (camera_id,))
                    else:
                        # Increment failure count
                        cur.execute("""
                            UPDATE cameras 
                            SET last_capture_success = false,
                                consecutive_failures = consecutive_failures + 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (camera_id,))
                        
                        # Check if we should mark as offline (3+ consecutive failures)
                        cur.execute("""
                            UPDATE cameras 
                            SET health_status = 'offline'
                            WHERE id = %s AND consecutive_failures >= 3
                        """, (camera_id,))
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to update camera health for camera {camera_id}: {e}")

    def check_camera_health_status(self):
        """Check and update health status for all cameras based on recent activity"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Mark cameras as offline if no capture in last 10 minutes
                    # (assuming 5 min capture interval + buffer)
                    cur.execute("""
                        UPDATE cameras 
                        SET health_status = 'offline'
                        WHERE status = 'active' 
                        AND health_status != 'offline'
                        AND (last_capture_at IS NULL 
                             OR last_capture_at < CURRENT_TIMESTAMP - INTERVAL '10 minutes')
                    """)
                    
                    affected = cur.rowcount
                    if affected > 0:
                        logger.warning(f"Marked {affected} cameras as offline due to inactivity")
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to check camera health status: {e}")

    def get_offline_cameras(self) -> List[Dict]:
        """Get cameras that are currently offline"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, health_status, last_capture_at, consecutive_failures
                        FROM cameras 
                        WHERE status = 'active' AND health_status = 'offline'
                        ORDER BY last_capture_at DESC NULLS LAST
                    """)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch offline cameras: {e}")
            return []

    def create_or_update_timelapse(self, camera_id: int, status: str) -> Optional[int]:
        """Create or update timelapse for camera, setting start_date on first run"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if timelapse exists
                    cur.execute("SELECT id, status FROM timelapses WHERE camera_id = %s", (camera_id,))
                    existing = cur.fetchone()
                    
                    if existing:
                        # Update existing timelapse
                        timelapse_id = existing['id']
                        
                        # If changing from stopped/paused to running, update start_date
                        if existing['status'] != 'running' and status == 'running':
                            cur.execute("""
                                UPDATE timelapses 
                                SET status = %s, start_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (status, timelapse_id))
                        else:
                            cur.execute("""
                                UPDATE timelapses 
                                SET status = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE id = %s
                            """, (status, timelapse_id))
                    else:
                        # Create new timelapse
                        cur.execute("""
                            INSERT INTO timelapses (camera_id, status, start_date)
                            VALUES (%s, %s, CURRENT_DATE)
                            RETURNING id
                        """, (camera_id, status))
                        timelapse_id = cur.fetchone()['id']
                    
                    conn.commit()
                    logger.info(f"Created/updated timelapse {timelapse_id} for camera {camera_id}")
                    return timelapse_id
                    
        except Exception as e:
            logger.error(f"Failed to create/update timelapse: {e}")
            return None

    def record_captured_image(self, camera_id: int, timelapse_id: int, file_path: str, file_size: int) -> Optional[int]:
        """Record a captured image in the database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get timelapse start date to calculate day number
                    cur.execute("SELECT start_date FROM timelapses WHERE id = %s", (timelapse_id,))
                    timelapse = cur.fetchone()
                    
                    if not timelapse or not timelapse['start_date']:
                        logger.error(f"Timelapse {timelapse_id} not found or missing start_date")
                        return None
                    
                    # Calculate day number (1-based)
                    from datetime import date
                    start_date = timelapse['start_date']
                    current_date = date.today()
                    day_number = (current_date - start_date).days + 1
                    
                    # Insert image record
                    cur.execute("""
                        INSERT INTO images (camera_id, timelapse_id, file_path, captured_at, day_number, file_size)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, %s, %s)
                        RETURNING id
                    """, (camera_id, timelapse_id, file_path, day_number, file_size))
                    
                    image_id = cur.fetchone()['id']
                    
                    # Update timelapse image count and last capture
                    cur.execute("""
                        UPDATE timelapses 
                        SET image_count = image_count + 1,
                            last_capture_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (timelapse_id,))
                    
                    conn.commit()
                    logger.info(f"Recorded image {image_id} for timelapse {timelapse_id}, day {day_number}")
                    return image_id
                    
        except Exception as e:
            logger.error(f"Failed to record captured image: {e}")
            return None

    def get_timelapse_images(self, timelapse_id: int, day_start: int = None, day_end: int = None) -> List[Dict]:
        """Get images for a specific timelapse, optionally filtered by day range"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT * FROM images 
                        WHERE timelapse_id = %s
                    """
                    params = [timelapse_id]
                    
                    if day_start is not None:
                        query += " AND day_number >= %s"
                        params.append(day_start)
                    
                    if day_end is not None:
                        query += " AND day_number <= %s"
                        params.append(day_end)
                    
                    query += " ORDER BY captured_at"
                    
                    cur.execute(query, params)
                    return cur.fetchall()
                    
        except Exception as e:
            logger.error(f"Failed to get timelapse images: {e}")
            return []

    def get_timelapse_day_range(self, timelapse_id: int) -> Dict:
        """Get day range and statistics for a timelapse"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            MIN(day_number) as min_day,
                            MAX(day_number) as max_day,
                            COUNT(*) as total_images,
                            COUNT(DISTINCT day_number) as days_with_images
                        FROM images 
                        WHERE timelapse_id = %s
                    """, (timelapse_id,))
                    
                    result = cur.fetchone()
                    return {
                        'min_day': result['min_day'] or 0,
                        'max_day': result['max_day'] or 0,
                        'total_images': result['total_images'] or 0,
                        'days_with_images': result['days_with_images'] or 0
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get timelapse day range: {e}")
            return {'min_day': 0, 'max_day': 0, 'total_images': 0, 'days_with_images': 0}

    def get_active_timelapse_for_camera(self, camera_id: int) -> Optional[Dict]:
        """Get the active (running) timelapse for a camera"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM timelapses 
                        WHERE camera_id = %s AND status = 'running'
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """, (camera_id,))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Failed to get active timelapse for camera {camera_id}: {e}")
            return None
