# Environment Variables

This document provides comprehensive documentation for all environment variables used in the Home Security Intelligence application.

## Quick Start

Choose an environment profile based on your deployment:

- **Development**: `cp docs/.env.development .env` - Local development with debug features
- **Staging**: `cp docs/.env.staging .env` - Pre-production testing environment
- **Production**: `cp docs/.env.production .env` - Hardened production deployment

After copying, customize the required values (marked with `CHANGE_ME_`).

## Environment Profiles

| Profile     | Debug    | Auth        | TLS         | Retention | Rate Limiting | Use Case                           |
| ----------- | -------- | ----------- | ----------- | --------- | ------------- | ---------------------------------- |
| Development | Enabled  | Optional    | HTTP        | 7 days    | Disabled      | Local development and testing      |
| Staging     | Optional | Recommended | Recommended | 14 days   | Enabled       | Pre-production integration testing |
| Production  | Disabled | Required    | Required    | 30 days   | Enabled       | Live production deployment         |

## Quick Reference

| Variable            | Type    | Required  | Default                    | Security  | Environment  |
| ------------------- | ------- | --------- | -------------------------- | --------- | ------------ |
| **Database**        |
| `DATABASE_URL`      | string  | Yes       | -                          | SENSITIVE | All          |
| `POSTGRES_USER`     | string  | Yes       | -                          | SENSITIVE | All          |
| `POSTGRES_PASSWORD` | string  | Yes       | -                          | SENSITIVE | All          |
| `POSTGRES_DB`       | string  | Yes       | -                          | Standard  | All          |
| **Redis**           |
| `REDIS_URL`         | string  | Yes       | `redis://localhost:6379/0` | Standard  | All          |
| `REDIS_PASSWORD`    | string  | Prod only | -                          | SENSITIVE | Staging/Prod |
| `REDIS_SSL_ENABLED` | boolean | No        | `false`                    | Standard  | All          |
| **AI Services**     |
| `RTDETR_URL`        | string  | Yes       | `http://localhost:8090`    | Standard  | All          |
| `NEMOTRON_URL`      | string  | Yes       | `http://localhost:8091`    | Standard  | All          |
| `RTDETR_API_KEY`    | string  | Prod only | -                          | SENSITIVE | Prod         |
| `NEMOTRON_API_KEY`  | string  | Prod only | -                          | SENSITIVE | Prod         |
| **Application**     |
| `DEBUG`             | boolean | No        | `false`                    | Standard  | All          |
| `API_HOST`          | string  | No        | `0.0.0.0`                  | Standard  | All          |
| `API_PORT`          | integer | No        | `8000`                     | Standard  | All          |
| `LOG_LEVEL`         | string  | No        | `INFO`                     | Standard  | All          |
| **Security**        |
| `API_KEY_ENABLED`   | boolean | Prod only | `false`                    | Standard  | Prod         |
| `API_KEYS`          | array   | Prod only | `[]`                       | SENSITIVE | Prod         |
| `TLS_MODE`          | string  | No        | `disabled`                 | Standard  | All          |
| `TLS_CERT_PATH`     | string  | Prod only | -                          | Standard  | Prod         |
| `TLS_KEY_PATH`      | string  | Prod only | -                          | SENSITIVE | Prod         |
| **Frontend**        |
| `VITE_API_BASE_URL` | string  | Yes       | `http://localhost:8000`    | Standard  | All          |
| `VITE_WS_BASE_URL`  | string  | Yes       | `ws://localhost:8000`      | Standard  | All          |

## Database Configuration

### DATABASE_URL

PostgreSQL database connection URL using asyncpg driver.

- **Type:** string
- **Required:** Yes
- **Default:** None
- **Security:** SENSITIVE - Contains credentials, never commit to version control
- **Format:** `postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>`
- **Environments:**
  - Development: `postgresql+asyncpg://security_dev:password@localhost:5432/security_dev` <!-- pragma: allowlist secret -->
  - Staging: `postgresql+asyncpg://user:password@postgres:5432/dbname` <!-- pragma: allowlist secret -->
  - Production: `postgresql+asyncpg://user:password@postgres:5432/dbname` <!-- pragma: allowlist secret -->

**Example:**

```bash
DATABASE_URL=postgresql+asyncpg://security:mysecurepass@localhost:5432/security  # pragma: allowlist secret
```

**Validation:**

- Must start with `postgresql://` or `postgresql+asyncpg://`
- SQLite is not supported

### POSTGRES_USER

PostgreSQL username for container/server authentication.

- **Type:** string
- **Required:** Yes (for Docker deployments)
- **Default:** None
- **Security:** SENSITIVE - Use unique credentials per environment
- **Environments:**
  - Development: `security_dev`
  - Staging/Production: Generate unique username

**Note:** Must match the username in `DATABASE_URL`.

### POSTGRES_PASSWORD

PostgreSQL password for database authentication.

- **Type:** string
- **Required:** Yes
- **Default:** None
- **Security:** SENSITIVE - Never commit real passwords
- **Generation:** `openssl rand -base64 32`
- **Best Practices:**
  - Use different passwords for each environment
  - Minimum 32 characters recommended
  - Rotate passwords periodically in production
  - Consider using secrets management (HashiCorp Vault, AWS Secrets Manager)

**Example:**

```bash
POSTGRES_PASSWORD=x7Kp2mN9qR4sT8vW1yZ3aB5cD6eF7gH8  # pragma: allowlist secret
```

### POSTGRES_DB

PostgreSQL database name.

- **Type:** string
- **Required:** Yes (for Docker deployments)
- **Default:** None
- **Security:** Standard
- **Environments:**
  - Development: `security_dev`
  - Staging: `security_staging`
  - Production: `security_prod`

**Note:** Must match the database name in `DATABASE_URL`.

### Database Connection Pool Settings

#### DATABASE_POOL_SIZE

Base number of database connections to maintain in the connection pool.

- **Type:** integer
- **Required:** No
- **Default:** 20
- **Range:** 5-100
- **Security:** Standard
- **Environments:**
  - Development: 5 (single developer)
  - Staging: 15 (moderate load)
  - Production: 20 (high load)

**Tuning Guide:**

- Too small: Connection starvation, increased latency
- Too large: Increased memory usage, PostgreSQL connection limits
- Formula: `pool_size + pool_overflow <= PostgreSQL max_connections - reserved`

#### DATABASE_POOL_OVERFLOW

Additional connections allowed beyond `pool_size` when under load.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 0-100
- **Security:** Standard
- **Environments:**
  - Development: 10
  - Staging: 20
  - Production: 30

#### DATABASE_POOL_TIMEOUT

Seconds to wait for an available connection before raising a timeout error.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 5-120
- **Security:** Standard
- **Tuning:** Increase if seeing frequent timeout errors under load.

#### DATABASE_POOL_RECYCLE

Seconds after which connections are recycled to prevent stale connections.

- **Type:** integer
- **Required:** No
- **Default:** 1800 (30 minutes)
- **Range:** 300-7200
- **Security:** Standard
- **Best Practice:** Set lower than PostgreSQL `idle_in_transaction_session_timeout`.

## Redis Configuration

### REDIS_URL

Redis connection URL for caching and pub/sub messaging.

- **Type:** string
- **Required:** Yes
- **Default:** `redis://localhost:6379/0`
- **Security:** Standard (SENSITIVE if password embedded)
- **Format:** `redis://[password@]<host>:<port>/<database>`
- **For TLS:** `rediss://<host>:<port>/<database>` (note double 's')
- **Environments:**
  - Development: `redis://localhost:6379/0`
  - Staging/Production: `redis://redis:6379/0`

**Example:**

```bash
# Without password (development)
REDIS_URL=redis://localhost:6379/0

# With password (production - use REDIS_PASSWORD instead)
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=mysecurepassword
```

**Validation:**

- Must start with `redis://` or `rediss://`
- Host component is required

