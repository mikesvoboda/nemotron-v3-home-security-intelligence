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

from collections import deque
from datetime import UTC
from typing import TypedDict

import numpy as np
from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from backend.core.logging import get_logger
from backend.core.sanitization import (
    sanitize_camera_id,
    sanitize_error_type,
    sanitize_metric_label,
    sanitize_object_class,
    sanitize_risk_level,
)


class StageStatsDict(TypedDict):
    """Type for pipeline stage latency statistics."""

    avg_ms: float | None
    min_ms: float | None
    max_ms: float | None
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    sample_count: int


class BucketStatsDict(TypedDict):
    """Type for latency bucket statistics (used in history snapshots)."""

    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    sample_count: int


class LatencyHistoryEntry(TypedDict):
    """Type for latency history entry."""

    timestamp: str
    stages: dict[str, BucketStatsDict | None]


class ModelStatsDict(TypedDict):
    """Type for model latency statistics."""

    avg_ms: float | None
    p50_ms: float | None
    p95_ms: float | None
    sample_count: int


class ModelLatencyHistoryEntry(TypedDict):
    """Type for model latency history entry."""

    timestamp: str
    stats: BucketStatsDict | None


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
# Worker Supervisor Metrics (NEM-2457, NEM-2459)
# =============================================================================

WORKER_RESTARTS_TOTAL = Counter(
    "hsi_worker_restarts_total",
    "Total number of worker restarts by worker name",
    labelnames=["worker_name"],
    registry=_registry,
)

WORKER_CRASHES_TOTAL = Counter(
    "hsi_worker_crashes_total",
    "Total number of worker crashes by worker name",
    labelnames=["worker_name"],
    registry=_registry,
)

WORKER_MAX_RESTARTS_EXCEEDED_TOTAL = Counter(
    "hsi_worker_max_restarts_exceeded_total",
    "Total number of times a worker exceeded max restart limit",
    labelnames=["worker_name"],
    registry=_registry,
)

WORKER_STATUS = Gauge(
    "hsi_worker_status",
    "Current worker status (0=stopped, 1=running, 2=crashed, 3=restarting, 4=failed)",
    labelnames=["worker_name"],
    registry=_registry,
)

# NEM-2459: Additional worker metrics for restart analysis and alerting

PIPELINE_WORKER_RESTARTS_TOTAL = Counter(
    "hsi_pipeline_worker_restarts_total",
    "Total number of pipeline worker restarts by worker name and reason category",
    labelnames=["worker_name", "reason_category"],
    registry=_registry,
)

# Buckets for worker restart durations (in seconds)
# Covers range from 100ms to 60s with finer granularity at lower values
WORKER_RESTART_DURATION_BUCKETS = (
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
    15.0,  # 15s
    30.0,  # 30s
    60.0,  # 60s
)

PIPELINE_WORKER_RESTART_DURATION_SECONDS = Histogram(
    "hsi_pipeline_worker_restart_duration_seconds",
    "Duration of pipeline worker restart operations in seconds",
    labelnames=["worker_name"],
    buckets=WORKER_RESTART_DURATION_BUCKETS,
    registry=_registry,
)

PIPELINE_WORKER_STATE = Gauge(
    "hsi_pipeline_worker_state",
    "Current pipeline worker state (0=stopped, 1=running, 2=restarting, 3=failed)",
    labelnames=["worker_name"],
    registry=_registry,
)

PIPELINE_WORKER_CONSECUTIVE_FAILURES = Gauge(
    "hsi_pipeline_worker_consecutive_failures",
    "Number of consecutive failures for a pipeline worker",
    labelnames=["worker_name"],
    registry=_registry,
)

PIPELINE_WORKER_UPTIME_SECONDS = Gauge(
    "hsi_pipeline_worker_uptime_seconds",
    "Uptime of a pipeline worker in seconds since last successful start",
    labelnames=["worker_name"],
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
# Detection Class and Confidence Metrics (NEM-768)
# =============================================================================

# Counter for detections by object class (person, car, dog, etc.)
DETECTIONS_BY_CLASS_TOTAL = Counter(
    "hsi_detections_by_class_total",
    "Detections by object class",
    labelnames=["object_class"],
    registry=_registry,
)

# Histogram for detection confidence scores
# Buckets match typical confidence thresholds used in object detection
DETECTION_CONFIDENCE_BUCKETS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)

DETECTION_CONFIDENCE = Histogram(
    "hsi_detection_confidence",
    "Detection confidence scores",
    buckets=DETECTION_CONFIDENCE_BUCKETS,
    registry=_registry,
)

# Counter for detections filtered due to low confidence
DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL = Counter(
    "hsi_detections_filtered_low_confidence_total",
    "Detections filtered due to low confidence",
    registry=_registry,
)

# =============================================================================
# Risk Analysis Metrics (NEM-769)
# =============================================================================

# Risk score distribution histogram with buckets covering 0-100 range
RISK_SCORE_BUCKETS = (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)

RISK_SCORE = Histogram(
    "hsi_risk_score",
    "Risk score distribution from Nemotron analysis",
    buckets=RISK_SCORE_BUCKETS,
    registry=_registry,
)

EVENTS_BY_RISK_LEVEL = Counter(
    "hsi_events_by_risk_level_total",
    "Events by risk level",
    labelnames=["level"],
    registry=_registry,
)

PROMPT_TEMPLATE_USED = Counter(
    "hsi_prompt_template_used_total",
    "Prompt template usage by template name",
    labelnames=["template"],
    registry=_registry,
)

# =============================================================================
# LLM Context Utilization Metrics (NEM-1666)
# =============================================================================

# Context utilization histogram tracks how much of the context window is used
# Buckets cover 0-100% utilization with finer granularity at higher values
CONTEXT_UTILIZATION_BUCKETS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)

LLM_CONTEXT_UTILIZATION = Histogram(
    "hsi_llm_context_utilization",
    "LLM context window utilization ratio (0.0 to 1.0+)",
    buckets=CONTEXT_UTILIZATION_BUCKETS,
    registry=_registry,
)

# Counter for prompts that exceeded context limits
PROMPTS_TRUNCATED_TOTAL = Counter(
    "hsi_prompts_truncated_total",
    "Total number of prompts that required truncation due to context limits",
    registry=_registry,
)

# Counter for prompts that triggered high utilization warnings
PROMPTS_HIGH_UTILIZATION_TOTAL = Counter(
    "hsi_prompts_high_utilization_total",
    "Total number of prompts that exceeded the context utilization warning threshold",
    registry=_registry,
)

# =============================================================================
# Business Metrics (NEM-770)
# =============================================================================

FLORENCE_TASK_TOTAL = Counter(
    "hsi_florence_task_total",
    "Florence-2 task invocations",
    labelnames=["task"],  # caption, ocr, detect, dense_caption
    registry=_registry,
)

ENRICHMENT_MODEL_CALLS_TOTAL = Counter(
    "hsi_enrichment_model_calls_total",
    "Enrichment model calls",
    labelnames=["model"],  # brisque, violence, clothing, vehicle, pet
    registry=_registry,
)

ENRICHMENT_RETRY_TOTAL = Counter(
    "hsi_enrichment_retry_total",
    "Total retry attempts for enrichment service by endpoint",
    labelnames=["endpoint"],  # vehicle, pet, clothing, depth, distance, pose, action
    registry=_registry,
)

# =============================================================================
# Enrichment Pipeline Partial Failure Metrics (NEM-1672)
# =============================================================================

ENRICHMENT_SUCCESS_RATE = Gauge(
    "hsi_enrichment_success_rate",
    "Success rate of enrichment models (0.0 to 1.0)",
    labelnames=["model"],
    registry=_registry,
)

ENRICHMENT_PARTIAL_BATCHES_TOTAL = Counter(
    "hsi_enrichment_partial_batches_total",
    "Total number of batches with partial enrichment (some models succeeded, some failed)",
    registry=_registry,
)

ENRICHMENT_FAILURES_TOTAL = Counter(
    "hsi_enrichment_failures_total",
    "Total number of enrichment model failures by model name",
    labelnames=["model"],
    registry=_registry,
)

