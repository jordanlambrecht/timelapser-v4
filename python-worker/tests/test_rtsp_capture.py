import pytest
from unittest.mock import patch, MagicMock, call
import tempfile
import os
import cv2


class TestRTSPCapture:
    """Test RTSP camera capture functionality"""

    def test_successful_rtsp_connection_test(self, rtsp_capture_instance, mock_opencv):
        """Test successful RTSP connection test"""
        mock_cv2, mock_cap = mock_opencv

        # Mock successful frame read
        mock_frame = MagicMock()
        mock_frame.shape = [1080, 1920, 3]  # height, width, channels
        mock_cap.read.return_value = (True, mock_frame)

        success, message = rtsp_capture_instance.test_rtsp_connection(
            "rtsp://192.168.1.100:554/stream"
        )

        assert success is True
        assert "connection successful" in message.lower()
        assert "1920x1080" in message
        mock_cv2.VideoCapture.assert_called_once_with("rtsp://192.168.1.100:554/stream")

    def test_failed_rtsp_connection_test(self, rtsp_capture_instance, mock_opencv):
        """Test failed RTSP connection test"""
        mock_cv2, mock_cap = mock_opencv
        mock_cap.read.return_value = (False, None)  # Failed to read

        success, message = rtsp_capture_instance.test_rtsp_connection(
            "rtsp://invalid.url"
        )

        assert success is False
        assert "failed" in message.lower()

    def test_capture_image_success(
        self, rtsp_capture_instance, mock_opencv, temp_directory
    ):
        """Test successful image capture"""
        mock_cv2, mock_cap = mock_opencv

        # Mock successful frame read
        mock_frame = MagicMock()
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2.imwrite.return_value = True

        with patch("capture.Path.stat") as mock_stat, patch(
            "capture.datetime"
        ) as mock_datetime:
            mock_stat.return_value.st_size = 1024000  # 1MB
            mock_datetime.now.return_value.strftime.return_value = "20250610_120000"

            success, message, filepath = rtsp_capture_instance.capture_image(
                camera_id=1,
                camera_name="Test Camera",
                rtsp_url="rtsp://192.168.1.100:554/stream",
            )

            assert success is True
            assert "successfully captured" in message.lower()
            assert filepath is not None

    def test_capture_image_frame_read_failure(self, rtsp_capture_instance, mock_opencv):
        """Test capture failure when frame read fails"""
        mock_cv2, mock_cap = mock_opencv
        mock_cap.read.return_value = (False, None)  # Failed to read frame

        success, message, filepath = rtsp_capture_instance.capture_image(
            camera_id=1,
            camera_name="Test Camera",
            rtsp_url="rtsp://192.168.1.100:554/stream",
        )

        assert success is False
        assert "failed" in message.lower()
        assert filepath is None

    def test_capture_image_with_database_tracking(
        self, rtsp_capture_instance, mock_opencv, database_instance
    ):
        """Test image capture with database tracking"""
        mock_cv2, mock_cap = mock_opencv
        mock_frame = MagicMock()
        mock_cap.read.return_value = (True, mock_frame)
        mock_cv2.imwrite.return_value = True

        db, mock_cursor = database_instance
        mock_cursor.fetchone.return_value = {"id": 1}  # Mock image ID

        with patch("capture.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 1024000

            success, message, filepath = rtsp_capture_instance.capture_image(
                camera_id=1,
                camera_name="Test Camera",
                rtsp_url="rtsp://192.168.1.100:554/stream",
                database=db,
                timelapse_id=1,
            )

            assert success is True
            assert filepath is not None

    def test_capture_frame_from_stream_success(
        self, rtsp_capture_instance, mock_opencv
    ):
        """Test successful frame capture from stream"""
        mock_cv2, mock_cap = mock_opencv
        mock_frame = MagicMock()
        mock_cap.read.return_value = (True, mock_frame)

        frame = rtsp_capture_instance.capture_frame_from_stream(
            "rtsp://192.168.1.100:554/stream"
        )

        assert frame is not None
        mock_cv2.VideoCapture.assert_called_once()
        mock_cap.release.assert_called_once()

    def test_capture_frame_from_stream_connection_failure(
        self, rtsp_capture_instance, mock_opencv
    ):
        """Test frame capture when connection fails"""
        mock_cv2, mock_cap = mock_opencv
        mock_cap.isOpened.return_value = False

        frame = rtsp_capture_instance.capture_frame_from_stream("rtsp://invalid.url")

        assert frame is None
        mock_cap.release.assert_called_once()

    def test_retry_logic(self, rtsp_capture_instance, mock_opencv):
        """Test retry logic on capture failures"""
        mock_cv2, mock_cap = mock_opencv

        # First two attempts fail, third succeeds
        mock_cap.read.side_effect = [
            (False, None),  # First attempt fails
            (False, None),  # Second attempt fails
            (True, MagicMock()),  # Third attempt succeeds
        ]
        mock_cv2.imwrite.return_value = True

        with patch("capture.Path.stat") as mock_stat, patch(
            "capture.time.sleep"
        ):  # Speed up test
            mock_stat.return_value.st_size = 1024000

            success, message, filepath = rtsp_capture_instance.capture_image(
                camera_id=1,
                camera_name="Test Camera",
                rtsp_url="rtsp://192.168.1.100:554/stream",
            )

            assert success is True
            # Should have called VideoCapture 3 times (3 attempts)
            assert mock_cv2.VideoCapture.call_count == 3

    def test_all_retry_attempts_fail(self, rtsp_capture_instance, mock_opencv):
        """Test when all retry attempts fail"""
        mock_cv2, mock_cap = mock_opencv
        mock_cap.read.return_value = (False, None)  # Always fail

        with patch("capture.time.sleep"):  # Speed up test
            success, message, filepath = rtsp_capture_instance.capture_image(
                camera_id=1,
                camera_name="Test Camera",
                rtsp_url="rtsp://192.168.1.100:554/stream",
            )

            assert success is False
            assert "all" in message.lower() and "failed" in message.lower()
            assert filepath is None
            # Should have tried 3 times (default retry_attempts)
            assert mock_cv2.VideoCapture.call_count == 3

    def test_directory_creation(self, rtsp_capture_instance, temp_directory):
        """Test that camera directory is created properly"""
        with patch("capture.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "2025-06-10"

            # Use the temp directory base
            camera_dir = rtsp_capture_instance.ensure_camera_directory(1)

            expected_path = (
                rtsp_capture_instance.base_data_dir
                / "cameras"
                / "camera-1"
                / "images"
                / "2025-06-10"
            )
            assert str(camera_dir) == str(expected_path)
            assert camera_dir.exists()  # Should be created

    def test_filename_generation(self, rtsp_capture_instance):
        """Test filename generation with timestamp"""
        with patch("capture.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250610_120000"

            filename = rtsp_capture_instance.generate_filename(1)

            assert filename == "capture_20250610_120000.jpg"

    def test_save_frame_success(
        self, rtsp_capture_instance, mock_opencv, temp_directory
    ):
        """Test successful frame saving"""
        mock_cv2, _ = mock_opencv
        mock_cv2.imwrite.return_value = True
        mock_frame = MagicMock()

        from pathlib import Path

        filepath = Path(temp_directory) / "test.jpg"

        with patch("capture.Path.stat") as mock_stat:
            mock_stat.return_value.st_size = 1024000

            success = rtsp_capture_instance.save_frame(mock_frame, filepath)

            assert success is True
            mock_cv2.imwrite.assert_called_once()

    def test_save_frame_failure(
        self, rtsp_capture_instance, mock_opencv, temp_directory
    ):
        """Test frame saving failure"""
        mock_cv2, _ = mock_opencv
        mock_cv2.imwrite.return_value = False
        mock_frame = MagicMock()

        from pathlib import Path

        filepath = Path(temp_directory) / "test.jpg"

        success = rtsp_capture_instance.save_frame(mock_frame, filepath)

        assert success is False
