# Configuration Reference

---

title: Configuration Reference
source_refs:

- backend/core/config.py:Settings:12
- backend/core/config.py:get_settings:618
- .env.example

---

> **How to configure the system.** For the authoritative list of environment variables and ports, use `docs/reference/config/env-reference.md` and `docs/RUNTIME_CONFIG.md`. Copy `.env.example` to `.env` and adjust values as needed.

<!-- Nano Banana Pro Prompt:
"Technical illustration of server configuration files and environment settings,
dark background #121212, NVIDIA green #76B900 accent lighting,
gear icons and configuration switches, vertical 2:3 aspect ratio,
clean minimalist style, no text overlays"
-->

## Configuration Loading

The application loads configuration in this order (later sources override earlier):

1. Default values in [`backend/core/config.py:12`](../../backend/core/config.py)
2. `.env` file in project root
3. `data/runtime.env` (via `HSI_RUNTIME_ENV_PATH`)
4. Environment variables (highest priority)

See [`get_settings()`](../../backend/core/config.py:618) for the loading implementation.

```mermaid
flowchart TB
    subgraph Loading["Configuration Loading Order"]
        D[Default Values<br/>config.py] --> E[.env File]
        E --> R[runtime.env]
        R --> ENV[Environment Variables]
    end

    ENV --> S[Settings Object]

    style D fill:#A855F7,color:#fff
    style ENV fill:#76B900,color:#fff
    style S fill:#3B82F6,color:#fff
```

---

## Quick Reference

| File                     | Purpose                                         |
| ------------------------ | ----------------------------------------------- |
| `.env`                   | Local overrides (not in git)                    |
| `.env.example`           | Template with documented defaults               |
| `data/runtime.env`       | Runtime overrides (survives container rebuilds) |
| `backend/core/config.py` | Source of truth for all settings                |

---

## Database Configuration

| Variable              | Default                    | Description                |
| --------------------- | -------------------------- | -------------------------- |
| `DATABASE_URL`        | _required_                 | PostgreSQL connection URL  |
| `REDIS_URL`           | `redis://localhost:6379/0` | Redis connection URL       |
| `REDIS_EVENT_CHANNEL` | `security_events`          | Redis pub/sub channel name |

**Source:** [`backend/core/config.py:25-38`](../../backend/core/config.py)

### Database URL Format

```bash
# PostgreSQL (required - SQLite is not supported)
DATABASE_URL=postgresql+asyncpg://username:password@host:port/database

# Examples:
# Native development
DATABASE_URL=postgresql+asyncpg://security:your_password@localhost:5432/security

# Docker Compose
DATABASE_URL=postgresql+asyncpg://security:your_password@postgres:5432/security
```

### Redis URL Format

```bash
# Standard Redis
REDIS_URL=redis://localhost:6379/0

# Redis with password
REDIS_URL=redis://:password@localhost:6379/0

# Redis TLS (rediss://)
REDIS_URL=rediss://localhost:6379/0
```

---

## Application Settings

| Variable        | Default                      | Description                                  |
| --------------- | ---------------------------- | -------------------------------------------- |
| `APP_NAME`      | `Home Security Intelligence` | Application display name                     |
| `APP_VERSION`   | `0.1.0`                      | Version string                               |
| `DEBUG`         | `false`                      | Enable debug mode                            |
| `ADMIN_ENABLED` | `false`                      | Enable admin endpoints (requires DEBUG=true) |
| `ADMIN_API_KEY` | _none_                       | API key for admin endpoints                  |

**Source:** [`backend/core/config.py:41-58`](../../backend/core/config.py)

### Admin Endpoint Security

Admin endpoints require **both** conditions:

- `DEBUG=true`
- `ADMIN_ENABLED=true`

If `ADMIN_API_KEY` is set, all admin requests must include the `X-Admin-API-Key` header.

---

## API Server Settings

| Variable       | Default                                              | Range      | Description          |
| -------------- | ---------------------------------------------------- | ---------- | -------------------- |
| `API_HOST`     | `0.0.0.0`                                            | -          | Bind address         |
| `API_PORT`     | `8000`                                               | 1-65535    | Server port          |
| `CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:5173"]` | JSON array | Allowed CORS origins |

**Source:** [`backend/core/config.py:61-68`](../../backend/core/config.py)

---

## Camera Integration

| Variable                        | Default          | Range    | Description                          |
| ------------------------------- | ---------------- | -------- | ------------------------------------ |
| `FOSCAM_BASE_PATH`              | `/export/foscam` | -        | Base directory for FTP uploads       |
| `FILE_WATCHER_POLLING`          | `false`          | -        | Use polling instead of native events |
| `FILE_WATCHER_POLLING_INTERVAL` | `1.0`            | 0.1-30.0 | Polling interval (seconds)           |