ENRICHMENT_BATCH_STATUS_TOTAL = Counter(
    "hsi_enrichment_batch_status_total",
    "Total number of enrichment batches by status (full, partial, failed, skipped)",
    labelnames=["status"],
    registry=_registry,
)

EVENTS_BY_CAMERA_TOTAL = Counter(
    "hsi_events_by_camera_total",
    "Events per camera",
    labelnames=["camera_id", "camera_name"],
    registry=_registry,
)

EVENTS_REVIEWED_TOTAL = Counter(
    "hsi_events_reviewed_total",
    "Events marked as reviewed",
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
# Cache Metrics (NEM-1682)
# =============================================================================

CACHE_HITS_TOTAL = Counter(
    "hsi_cache_hits_total",
    "Total number of cache hits",
    labelnames=["cache_type"],
    registry=_registry,
)

CACHE_MISSES_TOTAL = Counter(
    "hsi_cache_misses_total",
    "Total number of cache misses",
    labelnames=["cache_type"],
    registry=_registry,
)

CACHE_INVALIDATIONS_TOTAL = Counter(
    "hsi_cache_invalidations_total",
    "Total number of cache invalidations",
    labelnames=["cache_type", "reason"],
    registry=_registry,
)

# =============================================================================
# LLM Token Usage Metrics (NEM-1730)
# =============================================================================

NEMOTRON_TOKENS_INPUT_TOTAL = Counter(
    "hsi_nemotron_tokens_input_total",
    "Total input tokens sent to Nemotron LLM",
    labelnames=["camera_id"],
    registry=_registry,
)

NEMOTRON_TOKENS_OUTPUT_TOTAL = Counter(
    "hsi_nemotron_tokens_output_total",
    "Total output tokens received from Nemotron LLM",
    labelnames=["camera_id"],
    registry=_registry,
)

NEMOTRON_TOKENS_PER_SECOND = Gauge(
    "hsi_nemotron_tokens_per_second",
    "Current token throughput (tokens/second) for Nemotron LLM",
    registry=_registry,
)

NEMOTRON_TOKEN_COST_USD = Counter(
    "hsi_nemotron_token_cost_usd_total",
    "Total estimated cost in USD for Nemotron LLM token usage",
    labelnames=["camera_id"],
    registry=_registry,
)

# =============================================================================
# LLM Inference Cost Tracking Metrics (NEM-1673)
# =============================================================================

GPU_SECONDS_TOTAL = Counter(
    "hsi_gpu_seconds_total",
    "Total GPU time consumed by AI model inference in seconds",
    labelnames=["model"],
    registry=_registry,
)

ESTIMATED_COST_USD_TOTAL = Counter(
    "hsi_estimated_cost_usd_total",
    "Total estimated cost based on cloud equivalents in USD",
    labelnames=["service"],
    registry=_registry,
)

EVENT_ANALYSIS_COST_USD = Counter(
    "hsi_event_analysis_cost_usd_total",
    "Total estimated cost per event analysis in USD",
    labelnames=["camera_id"],
    registry=_registry,
)

# Budget tracking gauges
DAILY_COST_USD = Gauge(
    "hsi_daily_cost_usd",
    "Current daily estimated cost in USD",
    registry=_registry,
)

MONTHLY_COST_USD = Gauge(
    "hsi_monthly_cost_usd",
    "Current monthly estimated cost in USD",
    registry=_registry,
)

BUDGET_UTILIZATION_RATIO = Gauge(
    "hsi_budget_utilization_ratio",
    "Current budget utilization as a ratio (0.0 to 1.0+)",
    labelnames=["period"],  # daily, monthly
    registry=_registry,
)

BUDGET_EXCEEDED_TOTAL = Counter(
    "hsi_budget_exceeded_total",
    "Total number of times budget threshold was exceeded",
    labelnames=["period"],  # daily, monthly
    registry=_registry,
)

# =============================================================================
# MetricsService Class (NEM-1327)
# =============================================================================


class MetricsService:
    """Centralized service for recording Prometheus metrics.

    This class provides a unified interface for all metric recording operations,
    improving consistency, testability, and maintainability. All metric recording
    should go through this service rather than calling helper functions directly.

    Usage:
        from backend.core.metrics import get_metrics_service

        metrics = get_metrics_service()
        metrics.record_event_created()
        metrics.record_detection_by_class("person")
        metrics.observe_stage_duration("detect", 0.5)

    Benefits:
        - Centralized sanitization and validation
        - Easier mocking for tests
        - Consistent error handling
        - Single point for metric recording logic changes
    """

    def __init__(self) -> None:
        """Initialize the metrics service."""
        self._logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Queue Metrics
    # -------------------------------------------------------------------------

    def set_queue_depth(self, queue_name: str, depth: int) -> None:
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
            self._logger.warning(f"Unknown queue name for metrics: {queue_name}")

    def record_queue_overflow(self, queue_name: str, policy: str) -> None:
        """Record a queue overflow event.

        Args:
            queue_name: Name of the queue that overflowed
            policy: Overflow policy that was triggered (dlq, drop_oldest, reject)
        """
        QUEUE_OVERFLOW_TOTAL.labels(queue_name=queue_name, policy=policy).inc()

    def record_queue_items_moved_to_dlq(self, queue_name: str, count: int = 1) -> None:
        """Record items moved to dead-letter queue due to overflow.

        Args:
            queue_name: Name of the source queue
            count: Number of items moved (default 1)
        """
        QUEUE_ITEMS_MOVED_TO_DLQ_TOTAL.labels(queue_name=queue_name).inc(count)

    def record_queue_items_dropped(self, queue_name: str, count: int = 1) -> None:
        """Record items dropped due to queue overflow (drop_oldest policy).

        Args:
            queue_name: Name of the queue
            count: Number of items dropped (default 1)
        """
        QUEUE_ITEMS_DROPPED_TOTAL.labels(queue_name=queue_name).inc(count)

    def record_queue_items_rejected(self, queue_name: str, count: int = 1) -> None:
        """Record items rejected due to full queue (reject policy).

        Args:
            queue_name: Name of the queue
            count: Number of items rejected (default 1)
        """
        QUEUE_ITEMS_REJECTED_TOTAL.labels(queue_name=queue_name).inc(count)

    # -------------------------------------------------------------------------
    # Stage Duration Metrics
    # -------------------------------------------------------------------------

    def observe_stage_duration(self, stage: str, duration_seconds: float) -> None:
        """Record the duration of a pipeline stage.

        Args:
            stage: Name of the stage ("detect", "batch", "analyze")
            duration_seconds: Duration in seconds
        """
        STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)

    # -------------------------------------------------------------------------
    # Event/Detection Metrics
    # -------------------------------------------------------------------------

    def record_event_created(self) -> None:
        """Increment the events created counter."""
        EVENTS_CREATED_TOTAL.inc()

    def record_detection_processed(self, count: int = 1) -> None:
        """Increment the detections processed counter.

        Args:
            count: Number of detections to add (default 1)
        """
        DETECTIONS_PROCESSED_TOTAL.inc(count)

    def record_detection_by_class(self, object_class: str) -> None:
        """Increment the detection counter for a given object class.

        Args:
            object_class: The detected object class (e.g., "person", "car", "dog")

        Note:
            Object classes are sanitized using an allowlist of known COCO classes
            to prevent cardinality explosion from unexpected values.
        """
        safe_class = sanitize_object_class(object_class)
        DETECTIONS_BY_CLASS_TOTAL.labels(object_class=safe_class).inc()

    def observe_detection_confidence(self, confidence: float) -> None:
        """Record a detection confidence score to the histogram.

        Args:
            confidence: Detection confidence score (0.0-1.0)
        """
        DETECTION_CONFIDENCE.observe(confidence)

    def record_detection_filtered(self) -> None:
        """Increment the counter for detections filtered due to low confidence."""
        DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL.inc()

    # -------------------------------------------------------------------------
    # AI Service Metrics
    # -------------------------------------------------------------------------

    def observe_ai_request_duration(self, service: str, duration_seconds: float) -> None:
        """Record the duration of an AI service request.

        Args:
            service: Name of the service ("rtdetr" or "nemotron")
            duration_seconds: Duration in seconds
        """
        AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds)

    def record_pipeline_error(self, error_type: str) -> None:
        """Increment the pipeline errors counter.

        Args:
            error_type: Type of error (e.g., "connection_error", "timeout_error")

        Note:
            Error types are sanitized using an allowlist to prevent cardinality
            explosion from user-controlled or unexpected error types.
        """
        safe_error_type = sanitize_error_type(error_type)
        PIPELINE_ERRORS_TOTAL.labels(error_type=safe_error_type).inc()

    # -------------------------------------------------------------------------
    # Risk Analysis Metrics
    # -------------------------------------------------------------------------

    def observe_risk_score(self, score: int | float) -> None:
        """Record a risk score observation to the histogram.

        Args:
            score: Risk score from Nemotron analysis (0-100)
        """
        RISK_SCORE.observe(score)

    def record_event_by_risk_level(self, level: str) -> None:
        """Increment the events counter for a given risk level.

        Args:
            level: Risk level (e.g., "low", "medium", "high", "critical")

        Note:
            Risk levels are sanitized using an allowlist to prevent cardinality
            explosion from unexpected values.
        """
        safe_level = sanitize_risk_level(level)
        EVENTS_BY_RISK_LEVEL.labels(level=safe_level).inc()

    def record_prompt_template_used(self, template: str) -> None:
        """Increment the prompt template usage counter.

        Args:
            template: Name of the prompt template used
                (e.g., "basic", "enriched", "vision", "model_zoo")
        """
        PROMPT_TEMPLATE_USED.labels(template=template).inc()

    # -------------------------------------------------------------------------
    # Business Metrics
    # -------------------------------------------------------------------------

    def record_florence_task(self, task: str) -> None:
        """Increment the Florence task counter.

        Args:
            task: Name of the Florence task (caption, ocr, detect, dense_caption)
        """
        FLORENCE_TASK_TOTAL.labels(task=task).inc()

    def record_enrichment_model_call(self, model: str) -> None:
        """Increment the enrichment model calls counter.

        Args:
            model: Name of the enrichment model (brisque, violence, clothing, vehicle, pet)
        """
        ENRICHMENT_MODEL_CALLS_TOTAL.labels(model=model).inc()

    def set_enrichment_success_rate(self, model: str, rate: float) -> None:
        """Set the success rate gauge for an enrichment model.

        Args:
            model: Name of the enrichment model
            rate: Success rate (0.0 to 1.0)
        """
        ENRICHMENT_SUCCESS_RATE.labels(model=model).set(rate)

    def record_enrichment_partial_batch(self) -> None:
        """Increment the counter for batches with partial enrichment."""
        ENRICHMENT_PARTIAL_BATCHES_TOTAL.inc()

    def record_enrichment_failure(self, model: str) -> None:
        """Increment the failure counter for an enrichment model.

        Args:
            model: Name of the enrichment model that failed
        """
        ENRICHMENT_FAILURES_TOTAL.labels(model=model).inc()

    def record_enrichment_batch_status(self, status: str) -> None:
        """Record the status of an enrichment batch.

        Args:
            status: Enrichment status (full, partial, failed, skipped)
        """
        ENRICHMENT_BATCH_STATUS_TOTAL.labels(status=status).inc()

    def record_event_by_camera(self, camera_id: str, camera_name: str) -> None:
        """Increment the events per camera counter.

        Args:
            camera_id: Unique identifier for the camera
            camera_name: Human-readable camera name

        Note:
            Camera IDs and names are sanitized to prevent cardinality explosion
            from malformed or excessively long values.
        """
        safe_camera_id = sanitize_camera_id(camera_id)
        safe_camera_name = sanitize_metric_label(camera_name, max_length=64)
        EVENTS_BY_CAMERA_TOTAL.labels(camera_id=safe_camera_id, camera_name=safe_camera_name).inc()

    def record_event_reviewed(self) -> None:
        """Increment the events reviewed counter."""
        EVENTS_REVIEWED_TOTAL.inc()

    # -------------------------------------------------------------------------
    # Cache Metrics (NEM-1682)
    # -------------------------------------------------------------------------

    def record_cache_hit(self, cache_type: str) -> None:
        """Record a cache hit.

        Args:
            cache_type: Type of cache (e.g., "event_stats", "cameras", "system")
        """
        CACHE_HITS_TOTAL.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str) -> None:
        """Record a cache miss.

        Args:
            cache_type: Type of cache (e.g., "event_stats", "cameras", "system")
        """
        CACHE_MISSES_TOTAL.labels(cache_type=cache_type).inc()

    def record_cache_invalidation(self, cache_type: str, reason: str) -> None:
        """Record a cache invalidation.

        Args:
            cache_type: Type of cache (e.g., "event_stats", "cameras", "events")
            reason: Reason for invalidation (e.g., "event_created", "camera_updated")
        """
        CACHE_INVALIDATIONS_TOTAL.labels(cache_type=cache_type, reason=reason).inc()

    # -------------------------------------------------------------------------
    # LLM Token Usage Metrics (NEM-1730)
    # -------------------------------------------------------------------------

    def record_nemotron_tokens(
        self,
        camera_id: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float | None = None,
        input_cost_per_1k: float | None = None,
        output_cost_per_1k: float | None = None,
    ) -> None:
        """Record Nemotron LLM token usage metrics.

        Args:
            camera_id: Camera identifier for the analysis request
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            duration_seconds: Optional request duration for throughput calculation
            input_cost_per_1k: Optional cost per 1000 input tokens (USD)
            output_cost_per_1k: Optional cost per 1000 output tokens (USD)

        Note:
            Camera IDs are sanitized to prevent cardinality explosion.
            If duration_seconds is 0 or negative, throughput is not calculated.
        """
        safe_camera_id = sanitize_camera_id(camera_id)

        # Record token counts
        NEMOTRON_TOKENS_INPUT_TOTAL.labels(camera_id=safe_camera_id).inc(input_tokens)
        NEMOTRON_TOKENS_OUTPUT_TOTAL.labels(camera_id=safe_camera_id).inc(output_tokens)

        # Calculate and record throughput if duration is valid
        if duration_seconds is not None and duration_seconds > 0:
            total_tokens = input_tokens + output_tokens
            tokens_per_second = total_tokens / duration_seconds
            NEMOTRON_TOKENS_PER_SECOND.set(tokens_per_second)

        # Calculate and record cost if pricing is configured
        if input_cost_per_1k is not None or output_cost_per_1k is not None:
            cost = 0.0
            if input_cost_per_1k is not None:
                cost += (input_tokens / 1000.0) * input_cost_per_1k
            if output_cost_per_1k is not None:
                cost += (output_tokens / 1000.0) * output_cost_per_1k
            if cost > 0:
                NEMOTRON_TOKEN_COST_USD.labels(camera_id=safe_camera_id).inc(cost)

    # -------------------------------------------------------------------------
    # LLM Inference Cost Tracking Metrics (NEM-1673)
    # -------------------------------------------------------------------------

    def record_gpu_seconds(self, model: str, duration_seconds: float) -> None:
        """Record GPU time consumed by AI model inference.

        Args:
            model: Model identifier (e.g., 'nemotron', 'rtdetr', 'florence')
            duration_seconds: Duration of inference in seconds
        """
        if duration_seconds > 0:
            GPU_SECONDS_TOTAL.labels(model=model).inc(duration_seconds)

    def record_estimated_cost(self, service: str, cost_usd: float) -> None:
        """Record estimated cost based on cloud equivalents.

        Args:
            service: Service identifier (e.g., 'nemotron', 'rtdetr', 'enrichment')
            cost_usd: Estimated cost in USD
        """
        if cost_usd > 0:
            ESTIMATED_COST_USD_TOTAL.labels(service=service).inc(cost_usd)

    def record_event_analysis_cost(self, camera_id: str, cost_usd: float) -> None:
        """Record cost for a single event analysis.

        Args:
            camera_id: Camera identifier
            cost_usd: Total cost for the event analysis in USD
        """
        safe_camera_id = sanitize_camera_id(camera_id)
        if cost_usd > 0:
            EVENT_ANALYSIS_COST_USD.labels(camera_id=safe_camera_id).inc(cost_usd)

    def set_daily_cost(self, cost_usd: float) -> None:
        """Set the current daily cost gauge.

        Args:
            cost_usd: Current daily cost in USD
        """
        DAILY_COST_USD.set(cost_usd)

    def set_monthly_cost(self, cost_usd: float) -> None:
        """Set the current monthly cost gauge.

        Args:
            cost_usd: Current monthly cost in USD
        """
        MONTHLY_COST_USD.set(cost_usd)

    def set_budget_utilization(self, period: str, ratio: float) -> None:
        """Set budget utilization ratio for a period.

        Args:
            period: Budget period ('daily' or 'monthly')
            ratio: Utilization ratio (0.0 to 1.0+, >1.0 indicates over budget)
        """
        BUDGET_UTILIZATION_RATIO.labels(period=period).set(ratio)

    def record_budget_exceeded(self, period: str) -> None:
        """Record that budget threshold was exceeded.

        Args:
            period: Budget period ('daily' or 'monthly')
        """
        BUDGET_EXCEEDED_TOTAL.labels(period=period).inc()


