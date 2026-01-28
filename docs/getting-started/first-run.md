---
title: First Run
description: Starting the system and verifying everything works
source_refs:
  - ai/start_detector.sh:1
  - ai/start_detector.sh:12-13
  - ai/start_detector.sh:31-37
  - ai/start_llm.sh:1
  - ai/start_llm.sh:14-16
  - ai/start_llm.sh:36-43
  - docker-compose.prod.yml:1
  - docker-compose.prod.yml:46-81
  - docker-compose.prod.yml:109-143
---

# First Run

![First Run Hero](../images/first-run-hero.png)

_AI-generated visualization of system startup sequence showing container initialization, model loading, camera connections, and dashboard ready state._

This guide walks you through starting the system for the first time and verifying all components are working.

<!-- Nano Banana Pro Prompt:
"Technical illustration of system startup sequence,
multiple service containers connecting and synchronizing,
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

---

## Choose Your Deployment Mode

Use this decision tree to determine the best deployment path for your setup:

![Quickstart Decision Tree showing deployment path selection: Do you have NVIDIA Container Toolkit installed? If yes, use Production Mode with all services in containers. If no or prefer native AI for development, use Development Mode with host-run AI servers and containerized application services](../images/quickstart-decision-tree.png)

_Quickstart decision tree: Choose Production Mode for simplest setup with everything containerized, or Development Mode for faster AI iteration with native GPU access._

---

There are two deployment paths. Choose the one that fits your setup:

| Mode           | AI Services       | Use Case                                 | Docker Compose File       |
| -------------- | ----------------- | ---------------------------------------- | ------------------------- |
| **Production** | Run in containers | Simplest setup, everything containerized | `docker-compose.prod.yml` |

> **Important:** Do NOT mix host-run AI servers with `docker-compose.prod.yml`. This causes port conflicts on 8090–8094.

---

## Option A: Production Mode (Recommended)

All services run in containers, including GPU-accelerated AI servers.

### Prerequisites

- NVIDIA GPU with `nvidia-container-toolkit` installed
- AI model storage configured (see `docs/operator/ai-installation.md`)

### Start Everything

```bash
# Docker
docker compose -f docker-compose.prod.yml up -d

# OR Podman
podman-compose -f docker-compose.prod.yml up -d
```

**What starts** ([`docker-compose.prod.yml`](../../docker-compose.prod.yml:1)):

| Service       | Port         | Purpose                                            |
| ------------- | ------------ | -------------------------------------------------- |
| PostgreSQL    | 5432         | Database                                           |
| Redis         | 6379         | Queues + pub/sub                                   |
| ai-yolo26     | 8095         | YOLO26 object detection                            |
| ai-llm        | 8091         | Nemotron LLM risk analysis                         |
| ai-florence   | 8092         | Florence-2 (optional)                              |
| ai-clip       | 8093         | CLIP (optional)                                    |
| ai-enrichment | 8094         | Enrichment (optional)                              |
| Backend       | 8000         | FastAPI + WebSocket                                |
| Frontend      | 5173 (HTTP)  | React dashboard via nginx                          |
| Frontend      | 8443 (HTTPS) | React dashboard via nginx (SSL enabled by default) |

> **Port Note:** The frontend runs nginx serving the built React app. HTTP on port 5173 (configurable via `FRONTEND_PORT`), HTTPS on port 8443 (configurable via `FRONTEND_HTTPS_PORT`). SSL is enabled by default with auto-generated self-signed certificates.

### Verify Production Deployment

```bash
# Docker
docker compose -f docker-compose.prod.yml ps

# OR Podman
podman-compose -f docker-compose.prod.yml ps

# Expected: All services "healthy" or "running"
NAME                      STATUS
security-postgres-1       healthy
security-redis-1          healthy
security-ai-yolo26-1    healthy
security-ai-llm-1         healthy
security-backend-1        healthy
security-frontend-1       healthy
```

### Access Dashboard

