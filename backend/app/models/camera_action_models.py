# backend/app/models/camera_action_models.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from datetime import datetime

# Import constants for action types
from ..enums import TimelapseAction


class TimelapseActionRequest(BaseModel):
    """Unified request model for timelapse actions"""

    action: TimelapseAction = Field(..., description="Timelapse action to perform")
    timelapse_data: Optional[Dict[str, Any]] = Field(
        None, description="Optional timelapse configuration for create action"
    )

    model_config = ConfigDict(
        # Ensure timezone-aware datetime handling
        json_encoders={datetime: lambda v: v.isoformat() if v else None}
    )


class TimelapseActionResponse(BaseModel):
    """Unified response model for timelapse actions"""

    success: bool
    message: str
    action: str
    camera_id: int
    timelapse_id: Optional[int] = None
    timelapse_status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class CameraStatusResponse(BaseModel):
    """Comprehensive camera status response combining status, health, and connectivity"""

    camera_id: int
    status: Literal["active", "inactive"]
    health_status: Literal["online", "offline", "unknown"]

    # Connectivity information
    connectivity_status: Literal["connected", "disconnected", "testing", "error"]
    last_connectivity_test: Optional[datetime] = None
    connectivity_message: Optional[str] = None
    response_time_ms: Optional[float] = None

    # Health metrics
    last_capture_at: Optional[datetime] = None
    last_capture_success: Optional[bool] = None
    consecutive_failures: int = 0
    next_capture_at: Optional[datetime] = None

    # Current timelapse information
    active_timelapse_id: Optional[int] = None
    timelapse_status: Optional[Literal["running", "paused"]] = None

    # Corruption information
    corruption_score: int = Field(ge=0, le=100)
    is_flagged: bool = False
    consecutive_corruption_failures: int = 0

    # Timestamps
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