**Source:** [`backend/core/config.py:71-85`](../../backend/core/config.py)

### When to Enable Polling

Set `FILE_WATCHER_POLLING=true` if:

- Running backend in Docker Desktop on macOS/Windows
- Monitoring network-mounted filesystems (NFS, SMB)
- Native filesystem events are not triggering

| Interval | Latency | CPU Usage | Use Case                          |
| -------- | ------- | --------- | --------------------------------- |
| 0.5s     | ~500ms  | Higher    | Near real-time, small directories |
| 1.0s     | ~1s     | Moderate  | Default, good balance             |
| 5.0s     | ~5s     | Low       | Large directories, many cameras   |
| 10-30s   | Higher  | Minimal   | Non-critical monitoring           |

---

## AI Service Endpoints

| Variable         | Default                 | Description                              |
| ---------------- | ----------------------- | ---------------------------------------- |
| `RTDETR_URL`     | `http://localhost:8090` | RT-DETRv2 detection service              |
| `NEMOTRON_URL`   | `http://localhost:8091` | Nemotron LLM service                     |
| `FLORENCE_URL`   | `http://localhost:8092` | Florence-2 vision extraction (optional)  |
| `CLIP_URL`       | `http://localhost:8093` | CLIP entity re-identification (optional) |
| `ENRICHMENT_URL` | `http://localhost:8094` | Enrichment HTTP service (optional)       |

**Source:** [`backend/core/config.py`](../../backend/core/config.py)

### AI Service Timeouts

| Variable                | Default | Range      | Description                          |
| ----------------------- | ------- | ---------- | ------------------------------------ |
| `AI_CONNECT_TIMEOUT`    | `10.0`  | 1.0-60.0   | Connection timeout (seconds)         |
| `AI_HEALTH_TIMEOUT`     | `5.0`   | 1.0-30.0   | Health check timeout (seconds)       |
| `RTDETR_READ_TIMEOUT`   | `60.0`  | 10.0-300.0 | Detection response timeout (seconds) |
| `NEMOTRON_READ_TIMEOUT` | `120.0` | 30.0-600.0 | LLM response timeout (seconds)       |

**Source:** [`backend/core/config.py:115-138`](../../backend/core/config.py)

#### Health Check Timeout Configuration

Health checks are used to verify AI services are responsive. Configure timeouts based on your network conditions:

```bash
# For fast local networks (default)
AI_HEALTH_TIMEOUT=5.0

# For slower networks or remote AI services
AI_HEALTH_TIMEOUT=15.0

# For VPN or high-latency connections
AI_HEALTH_TIMEOUT=30.0
```

**When to increase `AI_HEALTH_TIMEOUT`:**

- AI services are on remote machines
- Network has high latency (>100ms)
- Services are under heavy load
- Health check failures appear in logs despite services being operational

**When to decrease `AI_HEALTH_TIMEOUT`:**

- AI services are on localhost
- Fast failover is needed
- Quick detection of service failures is critical

### Container Networking

AI services can run **containerized** (production compose) or **on the host** (development). Configure URLs based on what your backend can reach.

```bash
# Production (docker-compose.prod.yml): backend -> AI services on the compose network
RTDETR_URL=http://ai-detector:8090
NEMOTRON_URL=http://ai-llm:8091
FLORENCE_URL=http://ai-florence:8092
CLIP_URL=http://ai-clip:8093
ENRICHMENT_URL=http://ai-enrichment:8094

# Native development (host-run AI)
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091

# Docker Desktop (macOS/Windows)
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091

# Linux Docker (add to docker-compose.yml)
# extra_hosts:
#   - "host.docker.internal:host-gateway"
```

---

## Detection Settings

