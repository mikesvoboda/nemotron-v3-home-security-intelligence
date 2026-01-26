# Test Images Directory

## Purpose

The `backend/tests/fixtures/images/` directory contains test images used by backend integration and end-to-end tests. These images simulate real camera captures for testing the AI detection pipeline, event processing, and API responses.

## Directory Structure

```
backend/tests/fixtures/images/
├── AGENTS.md                           # This file
└── pipeline_test/                      # Pipeline integration test images (14 JPEG files)
    ├── HMDAlarm_20260101-103424.jpg    # 298KB - Real Foscam capture
    ├── HMDAlarm_20260101-171020.jpg    # 151KB - Real Foscam capture
    ├── MDAlarm_20250805-220848.jpg     # 124KB - Real Foscam capture
    ├── MDAlarm_20260101-143519.jpg     # 333KB - Real Foscam capture
    ├── test_person_house_front.jpg     # 110KB - Person detection test
    ├── test_person_porch_1.jpg         # 167KB - Person detection test
    ├── test_person_porch_cat.jpg       # 151KB - Person + pet test
    ├── test_person_walking_dog.jpg     # 792KB - Person + pet test
    ├── test_pet_cat_porch_tabby.jpg    # 156KB - Pet detection test
    ├── test_pet_dog_grass_brown.jpg    # 412KB - Pet detection test
    ├── test_pet_dog_yard_labrador.jpg  # 183KB - Pet detection test
    ├── test_vehicle_car_house.jpg      # 256KB - Vehicle detection test
    ├── test_vehicle_compact_building.jpg # 345KB - Vehicle detection test
    └── test_vehicle_sedan_road.jpg     # 97KB - Vehicle detection test
```

## Image Categories

### Real Foscam Captures (4 files)

These are actual images captured by Foscam cameras, following the naming convention used in production:

- **`HMDAlarm_*.jpg`** - Captures from "HMD" camera with motion detection alarm
- **`MDAlarm_*.jpg`** - Captures from "MD" camera with motion detection alarm

**Format:** `{camera_name}Alarm_{YYYYMMDD-HHMMSS}.jpg`

These images are used to test:

- Real-world image quality and resolution
- Foscam FTP upload naming conventions
- Production-like detection scenarios
- End-to-end pipeline processing

### Person Detection Test Images (4 files)

Images containing people in various home security scenarios:

- **`test_person_house_front.jpg`** - Person standing in front of house entrance
- **`test_person_porch_1.jpg`** - Person on porch, typical doorbell camera angle
- **`test_person_porch_cat.jpg`** - Person with cat on porch (multi-object scenario)
- **`test_person_walking_dog.jpg`** - Person walking dog (motion scenario)

**Used for:**

- YOLO26 person detection accuracy
- Risk scoring for human presence
- Nemotron risk analysis reasoning

### Pet Detection Test Images (3 files)

Images containing animals without people:

- **`test_pet_cat_porch_tabby.jpg`** - Tabby cat on porch
- **`test_pet_dog_grass_brown.jpg`** - Brown dog in yard
- **`test_pet_dog_yard_labrador.jpg`** - Labrador in yard

**Used for:**

- YOLO26 animal detection (cat, dog classes)
- Low-risk event classification
- False alarm reduction testing

### Vehicle Detection Test Images (3 files)

Images containing vehicles in residential settings:

- **`test_vehicle_car_house.jpg`** - Car parked near house
- **`test_vehicle_compact_building.jpg`** - Compact car near building
- **`test_vehicle_sedan_road.jpg`** - Sedan on road

**Used for:**

- YOLO26 vehicle detection (car, truck classes)
- Driveway monitoring scenarios
- Risk scoring for unfamiliar vehicles

## How These Images Are Used

### In Test Fixtures

Images are loaded as pytest fixtures for integration tests:

```python
from pathlib import Path

@pytest.fixture
def test_image_path():
    return Path(__file__).parent / "fixtures" / "images" / "pipeline_test" / "test_person_porch_1.jpg"

async def test_detection(test_image_path):
    result = await detection_service.process_image(test_image_path)
    assert result.detections
```

### In E2E Pipeline Tests

The E2E GPU pipeline test (`backend/tests/e2e/test_gpu_pipeline.py`) creates temporary test images in camera directories, but these fixture images serve as reference examples for expected detection results.

### In API Contract Tests

API tests may reference these images when testing:

- `/api/detections` endpoints
- `/api/events` endpoints with image attachments
- Image processing and thumbnail generation

## Image Specifications

All images are JPEG format with the following characteristics:

- **Resolution:** Varies from 1200x800 to 1920x1080 (typical Foscam output)
- **Color Space:** RGB (3 components)
- **Compression:** Progressive JPEG
- **Density:** 72 DPI (standard web resolution)
- **File Size:** 97KB to 792KB (typical camera capture sizes)

## Content Origin

- **Real captures:** 4 images from actual Foscam FTP uploads (manually copied)
- **Test images:** 10 images curated for testing specific detection scenarios

All images are safe for automated testing and do not contain sensitive or personal information.

## Usage in Tests

To use these images in tests:

```python
from pathlib import Path

# Get the images directory
IMAGES_DIR = Path(__file__).parent / "fixtures" / "images" / "pipeline_test"

# Load a specific test image
person_image = IMAGES_DIR / "test_person_house_front.jpg"
assert person_image.exists()

# Iterate through all test images
for image_path in IMAGES_DIR.glob("*.jpg"):
    print(f"Testing with: {image_path.name}")
```

## Maintenance

- **Do not modify** existing test images without updating dependent tests
- **Add new images** when testing new detection scenarios or edge cases
- **Document** any new images in this file with category and purpose
- **Keep file sizes reasonable** (< 1MB each) to avoid bloating the repository

## Related Documentation

- `/backend/tests/AGENTS.md` - Overview of test infrastructure
- `/backend/tests/fixtures/AGENTS.md` - Parent fixtures directory
- `/backend/tests/e2e/test_gpu_pipeline.py` - E2E tests using these images
- `/ai/yolo26/AGENTS.md` - YOLO26 detection model documentation
