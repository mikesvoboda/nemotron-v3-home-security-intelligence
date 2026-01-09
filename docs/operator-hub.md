# Operator Hub

> Deploy, configure, and maintain Home Security Intelligence.

This hub is for **sysadmins, DevOps engineers, and technically savvy users** who deploy and maintain the system. For end-user documentation, see the [User Hub](user-hub.md). For development and contribution, see the [Developer Hub](developer-hub.md).

> See [Stability Levels](reference/stability.md) for what’s stable vs still evolving.

---

## Quick Deploy

**New installation:** [Requirements](#system-requirements) -> [Installation](getting-started/installation.md) -> [First Run](getting-started/first-run.md)

**Estimated deployment time:** 30-45 minutes (including model downloads)

```bash
# Quick start (requires prerequisites)
git clone https://github.com/your-org/home-security-intelligence.git
cd home-security-intelligence
./scripts/setup-hooks.sh
./ai/download_models.sh
docker compose -f docker-compose.prod.yml up -d
```

---

## Deployment

### System Requirements

~5 min read | [Full Guide](getting-started/prerequisites.md)

| Component   | Minimum         | Recommended       |
| ----------- | --------------- | ----------------- |
| **GPU**     | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| **CPU**     | 4 cores         | 8+ cores          |
| **RAM**     | 8GB             | 16GB+             |
| **Storage** | 50GB            | 100GB+ SSD        |
| **CUDA**    | 11.8+           | 12.x              |

**AI VRAM Usage:**

- RT-DETRv2 (object detection): ~4GB
- Nemotron Mini 4B (risk analysis): ~3GB
- **Total required:** ~7GB concurrent

**Supported GPUs:** RTX 30/40 series, RTX A-series, Tesla/V100/A100

### Container Setup

~10 min read | [Full Guide](DOCKER_DEPLOYMENT.md)

This project supports **both Docker and Podman**. All compose files are OCI-compliant.

| Runtime        | Platform              | License    |
| -------------- | --------------------- | ---------- |
| Docker Engine  | Linux                 | Free       |
| Docker Desktop | macOS, Windows, Linux | Commercial |
| Podman         | Linux, macOS          | Free       |

**Quick commands:**

```bash
# Docker
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml down

# Podman
podman-compose -f docker-compose.prod.yml up -d
podman-compose -f docker-compose.prod.yml logs -f
podman-compose -f docker-compose.prod.yml down
```

**Compose files:**

| File                      | Purpose          | AI Services   |
| ------------------------- | ---------------- | ------------- |
| `docker-compose.yml`      | Development      | Host (native) |
| `docker-compose.prod.yml` | Production       | Containerized |
| `docker-compose.ghcr.yml` | Pre-built images | Containerized |

### GPU Passthrough

~15 min read | [Full Guide](operator/gpu-setup.md)

AI services run in containers with NVIDIA GPU passthrough via Container Device Interface (CDI).

**Prerequisites:**

1. NVIDIA driver 535+
2. NVIDIA Container Toolkit

```bash
# Verify GPU access
nvidia-smi

# Test container GPU access (Docker)
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi

# Test container GPU access (Podman with CDI)
podman run --rm --device nvidia.com/gpu=all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

**Troubleshooting:**

- [GPU Setup Guide](operator/gpu-setup.md#7-troubleshooting)
- [GPU Issues Reference](reference/troubleshooting/gpu-issues.md)

### Installation

~15 min read | [Full Guide](getting-started/installation.md)

**Step-by-step:**

1. **Clone and setup:**

   ```bash
   git clone https://github.com/your-org/home-security-intelligence.git
   cd home-security-intelligence
   ./scripts/setup-hooks.sh
   ```

2. **Download AI models (~2.7GB):**

   ```bash
   ./ai/download_models.sh
   ```

3. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Start services:**

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

5. **Verify:**
   ```bash
   curl http://localhost:8000/api/system/health
   ```

### Deployment Options

| Mode        | Use Case                          | AI Services            | Compose File              |
| ----------- | --------------------------------- | ---------------------- | ------------------------- |
| Production  | Full deployment                   | Containerized          | `docker-compose.prod.yml` |
| Development | Local development, hot reload     | Host (native)          | `docker-compose.yml`      |
| GHCR        | Pre-built app images, fast deploy | External (host/remote) | `docker-compose.ghcr.yml` |

**Production deployment:**

```bash
docker compose -f docker-compose.prod.yml up -d
```

**Development with host AI:**

```bash
# Terminal 1: Start RT-DETRv2
./ai/start_detector.sh

# Terminal 2: Start Nemotron
./ai/start_llm.sh

# Terminal 3: Start application stack
docker compose up -d
```

---

## Configuration

### Environment Variables

~10 min read | [Full Guide](admin-guide/configuration.md)

Configuration loads in order (later overrides earlier):

1. Default values in `backend/core/config.py`
2. `.env` file in project root
3. `data/runtime.env` (runtime overrides)
4. Shell environment variables

**Key configuration files:**

| File               | Purpose                      |
| ------------------ | ---------------------------- |
| `.env`             | Local settings (git ignored) |
| `.env.example`     | Template with defaults       |
| `data/runtime.env` | Runtime overrides            |

**Essential variables:**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security
REDIS_URL=redis://redis:6379

# AI Services
# Production (docker-compose.prod.yml): backend reaches AI services by compose DNS
RTDETR_URL=http://ai-detector:8090
NEMOTRON_URL=http://ai-llm:8091
FLORENCE_URL=http://ai-florence:8092
CLIP_URL=http://ai-clip:8093
ENRICHMENT_URL=http://ai-enrichment:8094

# Camera uploads
FOSCAM_BASE_PATH=/export/foscam

# Retention
RETENTION_DAYS=30
```

### AI Configuration

~8 min read | [Full Guide](operator/ai-overview.md)

**Deployment modes & networking (start here if AI is unreachable):**

- [Deployment Modes & AI Networking](operator/deployment-modes.md) - pick the right URLs for your setup

**AI Services Documentation:**

| Document                                             | Description                    | Time    |
| ---------------------------------------------------- | ------------------------------ | ------- |
| [AI Overview](operator/ai-overview.md)               | What the AI does, architecture | ~5 min  |
| [AI Installation](operator/ai-installation.md)       | Prerequisites and dependencies | ~10 min |
| [AI Configuration](operator/ai-configuration.md)     | Environment variables          | ~8 min  |
| [AI GHCR Deployment](operator/ai-ghcr-deployment.md) | Deploy AI from GHCR            | ~12 min |
| [AI Services](operator/ai-services.md)               | Starting, stopping, verifying  | ~8 min  |
| [AI Troubleshooting](operator/ai-troubleshooting.md) | Common issues and solutions    | ~10 min |
| [AI Performance](operator/ai-performance.md)         | Performance tuning             | ~6 min  |
| [AI TLS](operator/ai-tls.md)                         | Secure communications          | ~5 min  |

**Key variables:**

| Variable                         | Default                 | Description                  |
| -------------------------------- | ----------------------- | ---------------------------- |
| `RTDETR_URL`                     | `http://localhost:8090` | Detection service URL        |
| `NEMOTRON_URL`                   | `http://localhost:8091` | LLM service URL              |
| `FLORENCE_URL`                   | `http://localhost:8092` | Optional vision extraction   |
| `CLIP_URL`                       | `http://localhost:8093` | Optional re-identification   |
| `ENRICHMENT_URL`                 | `http://localhost:8094` | Optional enrichment endpoint |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5`                   | Minimum detection confidence |
| `AI_CONNECT_TIMEOUT`             | `10.0`                  | Connection timeout (seconds) |
| `RTDETR_READ_TIMEOUT`            | `60.0`                  | Detection timeout (seconds)  |
| `NEMOTRON_READ_TIMEOUT`          | `120.0`                 | LLM timeout (seconds)        |

**Container networking:**

```bash
# Production (docker-compose.prod.yml): internal DNS
RTDETR_URL=http://ai-detector:8090
NEMOTRON_URL=http://ai-llm:8091

# Docker Desktop (macOS/Windows) - default works
RTDETR_URL=http://host.docker.internal:8090

# Podman on macOS
export AI_HOST=host.containers.internal

# Linux - use host IP
export AI_HOST=192.168.1.100
```

### Camera Setup

~5 min read | [Full Guide](getting-started/first-run.md#configure-your-first-camera)

Cameras upload images via FTP to a monitored directory.

```bash
# Directory structure
/export/foscam/
  front_door/
  back_yard/
  garage/
```

**Configuration:**

```bash
# .env
FOSCAM_BASE_PATH=/export/foscam
```

**Add a camera via API:**

```bash
curl -X POST http://localhost:8000/api/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "folder_path": "front_door",
    "status": "active"
  }'
