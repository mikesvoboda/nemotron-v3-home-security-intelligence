# Troubleshooting

---

title: Troubleshooting
source_refs:

- backend/core/config.py:Settings:12
- backend/services/health_monitor.py:ServiceHealthMonitor:25
- docs/reference/config/env-reference.md

---

> **Common issues and their solutions.** Quick reference for diagnosing and resolving problems with the Home Security Intelligence system.

<!-- Nano Banana Pro Prompt:
"Technical illustration of server troubleshooting and debugging,
error indicators and diagnostic tools, dark background #121212,
red #E74856 warning accents, green #76B900 success indicators,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

## Quick Diagnostic Commands

```bash
# System health check
curl http://localhost:8000/api/system/health

# AI services health
curl http://localhost:8090/health   # RT-DETRv2
curl http://localhost:8091/health   # Nemotron
curl http://localhost:8092/health   # Florence-2 (optional)
curl http://localhost:8093/health   # CLIP (optional)
curl http://localhost:8094/health   # Enrichment (optional)

# Database connectivity
psql -h localhost -U security -d security -c "SELECT 1;"

# Redis connectivity
redis-cli ping

# GPU status
nvidia-smi

# Container logs
podman-compose logs -f backend
podman-compose logs -f frontend
```

> For a fast “health → fix” flowchart, start with the [Troubleshooting Index](../reference/troubleshooting/index.md).

---

## AI Services

### AI Servers Won't Start

**Symptoms:**

- `Connection refused` when testing health endpoints
- Backend logs show AI service connection errors

**Solutions:**

1. **Verify CUDA is working:**

   ```bash
   nvidia-smi
   ```

   Should show GPU info and driver version.

2. **Check GPU memory:**

   - RT-DETRv2 needs ~4GB VRAM
   - Nemotron Mini 4B needs ~3GB VRAM
   - Close other GPU-using applications

3. **Verify models are downloaded:**

   ```bash
   ./ai/download_models.sh
   ls -la ai/nemotron/*.gguf
   # RT-DETRv2 models are typically fetched via HuggingFace cache on first use
   ```

4. **Check startup logs:**
   Review the terminal where you ran `./ai/start_detector.sh` or `./ai/start_llm.sh`

5. **Port conflicts:**
   ```bash
   lsof -i :8090  # RT-DETRv2
   lsof -i :8091  # Nemotron
   ```

---

### Backend Can't Reach AI Services

**Symptoms:**

- Dashboard shows AI services as unhealthy
- Detection pipeline not processing images

**Solutions:**

1. **Test from host:**

   ```bash
   curl http://localhost:8090/health
   curl http://localhost:8091/health
   ```

2. **Check Docker networking (if using Docker):**

   The correct URLs depend on your deployment mode (prod compose DNS vs host-run AI vs Docker Desktop host routing).

   Start here:

   - [Deployment Modes & AI Networking](../operator/deployment-modes.md) (decision table + copy/paste `.env` snippets)

3. **Verify environment variables:**
   ```bash
   # Check what backend sees
   curl http://localhost:8000/api/system/config | jq '.rtdetr_url, .nemotron_url, .florence_url, .clip_url, .enrichment_url'
   ```

---

### AI Inference Slow or Timing Out

**Symptoms:**

- Detection takes longer than expected
- Timeout errors in logs

**Solutions:**

1. **Check GPU utilization:**

   ```bash
   nvidia-smi -l 1  # Live updates every second
   ```

2. **Increase timeouts:**

   ```bash
   # .env
   RTDETR_READ_TIMEOUT=120.0   # Default: 60s
   NEMOTRON_READ_TIMEOUT=300.0 # Default: 120s
   ```

3. **Check for thermal throttling:**

   - GPU temperature should be < 85C
   - Improve case airflow if needed

4. **Reduce batch size or model precision:**
   - Check AI service configuration files

---

## Database

### Connection Errors

**Symptoms:**

- `Connection refused` or authentication errors
- Backend fails to start

**Solutions:**

1. **Verify PostgreSQL is running:**

   ```bash
   # Docker
   podman-compose ps | grep postgres

   # Native
   pg_isready -h localhost -p 5432
   ```

2. **Check connection URL format:**

   ```bash
   # Correct format
   DATABASE_URL=postgresql+asyncpg://username:password@host:port/database

   # Native development
   DATABASE_URL=postgresql+asyncpg://security:your_password@localhost:5432/security

   # Docker
   DATABASE_URL=postgresql+asyncpg://security:your_password@postgres:5432/security
   ```

3. **Test direct connection:**

   ```bash
   psql -h localhost -U security -d security
   ```

