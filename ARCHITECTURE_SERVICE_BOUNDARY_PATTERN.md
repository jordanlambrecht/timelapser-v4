# Service Layer Boundary Pattern

## Overview

This document defines the **Service Layer Boundary Pattern** used throughout the
Timelapser v4 application. This pattern ensures consistent type conversion,
eliminates defensive coding, and maintains clean separation of concerns across
architectural layers.

## Architecture Principles

The Service Layer Boundary Pattern follows these core principles:

1. **Single Responsibility**: Each layer has one clear purpose
2. **Single Conversion Point**: Type conversion happens only at service
   boundaries
3. **Contract Guarantees**: Services provide guaranteed data contracts to
   consumers
4. **Type Safety**: Consumers receive typed objects for clean property access
5. **No Defensive Coding**: Eliminate `.get()` calls after service guarantees
6. **Explicit Error Handling**: Errors are part of typed contracts, not exceptions

## Pattern Definition

The Service Layer Boundary Pattern defines three distinct layers with specific
responsibilities:

### Database Layer

- **Returns**: `Dict[str, Any]` (raw database results)
- **Responsibility**: Data retrieval from PostgreSQL
- **Pattern**: Database → Dictionary (no conversions)

### Service Layer

- **Receives**: Dictionaries from database layer
- **Returns**: Typed objects at boundary (ProcessQueueResult, ProcessingStatus,
  etc.)
- **Internal Communication**: Services may return guaranteed dictionaries to other services for performance
- **Responsibility**: Single conversion point from dictionaries to typed objects
- **Pattern**: Dictionary → Typed Object (convert once at boundary)

### Consumer Layer (Workers/Controllers)

- **Receives**: Typed objects from service layer
- **Uses**: Clean property access without defensive coding
- **Responsibility**: Business logic using type-safe objects
- **Pattern**: Typed Object → Business Logic (no conversions)

## Implementation Pattern

```python
# 1. DATABASE LAYER - Always returns Dict[str, Any]
def get_video_job_queue_status(self) -> Dict[str, int]:
    query = "SELECT status, COUNT(*) FROM jobs GROUP BY status"
    results = cursor.fetchall()
    return {row["status"]: row["count"] for row in results}

# 2A. SERVICE LAYER - Contract guarantees for internal services
def get_queue_status(self) -> Dict[str, int]:
    """VideoJobService - Returns guaranteed dictionary with all required keys."""
    raw_status = self.video_ops.get_video_job_queue_status()

    # Ensure ALL keys exist (service contract guarantee)
    default_counts = {
        JobStatus.PENDING.value: 0,
        JobStatus.PROCESSING.value: 0,
        JobStatus.COMPLETED.value: 0,
        JobStatus.FAILED.value: 0,
    }
    default_counts.update(raw_status)
    return default_counts  # Guaranteed contract

# 2B. SERVICE LAYER - Typed object conversion at service boundary
def get_processing_status(self) -> ProcessingStatus:
    """VideoWorkflowService - Converts to typed objects at boundary."""
    queue_status_dict = self.job_service.get_queue_status()

    # Use enum.value for explicit string access
    queue_status = QueueStatus(
        pending=queue_status_dict[JobStatus.PENDING.value],      # Explicit string key
        processing=queue_status_dict[JobStatus.PROCESSING.value], # Clear intent
        completed=queue_status_dict[JobStatus.COMPLETED.value],   # No implicit behavior
        failed=queue_status_dict[JobStatus.FAILED.value],         # Type-safe + explicit
    )

    return ProcessingStatus(
        queue_status=queue_status,
        currently_processing=self.currently_processing,
        max_concurrent_jobs=self.max_concurrent_jobs,
        can_process_more=(self.currently_processing < self.max_concurrent_jobs),
    )

def process_queue_only(self) -> ProcessQueueResult:
    """VideoWorkflowService - Returns typed objects directly."""
    # Process jobs and build typed result at service boundary
    return ProcessQueueResult(
        success=True,
        jobs_processed=jobs_processed,
        currently_processing=self.currently_processing,
        errors=errors
    )

def execute_video_generation_direct(self, timelapse_id: int) -> VideoGenerationResult:
    """VideoWorkflowService - Returns typed objects for video operations."""
    # Execute video generation and return typed result
    return VideoGenerationResult(
        success=success,
        video_id=job_id,
        error=None if success else "Video generation failed"
    )

# 3. WORKER/CONSUMER LAYER - Uses typed objects with clean access
def get_status(self) -> Dict[str, Any]:
    """VideoWorker - Receives typed objects, no conversions needed."""
    processing_status = self.workflow_service.get_processing_status()

    return {
        "active_generations": processing_status.currently_processing,
        "pending_generations": processing_status.queue_status.pending,  # Clean access
        "completed_today": processing_status.queue_status.completed,
        "can_process_more": processing_status.can_process_more,
    }

async def process_pending_jobs(self) -> None:
    """VideoWorker - Receives typed objects directly from service."""
    result = await self.run_in_executor(
        self.workflow_service.process_queue_only  # Returns ProcessQueueResult
    )

    # Clean typed object access - no .get() calls needed
    if result.success and result.jobs_processed > 0:
        logger.info(f"Processed {result.jobs_processed} jobs")
```

