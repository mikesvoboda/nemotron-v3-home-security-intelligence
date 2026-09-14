# HSI Metrics Coverage

This document maps all HSI (Home Security Intelligence) Prometheus metrics to their corresponding Grafana dashboard panels.

## Overview

HSI exposes Prometheus metrics for comprehensive system observability. Metrics follow these naming conventions:

- Prefix: `hsi_` (Home Security Intelligence)
- Counters end with `_total`
- Histograms/durations end with `_seconds`
- Gauges use descriptive names without suffix

Metrics are defined in `/backend/core/metrics.py` (Prometheus) and `/backend/core/otel_metrics.py` (OpenTelemetry).

---

## Pipeline Stage Metrics

| Metric                       | Type      | Labels  | Dashboard    | Panel                                              | Description                                          |
| ---------------------------- | --------- | ------- | ------------ | -------------------------------------------------- | ---------------------------------------------------- |
| `hsi_stage_duration_seconds` | Histogram | `stage` | Consolidated | Pipeline Stage Latency, Stage Duration P50/P95/P99 | Duration of pipeline stages (detect, batch, analyze) |
| `hsi_detect_latency_p95_ms`  | Gauge     | -       | Consolidated | Detection Latency                                  | Pre-calculated P95 detection latency in milliseconds |

**Stage Labels:** `detect`, `batch`, `analyze`, `watch`

---

## Detection Metrics

| Metric                                         | Type      | Labels         | Dashboard    | Panel                                | Description                                    |
| ---------------------------------------------- | --------- | -------------- | ------------ | ------------------------------------ | ---------------------------------------------- |
| `hsi_detections_processed_total`               | Counter   | -              | Consolidated | Detection Rate, Event/Detection Rate | Total detections processed by YOLO26           |
| `hsi_detections_by_class_total`                | Counter   | `object_class` | Consolidated | Detections by Class                  | Detections by object class (person, car, etc.) |
| `hsi_detection_confidence`                     | Histogram | -              | Consolidated | Average Confidence                   | Detection confidence scores (0.0-1.0)          |
| `hsi_detections_filtered_low_confidence_total` | Counter   | -              | Consolidated | Filtered Detections                  | Detections filtered due to low confidence      |
| `hsi_detection_queue_depth`                    | Gauge     | -              | Consolidated | Detection Queue Depth                | Images waiting in detection queue              |

---

## Event Metrics

| Metric                          | Type    | Labels                      | Dashboard    | Panel               | Description                   |
| ------------------------------- | ------- | --------------------------- | ------------ | ------------------- | ----------------------------- |
| `hsi_events_created_total`      | Counter | -                           | Consolidated | Event Rate          | Total security events created |
| `hsi_events_by_camera_total`    | Counter | `camera_id`, `camera_name`  | Consolidated | Events by Camera    | Events per camera             |
| `hsi_events_reviewed_total`     | Counter | -                           | Consolidated | Events Reviewed     | Events marked as reviewed     |
| `hsi_events_acknowledged_total` | Counter | `camera_name`, `risk_level` | Consolidated | Events Acknowledged | Events acknowledged by users  |

---

## Risk Analysis Metrics

| Metric                           | Type      | Labels     | Dashboard               | Panel                                      | Description                                        |
| -------------------------------- | --------- | ---------- | ----------------------- | ------------------------------------------ | -------------------------------------------------- |
| `hsi_risk_score`                 | Histogram | -          | Consolidated, Analytics | Average Risk Score, Risk Score Trend       | Risk score distribution (0-100)                    |
| `hsi_events_by_risk_level_total` | Counter   | `level`    | Consolidated, Analytics | Events by Risk Level, High/Critical Alerts | Events by risk level (low, medium, high, critical) |
| `hsi_prompt_template_used_total` | Counter   | `template` | Consolidated            | Prompt Templates Used                      | Prompt template usage (basic, enriched, vision)    |

**Risk Levels:** `low`, `medium`, `high`, `critical`

---

## AI Service Request Metrics

