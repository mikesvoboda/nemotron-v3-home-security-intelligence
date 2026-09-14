# AI Enrichment Utilities

## Purpose

Video processing utilities for the AI Enrichment Service, built on the Supervision library from Roboflow. Provides object tracking with ByteTrack, frame annotation, and activity heatmap generation for security video analytics.

## Directory Structure

```
ai/enrichment/utils/
├── AGENTS.md              # This file
├── __init__.py            # Package exports
└── video_processing.py    # ByteTrack tracking, annotators, heatmaps
```

## Key Components

### video_processing.py

Video analytics utilities using the Supervision library.

#### Configuration Classes

| Class             | Purpose                         | Key Settings                                  |
| ----------------- | ------------------------------- | --------------------------------------------- |
| `ByteTrackConfig` | ByteTrack tracker configuration | lost_track_buffer, track_activation_threshold |
| `AnnotatorConfig` | Frame annotation settings       | box_enabled, label_enabled, trace_enabled     |
| `HeatmapConfig`   | Activity heatmap settings       | radius, opacity, color_map, decay_factor      |
| `TrackingResult`  | Single tracked object result    | tracker_id, class_name, confidence, bbox      |

#### Classes

| Class            | Purpose                          | Key Methods                                   |
| ---------------- | -------------------------------- | --------------------------------------------- |
| `VideoAnnotator` | Annotates frames with detections | annotate_frame(), generate_labels()           |
| `VideoProcessor` | Integrates tracking + annotation | process_frame(), reset(), get_active_tracks() |

#### Factory Functions

| Function                   | Purpose                            | Returns        |
| -------------------------- | ---------------------------------- | -------------- |
| `create_bytetrack_tracker` | Create ByteTrack with config       | sv.ByteTrack   |
| `create_video_annotator`   | Create annotator with config       | VideoAnnotator |
| `create_video_processor`   | Create full processor with configs | VideoProcessor |

## ByteTrack Tracking

ByteTrack is a multi-object tracking algorithm that assigns unique IDs to detected objects and tracks them across video frames.

### Configuration

```python
from ai.enrichment.utils.video_processing import ByteTrackConfig

# Default: 30-frame buffer for brief occlusions
config = ByteTrackConfig()

# Custom: longer buffer for challenging conditions
config = ByteTrackConfig(
    lost_track_buffer=60,           # Frames before losing track
    track_activation_threshold=0.3,  # Min confidence to start track
    minimum_matching_threshold=0.8,  # Min IoU for matching
    minimum_consecutive_frames=3,    # Frames before confirming
)
```

### Usage with YOLO

```python
from ai.enrichment.utils.video_processing import create_video_processor
from ultralytics import YOLO

model = YOLO("yolo26m.pt")
processor = create_video_processor()

for frame in video_frames:
    results = model(frame)
    tracking_results = processor.process_frame(frame, results[0])

    for track in tracking_results:
        print(f"Track #{track.tracker_id}: {track.class_name} "
              f"({track.confidence:.0%})")

# Reset between videos
processor.reset()
```

## Frame Annotation

Annotators draw visual overlays on video frames for debugging and visualization.

### Available Annotators

| Annotator        | Purpose                             | Enabled by Default |
| ---------------- | ----------------------------------- | ------------------ |
| BoxAnnotator     | Bounding boxes around detections    | Yes                |
| LabelAnnotator   | Class name and confidence labels    | Yes                |
| TraceAnnotator   | Movement traces for tracked objects | No                 |
| HeatMapAnnotator | Activity heatmap overlay            | No                 |

### Annotation Example

```python
from ai.enrichment.utils.video_processing import (
    AnnotatorConfig,
    create_video_processor,
)

# Enable traces for movement visualization
config = AnnotatorConfig(
    trace_enabled=True,
    trace_length=30,       # 30 positions in trace
    trace_thickness=2,
)

processor = create_video_processor(annotator_config=config)

# Get annotated frame
results, annotated_frame = processor.process_frame(
    frame, yolo_results, annotate=True
)
```

## Activity Heatmaps

Heatmaps visualize areas of high detection activity over time.

### Heatmap Configuration

```python
from ai.enrichment.utils.video_processing import (
    AnnotatorConfig,
    HeatmapConfig,
    create_video_processor,
)

annotator_config = AnnotatorConfig(heatmap_enabled=True)
heatmap_config = HeatmapConfig(
    radius=25,                   # Gaussian blur radius
    opacity=0.5,                 # Overlay opacity [0-1]
    color_map="turbo",           # Color scheme
    position_anchor="bottom_center",  # Detection anchor point
    decay_factor=0.99,           # Temporal decay
)

processor = create_video_processor(
    annotator_config=annotator_config,
    heatmap_config=heatmap_config,
)
```

## Integration with Enrichment Service

The video processing utilities integrate with the enrichment service for enhanced detection tracking.

### Example: Track Person Across Frames

```python
from ai.enrichment.utils.video_processing import create_video_processor

processor = create_video_processor()

# Process video frames
for frame, yolo_result in zip(frames, yolo_results):
    tracks = processor.process_frame(frame, yolo_result)

    for track in tracks:
        if track.class_name == "person":
            # Track persists across frames with same ID
            print(f"Person #{track.tracker_id} at {track.bbox}")

# Get all currently active tracks
active = processor.get_active_tracks()
print(f"Currently tracking {len(active)} objects")
```

## Testing

```bash
# Run video processing tests
uv run pytest ai/enrichment/tests/test_video_processing.py -v

# Run with coverage
uv run pytest ai/enrichment/tests/test_video_processing.py -v --cov=ai.enrichment.utils
```

## Dependencies

- **supervision>=0.25.0**: Roboflow's video analytics library
- **numpy**: Array operations for frames and bounding boxes
- **ultralytics**: YOLO model integration (optional, for detection)

## Environment Variables

| Variable         | Default | Description                           |
| ---------------- | ------- | ------------------------------------- |
| (none currently) | -       | Video processing uses default configs |

Future environment variables may include:

- `BYTETRACK_LOST_BUFFER`: Default lost track buffer
- `ANNOTATION_TRACE_ENABLED`: Enable trace by default

## See Also

- `/ai/enrichment/AGENTS.md` - Main enrichment service documentation
- `/ai/enrichment/model_manager.py` - Model loading for detectors
- [Supervision docs](https://supervision.roboflow.com/) - Official documentation
- [ByteTrack](https://supervision.roboflow.com/trackers/) - Tracker documentation