### ❌ Anti-Patterns to Avoid

**Service Layer Returning Raw Dictionaries**

```python
# ❌ AVOID: Service returning raw dictionaries
def process_queue_only(self) -> Dict[str, Any]:
    return {"success": True, "jobs_processed": 5}
```

**Worker Layer Doing Conversions**

```python
# ❌ AVOID: Workers converting dictionaries to objects
async def process_pending_jobs(self) -> None:
    result_dict = await self.run_in_executor(...)
    result = ProcessQueueResult(**result_dict)  # Wrong layer!
```

**Multiple Conversions Across Layers**

```python
# ❌ AVOID: Converting back and forth between types
def worker_method(self):
    raw_dict = database_service.get_data()      # Dict
    typed_obj = SomeObject(**raw_dict)          # Convert to object
    back_to_dict = typed_obj.__dict__           # Convert back to dict
    final_obj = AnotherObject(**back_to_dict)   # Convert again
```

## Layer Responsibilities

## Layer Responsibilities

### Database Layer

- **Returns**: `Dict[str, Any]` (raw PostgreSQL results via psycopg)
- **Responsibility**: Data retrieval from database
- **Pattern**: Database → Dictionary (no conversions)
- **Example**: `get_video_job_queue_status()` returns
  `{"pending": 5, "processing": 2}`

### Service Layer

- **Receives**: Dictionaries from database layer
- **Returns**: Typed objects at boundary (ProcessQueueResult,
  VideoGenerationResult, ProcessingStatus)
- **Internal Contracts**: Services may return guaranteed dictionaries to other
  services for performance (avoiding unnecessary object creation)
- **Responsibility**: Single conversion point from dictionaries to typed objects
- **Pattern**: Dictionary → Typed Object (convert once at boundary)
- **Example**: `get_processing_status()` converts dict to `ProcessingStatus`
  object

### Consumer Layer (Workers/Controllers)

- **Receives**: Typed objects from service layer
- **Uses**: Clean property access without defensive `.get()` calls
- **Responsibility**: Business logic using type-safe objects
- **Pattern**: Typed Object → Business Logic (no conversions)
- **Example**: `result.success` and `result.jobs_processed` (direct property
  access)

### Router Layer (HTTP/API Interface)

- **Location**: `backend/app/routers/`
- **Receives**: Typed objects from service layer
- **Returns**: JSON responses via FastAPI response models
- **Responsibility**: HTTP request/response handling and API contract
  enforcement
- **Pattern**: Typed Object → HTTP Response (via Pydantic serialization)
- **Example**: `return ResponseFormatter.success(processing_status)` where
  `processing_status` is a typed object

## Practical Examples

### Example 1: VideoJobService (Service Layer Contract)

