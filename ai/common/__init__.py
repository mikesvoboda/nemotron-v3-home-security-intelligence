"""Common AI Infrastructure for TensorRT Optimization.

This package provides reusable infrastructure for TensorRT-optimized
AI model inference across the Model Zoo.

Modules:
- tensorrt_utils: TensorRT conversion and engine management
- tensorrt_inference: Base classes for TensorRT-accelerated inference

Example Usage:
    from ai.common import (
        TensorRTConverter,
        TensorRTEngine,
        TensorRTConfig,
        TensorRTInferenceBase,
        is_tensorrt_available,
    )

    # Check TensorRT availability
    if is_tensorrt_available():
        converter = TensorRTConverter(precision="fp16")
        engine_path = converter.convert_onnx_to_trt(
            onnx_path=Path("model.onnx"),
            input_shapes={"input": (1, 3, 640, 640)},
        )

Environment Variables:
- TENSORRT_ENABLED: Enable/disable TensorRT globally (default: "true")
- TENSORRT_PRECISION: Default precision mode (default: "fp16")
- TENSORRT_CACHE_DIR: Engine cache directory (default: "models/tensorrt_cache")

For model-specific implementations, see:
- ai/enrichment/models/ - Model Zoo implementations
- ai/rtdetr/ - Object detection (RT-DETR/YOLO)
- ai/clip/ - Image embeddings
"""

from __future__ import annotations

# Version info
__version__ = "1.0.0"
__all__ = [
    # Sorted alphabetically for RUF022 compliance
    "TENSORRT_CACHE_DIR",
    "TENSORRT_ENABLED",
    "TENSORRT_PRECISION",
    "TensorRTClassificationModel",
    "TensorRTConfig",
    "TensorRTConverter",
    "TensorRTDetectionModel",
    "TensorRTEngine",
    "TensorRTInferenceBase",
    "TensorRTPrecision",
    "get_gpu_compute_capability",
    "get_gpu_name",
    "is_tensorrt_available",
]
from .tensorrt_inference import (
    TensorRTClassificationModel,
    TensorRTDetectionModel,
    TensorRTInferenceBase,
)
from .tensorrt_utils import (
    TENSORRT_CACHE_DIR,
    TENSORRT_ENABLED,
    TENSORRT_PRECISION,
    TensorRTConfig,
    TensorRTConverter,
    TensorRTEngine,
    TensorRTPrecision,
    get_gpu_compute_capability,
    get_gpu_name,
    is_tensorrt_available,
)
