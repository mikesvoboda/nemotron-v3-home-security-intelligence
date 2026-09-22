# Troubleshooting Hub

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

## Fast Triage Flow (Health -> Fix)

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

## Detailed Troubleshooting Guides

| Guide                                           | Covers                                                |
| ----------------------------------------------- | ----------------------------------------------------- |
| [AI Issues](ai-issues.md)                       | YOLO26, Nemotron, pipeline, batch processing          |
| [Connection Issues](connection-issues.md)       | Network, containers, WebSocket, CORS, file watcher    |
| [Database Issues](database-issues.md)           | PostgreSQL connection, schema, disk space             |
| [GPU Issues](gpu-issues.md)                     | CUDA, VRAM, temperature, container GPU access         |
| [Triton Rootless CUDA](triton-rootless-cuda.md) | Gateway `cudaGetDeviceCount err=3` in rootless Podman |

---

## Log Locations

| Service     | Docker Command                                                     | Native Path                                                                                                                                 |
| ----------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend     | `docker compose -f docker-compose.prod.yml logs backend`           | `backend/data/logs/security.log`                                                                                                            |
| Frontend    | `docker compose -f docker-compose.prod.yml logs frontend`          | Browser console (F12)                                                                                                                       |
| PostgreSQL  | `docker compose -f docker-compose.prod.yml logs postgres`          | Container `/var/lib/postgresql/data/log`                                                                                                    |
| Redis       | `docker compose -f docker-compose.prod.yml logs redis`             | Container logs only                                                                                                                         |
| AI Services | `docker compose -f docker-compose.prod.yml logs ai-gateway ai-llm` | Container stdout; host-run `ai/start_nemotron.sh` logs to `/tmp/nemotron.log`, `ai/start_llm.sh`/`ai/start_detector.sh` log to the terminal |

---

## Common Issues and Solutions

### Dashboard Shows No Events

**What You See:**

- Empty activity feed
- No recent events in timeline
- Risk gauge may be at 0 or stale

**Quick Diagnosis:**

```bash
# Check if events exist in database
curl -s http://localhost:8000/api/events?limit=5 | jq '.pagination.total'

# Check pipeline status
curl -s http://localhost:8000/api/system/pipeline | jq .
```

**Possible Causes (Most Likely First):**

1. **File watcher not running** - Images not being picked up
2. **AI services not running** - Detections not being created
3. **No images uploaded** - Cameras not sending images
4. **Batch not completing** - Detections queued but not analyzed

**Solutions:**

1. Check file watcher status:

   ```bash
   curl -s http://localhost:8000/api/system/health/ready | jq '.workers[] | select(.name | test("file_watcher|detection"))'
   ```

   If not running, restart backend: `docker compose -f docker-compose.prod.yml restart backend`

2. Verify images are being uploaded:

   ```bash
   ls -lt /export/foscam/*/  # Should show recent files
   ```

3. Check AI service health:

   ```bash
   curl http://localhost:8090/yolo26/health  # YOLO26 (AI gateway router)
   curl http://localhost:8091/health         # Nemotron
   ```

4. Check queue depths:
   ```bash
   curl -s http://localhost:8000/api/system/telemetry | jq '.queues'
   ```