Open **[http://localhost:5173](http://localhost:5173)** (HTTP) or **[https://localhost:8443](https://localhost:8443)** (HTTPS)

> **HTTPS Note:** SSL is enabled by default. The first time you access via HTTPS, your browser will show a certificate warning because the certificate is self-signed. Accept the warning to proceed. For trusted certificates, see the [SSL/HTTPS Configuration Guide](../development/ssl-https.md).

---

## Option B: Development Mode (Host AI)

AI servers run natively on the host for faster iteration. Application services run in containers.

![Development Mode Architecture](../images/first-run-devmode.png)

_Development mode: AI servers run natively on the host, application services run in containers._

> **Why host AI servers?** Faster restart times during model development, easier debugging, and simpler GPU access without container runtime configuration.

### Step 1: Start AI Servers

Open **two separate terminal windows** for the AI servers.

#### Terminal 1: YOLO26 Detection Server

```bash
cd home-security-intelligence
./ai/start_detector.sh
```

**What happens** ([`ai/yolo26/model.py`](../../ai/yolo26/model.py)):

- Loads YOLO26 via HuggingFace Transformers (`YOLO26_MODEL_PATH`)
- Starts HTTP server on port 8095
- Uses ~4GB VRAM

**Expected output:**

```
Starting YOLO26 Detection Server...
Model directory: /path/to/ai/yolo26
Port: 8095
Expected VRAM usage: ~4GB
INFO:     Uvicorn running on http://0.0.0.0:8095
```

#### Terminal 2: Nemotron LLM Server

```bash
cd home-security-intelligence
./ai/start_llm.sh
```

**What happens** ([`ai/start_llm.sh:36-43`](../../ai/start_llm.sh:36)):

- Loads the Nemotron GGUF model via llama.cpp
- Starts HTTP server on port 8091 ([line 16](../../ai/start_llm.sh:16))
- **Production**: Nemotron-3-Nano-30B (~14.7GB VRAM, 128K context)
- **Development**: Nemotron Mini 4B (~3GB VRAM, 4K context)

**Expected output (production):**

```
Starting Nemotron LLM Server via llama.cpp...
Model: /export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf
Port: 8091
Context size: 131072
GPU layers: 99 (all layers)
llama server listening at http://0.0.0.0:8091
```

#### Verify AI Servers

```bash
# Check YOLO26
curl http://localhost:8095/health
# Expected: JSON describing model + CUDA status

# Check Nemotron
curl http://localhost:8091/health
# Expected: {"status": "ok"}
```

### Step 2: Start Application Stack

In a **third terminal**, set the AI host and start containers:

```bash
# macOS with Docker Desktop (default, no export needed)
docker compose -f docker-compose.prod.yml up -d

# macOS with Podman
export AI_HOST=host.containers.internal
podman-compose -f docker-compose.prod.yml up -d

# Linux with Docker
docker compose -f docker-compose.prod.yml up -d

# Linux with Podman (use your host IP)
export AI_HOST=192.168.1.100  # Replace with your IP
podman-compose -f docker-compose.prod.yml up -d
```

> **Note:** When running AI servers natively on the host, the backend container connects to them via `AI_HOST`.

**What starts** ([`docker-compose.prod.yml`](../../docker-compose.prod.yml:1) without AI services, or start AI separately):

| Service    | Port         | Purpose                                            |
| ---------- | ------------ | -------------------------------------------------- |
| PostgreSQL | 5432         | Database                                           |
| Redis      | 6379         | Queues + pub/sub                                   |
| Backend    | 8000         | FastAPI + WebSocket                                |
| Frontend   | 5173 (HTTP)  | React dashboard via nginx                          |
| Frontend   | 8443 (HTTPS) | React dashboard via nginx (SSL enabled by default) |

### Verify Development Deployment

```bash
# Docker
docker compose -f docker-compose.prod.yml ps

# OR Podman
podman-compose -f docker-compose.prod.yml ps

# Expected: All services "healthy" or "running"
NAME                    STATUS
security-postgres-1     healthy
security-redis-1        healthy
security-backend-1      healthy
security-frontend-1     healthy
```

### Access Dashboard

Open **[http://localhost:5173](http://localhost:5173)** (HTTP) or **[https://localhost:8443](https://localhost:8443)** (HTTPS)

---

## Post-Startup Verification

After starting with either mode, verify all services are communicating:

### Backend Health Check

```bash
# Backend health (checks all dependencies)
curl http://localhost:8000/api/system/health
```

**Expected response:**

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "detection_service": "available",
  "llm_service": "available"
}
```

### Individual Health Endpoints

```bash
# Database readiness
curl http://localhost:8000/api/system/health/ready

# GPU Stats (if AI servers running)
curl http://localhost:8000/api/system/gpu
```

---

## Configure Your First Camera

1. **Via Dashboard**: Navigate to Settings > Cameras > Add Camera

2. **Via API**:

   ```bash
   curl -X POST http://localhost:8000/api/cameras \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Front Door",
       "folder_path": "front_door",
       "status": "active"
     }'
   ```

3. **Configure FTP**: Point your camera to upload to:
   - Host: Your server IP
   - Path: `/export/foscam/front_door/` (or your `FOSCAM_BASE_PATH`)

---

## Viewing Logs

### Production Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f backend

# OR Podman
podman-compose -f docker-compose.prod.yml logs -f
podman-compose -f docker-compose.prod.yml logs -f backend
```

