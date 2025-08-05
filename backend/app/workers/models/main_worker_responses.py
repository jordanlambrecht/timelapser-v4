"""
Typed response models for main worker (ecosystem orchestrator) operations.

These models provide type-safe access to worker ecosystem status and health monitoring,
following the Service Layer Boundary Pattern for consistent worker architecture.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from ...models.health_model import HealthStatus
from ...enums import WorkerType
from ...utils.time_utils import utc_now


class WorkerHealthStatus(BaseModel):
    """Individual worker health status within the ecosystem."""

    worker_name: str
    worker_type: WorkerType
    status: HealthStatus
    running: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ServiceHealthStatus(BaseModel):
    """Individual service health status within the ecosystem."""

    service_name: str
    status: HealthStatus
    available: bool
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class EcosystemStats(BaseModel):
    """Statistics about the worker ecosystem."""

    total_workers: int
    healthy_workers: int
    total_services: int
    healthy_services: int
    factory_created: bool
    running: bool
    uptime_seconds: Optional[float] = None


class WorkerEcosystemStatus(BaseModel):
    """Comprehensive worker ecosystem health and status information."""

    overall_status: HealthStatus
    timestamp: str
    ecosystem_status: HealthStatus
    error_count: int = 0

    # Detailed breakdowns
    workers: Dict[str, WorkerHealthStatus] = Field(default_factory=dict)
    services: Dict[str, ServiceHealthStatus] = Field(default_factory=dict)
    ecosystem_stats: EcosystemStats

    # Error tracking
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Check if the entire ecosystem is healthy."""
        return (
            self.overall_status == HealthStatus.HEALTHY
            and self.error_count == 0
            and all(
                worker.status == HealthStatus.HEALTHY
                for worker in self.workers.values()
            )
            and all(
                service.status == HealthStatus.HEALTHY
                for service in self.services.values()
            )
        )

    @property
    def is_degraded(self) -> bool:
        """Check if the ecosystem is in a degraded state."""
        return (
            self.overall_status == HealthStatus.DEGRADED
            or (0 < self.error_count <= EcosystemThresholds.MAX_DEGRADED_ERRORS)
            or any(
                worker.status == HealthStatus.DEGRADED
                for worker in self.workers.values()
            )
            or any(
                service.status == HealthStatus.DEGRADED
                for service in self.services.values()
            )
        )

    @property
    def healthy_worker_percentage(self) -> float:
        """Calculate percentage of workers that are healthy."""
        if not self.workers:
            return 100.0
        healthy_count = sum(
            1
            for worker in self.workers.values()
            if worker.status == HealthStatus.HEALTHY
        )
        return (healthy_count / len(self.workers)) * 100.0

    @property
    def healthy_service_percentage(self) -> float:
        """Calculate percentage of services that are healthy."""
        if not self.services:
            return 100.0
        healthy_count = sum(
            1
            for service in self.services.values()
            if service.status == HealthStatus.HEALTHY
        )
        return (healthy_count / len(self.services)) * 100.0

    def add_error(self, error_message: str) -> None:
        """Add an error to the status tracking."""
        self.errors.append(error_message)
        self.error_count += 1

        # Update overall status based on error count
        if self.error_count > EcosystemThresholds.MAX_DEGRADED_ERRORS:
            self.overall_status = HealthStatus.UNHEALTHY
        elif self.error_count > 0:
            self.overall_status = HealthStatus.DEGRADED

    def add_warning(self, warning_message: str) -> None:
        """Add a warning to the status tracking."""
        self.warnings.append(warning_message)


class MainWorkerStatus(BaseModel):
    """Status model for the main worker orchestrator."""

    worker_type: WorkerType = WorkerType.SYSTEM_WORKER  # Main worker is system-level
    running: bool
    ecosystem_healthy: bool
    total_workers_managed: int
    total_services_managed: int

    # Ecosystem status
    ecosystem: WorkerEcosystemStatus

    @property
    def is_healthy(self) -> bool:
        """Check if main worker is healthy."""
        return self.running and self.ecosystem_healthy and self.ecosystem.is_healthy

    @property
    def management_efficiency(self) -> float:
        """Calculate management efficiency based on healthy components."""
        if self.total_workers_managed == 0 and self.total_services_managed == 0:
            return 100.0

        total_components = self.total_workers_managed + self.total_services_managed
        healthy_workers = sum(
            1
            for worker in self.ecosystem.workers.values()
            if worker.status == HealthStatus.HEALTHY
        )
        healthy_services = sum(
            1
            for service in self.ecosystem.services.values()
            if service.status == HealthStatus.HEALTHY
        )
        healthy_components = healthy_workers + healthy_services

        return (healthy_components / total_components) * 100.0