# Global singleton instance for MetricsService
_metrics_service: MetricsService | None = None


def get_metrics_service() -> MetricsService:
    """Get the global MetricsService instance.

    Returns:
        The singleton MetricsService instance
    """
    global _metrics_service  # noqa: PLW0603
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service


# =============================================================================
# Helper Functions (Legacy - prefer using MetricsService)
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

    Note:
        Error types are sanitized using an allowlist to prevent cardinality
        explosion from user-controlled or unexpected error types (NEM-1064).
    """
    # Sanitize error type to prevent cardinality explosion
    safe_error_type = sanitize_error_type(error_type)
    PIPELINE_ERRORS_TOTAL.labels(error_type=safe_error_type).inc()


# =============================================================================
# Detection Class and Confidence Helpers (NEM-768)
# =============================================================================


def record_detection_by_class(object_class: str) -> None:
    """Increment the detection counter for a given object class.

    Args:
        object_class: The detected object class (e.g., "person", "car", "dog")

    Note:
        Object classes are sanitized using an allowlist of known COCO classes
        to prevent cardinality explosion from unexpected values (NEM-1064).
    """
    # Sanitize object class to prevent cardinality explosion
    safe_class = sanitize_object_class(object_class)
    DETECTIONS_BY_CLASS_TOTAL.labels(object_class=safe_class).inc()


def observe_detection_confidence(confidence: float) -> None:
    """Record a detection confidence score to the histogram.

    Args:
        confidence: Detection confidence score (0.0-1.0)
    """
    DETECTION_CONFIDENCE.observe(confidence)


def record_detection_filtered() -> None:
    """Increment the counter for detections filtered due to low confidence."""
    DETECTIONS_FILTERED_LOW_CONFIDENCE_TOTAL.inc()


def observe_risk_score(score: int | float) -> None:
    """Record a risk score observation to the histogram.

    Args:
        score: Risk score from Nemotron analysis (0-100)
    """
    RISK_SCORE.observe(score)


def record_event_by_risk_level(level: str) -> None:
    """Increment the events counter for a given risk level.

    Args:
        level: Risk level (e.g., "low", "medium", "high", "critical")

    Note:
        Risk levels are sanitized using an allowlist to prevent cardinality
        explosion from unexpected values (NEM-1064).
    """
    # Sanitize risk level to prevent cardinality explosion
    safe_level = sanitize_risk_level(level)
    EVENTS_BY_RISK_LEVEL.labels(level=safe_level).inc()


def record_prompt_template_used(template: str) -> None:
    """Increment the prompt template usage counter.

    Args:
        template: Name of the prompt template used
            (e.g., "basic", "enriched", "vision", "model_zoo")
    """
    PROMPT_TEMPLATE_USED.labels(template=template).inc()


# =============================================================================
# Context Utilization Helpers (NEM-1666)
# =============================================================================


def observe_context_utilization(utilization: float) -> None:
    """Record LLM context utilization ratio to the histogram.

    Args:
        utilization: Context utilization ratio (0.0 to 1.0+)
            Values > 1.0 indicate the prompt exceeded the context window
    """
    LLM_CONTEXT_UTILIZATION.observe(utilization)

    # Also record if utilization exceeds warning threshold (default 0.8)
    from backend.core.config import get_settings

    settings = get_settings()
    if utilization >= settings.context_utilization_warning_threshold:
        PROMPTS_HIGH_UTILIZATION_TOTAL.inc()


def record_prompt_truncated() -> None:
    """Increment the counter for prompts that required truncation."""
    PROMPTS_TRUNCATED_TOTAL.inc()


# =============================================================================
# Business Metric Helpers (NEM-770)
# =============================================================================


def record_florence_task(task: str) -> None:
    """Increment the Florence task counter.

    Args:
        task: Name of the Florence task (caption, ocr, detect, dense_caption)
    """
    FLORENCE_TASK_TOTAL.labels(task=task).inc()


def record_enrichment_model_call(model: str) -> None:
    """Increment the enrichment model calls counter.

    Args:
        model: Name of the enrichment model (brisque, violence, clothing, vehicle, pet)
    """
    ENRICHMENT_MODEL_CALLS_TOTAL.labels(model=model).inc()


def increment_enrichment_retry(endpoint: str) -> None:
    """Increment the enrichment retry counter for a specific endpoint.

    Called when an enrichment service call is retried due to transient failures
    (ConnectError, TimeoutException, HTTP 5xx errors).

    Args:
        endpoint: Name of the enrichment endpoint (vehicle, pet, clothing,
            depth, distance, pose, action)
    """
    ENRICHMENT_RETRY_TOTAL.labels(endpoint=endpoint).inc()


def set_enrichment_success_rate(model: str, rate: float) -> None:
    """Set the success rate gauge for an enrichment model.

    Args:
        model: Name of the enrichment model
        rate: Success rate (0.0 to 1.0)
    """
    ENRICHMENT_SUCCESS_RATE.labels(model=model).set(rate)


def record_enrichment_partial_batch() -> None:
    """Increment the counter for batches with partial enrichment."""
    ENRICHMENT_PARTIAL_BATCHES_TOTAL.inc()


def record_enrichment_failure(model: str) -> None:
    """Increment the failure counter for an enrichment model.

    Args:
        model: Name of the enrichment model that failed
    """
    ENRICHMENT_FAILURES_TOTAL.labels(model=model).inc()


def record_enrichment_batch_status(status: str) -> None:
    """Record the status of an enrichment batch.

    Args:
        status: Enrichment status (full, partial, failed, skipped)
    """
    ENRICHMENT_BATCH_STATUS_TOTAL.labels(status=status).inc()


def record_event_by_camera(camera_id: str, camera_name: str) -> None:
    """Increment the events per camera counter.

    Args:
        camera_id: Unique identifier for the camera
        camera_name: Human-readable camera name

    Note:
        Camera IDs and names are sanitized to prevent cardinality explosion
        from malformed or excessively long values (NEM-1064).
    """
    # Sanitize camera_id and camera_name to prevent cardinality explosion
    safe_camera_id = sanitize_camera_id(camera_id)
    safe_camera_name = sanitize_metric_label(camera_name, max_length=64)
    EVENTS_BY_CAMERA_TOTAL.labels(camera_id=safe_camera_id, camera_name=safe_camera_name).inc()


def record_event_reviewed() -> None:
    """Increment the events reviewed counter."""
    EVENTS_REVIEWED_TOTAL.inc()


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


# =============================================================================
# Cache Metric Helpers (NEM-1682)
# =============================================================================


def record_cache_hit(cache_type: str) -> None:
    """Record a cache hit.

    Args:
        cache_type: Type of cache (e.g., "event_stats", "cameras", "system")
    """
    CACHE_HITS_TOTAL.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Record a cache miss.

    Args:
        cache_type: Type of cache (e.g., "event_stats", "cameras", "system")
    """
    CACHE_MISSES_TOTAL.labels(cache_type=cache_type).inc()


