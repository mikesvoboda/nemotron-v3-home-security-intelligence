# Monitoring and Observability

> GPU monitoring, LLM token tracking, and distributed tracing for the Home Security Intelligence system.

This guide covers the three core observability pillars:

1. **GPU Monitoring** - Real-time GPU metrics and memory pressure alerts
2. **Token Tracking** - LLM context window management and utilization metrics
3. **Distributed Tracing** - OpenTelemetry integration for cross-service debugging

---

## GPU Monitoring

The GPU monitoring service (`GPUMonitor`) provides real-time metrics for the NVIDIA GPUs
carrying AI work: `ai-gateway` (Triton, `GPU_AI_SERVICES`) and `ai-vlm` (llama.cpp,
`GPU_LLM`, in the default compose set).

### How It Works

The GPU monitor uses a fallback strategy to collect metrics:

1. **pynvml** (preferred) - Direct NVIDIA Management Library bindings for lowest latency
2. **nvidia-smi** - Subprocess fallback when pynvml is unavailable (containerized environments)
3. **AI Container Endpoints** - Queries the detector URL (`YOLO26_URL`, default
   `http://ai-gateway:8090/yolo26` in compose) at its `/health` endpoint for GPU stats
4. **Mock Data** - Development mode when no GPU is available

### Metrics Tracked

| Metric            | Description                                       | Unit               |
| ----------------- | ------------------------------------------------- | ------------------ |
| `gpu_name`        | GPU model name                                    | string             |
| `gpu_utilization` | GPU compute utilization                           | percentage (0-100) |
| `memory_used`     | GPU memory currently in use                       | MB                 |
| `memory_total`    | Total GPU memory                                  | MB                 |
| `temperature`     | GPU core temperature                              | Celsius            |
| `power_usage`     | Current power draw                                | Watts              |
| `inference_fps`   | Inference throughput (calculated from detections) | frames/second      |

### Memory Pressure Monitoring

The system monitors GPU memory pressure to prevent out-of-memory errors and automatically throttle inference operations.

**Pressure Levels:**

| Level        | Memory Usage | Description                      |
| ------------ | ------------ | -------------------------------- |
| **NORMAL**   | < 85%        | Normal operations, no throttling |
| **WARNING**  | 85-95%       | Moderate throttling recommended  |
| **CRITICAL** | >= 95%       | Aggressive throttling required   |

When memory pressure changes, registered callbacks are invoked to allow downstream services (like the inference semaphore) to adjust concurrency.

**Configuration:**

```bash
# .env
# Memory pressure thresholds (hardcoded in code, not configurable via env)
# MEMORY_PRESSURE_WARNING_THRESHOLD = 85.0%
# MEMORY_PRESSURE_CRITICAL_THRESHOLD = 95.0%
```

### API Endpoints

```bash
# Current GPU stats
curl http://localhost:8000/api/system/gpu
# Returns: {"gpu_name": "NVIDIA RTX A5500", "gpu_utilization": 35.0, "memory_used": 4096, ...}

# GPU history (with time filter)
curl "http://localhost:8000/api/system/gpu/history?since=2025-12-30T09:45:00Z&limit=300"
# Returns: [{"recorded_at": "...", "gpu_utilization": 35.0, ...}, ...]

# System health (includes GPU status)
curl http://localhost:8000/api/system/health
```

### WebSocket Real-Time Updates

GPU stats are broadcast via WebSocket on the `/ws/system` channel:

```typescript
// Frontend: Connect to system WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/system');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'gpu_stats') {
    // Update dashboard
    console.log('GPU Utilization:', data.gpu_utilization + '%');
    console.log('Memory:', data.memory_used + '/' + data.memory_total + ' MB');
  }
};
```

### Configuration Options

| Variable                    | Default | Description                                      |
| --------------------------- | ------- | ------------------------------------------------ |
| `GPU_POLL_INTERVAL_SECONDS` | `5.0`   | Seconds between GPU stat collection              |
| `GPU_STATS_HISTORY_MINUTES` | `60`    | Minutes of history to retain in memory           |
| `GPU_HTTP_TIMEOUT`          | `5.0`   | Timeout for AI container health endpoint queries |

**Tuning recommendations:**

| Poll Interval | Use Case                            |
| ------------- | ----------------------------------- |
| 1-2s          | Active debugging, high visibility   |
| 5s            | Normal operation (default)          |
| 15-30s        | Heavy AI workloads, reduce overhead |

### Dashboard Integration

The frontend dashboard displays GPU metrics in the **System Status** panel:

- **GPU Utilization Gauge** - Real-time percentage with color coding
- **VRAM Usage Bar** - Memory used/total with warning thresholds
- **Temperature Indicator** - Current GPU temperature
- **Power Draw** - Current power consumption

### Troubleshooting

**No GPU metrics displayed:**

```bash
# Verify GPU is accessible
nvidia-smi

# Check backend logs for GPU monitor initialization
podman compose -f docker-compose.prod.yml logs backend | grep -i gpu

# Test AI container health endpoint
curl http://localhost:8090/yolo26/health  # ai-gateway /yolo26 router
```

**High memory pressure alerts:**

1. Check for memory leaks in AI containers
2. Reduce `AI_MAX_CONCURRENT_INFERENCES` setting
3. Restart AI containers to clear fragmented memory
4. Consider batching fewer images per request

---

## Token Tracking