| Metric                            | Type      | Labels    | Dashboard    | Panel                            | Description                                                     |
| --------------------------------- | --------- | --------- | ------------ | -------------------------------- | --------------------------------------------------------------- |
| `hsi_ai_request_duration_seconds` | Histogram | `service` | Consolidated | YOLO26/Nemotron/Florence Latency | Duration of AI service requests                                 |
| `hsi_yolo26_inference_seconds`    | Histogram | -         | AI Services  | Inference Latency Percentiles    | YOLO26 detection with optimized buckets                         |
| `hsi_nemotron_inference_seconds`  | Histogram | -         | Consolidated | Nemotron Inference Latency       | Nemotron LLM with optimized buckets                             |
| `hsi_florence_inference_seconds`  | Histogram | -         | AI Services  | Florence Latency                 | Florence vision-language with optimized buckets                 |
| `hsi_florence_task_total`         | Counter   | `task`    | Consolidated | Florence Tasks                   | Florence task invocations (caption, ocr, detect, dense_caption) |

**Services:** `yolo26`, `nemotron`, `florence`, `clip`

---

## Enrichment Model Metrics

| Metric                                  | Type      | Labels     | Dashboard    | Panel                    | Description                                   |
| --------------------------------------- | --------- | ---------- | ------------ | ------------------------ | --------------------------------------------- |
| `hsi_enrichment_model_calls_total`      | Counter   | `model`    | Consolidated | Enrichment Model Calls   | Enrichment model invocations                  |
| `hsi_enrichment_model_duration_seconds` | Histogram | `model`    | Consolidated | Enrichment Model Latency | Model inference duration                      |
| `hsi_enrichment_model_errors_total`     | Counter   | `model`    | Consolidated | Enrichment Errors        | Enrichment model errors                       |
| `hsi_enrichment_success_rate`           | Gauge     | `model`    | Consolidated | Success Rate             | Success rate per model (0.0-1.0)              |
| `hsi_enrichment_partial_batches_total`  | Counter   | -          | -            | -                        | Batches with partial enrichment               |
| `hsi_enrichment_failures_total`         | Counter   | `model`    | -            | -                        | Enrichment model failures                     |
| `hsi_enrichment_batch_status_total`     | Counter   | `status`   | -            | -                        | Batch status (full, partial, failed, skipped) |
| `hsi_enrichment_retry_total`            | Counter   | `endpoint` | -            | -                        | Retry attempts by endpoint                    |

**Models:** `brisque`, `brisque-quality`, `weather`, `weather-classification`, `depth`, `vehicle-damage-detection`, and others

---

## Queue and Pipeline Metrics

| Metric                               | Type    | Labels                 | Dashboard    | Panel                | Description                        |
| ------------------------------------ | ------- | ---------------------- | ------------ | -------------------- | ---------------------------------- |
| `hsi_analysis_queue_depth`           | Gauge   | -                      | Consolidated | Analysis Queue Depth | Batches waiting in analysis queue  |
| `hsi_dlq_depth`                      | Gauge   | `queue_name`           | -            | -                    | Dead letter queue depth            |
| `hsi_queue_overflow_total`           | Counter | `queue_name`, `policy` | Consolidated | Queue Overflow       | Queue overflow events              |
| `hsi_queue_items_moved_to_dlq_total` | Counter | `queue_name`           | Consolidated | Items Moved to DLQ   | Items moved to dead-letter queue   |
| `hsi_queue_items_dropped_total`      | Counter | `queue_name`           | Consolidated | Items Dropped        | Items dropped (drop_oldest policy) |
| `hsi_queue_items_rejected_total`     | Counter | `queue_name`           | Consolidated | Items Rejected       | Items rejected (reject policy)     |
| `hsi_pipeline_errors_total`          | Counter | `error_type`           | Consolidated | Pipeline Errors      | Pipeline errors by type            |

---

## Worker Metrics

