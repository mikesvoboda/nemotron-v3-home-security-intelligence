# Grafana Dashboards Directory - Agent Guide

## Purpose

This directory contains Grafana dashboard JSON definitions that are automatically provisioned when Grafana starts. Dashboards visualize the Home Security Intelligence system's health, performance, and AI pipeline metrics.

## Directory Contents

```
dashboards/
  AGENTS.md           # This file
  ai-services.json    # YOLO26 and AI services monitoring (inference workload, GPU, detections)
  api-health.json     # API health, deprecation tracking, and error monitoring
  consolidated.json   # Main unified monitoring dashboard
  analytics.json      # Analytics dashboard
  hsi-profiling.json  # Profiling dashboard
  logs.json           # Logs dashboard
  scene-ocr.json      # Scene OCR text extraction and service provider matching
  tracing.json        # Tracing dashboard
```

## Key Files

### ai-services.json

**Purpose:** AI services monitoring dashboard. AI serving is consolidated in
ai-gateway (Triton Inference Server): the standalone containers (ai-yolo26,
ai-florence, ai-clip, ai-enrichment, ai-enrichment-light) are retired, so per-service
`yolo26_*` / `clip_*` / `florence_inference_*` / `enrichment_*` series are dead. Triton
native `nv_*` metrics come from the `triton-metrics` scrape job (ai-gateway:8002);
model health comes from blackbox probes of the gateway routers; percentiles come from
the backend's client-side `hsi_ai_request_duration_seconds` histogram.

**Dashboard UID:** `ai-services`

**Panels by Section:**

