# Monitoring Directory - Agent Guide

## Purpose

This directory contains observability and monitoring infrastructure configuration for the Home Security Intelligence system. It includes:

- **Prometheus** - Metrics collection and alerting
- **Grafana** - Dashboards for visualization
- **Loki** - Log aggregation and querying
- **Pyroscope** - Continuous profiling
- **Alloy** - Grafana Alloy collector for unified telemetry
- **JSON Exporter** - API endpoint scraping for metrics
- **Blackbox Exporter** - Synthetic monitoring probes

## Directory Structure

```
monitoring/
  AGENTS.md                    # This file
  alerting-rules.yml           # Alert notification rules
  alertmanager.yml             # Alertmanager configuration
  alloy/                       # Grafana Alloy collector configuration
    config.alloy               # Alloy collector configuration
  blackbox-exporter.yml        # Blackbox Exporter synthetic monitoring config (NEM-1637)
  grafana/                     # Grafana configuration
    AGENTS.md                  # Grafana directory guide
    dashboards/                # Dashboard JSON definitions
      AGENTS.md                # Dashboards guide
      consolidated.json        # Unified monitoring dashboard (consolidates pipeline + synthetic)
    provisioning/              # Auto-provisioning configs
      AGENTS.md                # Provisioning guide
      dashboards/
        dashboard.yml          # Dashboard provider config
      datasources/
        prometheus.yml         # Datasource configuration
  json-exporter-config.yml     # JSON Exporter module definitions
  loki/                        # Loki log aggregation configuration
    loki-config.yml            # Loki server configuration
  prometheus.yml               # Prometheus scrape configuration
  prometheus-rules.yml         # Prometheus recording rules
  prometheus_rules.yml         # Prometheus alerting rules for AI pipeline
  pyroscope/                   # Pyroscope continuous profiling configuration
    pyroscope-config.yml       # Pyroscope server configuration
```

## Key Files

### prometheus.yml

**Purpose:** Prometheus server configuration for metrics scraping.

**Scrape Jobs:**

| Job Name         | Endpoint                                | Interval | Description                         |
| ---------------- | --------------------------------------- | -------- | ----------------------------------- |
| hsi-health       | /api/system/health via JSON exporter    | 10s      | System health status                |
| hsi-telemetry    | /api/system/telemetry via JSON exporter | 10s      | Pipeline queue depths and latencies |
| hsi-stats        | /api/system/stats via JSON exporter     | 30s      | Camera, event, detection counts     |
| hsi-gpu          | /api/system/gpu via JSON exporter       | 10s      | GPU utilization and memory          |
| backend-liveness | /health                                 | 10s      | Direct liveness probe               |
| redis            | redis-exporter:9121                     | 15s      | Redis metrics via redis_exporter    |
| prometheus       | localhost:9090                          | Default  | Prometheus self-monitoring          |
| json-exporter    | json-exporter:7979                      | Default  | JSON exporter health                |

**Architecture:**

```
Backend API --> JSON Exporter --> Prometheus --> Grafana
     |
     +--> Direct liveness probe
```

### prometheus_rules.yml

**Purpose:** Alerting rules for AI pipeline monitoring (NEM-1731).

**Alert Groups:**

1. **ai_pipeline_alerts** - Core AI service monitoring

   | Alert                   | Severity | Description                          |
   | ----------------------- | -------- | ------------------------------------ |
   | AIDetectorUnavailable   | critical | YOLO26 detector service down for 2m  |
   | AIBackendDown           | critical | Backend API unreachable for 1m       |
   | AINemotronTimeout       | warning  | Nemotron P95 inference > 120s for 5m |
   | AIDetectorSlow          | warning  | YOLO26 P95 detection > 5s for 5m     |
   | AIHighErrorRate         | warning  | Pipeline error rate > 10% over 5m    |
   | AIPipelineErrorSpike    | warning  | > 50 errors in 5m window             |
   | AIGPUOverheating        | critical | GPU temperature > 85C for 2m         |
   | AIGPUTemperatureWarning | warning  | GPU temperature > 75C for 5m         |
   | AIGPUMemoryCritical     | critical | GPU VRAM > 95% for 2m                |
   | AIGPUMemoryWarning      | warning  | GPU VRAM > 85% for 5m                |
   | AIDetectionQueueBacklog | warning  | Detection queue > 100 items for 5m   |
   | AIAnalysisQueueBacklog  | warning  | Analysis queue > 50 batches for 5m   |
   | AISystemDegraded        | warning  | System health degraded for 5m        |
   | AISystemUnhealthy       | critical | System health unhealthy for 2m       |

