# Prometheus Alerting

> Configure alerts for AI pipeline failures, infrastructure issues, and SLO violations.

This guide covers the alerting rules and Alertmanager configuration for Home Security
Intelligence. Prometheus, Alertmanager and Grafana are **default compose services** — they
start with a plain `up -d` (no `--profile` needed; the only profiled services are
`ai-llm-vllm` (profile `vllm`) and `dcgm-exporter` (profile `gpu-rootful`)).

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

### Start the Monitoring Stack

```bash
# Monitoring services are part of the default stack
podman compose -f docker-compose.prod.yml up -d

# Verify services are running
podman compose -f docker-compose.prod.yml ps | grep -E "(prometheus|alertmanager|grafana)"
```

### Access Points

All three bind to `127.0.0.1` only (ports overridable via `PROMETHEUS_PORT`,
`ALERTMANAGER_PORT`, `GRAFANA_PORT` in `.env`).

| Service      | URL                            | Purpose                                           |
| ------------ | ------------------------------ | ------------------------------------------------- |
| Prometheus   | http://localhost:9090          | Metrics and alert status                          |
| Alertmanager | http://localhost:9093          | Alert routing and silencing                       |
| Grafana      | http://localhost:3002/grafana/ | Dashboards (served from the `/grafana/` sub-path) |

### View Active Alerts

```bash
# Prometheus alerts
curl http://localhost:9090/api/v1/alerts | jq

# Alertmanager alerts
curl http://localhost:9093/api/v2/alerts | jq
```

---

## Pre-Configured Alerts

Rules live in `monitoring/` (loaded via `rule_files` in `monitoring/prometheus.yml`):
`prometheus_rules.yml` (core + self/infra), `prometheus-rules.yml` (SLI/SLO recording
rules), `alerting-rules.yml`, `gpu-alerts.yml`, `ai-pipeline-alerts.yml`,
`profiling-recording-rules.yml`, `profiling-regression-alerts.yml`.

### AI Pipeline Alerts (`monitoring/prometheus_rules.yml`)

| Alert                   | Condition                                                         | Duration | Severity |
| ----------------------- | ----------------------------------------------------------------- | -------- | -------- |
| `AIDetectorUnavailable` | `hsi_ai_healthy == 0` (json-exporter health)                      | 2 min    | critical |
| `AIBackendDown`         | `probe_success{job="blackbox-http-live", service="backend"} == 0` | 1 min    | critical |
| `AIHighErrorRate`       | Pipeline error rate > 10%                                         | 5 min    | warning  |
| `AIPipelineErrorSpike`  | > 50 errors in 5 min                                              | 2 min    | warning  |
| `AIDLQHasMessages`      | `hsi_dlq_depth > 0`                                               | 5 min    | warning  |
| `AIDLQGrowing`          | DLQ grew > 5 in 15 min                                            | 5 min    | warning  |
| `AIDLQCritical`         | `hsi_dlq_depth > 50`                                              | 2 min    | critical |

> [!NOTE] > `AINemotronTimeout` and `AIDetectorSlow` are **commented out** in the rules file: the
> `hsi_ai_request_duration_seconds_bucket` histogram they need is not exported by the
> backend yet.

**Example alert definition** (measured, with the wiki runbook/dashboard URLs the rules
actually use):

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
    description: 'The YOLO26 object detection service has been unhealthy for more than 2 minutes. No new detections will be processed until the service recovers.'
    runbook_url: 'https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/wiki/Runbooks#aidetectorunavailable'
    dashboard_url: 'http://localhost:3002/d/pipeline/pipeline?orgId=1'
