# Profiling Operations Runbook

> Operational procedures for managing Pyroscope continuous profiling in production.

> **Topology note (2026-09-22).** Since the AI-gateway consolidation, the only service that actually runs the py-spy profiler is **`backend`** (launched by `backend/entrypoint.sh`, log at `/app/data/logs/profiler.log`, service name `backend`), plus the backend's in-process Pyroscope SDK (application name `nemotron-backend`, `backend/core/telemetry.py`). The old per-AI-container profile names (`ai-yolo26`, `ai-florence`, `ai-clip`, …) no longer emit data: those containers are retired. `ai-llm` and `ai-gateway` declare `SERVICE_NAME`/`PYROSCOPE_*` env vars and a `pyroscope.profile` label, but neither image runs a profiler (llama.cpp is native code; the gateway is Triton) — treat those as placeholders.

## Quick Reference

| Task                        | Command                                                               |
| --------------------------- | --------------------------------------------------------------------- |
| Check Pyroscope health      | `curl http://localhost:4040/ready`                                    |
| View Pyroscope UI           | Open [http://localhost:4040](http://localhost:4040)                   |
| Restart Pyroscope           | `podman compose -f docker-compose.prod.yml restart pyroscope`         |
| View profiler log (backend) | `podman exec backend cat /app/data/logs/profiler.log`                 |
| Check backend SDK profiling | `podman logs backend 2>&1 \| grep -i pyroscope`                       |
| Disable profiling globally  | Set `PYROSCOPE_ENABLED=false` in `.env`                               |
| Profiling dashboard         | `http://localhost:3002/grafana/d/hsi-profiling` (uid `hsi-profiling`) |

---

## Automated Regression Alert Response Procedures

This section covers response procedures for automated regression detection alerts (NEM-4133). Alert definitions: `monitoring/profiling-regression-alerts.yml`; recording rules: `monitoring/profiling-recording-rules.yml`.

### ALERT-REG-001: ServiceCPUSpike / ServiceCPUSpikeCritical

**Alert Condition:** CPU usage >50% (warning) or >100% (critical) above 24-hour average for 15+ minutes.

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
# Select the affected service from dropdown (live names: "backend", "nemotron-backend")

# 3. Compare current vs baseline flame graphs
# Enable "Comparison" mode in the dashboard
# Look for new hot functions or significantly increased function times

# 4. Check for recent deployments
git log --oneline --since="24 hours ago"

# 5. Check if workload increased
curl -s "http://localhost:9090/api/v1/query?query=rate(hsi_detections_processed_total[1h])" | jq
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

   - Scale the service if possible
   - Implement rate limiting
   - Optimize hot code paths identified in flame graph

3. **If caused by memory pressure (GC overhead):**
   - Check memory alerts alongside CPU
   - Increase memory allocation
   - Investigate memory leaks

**Escalation:** If unresolved after 30 minutes, escalate to on-call engineer.

---

### ALERT-REG-002: ServiceMemoryGrowth / ServiceMemoryGrowthCritical

**Alert Condition:** Memory usage >25% (warning) or >50% (critical) above 6-hour average for 30+ minutes.

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
# (backend has PYROSCOPE_MEMORY_ENABLED=true, so allocation profiles exist for it)
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

**Alert Condition:** Memory projected to double within 24 hours based on current growth rate.

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
# In Grafana Pyroscope, compare memory profiles from:
# - 6 hours ago
# - Current
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

   - Use memory profiler to identify leak source
   - Check for unclosed database connections
   - Check for unbounded caches or queues
   - Review recent code changes for retained references

3. **Long-term fix:**
   - Deploy code fix
   - Add memory monitoring to CI/CD pipeline
   - Implement memory pressure alerts

---

### ALERT-REG-004: BackendHighLatency / BackendHighLatencyCritical

**Alert Condition:** Backend API P99 latency >2s (warning) or >5s (critical) for 10+ minutes.

**Symptoms:**

- Slow API responses
- UI timeouts
- WebSocket disconnections

**Diagnosis:**

```bash
# 1. Check current latency
curl -s "http://localhost:9090/api/v1/query?query=job:backend_api_latency:p99_5m" | jq '.data.result'

# 2. Check database query latency
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.99,rate(hsi_db_query_duration_seconds_bucket[5m]))" | jq

# 3. Check Redis latency
curl -s "http://localhost:9090/api/v1/query?query=redis_slowlog_length" | jq

# 4. Check CPU usage (may be contention)
curl -s "http://localhost:9090/api/v1/query?query=job:backend_cpu_seconds:rate5m" | jq

# 5. View backend flame graph for hot paths
# Open http://localhost:3002/grafana/d/hsi-profiling
# Select "nemotron-backend" (SDK) or "backend" (py-spy)
```

**Resolution:**

1. **If database is slow:**

   ```bash
   # Check for long-running queries
   podman exec postgres psql -U hsi -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

   # Check for missing indexes
   podman exec postgres psql -U hsi -c "EXPLAIN ANALYZE [slow_query];"
   ```

2. **If Redis is slow:**

   ```bash
   # Check slow log
   podman exec redis redis-cli slowlog get 10

   # Check memory usage
   podman exec redis redis-cli info memory
   ```

3. **If CPU contention:**
   - Scale backend instances
   - Optimize hot code paths from flame graph
   - Add caching for expensive operations

---

### ALERT-REG-005: YOLO26LatencyRegression

**Alert Condition:** YOLO26 inference P95 latency increased >50% compared to 1-hour average.

> **Status (2026-09-22):** the recording rule `job:yolo26_inference_latency:p95_5m` is built on `yolo26_inference_latency_seconds_bucket`, which only the retired standalone detector exported — the gateway's Triton exposes no such metric, so this rule has no data in the current topology. Triton's own latency signal is `nv_inference_request_duration_us`, a **cumulative counter** (µs), not a histogram: with the server's default metrics config (`summary_latencies` is NOT enabled) no P95 exists server-side, so the retarget lands on the per-model **mean** until the config changes. Work the equivalent signal directly:
>
> ```bash
> # Triton-side mean latency for the yolo26 model (scraped via triton-metrics at ai-gateway:8002)
> curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
>   'query=sum(rate(nv_inference_request_duration_us{model="yolo26"}[5m])) / (sum(rate(nv_inference_request_success[5m])) + 0.001)' | jq
> ```

**Symptoms:**

- Object detection taking longer
- Real-time detection pipeline backing up
- Detection queue growing

**Diagnosis:**

```bash
# 1. Triton inference latency + throughput for yolo26
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=sum(rate(nv_inference_request_success_total{model="yolo26"}[5m]))' | jq

# 2. Check GPU utilization (dcgm-exporter)
curl -s "http://localhost:9090/api/v1/query?query=DCGM_FI_DEV_GPU_UTIL" | jq

# 3. Check GPU temperature (throttling?)
curl -s "http://localhost:9090/api/v1/query?query=DCGM_FI_DEV_GPU_TEMP" | jq

# 4. Check the router still reports the model ready
curl -s http://localhost:8090/yolo26/health | jq .
curl -s http://localhost:8090/health | jq '.models.yolo26'

# 5. Check backend-attributed detector latency
curl -s "http://localhost:9090/api/v1/query" --data-urlencode \
  'query=rate(hsi_ai_request_duration_seconds_sum{ai_service="yolo26"}[5m]) / rate(hsi_ai_request_duration_seconds_count{ai_service="yolo26"}[5m])' | jq
```

**Resolution:**

1. **If GPU throttling:**

   - Improve cooling
   - Reduce batch size
   - Lower power limit

2. **If model not optimally loaded:**

   ```bash
   # Restart the gateway to reinitialize Triton/TensorRT
   podman compose -f docker-compose.prod.yml restart ai-gateway
   # Triton warm-up can take up to its 180s health start_period
   ```

3. **If input resolution changed:**
   - Verify input preprocessing
   - Check for larger than expected images

---

### ALERT-REG-006: MultiServiceCPURegression

**Alert Condition:** 2 or more services showing >30% CPU increase simultaneously.

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

# 3. Check for noisy neighbor (other processes)
top -b -n 1 | head -20

# 4. Check disk I/O (may cause CPU wait)
iostat -x 1 5

# 5. Check network issues
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

3. **If coordinated attack/abuse:**
   - Implement rate limiting
   - Block abusive traffic
   - Scale defensive capacity

---

## Incident Response Procedures

### INC-PROF-001: Pyroscope Server Unavailable

**Symptoms:**

- No new profiling data in Grafana dashboard
- "Connection refused" errors in service logs
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
```

**Resolution:**

```bash
# Restart Pyroscope
podman compose -f docker-compose.prod.yml restart pyroscope

# If restart fails, recreate container
podman compose -f docker-compose.prod.yml up -d --force-recreate pyroscope

# Verify recovery
curl http://localhost:4040/ready
```

**Impact:** Profiling data is lost during outage but services continue operating normally.

---

### INC-PROF-002: High CPU Overhead from Profiling

**Symptoms:**

- Higher than expected CPU usage (>5% overhead)
- Services responding slower than normal
- py-spy processes consuming excessive CPU

**Diagnosis:**

In the current topology the py-spy profiler runs only inside the `backend` container (started by `backend/entrypoint.sh`; it skips profiling of anything that isn't a Python process, so the LLM/gateway containers never run it).

```bash
# Check py-spy processes in backend
podman exec backend ps aux | grep py-spy

# Check profiler log for errors
podman exec backend cat /app/data/logs/profiler.log

# Check profile interval (default 30s, set via PROFILE_INTERVAL)
podman exec backend env | grep -E "PROFILE_INTERVAL|PYROSCOPE"
```

**Resolution:**

Option 1: Increase profile interval (less frequent profiling)

```bash
# Add to docker-compose.override.yml under backend.environment:
#   - PROFILE_INTERVAL=60      (default is 30)
podman compose -f docker-compose.prod.yml up -d backend
```

Option 2: Disable profiling on backend only

```bash
# Add to docker-compose.override.yml under backend.environment:
#   - PYROSCOPE_ENABLED=false   (turns off both the py-spy loop and the SDK)
podman compose -f docker-compose.prod.yml up -d backend
```

Option 3: Disable profiling globally

```bash
echo "PYROSCOPE_ENABLED=false" >> .env
podman compose -f docker-compose.prod.yml up -d
```

**Impact:** Reduced profiling coverage but improved service performance.

---

### INC-PROF-003: Profiler Not Collecting Data for Service

**Symptoms:**

- Expected service missing from Pyroscope UI
- Service running but no profiles being collected
- Profiler log shows errors

**Diagnosis:**

```bash
# Is the profiler script running in backend?
podman exec backend pgrep -fa pyroscope-profiler.sh

# Profiler log (launched by backend/entrypoint.sh)
podman exec backend tail -50 /app/data/logs/profiler.log
# Expect lines like: "[pyroscope-profiler] ... Starting profiler for backend"

# Pyroscope actually receiving anything?
curl -s http://localhost:4040/api/services/status 2>/dev/null | head -c 400

# For backend (SDK-based), check initialization in app logs
podman logs backend 2>&1 | grep -i "pyroscope profiling"
```

**Resolution:**

For the py-spy profiler (backend):

```bash
# Restart the service to reinitialize the profiler
podman compose -f docker-compose.prod.yml restart backend

# Verify profiler started
podman exec backend tail -5 /app/data/logs/profiler.log
```

For the SDK (in-process):

```bash
# Check the SDK dependency is installed in the image
podman exec backend python -c "import pyroscope; print(pyroscope.__name__)"

# Restart backend (SDK initializes during app startup, backend/core/telemetry.py)
podman compose -f docker-compose.prod.yml restart backend

# Verify initialization
podman logs backend 2>&1 | grep -i pyroscope
```

**Historical note:** the old per-AI-service procedure (`podman exec ai-yolo26 env | grep SERVICE_NAME`, `/tmp/profiler.log`) applied to the retired standalone AI containers, which baked `scripts/ai-entrypoint.sh` into their images. Those containers no longer exist in compose; if you are reading an older incident that references them, map them to `ai-gateway` (no profiler) or `backend` (profiler).

---

### INC-PROF-004: Pyroscope Storage Full (NEM-3928)

**Symptoms:**

- Pyroscope queries becoming slow
- Disk usage growing rapidly in pyroscope volume
- "disk full" or "quota exceeded" errors in logs

**Diagnosis:**

```bash
# Check volume usage
podman volume inspect pyroscope_data

# Check container disk usage (image is busybox-based — invoke df via busybox)
podman exec pyroscope busybox df -h /data

# Check retention settings currently mounted in the container (NEM-3928)
podman exec pyroscope cat /etc/pyroscope/config.yml

# Check compactor status
podman logs pyroscope 2>&1 | grep -i "compactor\|retention\|cleanup"
```

**Retention Configuration (NEM-3928):**

The Pyroscope retention policy is configured in `monitoring/pyroscope/pyroscope-config.yml` (mounted read-only at `/etc/pyroscope/config.yml`):

| Setting                                     | Value | Description                                     |
| ------------------------------------------- | ----- | ----------------------------------------------- |
| `limits.compactor_blocks_retention_period`  | 720h  | Maximum block age (30 days)                     |
| `pyroscopedb.min_free_disk_gb`              | 10 GB | Delete oldest blocks when free space below this |
| `pyroscopedb.min_disk_available_percentage` | 0.05  | Secondary disk space threshold (5%)             |
| `pyroscopedb.enforcement_interval`          | 5m    | How often disk-based retention is checked       |
| `compactor.cleanup_interval`                | 15m   | How often time-based retention is enforced      |
| `compactor.deletion_delay`                  | 2h    | Delay before permanent deletion                 |

**Resolution:**

```bash
# Option 1: Wait for automatic cleanup (recommended)
# The compactor runs every 15 minutes and will delete old blocks
# when disk space drops below thresholds. Check logs:
podman logs pyroscope 2>&1 | grep -i "deleting\|cleanup\|retention"

# Option 2: Reduce retention period for faster cleanup
# Edit monitoring/pyroscope/pyroscope-config.yml:
# Change: compactor_blocks_retention_period: 720h
# To:     compactor_blocks_retention_period: 168h  # 7 days

# Restart Pyroscope to apply new config
podman compose -f docker-compose.prod.yml restart pyroscope

# Option 3: Force immediate compaction
# Trigger a compaction cycle by restarting Pyroscope
podman compose -f docker-compose.prod.yml restart pyroscope

# Option 4: If urgent, clear all data (last resort)
podman compose -f docker-compose.prod.yml stop pyroscope
podman volume rm pyroscope_data  # WARNING: Deletes all profiling history
podman compose -f docker-compose.prod.yml up -d pyroscope
```

**Prevention:**

- Monitor Pyroscope disk usage with the "Storage growth per day" metric
- Alert when disk usage exceeds 80% of expected maximum (~16GB for 30-day retention)
- Consider reducing `compactor_blocks_retention_period` for disk-constrained environments

**Impact:** Automatic retention prevents disk exhaustion. Manual intervention only needed if retention policy is insufficient for workload.

---

## Maintenance Procedures

### MAINT-PROF-001: Updating Pyroscope Version

The Pyroscope image is **built**, not pulled directly: `docker-compose.prod.yml` builds `./monitoring/pyroscope` (a thin layer adding busybox for health checks on top of `docker.io/grafana/pyroscope:1.18.0`). Pin changes go in `monitoring/pyroscope/Dockerfile`, not compose.

**Pre-flight Checks:**

```bash
# Check current base version (pinned in the Dockerfile)
grep "grafana/pyroscope" monitoring/pyroscope/Dockerfile

# Review release notes for breaking changes
# https://github.com/grafana/pyroscope/releases
```

**Procedure:**

```bash
# 1. Update the base image tag in monitoring/pyroscope/Dockerfile
#    e.g. FROM docker.io/grafana/pyroscope:1.18.0 -> 1.19.0

# 2. Backup configuration
cp monitoring/pyroscope/pyroscope-config.yml monitoring/pyroscope/pyroscope-config.yml.bak

# 3. Rebuild (always --no-cache for infra changes) and recreate
podman compose -f docker-compose.prod.yml build --no-cache pyroscope
podman compose -f docker-compose.prod.yml up -d pyroscope

# 4. Verify health
curl http://localhost:4040/ready
```

**Rollback:**

```bash
# Revert monitoring/pyroscope/Dockerfile to the previous tag
podman compose -f docker-compose.prod.yml build --no-cache pyroscope
podman compose -f docker-compose.prod.yml up -d pyroscope
```

---

### MAINT-PROF-002: Adding Profiling to New Service

> **Status (2026-09-22):** the py-spy + `ai-entrypoint.sh` recipe below is the pattern the retired per-AI-container images used (`ai/yolo26`, `ai/clip`, `ai/florence`, `ai/enrichment*` Dockerfiles still reference `scripts/ai-entrypoint.sh`, but no active compose service builds them). `ai-gateway` uses its own `/entrypoint.sh` with no profiler; `ai-llm` runs native llama.cpp, which py-spy cannot profile. For a new **Python** service, follow the backend recipe instead.

**Recommended recipe (backend pattern):**

1. **Install py-spy and copy the profiler script into the image** (see `backend/Dockerfile:174-182`):

   ```dockerfile
   RUN uv tool install py-spy && \
       cp -L /root/.local/bin/py-spy /usr/local/bin/py-spy && \
       chmod +x /usr/local/bin/py-spy

   COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
   ```

2. **Start the profiler from the service entrypoint** (see `backend/entrypoint.sh:50-55`):

   ```bash
   if [ "${PYROSCOPE_ENABLED:-true}" = "true" ]; then
       nohup /usr/local/bin/pyroscope-profiler.sh "my-service" \
           "${PYROSCOPE_URL:-http://pyroscope:4040}" "${PROFILE_INTERVAL:-30}" \
           >> /app/data/logs/profiler.log 2>&1 &
   fi
   ```

3. **Add environment variables in docker-compose.prod.yml:**

   ```yaml
   my-new-service:
     labels:
       pyroscope.profile: 'true'
       pyroscope.service: 'my-new-service'
     environment:
       - PYROSCOPE_ENABLED=${PYROSCOPE_ENABLED:-true}
       - PYROSCOPE_URL=http://pyroscope:4040
   ```

4. **Rebuild and deploy:**

   ```bash
   podman compose -f docker-compose.prod.yml build --no-cache my-new-service
   podman compose -f docker-compose.prod.yml up -d my-new-service
   ```

5. **Verify profiling:**

   ```bash
   podman exec my-new-service cat /app/data/logs/profiler.log
   # Should see: "Starting profiler for my-new-service"
   ```

For in-process CPU/memory profiles, add the SDK instead (or as well): `pyroscope-io` is already a project dependency; see `backend/core/telemetry.py::init_profiling` for the wiring pattern (`PYROSCOPE_ENABLED`, `PYROSCOPE_URL`, `PYROSCOPE_SAMPLE_RATE`, `PYROSCOPE_MEMORY_ENABLED`).

**Legacy recipe (retired AI containers only):** bake `scripts/ai-entrypoint.sh` as the image ENTRYPOINT; it launches the same profiler script in the background when `SERVICE_NAME` and `PYROSCOPE_ENABLED=true` are set. Kept here for reading old incidents; do not build new services this way.

---

### MAINT-PROF-003: Configuring Grafana Datasource

The Pyroscope datasource is **not** auto-provisioned — `monitoring/grafana/provisioning/datasources/` contains only `prometheus.yml`. The profiling dashboards reference a datasource with uid `pyroscope`, so if it is missing, add it via a provisioning file. Grafana serves from the `/grafana/` sub-path (`GF_SERVER_SERVE_FROM_SUB_PATH=true`), so its API lives at `http://localhost:3002/grafana/api/...`.

**Procedure:**

```bash
# 1. Check if datasource exists (creds default to admin/admin unless GF_ADMIN_USER/GF_ADMIN_PASSWORD override in .env)
curl -s http://admin:admin@localhost:3002/grafana/api/datasources | jq '.[].name' # pragma: allowlist secret

# 2. If missing, add via provisioning
cat > monitoring/grafana/provisioning/datasources/pyroscope.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Pyroscope
    uid: pyroscope
    type: grafana-pyroscope-datasource
    url: http://pyroscope:4040
    access: proxy
    isDefault: false
EOF

# 3. Restart Grafana
podman compose -f docker-compose.prod.yml restart grafana
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
# Check if profiles are being collected (data within last 5 minutes)

# Live profile names in the current topology: "backend" (py-spy) and
# "nemotron-backend" (SDK). Retired names (ai-yolo26, ai-florence, ai-clip)
# stopped reporting at the gateway consolidation.
SERVICES="backend nemotron-backend"

for service in $SERVICES; do
    # Check for data in last 5 minutes
    RESULT=$(curl -s "http://localhost:4040/pyroscope/render?query=${service}&from=now-5m&until=now&format=json" | jq '.flamebearer.numTicks // 0')

    if [ "$RESULT" -eq 0 ]; then
        echo "WARNING: No recent profiles for $service"
    else
        echo "OK: $service has recent profile data"
    fi
done
```

---

## Performance Baselines

| Metric                        | Expected   | Alert Threshold |
| ----------------------------- | ---------- | --------------- |
| Pyroscope CPU usage           | < 5%       | > 10%           |
| Pyroscope memory usage        | < 500MB    | > 1GB           |
| Profile push latency          | < 1s       | > 5s            |
| Profiler overhead per service | 1-3%       | > 5%            |
| Storage growth per day        | ~350-700MB | > 1GB           |
| Total storage (30-day)        | ~10-20GB   | > 30GB          |

---

## Related Documentation

| Document                                        | Purpose                             |
| ----------------------------------------------- | ----------------------------------- |
| [Profiling Guide](../guides/profiling.md)       | User-facing profiling documentation |
| [Monitoring Guide](../operator/monitoring.md)   | Full observability stack            |
| [Pyroscope UI](../ui/pyroscope.md)              | Frontend dashboard documentation    |
| [AI Performance](../operator/ai-performance.md) | AI service performance tuning       |

---

## Appendix: Configuration Files

### Pyroscope Server Configuration (NEM-3928)

Location: `monitoring/pyroscope/pyroscope-config.yml` (mounted at `/etc/pyroscope/config.yml`). Actual file contents, abridged:

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

### AI Entrypoint Script (legacy — retired AI images)

Location: `scripts/ai-entrypoint.sh` (still referenced by the retired `ai/yolo26`, `ai/clip`, `ai/florence`, `ai/enrichment*` Dockerfiles; no active compose service uses it — `backend/entrypoint.sh` runs the profiler directly, `ai-gateway` has its own entrypoint without profiling).

```bash
#!/bin/bash
# Starts profiler in background if enabled, then runs main command
set -e

if [ "${PYROSCOPE_ENABLED:-true}" = "true" ] && [ -n "$SERVICE_NAME" ]; then
    nohup /usr/local/bin/pyroscope-profiler.sh "$SERVICE_NAME" \
        "${PYROSCOPE_URL:-http://pyroscope:4040}" \
        "${PROFILE_INTERVAL:-30}" >> /tmp/profiler.log 2>&1 &
fi

exec "$@"
```

### Profiler Script

Location: `scripts/pyroscope-profiler.sh`

Captures CPU profiles using py-spy and pushes to Pyroscope in Speedscope format. Key parameters:

- `--nonblocking`: Minimizes impact on profiled process
- `--duration`: Profile capture duration (default 30s, from `PROFILE_INTERVAL`)
- `--format speedscope`: Compatible with Pyroscope ingestion
