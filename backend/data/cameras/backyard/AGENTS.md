# Backyard Camera Test Images - Agent Guide

## Purpose

This directory contains sample images for testing the AI detection pipeline with the backyard camera. These images simulate camera uploads from a backyard security camera and are used for development and testing.

## Files

| File                          | Type        | Description                         |
| ----------------------------- | ----------- | ----------------------------------- |
| `capture_001.jpg` - `005.jpg` | Test images | Sequential test captures (5 images) |
| `alert_20251228_011355.jpg`   | Test image  | Alert-triggered capture sample      |

## Camera ID

The file watcher derives the camera ID from the directory name:

- **Directory:** `backyard`
- **Camera ID:** `backyard`
- **Camera Name:** "Backyard" (displayed in UI)

## Usage

These images are monitored by the file watcher service when configured to watch the `backend/data/cameras/` directory. When new files are added, they are automatically:

1. Detected by the file watcher
2. Queued for AI processing
3. Sent to RT-DETR for object detection
4. Enriched with additional AI attributes (Fashion-CLIP, X-CLIP, Florence-2)
5. Analyzed by Nemotron for risk scoring
6. Stored in the PostgreSQL database as events

## Testing the Pipeline

### Manual Test

Copy a new image to trigger detection:

```bash
# Copy an existing test image with a new timestamp
cp backend/data/cameras/backyard/capture_001.jpg \
   backend/data/cameras/backyard/test_$(date +%s).jpg

# Watch logs for detection results
tail -f backend/logs/security.log | grep -E "(backyard|detection)"
```

### Automated Test

Use the validation script to test the full pipeline:

```bash
# Run integration tests (includes file watcher tests)
uv run pytest backend/tests/integration/services/test_file_watcher.py -v
```

## Image Characteristics

Test images should represent typical backyard camera scenarios:

- **Lighting:** Day and night captures
- **Weather:** Clear, rainy, foggy conditions
- **Objects:** People, pets (dogs, cats), wildlife, vehicles (if visible)
- **Activities:** Walking, sitting, playing, normal backyard activities

## Production Deployment

In production, the file watcher monitors `/export/foscam/backyard/` (or configured camera path) where the Foscam camera uploads images via FTP.

**Configuration:**

```bash
# Environment variable for camera root path
CAMERA_ROOT=/export/foscam

# Camera folder_path in database
folder_path=/export/foscam/backyard
```

## Related Documentation

- `/backend/data/cameras/AGENTS.md` - Camera test data overview
- `/backend/services/file_watcher.py` - File monitoring service
- `/backend/services/AGENTS.md` - Services documentation
