# API Schemas

## Purpose

The `backend/api/schemas/` directory contains Pydantic models for request/response validation. These schemas ensure type safety, automatic validation, and OpenAPI documentation generation for all API endpoints.

## Files

### `__init__.py`

Package initialization with public exports:

- `CameraCreate`
- `CameraListResponse`
- `CameraResponse`
- `CameraUpdate`

### `camera.py`

Pydantic schemas for camera management endpoints.

**Schemas:**

| Schema               | Purpose                                               |
| -------------------- | ----------------------------------------------------- |
| `CameraCreate`       | Validate data for creating a new camera               |
| `CameraUpdate`       | Validate data for updating a camera (partial updates) |
| `CameraResponse`     | Serialize camera data in API responses                |
| `CameraListResponse` | Serialize list of cameras with count                  |

### `events.py`

Pydantic schemas for event management and statistics endpoints.

**Schemas:**

| Schema               | Purpose                                   |
| -------------------- | ----------------------------------------- |
| `EventResponse`      | Serialize event data with detection count |
| `EventUpdate`        | Validate event updates (reviewed, notes)  |
| `EventListResponse`  | Serialize paginated event list            |
| `EventsByRiskLevel`  | Events count by risk level                |
| `EventsByCamera`     | Events count for a single camera          |
| `EventStatsResponse` | Aggregated event statistics               |

### `detections.py`

Pydantic schemas for detection listing endpoints.

**Schemas:**

| Schema                  | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `DetectionResponse`     | Serialize detection with bounding box data |
| `DetectionListResponse` | Serialize paginated detection list         |

### `logs.py`

Pydantic schemas for log management and statistics endpoints.

**Schemas:**

| Schema              | Purpose                           |
| ------------------- | --------------------------------- |
| `LogEntry`          | Serialize a single log entry      |
| `LogsResponse`      | Serialize paginated logs response |
| `LogStats`          | Log statistics for dashboard      |
| `FrontendLogCreate` | Validate frontend log submission  |

### `system.py`

Pydantic schemas for system monitoring, configuration, and telemetry endpoints.

**Schemas:**

| Schema                    | Purpose                                     |
| ------------------------- | ------------------------------------------- |
| `ServiceStatus`           | Status of individual service components     |
| `HealthResponse`          | Complete system health check response       |
| `LivenessResponse`        | Liveness probe response (Kubernetes-style)  |
| `WorkerStatus`            | Status of background workers                |
| `ReadinessResponse`       | Readiness probe response (Kubernetes-style) |
| `GPUStatsResponse`        | Current GPU performance metrics             |
| `GPUStatsSample`          | Single time-series GPU sample               |
| `GPUStatsHistoryResponse` | GPU stats time series                       |
| `ConfigResponse`          | Public configuration settings               |
| `ConfigUpdateRequest`     | Configuration update request                |
| `SystemStatsResponse`     | System-wide statistics                      |
| `QueueDepths`             | Pipeline queue depth information            |
| `StageLatency`            | Latency statistics for a pipeline stage     |
| `PipelineLatencies`       | Latency stats for all pipeline stages       |
| `TelemetryResponse`       | Pipeline telemetry data                     |

### `media.py`

Pydantic schemas for media serving error responses.

**Schemas:**

| Schema               | Purpose                                  |
| -------------------- | ---------------------------------------- |
| `MediaErrorResponse` | Error response for media access failures |

### `dlq.py`

Pydantic schemas for dead-letter queue (DLQ) API endpoints.

**Schemas:**

| Schema               | Purpose                             |
| -------------------- | ----------------------------------- |
| `DLQJobResponse`     | Single job in the dead-letter queue |
| `DLQStatsResponse`   | DLQ statistics (counts per queue)   |
| `DLQJobsResponse`    | List of jobs in a DLQ               |
| `DLQRequeueResponse` | Response for requeue operation      |
| `DLQClearResponse`   | Response for clear operation        |

---

## Schema Details

### Camera Schemas (`camera.py`)

#### `CameraCreate`

**Fields:**

- `name: str` - Camera name (1-255 chars, required)
- `folder_path: str` - File system path (1-500 chars, required)
- `status: str` - Status (default: "online")

#### `CameraUpdate`

**Fields:** (all optional for partial updates)

- `name: str | None`
- `folder_path: str | None`
- `status: str | None`

#### `CameraResponse`

**Fields:**

- `id: str` - Camera UUID
- `name: str` - Camera name
- `folder_path: str` - File system path
- `status: str` - Status (online, offline, error)
- `created_at: datetime` - Creation timestamp
- `last_seen_at: datetime | None` - Last activity timestamp

**Config:** `from_attributes=True` for ORM mode

#### `CameraListResponse`

**Fields:**

- `cameras: list[CameraResponse]` - List of cameras
- `count: int` - Total number of cameras

---

### Event Schemas (`events.py`)

#### `EventResponse`

**Fields:**

