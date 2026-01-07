# Driveway Camera Test Images - Agent Guide

## Purpose

This directory contains sample images for testing the AI detection pipeline with the driveway camera. These images simulate camera uploads from a driveway security camera and are used for development and testing.

## Files

| File                                | Type        | Description                                         |
| ----------------------------------- | ----------- | --------------------------------------------------- |
| `capture_001.jpg` - `005.jpg`       | Test images | Sequential test captures (5 images)                 |
| `motion_$(date +%Y%m%d_%H%M%S).jpg` | Test image  | Motion-triggered capture sample (template filename) |

## Camera ID

The file watcher derives the camera ID from the directory name:

- **Directory:** `driveway`
- **Camera ID:** `driveway`
- **Camera Name:** "Driveway" (displayed in UI)

## Usage

These images are monitored by the file watcher service when configured to watch the `backend/data/cameras/` directory. Driveway images typically contain:

- **Vehicles:** Cars, trucks, delivery vehicles entering/exiting
- **People:** Residents, visitors, delivery personnel
- **Activities:** Parking, unloading, walking to front door

## Typical Detection Scenarios

### Vehicle Detection

- **Expected objects:** car, truck, motorcycle
- **Risk factors:** Unknown vehicles at night, vehicles with no visible driver
- **Low risk:** Known vehicles (ReID), delivery vehicles during business hours

### Person Detection

- **Expected objects:** person, backpack, handbag, suitcase
- **Risk factors:** Person checking car doors, loitering near vehicles
- **Low risk:** Delivery uniform, person walking to front door

## Testing the Pipeline

### Manual Test

```bash
# Simulate motion-triggered capture
cp backend/data/cameras/driveway/capture_001.jpg \
   backend/data/cameras/driveway/motion_$(date +%Y%m%d_%H%M%S).jpg

# Watch logs for detection results
tail -f backend/logs/security.log | grep -E "(driveway|detection|vehicle)"
```

### Vehicle Tracking Test

Test cross-camera vehicle tracking:

1. Add vehicle image to driveway camera
2. Wait for detection and ReID feature extraction
3. Add same vehicle to front_door or backyard camera
4. Verify ReID matches across cameras (same vehicle_id)

## Image Characteristics

Test images should represent typical driveway camera scenarios:

- **Lighting:** Day and night captures (vehicle headlights at night)
- **Weather:** Clear, rainy, snow conditions
- **Objects:** Cars, trucks, people walking to/from vehicles
- **Activities:** Parking, reversing, loading/unloading

## Production Deployment

In production, the file watcher monitors `/export/foscam/driveway/` where the Foscam camera uploads images via FTP.

**Configuration:**

```bash
# Environment variable for camera root path
CAMERA_ROOT=/export/foscam

# Camera folder_path in database
folder_path=/export/foscam/driveway
```

## Related Documentation

- `/backend/data/cameras/AGENTS.md` - Camera test data overview
- `/backend/services/file_watcher.py` - File monitoring service
- `/backend/services/enrichment/reid_enrichment.py` - Vehicle tracking service