| Metric                                         | Type      | Labels                           | Dashboard    | Panel                    | Description                                                             |
| ---------------------------------------------- | --------- | -------------------------------- | ------------ | ------------------------ | ----------------------------------------------------------------------- |
| `hsi_worker_restarts_total`                    | Counter   | `worker_name`                    | Consolidated | Worker Restarts          | Total worker restarts                                                   |
| `hsi_worker_crashes_total`                     | Counter   | `worker_name`                    | Consolidated | Worker Crashes           | Total worker crashes                                                    |
| `hsi_worker_max_restarts_exceeded_total`       | Counter   | `worker_name`                    | -            | -                        | Times max restart limit exceeded                                        |
| `hsi_worker_status`                            | Gauge     | `worker_name`                    | -            | -                        | Worker status (0=stopped, 1=running, 2=crashed, 3=restarting, 4=failed) |
| `hsi_worker_active_count`                      | Gauge     | -                                | Consolidated | Active Workers           | Workers currently active                                                |
| `hsi_worker_busy_count`                        | Gauge     | -                                | Consolidated | Busy Workers             | Workers processing tasks                                                |
| `hsi_worker_idle_count`                        | Gauge     | -                                | Consolidated | Idle Workers             | Workers idle                                                            |
| `hsi_pipeline_worker_restarts_total`           | Counter   | `worker_name`, `reason_category` | Consolidated | Pipeline Worker Restarts | Pipeline worker restarts by reason                                      |
| `hsi_pipeline_worker_restart_duration_seconds` | Histogram | `worker_name`                    | -            | -                        | Restart operation duration                                              |
| `hsi_pipeline_worker_state`                    | Gauge     | `worker_name`                    | Consolidated | Pipeline Worker State    | Worker state (0=stopped, 1=running, 2=restarting, 3=failed)             |
| `hsi_pipeline_worker_consecutive_failures`     | Gauge     | `worker_name`                    | Consolidated | Consecutive Failures     | Consecutive worker failures                                             |
| `hsi_pipeline_worker_uptime_seconds`           | Gauge     | `worker_name`                    | Consolidated | Worker Uptime            | Uptime since last successful start                                      |

---

## LLM Token and Cost Metrics

| Metric                               | Type      | Labels      | Dashboard    | Panel                    | Description                             |
| ------------------------------------ | --------- | ----------- | ------------ | ------------------------ | --------------------------------------- |
| `hsi_nemotron_tokens_input_total`    | Counter   | `camera_id` | Consolidated | Input Tokens             | Total input tokens sent to Nemotron     |
| `hsi_nemotron_tokens_output_total`   | Counter   | `camera_id` | Consolidated | Output Tokens            | Total output tokens received            |
| `hsi_nemotron_tokens_per_second`     | Gauge     | -           | Consolidated | Token Throughput         | Current token throughput                |
| `hsi_nemotron_token_cost_usd_total`  | Counter   | `camera_id` | Consolidated | Token Cost               | Estimated cost for token usage          |
| `hsi_llm_context_utilization`        | Histogram | -           | -            | -                        | Context window utilization (0.0-1.0+)   |
| `hsi_llm_context_utilization_ratio`  | Gauge     | `model`     | Consolidated | Context Utilization      | Current context utilization ratio       |
| `hsi_prompts_truncated_total`        | Counter   | -           | Consolidated | Prompts Truncated        | Prompts requiring truncation            |
| `hsi_prompts_high_utilization_total` | Counter   | -           | Consolidated | High Utilization Prompts | Prompts exceeding utilization threshold |

---

## Cost Tracking Metrics

| Metric                              | Type    | Labels      | Dashboard    | Panel              | Description                               |
| ----------------------------------- | ------- | ----------- | ------------ | ------------------ | ----------------------------------------- |
| `hsi_gpu_seconds_total`             | Counter | `model`     | -            | -                  | GPU time consumed by AI models            |
| `hsi_estimated_cost_usd_total`      | Counter | `service`   | -            | -                  | Estimated cost based on cloud equivalents |
| `hsi_event_analysis_cost_usd_total` | Counter | `camera_id` | -            | -                  | Cost per event analysis                   |
| `hsi_daily_cost_usd`                | Gauge   | -           | Consolidated | Daily Cost         | Current daily estimated cost              |
| `hsi_monthly_cost_usd`              | Gauge   | -           | Consolidated | Monthly Cost       | Current monthly estimated cost            |
| `hsi_budget_utilization_ratio`      | Gauge   | `period`    | Consolidated | Budget Utilization | Budget utilization ratio (daily, monthly) |
| `hsi_budget_exceeded_total`         | Counter | `period`    | -            | -                  | Times budget threshold exceeded           |
| `hsi_cost_per_detection_usd`        | Gauge   | -           | Consolidated | Cost per Detection | Average cost per detection                |
| `hsi_cost_per_event_usd`            | Gauge   | -           | Consolidated | Cost per Event     | Average cost per security event           |

