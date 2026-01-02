# Environment Variable Reference

> Complete reference for all configuration environment variables.

**Time to read:** ~10 min
**Prerequisites:** None

---

## Overview

Configuration is managed through environment variables. Set these in:

- `.env` file in the project root
- Shell environment (`export VAR=value`)
- Container environment (`docker-compose.yml`)

Priority: Environment > `.env` > Defaults

---

## Database

| Variable       | Required | Default | Description               |
| -------------- | -------- | ------- | ------------------------- |
| `DATABASE_URL` | **Yes**  | -       | PostgreSQL connection URL |

**Format:** `postgresql+asyncpg://user:password@host:port/database`

**Examples:**

```bash
# Local development
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security

# Docker container
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security
```

---

## Redis

| Variable    | Required | Default                    | Description          |
| ----------- | -------- | -------------------------- | -------------------- |
| `REDIS_URL` | No       | `redis://localhost:6379/0` | Redis connection URL |

**Format:** `redis://[password@]host:port[/database]` or `rediss://` for TLS

**Examples:**

```bash
# Local development
REDIS_URL=redis://localhost:6379/0

# Docker container
REDIS_URL=redis://redis:6379/0

# With password
REDIS_URL=redis://:password@localhost:6379/0

# TLS
REDIS_URL=rediss://redis-host:6379/0
```

---

## AI Services

### Service URLs

| Variable         | Required | Default                 | Description                             |
| ---------------- | -------- | ----------------------- | --------------------------------------- |
| `RTDETR_URL`     | No       | `http://localhost:8090` | RT-DETRv2 detection service URL         |
| `NEMOTRON_URL`   | No       | `http://localhost:8091` | Nemotron LLM service URL                |
| `FLORENCE_URL`   | No       | `http://localhost:8092` | Florence-2 vision-language service URL  |
| `CLIP_URL`       | No       | `http://localhost:8093` | CLIP embedding service URL              |
| `ENRICHMENT_URL` | No       | `http://localhost:8094` | Enrichment service URL (remote helpers) |

> **Warning:** Use HTTPS in production to prevent MITM attacks.

### Service Authentication

| Variable           | Required | Default | Description                   |
| ------------------ | -------- | ------- | ----------------------------- |
| `RTDETR_API_KEY`   | No       | -       | API key for RT-DETRv2 service |
| `NEMOTRON_API_KEY` | No       | -       | API key for Nemotron service  |

### Service Timeouts

### Enrichment Feature Toggles

These control enrichment behaviors in the backend. Defaults are designed for “rich context”, but you can
disable them if you’re resource constrained or running without those services.

| Variable                    | Required | Default | Description                               |
| --------------------------- | -------- | ------- | ----------------------------------------- |
| `VISION_EXTRACTION_ENABLED` | No       | `true`  | Enable Florence-2 based vision extraction |
| `REID_ENABLED`              | No       | `true`  | Enable CLIP-based re-identification       |
| `SCENE_CHANGE_ENABLED`      | No       | `true`  | Enable scene change detection             |

### Re-ID / Scene Change Tuning

| Variable                    | Required | Default | Description                              |
| --------------------------- | -------- | ------- | ---------------------------------------- |
| `REID_SIMILARITY_THRESHOLD` | No       | `0.85`  | Cosine similarity threshold for matching |
| `REID_TTL_HOURS`            | No       | `24`    | Redis TTL for embeddings                 |
| `SCENE_CHANGE_THRESHOLD`    | No       | `0.90`  | SSIM threshold (below = change detected) |

| Variable                | Required | Default | Range   | Description                |
| ----------------------- | -------- | ------- | ------- | -------------------------- |
| `AI_CONNECT_TIMEOUT`    | No       | `10.0`  | 1-60s   | Connection timeout         |
| `AI_HEALTH_TIMEOUT`     | No       | `5.0`   | 1-30s   | Health check timeout       |
| `RTDETR_READ_TIMEOUT`   | No       | `60.0`  | 10-300s | Detection response timeout |
| `NEMOTRON_READ_TIMEOUT` | No       | `120.0` | 30-600s | LLM response timeout       |

---

## Camera Integration

| Variable           | Required | Default          | Description                       |
| ------------------ | -------- | ---------------- | --------------------------------- |
| `FOSCAM_BASE_PATH` | No       | `/export/foscam` | Base directory for camera uploads |

Camera images are expected at: `{FOSCAM_BASE_PATH}/{camera_name}/`

---

## File Watcher