```python
def get_queue_status(self) -> Dict[str, int]:
    """Returns guaranteed dictionary with all required keys."""
    raw_status = self.video_ops.get_video_job_queue_status()

    # Service layer responsibility: guarantee all keys exist
    default_counts = {
        JobStatus.PENDING.value: 0,
        JobStatus.PROCESSING.value: 0,
        JobStatus.COMPLETED.value: 0,
        JobStatus.FAILED.value: 0,
    }
    default_counts.update(raw_status)
    return default_counts  # Guaranteed contract
```

### Example 2: VideoWorkflowService (Service Layer Conversion)

```python
def get_processing_status(self) -> ProcessingStatus:
    """Converts to typed objects at service boundary."""
    queue_status_dict = self.job_service.get_queue_status()

    # Convert guaranteed dictionary to typed object using enum values
    queue_status = QueueStatus(
        pending=queue_status_dict[JobStatus.PENDING.value],
        processing=queue_status_dict[JobStatus.PROCESSING.value],
        completed=queue_status_dict[JobStatus.COMPLETED.value],
        failed=queue_status_dict[JobStatus.FAILED.value],
    )

    return ProcessingStatus(
        queue_status=queue_status,
        currently_processing=self.currently_processing,
        max_concurrent_jobs=self.max_concurrent_jobs,
        can_process_more=(self.currently_processing < self.max_concurrent_jobs),
    )

def process_queue_only(self) -> ProcessQueueResult:
    """Returns typed objects directly at service boundary."""
    # Process jobs and build typed result
    return ProcessQueueResult(
        success=True,
        jobs_processed=jobs_processed,
        currently_processing=self.currently_processing,
        errors=errors
    )
```

### Example 3: VideoWorker (Consumer Layer Usage)

```python
def get_status(self) -> Dict[str, Any]:
    """Receives typed objects, no conversions needed."""
    processing_status = self.workflow_service.get_processing_status()

    # Clean access to typed object properties
    return {
        "pending_generations": processing_status.queue_status.pending,
        "active_generations": processing_status.currently_processing,
        "can_process_more": processing_status.can_process_more,
    }

async def process_pending_jobs(self) -> None:
    """Receives typed objects directly from service."""
    result = await self.run_in_executor(
        self.workflow_service.process_queue_only  # Returns ProcessQueueResult
    )

    # Clean typed object access - no .get() calls needed
    if result.success and result.jobs_processed > 0:
        logger.info(f"Processed {result.jobs_processed} jobs")
```

## Service-to-Service Communication

When services call other services, there are two acceptable patterns:

### Pattern 1: Guaranteed Dictionary Contracts (Performance-Optimized)

```python
# VideoJobService provides guaranteed dictionary to other services
def get_queue_status(self) -> Dict[str, int]:
    """Returns guaranteed dictionary with ALL JobStatus keys."""
    raw_status = self.video_ops.get_video_job_queue_status()
    
    # Guarantee all keys exist - this is the contract
    default_counts = {
        JobStatus.PENDING.value: 0,
        JobStatus.PROCESSING.value: 0,
        JobStatus.COMPLETED.value: 0,
        JobStatus.FAILED.value: 0,
    }
    default_counts.update(raw_status)
    return default_counts  # Other services can rely on all keys existing
```

### Pattern 2: Typed Object Returns (Maximum Type Safety)

```python
# Alternative: Service returns typed object
def get_queue_status(self) -> QueueStatus:
    """Returns typed object for maximum safety."""
    raw_status = self.video_ops.get_video_job_queue_status()
    
    return QueueStatus(
        pending=raw_status.get(JobStatus.PENDING.value, 0),
        processing=raw_status.get(JobStatus.PROCESSING.value, 0),
        completed=raw_status.get(JobStatus.COMPLETED.value, 0),
        failed=raw_status.get(JobStatus.FAILED.value, 0),
    )
```

### When to Use Each Pattern

- **Guaranteed Dictionaries**: Use when performance is critical and the consuming service will transform to its own typed object anyway
- **Typed Objects**: Use when the object will be passed through multiple layers or directly to consumers

Both patterns are acceptable as long as:
1. The contract is clearly documented
2. Dictionary contracts guarantee all required keys
3. Conversion to typed objects happens before reaching consumers

## Key Implementation Guidelines

