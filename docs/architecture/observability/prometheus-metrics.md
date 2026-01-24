# Prometheus Metrics

> Custom Prometheus metrics for pipeline monitoring, AI service performance, and business intelligence.

**Key Files:**

- `backend/core/metrics.py:1-2100` - All metric definitions and helpers
- `backend/core/sanitization.py` - Label sanitization for cardinality control
- `monitoring/prometheus.yml:1-411` - Prometheus scrape configuration
- `monitoring/prometheus-rules.yml:1-170` - Recording rules for SLIs

## Overview

The system exposes Prometheus metrics via the `/api/metrics` endpoint. Metrics cover the complete AI pipeline from image detection through LLM analysis, including queue depths, latencies, error rates, and business metrics like events by risk level.

All metrics use the `hsi_` prefix (home security intelligence) and follow Prometheus naming conventions: counters end with `_total`, histograms measuring duration end with `_seconds`, and gauges use descriptive names without suffix.

Label cardinality is controlled through sanitization functions that validate values against allowlists before recording. This prevents unbounded metric growth from unexpected values.

## Architecture

```mermaid
graph TD
    subgraph "Application"
        SVC[Services] --> MS[MetricsService<br/>metrics.py:696-1244]
        MS --> COUNTER[Counters<br/>metrics.py:259-365]
        MS --> HIST[Histograms<br/>metrics.py:247-295]
        MS --> GAUGE[Gauges<br/>metrics.py:107-224]
    end

    subgraph "Exposition"
        COUNTER --> REG[Prometheus Registry]
        HIST --> REG
        GAUGE --> REG
        REG --> EP[/api/metrics<br/>metrics.py:1724-1730]
    end

    subgraph "Collection"
        EP --> PROM[Prometheus Server]
        PROM --> RULES[Recording Rules<br/>prometheus-rules.yml]
    end

    subgraph "Visualization"
        PROM --> GRAF[Grafana Dashboards]
        RULES --> GRAF
    end
```

## Metric Categories

### Queue Depth Gauges

Monitor pipeline backpressure (`backend/core/metrics.py:107-117`):

| Metric                      | Type  | Description                      |
| --------------------------- | ----- | -------------------------------- |
| `hsi_detection_queue_depth` | Gauge | Images waiting for detection     |
| `hsi_analysis_queue_depth`  | Gauge | Batches waiting for LLM analysis |

PromQL Examples:

```promql
# Current detection queue depth
hsi_detection_queue_depth

# Queue backed up (>100 items for 5 minutes)
hsi_detection_queue_depth > 100
```

### Stage Duration Histograms

Track pipeline latency (`backend/core/metrics.py:232-253`):

| Metric                       | Labels  | Buckets                                                            |
| ---------------------------- | ------- | ------------------------------------------------------------------ |
| `hsi_stage_duration_seconds` | `stage` | 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0 |

Stage values: `detect`, `batch`, `analyze`

PromQL Examples:

```promql
# P95 detection latency over 5 minutes
histogram_quantile(0.95, sum(rate(hsi_stage_duration_seconds_bucket{stage="detect"}[5m])) by (le))

# Average analysis time
rate(hsi_stage_duration_seconds_sum{stage="analyze"}[5m]) / rate(hsi_stage_duration_seconds_count{stage="analyze"}[5m])
```

### AI Service Request Duration

Track external AI service latency (`backend/core/metrics.py:276-295`):

| Metric                            | Labels    | Buckets                                                |
| --------------------------------- | --------- | ------------------------------------------------------ |
| `hsi_ai_request_duration_seconds` | `service` | 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0 |

Service values: `rtdetr`, `nemotron`, `florence`, `clip`, `enrichment`

PromQL Examples:

```promql
# P99 Nemotron request latency
histogram_quantile(0.99, sum(rate(hsi_ai_request_duration_seconds_bucket{service="nemotron"}[5m])) by (le))

# Average RT-DETR inference time
rate(hsi_ai_request_duration_seconds_sum{service="rtdetr"}[5m]) / rate(hsi_ai_request_duration_seconds_count{service="rtdetr"}[5m])
```

### Event and Detection Counters

Track throughput (`backend/core/metrics.py:259-269`):

| Metric                           | Type    | Description                |
| -------------------------------- | ------- | -------------------------- |
| `hsi_events_created_total`       | Counter | Security events created    |
| `hsi_detections_processed_total` | Counter | Detections through RT-DETR |

PromQL Examples:

```promql
# Events per minute
rate(hsi_events_created_total[1m]) * 60

# Detections per second
rate(hsi_detections_processed_total[5m])
```

