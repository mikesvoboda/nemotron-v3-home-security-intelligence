# Troubleshooting Index

> Your first stop when something goes wrong. Find your symptom, get to the solution fast.

**Time to read:** ~5 min
**Prerequisites:** None

---

## Quick Self-Check Before Troubleshooting

Before diving into specific issues, run these quick checks:

```bash
# 1. System health (is everything running?)
curl -s http://localhost:8000/api/system/health | jq .

# 2. Service status (are all containers up?)
docker compose -f docker-compose.prod.yml ps

# 3. GPU status (is the GPU available?)
nvidia-smi

# 4. Recent logs (any obvious errors?)
docker compose -f docker-compose.prod.yml logs --tail=50 backend
```

If all services show "healthy" and containers are running, proceed to the specific symptom below.

---

## Fast Triage Flow (Health → Fix)

Use this when you're not sure where to start.

![Troubleshooting Decision Tree showing diagnostic flow: Start with system health check, branch based on failing component (database, Redis, AI services, backend, frontend), follow specific remediation steps for each failure type including restart commands and configuration checks](../../images/troubleshooting-decision-tree.png)

_Decision tree for diagnosing system health issues: Start with the health check endpoint, then follow the path based on which services are failing to quickly identify and resolve problems._

---

## Symptom Quick Reference Table

