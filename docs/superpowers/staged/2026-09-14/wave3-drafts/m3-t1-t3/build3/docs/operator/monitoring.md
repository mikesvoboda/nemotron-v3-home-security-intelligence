# Monitoring and Observability

> GPU monitoring, LLM token tracking, and distributed tracing for the Home Security Intelligence system.

This guide covers the three core observability pillars:

1. **GPU Monitoring** - Real-time GPU metrics and memory pressure alerts
2. **Token Tracking** - LLM context window management and utilization metrics
3. **Distributed Tracing** - OpenTelemetry integration for cross-service debugging

---

## GPU Monitoring

The GPU monitoring service (`GPUMonitor`) provides real-time metrics for NVIDIA GPUs used by AI services (YOLO26 and Nemotron).

### How It Works

The GPU monitor uses a fallback strategy to collect metrics:

1. **pynvml** (preferred) - Direct NVIDIA Management Library bindings for lowest latency
2. **nvidia-smi** - Subprocess fallback when pynvml is unavailable (containerized environments)
3. **AI Container Endpoints** - Queries YOLO26 `/health` endpoint for GPU stats
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
docker compose -f docker-compose.prod.yml logs backend | grep -i gpu

# Test AI container health endpoint
curl http://localhost:8095/health  # YOLO26
```

**High memory pressure alerts:**

1. Check for memory leaks in AI containers
2. Reduce `AI_MAX_CONCURRENT_INFERENCES` setting
3. Restart AI containers to clear fragmented memory
4. Consider batching fewer images per request

---

## Token Tracking

The token tracking service (`TokenCounter`) manages LLM context window utilization for the Nemotron analyzer.

### How It Works

Token counting uses [tiktoken](https://github.com/openai/tiktoken) for accurate tokenization:

1. **Prompt Validation** - Validates prompts fit within context limits before sending to LLM
2. **Utilization Tracking** - Records context utilization metrics for monitoring
3. **Intelligent Truncation** - Removes lower-priority enrichment sections when approaching limits

### Context Window Configuration

The Nemotron model context window varies by deployment profile:

| Model Profile                               | Context Window | VRAM Required |
| ------------------------------------------- | -------------- | ------------- |
| **Production (Nemotron-3-Nano-30B-A3B)**    | 131,072 tokens | ~14.7 GB      |
| **Development (Nemotron Mini 4B Instruct)** | 4,096 tokens   | ~3 GB         |

**Environment Variables:**

| Setting                      | Default       | Description                          |
| ---------------------------- | ------------- | ------------------------------------ |
| `NEMOTRON_CONTEXT_WINDOW`    | `131072`      | Total context window size (tokens)   |
| `NEMOTRON_MAX_OUTPUT_TOKENS` | `1536`        | Tokens reserved for LLM output       |
| `LLM_TOKENIZER_ENCODING`     | `cl100k_base` | Tiktoken encoding (GPT-4 compatible) |

**Note:** The `CTX_SIZE` environment variable in the AI container (`ai/nemotron/`) controls the llama.cpp server context size, while `NEMOTRON_CONTEXT_WINDOW` controls the backend's prompt validation. Both should be configured consistently.

**Available tokens for prompt:** `context_window - max_output_tokens`

- Production (128K): 131,072 - 1,536 = **129,536 tokens**
- Development (4K): 4,096 - 1,536 = **2,560 tokens**

### Utilization Thresholds

| Threshold                               | Default      | Behavior                                |
| --------------------------------------- | ------------ | --------------------------------------- |
| `CONTEXT_UTILIZATION_WARNING_THRESHOLD` | `0.80` (80%) | Logs warning when utilization exceeds   |
| `CONTEXT_TRUNCATION_ENABLED`            | `true`       | Enables automatic enrichment truncation |

When context utilization exceeds the warning threshold (default 80%), a warning is logged but the prompt is still processed.

### Prometheus Metrics

| Metric                               | Type      | Description                          |
| ------------------------------------ | --------- | ------------------------------------ |
| `hsi_llm_context_utilization`        | Histogram | Context utilization ratio (0.0-1.0+) |
| `hsi_prompts_high_utilization_total` | Counter   | Prompts exceeding warning threshold  |

**Query examples (Prometheus/Grafana):**

```promql
# Average context utilization (sum of values / count)
hsi_llm_context_utilization_sum / hsi_llm_context_utilization_count