1. **Single Conversion**: Convert only once at service boundary
2. **Contract Guarantees**: Services provide guaranteed data contracts to
   consumers
3. **No Defensive Coding**: After service guarantees, no `.get()` calls needed
4. **Clean Boundaries**: Each layer has single responsibility
5. **Type Safety**: Consumers get typed objects for business logic
6. **Explicit String Access**: Use `JobStatus.PENDING.value` for clarity

## Type-Safe Key Access

### Recommended Pattern

```python
from app.enums import JobStatus

# Service layer - use enum.value for explicit string access
queue_status = QueueStatus(
    pending=queue_status_dict[JobStatus.PENDING.value],      # ✅ Explicit string
    processing=queue_status_dict[JobStatus.PROCESSING.value], # ✅ Clear intent
    completed=queue_status_dict[JobStatus.COMPLETED.value],   # ✅ No ambiguity
    failed=queue_status_dict[JobStatus.FAILED.value],         # ✅ Type-safe
)
```

### Benefits

- **IDE Autocomplete**: `JobStatus.` shows all available options
- **Typo Prevention**: Compiler catches `JobStatus.PROCESING` (missing 'S')
- **Refactor Safety**: Changing enum value updates all usages
- **Type Validation**: Invalid enum access fails at import time
- **Documentation**: Enum values are self-documenting

### Why Use .value?

Using `.value` makes the string conversion explicit:

```python
# ❌ Implicit - relies on Python's enum __str__ behavior
queue_status_dict[JobStatus.PENDING]        # Works, but implicit

# ✅ Explicit - clear that we're using the string value
queue_status_dict[JobStatus.PENDING.value]  # Clear intent
```

## Error Handling Pattern

### Service Layer Error Handling

Services should return typed results that include error information, not throw exceptions:

```python
@dataclass
class VideoGenerationResult:
    """Result of video generation operation."""
    success: bool
    video_id: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "validation", "processing", "storage"

def execute_video_generation_direct(self, timelapse_id: int) -> VideoGenerationResult:
    """Returns typed result with error information."""
    try:
        # Validate input
        if not self._validate_timelapse(timelapse_id):
            return VideoGenerationResult(
                success=False,
                error="Invalid timelapse ID",
                error_type="validation"
            )
        
        # Process video
        job_id = self._create_video_job(timelapse_id)
        return VideoGenerationResult(
            success=True,
            video_id=job_id
        )
        
    except StorageError as e:
        # Convert exceptions to typed results
        return VideoGenerationResult(
            success=False,
            error=str(e),
            error_type="storage"
        )
```

### Consumer Layer Error Handling

Consumers check typed results for errors:

```python
async def generate_video(self, timelapse_id: int) -> None:
    """Worker handles errors from typed results."""
    result = await self.run_in_executor(
        self.workflow_service.execute_video_generation_direct,
        timelapse_id
    )
    
    # Clean error handling with typed results
    if not result.success:
        if result.error_type == "validation":
            logger.warning(f"Validation failed: {result.error}")
        else:
            logger.error(f"Video generation failed: {result.error}")
        return
    
    logger.info(f"Video {result.video_id} created successfully")
```

### Error Flow Through Layers

```
Database Error → Service catches → Returns typed error result → Consumer handles
```

This pattern ensures:
- Errors are part of the API contract
- No unexpected exceptions bubble up
- Consumers can handle different error types appropriately
- Type safety is maintained even in error cases

## Architecture Flow

```
Database Layer    Service Layer         Consumer Layer        Router Layer
───────────────   ─────────────────     ─────────────────     ──────────────
│ Dict[str,Any]│──▶│ProcessQueueResult│──▶│result.success   │──▶│HTTP Response│
│(raw results) │   │VideoGenResult    │   │result.jobs_*    │   │(FastAPI)    │
│              │   │ProcessingStatus  │   │(clean access)   │   │(JSON/Pydantic)│
└──────────────┘   └──────────────────┘   └─────────────────┘   └─────────────┘
```

This pattern follows industry standards used by FastAPI, Django REST Framework,
and other professional Python applications, ensuring maintainable and scalable
code architecture.