| Row                              | Panel                                                | Type       | Data Source | Metric                                                               |
| -------------------------------- | ---------------------------------------------------- | ---------- | ----------- | -------------------------------------------------------------------- |
| YOLO26 Overview                  | Documentation                                        | text       | -           | Gateway-topology notes, baselines and thresholds                     |
| YOLO26 Overview                  | Model Status (gateway health probe)                  | stat       | Prometheus  | probe_success{job="blackbox-http-2xx", model="yolo26"}               |
| YOLO26 Overview                  | Inference Latency (mean)                             | stat       | Prometheus  | nv_inference_request_duration_us / nv_inference_request_success      |
| YOLO26 Overview                  | Request Rate                                         | stat       | Prometheus  | nv_inference_request_success{model="yolo26"}                         |
| YOLO26 Overview                  | VRAM Usage                                           | stat       | Prometheus  | nv_gpu_memory_used_bytes                                             |
| YOLO26 Overview                  | Errors (5m)                                          | stat       | Prometheus  | nv_inference_request_failure{model="yolo26"}                         |
| YOLO26 Overview                  | GPU Utilization                                      | stat       | Prometheus  | nv_gpu_utilization                                                   |
| YOLO26 Inference Workload        | Inference Throughput                                 | stat       | Prometheus  | nv_inference_request_success{model="yolo26"}                         |
| YOLO26 Inference Workload        | Mean Inference Time                                  | stat       | Prometheus  | nv_inference_request_duration_us / nv_inference_request_success      |
| YOLO26 Inference Workload        | Inference Health (gateway probe)                     | stat       | Prometheus  | probe_success{job="blackbox-http-2xx", model="yolo26"}               |
| YOLO26 Inference Workload        | Detector Call Rate (p95 gate)                        | stat       | Prometheus  | hsi_ai_request_duration_seconds_bucket{service="yolo26"}             |
| YOLO26 Inference Workload        | Detection Rate                                       | stat       | Prometheus  | hsi_detections_processed_total                                       |
| Inference Performance            | Inference Latency Percentiles (backend client)       | timeseries | Prometheus  | hsi_ai_request_duration_seconds_bucket                               |
| Inference Performance            | Request Rate by Endpoint                             | timeseries | Prometheus  | nv_inference_request_success/failure (by model)                      |
| Detection Metrics                | Detections by Class                                  | timeseries | Prometheus  | hsi_detections_by_class_total (by object_class)                      |
| Detection Metrics                | Detection Confidence (median)                        | timeseries | Prometheus  | hsi_detection_confidence_bucket                                      |
| Error Tracking                   | Errors by Type                                       | timeseries | Prometheus  | hsi_pipeline_errors_total (by error_type)                            |
| GPU Resources                    | VRAM Usage Over Time                                 | timeseries | Prometheus  | nv_gpu_memory_used_bytes (by model)                                  |
| GPU Resources                    | GPU Metrics                                          | timeseries | Prometheus  | nv_gpu_utilization, hsi_gpu_temperature, DCGM_FI_DEV_POWER_USAGE     |
| Face Recognition                 | Face Detection Rate                                  | timeseries | Prometheus  | hsi_face_embeddings_generated_total                                  |
| Face Recognition                 | Face Quality Score Distribution                      | timeseries | Prometheus  | hsi_face_quality_score_bucket                                        |
| Face Recognition                 | Face Embedding Time (p95)                            | stat       | Prometheus  | hsi_face_embedding_duration_seconds_bucket                           |
| Face Recognition                 | Known vs Unknown Faces                               | piechart   | Prometheus  | hsi_face_embeddings_generated_total (by match_status)                |
| Face Recognition                 | Detection Count by Camera                            | timeseries | Prometheus  | hsi_face_embeddings_generated_total                                  |
| Face Recognition                 | Recognition Confidence Distribution                  | timeseries | Prometheus  | hsi_face_recognition_confidence_bucket                               |
| Face Recognition                 | Known Faces Database Size                            | stat       | Prometheus  | hsi_known_faces_database_size                                        |
| Enrichment Models                | CLIP Inference Latency (Triton mean + backend pctl)  | timeseries | Prometheus  | nv*inference_request_duration_us/success, hsi_ai_request*...\_bucket |
| Enrichment Models                | Florence-2 Latency (Triton mean + backend pctl)      | timeseries | Prometheus  | nv*inference_request_duration_us/success, hsi_ai_request*...\_bucket |
| Enrichment Models                | Enrichment Throughput                                | timeseries | Prometheus  | nv_inference_request_success (model!~ set-difference)                |
| Enrichment Models                | Enrichment Queue                                     | stat       | Prometheus  | hsi_analysis_queue_depth                                             |
| Action Recognition               | Actions Detected by Type                             | timeseries | Prometheus  | hsi_action_detections_total (by action_type)                         |
| Action Recognition               | Action Confidence Distribution                       | timeseries | Prometheus  | hsi_action_confidence_bucket                                         |
| Action Recognition               | Action Model Error Rate                              | stat       | Prometheus  | hsi_enrichment_model_errors_total / \_calls_total                    |
| Loitering Detection              | Loitering Events by Zone                             | timeseries | Prometheus  | hsi_loitering_events_total                                           |
| Loitering Detection              | Dwell Time Distribution                              | timeseries | Prometheus  | hsi_loitering_dwell_time_seconds_bucket                              |
| Loitering Detection              | Loitering Alerts Rate                                | timeseries | Prometheus  | hsi_loitering_alerts_total                                           |
| Model Warmup                     | Model Load Time                                      | timeseries | Prometheus  | hsi_model_load_duration_seconds (by model)                           |
| Model Warmup                     | Cold Start Latency                                   | timeseries | Prometheus  | hsi_model_cold_start_latency_seconds                                 |
| Model Warmup                     | Model Restarts (24h)                                 | stat       | Prometheus  | hsi_pipeline_worker_restarts_total                                   |
| Florence-2 Vision-Language Model | Florence Model Status (gateway health probe)         | stat       | Prometheus  | probe_success{job="blackbox-http-2xx", model="florence2"}            |
| Florence-2 Vision-Language Model | Florence Latency (P95, backend client-side)          | stat       | Prometheus  | hsi_ai_request_duration_seconds_bucket{service="florence"}           |
| Florence-2 Vision-Language Model | Florence Request Rate                                | stat       | Prometheus  | nv_inference_request_success{model="florence2"}                      |
| Florence-2 Vision-Language Model | Florence GPU Memory                                  | stat       | Prometheus  | nv_gpu_memory_used_bytes{model="florence2"}                          |
| Florence-2 Vision-Language Model | Florence Errors (5m)                                 | stat       | Prometheus  | nv_inference_request_failure{model="florence2"}                      |
| Florence-2 Vision-Language Model | Florence Success Rate                                | stat       | Prometheus  | nv_inference_request_success/failure{model="florence2"}              |
| Florence-2 Vision-Language Model | Florence Inference Latency Percentiles               | timeseries | Prometheus  | hsi_ai_request_duration_seconds_bucket{service=~"florence.\*"}       |
| Florence-2 Vision-Language Model | Florence Request Rate by Endpoint                    | timeseries | Prometheus  | nv_inference_request_success/failure{model="florence2"}              |
| Florence-2 Vision-Language Model | Florence Latency P95 (backend-side only)             | timeseries | Prometheus  | hsi_ai_request_duration_seconds_bucket{service=~"florence.\*"}       |
| Florence-2 Vision-Language Model | Florence Task Distribution                           | piechart   | Prometheus  | hsi_florence_task_total                                              |
| Florence-2 Vision-Language Model | Florence GPU Memory Over Time                        | timeseries | Prometheus  | nv_gpu_memory_used_bytes{model="florence2"}                          |
| Florence-2 Vision-Language Model | Florence Backend Inference Duration                  | timeseries | Prometheus  | hsi_ai_request_duration_seconds_bucket{service=~"florence.\*"}       |
| Florence-2 Vision-Language Model | Florence Task Rate by Type                           | timeseries | Prometheus  | hsi_florence_task_total                                              |
| Gateway Inference Traffic        | Gateway Inference Latency Percentiles (all services) | timeseries | Prometheus  | hsi_ai_inference_duration_seconds_bucket                             |
| Gateway Inference Traffic        | Gateway Request Rate by Service/Endpoint             | timeseries | Prometheus  | hsi_ai_inference_duration_seconds_count                              |
| Gateway Inference Traffic        | Gateway Inference Errors by Service/Endpoint         | timeseries | Prometheus  | hsi_ai_inference_errors_total                                        |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 1 hour
- Timezone: Browser
- Tags: ai, yolo26, inference, gpu, workload, face-recognition, enrichment, action-recognition, loitering, triton, gateway

