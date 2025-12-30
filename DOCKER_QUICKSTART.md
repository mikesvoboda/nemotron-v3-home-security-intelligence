# Docker Quick Start Guide

Quick reference for Docker Compose deployment.

## 🚀 Quick Commands

### Development

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build
```

### Production

```bash
# Start production services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop services
docker compose -f docker-compose.prod.yml down
```

### Testing

```bash
# Full deployment test
./scripts/test-docker.sh

# Test without cleanup
./scripts/test-docker.sh --no-cleanup

# Test using existing images
./scripts/test-docker.sh --skip-build
```

## 📋 Service Endpoints

### Development (docker-compose.yml)

| Service  | Port | URL                        | Health Check             |
| -------- | ---- | -------------------------- | ------------------------ |
| Backend  | 8000 | http://localhost:8000      | /api/system/health/ready |
| API Docs | 8000 | http://localhost:8000/docs | -                        |
| Frontend | 5173 | http://localhost:5173      | / (Vite dev server)      |
| Redis    | 6379 | redis://localhost:6379     | redis-cli ping           |

### Production (docker-compose.prod.yml)

| Service  | Port | URL                         | Health Check             |
| -------- | ---- | --------------------------- | ------------------------ |
| Backend  | 8000 | http://localhost:8000       | /api/system/health/ready |
| API Docs | 8000 | http://localhost:8000/docs  | -                        |
| Frontend | 80   | http://localhost            | / (Nginx)                |
| Redis    | 6379 | redis://localhost:6379      | redis-cli ping           |
| Postgres | 5432 | postgresql://localhost:5432 | pg_isready               |

> **Note:** In production, the frontend runs on Nginx (port 80 inside container, exposed as port 80 by default).
> You can change the host port with `FRONTEND_PORT` environment variable.

## 🔍 Health Checks

The backend provides two health check endpoints for different purposes:

### Liveness vs Readiness Probes

| Endpoint                   | Purpose                                  | When to Use                                            |
| -------------------------- | ---------------------------------------- | ------------------------------------------------------ |
| `/api/system/health/live`  | Checks if the process is running         | Container restart decisions                            |
| `/api/system/health/ready` | Checks if all dependencies are healthy   | Traffic routing decisions (used by Docker healthcheck) |
| `/api/system/health`       | Detailed health status with all services | Debugging and monitoring dashboards                    |

**Key differences:**

- **Liveness (`/live`)**: Minimal check - always returns 200 if the process is up. Use this for Kubernetes/Docker liveness probes to determine if the container needs restarting.
- **Readiness (`/ready`)**: Full dependency check - verifies database, Redis, and AI services are healthy. Use this for Kubernetes/Docker readiness probes to determine if traffic should be routed to this instance. **Docker healthchecks use this endpoint.**
- **Health (`/health`)**: Same checks as readiness but with detailed service status information.

```bash
# Check all services
docker compose ps

# Check Backend readiness (used by Docker healthcheck)
curl http://localhost:8000/api/system/health/ready

# Check Backend liveness (basic process check)
curl http://localhost:8000/api/system/health/live

# Check Backend detailed health status
curl http://localhost:8000/api/system/health

# Check Redis
docker compose exec redis redis-cli ping

# Check Frontend
curl http://localhost:5173
```

## 📊 Monitoring

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f redis
docker compose logs -f frontend

# Show resource usage
docker stats

# Show container details
docker compose ps
```

## 🛠️ Troubleshooting

### Services not starting

```bash
# Check service status
docker compose ps

# View error logs
docker compose logs

# Restart specific service
docker compose restart backend
```

### Reset everything

```bash
# Stop and remove all containers and volumes
docker compose down -v

# Rebuild from scratch
docker compose build --no-cache
docker compose up -d
```

### Database issues

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U security -d security

# Backup database
docker compose exec postgres pg_dump -U security security > backup.sql

# Restore database
docker compose exec -T postgres psql -U security security < backup.sql
```

## 🔐 Environment Variables

Create `.env` file in project root (copy from `.env.example`):

```bash
cp .env.example .env
```

### Core Configuration

| Variable       | Default                                                          | Description                             |
| -------------- | ---------------------------------------------------------------- | --------------------------------------- |
| `DATABASE_URL` | `postgresql+asyncpg://security:password@localhost:5432/security` | PostgreSQL database URL (required)      |
| `REDIS_URL`    | `redis://localhost:6379/0`                                       | Redis connection URL                    |
| `RTDETR_URL`   | `http://localhost:8090`                                          | RT-DETRv2 object detection service URL  |
| `NEMOTRON_URL` | `http://localhost:8091`                                          | Nemotron LLM risk reasoning service URL |

