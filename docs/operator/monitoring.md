# Monitoring and Observability

> GPU monitoring, LLM token tracking, and distributed tracing for the Home Security Intelligence system.

This guide covers the three core observability pillars:

1. **GPU Monitoring** - Real-time GPU metrics and memory pressure alerts
2. **Token Tracking** - LLM context window management and utilization metrics
3. **Distributed Tracing** - OpenTelemetry integration for cross-service debugging

---

## GPU Monitoring

The GPU monitoring service (`GPUMonitor`) provides real-time metrics for NVIDIA GPUs used by AI services (RT-DETRv2 and Nemotron).

### How It Works

The GPU monitor uses a fallback strategy to collect metrics:

1. **pynvml** (preferred) - Direct NVIDIA Management Library bindings for lowest latency
2. **nvidia-smi** - Subprocess fallback when pynvml is unavailable (containerized environments)
3. **AI Container Endpoints** - Queries RT-DETRv2 `/health` endpoint for GPU stats
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
curl http://localhost:8090/health  # RT-DETRv2
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

## See Also

- [GPU Setup Guide](gpu-setup.md) - Initial GPU configuration
- [AI Performance](ai-performance.md) - AI service tuning
- [Configuration Reference](../admin-guide/configuration.md) - All environment variables
- [Troubleshooting Index](../reference/troubleshooting/index.md) - Common issues
