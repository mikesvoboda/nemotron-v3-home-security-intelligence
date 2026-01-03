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
# Queue Overflow Metrics
# =============================================================================

QUEUE_OVERFLOW_TOTAL = Counter(
    "hsi_queue_overflow_total",
    "Total number of queue overflow events by queue and policy",
    labelnames=["queue_name", "policy"],
    registry=_registry,
)

QUEUE_ITEMS_MOVED_TO_DLQ_TOTAL = Counter(
    "hsi_queue_items_moved_to_dlq_total",
    "Total number of items moved to dead-letter queue due to overflow",
    labelnames=["queue_name"],
    registry=_registry,
)

QUEUE_ITEMS_DROPPED_TOTAL = Counter(
    "hsi_queue_items_dropped_total",
    "Total number of items dropped due to queue overflow (drop_oldest policy)",
    labelnames=["queue_name"],
    registry=_registry,
)

QUEUE_ITEMS_REJECTED_TOTAL = Counter(
    "hsi_queue_items_rejected_total",
    "Total number of items rejected due to full queue (reject policy)",
    labelnames=["queue_name"],
    registry=_registry,
)

# =============================================================================
# Semantic AI Metrics - Group 1: Detection Metrics (NEM-307)
# =============================================================================

DETECTIONS_BY_CLASS_TOTAL = Counter(
    "hsi_detections_by_class_total",
    "Total number of detections by object class (person, car, etc.)",
    labelnames=["class_name"],
    registry=_registry,
)

# Buckets for confidence scores (0-1 range, finer granularity at higher values)
DETECTION_CONFIDENCE_BUCKETS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0)

DETECTION_CONFIDENCE = Histogram(
    "hsi_detection_confidence",
    "Distribution of detection confidence scores from RT-DETRv2",
    buckets=DETECTION_CONFIDENCE_BUCKETS,
    registry=_registry,
)

DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL = Counter(
    "hsi_detections_filtered_low_confidence_total",
    "Total number of detections filtered out due to low confidence",
    registry=_registry,
)

# =============================================================================
# Semantic AI Metrics - Group 2: Risk Analysis Metrics (NEM-307)
# =============================================================================

# Risk score buckets (0-100 scale, 10-point intervals)
RISK_SCORE_BUCKETS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

RISK_SCORE = Histogram(
    "hsi_risk_score",
    "Distribution of risk scores assigned by Nemotron LLM",
    buckets=RISK_SCORE_BUCKETS,
    registry=_registry,
)

EVENTS_BY_RISK_LEVEL_TOTAL = Counter(
    "hsi_events_by_risk_level_total",
    "Total number of events by risk level (low, medium, high, critical)",
    labelnames=["level"],
    registry=_registry,
)

PROMPT_TEMPLATE_USED_TOTAL = Counter(
    "hsi_prompt_template_used_total",
    "Total number of times each prompt template was used for Nemotron",
    labelnames=["template"],
    registry=_registry,
)

# =============================================================================
# Semantic AI Metrics - Group 3: Model Usage Metrics (NEM-307)
# =============================================================================

FLORENCE_TASK_TOTAL = Counter(
    "hsi_florence_task_total",
    "Total number of Florence-2 tasks executed by task type",
    labelnames=["task"],
    registry=_registry,
)

ENRICHMENT_MODEL_CALLS_TOTAL = Counter(
    "hsi_enrichment_model_calls_total",
    "Total number of calls to enrichment models (model zoo)",
    labelnames=["model"],
    registry=_registry,
)

# =============================================================================
# Semantic AI Metrics - Group 4: Business Metrics (NEM-307)
# =============================================================================

EVENTS_BY_CAMERA_TOTAL = Counter(
    "hsi_events_by_camera_total",
    "Total number of events by camera",
    labelnames=["camera_id", "camera_name"],
    registry=_registry,
)

