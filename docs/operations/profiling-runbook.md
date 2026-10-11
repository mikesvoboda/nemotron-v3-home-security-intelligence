# Profiling Operations Runbook

> Operational procedures for managing Pyroscope continuous profiling in production.

Profiling subjects in this deployment are exactly three profile names:
`nemotron-backend` (the backend's in-process pyroscope-io SDK,
`backend/core/telemetry.py::init_profiling`) and `backend` (the py-spy loop
launched by `backend/entrypoint.sh:51`, log at
`/app/data/logs/profiler.log`) — two views of the **same** backend process —
plus `ai-vlm`, profiled from outside by Alloy's eBPF component because
`llama-server` is native code (label `pyroscope.profile: 'true'`,
`docker-compose.prod.yml:151-152`). `ai-gateway` runs Triton and pushes nothing.
Mechanism details: [Continuous Profiling Guide](../guides/profiling.md).

## Quick Reference

| Task                        | Command                                                               |
| --------------------------- | --------------------------------------------------------------------- |
| Check Pyroscope health      | `curl http://localhost:4040/ready`                                    |
| View Pyroscope UI           | Open [http://localhost:4040](http://localhost:4040)                   |
| Restart Pyroscope           | `podman compose -f docker-compose.prod.yml restart pyroscope`         |
| View profiler log (backend) | `podman exec backend cat /app/data/logs/profiler.log`                 |
| Check backend SDK profiling | `podman logs backend 2>&1 \| grep -i pyroscope`                       |
| Check the eBPF profiler     | `podman logs alloy 2>&1 \| grep -i pyroscope`                         |
| Disable backend profiling   | Set `PYROSCOPE_ENABLED=false` in `.env`                               |
| Profiling dashboard         | `http://localhost:3002/grafana/d/hsi-profiling` (uid `hsi-profiling`) |

Grafana serves from the `/grafana/` sub-path
(`GF_SERVER_ROOT_URL=/grafana/`, `GF_SERVER_SERVE_FROM_SUB_PATH=true`,
`docker-compose.prod.yml:1095-1096`) on host port `${GRAFANA_PORT:-3002}`, bound
to `127.0.0.1`.

---

## Automated Regression Alert Response Procedures

Response procedures for the automated regression alerts (NEM-4133). Alert
definitions: `monitoring/profiling-regression-alerts.yml`; recording rules:
`monitoring/profiling-recording-rules.yml`. Every ratio below is computed from
Prometheus container metrics (`job:service_cpu_seconds:rate5m`,
`job:service_memory_bytes:current`), so the alerts fire whether or not Pyroscope
is receiving profiles.

### ALERT-REG-001: ServiceCPUSpike / ServiceCPUSpikeCritical

**Alert Condition:** `job:service_cpu_regression_ratio:5m_vs_24h > 1.5` for 15m
(warning) or `> 2.0` for 10m (critical) — i.e. CPU 50% / 100% above its own
24-hour average.

**Symptoms:**

- Service consuming significantly more CPU than historical baseline
- Increased response times
- Higher infrastructure costs

**Diagnosis:**

```bash
# 1. Check current CPU regression ratio
curl -s "http://localhost:9090/api/v1/query?query=job:service_cpu_regression_ratio:5m_vs_24h" | jq '.data.result'

# 2. View CPU profile in Grafana Pyroscope
# Open: http://localhost:3002/grafana/d/hsi-profiling
# Profile names this deployment can return: nemotron-backend, backend, ai-vlm

# 3. Compare current vs baseline flame graphs
# Use the "Profile Comparison" row (baseline_from / baseline_to variables)
# Look for new hot functions or significantly increased function times

# 4. Check for recent deployments
git log --oneline --since="24 hours ago"

# 5. Check if workload increased
curl -s "http://localhost:9090/api/v1/query?query=rate(hsi_stage_duration_seconds_count[10m])" | jq
```

**Resolution:**

1. **If caused by code regression:**

   ```bash
   # Identify the problematic commit using flame graph comparison
   # Roll back to previous version if needed
   git checkout <previous-sha>
   podman compose -f docker-compose.prod.yml build --no-cache [service]
   podman compose -f docker-compose.prod.yml up -d [service]
   ```

2. **If caused by increased workload:**

   - Check the queue-depth gauges (`hsi_detection_queue_depth`,
     `hsi_analysis_queue_depth`) before scaling
   - Implement rate limiting
   - Optimize hot code paths identified in the flame graph

3. **If caused by memory pressure (GC overhead):**
   - Check memory alerts alongside CPU
   - Increase the container's host-RAM limit (`deploy.resources.limits.memory`)
   - Investigate memory leaks

**Escalation:** If unresolved after 30 minutes, escalate to on-call engineer.

---

### ALERT-REG-002: ServiceMemoryGrowth / ServiceMemoryGrowthCritical

**Alert Condition:** `(job:service_memory_regression_ratio:current_vs_6h - 1) >
0.25` for 30m (warning) or `> 0.5` for 15m (critical) — RSS 25% / 50% above its
own 6-hour average.

**Symptoms:**

- Gradual memory increase over time
- Service restarts due to OOM
- Degraded performance

**Diagnosis:**

```bash
# 1. Check current memory regression ratio
curl -s "http://localhost:9090/api/v1/query?query=job:service_memory_regression_ratio:current_vs_6h" | jq '.data.result'

# 2. Check memory growth rate
curl -s "http://localhost:9090/api/v1/query?query=job:service_memory_bytes:deriv1h" | jq '.data.result'

# 3. Check memory profile in Pyroscope
# Select "Memory Bytes" or "Memory Allocations" profile type
# Allocation profiles exist only for nemotron-backend — the py-spy loop and the
# eBPF profiler both emit process_cpu only
# Look for functions allocating large amounts

# 4. Check container memory limits
podman stats --no-stream [container_name]

# 5. For Python services, check for common leak patterns
podman exec [container] python -c "import tracemalloc; tracemalloc.start()"
```

**Resolution:**

1. **If memory leak suspected:**

   ```bash
   # Restart service as immediate mitigation
   podman compose -f docker-compose.prod.yml restart [service]

   # Schedule investigation of leak source
   ```

2. **If caused by caching:**

   - Review cache eviction policies
   - Reduce cache size limits
   - Add cache entry TTLs

3. **If caused by large request buffers:**
   - Implement streaming for large responses
   - Add request size limits

---

### ALERT-REG-003: PotentialMemoryLeak

**Alert Condition:** `job:service_memory_bytes:predicted_24h >
job:service_memory_bytes:current * 2` (with current RSS above 100 MB) for 1h —
memory projected to double within 24 hours from the 1h `deriv` slope.

**Symptoms:**

- Steadily increasing memory usage
- Linear growth pattern visible in monitoring
- No correlation with workload

**Diagnosis:**

```bash
# 1. Check projected memory
curl -s "http://localhost:9090/api/v1/query?query=job:service_memory_bytes:predicted_24h" | jq '.data.result'

# 2. Check growth rate (bytes/hour)
curl -s "http://localhost:9090/api/v1/query?query=job:service_memory_bytes:deriv1h" | jq '.data.result'

# 3. Analyze memory allocation profile over time
# In Grafana Pyroscope (or the Pyroscope UI), compare alloc_space profiles for
# nemotron-backend from 6 hours ago and from now
# Look for functions with significantly more allocations

# 4. For Python: enable memory profiling
podman exec [container] python -c "
import tracemalloc
tracemalloc.start()
# ... run suspect code ...
snapshot = tracemalloc.take_snapshot()
for stat in snapshot.statistics('lineno')[:10]:
    print(stat)
"
```

**Resolution:**

1. **Immediate mitigation:**

   ```bash
   # Set up scheduled restarts until fix is deployed
   # Add to crontab or systemd timer:
   # 0 */4 * * * podman compose -f docker-compose.prod.yml restart [service]
   ```

2. **Investigation:**

   - Use the allocation profile to identify the leak source
   - Check for unclosed database connections
   - Check for unbounded caches or queues
   - Review recent code changes for retained references

3. **Long-term fix:**
   - Deploy code fix
   - Add memory monitoring to CI/CD pipeline
   - Implement memory pressure alerts

---

### ALERT-REG-004: BackendHighLatency / BackendHighLatencyCritical

**Alert Condition:** `job:backend_api_latency:p99_5m > 2` for 10m (warning) or
`> 5` for 5m (critical) — backend API P99 above 2s / 5s.

**Symptoms:**

- Slow API responses
- UI timeouts
- WebSocket disconnections

**Diagnosis:**

```bash
# 1. Check current latency (recording rule over http_request_duration_seconds)
curl -s "http://localhost:9090/api/v1/query?query=job:backend_api_latency:p99_5m" | jq '.data.result'

# 2. Check which route is slow
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=topk(5, histogram_quantile(0.99, sum by (le, http_route) (rate(http_request_duration_seconds_bucket[5m]))))' | jq

# 3. Check database query latency
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,rate(hsi_db_query_duration_seconds_bucket[5m]))" | jq

# 4. Check Redis slowlog growth (redis exporter)
curl -s "http://localhost:9090/api/v1/query?query=increase(redis_slowlog_length[5m])" | jq

# 5. Check CPU usage (may be contention)
curl -s "http://localhost:9090/api/v1/query?query=job:backend_cpu_seconds:rate5m" | jq

# 6. View backend flame graph for hot paths
# Open http://localhost:3002/grafana/d/hsi-profiling
# Select "nemotron-backend" (SDK) or "backend" (py-spy)
```

**Resolution:**

1. **If database is slow:**

   ```bash
   # Check for long-running queries
   podman exec postgres psql -U "${POSTGRES_USER:-security}" -c "SELECT pid, state, query_start, left(query,120) FROM pg_stat_activity WHERE state = 'active';"

   # Check for missing indexes
   podman exec postgres psql -U "${POSTGRES_USER:-security}" -c "EXPLAIN ANALYZE [slow_query];"
   ```

2. **If Redis is slow:**

   ```bash
   # Check slow log
   podman exec redis redis-cli slowlog get 10

   # Check memory usage
   podman exec redis redis-cli info memory
   ```

3. **If CPU contention:**
   - Look at the flame graph for the dominant path
   - Optimize hot code paths
   - Add caching for expensive operations

---

### ALERT-REG-005: YOLO26LatencyRegression / YOLO26HighLatency

**Alert Condition:** `job:yolo26_latency_regression_ratio:p95_vs_1h > 1.5` for
10m (detector P95 up >50% on its own hour), or
`job:yolo26_inference_latency:p95_5m > 0.5` for 10m (P95 above 500ms).

Both rules read the backend's **client-side** histogram
`hsi_ai_request_duration_seconds_bucket{service="yolo26"}` — the label is
`service`, and `yolo26` is the only value the shipped code ever writes
(`monitoring/profiling-recording-rules.yml:167-174`,
`monitoring/profiling-recording-rules.yml:208-214`). So this alert measures the
whole detector round-trip as the backend experienced it: gateway queueing,
Triton compute and HTTP overhead together. Triton's own counters are cumulative
(`nv_inference_request_duration_us` over `nv_inference_request_success`), and
`summary_latencies` is not enabled, so no server-side percentile exists — the
`triton-metrics` job yields a per-model **mean** only.

**Symptoms:**

- Object detection taking longer
- Real-time detection pipeline backing up
- Detection queue growing

**Diagnosis:**

```bash
# 1. The alerting signal itself, plus sample count (a low-rate P95 is noisy)
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=job:yolo26_inference_latency:p95_5m' | jq
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=sum(rate(hsi_ai_request_duration_seconds_count{service="yolo26"}[5m]))' | jq

# 2. Split gateway-side from Triton-side: Triton mean per model, microseconds
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=job:triton_inference_latency:avg5m' | jq '.data.result[].metric.model, .data.result[].value'

# 3. Triton request failures piling up?
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=sum by (model) (rate(nv_inference_request_failure[5m]))' | jq

# 4. Check GPU utilization and temperature (dcgm-exporter)
curl -s "http://localhost:9090/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL" | jq
curl -s "http://localhost:9090/api/v1/query?query=DCGM_FI_DEV_GPU_TEMP" | jq

# 5. Check the router still reports the model ready
curl -s http://localhost:8090/yolo26/health | jq .
curl -s http://localhost:8090/health | jq '{status, models_loaded, models_total}'

# 6. Backend-attributed detector latency (same histogram, averaged)
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=rate(hsi_ai_request_duration_seconds_sum{service="yolo26"}[5m]) / rate(hsi_ai_request_duration_seconds_count{service="yolo26"}[5m])' | jq
```

**Resolution:**

1. **If GPU throttling:**

   - Improve cooling
   - Reduce batch size
   - Lower power limit

2. **If Triton-side mean is the whole latency (not transport):**

   ```bash
   # Restart the gateway to reinitialize Triton/TensorRT
   podman compose -f docker-compose.prod.yml restart ai-gateway
   # Triton warm-up can take up to its 180s health start_period
   ```

3. **If input resolution or volume changed:**
   - Verify input preprocessing and image sizes
   - Check whether `GATEWAY_ENABLE_THREAT=true` was set, which mounts an extra
     resident model on this card ([GPU Memory Limits](../deployment/gpu-memory-limits.md))

---

### ALERT-REG-006: MultiServiceCPURegression

**Alert Condition:** 2 or more services with a CPU regression ratio above 1.3,
sustained 15m (critical).

**Symptoms:**

- System-wide slowdown
- Multiple services affected
- Infrastructure-level issue likely

**Diagnosis:**

```bash
# 1. Check which services are affected
curl -s "http://localhost:9090/api/v1/query?query=job:service_cpu_regression_ratio:5m_vs_24h>1.3" | jq '.data.result[].metric.job'

# 2. Check host-level metrics
podman stats --no-stream

# 3. Check for noisy neighbour (other processes)
top -b -n 1 | head -20

# 4. Check disk I/O (may cause CPU wait)
iostat -x 1 5

# 5. Check network errors
netstat -s | grep -i error
```

**Resolution:**

1. **If host resource exhaustion:**

   - Identify and stop non-essential processes
   - Scale out to additional hosts
   - Increase host resources

2. **If shared dependency issue:**

   - Check database/Redis health
   - Check network connectivity
   - Verify shared storage performance

3. **If sustained by load shape:**
   - Implement rate limiting
   - Reduce batch/key-frame sizes
   - Scale defensive capacity

---

## Incident Response Procedures

### INC-PROF-001: Pyroscope Server Unavailable

**Symptoms:**

- No new profiling data in the Grafana dashboards
- Push errors in the backend profiler log
- Pyroscope UI not accessible at port 4040

**Diagnosis:**

```bash
# Check if Pyroscope container is running
podman ps | grep pyroscope

# Check container health
podman inspect pyroscope --format='{{.State.Health.Status}}'

# Check container logs
podman logs pyroscope --tail 100

# Test internal connectivity (from the backend container)
podman exec backend python -c "import httpx; print(httpx.get('http://pyroscope:4040/ready', timeout=5).status_code)"

# What did the py-spy loop get back?
podman exec backend tail -30 /app/data/logs/profiler.log
```

**Resolution:**

```bash
# Restart Pyroscope
podman compose -f docker-compose.prod.yml restart pyroscope

# If restart fails, recreate the container
podman compose -f docker-compose.prod.yml up -d --force-recreate pyroscope

# Verify recovery
curl http://localhost:4040/ready
```

**Impact:** Nothing in the detection path depends on Pyroscope — backend, gateway
and VLM keep serving. The py-spy loop POSTs one recording per cycle and starts
the next regardless of the response (`scripts/pyroscope-profiler.sh:69-73` logs
`Failed to push profile: HTTP $HTTP_CODE` and moves on), so an outage costs at
most the recordings attempted while it lasted; nothing is buffered for retry.

---

### INC-PROF-002: High CPU Overhead from Profiling

**Symptoms:**

- Higher than expected CPU usage (>5% overhead)
- Services responding slower than normal
- py-spy processes consuming excessive CPU

**Diagnosis:**

In this deployment the in-container profiler runs only inside `backend`; the VLM
engine is sampled from outside by Alloy, so its overhead appears in the `alloy`
container.

```bash
# Check py-spy processes in backend
podman exec backend ps aux | grep py-spy

# Check profiler log for errors
podman exec backend cat /app/data/logs/profiler.log

# Check interval and sample rate (defaults: PROFILE_INTERVAL=30, PYROSCOPE_SAMPLE_RATE=100)
podman exec backend env | grep -E "PROFILE_INTERVAL|PYROSCOPE"

# eBPF side: Alloy samples at 97 Hz every 15s for each labelled container
podman stats --no-stream alloy
```

**Resolution:**

Option 1: Shorten the py-spy capture window

The loop is `record for PROFILE_INTERVAL`, then `sleep 5` — so the default 30
means py-spy is attached ~30/35 of the time. Lowering the value shrinks the
attached duty cycle (`10` → ~10/15), at the cost of coarser profiles:

```bash
# Add to docker-compose.override.yml under backend.environment:
#   - PROFILE_INTERVAL=10      (default is 30)
podman compose -f docker-compose.prod.yml up -d backend
```

Option 2: Lower the SDK sample rate instead of switching it off

```bash
#   - PYROSCOPE_SAMPLE_RATE=50  (default is 100 Hz)
podman compose -f docker-compose.prod.yml up -d backend
```

Option 3: Disable the backend paths

```bash
# Add to docker-compose.override.yml under backend.environment:
#   - PYROSCOPE_ENABLED=false   (turns off both the py-spy loop and the SDK)
podman compose -f docker-compose.prod.yml up -d backend
```

Option 4: Disable globally

```bash
echo "PYROSCOPE_ENABLED=false" >> .env
podman compose -f docker-compose.prod.yml up -d
```

Option 5: Stop the VLM eBPF profile — remove the label from `ai-vlm` in an
override (`pyroscope.profile: 'false'`) and recreate that service.

**Impact:** Reduced profiling coverage, improved service performance.

---

### INC-PROF-003: Profiler Not Collecting Data for a Subject

**Symptoms:**

- An expected application missing from the Pyroscope UI
- Service running but no profiles being collected
- Profiler log shows errors

**Diagnosis (backend, py-spy loop):**

```bash
# Is the profiler script running?
podman exec backend pgrep -fa pyroscope-profiler.sh

# Profiler log (launched by backend/entrypoint.sh)
podman exec backend tail -50 /app/data/logs/profiler.log
# Expect lines like: "[pyroscope-profiler] ... Starting profiler for backend"

# Last py-spy failure
podman exec backend cat /tmp/pyspy_error.log
```

**Diagnosis (backend, SDK):**

```bash
# Initialization message during app startup
podman logs backend 2>&1 | grep -i "pyroscope profiling"
# Expect: "Pyroscope profiling initialized: server=http://pyroscope:4040, sample_rate=100Hz"
# A "skipped: pyroscope-io not installed" line means the import failed

podman exec backend python -c "import pyroscope; print(pyroscope.__name__)"
```

**Diagnosis (ai-vlm, Alloy eBPF):**

```bash
# Labels present?
podman inspect ai-vlm --format '{{json .Config.Labels}}' | jq '.["pyroscope.profile"], .["pyroscope.service"]'

# Alloy sees the target and can write?
podman logs alloy 2>&1 | grep -i "pyroscope\|ebpf" | tail -20
```

**Resolution:**

```bash
# Is Pyroscope receiving anything at all?
curl -s http://localhost:4040/api/services/status 2>/dev/null | head -c 400

# Restart the producer
podman compose -f docker-compose.prod.yml restart backend   # SDK + py-spy
podman compose -f docker-compose.prod.yml restart alloy     # eBPF targets

# Verify
podman exec backend tail -5 /app/data/logs/profiler.log
```

---

### INC-PROF-004: Pyroscope Storage Full (NEM-3928)

**Symptoms:**

- Pyroscope queries becoming slow
- Disk usage growing rapidly in the `pyroscope_data` volume
- "disk full" or "quota exceeded" errors in logs

**Diagnosis:**

```bash
# Check volume usage
podman volume inspect pyroscope_data

# Check container disk usage (the image is busybox-based — invoke df via busybox)
podman exec pyroscope busybox df -h /data

# Check retention settings currently mounted in the container
podman exec pyroscope cat /etc/pyroscope/config.yml

# Check compactor status
podman logs pyroscope 2>&1 | grep -i "compactor\|retention\|cleanup"
```

**Retention Configuration (NEM-3928):**

Configured in `monitoring/pyroscope/pyroscope-config.yml`, bind-mounted read-only
at `/etc/pyroscope/config.yml`:

| Setting                                     | Value | Effect                                                |
| ------------------------------------------- | ----- | ----------------------------------------------------- |
| `limits.compactor_blocks_retention_period`  | 720h  | Maximum block age (30 days)                           |
| `pyroscopedb.min_free_disk_gb`              | 10    | Delete oldest blocks when free space falls below this |
| `pyroscopedb.min_disk_available_percentage` | 0.05  | Secondary disk-safety threshold (5%)                  |
| `pyroscopedb.enforcement_interval`          | 5m    | How often disk-based retention is checked             |
| `pyroscopedb.max_block_duration`            | 1h    | Maximum duration of one block                         |
| `compactor.compaction_interval`             | 2h    | How often blocks are merged                           |
| `compactor.cleanup_interval`                | 15m   | How often retention cleanup runs                      |
| `compactor.deletion_delay`                  | 2h    | Delay before permanent deletion                       |

**Resolution:**

```bash
# Option 1: Wait for automatic cleanup (recommended)
# Cleanup runs every 15m; disk-based retention fires sooner than the 30-day age
# limit once free space drops. Check:
podman logs pyroscope 2>&1 | grep -i "deleting\|cleanup\|retention"

# Option 2: Reduce retention for faster cleanup
# Edit monitoring/pyroscope/pyroscope-config.yml:
# Change: compactor_blocks_retention_period: 720h
# To:     compactor_blocks_retention_period: 168h  # 7 days
podman compose -f docker-compose.prod.yml restart pyroscope

# Option 3: Force a compaction cycle by restarting
podman compose -f docker-compose.prod.yml restart pyroscope

# Option 4: If urgent, clear all data (last resort)
podman compose -f docker-compose.prod.yml stop pyroscope
podman volume rm pyroscope_data  # WARNING: deletes all profiling history
podman compose -f docker-compose.prod.yml up -d pyroscope
```

**Prevention:**

- Watch the volume (`podman volume inspect pyroscope_data`, or host `df`)
- Alert before the volume approaches the host's free space
- Reduce `compactor_blocks_retention_period` on disk-constrained hosts

**Impact:** Automatic retention prevents disk exhaustion in normal operation.
Manual intervention is only needed when the policy itself is too generous for
the workload.

---

## Maintenance Procedures

### MAINT-PROF-001: Updating The Pyroscope Version

The Pyroscope image is **built**, not pulled directly: `docker-compose.prod.yml`
builds `./monitoring/pyroscope`, a thin layer that adds a static busybox for
health checks on top of `docker.io/grafana/pyroscope:1.18.0`. Pin changes go in
`monitoring/pyroscope/Dockerfile`, not in compose.

**Pre-flight checks:**

```bash
# Current base version (pinned in the Dockerfile)
grep "grafana/pyroscope" monitoring/pyroscope/Dockerfile

# Review release notes for breaking changes
# https://github.com/grafana/pyroscope/releases
```

**Procedure:**

```bash
# 1. Update the base image tag in monitoring/pyroscope/Dockerfile
#    e.g. FROM docker.io/grafana/pyroscope:1.18.0 -> 1.19.0

# 2. Back up the config
cp monitoring/pyroscope/pyroscope-config.yml monitoring/pyroscope/pyroscope-config.yml.bak

# 3. Rebuild (always --no-cache for infra changes) and recreate
podman compose -f docker-compose.prod.yml build --no-cache pyroscope
podman compose -f docker-compose.prod.yml up -d pyroscope

# 4. Verify health and that the existing profiles still render
curl http://localhost:4040/ready
```

**Rollback:**

```bash
# Revert monitoring/pyroscope/Dockerfile to the previous tag
podman compose -f docker-compose.prod.yml build --no-cache pyroscope
podman compose -f docker-compose.prod.yml up -d pyroscope
```

The agent side matters as much as the server: `pyproject.toml` requires
`pyroscope-io>=0.8.7` and the speedscope fix needs a server ≥1.9.2
(grafana/pyroscope#4568).

---

### MAINT-PROF-002: Adding Profiling To A New Service

Pick the mechanism by what the process is written in.

**Python service — py-spy sidecar** (the backend pattern):

1. Install py-spy and copy the profiler script into the image (as
   `backend/Dockerfile:189-194` does):

   ```dockerfile
   RUN uv tool install py-spy && \
       cp -L /root/.local/bin/py-spy /usr/local/bin/py-spy && \
       chmod +x /usr/local/bin/py-spy

   COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
   ```

2. Start it from the entrypoint, backgrounded, before `exec "$@"` (as
   `backend/entrypoint.sh:50-55` does):

   ```bash
   if [ "${PYROSCOPE_ENABLED:-true}" = "true" ]; then
       nohup /usr/local/bin/pyroscope-profiler.sh "my-service" \
           "${PYROSCOPE_URL:-http://pyroscope:4040}" "${PROFILE_INTERVAL:-30}" \
           >> /app/data/logs/profiler.log 2>&1 &
   fi
   ```

3. Give it the endpoint:

   ```yaml
   my-new-service:
     environment:
       - PYROSCOPE_ENABLED=${PYROSCOPE_ENABLED:-true}
       - PYROSCOPE_URL=http://pyroscope:4040
   ```

4. Rebuild, deploy, verify:

   ```bash
   podman compose -f docker-compose.prod.yml build --no-cache my-new-service
   podman compose -f docker-compose.prod.yml up -d my-new-service
   podman exec my-new-service cat /app/data/logs/profiler.log
   # Expect: "Starting profiler for my-service"
   ```

**Python service — in-process SDK** (adds memory allocation profiles, which
py-spy cannot produce): add `pyroscope-io`, then call a `pyroscope.configure`
setup modelled on `init_profiling()` in `backend/core/telemetry.py` during app
startup — `application_name`, `server_address` from `PYROSCOPE_URL`,
`sample_rate` from `PYROSCOPE_SAMPLE_RATE`, plus your own tags, guarded so an
import failure degrades to "no profiling" instead of crashing.

**Native service (C/C++/Go/Rust) — Alloy eBPF:** add the labels and nothing
else; Alloy discovers it over the Podman socket.

```yaml
my-new-service:
  labels:
    pyroscope.profile: 'true'
    pyroscope.service: 'my-new-service'
```

`pyroscope.service` is the application name Pyroscope stores; omit it and the
container name is used instead.

**Verify any of the three:** the name appears in the Pyroscope UI application
list, and `curl -s http://localhost:4040/api/services/status` mentions it. Then
add a flame-graph panel keyed on `{service_name="my-new-service"}` if you want
it on a dashboard.

---

### MAINT-PROF-003: Changing The Pyroscope Datasource

The Pyroscope datasource **is** provisioned, inside the shared file
`monitoring/grafana/provisioning/datasources/prometheus.yml` (name `Pyroscope`,
uid `pyroscope`, `type: grafana-pyroscope-datasource`,
`url: http://pyroscope:4040`, `access: proxy`, `editable: false`, around line
238). That same file also declares `Prometheus`, `Alertmanager`, `Backend-API`,
`Tempo` and `Loki`, and the Pyroscope entry carries a `tracesToProfiles`-style
link back to Tempo (`datasourceUid: tempo`). Both profiling dashboards select
the datasource by uid, so renaming it breaks them.

`editable: false` means UI edits are refused — change the file, not the datasource.
Grafana serves from `/grafana/`, so its API lives at
`http://localhost:3002/grafana/api/...`; anonymous access is on by default
(`GF_AUTH_ANONYMOUS_ENABLED=true`; `setup.py` derives it off — via the newer
`GRAFANA_ANONYMOUS_ENABLED` — when `EXPOSE_LAN=true`, in which case these API
calls need the machine key or a login session), and the admin pair is
`GF_ADMIN_USER`/`GF_ADMIN_PASSWORD` (both default `admin`). The provisioning
directory is bind-mounted read-only
(`docker-compose.prod.yml:1074`).

**Procedure:**

```bash
# 1. Confirm what is live
curl -s -u admin:admin http://localhost:3002/grafana/api/datasources | jq '.[].uid' # pragma: allowlist secret

# 2. Edit monitoring/grafana/provisioning/datasources/prometheus.yml
#    (keep uid: pyroscope unless you are also rewriting the dashboards)

# 3. Restart Grafana — provisioning is read at startup
podman compose -f docker-compose.prod.yml restart grafana

# 4. Verify
curl -s -u admin:admin http://localhost:3002/grafana/api/datasources/uid/pyroscope | jq '.name, .url, .jsonData' # pragma: allowlist secret
```

---

## Health Monitoring

### Pyroscope Health Check

```bash
#!/bin/bash
# Check Pyroscope health and alert if down

if ! curl -sf http://localhost:4040/ready > /dev/null 2>&1; then
    echo "ALERT: Pyroscope is not responding"
    # Add alerting integration here
    exit 1
fi

echo "OK: Pyroscope is healthy"
```

### Profile Data Freshness

```bash
#!/bin/bash
# Check that each expected subject has data in the last 5 minutes

SERVICES="backend nemotron-backend ai-vlm"

for service in $SERVICES; do
    RESULT=$(curl -s "http://localhost:4040/pyroscope/render?query=${service}&from=now-5m&until=now&format=json" | jq '.flamebearer.numTicks // 0')

    if [ "$RESULT" -eq 0 ]; then
        echo "WARNING: No recent profiles for $service"
    else
        echo "OK: $service has recent profile data"
    fi
done
```

`ai-vlm` ships in the default bring-up (`up -d` starts it; until UR-18 it sat
behind a profile that had to be named explicitly), so its profiles should show
up on its own — still gate that entry on the container running.

---

## Performance Baselines

Overhead expectations for the mechanisms that ship (SDK 100 Hz in-process,
py-spy 30s cycles, eBPF 97 Hz):

| Metric                            | Expected | Watch  |
| --------------------------------- | -------- | ------ |
| Pyroscope server CPU              | < 5%     | > 10%  |
| Pyroscope server memory           | < 500MB  | > 1GB  |
| Profile push latency              | < 1s     | > 5s   |
| Per-subject profiling overhead    | 1-3%     | > 5%   |
| Storage growth per day            | see note | > 1GB  |
| Total storage at 30-day retention | see note | > 30GB |

**On the storage numbers:** the 350-700 MB/day figure quoted in
`monitoring/pyroscope/pyroscope-config.yml`'s comments was written for a stack
profiling seven AI services. A current deployment pushes two subjects from one
process plus one native profile, so measure your own volume instead of planning
against that figure:

```bash
podman exec pyroscope busybox df -h /data
```

---

## Related Documentation

| Document                                                | Purpose                                   |
| ------------------------------------------------------- | ----------------------------------------- |
| [Profiling Guide](../guides/profiling.md)               | Mechanisms, dashboards, trace correlation |
| [Metrics Coverage](../guides/metrics-coverage.md)       | Which series have a producer              |
| [Monitoring Guide](../operator/monitoring.md)           | Full observability stack                  |
| [Pyroscope UI](../ui/pyroscope.md)                      | Frontend dashboard documentation          |
| [AI Performance](../operator/ai-performance.md)         | AI service performance tuning             |
| [GPU Memory Limits](../deployment/gpu-memory-limits.md) | Per-service VRAM sizing                   |

---

## Appendix: Configuration Files

### Pyroscope Server Configuration (NEM-3928)

Location: `monitoring/pyroscope/pyroscope-config.yml`, mounted at
`/etc/pyroscope/config.yml`. Actual contents, abridged:

```yaml
# Pyroscope 1.18.0 configuration (NEM-3928)
# Comprehensive retention policy to prevent disk bloat

# Storage configuration
storage:
  backend: filesystem
  filesystem:
    dir: /data

# Server configuration
server:
  http_listen_port: 4040

# PyroscopeDB retention policy (NEM-3928)
# Disk-based retention to prevent storage exhaustion
pyroscopedb:
  min_free_disk_gb: 10 # Delete oldest when below 10GB free
  min_disk_available_percentage: 0.05 # Or below 5% free
  enforcement_interval: 5m # Check every 5 minutes
  max_block_duration: 1h # Must match block_ranges period

# Compactor configuration
compactor:
  data_dir: /data/compactor
  compaction_interval: 2h # Compact every 2 hours
  cleanup_interval: 15m # Apply retention every 15 minutes
  deletion_delay: 2h # Safety buffer before deletion
  max_opening_blocks_concurrency: 4

# Limits configuration
limits:
  compactor_blocks_retention_period: 720h # 30 days max retention
  ingestion_rate_mb: 4 # Max ingestion rate
  ingestion_burst_size_mb: 8 # Burst allowance
  max_label_names_per_series: 30
  max_label_value_length: 2048
```

### Retention Tuning Guide

| Scenario                   | Recommended Changes                                        |
| -------------------------- | ---------------------------------------------------------- |
| Limited disk space (<50GB) | `compactor_blocks_retention_period: 168h` (7 days)         |
| High-volume profiling      | Increase `ingestion_rate_mb` and `ingestion_burst_size_mb` |
| Faster cleanup             | Reduce `cleanup_interval` to `5m`                          |
| More disk safety margin    | Increase `min_free_disk_gb` to 20                          |
| Development/testing        | `compactor_blocks_retention_period: 24h` (1 day)           |

The config file is bind-mounted read-only, so edits need a container restart
(or recreate) to reach the process.

### Profiler Script

Location: `scripts/pyroscope-profiler.sh`, invoked as
`pyroscope-profiler.sh <service_name> <pyroscope_url> <interval>` with
`SERVICE_NAME`-style arguments (the backend passes `backend`, `PYROSCOPE_URL`
and `PROFILE_INTERVAL`). It waits 10s, finds the python/uvicorn PID, and loops:

```bash
py-spy record --pid "$PID" --duration "$PROFILE_INTERVAL" \
  --format speedscope --output "$PROFILE_FILE" --nonblocking
```

then POSTs the file to `/ingest?name=<service>&from=…&until=…&spyName=pyspy&format=speedscope`.

- `--nonblocking`: minimises impact on the profiled process
- `--duration`: capture length, from `PROFILE_INTERVAL` (default 30s)
- `--format speedscope`: what Pyroscope ingests for `process_cpu`