Token tracking answers one operational question: **does the prompt the backend is about to
send fit the llama.cpp slot it will land in?** On the shipped path the answer is produced by
`backend/services/vlm_client.py::_fitted_prompt`, which counts with
`backend/services/token_counter.py` and then drops the lowest-ranked detection rows until
the rendered prompt fits. It is a _row_ fitter, not a section editor: nothing rewrites the
prompt's prose to save tokens.

### The Budget

The slot size is a pair, and both halves are read by two processes — the llama.cpp container
and the backend client:

| Setting        | Default | Who reads it                                                                      |
| -------------- | ------- | --------------------------------------------------------------------------------- |
| `VLM_CTX_SIZE` | `32768` | `ai-vlm` (`CTX_SIZE=${VLM_CTX_SIZE:-32768}`) and `config.py` `vlm_context_window` |
| `VLM_PARALLEL` | `2`     | `ai-vlm` (`PARALLEL=${VLM_PARALLEL:-2}`) and `config.py` `vlm_slot_count`         |

llama.cpp splits one context pool across its slots, so one `vlm_assess` gets
`VLM_CTX_SIZE / VLM_PARALLEL` — **16,384 tokens** as shipped. From that the client reserves
the verdict's output (`_ASSESS_MAX_TOKENS = 1024`) and the attached stills
(`_IMAGE_TOKENS_PER_FRAME = 1280` × the number of frames offered, capped at the selector's
`MAX_KEY_FRAMES`) before it counts a single word of detection text.

> [!WARNING]
> The legacy `CTX_SIZE` / `PARALLEL` pair still appears in `docker-compose.prod.yml` under
> `backend` (`CTX_SIZE=${CTX_SIZE:-262144}`, `PARALLEL=${PARALLEL:-8}`) and still feeds the
> legacy field `config.py` `nemotron_context_window`. It sizes **nothing** on the shipped
> path — the `ai-vlm` container's pool comes from `VLM_CTX_SIZE`. Changing these two to
> "give the VLM more room" moves a number no request reads.

### Utilization Thresholds

| Threshold                               | Default | Behavior                                                                               |
| --------------------------------------- | ------- | -------------------------------------------------------------------------------------- |
| `CONTEXT_UTILIZATION_WARNING_THRESHOLD` | `0.80`  | Warns (and bumps `hsi_prompts_high_utilization_total`) inside `validate_prompt()` only |
| `CONTEXT_TRUNCATION_ENABLED`            | `true`  | Declared in `config.py`; the live row fitter does not consult it                       |

### Prometheus Metrics

| Metric                               | Type      | Emitted on the live path |                                                                                               |
| ------------------------------------ | --------- | ------------------------ | --------------------------------------------------------------------------------------------- |
| `hsi_prompts_truncated_total`        | Counter   | **yes**                  | `record_prompt_truncated()` fires in `vlm_client.assess` when the fitter dropped rows         |
| `hsi_llm_context_utilization`        | Histogram | no                       | Observed only inside `TokenCounter.validate_prompt()`, which the shipped client does not call |
| `hsi_prompts_high_utilization_total` | Counter   | no                       | Same call site                                                                                |

So a truncation panel is real and a context-utilization panel reads flat-zero. The engine's
own view of the slot is more useful here — the `ai-vlm-metrics` job scrapes `llama_*`
series from `ai-vlm:8098/metrics`:

```promql
# Tokens the engine has generated (throughput proxy)
rate(llama_tokens_predicted_total[5m])

# Requests currently occupying a slot
llama_requests_processing
```

### What the Fitter Drops

Rows are ranked strongest-first (`_rank_for_budget`: confidence, then lowest row id, so the
survivors never depend on arrival order) and a binary search finds the largest list that
fits; the dropped tail is announced to the model in the prompt itself:

```
[N further detections were omitted from this list to fit the model's context
budget; the K listed are the highest-confidence rows and are the ones the
attached frame(s) were selected around]
```

`Event.llm_prompt` stores the **fitted** text (the client exposes `prompt_text()` for
exactly this reason), so the row in the database records the question that was actually
asked, marker included. A full batch does not fit the slot by design: ~61 tokens per
detection row × `BATCH_MAX_DETECTIONS=500` is ~30K against a 16,384-token slot. Seeing
truncation on a busy camera is the fitter working, not a fault — read it as "the verdict was
made from the top N rows".

### Troubleshooting

**Verdicts that mention missing detections, or a rising `hsi_prompts_truncated_total`:**

1. Confirm the slot, don't guess: `curl -s http://localhost:8098/props | jq '.default_ctx_size, .n_ctx_per_slot?'`
2. Check the batch size feeding it (`BATCH_MAX_DETECTIONS`) — a wider window means more rows per prompt
3. Widen the slot with `VLM_CTX_SIZE` (raise `VLM_PARALLEL`'s divisor effect in mind: the
   per-slot figure is `VLM_CTX_SIZE / VLM_PARALLEL`), then recreate `ai-vlm`
   (`up -d --force-recreate ai-vlm`, no flag) and restart the backend so both processes
   agree

```bash
# Truncation counter
curl -s http://localhost:8000/api/metrics | grep hsi_prompts_truncated_total

# The client's own log line when it drops rows
podman compose -f docker-compose.prod.yml logs backend | grep "vlm prompt truncated"
```

---

## Distributed Tracing

OpenTelemetry distributed tracing enables end-to-end request tracking across services.

### How It Works

When enabled, OpenTelemetry automatically instruments:

- **FastAPI** - HTTP request/response tracing
- **HTTPX** - Outgoing HTTP requests to AI services
- **SQLAlchemy** - Database query tracing
- **Redis** - Cache operation tracing

Trace context is propagated via W3C Trace Context headers (`traceparent`, `tracestate`).

### Configuration

| Variable                      | Default                                                                            | Description                        |
| ----------------------------- | ---------------------------------------------------------------------------------- | ---------------------------------- |
| `OTEL_ENABLED`                | `false` in `.env.example`; compose defaults it to `true` for the backend service   | Enable/disable distributed tracing |
| `OTEL_SERVICE_NAME`           | `nemotron-backend`                                                                 | Service name in traces             |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` in `.env.example`; compose defaults to `http://alloy:4317` | OTLP gRPC endpoint                 |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true`                                                                             | Use insecure connection            |
| `OTEL_TRACE_SAMPLE_RATE`      | `1.0`                                                                              | Sampling rate (0.0-1.0)            |

**Enable tracing** (already the default inside the compose stack):

```bash
# .env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4317
```

### Trace Collection Pipeline

The backend exports OTLP/gRPC to **Alloy** (`alloy:4317`), which forwards traces to
**Grafana Tempo** (`tempo:4317`) — see `monitoring/alloy/config.alloy`
(`otelcol.receiver.otlp` -> `otelcol.exporter.otlp "tempo"`). Tempo is a compose service
(`docker.io/grafana/tempo:2.7.1`, config `monitoring/tempo/tempo-config.yml`) with its
querier on port 3200. Any OTLP-compatible backend works in Tempo's place if you repoint
`OTEL_EXPORTER_OTLP_ENDPOINT`.

### Log-to-Trace Correlation

All log entries automatically include trace context when OpenTelemetry is active:

```json
{
  "timestamp": "2025-01-09T10:30:45.123Z",
  "level": "INFO",
  "message": "Detection complete",
  "trace_id": "1234abcd5678ef901234abcd5678ef90",
  "span_id": "abcdef1234567890",
  "correlation_id": "req-abc123",
  "camera_id": "front_door"
}
```

**Query logs by trace ID (Grafana Loki):**

```logql
{job="backend"} |= "1234abcd5678ef901234abcd5678ef90" # pragma: allowlist secret
```

### Request ID and Correlation ID

In addition to trace IDs, the system generates:

- **request_id** - Unique ID for each HTTP request
- **correlation_id** - Cross-service correlation (from `X-Correlation-ID` header or generated)

These are included in all logs and can be used for debugging when OpenTelemetry is disabled.

### Custom Spans

For detailed tracing of specific operations, use the tracing utilities:

```python
from backend.core.telemetry import trace_span, trace_function, get_trace_id

# Context manager for spans
with trace_span("detect_objects", camera_id="front_door") as span:
    results = await detector.detect(image_path)
    span.set_attribute("detection_count", len(results))

# Decorator for functions
@trace_function("analyze_batch")
async def analyze_batch(batch_id: str) -> AnalysisResult:
    # Automatically traced
    ...

# Get trace ID for logging
logger.info("Processing", extra={"trace_id": get_trace_id()})
```

### Viewing Traces

Traces are queried through **Grafana Tempo** (there is no standalone Jaeger UI port):

