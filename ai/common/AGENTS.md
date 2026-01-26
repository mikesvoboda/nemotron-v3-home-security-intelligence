# AI Common Infrastructure

## Purpose

Provides reusable infrastructure for TensorRT-optimized AI model inference across the Model Zoo. This package enables model-agnostic TensorRT acceleration with automatic PyTorch fallback.

## Directory Structure

```
ai/common/
├── AGENTS.md                  # This file
├── __init__.py                # Package exports
├── tensorrt_utils.py          # TensorRT conversion and engine management
├── tensorrt_inference.py      # Base classes for TensorRT-accelerated inference
└── tests/
    ├── __init__.py
    ├── test_tensorrt_utils.py      # TensorRT utilities tests
    └── test_tensorrt_inference.py  # Inference base class tests
```

## Key Components

### tensorrt_utils.py

Core TensorRT utilities for ONNX-to-TensorRT conversion and engine management.

| Class/Function                 | Purpose                                   |
| ------------------------------ | ----------------------------------------- |
| `TensorRTConverter`            | Convert ONNX models to TensorRT engines   |
| `TensorRTEngine`               | Wrapper for TensorRT engine inference     |
| `TensorRTConfig`               | Configuration dataclass for TensorRT      |
| `TensorRTPrecision`            | Enum for precision modes (FP32/FP16/INT8) |
| `is_tensorrt_available()`      | Check if TensorRT is installed            |
| `get_gpu_compute_capability()` | Get GPU SM version for engine caching     |
| `get_gpu_name()`               | Get GPU name string                       |

### tensorrt_inference.py

Abstract base classes for model implementations with TensorRT support.

| Class                         | Purpose                                      |
| ----------------------------- | -------------------------------------------- |
| `TensorRTInferenceBase`       | Generic base class with automatic fallback   |
| `TensorRTDetectionModel`      | Specialized base for object detection models |
| `TensorRTClassificationModel` | Specialized base for classification models   |

## Environment Variables

| Variable                      | Default                   | Description                        |
| ----------------------------- | ------------------------- | ---------------------------------- |
| `TENSORRT_ENABLED`            | `"true"`                  | Global toggle for TensorRT         |
| `TENSORRT_PRECISION`          | `"fp16"`                  | Default precision (fp32/fp16/int8) |
| `TENSORRT_CACHE_DIR`          | `"models/tensorrt_cache"` | Engine cache directory             |
| `TENSORRT_MAX_WORKSPACE_SIZE` | `1073741824` (1GB)        | Max workspace memory in bytes      |
| `TENSORRT_VERBOSE`            | `"false"`                 | Enable verbose TensorRT logging    |

## Usage Examples

### Converting ONNX to TensorRT

```python
from ai.common import TensorRTConverter, is_tensorrt_available
from pathlib import Path

if is_tensorrt_available():
    converter = TensorRTConverter(precision="fp16")
    engine_path = converter.convert_onnx_to_trt(
        onnx_path=Path("model.onnx"),
        input_shapes={"input": (1, 3, 640, 640)},
        dynamic_axes={"input": [0]},  # Dynamic batch dimension
    )
```

### Running Inference with Engine

```python
from ai.common import TensorRTEngine
import numpy as np

engine = TensorRTEngine(engine_path)
outputs = engine.infer({"input": np.random.randn(1, 3, 640, 640).astype(np.float32)})
```

### Implementing a Model with TensorRT Support

```python
from ai.common import TensorRTInferenceBase
from pathlib import Path
import numpy as np

class MyDetector(TensorRTInferenceBase):
    def _init_pytorch(self):
        # Load PyTorch model (fallback)
        self.pytorch_model = load_my_model()

    def _init_tensorrt(self, onnx_path, precision):
        # Convert and load TensorRT engine
        from ai.common import TensorRTConverter, TensorRTEngine
        converter = TensorRTConverter(precision=precision)
        engine_path = converter.convert_onnx_to_trt(
            onnx_path=onnx_path,
            input_shapes={"input": (1, 3, 640, 640)},
        )
        self.trt_engine = TensorRTEngine(engine_path)

    def preprocess(self, image):
        # Normalize and convert to array
        return {"input": normalized_array}

    def postprocess(self, outputs):
        # Process detections
        return detections

# Usage - automatic backend selection
model = MyDetector(
    model_name="my_detector",
    onnx_path=Path("model.onnx"),
    use_tensorrt=True,  # Falls back to PyTorch if TensorRT unavailable
)
result = model(image)
```

## GPU Architecture Caching

TensorRT engines are architecture-specific and cannot be shared across different GPU types. The converter automatically includes the GPU SM version in the cache key:

```
models/tensorrt_cache/
├── model_sm_86_fp16_a1b2c3d4.engine  # For RTX 3090 (SM 8.6)
├── model_sm_89_fp16_a1b2c3d4.engine  # For RTX 4090 (SM 8.9)
└── model_sm_75_fp16_a1b2c3d4.engine  # For RTX 2080 (SM 7.5)
```

The cache key includes:

- Model name (from ONNX filename)
- GPU SM version (e.g., sm_86)
- Precision mode (fp32/fp16/int8)
- ONNX file hash (first 8 chars of SHA256)

## INT8 Calibration

For INT8 precision, calibration data is required:

```python
# Prepare calibration dataset (representative inputs)
calibration_data = np.stack([
    preprocess(img) for img in calibration_images
], axis=0).astype(np.float32)

converter = TensorRTConverter(precision="int8")
engine_path = converter.convert_onnx_to_trt(
    onnx_path=Path("model.onnx"),
    input_shapes={"input": (1, 3, 640, 640)},
    calibration_data=calibration_data,
)
```

## Testing

```bash
# Run TensorRT infrastructure tests
uv run pytest ai/common/tests/ -v

# Run with verbose output
uv run pytest ai/common/tests/ -v --tb=short
```

Tests are designed to run regardless of TensorRT availability using mocks.

## Integration with Model Zoo

Models in the Model Zoo should inherit from the appropriate base class:

| Model Type       | Base Class                    | Example Models                     |
| ---------------- | ----------------------------- | ---------------------------------- |
| Object Detection | `TensorRTDetectionModel`      | YOLO26, YOLO, Threat Detector      |
| Classification   | `TensorRTClassificationModel` | Pet Classifier, Vehicle Classifier |
| Pose Estimation  | `TensorRTInferenceBase`       | ViTPose, YOLOv8-pose               |
| Embeddings       | `TensorRTInferenceBase`       | CLIP, Person ReID                  |

## Performance Expectations

| Precision | Accuracy Impact | Speed Improvement | Memory Reduction |
| --------- | --------------- | ----------------- | ---------------- |
| FP32      | None            | 1.5-2x            | 0%               |
| FP16      | Minimal (<1%)   | 2-4x              | ~50%             |
| INT8      | Low (1-3%)      | 4-8x              | ~75%             |

## Entry Points

1. **Start here**: This file (`ai/common/AGENTS.md`)
2. **TensorRT utilities**: `tensorrt_utils.py`
3. **Base classes**: `tensorrt_inference.py`
4. **Tests**: `tests/test_tensorrt_utils.py`, `tests/test_tensorrt_inference.py`
5. **Model implementations**: See `ai/enrichment/models/` for examples
