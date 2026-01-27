# Loki, Pyroscope, and Alloy Integration Design

**Date:** 2026-01-20
**Status:** Approved
**Epic:** TBD

## Overview

Expand the observability stack with centralized log aggregation (Loki), continuous profiling (Pyroscope), and a unified telemetry collector (Alloy) to enable full correlation between metrics, logs, traces, and profiles.

## Goals

1. **Debugging AI pipeline issues** — Correlate logs across services to find root causes
2. **Performance optimization** — Profile GPU/CPU hotspots in AI services and async bottlenecks in backend
3. **Operational visibility** — Unified observability with logs, metrics, traces, and profiles in one place
4. **Future-proofing** — Modern observability stack with Grafana ecosystem

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Your Services                                │
├──────────────┬──────────────┬─────────────┬────────────┬───────────┤
│   Backend    │  AI-Detector │   AI-LLM    │ AI-Florence│  AI-CLIP  │
│  (Python)    │  (YOLO26)   │ (Nemotron)  │            │           │
│  +SDK prof   │              │             │            │           │
└──────┬───────┴───────┬──────┴──────┬──────┴─────┬──────┴─────┬─────┘
       │               │             │            │            │
       │    stdout     │   stdout    │  stdout    │  stdout    │
       ▼               ▼             ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Grafana Alloy (Unified Collector)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Log scraper │  │OTEL receiver│  │ eBPF profiler│  │Prom scraper│ │
│  │ (containers)│  │ (traces)    │  │ (AI services)│  │ (metrics)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
└─────────┼────────────────┼────────────────┼───────────────┼────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
     ┌────────┐       ┌────────┐       ┌──────────┐   ┌───────────┐
     │  Loki  │       │ Jaeger │       │ Pyroscope│   │Prometheus │
     │ (logs) │       │(traces)│       │(profiles)│   │ (metrics) │
     └────┬───┘       └────┬───┘       └────┬─────┘   └─────┬─────┘
          │                │                │               │
          └────────────────┴────────────────┴───────────────┘
                                   │
                                   ▼
                            ┌───────────┐
                            │  Grafana  │
                            │ (unified) │
                            └───────────┘
```

## Design Decisions

| Decision                | Choice                                 | Rationale                                                 |
| ----------------------- | -------------------------------------- | --------------------------------------------------------- |
| Implementation approach | Incremental (Loki → Pyroscope → Alloy) | Lower risk, easier debugging                              |
| Log retention           | 30 days                                | Matches metrics retention                                 |
| Profile targets         | Backend + AI services                  | Cover orchestration and inference                         |
| Profiling method        | Hybrid (eBPF for AI, SDK for backend)  | No code changes to AI services, finer control for backend |
| Alloy role              | Unified collector                      | Single config point for all telemetry                     |
| Resource budget         | Moderate (2-4GB RAM, 1-2 CPU)          | Production-quality without over-provisioning              |
| Container runtime       | Podman                                 | Existing infrastructure                                   |
| Monitoring services     | Required (not optional)                | All observability in production by default                |

## New Services

| Service       | Image                     | RAM   | CPU  | Storage   | Purpose                     |
| ------------- | ------------------------- | ----- | ---- | --------- | --------------------------- |
| **Loki**      | `grafana/loki:2.9.4`      | 512MB | 0.25 | 2GB (30d) | Log aggregation             |
| **Pyroscope** | `grafana/pyroscope:1.4.0` | 512MB | 0.25 | 1GB (30d) | Continuous profiling        |
| **Alloy**     | `grafana/alloy:v1.0.0`    | 768MB | 0.5  | -         | Unified telemetry collector |

**Total new resources:** ~1.8GB RAM, 1 CPU core

## Configuration Files

### Loki Configuration

**File:** `monitoring/loki/loki-config.yml`

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 720h # 30 days
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 8

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h
```

### Pyroscope Configuration

**File:** `monitoring/pyroscope/pyroscope-config.yml`

```yaml
storage:
  backend: filesystem
  filesystem:
    dir: /data

limits:
  max_query_length: 24h
  max_query_lookback: 720h # 30 days

retention:
  max_retention_period: 720h # 30 days

scrape_configs: [] # Alloy handles scraping via eBPF
```

