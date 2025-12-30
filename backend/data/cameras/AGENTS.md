# Camera Test Data Directory - Agent Guide

## Purpose

This directory contains sample camera images for testing and development of the AI detection pipeline. Each subdirectory represents a camera and contains sample JPEG images.

## Directory Structure

```
cameras/
├── AGENTS.md       # This file
├── backyard/       # Backyard camera samples
├── driveway/       # Driveway camera samples
└── front_door/     # Front door camera samples
```

## Camera ID Derivation

The `FileWatcher` service derives camera IDs from folder names using `normalize_camera_id()`:

| Folder        | Normalized Camera ID |
| ------------- | -------------------- |
| `backyard`    | `backyard`           |
| `driveway`    | `driveway`           |
| `front_door`  | `front_door`         |
| `Front Door`  | `front_door`         |
| `My Camera 1` | `my_camera_1`        |

## Image File Naming Conventions

The file watcher accepts any file with a supported extension. Common patterns:

| Pattern                      | Description                     |
| ---------------------------- | ------------------------------- |
| `capture_NNN.jpg`            | Sequential captures             |
| `motion_YYYYMMDD_HHMMSS.jpg` | Motion-triggered with timestamp |
| `alert_YYYYMMDD_HHMMSS.jpg`  | Alert-triggered with timestamp  |
| `new_capture_EPOCH.jpg`      | Captures with Unix timestamp    |

## Supported File Types

**Images:** `.jpg`, `.jpeg`, `.png`
**Videos:** `.mp4`, `.mkv`, `.avi`, `.mov`

## Testing the Pipeline

### Manual file copy test

```bash
# Copy a test image to trigger detection
cp /path/to/test.jpg backend/data/cameras/front_door/test_$(date +%s).jpg
```

### Watch for processing

```bash
# Tail backend logs to see detection results
tail -f backend/data/logs/security.log | grep -E "(detection|event)"
```

## Usage by Services

| Service              | Purpose                                      |
| -------------------- | -------------------------------------------- |
| `FileWatcher`        | Monitors for new files, queues for detection |
| `DetectorClient`     | Sends images to RT-DETRv2                    |
| `ThumbnailGenerator` | Creates preview images with bounding boxes   |
| `VideoProcessor`     | Extracts frames and metadata from videos     |

## Production Camera Paths

In production, the file watcher monitors `/export/foscam/{camera_name}/` where Foscam cameras upload via FTP. The path is configured via `CAMERA_ROOT` environment variable.

## Related Documentation

- `/backend/services/file_watcher.py` - File monitoring service
- `/backend/services/AGENTS.md` - Services documentation
- `/backend/data/AGENTS.md` - Data directory overview
