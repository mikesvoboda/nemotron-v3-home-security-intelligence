# Video and Image Processing

> Technical documentation of the media processing pipeline from FTP upload to AI analysis.

**Time to read:** ~10 min
**Prerequisites:** [Codebase Tour](codebase-tour.md)

---

## Processing Pipeline Overview

```mermaid
flowchart TD
    A[FTP Upload] -->|Foscam Camera| B[/export/foscam/{camera}/]
    B --> C[FileWatcher]
    C -->|Debounce| D{Media Type?}
    D -->|Image| E[PIL Validate]
    D -->|Video| F[ffprobe Validate]
    E --> G[SHA256 Dedupe]
    F --> G
    G -->|New| H[detection_queue]
    G -->|Duplicate| I[Skip]
    H --> J[DetectionQueueWorker]
    J -->|Image| K[YOLO26]
    J -->|Video| L[Extract Frames]
    L --> K
    K --> M[Store Detections]
    M --> N[BatchAggregator]
    N --> O[NemotronAnalyzer]
    O --> P[WebSocket Broadcast]
```

**Pipeline Summary:**

1. Camera uploads via FTP to `/export/foscam/{camera}/`
2. FileWatcher detects new files, validates, deduplicates
3. Valid files queued to Redis `detection_queue`
4. YOLO26 performs object detection
5. Detections batched (90s window) and analyzed by Nemotron LLM
6. Events created and broadcast via WebSocket

---

## File Watching

`FileWatcher` uses watchdog to monitor camera directories.

### Directory Structure

```
/export/foscam/              # Camera root (FOSCAM_BASE_PATH)
├── Front Door/              # -> camera_id: "front_door"
│   ├── image.jpg
│   └── video.mp4
└── Back Yard/               # -> camera_id: "back_yard"
```

### Supported Formats

| Type  | Extensions                     | Validation           |
| ----- | ------------------------------ | -------------------- |
| Image | `.jpg`, `.jpeg`, `.png`        | PIL `Image.verify()` |
| Video | `.mp4`, `.mkv`, `.avi`, `.mov` | Exists, size > 1KB   |

### Observer Modes

- **Native (default)**: inotify (Linux), FSEvents (macOS)
- **Polling**: Enable with `FILE_WATCHER_POLLING=true` for Docker mounts, NFS

### Debounce

FTP uploads trigger multiple events. Debounce waits 0.5s after last event:

```python
FileWatcher(camera_root="/export/foscam", debounce_delay=0.5)
```

---

## Image Processing

### Validation

```python
from backend.services.file_watcher import is_valid_image

if is_valid_image("/path/to/image.jpg"):
    # File exists, non-zero size, PIL can verify
```

### AI Detection

Images sent directly to YOLO26 via `DetectorClient`:

```python
from backend.services import DetectorClient

client = DetectorClient()
async with get_session() as session:
    detections = await client.detect_objects(
        image_path="/export/foscam/front_door/image.jpg",
        camera_id="front_door",
        session=session
    )
```

---

## Video Processing

Videos are processed by extracting frames at intervals, then detecting objects in each frame.

### Frame Extraction

```python
from backend.services.video_processor import VideoProcessor

processor = VideoProcessor(output_dir="data/thumbnails")
frames = await processor.extract_frames_for_detection(
    video_path="video.mp4",
    interval_seconds=2.0,  # Extract frame every 2 seconds
    max_frames=30          # Maximum frames per video
)
# Returns: ["frame_0000.jpg", "frame_0001.jpg", ...]
```

### ffmpeg Commands Used

**Metadata** (`ffprobe`):

```bash
ffprobe -v quiet -print_format json -show_format -show_streams video.mp4
```

**Frame extraction** (`ffmpeg`):

```bash
ffmpeg -y -ss 2.0 -i video.mp4 -vframes 1 -q:v 2 frame.jpg
```

**Thumbnail** (`ffmpeg`):

```bash
ffmpeg -ss 1.0 -i video.mp4 -vframes 1 \
    -vf "scale=320:240:force_original_aspect_ratio=decrease" thumbnail.jpg
```

### Video Metadata

Returned by `get_video_metadata()`:

```python
{"duration": 30.5, "video_codec": "h264", "video_width": 1920, "video_height": 1080}
```

---

## Storage Management

### Storage Locations

