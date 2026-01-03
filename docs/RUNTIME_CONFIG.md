# Runtime Configuration Reference

> **This is the authoritative reference for all environment variables and port assignments.**
> All other documentation files should reference this document to avoid inconsistencies.

## Quick Reference

Copy `.env.example` to `.env` and adjust values as needed. All variables have sensible defaults.

## Service Ports

| Service     | Port | Protocol | Description                                                        |
| ----------- | ---- | -------- | ------------------------------------------------------------------ |
| Frontend    | 5173 | HTTP     | Vite dev server (development) or host port in production (default) |
| Frontend    | 80   | HTTP     | Nginx inside production container (mapped via FRONTEND_PORT)       |
| Backend API | 8000 | HTTP/WS  | FastAPI REST + WebSocket                                           |
| RT-DETRv2   | 8090 | HTTP     | Object detection service                                           |
| Nemotron    | 8091 | HTTP     | LLM risk analysis service                                          |
| Florence-2  | 8092 | HTTP     | Vision extraction service (optional)                               |
| CLIP        | 8093 | HTTP     | Re-identification service (optional)                               |
| Enrichment  | 8094 | HTTP     | Enrichment HTTP service (optional)                                 |
| Redis       | 6379 | TCP      | Cache, queues, pub/sub                                             |

## AI Service Deployment Modes

This project supports multiple deployment modes for AI services (RT-DETRv2, Nemotron, and optional Florence/CLIP/Enrichment):

1. **Development Mode (Host-run AI)**: AI services run directly on the host machine; backend runs in containers
2. **Production Mode (Fully Containerized)**: All services including AI run in containers with GPU passthrough

### Development Mode: Host-Run AI Services

In development mode (`docker-compose.yml`), AI services run directly on the host while the backend runs in a container. This is useful when:

- You want to iterate on AI service code without rebuilding containers
- You're running on a machine where GPU passthrough is difficult to configure
- You need direct access to AI service logs and debugging

The backend container reaches host-run AI services via `host.docker.internal` (Docker) or `host.containers.internal` (Podman).

#### macOS with Docker Desktop

Docker Desktop provides `host.docker.internal` automatically:

```bash
# No additional configuration needed - this is the default in docker-compose.yml
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
FLORENCE_URL=http://host.docker.internal:8092
CLIP_URL=http://host.docker.internal:8093
ENRICHMENT_URL=http://host.docker.internal:8094
```

#### macOS with Podman

Podman uses `host.containers.internal` instead:

```bash
# Set AI_HOST before starting containers
export AI_HOST=host.containers.internal
podman-compose up -d
```

#### Linux with Docker

Linux Docker does not have `host.docker.internal` by default. Choose one approach:

**Option 1: Add host entry (recommended)**

```bash
docker compose up --add-host=host.docker.internal:host-gateway
```

Or add to your compose file:

```yaml
services:
  backend:
    extra_hosts:
      - 'host.docker.internal:host-gateway'
```

**Option 2: Use host's IP address directly**

```bash
# Find your host IP
ip route get 1 | awk '{print $7}'

# Set in .env or export before compose
export AI_HOST=192.168.1.100
docker compose up -d
```

#### Linux with Podman

Podman on Linux works similarly to Docker:

```bash
# Option 1: Use host-gateway (Podman 4.0+)
podman-compose up --add-host=host.containers.internal:host-gateway

# Option 2: Use host IP
export AI_HOST=192.168.1.100
podman-compose up -d
```

### Production Mode: Fully Containerized AI

In production mode (`docker-compose.prod.yml`), all services including AI run in containers with NVIDIA GPU passthrough. This provides:

- Reproducible deployments
- Isolated GPU resource allocation
- Container orchestration benefits (health checks, restart policies)

```bash
# Production deployment - all services containerized
docker compose -f docker-compose.prod.yml up -d
# or with Podman:
podman-compose -f docker-compose.prod.yml up -d
```

In this mode, the backend reaches AI services via container network names:

```yaml
# Set automatically in docker-compose.prod.yml
RTDETR_URL=http://ai-detector:8090
NEMOTRON_URL=http://ai-llm:8091
FLORENCE_URL=http://ai-florence:8092
CLIP_URL=http://ai-clip:8093
ENRICHMENT_URL=http://ai-enrichment:8094
```

**GPU Requirements for Production Mode:**