1. Open Grafana (http://localhost:3002, or through the frontend proxy at `/grafana/`)
2. Go to Explore > select the **Tempo** datasource
3. Search by trace ID or by tag query
4. View trace details with linked Loki logs

The frontend also embeds this at the `/tracing` page (see [docs/ui/tracing.md](../ui/tracing.md)).

### Sampling Configuration

For high-traffic deployments, configure sampling to reduce trace volume:

```bash
# Sample 10% of traces
OTEL_TRACE_SAMPLE_RATE=0.1

# Sample all traces (development)
OTEL_TRACE_SAMPLE_RATE=1.0
```

### Troubleshooting

**No traces appearing:**

```bash
# Verify OTEL is enabled
grep OTEL .env

# Check backend logs for initialization
podman compose -f docker-compose.prod.yml logs backend | grep -i telemetry

# Test OTLP endpoint connectivity (host port 4317 maps to Tempo's OTLP gRPC;
# inside the compose network the backend sends to alloy:4317)
curl -v http://localhost:4317
```

**Missing spans:**

1. Verify instrumentation is initialized (check startup logs)
2. Check sampling rate is not too low
3. Ensure trace context headers are propagated between services

**High trace volume:**

1. Reduce `OTEL_TRACE_SAMPLE_RATE` (e.g., 0.1 for 10%)
2. Configure head-based or tail-based sampling in collector
3. Filter out health check endpoints in collector config

---

## Prometheus Metrics Reference

All metrics are exposed at `/metrics` endpoint:

```bash
curl http://localhost:8000/metrics
```

### GPU Metrics

GPU hardware metrics are **not** exposed as Prometheus metrics. Instead, GPU stats are:

- Stored in PostgreSQL (`gpu_stats` table) for historical analysis
- Available via REST API (`/api/system/gpu`, `/api/system/gpu/history`)
- Broadcast via WebSocket (`/ws/system` channel)

The only GPU-related Prometheus metric tracks AI inference time:

| Metric                  | Type    | Description                                                     |
| ----------------------- | ------- | --------------------------------------------------------------- |
| `hsi_gpu_seconds_total` | Counter | Total GPU time consumed by AI model inference (labels: `model`) |

### Token/Context Metrics

| Metric                               | Type      | Live?    | Description                                             |
| ------------------------------------ | --------- | -------- | ------------------------------------------------------- |
| `hsi_prompts_truncated_total`        | Counter   | yes      | `vlm_assess` prompts the row fitter had to shorten      |
| `hsi_llm_context_utilization`        | Histogram | declared | Ratio recorded by `TokenCounter.validate_prompt()` only |
| `hsi_prompts_high_utilization_total` | Counter   | declared | Same call site                                          |

"declared" means the family exists in `backend/core/metrics.py` but nothing on the shipped
VLM path observes it, so it reads zero rather than low. See
[Token Tracking](#token-tracking) above.

### Request Tracing Metrics

| Metric                          | Type      | Description          |
| ------------------------------- | --------- | -------------------- |
| `http_request_duration_seconds` | Histogram | HTTP request latency |
| `http_requests_total`           | Counter   | Total HTTP requests  |

---

## Quick Reference

### Enable Full Observability

```bash
# .env
# GPU Monitoring (enabled by default)
GPU_POLL_INTERVAL_SECONDS=5.0

# Token Tracking (enabled by default)
CONTEXT_UTILIZATION_WARNING_THRESHOLD=0.80
CONTEXT_TRUNCATION_ENABLED=true

# Distributed Tracing (already on by default in docker-compose.prod.yml)
OTEL_ENABLED=true
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4317
```

### Diagnostic Commands

```bash
# GPU status
nvidia-smi
curl http://localhost:8000/api/system/gpu

# Prometheus metrics
curl http://localhost:8000/metrics | grep hsi_

# Backend logs with trace context
podman compose -f docker-compose.prod.yml logs backend | grep trace_id
```

---

## Monitoring Stack Services

The monitoring stack is included by default in `docker-compose.prod.yml` and provides full observability for the Home Security Intelligence system. This section documents each monitoring service, its purpose, configuration options, and how to access and use it.

### Service Overview

All ports below are the host bindings from `docker-compose.prod.yml` (bound to
`127.0.0.1` unless noted).

| Service           | Host Port  | Purpose                                         | Access URL                                                           |
| ----------------- | ---------- | ----------------------------------------------- | -------------------------------------------------------------------- |
| Prometheus        | 9090       | Metrics collection and alerting rules           | http://localhost:9090                                                |
| Grafana           | 3002       | Dashboards and visualization                    | http://localhost:3002 (direct) or `/grafana/` via the frontend proxy |
| Tempo             | 3200, 4317 | Distributed tracing (replaces Jaeger, NEM-5545) | via Grafana Explore / `/tracing` page                                |
| Alertmanager      | 9093       | Alert routing and delivery                      | http://localhost:9093                                                |
| Loki              | 3100       | Log storage                                     | http://localhost:3100/ready                                          |
| Alloy             | 12345      | Log/eBPF-profile/trace collection               | http://localhost:12345                                               |
| Pyroscope         | 4040       | Continuous profiling                            | http://localhost:4040                                                |
| Blackbox Exporter | 9115       | HTTP/TCP endpoint probing                       | http://localhost:9115                                                |
| JSON Exporter     | 7979       | JSON-to-Prometheus metric conversion            | http://localhost:7979                                                |
| Redis Exporter    | 9121       | Redis metrics for Prometheus                    | http://localhost:9121                                                |

---

### Tempo (Distributed Tracing)

Grafana Tempo provides distributed tracing for cross-service request correlation. When a
request flows through multiple services (frontend -> backend -> AI services ->
database), the backend's OpenTelemetry exporter sends spans to Alloy, Alloy forwards
them to Tempo, and traces are queried through Grafana. Tempo **replaced Jaeger +
Elasticsearch** under NEM-5545; the compose stack has no jaeger or elasticsearch
service.

**Port Mappings:**

| Port | Protocol | Purpose                             |
| ---- | -------- | ----------------------------------- |
| 3200 | HTTP     | Tempo querier / query API           |
| 4317 | gRPC     | OTLP gRPC receiver (host-published) |

**Configuration:** `monitoring/tempo/tempo-config.yml`, mounted read-only with the
`tempo_data` named volume for block storage. Limits: 1 CPU / 1G memory. Healthcheck
spiders `http://localhost:3200/ready`.

**Accessing traces:**

1. Open Grafana (http://localhost:3002 or `/grafana/` through the frontend)
2. Explore -> **Tempo** datasource (provisioned at `monitoring/grafana/provisioning/datasources/`, url `http://tempo:3200`)
3. Search by trace ID or tag query

The dashboard's **Tracing** page embeds the same query flow (see
[docs/ui/tracing.md](../ui/tracing.md)).

**Connecting the backend:** already wired in `docker-compose.prod.yml`:

```bash
OTEL_ENABLED=true                                   # compose default for backend
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4317       # Alloy forwards to tempo:4317
OTEL_TRACE_SAMPLE_RATE=1.0                          # 1.0 = 100% of traces
```

**Useful Queries:**

```bash
# Check Tempo readiness
curl http://localhost:3200/ready

# Fetch a trace by ID (replace <trace_id>)
curl "http://localhost:3200/api/trace/<trace_id>" | jq '.batch | length'
```

**Production Considerations:**

1. **Storage**: traces land in the `tempo_data` volume; retention/compaction settings live in `monitoring/tempo/tempo-config.yml`
2. **Sampling**: reduce `OTEL_TRACE_SAMPLE_RATE` to 0.1 (10%) for high-traffic systems
3. **Dependency**: Grafana waits for Prometheus health; Alloy (the trace path) depends on Loki and Pyroscope, not Tempo

---

### Blackbox Exporter (Synthetic Monitoring)

The blackbox exporter performs external endpoint probing to measure availability, latency, and health status. It simulates external client requests to detect issues before users report them.

**Port:** 9115

**Configuration File:** `monitoring/blackbox-exporter.yml`

**Available Probe Modules:**

| Module        | Type | Timeout | Purpose                                        |
| ------------- | ---- | ------- | ---------------------------------------------- |
| `http_2xx`    | HTTP | 5s      | Basic HTTP availability (200 OK)               |
| `http_health` | HTTP | 10s     | Health endpoint with JSON body validation      |
| `http_ready`  | HTTP | 15s     | Readiness probe (stricter, for load balancing) |
| `http_live`   | HTTP | 5s      | Liveness probe (basic availability)            |
| `http_api`    | HTTP | 10s     | API endpoint (200, 201, 204 status codes)      |
| `tcp_connect` | TCP  | 5s      | TCP port connectivity                          |
| `tcp_tls`     | TCP  | 10s     | TCP with TLS validation                        |
| `dns_resolve` | DNS  | 5s      | DNS resolution test                            |
| `icmp_ping`   | ICMP | 5s      | Network reachability (requires privileges)     |

**How Prometheus Uses Blackbox Exporter:**

Prometheus scrapes blackbox exporter with target URLs as parameters. Example scrape configs from `prometheus.yml`:

```yaml
# HTTP Health probes
- job_name: 'blackbox-http-health'
  metrics_path: /probe
  params:
    module: [http_health]
  static_configs:
    - targets:
        - http://backend:8000/api/system/health
```

**Probed Endpoints (Default Configuration):**

| Probe Type               | Endpoints Monitored                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| Health                   | `backend:8000/api/system/health`                                                                                    |
| Readiness                | `backend:8000/api/system/health/ready`                                                                              |
| Liveness                 | `backend:8000/health`, `frontend:8080`                                                                              |
| AI (`blackbox-http-2xx`) | `ai-vlm:8098/health`, `ai-gateway:8090/health`, `ai-gateway:8090/yolo26/health`, `ai-gateway:8090/enrich-lt/health` |
| TCP                      | `postgres:5432`, `redis:6379`                                                                                       |

> [!WARNING]
> The `ai-vlm` target in that job is the shape of the failure it cannot see. `ai-vlm` is in
> the default compose set, so a default `up` asks for it — but on a machine with no GPU the
> service fails at start and the probe reports `probe_success 0` for an engine that cannot
> run there, and `ai-vlm`'s own `/health` passes even when the multimodal projector is
> absent. A green/black probe here is not a verdict that reasoning works; prove that with
> `/props` and the multimodal check in [Monitoring Guide](monitoring/README.md) /
> [AI Troubleshooting](ai-troubleshooting.md).

**Key Metrics Exported:**

| Metric                           | Description                          |
| -------------------------------- | ------------------------------------ |
| `probe_success`                  | 1 if probe succeeded, 0 if failed    |
| `probe_duration_seconds`         | Total probe duration                 |
| `probe_http_status_code`         | HTTP response status code            |
| `probe_http_duration_seconds`    | HTTP request duration by phase       |
| `probe_ssl_earliest_cert_expiry` | SSL certificate expiration timestamp |

**Testing Probes Manually:**

```bash
# Test HTTP health probe
curl "http://localhost:9115/probe?target=http://backend:8000/api/system/health&module=http_health"

# Test TCP probe
curl "http://localhost:9115/probe?target=postgres:5432&module=tcp_connect"

# View blackbox exporter metrics
curl http://localhost:9115/metrics
```

**Adding Custom Probes:**

Edit `monitoring/blackbox-exporter.yml` to add custom probe modules:

```yaml
modules:
  custom_api:
    prober: http
    timeout: 10s
    http:
      valid_status_codes: [200, 201]
      fail_if_body_not_matches_regexp:
        - '"success":\s*true'
```

Then add to Prometheus scrape config in `monitoring/prometheus.yml`.

---

### JSON Exporter (Custom Metrics)

The JSON exporter converts JSON API responses into Prometheus metrics. This is useful for extracting metrics from endpoints that return JSON but do not expose native Prometheus metrics.

**Port:** 7979

**Configuration File:** `monitoring/json-exporter-config.yml`

**Available Modules:**

| Module      | Source Endpoint         | Metrics Extracted                                  |
| ----------- | ----------------------- | -------------------------------------------------- |
| `health`    | `/api/system/health`    | System, database, Redis, AI health status          |
| `telemetry` | `/api/system/telemetry` | Queue depths, latencies (detect, batch, analyze)   |
| `stats`     | `/api/system/stats`     | Camera count, event count, detection count, uptime |
| `gpu`       | `/api/system/gpu`       | GPU utilization, memory, temperature, power        |

**Metrics from Health Module:**

| Metric                 | Type  | Description                                                  |
| ---------------------- | ----- | ------------------------------------------------------------ |
| `hsi_system_healthy`   | Gauge | Overall system health (1=healthy, 0.5=degraded, 0=unhealthy) |
| `hsi_database_healthy` | Gauge | Database connection status                                   |
| `hsi_redis_healthy`    | Gauge | Redis connection status                                      |
| `hsi_ai_healthy`       | Gauge | AI services status                                           |

**Metrics from Telemetry Module:**

| Metric                       | Type  | Description                       |
| ---------------------------- | ----- | --------------------------------- |
| `hsi_detection_queue_depth`  | Gauge | Items waiting in detection queue  |
| `hsi_analysis_queue_depth`   | Gauge | Batches waiting for LLM analysis  |
| `hsi_detect_latency_avg_ms`  | Gauge | Average detection latency (ms)    |
| `hsi_detect_latency_p95_ms`  | Gauge | P95 detection latency (ms)        |
| `hsi_analyze_latency_avg_ms` | Gauge | Average LLM analysis latency (ms) |
| `hsi_analyze_latency_p95_ms` | Gauge | P95 LLM analysis latency (ms)     |

**Metrics from GPU Module:**

| Metric                      | Type  | Description                        |
| --------------------------- | ----- | ---------------------------------- |
| `hsi_gpu_utilization`       | Gauge | GPU compute utilization (%)        |
| `hsi_gpu_memory_used_mb`    | Gauge | GPU memory in use (MB)             |
| `hsi_gpu_memory_total_mb`   | Gauge | Total GPU memory (MB)              |
| `hsi_gpu_temperature`       | Gauge | GPU temperature (Celsius)          |
| `hsi_inference_fps`         | Gauge | Inference throughput (frames/sec)  |
| `hsi_gpu_throttle_reasons`  | Gauge | Throttle reasons bitfield (0=none) |
| `hsi_gpu_power_limit_watts` | Gauge | GPU power limit (watts)            |

**How It Works:**

1. Prometheus scrapes JSON exporter with target URL as parameter
2. JSON exporter fetches the target URL
3. JSON exporter extracts values using JSONPath expressions
4. Values are converted to Prometheus metrics

**Testing JSON Exporter:**

```bash
# Test health metrics extraction
curl "http://localhost:7979/probe?target=http://backend:8000/api/system/health&module=health"

# Test GPU metrics extraction
curl "http://localhost:7979/probe?target=http://backend:8000/api/system/gpu&module=gpu"

# View JSON exporter own metrics
curl http://localhost:7979/metrics
```

**Adding Custom Metrics:**

Edit `monitoring/json-exporter-config.yml`:

```yaml
modules:
  custom:
    metrics:
      - name: my_custom_metric
        path: '{ .some.json.path }'
        type: value
        help: 'Description of the metric'
```

---

### Redis Exporter

The Redis exporter collects Redis metrics and exposes them in Prometheus format. This enables monitoring of Redis memory usage, connection counts, command statistics, and replication status.

**Port:** 9121

**Environment Variables:**

| Variable         | Default              | Description                   |
| ---------------- | -------------------- | ----------------------------- |
| `REDIS_ADDR`     | `redis://redis:6379` | Redis server address          |
| `REDIS_PASSWORD` | (empty)              | Redis authentication password |

**Key Metrics Exported:**

| Metric                           | Type    | Description                         |
| -------------------------------- | ------- | ----------------------------------- |
| `redis_up`                       | Gauge   | Redis server availability (1=up)    |
| `redis_connected_clients`        | Gauge   | Number of connected clients         |
| `redis_blocked_clients`          | Gauge   | Clients blocked on BLPOP/BRPOP      |
| `redis_memory_used_bytes`        | Gauge   | Total memory used by Redis          |
| `redis_memory_max_bytes`         | Gauge   | Maximum memory limit (if set)       |
| `redis_commands_processed_total` | Counter | Total commands processed            |
| `redis_keyspace_hits_total`      | Counter | Cache hits                          |
| `redis_keyspace_misses_total`    | Counter | Cache misses                        |
| `redis_expired_keys_total`       | Counter | Total expired keys                  |
| `redis_evicted_keys_total`       | Counter | Keys evicted due to memory pressure |
| `redis_db_keys`                  | Gauge   | Number of keys per database         |
| `redis_connected_slaves`         | Gauge   | Connected replicas (if replication) |

**Useful PromQL Queries:**

```promql
# Redis memory utilization percentage
redis_memory_used_bytes / redis_memory_max_bytes * 100

# Cache hit rate
rate(redis_keyspace_hits_total[5m]) /
(rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))

# Commands per second
rate(redis_commands_processed_total[1m])

# Client connection growth
increase(redis_connected_clients[1h])
```

**Accessing Redis Exporter:**

```bash
# View all Redis metrics
curl http://localhost:9121/metrics

# Check Redis connectivity
curl http://localhost:9121/metrics | grep redis_up
```

**Health Check Note:**

The Redis exporter container does not have wget/curl installed (minimal Go binary), so container health checks are disabled. Prometheus scraping success serves as the health indicator.

**Security Configuration:**

If Redis authentication is enabled, ensure the exporter has the same password:

```bash
# In .env
REDIS_PASSWORD=your_secure_password
```

Both the Redis service and Redis exporter use this environment variable.

---

---

### Alloy (Log Collection)

Alloy is Grafana's telemetry collector. It runs three pipelines
(`monitoring/alloy/config.alloy`): container logs from Podman -> **Loki**, OTLP traces
(received on `0.0.0.0:4317` from the backend) -> **Tempo**, and eBPF-based continuous
profiles -> **Pyroscope**.

**Port:** 12345 (Alloy UI, `ALLOY_UI_PORT`); internal OTLP receivers on 4317/4318

**Configuration File:** `monitoring/alloy/config.alloy`

**Dependencies:**

- **Loki** - Log storage backend (port 3100)
- **Pyroscope** - Profile storage backend (port 4040) — `depends_on: [loki, pyroscope]`
- **Podman Socket** - Container discovery and log collection

**CRITICAL: Podman Socket Requirement**

Alloy requires access to the Podman socket to discover running containers and collect their logs. The socket **must be enabled** before starting the monitoring stack.

**Enable Podman Socket (one-time setup):**

```bash
# Start the Podman socket service
systemctl --user start podman.socket

# Enable it to start automatically on boot
systemctl --user enable podman.socket

# Verify the socket is active
systemctl --user status podman.socket

# Verify the socket file exists
ls -l /run/user/1000/podman/podman.sock
```

Expected output:

```
srw-rw----. 1 user user 0 Jan 23 14:09 /run/user/1000/podman/podman.sock
```

**Socket Mount:**

The `docker-compose.prod.yml` file mounts the Podman socket into the Alloy container.
The path comes from the `PODMAN_SOCKET` variable (your actual UID, not always 1000),
and the mount is read-write because Alloy reads container logs through the Podman API:

```yaml
volumes:
  - ${PODMAN_SOCKET:?PODMAN_SOCKET must be set}:${PODMAN_SOCKET}
```

**How It Works:**

1. **Container Discovery** - Alloy connects to the Podman socket to discover running containers
2. **Log Collection** - Alloy reads container logs directly from Podman
3. **Log Processing** - Logs are parsed and enriched with metadata (container name, image, labels)
4. **Log Forwarding** - Processed logs are sent to Loki for storage and querying

**Log Enrichment:**

Alloy automatically extracts and adds metadata to logs:

| Label            | Description                                | Source                              |
| ---------------- | ------------------------------------------ | ----------------------------------- |
| `container`      | Container name                             | `__meta_docker_container_name`      |
| `image`          | Container image name                       | `__meta_docker_container_image`     |
| `job`            | Static label (always `podman-containers`)  | Configuration                       |
| `level`          | Log level (DEBUG, INFO, WARNING, ERROR)    | Regex extraction from log line      |
| `camera`         | Camera name (from AI pipeline logs)        | Regex extraction (`camera=<name>`)  |
| `trace_id`       | OpenTelemetry trace ID (32-char hex)       | Regex extraction (`trace_id=<id>`)  |
| `span_id`        | OpenTelemetry span ID (16-char hex)        | Regex extraction (`span_id=<id>`)   |
| `batch_id`       | Batch processing ID (UUID)                 | Regex extraction (`batch_id=<id>`)  |
| `duration_ms`    | Operation duration in milliseconds         | Regex extraction (`duration=<ms>`)  |
| `pg_duration_ms` | PostgreSQL query duration (slow queries)   | Regex extraction from Postgres logs |
| `pg_event`       | PostgreSQL events (connection, checkpoint) | Regex extraction                    |

**Querying Logs in Grafana:**

```logql
# All logs from backend container
{container="backend"}

# Logs from a specific camera
{container="backend", camera="front_door"}

# Error logs only
{container="backend"} |= "ERROR"

# PostgreSQL slow queries (>1 second)
{container="postgres"} | pg_slow_query != ""

# Logs for a specific trace
{container="backend"} |= "trace_id=abc123..."

# Logs from AI services with errors
{container=~"ai-.*"} |= "error" | level="ERROR"
```

**PostgreSQL Query Logging:**

The PostgreSQL container is configured to log slow queries (>1 second) to stdout, which Alloy collects:

```yaml
# PostgreSQL logging configuration (docker-compose.prod.yml)
command:
  - postgres
  - -c
  - log_min_duration_statement=1000 # Log queries >1 second
  - -c
  - log_duration=on
  - -c
  - log_line_prefix=%t [%p] %u@%d
```

Alloy extracts query duration and connection info, making it easy to find slow queries in Grafana.

**Troubleshooting:**

**Error: "Cannot connect to the Docker daemon at unix:///run/user/1000/podman/podman.sock"**

This indicates the Podman socket is not active. Fix:

```bash
# Check if socket service is running
systemctl --user status podman.socket

# If inactive, start and enable it
systemctl --user start podman.socket
systemctl --user enable podman.socket

# Verify socket file is a socket (not a directory)
file /run/user/1000/podman/podman.sock
# Expected: /run/user/1000/podman/podman.sock: socket

# Restart Alloy to pick up the socket
podman stop alloy && podman rm alloy
podman compose -f docker-compose.prod.yml up -d alloy
```

**No logs appearing in Loki:**

```bash
# Check Alloy logs for errors
podman logs alloy 2>&1 | grep -i error

# Verify Loki is running and healthy
curl http://localhost:3100/ready

# Check if Alloy can reach Loki
podman exec alloy wget -qO- http://loki:3100/ready

# Verify log pipeline is active
curl http://localhost:12345  # Alloy UI
```

**Too many log streams error (429 from Loki):**

```
level=warn msg="error sending batch, will retry" error="server returned HTTP status 429 Too Many Requests"
```

This means Alloy is creating too many unique label combinations. Fix by:

1. Reducing labels in `monitoring/alloy/config.alloy`
2. Increasing Loki stream limits in `monitoring/loki/loki-config.yml`
3. Using log pipeline stages to drop unnecessary labels

---

### Loki (Log Storage)

Loki is a log aggregation system designed for storing and querying logs collected by Alloy.

**Port:** 3100

**Configuration File:** `monitoring/loki/loki-config.yml`

**Key Features:**

- **Label-based indexing** - Efficient querying using labels (not full-text indexing)
- **LogQL** - Powerful query language similar to PromQL
- **Grafana integration** - Native datasource for Grafana dashboards
- **Retention** - Configured in `monitoring/loki/loki-config.yml` (`retention_period: 720h` — 30 days)

**Accessing Loki:**

```bash
# Check Loki health
curl http://localhost:3100/ready

# Query logs via API
curl -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={container="backend"}' \
  --data-urlencode 'start=2026-01-23T00:00:00Z'

# View label values
curl http://localhost:3100/loki/api/v1/label/container/values
```

**Grafana Explore:**

1. Go to Grafana: http://localhost:3002
2. Navigate to **Explore** (compass icon)
3. Select **Loki** datasource from dropdown
4. Use LogQL to query logs
5. Click **Split** to compare multiple queries side-by-side

**Resource Limits:**

```yaml
# docker-compose.prod.yml
deploy:
  resources:
    limits:
      cpus: '0.25'
      memory: 1G
```

For high-volume deployments, increase memory limits and configure object storage (S3, GCS) for log storage.

---

### Pyroscope (Continuous Profiling)

Pyroscope provides continuous profiling for Python services, helping identify CPU and memory hotspots in the backend and AI services.

**Port:** 4040

**Configuration File:** `monitoring/pyroscope/pyroscope-config.yml`

**How It Works:**

Services push profiling data to Pyroscope when `PYROSCOPE_ENABLED=true`:

```yaml
# Backend service (docker-compose.prod.yml)
environment:
  - PYROSCOPE_ENABLED=true
  - PYROSCOPE_URL=http://pyroscope:4040
labels:
  pyroscope.profile: 'true'
  pyroscope.service: 'backend'
```

**Profiled Services:**

- `backend` - FastAPI backend (SDK-based py-spy profiling when `PYROSCOPE_ENABLED=true`)
- `ai-vlm` - llama.cpp process, profiled via Alloy's **eBPF** pipeline (container labels
  `pyroscope.profile=true`, `pyroscope.service=ai-vlm` in `docker-compose.prod.yml`)
- any other container carrying the `pyroscope.profile=true` label

**Accessing Pyroscope UI:**

1. Open http://localhost:4040
2. Select a service from the dropdown
3. View CPU flame graphs, call trees, and timeline
4. Filter by time range to analyze specific periods

**Useful for:**

- Identifying slow functions
- Finding CPU bottlenecks
- Analyzing memory allocation patterns
- Comparing performance before/after changes

---

### Verifying Monitoring Stack

After starting the stack, verify all services are healthy:

```bash
# Check all monitoring containers are running
podman compose -f docker-compose.prod.yml ps | grep -E "(prometheus|grafana|tempo|loki|alloy|pyroscope|alertmanager|blackbox|json-exporter|redis-exporter|node-exporter)"

# Verify Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check for any scrape errors
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'
```

**Expected Healthy Targets:**

| Job Name               | Target                                            | Expected Health                                          |
| ---------------------- | ------------------------------------------------- | -------------------------------------------------------- |
| `hsi-backend-metrics`  | `backend:8000` (`/api/metrics`)                   | up                                                       |
| `ai-vlm-metrics`       | `ai-vlm:8098`                                     | up when `ai-vlm` is running (fails at start with no GPU) |
| `ai-gateway-metrics`   | `ai-gateway:8090` (gateway `nv_*` series dropped) | up                                                       |
| `triton-metrics`       | `ai-gateway:8002`                                 | up                                                       |
| `hsi-health`           | Backend health via JSON exporter                  | up                                                       |
| `hsi-gpu`              | Backend GPU stats via JSON exporter               | up                                                       |
| `redis`                | `redis-exporter:9121`                             | up                                                       |
| `json-exporter`        | `json-exporter:7979`                              | up                                                       |
| `blackbox-exporter`    | `blackbox-exporter:9115`                          | up                                                       |
| `blackbox-http-health` | Backend health endpoint                           | up                                                       |
| `blackbox-http-ready`  | Backend readiness endpoint                        | up                                                       |
| `blackbox-http-live`   | Backend/frontend liveness                         | up                                                       |
| `blackbox-http-2xx`    | The four AI endpoints above                       | down for `ai-vlm` wherever `ai-vlm` is not running       |
| `blackbox-tcp`         | postgres:5432, redis:6379                         | up                                                       |

`ai-vlm` is in the default compose set, so `ai-vlm-metrics` and the `ai-vlm` 2xx probe
should be `up` on a normal GPU host; both report down on a machine with no GPU, where the
service fails at start — that is expected there, not an outage. Everything else listed
here should be `up`; a `dcgm-exporter` target is also behind a profile (`gpu-rootful`).

---

## See Also

- [GPU Setup Guide](gpu-setup.md) - Initial GPU configuration
- [AI Performance](ai-performance.md) - AI service tuning
- [Prometheus Alerting](prometheus-alerting.md) - Alert configuration and routing
- [Configuration Reference](../reference/config/env-reference.md) - All environment variables
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common issues