| Variable                        | Required | Default | Range   | Description                          |
| ------------------------------- | -------- | ------- | ------- | ------------------------------------ |
| `FILE_WATCHER_POLLING`          | No       | `false` | -       | Use polling instead of native events |
| `FILE_WATCHER_POLLING_INTERVAL` | No       | `1.0`   | 0.1-30s | Polling interval in seconds          |

> **Note:** Enable polling for Docker Desktop on macOS/Windows where inotify doesn't work across volume mounts.

---

## Detection Settings

| Variable                         | Required | Default | Range   | Description                       |
| -------------------------------- | -------- | ------- | ------- | --------------------------------- |
| `DETECTION_CONFIDENCE_THRESHOLD` | No       | `0.5`   | 0.0-1.0 | Minimum confidence for detections |

---

## Fast Path Settings

High-confidence detections can bypass batching for immediate alerts.

| Variable                         | Required | Default      | Range   | Description                                      |
| -------------------------------- | -------- | ------------ | ------- | ------------------------------------------------ |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | No       | `0.90`       | 0.0-1.0 | Confidence threshold for fast path               |
| `FAST_PATH_OBJECT_TYPES`         | No       | `["person"]` | -       | Object types eligible for fast path (JSON array) |

---

## Batch Processing

| Variable                     | Required | Default | Range | Description                             |
| ---------------------------- | -------- | ------- | ----- | --------------------------------------- |
| `BATCH_WINDOW_SECONDS`       | No       | `90`    | -     | Max time window for grouping detections |
| `BATCH_IDLE_TIMEOUT_SECONDS` | No       | `30`    | -     | Close batch after inactivity            |

---

## Retention

| Variable             | Required | Default | Description                        |
| -------------------- | -------- | ------- | ---------------------------------- |
| `RETENTION_DAYS`     | No       | `30`    | Days to keep events and detections |
| `LOG_RETENTION_DAYS` | No       | `7`     | Days to keep log entries           |

---

## GPU Monitoring

| Variable                    | Required | Default | Range  | Description                      |
| --------------------------- | -------- | ------- | ------ | -------------------------------- |
| `GPU_POLL_INTERVAL_SECONDS` | No       | `5.0`   | 1-60s  | GPU stats polling interval       |
| `GPU_STATS_HISTORY_MINUTES` | No       | `60`    | 1-1440 | Minutes of GPU history to retain |

**Recommended values:**

- 1-2s: Real-time debugging
- 5s: Balanced (default)
- 15-30s: Lower overhead under pressure
- 60s: Minimal monitoring

---

## Deduplication

| Variable             | Required | Default | Range    | Description                         |
| -------------------- | -------- | ------- | -------- | ----------------------------------- |
| `DEDUPE_TTL_SECONDS` | No       | `300`   | 60-3600s | TTL for file deduplication in Redis |

---

## Severity Thresholds

Risk score ranges for severity levels. See [Risk Levels Reference](risk-levels.md).

| Variable              | Required | Default | Range | Description                   |
| --------------------- | -------- | ------- | ----- | ----------------------------- |
| `SEVERITY_LOW_MAX`    | No       | `29`    | 0-100 | Max score for LOW severity    |
| `SEVERITY_MEDIUM_MAX` | No       | `59`    | 0-100 | Max score for MEDIUM severity |
| `SEVERITY_HIGH_MAX`   | No       | `84`    | 0-100 | Max score for HIGH severity   |

**Constraint:** `0 <= low_max < medium_max < high_max <= 100`

---

## Logging