**Key metrics (post gateway-consolidation):**

Triton native (scrape job `triton-metrics`, ai-gateway:8002/metrics; `model` label):

- `nv_inference_request_success` / `nv_inference_request_failure` - Cumulative request counters per model
- `nv_inference_request_duration_us` - Cumulative inference time (µs). NOT a histogram:
  Triton summary stats are disabled, so only a counter-ratio MEAN exists server-side
  (`rate(duration_us) / (rate(success) + 0.001) / 1e6`). Latency panels must say "mean".
- `nv_inference_queue_duration_us` - Cumulative queue time (µs), same mean-only caveat
- `nv_gpu_utilization`, `nv_gpu_memory_used_bytes` - Server-level GPU metrics

Backend client-side (backend/core/metrics.py, /api/metrics):

- `hsi_ai_request_duration_seconds` - Histogram of AI call duration, label `service`
  (client-side percentiles; no `endpoint` label)
- `hsi_ai_inference_duration_seconds{service,endpoint}` / `hsi_ai_inference_errors_total{service,endpoint}` -
  GATEWAY-side (not client-side) histogram + counter observed by the gateway's
  GatewayMetricsMiddleware (ai/gateway/main.py), scraped from `ai-gateway:8090/metrics`
  via the `ai-gateway-metrics` job. `service` = adapter prefix the route matched
  (`yolo26|clip|florence|enrichment|enrich-lt`; unmatched paths -> `other`), `endpoint` =
  route under it. Health (`/health`, `/…/health`) and `/metrics` requests are NOT observed,
  so `rate()` over these families is EMPTY — not 0 — until first inference traffic:
  dashboard queries must carry `or vector(0)` (or absent-metric tolerance). The counter
  keeps its `_total` suffix in queries. Server-side percentiles exist ONLY here — Triton
  exports mean-only `nv_*` counters and the backend histogram has no `endpoint` label.
- `hsi_detections_processed_total`, `hsi_detections_by_class_total{object_class}` - detection throughput
- `hsi_detection_confidence` - Histogram of detector confidence scores
- `hsi_pipeline_errors_total{error_type}` - Pipeline errors
- `hsi_florence_task_total` - backend-side Florence task counter. `hsi_florence_inference_seconds`
  is DEFINED but never observed (its helpers have no non-test callers), so it exports only
  static zero buckets — never use it for percentiles; use `hsi_ai_request_duration_seconds{service=~"florence.*"}`
