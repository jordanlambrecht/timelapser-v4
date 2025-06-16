from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, cast
from loguru import logger

from ..database import async_db

router = APIRouter()


@router.get("/")
async def get_dashboard_data():
    """Get aggregated dashboard data with all cameras, timelapses, and videos"""
    try:
        # Fetch all dashboard data in parallel
        cameras, timelapses, videos = await async_db.get_dashboard_data()

        # Transform the data to match the expected format
        dashboard_data = {
            "cameras": cameras,
            "timelapses": timelapses,
            "videos": videos,
            "timestamp": "2024-01-01T00:00:00Z",  # Add timestamp for cache busting
        }

        return dashboard_data

    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dashboard data")
