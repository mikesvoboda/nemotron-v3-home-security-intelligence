# Pipeline Test Images

## Purpose

The `backend/tests/fixtures/images/pipeline_test/` directory contains 14 JPEG test images used for testing the AI detection pipeline. These images cover person, pet, and vehicle detection scenarios that simulate real-world home security monitoring.

## Image Inventory

### Real Foscam Captures (4 images)

| Filename                       | Size  | Description                  | Source      |
| ------------------------------ | ----- | ---------------------------- | ----------- |
| `HMDAlarm_20260101-103424.jpg` | 298KB | Motion alarm from HMD camera | Real Foscam |
| `HMDAlarm_20260101-171020.jpg` | 151KB | Motion alarm from HMD camera | Real Foscam |
| `MDAlarm_20250805-220848.jpg`  | 124KB | Motion alarm from MD camera  | Real Foscam |
| `MDAlarm_20260101-143519.jpg`  | 333KB | Motion alarm from MD camera  | Real Foscam |

**Naming Convention:** `{camera_name}Alarm_{YYYYMMDD-HHMMSS}.jpg`

These are actual captures from production Foscam cameras uploaded via FTP. They test:

- Real image quality and resolution
- Production naming conventions
- Authentic lighting and scene conditions

### Person Detection Images (4 images)

| Filename                      | Size  | Description                       | Expected Detections |
| ----------------------------- | ----- | --------------------------------- | ------------------- |
| `test_person_house_front.jpg` | 110KB | Person in front of house entrance | person              |
| `test_person_porch_1.jpg`     | 167KB | Person on porch (doorbell angle)  | person              |
| `test_person_porch_cat.jpg`   | 151KB | Person with cat on porch          | person, cat         |
| `test_person_walking_dog.jpg` | 792KB | Person walking dog                | person, dog         |

**Purpose:**

- Test RT-DETRv2 person detection accuracy
- Validate high-risk scoring for human presence
- Test Nemotron risk analysis reasoning

### Pet Detection Images (3 images)

| Filename                         | Size  | Description        | Expected Detections |
| -------------------------------- | ----- | ------------------ | ------------------- |
| `test_pet_cat_porch_tabby.jpg`   | 156KB | Tabby cat on porch | cat                 |
| `test_pet_dog_grass_brown.jpg`   | 412KB | Brown dog in yard  | dog                 |
| `test_pet_dog_yard_labrador.jpg` | 183KB | Labrador in yard   | dog                 |

**Purpose:**

- Test RT-DETRv2 animal detection (cat, dog classes)
- Validate low-risk scoring for pets only
- Test false alarm reduction

### Vehicle Detection Images (3 images)

| Filename                            | Size  | Description               | Expected Detections |
| ----------------------------------- | ----- | ------------------------- | ------------------- |
| `test_vehicle_car_house.jpg`        | 256KB | Car parked near house     | car                 |
| `test_vehicle_compact_building.jpg` | 345KB | Compact car near building | car                 |
| `test_vehicle_sedan_road.jpg`       | 97KB  | Sedan on road             | car                 |

**Purpose:**

- Test RT-DETRv2 vehicle detection (car, truck classes)
- Validate medium-risk scoring for vehicles
- Test driveway monitoring scenarios

## Test Coverage

These 14 images provide comprehensive coverage for:

1. **Detection Classes:**

   - Person (4 images with people)
   - Cat (2 images)
   - Dog (3 images)
   - Car/Vehicle (3 images)

2. **Scenario Types:**

   - Single object (10 images)
   - Multi-object (4 images: person+cat, person+dog)
   - Real-world lighting and angles

3. **Risk Levels:**

   - High risk: Person present
   - Medium risk: Vehicle only
   - Low risk: Pet only

4. **File Characteristics:**
   - Size range: 97KB - 792KB
   - Resolution: 1200x800 to 1920x1080
   - Format: Progressive JPEG, RGB color space

## Usage in Tests

### Loading Images in Tests

```python
from pathlib import Path

# Get the pipeline test images directory
IMAGES_DIR = Path(__file__).parent / "fixtures" / "images" / "pipeline_test"

# Load a specific image
person_image = IMAGES_DIR / "test_person_house_front.jpg"

# Iterate through all images
for image_path in IMAGES_DIR.glob("*.jpg"):
    # Process each image
    pass
```

### Expected Detection Results

When using these images with RT-DETRv2, expect:

- **Person images:** `confidence >= 0.5` for `person` class
- **Pet images:** `confidence >= 0.5` for `cat` or `dog` class
- **Vehicle images:** `confidence >= 0.5` for `car` class
- **Multi-object images:** Multiple detections with appropriate bounding boxes

### Nemotron Risk Scoring

Expected risk scores when processed by Nemotron:

- **Person present:** Risk score 60-90 (high risk)
- **Vehicle only:** Risk score 30-60 (medium risk)
- **Pet only:** Risk score 0-30 (low risk)

## Image Quality

All images meet production quality standards:

- **Resolution:** High enough for object detection (min 800px width)
- **Lighting:** Mix of daylight, indoor, and low-light conditions
- **Focus:** Sharp focus on primary subjects
- **Compression:** Acceptable JPEG compression (quality ~80-90)

## Maintenance Guidelines

When adding new test images:

1. **Follow naming conventions:**

   - Real captures: `{camera}Alarm_{YYYYMMDD-HHMMSS}.jpg`
   - Test images: `test_{object}_{location}_{descriptor}.jpg`

2. **Document in this file:**

   - Add to appropriate category table
   - Specify expected detections
   - Note any special characteristics

3. **Keep file sizes reasonable:**

   - Target < 500KB per image
   - Use JPEG compression appropriately
   - Avoid unnecessarily high resolutions

4. **Verify test impact:**
   - Run integration tests after adding images
   - Update expected detection counts if needed
   - Document any breaking changes

## Related Files

- `/backend/tests/fixtures/images/AGENTS.md` - Parent directory documentation
- `/backend/tests/e2e/test_gpu_pipeline.py` - E2E pipeline tests
- `/ai/rtdetr/detect.py` - RT-DETRv2 detection service
- `/backend/services/analysis.py` - Nemotron risk analysis service

## Content Safety

All images in this directory are:

- Safe for automated testing
- Free from sensitive or personal information
- Appropriate for version control
- Non-proprietary (real captures are from owned cameras)
