#!/usr/bin/env python3
"""
Test script to verify image capture and database updates
Run this from the project root directory
"""

import sys
import os

# Add backend directory to path
backend_path = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_path)

# Change to backend directory so .env file is found
os.chdir(backend_path)

from app.database import sync_db
from rtsp_capture import RTSPCapture


def test_image_capture():
    print("🧪 Testing image capture and database updates...")

    # Initialize database
    sync_db.initialize()

    # Initialize capture with project data directory
    capture = RTSPCapture(base_data_dir="./data")

    # Get TestBullet camera info
    cameras = sync_db.get_running_timelapses()

    if not cameras:
        print("❌ No running timelapses found. Start a timelapse first!")
        return

    camera = cameras[0]  # Use first running camera
    camera_id = camera["id"]
    camera_name = camera["name"]
    rtsp_url = camera["rtsp_url"]
    timelapse_id = camera["timelapse_id"]

    print(f"📹 Testing capture from: {camera_name} (ID: {camera_id})")

    # Test capture
    success, message, filepath = capture.capture_image(
        camera_id=camera_id,
        camera_name=camera_name,
        rtsp_url=rtsp_url,
        database=sync_db,
        timelapse_id=timelapse_id,
    )

    if success:
        print(f"✅ Capture successful: {message}")

        # Check database for updated last_image_path
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_image_path FROM cameras WHERE id = %s", (camera_id,)
                )
                result = cur.fetchone()

                if result and result["last_image_path"]:
                    print(f"✅ Database updated: {result['last_image_path']}")
                    print(
                        f"🌐 Image should be available at: http://localhost:3000{result['last_image_path']}"
                    )
                else:
                    print("❌ Database not updated - last_image_path still null")
    else:
        print(f"❌ Capture failed: {message}")

    sync_db.close()


if __name__ == "__main__":
    test_image_capture()
