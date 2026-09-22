# Environment Variable Reference

> Complete reference for all configuration environment variables.

**Time to read:** ~10 min
**Prerequisites:** None

---

## Configuration Cascade

![Environment Variable Cascade](../../images/architecture/env-variable-cascade.png)

_Configuration priority hierarchy and feature toggles overview._

---

## Overview

Configuration is managed through environment variables. Set these in:

- `.env` file in the project root
- Shell environment (`export VAR=value`)
- Container environment (`docker-compose.prod.yml` service `environment:` blocks)

Priority: Environment > `.env` > Defaults (pydantic-settings resolution order). The settings classes read `.env` via `env_file=".env"` (no `env_prefix` on the main `Settings` class, so env vars are the uppercased field names; exceptions are noted per row).

---

## Database

| Variable                 | Required | Default | Range    | Description                                  |
| ------------------------ | -------- | ------- | -------- | -------------------------------------------- |
| `DATABASE_URL`           | **Yes**  | -       | -        | PostgreSQL connection URL                    |
| `DATABASE_POOL_SIZE`     | No       | `20`    | 5-100    | Base number of database connections in pool  |
| `DATABASE_POOL_OVERFLOW` | No       | `30`    | 5-100    | Additional connections beyond pool_size      |
| `DATABASE_POOL_TIMEOUT`  | No       | `30`    | 5-120s   | Seconds to wait for available connection     |
| `DATABASE_POOL_RECYCLE`  | No       | `1800`  | 300-7200 | Seconds after which connections are recycled |

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

### Connection

| Variable           | Required | Default                    | Range  | Description                       |
| ------------------ | -------- | -------------------------- | ------ | --------------------------------- |
| `REDIS_URL`        | No       | `redis://localhost:6379/0` | -      | Redis connection URL              |
| `REDIS_PASSWORD`   | No       | -                          | -      | Redis password for authentication |
| `REDIS_POOL_SIZE`  | No       | `50`                       | 10-500 | Maximum Redis connections in pool |
| `REDIS_KEY_PREFIX` | No       | `hsi`                      | -      | Global prefix for all Redis keys  |

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

### Redis SSL/TLS

| Variable                   | Required | Default    | Description                                |
| -------------------------- | -------- | ---------- | ------------------------------------------ |
| `REDIS_SSL_ENABLED`        | No       | `false`    | Enable SSL/TLS for Redis connections       |
| `REDIS_SSL_CERT_REQS`      | No       | `required` | SSL verification: none, optional, required |
| `REDIS_SSL_CA_CERTS`       | No       | -          | Path to CA certificate file (PEM)          |
| `REDIS_SSL_CERTFILE`       | No       | -          | Path to client certificate for mTLS        |
| `REDIS_SSL_KEYFILE`        | No       | -          | Path to client private key for mTLS        |
| `REDIS_SSL_CHECK_HOSTNAME` | No       | `true`     | Verify server certificate hostname         |

---

## AI Services

### Service URLs

| Variable               | Required | Default                         | Description                                          |
| ---------------------- | -------- | ------------------------------- | ---------------------------------------------------- |
| `YOLO26_URL`           | No       | `http://ai-gateway:8090/yolo26` | YOLO26 detection service URL                         |
| `NEMOTRON_URL`         | No       | `http://localhost:8091`         | Nemotron LLM service URL                             |
| `FLORENCE_URL`         | No       | `http://localhost:8092`         | Florence-2 vision-language service URL               |
| `CLIP_URL`             | No       | `http://localhost:8093`         | CLIP embedding service URL                           |
| `ENRICHMENT_URL`       | No       | `http://localhost:8094`         | Enrichment service URL (heavy models)                |
| `ENRICHMENT_LIGHT_URL` | No       | `http://localhost:8096`         | Light enrichment service URL (pose/threat/pet/depth) |

> **Note:** In deployed containers all five router services are reached through the AI Gateway on `ai-gateway:8090` — e.g. `http://ai-gateway:8090/florence`, `/clip`, `/enrichment`, `/enrich-lt` (set by `docker-compose.prod.yml`; `.env.example` ships the host-side equivalents on `localhost:8090`). The `localhost:809x` defaults above are the standalone-service dev ports. The standalone Nemotron LLM (compose service `ai-llm`) is the only AI service not routed through the gateway; the gateway routes `/yolo26` `/clip` `/florence` `/enrichment` `/enrich-lt` (`ai/gateway/main.py`).

