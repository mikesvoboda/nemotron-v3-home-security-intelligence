# API Schemas

## Purpose

The `backend/api/schemas/` directory contains Pydantic models for request/response validation. These schemas ensure type safety, automatic validation, and OpenAPI documentation generation for all API endpoints.

## Files

### `__init__.py`

Package initialization with public exports. Exports schemas from:

- `alerts.py` - AlertCreate, AlertResponse, AlertRuleCreate, AlertRuleResponse, AlertSeverity, AlertStatus, etc.
- `baseline.py` - AnomalyEvent, AnomalyListResponse, BaselineSummaryResponse, CurrentDeviation, etc.
- `camera.py` - CameraCreate, CameraResponse, CameraUpdate, CameraListResponse, CameraStatus
- `clips.py` - ClipGenerateRequest, ClipGenerateResponse, ClipInfoResponse, ClipStatus
- `detections.py` - EnrichmentDataSchema, PersonEnrichmentData, PetEnrichmentData, VehicleEnrichmentData
- `enrichment.py` - EnrichmentResponse, EventEnrichmentsResponse, LicensePlateEnrichment, VehicleEnrichment, etc.
- `llm_response.py` - LLMRawResponse, LLMRiskResponse, RiskLevel (as LLMRiskLevel)
- `notification.py` - NotificationChannel, SendNotificationRequest, TestNotificationRequest, etc.
- `scene_change.py` - SceneChangeResponse, SceneChangeListResponse, SceneChangeType
- `services.py` - ServiceCategory, ServiceStatus, ServiceInfo, ServicesResponse, ServiceActionResponse, ServiceStatusEvent
- `search.py` - SearchRequest, SearchResponse, SearchResult
- `websocket.py` - WebSocketMessage, WebSocketErrorResponse, WebSocketEventMessage, ServiceStatus, RiskLevel, etc.
- `zone.py` - ZoneCreate, ZoneResponse, ZoneUpdate, ZoneListResponse

### `camera.py`

Pydantic schemas for camera management endpoints.

**Enums:**

| Enum           | Purpose                                                |
| -------------- | ------------------------------------------------------ |
| `CameraStatus` | Camera status values (online, offline, error, unknown) |

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

Pydantic schemas for detection endpoints and enrichment data validation.

**Schemas:**

| Schema                  | Purpose                                             |
| ----------------------- | --------------------------------------------------- |
| `VehicleEnrichmentData` | Vehicle enrichment data (type, color, damage, etc.) |
| `PersonEnrichmentData`  | Person enrichment data (clothing, action, carrying) |
| `PetEnrichmentData`     | Pet enrichment data (type, breed)                   |
| `EnrichmentDataSchema`  | Composite enrichment_data JSONB field schema        |
| `DetectionResponse`     | Serialize detection with bounding box data          |
| `DetectionListResponse` | Serialize paginated detection list                  |

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
| `AiModelMetrics`    | YOLO26v2 model metrics (status, VRAM, model, device)     |
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

- `id: str` - Normalized camera ID (e.g., "front_door")
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
- `camera_id: str` - Normalized camera ID (e.g., "front_door")
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

- `camera_id: str` - Normalized camera ID (e.g., "front_door")
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
- `camera_id: str` - Normalized camera ID (e.g., "front_door")
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

- `detection_queue: int` - Items waiting for YOLO26v2
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
- `detect: StageLatency | None` - YOLO26v2 stage
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

### AI Audit Schemas (`ai_audit.py`)

Pydantic schemas for AI pipeline audit and self-evaluation endpoints.

**Schemas:**

| Schema                    | Purpose                                           |
| ------------------------- | ------------------------------------------------- |
| `ModelContributions`      | Flags for which AI models contributed to an event |
| `QualityScores`           | Self-evaluation quality scores (1-5 scale)        |
| `PromptImprovements`      | Suggestions for improving prompts                 |
| `EventAuditResponse`      | Full audit response for a single event            |
| `AuditStatsResponse`      | Aggregate audit statistics                        |
| `ModelLeaderboardEntry`   | Single entry in model contribution leaderboard    |
| `LeaderboardResponse`     | Model leaderboard ranked by contribution rate     |
| `RecommendationItem`      | Single prompt improvement recommendation          |
| `RecommendationsResponse` | Aggregated recommendations response               |
| `BatchAuditRequest`       | Request for batch audit processing                |
| `BatchAuditResponse`      | Response for batch audit request                  |