| Content          | Location           | Format                           |
| ---------------- | ------------------ | -------------------------------- |
| Original Media   | `/export/foscam/`  | Camera FTP uploads               |
| Thumbnails       | `data/thumbnails/` | `{detection_id}_thumb.jpg`       |
| Video Thumbs     | `data/thumbnails/` | `{detection_id}_video_thumb.jpg` |
| Extracted Frames | `data/thumbnails/` | `{stem}_frames/frame_NNNN.jpg`   |

### Thumbnail Generation

```python
from backend.services import ThumbnailGenerator

generator = ThumbnailGenerator(output_dir="data/thumbnails")
path = generator.generate_thumbnail(
    image_path="image.jpg",
    detections=[{"object_type": "person", "confidence": 0.95,
                 "bbox_x": 100, "bbox_y": 150, "bbox_width": 200, "bbox_height": 400}],
    detection_id=123
)
```

**Bounding Box Colors:**

- person: Red | car/truck: Blue | dog/cat: Green | bicycle: Yellow | bird: Purple

### Retention

`CleanupService` runs daily (default 3 AM):

```python
cleanup = CleanupService(retention_days=30, delete_images=False)
stats = await cleanup.run_cleanup()
# Deletes: old Events, Detections, GPUStats, thumbnails
```

---

## AI Integration

### YOLO26 API

**Request:**

```http
POST /detect HTTP/1.1
Content-Type: multipart/form-data

file=<image bytes>
```

**Response:**

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": { "x": 100, "y": 150, "width": 200, "height": 400 }
    }
  ],
  "inference_time_ms": 45.2
}
```

### Confidence Filtering

Only detections >= threshold are stored:

```bash
DETECTION_CONFIDENCE_THRESHOLD=0.5
```

### Security Classes

YOLO26 filters to: `person`, `car`, `truck`, `dog`, `cat`, `bird`, `bicycle`, `motorcycle`, `bus`

---

## Performance

### Batch Processing

| Setting        | Default | Purpose                      |
| -------------- | ------- | ---------------------------- |
| `BATCH_WINDOW` | 90s     | Max batch duration           |
| `BATCH_IDLE`   | 30s     | Close if no new detections   |
| `FAST_PATH`    | 0.90    | Immediate analysis threshold |

### Queue Management

```bash
QUEUE_MAX_SIZE=10000
QUEUE_OVERFLOW_POLICY=dlq  # Dead-letter queue on overflow
```

**Queues:** `detection_queue` -> `analysis_queue`
**DLQ:** `dlq:detection_queue`, `dlq:analysis_queue`

### Memory/I/O

- Images loaded fully into memory (~20MB for 4K)
- Video frames extracted via ffmpeg subprocess (low memory)
- Frames cleaned up after processing

---

## Extension Points

### Adding New Sources

Implement the queue contract:

```python
await redis.add_to_queue("detection_queue", {
    "camera_id": "new_cam",
    "file_path": "/path/to/file.jpg",
    "timestamp": datetime.now().isoformat(),
    "media_type": "image"
})
```

### Custom Preprocessing

Extend `DetectionQueueWorker._process_image_detection()` with preprocessing before detection.

### Alternative AI Models

Replace YOLO26 with any model that implements:

```
POST /detect (multipart file) -> {"detections": [...]}
```

---

## Configuration

| Variable                         | Default          | Description               |
| -------------------------------- | ---------------- | ------------------------- |
| `FOSCAM_BASE_PATH`               | `/export/foscam` | Camera upload root        |
| `FILE_WATCHER_POLLING`           | `false`          | Use polling observer      |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5`            | Minimum confidence        |
| `VIDEO_FRAME_INTERVAL_SECONDS`   | `2.0`            | Frame extraction interval |
| `VIDEO_MAX_FRAMES`               | `30`             | Max frames per video      |
| `DEDUPE_TTL_SECONDS`             | `300`            | Deduplication window      |
| `RETENTION_DAYS`                 | `30`             | Data retention            |

---

## Next Steps

- [Pipeline Overview](pipeline-overview.md) - Detection and analysis details
- [Detection Service](detection-service.md) - How YOLO26 processes images

---

## See Also

- [AI Overview](../operator/ai-overview.md) - AI services architecture
- [Environment Variable Reference](../reference/config/env-reference.md) - Video processing configuration
- [Data Model](data-model.md) - Detection database schema

---

[Back to Developer Hub](README.md)