---

## Cache Metrics

| Metric                               | Type    | Labels                 | Dashboard | Panel | Description                   |
| ------------------------------------ | ------- | ---------------------- | --------- | ----- | ----------------------------- |
| `hsi_cache_hits_total`               | Counter | `cache_type`           | -         | -     | Cache hits                    |
| `hsi_cache_misses_total`             | Counter | `cache_type`           | -         | -     | Cache misses                  |
| `hsi_cache_invalidations_total`      | Counter | `cache_type`, `reason` | -         | -     | Cache invalidations           |
| `hsi_cache_stale_hits_total`         | Counter | `cache_type`           | -         | -     | Stale cache hits (SWR)        |
| `hsi_cache_background_refresh_total` | Counter | `cache_type`, `status` | -         | -     | Background refresh operations |

**Cache Types:** `event_stats`, `cameras`, `system`, `events`

---

## Redis Pool Metrics

| Metric                     | Type  | Labels      | Dashboard | Panel | Description                |
| -------------------------- | ----- | ----------- | --------- | ----- | -------------------------- |
| `hsi_redis_pool_size`      | Gauge | `pool_type` | -         | -     | Redis connection pool size |
| `hsi_redis_pool_available` | Gauge | `pool_type` | -         | -     | Available pool connections |
| `hsi_redis_pool_in_use`    | Gauge | `pool_type` | -         | -     | Connections in use         |

---

## Video Analytics - Object Tracking Metrics

| Metric                          | Type      | Labels                     | Dashboard       | Panel                                | Description                                    |
| ------------------------------- | --------- | -------------------------- | --------------- | ------------------------------------ | ---------------------------------------------- |
| `hsi_tracks_created_total`      | Counter   | `camera_id`                | Video Analytics | Tracks Created (1h)                  | Object tracks created                          |
| `hsi_tracks_lost_total`         | Counter   | `camera_id`, `reason`      | Video Analytics | Tracks Lost (1h), Track Loss Reasons | Tracks lost (timeout, out_of_frame, occlusion) |
| `hsi_tracks_reidentified_total` | Counter   | `camera_id`                | Video Analytics | Tracks Reidentified (1h)             | Tracks reidentified after being lost           |
| `hsi_track_duration_seconds`    | Histogram | `camera_id`, `entity_type` | Video Analytics | Track Duration P95                   | Duration from creation to loss                 |
| `hsi_track_active_count`        | Gauge     | `camera_id`                | Video Analytics | Active Tracks                        | Current active tracks                          |

**Track Loss Reasons:** `timeout`, `out_of_frame`, `occlusion`

---

## Video Analytics - Zone Monitoring Metrics

| Metric                        | Type      | Labels                                | Dashboard       | Panel                                  | Description                           |
| ----------------------------- | --------- | ------------------------------------- | --------------- | -------------------------------------- | ------------------------------------- |
| `hsi_zone_crossings_total`    | Counter   | `zone_id`, `direction`, `entity_type` | Video Analytics | Zone Entries, Zone Crossings Over Time | Zone boundary crossings (enter, exit) |
| `hsi_zone_intrusions_total`   | Counter   | `zone_id`, `severity`                 | Video Analytics | Zone Intrusions (1h)                   | Zone intrusion alerts                 |
| `hsi_zone_occupancy`          | Gauge     | `zone_id`                             | Video Analytics | Current Zone Occupancy                 | Current entities in zone              |
| `hsi_zone_dwell_time_seconds` | Histogram | `zone_id`                             | Video Analytics | Zone Dwell Time P95                    | Time spent in zone                    |

**Zone Directions:** `enter`, `exit`
**Severity Levels:** `low`, `medium`, `high`

---

## Video Analytics - Loitering Detection Metrics

| Metric                             | Type      | Labels                 | Dashboard       | Panel                                             | Description                |
| ---------------------------------- | --------- | ---------------------- | --------------- | ------------------------------------------------- | -------------------------- |
| `hsi_loitering_alerts_total`       | Counter   | `camera_id`, `zone_id` | Video Analytics | Loitering Alerts (1h), Loitering Alerts Over Time | Loitering alerts generated |
| `hsi_loitering_dwell_time_seconds` | Histogram | `camera_id`            | Video Analytics | Median Loitering Duration                         | Loitering dwell time       |

