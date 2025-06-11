import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date
import psycopg
from psycopg.rows import dict_row

# Import our modules
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from capture import RTSPCapture
from video_generator import VideoGenerator

@pytest.fixture
def mock_db_config():
    """Mock database configuration for testing"""
    return {
        'host': 'localhost',
        'database': 'test_timelapser',
        'user': 'test_user',
        'password': 'test_pass'
    }

@pytest.fixture
def mock_connection(mock_db_config):
    """Mock database connection that returns dict-like rows"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    return mock_conn, mock_cursor

@pytest.fixture
def database_instance(mock_connection):
    """Database instance with mocked connection"""
    mock_conn, mock_cursor = mock_connection
    
    with patch('database.psycopg.connect') as mock_connect, \
         patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
        mock_connect.return_value = mock_conn
        db = Database()
        db.connection_string = "mock://test"
        yield db, mock_cursor

@pytest.fixture
def sample_camera_data():
    """Sample camera data for testing"""
    return {
        'id': 1,
        'name': 'Test Camera',
        'rtsp_url': 'rtsp://192.168.1.100:554/stream',
        'status': 'active',
        'health_status': 'online',
        'last_capture_at': datetime.now(),
        'consecutive_failures': 0,
        'use_time_window': True,
        'time_window_start': '06:00',
        'time_window_end': '18:00',
        'created_at': datetime.now()
    }

@pytest.fixture
def sample_timelapse_data():
    """Sample timelapse data for testing"""
    return {
        'id': 1,
        'camera_id': 1,
        'status': 'running',
        'start_date': date.today(),
        'image_count': 0,
        'last_capture_at': None,
        'settings': {'quality': 'medium', 'framerate': 30},
        'created_at': datetime.now()
    }

@pytest.fixture
def sample_image_data():
    """Sample image data for testing"""
    return {
        'id': 1,
        'camera_id': 1,
        'timelapse_id': 1,
        'file_path': '/data/cameras/camera-1/images/2025-06-10/capture_20250610_120000.jpg',
        'captured_at': datetime.now(),
        'day_number': 1,
        'file_size': 1024000,
        'created_at': datetime.now()
    }

@pytest.fixture
def mock_opencv():
    """Mock OpenCV for RTSP testing"""
    with patch('capture.cv2') as mock_cv2:
        mock_cap = MagicMock()
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, MagicMock())  # success, frame
        mock_cap.get.side_effect = lambda prop: 1920 if prop == mock_cv2.CAP_PROP_FRAME_WIDTH else 1080
        yield mock_cv2, mock_cap

@pytest.fixture
def mock_ffmpeg():
    """Mock FFmpeg subprocess calls"""
    with patch('video_generator.subprocess.run') as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        yield mock_run

@pytest.fixture
def temp_directory():
    """Temporary directory for file operations"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def mock_file_operations():
    """Mock file system operations"""
    with patch('builtins.open', create=True) as mock_open, \
         patch('os.path.exists') as mock_exists, \
         patch('os.makedirs') as mock_makedirs, \
         patch('os.path.getsize') as mock_getsize:
        
        mock_exists.return_value = True
        mock_getsize.return_value = 1024000  # 1MB
        yield {
            'open': mock_open,
            'exists': mock_exists,
            'makedirs': mock_makedirs,
            'getsize': mock_getsize
        }

@pytest.fixture
def rtsp_capture_instance(mock_opencv, temp_directory):
    """RTSP capture instance with mocked OpenCV and temp directory"""
    mock_cv2, mock_cap = mock_opencv
    capture = RTSPCapture(base_data_dir=temp_directory)
    return capture

@pytest.fixture
def video_generator_instance(database_instance, mock_ffmpeg):
    """Video generator instance with mocked dependencies"""
    db, _ = database_instance
    return VideoGenerator(db)

@pytest.fixture
def timelapse_worker_instance(database_instance):
    """TimelapseWorker instance with mocked dependencies"""
    db, _ = database_instance
    
    with patch('main.Database') as mock_db_class:
        mock_db_class.return_value = db
        from main import TimelapseWorker
        worker = TimelapseWorker()
        worker.db = db
        yield worker
