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
  ai-pipeline-alerts.yml       # GPU/OOM, enrichment, prompt/LLM, coalescing,
                               #   risk-calibration, CLIP/Florence alerts (mounted rule file)
  alerting-rules.yml           # Pipeline/db/redis/gpu/queue/LLM alerts + Prometheus
                               #   self-monitoring + profiling server alerts (mounted rule file)
  alertmanager.yml             # Alertmanager routing configuration
  alloy/                       # Grafana Alloy collector configuration
    config.alloy               # Alloy collector configuration
  blackbox-exporter.yml        # Blackbox Exporter synthetic monitoring config (NEM-1637)
  cadvisor/                    # cAdvisor systemd unit (container metrics)
  dcgm/                        # NVIDIA DCGM GPU exporter (see dcgm/AGENTS.md)
  grafana/                     # Grafana configuration
    AGENTS.md                  # Grafana directory guide
    dashboards/                # Dashboard JSON definitions (15 dashboards; see dashboards/AGENTS.md)
      AGENTS.md                # Dashboards guide
    provisioning/              # Auto-provisioning configs
      AGENTS.md                # Provisioning guide
      dashboards/
        dashboard.yml          # Dashboard provider config
      datasources/
        prometheus.yml         # Datasource configuration
  gpu-alerts.yml               # DCGM-based GPU alerts (mounted rule file)
  json-exporter-config.yml     # JSON Exporter module definitions
  loki/                        # Loki log aggregation configuration
    loki-config.yml            # Loki server configuration
  profiling-recording-rules.yml       # Recording rules feeding regression detection (NEM-4133)
  profiling-regression-alerts.yml     # CPU/memory/latency regression alerts (NEM-4133)
  prometheus.yml               # Prometheus scrape configuration (LIVE config; no templating)
  prometheus-rules.yml         # Backend SLI / error-budget recording rules
  prometheus_rules.yml         # Prometheus alerting rules for AI pipeline
  pyroscope/                   # Pyroscope continuous profiling configuration
    pyroscope-config.yml       # Pyroscope server configuration (NEM-3928: retention policy)
    Dockerfile                 # Custom Pyroscope image with health check tools
  tempo/                       # Tempo trace storage (tempo-config.yml)