```

**File watcher settings (for Docker Desktop on macOS/Windows):**

```bash
FILE_WATCHER_POLLING=true
FILE_WATCHER_POLLING_INTERVAL=1.0
```

### Database Setup

~5 min read | [Full Guide](admin-guide/configuration.md#database-configuration)

PostgreSQL is required. SQLite is not supported.

```bash
# Connection URL format
DATABASE_URL=postgresql+asyncpg://username:password@host:port/database

# Docker Compose (run ./setup.sh to generate .env with secure password)
DATABASE_URL=postgresql+asyncpg://security:<your-password>@postgres:5432/security

# Native development
DATABASE_URL=postgresql+asyncpg://security:<your-password>@localhost:5432/security
```

> **Note:** There is no default password. Run `./setup.sh` to generate secure credentials, or create a password with `openssl rand -base64 32`.

**Run migrations:**

```bash
cd backend
alembic upgrade head
```

### Redis Setup

~10 min read | [Full Guide](operator/redis.md)

Redis is required for caching, pub/sub messaging, and queue management.

```bash
# Connection URL format
REDIS_URL=redis://host:port

# Docker Compose (internal network)
REDIS_URL=redis://redis:6379

# Native development
REDIS_URL=redis://localhost:6379/0
```

**Password authentication (recommended for production):**

```bash
# Generate secure password
openssl rand -base64 32

