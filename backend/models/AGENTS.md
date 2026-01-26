# Database Models - Agent Guide

## Purpose

This directory contains SQLAlchemy 2.0 ORM models for the home security intelligence system. These models define the database schema for tracking cameras, object detections, security events, alerts, zones, activity baselines, GPU performance metrics, application logs, audit trails, and API keys.

## Architecture Overview

- **ORM Framework**: SQLAlchemy 2.0 with modern `Mapped` type hints
- **Database**: PostgreSQL with asyncpg driver (for concurrent access and reliability)
- **Type Safety**: Full type annotations for IDE support and mypy checking
- **Cascade Behavior**: Camera deletion automatically removes dependent records
- **PostgreSQL Features**: Uses JSONB, TSVECTOR, GIN indexes for efficient querying
- **Testing**: Comprehensive unit tests in `/backend/tests/unit/test_models.py`

## Files Overview

```
backend/models/
├── __init__.py              # Module exports (all models and enums)
├── alert.py                 # Alert and AlertRule models for notification system
├── area.py                  # Area/region model for camera coverage areas
├── audit.py                 # AuditLog model for security-sensitive operations
├── baseline.py              # ActivityBaseline and ClassBaseline for anomaly detection
├── camera_calibration.py    # Camera calibration settings model
├── camera.py                # Camera model and Base class definition
├── camera_zone.py           # Camera zone model (CameraZone) for region definitions
├── detection.py             # Object detection results model (with video metadata support)
├── enrichment.py            # Detection enrichment data model
├── entity.py                # Entity model for re-identification tracking (NEM-1880, NEM-2210)
├── enums.py                 # Shared enumerations (Severity, EntityType, TrustStatus)
├── event_audit.py           # AI pipeline audit model for performance tracking
├── event_detection.py       # Junction table for Event-Detection many-to-many relationship
├── event_feedback.py        # User feedback on security events (NEM-1794)
├── event.py                 # Security event model with LLM analysis
├── experiment_result.py     # Experiment/A/B test result tracking model
├── export_job.py            # Export job persistence model
├── gpu_stats.py             # GPU performance metrics model
├── household.py             # Household model for multi-tenant support
├── household_org.py         # Household organization/member model
├── job_attempt.py           # Job execution attempt model (NEM-2396)
├── job_log.py               # Job log entry model (NEM-2396)
├── job.py                   # Background job model for job tracking
├── job_transition.py        # Job state transition model (NEM-2396)
├── log.py                   # Structured application log model
├── notification_preferences.py  # Notification settings models
├── prometheus_alert.py      # Prometheus alerting rules model
├── prompt_config.py         # Current AI prompt configuration (user-editable)
├── prompt_version.py        # AI prompt configuration version tracking (historical)
├── property.py              # Property/location model for multi-site support
├── scene_change.py          # Scene change detection for camera tampering alerts
├── summary.py               # Summary model for dashboard summaries
├── user_calibration.py      # Personalized risk threshold calibration
├── zone.py                  # Zone model (legacy alias for CameraZone)
└── README.md                # Detailed model documentation
```

## `__init__.py` - Module Exports

**Exports:**

- `Base` - SQLAlchemy declarative base for all models
- `Camera` - Camera entity model
- `Detection` - Object detection results model
- `Event` - Security event model
- `EventAudit` - AI pipeline audit model
- `EventDetection`, `event_detections` - Junction table model and SQLAlchemy Table for Event-Detection relationship
- `EventFeedback`, `FeedbackType` - User feedback on security events and feedback type enum (NEM-1794)
- `Alert`, `AlertRule`, `AlertSeverity`, `AlertStatus` - Alerting system models and enums
- `NotificationPreferences` - Global notification settings (singleton)
- `CameraNotificationSetting` - Per-camera notification settings
- `QuietHoursPeriod` - Time periods when notifications are muted
- `RiskLevel`, `NotificationSound`, `DayOfWeek` - Notification-related enums
- `UserCalibration` - Personalized risk threshold calibration
- `Zone`, `ZoneType`, `ZoneShape` - Zone definition models and enums
- `ActivityBaseline`, `ClassBaseline` - Anomaly detection baseline models
- `AuditLog`, `AuditAction`, `AuditStatus` - Audit trail model and enums
- `GPUStats` - GPU performance metrics model
- `Log` - Structured application log model
- `PromptConfig` - Current AI prompt configuration model (user-editable, exported via `__init__.py`)
- `PromptVersion`, `AIModel` - Prompt version tracking model and enum (not re-exported via `__init__.py` - import directly from `backend.models.prompt_version`)
- `SceneChange`, `SceneChangeType` - Scene change detection model and enum
- `Severity`, `CameraStatus` - Shared enumerations
- `Entity`, `EntityType`, `TrustStatus` - Entity re-identification model and enums (NEM-1880, NEM-2210)
- `ExportJob`, `ExportJobStatus`, `ExportType` - Export job persistence model and enums
- `Job`, `JobStatus` - Background job model and status enum
- `JobAttempt`, `JobAttemptStatus` - Job attempt tracking model and enum (NEM-2396)
- `JobLog`, `LogLevel` - Job log model and log level enum (NEM-2396)
- `JobTransition`, `JobTransitionTrigger` - Job transition audit model and enum (NEM-2396)

## `camera.py` - Camera Model

**Model:** `Camera`
**Table:** `cameras`
**Purpose:** Represents physical security cameras in the system

**Fields:**

| Field          | Type                | Description                                     |
| -------------- | ------------------- | ----------------------------------------------- |
| `id`           | str (PK)            | Unique camera identifier (e.g., "front_door")   |
| `name`         | str                 | Human-readable name (e.g., "Front Door Camera") |
| `folder_path`  | str                 | File system path for FTP image uploads          |
| `status`       | str                 | Camera operational status (default: "online")   |
| `created_at`   | datetime            | Camera registration timestamp                   |
| `last_seen_at` | datetime (nullable) | Last activity timestamp                         |

**Relationships:**

- `detections` - One-to-many with Detection (cascade="all, delete-orphan")
- `events` - One-to-many with Event (cascade="all, delete-orphan")

**Helper Functions:**

- `normalize_camera_id(folder_name)` - Converts folder names to valid camera IDs (e.g., "Front Door" -> "front_door")

**Factory Methods:**

- `Camera.from_folder_name(folder_name, folder_path)` - Creates camera with properly normalized ID

**Note:** This file also defines the `Base` class used by all models. The camera ID contract requires `camera.id == normalize_camera_id(folder_name)` for proper file watcher mapping.

## `detection.py` - Detection Model

**Model:** `Detection`
**Table:** `detections`
**Purpose:** Stores individual object detection results from YOLO26v2 AI inference

**Fields:**

| Field            | Type                    | Description                                   |
| ---------------- | ----------------------- | --------------------------------------------- |
| `id`             | int (PK, autoincrement) | Unique detection ID                           |
| `camera_id`      | str (FK->cameras.id)    | Source camera reference                       |
| `file_path`      | str                     | Path to source image/video file               |
| `file_type`      | str (nullable)          | File extension (e.g., "jpg", "mp4")           |
| `detected_at`    | datetime                | Detection timestamp (default: utcnow)         |
| `object_type`    | str (nullable)          | Detected object class (e.g., "person", "car") |
| `confidence`     | float (nullable)        | Detection confidence score (0.0-1.0)          |
| `bbox_x`         | int (nullable)          | Bounding box top-left X coordinate            |
| `bbox_y`         | int (nullable)          | Bounding box top-left Y coordinate            |
| `bbox_width`     | int (nullable)          | Bounding box width                            |
| `bbox_height`    | int (nullable)          | Bounding box height                           |
| `thumbnail_path` | str (nullable)          | Path to cropped detection thumbnail           |