> **Warning:** Use HTTPS in production to prevent MITM attacks.

### Service Authentication

| Variable           | Required | Default | Description                  |
| ------------------ | -------- | ------- | ---------------------------- |
| `YOLO26_API_KEY`   | No       | -       | API key for YOLO26 service   |
| `NEMOTRON_API_KEY` | No       | -       | API key for Nemotron service |

### Service Timeouts

| Variable                  | Required | Default | Range   | Description                         |
| ------------------------- | -------- | ------- | ------- | ----------------------------------- |
| `AI_CONNECT_TIMEOUT`      | No       | `10.0`  | 1-60s   | Connection timeout                  |
| `AI_HEALTH_TIMEOUT`       | No       | `5.0`   | 1-30s   | Health check timeout                |
| `YOLO26_READ_TIMEOUT`     | No       | `30.0`  | 5-120s  | Detection response timeout          |
| `NEMOTRON_READ_TIMEOUT`   | No       | `120.0` | 30-600s | LLM response timeout                |
| `FLORENCE_READ_TIMEOUT`   | No       | `30.0`  | 5-120s  | Florence-2 response timeout         |
| `CLIP_READ_TIMEOUT`       | No       | `5.0`   | 1-60s   | CLIP embedding generation timeout   |
| `ENRICHMENT_READ_TIMEOUT` | No       | `60.0`  | 10-180s | Enrichment service response timeout |

### Enrichment Feature Toggles

These control enrichment behaviors in the backend. Defaults are designed for “rich context”, but you can
disable them if you’re resource constrained or running without those services.

| Variable                    | Required | Default | Description                               |
| --------------------------- | -------- | ------- | ----------------------------------------- |
| `VISION_EXTRACTION_ENABLED` | No       | `true`  | Enable Florence-2 based vision extraction |
| `REID_ENABLED`              | No       | `true`  | Enable CLIP-based re-identification       |
| `SCENE_CHANGE_ENABLED`      | No       | `true`  | Enable scene change detection             |

### Florence Feature Toggles

| Variable                              | Required | Default | Description                                             |
| ------------------------------------- | -------- | ------- | ------------------------------------------------------- |
| `FLORENCE_SCENE_CAPTIONS_ENABLED`     | No       | `true`  | Enable detailed scene captions (rich scene description) |
| `FLORENCE_DETECTION_CAPTIONS_ENABLED` | No       | `true`  | Enable per-detection captions (vehicles, persons)       |
| `FLORENCE_VQA_ENABLED`                | No       | `true`  | Enable Visual Question Answering attribute extraction   |

### Re-ID / Scene Change Tuning

| Variable                       | Required | Default | Range   | Description                              |
| ------------------------------ | -------- | ------- | ------- | ---------------------------------------- |
| `REID_SIMILARITY_THRESHOLD`    | No       | `0.85`  | 0.5-1.0 | Cosine similarity threshold for matching |
| `REID_TTL_HOURS`               | No       | `24`    | 1-168   | Redis TTL for embeddings                 |
| `REID_MAX_CONCURRENT_REQUESTS` | No       | `10`    | 1-100   | Max concurrent re-ID operations          |
| `REID_EMBEDDING_TIMEOUT`       | No       | `30.0`  | 5-120s  | Timeout for ReID embedding generation    |
| `SCENE_CHANGE_THRESHOLD`       | No       | `0.90`  | 0.5-1.0 | SSIM threshold (below = change detected) |

### Image Quality Assessment

| Variable                | Required | Default | Description                                                 |
| ----------------------- | -------- | ------- | ----------------------------------------------------------- |
| `IMAGE_QUALITY_ENABLED` | No       | `true`  | Enable BRISQUE image quality assessment (CPU-based, 0 VRAM) |

### Enrichment Circuit Breakers

| Variable                            | Required | Default | Range  | Description                   |
| ----------------------------------- | -------- | ------- | ------ | ----------------------------- |
| `ENRICHMENT_CB_FAILURE_THRESHOLD`   | No       | `10`    | 1-50   | Failures before circuit opens |
| `ENRICHMENT_CB_RECOVERY_TIMEOUT`    | No       | `60.0`  | 10-600 | Seconds to wait before retry  |
| `ENRICHMENT_CB_HALF_OPEN_MAX_CALLS` | No       | `3`     | 1-10   | Test calls in half-open state |

