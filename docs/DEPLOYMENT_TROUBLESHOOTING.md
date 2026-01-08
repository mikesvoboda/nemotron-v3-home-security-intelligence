# Deployment Troubleshooting Guide

This guide provides solutions for common deployment failures, diagnostic commands, and investigation procedures for the Home Security Intelligence system.

## Table of Contents

1. [Quick Diagnosis](#quick-diagnosis)
2. [Database Issues](#database-issues)
3. [Redis Issues](#redis-issues)
4. [AI Service Issues](#ai-service-issues)
5. [Backend Issues](#backend-issues)
6. [Frontend Issues](#frontend-issues)
7. [Network Issues](#network-issues)
8. [GPU Issues](#gpu-issues)
9. [Storage Issues](#storage-issues)
10. [Performance Issues](#performance-issues)

---

## Quick Diagnosis

### Health Check Command

Run this command first to identify which services are unhealthy:

```bash
# Check all services
docker compose -f docker-compose.prod.yml ps

# Check health endpoints
curl http://localhost:8000/api/system/health/ready
curl http://localhost:8090/health
curl http://localhost:8091/health
curl http://localhost:5173
```

### Log Locations

| Service     | Docker Command                                               | Native Path                              |
| ----------- | ------------------------------------------------------------ | ---------------------------------------- |
| Backend     | `docker compose -f docker-compose.prod.yml logs backend`     | `backend/data/logs/security.log`         |
| Frontend    | `docker compose -f docker-compose.prod.yml logs frontend`    | Browser console (F12)                    |
| PostgreSQL  | `docker compose -f docker-compose.prod.yml logs postgres`    | Container `/var/lib/postgresql/data/log` |
| Redis       | `docker compose -f docker-compose.prod.yml logs redis`       | Container logs only                      |
| AI Services | `docker compose -f docker-compose.prod.yml logs ai-detector` | Container stdout                         |

### System Overview

```bash
# All services status
docker compose -f docker-compose.prod.yml ps

# Resource usage
docker stats --no-stream

# GPU usage
nvidia-smi

# Disk space
df -h

# Network connectivity
docker network inspect <project>_security-net
```

---

## Database Issues

### Issue: Database Connection Refused

**Symptoms:**

- Backend logs: `connection refused` or `could not connect to server`
- Backend health check fails
- API returns 503 errors

**Diagnosis:**

```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs postgres | tail -50

# Test connection from host
pg_isready -h localhost -p 5432 -U security

# Test connection from backend container
docker compose -f docker-compose.prod.yml exec backend psql postgresql://security:$POSTGRES_PASSWORD@postgres:5432/security -c "\conninfo"
```

**Solutions:**

1. **PostgreSQL not started:**

   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres
   ```

2. **Wrong credentials:**

   ```bash
   # Check DATABASE_URL in .env
   grep DATABASE_URL .env

   # Ensure POSTGRES_PASSWORD matches
   grep POSTGRES_PASSWORD .env
   ```

3. **Port conflict:**

   ```bash
   # Check if port 5432 is in use
   sudo lsof -i :5432

   # Stop conflicting service or change port in docker-compose.prod.yml
   ```

4. **Container networking issue:**
   ```bash
   # Recreate network
   docker compose -f docker-compose.prod.yml down
   docker network prune
   docker compose -f docker-compose.prod.yml up -d
   ```

### Issue: Database Authentication Failed

**Symptoms:**

- `FATAL: password authentication failed for user "security"`
- Backend cannot connect despite correct URL

**Diagnosis:**

```bash
# Verify password in .env
grep POSTGRES_PASSWORD .env

# Try connecting manually
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security
```

**Solutions:**

1. **Password mismatch:**

   ```bash
   # Reset password (use your actual password)
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "ALTER USER security WITH PASSWORD '<YOUR_PASSWORD>';"  # pragma: allowlist secret

   # Update .env (replace with your actual credentials)
   DATABASE_URL=postgresql+asyncpg://security:<YOUR_PASSWORD>@postgres:5432/security  # pragma: allowlist secret

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

2. **Database not initialized:**

   ```bash
   # Check if database exists
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "\l"

   # Create if missing
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "CREATE DATABASE security;"
   ```

### Issue: Database Migrations Failed

**Symptoms:**

- Backend fails to start with migration errors
- `alembic.util.exc.CommandError` in logs

**Diagnosis:**

```bash
# Check migration status
docker compose -f docker-compose.prod.yml run --rm backend alembic current

# Check migration history
docker compose -f docker-compose.prod.yml run --rm backend alembic history
```

**Solutions:**

1. **Migrations not applied:**

   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```

2. **Migration conflict:**

   ```bash
   # Downgrade to previous version
   docker compose -f docker-compose.prod.yml run --rm backend alembic downgrade -1

   # Reapply
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```

3. **Database schema mismatch:**
   ```bash
   # Restore from backup and reapply migrations
   # See DEPLOYMENT_RUNBOOK.md for restore procedure
   ```

### Issue: Database Disk Full

**Symptoms:**

- `ERROR: could not extend file ... No space left on device`
- PostgreSQL stops accepting writes

**Diagnosis:**

```bash
# Check disk usage
df -h

# Check database size
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT pg_size_pretty(pg_database_size('security'));"

# Check table sizes
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Solutions:**

1. **Run cleanup service:**

   ```bash
   # Trigger manual cleanup
   curl -X POST http://localhost:8000/api/admin/cleanup
   ```

2. **Vacuum database:**

   ```bash
   docker compose -f docker-compose.prod.yml exec postgres vacuumdb -U security -d security --full --analyze
   ```

3. **Archive old data:**

   ```bash
   # Export old events
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "COPY (SELECT * FROM events WHERE created_at < NOW() - INTERVAL '60 days') TO STDOUT CSV HEADER" > archived-events.csv

   # Delete archived data
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "DELETE FROM events WHERE created_at < NOW() - INTERVAL '60 days';"
   ```

---

## Redis Issues

### Issue: Redis Connection Refused

**Symptoms:**

- Backend logs: `ConnectionError: Error while reading from socket`
- Queue processing stops
- WebSocket connections fail

**Diagnosis:**

```bash
# Check Redis status
docker compose -f docker-compose.prod.yml ps redis

# Test connection
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check logs
docker compose -f docker-compose.prod.yml logs redis | tail -50
```

**Solutions:**

1. **Redis not started:**

   ```bash
   docker compose -f docker-compose.prod.yml up -d redis
   ```

2. **Redis out of memory:**

   ```bash
   # Check memory usage
   docker compose -f docker-compose.prod.yml exec redis redis-cli INFO memory

   # Clear cache
   docker compose -f docker-compose.prod.yml exec redis redis-cli FLUSHDB

   # Restart Redis
   docker compose -f docker-compose.prod.yml restart redis
   ```

3. **Redis password mismatch:**

   ```bash
   # Check if password is set
   grep REDIS_PASSWORD .env

   # Test with auth
   docker compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping
   ```

### Issue: Queue Backlog

**Symptoms:**

- Detections not processing
- High queue depths in metrics
- API endpoint reports queue pressure

**Diagnosis:**

```bash
# Check queue depths
curl http://localhost:8000/api/system/status | jq '.queues'

# Check queue contents
docker compose -f docker-compose.prod.yml exec redis redis-cli LLEN detection_queue
docker compose -f docker-compose.prod.yml exec redis redis-cli LLEN analysis_queue

# Check dead-letter queue
curl http://localhost:8000/api/dlq/stats
```

**Solutions:**

1. **AI services slow/down:**

   ```bash
   # Check AI service health
   curl http://localhost:8090/health
   curl http://localhost:8091/health

   # Restart AI services
   docker compose -f docker-compose.prod.yml restart ai-detector ai-llm
   ```

2. **Clear stuck queue items:**

   ```bash
   # Inspect items in queue
   docker compose -f docker-compose.prod.yml exec redis redis-cli LRANGE detection_queue 0 5

   # Clear queue (WARNING: loses pending work)
   docker compose -f docker-compose.prod.yml exec redis redis-cli DEL detection_queue
   ```

3. **Increase worker concurrency:**
   Edit `.env` or `data/runtime.env`:

   ```bash
   # Increase AI read timeouts
   RTDETR_READ_TIMEOUT=120.0
   NEMOTRON_READ_TIMEOUT=300.0

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

---

## AI Service Issues

### Issue: RT-DETRv2 Not Responding

**Symptoms:**

- Backend logs: `RT-DETR health check failed`
- Detection queue grows
- API shows `rtdetr: unreachable`

**Diagnosis:**

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps ai-detector

# Test health endpoint
curl http://localhost:8090/health

# Check logs
docker compose -f docker-compose.prod.yml logs ai-detector | tail -100

# Check GPU access
docker compose -f docker-compose.prod.yml exec ai-detector nvidia-smi
```

**Solutions:**

1. **Service not started:**

   ```bash
   docker compose -f docker-compose.prod.yml up -d ai-detector
   ```

2. **GPU not accessible:**

   ```bash
   # Check GPU is visible
   docker compose -f docker-compose.prod.yml exec ai-detector nvidia-smi

   # If fails, check nvidia-container-toolkit
   sudo systemctl status nvidia-container-toolkit

   # Reinstall if needed
   sudo apt install nvidia-container-toolkit
   sudo systemctl restart docker
   ```

3. **Model files missing:**

   ```bash
   # Check model cache
   docker compose -f docker-compose.prod.yml exec ai-detector ls -lh /cache/huggingface

   # If empty, download will happen on first request (takes time)
   # Monitor logs:
   docker compose -f docker-compose.prod.yml logs -f ai-detector
   ```

4. **Out of VRAM:**

   ```bash
   # Check VRAM usage
   nvidia-smi

   # Restart service to clear memory
   docker compose -f docker-compose.prod.yml restart ai-detector
   ```

### Issue: Nemotron Not Responding

**Symptoms:**

- Backend logs: `Nemotron health check failed`
- Analysis queue grows
- Events created without risk scores

**Diagnosis:**

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps ai-llm

# Test health endpoint
curl http://localhost:8091/health

# Check logs
docker compose -f docker-compose.prod.yml logs ai-llm | tail -100

# Check GPU memory
nvidia-smi
```

**Solutions:**

1. **Model loading timeout:**

   ```bash
   # Increase start_period in docker-compose.prod.yml
   # Nemotron takes 2-3 minutes to load into VRAM

   # Check if still loading
   docker compose -f docker-compose.prod.yml logs ai-llm | grep -i "loading"
   ```

2. **Model files incorrect:**

   ```bash
   # Check model path
   docker compose -f docker-compose.prod.yml exec ai-llm ls -lh /models

   # Should contain .gguf file
   # If missing, check AI_MODELS_PATH in .env
   ```

3. **VRAM exhausted:**

   ```bash
   # Reduce GPU layers
   # Edit .env:
   GPU_LAYERS=20  # Lower from 35

   # Restart service
   docker compose -f docker-compose.prod.yml restart ai-llm
   ```

### Issue: Optional AI Services Failing

Florence-2, CLIP, or Enrichment service not responding.

**Symptoms:**

- Backend logs show optional AI service errors
- Enrichment data missing from events
- Performance degradation

**Diagnosis:**

```bash
# Check service status
docker compose -f docker-compose.prod.yml ps ai-florence ai-clip ai-enrichment

# Test health endpoints
curl http://localhost:8092/health  # Florence
curl http://localhost:8093/health  # CLIP
curl http://localhost:8094/health  # Enrichment

# Check logs
docker compose -f docker-compose.prod.yml logs ai-florence ai-clip ai-enrichment
```

**Solutions:**

1. **Services not critical:**
   Backend gracefully degrades if optional services are unavailable. System continues operating without enrichment data.

2. **Restart services:**

   ```bash
   docker compose -f docker-compose.prod.yml restart ai-florence ai-clip ai-enrichment
   ```

3. **Disable if not needed:**
   ```bash
   # Stop optional services to free resources
   docker compose -f docker-compose.prod.yml stop ai-florence ai-clip ai-enrichment
   ```

---

## Backend Issues

### Issue: Backend Won't Start

**Symptoms:**

- Container exits immediately
- Health check never passes
- Port 8000 not responding

**Diagnosis:**

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps backend

# Check logs for errors
docker compose -f docker-compose.prod.yml logs backend | tail -100

# Check if port is in use
sudo lsof -i :8000
```

**Solutions:**

1. **Missing dependencies:**

   ```bash
   # Check if database/redis are healthy
   docker compose -f docker-compose.prod.yml ps postgres redis

   # Wait for dependencies
   docker compose -f docker-compose.prod.yml up -d postgres redis
   sleep 15
   docker compose -f docker-compose.prod.yml up -d backend
   ```

2. **Configuration error:**

   ```bash
   # Validate .env file
   grep -E "DATABASE_URL|REDIS_URL" .env

   # Test config loading
   docker compose -f docker-compose.prod.yml run --rm backend python -c "from backend.core import get_settings; print(get_settings())"
   ```

3. **Module import error:**

   ```bash
   # Check Python path
   docker compose -f docker-compose.prod.yml run --rm backend python -c "import backend; print(backend.__file__)"

   # Rebuild if needed
   docker compose -f docker-compose.prod.yml build --no-cache backend
   ```

### Issue: Worker Crashes

**Symptoms:**

- Backend logs: `Worker crashed` or `Task exception`
- File watcher stops processing
- GPU monitor stops updating

**Diagnosis:**

```bash
# Check backend logs for exceptions
docker compose -f docker-compose.prod.yml logs backend | grep -i -E "exception|error|crash"

# Check system resources
docker stats backend

# Check file system access
docker compose -f docker-compose.prod.yml exec backend ls -la /cameras
```

**Solutions:**

1. **File permission issues:**

   ```bash
   # Check camera directory permissions
   ls -ld /export/foscam
   ls -la /export/foscam/*/

   # Fix permissions
   sudo chown -R $USER:$USER /export/foscam
   chmod -R 755 /export/foscam
   ```

2. **GPU access lost:**

   ```bash
   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend

   # If persists, restart Docker/Podman
   sudo systemctl restart docker
   ```

3. **Memory leak:**

   ```bash
   # Check memory usage
   docker stats backend

   # Restart to clear
   docker compose -f docker-compose.prod.yml restart backend
   ```

### Issue: API Timeouts

**Symptoms:**

- Requests to API hang or timeout
- Frontend shows "Request timeout"
- API returns 504 Gateway Timeout

**Diagnosis:**

```bash
# Check backend responsiveness
time curl http://localhost:8000/api/system/health/ready

# Check worker queue depths
curl http://localhost:8000/api/system/status

# Check AI service responsiveness
time curl http://localhost:8090/health
time curl http://localhost:8091/health
```

**Solutions:**

1. **AI services slow:**

   ```bash
   # Increase timeouts in .env
   RTDETR_READ_TIMEOUT=120.0
   NEMOTRON_READ_TIMEOUT=300.0

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

2. **Database slow:**

   ```bash
   # Vacuum database
   docker compose -f docker-compose.prod.yml exec postgres vacuumdb -U security -d security --analyze

   # Check slow queries (if enabled)
   docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT query, calls, total_time FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
   ```

3. **High load:**

   ```bash
   # Check CPU/memory
   docker stats

   # Reduce concurrent processing
   # Edit docker-compose.prod.yml to increase resource limits
   ```

---

## Frontend Issues

### Issue: Frontend Not Loading

**Symptoms:**

- Browser shows "Connection refused" or blank page
- Port 5173 not responding
- 404 errors on all routes

**Diagnosis:**

```bash
# Check frontend status
docker compose -f docker-compose.prod.yml ps frontend

# Test endpoint
curl http://localhost:5173

# Check logs
docker compose -f docker-compose.prod.yml logs frontend | tail -50
```

**Solutions:**

1. **Frontend not started:**

   ```bash
   docker compose -f docker-compose.prod.yml up -d frontend
   ```

2. **Port conflict:**

   ```bash
   # Check if port is in use
   sudo lsof -i :5173

   # Change FRONTEND_PORT in .env if needed
   FRONTEND_PORT=8080

   # Restart frontend
   docker compose -f docker-compose.prod.yml up -d frontend
   ```

3. **Nginx configuration error:**

   ```bash
   # Check nginx config
   docker compose -f docker-compose.prod.yml exec frontend cat /etc/nginx/conf.d/default.conf

   # Test nginx config
   docker compose -f docker-compose.prod.yml exec frontend nginx -t
   ```

### Issue: API Requests Failing from Frontend

**Symptoms:**

- Frontend loads but shows errors
- Browser console: `Failed to fetch` or CORS errors
- Network tab shows 404 or 500 errors

**Diagnosis:**

```bash
# Check browser console (F12)
# Look for CORS errors or failed requests

# Check backend is reachable from frontend container
docker compose -f docker-compose.prod.yml exec frontend curl http://backend:8000/health

# Check CORS configuration
curl -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" -X OPTIONS http://localhost:8000/health -v
```

**Solutions:**

1. **Backend not reachable:**

   ```bash
   # Ensure backend is healthy
   docker compose -f docker-compose.prod.yml ps backend
   curl http://localhost:8000/health

   # Check network
   docker network inspect <project>_security-net
   ```

2. **CORS misconfiguration:**

   ```bash
   # Update CORS_ORIGINS in .env
   CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

3. **Wrong API URL:**

   ```bash
   # Check frontend environment at build time
   # In production, nginx proxies /api to backend
   # Frontend should use relative URLs

   # Verify nginx proxy config
   docker compose -f docker-compose.prod.yml exec frontend cat /etc/nginx/conf.d/default.conf | grep proxy_pass
   ```

### Issue: WebSocket Connection Fails

**Symptoms:**

- Real-time updates not working
- Frontend shows "Disconnected" status
- Browser console: `WebSocket connection failed`

**Diagnosis:**

```bash
# Test WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Host: localhost:8000" http://localhost:8000/api/ws

# Check backend WebSocket endpoint
docker compose -f docker-compose.prod.yml logs backend | grep -i websocket
```

**Solutions:**

1. **Backend WebSocket not enabled:**

   ```bash
   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

2. **Nginx not proxying WebSocket:**

   ```bash
   # Check nginx WebSocket config
   docker compose -f docker-compose.prod.yml exec frontend cat /etc/nginx/conf.d/default.conf | grep -A 5 "location /ws"

   # Should have:
   # proxy_http_version 1.1;
   # proxy_set_header Upgrade $http_upgrade;
   # proxy_set_header Connection "upgrade";
   ```

---

## Network Issues

### Issue: Containers Cannot Communicate

**Symptoms:**

- Backend cannot reach Redis/PostgreSQL
- Frontend cannot reach backend
- Services show connection refused

**Diagnosis:**

```bash
# List networks
docker network ls

# Inspect security-net
docker network inspect <project>_security-net

# Check container IPs
docker compose -f docker-compose.prod.yml ps -q | xargs docker inspect -f '{{.Name}} - {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

**Solutions:**

1. **Network not created:**

   ```bash
   # Recreate network
   docker compose -f docker-compose.prod.yml down
   docker network prune
   docker compose -f docker-compose.prod.yml up -d
   ```

2. **Firewall blocking:**

   ```bash
   # Check iptables
   sudo iptables -L

   # Allow Docker networks
   sudo iptables -I INPUT -i docker0 -j ACCEPT
   ```

3. **DNS resolution:**
   ```bash
   # Test DNS from container
   docker compose -f docker-compose.prod.yml exec backend getent hosts postgres
   docker compose -f docker-compose.prod.yml exec backend getent hosts redis
   ```

### Issue: AI Services Unreachable

**Symptoms:**

- Backend logs: `AI service unreachable`
- Health checks show AI services offline
- Detection/analysis fails

**Diagnosis:**

```bash
# Check if AI services are running
docker compose -f docker-compose.prod.yml ps | grep ai-

# Test from backend container
docker compose -f docker-compose.prod.yml exec backend curl http://ai-detector:8090/health
docker compose -f docker-compose.prod.yml exec backend curl http://ai-llm:8091/health

# Check AI service URLs in .env
grep -E "RTDETR_URL|NEMOTRON_URL" .env
```

**Solutions:**

See `docs/operator/deployment-modes.md` for AI service URL configuration based on deployment mode.

1. **Wrong URL for deployment mode:**

   For production (all containerized):

   ```bash
   # Should use container names
   RTDETR_URL=http://ai-detector:8090
   NEMOTRON_URL=http://ai-llm:8091
   ```

   For development (host-run AI):

   ```bash
   # Should use host gateway
   RTDETR_URL=http://host.docker.internal:8090
   NEMOTRON_URL=http://host.docker.internal:8091
   ```

2. **Restart backend to apply changes:**
   ```bash
   docker compose -f docker-compose.prod.yml restart backend
   ```

---

## GPU Issues

### Issue: GPU Not Detected

**Symptoms:**

- AI services fail to start
- Logs: `CUDA not available` or `No NVIDIA GPU detected`
- `nvidia-smi` fails in container

**Diagnosis:**

```bash
# Check GPU on host
nvidia-smi

# Check Docker/Podman GPU support
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Check container GPU access
docker compose -f docker-compose.prod.yml exec ai-detector nvidia-smi
```

**Solutions:**

1. **nvidia-container-toolkit not installed:**

   ```bash
   # Install toolkit
   sudo apt install nvidia-container-toolkit

   # Configure Docker
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker

   # Test
   docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
   ```

2. **GPU not passed to container:**

   ```bash
   # Check docker-compose.prod.yml has GPU reservation:
   grep -A 5 "reservations" docker-compose.prod.yml

   # Should see:
   # devices:
   #   - driver: nvidia
   #     count: 1
   #     capabilities: [gpu]
   ```

3. **Driver issue:**

   ```bash
   # Check driver version
   nvidia-smi

   # Reinstall if needed
   sudo apt remove --purge nvidia-*
   sudo apt install nvidia-driver-525
   sudo reboot
   ```

### Issue: Out of VRAM

**Symptoms:**

- AI services crash with OOM errors
- Logs: `CUDA out of memory`
- `nvidia-smi` shows 100% memory usage

**Diagnosis:**

```bash
# Check VRAM usage
nvidia-smi

# Check which processes use GPU
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

**Solutions:**

1. **Reduce Nemotron GPU layers:**

   ```bash
   # Edit .env
   GPU_LAYERS=20  # Lower from 35

   # Restart service
   docker compose -f docker-compose.prod.yml restart ai-llm
   ```

2. **Disable optional AI services:**

   ```bash
   # Stop Florence/CLIP/Enrichment to free VRAM
   docker compose -f docker-compose.prod.yml stop ai-florence ai-clip ai-enrichment
   ```

3. **Restart all AI services:**
   ```bash
   docker compose -f docker-compose.prod.yml restart ai-detector ai-llm ai-florence ai-clip ai-enrichment
   ```

---

## Storage Issues

### Issue: Disk Space Full

**Symptoms:**

- Services fail to write
- Database errors: `No space left on device`
- Container logs full

**Diagnosis:**

```bash
# Check disk usage
df -h

# Find large directories
du -sh /* | sort -h | tail -10

# Check Docker/Podman disk usage
docker system df
```

**Solutions:**

1. **Clean Docker resources:**

   ```bash
   # Remove unused images
   docker image prune -a

   # Remove unused volumes
   docker volume prune

   # Clean everything (CAREFUL)
   docker system prune -a --volumes
   ```

2. **Clean camera uploads:**

   ```bash
   # Delete images older than 30 days
   find /export/foscam -name "*.jpg" -mtime +30 -delete
   ```

3. **Vacuum database:**

   ```bash
   docker compose -f docker-compose.prod.yml exec postgres vacuumdb -U security -d security --full
   ```

4. **Rotate logs:**

   ```bash
   # Truncate Docker logs
   docker compose -f docker-compose.prod.yml logs > /dev/null

   # Or configure log rotation in daemon.json
   ```

---

## Performance Issues

### Issue: High CPU Usage

**Symptoms:**

- System sluggish
- API slow to respond
- Fan noise increased

**Diagnosis:**

```bash
# Check CPU usage
docker stats

# Check process CPU
top -c

# Check which service uses CPU
docker compose -f docker-compose.prod.yml exec backend top
```

**Solutions:**

1. **Reduce detection frequency:**

   ```bash
   # Increase file watcher polling interval
   FILE_WATCHER_POLLING_INTERVAL=5.0  # Increase from 1.0

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

2. **Reduce GPU polling:**

   ```bash
   # Increase GPU monitor interval
   GPU_POLL_INTERVAL_SECONDS=15.0  # Increase from 5.0

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

3. **Limit container resources:**
   Edit `docker-compose.prod.yml` to add CPU limits.

### Issue: Slow Detection Processing

**Symptoms:**

- Long delays between image upload and event
- Queue depths increasing
- Detections taking minutes instead of seconds

**Diagnosis:**

```bash
# Check queue depths
curl http://localhost:8000/api/system/status | jq '.queues'

# Check AI service response times
curl http://localhost:8000/api/system/health | jq '.services'

# Check GPU utilization
nvidia-smi -l 1
```

**Solutions:**

1. **AI services slow:**

   ```bash
   # Restart AI services
   docker compose -f docker-compose.prod.yml restart ai-detector ai-llm
   ```

2. **GPU underutilized:**

   ```bash
   # Check GPU clock speed
   nvidia-smi -q -d CLOCK

   # Enable persistence mode
   sudo nvidia-smi -pm 1
   ```

3. **Increase timeouts:**

   ```bash
   # Edit .env
   RTDETR_READ_TIMEOUT=120.0
   NEMOTRON_READ_TIMEOUT=300.0

   # Restart backend
   docker compose -f docker-compose.prod.yml restart backend
   ```

---

## Advanced Diagnostics

### Collect Full System Report

```bash
#!/bin/bash
# save as collect-diagnostics.sh

OUTPUT_DIR="diagnostics-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "Collecting diagnostics..."

# System info
nvidia-smi > "$OUTPUT_DIR/nvidia-smi.txt"
df -h > "$OUTPUT_DIR/disk-usage.txt"
docker system df > "$OUTPUT_DIR/docker-disk.txt"
free -h > "$OUTPUT_DIR/memory.txt"

# Service status
docker compose -f docker-compose.prod.yml ps > "$OUTPUT_DIR/services-status.txt"
docker stats --no-stream > "$OUTPUT_DIR/resource-usage.txt"

# Logs
docker compose -f docker-compose.prod.yml logs --tail=500 > "$OUTPUT_DIR/all-logs.txt"
docker compose -f docker-compose.prod.yml logs backend > "$OUTPUT_DIR/backend.log"
docker compose -f docker-compose.prod.yml logs postgres > "$OUTPUT_DIR/postgres.log"
docker compose -f docker-compose.prod.yml logs redis > "$OUTPUT_DIR/redis.log"

# Configuration
cp .env "$OUTPUT_DIR/env-sanitized.txt"
sed -i 's/PASSWORD=.*/PASSWORD=***REDACTED***/' "$OUTPUT_DIR/env-sanitized.txt"

# API status
curl -s http://localhost:8000/api/system/health/ready > "$OUTPUT_DIR/backend-health.json"
curl -s http://localhost:8000/api/system/status > "$OUTPUT_DIR/backend-status.json"

tar -czf "$OUTPUT_DIR.tar.gz" "$OUTPUT_DIR"
echo "Diagnostics saved to $OUTPUT_DIR.tar.gz"
```

---

## Getting Help

If issues persist after following this guide:

1. **Collect diagnostics** using the script above
2. **Check GitHub Issues**: https://github.com/your-org/repo/issues
3. **Review recent changes**: `git log --oneline -20`
4. **Consult other documentation**:
   - `docs/DEPLOYMENT_RUNBOOK.md` - Deployment procedures
   - `docs/RUNTIME_CONFIG.md` - Configuration reference
   - `docs/operator/deployment-modes.md` - AI service connectivity
