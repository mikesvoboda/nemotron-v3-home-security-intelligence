# Unit Tests - Database Models

## Purpose

The `backend/tests/unit/models/` directory contains unit tests for SQLAlchemy ORM models in `backend/models/`. Tests verify model field definitions, relationships, constraints, and enumerations.

## Test Files (10 files)

| File                         | Tests For                  | Test Count |
| ---------------------------- | -------------------------- | ---------- |
| `test_camera.py`             | Camera model               | ~20 tests  |
| `test_detection.py`          | Detection model            | ~25 tests  |
| `test_event.py`              | Event model                | ~30 tests  |
| `test_alert.py`              | Alert and AlertRule models | ~40 tests  |
| `test_zone.py`               | Zone model                 | ~25 tests  |
| `test_gpu_stats.py`          | GPUStats model             | ~15 tests  |
| `test_api_key.py`            | APIKey model               | ~10 tests  |
| `test_enums.py`              | Severity and other enums   | ~15 tests  |
| `test_hypothesis_example.py` | Property-based tests       | ~10 tests  |

## Test Categories

### Model Field Tests

- Field type validation
- Default values
- Nullable constraints
- String length constraints
- Index definitions

### Relationship Tests

- Foreign key constraints
- Cascade delete behavior
- Back-reference configuration
- One-to-many relationships

### Enum Tests

- Enum value definitions
- Enum string representations
- Enum membership validation

### Property-Based Tests (Hypothesis)

`test_hypothesis_example.py` demonstrates property-based testing:

- Model invariants
- Constraint validation
- Edge case generation

## Running Tests

```bash
# Run all model unit tests
pytest backend/tests/unit/models/ -v

# Run specific model tests
pytest backend/tests/unit/models/test_camera.py -v

# Run with coverage
pytest backend/tests/unit/models/ -v --cov=backend/models
```

## Fixtures Used

From `backend/tests/conftest.py`:

- `isolated_db` - Isolated PostgreSQL database instance
- `session` - Database session with transaction rollback
- `reset_settings_cache` - Clears settings cache before each test

## Common Patterns

### Testing Model Creation

```python
@pytest.mark.asyncio
async def test_create_camera(session):
    camera = Camera(
        id="test_cam",
        name="Test Camera",
        folder_path="/path/to/folder",
    )
    session.add(camera)
    await session.commit()

    assert camera.id == "test_cam"
    assert camera.status == "online"  # Default value
```

### Testing Relationships

```python
@pytest.mark.asyncio
async def test_camera_detections_relationship(session):
    camera = Camera(id="test_cam", name="Test", folder_path="/path")
    detection = Detection(camera_id="test_cam", file_path="/img.jpg")

    session.add_all([camera, detection])
    await session.commit()

    assert detection in camera.detections
```

### Testing Cascade Deletes

```python
@pytest.mark.asyncio
async def test_cascade_delete(session):
    camera = Camera(id="test_cam", name="Test", folder_path="/path")
    detection = Detection(camera_id="test_cam", file_path="/img.jpg")

    session.add_all([camera, detection])
    await session.commit()

    await session.delete(camera)
    await session.commit()

    # Detection should be deleted via cascade
    result = await session.get(Detection, detection.id)
    assert result is None
```

## Related Documentation

- `/backend/models/AGENTS.md` - Model documentation
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/AGENTS.md` - Test infrastructure overview
