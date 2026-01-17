# Integration Tests - Repositories

## Purpose

The `backend/tests/integration/repositories/` directory contains integration tests for repository classes that implement the Repository pattern. These tests verify database operations against a real PostgreSQL database via testcontainers.

## Directory Structure

```
backend/tests/integration/repositories/
├── AGENTS.md                        # This file
├── __init__.py                      # Package initialization
├── conftest.py                      # Repository-specific fixtures (1.6KB)
├── README.md                        # Repository test documentation
├── test_base.py                     # Base repository tests (24KB)
├── test_camera_repository.py        # Camera repository tests (31KB)
├── test_detection_repository.py     # Detection repository tests (16KB)
├── test_entity_repository.py        # Entity repository tests (18KB)
└── test_event_repository.py         # Event repository tests (16KB)
```

## Test Files (5 total)

| File                           | Repository Tested   | Key Coverage                         |
| ------------------------------ | ------------------- | ------------------------------------ |
| `test_base.py`                 | BaseRepository      | Generic CRUD, pagination, filtering  |
| `test_camera_repository.py`    | CameraRepository    | Camera CRUD, status updates, queries |
| `test_detection_repository.py` | DetectionRepository | Detection storage, batch operations  |
| `test_entity_repository.py`    | EntityRepository    | Entity management, trust levels      |
| `test_event_repository.py`     | EventRepository     | Event storage, filtering, statistics |

## Running Tests

```bash
# All repository integration tests
uv run pytest backend/tests/integration/repositories/ -v

# Specific repository tests
uv run pytest backend/tests/integration/repositories/test_camera_repository.py -v

# With coverage
uv run pytest backend/tests/integration/repositories/ -v --cov=backend.repositories
```

## Repository Pattern

### Base Repository Features

```python
class BaseRepository[T]:
    async def create(self, entity: T) -> T
    async def get_by_id(self, id: str) -> T | None
    async def get_all(self, limit: int, offset: int) -> list[T]
    async def update(self, id: str, data: dict) -> T | None
    async def delete(self, id: str) -> bool
    async def count(self) -> int
```

### Test Patterns

```python
@pytest.mark.asyncio
async def test_create_and_retrieve(repository, session):
    # Create entity
    entity = await repository.create(Camera(id="test", name="Test Camera"))

    # Retrieve and verify
    retrieved = await repository.get_by_id("test")
    assert retrieved is not None
    assert retrieved.name == "Test Camera"
```

## Fixtures

From `conftest.py`:

| Fixture                | Description                           |
| ---------------------- | ------------------------------------- |
| `camera_repository`    | CameraRepository with test session    |
| `event_repository`     | EventRepository with test session     |
| `detection_repository` | DetectionRepository with test session |
| `entity_repository`    | EntityRepository with test session    |

## Key Test Coverage

### CameraRepository Tests

- Create camera with validation
- Update camera status
- List cameras with filtering
- Delete camera with cascade
- Get cameras by folder path

### EventRepository Tests

- Create event with detections
- Filter by camera, date range, risk level
- Get event statistics
- Mark events as reviewed
- Bulk operations

### DetectionRepository Tests

- Store detection with bounding box
- Batch detection creation
- Filter by confidence threshold
- Get detections for event
- Detection statistics

### EntityRepository Tests

- Create recognized entity
- Update trust classification
- Entity appearance tracking
- Entity-event associations

## Related Documentation

- `/backend/repositories/AGENTS.md` - Repository implementations
- `/backend/tests/integration/AGENTS.md` - Integration tests overview
- `/backend/tests/unit/repositories/AGENTS.md` - Unit tests for repositories