- `hsi_action_detections_total` / `hsi_action_confidence` / `hsi_action_corrections_total` - the FED
  action metrics; their only emitter lived in `action_recognition_service.py`, archived with the 2026-09-23
  X-CLIP full removal, so they now export ZERO until a ST-GCN++-era feeder is wired — panels reading them
  carry `or vector(0)` and the feed gap is annotated in the panel descriptions. `hsi_action_recognition_total`,
  `hsi_action_recognition_confidence` and `hsi_action_recognition_duration_seconds` (metrics.py video-analytics
  family) are DEFINED but never `.labels()`'d outside tests, so they are never exported
- `hsi_model_load_duration_seconds{model}`, `hsi_model_cold_start_latency_seconds`,
  `hsi_pipeline_worker_restarts_total` - warmup/restart tracking
- `hsi_gpu_temperature` (json-exporter from /api/system/gpu), `DCGM_FI_DEV_POWER_USAGE` (dcgm-exporter)

Health: `probe_success{job="blackbox-http-2xx", model="..."}` probes the gateway
routers (`ai-gateway:8090/<model>/health`) and the llama.cpp sidecar.

**Deleted panels (no live equivalent, gateway consolidation):** Avg Batch Size,
Batch Size Distribution (no batch-size histogram is exported anywhere now),
`yolo26_model_loaded` / `yolo26_model_inference_healthy` stats (replaced by probes).

### api-health.json

**Purpose:** API health monitoring with deprecation tracking and error rate analysis.

**Dashboard UID:** `hsi-api-health`

**Panels by Section:**

| Row                        | Panel                               | Type       | Data Source | Metric                              |
| -------------------------- | ----------------------------------- | ---------- | ----------- | ----------------------------------- |
| API Deprecation Tracking   | Total Deprecated Calls              | stat       | Prometheus  | hsi_api_deprecated_calls_total      |
| API Deprecation Tracking   | Deprecated Endpoints Count          | stat       | Prometheus  | hsi_api_deprecated_calls_total      |
| API Deprecation Tracking   | Deprecated Calls Rate               | stat       | Prometheus  | hsi_api_deprecated_calls_total      |
| API Deprecation Tracking   | Clients Using Deprecated APIs       | stat       | Prometheus  | hsi_api_deprecated_calls_total      |
| API Deprecation Tracking   | Deprecated Endpoint Usage           | table      | Prometheus  | hsi_api_deprecated_calls_total      |
| API Deprecation Tracking   | Deprecated Endpoint Usage Over Time | timeseries | Prometheus  | hsi_api_deprecated_calls_total      |
| API Error Overview         | Overall Error Rate                  | gauge      | Prometheus  | http_request_duration_seconds_count |
| API Error Overview         | 4xx Client Errors (5m)              | stat       | Prometheus  | http_request_duration_seconds_count |
| API Error Overview         | 5xx Server Errors (5m)              | stat       | Prometheus  | http_request_duration_seconds_count |
| API Error Overview         | Successful Requests (5m)            | stat       | Prometheus  | http_request_duration_seconds_count |
| API Error Overview         | 4xx vs 5xx Error Distribution       | timeseries | Prometheus  | http_request_duration_seconds_count |
| API Error Overview         | Error Rate Trend Over Time          | timeseries | Prometheus  | http_request_duration_seconds_count |
| Error Analysis by Endpoint | Top Endpoints by Error Count (1h)   | table      | Prometheus  | http_request_duration_seconds_count |
| Error Analysis by Endpoint | Top Endpoints by Error Rate         | table      | Prometheus  | http_request_duration_seconds_count |
| Error Details by Status    | Errors by Status Code (1h)          | piechart   | Prometheus  | http_request_duration_seconds_count |
| Error Details by Status    | Error Rate by Status Code Over Time | timeseries | Prometheus  | http_request_duration_seconds_count |
| Request Throughput         | Request Throughput Overview         | timeseries | Prometheus  | http_request_duration_seconds_count |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 1 hour
- Timezone: Browser

**Prometheus Metrics Used:**

- `hsi_api_deprecated_calls_total` - Counter for deprecated API endpoint calls (labels: endpoint, client_id)
- `http_request_duration_seconds_count` - HTTP request count from Prometheus middleware (labels: method, handler, status, http_route)