# Add to .env
REDIS_PASSWORD=your_generated_password_here
```

When `REDIS_PASSWORD` is set, both the Redis container and backend automatically use it. See [Redis Setup Guide](operator/redis.md) for:

- Authentication configuration
- SSL/TLS setup
- Troubleshooting connection issues

### Secrets Management

~8 min read | [Full Guide](operator/secrets-management.md)

For production deployments, use Docker Secrets instead of environment variables for sensitive credentials:

```bash
# Create secrets directory
mkdir -p secrets && chmod 700 secrets

# Generate secure passwords
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/redis_password.txt
chmod 600 secrets/*.txt
```

See [Secrets Management Guide](operator/secrets-management.md) for:

- Docker Secrets setup and configuration
- Credential rotation procedures
- Migration from environment variables
- Security best practices

---

## Operations

### Monitoring

~10 min read | [Full Guide](admin-guide/monitoring.md)

The system provides real-time monitoring for:

- **GPU metrics** - Utilization, memory, temperature, power
- **Service health** - AI services, Redis, PostgreSQL
- **Dead Letter Queue** - Failed job inspection and recovery

**Health endpoints:**

```bash
# Overall system health
curl http://localhost:8000/api/system/health

# GPU stats
curl http://localhost:8000/api/system/gpu

# GPU history (use `since` + `limit`)
curl "http://localhost:8000/api/system/gpu/history?since=2025-12-30T09:45:00Z&limit=300"

# DLQ stats
curl http://localhost:8000/api/dlq/stats
```

**WebSocket monitoring:**

GPU stats and service status broadcast via `/ws/system` channel.

**Advanced Observability:**

For detailed documentation on GPU monitoring, LLM token tracking, and distributed tracing, see:

- [Monitoring and Observability Guide](operator/monitoring.md) - GPU metrics, token tracking, OpenTelemetry setup
- [Prometheus Alerting Guide](operator/prometheus-alerting.md) - Alert rules, Alertmanager configuration, notification channels

**System Management:**

- [Service Control](operator/service-control.md) - Start, stop, restart services via dashboard UI
- [DLQ Management](operator/dlq-management.md) - Monitor and recover failed AI pipeline jobs
- [Scene Change Detection](operator/scene-change-detection.md) - Configure camera tampering alerts

### Prometheus Alerting

~10 min read | [Full Guide](operator/prometheus-alerting.md)

Configure alerts for AI pipeline failures, infrastructure issues, and SLO violations:

```bash
# Enable monitoring stack
docker compose --profile monitoring -f docker-compose.prod.yml up -d

# Access Alertmanager
open http://localhost:9093
```

**Pre-configured alerts include:**

| Category       | Examples                                             |
| -------------- | ---------------------------------------------------- |
| AI Pipeline    | Detector unavailable, high error rate, queue backlog |
| GPU Resources  | Overheating, memory critical, temperature warning    |
| Infrastructure | Database unhealthy, Redis unhealthy                  |
| SLO Violations | API availability, detection latency                  |

See [Prometheus Alerting Guide](operator/prometheus-alerting.md) for:

- Alert severity levels and routing
- Configuring Slack/email/PagerDuty notifications
- Custom alert rules
- Alert silencing and runbooks

### Backup and Recovery

~10 min read | [Full Guide](operator/backup.md)

**Quick database backup:**

```bash
# See operator/backup.md for full backup/restore runbooks.
# Docker (recommended):
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U security -d security \
  --format=custom --compress=9 \
  > backup_$(date +%Y%m%d).dump
```

**Quick restore:**

```bash
# Restore from compressed backup
docker compose -f docker-compose.prod.yml exec -T postgres pg_restore \
  -U security -d security --clean --if-exists \
  < backup.dump
```

> [!NOTE]
> Redis is ephemeral cache and does **not** require backup.

See [Backup Guide](operator/backup.md) for:

- Automated daily backups
- Full system recovery procedures
- Disaster recovery checklist

### Data Retention

~5 min read | [Full Guide](admin-guide/storage-retention.md)

Automated cleanup runs daily at 03:00.

| Data Type  | Default Retention | Variable             |
| ---------- | ----------------- | -------------------- |
| Events     | 30 days           | `RETENTION_DAYS`     |
| Detections | 30 days           | `RETENTION_DAYS`     |
| GPU Stats  | 30 days           | `RETENTION_DAYS`     |
| Logs       | 7 days            | `LOG_RETENTION_DAYS` |

**Preview cleanup (dry run):**

```bash
curl -X POST "http://localhost:8000/api/system/cleanup?dry_run=true"
```

**Storage estimates:**

| Deployment | Cameras | Recommended Disk | Retention  |
| ---------- | ------- | ---------------- | ---------- |
| Small      | 1-4     | 50GB             | 30 days    |
| Medium     | 5-8     | 100GB            | 30 days    |
| Large      | 8+      | 250GB+           | 14-30 days |

### Performance Tuning

~5 min read | [Full Guide](AI_SETUP.md#performance-tuning)

**GPU monitoring:**

```bash
# Real-time GPU utilization
nvidia-smi -l 1

# Detailed process view
nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
```

**Adjust polling intervals:**

| Interval | Use Case                   | Variable                    |
| -------- | -------------------------- | --------------------------- |
| 1-2s     | Active debugging           | `GPU_POLL_INTERVAL_SECONDS` |
| 5s       | Normal operation (default) | `GPU_POLL_INTERVAL_SECONDS` |
| 15-30s   | Heavy AI loads             | `GPU_POLL_INTERVAL_SECONDS` |

**Backend workers (production):**

```bash
# Adjust uvicorn workers based on CPU cores
# Default: 4 workers in docker-compose.prod.yml
```

### Upgrading

~8 min read | [Full Guide](getting-started/upgrading.md)

**Standard upgrade process:**

```bash
# 1. Backup
docker compose -f docker-compose.prod.yml down
cp .env backups/.env.$(date +%Y%m%d)

# 2. Pull updates
git fetch origin
git pull origin main

# 3. Update dependencies
uv sync --extra dev
cd frontend && npm install && cd ..

# 4. Run migrations
docker compose -f docker-compose.prod.yml up -d postgres
cd backend && alembic upgrade head && cd ..

# 5. Rebuild and start
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

**Rollback:**

```bash
git checkout v1.1.0  # Previous version
cp backups/.env.YYYYMMDD .env
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

---

## Common Tasks

### Quick Command Reference

**Service management:**

```bash
# Start all services (production)
docker compose -f docker-compose.prod.yml up -d

# Stop all services
docker compose -f docker-compose.prod.yml down

# View logs
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f backend

# Restart a service
docker compose -f docker-compose.prod.yml restart backend
```

**Health checks:**

```bash
# System health
curl http://localhost:8000/api/system/health

# AI services
curl http://localhost:8090/health   # RT-DETRv2
curl http://localhost:8091/health   # Nemotron

# Database
docker compose exec postgres pg_isready

# Redis
docker compose exec redis redis-cli ping
```

**GPU management:**

```bash
# GPU status
nvidia-smi

# GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv

# Kill GPU processes (emergency)
fuser -k /dev/nvidia*
```

**Database operations:**

```bash
# Run migrations
cd backend && alembic upgrade head

# Connect to database
docker compose exec postgres psql -U security -d security

# Backup
docker compose exec postgres pg_dump -U security security > backup.sql
```

**Container operations:**

```bash
# Shell into backend
docker compose exec backend bash

# Shell into Redis CLI
docker compose exec redis redis-cli

# Check resource usage
docker stats
```

### Ports Reference

| Service    | Port | Purpose                     |
| ---------- | ---- | --------------------------- |
| Frontend   | 80   | Web dashboard (production)  |
| Frontend   | 5173 | Web dashboard (development) |
| Backend    | 8000 | REST API + WebSocket        |
| RT-DETRv2  | 8090 | Object detection service    |
| Nemotron   | 8091 | LLM risk analysis service   |
| PostgreSQL | 5432 | Database                    |
| Redis      | 6379 | Cache + message broker      |

---

## Quick Reference

### Complete Environment Variable Reference

[Full Reference](admin-guide/configuration.md)

**Categories:**

- [Database](admin-guide/configuration.md#database-configuration)
- [AI Services](admin-guide/configuration.md#ai-service-endpoints)
- [Detection](admin-guide/configuration.md#detection-settings)
- [Batch Processing](admin-guide/configuration.md#batch-processing)
- [Retention](admin-guide/configuration.md#retention-settings)
- [GPU Monitoring](admin-guide/configuration.md#gpu-monitoring)
- [Rate Limiting](admin-guide/configuration.md#rate-limiting)
- [WebSocket](admin-guide/configuration.md#websocket-settings)
- [TLS/HTTPS](admin-guide/configuration.md#tlshttps-settings)
- [Notifications](admin-guide/configuration.md#notifications)

### Risk Levels

[Full Reference](reference/config/risk-levels.md)

| Level    | Score Range | Description                       |
| -------- | ----------- | --------------------------------- |
| Low      | 0-29        | Routine activity, no concern      |
| Medium   | 30-59       | Notable activity, worth reviewing |
| High     | 60-84       | Concerning activity, review soon  |
| Critical | 85-100      | Immediate attention required      |

---

## Troubleshooting

[Full Troubleshooting Guide](admin-guide/troubleshooting.md)

For a fast “health → fix” decision flow, use:

- [Troubleshooting Index](reference/troubleshooting/index.md) (includes a triage flowchart)

### Quick Diagnostics

```bash
# Comprehensive health check
curl http://localhost:8000/api/system/health

# AI service connectivity
curl http://localhost:8090/health   # RT-DETRv2
curl http://localhost:8091/health   # Nemotron
curl http://localhost:8092/health   # Florence-2 (optional)
curl http://localhost:8093/health   # CLIP (optional)
curl http://localhost:8094/health   # Enrichment (optional)

# GPU availability
nvidia-smi

# Container status
docker compose -f docker-compose.prod.yml ps

# Recent logs
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Common Issues

| Issue                      | Quick Fix                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------- |
| AI services unreachable    | Start with [Deployment Modes & AI Networking](operator/deployment-modes.md) to choose correct URLs |
| GPU out of memory          | Close other GPU applications, restart AI services                                                  |
| Database connection failed | Verify `DATABASE_URL`, check PostgreSQL is running                                                 |
| Redis auth failed          | Check `REDIS_PASSWORD` matches in .env, restart services. See [Redis Setup](operator/redis.md)     |
| WebSocket won't connect    | Check CORS settings, verify backend is healthy                                                     |
| Images not processing      | Check `FOSCAM_BASE_PATH`, enable `FILE_WATCHER_POLLING` for Docker Desktop                         |
| DLQ jobs accumulating      | Verify AI services are healthy, check [DLQ Management](operator/dlq-management.md)                 |
| Scene change false alerts  | Adjust threshold, see [Scene Change Detection](operator/scene-change-detection.md)                 |
| Service won't restart      | Check if disabled, use [Service Control](operator/service-control.md) to enable                    |

### Getting Help

When reporting issues, collect:

```bash
# System health
curl http://localhost:8000/api/system/health | jq

# GPU info
nvidia-smi

# Container status
docker compose -f docker-compose.prod.yml ps

# Recent logs
docker compose -f docker-compose.prod.yml logs --tail=100 backend
```

---

## See Also

- [User Hub](user-hub.md) - End-user documentation
- [Developer Hub](developer-hub.md) - Development and contribution
- [API Reference](reference/api/overview.md) - REST and WebSocket API documentation
- [Architecture Overview](architecture/overview.md) - System design and components
