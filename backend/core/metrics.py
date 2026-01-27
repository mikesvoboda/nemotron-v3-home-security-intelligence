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

NEM-3795: Disabled _created suffix metrics to reduce metric cardinality by ~50%.
The _created suffix is a Unix timestamp added to counters, histograms, and summaries
indicating when the metric was first created. While useful for some use cases, it
doubles the number of time series and is typically not needed for our monitoring.
"""

from collections import deque
from datetime import UTC
from typing import TypedDict

import numpy as np

# NEM-3795: Disable _created suffix metrics BEFORE importing any metric types.
# This must be done before creating any Counter, Histogram, or Summary metrics.
# The _created suffix adds a timestamp metric for each counter/histogram/summary,
# which doubles the metric cardinality. Disabling this reduces Prometheus storage
# and query overhead by approximately 50%.
# See: https://github.com/prometheus/client_python/issues/672
from prometheus_client import disable_created_metrics

disable_created_metrics()

from prometheus_client import (  # noqa: E402
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from backend.core.logging import get_logger  # noqa: E402
from backend.core.sanitization import (  # noqa: E402
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
# Worker Pool Metrics
# =============================================================================

WORKER_ACTIVE_COUNT = Gauge(
    "hsi_worker_active_count",
    "Number of workers currently active (registered and capable of processing)",
    registry=_registry,
)

WORKER_BUSY_COUNT = Gauge(
    "hsi_worker_busy_count",
    "Number of workers currently busy processing tasks",
    registry=_registry,
)

WORKER_IDLE_COUNT = Gauge(
    "hsi_worker_idle_count",
    "Number of workers currently idle (active but not processing)",
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
    "Total number of detections processed by YOLO26",
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
    "Duration of AI service requests (YOLO26 or Nemotron)",
    labelnames=["service"],
    buckets=AI_REQUEST_DURATION_BUCKETS,
    registry=_registry,
)

# =============================================================================
# Workload-Specific AI Model Histograms (NEM-3381)
# =============================================================================
# Optimized histogram buckets for specific AI workloads to achieve under 5%
# percentile error. Each model has buckets tuned to its typical latency profile.

# YOLO26 buckets: Fast inference model (~20-100ms typical)
# Designed for object detection with GPU acceleration
# P50 ~30ms, P95 ~80ms, P99 ~150ms based on benchmarks
YOLO26_INFERENCE_BUCKETS = (
    0.01,  # 10ms - minimum expected latency
    0.02,  # 20ms - fast path
    0.03,  # 30ms - typical P50
    0.05,  # 50ms - normal range
    0.075,  # 75ms - approaching P95
    0.1,  # 100ms - typical P95
    0.15,  # 150ms - P99
    0.2,  # 200ms - outliers
    0.3,  # 300ms - degraded
    0.5,  # 500ms - timeout threshold
)

YOLO26_INFERENCE_DURATION = Histogram(
    "hsi_yolo26_inference_seconds",
    "YOLO26 object detection inference duration with workload-optimized buckets",
    buckets=YOLO26_INFERENCE_BUCKETS,
    registry=_registry,
)

# Nemotron buckets: LLM inference (~500ms-5s typical for analysis)
# Designed for text generation with context-dependent latency
# P50 ~1s, P95 ~3s, P99 ~5s based on benchmarks
NEMOTRON_INFERENCE_BUCKETS = (
    0.1,  # 100ms - short cached responses
    0.25,  # 250ms - minimal generation
    0.5,  # 500ms - fast completions
    1.0,  # 1s - typical P50
    1.5,  # 1.5s - normal range
    2.0,  # 2s - longer analysis
    3.0,  # 3s - typical P95
    5.0,  # 5s - P99
    10.0,  # 10s - extended analysis
    30.0,  # 30s - complex multi-turn
)

NEMOTRON_INFERENCE_DURATION = Histogram(
    "hsi_nemotron_inference_seconds",
    "Nemotron LLM inference duration with workload-optimized buckets",
    buckets=NEMOTRON_INFERENCE_BUCKETS,
    registry=_registry,
)

# Florence buckets: Vision-language model (~100ms-2s typical)
# Designed for captioning, OCR, and detection tasks
# P50 ~300ms, P95 ~1s, P99 ~2s based on benchmarks
FLORENCE_INFERENCE_BUCKETS = (
    0.05,  # 50ms - cached/preprocessed
    0.1,  # 100ms - fast tasks
    0.2,  # 200ms - quick captions
    0.3,  # 300ms - typical P50
    0.5,  # 500ms - normal OCR
    0.75,  # 750ms - detailed captions
    1.0,  # 1s - typical P95
    1.5,  # 1.5s - complex tasks
    2.0,  # 2s - P99
    3.0,  # 3s - outliers
)

FLORENCE_INFERENCE_DURATION = Histogram(
    "hsi_florence_inference_seconds",
    "Florence vision-language inference duration with workload-optimized buckets",
    buckets=FLORENCE_INFERENCE_BUCKETS,
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
# LLM Context Utilization Metrics (NEM-1666, NEM-3288)
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

# NEM-3288: Gauge for current LLM context utilization ratio (used by Grafana dashboard)
# This gauge tracks the most recent context utilization value per model
LLM_CONTEXT_UTILIZATION_RATIO = Gauge(
    "hsi_llm_context_utilization_ratio",
    "LLM context window utilization ratio (0-1)",
    labelnames=["model"],  # e.g., nemotron-mini
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

# Histogram for enrichment model duration (Grafana dashboard compatibility)
ENRICHMENT_MODEL_DURATION = Histogram(
    "hsi_enrichment_model_duration_seconds",
    "Duration of enrichment model inference by model name",
    labelnames=["model"],
    buckets=AI_REQUEST_DURATION_BUCKETS,
    registry=_registry,
)

# Counter for enrichment model errors (Grafana dashboard compatibility)
# This is an alias-style metric that mirrors hsi_enrichment_failures_total
# but uses the naming convention expected by the Grafana dashboard
ENRICHMENT_MODEL_ERRORS_TOTAL = Counter(
    "hsi_enrichment_model_errors_total",
    "Total number of enrichment model errors by model name",
    labelnames=["model"],
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

# NEM-3288: Events acknowledged counter with labels for dashboard filtering
# Tracks security events acknowledged by users with camera and risk level labels
EVENTS_ACKNOWLEDGED_TOTAL = Counter(
    "hsi_events_acknowledged_total",
    "Total security events acknowledged by users",
    labelnames=["camera_name", "risk_level"],  # risk_level: low, medium, high, critical
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

# SWR (Stale-While-Revalidate) Metrics (NEM-3367)
CACHE_STALE_HITS_TOTAL = Counter(
    "hsi_cache_stale_hits_total",
    "Total number of stale cache hits (returned while revalidating in background)",
    labelnames=["cache_type"],
    registry=_registry,
)

CACHE_BACKGROUND_REFRESH_TOTAL = Counter(
    "hsi_cache_background_refresh_total",
    "Total number of background cache refresh operations",
    labelnames=["cache_type", "status"],
    registry=_registry,
)

# Connection Pool Metrics (NEM-3368)
REDIS_POOL_SIZE = Gauge(
    "hsi_redis_pool_size",
    "Current size of the Redis connection pool",
    labelnames=["pool_type"],
    registry=_registry,
)

REDIS_POOL_AVAILABLE = Gauge(
    "hsi_redis_pool_available",
    "Number of available connections in the Redis pool",
    labelnames=["pool_type"],
    registry=_registry,
)

REDIS_POOL_IN_USE = Gauge(
    "hsi_redis_pool_in_use",
    "Number of connections currently in use",
    labelnames=["pool_type"],
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

# Cost efficiency metrics (average cost per unit)
COST_PER_DETECTION_USD = Gauge(
    "hsi_cost_per_detection_usd",
    "Average cost per detection (image processed) in USD",
    registry=_registry,
)

COST_PER_EVENT_USD = Gauge(
    "hsi_cost_per_event_usd",
    "Average cost per security event in USD",
    registry=_registry,
)

# =============================================================================
# Video Analytics Metrics (NEM-3722)
# =============================================================================
# Comprehensive metrics for video analytics features including tracking,
# zone monitoring, loitering detection, action recognition, and face recognition.

# -----------------------------------------------------------------------------
# Tracking Metrics
# -----------------------------------------------------------------------------

TRACKS_CREATED_TOTAL = Counter(
    "hsi_tracks_created_total",
    "Total number of object tracks created",
    labelnames=["camera_id"],
    registry=_registry,
)

TRACKS_LOST_TOTAL = Counter(
    "hsi_tracks_lost_total",
    "Total number of object tracks lost",
    labelnames=["camera_id", "reason"],  # reason: timeout, out_of_frame, occlusion
    registry=_registry,
)

TRACKS_REIDENTIFIED_TOTAL = Counter(
    "hsi_tracks_reidentified_total",
    "Total number of tracks reidentified after being lost",
    labelnames=["camera_id"],
    registry=_registry,
)

# Buckets for track duration (in seconds)
# Covers short tracks (1s) to long tracks (30min+)
TRACK_DURATION_BUCKETS = (
    1.0,  # 1s
    5.0,  # 5s
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 1 min
    120.0,  # 2 min
    300.0,  # 5 min
    600.0,  # 10 min
    1800.0,  # 30 min
)

TRACK_DURATION_SECONDS = Histogram(
    "hsi_track_duration_seconds",
    "Duration of object tracks from creation to loss",
    labelnames=["camera_id", "entity_type"],  # entity_type: person, vehicle, etc.
    buckets=TRACK_DURATION_BUCKETS,
    registry=_registry,
)

TRACK_ACTIVE_COUNT = Gauge(
    "hsi_track_active_count",
    "Current number of active object tracks",
    labelnames=["camera_id"],
    registry=_registry,
)

# -----------------------------------------------------------------------------
# Zone Metrics
# -----------------------------------------------------------------------------

ZONE_CROSSINGS_TOTAL = Counter(
    "hsi_zone_crossings_total",
    "Total number of zone boundary crossings",
    labelnames=["zone_id", "direction", "entity_type"],  # direction: enter, exit
    registry=_registry,
)

ZONE_INTRUSIONS_TOTAL = Counter(
    "hsi_zone_intrusions_total",
    "Total number of zone intrusion alerts",
    labelnames=["zone_id", "severity"],  # severity: low, medium, high
    registry=_registry,
)

ZONE_OCCUPANCY = Gauge(
    "hsi_zone_occupancy",
    "Current number of entities in a zone",
    labelnames=["zone_id"],
    registry=_registry,
)

# Buckets for zone dwell time (in seconds)
# Covers brief visits (10s) to extended stays (1hr+)
ZONE_DWELL_TIME_BUCKETS = (
    10.0,  # 10s
    30.0,  # 30s
    60.0,  # 1 min
    120.0,  # 2 min
    300.0,  # 5 min
    600.0,  # 10 min
    1800.0,  # 30 min
    3600.0,  # 1 hr
)

ZONE_DWELL_TIME_SECONDS = Histogram(
    "hsi_zone_dwell_time_seconds",
    "Time spent by entities within a zone",
    labelnames=["zone_id"],
    buckets=ZONE_DWELL_TIME_BUCKETS,
    registry=_registry,
)

# -----------------------------------------------------------------------------
# Loitering Metrics
# -----------------------------------------------------------------------------

LOITERING_ALERTS_TOTAL = Counter(
    "hsi_loitering_alerts_total",
    "Total number of loitering alerts generated",
    labelnames=["camera_id", "zone_id"],
    registry=_registry,
)

# Buckets for loitering dwell time (in seconds)
# Loitering typically starts at 30s-60s and can extend to 30min+
LOITERING_DURATION_BUCKETS = (
    30.0,  # 30s - threshold for initial detection
    60.0,  # 1 min
    120.0,  # 2 min
    180.0,  # 3 min
    300.0,  # 5 min
    600.0,  # 10 min
    900.0,  # 15 min
    1800.0,  # 30 min
)

LOITERING_DWELL_TIME_SECONDS = Histogram(
    "hsi_loitering_dwell_time_seconds",
    "Dwell time for loitering detections",
    labelnames=["camera_id"],
    buckets=LOITERING_DURATION_BUCKETS,
    registry=_registry,
)

# -----------------------------------------------------------------------------
# Action Recognition Metrics
# -----------------------------------------------------------------------------

ACTION_RECOGNITION_TOTAL = Counter(
    "hsi_action_recognition_total",
    "Total number of actions recognized by type",
    labelnames=["action_type", "camera_id"],  # action_type: walking, loitering, fighting, etc.
    registry=_registry,
)

# Buckets for action recognition confidence scores (0.0 to 1.0)
ACTION_RECOGNITION_CONFIDENCE_BUCKETS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)

ACTION_RECOGNITION_CONFIDENCE = Histogram(
    "hsi_action_recognition_confidence",
    "Confidence scores for action recognition",
    labelnames=["action_type"],
    buckets=ACTION_RECOGNITION_CONFIDENCE_BUCKETS,
    registry=_registry,
)

# Buckets for action recognition inference duration (in seconds)
ACTION_RECOGNITION_DURATION_BUCKETS = (
    0.05,  # 50ms
    0.1,  # 100ms
    0.2,  # 200ms
    0.5,  # 500ms
    1.0,  # 1s
    2.0,  # 2s
    5.0,  # 5s (for complex multi-frame analysis)
)

ACTION_RECOGNITION_DURATION_SECONDS = Histogram(
    "hsi_action_recognition_duration_seconds",
    "Duration of action recognition inference",
    buckets=ACTION_RECOGNITION_DURATION_BUCKETS,
    registry=_registry,
)

# -----------------------------------------------------------------------------
# Face Recognition Metrics
# -----------------------------------------------------------------------------

FACE_DETECTIONS_TOTAL = Counter(
    "hsi_face_detections_total",
    "Total number of faces detected",
    labelnames=["camera_id", "match_status"],  # match_status: known, unknown
    registry=_registry,
)

# Buckets for face quality scores (0.0 to 1.0)
FACE_QUALITY_BUCKETS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)

FACE_QUALITY_SCORE = Histogram(
    "hsi_face_quality_score",
    "Quality scores for detected faces (higher is better)",
    buckets=FACE_QUALITY_BUCKETS,
    registry=_registry,
)

FACE_EMBEDDINGS_GENERATED_TOTAL = Counter(
    "hsi_face_embeddings_generated_total",
    "Total number of face embeddings generated",
    registry=_registry,
)

FACE_MATCHES_TOTAL = Counter(
    "hsi_face_matches_total",
    "Total number of face matches against known persons",
    labelnames=["person_id"],
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
            service: Name of the service ("yolo26" or "nemotron")
            duration_seconds: Duration in seconds
        """
        AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds)

    # -------------------------------------------------------------------------
    # Workload-Specific AI Model Duration Methods (NEM-3381)
    # -------------------------------------------------------------------------

    def observe_yolo26_inference(self, duration_seconds: float) -> None:
        """Record YOLO26 object detection inference duration.

        Uses workload-optimized histogram buckets designed for fast inference
        models with typical latencies of 20-100ms. Achieves under 5% percentile
        error for accurate P50/P95/P99 reporting.

        Args:
            duration_seconds: Inference duration in seconds
        """
        YOLO26_INFERENCE_DURATION.observe(duration_seconds)

    def observe_nemotron_inference(self, duration_seconds: float) -> None:
        """Record Nemotron LLM inference duration.

        Uses workload-optimized histogram buckets designed for LLM inference
        with typical latencies of 500ms-5s. Achieves under 5% percentile
        error for accurate P50/P95/P99 reporting.

        Args:
            duration_seconds: Inference duration in seconds
        """
        NEMOTRON_INFERENCE_DURATION.observe(duration_seconds)

    def observe_florence_inference(self, duration_seconds: float) -> None:
        """Record Florence vision-language model inference duration.

        Uses workload-optimized histogram buckets designed for vision-language
        tasks with typical latencies of 100ms-2s. Achieves under 5% percentile
        error for accurate P50/P95/P99 reporting.

        Args:
            duration_seconds: Inference duration in seconds
        """
        FLORENCE_INFERENCE_DURATION.observe(duration_seconds)

    # -------------------------------------------------------------------------
    # Exemplar Support Methods (NEM-3379)
    # -------------------------------------------------------------------------

    def observe_yolo26_with_exemplar(self, duration_seconds: float) -> None:
        """Record YOLO26 inference duration with trace context exemplar.

        Combines workload-optimized histogram buckets with exemplar support for
        complete observability. Use this method when tracing is enabled and
        you need to correlate slow inferences with their distributed traces.

        Args:
            duration_seconds: Inference duration in seconds
        """
        observe_with_exemplar(YOLO26_INFERENCE_DURATION, duration_seconds)

    def observe_nemotron_with_exemplar(self, duration_seconds: float) -> None:
        """Record Nemotron LLM inference duration with trace context exemplar.

        Combines workload-optimized histogram buckets with exemplar support for
        complete observability. Use this method when tracing is enabled and
        you need to correlate slow LLM inferences with their distributed traces.

        Args:
            duration_seconds: Inference duration in seconds
        """
        observe_with_exemplar(NEMOTRON_INFERENCE_DURATION, duration_seconds)

    def observe_florence_with_exemplar(self, duration_seconds: float) -> None:
        """Record Florence inference duration with trace context exemplar.

        Combines workload-optimized histogram buckets with exemplar support for
        complete observability. Use this method when tracing is enabled and
        you need to correlate slow vision-language inferences with their traces.

        Args:
            duration_seconds: Inference duration in seconds
        """
        observe_with_exemplar(FLORENCE_INFERENCE_DURATION, duration_seconds)

    def observe_ai_request_with_exemplar(self, service: str, duration_seconds: float) -> None:
        """Record AI service request duration with trace context exemplar.

        Records to the general AI_REQUEST_DURATION histogram with an exemplar
        containing the current trace ID for correlation with distributed traces.

        Args:
            service: Name of the service ("yolo26", "nemotron", "florence", etc.)
            duration_seconds: Duration in seconds
        """
        exemplar = _get_trace_exemplar()
        AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds, exemplar=exemplar)

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

    def observe_enrichment_model_duration(self, model: str, duration_seconds: float) -> None:
        """Record the duration of an enrichment model inference.

        Args:
            model: Name of the enrichment model (brisque, violence, clothing,
                vehicle, pet, depth, pose, action, weather, fashion-clip, etc.)
            duration_seconds: Duration of the model inference in seconds
        """
        ENRICHMENT_MODEL_DURATION.labels(model=model).observe(duration_seconds)

    def record_enrichment_model_error(self, model: str) -> None:
        """Increment the error counter for an enrichment model.

        This metric is used by Grafana dashboards and complements
        hsi_enrichment_failures_total with a different naming convention.

        Args:
            model: Name of the enrichment model that errored
        """
        ENRICHMENT_MODEL_ERRORS_TOTAL.labels(model=model).inc()

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

    def record_event_acknowledged(self, camera_name: str, risk_level: str) -> None:
        """Record an event acknowledgement with camera and risk level labels (NEM-3288).

        This metric tracks security events that have been acknowledged/reviewed by users,
        providing visibility into operator engagement and response patterns.

        Args:
            camera_name: Human-readable camera name where the event occurred
            risk_level: Risk level of the acknowledged event (low, medium, high, critical)

        Note:
            Camera names and risk levels are sanitized to prevent cardinality explosion.
        """
        safe_camera_name = sanitize_metric_label(camera_name, max_length=64)
        safe_risk_level = sanitize_risk_level(risk_level)
        EVENTS_ACKNOWLEDGED_TOTAL.labels(
            camera_name=safe_camera_name, risk_level=safe_risk_level
        ).inc()

    def set_llm_context_utilization_ratio(self, model: str, utilization: float) -> None:
        """Set the LLM context utilization ratio gauge (NEM-3288).

        This gauge tracks the most recent context window utilization ratio for the LLM,
        used by Grafana dashboards to monitor AI container health.

        Args:
            model: Name of the LLM model (e.g., "nemotron-mini")
            utilization: Context utilization ratio (0.0 to 1.0+)
                Values > 1.0 indicate the prompt exceeded the context window

        Note:
            Model names are sanitized to prevent cardinality explosion.
        """
        safe_model = sanitize_metric_label(model, max_length=32)
        LLM_CONTEXT_UTILIZATION_RATIO.labels(model=safe_model).set(utilization)

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
            model: Model identifier (e.g., 'nemotron', 'yolo26', 'florence')
            duration_seconds: Duration of inference in seconds
        """
        if duration_seconds > 0:
            GPU_SECONDS_TOTAL.labels(model=model).inc(duration_seconds)

    def record_estimated_cost(self, service: str, cost_usd: float) -> None:
        """Record estimated cost based on cloud equivalents.

        Args:
            service: Service identifier (e.g., 'nemotron', 'yolo26', 'enrichment')
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

    def set_cost_per_detection(self, cost_usd: float) -> None:
        """Set the average cost per detection gauge.

        Args:
            cost_usd: Average cost per detection (image processed) in USD
        """
        COST_PER_DETECTION_USD.set(cost_usd)

    def set_cost_per_event(self, cost_usd: float) -> None:
        """Set the average cost per event gauge.

        Args:
            cost_usd: Average cost per security event in USD
        """
        COST_PER_EVENT_USD.set(cost_usd)

    # -------------------------------------------------------------------------
    # Worker Pool Metrics
    # -------------------------------------------------------------------------

    def set_worker_active_count(self, count: int) -> None:
        """Set the number of active workers.

        Active workers are those that are registered and capable of processing
        tasks. This includes both busy and idle workers.

        Args:
            count: Number of active workers
        """
        WORKER_ACTIVE_COUNT.set(count)

    def set_worker_busy_count(self, count: int) -> None:
        """Set the number of busy workers.

        Busy workers are those currently processing tasks.

        Args:
            count: Number of busy workers
        """
        WORKER_BUSY_COUNT.set(count)

    def set_worker_idle_count(self, count: int) -> None:
        """Set the number of idle workers.

        Idle workers are active but not currently processing tasks.

        Args:
            count: Number of idle workers
        """
        WORKER_IDLE_COUNT.set(count)

    def update_worker_pool_metrics(self, active: int, busy: int, idle: int | None = None) -> None:
        """Update all worker pool metrics at once.

        This is a convenience method for updating all worker pool metrics
        in a single call. If idle is not provided, it is calculated as
        active - busy.

        Args:
            active: Number of active workers
            busy: Number of busy workers
            idle: Number of idle workers (optional, calculated if not provided)
        """
        self.set_worker_active_count(active)
        self.set_worker_busy_count(busy)
        if idle is None:
            idle = max(0, active - busy)
        self.set_worker_idle_count(idle)


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
        service: Name of the service ("yolo26" or "nemotron")
        duration_seconds: Duration in seconds
    """
    AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds)


# =============================================================================
# Workload-Specific AI Model Duration Helpers (NEM-3381)
# =============================================================================


def observe_yolo26_inference(duration_seconds: float) -> None:
    """Record YOLO26 object detection inference duration.

    Uses workload-optimized histogram buckets designed for fast inference
    models with typical latencies of 20-100ms. Achieves under 5% percentile
    error for accurate P50/P95/P99 reporting.

    Args:
        duration_seconds: Inference duration in seconds
    """
    YOLO26_INFERENCE_DURATION.observe(duration_seconds)


def observe_nemotron_inference(duration_seconds: float) -> None:
    """Record Nemotron LLM inference duration.

    Uses workload-optimized histogram buckets designed for LLM inference
    with typical latencies of 500ms-5s. Achieves under 5% percentile
    error for accurate P50/P95/P99 reporting.

    Args:
        duration_seconds: Inference duration in seconds
    """
    NEMOTRON_INFERENCE_DURATION.observe(duration_seconds)


def observe_florence_inference(duration_seconds: float) -> None:
    """Record Florence vision-language model inference duration.

    Uses workload-optimized histogram buckets designed for vision-language
    tasks with typical latencies of 100ms-2s. Achieves under 5% percentile
    error for accurate P50/P95/P99 reporting.

    Args:
        duration_seconds: Inference duration in seconds
    """
    FLORENCE_INFERENCE_DURATION.observe(duration_seconds)


# =============================================================================
# Exemplar Support for Trace-Metric Correlation (NEM-3379)
# =============================================================================


def _get_trace_exemplar() -> dict[str, str] | None:
    """Get current trace context as exemplar labels for histogram observations.

    This function retrieves the current OpenTelemetry trace ID and formats it
    as an exemplar dictionary that can be attached to Prometheus histogram
    observations. This enables direct correlation between metrics and traces
    for faster root cause analysis.

    Returns:
        Dictionary with trace_id key if a valid trace is active, None otherwise.
        Example: {"trace_id": "abcd1234ef567890abcd1234ef567890"}

    Note:
        Returns None if OpenTelemetry is not enabled or no trace is active.
        This is a lightweight operation suitable for hot paths.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            span_context = span.get_span_context()
            if span_context and span_context.is_valid:
                return {"trace_id": format(span_context.trace_id, "032x")}
    except ImportError:
        # OpenTelemetry not installed - expected in some deployments
        pass
    except Exception:  # noqa: S110 - Intentionally broad catch for observability hot path
        # Any other error, return None silently to avoid metric overhead.
        # Logging here would be too noisy for a hot path called on every metric observation.
        pass
    return None


