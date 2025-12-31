# API Schemas

## Purpose

The `backend/api/schemas/` directory contains Pydantic models for request/response validation. These schemas ensure type safety, automatic validation, and OpenAPI documentation generation for all API endpoints.

## Files

### `__init__.py`

Package initialization with public exports. Exports schemas from:

- `alerts.py` - AlertCreate, AlertResponse, AlertRuleCreate, AlertRuleResponse, etc.
- `camera.py` - CameraCreate, CameraResponse, CameraUpdate, CameraListResponse
- `notification.py` - NotificationChannel, SendNotificationRequest, etc.
- `search.py` - SearchRequest, SearchResponse, SearchResult
- `websocket.py` - WebSocketMessage, WebSocketErrorResponse, etc.
- `zone.py` - ZoneCreate, ZoneResponse, ZoneUpdate, ZoneListResponse

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

| Schema                       | Purpose                                       |
| ---------------------------- | --------------------------------------------- |
| `SeverityEnum`               | Severity levels (low, medium, high, critical) |
| `ServiceStatus`              | Status of individual service components       |
| `HealthResponse`             | Complete system health check response         |
| `LivenessResponse`           | Liveness probe response (Kubernetes-style)    |
| `WorkerStatus`               | Status of background workers                  |
| `ReadinessResponse`          | Readiness probe response (Kubernetes-style)   |
| `GPUStatsResponse`           | Current GPU performance metrics               |
| `GPUStatsSample`             | Single time-series GPU sample                 |
| `GPUStatsHistoryResponse`    | GPU stats time series                         |
| `ConfigResponse`             | Public configuration settings                 |
| `ConfigUpdateRequest`        | Configuration update request                  |
| `SystemStatsResponse`        | System-wide statistics                        |
| `QueueDepths`                | Pipeline queue depth information              |
| `StageLatency`               | Latency statistics for a pipeline stage       |
| `PipelineLatencies`          | Latency stats for all pipeline stages         |
| `TelemetryResponse`          | Pipeline telemetry data                       |
| `PipelineStageLatency`       | Latency stats for pipeline stage transitions  |
| `PipelineLatencyResponse`    | Pipeline latency with window and percentiles  |
| `CleanupResponse`            | Cleanup operation results                     |
| `SeverityDefinitionResponse` | Single severity level definition              |
| `SeverityThresholds`         | Current severity threshold configuration      |
| `SeverityMetadataResponse`   | All severity definitions and thresholds       |
| `StorageCategoryStats`       | Storage stats for a single category           |
| `StorageStatsResponse`       | Disk usage and storage breakdown              |

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

### `performance.py`

Pydantic schemas for system performance metrics (System Performance Dashboard).

**Schemas:**

| Schema              | Purpose                                                   |
| ------------------- | --------------------------------------------------------- |
| `TimeRange`         | Enum for historical data time ranges (5m, 15m, 60m)       |
| `GpuMetrics`        | GPU metrics (name, utilization, VRAM, temperature, power) |
| `AiModelMetrics`    | RT-DETRv2 model metrics (status, VRAM, model, device)     |
| `NemotronMetrics`   | Nemotron LLM metrics (status, slots, context size)        |
| `InferenceMetrics`  | AI inference latency and throughput metrics               |
| `DatabaseMetrics`   | PostgreSQL metrics (connections, cache hit, transactions) |
| `RedisMetrics`      | Redis metrics (clients, memory, hit ratio)                |
| `HostMetrics`       | Host system metrics (CPU, RAM, disk usage)                |
| `ContainerMetrics`  | Container health status (name, status, health)            |
| `PerformanceAlert`  | Alert when metric exceeds threshold                       |
| `PerformanceUpdate` | Complete performance update sent via WebSocket            |

### `queue.py`

Pydantic schemas for queue message payload validation with security validation.

**Schemas:**

| Schema                  | Purpose                                     |
| ----------------------- | ------------------------------------------- |
| `DetectionQueuePayload` | Validated payload for detection queue items |
| `AnalysisQueuePayload`  | Validated payload for analysis queue items  |