def record_cache_invalidation(cache_type: str, reason: str) -> None:
    """Record a cache invalidation.

    Args:
        cache_type: Type of cache (e.g., "event_stats", "cameras", "events")
        reason: Reason for invalidation (e.g., "event_created", "camera_updated")
    """
    CACHE_INVALIDATIONS_TOTAL.labels(cache_type=cache_type, reason=reason).inc()


# =============================================================================
# LLM Token Usage Helpers (NEM-1730)
# =============================================================================


def record_nemotron_tokens(
    camera_id: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float | None = None,
    input_cost_per_1k: float | None = None,
    output_cost_per_1k: float | None = None,
) -> None:
    """Record Nemotron LLM token usage metrics.

    Args:
        camera_id: Camera identifier for the analysis request
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens
        duration_seconds: Optional request duration for throughput calculation
        input_cost_per_1k: Optional cost per 1000 input tokens (USD)
        output_cost_per_1k: Optional cost per 1000 output tokens (USD)

    Note:
        Camera IDs are sanitized to prevent cardinality explosion.
        If duration_seconds is 0 or negative, throughput is not calculated.
    """
    safe_camera_id = sanitize_camera_id(camera_id)

    # Record token counts
    NEMOTRON_TOKENS_INPUT_TOTAL.labels(camera_id=safe_camera_id).inc(input_tokens)
    NEMOTRON_TOKENS_OUTPUT_TOTAL.labels(camera_id=safe_camera_id).inc(output_tokens)

    # Calculate and record throughput if duration is valid
    if duration_seconds is not None and duration_seconds > 0:
        total_tokens = input_tokens + output_tokens
        tokens_per_second = total_tokens / duration_seconds
        NEMOTRON_TOKENS_PER_SECOND.set(tokens_per_second)

    # Calculate and record cost if pricing is configured
    if input_cost_per_1k is not None or output_cost_per_1k is not None:
        cost = 0.0
        if input_cost_per_1k is not None:
            cost += (input_tokens / 1000.0) * input_cost_per_1k
        if output_cost_per_1k is not None:
            cost += (output_tokens / 1000.0) * output_cost_per_1k
        if cost > 0:
            NEMOTRON_TOKEN_COST_USD.labels(camera_id=safe_camera_id).inc(cost)


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

    def get_stage_stats(self, stage: str, window_minutes: int = 60) -> StageStatsDict:
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

        # NEM-1328: Use numpy for more accurate and efficient percentile calculations
        arr = np.array(samples)
        count = len(arr)

        return {
            "avg_ms": float(np.mean(arr)),
            "min_ms": float(np.min(arr)),
            "max_ms": float(np.max(arr)),
            "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)),
            "p99_ms": float(np.percentile(arr, 99)),
            "sample_count": count,
        }

    def get_pipeline_summary(self, window_minutes: int = 60) -> dict[str, StageStatsDict]:
        """Get latency statistics for all pipeline stages.

        Args:
            window_minutes: Only include samples from the last N minutes

        Returns:
            Dictionary mapping stage names to their statistics
        """
        return {stage: self.get_stage_stats(stage, window_minutes) for stage in self.STAGES}

    def get_latency_history(
        self, window_minutes: int = 60, bucket_seconds: int = 60
    ) -> list[LatencyHistoryEntry]:
        """Get latency history as time-series data for charting.

        Groups samples into time buckets and calculates statistics for each bucket.
        Returns chronologically ordered snapshots suitable for time-series visualization.

        Args:
            window_minutes: Time window to retrieve (default 60 minutes)
            bucket_seconds: Bucket size in seconds for aggregation (default 60 = 1 minute)

        Returns:
            List of snapshots, each containing:
            - timestamp: Bucket start time (ISO format)
            - stages: Dict mapping stage names to latency stats for that bucket
        """
        from collections import defaultdict
        from datetime import datetime

        cutoff = self._time.time() - (window_minutes * 60)

        # Collect all samples within window, grouped by bucket
        bucket_samples: dict[int, dict[str, list[float]]] = defaultdict(
            lambda: {stage: [] for stage in self.STAGES}
        )

        with self._lock:
            for stage in self.STAGES:
                for ts, latency in self._samples[stage]:
                    if ts >= cutoff:
                        # Calculate bucket index
                        bucket_idx = int((ts - cutoff) // bucket_seconds)
                        bucket_samples[bucket_idx][stage].append(latency)

        # Convert buckets to output format
        snapshots: list[LatencyHistoryEntry] = []
        for bucket_idx in sorted(bucket_samples.keys()):
            bucket_start = cutoff + (bucket_idx * bucket_seconds)
            timestamp = datetime.fromtimestamp(bucket_start, tz=UTC)

            stages: dict[str, BucketStatsDict | None] = {}
            for stage in self.STAGES:
                samples = bucket_samples[bucket_idx][stage]
                if samples:
                    # NEM-1328: Use numpy for more accurate and efficient percentile calculations
                    arr = np.array(samples)
                    count = len(arr)
                    stages[stage] = {
                        "avg_ms": float(np.mean(arr)),
                        "p50_ms": float(np.percentile(arr, 50)),
                        "p95_ms": float(np.percentile(arr, 95)),
                        "p99_ms": float(np.percentile(arr, 99)),
                        "sample_count": count,
                    }
                else:
                    stages[stage] = None  # type: ignore[assignment]

            snapshots.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "stages": stages,
                }
            )

        return snapshots


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
# Model Zoo Latency Tracker
# =============================================================================


