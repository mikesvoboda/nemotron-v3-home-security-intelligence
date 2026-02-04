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

**Purpose:** YOLO26 object detection and AI services monitoring dashboard with inference workload metrics.

**Dashboard UID:** `ai-services`

**Panels by Section:**

| Row                       | Panel                         | Type       | Data Source | Metric                                     |
| ------------------------- | ----------------------------- | ---------- | ----------- | ------------------------------------------ |
| YOLO26 Overview           | Documentation                 | text       | -           | Performance baselines and thresholds       |
| YOLO26 Overview           | Model Status                  | stat       | Prometheus  | yolo26_model_loaded                        |
| YOLO26 Overview           | Inference Latency (p95)       | stat       | Prometheus  | yolo26_inference_duration_seconds_bucket   |
| YOLO26 Overview           | Request Rate                  | stat       | Prometheus  | yolo26_requests_total                      |
| YOLO26 Overview           | VRAM Usage                    | stat       | Prometheus  | yolo26_vram_bytes                          |
| YOLO26 Overview           | Errors (5m)                   | stat       | Prometheus  | yolo26_errors_total                        |
| YOLO26 Overview           | GPU Utilization               | stat       | Prometheus  | yolo26_gpu_utilization_percent             |
| YOLO26 Inference Workload | Inference Throughput          | stat       | Prometheus  | yolo26_inference_latency_seconds_count     |
| YOLO26 Inference Workload | Avg Inference Time            | stat       | Prometheus  | yolo26_inference_latency_seconds           |
| YOLO26 Inference Workload | Inference Health              | stat       | Prometheus  | yolo26_model_inference_healthy             |
| YOLO26 Inference Workload | Batch Throughput              | stat       | Prometheus  | yolo26_batch_size_count                    |
| YOLO26 Inference Workload | Avg Batch Size                | stat       | Prometheus  | yolo26_batch_size                          |
| YOLO26 Inference Workload | Detection Rate                | stat       | Prometheus  | yolo26_detections_total                    |
| Inference Performance     | Inference Latency Percentiles | timeseries | Prometheus  | yolo26_inference_duration_seconds_bucket   |
| Inference Performance     | Request Rate by Endpoint      | timeseries | Prometheus  | yolo26_requests_total                      |
| Detection Metrics         | Detections by Class           | timeseries | Prometheus  | yolo26_detections_total                    |
| Detection Metrics         | Detections Per Image Dist.    | timeseries | Prometheus  | yolo26_detections_per_image_bucket         |
| Errors & Batch Processing | Errors by Type                | timeseries | Prometheus  | yolo26_errors_total                        |
| Errors & Batch Processing | Batch Size Distribution       | timeseries | Prometheus  | yolo26_batch_size_bucket                   |
| GPU Resources             | VRAM Usage Over Time          | timeseries | Prometheus  | yolo26_vram_bytes                          |
| GPU Resources             | GPU Metrics                   | timeseries | Prometheus  | yolo26_gpu_utilization/temperature/power   |
| Face Recognition          | Face Detection Rate           | timeseries | Prometheus  | hsi_face_embeddings_generated_total        |
| Face Recognition          | Face Quality Score Dist.      | timeseries | Prometheus  | hsi_face_quality_score_bucket              |
| Face Recognition          | Face Embedding Time (p95)     | stat       | Prometheus  | hsi_face_embedding_duration_seconds_bucket |
| Face Recognition          | Known vs Unknown Faces        | piechart   | Prometheus  | hsi_face_embeddings_generated_total        |
| Face Recognition          | Detection Count by Camera     | timeseries | Prometheus  | hsi_face_embeddings_generated_total        |
| Face Recognition          | Recognition Confidence Dist.  | timeseries | Prometheus  | hsi_face_recognition_confidence_bucket     |
| Face Recognition          | Known Faces Database Size     | stat       | Prometheus  | hsi_known_faces_database_size              |
| Enrichment Models         | CLIP Inference Latency        | timeseries | Prometheus  | clip_inference_latency_seconds_bucket      |
| Enrichment Models         | Florence-2 Latency            | timeseries | Prometheus  | florence_inference_latency_seconds_bucket  |
| Enrichment Models         | Enrichment Throughput         | timeseries | Prometheus  | enrichment_inference_latency_seconds_count |
| Enrichment Models         | Enrichment Queue              | stat       | Prometheus  | hsi_analysis_queue_depth                   |
| Action Recognition        | Actions Detected by Type      | timeseries | Prometheus  | hsi_enrichment_model_calls_total           |
| Action Recognition        | Action Confidence Dist.       | timeseries | Prometheus  | hsi_action_confidence_bucket               |
| Action Recognition        | Action False Positive Rate    | stat       | Prometheus  | hsi_action_corrections/detections_total    |
| Loitering Detection       | Loitering Events by Zone      | timeseries | Prometheus  | hsi_loitering_events_total                 |
| Loitering Detection       | Dwell Time Distribution       | timeseries | Prometheus  | hsi_loitering_dwell_time_seconds_bucket    |
| Loitering Detection       | Loitering Alerts Rate         | timeseries | Prometheus  | hsi_loitering_alerts_total                 |
| Model Warmup              | Model Load Time               | timeseries | Prometheus  | enrichment_model_load_time_seconds         |
| Model Warmup              | Cold Start Latency            | timeseries | Prometheus  | hsi_model_cold_start_latency_seconds       |
| Model Warmup              | Model Restarts (24h)          | stat       | Prometheus  | hsi_pipeline_worker_restarts_total         |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 1 hour
- Timezone: Browser
- Tags: ai, yolo26, inference, gpu, workload, face-recognition, enrichment, action-recognition, loitering