| Variable                         | Default | Range   | Description                            |
| -------------------------------- | ------- | ------- | -------------------------------------- |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5`   | 0.0-1.0 | Minimum confidence to record detection |

**Source:** [`backend/core/config.py:175-180`](../../backend/core/config.py)

### Fast Path Settings

High-confidence detections can bypass batching for immediate alerts.

| Variable                         | Default      | Range      | Description                         |
| -------------------------------- | ------------ | ---------- | ----------------------------------- |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | `0.90`       | 0.0-1.0    | Confidence threshold for fast path  |
| `FAST_PATH_OBJECT_TYPES`         | `["person"]` | JSON array | Object types eligible for fast path |

**Source:** [`backend/core/config.py:183-192`](../../backend/core/config.py)

---

## Batch Processing

| Variable                     | Default | Range  | Description                   |
| ---------------------------- | ------- | ------ | ----------------------------- |
| `BATCH_WINDOW_SECONDS`       | `90`    | 1-3600 | Maximum batch duration        |
| `BATCH_IDLE_TIMEOUT_SECONDS` | `30`    | 1-3600 | Close batch after idle period |

**Source:** [`backend/core/config.py:94-101`](../../backend/core/config.py)

---

## Retention Settings

| Variable             | Default | Range | Description                    |
| -------------------- | ------- | ----- | ------------------------------ |
| `RETENTION_DAYS`     | `30`    | 1-365 | Days to keep events/detections |
| `LOG_RETENTION_DAYS` | `7`     | 1-365 | Days to keep database logs     |

**Source:** [`backend/core/config.py:88-91`](../../backend/core/config.py), [`backend/core/config.py:251-254`](../../backend/core/config.py)

---

## GPU Monitoring

| Variable                    | Default | Range    | Description                      |
| --------------------------- | ------- | -------- | -------------------------------- |
| `GPU_POLL_INTERVAL_SECONDS` | `5.0`   | 1.0-60.0 | GPU stats polling interval       |
| `GPU_STATS_HISTORY_MINUTES` | `60`    | 1-1440   | Minutes of GPU history in memory |

**Source:** [`backend/core/config.py:195-206`](../../backend/core/config.py)

### Polling Interval Guidance

| Interval | DB Writes/min | Use Case                           |
| -------- | ------------- | ---------------------------------- |
| 1-2s     | ~60           | Active monitoring/debugging        |
| 5s       | ~12           | Normal operation (default)         |
| 15-30s   | ~4            | Low overhead during heavy AI loads |
| 60s      | ~1            | Minimal monitoring for trends      |

---

## Authentication

| Variable          | Default | Description                   |
| ----------------- | ------- | ----------------------------- |
| `API_KEY_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS`        | `[]`    | JSON array of valid API keys  |

**Source:** [`backend/core/config.py:209-216`](../../backend/core/config.py)

---

## Rate Limiting

| Variable                                      | Default | Range   | Description               |
| --------------------------------------------- | ------- | ------- | ------------------------- |
| `RATE_LIMIT_ENABLED`                          | `true`  | -       | Enable rate limiting      |
| `RATE_LIMIT_REQUESTS_PER_MINUTE`              | `60`    | 1-10000 | General API requests/min  |
| `RATE_LIMIT_BURST`                            | `10`    | 1-100   | Burst allowance           |
| `RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE`        | `120`   | 1-10000 | Media requests/min        |
| `RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE` | `10`    | 1-100   | WebSocket connections/min |
| `RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE`       | `30`    | 1-1000  | Search requests/min       |

**Source:** [`backend/core/config.py:290-324`](../../backend/core/config.py)

---

## WebSocket Settings

| Variable                          | Default | Range        | Description                    |
| --------------------------------- | ------- | ------------ | ------------------------------ |
| `WEBSOCKET_IDLE_TIMEOUT_SECONDS`  | `300`   | 30-3600      | Idle timeout before disconnect |
| `WEBSOCKET_PING_INTERVAL_SECONDS` | `30`    | 5-120        | Keep-alive ping interval       |
| `WEBSOCKET_MAX_MESSAGE_SIZE`      | `65536` | 1024-1048576 | Max message size (bytes)       |

**Source:** [`backend/core/config.py:327-344`](../../backend/core/config.py)

---

## Severity Thresholds

Risk scores are mapped to severity levels using these thresholds:

| Variable              | Default | Description                  |
| --------------------- | ------- | ---------------------------- |
| `SEVERITY_LOW_MAX`    | `29`    | 0-29 = LOW                   |
| `SEVERITY_MEDIUM_MAX` | `59`    | 30-59 = MEDIUM               |
| `SEVERITY_HIGH_MAX`   | `84`    | 60-84 = HIGH, 85+ = CRITICAL |

**Source:** [`backend/core/config.py:347-364`](../../backend/core/config.py)

---

## Notifications

### General

| Variable                   | Default | Description                      |
| -------------------------- | ------- | -------------------------------- |
| `NOTIFICATION_ENABLED`     | `true`  | Enable notification delivery     |
| `DEFAULT_EMAIL_RECIPIENTS` | `[]`    | JSON array of default recipients |

**Source:** [`backend/core/config.py:367-447`](../../backend/core/config.py)

### SMTP Settings

| Variable            | Default | Description                          |
| ------------------- | ------- | ------------------------------------ |
| `SMTP_HOST`         | _none_  | SMTP server hostname                 |
| `SMTP_PORT`         | `587`   | SMTP port (587 for TLS, 465 for SSL) |
| `SMTP_USER`         | _none_  | SMTP username                        |
| `SMTP_PASSWORD`     | _none_  | SMTP password                        |
| `SMTP_FROM_ADDRESS` | _none_  | Sender email address                 |
| `SMTP_USE_TLS`      | `true`  | Use TLS for SMTP                     |

### Webhook Settings

| Variable                  | Default | Range | Description             |
| ------------------------- | ------- | ----- | ----------------------- |
| `DEFAULT_WEBHOOK_URL`     | _none_  | -     | Default webhook URL     |
| `WEBHOOK_TIMEOUT_SECONDS` | `30`    | 1-300 | Webhook request timeout |

---

## Logging

| Variable                | Default                  | Description                           |
| ----------------------- | ------------------------ | ------------------------------------- |
| `LOG_LEVEL`             | `INFO`                   | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FILE_PATH`         | `data/logs/security.log` | Rotating log file path                |
| `LOG_FILE_MAX_BYTES`    | `10485760`               | Max log file size (10MB)              |
| `LOG_FILE_BACKUP_COUNT` | `7`                      | Number of backup files                |
| `LOG_DB_ENABLED`        | `true`                   | Write logs to database                |
| `LOG_DB_MIN_LEVEL`      | `DEBUG`                  | Minimum level for DB logging          |