```

### GPU Resource Alerts

| Alert                     | Condition         | Duration | Severity |
| ------------------------- | ----------------- | -------- | -------- |
| `AIGPUOverheating`        | Temperature > 85C | 2 min    | critical |
| `AIGPUTemperatureWarning` | Temperature > 75C | 5 min    | warning  |
| `AIGPUMemoryCritical`     | VRAM usage > 95%  | 2 min    | critical |
| `AIGPUMemoryWarning`      | VRAM usage > 95%  | 5 min    | warning  |

> [!NOTE]
> As shipped, `AIGPUMemoryWarning` uses the **same** `> 95` expression as
> `AIGPUMemoryCritical` — only the `for` duration differs (5m vs 2m), so the warning fires
> when pressure sits above 95% between 2 and 5 minutes without crossing to critical.

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
| `PrometheusAITargetsDown`              | Any AI scrape target down         | 10 min   | info     |
| `PrometheusExportersDown`              | Any exporter target down          | 10 min   | info     |

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

The routing tree in `monitoring/alertmanager.yml` matches on `severity` and `component`
labels. A critical alert is sent to `critical-receiver` **and** continues to its
component-specific receiver:

```yaml
route:
  receiver: 'default-receiver'
  group_by: ['alertname', 'component', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

  routes:
    # Critical alerts - immediate, then continue to the component route
    - match:
        severity: critical
      receiver: 'critical-receiver'
      group_wait: 10s
      group_interval: 1m
      repeat_interval: 1h
      continue: true

    - match:
        component: slo
      receiver: 'slo-receiver'
      group_by: ['alertname', 'slo']
      group_wait: 30s
      repeat_interval: 2h

    - match:
        component: pipeline
      receiver: 'pipeline-receiver'
      group_wait: 15s

    - match:
        component: database
      receiver: 'infrastructure-receiver'

    - match:
        component: redis
      receiver: 'infrastructure-receiver'

    - match:
        component: gpu
      receiver: 'gpu-receiver'

    # Warning alerts - batched
    - match:
        severity: warning
      receiver: 'warning-receiver'
      group_wait: 2m
      group_interval: 10m
      repeat_interval: 6h

    # Info alerts - low priority
    - match:
        severity: info
      receiver: 'info-receiver'
      group_wait: 5m
      group_interval: 30m
      repeat_interval: 24h
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

| Source Alert           | Suppresses                                      |
| ---------------------- | ----------------------------------------------- |
| `HSIPipelineDown`      | All `HSI*` alerts                               |
| `HSIDatabaseUnhealthy` | Queue and latency alerts                        |
| `HSIRedisUnhealthy`    | Queue alerts                                    |
| `HSIGPUMemoryHigh`     | `HSIGPUMemoryElevated`                          |
| `HSICriticalErrorRate` | `HSIHighErrorRate`                              |
| `HSIExtremeLatency`    | `HSISlowDetection`, `HSISlowAnalysis`           |
| `HSIQueueCritical`     | `HSIDetectionQueueHigh`, `HSIAnalysisQueueHigh` |
| `HSI*FastBurn`         | `HSI*SlowBurn` (same `slo` label)               |

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
# Validate rule file syntax (all files loaded via rule_files)
podman compose -f docker-compose.prod.yml exec prometheus promtool check rules \
  /etc/prometheus/prometheus_rules.yml \
  /etc/prometheus/prometheus-rules.yml \
  /etc/prometheus/alerting-rules.yml \
  /etc/prometheus/gpu-alerts.yml
```

### Reloading Configuration

After editing rules or Alertmanager config:

```bash
# Reload Prometheus (runs with --web.enable-lifecycle)
curl -X POST http://localhost:9090/-/reload

# Alertmanager does NOT run with a reload endpoint — restart it instead
podman compose -f docker-compose.prod.yml restart alertmanager
```

Remember that only the rule files bind-mounted in `docker-compose.prod.yml` exist inside the
Prometheus container — editing `monitoring/profiling-recording-rules.yml`,
`monitoring/profiling-regression-alerts.yml` or `monitoring/ai-pipeline-alerts.yml` on the host
has no effect until those files are added to the `prometheus` service's `volumes:` and the
container is recreated.

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

> NOTE (2026-09-23): retargeted to the gateway topology. The standalone
> `ai-yolo26` container in the older steps below was retired fully that day
> (owner ruling — Triton on `ai-gateway` serves yolo26 among the 14 models;
> recipe in `archive/ai-yolo26-image/`). The alert itself keys on
> `hsi_ai_healthy == 0` — the backend's view of the AI stack — so diagnose the
> gateway and the backend's AI client, not a yolo26 container.

**Symptoms:**

- YOLO26 health check fails (backend `hsi_ai_healthy` gauge reports 0)
- No new detections processing

**Diagnosis:**

```bash
# Check the gateway container that serves yolo26 via Triton
docker compose -f docker-compose.prod.yml ps ai-gateway

# Check gateway logs for Triton model-load or adapter errors
docker compose -f docker-compose.prod.yml logs --tail=100 ai-gateway

# Check the model's Triton readiness (Triton native HTTP is 8000 inside the
# container; the gateway's own 8090 /health aggregates all 14 models)
docker compose exec ai-gateway curl -s http://localhost:8000/v2/models/yolo26/ready && echo READY
curl -fsS http://localhost:8090/health | head -c 400

# Check GPU availability
nvidia-smi
```

**Resolution:**

1. **Gateway container crashed:** Restart it

   ```bash
   docker compose -f docker-compose.prod.yml restart ai-gateway
   ```

2. **GPU OOM:** Check GPU memory and reduce concurrent inferences

   ```bash
   nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
   ```

3. **Model loading failure:** Check the engine/model path inside the gateway

   ```bash
   docker compose exec ai-gateway ls -la /models/yolo26/
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

| File                                                                           | Purpose                                                  |
| ------------------------------------------------------------------------------ | -------------------------------------------------------- |
| `monitoring/prometheus.yml`                                                    | Main Prometheus configuration (rule_files list)          |
| `monitoring/prometheus_rules.yml`                                              | Core alerting rules (AI, GPU, queues, infra)             |
| `monitoring/prometheus-rules.yml`                                              | SLI/SLO recording rules                                  |
| `monitoring/alerting-rules.yml`                                                | HSI\* pipeline rules + Prometheus self-monitoring        |
| `monitoring/gpu-alerts.yml`                                                    | DCGM-based GPU alerts                                    |
| `monitoring/ai-pipeline-alerts.yml`                                            | Enrichment/LLM/risk-calibration alerts                   |
| `monitoring/profiling-recording-rules.yml` / `profiling-regression-alerts.yml` | Profiling metrics and regressions                        |
| `monitoring/alertmanager.yml`                                                  | Alert routing and receivers                              |
| `monitoring/json-exporter-config.yml`                                          | `hsi_*_healthy` / `hsi_gpu_*` gauges many alerts consume |

---

## See Also

- [Monitoring and Observability](monitoring.md) - GPU monitoring, token tracking, tracing
- [SLO Definitions](monitoring/slos.md) - Service Level Objectives
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common issues
- [Prometheus Documentation](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