### consolidated.json

**Purpose:** Main unified monitoring dashboard for the AI security pipeline.

**Dashboard UID:** `hsi-consolidated`

**Panels by Section:**

| Row                       | Panel                                                | Type       | Data Source | Endpoint                                          |
| ------------------------- | ---------------------------------------------------- | ---------- | ----------- | ------------------------------------------------- |
| System Overview           | System Health                                        | stat       | Backend-API | /api/system/health                                |
| System Overview           | Total Cameras                                        | stat       | Backend-API | /api/system/stats                                 |
| System Overview           | Total Events                                         | stat       | Backend-API | /api/system/stats                                 |
| System Overview           | Total Detections                                     | stat       | Backend-API | /api/system/stats                                 |
| System Overview           | Uptime                                               | stat       | Backend-API | /api/system/stats                                 |
| Queue Depths              | Detection Queue                                      | stat       | Backend-API | /api/system/telemetry                             |
| Queue Depths              | Analysis Queue                                       | stat       | Backend-API | /api/system/telemetry                             |
| Queue Depths              | Over Time                                            | timeseries | Backend-API | /api/system/telemetry                             |
| Pipeline Latencies        | Watch P95                                            | stat       | Backend-API | /api/system/telemetry                             |
| Pipeline Latencies        | Detect P95                                           | stat       | Backend-API | /api/system/telemetry                             |
| Pipeline Latencies        | Batch P95                                            | stat       | Backend-API | /api/system/telemetry                             |
| Pipeline Latencies        | Analysis P95                                         | stat       | Backend-API | /api/system/telemetry                             |
| Pipeline Latencies        | Histogram                                            | barchart   | Backend-API | /api/system/telemetry                             |
| GPU Statistics            | GPU Utilization                                      | gauge      | Backend-API | /api/system/gpu                                   |
| GPU Statistics            | GPU Temperature                                      | stat       | Backend-API | /api/system/gpu                                   |
| GPU Statistics            | Memory Used                                          | stat       | Backend-API | /api/system/gpu                                   |
| GPU Statistics            | Inference FPS                                        | stat       | Prometheus  | hsi_inference_fps (json-exporter /api/system/gpu) |
| Service Health            | Database                                             | stat       | Backend-API | /api/system/health                                |
| Service Health            | Redis                                                | stat       | Backend-API | /api/system/health                                |
| Service Health            | AI Services                                          | stat       | Backend-API | /api/system/health                                |
| Service Health            | Readiness                                            | stat       | Backend-API | /api/system/health/ready                          |
| Gateway Inference Traffic | Gateway Inference Latency Percentiles (all services) | timeseries | Prometheus  | hsi_ai_inference_duration_seconds_bucket          |
| Gateway Inference Traffic | Gateway Request Rate by Service/Endpoint             | timeseries | Prometheus  | hsi_ai_inference_duration_seconds_count           |
| Gateway Inference Traffic | Gateway Inference Errors by Service/Endpoint         | timeseries | Prometheus  | hsi_ai_inference_errors_total                     |