**Key YOLO26 Metrics:**

- `yolo26_inference_duration_seconds` - Histogram of inference duration
- `yolo26_inference_latency_seconds` - Legacy histogram (for backwards compatibility)
- `yolo26_requests_total` - Counter of requests by endpoint and status
- `yolo26_detections_total` - Counter of detections by class_name
- `yolo26_detections_per_image` - Histogram of detections per image
- `yolo26_batch_size` - Histogram of batch sizes
- `yolo26_errors_total` - Counter of errors by error_type
- `yolo26_vram_bytes` - Gauge of VRAM usage in bytes
- `yolo26_model_loaded` - Gauge indicating model load status (1=loaded)
- `yolo26_model_inference_healthy` - Gauge indicating inference health (1=healthy)
- `yolo26_gpu_utilization_percent` - Gauge of GPU utilization
- `yolo26_gpu_temperature_celsius` - Gauge of GPU temperature
- `yolo26_gpu_power_watts` - Gauge of GPU power consumption

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

| Row                | Panel            | Type       | Data Source | Endpoint                        |
| ------------------ | ---------------- | ---------- | ----------- | ------------------------------- |
| System Overview    | System Health    | stat       | Backend-API | /api/system/health              |
| System Overview    | Total Cameras    | stat       | Backend-API | /api/system/stats               |
| System Overview    | Total Events     | stat       | Backend-API | /api/system/stats               |
| System Overview    | Total Detections | stat       | Backend-API | /api/system/stats               |
| System Overview    | Uptime           | stat       | Backend-API | /api/system/stats               |
| Queue Depths       | Detection Queue  | stat       | Backend-API | /api/system/telemetry           |
| Queue Depths       | Analysis Queue   | stat       | Backend-API | /api/system/telemetry           |
| Queue Depths       | Over Time        | timeseries | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Watch P95        | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Detect P95       | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Batch P95        | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Analysis P95     | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Histogram        | barchart   | Backend-API | /api/system/telemetry           |
| GPU Statistics     | GPU Utilization  | gauge      | Backend-API | /api/system/gpu                 |
| GPU Statistics     | GPU Temperature  | stat       | Backend-API | /api/system/gpu                 |
| GPU Statistics     | Memory Used      | stat       | Backend-API | /api/system/gpu                 |
| GPU Statistics     | Inference FPS    | stat       | AI-Detector | yolo26_inference_requests_total |
| Service Health     | Database         | stat       | Backend-API | /api/system/health              |
| Service Health     | Redis            | stat       | Backend-API | /api/system/health              |
| Service Health     | AI Services      | stat       | Backend-API | /api/system/health              |
| Service Health     | Readiness        | stat       | Backend-API | /api/system/health/ready        |