- NVIDIA GPU with CUDA support
- nvidia-container-toolkit installed
- Docker/Podman configured for GPU access

### Quick Reference: AI_HOST by Platform

| Platform | Runtime | Development (host AI)            | Production (container AI)                                          |
| -------- | ------- | -------------------------------- | ------------------------------------------------------------------ |
| macOS    | Docker  | `host.docker.internal` (default) | N/A (use Linux for GPU)                                            |
| macOS    | Podman  | `host.containers.internal`       | N/A (use Linux for GPU)                                            |
| Linux    | Docker  | Host IP or `host-gateway`        | `ai-detector`, `ai-llm`, `ai-florence`, `ai-clip`, `ai-enrichment` |
| Linux    | Podman  | Host IP or `host-gateway`        | `ai-detector`, `ai-llm`, `ai-florence`, `ai-clip`, `ai-enrichment` |
| Windows  | Docker  | `host.docker.internal`           | N/A (use Linux for GPU)                                            |

> For a decision table and copy/paste `.env` snippets for each mode, see `docs/operator/deployment-modes.md`.

## Environment Variables

### Database Configuration

| Variable       | Default                                                                       | Description                   |
| -------------- | ----------------------------------------------------------------------------- | ----------------------------- |
| `DATABASE_URL` | `postgresql+asyncpg://security:security_dev_password@localhost:5432/security` | SQLAlchemy async database URL |

**Notes:**

- PostgreSQL is required for this application (SQLite is not supported)
- Use the `postgresql+asyncpg://` prefix for async operations
- Format: `postgresql+asyncpg://username:password@host:port/database_name`
- Inside Docker, use the service name (e.g., `postgres:5432`) instead of `localhost`
- Database must exist before starting the application

### Redis Configuration

| Variable    | Default                    | Description          |
| ----------- | -------------------------- | -------------------- |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |

**Notes:**

- When running in Docker, use `redis://redis:6379` (service name)
- When running natively, use `redis://localhost:6379/0`

### Application Settings

| Variable      | Default                      | Description              |
| ------------- | ---------------------------- | ------------------------ |
| `APP_NAME`    | `Home Security Intelligence` | Application display name |
| `APP_VERSION` | `0.1.0`                      | Application version      |
| `DEBUG`       | `false`                      | Enable debug mode        |

### API Server Settings

| Variable   | Default   | Description             |
| ---------- | --------- | ----------------------- |
| `API_HOST` | `0.0.0.0` | Bind address            |
| `API_PORT` | `8000`    | Port for FastAPI server |

### CORS Settings

| Variable       | Default                                              | Description                  |
| -------------- | ---------------------------------------------------- | ---------------------------- |
| `CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:5173"]` | Allowed origins (JSON array) |

### File Watching (Camera Integration)

| Variable                        | Default          | Range    | Description                           |
| ------------------------------- | ---------------- | -------- | ------------------------------------- |
| `FOSCAM_BASE_PATH`              | `/export/foscam` | -        | Base directory for Foscam FTP uploads |
| `FILE_WATCHER_POLLING`          | `false`          | -        | Use polling instead of native events  |
| `FILE_WATCHER_POLLING_INTERVAL` | `1.0`            | 0.1-30.0 | Polling interval in seconds           |

**Notes:**

- Cameras upload via FTP to `{FOSCAM_BASE_PATH}/{camera_name}/`
- Inside Docker, this maps to `/cameras` via volume mount
- Directory must exist and be readable by the backend process

**Native vs Polling Observer:**

By default, the file watcher uses native filesystem event APIs:

- Linux: inotify (kernel-level notifications)
- macOS: FSEvents (native filesystem event API)
- Windows: ReadDirectoryChangesW (native API)

Native observers are more efficient (near-instant detection, no CPU polling), but they **do not work reliably on Docker Desktop volume mounts** on macOS and Windows. The Docker Desktop file sharing layer does not propagate inotify/FSEvents events from the host to the container.

**When to Enable Polling:**

Set `FILE_WATCHER_POLLING=true` if:

- Running the backend in Docker Desktop on macOS or Windows
- Monitoring network-mounted filesystems (NFS, SMB, CIFS)
- Native events are not triggering file processing

**Polling Interval Considerations:**

