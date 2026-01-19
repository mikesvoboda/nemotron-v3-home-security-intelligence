# SLI/SLO Framework for Home Security Intelligence

This document defines the Service Level Indicators (SLIs) and Service Level Objectives (SLOs) for the Home Security Intelligence platform.

## Overview

The SLI/SLO framework provides quantifiable measures of service reliability and performance, enabling data-driven decisions about system changes and incident response.

## Service Level Objectives

### SLO 1: API Availability

| Metric          | Value                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------- |
| **Target**      | 99.5%                                                                                    |
| **Window**      | 30-day rolling                                                                           |
| **SLI**         | Ratio of successful HTTP responses (non-5xx) to total requests                           |
| **Measurement** | `sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))` |

**Error Budget:** 0.5% = 3.6 hours/month of allowed unavailability

### SLO 2: Event Processing Latency

| Metric          | Value                                                                              |
| --------------- | ---------------------------------------------------------------------------------- |
| **Target**      | P95 < 5 seconds                                                                    |
| **Window**      | 30-day rolling                                                                     |
| **SLI**         | 95th percentile of event processing time                                           |
| **Measurement** | `histogram_quantile(0.95, rate(hsi_event_processing_duration_seconds_bucket[5m]))` |

**Error Budget:** 5% of events may exceed 5s latency

### SLO 3: Detection Latency

| Metric          | Value                                                                       |
| --------------- | --------------------------------------------------------------------------- |
| **Target**      | P95 < 2 seconds                                                             |
| **Window**      | 30-day rolling                                                              |
| **SLI**         | 95th percentile of RT-DETR detection inference time                         |
| **Measurement** | `histogram_quantile(0.95, rate(hsi_detection_duration_seconds_bucket[5m]))` |

**Error Budget:** 5% of detections may exceed 2s latency

### SLO 4: Analysis Latency

| Metric          | Value                                                                      |
| --------------- | -------------------------------------------------------------------------- |
| **Target**      | P95 < 30 seconds                                                           |
| **Window**      | 30-day rolling                                                             |
| **SLI**         | 95th percentile of Nemotron LLM analysis time                              |
| **Measurement** | `histogram_quantile(0.95, rate(hsi_analysis_duration_seconds_bucket[5m]))` |

**Error Budget:** 5% of analyses may exceed 30s latency

### SLO 5: WebSocket Availability

| Metric          | Value                                                                                                    |
| --------------- | -------------------------------------------------------------------------------------------------------- |
| **Target**      | 99%                                                                                                      |
| **Window**      | 30-day rolling                                                                                           |
| **SLI**         | Ratio of successful WebSocket connections to total connection attempts                                   |
| **Measurement** | `sum(rate(hsi_websocket_connections_successful[5m])) / sum(rate(hsi_websocket_connection_attempts[5m]))` |

**Error Budget:** 1% = 7.2 hours/month of allowed unavailability

## Error Budget Policy

### Error Budget Consumption Flowchart

```mermaid
flowchart TD
    Start([Check Error Budget]) --> Calculate[Calculate budget consumed<br/>for 30-day window]
    Calculate --> Check{Budget Consumed?}

    Check -->|"< 50%"| Green[Normal Operations]
    Check -->|"50-75%"| Yellow[Caution Zone]
    Check -->|"75-90%"| Orange[Feature Freeze]
    Check -->|"> 90%"| Red[Emergency Response]

    Green --> GreenActions["Continue feature development<br/>Normal release cadence<br/>Standard monitoring"]
    Yellow --> YellowActions["Increase monitoring frequency<br/>Delay risky changes<br/>Review recent deployments"]
    Orange --> OrangeActions["Halt new features<br/>Focus on reliability<br/>Root cause analysis required"]
    Red --> RedActions["All hands on reliability<br/>Incident response mode<br/>Rollback consideration"]

    GreenActions --> Monitor[Continue Monitoring]
    YellowActions --> Monitor
    OrangeActions --> Monitor
    RedActions --> Monitor

    Monitor --> Start

    style Green fill:#c8e6c9,stroke:#2e7d32
    style Yellow fill:#fff9c4,stroke:#f9a825
    style Orange fill:#ffe0b2,stroke:#ef6c00
    style Red fill:#ffcdd2,stroke:#c62828
    style GreenActions fill:#e8f5e9
    style YellowActions fill:#fffde7
    style OrangeActions fill:#fff3e0
    style RedActions fill:#ffebee
```

### Consumption Thresholds

| Threshold | Action                                            |
| --------- | ------------------------------------------------- |
| < 50%     | Normal operations, feature development continues  |
| 50-75%    | Increased monitoring, caution with risky changes  |
| 75-90%    | Feature freeze, focus on reliability improvements |
| > 90%     | Emergency response, all hands on reliability      |