**Functions:**

| Function                     | Purpose                            |
| ---------------------------- | ---------------------------------- |
| `validate_detection_payload` | Validate a detection queue payload |
| `validate_analysis_payload`  | Validate an analysis queue payload |

**Security Features:**

- Path traversal prevention via file_path validation
- Camera ID character restrictions (alphanumeric, underscores, hyphens)
- Media type restriction to known types
- Timestamp format validation
- Null byte injection prevention
- DoS protection (max 10000 detection_ids)

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
- `detection_ids: list[int]` - IDs of associated detections

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
- `file_path: str` - Source image/video path
- `file_type: str | None` - MIME type
- `detected_at: datetime` - Detection timestamp
- `object_type: str | None` - person, car, etc.
- `confidence: float | None` - Score 0-1
- `bbox_x: int | None` - Bounding box X
- `bbox_y: int | None` - Bounding box Y
- `bbox_width: int | None` - Bounding box width
- `bbox_height: int | None` - Bounding box height
- `thumbnail_path: str | None` - Thumbnail path
- `media_type: str | None` - "image" or "video" (default: "image")
- `duration: float | None` - Video duration in seconds
- `video_codec: str | None` - Video codec (e.g., h264, hevc)
- `video_width: int | None` - Video resolution width
- `video_height: int | None` - Video resolution height

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

#### `PipelineStageLatency`

**Fields:**

- `avg_ms: float | None` - Average latency
- `min_ms: float | None` - Minimum latency
- `max_ms: float | None` - Maximum latency
- `p50_ms: float | None` - 50th percentile
- `p95_ms: float | None` - 95th percentile
- `p99_ms: float | None` - 99th percentile
- `sample_count: int` - Number of samples (>= 0)

#### `PipelineLatencyResponse`

**Fields:**

- `watch_to_detect: PipelineStageLatency | None` - Watch to detect latency
- `detect_to_batch: PipelineStageLatency | None` - Detect to batch latency
- `batch_to_analyze: PipelineStageLatency | None` - Batch to analyze latency
- `total_pipeline: PipelineStageLatency | None` - End-to-end latency
- `window_minutes: int` - Time window used (>= 1)
- `timestamp: datetime` - Latency snapshot time

#### `CleanupResponse`

**Fields:**

- `events_deleted: int` - Events deleted (or would be in dry run)
- `detections_deleted: int` - Detections deleted
- `gpu_stats_deleted: int` - GPU stats records deleted
- `logs_deleted: int` - Log records deleted
- `thumbnails_deleted: int` - Thumbnail files deleted
- `images_deleted: int` - Original image files deleted
- `space_reclaimed: int` - Bytes freed (estimated)
- `retention_days: int` - Retention period used
- `dry_run: bool` - Whether this was a dry run
- `timestamp: datetime` - Cleanup operation time

#### `SeverityDefinitionResponse`

**Fields:**

- `severity: SeverityEnum` - The severity level
- `label: str` - Human-readable label
- `description: str` - Description of when this applies
- `color: str` - Hex color code for UI (e.g., "#22c55e")
- `priority: int` - Sort priority (0 = highest)
- `min_score: int` - Minimum risk score (inclusive)
- `max_score: int` - Maximum risk score (inclusive)

#### `SeverityThresholds`

**Fields:**

- `low_max: int` - Max score for LOW severity
- `medium_max: int` - Max score for MEDIUM severity
- `high_max: int` - Max score for HIGH severity

#### `SeverityMetadataResponse`

**Fields:**

- `definitions: list[SeverityDefinitionResponse]` - All severity definitions
- `thresholds: SeverityThresholds` - Current threshold config

#### `StorageCategoryStats`

**Fields:**

- `file_count: int` - Number of files (>= 0)
- `size_bytes: int` - Total size in bytes (>= 0)

#### `StorageStatsResponse`

**Fields:**