The **Gateway Inference Traffic** row mirrors ai-services.json's same-named row
(the Ops view previously had zero gateway-traffic panels while ai-services.json
was the sole consumer of the gateway's `hsi_ai_inference_*` families). Keep the
two copies' queries identical — including the `or vector(0)` suffix: health and
`/metrics` requests are deliberately NOT observed by the gateway's
GatewayMetricsMiddleware (ai/gateway/main.py), so `rate()` over these families
is EMPTY — not 0 — until the first inference request, and the panels must show
0 rather than No-data. The "Panels by Section" tables in this file list the
headline panels per row, not an exhaustive panel inventory.

**Dashboard Settings:**

- Auto-refresh: 5 seconds
- Default time range: Last 15 minutes
- Timezone: Browser

### analytics.json

**Purpose:** Analytics dashboard for system metrics and trends.

**Dashboard UID:** `hsi-analytics`

**Panels by Section:**

| Row                             | Panel                                  | Type       | Data Source | Metric/Endpoint                      |
| ------------------------------- | -------------------------------------- | ---------- | ----------- | ------------------------------------ |
| Executive Summary               | Total Events                           | stat       | Backend-API | /api/events/stats                    |
| Executive Summary               | Total Detections                       | stat       | Backend-API | /api/detections/stats                |
| Executive Summary               | Average Confidence                     | stat       | Backend-API | /api/detections/stats                |
| Executive Summary               | High Risk Events                       | stat       | Backend-API | /api/events/stats                    |
| Detection Trends                | Detection Trend Over Time              | timeseries | Backend-API | /api/detections/stats                |
| Risk Analysis                   | Risk Distribution                      | piechart   | Backend-API | /api/events/stats                    |
| Risk Analysis                   | Risk History                           | timeseries | Backend-API | /api/events/stats                    |
| Camera & Detection Analysis     | Top Cameras by Activity                | barchart   | Backend-API | /api/events/stats                    |
| Camera & Detection Analysis     | Detections by Object Class             | barchart   | Backend-API | /api/detections/stats                |
| High Risk Events                | High Risk Events                       | table      | Backend-API | /api/events                          |
| Real User Monitoring            | Page Load Time                         | timeseries | Prometheus  | hsi_rum_page_load_time_seconds       |
| Real User Monitoring            | First Contentful Paint                 | timeseries | Prometheus  | hsi_rum_fcp_seconds                  |
| Real User Monitoring            | JavaScript Errors                      | timeseries | Prometheus  | hsi_rum_js_errors_total              |
| Real User Monitoring            | Active Sessions                        | stat       | Prometheus  | hsi_rum_active_sessions              |
| Core Web Vitals                 | LCP (Largest Contentful Paint)         | gauge      | Prometheus  | hsi_rum_lcp_seconds                  |
| Core Web Vitals                 | FID (First Input Delay)                | gauge      | Prometheus  | hsi_rum_inp_seconds                  |
| Core Web Vitals                 | CLS (Cumulative Layout Shift)          | gauge      | Prometheus  | hsi_rum_cls                          |
| Core Web Vitals                 | INP (Interaction to Next Paint)        | gauge      | Prometheus  | hsi_rum_inp_seconds                  |
| Database Performance            | Query Latency                          | timeseries | Prometheus  | hsi_db_query_duration_seconds        |
| Database Performance            | Connection Pool                        | timeseries | Prometheus  | hsi_db_pool_connections_active/idle  |
| Database Performance            | Slow Queries                           | timeseries | Prometheus  | hsi_slow_queries_total               |
| Database Performance            | Transactions/sec                       | timeseries | Prometheus  | hsi_db_transactions_total            |
| A/B Testing                     | Documentation                          | text       | -           | -                                    |
| A/B Testing                     | Traffic Distribution                   | piechart   | Prometheus  | hsi_ab_variant_traffic_total         |
| A/B Testing                     | Conversion by Variant                  | barchart   | Prometheus  | hsi_ab_conversions_total             |
| Shadow Prompt Comparison        | Documentation                          | text       | -           | -                                    |
| Shadow Prompt Comparison        | Shadow vs Production Accuracy          | timeseries | Prometheus  | hsi_prompt_accuracy                  |
| Shadow Prompt Comparison        | Response Time Difference               | timeseries | Prometheus  | hsi_prompt_latency_seconds           |
| Shadow Prompt Comparison        | Agreement Rate                         | gauge      | Prometheus  | hsi_prompt_agreement_total           |
| Prompt Context                  | Context Window Usage                   | gauge      | Prometheus  | hsi_prompt_context_used_tokens       |
| Prompt Context                  | Token Count Distribution               | histogram  | Prometheus  | hsi_prompt_input/output_tokens       |
| Prompt Context                  | Context Overflow Events                | timeseries | Prometheus  | hsi_prompt_context_overflow_total    |
| Cost Tracking                   | Daily Cost                             | timeseries | Prometheus  | hsi_llm_cost_dollars_total           |
| Cost Tracking                   | Cost by Model                          | piechart   | Prometheus  | hsi_llm_cost_dollars_total           |
| Cost Tracking                   | Budget Utilization                     | gauge      | Prometheus  | hsi_llm_monthly_budget_dollars       |
| Redis Pool                      | Active Connections                     | timeseries | Prometheus  | hsi_redis_pool_connections_active    |
| Redis Pool                      | Connection Wait Time                   | timeseries | Prometheus  | hsi_redis_pool_wait_seconds          |
| Redis Pool                      | Pool Exhaustion Events                 | timeseries | Prometheus  | hsi_redis_pool_exhaustion_total      |
| Backend-API Analytics Endpoints | Analytics Endpoints Request Rate       | timeseries | Prometheus  | http_request_duration_seconds_count  |
| Backend-API Analytics Endpoints | Analytics Endpoints Latency (P95)      | timeseries | Prometheus  | http_request_duration_seconds_bucket |
| Backend-API Analytics Endpoints | Analytics Latency Percentiles          | timeseries | Prometheus  | http_request_duration_seconds_bucket |
| Backend-API Analytics Endpoints | Analytics Endpoints Error Rate         | timeseries | Prometheus  | http_request_duration_seconds_count  |
| Backend-API Analytics Endpoints | Analytics Endpoints Latency Comparison | barchart   | Prometheus  | http_request_duration_seconds_bucket |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 7 days
- Timezone: Browser

**Analytics Endpoints Monitored:**

- `/api/analytics/detection-trends` - Daily detection counts
- `/api/analytics/risk-history` - Risk level distribution over time
- `/api/analytics/camera-uptime` - Camera uptime percentages
- `/api/analytics/object-distribution` - Detection counts by object type
- `/api/analytics/risk-score-distribution` - Risk score histogram
- `/api/analytics/risk-score-trends` - Average risk score over time

### hsi-profiling.json

**Purpose:** Profiling dashboard for performance analysis.

**Dashboard UID:** `hsi-profiling`

### logs.json

**Purpose:** Log aggregation and viewing dashboard.

**Dashboard UID:** `hsi-logs`

### scene-ocr.json

**Purpose:** Scene OCR text extraction and service provider matching dashboard for monitoring PaddleOCR performance and service identification.

**Dashboard UID:** `hsi-scene-ocr`

**Panels by Section:**

All scene-OCR metrics carry the `hsi_` prefix in the live tree
(backend/core/metrics.py); the unprefixed `scene_ocr_*` names the dashboard
previously queried never existed in /api/metrics output.

| Row                   | Panel                                | Type       | Data Source | Metric                                        |
| --------------------- | ------------------------------------ | ---------- | ----------- | --------------------------------------------- |
| Scene OCR Overview    | Documentation                        | text       | -           | Feature overview and service categories       |
| Scene OCR Overview    | OCR Request Rate                     | stat       | Prometheus  | hsi_scene_ocr_requests_total                  |
| Scene OCR Overview    | Texts Detected (1h)                  | stat       | Prometheus  | hsi_scene_ocr_texts_detected_total            |
| Scene OCR Overview    | Service Provider Matches (1h)        | stat       | Prometheus  | hsi_scene_ocr_service_providers_matched_total |
| Scene OCR Overview    | Processing Latency (P95)             | stat       | Prometheus  | hsi_scene_ocr_processing_seconds_bucket       |
| Request Rate & Volume | OCR Requests by Source               | timeseries | Prometheus  | hsi_scene_ocr_requests_total (by source)      |
| Request Rate & Volume | Texts Detected Over Time             | timeseries | Prometheus  | hsi_scene_ocr_texts_detected_total            |
| Request Rate & Volume | Service Provider Matches by Category | timeseries | Prometheus  | hsi_scene_ocr_service_providers_matched_total |
| Performance           | OCR Processing Latency Percentiles   | timeseries | Prometheus  | hsi_scene_ocr_processing_seconds_bucket       |
| Performance           | Processing Time by Source (P95)      | timeseries | Prometheus  | hsi_scene_ocr_processing_seconds_bucket       |
| Quality Metrics       | Confidence Score Distribution        | timeseries | Prometheus  | hsi_scene_ocr_confidence_bucket               |
| Quality Metrics       | Provider Match Rate                  | gauge      | Prometheus  | hsi_scene_ocr_service_providers_matched_total |
| Quality Metrics       | Detection by Category (24h)          | piechart   | Prometheus  | hsi_scene_ocr_service_providers_matched_total |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 1 hour
- Timezone: Browser
- Tags: ocr, scene-ocr, service-providers, text-extraction, enrichment

**Key Scene OCR Metrics:**

- `hsi_scene_ocr_requests_total` - Counter of OCR requests by source (full_frame, crop)
- `hsi_scene_ocr_texts_detected_total` - Counter of texts detected
- `hsi_scene_ocr_service_providers_matched_total` - Counter of service provider matches by category
- `hsi_scene_ocr_processing_seconds` - Histogram of OCR processing duration by source
- `hsi_scene_ocr_confidence` - Histogram of OCR confidence scores

**Deleted panels:** the whole "Error Tracking" row (OCR Error Rate, Total Errors,
Error Rate by Type) — `scene_ocr_errors_total` is not exported by the scene-OCR
service, so there is no live error counter to chart.

**Service Provider Categories:**

- DELIVERY (FedEx, UPS, Amazon, USPS, DHL)
- UTILITY (PG&E, ComEd)
- TELECOM (AT&T, Comcast, Verizon)
- PLUMBING (Roto-Rooter)
- HVAC, ELECTRICAL, LANDSCAPING, PEST_CONTROL
- MEDICAL, SECURITY, FOOD_DELIVERY

### tracing.json

**Purpose:** Distributed tracing dashboard (Tempo, TraceQL panels + backend AI
service metrics via Triton `nv_*` series). The `$service` template variable is
`nemotron-backend` only: the backend is the sole OTLP span emitter in the
gateway topology (ai-gateway/Triton do not export traces). AI panel rows use
Triton per-model counters; durations are MEAN only (µs counter ratio — Triton
percentiles require summary stats, which are disabled).

**Dashboard UID:** `hsi-tracing`

## Dashboard Structure

### JSON Schema Overview

```json
{
  "title": "Dashboard name",
  "uid": "unique-id",
  "refresh": "10s",
  "panels": [
    {
      "id": 1,
      "type": "stat|gauge|timeseries|barchart",
      "title": "Panel title",
      "gridPos": { "h": 4, "w": 6, "x": 0, "y": 0 },
      "targets": [
        /* data queries */
      ],
      "fieldConfig": {
        /* display config */
      },
      "options": {
        /* panel-specific options */
      }
    }
  ]
}
```

### Grid Positioning

Grafana uses a 24-column grid:

- `w`: Width in columns (1-24)
- `h`: Height in rows
- `x`: X position (0-23)
- `y`: Y position (rows from top)

## Creating New Dashboards

### Manual Creation

1. Create new JSON file in this directory
2. Include required fields:
   ```json
   {
     "title": "My Dashboard",
     "uid": "my-dashboard-uid",
     "panels": [],
     "schemaVersion": 38
   }
   ```
3. Add panels as needed
4. Restart Grafana (`podman-compose -f docker-compose.prod.yml restart grafana`) or wait for auto-reload (30s)

### Export from Grafana UI

1. Create dashboard in Grafana UI
2. Go to Dashboard Settings (gear icon)
3. Click "JSON Model" in sidebar
4. Copy JSON content
5. Save to file in this directory

## Modifying Existing Dashboards

### Adding a Panel

1. Copy existing panel JSON as template
2. Change `id` to unique value
3. Update `gridPos` for positioning
4. Modify `targets` for data source
5. Adjust `fieldConfig` for display

### Changing Thresholds

```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    { "color": "green", "value": null },
    { "color": "yellow", "value": 50 },
    { "color": "red", "value": 80 }
  ]
}
```

### Updating JSONPath Queries

```json
"fields": [
  {
    "jsonPath": "$.queues.detection_queue",
    "name": "Detection Queue"
  }
]
```

## Troubleshooting

### Dashboard Not Appearing

1. Validate JSON syntax: `jq . consolidated.json`
2. Check for duplicate UIDs
3. Verify provisioning config: `../provisioning/dashboards/dashboard.yml`
4. Check Grafana logs: `docker compose logs grafana`

### Panel Shows Error

1. Check datasource UID matches `Backend-API` or `Prometheus`
2. Verify JSONPath matches API response structure
3. Test endpoint: `curl http://localhost:8000/api/system/health`

### No Data Displayed

1. Verify backend API is running
2. Check network connectivity between containers
3. Ensure API returns non-null values

## Related Files

- `../provisioning/dashboards/dashboard.yml` - Dashboard provisioning config
- `../provisioning/datasources/prometheus.yml` - Datasource definitions
- `../../prometheus.yml` - Prometheus scrape configuration
- `backend/api/routes/system.py` - Backend API endpoints