EVENTS_REVIEWED_TOTAL = Counter(
    "hsi_events_reviewed_total",
    "Total number of events that have been reviewed by users",
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


def record_queue_overflow(queue_name: str, policy: str) -> None:
    """Record a queue overflow event.

    Args:
        queue_name: Name of the queue that overflowed
        policy: Overflow policy that was triggered (dlq, drop_oldest, reject)
    """
    QUEUE_OVERFLOW_TOTAL.labels(queue_name=queue_name, policy=policy).inc()


def record_queue_items_moved_to_dlq(queue_name: str, count: int = 1) -> None:
    """Record items moved to dead-letter queue due to overflow.

    Args:
        queue_name: Name of the source queue
        count: Number of items moved (default 1)
    """
    QUEUE_ITEMS_MOVED_TO_DLQ_TOTAL.labels(queue_name=queue_name).inc(count)


def record_queue_items_dropped(queue_name: str, count: int = 1) -> None:
    """Record items dropped due to queue overflow (drop_oldest policy).

    Args:
        queue_name: Name of the queue
        count: Number of items dropped (default 1)
    """
    QUEUE_ITEMS_DROPPED_TOTAL.labels(queue_name=queue_name).inc(count)


def record_queue_items_rejected(queue_name: str, count: int = 1) -> None:
    """Record items rejected due to full queue (reject policy).

    Args:
        queue_name: Name of the queue
        count: Number of items rejected (default 1)
    """
    QUEUE_ITEMS_REJECTED_TOTAL.labels(queue_name=queue_name).inc(count)


def get_metrics_response() -> bytes:
    """Generate the Prometheus metrics response.

    Returns:
        Bytes containing the metrics in Prometheus exposition format
    """
    return generate_latest(_registry)  # type: ignore[no-any-return]


# =============================================================================
# Semantic AI Metrics Helper Functions (NEM-307)
# =============================================================================


def record_detection_by_class(class_name: str, count: int = 1) -> None:
    """Record a detection by object class.

    Args:
        class_name: Name of the detected object class (e.g., "person", "car")
        count: Number of detections to add (default 1)
    """
    DETECTIONS_BY_CLASS_TOTAL.labels(class_name=class_name).inc(count)


def observe_detection_confidence(confidence: float) -> None:
    """Record a detection confidence score in the histogram.

    Args:
        confidence: Confidence score (0-1 range)
    """
    DETECTION_CONFIDENCE.observe(confidence)


def record_detection_filtered_low_confidence(count: int = 1) -> None:
    """Record detections filtered out due to low confidence.

    Args:
        count: Number of filtered detections (default 1)
    """
    DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL.inc(count)


def observe_risk_score(score: float) -> None:
    """Record a risk score in the histogram.

    Args:
        score: Risk score (0-100 range)
    """
    RISK_SCORE.observe(score)


def record_event_by_risk_level(level: str, count: int = 1) -> None:
    """Record an event by risk level.

    Args:
        level: Risk level (e.g., "low", "medium", "high", "critical")
        count: Number of events to add (default 1)
    """
    EVENTS_BY_RISK_LEVEL_TOTAL.labels(level=level).inc(count)


def record_prompt_template_used(template: str, count: int = 1) -> None:
    """Record usage of a prompt template for Nemotron.

    Args:
        template: Name of the prompt template (e.g., "basic", "enriched")
        count: Number of uses to add (default 1)
    """
    PROMPT_TEMPLATE_USED_TOTAL.labels(template=template).inc(count)


def record_florence_task(task: str, count: int = 1) -> None:
    """Record a Florence-2 task execution.

    Args:
        task: Task type (e.g., "caption", "ocr", "detect")
        count: Number of executions to add (default 1)
    """
    FLORENCE_TASK_TOTAL.labels(task=task).inc(count)


def record_enrichment_model_call(model: str, count: int = 1) -> None:
    """Record a call to an enrichment model.

    Args:
        model: Model name (e.g., "violence-detection", "fashion-clip")
        count: Number of calls to add (default 1)
    """
    ENRICHMENT_MODEL_CALLS_TOTAL.labels(model=model).inc(count)


def record_event_by_camera(camera_id: str, camera_name: str, count: int = 1) -> None:
    """Record an event for a specific camera.

    Args:
        camera_id: Unique identifier of the camera
        camera_name: Human-readable name of the camera
        count: Number of events to add (default 1)
    """
    EVENTS_BY_CAMERA_TOTAL.labels(camera_id=camera_id, camera_name=camera_name).inc(count)


def record_event_reviewed(count: int = 1) -> None:
    """Record an event that has been reviewed by a user.

    Args:
        count: Number of reviewed events to add (default 1)
    """
    EVENTS_REVIEWED_TOTAL.inc(count)


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

    def get_samples_history(
        self, window_minutes: int = 60, limit: int | None = None
    ) -> list[dict[str, str | float]]:
        """Get raw latency samples for time-series visualization.

        Args:
            window_minutes: Only include samples from the last N minutes
            limit: Maximum number of samples to return (None for all)

        Returns:
            List of samples with timestamp, stage, and latency_ms
        """
        cutoff = self._time.time() - (window_minutes * 60)
        all_samples: list[dict[str, str | float]] = []

        with self._lock:
            for stage in self.STAGES:
                for ts, latency in self._samples[stage]:
                    if ts >= cutoff:
                        all_samples.append({"timestamp": ts, "stage": stage, "latency_ms": latency})

        # Sort by timestamp (most recent first)
        all_samples.sort(key=lambda x: x["timestamp"], reverse=True)

        # Apply limit if specified
        if limit is not None and len(all_samples) > limit:
            all_samples = all_samples[:limit]

        return all_samples

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


# =============================================================================
# Throughput Tracker
# =============================================================================


class ThroughputTracker:
    """Track throughput metrics for images processed and events created.

    This class provides in-memory circular buffer storage for throughput
    measurements with rate calculation capabilities.

    Metrics tracked:
    - images: Images processed through the detection pipeline
    - events: Security events created

    It also tracks detection latency to compute inference FPS.

    Usage:
        tracker = ThroughputTracker(max_samples=1000)
        tracker.record_metric("images", 5)
        tracker.record_detection_latency(100.0)
        stats = tracker.get_throughput(window_minutes=5)
        fps = tracker.get_inference_fps()
    """

    # Valid metric types
    METRIC_TYPES = ("images", "events")

    def __init__(self, max_samples: int = 1000) -> None:
        """Initialize the throughput tracker.

        Args:
            max_samples: Maximum samples to keep per metric (circular buffer size)
        """
        import time
        from collections import deque
        from threading import Lock

        self._max_samples = max_samples
        self._lock = Lock()
        # Each metric has a deque of (timestamp, count) tuples
        self._samples: dict[str, deque[tuple[float, int]]] = {
            metric: deque(maxlen=max_samples) for metric in self.METRIC_TYPES
        }
        # Detection latency samples for FPS calculation: (timestamp, latency_ms)
        self._latency_samples: deque[tuple[float, float]] = deque(maxlen=max_samples)
        self._time = time  # Store reference for testing

    def record_metric(self, metric_type: str, count: int = 1) -> None:
        """Record a throughput metric sample.

        Args:
            metric_type: Metric type name (one of METRIC_TYPES)
            count: Number of items to record (default 1)
        """
        if metric_type not in self.METRIC_TYPES:
            logger.warning(f"Invalid metric type for throughput tracking: {metric_type}")
            return

        timestamp = self._time.time()
        with self._lock:
            self._samples[metric_type].append((timestamp, count))

    def record_detection_latency(self, latency_ms: float) -> None:
        """Record a detection latency sample for FPS calculation.

        Args:
            latency_ms: Detection latency in milliseconds
        """
        timestamp = self._time.time()
        with self._lock:
            self._latency_samples.append((timestamp, latency_ms))

    def get_throughput(self, window_minutes: int = 60) -> dict[str, float]:
        """Get throughput rates for all metric types.

        Args:
            window_minutes: Only include samples from the last N minutes

        Returns:
            Dictionary with throughput rates:
            - images_per_min: Images processed per minute
            - events_per_min: Events created per minute
        """
        cutoff = self._time.time() - (window_minutes * 60)

        result: dict[str, float] = {}
        with self._lock:
            for metric_type in self.METRIC_TYPES:
                samples = [(ts, count) for ts, count in self._samples[metric_type] if ts >= cutoff]

                if not samples:
                    result[f"{metric_type}_per_min"] = 0.0
                    continue

                # Sum all counts in the window
                total_count = sum(count for _, count in samples)

                # Calculate time span
                oldest_ts = min(ts for ts, _ in samples)
                newest_ts = max(ts for ts, _ in samples)

                # If all samples are at the same timestamp, use window_minutes as span
                time_span_minutes = (newest_ts - oldest_ts) / 60.0
                if time_span_minutes < 0.01:  # Less than 0.6 seconds
                    # Use time since oldest sample to now
                    time_span_minutes = (self._time.time() - oldest_ts) / 60.0
                    if time_span_minutes < 0.01:
                        time_span_minutes = window_minutes

                result[f"{metric_type}_per_min"] = total_count / time_span_minutes

        return result

    def get_inference_fps(self, window_minutes: int = 5) -> float | None:
        """Calculate inference FPS from average detection latency.

        FPS is calculated as 1000 / avg_latency_ms.

        Args:
            window_minutes: Only include samples from the last N minutes

        Returns:
            Inference FPS, or None if no samples available
        """
        cutoff = self._time.time() - (window_minutes * 60)

        with self._lock:
            samples = [latency for ts, latency in self._latency_samples if ts >= cutoff]

        if not samples:
            return None

        avg_latency_ms = sum(samples) / len(samples)
        if avg_latency_ms <= 0:
            return None

        # FPS = 1000 / latency_ms (convert ms to seconds: 1000ms = 1s)
        return 1000.0 / avg_latency_ms


# Global singleton instance for application-wide throughput tracking
_throughput_tracker: ThroughputTracker | None = None


def get_throughput_tracker() -> ThroughputTracker:
    """Get the global throughput tracker instance.

    Returns:
        The singleton ThroughputTracker instance
    """
    global _throughput_tracker  # noqa: PLW0603
    if _throughput_tracker is None:
        _throughput_tracker = ThroughputTracker()
    return _throughput_tracker


def record_throughput_metric(metric_type: str, count: int = 1) -> None:
    """Record a throughput metric.

    Convenience function that uses the global tracker instance.

    Args:
        metric_type: Metric type name ("images" or "events")
        count: Number of items to record (default 1)
    """
    get_throughput_tracker().record_metric(metric_type, count)


def record_detection_latency(latency_ms: float) -> None:
    """Record a detection latency sample for FPS calculation.

    Convenience function that uses the global tracker instance.

    Args:
        latency_ms: Detection latency in milliseconds
    """
    get_throughput_tracker().record_detection_latency(latency_ms)
