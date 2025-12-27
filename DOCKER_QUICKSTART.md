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

| Service  | Port | URL                        | Health Check        |
| -------- | ---- | -------------------------- | ------------------- |
| Backend  | 8000 | http://localhost:8000      | /health             |
| API Docs | 8000 | http://localhost:8000/docs | -                   |
| Frontend | 5173 | http://localhost:5173      | / (Vite dev server) |
| Redis    | 6379 | redis://localhost:6379     | redis-cli ping      |

## 🔍 Health Checks

```bash
# Check all services
docker compose ps

# Check Backend health
curl http://localhost:8000/health

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
# Backup database
docker compose exec backend sqlite3 /app/data/security.db ".backup /app/data/backup.db"

# Copy to host
docker compose cp backend:/app/data/security.db ./backup.db
```

## 🔐 Environment Variables

Create `.env` file in project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Key variables:

- `DATABASE_URL` - SQLite database location
- `REDIS_URL` - Redis connection URL
- `DETECTOR_URL` - RT-DETRv2 service URL
- `LLM_URL` - Nemotron service URL
- `FOSCAM_BASE_PATH` - Camera uploads directory

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
# Copy from container to host
docker compose cp backend:/app/data/security.db ./backup.db

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

- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Frontend App: http://localhost:5173
- Redis Commander: `docker compose exec redis redis-cli` (CLI interface)

## ✅ Pre-flight Checklist

Before deploying:

- [ ] Docker is installed and running
- [ ] `.env` file is configured
- [ ] `/export/foscam` directory exists (or update FOSCAM_BASE_PATH)
- [ ] AI services are running (RT-DETRv2 on 8090, Nemotron on 8091)
- [ ] Ports 5173, 6379, and 8000 are available

Test deployment:

```bash
./scripts/test-docker.sh
```

If test passes, you're ready to go! 🎉
