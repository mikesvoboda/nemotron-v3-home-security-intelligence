# HSI Metrics Coverage

This document maps the HSI (Home Security Intelligence) Prometheus metrics to their emitters and to the Grafana dashboard panels that read them.

## Overview

HSI exposes Prometheus metrics for comprehensive system observability. Metrics follow these naming conventions:

- Prefix: `hsi_` (Home Security Intelligence)
- Counters end with `_total`
- Histograms/durations end with `_seconds` (they export `_bucket` / `_sum` / `_count`)
- Gauges use descriptive names without suffix

### Who Exposes What

Six sources feed Prometheus. Knowing which one owns a family tells you where a
missing series has to be fixed:

| Source                                                       | Endpoint                   | Prometheus job                                           | What it exports                                                                                                                                                                                                                    |
| ------------------------------------------------------------ | -------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend (Python)                                             | `backend:8000/api/metrics` | `hsi-backend-metrics`                                    | everything defined in `backend/core/metrics.py`, plus the HTTP middleware's `http_request_duration_seconds` / `http_requests_total` and the deprecation counter                                                                    |
| AI gateway (FastAPI layer)                                   | `ai-gateway:8090/metrics`  | `ai-gateway-metrics`                                     | `hsi_ai_inference_duration_seconds`, `hsi_ai_inference_errors_total`, `process_*`; Triton's `nv_*` text is merged into this endpoint and **dropped by a `metric_relabel_configs` rule** so only the `triton-metrics` job counts it |
| Triton (inside the gateway container)                        | `ai-gateway:8002/metrics`  | `triton-metrics`                                         | the native `nv_*` families, labelled `service="triton"`                                                                                                                                                                            |
| VLM engine                                                   | `ai-vlm:8098/metrics`      | `ai-vlm-metrics`                                         | llama.cpp's native `llama_*` families, labelled `service="ai-vlm"`                                                                                                                                                                 |
| JSON exporter (backend health/telemetry/stats/GPU)           | `json-exporter:7979/probe` | `hsi-health` / `hsi-telemetry` / `hsi-stats` / `hsi-gpu` | the 43 derived `hsi_*` names in `monitoring/json-exporter-config.yml` — including the whole `hsi_gpu_*` gauge set                                                                                                                  |
| node / redis / alertmanager / blackbox / pyroscope exporters | their own ports            | matching jobs                                            | standard exporter families                                                                                                                                                                                                         |

`honor_labels: true` is set on the backend, gateway, Triton and VLM jobs so a
metric's own `service` label survives the scrape instead of being renamed.