class ModelLatencyTracker:
    """Track and analyze latency for Model Zoo models.

    This class provides in-memory circular buffer storage for model
    latency measurements with statistical analysis capabilities.

    Model Zoo models tracked:
    - yolo11-license-plate, yolo11-face, paddleocr, clip-vit-l, etc.
    - All 18 models in the Model Zoo registry

    Usage:
        tracker = ModelLatencyTracker(max_samples=1000)
        tracker.record_model_latency("yolo11-license-plate", 45.5)
        stats = tracker.get_model_stats("yolo11-license-plate", window_minutes=5)
        history = tracker.get_model_latency_history("yolo11-license-plate")
    """

    def __init__(self, max_samples: int = 1000) -> None:
        """Initialize the model latency tracker.

        Args:
            max_samples: Maximum samples to keep per model (circular buffer size)
        """
        import time
        from threading import Lock

        self._max_samples = max_samples
        self._lock = Lock()
        # Each model has a deque of (timestamp, latency_ms) tuples
        self._samples: dict[str, deque[tuple[float, float]]] = {}
        self._time = time  # Store reference for testing

    def _get_or_create_deque(self, model_name: str) -> deque[tuple[float, float]]:
        """Get or create a deque for a model.

        Args:
            model_name: Model identifier

        Returns:
            Deque for the model's latency samples
        """
        from collections import deque

        if model_name not in self._samples:
            self._samples[model_name] = deque(maxlen=self._max_samples)
        return self._samples[model_name]

    def record_model_latency(self, model_name: str, latency_ms: float) -> None:
        """Record a latency sample for a Model Zoo model.

        Args:
            model_name: Model identifier (e.g., 'yolo11-license-plate')
            latency_ms: Latency in milliseconds
        """
        timestamp = self._time.time()
        with self._lock:
            samples_deque = self._get_or_create_deque(model_name)
            samples_deque.append((timestamp, latency_ms))

    def get_model_stats(self, model_name: str, window_minutes: int = 60) -> ModelStatsDict:
        """Get latency statistics for a single model.

        Args:
            model_name: Model identifier
            window_minutes: Only include samples from the last N minutes

        Returns:
            Dictionary with statistics:
            - avg_ms: Average latency
            - p50_ms: 50th percentile (median)
            - p95_ms: 95th percentile
            - sample_count: Number of samples used
        """
        if model_name not in self._samples:
            return {
                "avg_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "sample_count": 0,
            }

        cutoff = self._time.time() - (window_minutes * 60)

        with self._lock:
            samples = [latency for ts, latency in self._samples[model_name] if ts >= cutoff]

        if not samples:
            return {
                "avg_ms": None,
                "p50_ms": None,
                "p95_ms": None,
                "sample_count": 0,
            }

        # NEM-1328: Use numpy for more accurate and efficient percentile calculations
        arr = np.array(samples)
        count = len(arr)

        return {
            "avg_ms": float(np.mean(arr)),
            "p50_ms": float(np.percentile(arr, 50)),
            "p95_ms": float(np.percentile(arr, 95)),
            "sample_count": count,
        }

    def get_model_latency_history(
        self, model_name: str, window_minutes: int = 60, bucket_seconds: int = 60
    ) -> list[ModelLatencyHistoryEntry]:
        """Get latency history for a specific model as time-series data.

        Groups samples into time buckets and calculates statistics for each bucket.
        Returns chronologically ordered snapshots suitable for time-series visualization.

        Args:
            model_name: Model identifier
            window_minutes: Time window to retrieve (default 60 minutes)
            bucket_seconds: Bucket size in seconds for aggregation (default 60 = 1 minute)

        Returns:
            List of snapshots, each containing:
            - timestamp: Bucket start time (ISO format)
            - stats: Latency stats for that bucket (None if no data)
        """
        from collections import defaultdict
        from datetime import datetime

        cutoff = self._time.time() - (window_minutes * 60)

        # Collect samples within window, grouped by bucket
        bucket_samples: dict[int, list[float]] = defaultdict(list)

        with self._lock:
            if model_name in self._samples:
                for ts, latency in self._samples[model_name]:
                    if ts >= cutoff:
                        # Calculate bucket index
                        bucket_idx = int((ts - cutoff) // bucket_seconds)
                        bucket_samples[bucket_idx].append(latency)

        # Generate all buckets in the window (including empty ones)
        num_buckets = (window_minutes * 60) // bucket_seconds
        snapshots: list[ModelLatencyHistoryEntry] = []

        for bucket_idx in range(num_buckets):
            bucket_start = cutoff + (bucket_idx * bucket_seconds)
            timestamp = datetime.fromtimestamp(bucket_start, tz=UTC)

            samples = bucket_samples.get(bucket_idx, [])
            stats: BucketStatsDict | None
            if samples:
                # NEM-1328: Use numpy for more accurate and efficient percentile calculations
                arr = np.array(samples)
                count = len(arr)
                stats = {
                    "avg_ms": float(np.mean(arr)),
                    "p50_ms": float(np.percentile(arr, 50)),
                    "p95_ms": float(np.percentile(arr, 95)),
                    "p99_ms": float(np.percentile(arr, 99)),
                    "sample_count": count,
                }
            else:
                stats = None

            snapshots.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "stats": stats,
                }
            )

        return snapshots


