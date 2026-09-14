# Prometheus Alerting

> Configure alerts for AI pipeline failures, infrastructure issues, and SLO violations.

This guide covers the alerting rules and Alertmanager configuration for Home Security Intelligence. The monitoring stack is optional and enabled with `--profile monitoring`.

---

## Overview

The alerting system consists of three components:

1. **Prometheus** - Evaluates alerting rules against collected metrics
2. **Alertmanager** - Routes, groups, and delivers alerts to receivers
3. **Backend Webhook** - Receives alerts for in-app notification and logging

### Alert Severity Levels

| Severity     | Description                                 | Response Time | Examples                                 |
| ------------ | ------------------------------------------- | ------------- | ---------------------------------------- |
| **critical** | System down, data loss imminent             | Immediate     | AI detector unavailable, GPU overheating |
| **warning**  | Performance degradation, approaching limits | Within hours  | High error rate, queue backlog           |
| **info**     | Informational, worth monitoring             | Best effort   | Prometheus target down                   |

---

## Quick Start

### Enable Monitoring Stack

```bash
# Start with monitoring profile
docker compose --profile monitoring -f docker-compose.prod.yml up -d

# Verify services are running
docker compose -f docker-compose.prod.yml ps | grep -E "(prometheus|alertmanager|grafana)"
```

### Access Points

| Service      | URL                   | Purpose                      |
| ------------ | --------------------- | ---------------------------- |
| Prometheus   | http://localhost:9090 | Metrics and alert status     |
| Alertmanager | http://localhost:9093 | Alert routing and silencing  |
| Grafana      | http://localhost:3002 | Dashboards and visualization |

### View Active Alerts

```bash
# Prometheus alerts
curl http://localhost:9090/api/v1/alerts | jq

# Alertmanager alerts
curl http://localhost:9093/api/v2/alerts | jq
```

---

## Pre-Configured Alerts

### AI Pipeline Alerts

| Alert                   | Condition                 | Duration | Severity |
| ----------------------- | ------------------------- | -------- | -------- |
| `AIDetectorUnavailable` | YOLO26 health check fails | 2 min    | critical |
| `AIBackendDown`         | Backend API unreachable   | 1 min    | critical |
| `AINemotronTimeout`     | P95 inference > 120s      | 5 min    | warning  |
| `AIDetectorSlow`        | P95 detection > 5s        | 5 min    | warning  |
| `AIHighErrorRate`       | Error rate > 10%          | 5 min    | warning  |
| `AIPipelineErrorSpike`  | > 50 errors in 5 min      | 2 min    | warning  |

**Example alert definition:**

```yaml
- alert: AIDetectorUnavailable
  expr: hsi_ai_healthy == 0
  for: 2m
  labels:
    severity: critical
    component: ai
    service: yolo26
  annotations:
    summary: 'AI detector service is unavailable'
    description: 'YOLO26 object detection service has been unhealthy for > 2 minutes.'
    runbook_url: 'https://github.com/.../wiki/Runbooks#aidetectorunavailable'
```

### GPU Resource Alerts

| Alert                     | Condition         | Duration | Severity |
| ------------------------- | ----------------- | -------- | -------- |
| `AIGPUOverheating`        | Temperature > 85C | 2 min    | critical |
| `AIGPUTemperatureWarning` | Temperature > 75C | 5 min    | warning  |
| `AIGPUMemoryCritical`     | VRAM usage > 95%  | 2 min    | critical |
| `AIGPUMemoryWarning`      | VRAM usage > 85%  | 5 min    | warning  |

**GPU memory pressure formula:**

```promql
(hsi_gpu_memory_used_mb / hsi_gpu_memory_total_mb) * 100 > 95
```

### Queue Depth Alerts

| Alert                     | Condition         | Duration | Severity |
| ------------------------- | ----------------- | -------- | -------- |
| `AIDetectionQueueBacklog` | Queue depth > 100 | 5 min    | warning  |
| `AIAnalysisQueueBacklog`  | Queue depth > 50  | 5 min    | warning  |