- `id: int` - Event ID
- `camera_id: str` - Camera UUID
- `started_at: datetime` - Event start timestamp
- `ended_at: datetime | None` - Event end timestamp
- `risk_score: int | None` - Risk score 0-100
- `risk_level: str | None` - low, medium, high, critical
- `summary: str | None` - LLM-generated summary
- `reviewed: bool` - Whether reviewed (default: False)
- `notes: str | None` - User notes
- `detection_count: int` - Number of detections (default: 0)

#### `EventUpdate`

**Fields:**

- `reviewed: bool | None` - Mark as reviewed
- `notes: str | None` - User notes

#### `EventListResponse`

**Fields:**

- `events: list[EventResponse]` - List of events
- `count: int` - Total matching filters
- `limit: int` - Max results returned
- `offset: int` - Results skipped

#### `EventsByRiskLevel`

**Fields:**

- `critical: int` - Critical risk count (default: 0)
- `high: int` - High risk count (default: 0)
- `medium: int` - Medium risk count (default: 0)
- `low: int` - Low risk count (default: 0)

#### `EventsByCamera`

**Fields:**

- `camera_id: str` - Camera UUID
- `camera_name: str` - Camera name
- `event_count: int` - Events for this camera

#### `EventStatsResponse`

**Fields:**

- `total_events: int` - Total events
- `events_by_risk_level: EventsByRiskLevel` - By risk level
- `events_by_camera: list[EventsByCamera]` - By camera (sorted by count)

---

### Detection Schemas (`detections.py`)

#### `DetectionResponse`

**Fields:**

- `id: int` - Detection ID
- `camera_id: str` - Camera UUID
- `file_path: str` - Source image path
- `file_type: str | None` - MIME type
- `detected_at: datetime` - Detection timestamp
- `object_type: str | None` - person, car, etc.
- `confidence: float | None` - Score 0-1
- `bbox_x: int | None` - Bounding box X
- `bbox_y: int | None` - Bounding box Y
- `bbox_width: int | None` - Bounding box width
- `bbox_height: int | None` - Bounding box height
- `thumbnail_path: str | None` - Thumbnail path

#### `DetectionListResponse`

**Fields:**

- `detections: list[DetectionResponse]` - List of detections
- `count: int` - Total matching filters
- `limit: int` - Max results returned
- `offset: int` - Results skipped

---

### Log Schemas (`logs.py`)

#### `LogEntry`

**Fields:**

- `id: int` - Log entry ID
- `timestamp: datetime` - Log timestamp
- `level: str` - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `component: str` - Component/module name
- `message: str` - Log message
- `camera_id: str | None` - Associated camera ID
- `event_id: int | None` - Associated event ID
- `request_id: str | None` - Request correlation ID
- `detection_id: int | None` - Associated detection ID
- `duration_ms: int | None` - Operation duration
- `extra: dict | None` - Additional structured data
- `source: str` - backend or frontend (default: "backend")

#### `LogsResponse`

**Fields:**

- `logs: list[LogEntry]` - List of log entries
- `count: int` - Total matching filters
- `limit: int` - Page size
- `offset: int` - Page offset

#### `LogStats`

**Fields:**

- `total_today: int` - Total logs today
- `errors_today: int` - Error count today
- `warnings_today: int` - Warning count today
- `by_component: dict[str, int]` - Counts by component
- `by_level: dict[str, int]` - Counts by level
- `top_component: str | None` - Most active component

#### `FrontendLogCreate`

**Fields:**

- `level: str` - Log level (pattern validated)
- `component: str` - Frontend component name (max 50 chars)
- `message: str` - Log message (max 2000 chars)
- `extra: dict | None` - Additional context
- `user_agent: str | None` - Browser user agent
- `url: str | None` - Page URL

---

### System Schemas (`system.py`)

#### `ServiceStatus`

**Fields:**

- `status: str` - healthy, unhealthy, or not_initialized
- `message: str | None` - Status message or error
- `details: dict[str, str] | None` - Service-specific details

#### `HealthResponse`

**Fields:**

- `status: str` - healthy, degraded, or unhealthy
- `services: dict[str, ServiceStatus]` - database, redis, ai
- `timestamp: datetime` - Health check timestamp

#### `LivenessResponse`

**Fields:**

- `status: str` - Always "alive" if process is responding

#### `WorkerStatus`

**Fields:**

- `name: str` - Worker/service name
- `running: bool` - Whether currently running
- `message: str | None` - Status message

#### `ReadinessResponse`

**Fields:**

- `ready: bool` - Overall readiness
- `status: str` - ready, degraded, or not_ready
- `services: dict[str, ServiceStatus]` - Infrastructure services
- `workers: list[WorkerStatus]` - Background workers
- `timestamp: datetime` - Check timestamp

#### `GPUStatsResponse`

**Fields:** (all nullable if unavailable)

- `utilization: float | None` - GPU % (0-100)
- `memory_used: int | None` - Memory used (MB)
- `memory_total: int | None` - Total memory (MB)
- `temperature: float | None` - Temperature (Celsius)
- `inference_fps: float | None` - Inference FPS

#### `GPUStatsSample`

**Fields:**

- `recorded_at: datetime` - Sample timestamp
- `utilization: float | None` - GPU %
- `memory_used: int | None` - Memory used
- `memory_total: int | None` - Total memory
- `temperature: float | None` - Temperature
- `inference_fps: float | None` - Inference FPS

