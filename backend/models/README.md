# Database Models

SQLAlchemy 2.0 models for the home security intelligence system.

## Models

### Camera (`camera.py`)

Represents a security camera in the system.

**Fields:**

- `id` (str, PK): Unique camera identifier
- `name` (str): Human-readable camera name
- `folder_path` (str): File system path for FTP uploads
- `status` (str): Camera status (default: "online")
- `created_at` (datetime): Creation timestamp
- `last_seen_at` (datetime, optional): Last activity timestamp

**Relationships:**

- `detections`: One-to-many with Detection (cascade delete)
- `events`: One-to-many with Event (cascade delete)

### Detection (`detection.py`)

Represents an object detection result from RT-DETRv2.

**Fields:**

- `id` (int, PK): Auto-incrementing ID
- `camera_id` (str, FK): References cameras.id
- `file_path` (str): Path to source image file
- `file_type` (str, optional): File type/extension
- `detected_at` (datetime): Detection timestamp
- `object_type` (str, optional): Detected object class
- `confidence` (float, optional): Detection confidence (0-1)
- `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height` (int, optional): Bounding box coordinates
- `thumbnail_path` (str, optional): Path to detection thumbnail

**Relationships:**

- `camera`: Many-to-one with Camera

**Indexes:**

- `idx_detections_camera_id`: For camera-based queries
- `idx_detections_detected_at`: For time-based queries
- `idx_detections_camera_time`: Composite index for camera+time queries

### Event (`event.py`)

Represents a security event aggregated from multiple detections.

**Fields:**

- `id` (int, PK): Auto-incrementing ID
- `batch_id` (str): Batch processing identifier
- `camera_id` (str, FK): References cameras.id
- `started_at` (datetime): Event start time
- `ended_at` (datetime, optional): Event end time
- `risk_score` (int, optional): LLM-determined risk score (0-100)
- `risk_level` (str, optional): Risk level classification
- `summary` (text, optional): LLM-generated event summary
- `reasoning` (text, optional): LLM reasoning for risk assessment
- `detection_ids` (text, optional): JSON array of detection IDs (e.g., "[1, 2, 3]")
- `reviewed` (bool): User review flag (default: False)
- `notes` (text, optional): User notes

**Relationships:**

- `camera`: Many-to-one with Camera

**Indexes:**

- `idx_events_camera_id`: For camera-based queries
- `idx_events_started_at`: For time-based queries
- `idx_events_risk_score`: For risk-based queries
- `idx_events_reviewed`: For review status queries
- `idx_events_batch_id`: For batch processing queries

### GPUStats (`gpu_stats.py`)

Tracks GPU performance metrics for AI inference monitoring.

**Fields:**

- `id` (int, PK): Auto-incrementing ID
- `recorded_at` (datetime): Recording timestamp
- `gpu_utilization` (float, optional): GPU utilization percentage
- `memory_used` (int, optional): GPU memory used (MB)
- `memory_total` (int, optional): Total GPU memory (MB)
- `temperature` (float, optional): GPU temperature (°C)
- `inference_fps` (float, optional): Inference frames per second

**Indexes:**

- `idx_gpu_stats_recorded_at`: For time-series queries

## Usage

```python
from backend.models import Base, Camera, Detection, Event, GPUStats
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Create engine and tables
engine = create_engine("sqlite:///security.db")
Base.metadata.create_all(engine)

# Create session
with Session(engine) as session:
    # Create a camera
    camera = Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door"
    )
    session.add(camera)
    session.commit()

    # Query cameras
    cameras = session.query(Camera).all()
```

## Testing

Comprehensive unit tests are available in `/backend/tests/unit/test_models.py`:

```bash
# Run model tests
pytest backend/tests/unit/test_models.py -v

# Run with coverage
pytest backend/tests/unit/test_models.py --cov=backend.models
```

## Design Decisions

1. **SQLAlchemy 2.0 Style**: Uses modern `Mapped` type hints and `mapped_column()` syntax
2. **Cascade Deletes**: Camera deletion automatically removes associated detections and events
3. **Indexes**: Strategic indexes on foreign keys and commonly queried fields
4. **Optional Fields**: Many fields are optional to support gradual data enrichment
5. **Type Safety**: Full type hints for better IDE support and type checking
6. **Base Class**: Shared `Base` class in camera.py for all models

## Schema Evolution

When modifying models:

1. Update the model class
2. Create an Alembic migration (future task)
3. Update tests in `test_models.py`
4. Update this README

## Related Tasks

- Phase 2, Task 1: ✓ Implement SQLite database models
- Phase 2, Task 13: ✓ Write tests for database models (TDD)
- Phase 2, Task 2: Connect to Redis (separate task)
- Phase 2, Task 3: Initialize FastAPI with database (separate task)
