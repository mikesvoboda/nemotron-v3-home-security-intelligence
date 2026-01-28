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
