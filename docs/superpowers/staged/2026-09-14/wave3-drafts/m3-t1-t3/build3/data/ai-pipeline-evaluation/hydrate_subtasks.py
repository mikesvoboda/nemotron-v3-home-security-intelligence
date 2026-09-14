#!/usr/bin/env python3
"""Hydrate Linear subtasks with detailed implementation context from evaluation reports."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

updates = [
    # --- NEM-5545: Tempo migration (MAJOR gap) ---
    {
        "id": "NEM-5545",
        "description": """**Impact:** HIGH (-5.5GB memory) | **Effort:** 4-8h | **Source:** Monitoring Eval (Report 06)

## Problem
Elasticsearch uses 6GB memory limit + 2GB heap solely for Jaeger trace storage. This is 57% of the total monitoring memory budget (~10.6GB). Jaeger all-in-one adds another 512MB. For a single-node system, this is excessive.

## Solution
Replace both `jaeger` and `elasticsearch` services with `grafana/tempo` in monolithic mode.

## Implementation

### Step 1: Add Tempo service to docker-compose.prod.yml

```yaml
tempo:
  image: docker.io/grafana/tempo:2.7.1
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  volumes:
    - ./monitoring/tempo/tempo-config.yml:/etc/tempo/config.yml:ro,z
    - tempo_data:/var/tempo
  command: -config.file=/etc/tempo/config.yml
  ports:
    - '127.0.0.1:${TEMPO_PORT:-3200}:3200'
    - '127.0.0.1:${TEMPO_OTLP_GRPC:-4317}:4317'
  healthcheck:
    test: ['CMD', 'wget', '-q', '--spider', 'http://localhost:3200/ready']
    interval: 15s
    timeout: 5s
    retries: 3
  restart: unless-stopped
  networks:
    - security-net
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 1G
```

### Step 2: Create Tempo config at `monitoring/tempo/tempo-config.yml`

```yaml
stream_over_http_enabled: true
server:
  http_listen_port: 3200
distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: '0.0.0.0:4317'
        http:
          endpoint: '0.0.0.0:4318'
storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
compactor:
  compaction:
    block_retention: 720h  # 30 days
```

### Step 3: Update Alloy config to export traces to Tempo

```
otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls { insecure = true }
  }
}
```

### Step 4: Update Grafana datasource provisioning

Replace Jaeger datasource with Tempo in `monitoring/grafana/provisioning/datasources/`:
```yaml
- name: Tempo
  type: tempo
  access: proxy
  url: http://tempo:3200
  jsonData:
    tracesToLogsV2:
      datasourceUid: loki
    tracesToMetrics:
      datasourceUid: prometheus
```

### Step 5: Remove old services

- Remove `jaeger` and `elasticsearch` services from docker-compose.prod.yml
- Remove `elasticsearch_data` volume
- Add `tempo_data` volume
- Update Prometheus `depends_on` if Alertmanager dependency chain references Jaeger
- Update backend `OTEL_EXPORTER_OTLP_ENDPOINT` to point to Tempo (or keep pointing to Alloy which forwards to Tempo)

## Risks
- Existing traces in Elasticsearch become inaccessible (acceptable — traces are ephemeral debugging data)
- Tempo query model differs from Jaeger: "search by trace ID" first, with TraceQL for attribute-based search
- TraceQL requires Grafana 10.2+ (we have 10.2.3, or higher after upgrade)

## Savings
- ~5.5GB RAM (6GB ES + 512MB Jaeger - 1GB Tempo)
- 2 services removed, 1 added
- Eliminates Elasticsearch operational complexity