### CLIP Circuit Breakers

| Variable                      | Required | Default | Range  | Description                   |
| ----------------------------- | -------- | ------- | ------ | ----------------------------- |
| `CLIP_CB_FAILURE_THRESHOLD`   | No       | `10`    | 1-50   | Failures before circuit opens |
| `CLIP_CB_RECOVERY_TIMEOUT`    | No       | `60.0`  | 10-600 | Seconds to wait before retry  |
| `CLIP_CB_HALF_OPEN_MAX_CALLS` | No       | `3`     | 1-10   | Test calls in half-open state |

### Florence Circuit Breakers

| Variable                          | Required | Default | Range  | Description                   |
| --------------------------------- | -------- | ------- | ------ | ----------------------------- |
| `FLORENCE_CB_FAILURE_THRESHOLD`   | No       | `10`    | 1-50   | Failures before circuit opens |
| `FLORENCE_CB_RECOVERY_TIMEOUT`    | No       | `60.0`  | 10-600 | Seconds to wait before retry  |
| `FLORENCE_CB_HALF_OPEN_MAX_CALLS` | No       | `3`     | 1-10   | Test calls in half-open state |

### AI Service Retries

| Variable                 | Required | Default | Range | Description                           |
| ------------------------ | -------- | ------- | ----- | ------------------------------------- |
| `DETECTOR_MAX_RETRIES`   | No       | `3`     | 1-10  | Retry attempts for YOLO26 detector    |
| `NEMOTRON_MAX_RETRIES`   | No       | `3`     | 1-10  | Retry attempts for Nemotron LLM       |
| `ENRICHMENT_MAX_RETRIES` | No       | `3`     | 1-10  | Retry attempts for enrichment service |

### AI Concurrency

| Variable                       | Required | Default | Range | Description                                                         |
| ------------------------------ | -------- | ------- | ----- | ------------------------------------------------------------------- |
| `AI_MAX_CONCURRENT_INFERENCES` | No       | `4`     | 1-32  | Max concurrent AI inference operations (20 on free-threaded Python) |

> **Note:** The default is resolved at startup by `_get_default_inference_limit()` in `backend/core/config.py`: 20 when running free-threaded Python (3.13t/3.14t with the GIL disabled), 4 on standard GIL builds.

### Nemotron Context Window

| Variable                     | Required | Default | Range       | Description                        |
| ---------------------------- | -------- | ------- | ----------- | ---------------------------------- |
| `NEMOTRON_CONTEXT_WINDOW`    | No       | `32768` | 1000-131072 | Context window size in tokens      |
| `NEMOTRON_MAX_OUTPUT_TOKENS` | No       | `1536`  | 100-8192    | Maximum tokens reserved for output |

> **Note:** `NEMOTRON_CONTEXT_WINDOW` reads from the `CTX_SIZE` env var (`validation_alias="CTX_SIZE"` — single source of truth shared with llama.cpp). `docker-compose.prod.yml` passes `CTX_SIZE=262144` (8 parallel slots x 32K) to the `ai-llm` container only; the backend container does not receive it, so it uses the 32768 code default.

### AI Warmup Settings

| Variable                          | Required | Default                                                                | Range    | Description                             |
| --------------------------------- | -------- | ---------------------------------------------------------------------- | -------- | --------------------------------------- |
| `AI_WARMUP_ENABLED`               | No       | `true`                                                                 | -        | Enable model warmup on startup          |
| `AI_COLD_START_THRESHOLD_SECONDS` | No       | `300.0`                                                                | 60-3600s | Seconds before model is considered cold |
| `NEMOTRON_WARMUP_PROMPT`          | No       | `"Hello, please respond with 'ready' to confirm you are operational."` | -        | Test prompt for Nemotron warmup         |

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
| `DETECTION_CONFIDENCE_THRESHOLD` | No       | `0.40`  | 0.0-1.0 | Minimum confidence for detections |

---

## Fast Path Settings

High-confidence detections can bypass batching for immediate alerts.

