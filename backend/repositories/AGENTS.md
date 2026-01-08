# Repository Layer

This directory contains the repository pattern implementation for database access abstraction.

## Purpose

The repository layer provides a clean abstraction over SQLAlchemy database operations, enabling:

- **Testability**: Repositories can be easily mocked in unit tests
- **Separation of Concerns**: Business logic doesn't need to know about SQLAlchemy
- **Reusability**: Common query patterns are encapsulated in repository methods
- **Type Safety**: Generic base class provides type hints throughout

## Architecture

```
BaseRepository[T, ID]       # Generic CRUD operations
    ├── CameraRepository    # Camera-specific queries (ID: str)
    ├── EventRepository     # Event-specific queries (ID: int)
    └── DetectionRepository # Detection-specific queries (ID: int)
```

## Key Files

| File                      | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `base.py`                 | Generic BaseRepository with CRUD methods |
| `camera_repository.py`    | Camera-specific database operations      |
| `event_repository.py`     | Event-specific database operations       |
| `detection_repository.py` | Detection-specific database operations   |

## BaseRepository Methods

The base class provides these generic operations:

| Method         | Description                    |
| -------------- | ------------------------------ |
| `get_by_id`    | Retrieve entity by primary key |
| `list_all`     | List entities with pagination  |
| `count`        | Count total entities           |
| `create`       | Create a new entity            |
| `update`       | Update an existing entity      |
| `delete`       | Delete an entity               |
| `delete_by_id` | Delete by primary key          |
| `exists`       | Check if entity exists         |
| `save`         | Create or update (upsert)      |

## Domain-Specific Methods

### CameraRepository

- `find_by_status(status)` - Find cameras by status
- `find_by_name(name)` - Find camera by name
- `find_by_folder_path(path)` - Find camera by folder path
- `update_status(id, status)` - Update camera status
- `update_last_seen(id, timestamp)` - Update last seen time
- `list_online()` / `list_offline()` - List by status
- `name_exists(name)` / `folder_path_exists(path)` - Check existence

### EventRepository

- `get_by_id_with_camera(id)` - Get event with camera eagerly loaded
- `find_by_camera_id(camera_id)` - Find events for a camera
- `find_by_risk_level(level)` - Find events by risk level
- `find_unreviewed()` - Find unreviewed events
- `find_by_batch_id(batch_id)` - Find events in a batch
- `find_by_time_range(start, end)` - Find events in time range
- `find_high_risk(min_score)` - Find high-risk events
- `mark_reviewed(id, notes)` - Mark event as reviewed
- `count_unreviewed()` - Count unreviewed events
- `count_by_camera(camera_id)` - Count events for camera

### DetectionRepository

- `get_by_id_with_camera(id)` - Get detection with camera eagerly loaded
- `find_by_camera_id(camera_id)` - Find detections for a camera
- `find_by_object_type(type)` - Find by detected object type
- `find_by_time_range(start, end)` - Find in time range
- `find_high_confidence(min_conf)` - Find high-confidence detections
- `find_by_file_path(path)` - Find by file path
- `find_videos()` - Find video detections
- `count_by_camera(camera_id)` - Count detections for camera
- `count_by_object_type(type)` - Count by object type
- `get_object_type_counts()` - Get counts per object type
- `get_latest_by_camera(camera_id, limit)` - Get recent detections
- `create_batch(detections)` - Batch create detections

## Usage Pattern

```python
from backend.repositories import CameraRepository
from backend.core.database import get_db

async def get_online_cameras(db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    return await repo.list_online()
```

## Testing

Repository tests are located in `backend/tests/unit/repositories/`:

- `test_base_repository.py` - Tests for generic CRUD operations
- `test_camera_repository.py` - Tests for camera-specific methods
- `test_event_repository.py` - Tests for event-specific methods
- `test_detection_repository.py` - Tests for detection-specific methods

All tests use mocked AsyncSession to isolate repository logic from database.