### Development Mode

AI server logs appear in the terminal windows where you started them.

```bash
# Docker
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f backend

# OR Podman
podman-compose -f docker-compose.prod.yml logs -f
podman-compose -f docker-compose.prod.yml logs -f backend
```

---

## Stopping the System

### Production Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml down -v  # Full cleanup (removes volumes)

# OR Podman
podman-compose -f docker-compose.prod.yml down
podman-compose -f docker-compose.prod.yml down -v  # Full cleanup (removes volumes)
```

### Development Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml down

# OR Podman
podman-compose -f docker-compose.prod.yml down

# Stop AI Servers: Press Ctrl+C in each terminal
```

---

## Troubleshooting

### AI servers won't start

```bash
# Check GPU availability
nvidia-smi

# Check model files exist
ls -la ai/nemotron/*.gguf
# YOLO26 weights are downloaded to HuggingFace cache; use /health to confirm model_loaded=true

# Check port availability
lsof -i :8095
lsof -i :8091
```

### Port conflict on 8090/8091

This happens when you mix host AI servers with `docker-compose.prod.yml`.

**Solution:** Choose one path:

- **Production:** Stop host AI servers, use `docker-compose.prod.yml` only
- **Development:** Run AI servers natively on the host and configure `AI_HOST` for the backend container

### Backend can't reach AI services

```bash
# From inside container - Docker
docker exec security-backend-1 curl http://host.docker.internal:8095/health

# From inside container - Podman
podman exec security-backend-1 curl http://host.containers.internal:8095/health

# Check AI_HOST is set correctly
echo $AI_HOST
```

### Database connection issues

```bash
# Docker
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml logs postgres

# OR Podman
podman-compose -f docker-compose.prod.yml ps postgres
podman-compose -f docker-compose.prod.yml logs postgres
```

### Frontend not loading

```bash
# Check nginx logs (production) - Docker or Podman
docker compose -f docker-compose.prod.yml logs frontend
# OR
podman-compose -f docker-compose.prod.yml logs frontend

# Verify backend is healthy
curl http://localhost:8000/api/system/health
```

---

## Next Steps

System is running. Continue with:

- **[Dashboard Guide](../ui/dashboard.md)** - Learn to use the dashboard
- **[Configuration Reference](../reference/config/env-reference.md)** - Customize settings
- **[Upgrading](upgrading.md)** - Future version upgrades
