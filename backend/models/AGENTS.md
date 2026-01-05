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
├── __init__.py       # Module exports (all models and enums)
├── camera.py         # Camera model and Base class definition
├── detection.py      # Object detection results model (with video metadata support)
├── event.py          # Security event model with LLM analysis
├── event_audit.py    # AI pipeline audit model for performance tracking
├── alert.py          # Alert and AlertRule models for notification system
├── zone.py           # Zone model for camera region definitions
├── baseline.py       # ActivityBaseline and ClassBaseline for anomaly detection
├── audit.py          # AuditLog model for security-sensitive operations
├── gpu_stats.py      # GPU performance metrics model
├── log.py            # Structured application log model
├── api_key.py        # API key authentication model
├── prompt_version.py # AI prompt configuration version tracking
├── scene_change.py   # Scene change detection for camera tampering alerts
├── enums.py          # Shared enumerations (Severity)
└── README.md         # Detailed model documentation
```

## `__init__.py` - Module Exports

**Exports:**

- `Base` - SQLAlchemy declarative base for all models
- `Camera` - Camera entity model
- `Detection` - Object detection results model
- `Event` - Security event model
- `EventAudit` - AI pipeline audit model
- `Alert`, `AlertRule`, `AlertSeverity`, `AlertStatus` - Alerting system models and enums
- `Zone`, `ZoneType`, `ZoneShape` - Zone definition models and enums
- `ActivityBaseline`, `ClassBaseline` - Anomaly detection baseline models
- `AuditLog`, `AuditAction`, `AuditStatus` - Audit trail model and enums
- `GPUStats` - GPU performance metrics model
- `Log` - Structured application log model
- `APIKey` - API key authentication model
- `PromptVersion`, `AIModel` - Prompt version tracking model and enum (not re-exported via `__init__.py` - import directly from `backend.models.prompt_version`)
- `SceneChange`, `SceneChangeType` - Scene change detection model and enum
- `Severity`, `CameraStatus` - Shared enumerations

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
**Purpose:** Stores individual object detection results from RT-DETRv2 AI inference

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

| Field               | Type | Description                          |
| ------------------- | ---- | ------------------------------------ |
| `has_rtdetr`        | bool | RT-DETR object detection contributed |
| `has_florence`      | bool | Florence-2 vision attributes used    |
| `has_clip`          | bool | CLIP embeddings used                 |
| `has_violence`      | bool | Violence detection ran               |
| `has_clothing`      | bool | Clothing analysis ran                |
| `has_vehicle`       | bool | Vehicle classification ran           |
| `has_pet`           | bool | Pet classification ran               |
| `has_weather`       | bool | Weather classification ran           |
| `has_image_quality` | bool | Image quality assessment ran         |
| `has_zones`         | bool | Zone analysis contributed            |
| `has_baseline`      | bool | Baseline comparison ran              |
| `has_cross_camera`  | bool | Cross-camera correlation ran         |

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

## `api_key.py` - API Key Model

**Model:** `APIKey`
**Table:** `api_keys`
**Purpose:** Manages API key authentication when enabled in settings

**Fields:**

| Field        | Type                            | Description                         |
| ------------ | ------------------------------- | ----------------------------------- |
| `id`         | int (PK, autoincrement)         | Unique API key record ID            |
| `key_hash`   | str (64 chars, unique, indexed) | SHA-256 hash of the API key         |
| `name`       | str (100 chars)                 | Human-readable name for the API key |
| `created_at` | datetime (with timezone)        | Key creation timestamp (UTC)        |
| `is_active`  | bool                            | Active status flag (default: True)  |

**Note:** Standalone table with no foreign key relationships. Used by authentication middleware when `api_key_enabled=True`.

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

Event (1) ----< (many) Alert
Event (1) ---- (one) EventAudit

AlertRule (1) ----< (many) Alert

GPUStats (standalone, no foreign key relationships)
APIKey (standalone, no foreign key relationships)
Log (standalone, no foreign key relationships - for reliability)
AuditLog (standalone, no foreign key relationships)
PromptVersion (standalone, no foreign key relationships)
```

**Cascade Behavior:**

- Deleting a Camera cascades to delete all its Detections, Events, Zones, SceneChanges, and Baselines
- Deleting an Event cascades to delete all its Alerts and EventAudit
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