---

## Video Analytics - Action Recognition Metrics

| Metric                                    | Type      | Labels                     | Dashboard       | Panel                                        | Description                           |
| ----------------------------------------- | --------- | -------------------------- | --------------- | -------------------------------------------- | ------------------------------------- |
| `hsi_action_recognition_total`            | Counter   | `action_type`, `camera_id` | Video Analytics | Actions Recognized, Actions by Type          | Actions recognized by type            |
| `hsi_action_recognition_confidence`       | Histogram | `action_type`              | Video Analytics | Median Confidence, Confidence by Action Type | Action recognition confidence scores  |
| `hsi_action_recognition_duration_seconds` | Histogram | -                          | Video Analytics | Inference Latency P95                        | Action recognition inference duration |

**Action Types:** `walking`, `loitering`, `fighting`, and others

---

## Video Analytics - Face Recognition Metrics

| Metric                                | Type      | Labels                      | Dashboard           | Panel                                                          | Description                                   |
| ------------------------------------- | --------- | --------------------------- | ------------------- | -------------------------------------------------------------- | --------------------------------------------- |
| `hsi_face_detections_total`           | Counter   | `camera_id`, `match_status` | Video Analytics     | Faces Detected, Known/Unknown Faces, Face Detections Over Time | Total faces detected                          |
| `hsi_face_quality_score`              | Histogram | -                           | Video Analytics     | Median Face Quality, Face Quality Score Distribution           | Face quality scores                           |
| `hsi_face_embeddings_generated_total` | Counter   | `match_status`              | Video Analytics, AI | Known Faces (1h), Unknown Faces (1h), Known vs Unknown Faces   | Face embeddings generated (NEM-4143)          |
| `hsi_face_recognition_confidence`     | Histogram | -                           | AI Services         | Recognition Confidence Distribution                            | Face recognition confidence scores (NEM-4143) |
| `hsi_face_matches_total`              | Counter   | `person_id`                 | -                   | -                                                              | Face matches against known persons            |

**Match Status:** `known`, `unknown`

---

## GPU Metrics

| Metric                                 | Type    | Labels | Dashboard    | Panel                   | Description                    |
| -------------------------------------- | ------- | ------ | ------------ | ----------------------- | ------------------------------ |
| `hsi_gpu_utilization`                  | Gauge   | -      | Consolidated | GPU Utilization         | GPU compute utilization %      |
| `hsi_gpu_temperature`                  | Gauge   | -      | Consolidated | GPU Temperature         | GPU temperature (Celsius)      |
| `hsi_gpu_memory_used_mb`               | Gauge   | -      | Consolidated | GPU Memory Used         | GPU memory used (MB)           |
| `hsi_gpu_memory_total_mb`              | Gauge   | -      | Consolidated | GPU Memory Total        | Total GPU memory (MB)          |
| `hsi_gpu_sm_clock_mhz`                 | Gauge   | -      | Consolidated | SM Clock                | Current SM clock speed         |
| `hsi_gpu_sm_clock_max_mhz`             | Gauge   | -      | Consolidated | SM Clock Max            | Max SM clock speed             |
| `hsi_gpu_memory_clock_mhz`             | Gauge   | -      | Consolidated | Memory Clock            | Current memory clock           |
| `hsi_gpu_memory_clock_max_mhz`         | Gauge   | -      | Consolidated | Memory Clock Max        | Max memory clock               |
| `hsi_gpu_power_limit_watts`            | Gauge   | -      | Consolidated | Power Limit             | GPU power limit (Watts)        |
| `hsi_gpu_throttle_reasons`             | Gauge   | -      | Consolidated | Throttle Reasons        | GPU throttling reasons         |
| `hsi_gpu_pstate`                       | Gauge   | -      | Consolidated | P-State                 | GPU performance state          |
| `hsi_gpu_fan_speed`                    | Gauge   | -      | Consolidated | Fan Speed               | GPU fan speed %                |
| `hsi_gpu_compute_processes`            | Gauge   | -      | Consolidated | Compute Processes       | Active compute processes       |
| `hsi_gpu_pcie_tx_throughput_kbs`       | Gauge   | -      | Consolidated | PCIe TX Throughput      | PCIe transmit throughput       |
| `hsi_gpu_pcie_rx_throughput_kbs`       | Gauge   | -      | Consolidated | PCIe RX Throughput      | PCIe receive throughput        |
| `hsi_gpu_encoder_utilization`          | Gauge   | -      | Consolidated | Encoder Utilization     | Video encoder utilization      |
| `hsi_gpu_decoder_utilization`          | Gauge   | -      | Consolidated | Decoder Utilization     | Video decoder utilization      |
| `hsi_gpu_memory_bandwidth_utilization` | Gauge   | -      | Consolidated | Memory Bandwidth Util   | Memory bandwidth utilization   |
| `hsi_gpu_temp_slowdown_threshold`      | Gauge   | -      | Consolidated | Temp Slowdown Threshold | Temperature slowdown threshold |
| `hsi_gpu_pcie_link_gen`                | Gauge   | -      | Consolidated | PCIe Link Gen           | PCIe link generation           |
| `hsi_gpu_pcie_link_width`              | Gauge   | -      | Consolidated | PCIe Link Width         | PCIe link width                |
| `hsi_gpu_pcie_replay_counter`          | Counter | -      | Consolidated | PCIe Replay Counter     | PCIe replay error counter      |
| `hsi_gpu_bar1_used_mb`                 | Gauge   | -      | Consolidated | BAR1 Memory Used        | BAR1 memory aperture used      |