> **Status:** The fast path is **DISABLED by default**. The threshold ships at `2.0` (an impossible value > 1.0) and the object-type list ships empty, as a second safety net — fast path bypasses enrichment, which caused Nemotron to produce inaccurate scores (NEM-5525). Do not lower the threshold or add object types without first adding enrichment to the fast-path code path.

| Variable                         | Required | Default | Range    | Description                                         |
| -------------------------------- | -------- | ------- | -------- | --------------------------------------------------- |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | No       | `2.0`   | 0.0-10.0 | Confidence threshold for fast path (2.0 = disabled) |
| `FAST_PATH_OBJECT_TYPES`         | No       | `[]`    | -        | Object types eligible for fast path (JSON array)    |

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
| `LOG_LEVEL`             | No       | `WARNING`                | DEBUG, INFO, WARNING, ERROR, CRITICAL |
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
| `RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE` | No       | `100`                  | 1-400                              | WebSocket limit      |
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

### Queue Overflow Policy Options

When the queue reaches `QUEUE_MAX_SIZE`, the system applies the configured overflow policy:

| Policy        | Behavior                                                                         | Use Case                                        |
| ------------- | -------------------------------------------------------------------------------- | ----------------------------------------------- |
| `dlq`         | **Default.** Move overflow items to dead-letter queue for later retry/inspection | Production - preserves all data for recovery    |
| `reject`      | Reject new items with an error; existing items preserved                         | Strict mode - alerts immediately on capacity    |
| `drop_oldest` | Discard oldest items to make room for new ones                                   | High-throughput - prioritizes recent detections |

**Consequences by policy:**

- **`dlq` (default):** Overflowed items are moved to `dlq:detection_queue` or `dlq:analysis_queue`. No data loss but requires monitoring DLQ depth. Use `/api/dlq/stats` to check and `/api/dlq/requeue-all/{queue_name}` to recover items.

- **`reject`:** New detections are dropped when queue is full. Backend logs error `Queue overflow: item rejected`. Useful for alerting on capacity issues but causes immediate data loss.

- **`drop_oldest`:** Oldest queued items are removed to make space. Prioritizes freshness over completeness. May result in missed security events from earlier timeframes.

> **Recommendation:** Use `dlq` (default) for production deployments. Monitor `hsi:queue:dlq:*` Redis keys or the `/api/dlq/stats` endpoint to detect overflow conditions.

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
| `VIDEO_FRAME_INTERVAL_SECONDS` | No       | `4.0`             | 0.1-60s | Interval between extracted frames |
| `VIDEO_THUMBNAILS_DIR`         | No       | `data/thumbnails` | -       | Directory for video thumbnails    |
| `VIDEO_MAX_FRAMES`             | No       | `20`              | 1-300   | Max frames to extract per video   |

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

| Variable        | Required | Default | Description                                               |
| --------------- | -------- | ------- | --------------------------------------------------------- |
| `ADMIN_ENABLED` | No       | `true`  | Enable admin endpoints (seeding, cache clearing, cleanup) |
| `ADMIN_API_KEY` | No       | -       | API key for admin endpoints (`X-Admin-API-Key` header)    |

> **Security:** Admin endpoints are enabled by default for single-user local deployments; network binding to 127.0.0.1 is the primary security boundary. The `require_admin_access` dependency (`backend/api/routes/admin.py`) gates on `ADMIN_ENABLED` alone — the `DEBUG=true` pairing in the config.py comment is not enforced in the route code. When `ADMIN_API_KEY` is set, all admin requests must include the `X-Admin-API-Key` header.

---

## Cache TTL Settings

| Variable                 | Required | Default | Range    | Description                     |
| ------------------------ | -------- | ------- | -------- | ------------------------------- |
| `CACHE_TTL_EVENTS`       | No       | `60`    | 30-3600s | TTL for event list cache        |
| `CACHE_TTL_CAMERAS`      | No       | `300`   | 60-3600s | TTL for camera list cache       |
| `CACHE_TTL_DETECTIONS`   | No       | `120`   | 30-3600s | TTL for detection cache         |
| `CACHE_TTL_SYSTEM_STATS` | No       | `30`    | 10-300s  | TTL for system statistics cache |
| `CACHE_TTL_AI_HEALTH`    | No       | `60`    | 30-600s  | TTL for AI health status cache  |

---

