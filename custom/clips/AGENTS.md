# Custom Clips Directory - Agent Guide

## Purpose

This directory is a placeholder for custom video clips used for testing, benchmarking, and validating the AI detection pipeline. It allows users to test the system with specific scenarios before deploying with live camera feeds.

## Directory Contents

```
clips/
  AGENTS.md     # This file
  (empty)       # Add your test clips here
```

## Usage

### Adding Test Clips

Place video or image files here for testing:

**Supported Formats:**

- Video: `.mp4`, `.avi`, `.mkv`, `.mov`
- Images: `.jpg`, `.jpeg`, `.png`

**Naming Convention (recommended):**

```
{scenario}_{timestamp}.{ext}
person_entering_20240115_1200.mp4
car_driveway_20240115_1430.jpg
```

### Testing with Clips

To test the detection pipeline with custom clips:

```bash
# Run detection on a specific image
curl -X POST http://localhost:8090/detect \
  -F "image=@custom/clips/test_image.jpg"

# Or use the E2E test script
uv run python scripts/test_ai_pipeline_e2e.py --input custom/clips/test_image.jpg
```

### Benchmark Clips

For benchmarking detection accuracy:

1. Place clips with known ground truth
2. Run benchmark script:
   ```bash
   uv run python scripts/benchmark_model_zoo.py --input custom/clips/
   ```

## Example Test Scenarios

| Scenario         | Description                   | Expected Detection      |
| ---------------- | ----------------------------- | ----------------------- |
| Person at door   | Person standing at front door | person, high confidence |
| Car in driveway  | Vehicle entering driveway     | car, medium confidence  |
| Package delivery | Delivery person with package  | person + package        |
| Night vision     | Low-light scenario            | Reduced accuracy        |
| False positive   | Tree branch moving            | No detection expected   |

## Git Ignore Rules

Video files in this directory are typically ignored:

```gitignore
custom/clips/*.mp4
custom/clips/*.avi
custom/clips/*.mkv
```

Keep the directory structure in version control but not the actual clips.

## Related Files

- `/ai/rtdetr/` - RT-DETRv2 detection model
- `/scripts/test_ai_pipeline_e2e.py` - E2E testing script
- `/scripts/benchmark_model_zoo.py` - Model benchmarking
- `/backend/services/detector_service.py` - Detection service