# Global singleton instance for Model Zoo latency tracking
_model_latency_tracker: ModelLatencyTracker | None = None


def get_model_latency_tracker() -> ModelLatencyTracker | None:
    """Get the global Model Zoo latency tracker instance.

    Returns:
        The singleton ModelLatencyTracker instance, or None if not initialized
    """
    global _model_latency_tracker  # noqa: PLW0603
    if _model_latency_tracker is None:
        _model_latency_tracker = ModelLatencyTracker()
    return _model_latency_tracker


def record_model_zoo_latency(model_name: str, latency_ms: float) -> None:
    """Record a Model Zoo model latency measurement.

    Convenience function that uses the global tracker instance.

    Args:
        model_name: Model identifier (e.g., 'yolo11-license-plate')
        latency_ms: Latency in milliseconds
    """
    tracker = get_model_latency_tracker()
    if tracker is not None:
        tracker.record_model_latency(model_name, latency_ms)


# =============================================================================
# Batch Size Limit Metrics (NEM-1726)
# =============================================================================

BATCH_MAX_DETECTIONS_REACHED_TOTAL = Counter(
    "hsi_batch_max_detections_reached_total",
    "Total number of times a batch reached max detections limit and was split",
    labelnames=["camera_id"],
    registry=_registry,
)