**Source:** [`backend/core/config.py:227-250`](../../backend/core/config.py)

---

## Queue Settings

| Variable                       | Default | Range                    | Description                    |
| ------------------------------ | ------- | ------------------------ | ------------------------------ |
| `QUEUE_MAX_SIZE`               | `10000` | 100-100000               | Maximum Redis queue size       |
| `QUEUE_OVERFLOW_POLICY`        | `dlq`   | dlq, reject, drop_oldest | Policy when queue is full      |
| `QUEUE_BACKPRESSURE_THRESHOLD` | `0.8`   | 0.5-1.0                  | Fill ratio for warnings        |
| `MAX_REQUEUE_ITERATIONS`       | `10000` | 1-100000                 | Max iterations for requeue-all |

**Source:** [`backend/core/config.py:257-279`](../../backend/core/config.py)

### Overflow Policies

| Policy        | Behavior                  | Data Loss |
| ------------- | ------------------------- | --------- |
| `dlq`         | Move to dead-letter queue | No        |
| `reject`      | Fail the operation        | No        |
| `drop_oldest` | Remove oldest items       | **Yes**   |

---

## File Deduplication

| Variable             | Default | Range   | Description                   |
| -------------------- | ------- | ------- | ----------------------------- |
| `DEDUPE_TTL_SECONDS` | `300`   | 60-3600 | TTL for deduplication entries |

**Source:** [`backend/core/config.py:219-224`](../../backend/core/config.py)

---

## Video Processing

| Variable                       | Default           | Range    | Description                       |
| ------------------------------ | ----------------- | -------- | --------------------------------- |
| `VIDEO_FRAME_INTERVAL_SECONDS` | `2.0`             | 0.1-60.0 | Interval between extracted frames |
| `VIDEO_THUMBNAILS_DIR`         | `data/thumbnails` | -        | Thumbnail storage directory       |
| `VIDEO_MAX_FRAMES`             | `30`              | 1-300    | Max frames per video              |

**Source:** [`backend/core/config.py:283-481`](../../backend/core/config.py)

---

## Clip Generation

| Variable                  | Default      | Range | Description                 |
| ------------------------- | ------------ | ----- | --------------------------- |
| `CLIPS_DIRECTORY`         | `data/clips` | -     | Event clips storage         |
| `CLIP_PRE_ROLL_SECONDS`   | `5`          | 0-60  | Seconds before event        |
| `CLIP_POST_ROLL_SECONDS`  | `5`          | 0-60  | Seconds after event         |
| `CLIP_GENERATION_ENABLED` | `true`       | -     | Enable auto clip generation |

**Source:** [`backend/core/config.py:450-469`](../../backend/core/config.py)

---

## TLS/HTTPS Settings

### Mode-Based Configuration (Recommended)

| Variable            | Default    | Options                         | Description                        |
| ------------------- | ---------- | ------------------------------- | ---------------------------------- |
| `TLS_MODE`          | `disabled` | disabled, self_signed, provided | TLS configuration mode             |
| `TLS_CERT_PATH`     | _none_     | -                               | Path to certificate file           |
| `TLS_KEY_PATH`      | _none_     | -                               | Path to private key file           |
| `TLS_CA_PATH`       | _none_     | -                               | Path to CA certificate             |
| `TLS_VERIFY_CLIENT` | `false`    | -                               | Require client certificates (mTLS) |
| `TLS_MIN_VERSION`   | `TLSv1.2`  | TLSv1.2, TLSv1.3                | Minimum TLS version                |

