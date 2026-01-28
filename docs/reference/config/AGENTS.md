# Configuration Reference Directory - Agent Guide

## Purpose

This directory contains authoritative configuration reference documentation for the Home Security Intelligence system. These are the canonical sources for environment variables, settings, and thresholds.

## Directory Contents

```
config/
  AGENTS.md                       # This file
  cache-invalidation-reasons.md   # Cache invalidation reason constants
  env-reference.md                # Complete environment variable reference
  risk-levels.md                  # Risk score ranges and severity definitions
```

## Key Files

### cache-invalidation-reasons.md

**Purpose:** Reference for cache invalidation reason constants used in backend services.

**Content:**

- `CacheInvalidationReason` enum documentation
- Event lifecycle operations (EVENT_CREATED, EVENT_UPDATED, etc.)
- Camera lifecycle operations
- Detection lifecycle operations
- Alert operations
- System operations (STATUS_CHANGED, GRACEFUL_SHUTDOWN, MANUAL)
- Test-specific reasons

**When to use:** Understanding cache invalidation patterns, implementing cache operations, writing tests.

### env-reference.md

**Purpose:** Complete reference for all configuration environment variables.

**Sections:**

| Section                | Variables                                                      |
| ---------------------- | -------------------------------------------------------------- |
| **Database**           | `DATABASE_URL`                                                 |
| **Redis**              | `REDIS_URL`                                                    |
| **AI Services**        | `YOLO26_URL`, `NEMOTRON_URL`, timeouts, API keys               |
| **Camera Integration** | `FOSCAM_BASE_PATH`                                             |
| **File Watcher**       | `FILE_WATCHER_POLLING`, `FILE_WATCHER_POLLING_INTERVAL`        |
| **Detection**          | `DETECTION_CONFIDENCE_THRESHOLD`                               |
| **Fast Path**          | `FAST_PATH_CONFIDENCE_THRESHOLD`, `FAST_PATH_OBJECT_TYPES`     |
| **Batch Processing**   | `BATCH_WINDOW_SECONDS`, `BATCH_IDLE_TIMEOUT_SECONDS`           |
| **Retention**          | `RETENTION_DAYS`, `LOG_RETENTION_DAYS`                         |
| **GPU Monitoring**     | `GPU_POLL_INTERVAL_SECONDS`, `GPU_STATS_HISTORY_MINUTES`       |
| **Deduplication**      | `DEDUPE_TTL_SECONDS`                                           |
| **Severity**           | `SEVERITY_LOW_MAX`, `SEVERITY_MEDIUM_MAX`, `SEVERITY_HIGH_MAX` |
| **Logging**            | `LOG_LEVEL`, `LOG_FILE_PATH`, file rotation settings           |
| **API Server**         | `DEBUG`, `API_HOST`, `API_PORT`                                |
| **Authentication**     | `API_KEY_ENABLED`, `API_KEYS`                                  |
| **Rate Limiting**      | `RATE_LIMIT_*` variables for all tiers                         |
| **WebSocket**          | `WEBSOCKET_IDLE_TIMEOUT_SECONDS`, ping interval, max size      |
| **TLS/HTTPS**          | `TLS_MODE`, certificate paths, verification options            |
| **CORS**               | `CORS_ORIGINS`                                                 |
| **Notifications**      | SMTP settings, webhook configuration                           |
| **Queue Settings**     | `QUEUE_MAX_SIZE`, overflow policy, backpressure                |
| **DLQ**                | Circuit breaker settings for dead-letter queue                 |
| **Video Processing**   | Frame interval, thumbnails directory, max frames               |
| **Clip Generation**    | Pre/post roll, clips directory, enabled flag                   |
| **Service Health**     | `AI_RESTART_ENABLED`                                           |
| **Admin Endpoints**    | `ADMIN_ENABLED`, `ADMIN_API_KEY`                               |
| **Frontend**           | `VITE_API_BASE_URL`, `VITE_WS_BASE_URL`, `FRONTEND_PORT`       |

**Format for Each Variable:**

- Required/Optional status
- Default value
- Valid range (if applicable)
- Description
- Examples

**When to use:** Setting up environment, deploying the system, debugging configuration issues.

### risk-levels.md

**Purpose:** Canonical definition of risk score ranges and severity levels.

**Content:**

- Risk score ranges (0-100 scale)
- Four severity levels:
  - **Low:** 0-29 (green)
  - **Medium:** 30-59 (yellow)
  - **High:** 60-84 (orange)
  - **Critical:** 85-100 (red)
- Boundary details (inclusive upper bounds)
- What each level means with examples
- Configuration via environment variables
- Color scheme for UI (Tailwind classes)
- Technical implementation reference

**When to use:** Understanding risk scoring, configuring severity thresholds, UI color consistency.

## Configuration Best Practices

### Setting Variables

1. **Use `.env` file** for local development
2. **Use environment** for containerized deployments
3. **Never commit secrets** to version control
4. **Document non-default values** in deployment notes

### Variable Priority

```
Environment > .env file > Default value
```

### Common Configuration Tasks

| Task                           | Variables to Set                                     |
| ------------------------------ | ---------------------------------------------------- |
| Connect to different database  | `DATABASE_URL`                                       |
| Use remote AI services         | `YOLO26_URL`, `NEMOTRON_URL`                         |
| Enable authentication          | `API_KEY_ENABLED=true`, `API_KEYS`                   |
| Enable TLS                     | `TLS_MODE`, certificate paths                        |
| Adjust batch timing            | `BATCH_WINDOW_SECONDS`, `BATCH_IDLE_TIMEOUT_SECONDS` |
| Change retention period        | `RETENTION_DAYS`                                     |
| Adjust detection sensitivity   | `DETECTION_CONFIDENCE_THRESHOLD`                     |
| Configure alerts more strictly | `SEVERITY_LOW_MAX`, `SEVERITY_MEDIUM_MAX`, etc.      |

## Validation

The backend validates configuration on startup. Invalid configurations cause startup failure with descriptive error messages.

```bash
# Test configuration without starting server
uv run python -c "from backend.core.config import get_settings; print(get_settings())"
```

## Target Audiences

| Audience       | Needs                             | Primary Documents |
| -------------- | --------------------------------- | ----------------- |
| **Operators**  | Deployment configuration          | env-reference.md  |
| **Developers** | Local development setup           | env-reference.md  |
| **Users**      | Understanding risk scores         | risk-levels.md    |
| **Security**   | Authentication, TLS configuration | env-reference.md  |

## Related Documentation

- **docs/reference/AGENTS.md:** Reference directory overview
- **docs/reference/config/env-reference.md:** Complete environment variable reference
- **docs/operator/ai-configuration.md:** AI-specific configuration
- **docs/developer/local-setup.md:** Development environment setup
- **backend/core/config.py:** Settings implementation