## Internal Service Timeouts

| Variable                       | Required | Default | Range  | Description                    |
| ------------------------------ | -------- | ------- | ------ | ------------------------------ |
| `INTERNAL_TIMEOUT_DATABASE`    | No       | `30.0`  | 5-120s | Database query timeout         |
| `INTERNAL_TIMEOUT_REDIS`       | No       | `10.0`  | 1-60s  | Redis operation timeout        |
| `INTERNAL_TIMEOUT_HEALTHCHECK` | No       | `5.0`   | 1-30s  | Health check operation timeout |

---

## Worker Supervisor

| Variable                          | Required | Default | Range | Description                         |
| --------------------------------- | -------- | ------- | ----- | ----------------------------------- |
| `WORKER_SUPERVISOR_ENABLED`       | No       | `true`  | -     | Enable background worker supervisor |
| `WORKER_SUPERVISOR_MAX_RESTARTS`  | No       | `5`     | 1-20  | Max restarts before giving up       |
| `WORKER_SUPERVISOR_RESTART_DELAY` | No       | `5.0`   | 1-60s | Seconds to wait between restarts    |

---

## Orchestrator Settings

| Variable                            | Required | Default | Range  | Description                       |
| ----------------------------------- | -------- | ------- | ------ | --------------------------------- |
| `ORCHESTRATOR_POLL_INTERVAL`        | No       | `1.0`   | 0.1-5s | Polling interval for work items   |
| `ORCHESTRATOR_MAX_CONCURRENT_TASKS` | No       | `4`     | 1-32   | Max concurrent orchestrator tasks |
| `ORCHESTRATOR_SHUTDOWN_TIMEOUT`     | No       | `30.0`  | 5-120s | Grace period for shutdown         |

---

## Job Management

| Variable                  | Required | Default | Range    | Description                         |
| ------------------------- | -------- | ------- | -------- | ----------------------------------- |
| `JOB_TIMEOUT_SECONDS`     | No       | `300`   | 60-3600s | Default timeout for background jobs |
| `JOB_MAX_RETRIES`         | No       | `3`     | 1-10     | Max retry attempts for failed jobs  |
| `JOB_RETRY_DELAY_SECONDS` | No       | `60`    | 10-600s  | Delay between job retries           |

---

## Pagination

| Variable                   | Required | Default | Range     | Description               |
| -------------------------- | -------- | ------- | --------- | ------------------------- |
| `PAGINATION_DEFAULT_LIMIT` | No       | `50`    | 1-1000    | Default items per page    |
| `PAGINATION_MAX_LIMIT`     | No       | `1000`  | 100-10000 | Maximum allowed page size |

---

## Transcode Cache

Settings come from `TranscodeCacheSettings` (`env_prefix="TRANSCODE_CACHE_"`).

| Variable                                    | Required | Default                | Range    | Description                                            |
| ------------------------------------------- | -------- | ---------------------- | -------- | ------------------------------------------------------ |
| `TRANSCODE_CACHE_DIR`                       | No       | `data/transcode_cache` | -        | Directory for transcoded media cache                   |
| `TRANSCODE_CACHE_MAX_CACHE_SIZE_GB`         | No       | `10.0`                 | 0.1-1000 | Max cache size in GB (LRU eviction above this)         |
| `TRANSCODE_CACHE_MAX_FILE_AGE_DAYS`         | No       | `7`                    | 1-365    | Age after which cached files are eligible for eviction |
| `TRANSCODE_CACHE_CLEANUP_THRESHOLD_PERCENT` | No       | `0.9`                  | 0.5-0.99 | Trigger cleanup at this fraction of max size           |
| `TRANSCODE_CACHE_CLEANUP_TARGET_PERCENT`    | No       | `0.8`                  | 0.3-0.95 | Cleanup removes files until this fraction              |
| `TRANSCODE_CACHE_LOCK_TIMEOUT_SECONDS`      | No       | `30`                   | 1-300    | Timeout for cache operation locks                      |
| `TRANSCODE_CACHE_ENABLED`                   | No       | `true`                 | -        | Enable the transcode cache                             |

---

## Thumbnail Settings