---

## System Metrics

| Metric               | Type  | Labels | Dashboard    | Panel         | Description                  |
| -------------------- | ----- | ------ | ------------ | ------------- | ---------------------------- |
| `hsi_uptime_seconds` | Gauge | -      | Consolidated | System Uptime | System uptime in seconds     |
| `hsi_total_cameras`  | Gauge | -      | Consolidated | Total Cameras | Number of configured cameras |
| `hsi_total_events`   | Gauge | -      | Consolidated | Total Events  | Total events in database     |

---

## Circuit Breaker Metrics

| Metric                            | Type    | Labels    | Dashboard    | Panel                 | Description                                   |
| --------------------------------- | ------- | --------- | ------------ | --------------------- | --------------------------------------------- |
| `hsi_circuit_breaker_state`       | Gauge   | `breaker` | Consolidated | Circuit Breaker State | Breaker state (0=closed, 1=open, 2=half_open) |
| `hsi_circuit_breaker_trips_total` | Counter | `breaker` | Consolidated | Circuit Breaker Trips | Total breaker trips                           |

---

## Real User Monitoring (RUM) Metrics

| Metric                           | Type      | Labels | Dashboard    | Panel                        | Description                    |
| -------------------------------- | --------- | ------ | ------------ | ---------------------------- | ------------------------------ |
| `hsi_rum_page_load_time_seconds` | Histogram | -      | Consolidated | Page Load Time P75           | Browser page load time         |
| `hsi_rum_fcp_seconds`            | Histogram | -      | Consolidated | First Contentful Paint P75   | First Contentful Paint (FCP)   |
| `hsi_rum_lcp_seconds`            | Histogram | -      | Consolidated | Largest Contentful Paint P75 | Largest Contentful Paint (LCP) |
| `hsi_rum_cls_bucket`             | Histogram | -      | Consolidated | Cumulative Layout Shift P75  | Cumulative Layout Shift (CLS)  |

---

## OpenTelemetry Metrics (otel_metrics.py)

These metrics use OpenTelemetry instrumentation and are available when OTEL_METRICS_ENABLED=True.

### Circuit Breaker OTel Metrics

| Metric                        | Type    | Labels                              | Description                                   |
| ----------------------------- | ------- | ----------------------------------- | --------------------------------------------- |
| `circuit_breaker.state`       | Gauge   | `breaker`                           | Current state (0=closed, 1=open, 2=half_open) |
| `circuit_breaker.transitions` | Counter | `breaker`, `from_state`, `to_state` | State transitions                             |
| `circuit_breaker.failures`    | Counter | `breaker`                           | Failures recorded                             |
| `circuit_breaker.successes`   | Counter | `breaker`                           | Successes recorded                            |
| `circuit_breaker.rejected`    | Counter | `breaker`                           | Calls rejected                                |

### AI Model Latency OTel Histograms