4. **Check database exists:**

   ```bash
   psql -h localhost -U postgres -c "\\l" | grep security
   ```

5. **Create database if missing:**
   ```bash
   createdb -h localhost -U postgres security
   ```

---

### Migration Errors

**Symptoms:**

- Schema mismatch errors
- Missing columns or tables

**Solutions:**

1. **Run migrations:**

   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Check migration status:**

   ```bash
   alembic current
   alembic history
   ```

3. **Reset database (development only):**
   ```bash
   # WARNING: Destroys all data
   dropdb -h localhost -U postgres security
   createdb -h localhost -U postgres security
   alembic upgrade head
   ```

---

## Redis

### Connection Errors

**Symptoms:**

- `Connection refused` to Redis
- Queue operations failing

**Solutions:**

1. **Verify Redis is running:**

   ```bash
   # Docker
   podman-compose ps | grep redis

   # Native
   redis-cli ping
   ```

2. **Check connection URL:**

   ```bash
   # Native
   REDIS_URL=redis://localhost:6379/0

   # Docker
   REDIS_URL=redis://redis:6379
   ```

3. **Test connectivity:**
   ```bash
   redis-cli -u redis://localhost:6379/0 ping
   ```

---

### Queue Backlog Growing

**Symptoms:**

- DLQ jobs accumulating
- Processing delays

**Solutions:**

1. **Check DLQ status:**

   ```bash
   curl http://localhost:8000/api/dlq/stats
   ```

2. **Verify AI services are healthy:**

   ```bash
   curl http://localhost:8000/api/system/health
   ```

3. **Check queue sizes:**

   ```bash
   redis-cli -u redis://localhost:6379/0 llen detection_queue
   redis-cli -u redis://localhost:6379/0 llen analysis_queue
   ```

4. **Increase queue limits if needed:**
   ```bash
   QUEUE_MAX_SIZE=20000  # Default: 10000
   ```

---

## WebSocket

### WebSocket Won't Connect

**Symptoms:**

- Dashboard shows "Disconnected"
- Real-time updates not working

**Solutions:**

1. **Verify backend is running:**

   ```bash
   curl http://localhost:8000/api/system/health
   ```

2. **Check browser console for errors:**

   - Open Developer Tools (F12)
   - Look for WebSocket connection errors in Console tab

3. **Verify CORS configuration:**

   ```bash
   # .env - ensure your frontend URL is included
   CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
   ```

4. **Check Vite proxy configuration (development):**

   ```typescript
   // vite.config.ts
   proxy: {
     '/ws': {
       target: 'ws://localhost:8000',
       ws: true
     }
   }
   ```

5. **Test WebSocket directly:**
   ```javascript
   // Browser console
   ws = new WebSocket('ws://localhost:8000/ws/events');
   ws.onopen = () => console.log('Connected');
   ws.onerror = (e) => console.error('Error', e);
   ```

---

### WebSocket Disconnects Frequently

**Symptoms:**

- Connection drops and reconnects
- "Disconnected" message appears intermittently

**Solutions:**

1. **Check idle timeout:**

   ```bash
   # Increase if needed (default: 300s)
   WEBSOCKET_IDLE_TIMEOUT_SECONDS=600
   ```

2. **Verify ping interval:**

   ```bash
   # Default: 30s - should be less than idle timeout
   WEBSOCKET_PING_INTERVAL_SECONDS=30
   ```

3. **Check for network issues:**
   - Proxy timeouts
   - Firewall interference
   - Load balancer settings

---

## File Watcher

### Images Not Being Processed

**Symptoms:**

- Camera uploads new images but no detections appear
- FileWatcher logs show no activity

**Solutions:**

1. **Verify camera directory exists:**

   ```bash
   ls -la /export/foscam/
   ```

2. **Check directory permissions:**

   ```bash
   # Backend process must be able to read
   sudo chmod -R 755 /export/foscam/
   ```

3. **Test file detection:**

   ```bash
   # Create test file
   touch /export/foscam/test_camera/test.jpg
   # Check backend logs for detection
   ```

4. **Enable polling mode (Docker Desktop):**
   ```bash
   FILE_WATCHER_POLLING=true
   FILE_WATCHER_POLLING_INTERVAL=1.0
   ```

---

### Duplicate Detection Errors

**Symptoms:**

- Same image processed multiple times
- Deduplication warnings in logs

**Solutions:**

1. **Increase dedupe TTL:**

   ```bash
   DEDUPE_TTL_SECONDS=600  # Default: 300
   ```

2. **Check Redis connectivity** (dedupe uses Redis)

3. **Verify file naming is unique:**
   - Cameras should use unique filenames
   - Include timestamps in filenames

---

## Frontend