def observe_with_exemplar(histogram: Histogram, value: float) -> None:
    """Record a histogram observation with trace context exemplar.

    This function records a value to the specified histogram and, if a trace
    is active, attaches the trace ID as an exemplar. Exemplars enable direct
    correlation between metric observations and distributed traces, allowing
    operators to jump directly from a slow metric observation to the
    corresponding trace for root cause analysis.

    Args:
        histogram: The Prometheus Histogram to observe
        value: The value to record

    Example:
        >>> from backend.core.metrics import observe_with_exemplar, YOLO26_INFERENCE_DURATION
        >>> observe_with_exemplar(YOLO26_INFERENCE_DURATION, inference_time)
    """
    exemplar = _get_trace_exemplar()
    histogram.observe(value, exemplar=exemplar)


def observe_yolo26_with_exemplar(duration_seconds: float) -> None:
    """Record YOLO26 inference duration with trace context exemplar.

    Combines workload-optimized histogram buckets with exemplar support for
    complete observability. Use this function when tracing is enabled and
    you need to correlate slow inferences with their distributed traces.

    Args:
        duration_seconds: Inference duration in seconds
    """
    observe_with_exemplar(YOLO26_INFERENCE_DURATION, duration_seconds)


def observe_nemotron_with_exemplar(duration_seconds: float) -> None:
    """Record Nemotron LLM inference duration with trace context exemplar.

    Combines workload-optimized histogram buckets with exemplar support for
    complete observability. Use this function when tracing is enabled and
    you need to correlate slow LLM inferences with their distributed traces.

    Args:
        duration_seconds: Inference duration in seconds
    """
    observe_with_exemplar(NEMOTRON_INFERENCE_DURATION, duration_seconds)