| Interval | Detection Latency | CPU Usage | Use Case                   |
| -------- | ----------------- | --------- | -------------------------- |
| 0.5s     | ~500ms            | Higher    | Near real-time, small dirs |
| 1.0s     | ~1s               | Moderate  | Default, good balance      |
| 5.0s     | ~5s               | Low       | Large dirs, many cameras   |
| 10-30s   | Higher            | Minimal   | Non-critical monitoring    |

Lower intervals mean faster detection but increased CPU usage from directory scanning.

### AI Service Endpoints

| Variable       | Default                 | Description                          |
| -------------- | ----------------------- | ------------------------------------ |
| `RTDETR_URL`   | `http://localhost:8090` | RT-DETRv2 object detection service   |
| `NEMOTRON_URL` | `http://localhost:8091` | Nemotron LLM service (via llama.cpp) |

**Notes:**

- RT-DETRv2 provides `/detect` endpoint for image analysis
- Nemotron provides `/completion` endpoint for risk reasoning (llama.cpp server completion API)

### AI Service Timeout Settings

| Variable                | Default | Range      | Description                                      |
| ----------------------- | ------- | ---------- | ------------------------------------------------ |
| `AI_CONNECT_TIMEOUT`    | `10.0`  | 1.0-60.0   | Maximum time (seconds) to establish connection   |
| `AI_HEALTH_TIMEOUT`     | `5.0`   | 1.0-30.0   | Timeout (seconds) for AI service health checks   |
| `RTDETR_READ_TIMEOUT`   | `60.0`  | 10.0-300.0 | Maximum time (seconds) for RT-DETR detection     |
| `NEMOTRON_READ_TIMEOUT` | `120.0` | 30.0-600.0 | Maximum time (seconds) for Nemotron LLM response |

**Health Check Timeout Configuration:**

Health checks verify AI services are responsive before sending inference requests. The `AI_HEALTH_TIMEOUT` setting controls how long to wait for the `/health` endpoint response.

```bash
# Default: 5 seconds (good for local/fast networks)
AI_HEALTH_TIMEOUT=5.0

# Increase for slower networks or remote AI services
AI_HEALTH_TIMEOUT=15.0

# Maximum allowed (for VPN or high-latency connections)
AI_HEALTH_TIMEOUT=30.0
```

**When to Increase Timeouts:**

| Symptom                                    | Setting to Adjust       | Recommended Value |
| ------------------------------------------ | ----------------------- | ----------------- |
| Connection refused during startup          | `AI_CONNECT_TIMEOUT`    | 30.0              |
| Health checks timing out (services are up) | `AI_HEALTH_TIMEOUT`     | 10.0-15.0         |
| Detection requests timing out              | `RTDETR_READ_TIMEOUT`   | 120.0             |
| LLM responses timing out                   | `NEMOTRON_READ_TIMEOUT` | 300.0             |
| AI services on remote/VPN network          | All AI timeouts         | 2x default        |

**When to Decrease Timeouts:**

- AI services are on localhost: Consider `AI_HEALTH_TIMEOUT=3.0` for faster failover
- Quick detection of service failures is critical
- Running in a controlled local environment with fast networking

**Timeout Tuning for Slow Systems:**

If running on systems with limited resources (older hardware, constrained VMs, or high load conditions):

```bash
# Conservative settings for slow systems
AI_CONNECT_TIMEOUT=30.0
AI_HEALTH_TIMEOUT=15.0
RTDETR_READ_TIMEOUT=180.0
NEMOTRON_READ_TIMEOUT=300.0
```

These settings prevent premature timeouts when services are functional but slow to respond.

### Detection Settings

