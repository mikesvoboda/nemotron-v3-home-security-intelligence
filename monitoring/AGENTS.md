# Monitoring Directory - Agent Guide

## Purpose

This directory contains observability and monitoring infrastructure configuration for the Home Security Intelligence system. It includes Prometheus metrics collection, JSON exporter configuration for API endpoint scraping, and Grafana dashboards for visualization.

## Directory Structure

```
monitoring/
  AGENTS.md                    # This file
  prometheus.yml               # Prometheus scrape configuration
  json-exporter-config.yml     # JSON Exporter module definitions
  grafana/                     # Grafana configuration
    AGENTS.md                  # Grafana directory guide
    dashboards/                # Dashboard JSON definitions
      AGENTS.md                # Dashboards guide
      pipeline.json            # Main AI pipeline monitoring dashboard
    provisioning/              # Auto-provisioning configs
      AGENTS.md                # Provisioning guide
      dashboards/
        dashboard.yml          # Dashboard provider config
      datasources/
        prometheus.yml         # Datasource configuration
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
| backend-liveness | /api/system/health/live                 | 10s      | Direct liveness probe               |
| redis            | redis-exporter:9121                     | 15s      | Redis metrics via redis_exporter    |
| prometheus       | localhost:9090                          | Default  | Prometheus self-monitoring          |
| json-exporter    | json-exporter:7979                      | Default  | JSON exporter health                |

**Architecture:**

```
Backend API --> JSON Exporter --> Prometheus --> Grafana
     |
     +--> Direct liveness probe
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

| Service        | Port | URL                   |
| -------------- | ---- | --------------------- |
| Prometheus     | 9090 | http://localhost:9090 |
| Grafana        | 3000 | http://localhost:3000 |
| JSON Exporter  | 7979 | http://localhost:7979 |
| Redis Exporter | 9121 | http://localhost:9121 |
| Backend API    | 8000 | http://localhost:8000 |

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

1. Open Grafana at http://localhost:3000
2. Default credentials: admin/admin (change on first login)
3. Navigate to "Home Security Intelligence" folder
4. Select "Pipeline" dashboard

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
- `grafana/dashboards/pipeline.json` - Main dashboard definition
- `grafana/provisioning/` - Auto-provisioning configs