### REDIS_PASSWORD

Redis password for authentication.

- **Type:** string
- **Required:** No (development), Yes (production)
- **Default:** None (no authentication)
- **Security:** SENSITIVE - Never commit
- **Generation:** `openssl rand -base64 32`
- **Environments:**
  - Development: Not set (no password)
  - Staging/Production: Required

**Best Practices:**

- Always set in production
- Must match Redis server's `requirepass` directive
- Use different passwords per environment

### REDIS_KEY_PREFIX

Global prefix for all Redis keys to enable key isolation.

- **Type:** string
- **Required:** No
- **Default:** `hsi`
- **Security:** Standard
- **Use Cases:**
  - Multi-instance deployments (append instance ID)
  - Blue-green deployments (use different prefixes)
  - Tenant isolation

**Example:**

```bash
REDIS_KEY_PREFIX=hsi-prod-v2
```

All Redis keys will be prefixed: `hsi-prod-v2:camera:front_door`, `hsi-prod-v2:batch:123`, etc.

### Redis SSL/TLS Settings

#### REDIS_SSL_ENABLED

Enable SSL/TLS encryption for Redis connections.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard (enables encryption in transit)
- **Environments:**
  - Development: `false`
  - Staging: Recommended
  - Production: Strongly recommended

**Impact:**

- When enabled, all Redis traffic (cached data, session info, pub/sub messages) is encrypted
- Requires Redis server configured with TLS certificates
- May slightly increase latency due to encryption overhead

#### REDIS_SSL_CERT_REQS

SSL certificate verification mode.

- **Type:** string
- **Required:** No
- **Default:** `required`
- **Options:**
  - `none` - No verification (NOT recommended)
  - `optional` - Verify if certificate provided
  - `required` - Always verify (RECOMMENDED)
- **Security:** Standard
- **Environments:**
  - Development: `none` (if using self-signed certs for testing)
  - Staging/Production: `required`

#### REDIS_SSL_CA_CERTS

Path to CA certificate file for verifying Redis server certificate.

- **Type:** string (file path)
- **Required:** When `REDIS_SSL_CERT_REQS` is `required` or `optional`
- **Default:** None
- **Security:** Standard
- **Format:** PEM format

**Example:**

```bash
REDIS_SSL_CA_CERTS=/path/to/redis-ca.crt
```

#### REDIS_SSL_CERTFILE

Path to client certificate file for mutual TLS (mTLS).

- **Type:** string (file path)
- **Required:** Only if Redis requires client certificates
- **Default:** None
- **Security:** Standard
- **Format:** PEM format

#### REDIS_SSL_KEYFILE

Path to client private key file for mutual TLS (mTLS).

- **Type:** string (file path)
- **Required:** When `REDIS_SSL_CERTFILE` is set
- **Default:** None
- **Security:** SENSITIVE - Protect private key file permissions (chmod 600)
- **Format:** PEM format

#### REDIS_SSL_CHECK_HOSTNAME

Verify Redis server's certificate hostname matches.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Environments:**
  - Development: `false` (for self-signed certs)
  - Production: `true`

## AI Services Configuration

### RTDETR_URL

RT-DETRv2 object detection service URL.

- **Type:** string (HTTP/HTTPS URL)
- **Required:** Yes
- **Default:** `http://localhost:8090`
- **Security:** Standard (use HTTPS in production)
- **Validation:** Must be valid HTTP/HTTPS URL
- **Environments:**
  - Development: `http://localhost:8090`
  - Staging: `http://ai-detector:8090` or `https://ai-detector.staging.example.com:8090`
  - Production: `https://ai-detector.example.com:8090` (HTTPS required)

**Security Note:** HTTP is acceptable for local development only. Use HTTPS in production to prevent man-in-the-middle (MITM) attacks on AI inference requests.

### NEMOTRON_URL

Nemotron LLM risk analysis service URL (llama.cpp server).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** Yes
- **Default:** `http://localhost:8091`
- **Security:** Standard (use HTTPS in production)
- **Validation:** Must be valid HTTP/HTTPS URL
- **Environments:**
  - Development: `http://localhost:8091`
  - Staging: `http://ai-llm:8091`
  - Production: `https://ai-llm.example.com:8091` (HTTPS required)

### FLORENCE_URL

Florence-2 vision-language extraction service URL (optional).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** No
- **Default:** `http://localhost:8092`
- **Security:** Standard
- **Feature:** Vehicle/person attribute extraction

### CLIP_URL

CLIP entity re-identification service URL (optional).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** No
- **Default:** `http://localhost:8093`
- **Security:** Standard
- **Feature:** Cross-camera entity tracking

### ENRICHMENT_URL

Combined enrichment service URL for vehicle, pet, and clothing classification (optional).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** No
- **Default:** `http://localhost:8094`
- **Security:** Standard

### AI Service Authentication

#### RTDETR_API_KEY

API key for RT-DETR service authentication (optional, sent via `X-API-Key` header).

- **Type:** string
- **Required:** No (development), Recommended (production)
- **Default:** None
- **Security:** SENSITIVE - Never commit
- **Generation:** `openssl rand -hex 32`

#### NEMOTRON_API_KEY

API key for Nemotron service authentication (optional, sent via `X-API-Key` header).

- **Type:** string
- **Required:** No (development), Recommended (production)
- **Default:** None
- **Security:** SENSITIVE - Never commit
- **Generation:** `openssl rand -hex 32`

### AI Service Timeout Settings

#### AI_CONNECT_TIMEOUT

Maximum time (seconds) to establish connection to AI services.

- **Type:** float
- **Required:** No
- **Default:** 10.0
- **Range:** 1.0-60.0
- **Security:** Standard
- **Environments:**
  - Development: 15.0 (relaxed for debugging)
  - Staging/Production: 10.0

#### AI_HEALTH_TIMEOUT

Timeout (seconds) for AI service health checks.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-30.0
- **Security:** Standard

#### RTDETR_READ_TIMEOUT

Maximum time (seconds) to wait for RT-DETR detection response.

- **Type:** float
- **Required:** No
- **Default:** 60.0
- **Range:** 10.0-300.0
- **Security:** Standard
- **Tuning:** Increase if processing high-resolution images or large batches.

#### NEMOTRON_READ_TIMEOUT

Maximum time (seconds) to wait for Nemotron LLM response.

- **Type:** float
- **Required:** No
- **Default:** 120.0
- **Range:** 30.0-600.0
- **Security:** Standard
- **Tuning:** Increase if LLM is slow or context window is large.

### AI Service Retry Settings

#### DETECTOR_MAX_RETRIES

Maximum retry attempts for RT-DETR detector on transient failures.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard
- **Backoff:** Exponential (2^attempt seconds, capped at 30s)

#### NEMOTRON_MAX_RETRIES

Maximum retry attempts for Nemotron LLM on transient failures.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard
- **Backoff:** Exponential (2^attempt seconds, capped at 30s)

#### ENRICHMENT_MAX_RETRIES

Maximum retry attempts for enrichment service on transient failures.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard
- **Backoff:** Exponential with jitter (2^attempt ± 10%, capped at 30s)

#### REID_MAX_RETRIES

Maximum retry attempts for ReID embedding generation on transient failures.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard

### AI Concurrency Settings

#### AI_MAX_CONCURRENT_INFERENCES

Maximum concurrent AI inference operations (RT-DETR + Nemotron combined).

- **Type:** integer
- **Required:** No
- **Default:** 4
- **Range:** 1-32
- **Security:** Standard
- **Environments:**
  - Development: 2 (single developer, lower GPU usage)
  - Staging: 4
  - Production: Adjust based on GPU VRAM and throughput requirements

**Tuning Guide:**

- Lower value: Reduces GPU memory usage, increases latency under high load
- Higher value: Better throughput but risks GPU OOM on memory-constrained GPUs
- Consider GPU VRAM, batch sizes, and expected traffic patterns