**Video-Specific Metadata:**

| Field          | Type             | Description                           |
| -------------- | ---------------- | ------------------------------------- |
| `media_type`   | str (nullable)   | "image" or "video" (default: "image") |
| `duration`     | float (nullable) | Video duration in seconds             |
| `video_codec`  | str (nullable)   | Video codec (e.g., "h264", "hevc")    |
| `video_width`  | int (nullable)   | Video resolution width                |
| `video_height` | int (nullable)   | Video resolution height               |

**Relationships:**

- `camera` - Many-to-one with Camera

**Indexes:**

- `idx_detections_camera_id` - Single-column index on camera_id
- `idx_detections_detected_at` - Single-column index on detected_at
- `idx_detections_camera_time` - Composite index on (camera_id, detected_at)

## `event.py` - Event Model

**Model:** `Event`
**Table:** `events`
**Purpose:** Represents security events analyzed by Nemotron LLM from batched detections

**Fields:**

| Field           | Type                    | Description                                                |
| --------------- | ----------------------- | ---------------------------------------------------------- |
| `id`            | int (PK, autoincrement) | Unique event ID                                            |
| `batch_id`      | str                     | Batch processing identifier for grouping detections        |
| `camera_id`     | str (FK->cameras.id)    | Source camera reference                                    |
| `started_at`    | datetime                | Event start timestamp                                      |
| `ended_at`      | datetime (nullable)     | Event end timestamp                                        |
| `risk_score`    | int (nullable)          | LLM-determined risk score (0-100)                          |
| `risk_level`    | str (nullable)          | Risk classification ("low", "medium", "high", "critical")  |
| `summary`       | text (nullable)         | LLM-generated event summary                                |
| `reasoning`     | text (nullable)         | LLM reasoning for risk assessment                          |
| `detection_ids` | text (nullable)         | JSON array of detection IDs in this event                  |
| `reviewed`      | bool                    | User review flag (default: False)                          |
| `notes`         | text (nullable)         | User-added notes                                           |
| `is_fast_path`  | bool                    | Fast path flag for high-priority analysis (default: False) |

**Relationships:**

- `camera` - Many-to-one with Camera
- `alerts` - One-to-many with Alert (cascade="all, delete-orphan")

**Indexes:**

- `idx_events_camera_id` - Single-column index on camera_id
- `idx_events_started_at` - Single-column index on started_at
- `idx_events_risk_score` - Single-column index on risk_score
- `idx_events_reviewed` - Single-column index on reviewed
- `idx_events_batch_id` - Single-column index on batch_id
- `idx_events_search_vector` - GIN index for full-text search
- `idx_events_object_types_trgm` - GIN trigram index for LIKE/ILIKE queries on object_types (requires pg_trgm extension)
- `idx_events_risk_level_started_at` - Composite index on (risk_level, started_at) for combined filtering (NEM-1529)
- `idx_events_export_covering` - Covering index for export query with columns: started_at, id, ended_at, risk_level, risk_score, camera_id, object_types, summary (NEM-1535)
- `idx_events_unreviewed` - Partial index on id WHERE reviewed = false for unreviewed count queries (NEM-1536)

**Additional Fields:**

- `object_types` - Cached object types from related detections (comma-separated)
- `clip_path` - Path to generated video clip for this event (optional)
- `search_vector` - PostgreSQL TSVECTOR for full-text search (auto-populated by trigger)

**Methods:**

- `get_severity()` - Returns Severity enum based on risk_score using SeverityService

## `alert.py` - Alert and AlertRule Models

**Model:** `Alert`
**Table:** `alerts`
**Purpose:** Notifications generated from security events based on alert rules

**Fields:**

| Field            | Type                      | Description                                       |
| ---------------- | ------------------------- | ------------------------------------------------- |
| `id`             | UUID (PK)                 | Unique alert ID                                   |
| `event_id`       | int (FK->events.id)       | Source event reference                            |
| `rule_id`        | UUID (FK->alert_rules.id) | Triggering rule reference (nullable)              |
| `severity`       | AlertSeverity enum        | Alert severity (low/medium/high/critical)         |
| `status`         | AlertStatus enum          | Status (pending/delivered/acknowledged/dismissed) |
| `created_at`     | datetime                  | Alert creation timestamp                          |
| `delivered_at`   | datetime (nullable)       | Delivery timestamp                                |
| `channels`       | JSON                      | Notification channels used                        |
| `dedup_key`      | str                       | Deduplication key                                 |
| `alert_metadata` | JSON                      | Additional metadata                               |

**Model:** `AlertRule`
**Table:** `alert_rules`
**Purpose:** Defines conditions for generating alerts

**Condition Fields:**

- `risk_threshold` - Minimum risk score to trigger
- `object_types` - JSON array of object types to match
- `camera_ids` - JSON array of cameras to apply to
- `zone_ids` - JSON array of zones to match
- `min_confidence` - Minimum detection confidence
- `schedule` - Time-based conditions (days, start_time, end_time, timezone)
- `cooldown_seconds` - Deduplication cooldown period (default: 300s)

## `zone.py` - Zone Model

**Model:** `Zone`
**Table:** `zones`
**Purpose:** Defines regions of interest on camera views for detection context

**Fields:**