def record_batch_max_reached(camera_id: str) -> None:
    """Record when a batch reaches max detections limit.

    Args:
        camera_id: Camera identifier where the batch was split
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    BATCH_MAX_DETECTIONS_REACHED_TOTAL.labels(camera_id=safe_camera_id).inc()


# =============================================================================
# Database Query Duration Metrics (NEM-1475)
# =============================================================================

# Buckets for database query durations (in seconds)
# Covers range from 10ms to 10s with finer granularity at lower values
DB_QUERY_DURATION_BUCKETS = (
    0.01,  # 10ms
    0.05,  # 50ms
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "hsi_db_query_duration_seconds",
    "Database query duration in seconds",
    buckets=DB_QUERY_DURATION_BUCKETS,
    registry=_registry,
)

SLOW_QUERIES_TOTAL = Counter(
    "hsi_slow_queries_total",
    "Total number of slow database queries detected",
    registry=_registry,
)


def observe_db_query_duration(duration_seconds: float) -> None:
    """Record a database query duration to the histogram.

    Args:
        duration_seconds: Query duration in seconds
    """
    DB_QUERY_DURATION_SECONDS.observe(duration_seconds)


def record_slow_query() -> None:
    """Increment the counter for slow database queries."""
    SLOW_QUERIES_TOTAL.inc()


# =============================================================================
# Token Counting Metrics (NEM-1723)
# =============================================================================

# Token count buckets for prompt size histogram
PROMPT_TOKEN_BUCKETS = (
    100,
    250,
    500,
    750,
    1000,
    1500,
    2000,
    2500,
    3000,
    3500,
    4000,
)

PROMPT_TOKENS = Histogram(
    "hsi_prompt_tokens",
    "Token count distribution for LLM prompts",
    buckets=PROMPT_TOKEN_BUCKETS,
    registry=_registry,
)

PROMPT_TRUNCATED_TOTAL = Counter(
    "hsi_prompt_truncated_total",
    "Total number of prompt sections truncated to fit context window",
    labelnames=["section_name"],
    registry=_registry,
)


def observe_prompt_tokens(token_count: int) -> None:
    """Record prompt token count to histogram.

    Args:
        token_count: Number of tokens in the prompt
    """
    PROMPT_TOKENS.observe(token_count)


def record_prompt_section_truncated(section_name: str) -> None:
    """Record when a prompt section is truncated.

    Args:
        section_name: Name of the section that was truncated
            (e.g., "cross_camera", "baseline", "zones")
    """
    # Sanitize section name to prevent cardinality explosion
    safe_section = sanitize_metric_label(section_name, max_length=32)
    PROMPT_TRUNCATED_TOTAL.labels(section_name=safe_section).inc()


# =============================================================================
# AI Model Cold Start and Warmup Metrics (NEM-1670)
# =============================================================================

# Warmup duration histogram buckets (in seconds)
# Covers range from 100ms to 60s with finer granularity at lower values
WARMUP_DURATION_BUCKETS = (
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

MODEL_WARMUP_DURATION = Histogram(
    "hsi_model_warmup_duration_seconds",
    "Duration of AI model warmup operations in seconds",
    labelnames=["model"],
    buckets=WARMUP_DURATION_BUCKETS,
    registry=_registry,
)

MODEL_COLD_START_TOTAL = Counter(
    "hsi_model_cold_start_total",
    "Total number of cold start events per AI model",
    labelnames=["model"],
    registry=_registry,
)

MODEL_WARMTH_STATE = Gauge(
    "hsi_model_warmth_state",
    "Current warmth state of AI models (0=cold, 1=warming, 2=warm)",
    labelnames=["model"],
    registry=_registry,
)

MODEL_LAST_INFERENCE_SECONDS_AGO = Gauge(
    "hsi_model_last_inference_seconds_ago",
    "Seconds since last inference for AI models",
    labelnames=["model"],
    registry=_registry,
)


def observe_model_warmup_duration(model: str, duration_seconds: float) -> None:
    """Record AI model warmup duration to histogram.

    Args:
        model: Model identifier (e.g., 'rtdetr', 'nemotron')
        duration_seconds: Warmup duration in seconds
    """
    MODEL_WARMUP_DURATION.labels(model=model).observe(duration_seconds)


def record_model_cold_start(model: str) -> None:
    """Increment cold start counter for an AI model.

    Args:
        model: Model identifier (e.g., 'rtdetr', 'nemotron')
    """
    MODEL_COLD_START_TOTAL.labels(model=model).inc()


def set_model_warmth_state(model: str, state: str) -> None:
    """Set the current warmth state gauge for an AI model.

    Args:
        model: Model identifier (e.g., 'rtdetr', 'nemotron')
        state: Warmth state ('cold', 'warming', 'warm')
    """
    state_value = {"cold": 0, "warming": 1, "warm": 2}.get(state, 0)
    MODEL_WARMTH_STATE.labels(model=model).set(state_value)


def set_model_last_inference_ago(model: str, seconds_ago: float | None) -> None:
    """Set the seconds since last inference gauge for an AI model.

    Args:
        model: Model identifier (e.g., 'rtdetr', 'nemotron')
        seconds_ago: Seconds since last inference, or None if never used
    """
    if seconds_ago is None:
        # Use -1 to indicate "never used" (gauge doesn't support None)
        MODEL_LAST_INFERENCE_SECONDS_AGO.labels(model=model).set(-1)
    else:
        MODEL_LAST_INFERENCE_SECONDS_AGO.labels(model=model).set(seconds_ago)


# =============================================================================
# Real User Monitoring (RUM) Metrics (NEM-1635)
# =============================================================================

# LCP (Largest Contentful Paint) histogram - measures in seconds
# Good: < 2.5s, Needs Improvement: 2.5-4s, Poor: > 4s
RUM_LCP_BUCKETS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 8.0, 10.0)

RUM_LCP_SECONDS = Histogram(
    "hsi_rum_lcp_seconds",
    "Largest Contentful Paint - measures loading performance (seconds)",
    labelnames=["path", "rating"],
    buckets=RUM_LCP_BUCKETS,
    registry=_registry,
)

# FID/INP (First Input Delay / Interaction to Next Paint) histogram - measures in seconds
# Good: < 100ms (0.1s), Needs Improvement: 100-300ms, Poor: > 300ms
RUM_INTERACTIVITY_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0)

RUM_FID_SECONDS = Histogram(
    "hsi_rum_fid_seconds",
    "First Input Delay - measures interactivity (seconds, legacy)",
    labelnames=["path", "rating"],
    buckets=RUM_INTERACTIVITY_BUCKETS,
    registry=_registry,
)

RUM_INP_SECONDS = Histogram(
    "hsi_rum_inp_seconds",
    "Interaction to Next Paint - measures interactivity (seconds)",
    labelnames=["path", "rating"],
    buckets=RUM_INTERACTIVITY_BUCKETS,
    registry=_registry,
)

# CLS (Cumulative Layout Shift) histogram - dimensionless score
# Good: < 0.1, Needs Improvement: 0.1-0.25, Poor: > 0.25
RUM_CLS_BUCKETS = (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 1.0)

RUM_CLS = Histogram(
    "hsi_rum_cls",
    "Cumulative Layout Shift - measures visual stability (dimensionless)",
    labelnames=["path", "rating"],
    buckets=RUM_CLS_BUCKETS,
    registry=_registry,
)

# TTFB (Time to First Byte) histogram - measures in seconds
# Good: < 800ms, Needs Improvement: 800-1800ms, Poor: > 1800ms
RUM_TTFB_BUCKETS = (0.2, 0.4, 0.6, 0.8, 1.0, 1.4, 1.8, 2.5, 5.0)

RUM_TTFB_SECONDS = Histogram(
    "hsi_rum_ttfb_seconds",
    "Time to First Byte - measures server response time (seconds)",
    labelnames=["path", "rating"],
    buckets=RUM_TTFB_BUCKETS,
    registry=_registry,
)

# FCP (First Contentful Paint) histogram - measures in seconds
# Good: < 1.8s, Needs Improvement: 1.8-3s, Poor: > 3s
RUM_FCP_BUCKETS = (0.5, 1.0, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 6.0)

RUM_FCP_SECONDS = Histogram(
    "hsi_rum_fcp_seconds",
    "First Contentful Paint - measures first content render (seconds)",
    labelnames=["path", "rating"],
    buckets=RUM_FCP_BUCKETS,
    registry=_registry,
)

# Counter for total RUM metrics received
RUM_METRICS_TOTAL = Counter(
    "hsi_rum_metrics_total",
    "Total number of RUM metrics received",
    labelnames=["metric_name", "rating"],
    registry=_registry,
)


def observe_rum_lcp(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record LCP (Largest Contentful Paint) metric.

    Args:
        value_ms: LCP value in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    # Sanitize path to prevent cardinality explosion
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    # Convert from milliseconds to seconds for Prometheus
    RUM_LCP_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="LCP", rating=safe_rating).inc()


def observe_rum_fid(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record FID (First Input Delay) metric.

    Args:
        value_ms: FID value in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    RUM_FID_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="FID", rating=safe_rating).inc()


def observe_rum_inp(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record INP (Interaction to Next Paint) metric.

    Args:
        value_ms: INP value in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    RUM_INP_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="INP", rating=safe_rating).inc()


def observe_rum_cls(value: float, path: str = "/", rating: str = "unknown") -> None:
    """Record CLS (Cumulative Layout Shift) metric.

    Args:
        value: CLS value (dimensionless score)
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    # CLS is already dimensionless, no conversion needed
    RUM_CLS.labels(path=safe_path, rating=safe_rating).observe(value)
    RUM_METRICS_TOTAL.labels(metric_name="CLS", rating=safe_rating).inc()


def observe_rum_ttfb(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record TTFB (Time to First Byte) metric.

    Args:
        value_ms: TTFB value in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    RUM_TTFB_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="TTFB", rating=safe_rating).inc()


def observe_rum_fcp(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record FCP (First Contentful Paint) metric.

    Args:
        value_ms: FCP value in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    RUM_FCP_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="FCP", rating=safe_rating).inc()


# =============================================================================
# Prompt A/B Testing Metrics (NEM-1667)
# =============================================================================

# Latency histogram for prompt versions
PROMPT_VERSION_LATENCY_BUCKETS = (
    0.1,  # 100ms
    0.25,  # 250ms
    0.5,  # 500ms
    1.0,  # 1s
    2.5,  # 2.5s
    5.0,  # 5s
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 60s
    120.0,  # 2min
)

prompt_version_latency_seconds = Histogram(
    "hsi_prompt_version_latency_seconds",
    "Latency of prompt versions in seconds",
    labelnames=["version"],
    buckets=PROMPT_VERSION_LATENCY_BUCKETS,
    registry=_registry,
)

# Risk score variance gauge between prompt versions
prompt_version_risk_score_variance = Gauge(
    "hsi_prompt_version_risk_score_variance",
    "Risk score variance between prompt versions",
    labelnames=["control_version", "treatment_version"],
    registry=_registry,
)

# A/B test traffic counter
PROMPT_AB_TRAFFIC_TOTAL = Counter(
    "hsi_prompt_ab_traffic_total",
    "Total requests routed through prompt A/B testing",
    labelnames=["version", "is_treatment"],
    registry=_registry,
)

# Shadow mode comparison counter
PROMPT_SHADOW_COMPARISONS_TOTAL = Counter(
    "hsi_prompt_shadow_comparisons_total",
    "Total shadow mode prompt comparisons",
    labelnames=["model"],
    registry=_registry,
)

# Rollback events counter
PROMPT_ROLLBACKS_TOTAL = Counter(
    "hsi_prompt_rollbacks_total",
    "Total prompt rollback events triggered by performance degradation",
    labelnames=["model", "reason"],
    registry=_registry,
)