### Dashboard Not Loading

**Symptoms:**

- Blank page or loading spinner
- JavaScript errors in console

**Solutions:**

1. **Check frontend is running:**

   ```bash
   # Development
   curl http://localhost:5173

   # Production
   curl http://localhost
   ```

2. **Verify API URL configuration:**

   ```bash
   # Must be accessible from browser
   VITE_API_BASE_URL=http://localhost:8000
   VITE_WS_BASE_URL=ws://localhost:8000
   ```

3. **Rebuild frontend (if env vars changed):**

   ```bash
   cd frontend
   npm run build
   ```

4. **Check browser console for errors**

---

### API Calls Failing

**Symptoms:**

- Network errors in browser console
- CORS errors

**Solutions:**

1. **Verify CORS origins:**

   ```bash
   # Must include frontend URL
   CORS_ORIGINS=["http://localhost:5173", "http://your-domain.com"]
   ```

2. **Check API is reachable:**

   ```bash
   curl http://localhost:8000/api/system/health
   ```

3. **Verify protocol matches:**
   - HTTP frontend -> HTTP API
   - HTTPS frontend -> HTTPS API (with proper TLS config)

---

## Container Issues

### Container Won't Start

**Symptoms:**

- `podman-compose up` fails
- Container exits immediately

**Solutions:**

1. **Check container logs:**

   ```bash
   podman-compose logs backend
   podman-compose logs frontend
   ```

2. **Verify environment file:**

   ```bash
   # Ensure .env exists and is valid
   cat .env
   ```

3. **Check port conflicts:**

   ```bash
   lsof -i :8000  # Backend
   lsof -i :5173  # Frontend (dev)
   lsof -i :80    # Frontend (prod)
   ```

4. **Rebuild containers:**
   ```bash
   podman-compose down
   podman-compose build --no-cache
   podman-compose up
   ```

---

### Volume Mount Issues

**Symptoms:**

- Files not visible inside container
- Permission denied errors

**Solutions:**

1. **Check volume configuration:**

   ```yaml
   # docker-compose.yml
   volumes:
     - /export/foscam:/cameras:ro
     - ./data:/app/data:rw
   ```

2. **Fix permissions (Linux):**

   ```bash
   sudo chown -R 1000:1000 /export/foscam
   ```

3. **Enable polling for macOS/Windows:**
   ```bash
   FILE_WATCHER_POLLING=true
   ```

---

## Environment Variables

### Variables Not Taking Effect

**Symptoms:**

- Configuration changes don't apply
- Old values persist

**Solutions:**

1. **Restart services:**

   ```bash
   podman-compose down
   podman-compose up -d
   ```

2. **Check loading order:**

   - `.env` (base)
   - `data/runtime.env` (overrides)
   - Environment variables (highest priority)

3. **Verify variable is set:**

   ```bash
   # In container (Docker or Podman)
   docker exec backend printenv | grep YOUR_VAR
   # OR
   podman exec backend printenv | grep YOUR_VAR
   ```

4. **Clear settings cache:**

   ```bash
   # Backend caches settings on startup
   # Restart required for changes
   ```

5. **Rebuild frontend (for VITE\_ vars):**
   ```bash
   # VITE_ vars are embedded at build time
   cd frontend && npm run build
   ```

---

## Logs and Debugging

### Enable Debug Logging

```bash
# .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### View Logs

```bash
# Application logs
tail -f data/logs/security.log

# Container logs
podman-compose logs -f backend

# Database logs
podman-compose logs -f postgres
```

### Structured Log Analysis

```bash
# Find errors
grep "ERROR" data/logs/security.log | tail -20

# Find specific service issues
grep "rtdetr" data/logs/security.log | tail -20

# Find cleanup activity
grep "Cleanup" data/logs/security.log
```

---

## Getting Help

### Collect Diagnostic Info

When reporting issues, include:

1. **System health:**

   ```bash
   curl http://localhost:8000/api/system/health | jq
   ```

2. **Configuration (redact passwords):**

   ```bash
   curl http://localhost:8000/api/system/config | jq
   ```

3. **Recent logs:**

   ```bash
   tail -100 data/logs/security.log
   ```

4. **GPU info:**

   ```bash
   nvidia-smi
   ```

5. **Container status:**
   ```bash
   podman-compose ps
   ```

---

## See Also

- [Configuration](configuration.md) - All configuration options
- [Monitoring](monitoring.md) - Health checks and diagnostics
- [Security](security.md) - Security hardening
- [Storage and Retention](storage-retention.md) - Disk management

---

Back to [Operator Hub](../operator/README.md) | [User Hub](../user/README.md) | [Developer Hub](../developer/README.md)
