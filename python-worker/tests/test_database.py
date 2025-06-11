import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date
import psycopg

class TestDatabase:
    """Test database operations"""

    def test_get_active_cameras(self, database_instance, sample_camera_data):
        """Test fetching active cameras"""
        db, mock_cursor = database_instance
        mock_cursor.fetchall.return_value = [sample_camera_data]
        
        cameras = db.get_active_cameras()
        
        assert len(cameras) == 1
        assert cameras[0]['name'] == 'Test Camera'
        mock_cursor.execute.assert_called_once()

    def test_update_camera_health_success(self, database_instance):
        """Test updating camera health after successful capture"""
        db, mock_cursor = database_instance
        
        db.update_camera_health(1, success=True)
        
        # Verify the correct SQL was called
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args[0]
        assert "UPDATE cameras" in call_args[0]
        assert "health_status = 'online'" in call_args[0]

    def test_update_camera_health_failure(self, database_instance):
        """Test updating camera health after failed capture"""
        db, mock_cursor = database_instance
        
        db.update_camera_health(1, success=False)
        
        # Should have made multiple SQL calls for failure case
        assert mock_cursor.execute.call_count >= 2
        # Check for the failure increment query
        call_args_list = [call[0][0] for call in mock_cursor.execute.call_args_list]
        assert any("consecutive_failures = consecutive_failures + 1" in query for query in call_args_list)

    def test_create_or_update_timelapse_new(self, database_instance):
        """Test creating a new timelapse"""
        db, mock_cursor = database_instance
        mock_cursor.fetchone.side_effect = [None, {'id': 1}]  # No existing, then return new ID
        
        timelapse_id = db.create_or_update_timelapse(1, 'running')
        
        assert timelapse_id == 1
        assert mock_cursor.execute.call_count >= 2  # SELECT + INSERT

    def test_create_or_update_timelapse_existing(self, database_instance):
        """Test updating existing timelapse"""
        db, mock_cursor = database_instance
        mock_cursor.fetchone.return_value = {'id': 1, 'status': 'stopped'}
        
        timelapse_id = db.create_or_update_timelapse(1, 'running')
        
        assert timelapse_id == 1
        # Should call UPDATE, not INSERT
        update_calls = [call for call in mock_cursor.execute.call_args_list 
                       if call[0][0].strip().startswith('UPDATE')]
        assert len(update_calls) >= 1

    def test_record_captured_image(self, database_instance):
        """Test recording a captured image"""
        db, mock_cursor = database_instance
        mock_cursor.fetchone.side_effect = [
            {'start_date': date.today()},  # Timelapse info
            {'id': 1}  # Image ID
        ]
        
        image_id = db.record_captured_image(
            camera_id=1,
            timelapse_id=1,
            file_path='/test/image.jpg',
            file_size=1024000
        )
        
        assert image_id == 1
        # Should have called INSERT for image and UPDATE for timelapse
        assert mock_cursor.execute.call_count >= 3

    def test_get_timelapse_images(self, database_instance, sample_image_data):
        """Test fetching images for a timelapse"""
        db, mock_cursor = database_instance
        mock_cursor.fetchall.return_value = [sample_image_data]
        
        images = db.get_timelapse_images(1)
        
        assert len(images) == 1
        assert images[0]['day_number'] == 1
        mock_cursor.execute.assert_called_once()

    def test_get_timelapse_images_with_day_range(self, database_instance, sample_image_data):
        """Test fetching images with day range filter"""
        db, mock_cursor = database_instance
        mock_cursor.fetchall.return_value = [sample_image_data]
        
        images = db.get_timelapse_images(1, day_start=1, day_end=10)
        
        assert len(images) == 1
        # Should include day range in query
        call_args = mock_cursor.execute.call_args[0]
        assert "day_number >=" in call_args[0]
        assert "day_number <=" in call_args[0]

    def test_get_timelapse_day_range(self, database_instance):
        """Test getting day range statistics"""
        db, mock_cursor = database_instance
        mock_cursor.fetchone.return_value = {
            'min_day': 1,
            'max_day': 30,
            'total_images': 150,
            'days_with_images': 25
        }
        
        stats = db.get_timelapse_day_range(1)
        
        assert stats['min_day'] == 1
        assert stats['max_day'] == 30
        assert stats['total_images'] == 150
        assert stats['days_with_images'] == 25

    def test_get_offline_cameras(self, database_instance, sample_camera_data):
        """Test fetching offline cameras"""
        db, mock_cursor = database_instance
        offline_camera = sample_camera_data.copy()
        offline_camera['health_status'] = 'offline'
        mock_cursor.fetchall.return_value = [offline_camera]
        
        cameras = db.get_offline_cameras()
        
        assert len(cameras) == 1
        assert cameras[0]['health_status'] == 'offline'
        # Should filter for offline status
        call_args = mock_cursor.execute.call_args[0]
        assert "health_status = 'offline'" in call_args[0]

    def test_database_connection_error(self, mock_db_config):
        """Test handling database connection errors"""
        with patch('database.psycopg.connect') as mock_connect, \
             patch.dict('os.environ', {'DATABASE_URL': 'postgresql://test:test@localhost/test'}):
            from database import Database
            mock_connect.side_effect = psycopg.Error("Connection failed")
            
            db = Database()
            # Should handle the error gracefully
            cameras = db.get_active_cameras()
            assert cameras == []

    def test_get_active_timelapse_for_camera(self, database_instance, sample_timelapse_data):
        """Test getting active timelapse for a camera"""
        db, mock_cursor = database_instance
        mock_cursor.fetchone.return_value = sample_timelapse_data
        
        timelapse = db.get_active_timelapse_for_camera(1)
        
        assert timelapse['status'] == 'running'
        # Should filter for running status
        call_args = mock_cursor.execute.call_args[0]
        assert "status = 'running'" in call_args[0]
        assert "camera_id = %s" in call_args[0]
