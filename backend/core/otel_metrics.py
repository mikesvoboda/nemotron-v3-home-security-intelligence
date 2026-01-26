"""OpenTelemetry metrics for circuit breaker state tracking and AI model latency.

NEM-3799: This module provides OpenTelemetry metrics infrastructure for monitoring
circuit breaker state transitions, failures, and recovery patterns. These metrics
complement the existing Prometheus metrics with OpenTelemetry's semantic conventions.

NEM-3798: Added histogram metrics for AI model inference latency tracking:
- ai.detection.latency: RT-DETR object detection inference latency
- ai.nemotron.latency: Nemotron LLM inference latency
- ai.florence.latency: Florence vision-language model inference latency
- ai.pipeline.latency: Total pipeline processing latency
- ai.batch.processing_time: Batch aggregation and processing time

Circuit Breaker Metrics:
- circuit_breaker.state: Current circuit breaker state (0=closed, 1=open, 2=half_open)
- circuit_breaker.transitions: Counter of state transitions
- circuit_breaker.failures: Counter of failures recorded
- circuit_breaker.successes: Counter of successes recorded
- circuit_breaker.time_in_state: Time spent in current state (seconds)

Configuration is via environment variables:
- OTEL_METRICS_ENABLED: Enable/disable metrics (default: True when OTEL_ENABLED=True)
- OTEL_SERVICE_NAME: Service name in metrics (default: nemotron-backend)

Usage:
    from backend.core.otel_metrics import (
        get_circuit_breaker_metrics,
        record_circuit_breaker_state_change,
        record_circuit_breaker_failure,
        record_circuit_breaker_success,
        # AI model latency metrics (NEM-3798)
        record_detection_latency,
        record_nemotron_latency,
        record_florence_latency,
        record_pipeline_latency,
        record_batch_processing_time,
    )

    # Get metrics instance for a circuit breaker
    metrics = get_circuit_breaker_metrics()

    # Record a state change
    record_circuit_breaker_state_change(
        breaker_name="rtdetr",
        from_state="closed",
        to_state="open",
    )

    # Record a failure
    record_circuit_breaker_failure(breaker_name="rtdetr")

    # Record a success
    record_circuit_breaker_success(breaker_name="rtdetr")

    # Record AI model latencies (NEM-3798)
    record_detection_latency(
        latency_ms=45.2,
        model_version="rtdetr-l",
        batch_size=1,
        gpu_id="0",
    )

    record_nemotron_latency(
        latency_ms=1250.5,
        model_version="nemotron-mini-4b-instruct",
        batch_size=1,
        gpu_id="1",
    )
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitBreakerStateValue(IntEnum):
    """Numeric values for circuit breaker states in metrics.

    These values are used for gauge metrics to represent the current state.
    """

    CLOSED = 0
    OPEN = 1
    HALF_OPEN = 2


# Module-level state for metrics
_meter: Any = None
_is_initialized: bool = False

# Circuit breaker metrics instruments
_circuit_state_gauge: Any = None
_circuit_transitions_counter: Any = None
_circuit_failures_counter: Any = None
_circuit_successes_counter: Any = None
_circuit_rejected_counter: Any = None

# AI model latency histogram instruments (NEM-3798)
_detection_latency_histogram: Any = None
_nemotron_latency_histogram: Any = None
_florence_latency_histogram: Any = None
_pipeline_latency_histogram: Any = None
_batch_processing_histogram: Any = None

# State tracking for time-in-state calculations
_breaker_state_timestamps: dict[str, float] = {}
_breaker_current_states: dict[str, int] = {}


# =============================================================================
# AI Model Latency Bucket Definitions (NEM-3798)
# =============================================================================

# RT-DETR detection buckets (milliseconds): Fast inference model (~20-100ms typical)
# P50 ~30ms, P95 ~80ms, P99 ~150ms based on benchmarks
DETECTION_LATENCY_BUCKETS = (
    1.0,  # 1ms - minimum
    5.0,  # 5ms - very fast
    10.0,  # 10ms - fast path
    25.0,  # 25ms - quick inference
    50.0,  # 50ms - typical
    100.0,  # 100ms - normal range
    250.0,  # 250ms - slow
    500.0,  # 500ms - degraded
    1000.0,  # 1s - timeout threshold
)

# Nemotron LLM buckets (milliseconds): LLM inference (~500ms-5s typical)
# P50 ~1s, P95 ~3s, P99 ~5s based on benchmarks
NEMOTRON_LATENCY_BUCKETS = (
    100.0,  # 100ms - cached/minimal
    250.0,  # 250ms - short responses
    500.0,  # 500ms - fast completions
    1000.0,  # 1s - typical P50
    1500.0,  # 1.5s - normal
    2000.0,  # 2s - longer analysis
    2500.0,  # 2.5s - approaching P95
    5000.0,  # 5s - P99
    10000.0,  # 10s - extended analysis
)

# Florence vision-language buckets (milliseconds): ~100ms-2s typical
# P50 ~300ms, P95 ~1s, P99 ~2s based on benchmarks
FLORENCE_LATENCY_BUCKETS = (
    50.0,  # 50ms - cached
    100.0,  # 100ms - fast tasks
    200.0,  # 200ms - quick captions
    300.0,  # 300ms - typical P50
    500.0,  # 500ms - normal OCR
    750.0,  # 750ms - detailed captions
    1000.0,  # 1s - typical P95
    1500.0,  # 1.5s - complex tasks
    2000.0,  # 2s - P99
    3000.0,  # 3s - outliers
)

# Pipeline total latency buckets (milliseconds): End-to-end processing
# Includes detection + enrichment + analysis
PIPELINE_LATENCY_BUCKETS = (
    100.0,  # 100ms - minimal pipeline
    250.0,  # 250ms - fast path
    500.0,  # 500ms - quick processing
    1000.0,  # 1s - typical detection-only
    2000.0,  # 2s - with enrichment
    5000.0,  # 5s - full pipeline
    10000.0,  # 10s - complex analysis
    30000.0,  # 30s - extended processing
    60000.0,  # 60s - timeout threshold
)

# Batch processing time buckets (milliseconds): Aggregation and processing
BATCH_PROCESSING_BUCKETS = (
    10.0,  # 10ms - minimal batch
    50.0,  # 50ms - small batch
    100.0,  # 100ms - typical
    250.0,  # 250ms - medium batch
    500.0,  # 500ms - large batch
    1000.0,  # 1s - very large
    2500.0,  # 2.5s - extended
    5000.0,  # 5s - maximum
)


@dataclass(slots=True)
class CircuitBreakerOtelMetrics:
    """Container for circuit breaker OpenTelemetry metrics.

    Attributes:
        name: Circuit breaker name
        state: Current state value (0=closed, 1=open, 2=half_open)
        transitions_total: Total state transitions
        failures_total: Total failures recorded
        successes_total: Total successes recorded
        rejected_total: Total calls rejected
        time_in_current_state_seconds: Time spent in current state
    """

    name: str
    state: int = 0
    transitions_total: int = 0
    failures_total: int = 0
    successes_total: int = 0
    rejected_total: int = 0
    time_in_current_state_seconds: float = 0.0
    last_state_change_timestamp: float = field(default_factory=time.monotonic)


def setup_otel_metrics() -> bool:
    """Initialize OpenTelemetry metrics infrastructure.

    This function sets up the MeterProvider and creates metric instruments
    for circuit breaker monitoring and AI model latency tracking. It should
    be called during application startup, after setup_telemetry() if tracing
    is also enabled.

    NEM-3798: Added AI model latency histogram instruments with explicit
    bucket boundaries optimized for ML workloads.

    Returns:
        True if metrics were initialized, False if disabled or already initialized
    """
    global _meter, _is_initialized  # noqa: PLW0603
    global _circuit_state_gauge, _circuit_transitions_counter  # noqa: PLW0603
    global _circuit_failures_counter, _circuit_successes_counter  # noqa: PLW0603
    global _circuit_rejected_counter  # noqa: PLW0603
    global _detection_latency_histogram, _nemotron_latency_histogram  # noqa: PLW0603
    global _florence_latency_histogram, _pipeline_latency_histogram  # noqa: PLW0603
    global _batch_processing_histogram  # noqa: PLW0603

    if _is_initialized:
        logger.debug("OpenTelemetry metrics already initialized, skipping")
        return False

    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            View,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource

        # Create resource with service name
        # Use environment variable or default
        service_name = os.getenv("OTEL_SERVICE_NAME", "nemotron-backend")
        resource = Resource.create({SERVICE_NAME: service_name})

        # Create views with explicit bucket boundaries for each histogram (NEM-3798)
        views = [
            View(
                instrument_name="ai.detection.latency",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=list(DETECTION_LATENCY_BUCKETS)
                ),
            ),
            View(
                instrument_name="ai.nemotron.latency",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=list(NEMOTRON_LATENCY_BUCKETS)
                ),
            ),
            View(
                instrument_name="ai.florence.latency",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=list(FLORENCE_LATENCY_BUCKETS)
                ),
            ),
            View(
                instrument_name="ai.pipeline.latency",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=list(PIPELINE_LATENCY_BUCKETS)
                ),
            ),
            View(
                instrument_name="ai.batch.processing_time",
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=list(BATCH_PROCESSING_BUCKETS)
                ),
            ),
        ]

        # Try to setup OTLP exporter if endpoint is configured
        metric_readers = []
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                    OTLPMetricExporter,
                )

                otlp_insecure = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
                exporter = OTLPMetricExporter(
                    endpoint=otlp_endpoint,
                    insecure=otlp_insecure,
                )
                reader = PeriodicExportingMetricReader(
                    exporter,
                    export_interval_millis=60000,  # 60 seconds
                )
                metric_readers.append(reader)
                logger.debug(f"OTLP metric exporter configured: endpoint={otlp_endpoint}")
            except ImportError:
                logger.debug("OTLP metric exporter not available")

        # Create and set meter provider
        provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers if metric_readers else [],
            views=views,
        )
        metrics.set_meter_provider(provider)

        # Get a meter for all metrics
        _meter = metrics.get_meter(
            name="nemotron_backend",
            version="1.0.0",
            schema_url="https://opentelemetry.io/schemas/1.23.0",
        )

        # Create circuit breaker metric instruments
        _circuit_state_gauge = _meter.create_gauge(
            name="circuit_breaker.state",
            description="Current circuit breaker state (0=closed, 1=open, 2=half_open)",
            unit="1",
        )

        _circuit_transitions_counter = _meter.create_counter(
            name="circuit_breaker.transitions",
            description="Total number of circuit breaker state transitions",
            unit="1",
        )

        _circuit_failures_counter = _meter.create_counter(
            name="circuit_breaker.failures",
            description="Total number of failures recorded by circuit breakers",
            unit="1",
        )

        _circuit_successes_counter = _meter.create_counter(
            name="circuit_breaker.successes",
            description="Total number of successes recorded by circuit breakers",
            unit="1",
        )

        _circuit_rejected_counter = _meter.create_counter(
            name="circuit_breaker.rejected",
            description="Total number of calls rejected by circuit breakers",
            unit="1",
        )

        # Create AI model latency histogram instruments (NEM-3798)
        _detection_latency_histogram = _meter.create_histogram(
            name="ai.detection.latency",
            description="RT-DETR object detection inference latency",
            unit="ms",
        )

        _nemotron_latency_histogram = _meter.create_histogram(
            name="ai.nemotron.latency",
            description="Nemotron LLM inference latency",
            unit="ms",
        )

        _florence_latency_histogram = _meter.create_histogram(
            name="ai.florence.latency",
            description="Florence vision-language model inference latency",
            unit="ms",
        )

        _pipeline_latency_histogram = _meter.create_histogram(
            name="ai.pipeline.latency",
            description="Total pipeline processing latency (detection + analysis)",
            unit="ms",
        )

        _batch_processing_histogram = _meter.create_histogram(
            name="ai.batch.processing_time",
            description="Batch aggregation and processing time",
            unit="ms",
        )

        _is_initialized = True
        logger.info("OpenTelemetry metrics initialized for circuit breaker and AI model latency")
        return True

    except ImportError as e:
        logger.debug(f"OpenTelemetry metrics dependencies not installed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to initialize OpenTelemetry metrics: {e}")
        return False


def shutdown_otel_metrics() -> None:
    """Shutdown OpenTelemetry metrics and flush any pending data.

    This should be called during application shutdown to ensure all
    pending metrics are exported before the process exits.
    """
    global _meter, _is_initialized  # noqa: PLW0603
    global _circuit_state_gauge, _circuit_transitions_counter  # noqa: PLW0603
    global _circuit_failures_counter, _circuit_successes_counter  # noqa: PLW0603
    global _circuit_rejected_counter  # noqa: PLW0603
    global _detection_latency_histogram, _nemotron_latency_histogram  # noqa: PLW0603
    global _florence_latency_histogram, _pipeline_latency_histogram  # noqa: PLW0603
    global _batch_processing_histogram  # noqa: PLW0603

    if not _is_initialized:
        return

    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider

        provider = metrics.get_meter_provider()
        if isinstance(provider, MeterProvider):
            provider.shutdown()

        _meter = None
        # Circuit breaker instruments
        _circuit_state_gauge = None
        _circuit_transitions_counter = None
        _circuit_failures_counter = None
        _circuit_successes_counter = None
        _circuit_rejected_counter = None
        # AI model latency instruments (NEM-3798)
        _detection_latency_histogram = None
        _nemotron_latency_histogram = None
        _florence_latency_histogram = None
        _pipeline_latency_histogram = None
        _batch_processing_histogram = None
        _is_initialized = False

        logger.info("OpenTelemetry metrics shut down")

    except Exception as e:
        logger.warning(f"Error shutting down OpenTelemetry metrics: {e}")


def is_otel_metrics_enabled() -> bool:
    """Check if OpenTelemetry metrics have been initialized.

    Returns:
        True if OpenTelemetry metrics are active
    """
    return _is_initialized


def _ensure_initialized() -> bool:
    """Ensure metrics are initialized, attempting lazy initialization if needed.

    Returns:
        True if metrics are available, False otherwise
    """
    if _is_initialized:
        return True

    # Try lazy initialization
    return setup_otel_metrics()


def record_circuit_breaker_state(
    breaker_name: str,
    state: int | CircuitBreakerStateValue,
) -> None:
    """Record the current state of a circuit breaker.

    Args:
        breaker_name: Name of the circuit breaker (e.g., "rtdetr", "nemotron")
        state: Current state value (0=closed, 1=open, 2=half_open)
    """
    if not _ensure_initialized():
        return

    try:
        state_value = int(state)
        attributes = {"breaker": breaker_name}

        if _circuit_state_gauge is not None:
            # For Gauge, we need to call it with the value
            # OpenTelemetry Python SDK uses set() for sync gauges
            _circuit_state_gauge.set(state_value, attributes)

        # Track state for time-in-state calculations
        current_time = time.monotonic()
        if breaker_name not in _breaker_current_states:
            _breaker_state_timestamps[breaker_name] = current_time

        _breaker_current_states[breaker_name] = state_value

    except Exception as e:
        logger.debug(f"Failed to record circuit breaker state: {e}")


def record_circuit_breaker_state_change(
    breaker_name: str,
    from_state: str,
    to_state: str,
) -> None:
    """Record a circuit breaker state transition.

    Args:
        breaker_name: Name of the circuit breaker
        from_state: Previous state name (e.g., "closed", "open", "half_open")
        to_state: New state name
    """
    if not _ensure_initialized():
        return

    try:
        attributes = {
            "breaker": breaker_name,
            "from_state": from_state,
            "to_state": to_state,
        }

        if _circuit_transitions_counter is not None:
            _circuit_transitions_counter.add(1, attributes)

        # Update state tracking
        current_time = time.monotonic()
        _breaker_state_timestamps[breaker_name] = current_time

        # Map state name to value
        state_map = {
            "closed": CircuitBreakerStateValue.CLOSED,
            "open": CircuitBreakerStateValue.OPEN,
            "half_open": CircuitBreakerStateValue.HALF_OPEN,
        }
        if to_state in state_map:
            _breaker_current_states[breaker_name] = state_map[to_state]

        # Also update the state gauge
        if to_state in state_map and _circuit_state_gauge is not None:
            _circuit_state_gauge.set(state_map[to_state], {"breaker": breaker_name})

        logger.debug(
            f"Circuit breaker '{breaker_name}' state transition: {from_state} -> {to_state}"
        )

    except Exception as e:
        logger.debug(f"Failed to record circuit breaker state change: {e}")


def record_circuit_breaker_failure(breaker_name: str) -> None:
    """Record a failure for a circuit breaker.

    Args:
        breaker_name: Name of the circuit breaker
    """
    if not _ensure_initialized():
        return

    try:
        attributes = {"breaker": breaker_name}

        if _circuit_failures_counter is not None:
            _circuit_failures_counter.add(1, attributes)

    except Exception as e:
        logger.debug(f"Failed to record circuit breaker failure: {e}")


def record_circuit_breaker_success(breaker_name: str) -> None:
    """Record a success for a circuit breaker.

    Args:
        breaker_name: Name of the circuit breaker
    """
    if not _ensure_initialized():
        return

    try:
        attributes = {"breaker": breaker_name}

        if _circuit_successes_counter is not None:
            _circuit_successes_counter.add(1, attributes)

    except Exception as e:
        logger.debug(f"Failed to record circuit breaker success: {e}")


def record_circuit_breaker_rejected(breaker_name: str) -> None:
    """Record a rejected call for a circuit breaker.

    Args:
        breaker_name: Name of the circuit breaker
    """
    if not _ensure_initialized():
        return

    try:
        attributes = {"breaker": breaker_name}

        if _circuit_rejected_counter is not None:
            _circuit_rejected_counter.add(1, attributes)

    except Exception as e:
        logger.debug(f"Failed to record circuit breaker rejection: {e}")


def get_time_in_current_state(breaker_name: str) -> float:
    """Get the time a circuit breaker has spent in its current state.

    Args:
        breaker_name: Name of the circuit breaker

    Returns:
        Time in seconds since the last state change, or 0.0 if not tracked
    """
    if breaker_name not in _breaker_state_timestamps:
        return 0.0

    return time.monotonic() - _breaker_state_timestamps[breaker_name]


def get_circuit_breaker_otel_metrics(breaker_name: str) -> CircuitBreakerOtelMetrics:
    """Get current OpenTelemetry metrics for a circuit breaker.

    Args:
        breaker_name: Name of the circuit breaker

    Returns:
        CircuitBreakerOtelMetrics with current state and counters

    Note:
        Counter values are not retrievable from OpenTelemetry instruments,
        so this returns tracked state information rather than actual metric values.
    """
    state = _breaker_current_states.get(breaker_name, 0)
    timestamp = _breaker_state_timestamps.get(breaker_name, time.monotonic())
    time_in_state = time.monotonic() - timestamp

    return CircuitBreakerOtelMetrics(
        name=breaker_name,
        state=state,
        time_in_current_state_seconds=time_in_state,
        last_state_change_timestamp=timestamp,
    )


def reset_otel_metrics_state() -> None:
    """Reset the module-level metrics state (for testing).

    This clears all tracked state and timestamps. It does not shutdown
    the MeterProvider or clear the metric instruments.
    """
    _breaker_state_timestamps.clear()
    _breaker_current_states.clear()


def reset_otel_metrics_for_testing() -> None:
    """Completely reset OpenTelemetry metrics state for testing.

    This resets all module-level state including the initialized flag,
    allowing setup_otel_metrics() to be called again in tests.
    """
    global _meter, _is_initialized  # noqa: PLW0603
    global _circuit_state_gauge, _circuit_transitions_counter  # noqa: PLW0603
    global _circuit_failures_counter, _circuit_successes_counter  # noqa: PLW0603
    global _circuit_rejected_counter  # noqa: PLW0603
    global _detection_latency_histogram, _nemotron_latency_histogram  # noqa: PLW0603
    global _florence_latency_histogram, _pipeline_latency_histogram  # noqa: PLW0603
    global _batch_processing_histogram  # noqa: PLW0603
    global _breaker_state_timestamps, _breaker_current_states  # noqa: PLW0603

    _meter = None
    _is_initialized = False
    # Circuit breaker instruments
    _circuit_state_gauge = None
    _circuit_transitions_counter = None
    _circuit_failures_counter = None
    _circuit_successes_counter = None
    _circuit_rejected_counter = None
    # AI model latency instruments (NEM-3798)
    _detection_latency_histogram = None
    _nemotron_latency_histogram = None
    _florence_latency_histogram = None
    _pipeline_latency_histogram = None
    _batch_processing_histogram = None
    # State tracking
    _breaker_state_timestamps = {}
    _breaker_current_states = {}


# =============================================================================
# AI Model Latency Recording Functions (NEM-3798)
# =============================================================================


def record_detection_latency(
    latency_ms: float,
    *,
    model_version: str = "rtdetr-l",
    batch_size: int = 1,
    gpu_id: str = "0",
) -> None:
    """Record RT-DETR object detection inference latency.

    Args:
        latency_ms: Inference latency in milliseconds
        model_version: Model version string (e.g., "rtdetr-l", "rtdetr-x", "yolo26")
        batch_size: Number of images in the batch
        gpu_id: GPU identifier (e.g., "0", "1", "cuda:0")

    Example:
        >>> from backend.core.otel_metrics import record_detection_latency
        >>> record_detection_latency(
        ...     latency_ms=45.2,
        ...     model_version="rtdetr-l",
        ...     batch_size=1,
        ...     gpu_id="0",
        ... )
    """
    if not _is_initialized or _detection_latency_histogram is None:
        return

    try:
        _detection_latency_histogram.record(
            latency_ms,
            attributes={
                "model.version": model_version,
                "batch.size": batch_size,
                "gpu.id": gpu_id,
            },
        )
    except Exception as e:
        logger.debug(f"Failed to record detection latency: {e}")


def record_nemotron_latency(
    latency_ms: float,
    *,
    model_version: str = "nemotron-mini-4b-instruct",
    batch_size: int = 1,
    gpu_id: str = "0",
    tokens_generated: int | None = None,
) -> None:
    """Record Nemotron LLM inference latency.

    Args:
        latency_ms: Inference latency in milliseconds
        model_version: Model version string (e.g., "nemotron-mini-4b-instruct")
        batch_size: Number of prompts in the batch
        gpu_id: GPU identifier (e.g., "0", "1", "cuda:0")
        tokens_generated: Optional number of tokens generated

    Example:
        >>> from backend.core.otel_metrics import record_nemotron_latency
        >>> record_nemotron_latency(
        ...     latency_ms=1250.5,
        ...     model_version="nemotron-mini-4b-instruct",
        ...     batch_size=1,
        ...     gpu_id="1",
        ...     tokens_generated=150,
        ... )
    """
    if not _is_initialized or _nemotron_latency_histogram is None:
        return

    try:
        attributes: dict[str, str | int] = {
            "model.version": model_version,
            "batch.size": batch_size,
            "gpu.id": gpu_id,
        }
        if tokens_generated is not None:
            attributes["tokens.generated"] = tokens_generated

        _nemotron_latency_histogram.record(latency_ms, attributes=attributes)
    except Exception as e:
        logger.debug(f"Failed to record nemotron latency: {e}")


def record_florence_latency(
    latency_ms: float,
    *,
    model_version: str = "florence-2-large",
    batch_size: int = 1,
    gpu_id: str = "0",
    task_type: str = "caption",
) -> None:
    """Record Florence vision-language model inference latency.

    Args:
        latency_ms: Inference latency in milliseconds
        model_version: Model version string (e.g., "florence-2-large")
        batch_size: Number of images in the batch
        gpu_id: GPU identifier (e.g., "0", "1", "cuda:0")
        task_type: Vision task type (e.g., "caption", "ocr", "detect", "dense_caption")

    Example:
        >>> from backend.core.otel_metrics import record_florence_latency
        >>> record_florence_latency(
        ...     latency_ms=320.5,
        ...     model_version="florence-2-large",
        ...     batch_size=1,
        ...     gpu_id="0",
        ...     task_type="caption",
        ... )
    """
    if not _is_initialized or _florence_latency_histogram is None:
        return

    try:
        _florence_latency_histogram.record(
            latency_ms,
            attributes={
                "model.version": model_version,
                "batch.size": batch_size,
                "gpu.id": gpu_id,
                "task.type": task_type,
            },
        )
    except Exception as e:
        logger.debug(f"Failed to record florence latency: {e}")


def record_pipeline_latency(
    latency_ms: float,
    *,
    camera_id: str = "unknown",
    pipeline_stage: str = "full",
    detection_count: int = 0,
) -> None:
    """Record total pipeline processing latency.

    Args:
        latency_ms: Total pipeline latency in milliseconds
        camera_id: Camera identifier
        pipeline_stage: Pipeline stage (e.g., "detection", "enrichment", "analysis", "full")
        detection_count: Number of detections processed

    Example:
        >>> from backend.core.otel_metrics import record_pipeline_latency
        >>> record_pipeline_latency(
        ...     latency_ms=3500.0,
        ...     camera_id="front_door",
        ...     pipeline_stage="full",
        ...     detection_count=5,
        ... )
    """
    if not _is_initialized or _pipeline_latency_histogram is None:
        return

    try:
        _pipeline_latency_histogram.record(
            latency_ms,
            attributes={
                "camera.id": camera_id,
                "pipeline.stage": pipeline_stage,
                "detection.count": detection_count,
            },
        )
    except Exception as e:
        logger.debug(f"Failed to record pipeline latency: {e}")


def record_batch_processing_time(
    processing_time_ms: float,
    *,
    batch_size: int = 1,
    camera_count: int = 1,
    batch_id: str = "unknown",
) -> None:
    """Record batch aggregation and processing time.

    Args:
        processing_time_ms: Batch processing time in milliseconds
        batch_size: Number of detections in the batch
        camera_count: Number of cameras contributing to the batch
        batch_id: Unique batch identifier

    Example:
        >>> from backend.core.otel_metrics import record_batch_processing_time
        >>> record_batch_processing_time(
        ...     processing_time_ms=150.0,
        ...     batch_size=12,
        ...     camera_count=3,
        ...     batch_id="batch-abc123",
        ... )
    """
    if not _is_initialized or _batch_processing_histogram is None:
        return

    try:
        _batch_processing_histogram.record(
            processing_time_ms,
            attributes={
                "batch.size": batch_size,
                "camera.count": camera_count,
                "batch.id": batch_id,
            },
        )
    except Exception as e:
        logger.debug(f"Failed to record batch processing time: {e}")