| Symptom                     | Likely Cause                                 | Quick Fix                   | Detailed Guide                                     |
| --------------------------- | -------------------------------------------- | --------------------------- | -------------------------------------------------- |
| Dashboard shows no events   | File watcher not running or AI services down | Restart backend             | [Events Not Appearing](#dashboard-shows-no-events) |
| Risk gauge stuck at 0       | Nemotron service unavailable                 | Start Nemotron LLM          | [AI Issues](ai-issues.md#analysis-failing)         |
| Camera shows offline        | Camera not uploading or folder path wrong    | Check FTP and folder config | [Camera Offline](#camera-shows-offline)            |
| AI not responding           | Services not started or port conflicts       | Start AI services           | [AI Not Working](#ai-not-working)                  |
| WebSocket disconnected      | Backend down or network issues               | Check backend health        | [WebSocket Issues](#websocket-disconnected)        |
| High CPU/memory usage       | Too many images or memory leak               | Check queue sizes           | [Performance Issues](#high-cpumemory-usage)        |
| Disk space running out      | Retention not configured                     | Run cleanup                 | [Disk Space Issues](#disk-space-running-out)       |
| Slow detection response     | GPU not being used                           | Check CUDA availability     | [Slow Performance](#slow-ai-inference)             |
| "Connection refused" errors | Service not running                          | Start the service           | [Connection Issues](connection-issues.md)          |
| CORS errors in browser      | Frontend/backend URL mismatch                | Update CORS_ORIGINS         | [CORS Errors](#cors-errors-in-browser)             |

---

## Dashboard Shows No Events

### What You See

- Empty activity feed
- No recent events in timeline
- Risk gauge may be at 0 or stale

### Quick Diagnosis

```bash
# Check if events exist in database
curl -s http://localhost:8000/api/events?limit=5 | jq '.pagination.total'

# Check pipeline status
curl -s http://localhost:8000/api/system/pipeline | jq .
```

### Possible Causes (Most Likely First)

1. **File watcher not running** - Images not being picked up
2. **AI services not running** - Detections not being created
3. **No images uploaded** - Cameras not sending images
4. **Batch not completing** - Detections queued but not analyzed

### Solutions

**1. Check file watcher status:**

```bash
curl -s http://localhost:8000/api/system/health/ready | jq '.workers[] | select(.name | test("file_watcher|detection"))'
```

If not running, restart backend: `docker compose -f docker-compose.prod.yml restart backend`

**2. Verify images are being uploaded:**

```bash
ls -lt /export/foscam/*/  # Should show recent files
```

**3. Check AI service health:**

```bash
curl http://localhost:8090/yolo26/health     # YOLO26 (AI gateway router)
curl http://localhost:8091/health            # Nemotron (ai-llm container)
curl http://localhost:8090/florence/health   # Florence-2 (optional router)
curl http://localhost:8090/clip/health       # CLIP (optional router)
curl http://localhost:8090/enrichment/health # Heavy enrichment (optional router)
curl http://localhost:8090/enrich-lt/health  # Light enrichment (optional router)
```

**4. Check queue depths:**

```bash
curl -s http://localhost:8000/api/system/telemetry | jq '.queues'
```

If queues are growing but not processing, AI services may be down.

See: [Connection Issues](connection-issues.md#file-watcher-issues), [AI Issues](ai-issues.md)

---

## Risk Gauge Stuck at 0

### What You See

- Dashboard risk gauge shows 0 or minimal value
- Events exist but have null risk scores
- "Analyzing..." spinner never completes

### Quick Diagnosis

```bash
# Check recent events for risk scores
curl -s http://localhost:8000/api/events?limit=3 | jq '.items[].risk_score'

# Check Nemotron health
curl -s http://localhost:8091/health
```

### Possible Causes

1. **Nemotron service not running** - Most common cause
2. **Nemotron timeout** - Model too slow or overloaded
3. **LLM response parsing failure** - Invalid JSON from model

### Solutions

**1. Start Nemotron if not running:**

```bash
./ai/start_llm.sh
# Or if containerized:
docker compose -f docker-compose.prod.yml up -d ai-llm
```

**2. Check Nemotron logs:**

```bash
docker compose -f docker-compose.prod.yml logs -f ai-llm
# Host-run ./ai/start_nemotron.sh writes /tmp/nemotron.log;
# ./ai/start_llm.sh logs to its terminal
```

**3. Increase timeout if needed:**

```bash
# In .env
NEMOTRON_READ_TIMEOUT=300.0  # Default is 120s
```

**4. Test Nemotron directly:**

```bash
curl -X POST http://localhost:8091/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Say hello", "max_tokens": 20}'
```

See: [AI Issues - Analysis Failing](ai-issues.md#analysis-failing)

---

## Camera Shows Offline

### What You See

- Camera status indicator shows offline/error
- No new detections from specific camera
- last_seen_at timestamp is stale

### Quick Diagnosis

```bash
# Check camera status in database
curl -s http://localhost:8000/api/cameras | jq '.items[] | {id, name, status, last_seen_at}'

# Check if images exist in camera folder
ls -lt /export/foscam/<camera_name>/ | head -5
```

### Possible Causes

1. **Camera not FTP uploading** - Network or camera config issue
2. **Wrong folder path** - Camera registered with incorrect path
3. **File permissions** - Backend cannot read camera folder
4. **Camera hardware issue** - Camera offline or rebooting

### Solutions

**1. Verify camera is uploading:**

```bash
# Watch for new files
watch -n 5 'ls -lt /export/foscam/<camera_name>/ | head -3'
```

**2. Check folder path in camera settings:**

```bash
curl -s http://localhost:8000/api/cameras | jq '.items[] | {id, name, folder_path}'
```

**3. Fix permissions:**

```bash
sudo chmod -R 755 /export/foscam/
```

**4. Check FTP server status:**

```bash
systemctl status vsftpd  # If using vsftpd
```

See: [Connection Issues - File Watcher](connection-issues.md#file-watcher-issues)

---

## AI Not Working

### What You See

- Health check shows AI services as unhealthy
- Error: "YOLO26 service connection refused"
- Error: "Nemotron service connection refused"
- No detections being created

### Quick Diagnosis

```bash
# Overall AI status
curl -s http://localhost:8000/api/system/health | jq '.services.ai'

# Individual service checks (production topology: Triton gateway + LLM container)
curl http://localhost:8090/yolo26/health  # Should return {"status": "healthy", ...}
curl http://localhost:8091/health         # Should return {"status": "ok"}
```

### Possible Causes (Most Likely First)

1. **AI containers not running** - `ai-gateway` and `ai-llm` start with the stack
2. **Port conflicts** - Something else using 8090/8091
3. **GPU not available** - CUDA not initialized (see [Triton Rootless CUDA](triton-rootless-cuda.md) under rootless Podman)
4. **Model files missing** - Models not downloaded

### Solutions

**1. Start AI services:**

```bash
# Production (containers)
docker compose -f docker-compose.prod.yml up -d ai-gateway ai-llm

# Host-run development (no unified wrapper script exists)
./ai/start_detector.sh  # Standalone YOLO26 server (PORT default 8090)
./ai/start_llm.sh       # Host-run Nemotron dev LLM on 8091
```

**2. Check for port conflicts:**

```bash
lsof -i :8090  # AI gateway port (8095 if using YOLO26_PORT from .env)
lsof -i :8091  # Nemotron port
```

**3. Verify CUDA:**

```bash
python3 -c "import torch; print(torch.cuda.is_available())"
```

**4. Download models if missing:**

```bash
./ai/download_models.sh
# Nemotron lands in ${AI_MODELS_PATH:-/export/ai_models}/nemotron/nemotron-3-nano-30b-a3b-q4km/
# (Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf, ~14.7GB); the rest go to model-zoo/
```

**5. Check AI service logs:**

```bash
docker compose -f docker-compose.prod.yml logs --tail=100 ai-gateway ai-llm
# Host-run: start_nemotron.sh writes /tmp/nemotron.log; start_detector.sh/start_llm.sh
# log to their terminal
```

See: [AI Issues](ai-issues.md), [GPU Issues](gpu-issues.md)

---

## WebSocket Disconnected

### What You See

- Dashboard shows "Disconnected" status
- Real-time updates stop working
- Events appear in timeline but feed not updating
- Browser console shows WebSocket errors

### Quick Diagnosis

```bash
# Test WebSocket endpoint
websocat ws://localhost:8000/ws/events

# Check backend is responding
curl http://localhost:8000/api/system/health
```

### Possible Causes

1. **Backend not running** - Container down
2. **Proxy/firewall issues** - WebSocket blocked
3. **Idle timeout** - Connection closed due to inactivity
4. **Rate limiting** - Too many reconnection attempts

### Solutions

**1. Restart backend:**

```bash
docker compose -f docker-compose.prod.yml restart backend
```

**2. Check backend logs:**

```bash
docker compose -f docker-compose.prod.yml logs -f backend | grep -i websocket
```

**3. Adjust idle timeout:**

```bash
# In .env
WEBSOCKET_IDLE_TIMEOUT_SECONDS=600  # Increase from default 300
```

**4. Check live WebSocket connections:**

```bash
curl -s http://localhost:8000/api/system/health/websocket | jq
```

**5. Clear browser cache and reload**

See: [Connection Issues - WebSocket](connection-issues.md#websocket-issues)

---

## High CPU/Memory Usage

### What You See

- System becomes slow or unresponsive
- Container restarts due to OOM
- Backend logs show high latency

### Quick Diagnosis

```bash
# Container resource usage
docker stats

# Queue backlogs
curl -s http://localhost:8000/api/system/telemetry | jq '.queues'

# DLQ size
curl -s http://localhost:8000/api/dlq/stats
```

### Possible Causes

1. **Queue backlog** - Images piling up faster than processed
2. **Too many cameras** - Overloading the system
3. **Memory leak** - Long-running process issue
4. **Insufficient resources** - Container limits too low

### Solutions

**1. Check and clear queues if backed up:**

```bash
# View queue sizes (Redis Streams mode is the default — USE_REDIS_STREAMS=true)
redis-cli xlen detections:stream
redis-cli xlen analysis:stream

# If severely backed up, you may need to clear
# CAUTION: This loses queued jobs (with consumer groups, delete/recreate the group too)
redis-cli del detections:stream
```

**2. Increase container memory limits:**

```yaml
# In docker-compose.prod.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

**3. Reduce camera throughput:**

- Increase camera upload interval
- Reduce number of active cameras

**4. Restart services:**

```bash
docker compose -f docker-compose.prod.yml restart
```

---

## Disk Space Running Out

### What You See

- Error: "No space left on device"
- Database operations fail
- Thumbnail generation fails

### Quick Diagnosis

```bash
# Check disk usage
df -h

# Check storage stats
curl -s http://localhost:8000/api/system/storage | jq .

# Database size
psql -h localhost -U security -d security -c "SELECT pg_size_pretty(pg_database_size('security'));"
```

### Possible Causes

1. **Retention too long** - Default 30 days may be too much
2. **Cleanup not running** - Scheduled cleanup failing
3. **Thumbnails accumulating** - Largest storage consumer
4. **Camera images not cleaned** - Original images retained

### Solutions

**1. Run immediate cleanup:**

```bash
# Preview first
curl -s -X POST "http://localhost:8000/api/system/cleanup?dry_run=true" | jq .

# Execute cleanup
curl -X POST http://localhost:8000/api/system/cleanup
```

**2. Reduce retention period:**

```bash
# In .env
RETENTION_DAYS=14      # Reduce from default 30
LOG_RETENTION_DAYS=3   # Reduce from default 7
```

**3. Vacuum PostgreSQL:**

```bash
psql -h localhost -U security -d security -c "VACUUM FULL;"
```

**4. Enable image deletion (if you have backups):**
Configure `delete_images=True` in cleanup service

See: [Database Issues - Disk Space](database-issues.md#disk-space)

---

## Slow AI Inference

### What You See

- Detection takes >100ms (expected: 5-20ms per frame via the gateway's TensorRT engines — see [YOLO26 performance](../benchmarks/yolo26-performance.md))
- LLM responses take >30s (expected: 2-5s)
- Queue backlogs growing

### Quick Diagnosis

```bash
# Check GPU utilization
nvidia-smi

# Check the gateway reports models ready
curl -s http://localhost:8090/health | jq

# Check pipeline latency
curl -s http://localhost:8000/api/system/pipeline-latency | jq .
```

### Possible Causes

1. **Running on CPU instead of GPU** - Most common
2. **GPU thermal throttling** - Temperature too high
3. **VRAM exhausted** - Too many models loaded
4. **Other GPU processes** - Competing for resources

### Solutions

**1. Verify GPU is being used:**

```bash
# tritonserver and llama-server should hold GPU memory
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv

# A host-run standalone detector reports its device directly
curl -s http://localhost:8095/health | jq '.device'  # "cuda:0" or "cpu"
```

**2. Check temperature:**

```bash
nvidia-smi  # Temperature should be < 85C
```

**3. Free GPU memory:**

```bash
# Restart the AI stack (drops loaded models and re-initialises CUDA)
docker compose -f docker-compose.prod.yml restart ai-gateway ai-llm
```

See: [GPU Issues](gpu-issues.md)

---

## CORS Errors in Browser

### What You See

- Browser console: "CORS policy blocked"
- API calls work in curl but fail in browser
- Dashboard shows errors loading data

### Quick Diagnosis

```bash
# Test CORS headers (origin = whatever the browser actually reports, e.g. the Vite dev server)
curl -v -X OPTIONS -H "Origin: https://localhost:8444" \
  http://localhost:8000/api/events 2>&1 | grep -i "access-control"
```

### Solutions

**1. Update CORS_ORIGINS in .env** (default ships `https://localhost:8444` and internal `http://frontend:8080`):

```bash
CORS_ORIGINS=["https://localhost:8444", "https://192.168.1.20:8444", "https://your-domain.com"]
```

**2. Restart backend after changes:**

```bash
docker compose -f docker-compose.prod.yml restart backend
```

See: [Connection Issues - CORS](connection-issues.md#cors-errors)

---

## Emergency Procedures

### System Won't Start At All

**Symptoms:** All services fail to start, immediate crashes

**Steps:**

1. Check Docker is running: `docker info`
2. Check for conflicting containers: `docker ps -a`
3. Remove stuck containers: `docker compose -f docker-compose.prod.yml down -v`
4. Check environment file: `cat .env`
5. Rebuild if needed: `docker compose -f docker-compose.prod.yml build --no-cache`
6. Start with verbose logs: `docker compose -f docker-compose.prod.yml up`

### Database Corruption Suspected

**Symptoms:** SQL errors, missing data, inconsistent state

**Steps:**

1. Stop all services: `docker compose -f docker-compose.prod.yml down`
2. Create backup: `pg_dump -h localhost -U security security > backup_emergency.sql`
3. Check for issues: `psql -h localhost -U security -d security -c "\dt"`
4. If corrupted, restore from backup
5. As last resort, recreate the database (this project has no Alembic — the schema
   is created directly from the SQLAlchemy models on next backend start):
   ```bash
   dropdb -h localhost -U postgres security
   createdb -h localhost -U postgres -O security security
   docker compose -f docker-compose.prod.yml up -d backend   # init_db creates the schema
   ```

### Complete Data Loss Recovery

**Symptoms:** Database empty, no events, no history

**Steps:**

1. Check if data exists but service cannot connect
2. Check Docker volumes: `docker volume ls`
3. Restore from backup if available:
   ```bash
   psql -h localhost -U security security < backup.sql
   ```
4. If no backup, the system will start fresh when cameras resume uploading

### Security Breach Suspected

**Symptoms:** Unauthorized access, unknown API activity, modified settings

**Steps:**

1. Immediately stop external access
2. Check for rejected requests — with `API_KEY_ENABLED=true`, calls without a valid
   `X-API-Key` header are refused with `401` and show up in the backend logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs backend | grep -iE "401|unauthorized"
   ```
3. Review logs for suspicious activity:
   ```bash
   grep -i "unauthorized\|forbidden\|invalid" backend/data/logs/security.log
   ```
4. Rotate API keys if used
5. Review CORS origins and network exposure
6. Consider enabling `API_KEY_ENABLED=true` if not already

---

## Information to Gather for Bug Reports

If you need to report an issue, collect this information:

```bash
# 1. System health summary
curl -s http://localhost:8000/api/system/health | jq . > health.json

# 2. System configuration (REDACT PASSWORDS)
curl -s http://localhost:8000/api/system/config | jq . > config.json

# 3. Recent backend logs
docker compose -f docker-compose.prod.yml logs --tail=200 backend > backend.log

# 4. GPU information
nvidia-smi > gpu.txt

# 5. Container status
docker compose -f docker-compose.prod.yml ps -a > containers.txt

# 6. Queue status
curl -s http://localhost:8000/api/system/telemetry | jq . > telemetry.json

# 7. Environment (REDACT SENSITIVE VALUES)
cat .env | grep -v PASSWORD | grep -v SECRET | grep -v KEY > env_safe.txt
```

---

## Troubleshooting Detailed Guides

- [GPU Issues](gpu-issues.md) - CUDA, VRAM, temperature, container GPU access
- [Triton Rootless CUDA](triton-rootless-cuda.md) - ai-gateway cudaGetDeviceCount err=3 in rootless Podman
- [Connection Issues](connection-issues.md) - Network, containers, WebSocket, CORS
- [AI Issues](ai-issues.md) - YOLO26, Nemotron, pipeline, batch processing
- [Database Issues](database-issues.md) - PostgreSQL connection, migrations, disk space

---

## Getting Help

If you can't resolve an issue:

1. **Check this index first** - Most common problems are covered
2. **Review specific troubleshooting pages** - Detailed solutions for each area
3. **Search [GitHub Issues](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/issues)** - Someone may have solved it
4. **Open a new issue** with:
   - Clear description of the problem
   - Steps to reproduce
   - Information gathered (see above)
   - What you've already tried

---

## See Also

- [AI Troubleshooting (Operator)](../../operator/ai-troubleshooting.md) - Quick AI fixes
- [GPU Setup](../../operator/gpu-setup.md) - GPU configuration guide
- [Environment Variable Reference](../config/env-reference.md) - Configuration options
- [Glossary](../glossary.md) - Terms and definitions

---

[Back to Operator Hub](../../operator/README.md) | [User Hub](../../user/README.md)
