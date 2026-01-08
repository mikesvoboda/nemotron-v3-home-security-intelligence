# Deployment Runbook

This runbook provides step-by-step procedures for deploying, upgrading, rolling back, and recovering the Home Security Intelligence system.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Fresh Deployment](#fresh-deployment)
3. [Upgrade Procedure](#upgrade-procedure)
4. [Rollback Procedures](#rollback-procedures)
5. [Service Recovery](#service-recovery)
6. [Emergency Procedures](#emergency-procedures)

---

## Prerequisites

### Required Software

| Software                 | Version | Purpose                       | Installation                                        |
| ------------------------ | ------- | ----------------------------- | --------------------------------------------------- |
| Docker or Podman         | 20.10+  | Container runtime             | `brew install podman` or `apt install docker.io`    |
| Docker Compose / Podman  | 2.0+    | Multi-container orchestration | `brew install podman-compose` or with Docker Engine |
| NVIDIA Driver            | 525+    | GPU support                   | `apt install nvidia-driver-525`                     |
| nvidia-container-toolkit | 1.13+   | GPU passthrough to containers | See NVIDIA documentation                            |
| PostgreSQL Client        | 15+     | Database administration       | `apt install postgresql-client`                     |
| curl/wget                | Any     | Health checks                 | Pre-installed on most systems                       |

### Required Resources

| Resource       | Minimum | Recommended | Purpose                                |
| -------------- | ------- | ----------- | -------------------------------------- |
| CPU            | 4 cores | 8 cores     | Backend workers, AI inference          |
| RAM            | 16 GB   | 32 GB       | Services + AI model loading            |
| GPU VRAM       | 16 GB   | 24 GB       | RT-DETRv2 + Nemotron + optional models |
| Disk Space     | 100 GB  | 500 GB      | Database, logs, media files            |
| Camera Storage | 50 GB   | 200 GB      | FTP upload directory                   |

### Network Requirements

| Port | Service     | Protocol | Access        |
| ---- | ----------- | -------- | ------------- |
| 5173 | Frontend    | HTTP     | Browser       |
| 8000 | Backend API | HTTP/WS  | Frontend      |
| 8090 | RT-DETRv2   | HTTP     | Backend       |
| 8091 | Nemotron    | HTTP     | Backend       |
| 8092 | Florence-2  | HTTP     | Backend (opt) |
| 8093 | CLIP        | HTTP     | Backend (opt) |
| 8094 | Enrichment  | HTTP     | Backend (opt) |
| 5432 | PostgreSQL  | TCP      | Backend       |
| 6379 | Redis       | TCP      | Backend       |

### Required Secrets

Before deployment, you must have:

1. **PostgreSQL Password**: Strong, randomly generated password

   ```bash
   openssl rand -base64 32
   ```

2. **Camera FTP Path**: Directory where cameras upload images

   ```bash
   # Example
   /export/foscam
   ```

3. **AI Models Path**: Directory containing AI model files

   ```bash
   # Example
   /export/ai_models
   ```

4. **(Optional) Grafana Password**: For monitoring dashboard
   ```bash
   openssl rand -base64 32
   ```

### Pre-Deployment Checklist

- [ ] Docker/Podman installed and running
- [ ] NVIDIA driver and container toolkit installed (check with `nvidia-smi`)
- [ ] Camera FTP directory exists and is accessible
- [ ] AI models downloaded and extracted to correct paths
- [ ] Network ports are not in use by other services
- [ ] DNS or `/etc/hosts` configured (if using custom domain)
- [ ] Firewall rules allow required traffic
- [ ] Backup storage configured (for PostgreSQL backups)
- [ ] Secrets generated and stored securely

---

## Fresh Deployment

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/nemotron-v3-home-security-intelligence.git
cd nemotron-v3-home-security-intelligence

# Checkout the desired version (or use main)
git checkout main
```

### Step 2: Run Setup Script

The setup script generates `.env` and `docker-compose.override.yml` with secure defaults.

```bash
# Quick mode (accept defaults)
./setup.sh

# Guided mode (with explanations)
./setup.sh --guided
```

The script will prompt for:

- PostgreSQL password (auto-generated if not provided)
- Camera upload path (default: `/export/foscam`)
- AI models path (default: `/export/ai_models`)
- Frontend port (default: `5173`)

### Step 3: Verify Configuration

```bash
# Check .env file was created
cat .env

# Verify critical settings
grep -E "DATABASE_URL|REDIS_URL|CAMERA_PATH|AI_MODELS_PATH" .env

# Ensure no placeholder passwords remain
grep -E "CHANGEME|password123|example" .env
```

### Step 4: Start Services

**Using Docker:**

```bash
# Start all services in production mode
docker compose -f docker-compose.prod.yml up -d

# Verify containers are starting
docker compose -f docker-compose.prod.yml ps
```

**Using Podman:**

```bash
# Start all services in production mode
podman-compose -f docker-compose.prod.yml up -d

# Verify containers are starting
podman-compose -f docker-compose.prod.yml ps
```

### Step 5: Monitor Startup

Services start in dependency order. Monitor logs:

```bash
# Stream all logs
docker compose -f docker-compose.prod.yml logs -f

# Or monitor specific services
docker compose -f docker-compose.prod.yml logs -f backend
```

Wait for health checks to pass. Expected startup times:

- **Redis**: 5-10 seconds
- **PostgreSQL**: 10-15 seconds
- **AI Services**: 60-180 seconds (model loading)
- **Backend**: 30-60 seconds (waits for dependencies)
- **Frontend**: 10-20 seconds

### Step 6: Verify Deployment

Run the deployment test script:

```bash
./scripts/test-docker.sh --no-cleanup
```

Or verify manually:

```bash
# Check all services are healthy
docker compose -f docker-compose.prod.yml ps

# Test health endpoints
curl http://localhost:8000/api/system/health/ready
curl http://localhost:8090/health  # RT-DETRv2
curl http://localhost:8091/health  # Nemotron
curl http://localhost:5173         # Frontend

# Check database connectivity
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security

# Check Redis connectivity
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

Expected responses:

- Backend: `{"status": "ready", ...}`
- AI services: `{"status": "ok"}`
- Frontend: HTML page
- PostgreSQL: `accepting connections`
- Redis: `PONG`

### Step 7: Verify AI Pipeline

Upload a test image to trigger the pipeline:

```bash
# Copy a test image to camera directory
cp backend/data/test_images/sample.jpg /export/foscam/test_camera/test_$(date +%s).jpg

# Monitor backend logs for processing
docker compose -f docker-compose.prod.yml logs -f backend | grep -E "detect|batch|analyze"
```

Expected log sequence:

1. `FileWatcher detected new file`
2. `Detection queued`
3. `RT-DETR detection complete`
4. `Detection saved to database`
5. `Batch aggregator created event`
6. `Nemotron analysis complete`
7. `Event created with risk score`

### Step 8: Access Dashboard

1. Open browser to `http://localhost:5173` (or your configured `FRONTEND_PORT`)
2. Verify dashboard loads without errors
3. Check WebSocket connection status (top-right indicator)
4. Verify camera grid appears
5. Check for test event in activity feed

### Step 9: Configure Monitoring (Optional)

If using the monitoring stack:

```bash
# Start with monitoring profile
docker compose --profile monitoring -f docker-compose.prod.yml up -d

# Access Grafana
open http://localhost:3002

# Default credentials (CHANGE IMMEDIATELY)
# Username: admin
# Password: (from GF_ADMIN_PASSWORD in .env)
```

### Step 10: Configure Backups

Set up automated PostgreSQL backups:

```bash
# Create backup directory
mkdir -p /var/backups/hsi

# Add to crontab (daily backups at 2 AM)
crontab -e

# Add this line
0 2 * * * docker compose -f /path/to/docker-compose.prod.yml exec -T postgres pg_dump -U security -d security | gzip > /var/backups/hsi/backup-$(date +\%Y\%m\%d-\%H\%M\%S).sql.gz
```

---

## Upgrade Procedure

### Pre-Upgrade Checklist

- [ ] Read release notes for breaking changes
- [ ] Backup database (see [Backup Procedures](#backup-procedures))
- [ ] Check disk space (at least 10 GB free)
- [ ] Review new environment variables in `.env.example`
- [ ] Notify users of planned downtime (if applicable)
- [ ] Verify current deployment is healthy
- [ ] Test upgrade in staging environment (if available)

### Upgrade Steps

#### 1. Backup Current Deployment

```bash
# Backup database
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U security -d security -F c > backup-pre-upgrade-$(date +%Y%m%d).dump

# Backup Redis data (if needed)
docker compose -f docker-compose.prod.yml exec redis redis-cli BGSAVE
docker compose -f docker-compose.prod.yml cp redis:/data/dump.rdb backup-redis-$(date +%Y%m%d).rdb

# Backup .env file
cp .env .env.backup-$(date +%Y%m%d)

# Backup docker-compose overrides (if exists)
[ -f docker-compose.override.yml ] && cp docker-compose.override.yml docker-compose.override.yml.backup-$(date +%Y%m%d)
```

#### 2. Pull Latest Code

```bash
# Fetch latest changes
git fetch origin

# Check what will be updated
git log HEAD..origin/main --oneline

# Pull the update
git pull origin main

# Or checkout a specific version
git checkout v1.2.0
```

#### 3. Review Configuration Changes

```bash
# Compare .env.example with current .env
diff .env.example .env

# Check for new required variables
grep -E "required|REQUIRED|must be set" .env.example
```

Add any new required variables to `.env`.

#### 4. Pull New Container Images

**If using GHCR pre-built images:**

```bash
# Pull latest images
docker pull ghcr.io/your-org/home-security-intelligence/backend:latest
docker pull ghcr.io/your-org/home-security-intelligence/frontend:latest

# Or pull specific version
docker pull ghcr.io/your-org/home-security-intelligence/backend:v1.2.0
docker pull ghcr.io/your-org/home-security-intelligence/frontend:v1.2.0
```

**If building locally:**

```bash
# Rebuild images
docker compose -f docker-compose.prod.yml build --no-cache
```

#### 5. Stop Services

```bash
# Graceful shutdown (allows containers to finish current work)
docker compose -f docker-compose.prod.yml down

# Verify all containers stopped
docker compose -f docker-compose.prod.yml ps
```

#### 6. Apply Database Migrations

```bash
# Start only database service
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for database to be ready
until docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security; do sleep 1; done

# Run migrations (backend container applies migrations on startup)
# Or run manually:
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

#### 7. Start Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Monitor logs for errors
docker compose -f docker-compose.prod.yml logs -f
```

#### 8. Verify Upgrade

```bash
# Check service health
curl http://localhost:8000/api/system/health/ready

# Verify version (if exposed in API)
curl http://localhost:8000/api/system/version

# Test AI pipeline with sample image
cp backend/data/test_images/sample.jpg /export/foscam/test_camera/upgrade_test_$(date +%s).jpg

# Check frontend loads
curl http://localhost:5173
```

#### 9. Monitor for Issues

Monitor logs for the first hour after upgrade:

```bash
# Watch for errors
docker compose -f docker-compose.prod.yml logs -f | grep -i -E "error|exception|failed"

# Monitor resource usage
docker stats

# Check GPU utilization
nvidia-smi -l 5
```

#### 10. Clean Up (Optional)

```bash
# Remove old images
docker image prune -f

# Remove old backups (keep last 7 days)
find /var/backups/hsi -name "backup-*.sql.gz" -mtime +7 -delete
```

---

## Rollback Procedures

If the upgrade fails or introduces critical issues, follow these rollback procedures.

### Scenario 1: Application Issues (Database Intact)

If the new version has bugs but the database is compatible:

#### 1. Stop Current Version

```bash
docker compose -f docker-compose.prod.yml down
```

#### 2. Revert Code

```bash
# Find previous version
git log --oneline -10

# Checkout previous version
git checkout <previous-commit-sha>

# Example
git checkout abc1234
```

#### 3. Pull Previous Images (if using GHCR)

```bash
# Pull previous version tag
docker pull ghcr.io/your-org/home-security-intelligence/backend:v1.1.0
docker pull ghcr.io/your-org/home-security-intelligence/frontend:v1.1.0

# Update IMAGE_TAG in .env or export
export IMAGE_TAG=v1.1.0
```

#### 4. Restore Configuration

```bash
# Restore previous .env if needed
cp .env.backup-<date> .env
```

#### 5. Restart Services

```bash
docker compose -f docker-compose.prod.yml up -d
```

#### 6. Verify Rollback

```bash
curl http://localhost:8000/api/system/health/ready
```

### Scenario 2: Database Migration Issues

If database migration fails or causes data corruption:

#### 1. Stop All Services

```bash
docker compose -f docker-compose.prod.yml down
```

#### 2. Restore Database Backup

```bash
# Start only PostgreSQL
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for database
until docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security; do sleep 1; done

# Drop current database
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "DROP DATABASE security;"

# Recreate database
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d postgres -c "CREATE DATABASE security;"

# Restore from backup
docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U security -d security < backup-pre-upgrade-<date>.dump

# Or from SQL format
gunzip -c backup-pre-upgrade-<date>.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U security -d security
```

#### 3. Revert to Previous Version

Follow steps from Scenario 1 to revert code and images.

#### 4. Verify Data Integrity

```bash
# Connect to database
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security

# Check row counts
SELECT 'cameras', COUNT(*) FROM cameras
UNION ALL
SELECT 'detections', COUNT(*) FROM detections
UNION ALL
SELECT 'events', COUNT(*) FROM events;

# Check latest timestamps
SELECT MAX(created_at) FROM events;
```

### Scenario 3: Critical Service Failure

If a critical service (Redis, PostgreSQL, AI service) fails to start:

#### 1. Identify Failing Service

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs <service-name>
```

#### 2. Rollback Specific Service

**For backend/frontend:**

```bash
# Revert code and rebuild
git checkout <previous-commit>
docker compose -f docker-compose.prod.yml build backend frontend
docker compose -f docker-compose.prod.yml up -d backend frontend
```

**For database:**

```bash
# Restore from backup (see Scenario 2)
```

**For AI services:**

```bash
# Check model files are intact
ls -lh /export/ai_models/nemotron/
ls -lh /export/ai_models/model-zoo/

# Restart service
docker compose -f docker-compose.prod.yml restart ai-detector ai-llm
```

### Rollback Decision Matrix

| Symptom                 | Action                                       | Downtime  |
| ----------------------- | -------------------------------------------- | --------- |
| Frontend UI broken      | Rollback frontend only                       | 1-2 min   |
| API errors, DB intact   | Rollback backend only                        | 2-5 min   |
| Database corruption     | Restore DB backup + rollback code            | 10-30 min |
| AI service crash loop   | Check GPU, restart AI services, check models | 5-10 min  |
| Complete system failure | Full rollback (all services + DB)            | 15-45 min |

---

## Service Recovery

### Redis Recovery

#### Symptoms

- Connection refused errors
- WebSocket disconnections
- Queue processing stops

#### Recovery Steps

```bash
# Check Redis status
docker compose -f docker-compose.prod.yml ps redis
docker compose -f docker-compose.prod.yml logs redis

# Check memory usage
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO memory

# Restart Redis
docker compose -f docker-compose.prod.yml restart redis

# Verify persistence
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO persistence

# Clear cache if corrupted (WARNING: loses cached data)
docker compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL
```

### PostgreSQL Recovery

#### Symptoms

- Database connection errors
- Slow query performance
- Disk space warnings

#### Recovery Steps

```bash
# Check database status
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U security

# Check connections
docker compose -f docker-compose.prod.yml exec postgres psql -U security -d security -c "SELECT count(*) FROM pg_stat_activity;"

# Check disk usage
docker compose -f docker-compose.prod.yml exec postgres df -h

# Restart database
docker compose -f docker-compose.prod.yml restart postgres

# Vacuum database (reclaim space)
docker compose -f docker-compose.prod.yml exec postgres vacuumdb -U security -d security --analyze

# Reindex if needed
docker compose -f docker-compose.prod.yml exec postgres reindexdb -U security -d security
```

### AI Service Recovery

#### RT-DETRv2 Recovery

```bash
# Check service status
curl http://localhost:8090/health

# Check logs
docker compose -f docker-compose.prod.yml logs ai-detector

# Verify GPU access
docker compose -f docker-compose.prod.yml exec ai-detector nvidia-smi

# Restart service
docker compose -f docker-compose.prod.yml restart ai-detector

# Check model files
docker compose -f docker-compose.prod.yml exec ai-detector ls -lh /cache/huggingface
```

#### Nemotron Recovery

```bash
# Check service status
curl http://localhost:8091/health

# Check logs
docker compose -f docker-compose.prod.yml logs ai-llm

# Verify model loaded
docker compose -f docker-compose.prod.yml exec ai-llm ls -lh /models

# Restart service (takes 2-3 minutes to reload model)
docker compose -f docker-compose.prod.yml restart ai-llm

# Check GPU memory
nvidia-smi
```

### Backend Recovery

#### Symptoms

- API timeouts
- Worker crashes
- Queue backlog

#### Recovery Steps

```bash
# Check service logs
docker compose -f docker-compose.prod.yml logs backend | tail -100

# Check health endpoint
curl http://localhost:8000/api/system/health/ready

# Check queue depths
curl http://localhost:8000/api/system/status

# Restart backend
docker compose -f docker-compose.prod.yml restart backend

# Clear Redis queues if stuck (WARNING: loses pending work)
docker compose -f docker-compose.prod.yml exec redis redis-cli DEL detection_queue analysis_queue

# Check for dead-letter queue items
curl http://localhost:8000/api/dlq/stats
```

### Frontend Recovery

```bash
# Check frontend status
curl http://localhost:5173

# Check logs
docker compose -f docker-compose.prod.yml logs frontend

# Restart frontend
docker compose -f docker-compose.prod.yml restart frontend

# Clear browser cache if issues persist
# (Instruct users to hard refresh: Ctrl+Shift+R / Cmd+Shift+R)
```

---

## Emergency Procedures

### Complete System Restart

```bash
# Stop all services gracefully
docker compose -f docker-compose.prod.yml down

# Wait 10 seconds
sleep 10

# Start services in order
docker compose -f docker-compose.prod.yml up -d redis postgres
sleep 15
docker compose -f docker-compose.prod.yml up -d ai-detector ai-llm ai-florence ai-clip ai-enrichment
sleep 60
docker compose -f docker-compose.prod.yml up -d backend
sleep 15
docker compose -f docker-compose.prod.yml up -d frontend

# Verify all services healthy
docker compose -f docker-compose.prod.yml ps
```

### Force Stop (Last Resort)

```bash
# Force stop all containers
docker compose -f docker-compose.prod.yml kill

# Remove containers
docker compose -f docker-compose.prod.yml rm -f

# Clean up volumes (WARNING: DELETES ALL DATA)
docker compose -f docker-compose.prod.yml down -v

# Restore from backup and redeploy
```

### Disk Space Emergency

```bash
# Check disk usage
df -h

# Find large files
du -sh /* | sort -h

# Clean Docker/Podman resources
docker system prune -a --volumes

# Clean camera uploads (older than 30 days)
find /export/foscam -name "*.jpg" -mtime +30 -delete

# Vacuum database
docker compose -f docker-compose.prod.yml exec postgres vacuumdb -U security -d security --full

# Rotate logs
docker compose -f docker-compose.prod.yml logs > /dev/null
```

### GPU Out of Memory

```bash
# Check GPU usage
nvidia-smi

# Kill processes using GPU
nvidia-smi --query-compute-apps=pid --format=csv,noheader | xargs kill

# Restart AI services
docker compose -f docker-compose.prod.yml restart ai-detector ai-llm ai-florence ai-clip ai-enrichment

# Reduce GPU layers (edit .env)
GPU_LAYERS=20  # Lower from 35

# Restart backend to apply new settings
docker compose -f docker-compose.prod.yml restart backend
```

---

## Post-Recovery Verification

After any recovery procedure, verify system health:

```bash
# Run full deployment test
./scripts/test-docker.sh --no-cleanup

# Check all health endpoints
for port in 8000 8090 8091 8092 8093 8094; do
  echo "Testing port $port..."
  curl -s http://localhost:$port/health || curl -s http://localhost:$port/api/system/health/ready
done

# Upload test image
cp backend/data/test_images/sample.jpg /export/foscam/test_camera/recovery_test_$(date +%s).jpg

# Monitor processing
docker compose -f docker-compose.prod.yml logs -f backend | grep -E "detect|batch|analyze" | head -20

# Check WebSocket connectivity
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Host: localhost:8000" http://localhost:8000/api/ws
```

---

## Contact and Support

### Log Collection for Support

```bash
# Collect all logs
docker compose -f docker-compose.prod.yml logs > system-logs-$(date +%Y%m%d-%H%M%S).txt

# Collect system info
docker compose -f docker-compose.prod.yml ps > system-status-$(date +%Y%m%d-%H%M%S).txt
docker stats --no-stream >> system-status-$(date +%Y%m%d-%H%M%S).txt
nvidia-smi >> system-status-$(date +%Y%m%d-%H%M%S).txt
```

### Emergency Contacts

- **GitHub Issues**: https://github.com/your-org/repo/issues
- **Documentation**: See `docs/` directory
- **Linear Workspace**: https://linear.app/nemotron-v3-home-security