- `disk_used_bytes: int` - Total disk space used
- `disk_total_bytes: int` - Total disk space available
- `disk_free_bytes: int` - Free disk space
- `disk_usage_percent: float` - Usage percentage (0-100)
- `thumbnails: StorageCategoryStats` - Thumbnail storage
- `images: StorageCategoryStats` - Camera images storage
- `clips: StorageCategoryStats` - Event clips storage
- `events_count: int` - Total events in database
- `detections_count: int` - Total detections in database
- `gpu_stats_count: int` - Total GPU stats records
- `logs_count: int` - Total log entries
- `timestamp: datetime` - Stats snapshot time

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

### Alert Schemas (`alerts.py`)

#### Enums

- `AlertSeverity` - low, medium, high, critical
- `AlertStatus` - pending, delivered, acknowledged, dismissed

#### `AlertRuleSchedule`

Time-based conditions for when rules are active.

**Fields:**

- `days: list[str] | None` - Days of week (empty = all days)
- `start_time: str | None` - Start time in HH:MM format
- `end_time: str | None` - End time in HH:MM format
- `timezone: str` - Timezone for evaluation (default: UTC)

#### `AlertRuleConditions`

Legacy conditions schema for backward compatibility.

**Fields:**

- `risk_threshold: int | None` - Minimum risk score (0-100)
- `object_types: list[str] | None` - Object types to match
- `camera_ids: list[str] | None` - Camera IDs to filter
- `time_ranges: list[dict] | None` - Time ranges when active

#### `AlertRuleCreate`

**Fields:**

- `name: str` - Rule name (1-255 chars)
- `description: str | None` - Rule description
- `enabled: bool` - Whether rule is active (default: True)
- `severity: AlertSeverity` - Severity level
- `risk_threshold: int | None` - Alert when risk_score >= threshold
- `object_types: list[str] | None` - Object types to match
- `camera_ids: list[str] | None` - Camera IDs (empty = all)
- `zone_ids: list[str] | None` - Zone IDs (empty = any)
- `min_confidence: float | None` - Minimum detection confidence (0.0-1.0)
- `schedule: AlertRuleSchedule | None` - Time-based conditions
- `conditions: AlertRuleConditions | None` - Legacy conditions
- `dedup_key_template: str` - Template for deduplication key
- `cooldown_seconds: int` - Seconds between duplicate alerts (default: 300)
- `channels: list[str]` - Notification channels

#### `AlertRuleUpdate`

Same as AlertRuleCreate but all fields optional for partial updates.

#### `AlertRuleResponse`

Response schema with all AlertRule fields plus `id`, `created_at`, `updated_at`.

#### `AlertRuleListResponse`

Paginated list with `rules`, `count`, `limit`, `offset`.

#### `AlertCreate`, `AlertUpdate`, `AlertResponse`, `AlertListResponse`

Standard CRUD schemas for triggered alerts.

#### `DedupCheckRequest`, `DedupCheckResponse`

Deduplication checking schemas.

#### `RuleTestRequest`, `RuleTestEventResult`, `RuleTestResponse`

Rule testing schemas for validating rules against historical events.

---

### Audit Schemas (`audit.py`)

#### `AuditLogResponse`

**Fields:**

- `id: int` - Audit log entry ID
- `timestamp: datetime` - When action occurred
- `action: str` - Action performed
- `resource_type: str` - Type of resource
- `resource_id: str | None` - Specific resource ID
- `actor: str` - User or system that performed action
- `ip_address: str | None` - Client IP address
- `user_agent: str | None` - Client user agent
- `details: dict | None` - Action-specific details
- `status: str` - success or failure

#### `AuditLogListResponse`

Paginated list with `logs`, `count`, `limit`, `offset`.

#### `AuditLogStats`

**Fields:**

- `total_logs: int` - Total audit log count
- `logs_today: int` - Logs created today
- `by_action: dict[str, int]` - Counts by action type
- `by_resource_type: dict[str, int]` - Counts by resource type
- `by_status: dict[str, int]` - Counts by status
- `recent_actors: list[str]` - Recently active actors

---

### Zone Schemas (`zone.py`)