## References
- [Grafana Tempo vs Jaeger Comparison](https://last9.io/blog/grafana-tempo-vs-jaeger/)
- [Migration from Jaeger to Tempo](https://developers.redhat.com/articles/2025/04/09/best-practices-migration-jaeger-tempo)
- [Tempo Monolithic Deployment](https://grafana.com/docs/tempo/latest/setup/operator/monolithic/)
""",
    },
    # --- NEM-5542: Redis eviction (MEDIUM gap) ---
    {
        "id": "NEM-5542",
        "description": """**Impact:** HIGH (data loss prevention) | **Effort:** 5min-2h | **Source:** Backend Eval (Report 04)

## Problem
Redis at 450MB with `allkeys-lru` will silently evict Stream entries (`detections:stream`, `detections:stream:dlq`), queue items, and rate limit counters under memory pressure. Stream data loss is silent — no errors raised, entries simply disappear.

## Current config (docker-compose.prod.yml line 791)
```
redis-server --maxmemory 450mb --maxmemory-policy allkeys-lru
```

## Three Options (choose one)

### Option A: `volatile-lru` (Preferred — LOW effort)
```
redis-server --maxmemory 512mb --maxmemory-policy volatile-lru
```
Only evicts keys with TTL set, preserving Streams/queues (which have no TTL).

**CRITICAL prerequisite:** Audit ALL Redis `SET` calls to ensure cache keys have TTLs. Without TTLs, `volatile-lru` will not evict anything and Redis will reject writes when full. Check:
- `backend/services/cache_service.py` — verify all cache operations set TTL/EX
- `backend/services/read_through_cache.py` — verify TTLs
- `backend/services/redis_json.py` — verify TTLs on JSON cache entries
- `backend/core/redis.py` — verify default TTL behavior

### Option B: `noeviction` (safest for queues, MEDIUM effort)
```
redis-server --maxmemory 768mb --maxmemory-policy noeviction
```
Rejects writes when full, allowing the application to handle backpressure. The `QueueOverflowPolicy` already supports this pattern.

### Option C: Dual Redis instances (Redis-recommended, HIGH effort)
Run two Redis instances — one for cache (`allkeys-lru`), one for queues/streams (`noeviction`). This is the [Redis-recommended approach](https://redis.io/docs/latest/develop/reference/eviction/) for mixed workloads.

## Recommendation
Start with **Option A** (`volatile-lru` + increase to 512mb). Audit cache TTLs first. If any cache keys lack TTLs, fix those before switching the eviction policy.

## Verification
```bash
# Check current memory usage
podman exec redis redis-cli INFO memory | grep used_memory_human
# Check keys without TTL (potential issues with volatile-lru)
podman exec redis redis-cli --scan | while read key; do
  ttl=$(podman exec redis redis-cli TTL "$key")
  [ "$ttl" = "-1" ] && echo "NO TTL: $key"
done
```
""",
    },
    # --- NEM-5538: httpx anti-pattern (MEDIUM gap) ---
    {
        "id": "NEM-5538",
        "description": """**Impact:** CRITICAL (-50-100ms per LLM call) | **Effort:** 1h | **Source:** Backend Eval (Report 04)

## Problem
`nemotron_analyzer.py` creates a new `httpx.AsyncClient` on every call at 5+ locations (lines 400, 983, 1375, 3504, 4072). Each new client triggers TCP connection establishment, TLS handshake (if applicable), and HTTP/2 negotiation. All other AI clients (DetectorClient, CLIPClient, FlorenceClient, EnrichmentClient) correctly use persistent clients per NEM-1721.

## Current code (at 5+ locations)
```python
async with httpx.AsyncClient(timeout=self._timeout) as client:
    response = await client.post(...)
```

## Should be (matching DetectorClient/CLIPClient/FlorenceClient/EnrichmentClient pattern)
```python
# In __init__:
self._http_client = httpx.AsyncClient(
    timeout=self._timeout,
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)

# In methods (replace all 5+ locations):
response = await self._http_client.post(...)

# Add close() method for lifecycle management:
async def close(self):
    if self._http_client:
        await self._http_client.aclose()
```

## Locations to fix in nemotron_analyzer.py
1. Line ~400: `_make_llm_call`
2. Line ~983: `check_health`
3. Line ~1375: `_check_guided_json_support`
4. Line ~3504: `warmup_inference`
5. Line ~4072: `analyze_batch`

## DI container lifecycle
Ensure `close()` is called during shutdown. The DI container already handles this for other clients — register NemotronAnalyzer the same way.

## Verification
- `grep -n "httpx.AsyncClient" backend/services/nemotron_analyzer.py` — should only appear once (initialization)
- Benchmark LLM call latency before/after (expect -50-100ms per call)
- At 10 events per batch with 2 LLM calls each, savings are 1-2 seconds per batch

## Reference
[httpx Clients docs](https://www.python-httpx.org/advanced/clients/) — "If you do anything more than experimentation, one-off scripts, or prototyping, then you should use a Client instance."
""",
    },
    # --- NEM-5547: YOLO INT8 (MEDIUM gap) ---
    {
        "id": "NEM-5547",
        "description": """**Impact:** HIGH (~2x speedup, 50% model size reduction) | **Effort:** 2-4h | **Source:** YOLO Eval (Report 02)

## Problem
YOLO26 runs as ONNX FP16 on GPU. INT8 would give ~2x throughput on A400's 3rd-gen Tensor Cores.

## Why INT8 works well for YOLO26
- YOLO26's architecture was specifically designed for quantization robustness
- "INT8 exports of YOLO26 retain nearly the same mAP as FP32 versions" (Ultralytics docs)
- NMS-free decoder means no custom ops that are hard to quantize
- RTX A400 has native INT8 Tensor Core support (Ampere sm_86)
- With only 4GB VRAM, reducing model memory footprint is critical

## Implementation Steps

### 1. Create calibration dataset (200-500 representative frames)
```bash
# Extract frames from actual security camera recordings
python export_tensorrt.py --int8 \\
  --data config/yolo26_calibration.yaml \\
  --extract-frames \\
  --model /export/ai_models/model-zoo/yolo26/yolo26m.pt \\
  --output /export/ai_models/model-zoo/yolo26/exports/
```

### 2. Benchmark INT8 vs FP16
```bash
python export_tensorrt.py --benchmark \\
  /export/ai_models/model-zoo/yolo26/exports/yolo26m_int8.engine
```

### 3. Validate accuracy
```bash
python export_tensorrt.py --validate \\
  /export/ai_models/model-zoo/yolo26/exports/yolo26m_int8.engine \\
  --data config/yolo26_calibration.yaml
```

### 4. Deploy to Triton
Update `ai/triton/model_repository/yolo26/config.pbtxt` to load INT8 engine. Update export scripts in `ai/gateway/export/` to produce INT8.

## Expected Results
- ~20% latency reduction (INT8 Tensor Core ops are 2x faster than FP16)
- ~50% model size reduction (smaller engine, less VRAM)
- Minimal accuracy loss (typically <1% mAP for YOLO26 INT8 vs FP16)

## Calibration Requirements
- Images MUST be representative of actual deployment (lighting, camera angles, weather)
- 200-500 frames from each camera is ideal
- Source: `/export/foscam/` directories

## References
- [Ultralytics TensorRT Export](https://docs.ultralytics.com/integrations/tensorrt/)
- [YOLO26 Architecture Paper](https://arxiv.org/html/2509.25164v3)
""",
    },
    # --- NEM-5543: Vehicle threshold (MEDIUM gap + factual correction) ---
    {
        "id": "NEM-5543",
        "description": """**Impact:** MEDIUM (vehicles being missed) | **Effort:** 30min | **Source:** YOLO Eval (Report 02)

## Problem
Vehicle detection confidence thresholds are too aggressive for security monitoring, causing missed detections.

## Current thresholds (from YOLO report analysis)
```python
_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS = {
    "car": 0.70,       # Too aggressive — missing vehicles
    "truck": 0.70,     # Too aggressive
    "bus": 0.70,       # Too aggressive
    "motorcycle": 0.50,
    "person": 0.45,    # Good — favors recall
    ...
}
```

## Recommended thresholds
Lower car/truck/bus from 0.70 to **0.55-0.60** for security camera use cases where recall matters more than precision. The YOLO evaluation report analyzed this specifically and recommends this range based on the YOLO26m model's confidence distribution.

Note: The original synthesis suggested 0.40-0.50 but the detailed YOLO report recommends **0.55-0.60** as the optimal balance. Going below 0.55 risks excessive false positives from shadows, reflections, and parked cars partially occluded.

## Location
Search for `_DEFAULT_CLASS_CONFIDENCE_THRESHOLDS` or vehicle confidence threshold configuration. This may be in:
- The Triton gateway YOLO adapter (`ai/gateway/adapters/yolo26.py`)
- The standalone YOLO server (`ai/yolo26/model.py`) — now dead code but may be referenced
- Backend detection configuration

## Verification
- Run detection on test images with known vehicles
- Confirm previously-missed vehicles are now detected
- Monitor false positive rate for 24h after change
""",
    },
    # --- NEM-5557: Monitoring upgrades (SMALL gap) ---
    {
        "id": "NEM-5557",
        "description": """**Impact:** MEDIUM | **Effort:** 4-8h | **Source:** Monitoring Eval (Report 06)

## Current → Target Versions

| Service | Current | Target | Gap | Key Features Gained |
|---------|---------|--------|-----|-------------------|
| Grafana | 10.2.3 | 12.3 | 2 major | Observability-as-code, dynamic dashboards, 97.8% faster tables, redesigned logs panel |
| Prometheus | 2.48.0 | 3.1 | 1 major | Native OTLP metric receiver, UTF-8 metric names, native histograms |
| Loki | 2.9.4 | 3.5 | 1 major | Native OTLP log endpoint, structured metadata, bloom filter acceleration |
| Alloy | 1.0.0 | 1.9+ | 18 minor | **May fix privileged mode SELinux issue**, improved eBPF profiler |

## Priority Order (upgrade one at a time, validate after each)

### 1. Alloy v1.0.0 → v1.9+ (HIGHEST PRIORITY)
May eliminate the privileged mode security workaround (NEM-4499). Test with `privileged: false` after upgrade.

### 2. Grafana 10.2.3 → 12.3
```yaml
grafana:
  image: docker.io/grafana/grafana:12.3.2
  environment:
    # IMPORTANT: Remove JSON API plugin version pin — v1.3.15+ requires Grafana 11.6+
    # Old: GF_INSTALL_PLUGINS=marcusolsson-json-datasource 1.3.0
    # New: (no version pin, latest compatible version will install)
    - GF_INSTALL_PLUGINS=marcusolsson-json-datasource
```

**Breaking change check:** Verify all provisioned dashboards render correctly after upgrade. The Grafana 12.x API has a new versioned model that may affect dashboard JSON.

### 3. Loki 2.9.4 → 3.5
Major version jump. Check config compatibility:
- Schema version may need update (current: v13, TSDB store)
- Storage config format may differ
- Test log queries in Grafana Explore after upgrade

### 4. Prometheus 2.48.0 → 3.1
Major version jump. Benefits:
- Native OTLP receiver: Alloy can send metrics directly via OTLP instead of remote_write
- Check `prometheus.yml` for deprecated config options

## Verification After Each Upgrade
```bash
# Check service health
curl -s localhost:3002/api/health  # Grafana
curl -s localhost:9090/-/healthy   # Prometheus
curl -s localhost:3100/ready       # Loki
# Check Alloy (test without privileged)
podman logs alloy --tail=20
```
""",
    },
    # --- NEM-5549: Triton batching (SMALL gap) ---
    {
        "id": "NEM-5549",
        "description": """**Impact:** HIGH (2-3x throughput) | **Effort:** 2-4h | **Source:** Enrichment Eval (Report 05)

## Problem
Dynamic batching is only configured for 2 of 13 Triton models:
- `reid`: preferred_batch_size [1, 4, 8]
- `vehicle`: preferred_batch_size [1, 4]

The other 11 models process requests one at a time, wasting GPU cycles when multiple cameras send frames simultaneously.

## Fix
Add dynamic batching config to all 13 model `config.pbtxt` files in `ai/triton/model_repository/*/config.pbtxt`.

### Template for GPU models (yolo26, clip, florence2)
```protobuf
dynamic_batching {
  preferred_batch_size: [1, 2, 4]
  max_queue_delay_microseconds: 50000  # 50ms — lower for latency-sensitive detection
}
```

### Template for CPU models (pose, threat, pet, depth, demographics_age, demographics_gender, fashion_clip)
```protobuf
dynamic_batching {
  preferred_batch_size: [1, 4, 8]
  max_queue_delay_microseconds: 100000  # 100ms — can tolerate more delay for enrichment
}
```

### Template for Python backend models (florence2, xclip_action)
Python backends need `max_batch_size` set in config AND the model.py `execute()` method must handle batched inputs:
```protobuf
max_batch_size: 4
dynamic_batching {
  preferred_batch_size: [1, 2, 4]
  max_queue_delay_microseconds: 100000
}
```

## Tuning Notes
- `max_queue_delay_microseconds`: How long Triton waits to collect a batch before executing. Lower = less latency, higher = better throughput.
- For security monitoring with 6 cameras, 50-100ms delay is acceptable and allows batching across camera frames.
- NVIDIA benchmarks show 70% throughput increase with dynamic batching on A100; proportional gains expected on A400.

## Location
`ai/triton/model_repository/*/config.pbtxt` — all 13 model directories

## Verification
After deploying, check Triton metrics for batch size distribution:
```bash
curl -s http://localhost:8090/health  # Verify models still healthy
# Once Triton metrics are exposed (NEM-5553):
# Check nv_inference_request_success and batch size histograms
```
""",
    },
]

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"Hydrating {len(updates)} subtasks with implementation details...\n"
)

for update in updates:
    issue_id = update["id"]
    # Use the GraphQL API directly to update description
    internal_id = client._resolve_issue_id(issue_id)

    escaped_desc = (
        update["description"].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    )

    mutation = f'''
    mutation {{
        issueUpdate(id: "{internal_id}", input: {{
            description: "{escaped_desc}"
        }}) {{
            success
            issue {{ identifier title }}
        }}
    }}
    '''

    try:
        result = client._query(mutation)
        issue = result["issueUpdate"]["issue"]
        print(  # noqa: T201 # noqa: T201
            f"  Updated {issue['identifier']}: {issue['title'][:65]}"
        )
    except Exception as e:
        print(  # noqa: T201 # noqa: T201
            f"  FAILED {issue_id}: {e}"
        )

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"\nDone! Hydrated {len(updates)} subtasks."
)