def observe_florence_with_exemplar(duration_seconds: float) -> None:
    """Record Florence inference duration with trace context exemplar.

    Combines workload-optimized histogram buckets with exemplar support for
    complete observability. Use this function when tracing is enabled and
    you need to correlate slow vision-language inferences with their traces.

    Args:
        duration_seconds: Inference duration in seconds
    """
    observe_with_exemplar(FLORENCE_INFERENCE_DURATION, duration_seconds)


def observe_ai_request_with_exemplar(service: str, duration_seconds: float) -> None:
    """Record AI service request duration with trace context exemplar.

    Records to the general AI_REQUEST_DURATION histogram with an exemplar
    containing the current trace ID for correlation with distributed traces.

    Args:
        service: Name of the service ("yolo26", "nemotron", "florence", etc.)
        duration_seconds: Duration in seconds
    """
    exemplar = _get_trace_exemplar()
    AI_REQUEST_DURATION.labels(service=service).observe(duration_seconds, exemplar=exemplar)


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


def observe_enrichment_model_duration(model: str, duration_seconds: float) -> None:
    """Record the duration of an enrichment model inference.

    Args:
        model: Name of the enrichment model (brisque, violence, clothing,
            vehicle, pet, depth, pose, action, weather, fashion-clip, etc.)
        duration_seconds: Duration of the model inference in seconds
    """
    ENRICHMENT_MODEL_DURATION.labels(model=model).observe(duration_seconds)