### Camera Path Configuration

There are two related but distinct path variables:

| Variable           | Used In            | Default          | Description                                                                           |
| ------------------ | ------------------ | ---------------- | ------------------------------------------------------------------------------------- |
| `CAMERA_PATH`      | docker-compose.yml | `/export/foscam` | **Host machine path** - where camera images are stored on your host                   |
| `FOSCAM_BASE_PATH` | Backend config     | `/cameras`       | **Container internal path** - where the backend looks for images inside the container |

**How they work together:**

```yaml
# In docker-compose.yml:
volumes:
  - ${CAMERA_PATH:-/export/foscam}:/cameras:ro # Host path -> Container path

environment:
  - FOSCAM_BASE_PATH=/cameras # Backend looks here (inside container)
```

**Common scenarios:**

1. **Default setup** (images at `/export/foscam` on host):

   - No changes needed, defaults work

2. **Custom host path** (e.g., images at `/mnt/cameras` on host):

   ```bash
   export CAMERA_PATH=/mnt/cameras
   docker compose up -d
   ```

3. **Different container mount point** (advanced):
   - Change both the volume mount and `FOSCAM_BASE_PATH` to match

## 📁 Important Files

| File                        | Purpose                                |
| --------------------------- | -------------------------------------- |
| `docker-compose.yml`        | Development configuration              |
| `docker-compose.prod.yml`   | Production configuration               |
| `backend/Dockerfile`        | Backend development image              |
| `backend/Dockerfile.prod`   | Backend production image (multi-stage) |
| `frontend/Dockerfile`       | Frontend development image             |
| `frontend/Dockerfile.prod`  | Frontend production image (Nginx)      |
| `scripts/test-docker.sh`    | Automated deployment test              |
| `docs/DOCKER_DEPLOYMENT.md` | Comprehensive deployment guide         |

## 🎯 Common Tasks

### View container shell

```bash
# Backend
docker compose exec backend bash

# Frontend
docker compose exec frontend sh

# Redis CLI
docker compose exec redis redis-cli
```

### Run commands in containers

```bash
# Run pytest in backend
docker compose exec backend pytest

# Run npm commands in frontend
docker compose exec frontend npm test
```

### Copy files to/from containers

```bash
# Backup PostgreSQL to host
docker compose exec postgres pg_dump -U security security > backup.sql

# Copy from host to container
docker compose cp ./config.json backend:/app/config.json
```

## 🚨 Emergency Commands

### Stop everything immediately

```bash
docker compose down --remove-orphans
```

### Remove all Docker resources

```bash
# ⚠️ WARNING: This removes ALL Docker resources on the system
docker system prune -a --volumes
```

### Force remove stuck containers

```bash
# Stop all containers
docker stop $(docker ps -q)

# Remove all containers
docker rm $(docker ps -aq)
```

## 📖 Documentation

- **Full deployment guide:** `docs/DOCKER_DEPLOYMENT.md`
- **Verification summary:** `docs/DOCKER_VERIFICATION_SUMMARY.md`
- **Project instructions:** `CLAUDE.md`
- **Agent guide:** `AGENTS.md`

## 🔗 Quick Links

**Development:**

- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend App: http://localhost:5173

**Production:**

- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend App: http://localhost (port 80)

**Utilities:**

- Redis CLI: `docker compose exec redis redis-cli`
- PostgreSQL: `docker compose exec postgres psql -U security -d security`

## ✅ Pre-flight Checklist

Before deploying:

- [ ] Docker is installed and running
- [ ] `.env` file is configured
- [ ] Camera images directory exists (default: `/export/foscam`, or set `CAMERA_PATH`)
- [ ] AI services are running (RT-DETRv2 on 8090, Nemotron on 8091)
- [ ] Required ports are available:
  - Development: 5173, 6379, 8000
  - Production: 80, 5432, 6379, 8000

Test deployment:

```bash
./scripts/test-docker.sh
```

If test passes, you're ready to go! 🎉
