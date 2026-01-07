# Front Door Camera Test Images - Agent Guide

## Purpose

This directory contains sample images for testing the AI detection pipeline with the front door camera. These images simulate camera uploads from a front door security camera and are used for development and testing.

## Files

| File                          | Type        | Description                            |
| ----------------------------- | ----------- | -------------------------------------- |
| `capture_001.jpg` - `005.jpg` | Test images | Sequential test captures (5 images)    |
| `new_capture_1766902398.jpg`  | Test image  | Additional capture with Unix timestamp |

## Camera ID

The file watcher derives the camera ID from the directory name:

- **Directory:** `front_door`
- **Camera ID:** `front_door`
- **Camera Name:** "Front Door" (displayed in UI)

## Usage

These images are monitored by the file watcher service when configured to watch the `backend/data/cameras/` directory. Front door images typically contain:

- **People:** Residents, visitors, delivery personnel, potential intruders
- **Activities:** Knocking, ringing doorbell, package delivery, loitering
- **Items:** Packages, backpacks, handbags, delivery carts

## Typical Detection Scenarios

### Package Delivery

- **Expected objects:** person, package box, cardboard box, delivery uniform
- **Risk level:** Low (expected activity during business hours)
- **Actions:** knocking, placing package, taking photo

### Visitor/Resident

- **Expected objects:** person, handbag, backpack, keys
- **Risk level:** Low (resident) or medium (unknown visitor)
- **Actions:** walking, standing, knocking, entering

### Suspicious Activity

- **Expected objects:** person, all black clothing, hoodie, gloves
- **Risk level:** High (suspicious attire) or critical (breaking in)
- **Actions:** crouching, looking around, checking door, loitering

## Testing the Pipeline

### Manual Test

```bash
# Simulate new capture
cp backend/data/cameras/front_door/capture_001.jpg \
   backend/data/cameras/front_door/new_capture_$(date +%s).jpg

# Watch logs for detection results
tail -f backend/logs/security.log | grep -E "(front_door|detection|person)"
```

### Person ReID Test

Test cross-camera person tracking:

1. Add person image to front_door camera
2. Wait for detection and ReID feature extraction
3. Add same person to driveway or backyard camera
4. Verify ReID matches across cameras (same person_id)

## Entry Point Detection

The front door is a critical entry point. The risk analysis system applies elevated scrutiny:

- **Crouching near door:** High suspicion (lock picking)
- **Loitering > 30 seconds:** Medium suspicion (casing location)
- **Checking door handle:** High suspicion (testing entry)
- **Breaking in action:** Critical alert (immediate threat)

## Image Characteristics

Test images should represent typical front door camera scenarios:

- **Lighting:** Day and night captures (porch light at night)
- **Weather:** Clear, rainy conditions
- **Objects:** People at various distances (close-up, medium distance)
- **Activities:** Knocking, doorbell ringing, package drop-off, entry attempts

## Production Deployment

In production, the file watcher monitors `/export/foscam/front_door/` where the Foscam camera uploads images via FTP.

**Configuration:**

```bash
# Environment variable for camera root path
CAMERA_ROOT=/export/foscam

# Camera folder_path in database
folder_path=/export/foscam/front_door
```

## Related Documentation

- `/backend/data/cameras/AGENTS.md` - Camera test data overview
- `/backend/services/file_watcher.py` - File monitoring service
- `/backend/services/enrichment/reid_enrichment.py` - Person tracking service
- `/backend/services/risk_analysis.py` - Risk scoring with entry point context