See: [Connection Issues](connection-issues.md#file-watcher-issues), [AI Issues](ai-issues.md)

---

### Camera Shows Offline

**What You See:**

- Camera status indicator shows offline/error
- No new detections from specific camera
- last_seen_at timestamp is stale

**Quick Diagnosis:**

```bash
# Check camera status in database
curl -s http://localhost:8000/api/cameras | jq '.items[] | {id, name, status, last_seen_at}'

# Check if images exist in camera folder
ls -lt /export/foscam/<camera_name>/ | head -5
```

**Solutions:**

1. Verify camera is uploading:

   ```bash
   watch -n 5 'ls -lt /export/foscam/<camera_name>/ | head -3'
   ```

2. Check folder path in camera settings:

   ```bash
   curl -s http://localhost:8000/api/cameras | jq '.items[] | {id, name, folder_path}'
   ```

3. Fix permissions:
   ```bash
   sudo chmod -R 755 /export/foscam/
   ```

See: [Connection Issues - File Watcher](connection-issues.md#file-watcher-issues)

---

### AI Not Working

**What You See:**

- Health check shows AI services as unhealthy
- Error: "YOLO26 service connection refused"
- Error: "Nemotron service connection refused"
- No detections being created

**Quick Diagnosis:**

```bash
# Overall AI status
curl -s http://localhost:8000/api/system/health | jq '.services.ai'

# Individual service checks
curl http://localhost:8090/yolo26/health  # YOLO26 via AI gateway; {"status": "healthy", ...}
curl http://localhost:8091/health         # Nemotron; {"status": "ok"}
```

**Solutions:**

1. Start AI services. In production both run as containers (`ai-gateway` on :8090, `ai-llm` on :8091) and start with the stack:

   ```bash
   docker compose -f docker-compose.prod.yml up -d ai-gateway ai-llm
   # Host-run development instead (no unified wrapper script exists):
   ./ai/start_detector.sh  # YOLO26 (defaults to :8090, or :8095 via .env's YOLO26_PORT)
   ./ai/start_llm.sh       # Nemotron dev server on :8091
   ```

2. Check for port conflicts:

   ```bash
   lsof -i :8090  # AI gateway port (or :8095 if host-run YOLO26 uses .env's YOLO26_PORT)
   lsof -i :8091  # Nemotron port
   ```

3. Verify CUDA:

   ```bash
   python3 -c "import torch; print(torch.cuda.is_available())"
   ```

4. Check AI service logs:
   ```bash
   # Containers (production):
   docker compose -f docker-compose.prod.yml logs --tail=100 ai-gateway
   docker compose -f docker-compose.prod.yml logs --tail=100 ai-llm
   # Host-run dev: start_detector.sh / start_llm.sh log to their terminal;
   # start_nemotron.sh writes /tmp/nemotron.log
   tail -f /tmp/nemotron.log
   ```

See: [AI Issues](ai-issues.md), [GPU Issues](gpu-issues.md)

---

### WebSocket Disconnected

**What You See:**

- Dashboard shows "Disconnected" status
- Real-time updates stop working
- Browser console shows WebSocket errors

**Quick Diagnosis:**

```bash
# Test WebSocket endpoint
websocat ws://localhost:8000/ws/events

# Check backend is responding
curl http://localhost:8000/api/system/health
```

**Solutions:**

1. Restart backend:

   ```bash
   docker compose -f docker-compose.prod.yml restart backend
   ```

2. Check backend logs:

   ```bash
   docker compose -f docker-compose.prod.yml logs -f backend | grep -i websocket
   ```

3. Adjust idle timeout:
   ```bash
   # In .env
   WEBSOCKET_IDLE_TIMEOUT_SECONDS=600  # Increase from default 300
   ```

See: [Connection Issues - WebSocket](connection-issues.md#websocket-issues)

---

### High CPU/Memory Usage

**What You See:**

- System becomes slow or unresponsive
- Container restarts due to OOM
- Backend logs show high latency

**Quick Diagnosis:**

```bash
# Container resource usage
docker stats

# Queue backlogs
curl -s http://localhost:8000/api/system/telemetry | jq '.queues'

# DLQ size
curl -s http://localhost:8000/api/dlq/stats
```

**Solutions:**

1. Check and clear queues if backed up:

   ```bash
   # View queue sizes (streams mode is the default — see USE_REDIS_STREAMS in .env.example)
   redis-cli xlen detections:stream
   redis-cli xlen analysis:stream
   ```

2. Increase container memory limits in docker-compose.prod.yml

3. Restart services:
   ```bash
   docker compose -f docker-compose.prod.yml restart
   ```

---

### Disk Space Running Out

**What You See:**

- Error: "No space left on device"
- Database operations fail
- Thumbnail generation fails

**Quick Diagnosis:**

```bash
# Check disk usage
df -h

# Check storage stats
curl -s http://localhost:8000/api/system/storage | jq .
```

**Solutions:**

1. Run immediate cleanup:

   ```bash
   curl -X POST http://localhost:8000/api/system/cleanup
   ```

2. Reduce retention period:

   ```bash
   # In .env
   RETENTION_DAYS=14      # Reduce from default 30
   LOG_RETENTION_DAYS=3   # Reduce from default 7
   ```

3. Vacuum PostgreSQL:
   ```bash
   psql -h localhost -U security -d security -c "VACUUM FULL;"
   ```

See: [Database Issues - Disk Space](database-issues.md#disk-space)

---

### Slow AI Inference

**What You See:**

- Detection takes >100ms (expected: 30-50ms)
- LLM responses take >30s (expected: 2-5s)
- Queue backlogs growing

**Quick Diagnosis:**

```bash
# Check GPU utilization
nvidia-smi

# Check the gateway reports its models ready
curl -s http://localhost:8090/health | jq
curl -s http://localhost:8090/yolo26/health | jq

# Host-run standalone YOLO26 server reports its device directly
curl -s http://localhost:8095/health | jq '.device'
```

**Solutions:**

1. Verify the GPU is in use: `nvidia-smi` should list the gateway (`tritonserver`) and `llama-server` processes with non-zero memory. A standalone host-run detector reports `"device": "cuda:0"` from `/health`.

2. Check temperature:

   ```bash
   nvidia-smi  # Temperature should be < 85C
   ```

3. Restart AI services:
   ```bash
   docker compose -f docker-compose.prod.yml restart ai-gateway ai-llm
   ```

See: [GPU Issues](gpu-issues.md)

---

### CORS Errors in Browser

**What You See:**

- Browser console: "CORS policy blocked"
- API calls work in curl but fail in browser
- Dashboard shows errors loading data

**Quick Diagnosis:**

```bash
curl -v -X OPTIONS -H "Origin: https://localhost:8444" \
  http://localhost:8000/api/events 2>&1 | grep -i "access-control"
```

**Solutions:**

1. Update CORS_ORIGINS in .env:

   ```bash
   CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173", "https://your-domain.com"]
   ```

2. Restart backend:
   ```bash
   docker compose -f docker-compose.prod.yml restart backend
   ```

---

## Database Issues

### Connection Refused

**Symptoms:**

- Backend logs: `connection refused` or `could not connect to server`
- API returns 503 errors

**Diagnosis:**

```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Test connection
pg_isready -h localhost -p 5432 -U security
```

**Solutions:**

1. Start PostgreSQL:

   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres
   ```

2. Check credentials:

   ```bash
   grep DATABASE_URL .env
   grep POSTGRES_PASSWORD .env
   ```

3. Check port conflicts:
   ```bash
   sudo lsof -i :5432
   ```

### Authentication Failed

**Symptoms:**

- `FATAL: password authentication failed for user "security"`

**Solutions:**

1. Reset password:

   ```bash
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "ALTER USER security WITH PASSWORD '<YOUR_PASSWORD>';"
   ```

2. Update DATABASE_URL in .env and restart backend

### Schema Out of Date

**Symptoms:**

- Backend fails to start with errors about missing tables or columns

**Reality check:** this project does **not** use Alembic — the schema is created directly from the SQLAlchemy models (`create_all` at backend startup). The alembic package is a dev-only dependency and `alembic upgrade head` has no migrations tree to run. See [Migrations](../../architecture/data-model/migrations.md).

**Diagnosis:**

```bash
docker compose -f docker-compose.prod.yml logs --tail=50 backend | grep -i "table\|schema"
```

**Solutions:**

New tables are created automatically on backend restart. For a dev database with a stale schema you can recreate it from the models (destructive — drops all tables, and it refuses to run against a production-looking URL without `--force`):

```bash
python -m backend.scripts.init_schema
```

See: [Database Issues](database-issues.md)

---

## Redis Issues

### Connection Refused

**Symptoms:**

- Backend logs: `ConnectionError: Error while reading from socket`
- Queue processing stops

**Diagnosis:**

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

**Solutions:**

```bash
docker compose -f docker-compose.prod.yml up -d redis
```

### Queue Backlog

**Symptoms:**

- Detections not processing
- High queue depths

**Diagnosis:**

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli XLEN detections:stream
docker compose -f docker-compose.prod.yml exec redis redis-cli XLEN analysis:stream
```

> Queues are Redis **Streams** by default (`USE_REDIS_STREAMS=true` in `.env.example`), keyed `detections:stream` and `analysis:stream`. `LLEN`/`DEL` on `detection_queue` only apply if streams were disabled and the legacy list queues are in use.

**Solutions:**

1. Check AI services are healthy
2. Restart AI services if needed
3. Clear a stuck stream (WARNING: loses pending work; with consumer groups, use `XTRIM detections:stream MAXLEN 0` or delete/recreate the group):
   ```bash
   docker compose -f docker-compose.prod.yml exec redis redis-cli DEL detections:stream
   ```

---

## GPU Issues

### GPU Not Detected

**Symptoms:**

- AI services fail to start
- Logs: `CUDA not available`

**Diagnosis:**

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

**Solutions:**

1. Install nvidia-container-toolkit:
   ```bash
   sudo apt install nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

### Out of VRAM

**Symptoms:**

- AI services crash with OOM errors
- `nvidia-smi` shows 100% memory usage

**Solutions:**

1. Reduce Nemotron GPU layers (default is `auto`, which fits the model to available VRAM):

   ```bash
   # In .env — a fixed layer count overrides auto-fit
   GPU_LAYERS=20
   ```

2. Free the rest of the GPU: Florence-2, CLIP and the enrichment models all run inside the single `ai-gateway` container (Triton, which loads every model in the zoo at startup), so there is no per-service container to stop — free VRAM by lowering `GPU_LAYERS` further, or stop the whole gateway:
   ```bash
   docker compose -f docker-compose.prod.yml stop ai-gateway
   ```

See: [GPU Issues](gpu-issues.md)

---

## Emergency Procedures

### System Won't Start At All

1. Check Docker is running: `docker info`
2. Check for conflicting containers: `docker ps -a`
3. Remove stuck containers: `docker compose -f docker-compose.prod.yml down -v`
4. Rebuild if needed: `docker compose -f docker-compose.prod.yml build --no-cache`
5. Start with verbose logs: `docker compose -f docker-compose.prod.yml up`

### Database Corruption Suspected

1. Stop all services: `docker compose -f docker-compose.prod.yml down`
2. Create backup: `pg_dump -h localhost -U security security > backup_emergency.sql`
3. Check for issues: `psql -h localhost -U security -d security -c "\dt"`
4. If corrupted, restore from backup

### Complete Data Loss Recovery

1. Check Docker volumes: `docker volume ls`
2. Restore from backup if available:
   ```bash
   psql -h localhost -U security security < backup.sql
   ```
3. If no backup, the system will start fresh when cameras resume uploading

---

## Collecting Diagnostics for Bug Reports

```bash
#!/bin/bash
OUTPUT_DIR="diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# System info
nvidia-smi > "$OUTPUT_DIR/nvidia-smi.txt"
df -h > "$OUTPUT_DIR/disk-usage.txt"
docker system df > "$OUTPUT_DIR/docker-disk.txt"

# Service status
docker compose -f docker-compose.prod.yml ps > "$OUTPUT_DIR/services-status.txt"
docker stats --no-stream > "$OUTPUT_DIR/resource-usage.txt"

# Logs
docker compose -f docker-compose.prod.yml logs --tail=500 > "$OUTPUT_DIR/all-logs.txt"

# API status
curl -s http://localhost:8000/api/system/health/ready > "$OUTPUT_DIR/backend-health.json"

tar -czf "$OUTPUT_DIR.tar.gz" "$OUTPUT_DIR"
echo "Diagnostics saved to $OUTPUT_DIR.tar.gz"
```

---

## Getting Help

If you can't resolve an issue:

1. **Check this index first** - Most common problems are covered
2. **Review specific troubleshooting pages** - Detailed solutions for each area
3. **Search [GitHub Issues](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/issues)** - Someone may have solved it
4. **Open a new issue** with:
   - Clear description of the problem
   - Steps to reproduce
   - Information gathered (see diagnostics script above)
   - What you've already tried

---

## See Also

- [Reference Hub](../) - Environment variables and configuration
- [AI Troubleshooting (Operator)](../../operator/ai-troubleshooting.md) - Quick AI fixes
- [GPU Setup](../../operator/gpu-setup.md) - GPU configuration guide
- [Environment Variable Reference](../config/env-reference.md) - Configuration options
- [Glossary](../glossary.md) - Terms and definitions

---

[Back to Reference Hub](../) | [Operator Hub](../../operator/README.md) | [User Hub](../../user/README.md)