### AI Warmup and Cold Start Settings

#### AI_WARMUP_ENABLED

Enable model warmup on service startup.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Feature:** Sends test inference to preload model weights into GPU memory, reducing first-request latency

#### AI_COLD_START_THRESHOLD_SECONDS

Seconds since last inference before model is considered "cold".

- **Type:** float
- **Required:** No
- **Default:** 300.0 (5 minutes)
- **Range:** 60.0-3600.0
- **Security:** Standard
- **Behavior:** Cold models may have slower first inference due to GPU memory paging

#### NEMOTRON_WARMUP_PROMPT

Test prompt used for Nemotron warmup.

- **Type:** string
- **Required:** No
- **Default:** `"Hello, please respond with 'ready' to confirm you are operational."`
- **Security:** Standard
- **Best Practice:** Keep simple and quick to process

### Nemotron Context Window Settings

#### NEMOTRON_CONTEXT_WINDOW

Nemotron-3-Nano context window size in tokens.

- **Type:** integer
- **Required:** No
- **Default:** 3900
- **Range:** 1000-128000
- **Security:** Standard
- **Model-Specific:** Nemotron-3-Nano supports 4096 tokens; 3900 leaves room for output

**Note:** Prompts exceeding `context_window - max_output_tokens` will be truncated if `CONTEXT_TRUNCATION_ENABLED=true`.

#### NEMOTRON_MAX_OUTPUT_TOKENS

Maximum tokens reserved for Nemotron LLM output.

- **Type:** integer
- **Required:** No
- **Default:** 1536
- **Range:** 100-8192
- **Security:** Standard
- **Validation:** Input prompts are validated against `context_window - max_output_tokens`

#### CONTEXT_UTILIZATION_WARNING_THRESHOLD

Log warning when context utilization exceeds this threshold.

- **Type:** float
- **Required:** No
- **Default:** 0.80
- **Range:** 0.5-0.95
- **Security:** Standard
- **Purpose:** Identify prompts approaching context limits before truncation occurs

#### CONTEXT_TRUNCATION_ENABLED

Enable intelligent truncation of enrichment data when approaching context limits.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Behavior:**
  - `true`: Less critical enrichment data is removed to fit within context window
  - `false`: Prompts exceeding limits will fail with an error

#### LLM_TOKENIZER_ENCODING

Tiktoken encoding to use for token counting.

- **Type:** string
- **Required:** No
- **Default:** `cl100k_base`
- **Options:** `cl100k_base` (GPT-4/ChatGPT), `p50k_base` (Codex), `r50k_base` (GPT-2)
- **Security:** Standard
- **Note:** `cl100k_base` is a reasonable default for most LLMs

## Camera Integration

### FOSCAM_BASE_PATH

Base directory for Foscam FTP uploads.

- **Type:** string (directory path)
- **Required:** Yes
- **Default:** `/export/foscam`
- **Security:** Standard
- **Structure:** Cameras upload to `{FOSCAM_BASE_PATH}/{camera_name}/`

**Example:**

```bash
FOSCAM_BASE_PATH=/export/foscam

# Camera uploads go to:
# /export/foscam/front_door/
# /export/foscam/backyard/
# /export/foscam/garage/
```

**Permissions:** Ensure the application has read access to this directory.

## File Watcher Configuration

### FILE_WATCHER_POLLING

