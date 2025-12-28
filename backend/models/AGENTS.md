# Database Models - Agent Guide

## Purpose

This directory contains SQLAlchemy 2.0 ORM models for the home security intelligence system. These models define the database schema for tracking cameras, object detections, security events, GPU performance metrics, application logs, and API keys.

## Architecture Overview

- **ORM Framework**: SQLAlchemy 2.0 with modern `Mapped` type hints
- **Database**: SQLite (local deployment) with WAL mode
- **Type Safety**: Full type annotations for IDE support and mypy checking
- **Cascade Behavior**: Camera deletion automatically removes dependent records
- **Testing**: Comprehensive unit tests in `/backend/tests/unit/test_models.py`

## Files Overview

```
backend/models/
├── __init__.py     # Module exports (Base, Camera, Detection, Event, GPUStats, Log, APIKey)
├── camera.py       # Camera model and Base class definition
├── detection.py    # Object detection results model (with video metadata support)
├── event.py        # Security event model with LLM analysis
├── gpu_stats.py    # GPU performance metrics model
├── log.py          # Structured application log model
├── api_key.py      # API key authentication model
└── README.md       # Detailed model documentation
```

## `__init__.py` - Module Exports

**Exports:**

- `Base` - SQLAlchemy declarative base for all models
- `Camera` - Camera entity model
- `Detection` - Object detection results model
- `Event` - Security event model
- `GPUStats` - GPU performance metrics model
- `Log` - Structured application log model
- `APIKey` - API key authentication model

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

**Note:** This file also defines the `Base` class used by all models.

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

**Indexes:**

- `idx_events_camera_id` - Single-column index on camera_id
- `idx_events_started_at` - Single-column index on started_at
- `idx_events_risk_score` - Single-column index on risk_score
- `idx_events_reviewed` - Single-column index on reviewed
- `idx_events_batch_id` - Single-column index on batch_id

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

GPUStats (standalone, no relationships)
APIKey (standalone, no relationships)
Log (standalone, no relationships)
```

**Cascade Behavior:**

- Deleting a Camera cascades to delete all its Detections and Events
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

# Initialize database
engine = create_engine("sqlite:///security.db")
Base.metadata.create_all(engine)

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
