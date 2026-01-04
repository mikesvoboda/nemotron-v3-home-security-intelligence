# Docker Deployment Guide

This guide covers deploying the Home Security Intelligence system using Docker Compose or Podman Compose.

## Deployment Architecture

![Docker Deployment Topology](images/deploy-docker-topology.png)

## Overview

The system consists of five main service groups:

1. **Backend** - FastAPI application (port 8000)
2. **Frontend** - React/Vite application (port 5173 dev, port 80 prod)
3. **Redis** - Cache and message broker (port 6379)
4. **PostgreSQL** - Database (port 5432)
5. **AI Services** - GPU-accelerated inference services:
   - RT-DETRv2 (8090)
   - Nemotron (8091)
   - Florence-2 (8092, optional)
   - CLIP (8093, optional)
   - Enrichment (8094, optional)

In production, all of the above are containerized (Docker/Podman). In development, it’s common to run the backend/frontend in containers and run the AI services on the host (GPU reasons).

> If you’re debugging “AI unreachable”, start with: `docs/operator/deployment-modes.md`.

## Container Runtime Options

| Runtime        | Platform              | License                          | Install                                       |
| -------------- | --------------------- | -------------------------------- | --------------------------------------------- |
| Docker Desktop | macOS, Windows, Linux | Paid (commercial >250 employees) | [docker.com](https://docker.com)              |
| Podman         | macOS, Linux          | Free (Apache 2.0)                | `brew install podman` or `dnf install podman` |
| Docker Engine  | Linux                 | Free                             | `apt install docker.io`                       |

This project supports all three. Podman is recommended for free, open-source deployment.

## Quick Start

### Docker (Development Mode)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Docker (Production Mode)

```bash
# Start all services with production configuration
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down
```

---

## Podman Setup (Free Alternative to Docker Desktop)

Podman is a free, daemonless container engine that runs the same OCI images as Docker.

### Install Podman

**macOS:**

```bash
# Install Podman and podman-compose
brew install podman podman-compose

# Initialize the Podman VM (required for macOS)
podman machine init

# Start the VM
podman machine start

# Verify installation
podman info
```

**Linux (Fedora/RHEL/CentOS):**

```bash
sudo dnf install podman podman-compose
```

**Linux (Ubuntu/Debian):**

```bash
sudo apt update
sudo apt install podman podman-compose
```

### Run with Podman

**Development:**

```bash
# Start services
podman-compose up -d

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

**Production:**

```bash
podman-compose -f docker-compose.prod.yml up -d
```

### Podman vs Docker Command Equivalents

| Docker                 | Podman                 |
| ---------------------- | ---------------------- |
| `docker compose up -d` | `podman-compose up -d` |
| `docker compose down`  | `podman-compose down`  |
| `docker compose logs`  | `podman-compose logs`  |
| `docker ps`            | `podman ps`            |
| `docker images`        | `podman images`        |
| `docker build`         | `podman build`         |

---

## Using Pre-built Images from GHCR

CI/CD automatically builds and pushes images to GitHub Container Registry (GHCR). Use these instead of building locally for faster deployment.

### Authenticate with GHCR

```bash
# Create a GitHub Personal Access Token with `read:packages` scope
# https://github.com/settings/tokens

# Docker login
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Podman login
echo $GITHUB_TOKEN | podman login ghcr.io -u YOUR_USERNAME --password-stdin
```

### Configure image location

The GHCR compose file supports these variables:

- `GHCR_OWNER`: your GitHub org/user (example: `your-org`)
- `GHCR_REPO`: your image namespace/repo (example: `home-security-intelligence`)
- `IMAGE_TAG`: image tag (example: `latest` or a commit SHA)

Example:

```bash
export GHCR_OWNER=your-org
export GHCR_REPO=home-security-intelligence
export IMAGE_TAG=latest
docker compose -f docker-compose.ghcr.yml up -d
```

### Deploy from GHCR

**Docker:**

```bash
# macOS with Docker Desktop
docker compose -f docker-compose.ghcr.yml up -d
```

**Podman on macOS:**

```bash
export AI_HOST=host.containers.internal
podman-compose -f docker-compose.ghcr.yml up -d
```

**Podman on Linux:**

```bash
export AI_HOST=$(hostname -I | awk '{print $1}')
export CAMERA_PATH=/path/to/your/cameras  # Adjust as needed
podman-compose -f docker-compose.ghcr.yml up -d
```

> Note: `docker-compose.ghcr.yml` runs the application stack (backend/frontend/postgres/redis). It assumes AI services are reachable externally (host-run or remote), so you must set `RTDETR_URL` / `NEMOTRON_URL` (and optionally `FLORENCE_URL` / `CLIP_URL` / `ENRICHMENT_URL`) correctly. See `docs/operator/deployment-modes.md`.

### Use a Specific Image Version

```bash
# Deploy a specific commit SHA instead of latest
export IMAGE_TAG=abc1234
docker compose -f docker-compose.ghcr.yml up -d
```

### Available Images

| Image                                                      | Description            |
| ---------------------------------------------------------- | ---------------------- |
| `ghcr.io/<org>/home-security-intelligence/backend:latest`  | FastAPI backend        |
| `ghcr.io/<org>/home-security-intelligence/frontend:latest` | React frontend (nginx) |

---

## Cross-Platform Host Resolution

This section applies when the **backend is containerized** but **AI is running on the host** (common with `docker-compose.yml`).

For production (`docker-compose.prod.yml`), the backend reaches AI services via compose DNS (`ai-detector`, `ai-llm`, etc.). See `docs/operator/deployment-modes.md`.

| Platform | Container Runtime | Host Resolution                  |
| -------- | ----------------- | -------------------------------- |
| macOS    | Docker Desktop    | `host.docker.internal` (default) |
| macOS    | Podman            | `host.containers.internal`       |
| Linux    | Docker Engine     | Host IP address                  |
| Linux    | Podman            | Host IP address                  |

### Configuration

`docker-compose.yml` and `docker-compose.ghcr.yml` use the `AI_HOST` environment variable to help a containerized backend reach host-run AI services:

```bash
# macOS with Docker Desktop (default, no action needed)
docker compose up -d

# macOS with Podman
export AI_HOST=host.containers.internal
podman-compose up -d

# Linux (Docker or Podman)
export AI_HOST=192.168.1.100  # Replace with your host IP
docker compose up -d
```

### Finding Your Host IP (Linux)

```bash
# Get primary IP
hostname -I | awk '{print $1}'

# Or use ip command
ip route get 1 | awk '{print $7}'
```

---

## Compose Files Reference

| File                      | Purpose                  | Builds Images?       |
| ------------------------- | ------------------------ | -------------------- |
| `docker-compose.yml`      | Development (hot reload) | Yes (local)          |
| `docker-compose.prod.yml` | Production (optimized)   | Yes (local)          |
| `docker-compose.ghcr.yml` | Production (pre-built)   | No (pulls from GHCR) |

---

## Testing Deployment

Run the automated deployment test script:

```bash
./scripts/test-docker.sh
```

Options:

- `--no-cleanup` - Leave containers running after test
- `--skip-build` - Skip docker compose build step
- `--help` - Show help message

The test script will:

1. Validate Docker is available and running
2. Validate docker-compose.yml syntax
3. Build Docker images
4. Start all services
5. Wait for services to become healthy (up to 2 minutes)
6. Test service endpoints (health checks, API, frontend)
7. Test inter-service communication
8. Show resource usage
9. Clean up (optional)

## Configuration Files

### Development (docker-compose.yml)

- Uses `Dockerfile` for each service
- Frontend runs Vite dev server (hot reload)
- Backend runs with auto-reload
- Minimal resource limits
- Includes health checks with service dependencies

### Production (docker-compose.prod.yml)

- Uses `Dockerfile.prod` for each service
- Frontend built and served via Nginx
- Backend runs with 4 workers
- Resource limits enforced
- Optimized health check intervals
- Redis persistence enabled (AOF)

---

## Backend Dockerfile Module Import Path Requirement

The backend uses **absolute imports** throughout the codebase (e.g., `from backend.api.middleware import AuthMiddleware`). This requires careful structuring in Docker to ensure Python can resolve these imports correctly.

### The Problem

When building the Docker image, if you copy files directly to the working directory:

```dockerfile
# INCORRECT - causes ModuleNotFoundError
WORKDIR /app
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This produces a directory structure of `/app/main.py`, `/app/api/`, `/app/core/`, etc. When Python tries to resolve `from backend.api.middleware import AuthMiddleware`, it fails because there is no `backend/` directory in the Python path.

### The Solution

Copy the application code to a subdirectory that matches the import structure:

```dockerfile
# CORRECT - matches import structure
WORKDIR /app

# Copy application code to backend subdirectory (for absolute imports)
COPY . ./backend/

# Use backend.main:app (not main:app)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This produces the correct structure: `/app/backend/main.py`, `/app/backend/api/`, `/app/backend/core/`, etc.

### Current Implementation

The `backend/Dockerfile.prod` implements this correctly:

```dockerfile
WORKDIR /app

# Copy application code to backend subdirectory (for absolute imports)
COPY . ./backend/

# ...

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

### Key Points

1. **COPY destination**: Use `COPY . ./backend/` to create the subdirectory structure
2. **CMD module path**: Use `backend.main:app` instead of `main:app`
3. **Import consistency**: All imports in the codebase use `backend.*` prefix
4. **PYTHONPATH**: No PYTHONPATH modification needed when structured correctly

### Verification

After building the image, verify the structure:

```bash
# Check directory structure
docker run --rm backend-prod ls -la /app/

# Verify imports work
docker run --rm backend-prod python -c "from backend.core import get_settings; print('OK')"
```

---

## Service Details

### Backend Service

**Development:**

- Image: Built from `backend/Dockerfile`
- Port: 8000
- Volumes:
  - `./backend/data:/app/data` - Application data (logs, runtime configs)
  - `/export/foscam:/cameras:ro` - Read-only camera uploads
- Health check: HTTP GET to `/health` endpoint
- Depends on: PostgreSQL and Redis services

**Production:**

- Image: Built from `backend/Dockerfile.prod` (multi-stage, non-root user)
- Workers: 4 uvicorn workers
- Resource limits: 2 CPU, 2GB RAM

### Frontend Service

**Development:**

- Image: Built from `frontend/Dockerfile`
- Port: 5173
- Command: `npm run dev --host`
- Health check: HTTP GET to root

**Production:**

- Image: Built from `frontend/Dockerfile.prod` (multi-stage with Nginx)
- Port: 80
- Static files served by Nginx with compression and caching
- Health check: HTTP GET to `/health` endpoint

### Redis Service

- Image: `redis:7-alpine`
- Port: 6379
- Volume: `redis_data` - Data persistence
- Health check: `redis-cli ping`
- Production: AOF persistence enabled

## Environment Variables

Create a `.env` file in the project root (use `.env.example` as template).

> **Note:** See [docs/RUNTIME_CONFIG.md](RUNTIME_CONFIG.md) for the complete environment variable reference.

```bash
# Camera Configuration
FOSCAM_BASE_PATH=/export/foscam

# Database (REQUIRED - no default password, run ./setup.sh to generate)
# Generate password: openssl rand -base64 32
DATABASE_URL=postgresql+asyncpg://security:<your-password>@postgres:5432/security

# Redis
REDIS_URL=redis://redis:6379

# AI Services (containerized with GPU passthrough)
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
FLORENCE_URL=http://localhost:8092
CLIP_URL=http://localhost:8093
ENRICHMENT_URL=http://localhost:8094

# Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30
DETECTION_CONFIDENCE_THRESHOLD=0.5

# Retention
RETENTION_DAYS=30

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

## Health Checks

All services include health checks:

### Redis

- Test: `redis-cli ping`
- Interval: 5s (dev) / 10s (prod)
- Timeout: 3s (dev) / 5s (prod)
- Retries: 5 (dev) / 3 (prod)

### Backend

- Test: HTTP GET to `http://localhost:8000/health`
- Interval: 10s (dev) / 30s (prod)
- Timeout: 5s (dev) / 10s (prod)
- Retries: 5 (dev) / 3 (prod)
- Start period: 30s (dev) / 40s (prod)

### Frontend

- Test: HTTP GET via wget
- Interval: 10s (dev) / 30s (prod)
- Timeout: 5s (dev) / 10s (prod)
- Retries: 5 (dev) / 3 (prod)
- Start period: 30s (dev) / 40s (prod)

## Service Dependencies

Services start in order based on health checks:

1. **Redis** starts first
2. **Backend** waits for Redis to be healthy
3. **Frontend** waits for Backend to be healthy

This ensures proper startup order and prevents connection errors.

## Networking

All services are connected via a custom bridge network `security-net`:

- Services can communicate using service names as hostnames
- Backend connects to Redis via `redis://redis:6379`
- Frontend connects to Backend via `http://backend:8000` (internal) or `http://localhost:8000` (from host)
- In development (`docker-compose.yml`), backend reaches host-run AI via `AI_HOST` (defaults to `host.docker.internal`).
- In production (`docker-compose.prod.yml`), backend reaches containerized AI via compose DNS (`ai-detector`, `ai-llm`, `ai-florence`, `ai-clip`, `ai-enrichment`).

## Volume Management

### Data Persistence

- **Backend data**: `./backend/data` - Application logs and runtime configs
- **PostgreSQL data**: `postgres_data` volume - Database persistence
- **Redis data**: `redis_data` volume - Cache and queue data
- **Camera uploads**: `/export/foscam` - Read-only mount (must exist on host)

### Cleanup

```bash
# Remove all containers and volumes
docker compose down -v

# Remove all containers but keep volumes
docker compose down
```

## Build Optimization

### .dockerignore Files

Both backend and frontend have `.dockerignore` files to exclude unnecessary files from build context:

**Backend excludes:**

- Virtual environments (.venv, venv)
- Python cache files (**pycache**, \*.pyc)
- Tests (tests/, \*.test.py)
- Documentation (docs/, \*.md except README.md)
- IDE files (.vscode, .idea)
- Database files (\*.db, data/)

**Frontend excludes:**

- node_modules/
- Build artifacts (dist/, build/)
- Tests (tests/, _.test.ts, _.spec.ts)
- Documentation (docs/, \*.md except README.md)
- IDE files (.vscode, .idea)

## Troubleshooting

### Services not becoming healthy

1. Check logs: `docker compose logs <service>`
2. Check service status: `docker compose ps`
3. Verify health check endpoint manually:

   ```bash
   # Backend
   curl http://localhost:8000/health

   # Redis
   docker compose exec redis redis-cli ping

   # Frontend (dev)
   curl http://localhost:5173
   # Frontend (prod)
   curl http://localhost:80
   ```

### Backend cannot connect to Redis

- Ensure Redis is healthy: `docker compose ps redis`
- Check Redis logs: `docker compose logs redis`
- Verify network: `docker network ls | grep security-net` (then inspect the actual `${project}_security-net` name if needed)

### Frontend cannot connect to Backend

- Ensure Backend is healthy: `docker compose ps backend`
- Check Backend logs: `docker compose logs backend`
- Verify environment variables in frontend: `docker compose exec frontend env | grep VITE`

### AI services not accessible

AI services run with GPU passthrough in production compose. Ensure they are:

1. Running: `docker ps --filter name=ai-` or `podman ps --filter name=ai-`
2. Healthy: Check container health status
3. GPU accessible: `nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv`

**Check AI container status:**

```bash
# List AI containers (Docker or Podman)
docker ps --filter name=ai-
# OR
podman ps --filter name=ai-

# Check logs
docker compose -f docker-compose.prod.yml logs ai-detector ai-llm ai-florence ai-clip ai-enrichment
# OR
podman-compose -f docker-compose.prod.yml logs ai-detector ai-llm ai-florence ai-clip ai-enrichment

# Test health endpoints
curl http://localhost:8090/health
curl http://localhost:8091/health
curl http://localhost:8092/health
curl http://localhost:8093/health
curl http://localhost:8094/health
```

If the backend is healthy but AI shows unreachable, it’s usually a URL mode mismatch. See `docs/operator/deployment-modes.md`.

### Insufficient resources

If containers are OOM (Out of Memory) or CPU throttled:

1. Check resource usage: `docker stats`
2. Adjust limits in `docker-compose.prod.yml`
3. Increase Docker daemon resources (Docker Desktop: Preferences → Resources)

### Permission issues with volumes

If database or camera files have permission errors:

```bash
# Fix backend data directory permissions
sudo chown -R $USER:$USER ./backend/data

# Verify camera directory exists and is readable
ls -la /export/foscam
```

### Podman-specific issues

**Podman machine not running (macOS):**

```bash
# Check machine status
podman machine list

# Start the machine
podman machine start

# If corrupted, recreate
podman machine rm
podman machine init
podman machine start
```

**podman-compose not found:**

```bash
# macOS
brew install podman-compose

# Linux (pip)
pip install podman-compose

# Or use podman compose (v4.1+)
podman compose up -d
```

**Volume mount permissions (Linux with SELinux):**

```bash
# Add :Z suffix for SELinux relabeling
# Edit compose file or use:
podman-compose up -d --userns=keep-id
```

**Container can't reach host services:**

```bash
# Docker - verify host.docker.internal resolves
docker exec <container> getent hosts host.docker.internal

# Podman - verify host.containers.internal resolves
podman exec <container> getent hosts host.containers.internal

# If not, use host IP directly
export AI_HOST=$(hostname -I | awk '{print $1}')
```

See also: `docs/operator/deployment-modes.md` (decision table + correct URLs for each mode).

## Manual Commands

### Start services

```bash
docker compose up -d
```

### Stop services

```bash
docker compose down
```

### Rebuild images

```bash
docker compose build --no-cache
```

### View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
```

### Execute commands in containers

```bash
# Backend shell
docker compose exec backend bash

# Redis CLI
docker compose exec redis redis-cli

# Frontend shell
docker compose exec frontend sh
```

### Inspect service health

```bash
docker compose ps
```

### Resource usage

```bash
docker stats
```

## Security Considerations

### Production Hardening

1. **Non-root users**: Production Dockerfiles run as non-root users
2. **Resource limits**: CPU and memory limits enforced
3. **Security headers**: Nginx adds security headers (X-Frame-Options, etc.)
4. **Read-only mounts**: Camera directory mounted read-only
5. **Network isolation**: Custom bridge network isolates services

### Additional Recommendations

1. Use Docker secrets for sensitive environment variables
2. Enable TLS/SSL for production (add reverse proxy like Traefik)
3. Regularly update base images for security patches
4. Scan images for vulnerabilities: `docker scan <image>`
5. Implement rate limiting on API endpoints
6. Use a proper authentication system (currently no auth for single-user MVP)

## Performance Tuning

### Backend

- Adjust uvicorn workers based on CPU cores: `--workers <N>`
- Tune database connection pool settings
- Enable Redis persistence based on data criticality

### Frontend

- Enable Nginx gzip compression (already configured)
- Add CDN for static assets
- Implement service worker for offline support

### Redis

- Tune maxmemory policy: `redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru`
- Use Redis Cluster for high availability
- Monitor memory usage and eviction stats

## Monitoring

### Health Checks

All services expose health endpoints:

- Backend: `http://localhost:8000/health`
- Frontend: `http://localhost:5173/` (dev) or `http://localhost:80/health` (prod)
- Redis: `docker compose exec redis redis-cli ping`

### Logs

```bash
# Stream all logs
docker compose logs -f

# Filter by service
docker compose logs -f backend

# Show last N lines
docker compose logs --tail=100 backend
```

### Metrics

Add monitoring stack (Prometheus + Grafana):

1. Add Prometheus scraping of backend `/metrics` endpoint
2. Add cAdvisor for container metrics
3. Add Redis exporter for Redis metrics
4. Create Grafana dashboards for visualization

## Backup and Recovery

### Database Backup

```bash
# Create PostgreSQL backup
docker compose exec -T postgres pg_dump -U security -d security > backup.sql

# Or use compressed format
docker compose exec -T postgres pg_dump -U security -d security -F c > backup.dump

# Tip: keep backups outside the repo and outside container volumes.
```

### Redis Backup

```bash
# Trigger background save
docker compose exec redis redis-cli BGSAVE

# Copy RDB file to host
docker compose cp redis:/data/dump.rdb ./redis-backup.rdb
```

### Restore from Backup

```bash
# Stop services
docker compose down

# Restore PostgreSQL database (example for .sql format)
docker compose -f docker-compose.prod.yml up -d postgres
docker compose exec -T postgres psql -U security -d security < backup.sql

# Replace Redis data
docker compose cp redis-backup.rdb redis:/data/dump.rdb

# Restart services
docker compose up -d
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Docker Build and Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build images
        run: docker compose build

      - name: Run deployment test
        run: ./scripts/test-docker.sh --no-cleanup

      - name: Show logs on failure
        if: failure()
        run: docker compose logs

      - name: Cleanup
        if: always()
        run: docker compose down -v
```

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Podman Documentation](https://podman.io/docs)
- [Podman Compose](https://github.com/containers/podman-compose)
- [GHCR Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Nginx Configuration](https://nginx.org/en/docs/)
