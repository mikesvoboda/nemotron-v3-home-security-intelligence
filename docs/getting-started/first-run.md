---
title: First Run
description: Starting the system and verifying everything works
source_refs:
  - ai/start_detector.sh:1
  - ai/start_detector.sh:12-13
  - ai/start_detector.sh:26-30
  - ai/vlm/Dockerfile:138-139
  - docker-compose.prod.yml:1
  - docker-compose.prod.yml:44-118
  - docker-compose.prod.yml:134-265
  - docker-compose.prod.yml:348-420
  - docker-compose.prod.yml:667-700
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

Everything runs from one file, `docker-compose.prod.yml`. The only choice is whether the detector also runs on your host for debugging:

| Mode                  | AI services                                                           | Use case                                             |
| --------------------- | --------------------------------------------------------------------- | ---------------------------------------------------- |
| **Production**        | `ai-gateway` and `ai-vlm` both in containers                          | The normal path — simplest, everything containerized |
| **Host-run detector** | `./ai/start_detector.sh` on the host, `ai-vlm` still in its container | Debugging a detector model outside a container       |

![Quickstart decision tree: deployment path selection](../images/quickstart-decision-tree.png)

_The containerized path: application services and both AI services come up from one compose file._

> **Port collision:** `./ai/start_detector.sh` binds **8090** (`YOLO26_PORT` overrides it) and `ai-gateway` publishes the same host port, so run one or the other — not both.

---

## Option A: Production Mode (Recommended)

All services run in containers, including GPU-accelerated AI servers.

### Prerequisites

- NVIDIA GPU with `nvidia-container-toolkit` installed
- AI model storage configured, including the VLM weight pair under `${AI_MODELS_PATH}/vlm` (see [Installation](installation.md))
- `.env` and `docker-compose.override.yml` written by `python setup.py` (see [Installation](installation.md))

### Start Everything

Add `--profile vlm` — the reasoning serve sits behind that profile, and a plain `up -d` leaves it out:

```bash
# Docker
docker compose -f docker-compose.prod.yml --profile vlm up -d

# OR Podman
podman compose -f docker-compose.prod.yml --profile vlm up -d
```

**What starts** ([`docker-compose.prod.yml`](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/docker-compose.prod.yml)) — 21 services; the ones you interact with day one:

| Service    | Host port           | Purpose                                                  |
| ---------- | ------------------- | -------------------------------------------------------- |
| postgres   | 5432                | Database                                                 |
| redis      | 6379                | Queues + pub/sub                                         |
| ai-gateway | 8090 (metrics 8002) | Triton + FastAPI: the `/yolo26` and `/enrich-lt` routers |
| ai-vlm     | 8098                | llama.cpp reasoning serve (compose profile `vlm`)        |
| go2rtc     | 1984 / 8555         | Camera stream relaying                                   |
| backend    | 8000                | FastAPI + WebSocket                                      |
| frontend   | 8080 / 8444         | React dashboard via nginx (HTTP / HTTPS)                 |

The rest is the observability stack (prometheus, grafana on 3002, loki, tempo, alertmanager, pyroscope, alloy, the exporters) plus `foscam-init`, a one-shot job that prepares the camera directory.

> **Port Note:** Every service binds `127.0.0.1` only, except the frontend, which listens on all interfaces. The dashboard is on **port 8080 (HTTP)** by default, configurable via `FRONTEND_HTTP_PORT`, and **port 8444 (HTTPS)** when enabled via `SSL_ENABLED=true`, configurable via `FRONTEND_HTTPS_PORT`. The HTTPS listener serves auto-generated self-signed certificates; the backend's own AI calls go to the gateway over compose DNS, not through these ports.

### Verify Production Deployment

```bash
# Docker
docker compose -f docker-compose.prod.yml ps

# OR Podman
podman compose -f docker-compose.prod.yml ps

# Expected: every service "Up (healthy)" (or the one-shot foscam-init "Completed"),
# and ai-vlm listed too — `ps` needs the same --profile vlm to show it.
# The two AI containers load the slowest: ai-vlm's healthcheck allows a 120 s
# start period (ai/vlm/Dockerfile:138-139) and ai-gateway's allows 180 s
# (docker-compose.prod.yml:404). Re-run until everything is healthy.
```

### Register the First Admin

A fresh install serves nothing useful until you create the first account. The API returns **503** for every route except setup, health, and metrics (SetupGuardMiddleware) until an admin exists.

Open the dashboard — it will show the setup page — and register the first admin account there, or do it via the API:

