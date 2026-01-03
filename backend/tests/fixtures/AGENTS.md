# Test Fixtures

## Purpose

The `backend/tests/fixtures/` directory contains test fixture files used by automated tests. These include sample images, configuration files, and other static test data.

## Directory Structure

```
backend/tests/fixtures/
├── AGENTS.md                 # This file
└── images/                   # Test images
    └── pipeline_test/        # Pipeline integration test images
```

## Fixture Files

### `images/pipeline_test/`

Contains test images for pipeline integration tests:

**Person Detection Images:**

- `test_person_house_front.jpg` - Person in front of house
- `test_person_porch_1.jpg` - Person on porch
- `test_person_porch_cat.jpg` - Person with cat on porch
- `test_person_walking_dog.jpg` - Person walking a dog

**Pet Detection Images:**

- `test_pet_cat_porch_tabby.jpg` - Tabby cat on porch
- `test_pet_dog_grass_brown.jpg` - Brown dog on grass
- `test_pet_dog_yard_labrador.jpg` - Labrador in yard

**Vehicle Detection Images:**

- `test_vehicle_car_house.jpg` - Car near house
- `test_vehicle_compact_building.jpg` - Compact car near building
- `test_vehicle_sedan_road.jpg` - Sedan on road

**Motion Detection Images (HMD/MD Alarm):**

- `HMDAlarm_*.jpg` - Human motion detection alarm images
- `MDAlarm_*.jpg` - Motion detection alarm images

## Usage in Tests

These fixtures are used in:

- **E2E tests** (`backend/tests/e2e/test_pipeline_integration.py`)
- **Integration tests** for detector client
- **Unit tests** for file watcher and image validation

**Example Usage:**

```python
import pytest
from pathlib import Path

@pytest.fixture
def test_image_path():
    return Path(__file__).parent / "fixtures" / "images" / "pipeline_test" / "test_person_porch_1.jpg"

async def test_detection(test_image_path):
    # Use fixture image for testing
    result = await detector.detect_objects(str(test_image_path), "test_camera", session)
    assert len(result) > 0
```

## Image Specifications

All test images are:

- JPEG format
- Real camera captures from Foscam cameras
- Various resolutions (typical: 1920x1080 or 2560x1440)
- File sizes ranging from ~100KB to ~800KB

## Adding New Fixtures

When adding new test fixtures:

1. Place files in appropriate subdirectory
2. Use descriptive filenames
3. Document the fixture in this file
4. Ensure files are committed to git (not ignored)

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/e2e/AGENTS.md` - E2E test documentation
- `/backend/tests/conftest.py` - Shared pytest fixtures