2. **infrastructure_alerts** - Dependency monitoring

   | Alert                | Severity | Description                   |
   | -------------------- | -------- | ----------------------------- |
   | DatabaseUnhealthy    | critical | PostgreSQL unreachable for 2m |
   | RedisUnhealthy       | critical | Redis unreachable for 2m      |
   | PrometheusTargetDown | warning  | Any scrape target down for 5m |

3. **prometheus_self_monitoring_alerts** - Prometheus health (NEM-2468)

   | Alert                                | Severity | Description                            |
   | ------------------------------------ | -------- | -------------------------------------- |
   | PrometheusNotScrapingSelf            | critical | Prometheus not scraping itself for 2m  |
   | PrometheusConfigReloadFailed         | critical | Config reload failing for 5m           |
   | PrometheusRuleEvaluationFailures     | warning  | Rule evaluation errors in 5m window    |
   | PrometheusRuleEvaluationSlow         | warning  | Rule eval exceeds interval for 10m     |
   | PrometheusScrapeFailuresHigh         | critical | >10% scrape sync failures for 5m       |
   | PrometheusTargetsUnhealthy           | warning  | >20% targets down for 5m               |
   | PrometheusNotificationQueueFull      | warning  | Notification queue >90% for 5m         |
   | PrometheusNotificationsFailing       | critical | >5 notification failures in 5m         |
   | PrometheusTSDBCompactionsFailing     | warning  | TSDB compaction failures in 6h         |
   | PrometheusTSDBHeadTruncationsFailing | critical | TSDB head truncation failures in 1h    |
   | PrometheusTSDBWALCorruptions         | warning  | WAL corruptions detected in 1h         |
   | PrometheusStorageFillingUp           | warning  | TSDB storage >80% full for 15m         |
   | PrometheusQueryLoadHigh              | warning  | Avg query duration >10s for 10m        |
   | PrometheusRestarted                  | info     | Prometheus instance restarted          |
   | PrometheusAlertmanagerDown           | warning  | No Alertmanager discovered for 5m      |
   | PrometheusSamplesRejected            | warning  | Out-of-order/duplicate samples for 10m |

**Severity Levels:**

- **critical**: Immediate action required. System down or data loss imminent.
- **warning**: Action required soon. Performance degradation or approaching limits.
- **info**: Informational. Logged for analysis but no notifications.

**Validation:**

```bash
# Validate rules with promtool
cat monitoring/prometheus_rules.yml | podman run --rm -i --entrypoint sh \
  docker.io/prom/prometheus:v2.48.0 -c "cat > /tmp/rules.yml && promtool check rules /tmp/rules.yml"
```

### blackbox-exporter.yml

**Purpose:** Blackbox Exporter configuration for synthetic monitoring (NEM-1637).

**Probe Modules:**

| Module      | Prober | Timeout | Description                                              |
| ----------- | ------ | ------- | -------------------------------------------------------- |
| http_2xx    | http   | 5s      | Basic HTTP probe - checks for 200 OK response            |
| http_health | http   | 10s     | Health endpoint - validates JSON health response body    |
| http_ready  | http   | 15s     | Readiness probe - strict check for "ready" status        |
| http_live   | http   | 5s      | Liveness probe - simple availability check               |
| http_api    | http   | 10s     | API endpoint - accepts 200/201/204 responses             |
| tcp_connect | tcp    | 5s      | TCP connectivity - validates service accepts connections |
| tcp_tls     | tcp    | 10s     | TCP with TLS - for encrypted connections                 |
| dns_resolve | dns    | 5s      | DNS resolution validation                                |
| icmp_ping   | icmp   | 5s      | ICMP ping (requires NET_RAW capability)                  |

**Prometheus Scrape Jobs:**

| Job Name             | Module      | Targets                              | Interval |
| -------------------- | ----------- | ------------------------------------ | -------- |
| blackbox-http-health | http_health | Backend health endpoint              | 15s      |
| blackbox-http-ready  | http_ready  | Backend readiness endpoint           | 10s      |
| blackbox-http-live   | http_live   | Backend/Frontend liveness endpoints  | 10s      |
| blackbox-http-2xx    | http_2xx    | AI service health endpoints (5 svcs) | 30s      |
| blackbox-tcp         | tcp_connect | PostgreSQL, Redis                    | 15s      |

**Validation:**

```bash
# Test blackbox exporter config
podman run --rm -v $(pwd)/monitoring/blackbox-exporter.yml:/config.yml:ro,z \
  docker.io/prom/blackbox-exporter:v0.24.0 --config.check --config.file=/config.yml
```

