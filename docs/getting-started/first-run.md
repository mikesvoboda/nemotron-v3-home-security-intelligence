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

This guide walks you through starting the system for the first time and verifying all components are working.

<!-- Nano Banana Pro Prompt:
"Technical illustration of system startup sequence,
multiple service containers connecting and synchronizing,
dark background #121212, NVIDIA green #76B900 accent lighting,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

---

## Startup Sequence

The system requires starting components in a specific order:

```mermaid
flowchart TB
    subgraph AIServers["1. AI Servers (Native)"]
        DET[RT-DETRv2<br/>Port 8090]
        LLM[Nemotron<br/>Port 8091]
    end

    subgraph Containers["2. Application (Podman)"]
        PG[(PostgreSQL<br/>Port 5432)]
        REDIS[(Redis<br/>Port 6379)]
        BACK[Backend<br/>Port 8000]
        FRONT[Frontend<br/>Port 80]

        PG --> BACK
        REDIS --> BACK
        BACK --> FRONT
    end

    DET -.->|HTTP| BACK
    LLM -.->|HTTP| BACK

    style AIServers fill:#76B900,color:#fff
    style Containers fill:#3B82F6,color:#fff
```

> **Why native AI servers?** GPU access from containers requires complex configuration. Running AI servers natively with Podman for the application stack is simpler and more reliable.

---

## Step 1: Start AI Servers

Open **two separate terminal windows** for the AI servers.

### Terminal 1: RT-DETRv2 Detection Server

```bash
cd home-security-intelligence
./ai/start_detector.sh
```

**What happens** ([`ai/start_detector.sh:31-37`](../../ai/start_detector.sh:31)):

- Loads the RT-DETRv2 ONNX model
- Starts HTTP server on port 8090 ([line 12](../../ai/start_detector.sh:12))
- Uses ~4GB VRAM

**Expected output:**

```
Starting RT-DETRv2 Detection Server...
Model directory: /path/to/ai/rtdetr
Port: 8090
Expected VRAM usage: ~4GB
INFO:     Uvicorn running on http://0.0.0.0:8090
```

### Terminal 2: Nemotron LLM Server

```bash
cd home-security-intelligence
./ai/start_llm.sh
```

**What happens** ([`ai/start_llm.sh:36-43`](../../ai/start_llm.sh:36)):

- Loads the Nemotron GGUF model via llama.cpp
- Starts HTTP server on port 8091 ([line 16](../../ai/start_llm.sh:16))
- Uses ~3GB VRAM
- Configures 4096 token context, 2 parallel requests

**Expected output:**

```
Starting Nemotron LLM Server via llama.cpp...
Model: /path/to/ai/nemotron/nemotron-mini-4b-instruct-q4_k_m.gguf
Port: 8091
Context size: 4096
GPU layers: 99 (all layers)
llama server listening at http://0.0.0.0:8091
```

### Verify AI Servers

```bash
# Check RT-DETRv2
curl http://localhost:8090/health
# Expected: {"status": "ok"}

# Check Nemotron
curl http://localhost:8091/health
# Expected: {"status": "ok"}
```

---

## Step 2: Start Application Stack

In a **third terminal**, start the Podman containers:

### Production Mode (Recommended)

```bash
# macOS: Set AI host first
export AI_HOST=host.containers.internal

# Start containers
podman-compose -f docker-compose.prod.yml up -d
```

**What starts** ([`docker-compose.prod.yml`](../../docker-compose.prod.yml:1)):

| Service    | Port | Purpose                                                               |
| ---------- | ---- | --------------------------------------------------------------------- |
| PostgreSQL | 5432 | Database ([lines 17-45](../../docker-compose.prod.yml:17))            |
| Redis      | 6379 | Queues + pub/sub ([lines 88-107](../../docker-compose.prod.yml:88))   |
| Backend    | 8000 | FastAPI + WebSocket ([lines 46-86](../../docker-compose.prod.yml:46)) |
| Frontend   | 80   | React dashboard ([lines 109-143](../../docker-compose.prod.yml:109))  |

### Development Mode

For development with hot-reload:

```bash
podman-compose up -d
```

This uses `docker-compose.yml` with Vite dev server on port 5173.

### Verify Containers

```bash
# Check container status
podman-compose -f docker-compose.prod.yml ps

# Expected: All services "healthy" or "running"
NAME                    STATUS
security-postgres-1     healthy
security-redis-1        healthy
security-backend-1      healthy
security-frontend-1     healthy
```

---

## Step 3: Access the Dashboard

Open your browser to:

| Mode            | URL                                            |
| --------------- | ---------------------------------------------- |
| **Production**  | [http://localhost](http://localhost)           |
| **Development** | [http://localhost:5173](http://localhost:5173) |

### First-time Dashboard

On first load, you should see:

- **Risk Gauge**: Shows "No Data" or low risk (no events yet)
- **Camera Grid**: Empty (cameras not configured yet)
- **Activity Feed**: Empty (no detections yet)
- **System Status**: All green indicators

---

## Step 4: Health Check

Verify all services are communicating:

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
# Database
curl http://localhost:8000/api/system/health/ready

# GPU Stats (if AI servers running)
curl http://localhost:8000/api/system/gpu
```

---

## Step 5: Configure Your First Camera

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

### AI Server Logs

Logs appear in the terminal windows where you started the servers.

### Container Logs

```bash
# All services
podman-compose -f docker-compose.prod.yml logs -f

# Specific service
podman-compose -f docker-compose.prod.yml logs -f backend
```

### Log Locations

| Component | Location                |
| --------- | ----------------------- |
| RT-DETRv2 | Terminal stdout         |
| Nemotron  | Terminal stdout         |
| Backend   | Container: `/app/logs/` |
| Frontend  | Browser console         |

---

## Stopping the System

### Stop Containers

```bash
podman-compose -f docker-compose.prod.yml down
```

### Stop AI Servers

Press `Ctrl+C` in each AI server terminal.

### Full Cleanup (removes volumes)

```bash
podman-compose -f docker-compose.prod.yml down -v
```

---

## Troubleshooting

### AI servers won't start

```bash
# Check GPU availability
nvidia-smi

# Check model files exist
ls -la ai/nemotron/*.gguf
ls -la ai/rtdetr/*.onnx

# Check port availability
lsof -i :8090
lsof -i :8091
```

### Backend can't reach AI services

```bash
# From inside container (Linux)
podman exec security-backend-1 curl http://host.docker.internal:8090/health

# Check AI_HOST is set correctly
echo $AI_HOST
```

### Database connection issues

```bash
# Check PostgreSQL is running
podman-compose -f docker-compose.prod.yml ps postgres

# View PostgreSQL logs
podman-compose -f docker-compose.prod.yml logs postgres
```

### Frontend not loading

```bash
# Check nginx logs (production)
podman-compose -f docker-compose.prod.yml logs frontend

# Verify backend is healthy
curl http://localhost:8000/api/system/health
```

---

## Next Steps

System is running. Continue with:

- **[User Guide](../user-guide/dashboard-overview.md)** - Learn to use the dashboard
- **[Configuration](../admin-guide/configuration.md)** - Customize settings
- **[Upgrading](upgrading.md)** - Future version upgrades