| Variable                         | Default | Range   | Description                              |
| -------------------------------- | ------- | ------- | ---------------------------------------- |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5`   | 0.0-1.0 | Minimum confidence to record a detection |

### Fast Path Settings

High-confidence detections of critical objects can bypass batching for immediate alerts.

| Variable                         | Default      | Range      | Description                                   |
| -------------------------------- | ------------ | ---------- | --------------------------------------------- |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | `0.90`       | 0.0-1.0    | Confidence threshold for immediate processing |
| `FAST_PATH_OBJECT_TYPES`         | `["person"]` | JSON array | Object types eligible for fast path           |

### Batch Processing Settings

Detections are grouped into events based on time windows.

| Variable                     | Default | Range  | Description                              |
| ---------------------------- | ------- | ------ | ---------------------------------------- |
| `BATCH_WINDOW_SECONDS`       | `90`    | 1-3600 | Maximum time window for a batch          |
| `BATCH_IDLE_TIMEOUT_SECONDS` | `30`    | 1-3600 | Close batch after this many idle seconds |

**Notes:**

- A "person walks to door" event might span 30 seconds across 15 images
- Batching groups these into one event for LLM context
- Fast path bypasses batching for urgent detections

### Retention Settings

| Variable             | Default | Range | Description                          |
| -------------------- | ------- | ----- | ------------------------------------ |
| `RETENTION_DAYS`     | `30`    | 1-365 | Days to keep events and detections   |
| `LOG_RETENTION_DAYS` | `7`     | 1-365 | Days to keep log entries in database |

### GPU Monitoring Settings

| Variable                    | Default | Range    | Description                                |
| --------------------------- | ------- | -------- | ------------------------------------------ |
| `GPU_POLL_INTERVAL_SECONDS` | `5.0`   | 1.0-60.0 | How often to poll GPU stats (seconds)      |
| `GPU_STATS_HISTORY_MINUTES` | `60`    | 1-1440   | Minutes of GPU history to retain in memory |

**How GPU Polling Works:**

The GPU monitor uses `pynvml` (NVIDIA Management Library Python bindings) to query GPU metrics. Each poll cycle reads:

- GPU utilization percentage (compute load)
- VRAM usage (used/total MB)
- GPU temperature (Celsius)
- Power consumption (Watts)

These metrics are stored in PostgreSQL for historical analysis and broadcast via WebSocket for real-time dashboard updates.

**Performance Impact Considerations:**

Each poll involves:

1. Multiple NVML API calls to the GPU driver
2. A database write to persist the stats
3. A WebSocket broadcast to connected clients

While individual polls are lightweight (~1-5ms), frequent polling can add cumulative overhead:

- At 1 second intervals: ~60 DB writes/minute, higher CPU/disk I/O
- At 5 seconds (default): ~12 DB writes/minute, balanced responsiveness
- At 15+ seconds: ~4 DB writes/minute, minimal overhead

**Recommended Values:**

| Scenario                          | Interval | Rationale                                    |
| --------------------------------- | -------- | -------------------------------------------- |
| Active monitoring/debugging       | 1-2s     | Real-time visibility during development      |
| Normal operation (default)        | 5s       | Good balance of responsiveness and overhead  |
| Low-overhead/background operation | 15-30s   | Reduce system pressure during heavy AI loads |
| Minimal monitoring                | 60s      | Just enough for trend analysis               |

**When to Increase the Interval:**

- System is under heavy CPU/disk I/O pressure
- AI inference pipeline is saturating GPU bandwidth
- Database is on slow storage (HDD, network mount)
- Running on lower-spec hardware
- Observing high context-switch counts in system monitors

**Runtime Adjustment:**

To change the interval without restarting, modify `.env` or `data/runtime.env` and restart the backend service:

```bash
# In .env or data/runtime.env
GPU_POLL_INTERVAL_SECONDS=15.0

# Then restart backend
docker compose restart backend
# or for native: kill and restart the uvicorn process
```

### Authentication Settings

| Variable          | Default | Description                   |
| ----------------- | ------- | ----------------------------- |
| `API_KEY_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS`        | `[]`    | JSON array of valid API keys  |

**Notes:**

- Authentication is disabled by default (single-user assumption)
- Enable for multi-user or exposed deployments
- Keys are hashed on startup for security

### TLS/HTTPS Settings

The application supports HTTPS for secure communication. There are two configuration approaches:

#### Modern Mode-Based Configuration (Recommended)

| Variable            | Default    | Description                                               |
| ------------------- | ---------- | --------------------------------------------------------- |
| `TLS_MODE`          | `disabled` | TLS mode: `disabled`, `self_signed`, or `provided`        |
| `TLS_CERT_PATH`     | -          | Path to TLS certificate file (PEM format)                 |
| `TLS_KEY_PATH`      | -          | Path to TLS private key file (PEM format)                 |
| `TLS_CA_PATH`       | -          | Path to CA certificate for client verification (optional) |
| `TLS_VERIFY_CLIENT` | `false`    | Require and verify client certificates (mutual TLS)       |
| `TLS_MIN_VERSION`   | `TLSv1.2`  | Minimum TLS version: `TLSv1.2` or `TLSv1.3`               |

**TLS Modes:**

| Mode          | Description                                                              |
| ------------- | ------------------------------------------------------------------------ |
| `disabled`    | HTTP only, no encryption (default, suitable for local development)       |
| `self_signed` | Auto-generate self-signed certificates (LAN deployments, not production) |
| `provided`    | Use existing certificates from `TLS_CERT_PATH` and `TLS_KEY_PATH`        |

**Configuration Examples:**

```bash
# Development (HTTP only - default)
TLS_MODE=disabled

