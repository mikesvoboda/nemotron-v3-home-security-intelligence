# Grafana Operations Dashboard Design

**Date:** 2026-01-05
**Status:** Approved
**Dashboard UID:** `hsi-operations`

## Overview

A comprehensive single-dashboard view exposing all available Prometheus metrics for the Home Security Intelligence system. Designed for real-time operations monitoring with drill-down capability via collapsible rows.

## Dashboard Configuration

| Property           | Value                                   |
| ------------------ | --------------------------------------- |
| Name               | Home Security Intelligence - Operations |
| UID                | `hsi-operations`                        |
| Default Time Range | Last 15 minutes                         |
| Auto-Refresh       | 5 seconds                               |
| Tags               | `hsi`, `operations`, `monitoring`       |

### Quick Time Selectors

Top bar with link panels for one-click time range switching:

- 15m | 1h | 6h | 24h | 7d

### Panel Standards

All panels use timeseries visualization with:

- Legend: Table mode showing Last/Min/Max/Avg
- Current value prominent via "Last" column
- Color thresholds applied as threshold lines or background bands
- Tooltip: All series, sorted by value

---

## Row 1: System Health (Expanded by Default)

Overall system status and service connectivity at a glance.

| Panel          | Metrics                     | Display                                  |
| -------------- | --------------------------- | ---------------------------------------- |
| Health Status  | `hsi_health_status`         | Timeseries, green/yellow/red thresholds  |
| Uptime         | `hsi_system_uptime_seconds` | Timeseries, legend shows days/hours      |
| Database       | Service health probe        | Timeseries, connected/disconnected state |
| Redis          | `redis_up`                  | Timeseries, connected/disconnected state |
| RT-DETR        | Circuit breaker state       | Timeseries, healthy/open/half-open       |
| Nemotron       | Circuit breaker state       | Timeseries, healthy/open/half-open       |
| Active Cameras | `hsi_camera_count`          | Timeseries with sparkline trend          |
| Events Today   | `hsi_events_created_total`  | Timeseries, counter with trend           |

---

## Row 2: Pipeline Overview (Expanded by Default)

Pipeline flow, latency, and queue status.

| Panel                    | Metrics                                                 | Display                                                                       |
| ------------------------ | ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| End-to-End Latency       | `hsi_stage_duration_seconds{stage="total"}` P50/P95/P99 | Timeseries, threshold lines at 5s/15s                                         |
| Throughput               | `rate(hsi_detections_processed_total[5m])`              | Timeseries, detections/sec in legend                                          |
| Detection Queue Depth    | `hsi_detection_queue_depth`                             | Timeseries, fill opacity, threshold bands (green 0-30, yellow 31-70, red 71+) |
| Analysis Queue Depth     | `hsi_analysis_queue_depth`                              | Timeseries, fill opacity, threshold bands                                     |
| Pipeline Stage Breakdown | All `hsi_stage_duration_seconds` by stage               | Stacked timeseries (watch=blue, detect=orange, batch=purple, analyze=green)   |
| Queue Comparison         | Both queue depths overlaid                              | Dual-axis timeseries for side-by-side comparison                              |

---

## Row 3: GPU Resources (Expanded by Default)

GPU utilization, memory, thermal, and throughput.

| Panel                | Metrics                                                    | Display                                                                      |
| -------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| GPU Utilization      | `hsi_gpu_utilization_percent`                              | Timeseries, 0-100% scale, threshold at 90%                                   |
| VRAM Usage           | `hsi_gpu_memory_used_bytes` / `hsi_gpu_memory_total_bytes` | Timeseries, used vs total, threshold at 85%                                  |
| GPU Temperature      | `hsi_gpu_temperature_celsius`                              | Timeseries, warm color gradient, thresholds at 75C (warning), 85C (critical) |
| Inference FPS        | `hsi_gpu_inference_fps`                                    | Timeseries, processing throughput                                            |
| GPU Power Draw       | `hsi_gpu_power_watts` (if available)                       | Timeseries, power consumption                                                |
| GPU Memory Breakdown | Memory by process/model                                    | Stacked timeseries showing VRAM consumers                                    |