```

> The seven files listed in `rule_files:` inside `prometheus.yml` (`prometheus_rules.yml`,
> `prometheus-rules.yml`, `alerting-rules.yml`, `profiling-recording-rules.yml`,
> `profiling-regression-alerts.yml`, `gpu-alerts.yml`, `ai-pipeline-alerts.yml`) are each
> bind-mounted into the prometheus container by BOTH `docker-compose.prod.yml` and
> `docker-compose.ghcr.yml` — prometheus exits fatally at startup on a listed-but-absent
> rule file. Add a rule file to `rule_files:` only together with its mount in both compose
> files. There are no `.template` variants any more: `prometheus.yml.template` and
> `prometheus_rules.yml.template` had zero consumers (nothing ever ran envsubst over them)
> and now live under `../archive/` pending the owner's delete ruling.

### pyroscope-config.yml (NEM-3928)

**Purpose:** Pyroscope server configuration with comprehensive retention policy to prevent disk bloat.

**Retention Settings:**

| Setting                                                      | Value | Description                                     |
| ------------------------------------------------------------ | ----- | ----------------------------------------------- |
| `limits.compactor_blocks_retention_period`                   | 720h  | Maximum block age (30 days)                     |
| `pyroscopedb.retention_policy_min_free_disk_gb`              | 10 GB | Delete oldest blocks when free space below this |
| `pyroscopedb.retention_policy_min_disk_available_percentage` | 5%    | Secondary disk space threshold                  |
| `compactor.cleanup_interval`                                 | 15m   | How often retention is enforced                 |
| `compactor.compaction_interval`                              | 2h    | How often blocks are compacted                  |

**Storage Estimates:**

- Per day: ~350-700 MB (7 services at 100Hz)
- Per week: ~2.5-5 GB
- 30 days max: ~10-20 GB

## Key Files

### prometheus.yml

**Purpose:** Prometheus server configuration for metrics scraping. LIVE config:
compose bind-mounts it read-only; nothing templates or substitutes into it at startup.

**Scrape Jobs (22, as of the gateway consolidation):**

| Job Name             | Target                                          | Path/Module          | Interval |
| -------------------- | ----------------------------------------------- | -------------------- | -------- |
| hsi-backend-metrics  | backend:8000                                    | /api/metrics         | 15s      |
| ai-llm-metrics       | ai-llm:8091 (llama.cpp `--metrics`)             | /metrics             | 15s      |
| triton-metrics       | ai-gateway:8002 (Triton native)                 | /metrics             | 15s      |
| ai-gateway-metrics   | ai-gateway:8090 (FastAPI layer; `nv_*` dropped) | /metrics             | 15s      |
| hsi-health           | backend /api/system/health via json-exporter    | /probe (health)      | 10s      |
| hsi-telemetry        | backend /api/system/telemetry via json-exporter | /probe (telemetry)   | 10s      |
| hsi-stats            | backend /api/system/stats via json-exporter     | /probe (stats)       | 30s      |
| hsi-gpu              | backend /api/system/gpu via json-exporter       | /probe (gpu)         | 10s      |
| node-exporter        | node-exporter:9100                              | /metrics             | 15s      |
| redis                | redis-exporter:9121                             | /metrics             | 15s      |
| prometheus           | localhost:9090                                  | /metrics             | 15s      |
| json-exporter        | json-exporter:7979                              | /metrics             | 15s      |
| alertmanager         | alertmanager:9093                               | /metrics             | 15s      |
| blackbox-exporter    | blackbox-exporter:9115                          | /metrics             | 15s      |
| pyroscope            | pyroscope:4040                                  | /metrics             | 15s      |
| blackbox-http-health | backend /api/system/health                      | /probe (http_health) | 15s      |
| blackbox-http-ready  | backend /api/system/health/ready                | /probe (http_ready)  | 15s      |
| blackbox-http-live   | backend /health + frontend:8080                 | /probe (http_live)   | 10s      |
| blackbox-http-2xx    | AI service health endpoints (7 probes)          | /probe (http_2xx)    | 30s      |
| cadvisor             | host.containers.internal:8088                   | /metrics             | 15s      |
| blackbox-tcp         | postgres:5432, redis:6379                       | /probe (tcp_connect) | 15s      |
| dcgm-exporter        | host.containers.internal:9400                   | /metrics             | 15s      |

**Architecture:**

```
Backend /api/metrics ─────────────────────────────┐
ai-llm (llama.cpp) / triton / ai-gateway /metrics ─┤
json-exporter (backend health/telemetry/stats/gpu) ┼──> Prometheus ──> Grafana
blackbox-exporter (http/tcp probes) ────────────────┤         │
cadvisor / dcgm-exporter / node / redis ──────────┘         └──> Alertmanager
```

### prometheus_rules.yml

**Purpose:** Alerting rules for AI pipeline monitoring (NEM-1731). This is a LIVE file
— compose bind-mounts it directly (the old `.template` twin with its envsubst header is
archived; see the tree note above).

**Alert Groups (2, as of the gateway consolidation):**

1. **ai_pipeline_alerts** - Core AI service monitoring (15 active, incl. the DLQ trio)

   | Alert                   | Severity | Description                         |
   | ----------------------- | -------- | ----------------------------------- |
   | AIDetectorUnavailable   | critical | YOLO26 detector service down for 2m |
   | AIBackendDown           | critical | Backend API unreachable for 1m      |
   | AIHighErrorRate         | warning  | Pipeline error rate > 10% over 5m   |
   | AIPipelineErrorSpike    | warning  | > 50 errors in 5m window            |
   | AIGPUOverheating        | critical | GPU temperature > 85C for 2m        |
   | AIGPUTemperatureWarning | warning  | GPU temperature > 75C for 5m        |
   | AIGPUMemoryCritical     | critical | GPU VRAM > 95% for 2m               |
   | AIGPUMemoryWarning      | warning  | GPU VRAM > 85% for 5m               |
   | AIDetectionQueueBacklog | warning  | Detection queue > 100 items for 5m  |
   | AIAnalysisQueueBacklog  | warning  | Analysis queue > 50 batches for 5m  |
   | AIDLQHasMessages        | warning  | Dead-letter queue depth > 0         |
   | AIDLQGrowing            | warning  | DLQ gained > 5 messages in 15m      |
   | AIDLQCritical           | critical | DLQ depth > 50                      |
   | AISystemDegraded        | warning  | System health degraded for 5m       |
   | AISystemUnhealthy       | critical | System health unhealthy for 2m      |

   `AINemotronTimeout` and `AIDetectorSlow` are commented out in the file (kept as a
   re-enable sketch); do not list them as active.

2. **infrastructure_alerts** - Dependency monitoring

   | Alert                | Severity | Description                   |
   | -------------------- | -------- | ----------------------------- |
   | DatabaseUnhealthy    | critical | PostgreSQL unreachable for 2m |
   | RedisUnhealthy       | critical | Redis unreachable for 2m      |
   | PrometheusTargetDown | warning  | Any scrape target down for 5m |

**Where the other rule files' alerts live:** the self-monitoring group
`prometheus_self_monitoring_alerts` (NEM-2468: PrometheusNotScrapingSelf,
PrometheusStorageFillingUp, ... 16 alerts) is in **alerting-rules.yml**, not here.
The full mounted set: `alerting-rules.yml` (pipeline/db/redis/gpu/queue/LLM/workers/
circuit-breaker + self-monitoring + profiling-server groups), `ai-pipeline-alerts.yml`
(GPU/Triton, enrichment, prompt/LLM, coalescing, risk-calibration, CLIP/Florence),
`gpu-alerts.yml` (DCGM), `profiling-regression-alerts.yml` (NEM-4133 regressions),
`profiling-recording-rules.yml` + `prometheus-rules.yml` (recording rules, no alerts).

**Severity Levels:**

- **critical**: Immediate action required. System down or data loss imminent.
- **warning**: Action required soon. Performance degradation or approaching limits.
- **info**: Informational. Logged for analysis but no notifications.

**Validation:**

```bash
# Validate every mounted rule file with promtool (prometheus v3.1.0 = the
# compose image tag):
podman run --rm --entrypoint promtool \
  -v "$(pwd)/monitoring:/m:ro,z" \
  docker.io/prom/prometheus:v3.1.0 check rules \
  /m/prometheus_rules.yml /m/prometheus-rules.yml /m/alerting-rules.yml \
  /m/profiling-recording-rules.yml /m/profiling-regression-alerts.yml \
  /m/gpu-alerts.yml /m/ai-pipeline-alerts.yml

