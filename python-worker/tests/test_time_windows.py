import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, time
import sys
import os

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTimeWindows:
    """Test time window functionality for daylight-only captures"""

    @pytest.fixture
    def sample_camera_with_time_window(self):
        """Sample camera with time window enabled"""
        return {
            'id': 1,
            'name': 'Test Camera',
            'rtsp_url': 'rtsp://192.168.1.100:554/stream',
            'status': 'active',
            'use_time_window': True,
            'time_window_start': '06:00',
            'time_window_end': '18:00'
        }

    @pytest.fixture
    def sample_camera_without_time_window(self):
        """Sample camera without time window (always capture)"""
        return {
            'id': 2,
            'name': 'Night Camera',
            'rtsp_url': 'rtsp://192.168.1.101:554/stream',
            'status': 'active',
            'use_time_window': False,
            'time_window_start': None,
            'time_window_end': None
        }

    def test_is_within_time_window_during_day(self, sample_camera_with_time_window, timelapse_worker_instance):
        """Test camera should capture during day hours"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to 12:00 PM (noon)
            mock_datetime.now.return_value = datetime(2025, 6, 10, 12, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_with_time_window)
            
            assert result is True

    def test_is_within_time_window_before_start(self, sample_camera_with_time_window, timelapse_worker_instance):
        """Test camera should not capture before start time"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to 5:00 AM (before 6:00 AM start)
            mock_datetime.now.return_value = datetime(2025, 6, 10, 5, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_with_time_window)
            
            assert result is False

    def test_is_within_time_window_after_end(self, sample_camera_with_time_window, timelapse_worker_instance):
        """Test camera should not capture after end time"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to 8:00 PM (after 6:00 PM end)
            mock_datetime.now.return_value = datetime(2025, 6, 10, 20, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_with_time_window)
            
            assert result is False

    def test_is_within_time_window_at_exact_start(self, sample_camera_with_time_window, timelapse_worker_instance):
        """Test camera should capture at exact start time"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to exactly 6:00 AM
            mock_datetime.now.return_value = datetime(2025, 6, 10, 6, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_with_time_window)
            
            assert result is True

    def test_is_within_time_window_at_exact_end(self, sample_camera_with_time_window, timelapse_worker_instance):
        """Test camera should not capture at exact end time"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to exactly 6:00 PM
            mock_datetime.now.return_value = datetime(2025, 6, 10, 18, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_with_time_window)
            
            assert result is False

    def test_is_within_time_window_disabled(self, sample_camera_without_time_window, timelapse_worker_instance):
        """Test camera without time window should always capture"""
        with patch('main.datetime') as mock_datetime:
            # Mock current time to middle of night
            mock_datetime.now.return_value = datetime(2025, 6, 10, 2, 0, 0)
            
            worker = timelapse_worker_instance
            result = worker.is_within_time_window(sample_camera_without_time_window)
            
            assert result is True

    def test_overnight_time_window(self, timelapse_worker_instance):
        """Test time window that spans midnight (22:00 - 06:00)"""
        camera = {
            'id': 3,
            'name': 'Security Camera',
            'use_time_window': True,
            'time_window_start': '22:00',
            'time_window_end': '06:00'
        }
        
        worker = timelapse_worker_instance
        
        # Test during night hours (should capture)
        with patch('main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 10, 23, 0, 0)  # 11 PM
            assert worker.is_within_time_window(camera) is True
            
            mock_datetime.now.return_value = datetime(2025, 6, 10, 3, 0, 0)   # 3 AM
            assert worker.is_within_time_window(camera) is True
        
        # Test during day hours (should not capture)
        with patch('main.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 6, 10, 12, 0, 0)  # Noon
            assert worker.is_within_time_window(camera) is False

    def test_invalid_time_format_handling(self, timelapse_worker_instance):
        """Test handling of invalid time format in camera settings"""
        camera_with_bad_time = {
            'id': 4,
            'name': 'Bad Time Camera',
            'use_time_window': True,
            'time_window_start': 'invalid',
            'time_window_end': '18:00'
        }
        
        worker = timelapse_worker_instance
        # Should default to allowing capture when time parsing fails
        result = worker.is_within_time_window(camera_with_bad_time)
        assert result is True

    def test_missing_time_window_fields(self, timelapse_worker_instance):
        """Test handling of missing time window fields"""
        camera_missing_fields = {
            'id': 5,
            'name': 'Incomplete Camera',
            'use_time_window': True
            # Missing time_window_start and time_window_end
        }
        
        worker = timelapse_worker_instance
        result = worker.is_within_time_window(camera_missing_fields)
        # Should default to allowing capture when fields are missing
        assert result is True

    @patch('main.TimelapseWorker.capture_from_camera')
    @patch('main.TimelapseWorker.get_active_timelapse_for_camera')
    def test_capture_images_respects_time_window(self, mock_get_timelapse, mock_capture, timelapse_worker_instance):
        """Test that capture_images method respects time windows"""
        worker = timelapse_worker_instance
        mock_get_timelapse.return_value = {'id': 1, 'status': 'running'}
        
        # Camera with time window that's currently outside hours
        camera = {
            'id': 1,
            'name': 'Test Camera',
            'use_time_window': True,
            'time_window_start': '06:00',
            'time_window_end': '18:00'
        }
        
        with patch('main.datetime') as mock_datetime:
            # Mock time to 8 PM (outside window)
            mock_datetime.now.return_value = datetime(2025, 6, 10, 20, 0, 0)
            
            worker.capture_images([camera])
            
            # Should not call capture_from_camera due to time window
            mock_capture.assert_not_called()

    @patch('main.TimelapseWorker.capture_from_camera')
    @patch('main.TimelapseWorker.get_active_timelapse_for_camera')
    def test_capture_images_allows_within_time_window(self, mock_get_timelapse, mock_capture, timelapse_worker_instance):
        """Test that capture proceeds when within time window"""
        worker = timelapse_worker_instance
        mock_get_timelapse.return_value = {'id': 1, 'status': 'running'}
        mock_capture.return_value = True
        
        # Camera with time window that's currently active
        camera = {
            'id': 1,
            'name': 'Test Camera',
            'use_time_window': True,
            'time_window_start': '06:00',
            'time_window_end': '18:00'
        }
        
        with patch('main.datetime') as mock_datetime:
            # Mock time to 12 PM (inside window)
            mock_datetime.now.return_value = datetime(2025, 6, 10, 12, 0, 0)
            
            worker.capture_images([camera])
            
            # Should call capture_from_camera
            mock_capture.assert_called_once()