#### `ZoneCreate`

**Fields:**

- `name: str` - Zone name (1-255 chars)
- `zone_type: ZoneType` - entry_point, exit_point, restricted, monitored, other
- `coordinates: list[list[float]]` - Normalized [x, y] points (0-1 range, min 3 points)
- `shape: ZoneShape` - rectangle or polygon
- `color: str` - Hex color for UI (e.g., "#3B82F6")
- `enabled: bool` - Whether zone is active (default: True)
- `priority: int` - Priority for overlapping zones (0-100)

**Validators:**

- Coordinates must be exactly 2 values per point
- All coordinates must be in 0-1 normalized range

#### `ZoneUpdate`

Same as ZoneCreate but all fields optional.

#### `ZoneResponse`

Response with all Zone fields plus `id`, `camera_id`, `created_at`, `updated_at`.

#### `ZoneListResponse`

List with `zones` and `count`.

---

### WebSocket Schemas (`websocket.py`)

#### Message Types (enum)

- `PING` - Keep-alive heartbeat
- `SUBSCRIBE` - Subscribe to channels
- `UNSUBSCRIBE` - Unsubscribe from channels

#### Incoming Messages

- `WebSocketPingMessage` - Ping request (responds with pong)
- `WebSocketSubscribeMessage` - Subscribe with channel list
- `WebSocketUnsubscribeMessage` - Unsubscribe from channels
- `WebSocketMessage` - Generic message for type detection

#### Outgoing Messages

- `WebSocketPongResponse` - Pong response
- `WebSocketErrorResponse` - Error with code and message
- `WebSocketEventData` - Event data payload
- `WebSocketEventMessage` - Complete event message envelope

#### Error Codes

- `INVALID_JSON` - Message is not valid JSON
- `INVALID_MESSAGE_FORMAT` - Message structure is invalid
- `UNKNOWN_MESSAGE_TYPE` - Unrecognized message type
- `VALIDATION_ERROR` - Pydantic validation failed

---

### Search Schemas (`search.py`)

#### `SearchResult`

**Fields:**

- `id: int` - Event ID
- `camera_id: str` - Camera ID
- `camera_name: str | None` - Camera display name
- `started_at: datetime` - Event start timestamp
- `ended_at: datetime | None` - Event end timestamp
- `risk_score: int | None` - Risk score (0-100)
- `risk_level: str | None` - Risk classification
- `summary: str | None` - LLM-generated summary
- `reasoning: str | None` - LLM reasoning
- `reviewed: bool` - Review status
- `detection_count: int` - Number of detections
- `detection_ids: list[int]` - Detection IDs
- `object_types: str | None` - Comma-separated object types
- `relevance_score: float` - Full-text search relevance

#### `SearchResponse`

Paginated results with `results`, `total_count`, `limit`, `offset`.

#### `SearchRequest`

**Fields:**

- `query: str` - Search query string
- `start_date: datetime | None` - Start date filter
- `end_date: datetime | None` - End date filter
- `camera_ids: list[str] | None` - Camera filter
- `severity: list[str] | None` - Risk level filter
- `object_types: list[str] | None` - Object type filter
- `reviewed: bool | None` - Review status filter
- `limit: int` - Max results (default: 50)
- `offset: int` - Skip results (default: 0)

---

### Notification Schemas (`notification.py`)

#### `NotificationChannel` (enum)

- `EMAIL` - Email notifications
- `WEBHOOK` - Webhook notifications
- `PUSH` - Push notifications

#### `NotificationDeliveryResponse`

Single delivery result with `channel`, `success`, `error`, `delivered_at`, `recipient`.

#### `DeliveryResultResponse`

Complete delivery result across channels with success counts.

#### `SendNotificationRequest`

Request to deliver notifications for an alert.

#### `TestNotificationRequest`, `TestNotificationResponse`

Test notification configuration.

#### `NotificationConfigResponse`

Configuration status with enabled channels and default settings.

#### `NotificationHistoryEntry`, `NotificationHistoryResponse`

Notification delivery history.

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