### json-exporter-config.yml

**Purpose:** Defines how JSON API responses are converted to Prometheus metrics.

**Modules:**

1. **health** - System health metrics

   - `hsi_system_healthy` - Overall system status (healthy/degraded/unhealthy)
   - `hsi_database_healthy` - Database connection status
   - `hsi_redis_healthy` - Redis connection status
   - `hsi_ai_healthy` - AI services status

2. **telemetry** - Pipeline performance metrics

   - Queue depths: `hsi_detection_queue_depth`, `hsi_analysis_queue_depth`
   - Watch stage latencies: avg, P95, P99
   - Detect stage latencies: avg, P95, P99
   - Batch stage latencies: avg, P95, P99
   - Analyze stage latencies: avg, P95, P99

3. **stats** - System statistics

   - `hsi_total_cameras` - Total cameras configured
   - `hsi_total_events` - Total security events
   - `hsi_total_detections` - Total object detections
   - `hsi_uptime_seconds` - Application uptime

4. **gpu** - GPU monitoring
   - `hsi_gpu_utilization` - GPU utilization percentage
   - `hsi_gpu_memory_used_mb` - VRAM usage
   - `hsi_gpu_memory_total_mb` - Total VRAM
   - `hsi_gpu_temperature` - GPU temperature
   - `hsi_inference_fps` - Inference throughput

## Service Ports

| Service           | Port | URL                   |
| ----------------- | ---- | --------------------- |
| Prometheus        | 9090 | http://localhost:9090 |
| Grafana           | 3002 | http://localhost:3002 |
| JSON Exporter     | 7979 | http://localhost:7979 |
| Redis Exporter    | 9121 | http://localhost:9121 |
| Blackbox Exporter | 9115 | http://localhost:9115 |
| Backend API       | 8000 | http://localhost:8000 |

## Usage

### Starting Monitoring Stack

```bash
# With Podman Compose (this project uses Podman, not Docker)
podman-compose -f docker-compose.prod.yml up -d

# Or individual services (if monitoring compose file exists)
podman-compose -f docker-compose.monitoring.yml up -d prometheus grafana json-exporter redis-exporter
```

Note: This project uses **Podman** for container management. Replace `docker` with `podman` and `docker compose` with `podman-compose` in all commands.

### Accessing Dashboards

1. Open Grafana at http://localhost:3002
2. Anonymous users can view dashboards (read-only Viewer role)
3. To make changes, log in with admin credentials:
   - Default: admin/admin (change via `GF_ADMIN_PASSWORD` env var in production)
4. Navigate to "Home Security Intelligence" folder
5. Select "Pipeline" dashboard

**Security Note:** Anonymous access is restricted to Viewer role only. Administrators must log in to modify dashboards, data sources, or settings.

### Prometheus Queries

```promql
# System health (1 = healthy)
hsi_system_healthy

# Detection queue depth over time
hsi_detection_queue_depth

# P95 detection latency
hsi_detect_latency_p95_ms

# GPU utilization
hsi_gpu_utilization
```

## Important Patterns

### JSON Path Syntax

The JSON exporter uses JSONPath expressions:

```yaml
path: "{ .status }"               # Top-level field
path: "{ .services.redis.status }" # Nested field
path: "{ .queues.detection_queue }" # Nested numeric
```

### Value Mappings

For string-to-numeric conversions:

```yaml
values:
  healthy: 1
  degraded: 0.5
  unhealthy: 0
```

### Relabel Configs

Prometheus uses relabeling to route requests through JSON exporter:

```yaml
relabel_configs:
  - source_labels: [__address__]
    target_label: __param_target
  - source_labels: [__param_target]
    target_label: instance
  - target_label: __address__
    replacement: json-exporter:7979
```

## Troubleshooting

### Prometheus Not Scraping

1. Check targets: http://localhost:9090/targets
2. Verify JSON exporter: `curl http://localhost:7979/probe?target=http://backend:8000/api/system/health`
3. Check backend: `curl http://localhost:8000/api/system/health`

### Missing Metrics

1. Verify endpoint returns expected JSON structure
2. Check JSON exporter logs: `docker compose logs json-exporter`
3. Test module directly: `curl "http://localhost:7979/probe?module=health&target=http://backend:8000/api/system/health"`

## Related Files

- `docker-compose.yml` - Service definitions
- `backend/api/routes/system.py` - Backend endpoints for metrics
- `grafana/dashboards/consolidated.json` - Main unified monitoring dashboard
- `grafana/provisioning/` - Auto-provisioning configs
