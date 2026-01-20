# AI Enrichment Models

This directory contains on-demand model implementations for the ai-enrichment service. Each model is designed to be loaded lazily when needed to optimize VRAM usage.

## Directory Structure

```
models/
  __init__.py              # Package exports
  action_recognizer.py     # X-CLIP video action recognition
  demographics.py          # Age/gender classification (existing)
  person_reid.py           # Person re-identification (existing)
```

## Model Priority Levels

Models are prioritized for VRAM allocation:

| Priority | Level | Models                       |
| -------- | ----- | ---------------------------- |
| CRITICAL | 0     | Threat detection (weapons)   |
| HIGH     | 1     | Pose, demographics, clothing |
| MEDIUM   | 2     | Vehicle, pet, re-ID          |
| LOW      | 3     | Depth, action recognition    |

## ActionRecognizer (X-CLIP)

### Overview

Video-based action recognition using Microsoft's X-CLIP model for zero-shot classification.

### Specifications

- **Model**: `microsoft/xclip-base-patch32`
- **VRAM**: ~1.5GB
- **Priority**: LOW (expensive, use sparingly)
- **Input**: 8-32 video frames
- **Output**: Action classification with confidence

### Trigger Conditions

Only run action recognition when:

1. Person detected for >3 seconds
2. Multiple frames available in buffer
3. Unusual pose detected (trigger from pose estimator)

### Security Action Classes (15 total)

**Normal Activities:**

- walking normally
- running
- delivering package
- checking mailbox
- ringing doorbell
- waving
- falling down
- carrying large object

**Suspicious Activities (flagged):**

- fighting
- climbing
- breaking window
- picking lock
- hiding
- loitering
- looking around suspiciously

### Usage Example

```python
from ai.enrichment.models.action_recognizer import (
    ActionRecognizer,
    load_action_recognizer,
)

# Create and load model
recognizer = load_action_recognizer(
    model_path="microsoft/xclip-base-patch32",
    device="cuda:0",
)

# Recognize action from video frames
frames = [...]  # List of PIL Images or numpy arrays
result = recognizer.recognize_action(frames)

print(f"Action: {result.action}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Suspicious: {result.is_suspicious}")
```

### Integration with Model Registry

The ActionRecognizer is registered in `model_registry.py` and can be loaded on-demand:

```python
from ai.enrichment.model_registry import get_models_for_detection_type

# Get models for suspicious person detection with multiple frames
models = get_models_for_detection_type(
    detection_type="person",
    is_suspicious=True,
    has_multiple_frames=True,
)
# Returns: ["fashion_clip", "depth_estimator", "action_recognizer"]
```

## Testing

```bash
# Run unit tests
uv run pytest ai/enrichment/tests/test_action_recognizer.py -v

# With coverage
uv run pytest ai/enrichment/tests/test_action_recognizer.py --cov=ai.enrichment.models.action_recognizer
```

## Related Documentation

- [Model Zoo Design Document](../../../docs/plans/2026-01-19-model-zoo-prompt-improvements-design.md)
- [Model Manager](../model_manager.py)
- [Model Registry](../model_registry.py)
