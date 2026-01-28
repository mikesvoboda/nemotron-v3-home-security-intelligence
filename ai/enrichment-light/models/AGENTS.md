# Enrichment Light Models

## Purpose

Lightweight AI models optimized for the secondary GPU (A400 4GB) in multi-GPU configurations. These models provide person re-identification, pose estimation, and threat detection with minimal VRAM footprint and TensorRT acceleration support.

## Directory Structure

```
ai/enrichment-light/models/
├── AGENTS.md            # This file
├── __init__.py          # Package exports
├── person_reid.py       # OSNet-x0.25 person re-identification
├── pose_estimator.py    # YOLOv8n-pose human pose estimation
└── threat_detector.py   # YOLOv8n weapon/threat detection
```

## Key Files

### __init__.py

Package exports for model classes:

```python
from models.person_reid import PersonReID
from models.pose_estimator import PoseEstimator
from models.threat_detector import ThreatDetector

__all__ = ["PersonReID", "PoseEstimator", "ThreatDetector"]
```

### person_reid.py

OSNet-x0.25 person re-identification for tracking individuals across cameras.

| Class/Function       | Purpose                                         |
| -------------------- | ----------------------------------------------- |
| `PersonReID`         | Main model wrapper for embedding extraction     |
| `ReIDResult`         | Dataclass for embedding + hash result           |
| `OSNet`              | Standalone OSNet architecture (no torchreid)    |
| `create_osnet_x0_25` | Factory for OSNet-x0.25 configuration           |
| `load_person_reid`   | Factory function for model registry             |

**Features:**
- 512-dimensional normalized embeddings
- L2 normalization for cosine similarity
- Embedding hash for quick lookup
- ~100MB VRAM usage

**Usage:**
```python
reid = PersonReID("/models/osnet-reid")
reid.load_model()
result = reid.extract_embedding(person_crop)
similarity = reid.compute_similarity(emb1, emb2)
is_same = reid.is_same_person(emb1, emb2, threshold=0.7)
```

**Constants:**
- `OSNET_INPUT_HEIGHT`: 256
- `OSNET_INPUT_WIDTH`: 128
- `EMBEDDING_DIMENSION`: 512
- `DEFAULT_SIMILARITY_THRESHOLD`: 0.7

### pose_estimator.py

YOLOv8n-pose for human pose estimation with suspicious pose detection.

| Class/Function         | Purpose                                       |
| ---------------------- | --------------------------------------------- |
| `PoseEstimator`        | Main model wrapper for pose estimation        |
| `Keypoint`             | Dataclass for single keypoint (x, y, conf)    |
| `PoseResult`           | Dataclass with keypoints, pose_class, flags   |
| `load_pose_estimator`  | Factory function for model registry           |
| `validate_model_path`  | Security validation for model paths           |

**Features:**
- 17 COCO keypoints (nose, eyes, ears, shoulders, etc.)
- Pose classification (standing, crouching, running, reaching_up, crawling)
- Suspicious pose flagging (crouching, crawling, hiding, reaching_up)
- TensorRT acceleration (NEM-3838)
- Batch inference support (NEM-3377)

**VRAM Usage:**
- ~300MB (PyTorch)
- ~200MB (TensorRT FP16)

**Environment Variables:**
- `POSE_USE_TENSORRT`: Enable TensorRT (default: false)
- `POSE_TENSORRT_ENGINE_PATH`: Custom engine path
- `POSE_TENSORRT_FP16`: Use FP16 precision (default: true)

**Usage:**
```python
estimator = PoseEstimator("/models/yolov8n-pose.pt", use_tensorrt=True)
estimator.load_model()
result = estimator.estimate_pose(image)
print(f"Pose: {result.pose_class}, Suspicious: {result.is_suspicious}")
```

### threat_detector.py

YOLOv8n for detecting weapons and dangerous objects.

| Class/Function         | Purpose                                       |
| ---------------------- | --------------------------------------------- |
| `ThreatDetector`       | Main model wrapper for threat detection       |
| `ThreatDetection`      | Single detection result with severity         |
| `ThreatResult`         | Full result with threats list and metadata    |
| `load_threat_detector` | Factory function for model registry           |

**Threat Classes:**
| Class    | Severity |
| -------- | -------- |
| knife    | high     |
| gun      | critical |
| rifle    | critical |
| pistol   | critical |
| bat      | medium   |
| crowbar  | medium   |

**VRAM Usage:**
- ~400MB (PyTorch)
- ~300MB (TensorRT FP16)

**Environment Variables:**
- `THREAT_USE_TENSORRT` / `THREAT_DETECTOR_USE_TENSORRT`: Enable TensorRT
- `THREAT_TENSORRT_ENGINE_PATH`: Custom engine path
- `THREAT_TENSORRT_FP16`: Use FP16 precision (default: true)

**Usage:**
```python
detector = ThreatDetector("/models/threat-detection.pt", use_tensorrt=True)
detector.load_model()
result = detector.detect_threats(image)
if result.has_threat:
    print(f"Max severity: {result.max_severity}")
```

## Model Specifications

| Model           | Architecture   | Input Size | VRAM (PyTorch) | VRAM (TensorRT) |
| --------------- | -------------- | ---------- | -------------- | --------------- |
| PersonReID      | OSNet-x0.25    | 256x128    | ~100MB         | N/A             |
| PoseEstimator   | YOLOv8n-pose   | 640x640    | ~300MB         | ~200MB          |
| ThreatDetector  | YOLOv8n        | 640x640    | ~400MB         | ~300MB          |

## TensorRT Support

Both PoseEstimator and ThreatDetector support TensorRT acceleration:

1. **Auto-export**: On first load with TensorRT enabled, the engine is auto-built
2. **Cache directory**: Engines cached in `/cache/tensorrt/` (read-only model mounts)
3. **Fallback**: Automatic PyTorch fallback if TensorRT fails
4. **Architecture-specific**: Engines must be rebuilt per GPU architecture

## Common Patterns

### Model Loading with TensorRT

```python
# Environment-based TensorRT toggle
model = PoseEstimator(
    model_path="/models/yolov8n-pose.pt",
    use_tensorrt=True,  # or None to use env var
)
model.load_model()  # Auto-exports to TensorRT if needed

# Check backend
info = model.get_backend_info()
print(f"Using: {info['backend']}")  # 'tensorrt' or 'pytorch'
```

### Batch Inference

```python
images = [img1, img2, img3]
results = model.estimate_poses_batch(images)
```

### Resource Management

```python
model.load_model()
try:
    result = model.detect_threats(image)
finally:
    model.unload()  # Free VRAM
```

## Entry Points

1. **Package**: `from ai.enrichment_light.models import PersonReID, PoseEstimator, ThreatDetector`
2. **AI overview**: `ai/AGENTS.md`
3. **Related enrichment module**: `ai/enrichment/AGENTS.md`
4. **Export scripts**: `ai/enrichment/scripts/AGENTS.md`
5. **TensorRT infrastructure**: `ai/common/AGENTS.md`

## Related Documentation

- Multi-GPU configuration: `docs/development/multi-gpu.md`
- Model Zoo: `backend/services/model_zoo.py`
- Video Analytics Guide: `docs/guides/video-analytics.md`