```bash
# Confirm setup is pending
curl -s http://localhost:8000/api/auth/setup-status

# Register the first admin (username: 3-50 chars of letters/digits/_/-;
# password: 8+ chars with an uppercase letter, a lowercase letter, and a digit)
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "you@example.com", "password": "<choose-one>"}'
```

### Access Dashboard

Open **[http://localhost:8080](http://localhost:8080)** (HTTP), or **[https://localhost:8444](https://localhost:8444)** (HTTPS, if `SSL_ENABLED=true`).

> **HTTPS Note:** SSL is **off by default** (`SSL_ENABLED=false` in the compose file). Enable it in `.env` and recreate the frontend container to get HTTPS with auto-generated self-signed certificates. Your browser will show a certificate warning because the certificate is self-signed — accept it to proceed. For trusted certificates, see the [SSL/HTTPS Configuration Guide](../developer/ssl-https.md).

---

## Option B: Development Mode (Host-Run Detector)

The detector runs natively on the host for faster iteration; everything else, reasoning included, runs in containers.

![Development Mode Architecture](../images/first-run-devmode.png)

_Development mode: the detector runs natively on the host, application services and `ai-vlm` run in containers._

> **Why a host-run detector?** Faster restart times while iterating on a detection model, and GPU access without container runtime configuration. It is a debug path: the prod detector is Triton inside `ai-gateway`.

> **Scope:** One script exists for this: `./ai/start_detector.sh`, which stands in for the gateway's `/yolo26` router. There is no launcher script for a host-run reasoning serve — if you want one, run your own `llama-server` build against the GGUF pair and point `AI_VLM_URL` at it; most people leave reasoning in the `ai-vlm` container and run only the detector on the host.

### Step 1: Start the Detector on the Host

```bash
cd nemotron-v3-home-security-intelligence
./ai/start_detector.sh
```

**What happens** ([`ai/yolo26/model.py`](https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence/blob/main/ai/yolo26/model.py)):

- Runs `ai/yolo26/model.py` on the host, loading the weights named by `YOLO26_MODEL_PATH`
- Listens on port **8090** (`YOLO26_PORT` overrides; the script exports `PORT`)
- Reports ~4GB VRAM

**Expected output** (the script's own lines, `ai/start_detector.sh:22-30`):

```
Starting YOLO26v2 Detection Server...
Model directory: /path/to/repo/ai/yolo26
Port: 8090
Expected VRAM usage: ~4GB
```

#### Verify the detector

```bash
# Root path — this server has no /yolo26 prefix and is the only server in the
# tree that answers with a `device` field ("cuda:0" or "cpu")
curl http://localhost:8090/health
```

### Step 2: Point the Stack at the Host Detector, Then Start It

The backend reaches AI services purely through URL variables from `.env` — there is no `AI_HOST` variable. For a host-run detector:

```bash
# In .env — leave AI_VLM_URL at http://ai-vlm:8098 and keep using the vlm profile
YOLO26_URL=http://host.docker.internal:8090   # Docker Desktop, or your host IP
                                              # Podman: http://host.containers.internal:8090
```

With `YOLO26_URL` set this way the detector dials that URL directly; `USE_AI_GATEWAY=true` would instead route it through `{AI_GATEWAY_URL}/yolo26`, which is what compose sets for the containerized path.

> **Podman on Linux:** `host.containers.internal` resolves inside the default Podman network; if it doesn't on your host, use the host's LAN IP (e.g. `http://192.168.1.100:8090`).

Then start the services **without `ai-gateway`**, so it does not fight your host server for port 8090 (`ai-vlm` needs the profile named):

```bash
# Docker
docker compose -f docker-compose.prod.yml --profile vlm up -d \
  postgres redis go2rtc backend frontend ai-vlm

# OR Podman
podman compose -f docker-compose.prod.yml --profile vlm up -d \
  postgres redis go2rtc backend frontend ai-vlm
```

### Verify the Development Deployment

```bash
# Docker
docker compose -f docker-compose.prod.yml ps

# OR Podman
podman compose -f docker-compose.prod.yml ps

# Expected: the services you started are "Up (healthy)". Use `ps` rather than
# pattern-matching container names — compose derives container names from the
# project directory unless a service pins container_name (e.g. hsi-go2rtc).
```

### Access Dashboard

Open **[http://localhost:8080](http://localhost:8080)** (HTTP) or **[https://localhost:8444](https://localhost:8444)** (HTTPS) — same as production. Register the first admin on first boot as described above.

---

## Post-Startup Verification

After starting with either mode, verify all services are communicating:

### Backend Health Check

```bash
# Backend health (checks all dependencies)
curl http://localhost:8000/api/system/health
```

**Expected response** (shape per the backend's `HealthResponse` schema — service names are keys in `services`):

```json
{
  "status": "healthy",
  "services": {
    "database": { "status": "healthy" },
    "redis": { "status": "healthy" },
    "ai": { "status": "healthy" }
  },
  "timestamp": "2026-09-22T12:00:00Z",
  "recent_events": [],
  "memory": { "rss_mb": 250.1 }
}
```

The endpoint returns HTTP 200 when healthy and 503 when degraded or unhealthy.

### Individual Health Endpoints

```bash
# Readiness probe (fast)
curl http://localhost:8000/api/system/health/ready

# Per-AI-service status
curl http://localhost:8000/api/health/ai-services

# GPU Stats
curl http://localhost:8000/api/system/gpu
```

---

## Configure Your First Camera

You usually don't need to register cameras at all: the backend's file watcher **auto-creates** a camera record the first time it sees a new image under any subfolder of the camera root. To set it up:

1. **Point your camera's FTP** at `<FOSCAM_BASE_PATH>/<folder>/` on the host — by default `/export/foscam/front_door/`. On the host that is your FTP destination; inside the backend container the same directory is mounted at `/cameras/front_door` (compose always mounts the camera root at `/cameras`).

2. **Via Dashboard** (to review or edit): Settings → Cameras (`/settings/cameras`).

3. **Via API** (cameras are matched by folder path, so use the path as the backend sees it):

   ```bash
   curl -X POST http://localhost:8000/api/cameras \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Front Door",
       "folder_path": "/cameras/front_door",
       "status": "online"
     }'
   ```

---

## Viewing Logs

### Production Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml logs -f
docker compose -f docker-compose.prod.yml logs -f backend

# OR Podman
podman compose -f docker-compose.prod.yml logs -f
podman compose -f docker-compose.prod.yml logs -f backend
```

### Development Mode

AI server logs appear in the terminal windows where you started them.

```bash
# Docker
docker compose -f docker-compose.prod.yml logs -f backend

# OR Podman
podman compose -f docker-compose.prod.yml logs -f backend
```

---

## Stopping the System

### Production Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml down -v  # Full cleanup (removes volumes)

# OR Podman
podman compose -f docker-compose.prod.yml down
podman compose -f docker-compose.prod.yml down -v  # Full cleanup (removes volumes)
```

### Development Mode

```bash
# Docker
docker compose -f docker-compose.prod.yml down

# OR Podman
podman compose -f docker-compose.prod.yml down

# Stop AI Servers: Press Ctrl+C in each terminal
```

---

## Troubleshooting

### AI servers won't start

```bash
# Check GPU availability
nvidia-smi

# Check the weights the host server wants (it fetches via the HuggingFace cache)
ls -la /export/ai_models/model-zoo/yolo26/

# Port availability: ai-gateway publishes 8090, the VLM serve publishes 8098
lsof -i :8090
lsof -i :8098
```

### Port conflict on 8090

This happens when you run `./ai/start_detector.sh` while the `ai-gateway` container is also up.

**Solution:** Choose one path:

- **Production:** Stop the host server, use `docker-compose.prod.yml` only
- **Host-run detector:** Run the detector natively, leave `ai-gateway` down, and point `YOLO26_URL` (in `.env`) at it — see Option B

### Backend can't reach AI services

```bash
# Find the backend container name
podman compose -f docker-compose.prod.yml ps backend

# From inside the container - Docker
docker exec <backend-container> curl http://host.docker.internal:8090/health

# From inside the container - Podman
podman exec <backend-container> curl http://host.containers.internal:8090/health

# Check the URL vars the container actually has
podman compose -f docker-compose.prod.yml exec backend env | grep -E "YOLO26_URL|AI_VLM_URL|AI_GATEWAY_URL|USE_AI_GATEWAY"
```

### Database connection issues

```bash
# Docker
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml logs postgres

# OR Podman
podman compose -f docker-compose.prod.yml ps postgres
podman compose -f docker-compose.prod.yml logs postgres
```

### Frontend not loading

```bash
# Check nginx logs (production) - Docker or Podman
docker compose -f docker-compose.prod.yml logs frontend
# OR
podman compose -f docker-compose.prod.yml logs frontend

# Verify backend is healthy
curl http://localhost:8000/api/system/health
```

---

## Next Steps

System is running. Continue with:

- **[Dashboard Guide](../ui/dashboard.md)** - Learn to use the dashboard
- **[Configuration Reference](../reference/config/env-reference.md)** - Customize settings
- **[Upgrading](upgrading.md)** - Future version upgrades
