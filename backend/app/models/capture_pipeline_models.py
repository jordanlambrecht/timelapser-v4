# backend/app/models/capture_pipeline_models.py
"""
Capture Pipeline Domain Models

Pydantic models for capture pipeline workflow orchestration, including
workflow contexts, step results, and coordination data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorkflowStepStatus(str, Enum):
    """Status values for individual workflow steps."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class CaptureWorkflowResult(str, Enum):
    """Overall result status for capture workflow."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    RETRY_NEEDED = "retry_needed"


class WorkflowStepResult(BaseModel):
    """Result from individual workflow step execution."""

    step_name: str = Field(..., description="Name of the workflow step")
    status: WorkflowStepStatus = Field(..., description="Step execution status")
    start_time: datetime = Field(..., description="Step start timestamp")
    end_time: Optional[datetime] = Field(None, description="Step completion timestamp")
    duration_seconds: Optional[float] = Field(
        None, description="Step execution duration"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Step-specific result data"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if step failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional step metadata"
    )


class CapturePipelineContext(BaseModel):
    """Context for capture pipeline workflow execution."""

    camera_id: int = Field(..., description="ID of camera to capture from")
    timelapse_id: int = Field(..., description="ID of timelapse being captured for")
    workflow_id: str = Field(
        ..., description="Unique identifier for this workflow execution"
    )
    initiated_by: str = Field(
        ..., description="Source that initiated the capture (scheduler, manual, etc.)"
    )
    initiated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Workflow initiation timestamp"
    )
    context_data: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context data"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted")
    max_retries: int = Field(default=1, description="Maximum retries allowed")


class RTSPCaptureResult(BaseModel):
    """Result from RTSP frame capture operation."""

    success: bool = Field(..., description="Whether capture was successful")
    file_path: Optional[str] = Field(None, description="Path to captured image file")
    file_size_bytes: Optional[int] = Field(
        None, description="Size of captured file in bytes"
    )
    capture_timestamp: Optional[datetime] = Field(
        None, description="Actual capture timestamp"
    )
    camera_id: int = Field(..., description="ID of camera that was captured from")
    resolution: Optional[str] = Field(
        None, description="Image resolution (e.g., '1920x1080')"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if capture failed"
    )


class CorruptionAssessmentResult(BaseModel):
    """Result from corruption detection assessment."""

    overall_score: float = Field(..., description="Overall corruption score (0-100)")
    fast_detection_score: Optional[float] = Field(
        None, description="Fast detection score"
    )
    heavy_detection_score: Optional[float] = Field(
        None, description="Heavy detection score if enabled"
    )
    is_acceptable: bool = Field(..., description="Whether image quality is acceptable")
    assessment_method: str = Field(
        ..., description="Method used for assessment (fast_only, combined)"
    )
    detection_duration_ms: float = Field(
        ..., description="Time taken for corruption detection"
    )
    retry_recommended: bool = Field(
        default=False, description="Whether retry is recommended"
    )


class ImageRecordResult(BaseModel):
    """Result from image record creation and enrichment."""

    image_id: int = Field(..., description="Database ID of created image record")
    record_created: bool = Field(
        ..., description="Whether database record was created successfully"
    )
    weather_data_added: bool = Field(
        default=False, description="Whether weather data was included"
    )
    metadata_enriched: bool = Field(
        default=False, description="Whether additional metadata was added"
    )
    timelapse_updated: bool = Field(
        default=False, description="Whether timelapse counts were updated"
    )


class OverlayGenerationResult(BaseModel):
    """Result from overlay generation process."""

    overlay_generated: bool = Field(..., description="Whether overlay was generated")
    overlay_path: Optional[str] = Field(
        None, description="Path to generated overlay file"
    )
    overlay_status: str = Field(
        ..., description="Status of overlay (generated, disabled, fallback)"
    )
    generation_duration_ms: Optional[float] = Field(
        None, description="Time taken for overlay generation"
    )
    fallback_used: bool = Field(
        default=False, description="Whether fallback overlay was used"
    )


class JobCoordinationResult(BaseModel):
    """Result from background job coordination."""

    thumbnail_job_queued: bool = Field(
        default=False, description="Whether thumbnail job was queued"
    )
    video_automation_triggered: bool = Field(
        default=False, description="Whether video automation was triggered"
    )
    jobs_queued_count: int = Field(default=0, description="Total number of jobs queued")
    job_queue_errors: List[str] = Field(
        default_factory=list, description="Any errors during job queueing"
    )


class CapturePipelineResult(BaseModel):
    """Complete result from capture pipeline workflow execution."""

    overall_result: CaptureWorkflowResult = Field(
        ..., description="Overall workflow result"
    )
    context: CapturePipelineContext = Field(
        ..., description="Original workflow context"
    )
    step_results: List[WorkflowStepResult] = Field(
        default_factory=list, description="Results from individual steps"
    )

    # Aggregated results from key steps
    rtsp_result: Optional[RTSPCaptureResult] = Field(
        None, description="RTSP capture result"
    )
    corruption_result: Optional[CorruptionAssessmentResult] = Field(
        None, description="Corruption assessment result"
    )
    image_result: Optional[ImageRecordResult] = Field(
        None, description="Image record creation result"
    )
    overlay_result: Optional[OverlayGenerationResult] = Field(
        None, description="Overlay generation result"
    )
    job_result: Optional[JobCoordinationResult] = Field(
        None, description="Job coordination result"
    )

    # Workflow metadata
    total_duration_seconds: Optional[float] = Field(
        None, description="Total workflow execution time"
    )
    completed_at: Optional[datetime] = Field(
        None, description="Workflow completion timestamp"
    )
    error_summary: Optional[str] = Field(
        None, description="Summary of any errors encountered"
    )

    @property
    def was_successful(self) -> bool:
        """Check if the overall workflow was successful."""
        return self.overall_result == CaptureWorkflowResult.SUCCESS

    @property
    def requires_retry(self) -> bool:
        """Check if the workflow should be retried."""
        return self.overall_result == CaptureWorkflowResult.RETRY_NEEDED

    def get_step_result(self, step_name: str) -> Optional[WorkflowStepResult]:
        """Get result for a specific workflow step."""
        for step_result in self.step_results:
            if step_result.step_name == step_name:
                return step_result
        return None