---

## Row 4: AI Models (Collapsed by Default)

Individual AI service performance metrics.

| Panel                 | Metrics                                                               | Display                                                  |
| --------------------- | --------------------------------------------------------------------- | -------------------------------------------------------- |
| RT-DETR Latency       | `hsi_ai_request_duration_seconds{service="rtdetr"}` P50/P95/P99       | Timeseries, threshold at 500ms                           |
| RT-DETR Request Rate  | `rate(hsi_ai_request_duration_seconds_count{service="rtdetr"}[1m])`   | Timeseries, requests/sec                                 |
| Nemotron Latency      | `hsi_ai_request_duration_seconds{service="nemotron"}` P50/P95/P99     | Timeseries, threshold at 5s                              |
| Nemotron Request Rate | `rate(hsi_ai_request_duration_seconds_count{service="nemotron"}[1m])` | Timeseries, requests/sec                                 |
| Florence Latency      | `hsi_ai_request_duration_seconds{service="florence"}` P50/P95/P99     | Timeseries, threshold at 1s                              |
| Florence Tasks        | `rate(hsi_florence_task_total[5m])` by task type                      | Stacked timeseries (caption, ocr, detect, dense_caption) |
| CLIP Latency          | `hsi_ai_request_duration_seconds{service="clip"}`                     | Timeseries, threshold at 200ms                           |
| All Models Comparison | All service latencies overlaid                                        | Multi-line timeseries, color-coded by service            |

**Color Coding:**

- RT-DETR: Orange
- Nemotron: Purple
- Florence: Blue
- CLIP: Green

---

## Row 5: Detection Analytics (Collapsed by Default)

Detection quality, classification, and camera activity.

| Panel                             | Metrics                                          | Display                                                      |
| --------------------------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| Detection Confidence Distribution | `hsi_detection_confidence` histogram             | Heatmap showing confidence spread over time                  |
| Avg Confidence                    | `hsi_detection_confidence` avg                   | Timeseries, threshold below 0.7                              |
| Detections by Class               | `hsi_detections_by_class_total`                  | Stacked timeseries per class (person, vehicle, animal, etc.) |
| Top Classes (Current)             | `topk(10, hsi_detections_by_class_total)`        | Bar chart, most detected objects in window                   |
| Detections by Camera              | `hsi_events_by_camera_total`                     | Stacked timeseries per camera                                |
| Camera Activity Ranking           | `topk(10, rate(hsi_events_by_camera_total[5m]))` | Bar chart, most active cameras                               |
| Detection Rate                    | `rate(hsi_detections_processed_total[1m])`       | Timeseries, overall throughput                               |
| Unique Objects                    | Count of distinct classes detected               | Timeseries, detection diversity                              |

---

## Row 6: Risk Analysis (Collapsed by Default)

Risk scoring and threat level distribution.

| Panel                   | Metrics                                           | Display                                                                              |
| ----------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------- |
| Risk Score Distribution | `hsi_risk_score` histogram                        | Heatmap, 0-100 scale over time                                                       |
| Avg Risk Score          | `hsi_risk_score` avg                              | Timeseries, trending indicator                                                       |
| Current Risk Level      | Latest `hsi_risk_score`                           | Timeseries, large legend "Last" value, thresholds (green <30, yellow 30-70, red >70) |
| Events by Risk Level    | `hsi_events_by_risk_level_total`                  | Stacked timeseries (low, medium, high, critical)                                     |
| Risk Level Breakdown    | `hsi_events_by_risk_level_total`                  | Pie/bar chart, proportion in current window                                          |
| High Risk Event Rate    | `rate(hsi_events_by_risk_level_total{level=~"high | critical"}[5m])`                                                                     | Timeseries, concerning events focus |
| Prompt Template Usage   | `hsi_prompt_template_used_total`                  | Stacked timeseries by template                                                       |
| Events Reviewed         | `rate(hsi_events_reviewed_total[5m])`             | Timeseries, human review activity                                                    |