| Variable                | Required | Default                  | Description                           |
| ----------------------- | -------- | ------------------------ | ------------------------------------- |
| `LOG_LEVEL`             | No       | `INFO`                   | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FILE_PATH`         | No       | `data/logs/security.log` | Path for rotating log file            |
| `LOG_FILE_MAX_BYTES`    | No       | `10485760`               | Max size per log file (10MB)          |
| `LOG_FILE_BACKUP_COUNT` | No       | `7`                      | Number of backup files to keep        |
| `LOG_DB_ENABLED`        | No       | `true`                   | Write logs to database                |
| `LOG_DB_MIN_LEVEL`      | No       | `DEBUG`                  | Min level for database logging        |

---

## API Server

| Variable   | Required | Default   | Description                          |
| ---------- | -------- | --------- | ------------------------------------ |
| `DEBUG`    | No       | `false`   | Enable debug mode (development only) |
| `API_HOST` | No       | `0.0.0.0` | Server bind address                  |
| `API_PORT` | No       | `8000`    | Server port                          |

---

## Authentication

| Variable          | Required | Default | Description                   |
| ----------------- | -------- | ------- | ----------------------------- |
| `API_KEY_ENABLED` | No       | `false` | Enable API key authentication |
| `API_KEYS`        | No       | `[]`    | Valid API keys (JSON array)   |

**Example:**

```bash
API_KEY_ENABLED=true
API_KEYS=["key1-here", "key2-here"]
```

---

## Rate Limiting

| Variable                                      | Required | Default                | Range                              | Description          |
| --------------------------------------------- | -------- | ---------------------- | ---------------------------------- | -------------------- |
| `RATE_LIMIT_ENABLED`                          | No       | `true`                 | -                                  | Enable rate limiting |
| `RATE_LIMIT_REQUESTS_PER_MINUTE`              | No       | `60`                   | 1-10000                            | Standard tier limit  |
| `RATE_LIMIT_BURST`                            | No       | `10`                   | 1-100                              | Burst allowance      |
| `RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE`        | No       | `120`                  | 1-10000                            | Media tier limit     |
| `RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE` | No       | `10`                   | 1-100                              | WebSocket limit      |
| `RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE`       | No       | `30`                   | 1-1000                             | Search tier limit    |
| `TRUSTED_PROXY_IPS`                           | No       | `["127.0.0.1", "::1"]` | Trusted proxy IPs (CIDR supported) |

---

## WebSocket

| Variable                          | Required | Default | Range    | Description                  |
| --------------------------------- | -------- | ------- | -------- | ---------------------------- |
| `WEBSOCKET_IDLE_TIMEOUT_SECONDS`  | No       | `300`   | 30-3600s | Close idle connections after |
| `WEBSOCKET_PING_INTERVAL_SECONDS` | No       | `30`    | 5-120s   | Server heartbeat interval    |
| `WEBSOCKET_MAX_MESSAGE_SIZE`      | No       | `65536` | 1KB-1MB  | Max message size (bytes)     |

---

## TLS/HTTPS Configuration

### Modern Configuration (Recommended)

| Variable            | Required    | Default    | Description                              |
| ------------------- | ----------- | ---------- | ---------------------------------------- |
| `TLS_MODE`          | No          | `disabled` | `disabled`, `self_signed`, or `provided` |
| `TLS_CERT_PATH`     | If provided | -          | Path to certificate file (PEM)           |
| `TLS_KEY_PATH`      | If provided | -          | Path to private key file (PEM)           |
| `TLS_CA_PATH`       | No          | -          | CA certificate for client verification   |
| `TLS_VERIFY_CLIENT` | No          | `false`    | Require client certificates (mTLS)       |
| `TLS_MIN_VERSION`   | No          | `TLSv1.2`  | Minimum TLS version                      |

### Legacy Configuration (Deprecated)

| Variable            | Required | Default      | Description                        |
| ------------------- | -------- | ------------ | ---------------------------------- |
| `TLS_ENABLED`       | No       | `false`      | Use `TLS_MODE` instead             |
| `TLS_CERT_FILE`     | No       | -            | Use `TLS_CERT_PATH` instead        |
| `TLS_KEY_FILE`      | No       | -            | Use `TLS_KEY_PATH` instead         |
| `TLS_AUTO_GENERATE` | No       | `false`      | Use `TLS_MODE=self_signed` instead |
| `TLS_CERT_DIR`      | No       | `data/certs` | Directory for auto-generated certs |

---

## CORS

| Variable       | Required | Default                                              | Description                  |
| -------------- | -------- | ---------------------------------------------------- | ---------------------------- |
| `CORS_ORIGINS` | No       | `["http://localhost:3000", "http://localhost:5173"]` | Allowed origins (JSON array) |

---

## Notifications

### Email (SMTP)

| Variable                   | Required | Default | Description                          |
| -------------------------- | -------- | ------- | ------------------------------------ |
| `SMTP_HOST`                | No       | -       | SMTP server hostname                 |
| `SMTP_PORT`                | No       | `587`   | SMTP port (587 for TLS, 465 for SSL) |
| `SMTP_USER`                | No       | -       | SMTP username                        |
| `SMTP_PASSWORD`            | No       | -       | SMTP password                        |
| `SMTP_FROM_ADDRESS`        | No       | -       | Sender email address                 |
| `SMTP_USE_TLS`             | No       | `true`  | Use TLS for SMTP                     |
| `DEFAULT_EMAIL_RECIPIENTS` | No       | `[]`    | Default recipients (JSON array)      |

### Webhooks

| Variable                  | Required | Default | Description                    |
| ------------------------- | -------- | ------- | ------------------------------ |
| `DEFAULT_WEBHOOK_URL`     | No       | -       | Default webhook URL for alerts |
| `WEBHOOK_TIMEOUT_SECONDS` | No       | `30`    | Webhook request timeout        |

### General

| Variable               | Required | Default | Description                  |
| ---------------------- | -------- | ------- | ---------------------------- |
| `NOTIFICATION_ENABLED` | No       | `true`  | Enable notification delivery |

---

## Queue Settings

| Variable                       | Required | Default | Range      | Description                       |
| ------------------------------ | -------- | ------- | ---------- | --------------------------------- |
| `QUEUE_MAX_SIZE`               | No       | `10000` | 100-100000 | Maximum Redis queue size          |
| `QUEUE_OVERFLOW_POLICY`        | No       | `dlq`   | -          | `dlq`, `reject`, or `drop_oldest` |
| `QUEUE_BACKPRESSURE_THRESHOLD` | No       | `0.8`   | 0.5-1.0    | Start warnings at this fill ratio |

---

## Dead Letter Queue (DLQ)

| Variable                                  | Required | Default | Range    | Description                     |
| ----------------------------------------- | -------- | ------- | -------- | ------------------------------- |
| `MAX_REQUEUE_ITERATIONS`                  | No       | `10000` | 1-100000 | Max iterations for requeue-all  |
| `DLQ_CIRCUIT_BREAKER_FAILURE_THRESHOLD`   | No       | `5`     | 1-50     | Failures before opening circuit |
| `DLQ_CIRCUIT_BREAKER_RECOVERY_TIMEOUT`    | No       | `60.0`  | 10-600s  | Wait before retry               |
| `DLQ_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS` | No       | `3`     | 1-10     | Test calls in half-open state   |
| `DLQ_CIRCUIT_BREAKER_SUCCESS_THRESHOLD`   | No       | `2`     | 1-10     | Successes to close circuit      |

---

## Video Processing

| Variable                       | Required | Default           | Range   | Description                       |
| ------------------------------ | -------- | ----------------- | ------- | --------------------------------- |
| `VIDEO_FRAME_INTERVAL_SECONDS` | No       | `2.0`             | 0.1-60s | Interval between extracted frames |
| `VIDEO_THUMBNAILS_DIR`         | No       | `data/thumbnails` | -       | Directory for video thumbnails    |
| `VIDEO_MAX_FRAMES`             | No       | `30`              | 1-300   | Max frames to extract per video   |

---

## Clip Generation

| Variable                  | Required | Default      | Range | Description                      |
| ------------------------- | -------- | ------------ | ----- | -------------------------------- |
| `CLIPS_DIRECTORY`         | No       | `data/clips` | -     | Directory for event clips        |
| `CLIP_PRE_ROLL_SECONDS`   | No       | `5`          | 0-60s | Seconds before event to include  |
| `CLIP_POST_ROLL_SECONDS`  | No       | `5`          | 0-60s | Seconds after event to include   |
| `CLIP_GENERATION_ENABLED` | No       | `true`       | -     | Enable automatic clip generation |

---

## Service Health

| Variable             | Required | Default | Description                         |
| -------------------- | -------- | ------- | ----------------------------------- |
| `AI_RESTART_ENABLED` | No       | `true`  | Auto-restart AI services on failure |

> **Note:** Set to `false` in containerized deployments where restart scripts aren't available.

---

## Admin Endpoints

| Variable        | Required | Default | Description                                    |
| --------------- | -------- | ------- | ---------------------------------------------- |
| `ADMIN_ENABLED` | No       | `false` | Enable admin endpoints (requires `DEBUG=true`) |
| `ADMIN_API_KEY` | No       | -       | API key for admin endpoints                    |

> **Security:** Admin endpoints require BOTH `DEBUG=true` AND `ADMIN_ENABLED=true`.

---

## Frontend (Build-Time)

These are embedded at frontend build time:

| Variable            | Required | Default                 | Description                      |
| ------------------- | -------- | ----------------------- | -------------------------------- |
| `VITE_API_BASE_URL` | No       | `http://localhost:8000` | Backend API URL                  |
| `VITE_WS_BASE_URL`  | No       | `ws://localhost:8000`   | WebSocket URL                    |
| `FRONTEND_PORT`     | No       | `5173`                  | Host port for frontend container |

---

## Next Steps

- [Risk Levels Reference](risk-levels.md) - Severity configuration details
- [Troubleshooting](../troubleshooting/index.md) - Configuration issues

---

## See Also

- [AI Configuration](../../operator/ai-configuration.md) - AI-specific configuration
- [Batching Logic](../../developer/batching-logic.md) - Batch timing configuration
- [Local Setup](../../developer/local-setup.md) - Development environment setup

---

[Back to Operator Hub](../../operator-hub.md) | [Developer Hub](../../developer-hub.md)