# High utilization rate (last hour)
rate(hsi_prompts_high_utilization_total[1h])

# Context utilization 95th percentile
histogram_quantile(0.95, rate(hsi_llm_context_utilization_bucket[5m]))
```

### Intelligent Truncation

When prompts exceed context limits, the token counter removes enrichment sections in priority order (lowest priority first):

**Truncation Priority (removed first to last):**

1. `depth_context` - Often not critical
2. `pose_analysis` - Future feature placeholder
3. `action_recognition` - Future feature placeholder
4. `pet_classification_context` - Nice to have
5. `image_quality_context` - Informational
6. `weather_context` - Informational
7. `vehicle_damage_context` - Can be summarized
8. `vehicle_classification_context` - Can be summarized
9. `clothing_analysis_context` - Can be summarized
10. `violence_context` - Important but can be summarized
11. `reid_context` - Important for tracking
12. `cross_camera_summary` - Important for correlation
13. `baseline_comparison` - Important for anomaly detection
14. `zone_analysis` - Important for context
15. `detections_with_all_attributes` - High priority (core data)
16. `scene_analysis` - High priority (core analysis)

### API Usage

The token counter is used internally by the Nemotron analyzer:

```python
from backend.services.token_counter import get_token_counter

counter = get_token_counter()

# Count tokens in a prompt
token_count = counter.count_tokens(prompt_text)

# Validate prompt fits in context
result = counter.validate_prompt(prompt_text)
if not result.is_valid:
    # Truncate enrichment data
    truncated = counter.truncate_enrichment_data(prompt_text, max_tokens=2364)
    print(f"Removed sections: {truncated.sections_removed}")

# Get context budget
budget = counter.get_context_budget()
# {"context_window": 3900, "max_output_tokens": 1536, "available_for_prompt": 2364}
```

### Troubleshooting

**Prompts being truncated:**

1. Check logs for truncation warnings
2. Review `sections_removed` in truncation results
3. Consider increasing `NEMOTRON_CONTEXT_WINDOW` if using a larger model
4. Disable less useful enrichment sources

**High context utilization alerts:**

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep hsi_llm_context

# Review recent prompts in logs
docker compose -f docker-compose.prod.yml logs backend | grep "context utilization"
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

| Variable                      | Default                 | Description                        |
| ----------------------------- | ----------------------- | ---------------------------------- |
| `OTEL_ENABLED`                | `false`                 | Enable/disable distributed tracing |
| `OTEL_SERVICE_NAME`           | `nemotron-backend`      | Service name in traces             |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint                 |
| `OTEL_EXPORTER_OTLP_INSECURE` | `true`                  | Use insecure connection            |
| `OTEL_TRACE_SAMPLE_RATE`      | `1.0`                   | Sampling rate (0.0-1.0)            |

**Enable tracing:**

```bash
# .env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### Trace Collection Backends

The system exports traces to any OTLP-compatible backend:

| Backend               | Endpoint             | Description                 |
| --------------------- | -------------------- | --------------------------- |
| **Jaeger**            | `http://jaeger:4317` | Popular open-source tracing |
| **Grafana Tempo**     | `http://tempo:4317`  | Grafana-native tracing      |
| **Zipkin** (via OTLP) | `http://zipkin:4317` | Alternative tracing backend |

**Docker Compose addition for Jaeger:**

```yaml
# docker-compose.override.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - '16686:16686' # Jaeger UI
      - '4317:4317' # OTLP gRPC
    environment:
      COLLECTOR_OTLP_ENABLED: 'true'
```

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