### Alloy Configuration (Podman-compatible)

**File:** `monitoring/alloy/config.alloy`

```hcl
// ============================================
// LOG COLLECTION PIPELINE (Podman)
// ============================================

// Discover containers via Podman socket
discovery.docker "containers" {
  host = "unix:///run/podman/podman.sock"
}

// Scrape container logs from Podman
loki.source.docker "default" {
  host       = "unix:///run/podman/podman.sock"
  targets    = discovery.docker.containers.targets
  forward_to = [loki.process.parse.receiver]
}

// Parse and enrich logs
loki.process "parse" {
  stage.docker {}

  // Extract log level
  stage.regex {
    expression = "(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)"
  }

  // Extract camera name from AI pipeline logs
  stage.regex {
    expression = "camera[=: ]+(?P<camera>[a-z_]+)"
  }

  stage.labels {
    values = { level = "", camera = "" }
  }

  forward_to = [loki.write.local.receiver]
}

// Send to Loki
loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}

// ============================================
// TRACE COLLECTION PIPELINE
// ============================================

// Receive OTLP traces from backend
otelcol.receiver.otlp "default" {
  grpc { endpoint = "0.0.0.0:4317" }
  http { endpoint = "0.0.0.0:4318" }
  output { traces = [otelcol.exporter.otlp.jaeger.input] }
}

// Forward to Jaeger
otelcol.exporter.otlp "jaeger" {
  client {
    endpoint = "jaeger:4317"
    tls { insecure = true }
  }
}

// ============================================
// EBPF PROFILING PIPELINE (AI Services)
// ============================================

// eBPF targets via Podman labels
discovery.docker "ai_targets" {
  host = "unix:///run/podman/podman.sock"
  filter {
    name   = "label"
    values = ["pyroscope.profile=true"]
  }
}

pyroscope.ebpf "ai_services" {
  targets    = discovery.docker.ai_targets.targets
  forward_to = [pyroscope.write.local.receiver]
}

// Send profiles to Pyroscope
pyroscope.write "local" {
  endpoint {
    url = "http://pyroscope:4040"
  }
}
```

### Docker Compose Services

**Add to `docker-compose.prod.yml`:**

```yaml
  # ============================================
  # OBSERVABILITY STACK (Required)
  # ============================================

  loki:
    image: grafana/loki:2.9.4
    container_name: loki
    volumes:
      - ./monitoring/loki/loki-config.yml:/etc/loki/config.yml:ro,z
      - loki_data:/loki
    command: -config.file=/etc/loki/config.yml
    ports:
      - "3100:3100"
    healthcheck:
      test: ['CMD', 'wget', '-q', '--spider', 'http://localhost:3100/ready']
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 512M

  pyroscope:
    image: grafana/pyroscope:1.4.0
    container_name: pyroscope
    volumes:
      - ./monitoring/pyroscope/pyroscope-config.yml:/etc/pyroscope/config.yml:ro,z
      - pyroscope_data:/data
    command: -config.file=/etc/pyroscope/config.yml
    ports:
      - "4040:4040"
    healthcheck:
      test: ['CMD', 'wget', '-q', '--spider', 'http://localhost:4040/ready']
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 512M

  alloy:
    image: grafana/alloy:v1.0.0
    container_name: alloy
    privileged: true
    pid: host
    user: root
    security_opt:
      - label:disable  # Disable SELinux labeling for eBPF access
    volumes:
      - ./monitoring/alloy/config.alloy:/etc/alloy/config.alloy:ro,z
      - /run/podman/podman.sock:/run/podman/podman.sock:ro
      - /sys/kernel/debug:/sys/kernel/debug:ro
      - /sys/fs/cgroup:/sys/fs/cgroup:ro
      - /proc:/host/proc:ro  # Required for eBPF process discovery
    environment:
      - HOST_PROC=/host/proc
    command:
      - run
      - /etc/alloy/config.alloy
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "12345:12345" # Alloy UI
    depends_on:
      - loki
      - pyroscope
      - jaeger
    healthcheck:
      test: ['CMD', 'wget', '-q', '--spider', 'http://localhost:12345/ready']
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 768M

volumes:
  loki_data:
  pyroscope_data:
```