def record_enrichment_model_error(model: str) -> None:
    """Increment the error counter for an enrichment model.

    This metric is used by Grafana dashboards and complements
    hsi_enrichment_failures_total with a different naming convention.

    Args:
        model: Name of the enrichment model that errored
    """
    ENRICHMENT_MODEL_ERRORS_TOTAL.labels(model=model).inc()


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


def record_event_acknowledged(camera_name: str, risk_level: str) -> None:
    """Record an event acknowledgement with camera and risk level labels (NEM-3288).

    This metric tracks security events that have been acknowledged/reviewed by users,
    providing visibility into operator engagement and response patterns.

    Args:
        camera_name: Human-readable camera name where the event occurred
        risk_level: Risk level of the acknowledged event (low, medium, high, critical)

    Note:
        Camera names and risk levels are sanitized to prevent cardinality explosion.
    """
    safe_camera_name = sanitize_metric_label(camera_name, max_length=64)
    safe_risk_level = sanitize_risk_level(risk_level)
    EVENTS_ACKNOWLEDGED_TOTAL.labels(camera_name=safe_camera_name, risk_level=safe_risk_level).inc()


def set_llm_context_utilization_ratio(model: str, utilization: float) -> None:
    """Set the LLM context utilization ratio gauge (NEM-3288).

    This gauge tracks the most recent context window utilization ratio for the LLM,
    used by Grafana dashboards to monitor AI container health.

    Args:
        model: Name of the LLM model (e.g., "nemotron-mini")
        utilization: Context utilization ratio (0.0 to 1.0+)
            Values > 1.0 indicate the prompt exceeded the context window

    Note:
        Model names are sanitized to prevent cardinality explosion.
    """
    safe_model = sanitize_metric_label(model, max_length=32)
    LLM_CONTEXT_UTILIZATION_RATIO.labels(model=safe_model).set(utilization)


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