**Jaeger UI (default: http://localhost:16686):**

1. Select service: `nemotron-backend`
2. Search by operation or trace ID
3. View span timeline and service map

**Grafana Tempo:**

1. Go to Explore > Tempo
2. Search by trace ID or query
3. View trace details with linked logs

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
docker compose -f docker-compose.prod.yml logs backend | grep -i telemetry

# Test OTLP endpoint connectivity
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

| Metric                               | Type      | Description                         |
| ------------------------------------ | --------- | ----------------------------------- |
| `hsi_llm_context_utilization`        | Histogram | Context window utilization ratio    |
| `hsi_prompts_high_utilization_total` | Counter   | Prompts exceeding warning threshold |

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

# Distributed Tracing (opt-in)
OTEL_ENABLED=true
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

### Diagnostic Commands

```bash
# GPU status
nvidia-smi
curl http://localhost:8000/api/system/gpu

# Prometheus metrics
curl http://localhost:8000/metrics | grep hsi_

# Backend logs with trace context
docker compose -f docker-compose.prod.yml logs backend | grep trace_id
```

---

## Monitoring Stack Services

The monitoring stack is included by default in `docker-compose.prod.yml` and provides full observability for the Home Security Intelligence system. This section documents each monitoring service, its purpose, configuration options, and how to access and use it.

### Service Overview

| Service           | Port  | Purpose                               | Access URL             |
| ----------------- | ----- | ------------------------------------- | ---------------------- |
| Prometheus        | 9090  | Metrics collection and alerting rules | http://localhost:9090  |
| Grafana           | 3002  | Dashboards and visualization          | http://localhost:3002  |
| Jaeger            | 16686 | Distributed tracing UI                | http://localhost:16686 |
| Alertmanager      | 9093  | Alert routing and delivery            | http://localhost:9093  |
| Blackbox Exporter | 9115  | HTTP/TCP endpoint probing             | http://localhost:9115  |
| JSON Exporter     | 7979  | JSON-to-Prometheus metric conversion  | http://localhost:7979  |
| Redis Exporter    | 9121  | Redis metrics for Prometheus          | http://localhost:9121  |

---

### Jaeger (Distributed Tracing)

Jaeger provides distributed tracing for cross-service request correlation. When a request flows through multiple services (frontend -> backend -> AI services -> database), Jaeger captures the complete trace to help identify latency bottlenecks and failures.

**Port Mappings:**

| Port  | Protocol | Purpose            |
| ----- | -------- | ------------------ |
| 16686 | HTTP     | Jaeger UI          |
| 4317  | gRPC     | OTLP gRPC receiver |
| 4318  | HTTP     | OTLP HTTP receiver |

**Configuration:**

```bash
# Environment variables (docker-compose.prod.yml)
COLLECTOR_OTLP_ENABLED=true                    # Enable OTLP collector
SPAN_STORAGE_TYPE=elasticsearch                # Elasticsearch storage backend
ES_SERVER_URLS=http://elasticsearch:9200       # Elasticsearch endpoint
ES_INDEX_PREFIX=jaeger                         # Index name prefix
ES_TAGS_AS_FIELDS_ALL=true                     # Store all tags as indexed fields
ES_NUM_SHARDS=1                                # Shards per index (single-node)
ES_NUM_REPLICAS=0                              # No replicas (single-node)
```

**Environment Variables:**

| Variable                 | Default                     | Description                               |
| ------------------------ | --------------------------- | ----------------------------------------- |
| `SPAN_STORAGE_TYPE`      | `elasticsearch`             | Storage backend (elasticsearch or memory) |
| `ES_SERVER_URLS`         | `http://elasticsearch:9200` | Elasticsearch endpoint(s)                 |
| `ES_INDEX_PREFIX`        | `jaeger`                    | Index name prefix for Jaeger data         |
| `ES_TAGS_AS_FIELDS_ALL`  | `true`                      | Store all tags as indexed fields          |
| `ES_NUM_SHARDS`          | `1`                         | Number of shards per index                |
| `ES_NUM_REPLICAS`        | `0`                         | Number of replicas (0 for single-node)    |
| `ES_BULK_SIZE`           | `5000000`                   | Bulk request size in bytes                |
| `ES_BULK_WORKERS`        | `1`                         | Number of bulk workers                    |
| `ES_BULK_FLUSH_INTERVAL` | `200ms`                     | Bulk flush interval                       |

**Accessing Jaeger UI:**

1. Open http://localhost:16686
2. Select a service from the "Service" dropdown (e.g., `nemotron-backend`)
3. Click "Find Traces" to view recent traces
4. Click a trace to view the span timeline and service interactions

**Connecting Backend to Jaeger:**

The backend sends traces to Jaeger via OpenTelemetry. Configure in `.env`:

```bash
OTEL_ENABLED=true
OTEL_SERVICE_NAME=nemotron-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
OTEL_TRACE_SAMPLE_RATE=1.0  # 1.0 = 100% of traces
```

**Useful Queries:**

```bash
# Check Jaeger health
curl http://localhost:16686

# View services being traced
curl http://localhost:16686/api/services | jq

# Get traces for a specific service
curl "http://localhost:16686/api/traces?service=nemotron-backend&limit=20" | jq
```

**Production Considerations:**

The default configuration uses Elasticsearch for persistent trace storage with the following characteristics:

1. **Elasticsearch Backend**: Traces are stored in Elasticsearch with 30-day ILM retention (configured in `monitoring/elasticsearch/`)
2. **Index Lifecycle Management**: Jaeger indices follow the `jaeger-span-*` pattern with automatic rollover
3. **Sampling**: Reduce `OTEL_TRACE_SAMPLE_RATE` to 0.1 (10%) for high-traffic systems
4. **Resource Limits**: Elasticsearch is configured with `ES_HEAP_SIZE` (default 2GB) and `ES_MEMORY_LIMIT` (default 4GB)

**Elasticsearch Dependency:**

Jaeger depends on Elasticsearch being healthy before starting:

```yaml
depends_on:
  elasticsearch:
    condition: service_healthy
```

If Elasticsearch is not available, Jaeger will fail to start. Check Elasticsearch health:

```bash
curl http://localhost:9200/_cluster/health | jq '.status'
# Expected: "green" or "yellow"
```

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

| Probe Type  | Endpoints Monitored                    |
| ----------- | -------------------------------------- |
| Health      | `backend:8000/api/system/health`       |
| Readiness   | `backend:8000/api/system/health/ready` |
| Liveness    | `backend:8000/health`, `frontend:8080` |
| AI Services | All AI service `/health` endpoints     |
| TCP         | `postgres:5432`, `redis:6379`          |

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

Alloy is Grafana's telemetry collector that collects container logs from Podman and forwards them to Loki for centralized log aggregation and querying.

**Port:** 12345 (Alloy UI)

**Configuration File:** `monitoring/alloy/config.alloy`

**Dependencies:**

- **Loki** - Log storage backend (port 3100)
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

The `docker-compose.prod.yml` file mounts the Podman socket into the Alloy container:

```yaml
volumes:
  - /run/user/1000/podman/podman.sock:/run/user/1000/podman/podman.sock:ro
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
podman-compose -f docker-compose.prod.yml up -d alloy
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
- **Retention** - Configurable log retention (default: 7 days)

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
      memory: 512M
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

**Supported Services:**

- `backend` - FastAPI backend
- `ai-yolo26` - YOLO26 object detection
- `ai-florence` - Florence-2 vision-language
- `ai-enrichment` - Entity enrichment

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
docker compose -f docker-compose.prod.yml ps | grep -E "(prometheus|grafana|jaeger|alertmanager|blackbox|json-exporter|redis-exporter)"

# Verify Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check for any scrape errors
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.health != "up")'
```

**Expected Healthy Targets:**

| Job Name               | Target                      | Expected Health |
| ---------------------- | --------------------------- | --------------- |
| `hsi-backend-metrics`  | `backend:8000`              | up              |
| `redis`                | `redis-exporter:9121`       | up              |
| `json-exporter`        | `json-exporter:7979`        | up              |
| `blackbox-exporter`    | `blackbox-exporter:9115`    | up              |
| `blackbox-http-health` | Backend health endpoint     | up              |
| `blackbox-http-ready`  | Backend readiness endpoint  | up              |
| `blackbox-http-live`   | Backend/frontend liveness   | up              |
| `blackbox-http-2xx`    | AI service health endpoints | up              |
| `blackbox-tcp`         | postgres:5432, redis:6379   | up              |

---

## See Also

- [GPU Setup Guide](gpu-setup.md) - Initial GPU configuration
- [AI Performance](ai-performance.md) - AI service tuning
- [Prometheus Alerting](prometheus-alerting.md) - Alert configuration and routing
- [Configuration Reference](../reference/config/env-reference.md) - All environment variables
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common issues
