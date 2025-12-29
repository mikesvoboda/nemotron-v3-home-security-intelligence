"""Prometheus metrics definitions and utilities for observability.

This module defines all Prometheus metrics used by the home security
intelligence pipeline and provides helper functions for recording metrics.

Metric Naming Conventions:
- All metrics are prefixed with 'hsi_' (home security intelligence)
- Counters end with '_total'
- Histograms/durations end with '_seconds'
- Gauges use descriptive names without suffix

Usage:
    from backend.core.metrics import (
        record_event_created,
        observe_stage_duration,
        set_queue_depth,
    )

    # Record an event creation
    record_event_created()

    # Record stage duration
    observe_stage_duration("detect", 0.5)

    # Update queue depth
    set_queue_depth("detection", 10)
"""

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Create a custom registry to avoid conflicts with default collectors
# Use the default registry for broader compatibility with prometheus_client
_registry = REGISTRY

# =============================================================================
# Queue Depth Gauges
# =============================================================================

DETECTION_QUEUE_DEPTH = Gauge(
    "hsi_detection_queue_depth",
    "Number of images waiting in the detection queue",
    registry=_registry,
)

ANALYSIS_QUEUE_DEPTH = Gauge(
    "hsi_analysis_queue_depth",
    "Number of batches waiting in the analysis queue",
    registry=_registry,
)

# =============================================================================
# Stage Duration Histograms
# =============================================================================

# Buckets for stage durations (in seconds)
# Covers range from 10ms to 60s with finer granularity at lower values
STAGE_DURATION_BUCKETS = (
    0.01,  # 10ms
    0.025,  # 25ms
    0.05,  # 50ms
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 60s
)

STAGE_DURATION_SECONDS = Histogram(
    "hsi_stage_duration_seconds",
    "Duration of pipeline stages in seconds",
    labelnames=["stage"],
    buckets=STAGE_DURATION_BUCKETS,
    registry=_registry,
)

# =============================================================================
# Event/Detection Counters
# =============================================================================

EVENTS_CREATED_TOTAL = Counter(
    "hsi_events_created_total",
    "Total number of security events created",
    registry=_registry,
)

DETECTIONS_PROCESSED_TOTAL = Counter(
    "hsi_detections_processed_total",
    "Total number of detections processed by RT-DETRv2",
    registry=_registry,
)

# =============================================================================
# AI Service Histograms
# =============================================================================

# Buckets for AI request durations (typically longer than stage durations)
AI_REQUEST_DURATION_BUCKETS = (
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 60s
    120.0,  # 2min (for long LLM requests)
)

AI_REQUEST_DURATION = Histogram(
    "hsi_ai_request_duration_seconds",
    "Duration of AI service requests (RT-DETRv2 or Nemotron)",
    labelnames=["service"],
    buckets=AI_REQUEST_DURATION_BUCKETS,
    registry=_registry,
)

# =============================================================================
# Error Counters
# =============================================================================

PIPELINE_ERRORS_TOTAL = Counter(
    "hsi_pipeline_errors_total",
    "Total number of pipeline errors by type",
    labelnames=["error_type"],
    registry=_registry,
)

# =============================================================================
# Helper Functions
# =============================================================================


def set_queue_depth(queue_name: str, depth: int) -> None:
    """Set the current depth of a queue.

    Args:
        queue_name: Name of the queue ("detection" or "analysis")
        depth: Current number of items in the queue
    """
    if queue_name == "detection":
        DETECTION_QUEUE_DEPTH.set(depth)
    elif queue_name == "analysis":
        ANALYSIS_QUEUE_DEPTH.set(depth)
    else:
        logger.warning(f"Unknown queue name for metrics: {queue_name}")


def observe_stage_duration(stage: str, duration_seconds: float) -> None:
    """Record the duration of a pipeline stage.

    Args:
        stage: Name of the stage ("detect", "batch", "analyze")
        duration_seconds: Duration in seconds
    """
    STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)


def record_event_created() -> None:
    """Increment the events created counter."""
    EVENTS_CREATED_TOTAL.inc()


def record_detection_processed(count: int = 1) -> None:
    """Increment the detections processed counter.

    Args:
        count: Number of detections to add (default 1)
    """
    DETECTIONS_PROCESSED_TOTAL.inc(count)


def observe_ai_request_duration(service: str, duration_seconds: float) -> None:
    """Record the duration of an AI service request.

    Args:
        service: Name of the service ("rtdetr" or "nemotron")
        duration_seconds: Duration in seconds
    """
    AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds)


def record_pipeline_error(error_type: str) -> None:
    """Increment the pipeline errors counter.

    Args:
        error_type: Type of error (e.g., "connection_error", "timeout_error")
    """
    PIPELINE_ERRORS_TOTAL.labels(error_type=error_type).inc()


def get_metrics_response() -> bytes:
    """Generate the Prometheus metrics response.

    Returns:
        Bytes containing the metrics in Prometheus exposition format
    """
    return generate_latest(_registry)  # type: ignore[no-any-return]


# =============================================================================
# Pipeline Latency Tracker
# =============================================================================