def record_cache_stale_hit(cache_type: str) -> None:
    """Record a stale cache hit (SWR pattern - NEM-3367).

    A stale hit occurs when cached data is served while being refreshed in the background.
    This is part of the Stale-While-Revalidate pattern for zero-latency cache updates.

    Args:
        cache_type: Type of cache (e.g., "dashboard_stats", "event_stats")
    """
    CACHE_STALE_HITS_TOTAL.labels(cache_type=cache_type).inc()


def record_cache_background_refresh(cache_type: str, success: bool = True) -> None:
    """Record a background cache refresh (SWR pattern - NEM-3367).

    Background refreshes occur when stale data is served while fresh data is fetched.
    This metric tracks the success/failure rate of these background operations.

    Args:
        cache_type: Type of cache being refreshed
        success: Whether the refresh succeeded
    """
    status = "success" if success else "skipped"
    CACHE_BACKGROUND_REFRESH_TOTAL.labels(cache_type=cache_type, status=status).inc()


def set_redis_pool_metrics(pool_type: str, size: int, available: int, in_use: int) -> None:
    """Update Redis pool metrics (NEM-3368).

    Args:
        pool_type: Type of pool ("cache", "queue", "pubsub", "ratelimit")
        size: Total pool size
        available: Number of available connections
        in_use: Number of connections in use
    """
    REDIS_POOL_SIZE.labels(pool_type=pool_type).set(size)
    REDIS_POOL_AVAILABLE.labels(pool_type=pool_type).set(available)
    REDIS_POOL_IN_USE.labels(pool_type=pool_type).set(in_use)


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
    - watch_to_detect: Time from file detection to YOLO26 processing
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
        model: Model identifier (e.g., 'yolo26', 'nemotron')
        duration_seconds: Warmup duration in seconds
    """
    MODEL_WARMUP_DURATION.labels(model=model).observe(duration_seconds)


def record_model_cold_start(model: str) -> None:
    """Increment cold start counter for an AI model.

    Args:
        model: Model identifier (e.g., 'yolo26', 'nemotron')
    """
    MODEL_COLD_START_TOTAL.labels(model=model).inc()


def set_model_warmth_state(model: str, state: str) -> None:
    """Set the current warmth state gauge for an AI model.

    Args:
        model: Model identifier (e.g., 'yolo26', 'nemotron')
        state: Warmth state ('cold', 'warming', 'warm')
    """
    state_value = {"cold": 0, "warming": 1, "warm": 2}.get(state, 0)
    MODEL_WARMTH_STATE.labels(model=model).set(state_value)


def set_model_last_inference_ago(model: str, seconds_ago: float | None) -> None:
    """Set the seconds since last inference gauge for an AI model.

    Args:
        model: Model identifier (e.g., 'yolo26', 'nemotron')
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

