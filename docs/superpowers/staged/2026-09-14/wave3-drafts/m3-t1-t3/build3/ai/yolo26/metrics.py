"""Prometheus metrics for YOLO26 inference server.

This module provides comprehensive Prometheus metrics for monitoring the YOLO26
object detection service, including:

- Inference latency and throughput
- Detection counts by class
- VRAM usage monitoring
- Error tracking
- Batch processing metrics

Metrics follow Prometheus naming conventions and best practices:
- Use _total suffix for counters
- Use _seconds suffix for duration histograms
- Use _bytes suffix for byte measurements

Usage:
    from metrics import record_inference, record_detection, record_error

    # After successful inference:
    record_inference(endpoint="detect", duration_seconds=0.045, success=True)

    # For each detection:
    record_detection(class_name="person")

    # Or batch record detections:
    record_detections([{"class": "person"}, {"class": "car"}])

    # On error:
    record_error(error_type="invalid_image")
"""

import logging

import torch
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# =============================================================================
# Core Inference Metrics (required by acceptance criteria)
# =============================================================================

# Inference duration histogram (yolo26_inference_duration_seconds)
# Buckets tuned for typical inference times (10-100ms for TensorRT)
INFERENCE_DURATION_SECONDS = Histogram(
    "yolo26_inference_duration_seconds",
    "Inference duration in seconds",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Request counter (yolo26_requests_total)
REQUESTS_TOTAL = Counter(
    "yolo26_requests_total",
    "Total number of requests to YOLO26",
    ["endpoint", "status"],
)

# Detection counter by class (yolo26_detections_total)
DETECTIONS_TOTAL = Counter(
    "yolo26_detections_total",
    "Total number of detections by class",
    ["class_name"],
)

# VRAM usage gauge in bytes (yolo26_vram_bytes)
VRAM_BYTES = Gauge(
    "yolo26_vram_bytes",
    "VRAM usage in bytes",
)

# Error counter (yolo26_errors_total)
ERRORS_TOTAL = Counter(
    "yolo26_errors_total",
    "Total number of errors by type",
    ["error_type"],
)

# Batch size histogram (yolo26_batch_size)
BATCH_SIZE = Histogram(
    "yolo26_batch_size",
    "Batch size distribution for batch inference requests",
    buckets=[1, 2, 4, 8, 16, 32, 64, 128],
)

# =============================================================================
# Legacy Metrics (backwards compatibility with existing model.py)
# =============================================================================
# These maintain compatibility with existing dashboards and monitoring

# Total inference requests (legacy name)
INFERENCE_REQUESTS_TOTAL = Counter(
    "yolo26_inference_requests_total",
    "Total number of inference requests",
    ["endpoint", "status"],
)

# Inference latency histogram (legacy name)
INFERENCE_LATENCY_SECONDS = Histogram(
    "yolo26_inference_latency_seconds",
    "Inference latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Number of detections per image (legacy)
DETECTIONS_PER_IMAGE = Histogram(
    "yolo26_detections_per_image",
    "Number of detections per image",
    buckets=[0, 1, 2, 3, 5, 10, 20, 50, 100],
)

# Model status gauge (1 = loaded, 0 = not loaded)
MODEL_LOADED = Gauge(
    "yolo26_model_loaded",
    "Whether the model is loaded (1) or not (0)",
)

# Model inference health gauge (1 = inference tested and working, 0 = inference failed/not tested)
# NEM-3878: This metric tracks whether warmup inference succeeded on startup
MODEL_INFERENCE_HEALTHY = Gauge(
    "yolo26_model_inference_healthy",
    "Whether model inference has been tested and is working (1) or not (0)",
)

# GPU metrics gauges (legacy)
GPU_UTILIZATION = Gauge(
    "yolo26_gpu_utilization_percent",
    "GPU utilization percentage",
)

GPU_MEMORY_USED_GB = Gauge(
    "yolo26_gpu_memory_used_gb",
    "GPU memory used in GB",
)

GPU_TEMPERATURE = Gauge(
    "yolo26_gpu_temperature_celsius",
    "GPU temperature in Celsius",
)

GPU_POWER_WATTS = Gauge(
    "yolo26_gpu_power_watts",
    "GPU power usage in Watts",
)


# =============================================================================
# Helper Functions for Recording Metrics
# =============================================================================


def record_inference(
    endpoint: str,
    duration_seconds: float,
    success: bool,
) -> None:
    """Record inference request metrics.

    Records both the new standardized metrics and legacy metrics for
    backwards compatibility.

    Args:
        endpoint: The endpoint name (e.g., "detect", "detect_batch")
        duration_seconds: Time taken for inference in seconds
        success: Whether the inference succeeded
    """
    status = "success" if success else "error"

    # Record new standardized metrics
    INFERENCE_DURATION_SECONDS.labels(endpoint=endpoint).observe(duration_seconds)
    REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()

    # Record legacy metrics for backwards compatibility
    INFERENCE_LATENCY_SECONDS.labels(endpoint=endpoint).observe(duration_seconds)
    INFERENCE_REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()


def record_detection(class_name: str) -> None:
    """Record a single detection by class.

    Args:
        class_name: The class name of the detected object (e.g., "person", "car")
    """
    DETECTIONS_TOTAL.labels(class_name=class_name).inc()


def record_detections(detections: list[dict]) -> None:
    """Record multiple detections from an inference result.

    Args:
        detections: List of detection dicts with "class" key
    """
    for detection in detections:
        class_name = detection.get("class") or detection.get("class_name")
        if class_name:
            record_detection(class_name)


def record_error(error_type: str) -> None:
    """Record an error occurrence.

    Args:
        error_type: Type of error (e.g., "invalid_image", "model_error", "timeout")
    """
    ERRORS_TOTAL.labels(error_type=error_type).inc()


def record_batch_size(batch_size: int) -> None:
    """Record batch size for batch inference.

    Args:
        batch_size: Number of images in the batch
    """
    BATCH_SIZE.observe(batch_size)


def update_vram_bytes(vram_bytes: int) -> None:
    """Update VRAM usage gauge.

    Args:
        vram_bytes: VRAM usage in bytes
    """
    VRAM_BYTES.set(vram_bytes)


def get_vram_usage_bytes() -> int | None:
    """Get current VRAM usage in bytes.

    Returns:
        VRAM usage in bytes, or None if CUDA is unavailable
    """
    try:
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated()
    except Exception as e:
        logger.warning(f"Failed to get VRAM usage: {e}")
    return None


def update_gpu_metrics() -> None:
    """Update all GPU-related metrics.

    Updates VRAM usage in both bytes (new) and GB (legacy) formats.
    Should be called periodically or before metrics scraping.
    """
    vram_bytes = get_vram_usage_bytes()
    if vram_bytes is not None:
        VRAM_BYTES.set(vram_bytes)
        GPU_MEMORY_USED_GB.set(vram_bytes / (1024**3))


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Metrics (sorted alphabetically)
    "BATCH_SIZE",
    "DETECTIONS_PER_IMAGE",
    "DETECTIONS_TOTAL",
    "ERRORS_TOTAL",
    "GPU_MEMORY_USED_GB",
    "GPU_POWER_WATTS",
    "GPU_TEMPERATURE",
    "GPU_UTILIZATION",
    "INFERENCE_DURATION_SECONDS",
    "INFERENCE_LATENCY_SECONDS",
    "INFERENCE_REQUESTS_TOTAL",
    "MODEL_INFERENCE_HEALTHY",
    "MODEL_LOADED",
    "REQUESTS_TOTAL",
    "VRAM_BYTES",
    # Helper functions (sorted alphabetically)
    "get_vram_usage_bytes",
    "record_batch_size",
    "record_detection",
    "record_detections",
    "record_error",
    "record_inference",
    "update_gpu_metrics",
    "update_vram_bytes",
]