**Config:** `from_attributes=True` for ORM mode

#### `GPUStatsHistoryResponse`

**Fields:**

- `samples: list[GPUStatsSample]` - Chronological samples
- `count: int` - Number of samples
- `limit: int` - Applied limit

#### `ConfigResponse`

**Fields:** (public configuration only)

- `app_name: str` - Application name
- `version: str` - Application version
- `retention_days: int` - Data retention period (>= 1)
- `batch_window_seconds: int` - Batch processing window (>= 1)
- `batch_idle_timeout_seconds: int` - Batch idle timeout (>= 1)
- `detection_confidence_threshold: float` - Min confidence (0.0-1.0)

#### `ConfigUpdateRequest`

**Fields:** (all optional for partial updates)

- `retention_days: int | None`
- `batch_window_seconds: int | None`
- `batch_idle_timeout_seconds: int | None`
- `detection_confidence_threshold: float | None`

#### `SystemStatsResponse`

**Fields:**

- `total_cameras: int` - Total cameras (>= 0)
- `total_events: int` - Total events (>= 0)
- `total_detections: int` - Total detections (>= 0)
- `uptime_seconds: float` - Application uptime (>= 0)

#### `QueueDepths`

**Fields:**

- `detection_queue: int` - Items waiting for RT-DETRv2
- `analysis_queue: int` - Batches waiting for Nemotron

#### `StageLatency`

**Fields:**

- `avg_ms: float | None` - Average latency
- `min_ms: float | None` - Minimum latency
- `max_ms: float | None` - Maximum latency
- `p50_ms: float | None` - 50th percentile
- `p95_ms: float | None` - 95th percentile
- `p99_ms: float | None` - 99th percentile
- `sample_count: int` - Number of samples

#### `PipelineLatencies`

**Fields:**

- `watch: StageLatency | None` - File watcher stage
- `detect: StageLatency | None` - RT-DETRv2 stage
- `batch: StageLatency | None` - Batch aggregation
- `analyze: StageLatency | None` - Nemotron LLM stage

#### `TelemetryResponse`

**Fields:**

- `queues: QueueDepths` - Current queue depths
- `latencies: PipelineLatencies | None` - Stage latencies
- `timestamp: datetime` - Telemetry snapshot time

---

### Media Schemas (`media.py`)

#### `MediaErrorResponse`

**Fields:**

- `error: str` - Error message
- `path: str` - Attempted path

---

### DLQ Schemas (`dlq.py`)

#### `DLQJobResponse`

**Fields:**

- `original_job: dict` - Original job payload
- `error: str` - Error from last failure
- `attempt_count: int` - Processing attempts (>= 1)
- `first_failed_at: str` - ISO timestamp of first failure
- `last_failed_at: str` - ISO timestamp of last failure
- `queue_name: str` - Original queue name

#### `DLQStatsResponse`

**Fields:**

- `detection_queue_count: int` - Detection DLQ count
- `analysis_queue_count: int` - Analysis DLQ count
- `total_count: int` - Total across all DLQs

#### `DLQJobsResponse`

**Fields:**

- `queue_name: str` - DLQ name
- `jobs: list[DLQJobResponse]` - Jobs in queue
- `count: int` - Jobs returned

#### `DLQRequeueResponse`

**Fields:**

- `success: bool` - Operation succeeded
- `message: str` - Status message
- `job: dict | None` - Requeued job data

#### `DLQClearResponse`

**Fields:**

- `success: bool` - Operation succeeded
- `message: str` - Status message
- `queue_name: str` - Cleared queue name

---

## Common Patterns

### Field Validation

Pydantic provides automatic validation:

```python
name: str = Field(..., min_length=1, max_length=255)  # String length
utilization: float = Field(None, ge=0, le=100)        # Numeric range
status: str | None = Field(None)                       # Optional field
```

### Configuration

All schemas use `model_config` for:

```python
model_config = ConfigDict(
    from_attributes=True,  # Enable ORM mode for SQLAlchemy
    json_schema_extra={    # Example data for OpenAPI docs
        "example": {...}
    }
)
```

### Request/Response Patterns

| Pattern | Request Schema           | Response Schema             |
| ------- | ------------------------ | --------------------------- |
| Create  | `*Create` (all required) | `*Response` (with ID)       |
| Update  | `*Update` (all optional) | `*Response` (updated)       |
| List    | Query params             | `*ListResponse` (paginated) |
| Error   | N/A                      | `*ErrorResponse`            |

### ORM Integration

Schemas with `from_attributes=True` serialize SQLAlchemy models:

```python
camera = await db.get(Camera, camera_id)
return CameraResponse.model_validate(camera)
```

### Validation Errors

Returns 422 Unprocessable Entity with detailed information:

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Testing Considerations

When testing with schemas:

1. Test required field validation
2. Test field length/range constraints
3. Test optional field handling (None values)
4. Verify example JSON is valid
5. Test ORM mode with actual SQLAlchemy models
6. Verify partial updates exclude unset fields
7. Test regex pattern validation (e.g., log levels)