| Variable            | Required | Default | Range   | Description                 |
| ------------------- | -------- | ------- | ------- | --------------------------- |
| `THUMBNAIL_WIDTH`   | No       | `320`   | 100-800 | Thumbnail width in pixels   |
| `THUMBNAIL_HEIGHT`  | No       | `240`   | 100-600 | Thumbnail height in pixels  |
| `THUMBNAIL_QUALITY` | No       | `85`    | 50-100  | JPEG quality for thumbnails |

---

## Hardware Acceleration

| Variable                        | Required | Default | Description                                                      |
| ------------------------------- | -------- | ------- | ---------------------------------------------------------------- |
| `HARDWARE_ACCELERATION_ENABLED` | No       | `true`  | Enable NVIDIA NVENC hardware acceleration for video transcoding  |
| `NVENC_PRESET`                  | No       | `p4`    | NVENC encoding preset: p1 (fastest) to p7 (slowest/best quality) |
| `NVENC_CQ`                      | No       | `23`    | NVENC constant quality (CQ), 0-51; lower = higher quality        |

> Falls back to software encoding (libx264) when NVENC is unavailable. There is no `HARDWARE_ACCEL_DEVICE` variable — device selection is NVENC-only.

---

## Performance Profiling

| Variable                    | Required | Default         | Description                                      |
| --------------------------- | -------- | --------------- | ------------------------------------------------ |
| `PROFILING_ENABLED`         | No       | `false`         | Enable cProfile profiling of decorated functions |
| `PROFILING_OUTPUT_DIR`      | No       | `data/profiles` | Directory for `.prof` output files               |
| `SLOW_REQUEST_THRESHOLD_MS` | No       | `500`           | Log requests slower than this (ms)               |

---

## Slow Query Logging

| Variable                  | Required | Default | Range      | Description                  |
| ------------------------- | -------- | ------- | ---------- | ---------------------------- |
| `SLOW_QUERY_THRESHOLD_MS` | No       | `100`   | 10-10000ms | Log queries slower than this |
| `SLOW_QUERY_LOG_ENABLED`  | No       | `true`  | -          | Enable slow query logging    |

---

## Request Logging

| Variable                  | Required | Default | Description                                                              |
| ------------------------- | -------- | ------- | ------------------------------------------------------------------------ |
| `REQUEST_LOGGING_ENABLED` | No       | `true`  | Log incoming HTTP requests (structured, with timing and correlation IDs) |

> `REQUEST_LOGGING_BODY` / `REQUEST_LOGGING_HEADERS` do not exist in the code — `RequestLoggingMiddleware` has no body/header options.

---

## Request Recording

| Variable                          | Required | Default | Description                                                     |
| --------------------------------- | -------- | ------- | --------------------------------------------------------------- |
| `REQUEST_RECORDING_ENABLED`       | No       | `false` | Record requests for replay/debugging (5xx always recorded)      |
| `REQUEST_RECORDING_SAMPLE_RATE`   | No       | `0.01`  | Fraction of successful requests sampled for recording (0.0-1.0) |
| `REQUEST_RECORDING_MAX_BODY_SIZE` | No       | `10000` | Max request/response body to record in bytes (truncated above)  |

> The recordings directory is not env-configurable — `REQUEST_RECORDING_DIR` does not exist; recordings land in `data/recordings` (`DEFAULT_RECORDINGS_DIR`, a constructor argument of `RequestRecorderMiddleware`).

---

## HSTS Configuration

| Variable       | Required | Default | Description                       |
| -------------- | -------- | ------- | --------------------------------- |
| `HSTS_PRELOAD` | No       | `false` | Allow HSTS preload list inclusion |

> Only `HSTS_PRELOAD` is an env variable (config field passed to `SecurityHeadersMiddleware` in `backend/main.py`). The HSTS header itself is always sent on HTTPS responses with constructor defaults max-age=31536000 (1 year) and includeSubDomains=true — `HSTS_ENABLED`, `HSTS_MAX_AGE` and `HSTS_INCLUDE_SUBDOMAINS` are middleware constructor arguments, not env-configurable.

---

## Idempotency

| Variable                  | Required | Default | Range       | Description                      |
| ------------------------- | -------- | ------- | ----------- | -------------------------------- |
| `IDEMPOTENCY_ENABLED`     | No       | `true`  | -           | Enable idempotency key support   |
| `IDEMPOTENCY_TTL_SECONDS` | No       | `86400` | 3600-604800 | TTL for idempotency keys (1 day) |

