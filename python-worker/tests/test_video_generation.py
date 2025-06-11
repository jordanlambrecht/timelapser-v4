import pytest
from unittest.mock import patch, MagicMock, call
import tempfile
import os
import subprocess
from datetime import datetime

class TestVideoGeneration:
    """Test video generation with FFmpeg"""

    def test_basic_video_generation(self, video_generator_instance, mock_ffmpeg, temp_directory, mock_file_operations):
        """Test basic video generation from image directory"""
        # Setup mock images
        images_dir = temp_directory
        output_path = os.path.join(temp_directory, "test_video.mp4")
        
        with patch('video_generator.Path.exists') as mock_exists, \
             patch('video_generator.VideoGenerator.find_image_files') as mock_find:
            
            mock_exists.return_value = True
            mock_find.return_value = ['img_001.jpg', 'img_002.jpg', 'img_003.jpg']
            
            success, message = video_generator_instance.generate_video(
                images_directory=images_dir,
                output_path=output_path
            )
            
            assert success is True
            assert "successfully" in message.lower()
            mock_ffmpeg.assert_called_once()

    def test_video_generation_with_tracking(self, video_generator_instance, database_instance, mock_ffmpeg, temp_directory):
        """Test video generation with database tracking"""
        db, mock_cursor = database_instance
        
        # Mock database responses for create_video_record
        mock_cursor.fetchone.side_effect = [
            {'id': 1}  # Video ID from create_video_record
        ]
        
        with patch('video_generator.Path.exists') as mock_exists, \
             patch('video_generator.VideoGenerator.find_image_files') as mock_find, \
             patch('video_generator.VideoGenerator.get_image_date_range') as mock_date_range:
            
            mock_exists.return_value = True
            mock_find.return_value = ['capture_20250610_120000.jpg', 'capture_20250610_130000.jpg']
            mock_date_range.return_value = (datetime(2025, 6, 10).date(), datetime(2025, 6, 10).date())
            
            success, message, video_id = video_generator_instance.generate_video_with_tracking(
                camera_id=1,
                camera_name="Test Camera",
                images_directory=temp_directory,
                output_directory=temp_directory
            )
            
            assert success is True
            assert video_id == 1

    def test_no_images_found(self, video_generator_instance, temp_directory):
        """Test handling when no images are found"""
        with patch('video_generator.VideoGenerator.find_image_files') as mock_find:
            mock_find.return_value = []  # No images
            
            success, message = video_generator_instance.generate_video(
                images_directory=temp_directory,
                output_path=os.path.join(temp_directory, "test_video.mp4")
            )
            
            assert success is False
            assert "need at least 2 images" in message.lower()

    def test_ffmpeg_failure(self, video_generator_instance, mock_ffmpeg, temp_directory):
        """Test handling of FFmpeg execution failure"""
        mock_ffmpeg.side_effect = subprocess.CalledProcessError(1, 'ffmpeg')
        
        with patch('video_generator.Path.exists') as mock_exists, \
             patch('video_generator.VideoGenerator.find_image_files') as mock_find:
            
            mock_exists.return_value = True
            mock_find.return_value = ['img_001.jpg', 'img_002.jpg']
            
            success, message = video_generator_instance.generate_video(
                images_directory=temp_directory,
                output_path=os.path.join(temp_directory, "test_video.mp4")
            )
            
            assert success is False
            assert "error" in message.lower()

    def test_different_quality_settings(self, video_generator_instance, mock_ffmpeg, temp_directory):
        """Test video generation with different quality settings"""
        qualities = ['low', 'medium', 'high']
        
        with patch('video_generator.Path.exists') as mock_exists, \
             patch('video_generator.VideoGenerator.find_image_files') as mock_find:
            
            mock_exists.return_value = True
            mock_find.return_value = ['img_001.jpg', 'img_002.jpg']
            
            for quality in qualities:
                mock_ffmpeg.reset_mock()
                
                success, message = video_generator_instance.generate_video(
                    images_directory=temp_directory,
                    output_path=os.path.join(temp_directory, f"test_{quality}.mp4"),
                    quality=quality
                )
                
                assert success is True
                mock_ffmpeg.assert_called_once()
                
                # Check that quality affects FFmpeg parameters
                call_args = mock_ffmpeg.call_args[0][0]
                assert '-crf' in call_args

    def test_custom_framerate(self, video_generator_instance, mock_ffmpeg, temp_directory):
        """Test video generation with custom framerate"""
        with patch('video_generator.Path.exists') as mock_exists, \
             patch('video_generator.VideoGenerator.find_image_files') as mock_find:
            
            mock_exists.return_value = True
            mock_find.return_value = ['img_001.jpg', 'img_002.jpg']
            
            success, message = video_generator_instance.generate_video(
                images_directory=temp_directory,
                output_path=os.path.join(temp_directory, "test_30fps.mp4"),
                framerate=30
            )
            
            assert success is True
            # Check that framerate is included in FFmpeg command
            call_args = mock_ffmpeg.call_args[0][0]
            assert '-framerate' in call_args
            assert '30' in call_args

    def test_output_directory_creation(self, video_generator_instance, mock_ffmpeg, temp_directory):
        """Test that output directory is created if it doesn't exist"""
        nonexistent_dir = os.path.join(temp_directory, "nonexistent")
        output_path = os.path.join(nonexistent_dir, "test.mp4")
        
        with patch('video_generator.VideoGenerator.find_image_files') as mock_find, \
             patch('video_generator.Path.exists') as mock_exists:
            
            mock_find.return_value = ['img_001.jpg']
            mock_exists.return_value = True
            
            success, message = video_generator_instance.generate_video(
                images_directory=temp_directory,
                output_path=output_path
            )
            
            assert success is True

    def test_ffmpeg_availability_test(self, video_generator_instance):
        """Test FFmpeg availability testing"""
        with patch('video_generator.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ffmpeg version 4.4.0"
            
            success, message = video_generator_instance.test_ffmpeg_available()
            
            assert success is True
            assert "ffmpeg version" in message.lower()

    def test_ffmpeg_not_available(self, video_generator_instance):
        """Test handling when FFmpeg is not available"""
        with patch('video_generator.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            success, message = video_generator_instance.test_ffmpeg_available()
            
            assert success is False
            assert "not found" in message.lower()

    def test_find_image_files_regular_directory(self, video_generator_instance, temp_directory):
        """Test finding images in a regular directory"""
        from pathlib import Path
        
        # Create some test files
        test_files = ['img1.jpg', 'img2.jpeg', 'img3.png', 'not_image.txt']
        for filename in test_files:
            (Path(temp_directory) / filename).touch()
        
        with patch('video_generator.glob.glob') as mock_glob:
            mock_glob.return_value = [
                os.path.join(temp_directory, 'img1.jpg'),
                os.path.join(temp_directory, 'img2.jpeg'),
                os.path.join(temp_directory, 'img3.png')
            ]
            
            images = video_generator_instance.find_image_files(Path(temp_directory))
            
            assert len(images) == 3
            assert all('img' in img for img in images)

    def test_get_quality_settings(self, video_generator_instance):
        """Test quality settings retrieval"""
        low_settings = video_generator_instance.get_quality_settings('low')
        medium_settings = video_generator_instance.get_quality_settings('medium')
        high_settings = video_generator_instance.get_quality_settings('high')
        
        assert low_settings['crf'] > medium_settings['crf']
        assert medium_settings['crf'] > high_settings['crf']
        assert 'scale' in low_settings
        assert 'scale' in medium_settings
        assert high_settings['scale'] is None  # Keep original resolution

    def test_extract_date_from_filename(self, video_generator_instance):
        """Test date extraction from capture filenames"""
        from datetime import date
        
        # Valid filename
        result = video_generator_instance.extract_date_from_filename('capture_20250610_143022.jpg')
        assert result == date(2025, 6, 10)
        
        # Invalid filename
        result = video_generator_instance.extract_date_from_filename('invalid_filename.jpg')
        assert result is None
        
        # Another valid filename
        result = video_generator_instance.extract_date_from_filename('capture_20241225_120000.jpg')
        assert result == date(2024, 12, 25)

    def test_get_image_date_range(self, video_generator_instance):
        """Test getting date range from image filenames"""
        from datetime import date
        
        image_files = [
            'capture_20250610_120000.jpg',
            'capture_20250612_120000.jpg',
            'capture_20250615_120000.jpg'
        ]
        
        start_date, end_date = video_generator_instance.get_image_date_range(image_files)
        
        assert start_date == date(2025, 6, 10)
        assert end_date == date(2025, 6, 15)

    def test_video_generation_timeout(self, video_generator_instance, temp_directory):
        """Test video generation timeout handling"""
        with patch('video_generator.VideoGenerator.find_image_files') as mock_find, \
             patch('video_generator.subprocess.run') as mock_run:
            
            mock_find.return_value = ['img_001.jpg', 'img_002.jpg']
            mock_run.side_effect = subprocess.TimeoutExpired('ffmpeg', 300)
            
            success, message = video_generator_instance.generate_video(
                images_directory=temp_directory,
                output_path=os.path.join(temp_directory, "test.mp4")
            )
            
            assert success is False
            assert "timed out" in message.lower()