### Detection Class Distribution

Track what objects are detected (`backend/core/metrics.py:313-318`):

| Metric                          | Labels         | Description              |
| ------------------------------- | -------------- | ------------------------ |
| `hsi_detections_by_class_total` | `object_class` | Detections by COCO class |

Object classes are sanitized to COCO vocabulary (`backend/core/sanitization.py`).

PromQL Examples:

```promql
# Top 5 detected classes
topk(5, sum by (object_class) (rate(hsi_detections_by_class_total[1h])))

# Person detections per minute
rate(hsi_detections_by_class_total{object_class="person"}[1m]) * 60
```

### Detection Confidence Histogram

Track model confidence distribution (`backend/core/metrics.py:322-329`):

| Metric                     | Buckets                             |
| -------------------------- | ----------------------------------- |
| `hsi_detection_confidence` | 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99 |

PromQL Examples:

```promql
# Median confidence score
histogram_quantile(0.5, rate(hsi_detection_confidence_bucket[5m]))

# Percentage of detections with >90% confidence
sum(rate(hsi_detection_confidence_bucket{le="0.9"}[5m])) / sum(rate(hsi_detection_confidence_count[5m]))
```

### Risk Score Distribution

Track LLM-assigned risk scores (`backend/core/metrics.py:343-357`):

| Metric                           | Labels  | Buckets/Description                     |
| -------------------------------- | ------- | --------------------------------------- |
| `hsi_risk_score`                 | -       | 10, 20, 30, 40, 50, 60, 70, 80, 90, 100 |
| `hsi_events_by_risk_level_total` | `level` | Counter by risk level                   |

Level values: `low`, `medium`, `high`, `critical`

PromQL Examples:

```promql
# Average risk score
histogram_quantile(0.5, rate(hsi_risk_score_bucket[1h]))

# Critical events per hour
increase(hsi_events_by_risk_level_total{level="critical"}[1h])

# High-risk event rate
rate(hsi_events_by_risk_level_total{level=~"high|critical"}[5m])
```

### LLM Token Metrics

Track Nemotron usage (`backend/core/metrics.py:599-624`):

| Metric                              | Labels      | Description              |
| ----------------------------------- | ----------- | ------------------------ |
| `hsi_nemotron_tokens_input_total`   | `camera_id` | Input tokens sent        |
| `hsi_nemotron_tokens_output_total`  | `camera_id` | Output tokens received   |
| `hsi_nemotron_tokens_per_second`    | -           | Current throughput gauge |
| `hsi_nemotron_token_cost_usd_total` | `camera_id` | Estimated cost           |

PromQL Examples:

```promql
# Tokens per second (current)
hsi_nemotron_tokens_per_second

# Total tokens in last hour
increase(hsi_nemotron_tokens_input_total[1h]) + increase(hsi_nemotron_tokens_output_total[1h])

# Daily estimated cost
sum(increase(hsi_nemotron_token_cost_usd_total[24h]))
```

### LLM Context Utilization

Track context window usage (`backend/core/metrics.py:373-402`):

| Metric                               | Labels  | Buckets/Description                            |
| ------------------------------------ | ------- | ---------------------------------------------- |
| `hsi_llm_context_utilization`        | -       | 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0 |
| `hsi_llm_context_utilization_ratio`  | `model` | Current utilization gauge                      |
| `hsi_prompts_truncated_total`        | -       | Prompts requiring truncation                   |
| `hsi_prompts_high_utilization_total` | -       | Prompts exceeding warning threshold            |

PromQL Examples:

```promql
# P95 context utilization
histogram_quantile(0.95, rate(hsi_llm_context_utilization_bucket[5m]))

# Truncation rate per minute
rate(hsi_prompts_truncated_total[5m]) * 60
```

### Cache Metrics

Track Redis cache effectiveness (`backend/core/metrics.py:537-594`):

| Metric                               | Labels                 | Description                 |
| ------------------------------------ | ---------------------- | --------------------------- |
| `hsi_cache_hits_total`               | `cache_type`           | Cache hits                  |
| `hsi_cache_misses_total`             | `cache_type`           | Cache misses                |
| `hsi_cache_invalidations_total`      | `cache_type`, `reason` | Cache invalidations         |
| `hsi_cache_stale_hits_total`         | `cache_type`           | Stale-while-revalidate hits |
| `hsi_cache_background_refresh_total` | `cache_type`, `status` | Background refreshes        |

Cache types: `event_stats`, `cameras`, `system`, `dashboard_stats`