### AI Service Labels

**Add to each AI service in `docker-compose.prod.yml`:**

```yaml
ai-yolo26:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'ai-yolo26'

ai-llm:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'ai-llm'

ai-florence:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'ai-florence'

ai-clip:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'ai-clip'

ai-enrichment:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'ai-enrichment'
```

### Grafana Datasources

**Add to `monitoring/grafana/provisioning/datasources/prometheus.yml`:**

```yaml
# Loki datasource for log aggregation
- name: Loki
  type: loki
  access: proxy
  url: http://loki:3100
  isDefault: false
  editable: false
  jsonData:
    maxLines: 1000
    derivedFields:
      # Link logs to traces via trace_id
      - name: TraceID
        matcherRegex: 'trace_id=([a-f0-9]+)'
        url: '${__value.raw}'
        datasourceUid: jaeger
        urlDisplayLabel: 'View Trace'
      # Link logs to profiles via span_id
      - name: ProfileLink
        matcherRegex: 'span_id=([a-f0-9]+)'
        url: '${__value.raw}'
        datasourceUid: pyroscope
        urlDisplayLabel: 'View Profile'

# Pyroscope datasource for continuous profiling
- name: Pyroscope
  type: grafana-pyroscope-datasource
  access: proxy
  url: http://pyroscope:4040
  isDefault: false
  editable: false
  jsonData:
    # Enable trace-to-profile correlation
    tracesToProfiles:
      datasourceUid: jaeger
      tags:
        - key: service.name
          value: service
      profileTypeId: 'process_cpu:cpu:nanoseconds:cpu:nanoseconds'
      customQuery: true
```

### Backend SDK Integration

**Add to `backend/pyproject.toml`:**

```toml
[project.dependencies]
pyroscope-io = ">=0.8.7"
```

**Add to `backend/core/telemetry.py`:**

```python
import os
import pyroscope

def init_profiling():
    """Initialize Pyroscope continuous profiling for backend service."""
    pyroscope.configure(
        application_name="hsi-backend",
        server_address=os.getenv("PYROSCOPE_SERVER", "http://pyroscope:4040"),
        tags={
            "service": "backend",
            "env": os.getenv("ENVIRONMENT", "production"),
        },
        # Profile async event loops
        oncpu=True,
        gil=True,
        enable_logging=True,
    )
```

**Update `backend/core/logging_config.py`** to include trace context:

```python
# Add trace_id and span_id to log format for correlation
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "trace_id=%(otelTraceID)s span_id=%(otelSpanID)s | %(message)s"
)
```

## Implementation Phases

### Phase 1: Loki (Log Aggregation)

**Tasks:**

1. Create `monitoring/loki/loki-config.yml`
2. Add Loki service to `docker-compose.prod.yml`
3. Add Alloy service (log collection pipeline only)
4. Add Loki datasource to Grafana
5. Verify logs appear in Grafana Explore

**Validation:**

```bash
curl -s http://localhost:3100/ready  # Should return "ready"
# In Grafana Explore: {job=~".+"}
```

**Code changes:** None

### Phase 2: Pyroscope (Profiling)

**Tasks:**

1. Create `monitoring/pyroscope/pyroscope-config.yml`
2. Add Pyroscope service to `docker-compose.prod.yml`
3. Enable eBPF pipeline in Alloy config
4. Add `pyroscope.profile=true` labels to AI services
5. Add Pyroscope datasource to Grafana
6. Verify flame graphs appear

**Validation:**

```bash
curl -s http://localhost:4040/ready  # Should return "ready"
curl -s http://localhost:4040/api/v1/apps | jq .  # Should list AI services
```

**Code changes:** None (eBPF auto-instruments)

### Phase 3: Backend SDK Profiling

**Tasks:**

1. Add `pyroscope-io` to backend requirements
2. Add profiling initialization to backend startup
3. Rebuild backend container
4. Verify backend profiles in Pyroscope

**Validation:**

```bash
curl -s http://localhost:4040/api/v1/apps | jq . | grep hsi-backend
```

**Code changes:** ~20 lines

### Phase 4: Trace Pipeline Migration

**Tasks:**