Queue backlog indicates that processing cannot keep up with incoming images.

### Infrastructure Alerts

| Alert                  | Condition                     | Duration | Severity |
| ---------------------- | ----------------------------- | -------- | -------- |
| `DatabaseUnhealthy`    | PostgreSQL health check fails | 2 min    | critical |
| `RedisUnhealthy`       | Redis health check fails      | 2 min    | critical |
| `PrometheusTargetDown` | Scrape target unreachable     | 5 min    | warning  |

### System Health Alerts

| Alert               | Condition           | Duration | Severity |
| ------------------- | ------------------- | -------- | -------- |
| `AISystemDegraded`  | System health = 0.5 | 5 min    | warning  |
| `AISystemUnhealthy` | System health = 0   | 2 min    | critical |

### Prometheus Self-Monitoring Alerts

Alerts for monitoring Prometheus itself to ensure observability infrastructure health.

| Alert                                  | Condition                         | Duration | Severity |
| -------------------------------------- | --------------------------------- | -------- | -------- |
| `PrometheusNotScrapingSelf`            | Self-scrape target down           | 2 min    | critical |
| `PrometheusConfigReloadFailed`         | Config reload unsuccessful        | 5 min    | critical |
| `PrometheusRuleEvaluationFailures`     | Rule evaluation errors            | 5 min    | warning  |
| `PrometheusRuleEvaluationSlow`         | Rule eval > interval duration     | 10 min   | warning  |
| `PrometheusScrapeFailuresHigh`         | Scrape sync failures > 10%        | 5 min    | critical |
| `PrometheusTargetsUnhealthy`           | > 20% targets down                | 5 min    | warning  |
| `PrometheusNotificationQueueFull`      | Notification queue > 90% capacity | 5 min    | warning  |
| `PrometheusNotificationsFailing`       | > 5 notification failures in 5min | 5 min    | critical |
| `PrometheusTSDBCompactionsFailing`     | TSDB compaction failures          | 5 min    | warning  |
| `PrometheusTSDBHeadTruncationsFailing` | TSDB head truncation failures     | 5 min    | critical |
| `PrometheusTSDBWALCorruptions`         | WAL corruptions detected          | 1 min    | warning  |
| `PrometheusStorageFillingUp`           | TSDB storage > 80% full           | 15 min   | warning  |
| `PrometheusQueryLoadHigh`              | Avg query duration > 10s          | 10 min   | warning  |
| `PrometheusRestarted`                  | Instance restarted                | 0 min    | info     |
| `PrometheusAlertmanagerDown`           | No Alertmanager discovered        | 5 min    | warning  |
| `PrometheusSamplesRejected`            | Out-of-order or duplicate samples | 10 min   | warning  |

**Example self-monitoring alert:**

```yaml
- alert: PrometheusConfigReloadFailed
  expr: prometheus_config_last_reload_successful == 0
  for: 5m
  labels:
    severity: critical
    component: monitoring
    service: prometheus
  annotations:
    summary: 'Prometheus configuration reload failed'
    description: 'Configuration reload has been failing for > 5 minutes. New rules are not being applied.'
```

---

## Alert Routing (Alertmanager)

### Default Configuration

Alerts are routed based on severity and component labels:

```yaml
route:
  receiver: 'default-receiver'
  group_by: ['alertname', 'component', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts - immediate
    - match:
        severity: critical
      receiver: 'critical-receiver'
      group_wait: 10s
      repeat_interval: 1h

    # Warning alerts - batched
    - match:
        severity: warning
      receiver: 'warning-receiver'
      group_wait: 2m
      repeat_interval: 6h
```

### Alert Grouping

Alerts are grouped to reduce notification noise:

| Parameter         | Value                              | Purpose                                   |
| ----------------- | ---------------------------------- | ----------------------------------------- |
| `group_by`        | `[alertname, component, severity]` | Group similar alerts together             |
| `group_wait`      | `30s`                              | Wait before first notification            |
| `group_interval`  | `5m`                               | Wait before notifying new alerts in group |
| `repeat_interval` | `4h`                               | Wait before resending notification        |

### Inhibition Rules

Higher-severity alerts suppress related lower-severity alerts:

| Source Alert           | Suppresses               |
| ---------------------- | ------------------------ |
| `HSIPipelineDown`      | All `HSI*` alerts        |
| `HSIDatabaseUnhealthy` | Queue and latency alerts |
| `HSIRedisUnhealthy`    | Queue alerts             |
| `HSIGPUMemoryHigh`     | `HSIGPUMemoryElevated`   |
| `HSICriticalErrorRate` | `HSIHighErrorRate`       |

---

## Configuring Notification Channels

### Webhook (Default)

All alerts are sent to the backend webhook for in-app notification:

```yaml
receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://backend:8000/api/webhooks/alerts'
        send_resolved: true
```

### Slack Integration

Uncomment and configure in `monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical-receiver'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#hsi-alerts'
        title: 'CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        send_resolved: true
```

**Required setup:**

1. Create a Slack webhook: https://api.slack.com/messaging/webhooks
2. Set `slack_api_url` in Alertmanager global config or per-receiver
3. Configure channel and message format

### Email Integration

Uncomment and configure SMTP settings:

```yaml
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'alertmanager@hsi.local'
  smtp_auth_username: 'alertmanager'
  smtp_auth_password: 'password' # pragma: allowlist secret

receivers:
  - name: 'critical-receiver'
    email_configs:
      - to: 'oncall@example.com'
        send_resolved: true
```

### PagerDuty Integration

For on-call rotation and escalation:

```yaml
receivers:
  - name: 'critical-receiver'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_SERVICE_KEY' # pragma: allowlist secret
        severity: critical
```

---

## Custom Alert Configuration

### Adding Custom Alerts

Edit `monitoring/prometheus_rules.yml`:

```yaml
groups:
  - name: custom_alerts
    interval: 15s
    rules:
      - alert: HighDetectionLatency
        expr: |
          histogram_quantile(0.95,
            rate(hsi_detection_duration_seconds_bucket[5m])
          ) > 10
        for: 5m
        labels:
          severity: warning
          component: ai
          service: pipeline
        annotations:
          summary: 'Detection latency is high'
          description: 'P95 detection latency exceeded 10 seconds for 5 minutes.'
```

### Validating Rules

Use `promtool` to validate rules before deployment:

```bash
# Validate rule file syntax
docker compose exec prometheus promtool check rules /etc/prometheus/prometheus_rules.yml

# Test rule expressions
docker compose exec prometheus promtool test rules /etc/prometheus/test_rules.yml
```

### Reloading Configuration

After editing rules or Alertmanager config:

```bash
# Reload Prometheus rules
curl -X POST http://localhost:9090/-/reload

# Reload Alertmanager config
curl -X POST http://localhost:9093/-/reload
```

---

## SLI/SLO Recording Rules

Pre-computed Service Level Indicators for dashboard efficiency:

### API Availability

```promql
# Success rate (non-5xx responses)
hsi:api_requests:success_rate_5m

# Availability ratios
hsi:api_availability:ratio_rate1h
hsi:api_availability:ratio_rate6h
hsi:api_availability:ratio_rate1d
hsi:api_availability:ratio_rate30d
```

### Detection Latency

```promql
# P95 and P99 latency
hsi:detection_latency:p95_5m
hsi:detection_latency:p99_5m

# Within SLO (< 2s)
hsi:detection_latency:within_slo_rate5m
```

### Analysis Latency

```promql
# P95 and P99 latency
hsi:analysis_latency:p95_5m
hsi:analysis_latency:p99_5m

# Within SLO (< 30s)
hsi:analysis_latency:within_slo_rate5m
```

