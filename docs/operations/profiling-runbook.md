# Profiling Operations Runbook

> Operational procedures for managing Pyroscope continuous profiling in production.

## Quick Reference

| Task                        | Command                                                       |
| --------------------------- | ------------------------------------------------------------- |
| Check Pyroscope health      | `curl http://localhost:4040/ready`                            |
| View Pyroscope UI           | Open [http://localhost:4040](http://localhost:4040)           |
| Restart Pyroscope           | `podman-compose -f docker-compose.prod.yml restart pyroscope` |
| View profiler logs (AI svc) | `podman exec ai-yolo26 cat /tmp/profiler.log`                 |
| Check backend profiling     | `podman logs backend 2>&1 \| grep -i pyroscope`               |
| Disable profiling globally  | Set `PYROSCOPE_ENABLED=false` in `.env`                       |

---

## Automated Regression Alert Response Procedures

This section covers response procedures for automated regression detection alerts (NEM-4133).

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
# Open: http://localhost:3002/d/hsi-profiling
# Select the affected service from dropdown

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
   podman-compose -f docker-compose.prod.yml pull [service]
   podman-compose -f docker-compose.prod.yml up -d [service]
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
   podman-compose -f docker-compose.prod.yml restart [service]

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
   # 0 */4 * * * podman-compose -f docker-compose.prod.yml restart [service]
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
# Open http://localhost:3002/d/hsi-profiling
# Select "nemotron-backend" service
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

**Symptoms:**

- Object detection taking longer
- Real-time detection pipeline backing up
- Detection queue growing

**Diagnosis:**

```bash
# 1. Check YOLO26 latency
curl -s "http://localhost:9090/api/v1/query?query=job:yolo26_inference_latency:p95_5m" | jq

# 2. Check GPU utilization
curl -s "http://localhost:9090/api/v1/query?query=yolo26_gpu_utilization" | jq

# 3. Check GPU temperature (throttling?)
curl -s "http://localhost:9090/api/v1/query?query=yolo26_gpu_temperature" | jq

# 4. Check if model is loaded
curl -s "http://localhost:9090/api/v1/query?query=yolo26_model_loaded" | jq

# 5. View YOLO26 flame graph
# Open http://localhost:3002/d/hsi-profiling
# Select "ai-yolo26" service
```

**Resolution:**

1. **If GPU throttling:**

   - Improve cooling
   - Reduce batch size
   - Lower power limit

2. **If model not optimally loaded:**

   ```bash
   # Restart to reinitialize TensorRT
   podman-compose -f docker-compose.prod.yml restart ai-yolo26
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

# Test internal connectivity
podman exec backend curl -s http://pyroscope:4040/ready
```

**Resolution:**

```bash
# Restart Pyroscope
podman-compose -f docker-compose.prod.yml restart pyroscope

# If restart fails, recreate container
podman-compose -f docker-compose.prod.yml up -d --force-recreate pyroscope

# Verify recovery
curl http://localhost:4040/ready
# Expected: "ready"
```

**Impact:** Profiling data is lost during outage but services continue operating normally.

---

### INC-PROF-002: High CPU Overhead from Profiling

**Symptoms:**

- Higher than expected CPU usage (>5% overhead)
- Services responding slower than normal
- py-spy processes consuming excessive CPU

**Diagnosis:**

```bash
# Check py-spy processes
podman exec ai-yolo26 ps aux | grep py-spy

# Check profiler log for errors
podman exec ai-yolo26 cat /tmp/profiler.log

# Check profile interval
podman exec ai-yolo26 env | grep PROFILE_INTERVAL
```

**Resolution:**

Option 1: Increase profile interval (less frequent profiling)

```bash
# Edit docker-compose.prod.yml or create override
# Set PROFILE_INTERVAL=60 (default is 30)
podman-compose -f docker-compose.prod.yml up -d ai-yolo26
```

Option 2: Disable profiling on specific service

```bash
# Add to docker-compose override
# PYROSCOPE_ENABLED=false for the affected service
podman-compose -f docker-compose.prod.yml up -d ai-yolo26
```

Option 3: Disable profiling globally

```bash
echo "PYROSCOPE_ENABLED=false" >> .env
podman-compose -f docker-compose.prod.yml up -d
```

**Impact:** Reduced profiling coverage but improved service performance.

---

### INC-PROF-003: Profiler Not Collecting Data for Service

**Symptoms:**

- Specific service missing from Pyroscope UI
- Service running but no profiles being collected
- Profiler log shows errors

**Diagnosis:**

```bash
# Check if SERVICE_NAME is set
podman exec ai-yolo26 env | grep SERVICE_NAME

# Check profiler script is running
podman exec ai-yolo26 pgrep -a pyroscope

# Check profiler log
podman exec ai-yolo26 cat /tmp/profiler.log

# For backend (SDK-based), check initialization
podman logs backend 2>&1 | grep -i "pyroscope profiling"
```

**Resolution:**

For AI services (py-spy based):

```bash
# Restart the service to reinitialize profiler
podman-compose -f docker-compose.prod.yml restart ai-yolo26

# Verify profiler started
podman exec ai-yolo26 cat /tmp/profiler.log
# Should see: "Starting profiler for ai-yolo26"
```

For backend (SDK based):

```bash
# Check SDK is installed
podman exec backend pip show pyroscope-io

# Restart backend
podman-compose -f docker-compose.prod.yml restart backend

# Verify initialization
podman logs backend 2>&1 | grep -i "pyroscope profiling initialized"
```

---

### INC-PROF-004: Pyroscope Storage Full

**Symptoms:**

- Pyroscope queries becoming slow
- Disk usage growing rapidly in pyroscope volume
- "disk full" or "quota exceeded" errors in logs

**Diagnosis:**

```bash
# Check volume usage
podman volume inspect pyroscope_data

# Check container disk usage
podman exec pyroscope df -h /data

# Check retention settings
podman exec pyroscope cat /etc/pyroscope/server.yml
```

**Resolution:**

```bash
# Reduce retention period (requires config change)
# Edit monitoring/pyroscope/pyroscope-config.yml
# Set retention-period to a lower value (e.g., 7d)

# Recreate Pyroscope with new config
podman-compose -f docker-compose.prod.yml up -d --force-recreate pyroscope

# If urgent, clear old data
podman-compose -f docker-compose.prod.yml stop pyroscope
podman volume rm pyroscope_data  # WARNING: Deletes all profiling history
podman-compose -f docker-compose.prod.yml up -d pyroscope
```

**Impact:** Reduced historical data but prevents service disruption.

---

## Maintenance Procedures

### MAINT-PROF-001: Updating Pyroscope Version

**Pre-flight Checks:**

```bash
# Check current version
podman exec pyroscope pyroscope --version

# Review release notes for breaking changes
# https://github.com/grafana/pyroscope/releases
```

**Procedure:**

```bash
# 1. Pull new image
podman pull grafana/pyroscope:latest

# 2. Stop Pyroscope
podman-compose -f docker-compose.prod.yml stop pyroscope

# 3. Backup configuration
cp monitoring/pyroscope/pyroscope-config.yml monitoring/pyroscope/pyroscope-config.yml.bak

# 4. Update version in docker-compose.prod.yml if pinned
# image: grafana/pyroscope:1.18.0 -> grafana/pyroscope:1.19.0

# 5. Recreate container
podman-compose -f docker-compose.prod.yml up -d pyroscope

# 6. Verify health
curl http://localhost:4040/ready
```

**Rollback:**

```bash
podman-compose -f docker-compose.prod.yml stop pyroscope
# Revert docker-compose.prod.yml version
podman-compose -f docker-compose.prod.yml up -d pyroscope
```

---

### MAINT-PROF-002: Adding Profiling to New Service

**Procedure:**

1. **Add py-spy to Dockerfile:**

   ```dockerfile
   # Install py-spy for profiling
   RUN uv tool install py-spy && \
       cp /root/.local/bin/py-spy /usr/local/bin/py-spy && \
       chmod +x /usr/local/bin/py-spy

   # Copy profiler scripts
   COPY --chmod=755 scripts/pyroscope-profiler.sh /usr/local/bin/pyroscope-profiler.sh
   COPY --chmod=755 scripts/ai-entrypoint.sh /usr/local/bin/ai-entrypoint.sh

   # Install procps for pgrep
   RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

   ENTRYPOINT ["/usr/local/bin/ai-entrypoint.sh"]
   ```

2. **Add environment variables in docker-compose.prod.yml:**

   ```yaml
   my-new-service:
     labels:
       pyroscope.profile: 'true'
       pyroscope.service: 'my-new-service'
     environment:
       - SERVICE_NAME=my-new-service
       - PYROSCOPE_ENABLED=${PYROSCOPE_ENABLED:-true}
       - PYROSCOPE_URL=http://pyroscope:4040
   ```

3. **Rebuild and deploy:**

   ```bash
   podman-compose -f docker-compose.prod.yml build --no-cache my-new-service
   podman-compose -f docker-compose.prod.yml up -d my-new-service
   ```

4. **Verify profiling:**
   ```bash
   podman exec my-new-service cat /tmp/profiler.log
   # Should see: "Starting profiler for my-new-service"
   ```

---

### MAINT-PROF-003: Configuring Grafana Datasource

**Procedure:**

Pyroscope datasource is auto-provisioned. If manual setup needed:

```bash
# 1. Check if datasource exists
curl -s http://admin:admin@localhost:3002/api/datasources | jq '.[].name' # pragma: allowlist secret

# 2. If missing, add via provisioning
cat > monitoring/grafana/provisioning/datasources/pyroscope.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Pyroscope
    type: pyroscope
    url: http://pyroscope:4040
    access: proxy
    isDefault: false
EOF

# 3. Restart Grafana
podman-compose -f docker-compose.prod.yml restart grafana
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

# Query Pyroscope API for recent data
SERVICES="nemotron-backend ai-yolo26 ai-florence ai-clip"

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

| Metric                        | Expected | Alert Threshold |
| ----------------------------- | -------- | --------------- |
| Pyroscope CPU usage           | < 5%     | > 10%           |
| Pyroscope memory usage        | < 500MB  | > 1GB           |
| Profile push latency          | < 1s     | > 5s            |
| Profiler overhead per service | 1-3%     | > 5%            |
| Storage growth per day        | ~100MB   | > 500MB         |

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

### Pyroscope Server Configuration

Location: `monitoring/pyroscope/pyroscope-config.yml`

```yaml
# Default Pyroscope configuration
analytics-opt-out: true

# Storage configuration
storage:
  path: /data

# Retention (15 days default)
retention-period: 15d

# Server configuration
server:
  http-listen-port: 4040
```

### AI Entrypoint Script

Location: `scripts/ai-entrypoint.sh`

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
- `--duration`: Profile capture duration (default 30s)
- `--format speedscope`: Compatible with Pyroscope ingestion
