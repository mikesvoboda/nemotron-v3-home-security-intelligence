# Database Models - Agent Guide

## Purpose

This directory contains SQLAlchemy 2.0 ORM models for the home security intelligence system. These models define the database schema for tracking cameras, object detections, security events, and GPU performance metrics.

## Architecture Overview

- **ORM Framework**: SQLAlchemy 2.0 with modern `Mapped` type hints
- **Database**: SQLite (local deployment)
- **Type Safety**: Full type annotations for IDE support and mypy checking
- **Cascade Behavior**: Camera deletion automatically removes dependent records
- **Testing**: Comprehensive unit tests in `/backend/tests/unit/test_models.py`

## Key Files

### `__init__.py`

Module initialization file that exports all models and the declarative base class.

**Exports:**

- `Base` - SQLAlchemy declarative base for all models
- `Camera` - Camera entity model
- `Detection` - Object detection results model
- `Event` - Security event model
- `GPUStats` - GPU performance metrics model

### `camera.py`

Defines the Camera model and declarative Base class used by all models.

**Model:** `Camera`
**Purpose:** Represents physical security cameras in the system

**Fields:**

- `id` (str, PK) - Unique camera identifier (e.g., "front_door")
- `name` (str) - Human-readable name (e.g., "Front Door Camera")
- `folder_path` (str) - File system path for FTP image uploads (e.g., "/export/foscam/front_door")
- `status` (str) - Camera operational status (default: "online")
- `created_at` (datetime) - Camera registration timestamp
- `last_seen_at` (datetime, nullable) - Last activity timestamp

**Relationships:**

- `detections` - One-to-many with Detection (cascade="all, delete-orphan")
- `events` - One-to-many with Event (cascade="all, delete-orphan")

**Design Notes:**

- Uses string IDs for human-readable camera identifiers
- Cascade deletes ensure orphaned records are cleaned up
- `folder_path` links cameras to FTP upload directories

### `detection.py`

Defines the Detection model for RT-DETRv2 object detection results.

**Model:** `Detection`
**Purpose:** Stores individual object detection results from AI inference

**Fields:**

- `id` (int, PK, autoincrement) - Unique detection ID
- `camera_id` (str, FK→cameras.id) - Source camera reference
- `file_path` (str) - Path to source image file
- `file_type` (str, nullable) - File extension (e.g., "jpg")
- `detected_at` (datetime) - Detection timestamp (default: utcnow)
- `object_type` (str, nullable) - Detected object class (e.g., "person", "car")
- `confidence` (float, nullable) - Detection confidence score (0.0-1.0)
- `bbox_x`, `bbox_y` (int, nullable) - Bounding box top-left coordinates
- `bbox_width`, `bbox_height` (int, nullable) - Bounding box dimensions
- `thumbnail_path` (str, nullable) - Path to cropped detection thumbnail

**Relationships:**

- `camera` - Many-to-one with Camera

**Indexes:**

- `idx_detections_camera_id` - Single-column index on camera_id
- `idx_detections_detected_at` - Single-column index on detected_at
- `idx_detections_camera_time` - Composite index on (camera_id, detected_at)

**Design Notes:**

- Auto-incrementing integer ID for large-scale detection storage
- Optional fields support gradual enrichment (detection → analysis → thumbnail)
- Composite index optimizes camera-specific time-range queries
- Bounding box stored as separate fields for SQL query flexibility

### `event.py`

Defines the Event model for aggregated security events.

**Model:** `Event`
**Purpose:** Represents security events analyzed by Nemotron LLM from batched detections

**Fields:**

- `id` (int, PK, autoincrement) - Unique event ID
- `batch_id` (str) - Batch processing identifier for grouping detections
- `camera_id` (str, FK→cameras.id) - Source camera reference
- `started_at` (datetime) - Event start timestamp
- `ended_at` (datetime, nullable) - Event end timestamp
- `risk_score` (int, nullable) - LLM-determined risk score (0-100)
- `risk_level` (str, nullable) - Risk classification (e.g., "low", "medium", "high")
- `summary` (text, nullable) - LLM-generated event summary
- `reasoning` (text, nullable) - LLM reasoning for risk assessment
- `detection_ids` (text, nullable) - Comma-separated detection IDs in this event
- `reviewed` (bool) - User review flag (default: False)
- `notes` (text, nullable) - User-added notes

**Relationships:**

- `camera` - Many-to-one with Camera

**Indexes:**

- `idx_events_camera_id` - Single-column index on camera_id
- `idx_events_started_at` - Single-column index on started_at
- `idx_events_risk_score` - Single-column index on risk_score
- `idx_events_reviewed` - Single-column index on reviewed
- `idx_events_batch_id` - Single-column index on batch_id

**Design Notes:**

- Risk scoring is LLM-determined, not rule-based
- Events aggregate multiple detections within 90-second windows
- Text fields use SQL `Text` type for large content
- `reviewed` flag enables user workflow tracking
- `batch_id` links back to batch processing pipeline

### `gpu_stats.py`

Defines the GPUStats model for monitoring NVIDIA RTX A5500 performance.

**Model:** `GPUStats`
**Purpose:** Time-series tracking of GPU metrics during AI inference

**Fields:**

- `id` (int, PK, autoincrement) - Unique stats record ID
- `recorded_at` (datetime) - Recording timestamp (default: utcnow)
- `gpu_utilization` (float, nullable) - GPU utilization percentage (0-100)
- `memory_used` (int, nullable) - GPU memory used in MB
- `memory_total` (int, nullable) - Total GPU memory in MB (typically 24576 for RTX A5500)
- `temperature` (float, nullable) - GPU temperature in Celsius
- `inference_fps` (float, nullable) - Inference throughput in frames per second

**Indexes:**

- `idx_gpu_stats_recorded_at` - Single-column index on recorded_at for time-series queries

**Design Notes:**

- All metric fields are nullable for partial data collection
- Time-series optimized with indexed timestamp
- Supports real-time dashboard GPU monitoring
- No foreign keys - standalone performance tracking

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
Camera (1) ──< (many) Detection
Camera (1) ──< (many) Event

GPUStats (standalone, no relationships)
```

**Cascade Behavior:**

- Deleting a Camera cascades to delete all its Detections and Events
- `cascade="all, delete-orphan"` ensures orphaned records are removed

## Indexing Strategy

### Detection Table

1. **Camera queries**: `idx_detections_camera_id` - List detections by camera
2. **Time queries**: `idx_detections_detected_at` - Time-range filtering
3. **Combined queries**: `idx_detections_camera_time` - Camera-specific time ranges (most common query pattern)

### Event Table

1. **Camera queries**: `idx_events_camera_id` - Events by camera
2. **Time queries**: `idx_events_started_at` - Event timeline
3. **Risk filtering**: `idx_events_risk_score` - High-risk event queries
4. **Workflow**: `idx_events_reviewed` - Unreviewed event queries
5. **Batch tracking**: `idx_events_batch_id` - Batch processing audit

### GPUStats Table

1. **Time-series**: `idx_gpu_stats_recorded_at` - Performance metrics over time

## Usage Example

```python
from backend.models import Base, Camera, Detection, Event, GPUStats
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

- `/backend/models/README.md` - Detailed model documentation
- `/backend/tests/unit/test_models.py` - Model test suite
- `/backend/core/database.py` - Database connection and session management