# Structured Error Models for Worker Failures


class SeverityLevel(str, Enum):
    """Severity levels for ecosystem failures."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EcosystemThresholds:
    """Thresholds for ecosystem health evaluation."""

    MAX_DEGRADED_ERRORS = 3
    CRITICAL_AFFECTED_WORKERS = 5
    HIGH_AFFECTED_WORKERS = 3
    DEFAULT_MAX_RETRIES = 3


class WorkerFailureType(str, Enum):
    """Types of worker failures that can occur."""

    INITIALIZATION_FAILED = "initialization_failed"
    STARTUP_FAILED = "startup_failed"
    RUNTIME_ERROR = "runtime_error"
    HEALTH_CHECK_FAILED = "health_check_failed"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DEPENDENCY_MISSING = "dependency_missing"
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT = "timeout"
    SHUTDOWN_FAILED = "shutdown_failed"
    UNKNOWN = "unknown"


class WorkerFailureContext(BaseModel):
    """Context information about a worker failure."""

    worker_name: str
    worker_type: WorkerType
    failure_type: WorkerFailureType
    error_message: str
    stack_trace: Optional[str] = None

    # Timing information
    occurred_at: datetime
    operation_attempted: Optional[str] = None

    # Environment context
    dependencies_available: Dict[str, bool] = Field(default_factory=dict)
    configuration_valid: bool = True
    resource_constraints: Optional[Dict[str, Any]] = None

    # Recovery information
    recoverable: bool = False
    recovery_suggestions: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = EcosystemThresholds.DEFAULT_MAX_RETRIES


class EcosystemFailureEvent(BaseModel):
    """Structured model for ecosystem-level failure events."""

    event_id: str
    event_type: str = "ecosystem_failure"
    severity: SeverityLevel

    # Failure details
    overall_impact: HealthStatus
    affected_workers: List[str]
    affected_services: List[str]
    root_cause: Optional[str] = None

    # Worker-specific failures
    worker_failures: List[WorkerFailureContext] = Field(default_factory=list)

    # Recovery tracking
    recovery_initiated: bool = False
    recovery_strategy: Optional[str] = None
    estimated_recovery_time: Optional[int] = None  # seconds

    # Metrics
    total_downtime: Optional[int] = None  # seconds
    affected_operations: List[str] = Field(default_factory=list)

    def add_worker_failure(self, failure: WorkerFailureContext) -> None:
        """Add a worker failure to this ecosystem event."""
        self.worker_failures.append(failure)
        if failure.worker_name not in self.affected_workers:
            self.affected_workers.append(failure.worker_name)

    def calculate_severity(self) -> SeverityLevel:
        """Calculate severity based on affected components."""
        if len(self.affected_workers) >= EcosystemThresholds.CRITICAL_AFFECTED_WORKERS:
            return SeverityLevel.CRITICAL
        elif len(self.affected_workers) >= EcosystemThresholds.HIGH_AFFECTED_WORKERS:
            return SeverityLevel.HIGH
        elif len(self.affected_workers) >= 1:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    @property
    def is_critical(self) -> bool:
        """Check if this is a critical ecosystem failure."""
        return (
            self.severity == SeverityLevel.CRITICAL
            or self.overall_impact == HealthStatus.ERROR
            or len(self.affected_workers)
            >= EcosystemThresholds.CRITICAL_AFFECTED_WORKERS
        )


class MainWorkerError(BaseModel):
    """Structured error model for main worker failures."""

    error_id: str
    error_type: WorkerFailureType
    message: str
    timestamp: datetime

    # Context
    ecosystem_state: Optional[Dict[str, Any]] = None
    operation_context: Optional[str] = None

    # Impact assessment
    services_affected: List[str] = Field(default_factory=list)
    operations_blocked: List[str] = Field(default_factory=list)
    estimated_impact_duration: Optional[int] = None  # seconds

    # Recovery information
    automatic_recovery_possible: bool = False
    manual_intervention_required: bool = True
    recovery_steps: List[str] = Field(default_factory=list)

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        operation: str,
        error_id: str,
        ecosystem_state: Optional[Dict[str, Any]] = None,
    ) -> "MainWorkerError":
        """Create MainWorkerError from an exception."""
        return cls(
            error_id=error_id,
            error_type=WorkerFailureType.RUNTIME_ERROR,
            message=str(exception),
            timestamp=utc_now(),
            ecosystem_state=ecosystem_state,
            operation_context=operation,
            manual_intervention_required=True,
            recovery_steps=[
                "Check logs for detailed error information",
                "Verify all dependencies are available",
                "Restart the main worker if necessary",
                "Monitor ecosystem health after recovery",
            ],
        )