### Error Budget

```promql
# Remaining error budget (target 99.5% availability)
hsi:error_budget:api_availability_remaining

# Burn rates
hsi:burn_rate:api_availability_1h
hsi:burn_rate:api_availability_6h
```

---

## Alert Silencing

### Temporary Silence via UI

1. Open Alertmanager UI: http://localhost:9093
2. Click "Silences" tab
3. Click "New Silence"
4. Configure matchers (e.g., `alertname=AIDetectorSlow`)
5. Set duration and comment

### Silence via API

```bash
# Create a 2-hour silence for detector slow alerts
curl -X POST http://localhost:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [{"name": "alertname", "value": "AIDetectorSlow", "isRegex": false}],
    "startsAt": "2025-01-09T00:00:00Z",
    "endsAt": "2025-01-09T02:00:00Z",
    "createdBy": "operator",
    "comment": "Planned maintenance"
  }'
```

### List Active Silences

```bash
curl http://localhost:9093/api/v2/silences | jq
```

---

## Runbooks

Each alert includes a `runbook_url` annotation linking to resolution steps. Create runbooks in your wiki:

### Example Runbook: AIDetectorUnavailable

**Symptoms:**

- YOLO26 health check fails
- No new detections processing

**Diagnosis:**

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps ai-yolo26

# Check container logs
docker compose -f docker-compose.prod.yml logs --tail=100 ai-yolo26

# Check GPU availability
nvidia-smi
```

**Resolution:**

1. **Container crashed:** Restart container

   ```bash
   docker compose -f docker-compose.prod.yml restart ai-yolo26
   ```

2. **GPU OOM:** Check GPU memory and reduce concurrent inferences

   ```bash
   nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
   ```

3. **Model loading failure:** Check model path and permissions

   ```bash
   docker compose exec ai-yolo26 ls -la /models/
   ```

---

## Troubleshooting

### Alerts Not Firing

1. **Check if rule is loaded:**

   ```bash
   curl http://localhost:9090/api/v1/rules | jq '.data.groups[].rules[].name'
   ```

2. **Verify metric exists:**

   ```bash
   curl "http://localhost:9090/api/v1/query?query=hsi_ai_healthy"
   ```

3. **Test expression manually:**

   ```bash
   curl "http://localhost:9090/api/v1/query?query=hsi_ai_healthy==0"
   ```

### Alerts Not Being Delivered

1. **Check Alertmanager status:**

   ```bash
   curl http://localhost:9093/-/ready
   ```

2. **View pending alerts:**

   ```bash
   curl http://localhost:9093/api/v2/alerts | jq
   ```

3. **Check receiver configuration:**

   ```bash
   curl http://localhost:9093/api/v2/status | jq '.config'
   ```

### Too Many Alerts (Alert Fatigue)

1. Increase `for` duration to filter transient issues
2. Adjust thresholds to reduce false positives
3. Use inhibition rules to suppress related alerts
4. Increase `group_interval` and `repeat_interval`

### Missing Metrics

1. **Check scrape targets:**

   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health, lastError}'
   ```

2. **Verify backend metrics endpoint:**

   ```bash
   curl http://localhost:8000/api/metrics | head -50
   ```

---

## Configuration Files

| File                              | Purpose                       |
| --------------------------------- | ----------------------------- |
| `monitoring/prometheus.yml`       | Main Prometheus configuration |
| `monitoring/prometheus_rules.yml` | Alerting rules                |
| `monitoring/prometheus-rules.yml` | SLI/SLO recording rules       |
| `monitoring/alertmanager.yml`     | Alert routing and receivers   |
| `monitoring/alerting-rules.yml`   | Additional alerting rules     |

---

## See Also

- [Monitoring and Observability](monitoring.md) - GPU monitoring, token tracking, tracing
- [SLO Definitions](monitoring/slos.md) - Service Level Objectives
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common issues
- [Prometheus Documentation](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