# Page Load Time histogram - measures in seconds
# Uses Navigation Timing API's loadEventEnd - navigationStart
# Good: < 3s, Needs Improvement: 3-6s, Poor: > 6s
RUM_PAGE_LOAD_BUCKETS = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0)

RUM_PAGE_LOAD_TIME_SECONDS = Histogram(
    "hsi_rum_page_load_time_seconds",
    "Page Load Time - measures full page load duration (seconds)",
    labelnames=["path", "rating"],
    buckets=RUM_PAGE_LOAD_BUCKETS,
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


def observe_rum_page_load_time(value_ms: float, path: str = "/", rating: str = "unknown") -> None:
    """Record Page Load Time metric.

    This metric represents the full page load duration from Navigation Timing API
    (loadEventEnd - navigationStart).

    Args:
        value_ms: Page load time in milliseconds
        path: Page path where metric was measured
        rating: Performance rating (good, needs-improvement, poor)
    """
    safe_path = sanitize_metric_label(path, max_length=64)
    safe_rating = sanitize_metric_label(rating, max_length=20)
    RUM_PAGE_LOAD_TIME_SECONDS.labels(path=safe_path, rating=safe_rating).observe(value_ms / 1000.0)
    RUM_METRICS_TOTAL.labels(metric_name="PAGE_LOAD_TIME", rating=safe_rating).inc()


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

# =============================================================================
# Shadow Mode Risk Distribution Comparison Metrics (NEM-3337)
# =============================================================================

# Risk score histogram for shadow mode comparison (control vs treatment)
# Uses same buckets as RISK_SCORE for consistency
SHADOW_RISK_SCORE_DISTRIBUTION = Histogram(
    "hsi_shadow_risk_score_distribution",
    "Risk score distribution from shadow mode prompt comparison",
    labelnames=["prompt_version"],  # "control" or "treatment"
    buckets=RISK_SCORE_BUCKETS,
    registry=_registry,
)

# Risk score difference histogram for shadow mode
# Tracks the absolute difference between control and treatment scores
SHADOW_RISK_SCORE_DIFF_BUCKETS = (0, 5, 10, 15, 20, 25, 30, 40, 50, 75, 100)

SHADOW_RISK_SCORE_DIFF = Histogram(
    "hsi_shadow_risk_score_diff",
    "Absolute difference in risk scores between control and treatment prompts",
    buckets=SHADOW_RISK_SCORE_DIFF_BUCKETS,
    registry=_registry,
)

# Gauge for average risk score per prompt version in shadow mode
SHADOW_AVG_RISK_SCORE = Gauge(
    "hsi_shadow_avg_risk_score",
    "Rolling average risk score for shadow mode prompts",
    labelnames=["prompt_version"],  # "control" or "treatment"
    registry=_registry,
)

# Counter for shadow mode comparisons by risk level change direction
SHADOW_RISK_LEVEL_SHIFT_TOTAL = Counter(
    "hsi_shadow_risk_level_shift_total",
    "Count of risk level shifts in shadow mode (treatment vs control)",
    labelnames=["direction"],  # "lower", "same", "higher"
    registry=_registry,
)

# Histogram for shadow mode latency comparison
SHADOW_LATENCY_DIFF_BUCKETS = (
    -1.0,  # Treatment faster by >1s
    -0.5,  # Treatment faster by 500ms
    -0.1,  # Treatment faster by 100ms
    0.0,  # Same
    0.1,  # Treatment slower by 100ms
    0.5,  # Treatment slower by 500ms
    1.0,  # Treatment slower by 1s
    2.0,  # Treatment slower by 2s
    5.0,  # Treatment slower by 5s
)

SHADOW_LATENCY_DIFF = Histogram(
    "hsi_shadow_latency_diff_seconds",
    "Latency difference (treatment - control) in shadow mode comparisons",
    buckets=SHADOW_LATENCY_DIFF_BUCKETS,
    registry=_registry,
)

# Counter for shadow mode latency warnings
SHADOW_LATENCY_WARNING_TOTAL = Counter(
    "hsi_shadow_latency_warning_total",
    "Total shadow mode latency warnings when treatment exceeds threshold",
    labelnames=["model"],
    registry=_registry,
)

# Counter for shadow mode comparison errors
SHADOW_COMPARISON_ERRORS_TOTAL = Counter(
    "hsi_shadow_comparison_errors_total",
    "Total shadow mode comparison errors by error type",
    labelnames=["error_type"],  # "control_failed", "treatment_failed", "both_failed"
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


def record_shadow_risk_score(prompt_version: str, risk_score: int) -> None:
    """Record a risk score for shadow mode distribution tracking.

    Args:
        prompt_version: Prompt version ("control" or "treatment")
        risk_score: Risk score from analysis (0-100)
    """
    safe_version = sanitize_metric_label(prompt_version, max_length=16)
    SHADOW_RISK_SCORE_DISTRIBUTION.labels(prompt_version=safe_version).observe(risk_score)


def record_shadow_risk_score_diff(diff: int) -> None:
    """Record the absolute risk score difference in shadow mode.

    Args:
        diff: Absolute difference between control and treatment risk scores
    """
    SHADOW_RISK_SCORE_DIFF.observe(abs(diff))


def update_shadow_avg_risk_score(prompt_version: str, avg_score: float) -> None:
    """Update the rolling average risk score for a prompt version.

    Args:
        prompt_version: Prompt version ("control" or "treatment")
        avg_score: Rolling average risk score
    """
    safe_version = sanitize_metric_label(prompt_version, max_length=16)
    SHADOW_AVG_RISK_SCORE.labels(prompt_version=safe_version).set(avg_score)


def record_shadow_risk_level_shift(direction: str) -> None:
    """Record a risk level shift in shadow mode comparison.

    Args:
        direction: Shift direction ("lower", "same", "higher")
            - "lower": treatment produced lower risk than control
            - "same": treatment produced same risk level as control
            - "higher": treatment produced higher risk than control
    """
    safe_direction = sanitize_metric_label(direction, max_length=16)
    SHADOW_RISK_LEVEL_SHIFT_TOTAL.labels(direction=safe_direction).inc()


def record_shadow_latency_diff(diff_seconds: float) -> None:
    """Record the latency difference in shadow mode (treatment - control).

    Args:
        diff_seconds: Latency difference in seconds (positive = treatment slower)
    """
    SHADOW_LATENCY_DIFF.observe(diff_seconds)


def record_shadow_latency_warning(model: str) -> None:
    """Record a shadow mode latency warning event.

    Args:
        model: Model name (e.g., "nemotron")
    """
    safe_model = sanitize_metric_label(model, max_length=32)
    SHADOW_LATENCY_WARNING_TOTAL.labels(model=safe_model).inc()


def record_shadow_comparison_error(error_type: str) -> None:
    """Record a shadow mode comparison error.

    Args:
        error_type: Type of error ("control_failed", "treatment_failed", "both_failed")
    """
    safe_type = sanitize_metric_label(error_type, max_length=32)
    SHADOW_COMPARISON_ERRORS_TOTAL.labels(error_type=safe_type).inc()


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
# A/B Rollout Experiment Metrics (NEM-3338)
# =============================================================================

# Counter for A/B rollout analysis by group
AB_ROLLOUT_ANALYSIS_TOTAL = Counter(
    "hsi_ab_rollout_analysis_total",
    "Total A/B rollout experiment analyses by group",
    labelnames=["group"],  # control, treatment
    registry=_registry,
)

# Gauge for A/B rollout FP rate by group
AB_ROLLOUT_FP_RATE = Gauge(
    "hsi_ab_rollout_fp_rate",
    "A/B rollout experiment false positive rate by group",
    labelnames=["group"],  # control, treatment
    registry=_registry,
)

# Gauge for A/B rollout average latency by group
AB_ROLLOUT_AVG_LATENCY_MS = Gauge(
    "hsi_ab_rollout_avg_latency_ms",
    "A/B rollout experiment average latency in milliseconds by group",
    labelnames=["group"],  # control, treatment
    registry=_registry,
)

# Gauge for A/B rollout average risk score by group
AB_ROLLOUT_AVG_RISK_SCORE = Gauge(
    "hsi_ab_rollout_avg_risk_score",
    "A/B rollout experiment average risk score by group",
    labelnames=["group"],  # control, treatment
    registry=_registry,
)

# Counter for A/B rollout feedback by group
AB_ROLLOUT_FEEDBACK_TOTAL = Counter(
    "hsi_ab_rollout_feedback_total",
    "Total A/B rollout experiment feedback submissions by group and type",
    labelnames=["group", "feedback_type"],  # group: control/treatment, type: fp/correct
    registry=_registry,
)


def record_ab_rollout_analysis(group: str) -> None:
    """Record an A/B rollout analysis.

    Args:
        group: Experiment group ("control" or "treatment")
    """
    safe_group = sanitize_metric_label(group, max_length=16)
    AB_ROLLOUT_ANALYSIS_TOTAL.labels(group=safe_group).inc()


def update_ab_rollout_fp_rate(group: str, fp_rate: float) -> None:
    """Update the A/B rollout FP rate gauge.

    Args:
        group: Experiment group ("control" or "treatment")
        fp_rate: False positive rate (0.0 to 1.0)
    """
    safe_group = sanitize_metric_label(group, max_length=16)
    AB_ROLLOUT_FP_RATE.labels(group=safe_group).set(fp_rate)


def update_ab_rollout_avg_latency(group: str, latency_ms: float) -> None:
    """Update the A/B rollout average latency gauge.

    Args:
        group: Experiment group ("control" or "treatment")
        latency_ms: Average latency in milliseconds
    """
    safe_group = sanitize_metric_label(group, max_length=16)
    AB_ROLLOUT_AVG_LATENCY_MS.labels(group=safe_group).set(latency_ms)


def update_ab_rollout_avg_risk_score(group: str, avg_score: float) -> None:
    """Update the A/B rollout average risk score gauge.

    Args:
        group: Experiment group ("control" or "treatment")
        avg_score: Average risk score
    """
    safe_group = sanitize_metric_label(group, max_length=16)
    AB_ROLLOUT_AVG_RISK_SCORE.labels(group=safe_group).set(avg_score)


def record_ab_rollout_feedback(group: str, is_false_positive: bool) -> None:
    """Record an A/B rollout feedback submission.

    Args:
        group: Experiment group ("control" or "treatment")
        is_false_positive: Whether the feedback indicates a false positive
    """
    safe_group = sanitize_metric_label(group, max_length=16)
    feedback_type = "false_positive" if is_false_positive else "correct"
    AB_ROLLOUT_FEEDBACK_TOTAL.labels(group=safe_group, feedback_type=feedback_type).inc()


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
# Worker Pool Metrics Helpers
# =============================================================================


def set_worker_active_count(count: int) -> None:
    """Set the number of active workers.

    Active workers are those that are registered and capable of processing
    tasks. This includes both busy and idle workers.

    Args:
        count: Number of active workers
    """
    WORKER_ACTIVE_COUNT.set(count)


def set_worker_busy_count(count: int) -> None:
    """Set the number of busy workers.

    Busy workers are those currently processing tasks.

    Args:
        count: Number of busy workers
    """
    WORKER_BUSY_COUNT.set(count)


def set_worker_idle_count(count: int) -> None:
    """Set the number of idle workers.

    Idle workers are active but not currently processing tasks.

    Args:
        count: Number of idle workers
    """
    WORKER_IDLE_COUNT.set(count)


def update_worker_pool_metrics(active: int, busy: int, idle: int | None = None) -> None:
    """Update all worker pool metrics at once.

    This is a convenience function for updating all worker pool metrics
    in a single call. If idle is not provided, it is calculated as
    active - busy.

    Args:
        active: Number of active workers
        busy: Number of busy workers
        idle: Number of idle workers (optional, calculated if not provided)
    """
    set_worker_active_count(active)
    set_worker_busy_count(busy)
    if idle is None:
        idle = max(0, active - busy)
    set_worker_idle_count(idle)


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


# =============================================================================
# Video Analytics Helper Functions (NEM-3722)
# =============================================================================


# -----------------------------------------------------------------------------
# Tracking Metric Helpers
# -----------------------------------------------------------------------------


def record_track_created(camera_id: str) -> None:
    """Record a new object track being created.

    Args:
        camera_id: ID of the camera where the track was created.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    TRACKS_CREATED_TOTAL.labels(camera_id=safe_camera_id).inc()


def record_track_lost(camera_id: str, reason: str) -> None:
    """Record an object track being lost.

    Args:
        camera_id: ID of the camera where the track was lost.
        reason: Reason for track loss (timeout, out_of_frame, occlusion).
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    safe_reason = sanitize_metric_label(reason, max_length=32)
    TRACKS_LOST_TOTAL.labels(camera_id=safe_camera_id, reason=safe_reason).inc()


def record_track_reidentified(camera_id: str) -> None:
    """Record a track being reidentified after being lost.

    Args:
        camera_id: ID of the camera where the track was reidentified.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    TRACKS_REIDENTIFIED_TOTAL.labels(camera_id=safe_camera_id).inc()


def observe_track_duration(camera_id: str, entity_type: str, duration_seconds: float) -> None:
    """Record the duration of an object track.

    Args:
        camera_id: ID of the camera where the track existed.
        entity_type: Type of entity tracked (person, vehicle, etc.).
        duration_seconds: Duration of the track in seconds.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    safe_entity_type = sanitize_metric_label(entity_type, max_length=32)
    TRACK_DURATION_SECONDS.labels(camera_id=safe_camera_id, entity_type=safe_entity_type).observe(
        duration_seconds
    )


def set_active_track_count(camera_id: str, count: int) -> None:
    """Set the current number of active tracks for a camera.

    Args:
        camera_id: ID of the camera.
        count: Number of active tracks.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    TRACK_ACTIVE_COUNT.labels(camera_id=safe_camera_id).set(count)


# -----------------------------------------------------------------------------
# Zone Metric Helpers
# -----------------------------------------------------------------------------


def record_zone_crossing(zone_id: str, direction: str, entity_type: str) -> None:
    """Record a zone boundary crossing event.

    Args:
        zone_id: ID of the zone being crossed.
        direction: Direction of crossing (enter, exit).
        entity_type: Type of entity crossing (person, vehicle, etc.).
    """
    safe_zone_id = sanitize_metric_label(zone_id, max_length=64)
    safe_direction = sanitize_metric_label(direction, max_length=16)
    safe_entity_type = sanitize_metric_label(entity_type, max_length=32)
    ZONE_CROSSINGS_TOTAL.labels(
        zone_id=safe_zone_id, direction=safe_direction, entity_type=safe_entity_type
    ).inc()


def record_zone_intrusion(zone_id: str, severity: str) -> None:
    """Record a zone intrusion alert.

    Args:
        zone_id: ID of the zone where intrusion was detected.
        severity: Severity of the intrusion (low, medium, high).
    """
    safe_zone_id = sanitize_metric_label(zone_id, max_length=64)
    safe_severity = sanitize_metric_label(severity, max_length=16)
    ZONE_INTRUSIONS_TOTAL.labels(zone_id=safe_zone_id, severity=safe_severity).inc()


def set_zone_occupancy(zone_id: str, count: int) -> None:
    """Set the current occupancy count for a zone.

    Args:
        zone_id: ID of the zone.
        count: Number of entities currently in the zone.
    """
    safe_zone_id = sanitize_metric_label(zone_id, max_length=64)
    ZONE_OCCUPANCY.labels(zone_id=safe_zone_id).set(count)


def observe_zone_dwell_time(zone_id: str, duration_seconds: float) -> None:
    """Record the dwell time of an entity in a zone.

    Args:
        zone_id: ID of the zone.
        duration_seconds: Time spent in the zone in seconds.
    """
    safe_zone_id = sanitize_metric_label(zone_id, max_length=64)
    ZONE_DWELL_TIME_SECONDS.labels(zone_id=safe_zone_id).observe(duration_seconds)


# -----------------------------------------------------------------------------
# Loitering Metric Helpers
# -----------------------------------------------------------------------------


def record_loitering_alert(camera_id: str, zone_id: str) -> None:
    """Record a loitering alert being generated.

    Args:
        camera_id: ID of the camera where loitering was detected.
        zone_id: ID of the zone where loitering occurred.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    safe_zone_id = sanitize_metric_label(zone_id, max_length=64)
    LOITERING_ALERTS_TOTAL.labels(camera_id=safe_camera_id, zone_id=safe_zone_id).inc()


def observe_loitering_dwell_time(camera_id: str, duration_seconds: float) -> None:
    """Record the dwell time for a loitering detection.

    Args:
        camera_id: ID of the camera where loitering was detected.
        duration_seconds: Duration of the loitering in seconds.
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    LOITERING_DWELL_TIME_SECONDS.labels(camera_id=safe_camera_id).observe(duration_seconds)


# -----------------------------------------------------------------------------
# Action Recognition Metric Helpers
# -----------------------------------------------------------------------------


def record_action_recognition(action_type: str, camera_id: str) -> None:
    """Record an action being recognized.

    Args:
        action_type: Type of action recognized (walking, loitering, fighting, etc.).
        camera_id: ID of the camera where the action was detected.
    """
    safe_action_type = sanitize_metric_label(action_type, max_length=64)
    safe_camera_id = sanitize_camera_id(camera_id)
    ACTION_RECOGNITION_TOTAL.labels(action_type=safe_action_type, camera_id=safe_camera_id).inc()


def observe_action_recognition_confidence(action_type: str, confidence: float) -> None:
    """Record the confidence score for an action recognition.

    Args:
        action_type: Type of action recognized.
        confidence: Confidence score (0.0 to 1.0).
    """
    safe_action_type = sanitize_metric_label(action_type, max_length=64)
    ACTION_RECOGNITION_CONFIDENCE.labels(action_type=safe_action_type).observe(confidence)


def observe_action_recognition_duration(duration_seconds: float) -> None:
    """Record the duration of an action recognition inference.

    Args:
        duration_seconds: Inference duration in seconds.
    """
    ACTION_RECOGNITION_DURATION_SECONDS.observe(duration_seconds)


# -----------------------------------------------------------------------------
# Face Recognition Metric Helpers
# -----------------------------------------------------------------------------


def record_face_detection(camera_id: str, match_status: str) -> None:
    """Record a face detection event.

    Args:
        camera_id: ID of the camera where the face was detected.
        match_status: Whether face matched a known person (known, unknown).
    """
    safe_camera_id = sanitize_camera_id(camera_id)
    safe_match_status = sanitize_metric_label(match_status, max_length=16)
    FACE_DETECTIONS_TOTAL.labels(camera_id=safe_camera_id, match_status=safe_match_status).inc()


def observe_face_quality_score(quality_score: float) -> None:
    """Record the quality score of a detected face.

    Args:
        quality_score: Face quality score (0.0 to 1.0, higher is better).
    """
    FACE_QUALITY_SCORE.observe(quality_score)


def record_face_embedding_generated() -> None:
    """Record a face embedding being generated."""
    FACE_EMBEDDINGS_GENERATED_TOTAL.inc()


def record_face_match(person_id: str) -> None:
    """Record a face matching against a known person.

    Args:
        person_id: ID of the matched person.
    """
    safe_person_id = sanitize_metric_label(person_id, max_length=64)
    FACE_MATCHES_TOTAL.labels(person_id=safe_person_id).inc()