Use polling observer instead of native filesystem events.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Environments:**
  - Development (Linux/macOS native): `false` (more efficient)
  - Development (Docker Desktop macOS/Windows): `true` (inotify/FSEvents don't work across volume mounts)
  - Production (native Linux): `false`

**Performance:**

- Native observers (inotify on Linux, FSEvents on macOS): Lower CPU, immediate detection
- Polling observer: Higher CPU, detection delay based on polling interval

### FILE_WATCHER_POLLING_INTERVAL

Polling interval in seconds when `FILE_WATCHER_POLLING=true`.

- **Type:** float
- **Required:** No
- **Default:** 1.0
- **Range:** 0.1-30.0
- **Security:** Standard
- **Tuning:**
  - Lower values (0.5-1.0): Faster detection, higher CPU usage
  - Higher values (5.0-30.0): Lower CPU, slower detection

## Detection Settings

### DETECTION_CONFIDENCE_THRESHOLD

Minimum confidence threshold for object detections.

- **Type:** float
- **Required:** No
- **Default:** 0.5
- **Range:** 0.0-1.0
- **Security:** Standard
- **Tuning:**
  - Lower (0.3-0.4): More detections, more false positives
  - Higher (0.6-0.8): Fewer false positives, may miss legitimate detections

### FAST_PATH_CONFIDENCE_THRESHOLD

Confidence threshold for fast path high-priority analysis.

- **Type:** float
- **Required:** No
- **Default:** 0.90
- **Range:** 0.0-1.0
- **Security:** Standard
- **Feature:** High-confidence detections bypass batching for immediate alerts

### FAST_PATH_OBJECT_TYPES

Object types that trigger fast path analysis when confidence threshold is met.

- **Type:** JSON array of strings
- **Required:** No
- **Default:** `["person"]`
- **Security:** Standard
- **Example:** `["person","vehicle","dog"]`

## Batch Processing Configuration

### BATCH_WINDOW_SECONDS

Maximum time window for grouping detections into events.

- **Type:** integer
- **Required:** No
- **Default:** 90
- **Security:** Standard
- **Behavior:** Detections within this window from the same camera are grouped into a single event

### BATCH_IDLE_TIMEOUT_SECONDS

Close batch after this many seconds of inactivity.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Security:** Standard
- **Behavior:** If no new detections arrive within this timeout, the batch is closed and processed

### BATCH_CHECK_INTERVAL_SECONDS

Interval (seconds) between batch timeout checks.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-60.0
- **Security:** Standard
- **Tuning:**
  - Lower values: Reduce latency between timeout and batch close, higher CPU usage
  - Higher values: Lower CPU, increased latency

### BATCH_MAX_DETECTIONS

Maximum detections per batch before splitting.

- **Type:** integer
- **Required:** No
- **Default:** 500
- **Range:** 1-10000
- **Security:** Standard
- **Feature:** Prevents memory exhaustion and LLM timeouts with large batches
- **Behavior:** When batch reaches this limit, it is closed and a new batch is created

## Retention Configuration

### RETENTION_DAYS

Number of days to retain events and detections.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Security:** Standard
- **Environments:**
  - Development: 7 (less storage usage)
  - Staging: 14
  - Production: 30 (or adjust based on compliance requirements)

**Storage Impact:**

- Longer retention: More disk space for images, detections, and events
- Consider database size, image storage capacity, and backup costs

### LOG_RETENTION_DAYS

Number of days to retain log entries in database.

- **Type:** integer
- **Required:** No
- **Default:** 7
- **Security:** Standard
- **Environments:**
  - Development: 3 (faster log table cleanup)
  - Staging/Production: 7

## Container Orchestrator Configuration

The container orchestrator provides health monitoring and self-healing for AI containers.

### ORCHESTRATOR_ENABLED

Enable container orchestration.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Feature:** Monitors AI container health and automatically restarts unhealthy containers

### ORCHESTRATOR_DOCKER_HOST

Docker/Podman host URL.

- **Type:** string
- **Required:** No
- **Default:** Auto-detect from `DOCKER_HOST` environment variable or socket
- **Security:** Standard
- **Options:**
  - `unix:///var/run/docker.sock` - Docker (rootful)
  - `unix:///run/user/1000/podman/podman.sock` - Podman (rootless)
  - `tcp://localhost:2375` - Docker TCP (not recommended for production)

### ORCHESTRATOR_HEALTH_CHECK_INTERVAL

Seconds between container health checks.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 5-300
- **Security:** Standard
- **Tuning:**
  - Lower values: Faster detection of unhealthy containers, more overhead
  - Higher values: Lower overhead, slower detection

### ORCHESTRATOR_HEALTH_CHECK_TIMEOUT

Timeout in seconds for individual health check HTTP requests.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-60
- **Security:** Standard
- **Best Practice:** Should be lower than `ORCHESTRATOR_HEALTH_CHECK_INTERVAL`

### ORCHESTRATOR_STARTUP_GRACE_PERIOD

Seconds to wait after container start before performing health checks.

- **Type:** integer
- **Required:** No
- **Default:** 60
- **Range:** 10-600
- **Security:** Standard
- **Purpose:** Allows time for AI models to load into GPU memory

### ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES

Number of consecutive health check failures before disabling automatic restart.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-50
- **Security:** Standard
- **Purpose:** Prevents restart loops for persistently failing containers

### ORCHESTRATOR_RESTART_BACKOFF_BASE

Base backoff time in seconds for restart attempts.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-60.0
- **Security:** Standard
- **Formula:** Actual delay = `min(base * 2^attempt, max)`

### ORCHESTRATOR_RESTART_BACKOFF_MAX

Maximum backoff time in seconds between restart attempts.

- **Type:** float
- **Required:** No
- **Default:** 300.0 (5 minutes)
- **Range:** 30.0-3600.0
- **Security:** Standard
- **Purpose:** Caps exponential backoff to prevent excessively long waits

## GPU Monitoring Configuration

### GPU_POLL_INTERVAL_SECONDS

How often to poll GPU stats via pynvml.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-60.0
- **Security:** Standard
- **Environments:**
  - Development: 2.0 (real-time visibility for debugging)
  - Staging/Production: 5.0 (balanced)

**Performance Considerations:**

- Each poll reads GPU utilization, VRAM, temperature, power usage
- Writes to database and broadcasts via WebSocket
- Lower values: More overhead but better real-time monitoring
- Higher values: Lower overhead, less granular data

### GPU_STATS_HISTORY_MINUTES

Minutes of GPU history to retain in memory.

- **Type:** integer
- **Required:** No
- **Default:** 60
- **Range:** 1-1440
- **Security:** Standard
- **Environments:**
  - Development: 30 (less memory usage)
  - Production: 60

### GPU_HTTP_TIMEOUT

HTTP timeout (seconds) for GPU stats collection from AI containers.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-60.0
- **Security:** Standard
- **Purpose:** Prevents hanging when AI services are unresponsive

## Logging Configuration

### LOG_LEVEL

Logging level for console and file output.

- **Type:** string
- **Required:** No
- **Default:** `INFO`
- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Security:** Standard
- **Environments:**
  - Development: `DEBUG` (detailed debugging info)
  - Staging: `INFO`
  - Production: `WARNING` (reduce noise)

### LOG_FILE_PATH

Path for rotating log file.

- **Type:** string (file path)
- **Required:** No
- **Default:** `data/logs/security.log`
- **Security:** Standard
- **Note:** Directory will be created automatically if it doesn't exist

### LOG_FILE_MAX_BYTES

Maximum size of each log file in bytes.

- **Type:** integer
- **Required:** No
- **Default:** 10485760 (10MB)
- **Security:** Standard
- **Behavior:** When file reaches this size, it is rotated

### LOG_FILE_BACKUP_COUNT

Number of backup log files to keep.

- **Type:** integer
- **Required:** No
- **Default:** 7
- **Security:** Standard
- **Example:** With 7 backups, you'll have `security.log`, `security.log.1`, ..., `security.log.7`

### LOG_DB_ENABLED

Write logs to database.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Feature:** Enables searchable log storage in PostgreSQL

### LOG_DB_MIN_LEVEL

Minimum log level to write to database.

- **Type:** string
- **Required:** No
- **Default:** `DEBUG`
- **Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Security:** Standard
- **Tuning:** Set to `INFO` in production to reduce database writes

### SLOW_QUERY_THRESHOLD_MS

Threshold in milliseconds for slow query detection.

- **Type:** float
- **Required:** No
- **Default:** 100.0
- **Range:** 10.0-10000.0
- **Security:** Standard
- **Feature:** Queries exceeding this threshold will have `EXPLAIN ANALYZE` logged

### SLOW_QUERY_EXPLAIN_ENABLED

Enable `EXPLAIN ANALYZE` logging for slow queries.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Environments:**
  - Development/Staging: `true` (debug performance issues)
  - Production: `false` (disable to reduce overhead)

### SLOW_REQUEST_THRESHOLD_MS

Threshold in milliseconds for logging slow API requests.

- **Type:** integer
- **Required:** No
- **Default:** 500
- **Range:** 1-60000
- **Security:** Standard
- **Feature:** Requests exceeding this duration are logged at WARNING level with method, path, status, and duration

## Application Settings

### DEBUG

Enable debug mode (development only).

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** CRITICAL - MUST be `false` in production
- **Environments:**
  - Development: `true`
  - Staging: `false` (or `true` for testing)
  - Production: `false` (REQUIRED)

**Security Impact:**

- Enables detailed error messages (may leak sensitive info)
- Enables admin endpoints (when combined with `ADMIN_ENABLED=true`)
- Bypasses certain security checks

### ADMIN_ENABLED

Enable admin endpoints.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** CRITICAL - MUST be `false` in production
- **Requirements:** Requires `DEBUG=true` as well (defense-in-depth)
- **Feature:** Enables admin API endpoints for testing and debugging

### ADMIN_API_KEY

Optional API key required for admin endpoints.

- **Type:** string
- **Required:** No
- **Default:** None
- **Security:** SENSITIVE - Never commit
- **Behavior:** When set, all admin requests must include `X-Admin-API-Key` header

### API_HOST

API server bind address.

- **Type:** string (IP address)
- **Required:** No
- **Default:** `0.0.0.0`
- **Security:** Standard
- **Options:**
  - `0.0.0.0` - Listen on all interfaces (Docker default)
  - `127.0.0.1` - Listen on localhost only (more secure for local dev)

### API_PORT

API server port.

- **Type:** integer
- **Required:** No
- **Default:** 8000
- **Security:** Standard
- **Note:** Must match port exposed in Docker Compose files

### APP_NAME

Application name for display and logging.

- **Type:** string
- **Required:** No
- **Default:** `"Home Security Intelligence"`
- **Security:** Standard

### APP_VERSION

Application version.

- **Type:** string
- **Required:** No
- **Default:** `"0.1.0"`
- **Security:** Standard

## CORS Configuration

### CORS_ORIGINS

Allowed CORS origins.

- **Type:** JSON array of strings
- **Required:** No
- **Default:** `["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173","http://0.0.0.0:3000","http://0.0.0.0:5173"]`
- **Security:** Standard
- **Environments:**
  - Development: Include all localhost ports
  - Staging: `["https://staging.example.com","http://localhost:5173"]`
  - Production: `["https://security.example.com"]` (production domain ONLY)

**Security Best Practices:**

- Never use `["*"]` in production (allows any origin)
- Limit to specific domains
- Use HTTPS URLs in production

**Example:**

```bash
# Development
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://192.168.1.145:5173"]

# Production
CORS_ORIGINS=["https://security.example.com"]
```

**Note:** In production with nginx proxy, CORS may not be needed if frontend and API are served from the same origin.

## Authentication Configuration

### API_KEY_ENABLED

Enable API key authentication.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Environments:**
  - Development: `false` (single-user local deployment)
  - Staging: `true` (recommended)
  - Production: `true` (REQUIRED)

### API_KEYS

List of valid API keys (plain text, hashed on startup).

- **Type:** JSON array of strings
- **Required:** When `API_KEY_ENABLED=true`
- **Default:** `[]`
- **Security:** SENSITIVE - Never commit real keys
- **Generation:** `openssl rand -hex 32`

**Example:**

```bash
API_KEYS=["key1_abc123def456","key2_ghi789jkl012"]
```

**Usage:**

- Clients include API key in `X-API-Key` header
- Keys are hashed with bcrypt on startup for secure comparison

## TLS/HTTPS Configuration

### TLS_MODE

TLS mode for HTTPS configuration.

- **Type:** string
- **Required:** No
- **Default:** `disabled`
- **Options:**
  - `disabled` - HTTP only (development)
  - `self_signed` - Auto-generate self-signed certificates (staging/testing)
  - `provided` - Use existing certificates (production)
- **Security:** Standard
- **Environments:**
  - Development: `disabled`
  - Staging: `self_signed` or `provided`
  - Production: `provided` (REQUIRED)

### TLS_CERT_PATH

Path to TLS certificate file (PEM format).

- **Type:** string (file path)
- **Required:** When `TLS_MODE=provided`
- **Default:** None
- **Security:** Standard
- **Format:** PEM format (X.509 certificate)

**Example:**

```bash
TLS_CERT_PATH=/path/to/security.example.com.crt
```

### TLS_KEY_PATH

Path to TLS private key file (PEM format).

- **Type:** string (file path)
- **Required:** When `TLS_MODE=provided`
- **Default:** None
- **Security:** SENSITIVE - Protect file permissions (chmod 600)
- **Format:** PEM format (RSA or ECDSA private key)

**Example:**

```bash
TLS_KEY_PATH=/path/to/security.example.com.key
```

### TLS_CA_PATH

Path to CA certificate for client verification (optional, for mutual TLS).

- **Type:** string (file path)
- **Required:** When `TLS_VERIFY_CLIENT=true`
- **Default:** None
- **Security:** Standard
- **Feature:** Enables mutual TLS (mTLS) authentication

### TLS_VERIFY_CLIENT

Require and verify client certificates (mutual TLS / mTLS).

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Feature:** When enabled, clients must present a valid certificate signed by `TLS_CA_PATH`

### TLS_MIN_VERSION

Minimum TLS version.

- **Type:** string
- **Required:** No
- **Default:** `TLSv1.2`
- **Options:** `TLSv1.2`, `TLSv1.3` (or `1.2`, `1.3`)
- **Security:** Standard
- **Environments:**
  - Staging: `TLSv1.2` (broader compatibility)
  - Production: `TLSv1.3` (best security)

**Note:** TLSv1.0 and TLSv1.1 are not supported due to known security vulnerabilities.

### TLS_CERT_DIR

Directory for auto-generated certificates (when `TLS_MODE=self_signed`).

- **Type:** string (directory path)
- **Required:** No
- **Default:** `data/certs`
- **Security:** Standard

### Legacy TLS Settings (Deprecated)

The following settings are deprecated in favor of `TLS_MODE`. They are kept for backward compatibility but will be removed in a future version.

- `TLS_ENABLED` - Use `TLS_MODE` instead
- `TLS_CERT_FILE` - Use `TLS_CERT_PATH` instead
- `TLS_KEY_FILE` - Use `TLS_KEY_PATH` instead
- `TLS_CA_FILE` - Use `TLS_CA_PATH` instead
- `TLS_AUTO_GENERATE` - Use `TLS_MODE=self_signed` instead

## Frontend Configuration

### VITE_DEV_BACKEND_URL

Backend API URL for Vite dev server proxy (used during `npm run dev`).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** No
- **Default:** `http://localhost:8000`
- **Security:** Standard
- **Feature:** Configures where the development proxy forwards `/api` and `/ws` requests
- **Use Case:** Remote development when backend runs on a different host

**Example:**

```bash
# Local backend
VITE_DEV_BACKEND_URL=http://localhost:8000

# Remote backend
VITE_DEV_BACKEND_URL=http://192.168.1.100:8000
```

### VITE_API_BASE_URL

Backend API URL (accessed from browser, not container).

- **Type:** string (HTTP/HTTPS URL)
- **Required:** Yes
- **Default:** `http://localhost:8000`
- **Security:** Standard
- **Environments:**
  - Development: `http://localhost:8000`
  - Staging: `https://staging.example.com`
  - Production: `https://security.example.com`

**Note:** This is embedded at build time. Rebuild frontend after changing.

### VITE_WS_BASE_URL

WebSocket URL (accessed from browser, not container).

- **Type:** string (WS/WSS URL)
- **Required:** Yes
- **Default:** `ws://localhost:8000`
- **Security:** Standard
- **Environments:**
  - Development: `ws://localhost:8000`
  - Staging: `wss://staging.example.com`
  - Production: `wss://security.example.com`

**Note:** Use `wss://` (secure WebSocket) in production.

### FRONTEND_URL

Frontend container URL for health checks (internal Docker network URL).

- **Type:** string (HTTP URL)
- **Required:** No
- **Default:** `http://frontend:80`
- **Security:** Standard
- **Options:**
  - Docker/Podman: `http://frontend:80`
  - Local dev: `http://localhost:5173`

### FRONTEND_PORT

Host port to expose the production frontend container.

- **Type:** integer
- **Required:** No
- **Default:** 5173
- **Security:** Standard
- **Note:** This is a docker-compose variable, not a Python config setting
- **Behavior:** Maps host port to container port 80 (nginx)

## Monitoring Stack Configuration

### PROMETHEUS_RETENTION_TIME

Prometheus data retention period.

- **Type:** string (duration)
- **Required:** No
- **Default:** `15d`
- **Format:** Number + unit (e.g., `15d`, `30d`, `90d`)
- **Security:** Standard
- **Environments:**
  - Development: `7d`
  - Staging: `14d`
  - Production: `30d` (or adjust based on compliance requirements)

**Storage Impact:** Longer retention requires more disk space.

### Grafana Configuration

#### GF_ADMIN_USER

Grafana admin username.

- **Type:** string
- **Required:** No
- **Default:** `admin`
- **Security:** Standard
- **Best Practice:** Change default username in production

#### GF_ADMIN_PASSWORD

Grafana admin password.

- **Type:** string
- **Required:** Yes (when using monitoring stack)
- **Default:** None
- **Security:** SENSITIVE - Never commit
- **Generation:** `openssl rand -base64 32`
- **Environments:**
  - Development: `admin` (acceptable for local)
  - Staging/Production: Strong password (REQUIRED)

#### GF_AUTH_ANONYMOUS_ENABLED

Enable anonymous access to Grafana dashboards.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Environments:**
  - Development: `true` (convenient for local dev)
  - Production: `false` (REQUIRED for security)

**Note:** Anonymous users get Viewer role only (read-only access).

### GRAFANA_URL

Grafana dashboard URL for frontend link.

- **Type:** string (HTTP/HTTPS URL)
- **Required:** No
- **Default:** `http://localhost:3002`
- **Security:** Standard (validated with SSRF protection)
- **Environments:**
  - Development: `http://localhost:3002`
  - Staging: `https://staging.example.com:3002`
  - Production: `https://security.example.com:3002`

**Validation:**

- Must be valid HTTP/HTTPS URL
- Cloud metadata endpoints blocked (SSRF protection)
- Internal IPs allowed (since Grafana is typically local)

## OpenTelemetry Tracing Configuration

### OTEL_ENABLED

Enable OpenTelemetry distributed tracing.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Environments:**
  - Development: `false` (enable for debugging)
  - Staging: `true` (performance analysis)
  - Production: `true` (observability)

### OTEL_SERVICE_NAME

Service name for OpenTelemetry traces.

- **Type:** string
- **Required:** No
- **Default:** `nemotron-backend`
- **Security:** Standard
- **Environments:**
  - Development: `nemotron-backend-dev`
  - Staging: `nemotron-backend-staging`
  - Production: `nemotron-backend-prod`

### OTEL_EXPORTER_OTLP_ENDPOINT

OTLP gRPC endpoint for trace export.

- **Type:** string (gRPC URL)
- **Required:** When `OTEL_ENABLED=true`
- **Default:** `http://localhost:4317`
- **Security:** Standard
- **Examples:**
  - Docker: `http://jaeger:4317`
  - Local dev: `http://localhost:4317`
  - Production: `https://jaeger.example.com:4317`

### OTEL_EXPORTER_OTLP_INSECURE

Use insecure (non-TLS) connection to OTLP endpoint.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Environments:**
  - Development/Staging: `true`
  - Production: `false` (use TLS)

### OTEL_TRACE_SAMPLE_RATE

Trace sampling rate.

- **Type:** float
- **Required:** No
- **Default:** 1.0
- **Range:** 0.0-1.0
- **Security:** Standard
- **Environments:**
  - Development: 1.0 (trace all requests)
  - Staging: 1.0
  - Production: 0.1 (sample 10% to reduce overhead)

**Tuning:** Lower values for high-traffic production environments to reduce tracing overhead.

## Rate Limiting Configuration

### RATE_LIMIT_ENABLED

Enable rate limiting for API endpoints.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Environments:**
  - Development: `false` (no local abuse risk)
  - Staging/Production: `true` (REQUIRED)

### RATE_LIMIT_REQUESTS_PER_MINUTE

Maximum requests per minute per client IP.

- **Type:** integer
- **Required:** No
- **Default:** 60
- **Range:** 1-10000
- **Security:** Standard

### RATE_LIMIT_BURST

Additional burst allowance for short request spikes.

- **Type:** integer
- **Required:** No
- **Default:** 10
- **Range:** 1-100
- **Security:** Standard

### RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE

Maximum media requests per minute per client IP (stricter tier).

- **Type:** integer
- **Required:** No
- **Default:** 120
- **Range:** 1-10000
- **Security:** Standard

### RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE

Maximum WebSocket connection attempts per minute per client IP.

- **Type:** integer
- **Required:** No
- **Default:** 10
- **Range:** 1-100
- **Security:** Standard

### RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE

Maximum search requests per minute per client IP.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 1-1000
- **Security:** Standard

### RATE_LIMIT_EXPORT_REQUESTS_PER_MINUTE

Maximum export requests per minute per client IP.

- **Type:** integer
- **Required:** No
- **Default:** 10
- **Range:** 1-100
- **Security:** Standard
- **Purpose:** Lower limit to prevent abuse of CSV export functionality which could overload the server or be used for data exfiltration

### RATE_LIMIT_AI_INFERENCE_REQUESTS_PER_MINUTE

Maximum AI inference requests per minute per client IP.

- **Type:** integer
- **Required:** No
- **Default:** 10
- **Range:** 1-60
- **Security:** Standard
- **Purpose:** Strict limit to prevent abuse of computationally expensive AI endpoints like prompt testing which runs LLM inference

### RATE_LIMIT_AI_INFERENCE_BURST

Burst allowance for AI inference rate limiting.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 0-10
- **Security:** Standard

### TRUSTED_PROXY_IPS

List of trusted proxy IP addresses.

- **Type:** JSON array of strings (IP addresses or CIDR notation)
- **Required:** No
- **Default:** `["127.0.0.1","::1"]`
- **Security:** Standard
- **Purpose:** `X-Forwarded-For` headers are only processed from these IPs
- **Examples:**
  - Localhost: `["127.0.0.1","::1"]`
  - Private networks: `["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]`
  - Specific proxy: `["192.168.1.100"]`

**Security Note:** Only trust proxies you control. Untrusted proxies can spoof client IPs.

## WebSocket Configuration

### WEBSOCKET_IDLE_TIMEOUT_SECONDS

WebSocket idle timeout in seconds.

- **Type:** integer
- **Required:** No
- **Default:** 300 (5 minutes)
- **Range:** 30-3600
- **Security:** Standard
- **Behavior:** Connections without activity will be closed

### WEBSOCKET_PING_INTERVAL_SECONDS

Interval for sending WebSocket ping frames to keep connections alive.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 5-120
- **Security:** Standard

### WEBSOCKET_MAX_MESSAGE_SIZE

Maximum WebSocket message size in bytes.

- **Type:** integer
- **Required:** No
- **Default:** 65536 (64KB)
- **Range:** 1024-1048576 (1KB-1MB)
- **Security:** Standard

## Severity Threshold Configuration

Risk scores (0-100) are mapped to severity levels using these thresholds.

### SEVERITY_LOW_MAX

Maximum risk score for LOW severity.

- **Type:** integer
- **Required:** No
- **Default:** 29
- **Range:** 0-100
- **Security:** Standard
- **Mapping:** Scores 0-29 = LOW

### SEVERITY_MEDIUM_MAX

Maximum risk score for MEDIUM severity.

- **Type:** integer
- **Required:** No
- **Default:** 59
- **Range:** 0-100
- **Security:** Standard
- **Mapping:** Scores 30-59 = MEDIUM

### SEVERITY_HIGH_MAX

Maximum risk score for HIGH severity.

- **Type:** integer
- **Required:** No
- **Default:** 84
- **Range:** 0-100
- **Security:** Standard
- **Mapping:** Scores 60-84 = HIGH, 85-100 = CRITICAL

## Notification Configuration

### NOTIFICATION_ENABLED

Enable notification delivery for alerts.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Environments:**
  - Development: `false` (avoid spam)
  - Staging/Production: `true`

### SMTP Email Settings

#### SMTP_HOST

SMTP server hostname for email notifications.

- **Type:** string (hostname)
- **Required:** When using email notifications
- **Default:** None
- **Security:** Standard
- **Example:** `smtp.example.com`

#### SMTP_PORT

SMTP server port.

- **Type:** integer
- **Required:** No
- **Default:** 587
- **Range:** 1-65535
- **Security:** Standard
- **Common Ports:**
  - 587: STARTTLS (recommended)
  - 465: SSL/TLS
  - 25: Plain (not recommended)

#### SMTP_USER

SMTP authentication username.

- **Type:** string
- **Required:** When SMTP authentication enabled
- **Default:** None
- **Security:** SENSITIVE
- **Example:** `alerts@example.com`

#### SMTP_PASSWORD

SMTP authentication password.

- **Type:** string
- **Required:** When SMTP authentication enabled
- **Default:** None
- **Security:** SENSITIVE - Never commit

#### SMTP_FROM_ADDRESS

Email sender address for notifications.

- **Type:** string (email address)
- **Required:** When using email notifications
- **Default:** None
- **Security:** Standard
- **Example:** `security-alerts@example.com`

#### SMTP_USE_TLS

Use TLS for SMTP connection.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard (REQUIRED for production)

### Webhook Settings

#### DEFAULT_WEBHOOK_URL

Default webhook URL for alert notifications.

- **Type:** string (HTTPS URL)
- **Required:** When using webhook notifications
- **Default:** None
- **Security:** Standard (validated with SSRF protection)
- **Example:** `https://hooks.example.com/security-alerts`

**Validation:**

- Must be valid HTTP/HTTPS URL
- SSRF protection enabled (blocks private IPs and cloud metadata endpoints)
- HTTPS required in production (HTTP allowed for localhost in dev)

#### WEBHOOK_TIMEOUT_SECONDS

Timeout for webhook HTTP requests.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 1-300
- **Security:** Standard

### DEFAULT_EMAIL_RECIPIENTS

Default email recipients for notifications.

- **Type:** JSON array of strings (email addresses)
- **Required:** No
- **Default:** `[]`
- **Security:** Standard
- **Example:** `["security-team@example.com","ops@example.com"]`

## Clip Generation Configuration

### CLIPS_DIRECTORY

Directory to store generated event clips.

- **Type:** string (directory path)
- **Required:** No
- **Default:** `data/clips`
- **Security:** Standard

### CLIP_PRE_ROLL_SECONDS

Seconds before event start to include in clip.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 0-60
- **Security:** Standard

### CLIP_POST_ROLL_SECONDS

Seconds after event end to include in clip.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 0-60
- **Security:** Standard

### CLIP_GENERATION_ENABLED

Enable automatic clip generation for events.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard

## Video Processing Configuration

### VIDEO_THUMBNAILS_DIR

Directory for storing video thumbnails and extracted frames.

- **Type:** string (directory path)
- **Required:** No
- **Default:** `data/thumbnails`
- **Security:** Standard

### VIDEO_MAX_FRAMES

Maximum number of frames to extract from a video.

- **Type:** integer
- **Required:** No
- **Default:** 30
- **Range:** 1-300
- **Security:** Standard

### VIDEO_FRAME_INTERVAL_SECONDS

Interval between extracted video frames in seconds.

- **Type:** float
- **Required:** No
- **Default:** 2.0
- **Range:** 0.1-60.0
- **Security:** Standard

## Performance Profiling Configuration

### PROFILING_ENABLED

Enable performance profiling for deep debugging.

- **Type:** boolean
- **Required:** No
- **Default:** `false`
- **Security:** Standard
- **Environments:**
  - Development: Enable when debugging performance issues
  - Production: Disable (significant overhead)

**Feature:** When enabled, the `profile_if_enabled` decorator profiles decorated functions. Profile data is saved as `.prof` files that can be analyzed with `snakeviz` or `py-spy`.

### PROFILING_OUTPUT_DIR

Directory for storing profiling output files.

- **Type:** string (directory path)
- **Required:** No
- **Default:** `data/profiles`
- **Security:** Standard
- **Analysis:** `snakeviz <file>.prof` or convert to flamegraphs

## Background Evaluation Configuration

### BACKGROUND_EVALUATION_ENABLED

Enable automatic background AI audit evaluation when GPU is idle.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Feature:** Full evaluations (self-critique, rubric scoring, consistency check, prompt improvement) run automatically instead of requiring manual "Run Evaluation" clicks

### BACKGROUND_EVALUATION_GPU_IDLE_THRESHOLD

GPU utilization percentage below which GPU is considered idle.

- **Type:** integer
- **Required:** No
- **Default:** 20
- **Range:** 0-100
- **Security:** Standard
- **Behavior:** Background evaluations only run when utilization is at or below this threshold

### BACKGROUND_EVALUATION_IDLE_DURATION

Seconds GPU must remain idle before background evaluation starts.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-300
- **Security:** Standard
- **Purpose:** Prevents evaluation from starting during brief pauses in detection pipeline

### BACKGROUND_EVALUATION_POLL_INTERVAL

How often (in seconds) to check if conditions are met for background evaluation.

- **Type:** float
- **Required:** No
- **Default:** 5.0
- **Range:** 1.0-60.0
- **Security:** Standard

## Vision Extraction Configuration

### VISION_EXTRACTION_ENABLED

Enable Florence-2 vision extraction for vehicle/person attributes.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard

### IMAGE_QUALITY_ENABLED

Enable BRISQUE image quality assessment (CPU-based).

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard
- **Feature:** Provides quality scores to help identify blurry, noisy, or degraded images

### REID_ENABLED

Enable CLIP re-identification for tracking entities across cameras.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard

### SCENE_CHANGE_ENABLED

Enable SSIM-based scene change detection.

- **Type:** boolean
- **Required:** No
- **Default:** `true`
- **Security:** Standard

### REID_SIMILARITY_THRESHOLD

Cosine similarity threshold for re-identification matching.

- **Type:** float
- **Required:** No
- **Default:** 0.85
- **Range:** 0.5-1.0
- **Security:** Standard
- **Tuning:**
  - Higher (0.9-0.95): Fewer false matches, may miss legitimate matches
  - Lower (0.7-0.85): More matches, more false positives

### REID_TTL_HOURS

Time-to-live for re-identification embeddings in Redis (hours).

- **Type:** integer
- **Required:** No
- **Default:** 24
- **Range:** 1-168 (1 hour to 1 week)
- **Security:** Standard

### REID_MAX_CONCURRENT_REQUESTS

Maximum concurrent re-identification operations.

- **Type:** integer
- **Required:** No
- **Default:** 10
- **Range:** 1-100
- **Security:** Standard
- **Purpose:** Prevents resource exhaustion from too many simultaneous CLIP/Redis operations

### REID_EMBEDDING_TIMEOUT

Timeout (seconds) for ReID embedding generation operations.

- **Type:** float
- **Required:** No
- **Default:** 30.0
- **Range:** 5.0-120.0
- **Security:** Standard
- **Purpose:** Prevents hanging when CLIP service is slow or unresponsive

### SCENE_CHANGE_THRESHOLD

SSIM threshold for scene change detection.

- **Type:** float
- **Required:** No
- **Default:** 0.90
- **Range:** 0.5-1.0
- **Security:** Standard
- **Behavior:** SSIM scores below this threshold indicate a scene change
- **Tuning:**
  - Higher (0.95-0.99): Only detect major scene changes
  - Lower (0.7-0.85): Detect subtle changes (more sensitive)

## Circuit Breaker Configuration

Circuit breakers prevent cascading failures by temporarily disabling failing services.

### DLQ Circuit Breaker

#### DLQ_CIRCUIT_BREAKER_FAILURE_THRESHOLD

Number of DLQ write failures before opening circuit breaker.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-50
- **Security:** Standard

#### DLQ_CIRCUIT_BREAKER_RECOVERY_TIMEOUT

Seconds to wait before attempting DLQ writes again after circuit opens.

- **Type:** float
- **Required:** No
- **Default:** 60.0
- **Range:** 10.0-600.0
- **Security:** Standard

#### DLQ_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS

Maximum test calls allowed when circuit is half-open.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard

#### DLQ_CIRCUIT_BREAKER_SUCCESS_THRESHOLD

Successful DLQ writes needed to close circuit from half-open state.

- **Type:** integer
- **Required:** No
- **Default:** 2
- **Range:** 1-10
- **Security:** Standard

### Enrichment Service Circuit Breaker

#### ENRICHMENT_CB_FAILURE_THRESHOLD

Number of Enrichment service failures before opening circuit breaker.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-50
- **Security:** Standard

#### ENRICHMENT_CB_RECOVERY_TIMEOUT

Seconds to wait before attempting Enrichment service calls again after circuit opens.

- **Type:** float
- **Required:** No
- **Default:** 60.0
- **Range:** 10.0-600.0
- **Security:** Standard

#### ENRICHMENT_CB_HALF_OPEN_MAX_CALLS

Maximum test calls allowed when Enrichment circuit is half-open.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard

### CLIP Service Circuit Breaker

#### CLIP_CB_FAILURE_THRESHOLD

Number of CLIP service failures before opening circuit breaker.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-50
- **Security:** Standard

#### CLIP_CB_RECOVERY_TIMEOUT

Seconds to wait before attempting CLIP service calls again after circuit opens.

- **Type:** float
- **Required:** No
- **Default:** 60.0
- **Range:** 10.0-600.0
- **Security:** Standard

#### CLIP_CB_HALF_OPEN_MAX_CALLS

Maximum test calls allowed when CLIP circuit is half-open.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard

### Florence Service Circuit Breaker

#### FLORENCE_CB_FAILURE_THRESHOLD

Number of Florence service failures before opening circuit breaker.

- **Type:** integer
- **Required:** No
- **Default:** 5
- **Range:** 1-50
- **Security:** Standard

#### FLORENCE_CB_RECOVERY_TIMEOUT

Seconds to wait before attempting Florence service calls again after circuit opens.

- **Type:** float
- **Required:** No
- **Default:** 60.0
- **Range:** 10.0-600.0
- **Security:** Standard

#### FLORENCE_CB_HALF_OPEN_MAX_CALLS

Maximum test calls allowed when Florence circuit is half-open.

- **Type:** integer
- **Required:** No
- **Default:** 3
- **Range:** 1-10
- **Security:** Standard

## Queue Settings

### QUEUE_MAX_SIZE

Maximum size of Redis queues.

- **Type:** integer
- **Required:** No
- **Default:** 10000
- **Range:** 100-100000
- **Security:** Standard

### QUEUE_OVERFLOW_POLICY

Policy when queue is full.

- **Type:** string
- **Required:** No
- **Default:** `dlq`
- **Options:**
  - `dlq` - Move to dead-letter queue (recommended)
  - `reject` - Fail operation with error
  - `drop_oldest` - Silent data loss (NOT recommended)
- **Security:** Standard

### QUEUE_BACKPRESSURE_THRESHOLD

Queue fill ratio at which to start backpressure warnings.

- **Type:** float
- **Required:** No
- **Default:** 0.8
- **Range:** 0.5-1.0
- **Security:** Standard

### MAX_REQUEUE_ITERATIONS

Maximum iterations for requeue-all operations.

- **Type:** integer
- **Required:** No
- **Default:** 10000
- **Range:** 1-100000
- **Security:** Standard

## File Deduplication Configuration

### DEDUPE_TTL_SECONDS

TTL for file deduplication entries in Redis.

- **Type:** integer
- **Required:** No
- **Default:** 300 (5 minutes)
- **Range:** 60-3600
- **Security:** Standard
- **Environments:**
  - Development: 60 (faster re-processing for testing)
  - Production: 300

**Purpose:** Prevents duplicate processing of the same file within the TTL window.

## Frontend/Backend Mapping

Frontend environment variables (prefixed with `VITE_`) are embedded at build time and map to backend configuration as follows:

| Frontend Variable      | Backend Equivalent      | Purpose                               |
| ---------------------- | ----------------------- | ------------------------------------- |
| `VITE_API_BASE_URL`    | `API_HOST` + `API_PORT` | API endpoint URL (browser-accessible) |
| `VITE_WS_BASE_URL`     | `API_HOST` + `API_PORT` | WebSocket URL (browser-accessible)    |
| `VITE_DEV_BACKEND_URL` | -                       | Dev proxy target (development only)   |

**Important Notes:**

1. Frontend variables are **embedded at build time** - rebuild after changing
2. Backend variables are **loaded at runtime** - no rebuild needed
3. URLs must be browser-accessible (not Docker internal hostnames like `postgres:5432`)
4. Use HTTPS/WSS in production for security

**Example Mapping:**

```bash
# Backend (runtime)
API_HOST=0.0.0.0
API_PORT=8000
TLS_MODE=provided
TLS_CERT_PATH=/path/to/cert.crt

# Frontend (build-time)
VITE_API_BASE_URL=https://security.example.com
VITE_WS_BASE_URL=wss://security.example.com
```

## Security Best Practices

### Credentials Management

1. **Never commit credentials** to version control

   - Use `.env` files (gitignored)
   - Use secrets management tools (HashiCorp Vault, AWS Secrets Manager)
   - Rotate credentials periodically

2. **Generate strong passwords**

   ```bash
   openssl rand -base64 32  # For passwords
   openssl rand -hex 32     # For API keys
   ```

3. **Use different credentials per environment**
   - Development passwords should not match production
   - API keys should be unique per environment

### Network Security

1. **Use HTTPS/TLS in production**

   - Set `TLS_MODE=provided` with valid certificates
   - Set `TLS_MIN_VERSION=TLSv1.3`
   - Enable `REDIS_SSL_ENABLED=true`

2. **Restrict CORS origins**

   - Never use `["*"]` in production
   - Limit to specific production domain

3. **Use HTTPS for AI service URLs**
   - `RTDETR_URL=https://...`
   - `NEMOTRON_URL=https://...`

### Authentication

1. **Enable API key authentication in production**

   ```bash
   API_KEY_ENABLED=true
   API_KEYS=["generated_key_1","generated_key_2"]
   ```

2. **Disable debug mode in production**

   ```bash
   DEBUG=false
   ADMIN_ENABLED=false
   ```

3. **Configure rate limiting**
   ```bash
   RATE_LIMIT_ENABLED=true
   RATE_LIMIT_REQUESTS_PER_MINUTE=60
   ```

### Monitoring and Logging

1. **Enable monitoring stack**

   - Prometheus + Grafana for metrics
   - OpenTelemetry for distributed tracing

2. **Configure notifications**

   - SMTP for email alerts
   - Webhook for integration with incident management

3. **Adjust log levels appropriately**
   - Development: `LOG_LEVEL=DEBUG`
   - Production: `LOG_LEVEL=WARNING`

## Troubleshooting

### Common Issues

#### Database Connection Failures

**Symptom:** `asyncpg.exceptions.InvalidCatalogNameError` or connection refused

**Solutions:**

1. Verify `DATABASE_URL` format: `postgresql+asyncpg://user:pass@host:port/db` <!-- pragma: allowlist secret -->
2. Ensure credentials match in `DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
3. Check PostgreSQL container is running: `docker ps` or `podman ps`
4. Verify network connectivity: `psql -h localhost -U user -d db`

#### Redis Connection Failures

**Symptom:** `redis.exceptions.ConnectionError`

**Solutions:**

1. Verify `REDIS_URL` format: `redis://host:port/db`
2. Check if password required: Set `REDIS_PASSWORD`
3. Ensure Redis container is running
4. Verify SSL settings match Redis server configuration

#### AI Service Timeouts

**Symptom:** `httpx.ReadTimeout` or slow inference

**Solutions:**

1. Increase timeout settings:
   - `RTDETR_READ_TIMEOUT=120.0`
   - `NEMOTRON_READ_TIMEOUT=180.0`
2. Check GPU availability: Ensure AI containers have GPU access
3. Monitor GPU utilization: Check for memory exhaustion
4. Reduce `AI_MAX_CONCURRENT_INFERENCES` if GPU overloaded

#### Frontend Cannot Connect to Backend

**Symptom:** Network errors in browser console

**Solutions:**

1. Verify `VITE_API_BASE_URL` is browser-accessible (not Docker hostname)
2. Check CORS settings: `CORS_ORIGINS` includes frontend domain
3. Ensure backend is running: `curl http://localhost:8000/api/system/health`
4. Rebuild frontend after changing VITE\_\* variables: `npm run build`

### Environment-Specific Issues

#### Development

- **File watcher not detecting changes**: Set `FILE_WATCHER_POLLING=true`
- **Pre-commit hooks too slow**: Tests run on push, not commit
- **GPU not available**: Ensure NVIDIA drivers installed, check `nvidia-smi`

#### Staging

- **Self-signed certificate warnings**: Expected with `TLS_MODE=self_signed`
- **Rate limiting too strict**: Adjust limits for testing traffic patterns

#### Production

- **Slow database queries**: Check `SLOW_QUERY_THRESHOLD_MS`, analyze EXPLAIN output
- **High memory usage**: Review connection pool settings, reduce `DATABASE_POOL_SIZE`
- **Notification failures**: Verify SMTP credentials, webhook URL accessibility

## Migration Guide

### Upgrading from Legacy TLS Settings

Old (deprecated):

```bash
TLS_ENABLED=true
TLS_CERT_FILE=/path/to/cert.crt
TLS_KEY_FILE=/path/to/key.key
```

New:

```bash
TLS_MODE=provided
TLS_CERT_PATH=/path/to/cert.crt
TLS_KEY_PATH=/path/to/key.key
```

### Upgrading from Single .env to Environment Profiles

1. Backup existing `.env`: `cp .env .env.backup`
2. Choose profile: `cp docs/.env.production .env`
3. Migrate custom values from `.env.backup` to new `.env`
4. Test: `./scripts/validate.sh`

## Additional Resources

- **Setup Script**: `./setup.sh` - Interactive environment configuration
- **Validation Script**: `./scripts/validate.sh` - Verify configuration and run tests
- **Runtime Config Documentation**: `docs/RUNTIME_CONFIG.md`
- **Backend Config Source**: `backend/core/config.py`
- **Frontend Config Source**: `frontend/vite.config.ts`