Metrics are defined in `backend/core/metrics.py` (Prometheus client registry) and
`backend/core/otel_metrics.py` (OpenTelemetry instruments — see
[OpenTelemetry](#opentelemetry-instrumentation-otel_metricspy) below).

### A series is only signal if something calls its recorder

`backend/core/metrics.py` defines 160 `hsi_*` families, and `prometheus_client`
exports an unlabelled counter or histogram **even when nothing ever observes
it** — it shows up at zero (or with zero-valued buckets, for a histogram). A
labelled family exports nothing until its first `.labels(...)` call. So "the
metric exists in the code" and "the panel has data" are different claims, and the
tables below say which is which. §
[Defined, not emitted](#defined-not-emitted) lists
every family whose recorder has no caller in the shipped code, and
[Dashboards that read empty series](#dashboards-that-read-empty-series) lists the
panels sitting on top of them.

---

## Backend `/api/metrics` Metrics With A Live Producer

Each row names the production call site that feeds the family.

### Pipeline Stages, Workers, Queues

| Metric                                                    | Type      | Labels                           | Emitted by                                                                                          | Panels                                     |
| --------------------------------------------------------- | --------- | -------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| `hsi_stage_duration_seconds`                              | Histogram | `stage`                          | `services/pipeline_workers.py`                                                                      | Consolidated: Pipeline Stage Latency       |
| `hsi_pipeline_errors_total`                               | Counter   | `error_type`                     | `pipeline_workers.py`, `redis_streams.py`, `detector_client.py`, `vlm_analyzer.py`, `vlm_client.py` | Consolidated: Pipeline Errors              |
| `hsi_detection_queue_depth`                               | Gauge     | -                                | `pipeline_workers.py` (`set_queue_depth("detection", …)`)                                           | Consolidated: Detection Queue Depth        |
| `hsi_analysis_queue_depth`                                | Gauge     | -                                | `pipeline_workers.py` (`set_queue_depth("analysis", …)`)                                            | Consolidated: Analysis Queue Depth         |
| `hsi_dlq_depth`                                           | Gauge     | `queue_name`                     | `api/routes/health_ai_services.py`                                                                  | -                                          |
| `hsi_queue_overflow_total`                                | Counter   | `queue_name`, `policy`           | `core/redis.py`                                                                                     | Consolidated: Queue Overflow               |
| `hsi_queue_items_moved_to_dlq_total`                      | Counter   | `queue_name`                     | `core/redis.py`                                                                                     | Consolidated: Items Moved to DLQ           |
| `hsi_queue_items_dropped_total`                           | Counter   | `queue_name`                     | `core/redis.py`                                                                                     | Consolidated: Items Dropped                |
| `hsi_queue_items_rejected_total`                          | Counter   | `queue_name`                     | `core/redis.py`                                                                                     | Consolidated: Items Rejected               |
| `hsi_batch_max_detections_reached_total`                  | Counter   | -                                | `services/batch_aggregator.py`                                                                      | -                                          |
| `hsi_batch_coalesced_total`                               | Counter   | -                                | `services/batch_coalescer.py`                                                                       | -                                          |
| `hsi_batch_coalesce_candidates_total`                     | Counter   | -                                | `api/routes/system.py`, `batch_coalescer.py`                                                        | -                                          |
| `hsi_batch_coalesce_detections_merged_total`              | Counter   | -                                | `api/routes/system.py`, `batch_coalescer.py`                                                        | -                                          |
| `hsi_batch_coalesce_merge_rate`                           | Gauge     | -                                | `api/routes/system.py`, `batch_coalescer.py`                                                        | -                                          |
| `hsi_batch_coalesce_llm_calls_saved_total`                | Counter   | -                                | `api/routes/system.py`                                                                              | -                                          |
| `hsi_worker_restarts_total`                               | Counter   | `worker_name`                    | `services/worker_supervisor.py`                                                                     | Consolidated: Worker Restarts              |
| `hsi_worker_crashes_total`                                | Counter   | `worker_name`                    | `services/worker_supervisor.py`                                                                     | Consolidated: Worker Crashes               |
| `hsi_worker_heartbeat_missed_total`                       | Counter   | `worker_name`                    | `services/worker_supervisor.py`                                                                     | -                                          |
| `hsi_worker_max_restarts_exceeded_total`                  | Counter   | `worker_name`                    | `services/worker_supervisor.py`                                                                     | -                                          |
| `hsi_worker_status`                                       | Gauge     | `worker_name`                    | `services/worker_supervisor.py`                                                                     | -                                          |
| `hsi_worker_active_count` / `_busy_count` / `_idle_count` | Gauge     | -                                | `services/worker_supervisor.py` (`update_worker_pool_metrics`)                                      | Consolidated: Active / Busy / Idle Workers |
| `hsi_pipeline_worker_restarts_total`                      | Counter   | `worker_name`, `reason_category` | `services/worker_supervisor.py`                                                                     | Consolidated: Pipeline Worker Restarts     |
| `hsi_pipeline_worker_restart_duration_seconds`            | Histogram | `worker_name`                    | `services/worker_supervisor.py`                                                                     | -                                          |
| `hsi_pipeline_worker_state`                               | Gauge     | `worker_name`                    | `services/worker_supervisor.py`                                                                     | Consolidated: Pipeline Worker State        |
| `hsi_pipeline_worker_consecutive_failures`                | Gauge     | `worker_name`                    | `services/worker_supervisor.py`                                                                     | Consolidated: Consecutive Failures         |
| `hsi_pipeline_worker_uptime_seconds`                      | Gauge     | `worker_name`                    | `services/worker_supervisor.py`                                                                     | Consolidated: Worker Uptime                |

`hsi_stage_duration_seconds` is observed with `stage="detect"` (detection worker
loop) and `stage="batch"` (aggregation worker loop) — those are the only two
label values the shipped code writes.

### Detection

Recorded in `backend/services/detector_client.py`, i.e. on the client side of the
gateway call, so the numbers are round-trip figures for one detector request.

| Metric                                         | Type      | Labels         | Panels                                         |
| ---------------------------------------------- | --------- | -------------- | ---------------------------------------------- |
| `hsi_detections_processed_total`               | Counter   | -              | Consolidated, AI Services: Detection Rate      |
| `hsi_detections_by_class_total`                | Counter   | `object_class` | Consolidated, AI Services: Detections by Class |
| `hsi_detection_confidence`                     | Histogram | -              | Consolidated, AI Services: Average Confidence  |
| `hsi_detections_filtered_low_confidence_total` | Counter   | -              | Consolidated: Filtered Detections              |

### AI Service Requests

| Metric                            | Type      | Labels    | Emitted by                    | Panels                                                  |
| --------------------------------- | --------- | --------- | ----------------------------- | ------------------------------------------------------- |
| `hsi_ai_request_duration_seconds` | Histogram | `service` | `services/detector_client.py` | Consolidated, AI Services: detector latency percentiles |

`DetectorClient` hard-codes `self._detector_type = "yolo26"`, so
`service="yolo26"` is the only label value this histogram ever gets on the
shipped path. The recording rule
`job:yolo26_inference_latency:p95_5m` is built from exactly that selector:

```promql
histogram_quantile(0.95, sum(rate(hsi_ai_request_duration_seconds_bucket{service="yolo26"}[5m])) by (le))
```

(`monitoring/profiling-recording-rules.yml`, which also defines
`…:p99_5m` and `job:yolo26_latency_regression_ratio:p95_vs_1h`.)

| Metric                              | Type      | Labels    | Emitted by                                              | Notes                                            |
| ----------------------------------- | --------- | --------- | ------------------------------------------------------- | ------------------------------------------------ |
| `hsi_ai_service_degraded`           | Gauge     | `service` | `services/vlm_client.py`                                | set from the VLM circuit breaker's state changes |
| `hsi_model_cold_start_total`        | Counter   | `model`   | `services/detector_client.py`, `services/vlm_client.py` | Consolidated / AI Services                       |
| `hsi_model_warmth_state`            | Gauge     | `model`   | `services/detector_client.py`                           | -                                                |
| `hsi_model_warmup_duration_seconds` | Histogram | `model`   | `services/detector_client.py`                           | -                                                |

### Specialist Degradation — The Signal That Matters

`hsi_specialist_unavailable_total` (Counter, labels `specialist`, `reason`) is
recorded by `_record_unavailable()` in `backend/services/vlm_specialists.py`. The
three in-process lookup legs (faces, plates, person re-ID) report every
non-scoring outcome through it, and it is the **only** metric that distinguishes
"the specialist could not run" from "the specialist ran and found nothing". Any
dashboard or alert about specialist health must key on this family.

### Face And Re-ID

| Metric                                | Type      | Labels                                          | Emitted by                                                                            | Panels                          |
| ------------------------------------- | --------- | ----------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------- |
| `hsi_face_detections_total`           | Counter   | `camera_id`, `match_status`                     | `services/face_detector.py`, `face_recognition_service.py`, `models/face_identity.py` | Video Analytics: Faces Detected |
| `hsi_face_recognition_confidence`     | Histogram | `camera_id`                                     | `services/face_detector.py`                                                           | -                               |
| `hsi_face_embedding_duration_seconds` | Histogram | `camera_id`                                     | `services/face_detector.py`                                                           | AI Services                     |
| `hsi_reid_attempts_total`             | Counter   | `entity_type`, `camera_id`                      | `services/reid_service.py`                                                            | Video Analytics                 |
| `hsi_reid_matches_total`              | Counter   | `entity_type`, `camera_id`                      | `services/reid_service.py`                                                            | Video Analytics                 |
| `hsi_reid_match_duration_seconds`     | Histogram | `entity_type`                                   | `services/reid_service.py`                                                            | Video Analytics                 |
| `hsi_cross_camera_handoffs_total`     | Counter   | `source_camera`, `target_camera`, `entity_type` | `services/reid_service.py`                                                            | Video Analytics                 |

### Tracking, Zones, Loitering

| Metric                             | Type      | Labels                                | Emitted by                          | Panels                                     |
| ---------------------------------- | --------- | ------------------------------------- | ----------------------------------- | ------------------------------------------ |
| `hsi_tracks_created_total`         | Counter   | `camera_id`                           | `services/track_service.py`         | Video Analytics: Tracks Created            |
| `hsi_tracks_lost_total`            | Counter   | `camera_id`, `object_class`, `reason` | `services/track_service.py`         | Video Analytics: Tracks Lost, Loss Reasons |
| `hsi_tracks_reidentified_total`    | Counter   | `camera_id`                           | `services/track_service.py`         | Video Analytics: Tracks Reidentified       |
| `hsi_track_duration_seconds`       | Histogram | `camera_id`, `entity_type`            | `services/track_service.py`         | Video Analytics: Track Duration P95        |
| `hsi_zone_crossings_total`         | Counter   | `zone_id`, `direction`, `entity_type` | `services/zone_crossing_service.py` | Video Analytics: Zone Entries              |
| `hsi_zone_intrusions_total`        | Counter   | `zone_id`, `severity`                 | `services/zone_crossing_service.py` | Video Analytics: Zone Intrusions           |
| `hsi_zone_occupancy`               | Gauge     | `zone_id`                             | `services/zone_crossing_service.py` | Video Analytics: Current Zone Occupancy    |
| `hsi_zone_dwell_time_seconds`      | Histogram | `zone_id`                             | `services/zone_crossing_service.py` | Video Analytics: Zone Dwell Time P95       |
| `hsi_loitering_alerts_total`       | Counter   | `camera_id`, `zone_id`                | `services/dwell_time_service.py`    | Video Analytics: Loitering Alerts          |
| `hsi_loitering_events_total`       | Counter   | `zone_id`, `zone_name`, `severity`    | `services/dwell_time_service.py`    | Video Analytics                            |
| `hsi_loitering_dwell_time_seconds` | Histogram | `camera_id`                           | `services/dwell_time_service.py`    | Video Analytics: Median Loitering Duration |

### Events, Review, Cost

| Metric                                                  | Type    | Labels                      | Emitted by                 | Panels                                        |
| ------------------------------------------------------- | ------- | --------------------------- | -------------------------- | --------------------------------------------- |
| `hsi_events_reviewed_total`                             | Counter | -                           | `api/routes/events.py`     | Consolidated: Events Reviewed                 |
| `hsi_events_acknowledged_total`                         | Counter | `camera_name`, `risk_level` | `api/routes/events.py`     | Consolidated: Events Acknowledged             |
| `hsi_gpu_seconds_total`                                 | Counter | `model`                     | `services/cost_tracker.py` | -                                             |
| `hsi_estimated_cost_usd_total`                          | Counter | `service`                   | `services/cost_tracker.py` | Analytics                                     |
| `hsi_event_analysis_cost_usd_total`                     | Counter | `camera_id`                 | `services/cost_tracker.py` | -                                             |
| `hsi_daily_cost_usd` / `hsi_monthly_cost_usd`           | Gauge   | -                           | `services/cost_tracker.py` | Consolidated, Analytics: Daily / Monthly Cost |
| `hsi_cost_per_detection_usd` / `hsi_cost_per_event_usd` | Gauge   | -                           | `services/cost_tracker.py` | Consolidated: Cost per Detection / Event      |
| `hsi_budget_utilization_ratio`                          | Gauge   | `period`                    | `services/cost_tracker.py` | Consolidated, Analytics: Budget Utilization   |
| `hsi_budget_exceeded_total`                             | Counter | `period`                    | `services/cost_tracker.py` | -                                             |

### Cache And Redis Pool

| Metric                                                                       | Type    | Labels                 | Emitted by                                                    |
| ---------------------------------------------------------------------------- | ------- | ---------------------- | ------------------------------------------------------------- |
| `hsi_cache_hits_total` / `hsi_cache_misses_total`                            | Counter | `cache_type`           | `services/cache_service.py`, `services/read_through_cache.py` |
| `hsi_cache_stale_hits_total`                                                 | Counter | `cache_type`           | `services/cache_service.py`                                   |
| `hsi_cache_invalidations_total`                                              | Counter | `cache_type`, `reason` | `services/cache_service.py`                                   |
| `hsi_cache_background_refresh_total`                                         | Counter | `cache_type`, `status` | `services/cache_service.py`                                   |
| `hsi_redis_pool_size` / `hsi_redis_pool_available` / `hsi_redis_pool_in_use` | Gauge   | `pool_type`            | `services/worker_supervisor.py`                               |

### Database And HTTP

| Metric                                                  | Type                | Labels                   | Emitted by                                                         |
| ------------------------------------------------------- | ------------------- | ------------------------ | ------------------------------------------------------------------ |
| `hsi_db_query_duration_seconds`                         | Histogram           | -                        | `core/database.py`, `services/batch_aggregator.py`                 |
| `hsi_slow_queries_total`                                | Counter             | -                        | `core/database.py`, `services/batch_aggregator.py`                 |
| `hsi_health_check_latency_seconds`                      | Histogram           | `endpoint`, `check_type` | `api/routes/system.py`                                             |
| `hsi_health_check_component_latency_seconds`            | Histogram           | `component`              | `api/routes/system.py` (values `database`, `redis`, `ai_services`) |
| `hsi_health_check_cache_hits_total` / `_misses_total`   | Counter             | -                        | `api/routes/system.py`                                             |
| `hsi_api_deprecated_calls_total`                        | Counter             | `endpoint`, `client_id`  | `api/middleware/deprecation_logger.py`                             |
| `http_request_duration_seconds` / `http_requests_total` | Histogram / Counter | route, method, status    | `api/middleware/prometheus.py` (no `hsi_` prefix)                  |

`job:backend_api_latency:p99_5m` is computed from
`http_request_duration_seconds_bucket` — the middleware histogram carries no
`hsi_` prefix.

### Prompt Utilisation

| Metric                               | Type      | Labels  | Emitted by                  | Panels                                  |
| ------------------------------------ | --------- | ------- | --------------------------- | --------------------------------------- |
| `hsi_llm_context_utilization`        | Histogram | -       | `services/token_counter.py` | Nemotron Prompt Analytics               |
| `hsi_llm_context_utilization_ratio`  | Gauge     | `model` | `services/token_counter.py` | Consolidated, Nemotron Prompt Analytics |
| `hsi_prompts_truncated_total`        | Counter   | -       | `services/vlm_client.py`    | Consolidated, Nemotron Prompt Analytics |
| `hsi_prompts_high_utilization_total` | Counter   | -       | `services/token_counter.py` | Consolidated, Nemotron Prompt Analytics |
| `hsi_prompt_tokens`                  | Histogram | -       | `core/database.py`          | Nemotron Prompt Analytics               |
| `hsi_prompt_truncated_total`         | Counter   | -       | `core/database.py`          | Nemotron Prompt Analytics               |

The two similarly-named truncation counters are different series:
`hsi_prompts_truncated_total` counts VLM prompts trimmed by `vlm_client`,
`hsi_prompt_truncated_total` counts prompt records truncated in the database
layer.

### Shadow / A-B Comparison

Recorded by `api/routes/rum.py`, `services/prompt_service.py` and
`config/shadow_mode_deployment.py`:

`hsi_prompt_ab_traffic_total`, `hsi_prompt_rollbacks_total`,
`hsi_prompt_shadow_comparisons_total`, `hsi_ab_rollout_analysis_total`,
`hsi_ab_rollout_feedback_total`, `hsi_ab_rollout_avg_latency_ms`,
`hsi_ab_rollout_avg_risk_score`, `hsi_ab_rollout_fp_rate`,
`hsi_shadow_avg_risk_score`, `hsi_shadow_risk_score_distribution`,
`hsi_shadow_risk_score_diff`, `hsi_shadow_risk_level_shift_total`,
`hsi_shadow_latency_diff_seconds`, `hsi_shadow_latency_warning_total`,
`hsi_shadow_comparison_errors_total`.

### Backend Process Memory

`api/routes/system.py` sets `hsi_process_memory_rss_bytes`,
`hsi_process_memory_container_usage_ratio` and
`hsi_process_memory_container_limit_bytes` — the container-RAM view that pairs
with the host-RAM limits in [GPU Memory Limits](../deployment/gpu-memory-limits.md).

### Real User Monitoring

`api/routes/rum.py` observes `hsi_rum_lcp_seconds`, `hsi_rum_fcp_seconds`,
`hsi_rum_fid_seconds`, `hsi_rum_inp_seconds`, `hsi_rum_ttfb_seconds`,
`hsi_rum_cls`, `hsi_rum_page_load_time_seconds` (histograms labelled
`path`,`rating`) and counts intake with `hsi_rum_metrics_total` (labels `metric_name`,
`rating`).

### Circuit Breakers And Retries

These families are defined **in the module that emits them**, not in
`backend/core/metrics.py`:

| Metric                            | Type    | Labels                 | Owner                                 |
| --------------------------------- | ------- | ---------------------- | ------------------------------------- |
| `hsi_circuit_breaker_state`       | Gauge   | `service`              | `backend/services/circuit_breaker.py` |
| `hsi_circuit_breaker_trips_total` | Counter | `service`              | `backend/services/circuit_breaker.py` |
| `hsi_retry_attempts_total`        | Counter | `operation`, `outcome` | `backend/core/retry.py`               |
| `hsi_retry_operations_total`      | Counter | `operation`            | `backend/core/retry.py`               |

---

## Defined, Not Emitted

The following families are **defined in `backend/core/metrics.py` but no shipped
code path calls their recorder**. A labelled one exports nothing; an unlabelled
histogram exports zero-valued buckets. Treat every panel over them as flat.

| Family group                       | Series                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Event/risk counters with no caller | `hsi_events_created_total`, `hsi_events_by_risk_level_total`, `hsi_events_by_camera_total`, `hsi_risk_score`, `hsi_risk_score_distribution`, `hsi_risk_tier_total`, `hsi_prompt_template_used_total`                                                                                                                                                                                                                                                                                                                                                      |
| Action recognition                 | `hsi_action_recognition_total`, `hsi_action_recognition_confidence`, `hsi_action_recognition_duration_seconds`                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Track/face gauges                  | `hsi_active_tracks_count`, `hsi_track_active_count`, `hsi_face_embeddings_generated_total`, `hsi_face_matches_total`, `hsi_face_quality_score`, `hsi_known_faces_database_size`                                                                                                                                                                                                                                                                                                                                                                           |
| Scene OCR                          | `hsi_scene_ocr_requests_total`, `hsi_scene_ocr_texts_detected_total`, `hsi_scene_ocr_service_providers_matched_total`, `hsi_scene_ocr_processing_seconds`, `hsi_scene_ocr_confidence`                                                                                                                                                                                                                                                                                                                                                                     |
| Model warmth gauge                 | `hsi_model_last_inference_seconds_ago`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Enrichment lane bookkeeping        | `hsi_enrichment_model_calls_total`, `hsi_enrichment_model_duration_seconds`, `hsi_enrichment_model_errors_total`, `hsi_enrichment_success_rate`, `hsi_enrichment_retry_total`, `hsi_enrichment_partial_batches_total`, `hsi_enrichment_failures_total`, `hsi_enrichment_batch_status_total`, `hsi_enrichment_pipeline_stage_duration_seconds`, `hsi_enrichment_pipeline_timeouts_total`, `hsi_enrichment_cascade_skipped_total`, `hsi_enrichment_cascade_processed_total`, `hsi_enrichment_cascade_models_deferred_total`, `hsi_enrichment_quality_level` |
| Workload-specific AI histograms    | `hsi_yolo26_inference_seconds`, `hsi_nemotron_inference_seconds`, `hsi_florence_inference_seconds`, `hsi_florence_task_total`, `hsi_nemotron_tokens_input_total`, `hsi_nemotron_tokens_output_total`, `hsi_nemotron_tokens_per_second`, `hsi_nemotron_token_cost_usd_total`                                                                                                                                                                                                                                                                               |

Why these stay defined: `backend/core/metrics.py` is the recording API other
branches call, and the unit suite in `backend/tests/unit/core/test_metrics.py`
exercises the recorders. Nothing in the running pipeline reaches them, so:

- The VLM's token and latency numbers come from **llama.cpp's own `llama_*`
  families** on `ai-vlm:8098/metrics` (`llama_tokens_predicted_total`,
  `llama_generation_time_seconds`, `llama_kv_cache_usage_ratio`, …), not from any
  `hsi_nemotron_*` / `hsi_llm_*` family. Tokens per second is
  `rate(llama_tokens_predicted_total[1m])`.
- Detector latency is the client-side
  `hsi_ai_request_duration_seconds{service="yolo26"}` histogram; the per-model
  server-side view is Triton's `nv_inference_*` (see below).
- Enrichment-model dashboards have no producer; the readiness-only
  `/enrich-lt` lane does not publish through these families.

## Triton And Gateway Series

From the `triton-metrics` job (`ai-gateway:8002/metrics`, labelled
`service="triton"`), for every model in the mounted repository (`yolo26`, `reid`,
plus `threat` when `GATEWAY_ENABLE_THREAT=true`):

| Series                                            | Meaning                                                             |
| ------------------------------------------------- | ------------------------------------------------------------------- |
| `nv_inference_request_success` / `_failure`       | per-model request counts                                            |
| `nv_inference_request_duration_us`                | cumulative request time (averages only — Triton exposes no buckets) |
| `nv_inference_queue_duration_us`                  | scheduler queue time                                                |
| `nv_inference_compute_infer_duration_us`          | pure inference compute time                                         |
| `nv_gpu_utilization` / `nv_gpu_memory_used_bytes` | GPU view from inside Triton                                         |

`job:triton_inference_latency:avg5m` derives the per-model mean:

```promql
sum by (model) (rate(nv_inference_request_duration_us[5m]))
  / (sum by (model) (rate(nv_inference_request_success[5m])) + 0.001)
```

From the `ai-gateway-metrics` job (`ai-gateway:8090/metrics`):

| Metric                              | Type      | Labels                | Notes                                                                                                                                |
| ----------------------------------- | --------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `hsi_ai_inference_duration_seconds` | Histogram | `service`, `endpoint` | `GatewayMetricsMiddleware` times every non-health, non-scrape request; unmatched paths land in `service="other"`, `endpoint="other"` |
| `hsi_ai_inference_errors_total`     | Counter   | `service`, `endpoint` | counted on 5xx or a handler crash                                                                                                    |
| `process_*`                         | -         | -                     | the gateway process's own runtime metrics                                                                                            |

The `nv_*` families are dropped from this target by
`metric_relabel_configs` in `monitoring/prometheus.yml`, so a query against
`:8090/metrics` will never see them — and never double-counts them.

## GPU And System Metrics (JSON Exporter)

The `hsi_gpu_*` gauges and the small system set are **not** emitted by
`backend/core/metrics.py`. `json-exporter` derives them from backend JSON
endpoints — `/api/system/health`, `/api/system/telemetry`, `/api/system/stats`,
`/api/system/gpu` — per `monitoring/json-exporter-config.yml`:

`hsi_system_healthy`, `hsi_database_healthy`, `hsi_redis_healthy`,
`hsi_ai_healthy`, `hsi_detect_latency_avg_ms`, `hsi_detect_latency_p95_ms`,
`hsi_detect_latency_p99_ms`, `hsi_batch_latency_avg_ms`,
`hsi_batch_latency_p95_ms`, `hsi_batch_latency_p99_ms`,
`hsi_analyze_latency_avg_ms`, `hsi_analyze_latency_p95_ms`,
`hsi_analyze_latency_p99_ms`, `hsi_total_cameras`, `hsi_total_events`,
`hsi_total_detections`, `hsi_uptime_seconds`, `hsi_inference_fps`, and the
`hsi_gpu_*` set: `utilization`, `temperature`, `memory_used_mb`,
`memory_total_mb`, `fan_speed`, `sm_clock_mhz`, `sm_clock_max_mhz`,
`memory_clock_mhz`, `memory_clock_max_mhz`, `power_limit_watts`,
`throttle_reasons`, `pstate`, `compute_processes`, `pcie_tx_throughput_kbs`,
`pcie_rx_throughput_kbs`, `pcie_link_gen`, `pcie_link_width`,
`pcie_replay_counter`, `encoder_utilization`, `decoder_utilization`,
`memory_bandwidth_utilization`, `temp_slowdown_threshold`, `bar1_used_mb`.

Two consequences:

- These are **polled snapshots**, not counters — `hsi_detect_latency_p95_ms` is a
  gauge the exporter computed from one response, so it cannot be `rate()`d and
  its staleness is the scrape interval (`hsi-gpu` 10s, `hsi-stats` 30s).
- If the backend stops answering `/api/system/gpu`, every GPU panel flatlines
  even though the exporter's own target stays up (`redis-exporter` aside — see
  [Container Orchestration](../deployment/container-orchestration.md), the
  json-exporter container itself declares no healthcheck).

DCGM (`dcgm-exporter:9400`, compose profile `gpu-rootful`) and
`node-exporter:9100` are the host-level alternatives when you need per-device
truth rather than a snapshot.

## OpenTelemetry Instrumentation (`otel_metrics.py`)

`backend/core/otel_metrics.py` defines these instruments:

| Instrument                                              | Type      | Declared attributes                              |
| ------------------------------------------------------- | --------- | ------------------------------------------------ |
| `ai.detection.latency`                                  | Histogram | `model.version`, `batch.size`, `gpu.id`          |
| `ai.pipeline.latency`                                   | Histogram | `camera.id`, `pipeline.stage`, `detection.count` |
| `ai.batch.processing_time`                              | Histogram | `batch.size`, `camera.count`, `batch.id`         |
| `circuit_breaker.state`                                 | Gauge     | `breaker`                                        |
| `circuit_breaker.transitions`                           | Counter   | `breaker`, `from_state`, `to_state`              |
| `circuit_breaker.failures` / `.successes` / `.rejected` | Counter   | `breaker`                                        |

Only `backend/services/circuit_breaker.py` imports from this module in
production code — the `ai.*` recorders have no caller, and
`ai.nemotron.latency` / `ai.florence.latency` are instrument names for services
the stack does not run. The whole module is gated on OpenTelemetry being
initialised, and `.env.example` ships `OTEL_ENABLED=false`, so by default none of
these instruments exist at runtime. Traces go to **Tempo**
(`tempo:4317` OTLP gRPC); there is no Jaeger in this stack.

## Dashboard Reference

Every dashboard in `monitoring/grafana/dashboards/` is provisioned by
`monitoring/grafana/provisioning/dashboards/dashboard.yml` (30s refresh, folder
`hsi-dashboards`):

| File                         | UID                     | Title                                   | Reads                                                                              |
| ---------------------------- | ----------------------- | --------------------------------------- | ---------------------------------------------------------------------------------- |
| `consolidated.json`          | `hsi-consolidated`      | Home Security Intelligence - Operations | live backend families + the JSON-exporter set — plus the empty series listed below |
| `ai-services.json`           | `ai-services`           | AI Services                             | `hsi_ai_request_duration_seconds`, `hsi_ai_inference_*`, detection + face families |
| `ai-service-health.json`     | `hsi-ai-service-health` | AI Service Health                       | enrichment model families + `hsi_gpu_memory_*`                                     |
| `analytics.json`             | `hsi-analytics`         | HSI Analytics                           | cost, cache, redis pool, db queries, RUM                                           |
| `api-health.json`            | `hsi-api-health`        | HSI API Health & Deprecation            | `hsi_api_deprecated_calls_total`                                                   |
| `video-analytics.json`       | `video-analytics`       | Video Analytics                         | tracks, zones, loitering, re-ID, face families                                     |
| `hsi-gpu-metrics.json`       | `hsi-gpu-metrics`       | HSI GPU Metrics                         | the JSON-exporter `hsi_gpu_*` gauges                                               |
| `hsi-profiling.json`         | `hsi-profiling`         | HSI Profiling                           | Pyroscope data sources (no `hsi_*` PromQL)                                         |
| `hsi-request-profiling.json` | `hsi-request-profiling` | HSI Request-Level Profiling             | Pyroscope / trace data sources                                                     |
| `logs.json`                  | `hsi-logs`              | HSI System Logs                         | Loki                                                                               |
| `tracing.json`               | `hsi-tracing`           | HSI Distributed Tracing                 | **Tempo** datasource                                                               |
| `scene-ocr.json`             | `hsi-scene-ocr`         | Scene OCR                               | `hsi_scene_ocr_*` only                                                             |

### Dashboards That Read Empty Series

Auditing the query text in each file against the producer census above, these
panels are wired to series that no shipped code path writes, and will read zero
or "No data":

| Dashboard                | Empty series it queries                                                                                                                                                                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scene-ocr.json`         | every panel — all five `hsi_scene_ocr_*` families                                                                                                                                                                                                                           |
| `ai-service-health.json` | the three `hsi_enrichment_*` panels (only `hsi_gpu_memory_*` has data)                                                                                                                                                                                                      |
| `consolidated.json`      | `hsi_events_created_total`, `hsi_events_by_risk_level_total`, `hsi_events_by_camera_total`, `hsi_risk_score*`, `hsi_prompt_template_used_total`, `hsi_florence_task_total`, the four `hsi_nemotron_*` token panels, `hsi_enrichment_*`                                      |
| `ai-services.json`       | `hsi_action_detections_total`, `hsi_action_confidence`, `hsi_action_recognition_*`, `hsi_florence_inference_seconds`, `hsi_florence_task_total`, `hsi_enrichment_model_*`, `hsi_face_embeddings_generated_total`, `hsi_face_quality_score`, `hsi_known_faces_database_size` |
| `video-analytics.json`   | `hsi_action_detections_total`, `hsi_action_confidence`, `hsi_action_recognition_*`, `hsi_face_embeddings_generated_total`, `hsi_face_quality_score`, `hsi_enrichment_model_duration_seconds`                                                                                |

`scripts/audit_grafana_queries.py` exists to re-derive this list from the
dashboard JSON; run it after any metrics change.

## Adding Or Fixing Metrics

1. Define the metric in `backend/core/metrics.py` with `registry=_registry`
   (that registry is what `/api/metrics` renders):

   ```python
   MY_NEW_METRIC = Counter(
       "hsi_my_new_metric_total",
       "Description of what this metric tracks",
       labelnames=["label1", "label2"],
       registry=_registry,
   )
   ```

2. Add a module-level `record_*` / `observe_*` / `set_*` recorder next to it and
   export it — a metric without a recorder is invisible to callers and joins the
   dead set.
3. Call the recorder from the owning service. Prefer the component that owns the
   number: the client that made the call, the worker that spent the time.
4. Re-run `uv run python scripts/audit_grafana_queries.py` and the dashboard
   panels you touched.
5. Update this page: a family belongs in the live table or in
   [Defined, not emitted](#defined-not-emitted),
   and the distinction is what makes this page worth reading.

## See Also

- [Container Orchestration](../deployment/container-orchestration.md) - which targets exist and how health checks gate them
- [GPU Memory Limits](../deployment/gpu-memory-limits.md) - what the GPU panels are actually measuring
- [YOLO26 Deployment Guide](../deployment/yolo26-migration.md) - the detector behind `service="yolo26"`
- [Profiling Guide](./profiling.md) - Pyroscope and request-level profiling