# LAN deployment with auto-generated self-signed certificates
TLS_MODE=self_signed
TLS_CERT_DIR=data/certs

# Production with Let's Encrypt or purchased certificates
TLS_MODE=provided
TLS_CERT_PATH=/etc/ssl/certs/hsi.crt
TLS_KEY_PATH=/etc/ssl/private/hsi.key
TLS_MIN_VERSION=TLSv1.3

# Production with mutual TLS (mTLS) for client authentication
TLS_MODE=provided
TLS_CERT_PATH=/etc/ssl/certs/hsi.crt
TLS_KEY_PATH=/etc/ssl/private/hsi.key
TLS_CA_PATH=/etc/ssl/certs/client-ca.crt
TLS_VERIFY_CLIENT=true
```

#### Legacy Configuration (Deprecated)

These settings are kept for backward compatibility but will be removed in a future version. Use `TLS_MODE` instead.

| Variable            | Default      | Description                                    |
| ------------------- | ------------ | ---------------------------------------------- |
| `TLS_ENABLED`       | `false`      | Enable TLS (use `TLS_MODE=provided` instead)   |
| `TLS_CERT_FILE`     | -            | Certificate path (use `TLS_CERT_PATH` instead) |
| `TLS_KEY_FILE`      | -            | Key path (use `TLS_KEY_PATH` instead)          |
| `TLS_CA_FILE`       | -            | CA path (use `TLS_CA_PATH` instead)            |
| `TLS_AUTO_GENERATE` | `false`      | Auto-generate (use `TLS_MODE=self_signed`)     |
| `TLS_CERT_DIR`      | `data/certs` | Directory for auto-generated certificates      |

**Migration from Legacy to Modern:**

```bash
# Legacy configuration:
TLS_ENABLED=true
TLS_CERT_FILE=/path/to/cert.pem
TLS_KEY_FILE=/path/to/key.pem

# Equivalent modern configuration:
TLS_MODE=provided
TLS_CERT_PATH=/path/to/cert.pem
TLS_KEY_PATH=/path/to/key.pem
```

### File Deduplication Settings

| Variable             | Default | Range   | Description                         |
| -------------------- | ------- | ------- | ----------------------------------- |
| `DEDUPE_TTL_SECONDS` | `300`   | 60-3600 | TTL for file deduplication in Redis |

**Notes:**

- Prevents processing the same image file multiple times
- Uses Redis to track recently processed files

### Logging Settings

| Variable                | Default                  | Description                                           |
| ----------------------- | ------------------------ | ----------------------------------------------------- |
| `LOG_LEVEL`             | `INFO`                   | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE_PATH`         | `data/logs/security.log` | Path for rotating log file                            |
| `LOG_FILE_MAX_BYTES`    | `10485760` (10MB)        | Maximum size of each log file                         |
| `LOG_FILE_BACKUP_COUNT` | `7`                      | Number of backup log files to keep                    |
| `LOG_DB_ENABLED`        | `true`                   | Write logs to PostgreSQL database                     |
| `LOG_DB_MIN_LEVEL`      | `DEBUG`                  | Minimum level for database logging                    |

### Frontend Environment Variables

Frontend variables use the `VITE_` prefix and are embedded at build time.

| Variable            | Default                 | Description                    |
| ------------------- | ----------------------- | ------------------------------ |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL (from browser) |
| `VITE_WS_BASE_URL`  | `ws://localhost:8000`   | WebSocket URL (from browser)   |

**Notes:**

