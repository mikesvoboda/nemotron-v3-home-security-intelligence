"""NVIDIA Triton Inference Server Integration for AI Pipeline.

This package provides client wrappers and utilities for interacting with
NVIDIA Triton Inference Server for high-performance model inference.

Key Features:
- Dynamic batching for improved GPU utilization
- Model versioning and management
- Multi-model serving on single server
- gRPC and HTTP client support
- Automatic request coalescing

Components:
- TritonClient: High-level client for inference requests
- TritonConfig: Configuration management
- Model configs: config.pbtxt files for each model

Model Repository Structure:
    ai/triton/model_repository/
      yolo26/
        config.pbtxt
        1/
          model.plan  # TensorRT engine
      yolo26/
        config.pbtxt
        1/
          model.plan  # TensorRT engine

Usage:
    from ai.triton import TritonClient, TritonConfig

    # Create client with default configuration
    config = TritonConfig.from_env()
    client = TritonClient(config)

    # Run inference
    detections = await client.detect(image_data, model="yolo26")

Environment Variables:
    TRITON_URL: Triton server URL (default: localhost:8001 for gRPC)
    TRITON_HTTP_URL: Triton HTTP URL (default: localhost:8000)
    TRITON_TIMEOUT: Request timeout in seconds (default: 60)
    TRITON_MODEL: Default model name (default: yolo26)
    TRITON_ENABLED: Enable Triton inference (default: false)

References:
    - Triton Inference Server: https://github.com/triton-inference-server/server
    - Triton Client: https://github.com/triton-inference-server/client
"""

from ai.triton.client import (
    TritonClient,
    TritonConfig,
    TritonConnectionError,
    TritonInferenceError,
    TritonModelNotFoundError,
)

__all__ = [
    "TritonClient",
    "TritonConfig",
    "TritonConnectionError",
    "TritonInferenceError",
    "TritonModelNotFoundError",
]

__version__ = "1.0.0"