def record_prompt_latency(version: str, latency_seconds: float) -> None:
    """Record latency for a specific prompt version.

    Args:
        version: Prompt version identifier (e.g., "v1", "v2")
        latency_seconds: Request latency in seconds
    """
    safe_version = sanitize_metric_label(version, max_length=32)
    prompt_version_latency_seconds.labels(version=safe_version).observe(latency_seconds)


def record_risk_score_variance(
    control_version: str,
    treatment_version: str,
    variance: float,
) -> None:
    """Record risk score variance between two prompt versions.

    Args:
        control_version: Control prompt version identifier
        treatment_version: Treatment prompt version identifier
        variance: Variance in risk scores between versions
    """
    safe_control = sanitize_metric_label(control_version, max_length=32)
    safe_treatment = sanitize_metric_label(treatment_version, max_length=32)
    prompt_version_risk_score_variance.labels(
        control_version=safe_control,
        treatment_version=safe_treatment,
    ).set(variance)


def record_prompt_ab_traffic(version: str, is_treatment: bool) -> None:
    """Record A/B test traffic routing decision.

    Args:
        version: Prompt version that received the request
        is_treatment: Whether this was the treatment (new) version
    """
    safe_version = sanitize_metric_label(version, max_length=32)
    PROMPT_AB_TRAFFIC_TOTAL.labels(
        version=safe_version,
        is_treatment=str(is_treatment).lower(),
    ).inc()


def record_shadow_comparison(model: str) -> None:
    """Record a shadow mode comparison execution.

    Args:
        model: Model name (e.g., "nemotron")
    """
    safe_model = sanitize_metric_label(model, max_length=32)
    PROMPT_SHADOW_COMPARISONS_TOTAL.labels(model=safe_model).inc()


def record_prompt_rollback(model: str, reason: str) -> None:
    """Record a prompt rollback event.

    Args:
        model: Model name (e.g., "nemotron")
        reason: Reason for rollback (e.g., "latency", "variance")
    """
    safe_model = sanitize_metric_label(model, max_length=32)
    safe_reason = sanitize_metric_label(reason, max_length=32)
    PROMPT_ROLLBACKS_TOTAL.labels(model=safe_model, reason=safe_reason).inc()


# =============================================================================
# Worker Supervisor Metrics Helpers (NEM-2457)
# =============================================================================

# Worker status value mapping for gauge metric
WORKER_STATUS_VALUES = {
    "stopped": 0,
    "running": 1,
    "crashed": 2,
    "restarting": 3,
    "failed": 4,
}


def record_worker_restart(worker_name: str) -> None:
    """Record a worker restart event.

    Args:
        worker_name: Name of the worker that was restarted.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    WORKER_RESTARTS_TOTAL.labels(worker_name=safe_name).inc()


def record_worker_crash(worker_name: str) -> None:
    """Record a worker crash event.

    Args:
        worker_name: Name of the worker that crashed.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    WORKER_CRASHES_TOTAL.labels(worker_name=safe_name).inc()


def record_worker_max_restarts_exceeded(worker_name: str) -> None:
    """Record when a worker exceeds max restart limit.

    Args:
        worker_name: Name of the worker that exceeded restart limit.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    WORKER_MAX_RESTARTS_EXCEEDED_TOTAL.labels(worker_name=safe_name).inc()


def set_worker_status(worker_name: str, status: str) -> None:
    """Set the current status of a worker.

    Args:
        worker_name: Name of the worker.
        status: Status string (stopped, running, crashed, restarting, failed).
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    status_value = WORKER_STATUS_VALUES.get(status.lower(), 0)
    WORKER_STATUS.labels(worker_name=safe_name).set(status_value)


# =============================================================================
# Pipeline Worker Metrics Helpers (NEM-2459)
# =============================================================================

# Allowlist of reason categories for worker restarts to prevent cardinality explosion
_RESTART_REASON_CATEGORIES = {
    "exception",
    "timeout",
    "memory",
    "connection",
    "resource",
    "dependency",
    "manual",
    "unknown",
}

# Worker state value mapping for pipeline worker state gauge
PIPELINE_WORKER_STATE_VALUES = {
    "stopped": 0,
    "running": 1,
    "restarting": 2,
    "failed": 3,
}


def _categorize_restart_reason(error: str | None) -> str:  # noqa: PLR0911
    """Categorize a restart reason into predefined categories.

    This function examines the error message and categorizes it into
    one of the predefined reason categories to prevent metric cardinality
    explosion while still providing useful insights.

    The multiple return statements are intentional for clear categorization
    logic and early exit patterns.

    Args:
        error: The error message or None if no error.

    Returns:
        A categorized reason string from _RESTART_REASON_CATEGORIES.
    """
    if error is None:
        return "manual"

    error_lower = error.lower()

    # Timeout-related errors
    if any(kw in error_lower for kw in ["timeout", "timed out", "deadline"]):
        return "timeout"

    # Memory-related errors
    if any(kw in error_lower for kw in ["memory", "oom", "out of memory", "memoryerror"]):
        return "memory"

    # Connection-related errors
    if any(
        kw in error_lower
        for kw in [
            "connection",
            "connect",
            "refused",
            "unreachable",
            "network",
            "socket",
            "dns",
        ]
    ):
        return "connection"

    # Resource-related errors
    if any(
        kw in error_lower
        for kw in [
            "resource",
            "file",
            "disk",
            "space",
            "permission",
            "access",
            "limit",
        ]
    ):
        return "resource"

    # Dependency-related errors
    if any(
        kw in error_lower
        for kw in ["dependency", "import", "module", "service", "unavailable", "not found"]
    ):
        return "dependency"

    # Generic exception or error
    if any(kw in error_lower for kw in ["exception", "error", "failed", "failure"]):
        return "exception"

    return "unknown"


def record_pipeline_worker_restart(
    worker_name: str, reason: str | None = None, duration_seconds: float | None = None
) -> None:
    """Record a pipeline worker restart event with categorized reason.

    Args:
        worker_name: Name of the worker that was restarted.
        reason: The error message or reason for restart (will be categorized).
        duration_seconds: Optional duration of the restart operation in seconds.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    reason_category = _categorize_restart_reason(reason)

    PIPELINE_WORKER_RESTARTS_TOTAL.labels(
        worker_name=safe_name, reason_category=reason_category
    ).inc()

    if duration_seconds is not None and duration_seconds > 0:
        PIPELINE_WORKER_RESTART_DURATION_SECONDS.labels(worker_name=safe_name).observe(
            duration_seconds
        )


def observe_pipeline_worker_restart_duration(worker_name: str, duration_seconds: float) -> None:
    """Record the duration of a pipeline worker restart operation.

    Args:
        worker_name: Name of the worker.
        duration_seconds: Duration of the restart operation in seconds.
    """
    if duration_seconds > 0:
        safe_name = sanitize_metric_label(worker_name, max_length=64)
        PIPELINE_WORKER_RESTART_DURATION_SECONDS.labels(worker_name=safe_name).observe(
            duration_seconds
        )


def set_pipeline_worker_state(worker_name: str, state: str) -> None:
    """Set the current state of a pipeline worker.

    Args:
        worker_name: Name of the worker.
        state: State string (stopped, running, restarting, failed).
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    state_value = PIPELINE_WORKER_STATE_VALUES.get(state.lower(), 0)
    PIPELINE_WORKER_STATE.labels(worker_name=safe_name).set(state_value)


def set_pipeline_worker_consecutive_failures(worker_name: str, count: int) -> None:
    """Set the number of consecutive failures for a pipeline worker.

    Args:
        worker_name: Name of the worker.
        count: Number of consecutive failures.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    PIPELINE_WORKER_CONSECUTIVE_FAILURES.labels(worker_name=safe_name).set(count)


def set_pipeline_worker_uptime(worker_name: str, uptime_seconds: float) -> None:
    """Set the uptime of a pipeline worker.

    Args:
        worker_name: Name of the worker.
        uptime_seconds: Uptime in seconds since last successful start.
            Use -1 to indicate the worker is not running.
    """
    safe_name = sanitize_metric_label(worker_name, max_length=64)
    PIPELINE_WORKER_UPTIME_SECONDS.labels(worker_name=safe_name).set(uptime_seconds)