- These are accessed from the browser, not the container
- Use `localhost` or your server's public hostname
- Do NOT use `host.docker.internal` (that's for container-to-host, not browser-to-host)

### Frontend Production Port Configuration

| Variable        | Default | Description                                           |
| --------------- | ------- | ----------------------------------------------------- |
| `FRONTEND_PORT` | `5173`  | Host port to expose the production frontend container |

**How it works:**

In production, the frontend is served by nginx inside a Docker/Podman container. The nginx server always listens on **port 80 inside the container**. The `FRONTEND_PORT` environment variable controls which host port is mapped to container port 80.

```yaml
# docker-compose.prod.yml
ports:
  - '${FRONTEND_PORT:-5173}:80'
```

**Examples:**

```bash
# Default: Access frontend at http://localhost:5173
FRONTEND_PORT=5173

# Custom: Access frontend at http://localhost:3000
FRONTEND_PORT=3000

# Standard HTTP: Access frontend at http://localhost:80
FRONTEND_PORT=80
```

**Notes:**

- The container internal port (80) is fixed and cannot be changed without modifying nginx.conf
- Only the host-side port is configurable via `FRONTEND_PORT`
- Development mode uses Vite's dev server on port 5173 directly (not nginx)

## Configuration Files

| File                      | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| `.env`                    | Local environment overrides (not in git) |
| `.env.example`            | Template with documented defaults        |
| `data/runtime.env`        | Runtime overrides (loaded after .env)    |
| `docker-compose.yml`      | Development Docker configuration         |
| `docker-compose.prod.yml` | Production Docker configuration          |

### Loading Order

1. Default values from `backend/core/config.py`
2. `.env` file (if exists)
3. `data/runtime.env` file (if exists, via `HSI_RUNTIME_ENV_PATH`)
4. Environment variables override all

## Example Configurations

### Development (Native)

Running everything on your development machine:

```bash
# .env
DATABASE_URL=postgresql+asyncpg://security:security_dev_password@localhost:5432/security
REDIS_URL=redis://localhost:6379/0
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
FOSCAM_BASE_PATH=/export/foscam
DEBUG=true
LOG_LEVEL=DEBUG
```

### Development (Docker)

Using Docker Compose for backend/frontend/redis/postgres, native AI services:

```bash
# .env (values are set in docker-compose.yml, this is for reference)
DATABASE_URL=postgresql+asyncpg://security:security_dev_password@postgres:5432/security
REDIS_URL=redis://redis:6379
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
```

### Production

```bash
# .env
DATABASE_URL=postgresql+asyncpg://security:your_secure_password@postgres:5432/security
REDIS_URL=redis://redis:6379
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
DEBUG=false
LOG_LEVEL=INFO
RETENTION_DAYS=30
DETECTION_CONFIDENCE_THRESHOLD=0.6
API_KEY_ENABLED=true
API_KEYS=["your-secure-api-key-here"]
```

## Validation

Test your configuration:

```bash
# Check backend config loads correctly
cd backend
python -c "from core.config import get_settings; s = get_settings(); print(s.model_dump_json(indent=2))"

# Test service connectivity
curl http://localhost:8000/api/system/health     # Backend
curl http://localhost:8090/health                # RT-DETRv2
curl http://localhost:8091/health                # Nemotron
redis-cli ping                                   # Redis
```

## Troubleshooting

### Backend can't reach AI services in Docker

**Symptom:** `Connection refused` errors to RT-DETRv2 or Nemotron

**Solution:** Use `host.docker.internal` URLs and ensure AI services are running:

```bash
# Verify AI services are running on host
curl http://localhost:8090/health
curl http://localhost:8091/health

# Check backend logs
docker compose logs backend | grep -i "rtdetr\|nemotron"
```

### Environment variables not taking effect

**Symptom:** Changes to `.env` don't apply

**Solution:** Restart services and clear cache:

```bash
# For Docker
docker compose down && docker compose up -d

# For native backend, restart the process
# Settings are cached; restart clears the cache
```

### Database connection issues

**Symptom:** Database connection errors or authentication failures

**Solution:** Ensure PostgreSQL is running and credentials are correct:

- Native: `postgresql+asyncpg://security:security_dev_password@localhost:5432/security`
- Docker: `postgresql+asyncpg://security:security_dev_password@postgres:5432/security` (use service name)
- Verify PostgreSQL is accessible: `psql -h localhost -U security -d security`
- Ensure the database exists before starting the application

## Security Considerations

### AI Service URLs - HTTPS in Production

**WARNING:** The default AI service URLs use HTTP, which is vulnerable to man-in-the-middle (MITM) attacks. In a MITM attack, an attacker could:

- Intercept and modify detection requests/responses
- Inject false detection data
- Exfiltrate camera images being sent for analysis

**Recommendations:**

| Environment | Protocol | Notes                                                        |
| ----------- | -------- | ------------------------------------------------------------ |
| Local dev   | HTTP     | Acceptable when both services run on localhost               |
| Docker dev  | HTTP     | Acceptable within trusted Docker network                     |
| Production  | HTTPS    | **Required** - Use TLS certificates for AI service endpoints |
| Remote AI   | HTTPS    | **Required** - Never send images over untrusted networks     |

**Production Configuration Example:**

```bash
# Use HTTPS for production AI services
RTDETR_URL=https://your-rtdetr-host:8090
NEMOTRON_URL=https://your-nemotron-host:8091
```

**Setting up HTTPS for AI services:**

1. Obtain TLS certificates (Let's Encrypt, self-signed for internal, or purchased)
2. Configure your AI service (llama.cpp server, RT-DETRv2 wrapper) to use TLS
3. Update the environment variables to use `https://` URLs
4. If using self-signed certificates, configure the backend to trust them

### Other Security Best Practices

- Enable `API_KEY_ENABLED=true` for exposed deployments
- Use strong, unique API keys in `API_KEYS`
- Restrict `CORS_ORIGINS` to only trusted domains
- Keep `DEBUG=false` in production
- Use a firewall to restrict access to Redis and database ports

## Scalability Considerations

### Current Architecture (Single-Node)

The MVP runs all background workers **in-process** with the FastAPI application:

| Worker            | Description                                    |
| ----------------- | ---------------------------------------------- |
| `FileWatcher`     | Monitors FTP directories for new camera images |
| `GPUMonitor`      | Polls GPU metrics via pynvml                   |
| `CleanupService`  | Prunes old events and detections               |
| `BatchAggregator` | Groups detections into time-windowed events    |

These workers are started as asyncio background tasks when the FastAPI application starts (`@app.on_event("startup")`). They share the same process memory space and event loop.

**This is intentional for the MVP:**

- Single-user local deployment (one household)
- All services run on one machine with GPU
- No need for distributed coordination
- Simpler deployment and debugging

### Single-Node Limitations

The in-process worker architecture has inherent limitations:

- **Horizontal scaling:** Cannot distribute workers across multiple nodes
- **Fault isolation:** A crashing worker can affect the API process
- **Resource contention:** Workers compete with API handlers for CPU/memory
- **No work distribution:** Cannot balance load across multiple consumers

For the target use case (single home, single GPU server), these limitations are acceptable.

### Multi-Node Deployment (Future)

If scaling beyond a single node becomes necessary (e.g., multi-site deployment, commercial product), the architecture would need these changes:

**Task Queue (Replace In-Process Workers)**

- Use **Celery** or **RQ** (Redis Queue) for distributed task processing
- Workers become standalone processes/containers
- Tasks are serialized and distributed via Redis/RabbitMQ

```python
# Current (in-process)
asyncio.create_task(file_watcher.watch())

# Future (Celery)
@celery.task
def process_image(image_path: str):
    ...
```

**Event Distribution (Replace Redis Pub/Sub)**

- Use **Redis Streams** for durable, multi-consumer event delivery
- Consumer groups ensure each event is processed exactly once
- Supports replay and acknowledgment

```python
# Current (pub/sub - fire and forget)
await redis.publish("events", event_json)

# Future (streams - durable)
await redis.xadd("events:stream", event_data)
```

**Container Orchestration**

- **Kubernetes** for container scheduling and scaling
- Separate deployments for API, workers, and AI services
- Horizontal Pod Autoscaler for demand-based scaling

**Database**

- Already using PostgreSQL for concurrent access
- Consider read replicas for heavy query loads
- Add connection pooling (pgBouncer) for high-concurrency scenarios

### What Would Need to Change

| Component       | Current                  | Multi-Node                          |
| --------------- | ------------------------ | ----------------------------------- |
| Task scheduling | asyncio background tasks | Celery/RQ workers                   |
| Event pub/sub   | Redis PUBLISH/SUBSCRIBE  | Redis Streams with consumer groups  |
| Database        | PostgreSQL (single-node) | PostgreSQL cluster with replication |
| Session state   | In-memory                | Redis-backed sessions               |
| File storage    | Local filesystem         | S3/MinIO object storage             |
| Deployment      | Docker Compose           | Kubernetes                          |

**Note:** These changes are out of scope for the MVP. The current architecture is appropriate for single-user home deployments.