**Dashboard Settings:**

- Auto-refresh: 10 seconds
- Default time range: Last 1 hour
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

| Row                   | Panel                                | Type       | Data Source | Metric                                            |
| --------------------- | ------------------------------------ | ---------- | ----------- | ------------------------------------------------- |
| Scene OCR Overview    | Documentation                        | text       | -           | Feature overview and service categories           |
| Scene OCR Overview    | OCR Request Rate                     | stat       | Prometheus  | scene_ocr_requests_total                          |
| Scene OCR Overview    | Texts Detected (1h)                  | stat       | Prometheus  | scene_ocr_texts_detected_total                    |
| Scene OCR Overview    | Service Provider Matches (1h)        | stat       | Prometheus  | scene_ocr_service_providers_matched_total         |
| Scene OCR Overview    | Processing Latency (P95)             | stat       | Prometheus  | scene_ocr_processing_seconds_bucket               |
| Request Rate & Volume | OCR Requests by Source               | timeseries | Prometheus  | scene_ocr_requests_total (by source)              |
| Request Rate & Volume | Texts Detected Over Time             | timeseries | Prometheus  | scene_ocr_texts_detected_total                    |
| Request Rate & Volume | Service Provider Matches by Category | timeseries | Prometheus  | scene_ocr_service_providers_matched_total         |
| Performance           | OCR Processing Latency Percentiles   | timeseries | Prometheus  | scene_ocr_processing_seconds_bucket               |
| Performance           | Processing Time by Source (P95)      | timeseries | Prometheus  | scene_ocr_processing_seconds_bucket               |
| Quality Metrics       | Confidence Score Distribution        | timeseries | Prometheus  | scene_ocr_confidence_distribution_bucket          |
| Quality Metrics       | Provider Match Rate                  | gauge      | Prometheus  | scene_ocr_service_providers_matched_total         |
| Quality Metrics       | Detection by Category (24h)          | piechart   | Prometheus  | scene_ocr_service_providers_matched_total         |
| Error Tracking        | OCR Error Rate                       | stat       | Prometheus  | scene_ocr_errors_total / scene_ocr_requests_total |
| Error Tracking        | Total Errors (1h)                    | stat       | Prometheus  | scene_ocr_errors_total                            |
| Error Tracking        | Error Rate by Type                   | timeseries | Prometheus  | scene_ocr_errors_total                            |

**Dashboard Settings:**

- Auto-refresh: 30 seconds
- Default time range: Last 1 hour
- Timezone: Browser
- Tags: ocr, scene-ocr, service-providers, text-extraction, enrichment

**Key Scene OCR Metrics:**

- `scene_ocr_requests_total` - Counter of OCR requests by source (full_frame, crop)
- `scene_ocr_texts_detected_total` - Counter of texts detected
- `scene_ocr_service_providers_matched_total` - Counter of service provider matches by category
- `scene_ocr_processing_seconds` - Histogram of OCR processing duration by source
- `scene_ocr_confidence_distribution` - Histogram of OCR confidence scores
- `scene_ocr_errors_total` - Counter of OCR errors by error_type

**Service Provider Categories:**

- DELIVERY (FedEx, UPS, Amazon, USPS, DHL)
- UTILITY (PG&E, ComEd)
- TELECOM (AT&T, Comcast, Verizon)
- PLUMBING (Roto-Rooter)
- HVAC, ELECTRICAL, LANDSCAPING, PEST_CONTROL
- MEDICAL, SECURITY, FOOD_DELIVERY

### tracing.json

**Purpose:** Distributed tracing dashboard.

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