class PipelineLatencyTracker:
    """Track and analyze latency for AI pipeline stages.

    This class provides in-memory circular buffer storage for pipeline
    latency measurements with statistical analysis capabilities.

    Pipeline stages tracked:
    - watch_to_detect: Time from file detection to RT-DETR processing
    - detect_to_batch: Time from detection to batch aggregation
    - batch_to_analyze: Time from batch to Nemotron analysis
    - total_pipeline: End-to-end latency

    Usage:
        tracker = PipelineLatencyTracker(max_samples=1000)
        tracker.record_stage_latency("watch_to_detect", 150.5)
        stats = tracker.get_stage_stats("watch_to_detect", window_minutes=5)
        summary = tracker.get_pipeline_summary()
    """

    # Valid pipeline stage names
    STAGES = ("watch_to_detect", "detect_to_batch", "batch_to_analyze", "total_pipeline")

    def __init__(self, max_samples: int = 1000) -> None:
        """Initialize the latency tracker.

        Args:
            max_samples: Maximum samples to keep per stage (circular buffer size)
        """
        import time
        from collections import deque
        from threading import Lock

        self._max_samples = max_samples
        self._lock = Lock()
        # Each stage has a deque of (timestamp, latency_ms) tuples
        self._samples: dict[str, deque[tuple[float, float]]] = {
            stage: deque(maxlen=max_samples) for stage in self.STAGES
        }
        self._time = time  # Store reference for testing

    def record_stage_latency(self, stage: str, latency_ms: float) -> None:
        """Record a latency sample for a pipeline stage.

        Args:
            stage: Pipeline stage name (one of STAGES)
            latency_ms: Latency in milliseconds

        Raises:
            ValueError: If stage name is invalid
        """
        if stage not in self.STAGES:
            logger.warning(f"Invalid pipeline stage for latency tracking: {stage}")
            return

        timestamp = self._time.time()
        with self._lock:
            self._samples[stage].append((timestamp, latency_ms))

    def get_stage_stats(
        self, stage: str, window_minutes: int = 60
    ) -> dict[str, float | int | None]:
        """Get latency statistics for a single stage.

        Args:
            stage: Pipeline stage name
            window_minutes: Only include samples from the last N minutes

        Returns:
            Dictionary with statistics:
            - avg_ms: Average latency
            - min_ms: Minimum latency
            - max_ms: Maximum latency
            - p50_ms: 50th percentile (median)
            - p95_ms: 95th percentile
            - p99_ms: 99th percentile
            - sample_count: Number of samples used
        """
        if stage not in self.STAGES:
            return {
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "sample_count": 0,
            }

        cutoff = self._time.time() - (window_minutes * 60)

        with self._lock:
            samples = [latency for ts, latency in self._samples[stage] if ts >= cutoff]

        if not samples:
            return {
                "avg_ms": None,
                "min_ms": None,
                "max_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "sample_count": 0,
            }

        sorted_samples = sorted(samples)
        count = len(sorted_samples)

        return {
            "avg_ms": sum(sorted_samples) / count,
            "min_ms": sorted_samples[0],
            "max_ms": sorted_samples[-1],
            "p50_ms": self._percentile(sorted_samples, 50),
            "p95_ms": self._percentile(sorted_samples, 95),
            "p99_ms": self._percentile(sorted_samples, 99),
            "sample_count": count,
        }

    def get_pipeline_summary(
        self, window_minutes: int = 60
    ) -> dict[str, dict[str, float | int | None]]:
        """Get latency statistics for all pipeline stages.

        Args:
            window_minutes: Only include samples from the last N minutes

        Returns:
            Dictionary mapping stage names to their statistics
        """
        return {stage: self.get_stage_stats(stage, window_minutes) for stage in self.STAGES}

    @staticmethod
    def _percentile(sorted_samples: list[float], percentile: float) -> float:
        """Calculate a percentile from a sorted list.

        Args:
            sorted_samples: Sorted list of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Value at the given percentile
        """
        if not sorted_samples:
            return 0.0
        index = int(len(sorted_samples) * percentile / 100)
        index = min(index, len(sorted_samples) - 1)
        return sorted_samples[index]


# Global singleton instance for application-wide latency tracking
_pipeline_latency_tracker: PipelineLatencyTracker | None = None


def get_pipeline_latency_tracker() -> PipelineLatencyTracker:
    """Get the global pipeline latency tracker instance.

    Returns:
        The singleton PipelineLatencyTracker instance
    """
    global _pipeline_latency_tracker  # noqa: PLW0603
    if _pipeline_latency_tracker is None:
        _pipeline_latency_tracker = PipelineLatencyTracker()
    return _pipeline_latency_tracker


def record_pipeline_stage_latency(stage: str, latency_ms: float) -> None:
    """Record a pipeline stage latency measurement.

    Convenience function that uses the global tracker instance.

    Args:
        stage: Pipeline stage name (watch_to_detect, detect_to_batch,
               batch_to_analyze, or total_pipeline)
        latency_ms: Latency in milliseconds
    """
    get_pipeline_latency_tracker().record_stage_latency(stage, latency_ms)