1. Update backend OTEL endpoint: `jaeger:4317` → `alloy:4317`
2. Enable OTLP receiver in Alloy config
3. Verify traces flow through Alloy to Jaeger

**Validation:**

```bash
curl http://localhost:8000/api/health
# Check Jaeger UI for trace from "hsi-backend"
```

**Code changes:** Config only

### Phase 5: Full Correlation

**Tasks:**

1. Add trace_id/span_id to backend log format
2. Configure Grafana derived fields
3. Verify log↔trace↔profile navigation

**Validation:**

1. Query Loki: `{container="backend"} |= "trace_id"`
2. Click trace_id → Opens Jaeger trace
3. Click span → Shows "View Profile" link
4. Click profile → Opens Pyroscope flame graph

**Code changes:** ~10 lines

## Correlation Matrix

| From            | To      | How                                         |
| --------------- | ------- | ------------------------------------------- |
| Trace span      | Logs    | Click span → Loki query with `trace_id`     |
| Trace span      | Profile | Click span → Pyroscope flame graph          |
| Log line        | Trace   | Click `trace_id` in log → Jaeger trace view |
| Log line        | Profile | Click `span_id` → Pyroscope flame graph     |
| Metric alert    | Logs    | Grafana Explore split view                  |
| Profile hotspot | Traces  | Pyroscope → linked spans                    |

## Testing & Verification

### Verification Script

**File:** `scripts/verify-observability.sh`

```bash
#!/bin/bash
set -e

echo "=== Observability Stack Verification ==="

# Check all services healthy
declare -A PORTS=(
  ["loki"]=3100
  ["pyroscope"]=4040
  ["alloy"]=12345
  ["prometheus"]=9090
  ["jaeger"]=16686
  ["grafana"]=3000
)

for svc in "${!PORTS[@]}"; do
  port=${PORTS[$svc]}
  echo -n "Checking $svc:$port... "
  if curl -sf "http://localhost:$port/ready" > /dev/null 2>&1 || \
     curl -sf "http://localhost:$port/-/ready" > /dev/null 2>&1 || \
     curl -sf "http://localhost:$port/api/health" > /dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
  fi
done

# Verify log ingestion
echo -n "Loki log streams: "
curl -s 'http://localhost:3100/loki/api/v1/labels' | jq -r '.data | length'

# Verify profile ingestion
echo -n "Pyroscope apps: "
curl -s http://localhost:4040/api/v1/apps | jq -r 'length'

# Verify trace ingestion
echo -n "Jaeger services: "
curl -s http://localhost:16686/api/services | jq -r '.data | length'

echo "=== Verification Complete ==="
```

## Success Criteria

| Criteria                 | Measurement                                            |
| ------------------------ | ------------------------------------------------------ |
| Logs queryable           | Can run `{container="backend"} \|= "ERROR"` in Grafana |
| Log retention            | Logs older than 30 days auto-deleted                   |
| AI profiles visible      | Flame graphs for all 5 AI services in Pyroscope        |
| Backend profiles visible | Async spans visible in hsi-backend flame graph         |
| Trace correlation        | Click trace_id in log → opens Jaeger trace             |
| Profile correlation      | Click span in Jaeger → opens Pyroscope flame graph     |
| Resource budget          | Total new RAM < 2GB, CPU < 1 core                      |
| No service disruption    | All existing functionality unchanged                   |

## Files Summary

| File                                                         | Action |
| ------------------------------------------------------------ | ------ |
| `monitoring/loki/loki-config.yml`                            | Create |
| `monitoring/pyroscope/pyroscope-config.yml`                  | Create |
| `monitoring/alloy/config.alloy`                              | Create |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Modify |
| `docker-compose.prod.yml`                                    | Modify |
| `backend/pyproject.toml`                                     | Modify |
| `backend/core/telemetry.py`                                  | Modify |
| `backend/core/logging_config.py`                             | Modify |
| `scripts/verify-observability.sh`                            | Create |

## References

- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [Grafana Pyroscope Documentation](https://grafana.com/docs/pyroscope/latest/)
- [Grafana Alloy Documentation](https://grafana.com/docs/alloy/latest/)
- [LGTM Stack Deep Dive](https://blog.tarazevits.io/a-deep-dive-into-my-self-hosted-grafana-lgtm-stack/)