---

## Row 7: Queue Health (Collapsed by Default)

Queue overflow, dead letter queue, and backpressure indicators.

| Panel                 | Metrics                                           | Display                                              |
| --------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| Queue Overflow Events | `rate(hsi_queue_overflow_total[5m])`              | Timeseries, should be zero (any value is concerning) |
| Items Moved to DLQ    | `hsi_queue_items_moved_to_dlq_total`              | Timeseries, dead letter queue activity               |
| Items Dropped         | `rate(hsi_queue_items_dropped_total[5m])`         | Timeseries, data loss indicator, red threshold at >0 |
| Items Rejected        | `rate(hsi_queue_items_rejected_total[5m])`        | Timeseries, validation failures                      |
| DLQ Total Size        | `hsi_queue_items_moved_to_dlq_total` (cumulative) | Timeseries, growing DLQ needs attention              |
| Queue Health Summary  | All overflow/drop/reject metrics                  | Multi-line timeseries for correlation                |
| Queue Saturation      | `hsi_detection_queue_depth / queue_capacity`      | Timeseries, percentage of capacity used              |
| Backpressure Events   | Derived from queue depth spikes                   | Timeseries, system pressure indicator                |

**Alert Candidates:**
These metrics are prime for alerting - non-zero values on overflow/dropped indicate problems.

---

## Row 8: Model Zoo (Collapsed by Default)

Enrichment model performance across all 18 models.

| Panel                         | Metrics                                               | Display                                               |
| ----------------------------- | ----------------------------------------------------- | ----------------------------------------------------- |
| Enrichment Model Calls        | `rate(hsi_enrichment_model_calls_total[5m])` by model | Stacked timeseries (vehicle, pet, clothing, violence) |
| Model Call Volume             | `hsi_enrichment_model_calls_total` by model           | Bar chart ranking model usage                         |
| Vehicle Detection Latency     | Model Zoo latency for vehicle model                   | Timeseries P50/P95/P99                                |
| Pet Detection Latency         | Model Zoo latency for pet model                       | Timeseries P50/P95/P99                                |
| Clothing Detection Latency    | Model Zoo latency for clothing model                  | Timeseries P50/P95/P99                                |
| Violence Detection Latency    | Model Zoo latency for violence model                  | Timeseries P50/P95/P99                                |
| All Models Latency Comparison | All 18 Model Zoo model latencies                      | Multi-line timeseries, identify slowest               |
| Model Latency Heatmap         | All models x time                                     | Heatmap showing latency patterns                      |
| Model Error Rate              | Errors/failures per model                             | Timeseries, identifies problematic models             |
| Model Throughput              | Successful calls per model                            | Stacked timeseries, processing volume                 |

---

## Summary

| Row | Name                | State     | Panels |
| --- | ------------------- | --------- | ------ |
| 1   | System Health       | Expanded  | 8      |
| 2   | Pipeline Overview   | Expanded  | 6      |
| 3   | GPU Resources       | Expanded  | 6      |
| 4   | AI Models           | Collapsed | 8      |
| 5   | Detection Analytics | Collapsed | 8      |
| 6   | Risk Analysis       | Collapsed | 8      |
| 7   | Queue Health        | Collapsed | 8      |
| 8   | Model Zoo           | Collapsed | 10     |

**Total: 62 panels covering all available Prometheus metrics**

---

## Implementation Notes

1. **File Location:** `monitoring/grafana/dashboards/operations.json`
2. **Provisioning:** Auto-loaded via existing dashboard provisioner
3. **Replaces/Supplements:** Supplements existing `pipeline.json` dashboard
4. **Testing:** Verify all metrics exist in Prometheus before panel creation

## Future Enhancements

- Add alerting rules for critical metrics (queue overflow, high latency, GPU thermal)
- Create Alertmanager integration for notifications
- Add annotation support for deployment markers
- Consider log panel integration if Loki is added