---

### Baseline Schemas (`baseline.py`)

Pydantic schemas for camera baseline activity patterns and anomaly detection.

**Schemas:**

| Schema                    | Purpose                                                        |
| ------------------------- | -------------------------------------------------------------- |
| `DeviationInterpretation` | Enum for deviation interpretation (normal to far_above_normal) |
| `HourlyPattern`           | Activity pattern for a specific hour                           |
| `DailyPattern`            | Activity pattern for a specific day of the week                |
| `ObjectBaseline`          | Baseline statistics for a specific object class                |
| `CurrentDeviation`        | Current activity deviation from established baseline           |
| `BaselineSummaryResponse` | Comprehensive baseline data for a camera                       |
| `AnomalyEvent`            | Single anomaly event detected for a camera                     |
| `AnomalyListResponse`     | Response for camera anomaly list endpoint                      |

---

### Clips Schemas (`clips.py`)

Pydantic schemas for event clip generation and retrieval.

**Schemas:**

| Schema                 | Purpose                                                      |
| ---------------------- | ------------------------------------------------------------ |
| `ClipStatus`           | Enum for clip generation status (pending, completed, failed) |
| `ClipInfoResponse`     | Response for clip info (availability, URL, duration)         |
| `ClipGenerateRequest`  | Request for clip generation with time offsets                |
| `ClipGenerateResponse` | Response after clip generation                               |

---

### Enrichment Data Schemas (`enrichment_data.py`)

Pydantic schemas for validating the enrichment_data JSONB field in detections. Handles raw database format with graceful legacy data handling.

**Schemas:**

| Schema                       | Purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `LicensePlateItem`           | Single license plate detection with OCR          |
| `FaceItem`                   | Single face detection with bounding box          |
| `ViolenceDetectionData`      | Violence detection results                       |
| `VehicleClassificationData`  | Vehicle type classification per-detection        |
| `VehicleDamageData`          | Vehicle damage detection per-detection           |
| `ClothingClassificationData` | Clothing analysis per-detection                  |
| `ClothingSegmentationData`   | Clothing segmentation per-detection              |
| `PetClassificationData`      | Pet classification per-detection                 |
| `ImageQualityData`           | Image quality assessment results                 |
| `EnrichmentDataSchema`       | Complete enrichment_data JSONB validation schema |
| `EnrichmentValidationResult` | Validation result with warnings and errors       |

**Functions:**

| Function                   | Purpose                                               |
| -------------------------- | ----------------------------------------------------- |
| `validate_enrichment_data` | Validate enrichment data gracefully (with warnings)   |
| `coerce_enrichment_data`   | Convenience function returning validated/coerced data |

---

### Enrichment Schemas (`enrichment.py`)

Pydantic schemas for enrichment API endpoints - structured access to 18+ vision model results.

**Schemas:**

| Schema                     | Purpose                                           |
| -------------------------- | ------------------------------------------------- |
| `LicensePlateEnrichment`   | License plate detection and OCR results           |
| `FaceEnrichment`           | Face detection results                            |
| `VehicleEnrichment`        | Vehicle classification results                    |
| `ClothingEnrichment`       | Clothing classification and segmentation          |
| `ViolenceEnrichment`       | Violence detection results                        |
| `WeatherEnrichment`        | Weather classification results                    |
| `PoseEnrichment`           | Pose estimation results (placeholder)             |
| `DepthEnrichment`          | Depth estimation results (placeholder)            |
| `ImageQualityEnrichment`   | Image quality assessment                          |
| `PetEnrichment`            | Pet classification for false positive reduction   |
| `EnrichmentResponse`       | Structured enrichment data for a single detection |
| `EventEnrichmentsResponse` | Enrichment data for all detections in an event    |

---

### Error Response Schemas (`errors.py`)

Standardized error response schemas for consistent API error handling across all endpoints.

**Purpose:**

Defines Pydantic models for error responses that ensure all API endpoints return errors in a
consistent format, regardless of the error source. This improves client integration and
provides clear, actionable error messages.

**Schemas:**

| Schema                       | Purpose                                        |
| ---------------------------- | ---------------------------------------------- |
| `ErrorDetail`                | Detailed error information with code/message   |
| `ErrorResponse`              | Standard error response wrapper                |
| `ValidationErrorDetail`      | Detail for a single validation error           |
| `ValidationErrorResponse`    | Error response with multiple validation errors |
| `RateLimitErrorResponse`     | Rate limit exceeded with retry information     |
| `ServiceUnavailableResponse` | Service unavailability with retry hints        |

