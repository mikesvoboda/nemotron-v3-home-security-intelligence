# Runtime Configuration Reference

> **This is the authoritative reference for all environment variables and port assignments.**
> All other documentation files should reference this document to avoid inconsistencies.

## Quick Reference

Copy `.env.example` to `.env` and adjust values as needed. All variables have sensible defaults.

## Service Ports

| Service     | Port | Protocol | Description                                          |
| ----------- | ---- | -------- | ---------------------------------------------------- |
| Frontend    | 5173 | HTTP     | Vite dev server (development)                        |
| Frontend    | 80   | HTTP     | Nginx (production)                                   |
| Backend API | 8000 | HTTP/WS  | FastAPI REST + WebSocket                             |
| RT-DETRv2   | 8090 | HTTP     | Object detection service (runs on host, not Docker)  |
| Nemotron    | 8091 | HTTP     | LLM risk analysis service (runs on host, not Docker) |
| Redis       | 6379 | TCP      | Cache, queues, pub/sub                               |

## Container vs Host Networking

The AI services (RT-DETRv2 and Nemotron) run **natively on the host** for GPU access, not inside Docker. The dockerized backend must reach them via special hostnames:

### macOS and Windows (Docker Desktop)

Use `host.docker.internal` which Docker Desktop provides automatically:

```bash
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
```

### Linux

Linux does not have `host.docker.internal` by default. Choose one of these approaches:

**Option 1: Add host entry manually (recommended)**

```bash
docker compose up --add-host=host.docker.internal:host-gateway
```

Or add to your `docker-compose.yml`:

```yaml
services:
  backend:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Option 2: Use host's IP address directly**

```bash
# Find your host IP
ip route get 1 | awk '{print $7}'

# Set in .env
RTDETR_URL=http://192.168.1.100:8090
NEMOTRON_URL=http://192.168.1.100:8091
```

**Option 3: Use host network mode (simplest but less isolated)**

```yaml
services:
  backend:
    network_mode: host
```

## Environment Variables

### Database Configuration

| Variable       | Default                                  | Description                   |
| -------------- | ---------------------------------------- | ----------------------------- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/security.db` | SQLAlchemy async database URL |

**Notes:**

- SQLite is the default; suitable for single-user deployments
- Path is relative to the backend working directory
- Inside Docker, the path maps to `/app/data/security.db`
- Directory is auto-created if it doesn't exist

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

| Variable           | Default          | Description                           |
| ------------------ | ---------------- | ------------------------------------- |
| `FOSCAM_BASE_PATH` | `/export/foscam` | Base directory for Foscam FTP uploads |

**Notes:**

- Cameras upload via FTP to `{FOSCAM_BASE_PATH}/{camera_name}/`
- Inside Docker, this maps to `/cameras` via volume mount
- Directory must exist and be readable by the backend process

### AI Service Endpoints

| Variable       | Default                 | Description                          |
| -------------- | ----------------------- | ------------------------------------ |
| `RTDETR_URL`   | `http://localhost:8090` | RT-DETRv2 object detection service   |
| `NEMOTRON_URL` | `http://localhost:8091` | Nemotron LLM service (via llama.cpp) |

**Notes:**

- Both services run natively on the host for GPU access
- Inside Docker, use `http://host.docker.internal:8090` (see Container vs Host section)
- RT-DETRv2 provides `/detect` endpoint for image analysis
- Nemotron provides `/v1/chat/completions` endpoint for risk reasoning

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

### Authentication Settings

| Variable          | Default | Description                   |
| ----------------- | ------- | ----------------------------- |
| `API_KEY_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS`        | `[]`    | JSON array of valid API keys  |

**Notes:**

- Authentication is disabled by default (single-user assumption)
- Enable for multi-user or exposed deployments
- Keys are hashed on startup for security

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
| `LOG_DB_ENABLED`        | `true`                   | Write logs to SQLite database                         |
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
DATABASE_URL=sqlite+aiosqlite:///./data/security.db
REDIS_URL=redis://localhost:6379/0
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
FOSCAM_BASE_PATH=/export/foscam
DEBUG=true
LOG_LEVEL=DEBUG
```

### Development (Docker)

Using Docker Compose for backend/frontend/redis, native AI services:

```bash
# .env (values are set in docker-compose.yml, this is for reference)
DATABASE_URL=sqlite+aiosqlite:///data/security.db
REDIS_URL=redis://redis:6379
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
```

### Production

```bash
# .env
DATABASE_URL=sqlite+aiosqlite:///data/security.db
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

### Wrong database path

**Symptom:** Database not found or permission errors

**Solution:** Ensure path is correct for your deployment:

- Native: `sqlite+aiosqlite:///./data/security.db` (relative to backend/)
- Docker: `sqlite+aiosqlite:///data/security.db` (maps to /app/data/ in container)