| Field         | Type                 | Description                              |
| ------------- | -------------------- | ---------------------------------------- |
| `id`          | str (PK)             | Unique zone ID                           |
| `camera_id`   | str (FK->cameras.id) | Parent camera reference                  |
| `name`        | str                  | Human-readable zone name                 |
| `zone_type`   | ZoneType enum        | entry_point/driveway/sidewalk/yard/other |
| `coordinates` | JSONB                | Normalized coordinates (0-1 range)       |
| `shape`       | ZoneShape enum       | rectangle/polygon                        |
| `color`       | str                  | Display color (default: #3B82F6)         |
| `enabled`     | bool                 | Active status                            |
| `priority`    | int                  | Priority for overlapping zones           |
| `created_at`  | datetime             | Creation timestamp                       |
| `updated_at`  | datetime             | Last update timestamp (auto-updated)     |

**Relationships:**

- `camera` - Many-to-one with Camera

**Indexes:**

- `idx_zones_camera_id` - Index on camera_id
- `idx_zones_enabled` - Index on enabled
- `idx_zones_camera_enabled` - Composite index on (camera_id, enabled)

## `baseline.py` - Activity Baseline Models

**Model:** `ActivityBaseline`
**Table:** `activity_baselines`
**Purpose:** Tracks activity rates per camera by hour and day-of-week for anomaly detection

**Key Fields:** `camera_id`, `hour` (0-23), `day_of_week` (0-6), `avg_count`, `sample_count`

**Model:** `ClassBaseline`
**Table:** `class_baselines`
**Purpose:** Tracks frequency of specific object classes per camera and hour

**Key Fields:** `camera_id`, `detection_class`, `hour`, `frequency`, `sample_count`

**Note:** Both use exponential decay for handling seasonal drift with a 30-day rolling window.

## `audit.py` - Audit Log Model

**Model:** `AuditLog`
**Table:** `audit_logs`
**Purpose:** Tracks security-sensitive operations for compliance and debugging

**Fields:**

| Field           | Type                    | Description                              |
| --------------- | ----------------------- | ---------------------------------------- |
| `id`            | int (PK, autoincrement) | Unique audit log ID                      |
| `timestamp`     | datetime                | Action timestamp (UTC)                   |
| `action`        | str                     | Action type (from AuditAction enum)      |
| `resource_type` | str                     | Type of resource (event, settings, etc.) |
| `resource_id`   | str (nullable)          | ID of affected resource                  |
| `actor`         | str                     | Who performed the action                 |
| `ip_address`    | str (nullable)          | Client IP address                        |
| `user_agent`    | text (nullable)         | Client user agent                        |
| `details`       | JSONB                   | Additional action details                |
| `status`        | str                     | success/failure                          |

**AuditAction Types:** EVENT_REVIEWED, EVENT_DISMISSED, SETTINGS_CHANGED, MEDIA_EXPORTED, RULE_CREATED/UPDATED/DELETED, CAMERA_CREATED/UPDATED/DELETED, LOGIN, LOGOUT, API_KEY_CREATED/REVOKED, NOTIFICATION_TEST, DATA_CLEARED

**Indexes:**

- `idx_audit_logs_timestamp` - Index on timestamp
- `idx_audit_logs_action` - Index on action
- `idx_audit_logs_resource_type` - Index on resource_type
- `idx_audit_logs_actor` - Index on actor
- `idx_audit_logs_status` - Index on status
- `idx_audit_logs_resource` - Composite index on (resource_type, resource_id)

## `event_detection.py` - Event Detection Junction Table

**Model:** `EventDetection`
**Table:** `event_detections`
**Purpose:** Junction/association table normalizing the Event-Detection many-to-many relationship

This junction table replaces the legacy `detection_ids` JSON array column in the events table,
providing better query performance, referential integrity, and standard SQL patterns.

**Fields:**

| Field          | Type                        | Description                                              |
| -------------- | --------------------------- | -------------------------------------------------------- |
| `event_id`     | int (PK, FK->events.id)     | Foreign key to events table (CASCADE delete)             |
| `detection_id` | int (PK, FK->detections.id) | Foreign key to detections table (CASCADE delete)         |
| `created_at`   | datetime                    | When the association was created (server default: now()) |

**Relationships:**

- `event` - Many-to-one with Event (back_populates="detection_records")
- `detection` - Many-to-one with Detection (back_populates="event_records")

**Indexes:**

- `idx_event_detections_event_id` - For efficient event-based lookups
- `idx_event_detections_detection_id` - For efficient detection-based lookups
- `idx_event_detections_created_at` - For time-range queries

**Module Exports:**

- `EventDetection` - ORM model class
- `event_detections` - SQLAlchemy Table for use with `secondary` parameter in relationship()

**Migration Notes:**

The migration (`add_event_detections_junction_table.py`) handles both data formats:

- JSON array: `"[1, 2, 3]"`
- Legacy CSV: `"1,2,3"`

The legacy `detection_ids` column is retained for backward compatibility during transition.

## `entity.py` - Entity Model (NEM-1880, NEM-2210, NEM-2431, NEM-2670)

**Model:** `Entity`
**Table:** `entities`
**Purpose:** Tracks unique individuals and objects across cameras using embedding vectors for re-identification.

**Enums in `enums.py`:**

| Enum          | Values                                  | Description            |
| ------------- | --------------------------------------- | ---------------------- |
| `EntityType`  | person, vehicle, animal, package, other | Type of tracked entity |
| `TrustStatus` | trusted, untrusted, unknown             | Trust classification   |

**Fields:**

| Field                  | Type             | Description                                  |
| ---------------------- | ---------------- | -------------------------------------------- |
| `id`                   | UUID (PK)        | Unique entity identifier                     |
| `entity_type`          | str (20 chars)   | Type of entity (person, vehicle, etc.)       |
| `trust_status`         | str (20 chars)   | Trust classification (default: unknown)      |
| `embedding_vector`     | JSONB (nullable) | Feature vector for re-identification         |
| `first_seen_at`        | datetime         | Timestamp of first detection                 |
| `last_seen_at`         | datetime         | Timestamp of most recent detection           |
| `detection_count`      | int              | Total detections linked to this entity       |
| `entity_metadata`      | JSONB (nullable) | Flexible attributes (clothing, vehicle make) |
| `primary_detection_id` | int (nullable)   | Reference to primary/best detection (no FK)  |

**Relationships:**

- `primary_detection` - Optional link to primary Detection (viewonly, no FK constraint)

**Important:** No FK constraint on `primary_detection_id` because `detections` is a partitioned table with composite PK. Application-level validation via `validate_primary_detection_async()`.

**Indexes:**

- `idx_entities_entity_type` - Filter by entity type
- `idx_entities_trust_status` - Filter by trust status
- `idx_entities_first_seen_at` - First seen time queries
- `idx_entities_last_seen_at` - Recent activity queries
- `idx_entities_type_last_seen` - Composite for type + time filtering
- `ix_entities_entity_metadata_gin` - GIN index for JSONB attribute queries

**Constraints:**

- `ck_entities_entity_type` - Valid entity types
- `ck_entities_trust_status` - Valid trust status values
- `ck_entities_detection_count` - Non-negative detection count

**Methods:**

| Method                                         | Purpose                                        |
| ---------------------------------------------- | ---------------------------------------------- |
| `get_trust_status()`                           | Return TrustStatus enum value                  |
| `is_trusted()` / `is_untrusted()`              | Check trust status                             |
| `update_seen(timestamp)`                       | Update last_seen_at, increment detection_count |
| `set_embedding(vector, model)`                 | Set embedding vector with metadata             |
| `get_embedding_vector()`                       | Get raw embedding vector                       |
| `from_detection(...)` (classmethod)            | Factory method to create entity from detection |
| `validate_primary_detection_async(session)`    | Validate detection exists (async)              |
| `set_primary_detection_validated(session, id)` | Set detection with validation                  |

## `export_job.py` - Export Job Model

**Model:** `ExportJob`
**Table:** `export_jobs`
**Purpose:** Tracks background export jobs with progress updates, timing, and results.

**Enums:**

| Enum              | Values                              | Description          |
| ----------------- | ----------------------------------- | -------------------- |
| `ExportJobStatus` | pending, running, completed, failed | Job lifecycle states |
| `ExportType`      | events, alerts, full_backup         | Types of exports     |

**Fields:**

| Field                  | Type                 | Description                      |
| ---------------------- | -------------------- | -------------------------------- |
| `id`                   | UUID (PK)            | Unique job identifier            |
| `status`               | ExportJobStatus enum | Current job status               |
| `export_type`          | str (50 chars)       | Type of export                   |
| `export_format`        | str (20 chars)       | Format (csv, json, zip, excel)   |
| `total_items`          | int (nullable)       | Total items to process           |
| `processed_items`      | int                  | Items processed so far           |
| `progress_percent`     | int                  | Progress percentage (0-100)      |
| `current_step`         | str (nullable)       | Description of current step      |
| `created_at`           | datetime             | Job creation timestamp           |
| `started_at`           | datetime (nullable)  | Job start timestamp              |
| `completed_at`         | datetime (nullable)  | Job completion timestamp         |
| `estimated_completion` | datetime (nullable)  | Estimated completion time        |
| `output_path`          | str (nullable)       | Path to output file              |
| `output_size_bytes`    | int (nullable)       | Output file size                 |
| `error_message`        | text (nullable)      | Error message for failed exports |
| `filter_params`        | text (nullable)      | Filter parameters (JSON string)  |

**Indexes:**

- `idx_export_jobs_status` - Filter by status
- `idx_export_jobs_export_type` - Filter by type
- `idx_export_jobs_created_at` - Time-based queries
- `idx_export_jobs_status_created_at` - Composite for status + time

**Properties:**

| Property           | Description                 |
| ------------------ | --------------------------- |
| `is_complete`      | True if completed or failed |
| `is_running`       | True if currently running   |
| `duration_seconds` | Job duration in seconds     |

## `job.py` - Background Job Model

**Model:** `Job`
**Table:** `jobs`
**Purpose:** Persistent storage for background jobs with tracking, filtering, and retry support.

**Enum:** `JobStatus`

| Value       | Description               |
| ----------- | ------------------------- |
| `queued`    | Waiting to be processed   |
| `running`   | Currently executing       |
| `completed` | Finished successfully     |
| `failed`    | Encountered an error      |
| `cancelled` | Cancelled by user request |

**Fields:**

| Field              | Type                | Description                         |
| ------------------ | ------------------- | ----------------------------------- |
| `id`               | str (36, PK)        | Unique job identifier (UUID)        |
| `job_type`         | str (50 chars)      | Type (export, cleanup, backup, etc) |
| `status`           | str (20 chars)      | Current status                      |
| `queue_name`       | str (nullable)      | Assigned queue name                 |
| `priority`         | int                 | Priority 0-4 (0=highest)            |
| `created_at`       | datetime            | Creation timestamp                  |
| `started_at`       | datetime (nullable) | Start timestamp                     |
| `completed_at`     | datetime (nullable) | Completion timestamp                |
| `progress_percent` | int                 | Progress percentage (0-100)         |
| `current_step`     | str (nullable)      | Current processing step             |
| `result`           | JSONB (nullable)    | Result data for completed jobs      |
| `error_message`    | text (nullable)     | Error message for failed jobs       |
| `error_traceback`  | text (nullable)     | Full traceback for debugging        |
| `attempt_number`   | int                 | Current attempt number (default: 1) |
| `max_attempts`     | int                 | Maximum retry attempts (default: 3) |
| `next_retry_at`    | datetime (nullable) | Next retry timestamp                |

**Indexes:**

- `idx_jobs_status` - Filter by status
- `idx_jobs_job_type` - Filter by job type
- `idx_jobs_created_at` - Time-based queries
- `idx_jobs_queue_name` - Filter by queue
- `idx_jobs_priority` - Priority ordering
- `idx_jobs_status_created_at` - Composite for status + time
- `idx_jobs_job_type_status` - Composite for type + status
- `ix_jobs_created_at_brin` - BRIN index for time-series

**Properties:**

| Property           | Description                               |
| ------------------ | ----------------------------------------- |
| `is_active`        | True if queued or running                 |
| `is_finished`      | True if completed, failed, or cancelled   |
| `can_retry`        | True if failed and has remaining attempts |
| `duration_seconds` | Job duration in seconds                   |

**Methods:**

| Method                           | Purpose                 |
| -------------------------------- | ----------------------- |
| `start()`                        | Mark job as running     |
| `complete(result)`               | Mark job as completed   |
| `fail(error_message, tb)`        | Mark job as failed      |
| `cancel()`                       | Mark job as cancelled   |
| `update_progress(percent, step)` | Update progress         |
| `prepare_retry()`                | Reset for retry attempt |

## `job_attempt.py` - Job Attempt Model (NEM-2396)

**Model:** `JobAttempt`
**Table:** `job_attempts`
**Purpose:** Tracks individual job execution attempts for retry history and debugging.

**Enum:** `JobAttemptStatus`

| Value       | Description       |
| ----------- | ----------------- |
| `started`   | Attempt started   |
| `succeeded` | Attempt succeeded |
| `failed`    | Attempt failed    |
| `cancelled` | Attempt cancelled |

**Fields:**

| Field             | Type                | Description                   |
| ----------------- | ------------------- | ----------------------------- |
| `id`              | UUID (PK)           | Unique attempt identifier     |
| `job_id`          | UUID                | Reference to parent job       |
| `attempt_number`  | int                 | Sequential attempt number     |
| `started_at`      | datetime            | Attempt start timestamp       |
| `ended_at`        | datetime (nullable) | Attempt end timestamp         |
| `status`          | str (20 chars)      | Attempt status                |
| `worker_id`       | str (nullable)      | Worker that processed attempt |
| `error_message`   | text (nullable)     | Error message if failed       |
| `error_traceback` | text (nullable)     | Full traceback if failed      |
| `result`          | JSONB (nullable)    | Result data if successful     |

**Indexes:**

- `idx_job_attempts_job_attempt` - Composite for job_id + attempt_number
- `idx_job_attempts_status` - Filter by status
- `ix_job_attempts_started_at_brin` - BRIN index for time-series

**Properties:**

- `duration_seconds` - Attempt duration in seconds

## `job_log.py` - Job Log Model (NEM-2396)

**Model:** `JobLog`
**Table:** `job_logs`
**Purpose:** Stores log entries generated during job execution for debugging and audit trails.

**Enum:** `LogLevel`

| Value     | Description   |
| --------- | ------------- |
| `debug`   | Debug level   |
| `info`    | Info level    |
| `warning` | Warning level |
| `error`   | Error level   |

**Fields:**

| Field            | Type             | Description                     |
| ---------------- | ---------------- | ------------------------------- |
| `id`             | UUID (PK)        | Unique log entry identifier     |
| `job_id`         | UUID             | Reference to parent job         |
| `attempt_number` | int              | Which attempt generated the log |
| `timestamp`      | datetime         | Log entry timestamp             |
| `level`          | str (10 chars)   | Log level                       |
| `message`        | text             | Log message                     |
| `context`        | JSONB (nullable) | Optional structured context     |

**Indexes:**

- `idx_job_logs_job_attempt` - Composite for job_id + attempt_number
- `idx_job_logs_level` - Filter by level
- `idx_job_logs_job_timestamp` - Composite for time range queries
- `ix_job_logs_timestamp_brin` - BRIN index for time-series

## `job_transition.py` - Job Transition Model (NEM-2396)

**Model:** `JobTransition`
**Table:** `job_transitions`
**Purpose:** Records all job state transitions for audit trails and debugging.

**Enum:** `JobTransitionTrigger`

| Value     | Description                          |
| --------- | ------------------------------------ |
| `worker`  | Background worker initiated          |
| `user`    | User action (cancel, retry)          |
| `timeout` | Timeout-based transition             |
| `retry`   | Retry mechanism initiated            |
| `system`  | System-initiated (cleanup, recovery) |

**Fields:**

| Field             | Type            | Description                   |
| ----------------- | --------------- | ----------------------------- |
| `id`              | UUID (PK)       | Unique transition identifier  |
| `job_id`          | str (36 chars)  | Reference to parent job       |
| `from_status`     | str (50 chars)  | Previous status               |
| `to_status`       | str (50 chars)  | New status                    |
| `transitioned_at` | datetime        | Transition timestamp          |
| `triggered_by`    | str (50 chars)  | What triggered the transition |
| `metadata_json`   | text (nullable) | Optional metadata JSON        |

**Indexes:**

- `idx_job_transitions_job_id` - Filter by job
- `idx_job_transitions_transitioned_at` - Time-based queries
- `idx_job_transitions_job_id_transitioned_at` - Composite for job + time

## `event_audit.py` - Event Audit Model

**Model:** `EventAudit`
**Table:** `event_audits`
**Purpose:** Tracks AI pipeline performance on events including model contributions, quality scores, and prompt improvement suggestions

**Fields:**

| Field        | Type                    | Description                                     |
| ------------ | ----------------------- | ----------------------------------------------- |
| `id`         | int (PK, autoincrement) | Unique audit ID                                 |
| `event_id`   | int (FK->events.id)     | Source event reference (unique, cascade delete) |
| `audited_at` | datetime                | Audit timestamp (UTC)                           |

**Model Contribution Flags:**

| Field               | Type | Description                         |
| ------------------- | ---- | ----------------------------------- |
| `has_yolo26`        | bool | YOLO26 object detection contributed |
| `has_florence`      | bool | Florence-2 vision attributes used   |
| `has_clip`          | bool | CLIP embeddings used                |
| `has_violence`      | bool | Violence detection ran              |
| `has_clothing`      | bool | Clothing analysis ran               |
| `has_vehicle`       | bool | Vehicle classification ran          |
| `has_pet`           | bool | Pet classification ran              |
| `has_weather`       | bool | Weather classification ran          |
| `has_image_quality` | bool | Image quality assessment ran        |
| `has_zones`         | bool | Zone analysis contributed           |
| `has_baseline`      | bool | Baseline comparison ran             |
| `has_cross_camera`  | bool | Cross-camera correlation ran        |

**Prompt Metrics:**

| Field                    | Type  | Description                        |
| ------------------------ | ----- | ---------------------------------- |
| `prompt_length`          | int   | Length of the prompt sent to LLM   |
| `prompt_token_estimate`  | int   | Estimated token count              |
| `enrichment_utilization` | float | Percentage of enrichment data used |

**Self-Evaluation Scores (1-5 scale):**

| Field                       | Type             | Description                     |
| --------------------------- | ---------------- | ------------------------------- |
| `context_usage_score`       | float (nullable) | How well context was used       |
| `reasoning_coherence_score` | float (nullable) | Logical coherence of reasoning  |
| `risk_justification_score`  | float (nullable) | Quality of risk justification   |
| `consistency_score`         | float (nullable) | Consistency with similar events |
| `overall_quality_score`     | float (nullable) | Overall quality score           |

**Consistency Check:**

| Field                    | Type           | Description                       |
| ------------------------ | -------------- | --------------------------------- |
| `consistency_risk_score` | int (nullable) | Risk score from consistency check |
| `consistency_diff`       | int (nullable) | Difference from original score    |

**Self-Evaluation Text:**

| Field                | Type            | Description                     |
| -------------------- | --------------- | ------------------------------- |
| `self_eval_critique` | text (nullable) | Self-critique text              |
| `self_eval_prompt`   | text (nullable) | Prompt used for self-evaluation |
| `self_eval_response` | text (nullable) | LLM response to self-evaluation |

**Prompt Improvement Suggestions (JSON arrays as text):**

| Field                | Type            | Description                    |
| -------------------- | --------------- | ------------------------------ |
| `missing_context`    | text (nullable) | Missing context suggestions    |
| `confusing_sections` | text (nullable) | Confusing sections identified  |
| `unused_data`        | text (nullable) | Unused enrichment data         |
| `format_suggestions` | text (nullable) | Format improvement suggestions |
| `model_gaps`         | text (nullable) | Missing model recommendations  |

**Relationships:**

- `event` - One-to-one with Event (back_populates="audit")

**Indexes:**

- `idx_event_audits_event_id` - Index on event_id
- `idx_event_audits_audited_at` - Index on audited_at
- `idx_event_audits_overall_score` - Index on overall_quality_score

**Properties:**

- `is_fully_evaluated` - Returns True if overall_quality_score is not None

## `prompt_version.py` - Prompt Version Model

**Model:** `PromptVersion`
**Table:** `prompt_versions`
**Purpose:** Version tracking for AI model prompt configurations with rollback support

**Enum:** `AIModel`

| Value          | Description                        |
| -------------- | ---------------------------------- |
| `nemotron`     | Nemotron LLM risk analysis model   |
| `florence2`    | Florence-2 scene analysis model    |
| `yolo_world`   | YOLO-World custom object detection |
| `xclip`        | X-CLIP action recognition model    |
| `fashion_clip` | Fashion-CLIP clothing analysis     |

**Fields:**

| Field                | Type                    | Description                        |
| -------------------- | ----------------------- | ---------------------------------- |
| `id`                 | int (PK, autoincrement) | Unique version ID                  |
| `model`              | AIModel enum            | Which AI model this config is for  |
| `version`            | int                     | Version number                     |
| `created_at`         | datetime                | Version creation timestamp (UTC)   |
| `created_by`         | str (255, nullable)     | Who created this version           |
| `config_json`        | text                    | Configuration as JSON string       |
| `change_description` | text (nullable)         | Description of what changed        |
| `is_active`          | bool                    | Whether this is the active version |

**Configuration Formats by Model:**

- **Nemotron:** `{"system_prompt": "..."}`
- **Florence2:** `{"queries": ["..."]}`
- **YOLO-World:** `{"classes": ["..."], "confidence_threshold": 0.35}`
- **X-CLIP:** `{"action_classes": ["..."]}`
- **Fashion-CLIP:** `{"clothing_categories": ["..."]}`

**Indexes:**

- `idx_prompt_versions_model` - Index on model
- `idx_prompt_versions_model_version` - Composite index on (model, version)
- `idx_prompt_versions_model_active` - Composite index on (model, is_active)
- `idx_prompt_versions_created_at` - Index on created_at

**Properties and Methods:**

- `config` - Property that parses config_json and returns as dict
- `set_config(config)` - Method to set config from dict, serializing to JSON

## `scene_change.py` - Scene Change Model

**Model:** `SceneChange`
**Table:** `scene_changes`
**Purpose:** Tracks detected camera view changes that may indicate tampering, angle changes, or blocked views

**Enum:** `SceneChangeType`

| Value           | Description                     |
| --------------- | ------------------------------- |
| `view_blocked`  | Camera view is blocked/obscured |
| `angle_changed` | Camera angle has changed        |
| `view_tampered` | Camera view has been tampered   |
| `unknown`       | Unknown type of scene change    |

**Fields:**

| Field              | Type                    | Description                                         |
| ------------------ | ----------------------- | --------------------------------------------------- |
| `id`               | int (PK, autoincrement) | Unique scene change ID                              |
| `camera_id`        | str (FK->cameras.id)    | Source camera reference (cascade delete)            |
| `detected_at`      | datetime                | Detection timestamp (UTC)                           |
| `change_type`      | SceneChangeType enum    | Type of change detected                             |
| `similarity_score` | float                   | SSIM score (0-1, 1=identical, lower=more different) |
| `acknowledged`     | bool                    | Whether change has been acknowledged                |
| `acknowledged_at`  | datetime (nullable)     | When change was acknowledged                        |
| `file_path`        | str (nullable)          | Path to triggering image                            |

**Relationships:**

- `camera` - Many-to-one with Camera (back_populates="scene_changes")

**Indexes:**

- `idx_scene_changes_camera_id` - Index on camera_id
- `idx_scene_changes_detected_at` - Index on detected_at
- `idx_scene_changes_acknowledged` - Index on acknowledged
- `idx_scene_changes_camera_acknowledged` - Composite index on (camera_id, acknowledged)

**Note:** Scene changes are detected by the SceneChangeDetector service using SSIM (Structural Similarity Index) comparison against a stored baseline image.

## `enums.py` - Shared Enumerations

### CameraStatus Enum

Indicates the operational state of a camera:

- `ONLINE` - Camera is active and receiving images
- `OFFLINE` - Camera is not currently active
- `ERROR` - Camera is experiencing an error condition
- `UNKNOWN` - Camera status cannot be determined

### Severity Enum

Maps risk scores to severity levels (configurable thresholds):

- `LOW` - 0-29 (routine activity)
- `MEDIUM` - 30-59 (notable activity)
- `HIGH` - 60-84 (concerning activity)
- `CRITICAL` - 85-100 (immediate attention)

## `gpu_stats.py` - GPU Statistics Model

**Model:** `GPUStats`
**Table:** `gpu_stats`
**Purpose:** Time-series tracking of NVIDIA RTX A5500 GPU performance during AI inference

**Fields:**

| Field             | Type                    | Description                           |
| ----------------- | ----------------------- | ------------------------------------- |
| `id`              | int (PK, autoincrement) | Unique stats record ID                |
| `recorded_at`     | datetime                | Recording timestamp (default: utcnow) |
| `gpu_name`        | str (nullable)          | GPU name (e.g., "NVIDIA RTX A5500")   |
| `gpu_utilization` | float (nullable)        | GPU utilization percentage (0-100)    |
| `memory_used`     | int (nullable)          | GPU memory used in MB                 |
| `memory_total`    | int (nullable)          | Total GPU memory in MB                |
| `temperature`     | float (nullable)        | GPU temperature in Celsius            |
| `power_usage`     | float (nullable)        | Power usage in Watts                  |
| `inference_fps`   | float (nullable)        | Inference throughput in FPS           |

**Indexes:**

- `idx_gpu_stats_recorded_at` - Single-column index on recorded_at for time-series queries

**Note:** Standalone table with no foreign key relationships.

## `log.py` - Log Model

**Model:** `Log`
**Table:** `logs`
**Purpose:** Stores structured application logs for admin UI queries and debugging

**Fields:**

| Field       | Type                    | Description                                       |
| ----------- | ----------------------- | ------------------------------------------------- |
| `id`        | int (PK, autoincrement) | Unique log record ID                              |
| `timestamp` | datetime                | Log entry timestamp (server_default=func.now())   |
| `level`     | str (10 chars)          | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `component` | str (50 chars)          | Logger name (typically module `__name__`)         |
| `message`   | text                    | Formatted log message                             |

**Structured Metadata (nullable, for filtering):**

| Field          | Type                      | Description            |
| -------------- | ------------------------- | ---------------------- |
| `camera_id`    | str (100 chars, nullable) | Camera reference       |
| `event_id`     | int (nullable)            | Event reference        |
| `request_id`   | str (36 chars, nullable)  | Request correlation ID |
| `detection_id` | int (nullable)            | Detection reference    |

**Performance/Debug Fields:**

| Field         | Type            | Description                        |
| ------------- | --------------- | ---------------------------------- |
| `duration_ms` | int (nullable)  | Operation duration in milliseconds |
| `extra`       | JSON (nullable) | Additional structured context      |

**Source Tracking:**

| Field        | Type            | Description                                              |
| ------------ | --------------- | -------------------------------------------------------- |
| `source`     | str (10 chars)  | Log source: "backend" or "frontend" (default: "backend") |
| `user_agent` | text (nullable) | Browser user agent for frontend logs                     |

**Indexes:**

- `idx_logs_timestamp` - Index on timestamp for time-range queries
- `idx_logs_level` - Index on level for filtering by severity
- `idx_logs_component` - Index on component for filtering by module
- `idx_logs_camera_id` - Index on camera_id for camera-specific queries
- `idx_logs_source` - Index on source for backend/frontend filtering

**Note:** Standalone table with no foreign key relationships for reliability.

- Stores both backend and frontend logs in unified table
- JSON extra field allows arbitrary structured context
- Source field enables log separation in admin UI
- Indexes optimized for common dashboard filter patterns
- No foreign keys - standalone logging table for reliability
- Written by `DatabaseHandler` in `backend/core/logging.py`
- Frontend logs submitted via `POST /api/logs/frontend` endpoint

## `prompt_config.py` - Prompt Configuration Model

### Purpose

Stores the current (active) configuration for AI model prompts, allowing users to customize system prompts, temperature, and max_tokens settings through the admin UI.

**Note:** This is distinct from `PromptVersion` (which tracks historical versions). `PromptConfig` stores the **current** configuration that is actively used by the AI pipeline.

### Model: `PromptConfig`

**Table:** `prompt_configs`

**Fields:**

| Field           | Type                    | Description                                          |
| --------------- | ----------------------- | ---------------------------------------------------- |
| `id`            | int (PK, autoincrement) | Unique config ID                                     |
| `model`         | str (50 chars)          | Model name (unique index)                            |
| `system_prompt` | text                    | Full system prompt text for the model                |
| `temperature`   | float                   | LLM temperature setting (0-2, default: 0.7)          |
| `max_tokens`    | int                     | Maximum tokens in response (100-8192, default: 2048) |
| `version`       | int                     | Auto-incrementing version number (default: 1)        |
| `created_at`    | datetime                | When the config was first created (UTC)              |
| `updated_at`    | datetime                | When the config was last updated (UTC)               |

**Supported Models:**

- `nemotron` - Nemotron LLM risk analysis model
- `florence-2` - Florence-2 scene analysis model
- `yolo-world` - YOLO-World custom object detection
- `x-clip` - X-CLIP action recognition model
- `fashion-clip` - Fashion-CLIP clothing analysis

**Indexes:**

- `idx_prompt_configs_model` - Unique index on model (one config per model)
- `idx_prompt_configs_updated_at` - Index on updated_at for audit queries

### Version Tracking

Each time a configuration is updated:

1. The `version` field is incremented
2. The `updated_at` timestamp is updated
3. A new `PromptVersion` record is created for historical tracking

This provides both:

- **Current state**: `PromptConfig` table (one row per model)
- **Historical audit trail**: `PromptVersion` table (all versions over time)

### Usage

**Fetching Current Configuration:**

```python
from sqlalchemy import select
from backend.models import PromptConfig

async with get_session() as session:
    result = await session.execute(
        select(PromptConfig).where(PromptConfig.model == "nemotron")
    )
    config = result.scalar_one_or_none()

    if config:
        print(f"System Prompt: {config.system_prompt}")
        print(f"Temperature: {config.temperature}")
        print(f"Max Tokens: {config.max_tokens}")
        print(f"Version: {config.version}")
```

**Updating Configuration:**

```python
async with get_session() as session:
    result = await session.execute(
        select(PromptConfig).where(PromptConfig.model == "nemotron")
    )
    config = result.scalar_one_or_none()

    if config:
        config.system_prompt = "Updated prompt..."
        config.temperature = 0.8
        config.version += 1  # Increment version
        await session.commit()
```

**Creating Initial Configuration:**

```python
from backend.models import PromptConfig

async with get_session() as session:
    config = PromptConfig(
        model="nemotron",
        system_prompt="You are a security analyst...",
        temperature=0.7,
        max_tokens=2048,
    )
    session.add(config)
    await session.commit()
```

### Integration with Admin UI

The admin UI provides a "Prompt Configuration" page where users can:

- View current prompts for all models
- Edit system prompts in a text editor
- Adjust temperature and max_tokens sliders
- See version history (links to `PromptVersion` records)
- Preview prompt changes before saving
- Rollback to previous versions

**API Endpoints:**

- `GET /api/admin/prompts` - List all prompt configurations
- `GET /api/admin/prompts/{model}` - Get specific model config
- `PUT /api/admin/prompts/{model}` - Update model config
- `GET /api/admin/prompts/{model}/history` - View version history

### Relationship to PromptVersion

| Model           | Purpose                     | Records per Model  |
| --------------- | --------------------------- | ------------------ |
| `PromptConfig`  | Current active config       | 1 (singleton)      |
| `PromptVersion` | Historical version tracking | Many (audit trail) |

When updating a `PromptConfig`:

1. Update the `PromptConfig` record (in-place update)
2. Create a new `PromptVersion` record (snapshot)
3. Increment the `version` field in both tables

This pattern provides:

- **Fast lookups**: Query `PromptConfig` for current state (no sorting required)
- **Audit trail**: Query `PromptVersion` for history and rollback capability
- **Version consistency**: Both tables track the same version number

## `event_feedback.py` - Event Feedback Model (NEM-1794)

**Model:** `EventFeedback`
**Table:** `event_feedback`
**Purpose:** Tracks user feedback on security events for calibrating personalized risk thresholds

**Enum:** `FeedbackType`

| Value            | Description                                       |
| ---------------- | ------------------------------------------------- |
| `CORRECT`        | The alert was accurate and appropriately flagged  |
| `FALSE_POSITIVE` | Event was incorrectly flagged as concerning       |
| `MISSED_THREAT`  | A real threat was not detected (missed detection) |
| `SEVERITY_WRONG` | Threat detected but severity level was incorrect  |

**Fields:**

| Field               | Type                    | Description                                               |
| ------------------- | ----------------------- | --------------------------------------------------------- |
| `id`                | int (PK, autoincrement) | Unique feedback ID                                        |
| `event_id`          | int (FK->events.id)     | Source event reference (unique, cascade delete)           |
| `feedback_type`     | FeedbackType enum       | Type of feedback (correct/false_positive/etc.)            |
| `notes`             | text (nullable)         | Optional user notes                                       |
| `expected_severity` | str (nullable)          | For severity_wrong: expected severity (low/med/high/crit) |
| `created_at`        | datetime (timezone)     | Feedback creation timestamp (UTC)                         |

**Relationships:**

- `event` - One-to-one with Event (back_populates="feedback")

**Indexes:**

- `idx_event_feedback_event_id` - Index on event_id for event lookups
- `idx_event_feedback_type` - Index on feedback_type for filtering by type
- `idx_event_feedback_created_at` - Index on created_at for time-based queries

**Constraints:**

- `ck_event_feedback_type` - CHECK constraint for valid feedback types (correct, false_positive, missed_threat, severity_wrong)
- `ck_event_feedback_expected_severity` - CHECK constraint for expected_severity values (NULL or low/medium/high/critical)

## `notification_preferences.py` - Notification Models

### Model: `NotificationPreferences`

**Table:** `notification_preferences`
**Purpose:** Global notification settings (singleton table with id=1)

**Enums:**

| Enum                | Values                              | Description                   |
| ------------------- | ----------------------------------- | ----------------------------- |
| `RiskLevel`         | CRITICAL, HIGH, MEDIUM, LOW         | Risk level categories         |
| `NotificationSound` | NONE, DEFAULT, ALERT, CHIME, URGENT | Available notification sounds |
| `DayOfWeek`         | MONDAY through SUNDAY               | Days for quiet hours config   |

**Fields:**

| Field          | Type       | Description                                      |
| -------------- | ---------- | ------------------------------------------------ |
| `id`           | int (PK)   | Always 1 (singleton constraint)                  |
| `enabled`      | bool       | Master notification toggle                       |
| `sound`        | str        | Notification sound (from NotificationSound enum) |
| `risk_filters` | ARRAY(str) | Risk levels that trigger notifications           |

**Constraints:**

- `ck_notification_preferences_singleton` - CHECK(id = 1) ensures singleton
- `ck_notification_preferences_sound` - CHECK for valid sound values

**Default Values:**

- `enabled`: True
- `sound`: "default"
- `risk_filters`: ["critical", "high", "medium"]

### Model: `CameraNotificationSetting`

**Table:** `camera_notification_settings`
**Purpose:** Per-camera notification settings for individual camera configuration

**Fields:**

| Field            | Type                 | Description                                 |
| ---------------- | -------------------- | ------------------------------------------- |
| `id`             | UUID (PK)            | Unique setting ID                           |
| `camera_id`      | str (FK->cameras.id) | Camera reference (unique, cascade delete)   |
| `enabled`        | bool                 | Notifications enabled for this camera       |
| `risk_threshold` | int                  | Minimum risk score to trigger notifications |

**Relationships:**

- `camera` - Many-to-one with Camera (backref="notification_setting")

**Indexes:**

- `idx_camera_notification_settings_camera_id` - Unique index on camera_id

**Constraints:**

- `ck_camera_notification_settings_risk_threshold` - CHECK(risk_threshold >= 0 AND <= 100)

### Model: `QuietHoursPeriod`

**Table:** `quiet_hours_periods`
**Purpose:** Defines time ranges when notifications are muted

**Fields:**

| Field        | Type       | Description                        |
| ------------ | ---------- | ---------------------------------- |
| `id`         | UUID (PK)  | Unique period ID                   |
| `label`      | str        | Human-readable name for the period |
| `start_time` | time       | Start of quiet period              |
| `end_time`   | time       | End of quiet period                |
| `days`       | ARRAY(str) | Days when this period is active    |

**Indexes:**

- `idx_quiet_hours_periods_start_end` - Composite index on (start_time, end_time)

**Constraints:**

- `ck_quiet_hours_periods_time_range` - CHECK(start_time < end_time)

**Default Values:**

- `days`: All days of the week

## `user_calibration.py` - User Calibration Model

**Model:** `UserCalibration`
**Table:** `user_calibration`
**Purpose:** Stores personalized risk thresholds that adapt based on user feedback

**Fields:**

| Field                  | Type                    | Description                                   |
| ---------------------- | ----------------------- | --------------------------------------------- |
| `id`                   | int (PK, autoincrement) | Unique calibration ID                         |
| `user_id`              | str (unique)            | User identifier (one calibration per user)    |
| `low_threshold`        | int                     | Low risk threshold (default: 30)              |
| `medium_threshold`     | int                     | Medium risk threshold (default: 60)           |
| `high_threshold`       | int                     | High/critical threshold (default: 85)         |
| `decay_factor`         | float                   | Learning rate for adjustments (default: 0.1)  |
| `correct_count`        | int                     | Count of correct feedback (default: 0)        |
| `false_positive_count` | int                     | Count of false positive feedback (default: 0) |
| `missed_threat_count`  | int                     | Count of missed threat feedback (default: 0)  |
| `severity_wrong_count` | int                     | Count of severity wrong feedback (default: 0) |
| `created_at`           | datetime (timezone)     | Creation timestamp (UTC)                      |
| `updated_at`           | datetime (timezone)     | Last update timestamp (auto-updated)          |

**Indexes:**

- `idx_user_calibration_user_id` - Index on user_id for user lookups

**Constraints:**

- `ck_user_calibration_low_range` - CHECK(low_threshold >= 0 AND <= 100)
- `ck_user_calibration_medium_range` - CHECK(medium_threshold >= 0 AND <= 100)
- `ck_user_calibration_high_range` - CHECK(high_threshold >= 0 AND <= 100)
- `ck_user_calibration_threshold_order` - CHECK(low < medium < high)
- `ck_user_calibration_decay_range` - CHECK(decay_factor >= 0.0 AND <= 1.0)
- `ck_user_calibration_correct_count` - CHECK(correct_count >= 0)
- `ck_user_calibration_fp_count` - CHECK(false_positive_count >= 0)
- `ck_user_calibration_mt_count` - CHECK(missed_threat_count >= 0)
- `ck_user_calibration_sw_count` - CHECK(severity_wrong_count >= 0)

**Default Thresholds:**

- 0-29: Low risk
- 30-59: Medium risk
- 60-84: High risk
- 85-100: Critical risk

**Note:** This model works in conjunction with EventFeedback to provide adaptive risk thresholds. When users provide feedback, the thresholds adjust based on the decay_factor.

## SQLAlchemy Patterns Used

### Modern SQLAlchemy 2.0 Syntax

```python
from sqlalchemy.orm import Mapped, mapped_column

class Camera(Base):
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### Type-Checked Relationships

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .detection import Detection

class Camera(Base):
    detections: Mapped[list["Detection"]] = relationship(
        "Detection", back_populates="camera", cascade="all, delete-orphan"
    )
```

### Foreign Key Cascade Deletes

```python
camera_id: Mapped[str] = mapped_column(
    String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
)
```

### Composite Indexes

```python
__table_args__ = (
    Index("idx_detections_camera_id", "camera_id"),
    Index("idx_detections_detected_at", "detected_at"),
    Index("idx_detections_camera_time", "camera_id", "detected_at"),
)
```

## Database Relationships

```
Camera (1) ----< (many) Detection
Camera (1) ----< (many) Event
Camera (1) ----< (many) Zone
Camera (1) ----< (many) SceneChange
Camera (1) ----< (many) ActivityBaseline (via backref)
Camera (1) ----< (many) ClassBaseline (via backref)
Camera (1) ---- (one) CameraNotificationSetting (via backref)

Event (1) ----< (many) Alert
Event (1) ---- (one) EventAudit
Event (1) ---- (one) EventFeedback
Event (1) ----< (many) EventDetection (junction table)

Detection (1) ----< (many) EventDetection (junction table)

AlertRule (1) ----< (many) Alert

GPUStats (standalone, no foreign key relationships)
PromptConfig (standalone, no foreign key relationships - current AI prompt configuration)
PromptVersion (standalone, no foreign key relationships - historical prompt versions)
Log (standalone, no foreign key relationships - for reliability)
AuditLog (standalone, no foreign key relationships)
EventDetection (junction table between Event and Detection)
EventFeedback (one-to-one with Event for user feedback)
NotificationPreferences (standalone singleton - global notification settings)
CameraNotificationSetting (one-to-one with Camera for per-camera notification settings)
QuietHoursPeriod (standalone - quiet hours configuration)
UserCalibration (standalone - personalized risk thresholds)
Entity (standalone - re-identification tracking with optional Detection link)
ExportJob (standalone - export job tracking)
Job (standalone - background job tracking)
JobAttempt (references Job by UUID - job execution attempts)
JobLog (references Job by UUID - job execution logs)
JobTransition (references Job by id - job state transitions)
```

**Cascade Behavior:**

- Deleting a Camera cascades to delete all its Detections, Events, Zones, SceneChanges, Baselines, and CameraNotificationSetting
- Deleting an Event or Detection cascades to delete EventDetection junction records
- Deleting an Event cascades to delete all its Alerts, EventAudit, and EventFeedback
- Deleting an AlertRule sets Alert.rule_id to NULL (SET NULL on delete)
- `cascade="all, delete-orphan"` ensures orphaned records are removed

## Indexing Strategy

### Detection Table

1. **Camera queries**: `idx_detections_camera_id` - List detections by camera
2. **Time queries**: `idx_detections_detected_at` - Time-range filtering
3. **Combined queries**: `idx_detections_camera_time` - Camera-specific time ranges

### Event Table

1. **Camera queries**: `idx_events_camera_id` - Events by camera
2. **Time queries**: `idx_events_started_at` - Event timeline
3. **Risk filtering**: `idx_events_risk_score` - High-risk event queries
4. **Workflow**: `idx_events_reviewed` - Unreviewed event queries
5. **Batch tracking**: `idx_events_batch_id` - Batch processing audit

### Log Table

1. **Time queries**: `idx_logs_timestamp` - Log timeline
2. **Severity filtering**: `idx_logs_level` - Filter by log level
3. **Component filtering**: `idx_logs_component` - Filter by module
4. **Camera filtering**: `idx_logs_camera_id` - Camera-specific logs
5. **Source filtering**: `idx_logs_source` - Backend vs frontend separation

## Usage Example

```python
from backend.models import Base, Camera, Detection, Event, GPUStats, Log
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Initialize database (async)
from backend.core.database import init_db
await init_db()  # Creates all tables in PostgreSQL

# Create camera
with Session(engine) as session:
    camera = Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door"
    )
    session.add(camera)
    session.commit()

    # Add detection
    detection = Detection(
        camera_id="front_door",
        file_path="/export/foscam/front_door/20250101_120000.jpg",
        object_type="person",
        confidence=0.95
    )
    session.add(detection)
    session.commit()
```

## Testing

Run model tests:

```bash
pytest backend/tests/unit/test_models.py -v
pytest backend/tests/unit/test_models.py --cov=backend.models
```

## Related Documentation

- `/backend/AGENTS.md` - Backend architecture overview
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/core/database.py` - Database connection and session management
