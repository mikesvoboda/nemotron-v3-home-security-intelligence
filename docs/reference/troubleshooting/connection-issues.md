# Connection Troubleshooting

> Solving network, container, and connectivity problems.

**Time to read:** ~6 min
**Prerequisites:** None

---

## Service Not Reachable

### Symptoms

- Error: `Connection refused`
- Health check fails
- `curl` returns "connection refused"

### Diagnosis

```bash
# Check if service is listening
ss -tlnp | grep 8000   # Backend
ss -tlnp | grep 8090   # YOLO26
ss -tlnp | grep 8091   # Nemotron
ss -tlnp | grep 8092   # Florence-2 (optional)
ss -tlnp | grep 8093   # CLIP (optional)
ss -tlnp | grep 8094   # Enrichment (optional)

# Check container status
docker compose -f docker-compose.prod.yml ps

# Check container logs
docker compose -f docker-compose.prod.yml logs backend
```

### Solutions

**1. Start the service:**

```bash
# All services
docker compose -f docker-compose.prod.yml up -d

# AI services only
./scripts/start-ai.sh start
```

**2. Check port conflicts:**

```bash
# Find what's using the port
sudo lsof -i :8000

# Kill conflicting process
sudo kill <PID>
```

**3. Verify network configuration:**

For Docker:

- Services on same network can use service names (`postgres`, `redis`)
- External access uses `localhost:PORT`

For production compose, AI services are reachable from the backend by compose DNS:

- `ai-yolo26:8095`
- `ai-llm:8091`
- `ai-florence:8092` (optional)
- `ai-clip:8093` (optional)
- `ai-enrichment:8094` (optional)

For native development:

- All services use `localhost`
- Verify each service is bound to correct address

---

## Redis Not Available

### Symptoms

- Error: `Connection refused` to Redis
- Health check shows Redis unhealthy
- Queue operations fail

### Diagnosis

```bash
# Check Redis is running
docker compose -f docker-compose.prod.yml ps redis

# Test Redis connection
redis-cli ping

# Check Redis logs
docker compose -f docker-compose.prod.yml logs redis
```

### Solutions

**1. Start Redis:**

```bash
docker compose -f docker-compose.prod.yml up -d redis
```

**2. Check REDIS_URL:**

```bash
# Local development
REDIS_URL=redis://localhost:6379/0

# Docker network
REDIS_URL=redis://redis:6379/0
```

**3. Check Redis memory:**

```bash
redis-cli info memory
```

If Redis is out of memory, increase `maxmemory` or clear old data.

---

## Container Crashes

### Symptoms

- Container exits immediately after starting
- Container in "restarting" state
- Exit code 1 or 137

### Diagnosis

```bash
# Check container status and exit codes
docker compose -f docker-compose.prod.yml ps -a

# Check container logs
docker compose -f docker-compose.prod.yml logs backend

# Check recent events
docker events --since="10m" --filter="type=container"
```

### Solutions

**Exit code 1 (application error):**

Check logs for:

- Missing environment variables
- Database connection failures
- Configuration errors

**Exit code 137 (OOM killed):**

```bash
# Check if OOM killed
dmesg | grep -i "killed process"

# Increase container memory limit
# In docker-compose.yml:
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

**Exit code 139 (segfault):**

Usually indicates:

- Incompatible library versions
- GPU driver issues
- Corrupted container image

Try: `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d`

---

## File Watcher Issues

### Symptoms

- Images uploaded but not processed
- No detections created from new images
- Pipeline status shows file watcher not running

### Diagnosis

```bash
# Check pipeline status
curl http://localhost:8000/api/system/pipeline | jq .file_watcher

# Check camera folder permissions
ls -la /export/foscam/

# Check for inotify limits (Linux)
cat /proc/sys/fs/inotify/max_user_watches
```

### Solutions

**1. Verify folder path:**

Ensure `FOSCAM_BASE_PATH` matches where cameras upload images.

**2. Enable polling for Docker:**

If using Docker Desktop on macOS/Windows:

```bash
FILE_WATCHER_POLLING=true
FILE_WATCHER_POLLING_INTERVAL=1.0
```

**3. Increase inotify watches (Linux):**

```bash
# Temporary
echo 524288 | sudo tee /proc/sys/fs/inotify/max_user_watches

# Permanent
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

**4. Check file permissions:**

Backend needs read access to camera folders.

---

## WebSocket Issues

### Symptoms

- Dashboard shows stale data
- "WebSocket connection failed"
- Frequent reconnections

### Diagnosis

```bash
# Test WebSocket connection
websocat ws://localhost:8000/ws/events

# Check for proxy issues
curl -v http://localhost:8000/ws/events

# Check WebSocket rate limiting
curl http://localhost:8000/api/system/telemetry
```

### Solutions

**1. Check idle timeout:**

Default is 300 seconds. Client should send periodic pings:

```javascript
setInterval(() => ws.send('{"type":"ping"}'), 30000);
```

**2. Check proxy configuration:**

If behind nginx/reverse proxy:

```nginx
location /ws/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

**3. Check rate limits:**

WebSocket connections limited to 10/minute by default. Adjust:

```bash
RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE=20
```

---

## CORS Errors

### Symptoms

- Browser console: "CORS policy blocked"
- API works in curl but not browser
- OPTIONS requests fail

### Diagnosis

```bash
# Check CORS headers
curl -v -X OPTIONS -H "Origin: http://localhost:3000" \
  http://localhost:8000/api/events
```

### Solutions

**1. Add origin to allowed list:**

```bash
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173", "https://your-domain.com"]
```

**2. For development, allow all (not for production):**

```bash
CORS_ORIGINS=["*"]
```

**3. Check frontend URLs:**

Ensure `VITE_API_BASE_URL` matches actual backend URL:

```bash
# Frontend expects backend at:
VITE_API_BASE_URL=http://localhost:8000

# Backend must allow this origin in CORS_ORIGINS
```

---

## Timeouts

### Symptoms

- Health checks timeout
- Requests hang then fail
- "Request timeout" errors

### Diagnosis

```bash
# Check service response time
time curl http://localhost:8000/health

# Check AI service response time
time curl http://localhost:8095/health
time curl http://localhost:8091/health
```

### Solutions

**1. Increase timeout settings:**

```bash
AI_CONNECT_TIMEOUT=30.0
AI_HEALTH_TIMEOUT=10.0
YOLO26_READ_TIMEOUT=120.0
NEMOTRON_READ_TIMEOUT=300.0
```

**2. Check service load:**

AI services may be overloaded. Check queue depths:

```bash
curl http://localhost:8000/api/system/telemetry | jq .queues
```

**3. Check network latency:**

If AI services are remote:

```bash
ping ai-server-hostname
```

---

## Next Steps

- [AI Issues](ai-issues.md) - AI service-specific problems
- [Database Issues](database-issues.md) - PostgreSQL problems
- [Troubleshooting Index](index.md) - Back to symptom index

---

## See Also

- [Environment Variable Reference](../config/env-reference.md) - Network configuration options
- [Local Setup](../../developer/local-setup.md) - Development environment setup
- [AI Services](../../operator/ai-services.md) - Starting and stopping services

---

[Back to Operator Hub](../../operator/)