# And the scrape config (also resolves the rule_files: list):
podman run --rm --entrypoint promtool \
  -v "$(pwd)/monitoring:/m:ro,z" \
  docker.io/prom/prometheus:v3.1.0 check config /m/prometheus.yml
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

| Job Name             | Module      | Targets                                | Interval |
| -------------------- | ----------- | -------------------------------------- | -------- |
| blackbox-http-health | http_health | Backend health endpoint                | 15s      |
| blackbox-http-ready  | http_ready  | Backend readiness endpoint             | 15s      |
| blackbox-http-live   | http_live   | Backend/Frontend liveness endpoints    | 10s      |
| blackbox-http-2xx    | http_2xx    | AI service health endpoints (7 probes) | 30s      |
| blackbox-tcp         | tcp_connect | PostgreSQL, Redis                      | 15s      |

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
# With Podman Compose (this project uses Podman, not Docker). The monitoring
# stack (prometheus, grafana, alertmanager, loki, tempo, pyroscope, alloy,
# exporters) is defined inside docker-compose.prod.yml — there is no separate
# monitoring compose file and no root docker-compose.yml.
podman-compose -f docker-compose.prod.yml up -d

# Individual services:
podman-compose -f docker-compose.prod.yml up -d prometheus grafana json-exporter
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
path: '{ .status }' # Top-level field
path: '{ .services.redis.status }' # Nested field
path: '{ .queues.detection_queue }' # Nested numeric
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

- `docker-compose.prod.yml` - Service definitions (prometheus/grafana/etc. live here)
- `backend/api/routes/system.py` - Backend endpoints for metrics
- `grafana/dashboards/consolidated.json` - Main unified monitoring dashboard
- `grafana/provisioning/` - Auto-provisioning configs