| Metric                     | Type      | Labels                                                      | Description                   |
| -------------------------- | --------- | ----------------------------------------------------------- | ----------------------------- |
| `ai.detection.latency`     | Histogram | `model.version`, `batch.size`, `gpu.id`                     | YOLO26 inference latency (ms) |
| `ai.nemotron.latency`      | Histogram | `model.version`, `batch.size`, `gpu.id`, `tokens.generated` | Nemotron LLM latency (ms)     |
| `ai.florence.latency`      | Histogram | `model.version`, `batch.size`, `gpu.id`, `task.type`        | Florence latency (ms)         |
| `ai.pipeline.latency`      | Histogram | `camera.id`, `pipeline.stage`, `detection.count`            | Total pipeline latency (ms)   |
| `ai.batch.processing_time` | Histogram | `batch.size`, `camera.count`, `batch.id`                    | Batch processing time (ms)    |

---

## Metrics Not Yet Visualized

The following metrics exist in the codebase but do not have dedicated dashboard panels:

| Metric                                         | Reason                                           |
| ---------------------------------------------- | ------------------------------------------------ |
| `hsi_dlq_depth`                                | Alert-based monitoring only                      |
| `hsi_enrichment_partial_batches_total`         | Detailed operational metric                      |
| `hsi_enrichment_failures_total`                | Uses `hsi_enrichment_model_errors_total` instead |
| `hsi_enrichment_batch_status_total`            | Detailed operational metric                      |
| `hsi_enrichment_retry_total`                   | Detailed operational metric                      |
| `hsi_worker_max_restarts_exceeded_total`       | Alert-based monitoring only                      |
| `hsi_worker_status`                            | Uses `hsi_pipeline_worker_state` instead         |
| `hsi_pipeline_worker_restart_duration_seconds` | Detailed operational metric                      |
| `hsi_gpu_seconds_total`                        | Cost calculation intermediate                    |
| `hsi_estimated_cost_usd_total`                 | Cost calculation intermediate                    |
| `hsi_event_analysis_cost_usd_total`            | Cost calculation intermediate                    |
| `hsi_budget_exceeded_total`                    | Alert-based monitoring only                      |
| `hsi_cache_*`                                  | Detailed operational metrics                     |
| `hsi_redis_pool_*`                             | Detailed operational metrics                     |
| `hsi_face_embeddings_generated_total`          | Now dashboarded (NEM-4143) - Known/Unknown faces |
| `hsi_face_matches_total`                       | Detailed operational metric                      |
| All OpenTelemetry metrics                      | Exported to OTel backend (Tempo/Jaeger)          |

---

## Dashboard Reference

| Dashboard                   | UID               | Purpose                          | Primary Metrics                                                               |
| --------------------------- | ----------------- | -------------------------------- | ----------------------------------------------------------------------------- |
| **Consolidated**            | `consolidated`    | Main operations dashboard        | Pipeline, AI services, GPU, workers, costs                                    |
| **AI Services**             | `ai-services`     | YOLO26 detection monitoring      | `yolo26_*` (from ai/yolo26 service)                                           |
| **HSI Analytics**           | `hsi-analytics`   | Events and risk analysis         | Backend API data (JSON datasource)                                            |
| **Video Analytics**         | `video-analytics` | Tracking, zones, faces, actions  | `hsi_tracks_*`, `hsi_zone_*`, `hsi_face_*`, `hsi_action_*`, `hsi_loitering_*` |
| **HSI Profiling**           | `hsi-profiling`   | Continuous profiling (Pyroscope) | CPU and memory flame graphs                                                   |
| **HSI System Logs**         | `hsi-logs`        | Centralized logging (Loki)       | Log volume, error patterns                                                    |
| **HSI Distributed Tracing** | `hsi-tracing`     | Request tracing (Jaeger)         | Trace search and analysis                                                     |

---

## Adding New Metrics

When adding new metrics:

1. Define the metric in `/backend/core/metrics.py` following naming conventions
2. Add recording method to `MetricsService` class
3. Call the method from relevant service code
4. Add to appropriate Grafana dashboard(s)
5. Update this documentation

Example metric definition:

```python
MY_NEW_METRIC = Counter(
    "hsi_my_new_metric_total",
    "Description of what this metric tracks",
    labelnames=["label1", "label2"],
    registry=_registry,
)
```