PromQL Examples:

```promql
# Cache hit ratio
sum(rate(hsi_cache_hits_total[5m])) / (sum(rate(hsi_cache_hits_total[5m])) + sum(rate(hsi_cache_misses_total[5m])))

# Cache invalidations by reason
sum by (reason) (rate(hsi_cache_invalidations_total[1h]))
```

### Pipeline Error Counters

Track errors by type (`backend/core/metrics.py:301-306`):

| Metric                      | Labels       | Description             |
| --------------------------- | ------------ | ----------------------- |
| `hsi_pipeline_errors_total` | `error_type` | Pipeline errors by type |

Error types are sanitized to an allowlist including: `connection_error`, `timeout_error`, `validation_error`, `rate_limit_error`, `unknown_error`

PromQL Examples:

```promql
# Error rate by type
sum by (error_type) (rate(hsi_pipeline_errors_total[5m]))

# Total errors per minute
sum(rate(hsi_pipeline_errors_total[1m])) * 60
```

### Worker Pool Metrics

Track pipeline worker state (`backend/core/metrics.py:119-202`):

| Metric                                     | Labels        | Description                                          |
| ------------------------------------------ | ------------- | ---------------------------------------------------- |
| `hsi_worker_restarts_total`                | `worker_name` | Worker restart count                                 |
| `hsi_worker_crashes_total`                 | `worker_name` | Worker crash count                                   |
| `hsi_worker_status`                        | `worker_name` | Current status (0-4)                                 |
| `hsi_pipeline_worker_state`                | `worker_name` | State (0=stopped, 1=running, 2=restarting, 3=failed) |
| `hsi_pipeline_worker_consecutive_failures` | `worker_name` | Consecutive failure count                            |
| `hsi_pipeline_worker_uptime_seconds`       | `worker_name` | Uptime since last start                              |
| `hsi_worker_active_count`                  | -             | Total active workers                                 |
| `hsi_worker_busy_count`                    | -             | Workers processing tasks                             |
| `hsi_worker_idle_count`                    | -             | Workers waiting for tasks                            |

PromQL Examples:

```promql
# All workers running
count(hsi_pipeline_worker_state == 1)

# Workers in failed state
count(hsi_pipeline_worker_state == 3)

# Worker utilization
hsi_worker_busy_count / hsi_worker_active_count
```

### Enrichment Model Metrics

Track Model Zoo performance (`backend/core/metrics.py:433-477`):

| Metric                                  | Labels   | Description                  |
| --------------------------------------- | -------- | ---------------------------- |
| `hsi_enrichment_model_calls_total`      | `model`  | Calls per model              |
| `hsi_enrichment_model_duration_seconds` | `model`  | Inference duration histogram |
| `hsi_enrichment_model_errors_total`     | `model`  | Errors per model             |
| `hsi_enrichment_success_rate`           | `model`  | Success rate gauge (0-1)     |
| `hsi_enrichment_partial_batches_total`  | -        | Batches with partial success |
| `hsi_enrichment_batch_status_total`     | `status` | Batch outcomes               |

Model values: `brisque`, `violence`, `clothing`, `vehicle`, `pet`, `depth`, `pose`, `action`, `weather`, `fashion-clip`

PromQL Examples:

```promql
# P95 enrichment latency by model
histogram_quantile(0.95, sum by (model, le) (rate(hsi_enrichment_model_duration_seconds_bucket[5m])))

# Enrichment error rate
sum(rate(hsi_enrichment_model_errors_total[5m])) / sum(rate(hsi_enrichment_model_calls_total[5m]))
```

### Cost Tracking Metrics

Track inference costs (`backend/core/metrics.py:630-689`):

| Metric                              | Labels      | Description                     |
| ----------------------------------- | ----------- | ------------------------------- |
| `hsi_gpu_seconds_total`             | `model`     | GPU time consumed               |
| `hsi_estimated_cost_usd_total`      | `service`   | Estimated cloud-equivalent cost |
| `hsi_event_analysis_cost_usd_total` | `camera_id` | Cost per event                  |
| `hsi_daily_cost_usd`                | -           | Current daily cost gauge        |
| `hsi_monthly_cost_usd`              | -           | Current monthly cost gauge      |
| `hsi_budget_utilization_ratio`      | `period`    | Budget utilization (0-1+)       |
| `hsi_cost_per_detection_usd`        | -           | Average cost per detection      |
| `hsi_cost_per_event_usd`            | -           | Average cost per event          |

PromQL Examples:

```promql
# Daily cost
hsi_daily_cost_usd

# Budget utilization
hsi_budget_utilization_ratio{period="monthly"}

# Cost per event
hsi_cost_per_event_usd
```

### Queue Overflow Metrics

Track backpressure handling (`backend/core/metrics.py:505-531`):

| Metric                               | Labels                 | Description                |
| ------------------------------------ | ---------------------- | -------------------------- |
| `hsi_queue_overflow_total`           | `queue_name`, `policy` | Overflow events            |
| `hsi_queue_items_moved_to_dlq_total` | `queue_name`           | Items to dead-letter queue |
| `hsi_queue_items_dropped_total`      | `queue_name`           | Items dropped              |
| `hsi_queue_items_rejected_total`     | `queue_name`           | Items rejected             |

PromQL Examples:

```promql
# Overflow events by policy
sum by (policy) (rate(hsi_queue_overflow_total[1h]))

# DLQ rate
rate(hsi_queue_items_moved_to_dlq_total[5m])
```

## MetricsService Class

The `MetricsService` (`backend/core/metrics.py:696-1244`) provides a centralized interface for recording metrics with automatic sanitization:

```python
# From backend/core/metrics.py:696-720
class MetricsService:
    """Centralized service for recording Prometheus metrics."""

    def record_event_created(self) -> None:
        EVENTS_CREATED_TOTAL.inc()

    def record_detection_by_class(self, object_class: str) -> None:
        safe_class = sanitize_object_class(object_class)
        DETECTIONS_BY_CLASS_TOTAL.labels(object_class=safe_class).inc()

    def observe_stage_duration(self, stage: str, duration_seconds: float) -> None:
        STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)
```

Usage:

```python
from backend.core.metrics import get_metrics_service

metrics = get_metrics_service()
metrics.record_event_created()
metrics.observe_stage_duration("detect", 0.245)
metrics.record_detection_by_class("person")
```

## Recording Rules

Pre-computed SLI metrics (`monitoring/prometheus-rules.yml`):

| Rule                                          | Expression                                                    | Purpose               |
| --------------------------------------------- | ------------------------------------------------------------- | --------------------- |
| `hsi:api_requests:success_rate_5m`            | `avg_over_time(probe_success{job="blackbox-http-ready"}[5m])` | API availability      |
| `hsi:detection_latency:p95_5m`                | `histogram_quantile(0.95, ...)`                               | Detection P95 latency |
| `hsi:analysis_latency:p95_5m`                 | `histogram_quantile(0.95, ...)`                               | Analysis P95 latency  |
| `hsi:gpu:memory_utilization`                  | `hsi_gpu_memory_used_mb / hsi_gpu_memory_total_mb`            | GPU memory %          |
| `hsi:error_budget:api_availability_remaining` | Budget calculation                                            | SLO error budget      |
| `hsi:burn_rate:api_availability_1h`           | Burn rate calculation                                         | SLO burn rate         |

## Configuration

Prometheus scrape configuration (`monitoring/prometheus.yml:35-45`):

```yaml
- job_name: 'hsi-backend-metrics'
  metrics_path: /api/metrics
  scrape_interval: 15s
  static_configs:
    - targets:
        - 'backend:8000'
  relabel_configs:
    - target_label: service
      replacement: 'home-security-intelligence'
```

## Histogram Bucket Selection

Buckets are designed for the expected latency distributions:

| Use Case            | Buckets      | Rationale                               |
| ------------------- | ------------ | --------------------------------------- |
| Stage durations     | 10ms - 60s   | Covers fast detections to slow analyses |
| AI requests         | 100ms - 120s | Includes long LLM generation            |
| Confidence          | 0.5 - 0.99   | Focus on high-confidence detections     |
| Risk scores         | 10 - 100     | Full 0-100 range in 10-point increments |
| Context utilization | 0.5 - 1.0    | Focus on high utilization               |

## Testing

Run metrics tests:

```bash
uv run pytest backend/tests/unit/core/test_metrics.py -v
```

| Test                             | Purpose                |
| -------------------------------- | ---------------------- |
| `test_record_event_created`      | Counter increment      |
| `test_observe_stage_duration`    | Histogram observation  |
| `test_label_sanitization`        | Cardinality protection |
| `test_metrics_service_singleton` | Single instance        |

## Related Documents

- [Grafana Dashboards](./grafana-dashboards.md) - Dashboard panel queries
- [Alertmanager](./alertmanager.md) - Alert rules using metrics
- [Distributed Tracing](./distributed-tracing.md) - Trace-to-metrics correlation