### Burn Rate Alerting

We use multi-window burn rate alerting to detect SLO violations early:

| Window | Burn Rate | Alert Severity | Time to Exhaust Budget |
| ------ | --------- | -------------- | ---------------------- |
| 1h     | 14.4x     | Critical       | 2 hours                |
| 6h     | 6x        | Critical       | 5 hours                |
| 1d     | 3x        | Warning        | 10 days                |
| 3d     | 1x        | Info           | 30 days                |

#### Burn Rate Alerting Windows Visualization

```mermaid
flowchart LR
    subgraph "Multi-Window Burn Rate Detection"
        direction TB

        subgraph "1h Window"
            W1[1 hour] --> B1["14.4x burn rate"]
            B1 --> A1["CRITICAL<br/>2h to exhaust"]
        end

        subgraph "6h Window"
            W2[6 hours] --> B2["6x burn rate"]
            B2 --> A2["CRITICAL<br/>5h to exhaust"]
        end

        subgraph "1d Window"
            W3[1 day] --> B3["3x burn rate"]
            B3 --> A3["WARNING<br/>10d to exhaust"]
        end

        subgraph "3d Window"
            W4[3 days] --> B4["1x burn rate"]
            B4 --> A4["INFO<br/>30d to exhaust"]
        end
    end

    subgraph "Alert Logic"
        A1 --> Page["Page on-call immediately"]
        A2 --> Page
        A3 --> Notify["Notify team, investigate"]
        A4 --> Log["Log for review"]
    end

    style A1 fill:#ffcdd2,stroke:#c62828
    style A2 fill:#ffcdd2,stroke:#c62828
    style A3 fill:#fff9c4,stroke:#f9a825
    style A4 fill:#e3f2fd,stroke:#1976d2
    style Page fill:#ffebee
    style Notify fill:#fffde7
    style Log fill:#e3f2fd
```

**How it works:**

1. **Short windows (1h, 6h)** detect rapid budget consumption requiring immediate action
2. **Long windows (1d, 3d)** detect gradual degradation for proactive investigation
3. **Both conditions must be true** to fire an alert (prevents false positives from spikes)

## Recording Rules

Pre-computed metrics for efficient dashboard queries:

```yaml
# SLI Recording Rules (prometheus-rules.yml)
- record: hsi:api_availability:ratio_rate5m
  expr: sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

- record: hsi:detection_latency:p95_5m
  expr: histogram_quantile(0.95, rate(hsi_detection_duration_seconds_bucket[5m]))

- record: hsi:analysis_latency:p95_5m
  expr: histogram_quantile(0.95, rate(hsi_analysis_duration_seconds_bucket[5m]))
```

## Alert Rules

### Critical Alerts

| Alert Name           | Condition                        | For |
| -------------------- | -------------------------------- | --- |
| HSIPipelineDown      | All backend replicas unavailable | 1m  |
| HSIDatabaseUnhealthy | PostgreSQL connection failures   | 2m  |
| HSIRedisUnhealthy    | Redis connection failures        | 2m  |
| HSIGPUMemoryHigh     | GPU memory > 90%                 | 5m  |

### Warning Alerts

| Alert Name            | Condition                   | For |
| --------------------- | --------------------------- | --- |
| HSIDetectionQueueHigh | Detection queue > 100 items | 5m  |
| HSIAnalysisQueueHigh  | Analysis queue > 50 items   | 5m  |
| HSIHighErrorRate      | Error rate > 5%             | 5m  |
| HSISlowDetection      | P95 detection latency > 2s  | 10m |
| HSISlowAnalysis       | P95 analysis latency > 30s  | 10m |

## Dashboard

The SLO dashboard (`monitoring/grafana/dashboards/slo.json`) provides:

1. **SLO Compliance Gauges** - Current compliance for each SLO
2. **Error Budget Remaining** - Time-based visualization of remaining budget
3. **Burn Rate Trends** - Multi-window burn rate graphs
4. **Historical SLI Trends** - 30-day rolling SLI values

## Implementation Notes

### Metric Sources

- **API metrics**: FastAPI middleware via Prometheus client
- **Detection metrics**: RT-DETR service instrumentation
- **Analysis metrics**: Nemotron service instrumentation
- **WebSocket metrics**: WebSocket handler instrumentation
- **Infrastructure metrics**: Redis exporter, PostgreSQL exporter

### Data Retention

- Raw metrics: 15 days
- Recording rules (aggregated): 90 days
- Dashboard snapshots: 365 days

## Related Documentation

- [Prometheus Rules](../monitoring/prometheus-rules.yml)
- [Alerting Rules](../monitoring/alerting-rules.yml)
- [Alertmanager Configuration](../monitoring/alertmanager.yml)
- [SLO Dashboard](../monitoring/grafana/dashboards/slo.json)