---

## Background Evaluation

| Variable                                   | Required | Default | Range | Description                                                |
| ------------------------------------------ | -------- | ------- | ----- | ---------------------------------------------------------- |
| `BACKGROUND_EVALUATION_ENABLED`            | No       | `true`  | -     | Enable background model evaluation when GPU is idle        |
| `BACKGROUND_EVALUATION_GPU_IDLE_THRESHOLD` | No       | `20`    | 0-100 | GPU utilization % at or below which the GPU counts as idle |
| `BACKGROUND_EVALUATION_IDLE_DURATION`      | No       | `5`     | 1-300 | Seconds GPU must stay idle before evaluation starts        |
| `BACKGROUND_EVALUATION_POLL_INTERVAL`      | No       | `5.0`   | 1-60s | How often (seconds) to check evaluation conditions         |

> `BACKGROUND_EVAL_ENABLED`/`BACKGROUND_EVAL_INTERVAL` do not exist under those names. Evaluation is idle-gated, not fixed-interval: the documented "3600 s interval" had no counterpart in code — the closest knob, `BACKGROUND_EVALUATION_POLL_INTERVAL`, is the 5 s condition check.

---

## Orphan File Cleanup

Configuration for periodic cleanup of orphaned files (files on disk without corresponding database records).

| Variable                             | Required | Default | Range | Description                                                |
| ------------------------------------ | -------- | ------- | ----- | ---------------------------------------------------------- |
| `ORPHAN_CLEANUP_ENABLED`             | No       | `true`  | -     | Enable periodic cleanup of orphaned files                  |
| `ORPHAN_CLEANUP_SCAN_INTERVAL_HOURS` | No       | `24`    | 1-168 | Hours between cleanup scans (default: daily)               |
| `ORPHAN_CLEANUP_AGE_THRESHOLD_HOURS` | No       | `24`    | 1-720 | Minimum age (hours) before an orphaned file can be deleted |

> **Safety:** Files younger than `ORPHAN_CLEANUP_AGE_THRESHOLD_HOURS` are skipped to allow for incomplete processing. This prevents deletion of files that may still be in use.

---

## Model Zoo

Configuration for the Model Zoo, which provides on-demand AI model loading during enrichment.

| Variable         | Required | Default             | Description                                   |
| ---------------- | -------- | ------------------- | --------------------------------------------- |
| `MODEL_ZOO_PATH` | No       | `/models/model-zoo` | Base directory path for Model Zoo model files |

The Model Zoo contains supplementary AI models loaded on-demand during batch processing:

- License plate detection (yolo11-license-plate)
- Face detection (yolo11-face)
- OCR text extraction (paddleocr)
- Clothing segmentation (segformer-b2-clothes)
- Violence detection
- Weather classification
- And more

> **Note:** Models are loaded sequentially within a ~1,650 MB VRAM budget (shared with the primary Nemotron and YOLO26 models).

---

## Frontend (Build-Time)

The `VITE_*` variables are embedded at frontend build time; the `FRONTEND_*` port variables are consumed by `docker-compose.prod.yml` at deploy time:

| Variable                 | Required | Default                 | Description                              |
| ------------------------ | -------- | ----------------------- | ---------------------------------------- |
| `VITE_API_BASE_URL`      | No       | `http://localhost:8000` | Backend API URL                          |
| `VITE_WS_BASE_URL`       | No       | `ws://localhost:8000`   | WebSocket URL                            |
| `FRONTEND_HTTP_PORT`     | No       | `8080`                  | Host port mapped to frontend nginx HTTP  |
| `FRONTEND_HTTPS_PORT`    | No       | `8444`                  | Host port mapped to frontend nginx HTTPS |
| `FRONTEND_INTERNAL_PORT` | No       | `8080`                  | Container port for nginx (health checks) |

> `FRONTEND_PORT=5173` is dead in `docker-compose.prod.yml` — the compose file never references it (5173 only survives as the Vite dev-server target in `frontend/Dockerfile`). It is still consumed by `scripts/test-docker.sh` and a `setup.py` port-scanner entry, but it does not affect deployed frontend ports.

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

[Back to Operator Hub](../../operator/README.md) | [Developer Hub](../../developer/README.md)