**Standard Error Response Format:**

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": { "field": "value" },
    "request_id": "uuid-for-tracing",
    "timestamp": "2025-01-07T10:30:00Z"
  }
}
```

**Common Error Responses Dictionary:**

`COMMON_ERROR_RESPONSES` - Predefined OpenAPI documentation for standard HTTP error codes (400, 401, 403, 404, 409, 429, 500, 502, 503).

**Usage in Routes:**

```python
from backend.api.schemas.errors import ErrorResponse, COMMON_ERROR_RESPONSES

@router.get("/{id}", responses=COMMON_ERROR_RESPONSES)
async def get_item(id: int) -> Item:
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found"
        )
    return item
```

**Error Codes:**

- `CAMERA_NOT_FOUND` - Camera resource not found
- `VALIDATION_ERROR` - Request validation failed
- `RATE_LIMIT_EXCEEDED` - Rate limit exceeded
- `AUTHENTICATION_REQUIRED` - API key required
- `ACCESS_DENIED` - Forbidden access
- `INTERNAL_ERROR` - Internal server error
- `SERVICE_UNAVAILABLE` - External service unavailable

---

### Entity Schemas (`entities.py`)

Pydantic schemas for entity re-identification API endpoints - tracking persons/vehicles across cameras.

**Schemas:**

| Schema                  | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| `EntityAppearance`      | Single entity appearance at a specific time/camera |
| `EntitySummary`         | Entity overview without full appearance history    |
| `EntityDetail`          | Detailed entity info including all appearances     |
| `EntityListResponse`    | Paginated entity list response                     |
| `EntityHistoryResponse` | Entity appearance history response                 |

---

### LLM Schemas (`llm.py`)

Pydantic schemas for comprehensive LLM (Nemotron) response validation with entities, flags, and detailed confidence factors.

**Enums:**

| Enum                 | Purpose                                   |
| -------------------- | ----------------------------------------- |
| `RiskLevel`          | Risk levels (low, medium, high, critical) |
| `ThreatLevel`        | Threat level for individual entities      |
| `EntityType`         | Entity types (person, vehicle, pet)       |
| `FlagSeverity`       | Security flag severity levels             |
| `FlagType`           | Types of security flags                   |
| `DetectionQuality`   | Detection quality assessment              |
| `WeatherImpact`      | Weather impact on detection accuracy      |
| `EnrichmentCoverage` | Level of enrichment data coverage         |

**Schemas:**

| Schema                  | Purpose                                         |
| ----------------------- | ----------------------------------------------- |
| `LLMEntity`             | Individual entity detected in security event    |
| `LLMFlag`               | Security flag raised during analysis            |
| `LLMConfidenceFactors`  | Confidence factors affecting reliability        |
| `LLMRiskResponse`       | Primary schema for LLM risk assessment response |
| `LLMResponseParseError` | Exception for unparseable LLM responses         |

**Functions:**

| Function                      | Purpose                              |
| ----------------------------- | ------------------------------------ |
| `validate_llm_response`       | Validate and parse LLM response data |
| `infer_risk_level_from_score` | Infer risk level from numeric score  |

---

### LLM Response Schemas (`llm_response.py`)

Simpler Pydantic schemas for LLM response validation focusing on core risk assessment fields.

**Enums:**

| Enum        | Purpose                                                           |
| ----------- | ----------------------------------------------------------------- |
| `RiskLevel` | Risk levels with severity thresholds (0-29, 30-59, 60-84, 85-100) |

**Schemas:**

| Schema            | Purpose                                           |
| ----------------- | ------------------------------------------------- |
| `LLMRiskResponse` | Validated risk assessment with strict constraints |
| `LLMRawResponse`  | Lenient parsing for raw LLM JSON output           |

**Functions:**

| Function                      | Purpose                             |
| ----------------------------- | ----------------------------------- |
| `infer_risk_level_from_score` | Infer risk level from numeric score |

**Notes:**

- `LLMRawResponse` is used for initial parsing of LLM output with flexible coercion
- `LLMRiskResponse` is used after normalization for strict validation
- Both are exported via `__init__.py` for use in services

---

### Prompt Management Schemas (`prompt_management.py`)

Pydantic schemas for prompt management API - configuration, versioning, testing, and import/export.

**Enums:**

| Enum          | Purpose                                                                    |
| ------------- | -------------------------------------------------------------------------- |
| `AIModelEnum` | Supported AI models (nemotron, florence2, yolo_world, xclip, fashion_clip) |

**Model-specific Config Schemas:**

| Schema              | Purpose                                   |
| ------------------- | ----------------------------------------- |
| `NemotronConfig`    | Nemotron risk analysis configuration      |
| `Florence2Config`   | Florence-2 scene analysis configuration   |
| `YoloWorldConfig`   | YOLO-World custom object detection config |
| `XClipConfig`       | X-CLIP action recognition configuration   |
| `FashionClipConfig` | Fashion-CLIP clothing analysis config     |

**Request/Response Schemas:**

| Schema                         | Purpose                                   |
| ------------------------------ | ----------------------------------------- |
| `ModelPromptConfig`            | Configuration for a specific AI model     |
| `AllPromptsResponse`           | Response with all model configurations    |
| `PromptUpdateRequest`          | Request to update a model's configuration |
| `PromptTestRequest`            | Request to test a prompt modification     |
| `PromptTestResult`             | Result of a prompt test                   |
| `PromptVersionInfo`            | Information about a single version        |
| `PromptHistoryResponse`        | Version history response                  |
| `PromptRestoreRequest`         | Request to restore a version              |
| `PromptRestoreResponse`        | Response after restoring a version        |
| `PromptsExportResponse`        | Export of all configurations              |
| `PromptsImportRequest`         | Request to import configurations          |
| `PromptsImportResponse`        | Response after importing                  |
| `PromptDiffEntry`              | Diff entry for a single model             |
| `PromptsImportPreviewRequest`  | Request to preview import changes         |
| `PromptsImportPreviewResponse` | Response with preview of changes          |

---

### Services Schemas (`services.py`)

Pydantic schemas for the container orchestrator API - managing lifecycle of deployment containers.

**Enums:**

| Enum              | Purpose                                                                               |
| ----------------- | ------------------------------------------------------------------------------------- |
| `ServiceCategory` | Service classification (infrastructure, ai, monitoring)                               |
| `ServiceStatus`   | Current container status (running, starting, unhealthy, stopped, disabled, not_found) |

**Schemas:**

| Schema                  | Purpose                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `ServiceInfo`           | Information about a single managed service/container           |
| `CategorySummary`       | Summary of services in a category (total, healthy, unhealthy)  |
| `ServicesResponse`      | Response for GET /api/system/services                          |
| `ServiceActionResponse` | Response for service actions (restart, enable, disable, start) |
| `ServiceStatusEvent`    | WebSocket event for service status changes                     |

**Service Categories:**

| Category       | Services                                      | Restart Policy |
| -------------- | --------------------------------------------- | -------------- |
| Infrastructure | PostgreSQL, Redis                             | Critical       |
| AI             | YOLO26, Nemotron, Florence, CLIP, Enrichment | Standard       |
| Monitoring     | Prometheus, Grafana, Redis Exporter           | Lenient        |

---

### Scene Change Schemas (`scene_change.py`)

Pydantic schemas for scene change detection and acknowledgement.

**Enums:**

| Enum              | Purpose                                                              |
| ----------------- | -------------------------------------------------------------------- |
| `SceneChangeType` | Type of change (view_blocked, angle_changed, view_tampered, unknown) |

**Schemas:**

| Schema                           | Purpose                                     |
| -------------------------------- | ------------------------------------------- |
| `SceneChangeResponse`            | Single scene change with similarity score   |
| `SceneChangeListResponse`        | List of scene changes for a camera          |
| `SceneChangeAcknowledgeResponse` | Response after acknowledging a scene change |

---

### Analytics Schemas (`analytics.py`)

Pydantic schemas for analytics endpoints - trends, risk history, uptime, and object distribution.

**Schemas:**

| Schema                        | Purpose                                        |
| ----------------------------- | ---------------------------------------------- |
| `DetectionTrendDataPoint`     | Single detection trend data point by date      |
| `DetectionTrendsResponse`     | Detection counts aggregated by day             |
| `RiskHistoryDataPoint`        | Risk level distribution for a single date      |
| `RiskHistoryResponse`         | Risk score distribution over time              |
| `CameraUptimeDataPoint`       | Uptime and detection count for a single camera |
| `CameraUptimeResponse`        | Uptime percentage per camera                   |
| `ObjectDistributionDataPoint` | Detection count for a single object type       |
| `ObjectDistributionResponse`  | Detection counts by object type                |

---

### Bulk Operations Schemas (`bulk.py`)

Pydantic schemas for bulk create, update, and delete operations with HTTP 207 Multi-Status support.

**Enums:**

| Enum                  | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| `BulkOperationStatus` | Status of individual items (success, failed, skipped) |

**Schemas:**

| Schema                        | Purpose                                       |
| ----------------------------- | --------------------------------------------- |
| `BulkItemResult`              | Result for a single item in a bulk operation  |
| `BulkOperationResponse`       | Base response with partial success support    |
| `EventBulkCreateItem`         | Single event in a bulk create request         |
| `EventBulkCreateRequest`      | Request for bulk event creation (max 100)     |
| `EventBulkCreateResponse`     | Response for bulk event creation              |
| `EventBulkUpdateItem`         | Single event update in bulk update request    |
| `EventBulkUpdateRequest`      | Request for bulk event updates (max 100)      |
| `EventBulkDeleteRequest`      | Request for bulk event deletion (max 100)     |
| `DetectionBulkCreateItem`     | Single detection in bulk create request       |
| `DetectionBulkCreateRequest`  | Request for bulk detection creation (max 100) |
| `DetectionBulkCreateResponse` | Response for bulk detection creation          |
| `DetectionBulkUpdateItem`     | Single detection update in bulk request       |
| `DetectionBulkUpdateRequest`  | Request for bulk detection updates (max 100)  |
| `DetectionBulkDeleteRequest`  | Request for bulk detection deletion (max 100) |

---

### Health Check Schemas (`health.py`)

Consolidated response schemas for health check endpoints (NEM-1582).

**Enums:**

| Enum                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `ServiceHealthState` | Health state (healthy, unhealthy, degraded, unknown) |
| `CircuitState`       | Circuit breaker state (closed, open, half_open)      |

**Schemas:**

| Schema                       | Purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `LivenessResponse`           | Liveness probe response (always "alive")         |
| `CheckResult`                | Individual service health check result           |
| `ReadinessResponse`          | Readiness probe with service checks              |
| `SimpleReadinessResponse`    | Minimal readiness response                       |
| `AIServiceHealthStatus`      | Health status for AI services with circuit state |
| `InfrastructureHealthStatus` | Health status for postgres/redis                 |
| `CircuitBreakerSummary`      | Summary of all circuit breakers                  |
| `WorkerHealthStatus`         | Health status for background workers             |
| `FullHealthResponse`         | Comprehensive health check response              |

---

### HATEOAS Schemas (`hateoas.py`)

Hypermedia links for REST API discoverability.

**Schemas:**

| Schema    | Purpose                                        |
| --------- | ---------------------------------------------- |
| `Link`    | HATEOAS link with href, rel, and HTTP method   |
| `LinkRel` | Constants for standard link relationship types |

**Functions:**

| Function                      | Purpose                                    |
| ----------------------------- | ------------------------------------------ |
| `build_link`                  | Build a HATEOAS link from request and path |
| `build_camera_links`          | Standard links for camera resources        |
| `build_event_links`           | Standard links for event resources         |
| `build_detection_links`       | Standard links for detection resources     |
| `build_detection_video_links` | Extended links for video detections        |

---

### Notification Preferences Schemas (`notification_preferences.py`)

Pydantic schemas for notification preferences including global settings, per-camera settings, and quiet hours.

**Schemas:**

| Schema                                   | Purpose                                  |
| ---------------------------------------- | ---------------------------------------- |
| `NotificationPreferencesResponse`        | Global notification preferences response |
| `NotificationPreferencesUpdate`          | Update global notification preferences   |
| `CameraNotificationSettingResponse`      | Per-camera notification setting response |
| `CameraNotificationSettingUpdate`        | Update per-camera notification settings  |
| `CameraNotificationSettingsListResponse` | List of camera notification settings     |
| `QuietHoursPeriodCreate`                 | Create a quiet hours period              |
| `QuietHoursPeriodResponse`               | Quiet hours period response              |
| `QuietHoursPeriodsListResponse`          | List of quiet hours periods              |

---

### Problem Details Schemas (`problem_details.py`)

RFC 7807 Problem Details format for standardized API error responses.

**Functions:**

| Function            | Purpose                                  |
| ------------------- | ---------------------------------------- |
| `get_status_phrase` | Get standard HTTP status phrase for code |

**Schemas:**

| Schema          | Purpose                           |
| --------------- | --------------------------------- |
| `ProblemDetail` | RFC 7807 compliant error response |

**Fields:**

- `type` - URI reference identifying the problem type
- `title` - Short, human-readable summary
- `status` - HTTP status code
- `detail` - Human-readable explanation
- `instance` - URI reference for specific occurrence

---

### RUM Schemas (`rum.py`)

Real User Monitoring schemas for Core Web Vitals ingestion.

**Enums:**

| Enum           | Purpose                                            |
| -------------- | -------------------------------------------------- |
| `WebVitalName` | Supported metrics (LCP, FID, INP, CLS, TTFB, FCP)  |
| `RatingType`   | Performance rating (good, needs-improvement, poor) |

**Schemas:**

| Schema              | Purpose                                  |
| ------------------- | ---------------------------------------- |
| `WebVitalMetric`    | Single Core Web Vital metric measurement |
| `RUMBatchRequest`   | Batch request for multiple metrics       |
| `RUMIngestResponse` | Response from RUM ingestion endpoint     |

---

### Streaming Schemas (`streaming.py`)

SSE streaming event schemas for LLM analysis responses (NEM-1665).

**Enums:**

| Enum                 | Purpose                            |
| -------------------- | ---------------------------------- |
| `StreamingErrorCode` | Error codes for streaming failures |

**Schemas:**

| Schema                   | Purpose                                   |
| ------------------------ | ----------------------------------------- |
| `StreamingProgressEvent` | Progress event with content chunk         |
| `StreamingCompleteEvent` | Completion event with event ID and scores |
| `StreamingErrorEvent`    | Error event with code and recoverability  |

---

### Export Schemas (`export.py`)

Pydantic schemas for export API endpoints with background job tracking.

**Enums:**

| Enum                  | Purpose                                          |
| --------------------- | ------------------------------------------------ |
| `ExportJobStatusEnum` | Job status (pending, running, completed, failed) |
| `ExportTypeEnum`      | Export types (events, alerts, full_backup)       |
| `ExportFormatEnum`    | File formats (csv, json, zip, excel)             |

**Schemas:**

| Schema                    | Purpose                                     |
| ------------------------- | ------------------------------------------- |
| `ExportJobCreate`         | Request to create an export job             |
| `ExportJobStartResponse`  | Response with job ID for tracking           |
| `ExportJobProgress`       | Progress info (items, percent, step)        |
| `ExportJobResult`         | Completed export result (path, size, count) |
| `ExportJobResponse`       | Full job status with progress and timing    |
| `ExportJobListResponse`   | Paginated list of export jobs               |
| `ExportJobUpdate`         | Internal schema for updating job progress   |
| `ExportDownloadResponse`  | Download metadata (readiness, URL, size)    |
| `ExportJobCancelResponse` | Cancellation response                       |

---

### Feedback Schemas (`feedback.py`)

Pydantic schemas for event feedback API (NEM-1908).

**Enums:**

| Enum           | Purpose                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `FeedbackType` | Feedback types (accurate, false_positive, missed_threat, severity_wrong) |

**Schemas:**

| Schema                  | Purpose                                 |
| ----------------------- | --------------------------------------- |
| `EventFeedbackCreate`   | Request to submit feedback for an event |
| `EventFeedbackResponse` | Feedback record response                |
| `FeedbackStatsResponse` | Aggregate statistics by type and camera |

---

### Jobs Schemas (`jobs.py`)

Pydantic schemas for background job tracking API (NEM-2390, NEM-2392, NEM-2396).

**Enums:**

| Enum            | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `JobStatusEnum` | Job status (pending, running, completed, failed) |
| `ExportFormat`  | Export formats (csv, json, zip)                  |

**Core Schemas:**

| Schema             | Purpose                                         |
| ------------------ | ----------------------------------------------- |
| `JobResponse`      | Basic job status response                       |
| `JobListResponse`  | Paginated job list                              |
| `JobTypeInfo`      | Job type name and description                   |
| `JobTypesResponse` | List of available job types                     |
| `JobStatsResponse` | Aggregate statistics with counts by status/type |
| `JobStatusCount`   | Count of jobs by status                         |
| `JobTypeCount`     | Count of jobs by type                           |

**Detailed Job Schemas (NEM-2390):**

| Schema              | Purpose                                             |
| ------------------- | --------------------------------------------------- |
| `JobProgressDetail` | Detailed progress (percent, step, items)            |
| `JobTiming`         | Timing info (created, started, completed, duration) |
| `JobRetryInfo`      | Retry info (attempt, max, previous errors)          |
| `JobMetadata`       | Input params and worker ID                          |
| `JobDetailResponse` | Comprehensive job detail with nested schemas        |

**Job Action Schemas:**

| Schema               | Purpose                             |
| -------------------- | ----------------------------------- |
| `ExportJobRequest`   | Request to start an export job      |
| `ExportJobResult`    | Result data for completed export    |
| `JobCancelResponse`  | Cancellation response               |
| `JobAbortResponse`   | Abort response for running jobs     |
| `BulkCancelRequest`  | Request to cancel multiple jobs     |
| `BulkCancelError`    | Error for single job in bulk cancel |
| `BulkCancelResponse` | Summary of bulk cancellation        |

**Job Search Schemas (NEM-2392):**

| Schema                  | Purpose                                         |
| ----------------------- | ----------------------------------------------- |
| `JobSearchAggregations` | Aggregation counts by status and type           |
| `JobSearchResponse`     | Search results with pagination and aggregations |

**Job History Schemas (NEM-2396):**

| Schema                  | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `JobTransitionResponse` | Single state transition record             |
| `JobAttemptResponse`    | Single execution attempt record            |
| `JobHistoryResponse`    | Complete history with transitions/attempts |
| `JobLogEntryResponse`   | Single log entry                           |
| `JobLogsResponse`       | Job logs with pagination                   |

---

### OpenAPI Docs Schemas (`openapi_docs.py`)

OpenAPI documentation helpers and response examples (NEM-1434, NEM-2002).

**Constants:**

| Constant                            | Purpose                                    |
| ----------------------------------- | ------------------------------------------ |
| `SPARSE_FIELDSETS_DESCRIPTION`      | Documentation for sparse fieldsets feature |
| `SPARSE_FIELDSETS_QUERY_PARAM_DOCS` | Query parameter documentation              |

**Example Constants:**

| Constant                             | Purpose                   |
| ------------------------------------ | ------------------------- |
| `EVENT_LIST_RESPONSE_EXAMPLE`        | Full event list response  |
| `EVENT_LIST_SPARSE_RESPONSE_EXAMPLE` | Sparse fieldsets response |
| `CAMERA_LIST_RESPONSE_EXAMPLE`       | Camera list response      |
| `DETECTION_LIST_RESPONSE_EXAMPLE`    | Detection list response   |
| `EVENT_STATS_RESPONSE_EXAMPLE`       | Event stats response      |
| `DETECTION_STATS_RESPONSE_EXAMPLE`   | Detection stats response  |
| `EVENT_RESPONSE_EXAMPLE`             | Single event response     |
| `CAMERA_RESPONSE_EXAMPLE`            | Single camera response    |
| `DETECTION_RESPONSE_EXAMPLE`         | Single detection response |

**Functions:**

| Function                       | Purpose                                    |
| ------------------------------ | ------------------------------------------ |
| `get_sparse_fieldsets_example` | Generate OpenAPI example for fields param  |
| `build_list_responses`         | Build OpenAPI responses for list endpoints |
| `build_detail_responses`       | Build responses for GET by ID endpoints    |
| `build_create_responses`       | Build responses for POST endpoints         |
| `build_update_responses`       | Build responses for PATCH/PUT endpoints    |
| `build_delete_responses`       | Build responses for DELETE endpoints       |
| `build_ai_endpoint_responses`  | Build responses including 502/503 for AI   |

---

### Pagination Schemas (`pagination.py`)

Standard pagination schemas for API responses (NEM-2075).

**Schemas:**

| Schema           | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| `PaginationMeta` | Pagination metadata with offset and cursor support |

**Fields:**

- `total` - Total items matching the query
- `limit` - Maximum items per page
- `offset` - Items skipped (offset pagination)
- `cursor` - Current cursor position (cursor pagination)
- `next_cursor` - Cursor for next page
- `has_more` - Whether more items are available

**Functions:**

| Function                 | Purpose                                      |
| ------------------------ | -------------------------------------------- |
| `create_pagination_meta` | Create PaginationMeta with computed has_more |

---

### Queue Status Schemas (`queue_status.py`)

Pydantic schemas for queue status monitoring API.

**Enums:**

| Enum                | Purpose                                    |
| ------------------- | ------------------------------------------ |
| `QueueHealthStatus` | Health status (healthy, warning, critical) |

**Schemas:**

| Schema                 | Purpose                                |
| ---------------------- | -------------------------------------- |
| `ThroughputMetrics`    | Jobs/minute and avg processing time    |
| `OldestJobInfo`        | Oldest job ID, queued_at, wait_seconds |
| `QueueStatus`          | Single queue status with all metrics   |
| `QueueStatusSummary`   | Aggregated stats across all queues     |
| `QueuesStatusResponse` | Response for GET /api/queues/status    |

---

### Alertmanager Schemas (`alertmanager.py`)

Pydantic schemas for Prometheus Alertmanager webhook integration (NEM-3122).

**Schemas:**

| Schema                         | Purpose                                  |
| ------------------------------ | ---------------------------------------- |
| `AlertmanagerWebhook`          | Incoming Alertmanager webhook payload    |
| `AlertmanagerWebhookResponse`  | Response for webhook acknowledgement     |
| `AlertmanagerAlert`            | Individual alert from Alertmanager       |
| `AlertmanagerAlertLabels`      | Alert labels (alertname, severity, etc.) |
| `AlertmanagerAlertAnnotations` | Alert annotations (summary, description) |

---

### Hierarchy Schemas (`hierarchy.py`)

Pydantic schemas for household organizational hierarchy (NEM-3131, NEM-3132, NEM-3133).

**Schemas:**

| Schema                  | Purpose                        |
| ----------------------- | ------------------------------ |
| `HouseholdCreate`       | Create household request       |
| `HouseholdResponse`     | Household response             |
| `HouseholdUpdate`       | Update household request       |
| `HouseholdListResponse` | Paginated list of households   |
| `PropertyCreate`        | Create property request        |
| `PropertyResponse`      | Property response              |
| `PropertyUpdate`        | Update property request        |
| `PropertyListResponse`  | Paginated list of properties   |
| `AreaCreate`            | Create area request            |
| `AreaResponse`          | Area response                  |
| `AreaUpdate`            | Update area request            |
| `AreaListResponse`      | Paginated list of areas        |
| `AreaCameraResponse`    | Camera linked to area          |
| `AreaCamerasResponse`   | List of cameras in area        |
| `CameraLinkRequest`     | Request to link camera to area |

---

### Household Schemas (`household.py`)

Pydantic schemas for household member and vehicle management (NEM-3018).

**Schemas:**

| Schema                      | Purpose                         |
| --------------------------- | ------------------------------- |
| `HouseholdMemberCreate`     | Create household member         |
| `HouseholdMemberResponse`   | Member response with embeddings |
| `HouseholdMemberUpdate`     | Update household member         |
| `PersonEmbeddingResponse`   | Person embedding details        |
| `AddEmbeddingRequest`       | Add embedding from event        |
| `RegisteredVehicleCreate`   | Create registered vehicle       |
| `RegisteredVehicleResponse` | Vehicle response                |
| `RegisteredVehicleUpdate`   | Update registered vehicle       |

---

### Settings Schemas (`settings_api.py`)

Pydantic schemas for user-configurable system settings (NEM-3119, NEM-3120).

**Schemas:**

| Schema                 | Purpose                           |
| ---------------------- | --------------------------------- |
| `DetectionSettings`    | Detection confidence thresholds   |
| `BatchSettings`        | Batch window and timeout settings |
| `SeveritySettings`     | Risk level threshold settings     |
| `RetentionSettings`    | Data retention period settings    |
| `RateLimitingSettings` | Rate limiting configuration       |
| `QueueSettings`        | Queue size and threshold settings |
| `FeatureSettings`      | Feature flag settings             |
| `SettingsResponse`     | Full settings response            |
| `SettingsUpdate`       | Partial settings update request   |

---

### Summary Schemas (`summaries.py`)

Pydantic schemas for dashboard summaries.

**Schemas:**

| Schema                    | Purpose                               |
| ------------------------- | ------------------------------------- |
| `BulletPointSchema`       | Single bullet point with priority     |
| `StructuredSummarySchema` | Structured summary with bullet points |
| `SummaryResponse`         | Summary response with metadata        |
| `LatestSummariesResponse` | Both hourly and daily summaries       |

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