**Source:** [`backend/core/config.py:509-533`](../../backend/core/config.py)

### Legacy Settings (Backward Compatibility)

| Variable            | Default      | Description                     |
| ------------------- | ------------ | ------------------------------- |
| `TLS_ENABLED`       | `false`      | Enable TLS                      |
| `TLS_CERT_FILE`     | _none_       | Certificate path                |
| `TLS_KEY_FILE`      | _none_       | Private key path                |
| `TLS_CA_FILE`       | _none_       | CA certificate path             |
| `TLS_AUTO_GENERATE` | `false`      | Auto-generate self-signed certs |
| `TLS_CERT_DIR`      | `data/certs` | Directory for generated certs   |

**Source:** [`backend/core/config.py:484-507`](../../backend/core/config.py)

---

## Frontend Environment Variables

Frontend variables use the `VITE_` prefix and are embedded at **build time**.

| Variable            | Default                 | Description                    |
| ------------------- | ----------------------- | ------------------------------ |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL (from browser) |
| `VITE_WS_BASE_URL`  | `ws://localhost:8000`   | WebSocket URL (from browser)   |

**Important:** These URLs are accessed from the browser, not from containers. Use `localhost` or your server's public hostname, not `host.docker.internal`.

### Frontend Port Configuration

The frontend serves on different ports depending on the environment:

| Environment | Port | Server    | Configuration             |
| ----------- | ---- | --------- | ------------------------- |
| Development | 5173 | Vite dev  | Default Vite port         |
| Production  | 80   | Nginx     | Container exposes port 80 |
| Production  | 443  | Nginx+TLS | When TLS is enabled       |

#### Changing the Production Port

To change the production frontend port (default: 80), modify `docker-compose.prod.yml`:

```yaml
# docker-compose.prod.yml
services:
  frontend:
    ports:
      - "${FRONTEND_PORT:-80}:80" # Use FRONTEND_PORT env var or default to 80
```

Then set the environment variable:

```bash
# Serve frontend on port 3000 instead of 80
export FRONTEND_PORT=3000
podman-compose -f docker-compose.prod.yml up -d
```

#### Running Frontend Behind a Reverse Proxy

When running behind nginx, Traefik, or another reverse proxy:

```bash
# .env - Point frontend to your proxy URL
VITE_API_BASE_URL=https://yourdomain.com/api
VITE_WS_BASE_URL=wss://yourdomain.com/api

# Rebuild frontend with new URLs
cd frontend && npm run build
```

#### Development Port Override

To change the development port (default: 5173):

```bash
cd frontend

# Using environment variable
VITE_PORT=3000 npm run dev

# Or modify vite.config.ts:
# server: {
#   port: 3000,
#   host: true
# }
```

---

## Example Configurations

### Development (Native)

```bash
# .env
DATABASE_URL=postgresql+asyncpg://security:dev_password@localhost:5432/security
REDIS_URL=redis://localhost:6379/0
RTDETR_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
FOSCAM_BASE_PATH=/export/foscam
DEBUG=true
LOG_LEVEL=DEBUG
```

### Development (Docker)

```bash
# .env
DATABASE_URL=postgresql+asyncpg://security:dev_password@postgres:5432/security
REDIS_URL=redis://redis:6379
RTDETR_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
DEBUG=true
```

### Production

```bash
# .env
DATABASE_URL=postgresql+asyncpg://security:secure_password@postgres:5432/security
REDIS_URL=redis://redis:6379
RTDETR_URL=https://your-rtdetr-host:8090
NEMOTRON_URL=https://your-nemotron-host:8091
DEBUG=false
LOG_LEVEL=INFO
RETENTION_DAYS=30
DETECTION_CONFIDENCE_THRESHOLD=0.6
API_KEY_ENABLED=true
API_KEYS=["your-secure-api-key"]
TLS_MODE=provided
TLS_CERT_PATH=/path/to/server.crt
TLS_KEY_PATH=/path/to/server.key
```

---

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

---

## See Also

- [Storage and Retention](storage-retention.md) - Disk management and cleanup policies
- [Monitoring](monitoring.md) - GPU stats, health checks, DLQ
- [Troubleshooting](troubleshooting.md) - Common configuration issues
- [Security](security.md) - Hardening recommendations
