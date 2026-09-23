# Configuration

This document describes the settings architecture, environment variables, and configuration patterns for the Home Security Intelligence system.

## Settings Architecture

The application uses **Pydantic Settings** for type-safe configuration management with environment variable support.

**Source:** `backend/core/config.py:298-306`

```python
class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
```

### Settings Singleton Pattern

Settings are loaded once and cached using the `@cache` decorator.

**Source:** `backend/core/config.py` (end of file)

```python
@cache
def get_settings() -> Settings:
    """Get cached application settings.

    Returns the same Settings instance throughout the application lifecycle.
    Uses functools.cache for thread-safe singleton behavior.
    """
    return Settings()
```

**Usage:**

```python
from backend.core import get_settings

settings = get_settings()
print(settings.database_url)
```

## Environment Variables by Category

### Database Configuration

| Variable                 | Default    | Description                       |
| ------------------------ | ---------- | --------------------------------- |
| `DATABASE_URL`           | (required) | PostgreSQL connection URL         |
| `DATABASE_POOL_SIZE`     | 20         | Base connection pool size         |
| `DATABASE_POOL_OVERFLOW` | 30         | Additional connections under load |
| `DATABASE_POOL_TIMEOUT`  | 30         | Seconds to wait for connection    |
| `DATABASE_POOL_RECYCLE`  | 1800       | Connection recycle interval       |

**Source:** `backend/core/config.py:313-344`

### Redis Configuration

| Variable                       | Default                    | Description                     |
| ------------------------------ | -------------------------- | ------------------------------- |
| `REDIS_URL`                    | `redis://localhost:6379/0` | Redis connection URL            |
| `REDIS_PASSWORD`               | None                       | Redis authentication password   |
| `REDIS_EVENT_CHANNEL`          | `security_events`          | Pub/sub channel name            |
| `REDIS_KEY_PREFIX`             | `hsi`                      | Global key prefix               |
| `REDIS_POOL_SIZE`              | 50                         | Total pool size (non-dedicated) |
| `REDIS_POOL_DEDICATED_ENABLED` | true                       | Enable dedicated pools          |
| `REDIS_POOL_SIZE_CACHE`        | 20                         | Cache pool connections          |
| `REDIS_POOL_SIZE_QUEUE`        | 15                         | Queue pool connections          |
| `REDIS_POOL_SIZE_PUBSUB`       | 10                         | Pub/sub pool connections        |
| `REDIS_POOL_SIZE_RATELIMIT`    | 10                         | Rate limit pool connections     |

**Source:** `backend/core/config.py:346-405`

### Redis SSL/TLS Settings

| Variable                   | Default    | Description                   |
| -------------------------- | ---------- | ----------------------------- |
| `REDIS_SSL_ENABLED`        | false      | Enable SSL/TLS                |
| `REDIS_SSL_CERT_REQS`      | `required` | Certificate verification mode |
| `REDIS_SSL_CA_CERTS`       | None       | CA certificate path           |
| `REDIS_SSL_CERTFILE`       | None       | Client certificate path       |
| `REDIS_SSL_KEYFILE`        | None       | Client key path               |
| `REDIS_SSL_CHECK_HOSTNAME` | true       | Verify hostname               |

**Source:** `backend/core/config.py:408-439`

### Cache TTL Settings

| Variable              | Default | Description                   |
| --------------------- | ------- | ----------------------------- |
| `CACHE_DEFAULT_TTL`   | 300     | Default TTL (5 minutes)       |
| `CACHE_SHORT_TTL`     | 60      | Short TTL (1 minute)          |
| `CACHE_LONG_TTL`      | 3600    | Long TTL (1 hour)             |
| `CACHE_SWR_STALE_TTL` | 60      | Stale-while-revalidate window |
| `CACHE_SWR_ENABLED`   | true    | Enable SWR pattern            |
| `SNAPSHOT_CACHE_TTL`  | 3600    | Camera snapshot cache TTL     |

**Source:** `backend/core/config.py:728-765`

### AI Service Endpoints

All AI models (YOLO26, Florence-2, CLIP, enrichment) run inside one `ai-gateway` container on port
8090 and are addressed by path prefix. `.env.example` defaults:

| Variable               | Default                            | Description                                |
| ---------------------- | ---------------------------------- | ------------------------------------------ |
| `YOLO26_URL`           | `http://localhost:8090/yolo26`     | YOLO26 detection route                     |
| `NEMOTRON_URL`         | `http://localhost:8091`            | Nemotron LLM (separate `ai-llm` container) |
| `FLORENCE_URL`         | `http://localhost:8090/florence`   | Florence-2 vision route                    |
| `CLIP_URL`             | `http://localhost:8090/clip`       | CLIP embedding route                       |
| `ENRICHMENT_URL`       | `http://localhost:8090/enrichment` | Heavy enrichment route                     |
| `ENRICHMENT_LIGHT_URL` | `http://localhost:8090/enrich-lt`  | Light enrichment route                     |

In containers the same routes use `http://ai-gateway:8090/...` and `NEMOTRON_URL=http://ai-llm:8091`
(`docker-compose.prod.yml`, backend `AI Gateway routes` block).

### AI Service Timeouts

| Variable                  | Default | Description                  |
| ------------------------- | ------- | ---------------------------- |
| `AI_CONNECT_TIMEOUT`      | 10.0    | Connection timeout (seconds) |
| `AI_HEALTH_TIMEOUT`       | 5.0     | Health check timeout         |
| `YOLO26_READ_TIMEOUT`     | 30.0    | Detection response timeout   |
| `NEMOTRON_READ_TIMEOUT`   | 120.0   | LLM response timeout         |
| `FLORENCE_READ_TIMEOUT`   | 30.0    | Florence-2 timeout           |
| `CLIP_READ_TIMEOUT`       | 5.0     | CLIP embedding timeout       |
| `ENRICHMENT_READ_TIMEOUT` | 60.0    | Enrichment service timeout   |

**Source:** `backend/core/config.py:1046-1100`

### Batch Processing

| Variable                       | Default | Description                  |
| ------------------------------ | ------- | ---------------------------- |
| `BATCH_WINDOW_SECONDS`         | 90      | Maximum batch window         |
| `BATCH_IDLE_TIMEOUT_SECONDS`   | 30      | Idle timeout for early close |
| `BATCH_CHECK_INTERVAL_SECONDS` | 5.0     | Timeout check frequency      |
| `BATCH_MAX_DETECTIONS`         | 500     | Max detections before split  |

**Source:** `backend/core/config.py:935-956`

### Fast Path Configuration

| Variable                         | Default      | Description                 |
| -------------------------------- | ------------ | --------------------------- |
| `FAST_PATH_ENABLED`              | false        | Enable fast path processing |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | 0.90         | Confidence threshold        |
| `FAST_PATH_OBJECT_TYPES`         | `["person"]` | Object types for fast path  |

**Source:** `docker-compose.prod.yml:485-487`, `backend/core/config.py:1757-1770`

### Application Settings

| Variable         | Default      | Description                            |
| ---------------- | ------------ | -------------------------------------- |
| `DEBUG`          | false        | Enable debug mode                      |
| `ENVIRONMENT`    | `production` | Deployment environment                 |
| `ADMIN_ENABLED`  | true         | Enable admin endpoints                 |
| `ADMIN_API_KEY`  | None         | Admin API key (reserved, not enforced) |
| `API_HOST`       | `0.0.0.0`    | API bind address                       |
| `API_PORT`       | 8000         | API port                               |
| `RETENTION_DAYS` | 30           | Data retention period                  |

**Source:** `backend/core/config.py:842-930`

### CORS Settings

| Variable       | Default     | Description          |
| -------------- | ----------- | -------------------- |
| `CORS_ORIGINS` | (see below) | Allowed CORS origins |

Default CORS origins (see `backend/core/config.py:884-894`):

```python
[
    # HTTPS origins for external browser access
    "https://localhost:8444",
    "https://127.0.0.1:8444",
    "https://0.0.0.0:8444",
    # Internal container communication (HTTP within Docker network)
    "http://frontend:8080",
]
```

Set `CORS_ORIGINS` to your own hostnames for LAN access.

### Nemotron Context Settings

| Variable                                | Default       | Description                                                                    |
| --------------------------------------- | ------------- | ------------------------------------------------------------------------------ |
| `CTX_SIZE`                              | 262144        | Context window (tokens) — sets `nemotron_context_window` (field default 32768) |
| `NEMOTRON_MAX_OUTPUT_TOKENS`            | 1536          | Max output tokens                                                              |
| `CONTEXT_UTILIZATION_WARNING_THRESHOLD` | 0.80          | Warning threshold                                                              |
| `CONTEXT_TRUNCATION_ENABLED`            | true          | Enable smart truncation                                                        |
| `LLM_TOKENIZER_ENCODING`                | `cl100k_base` | Token counting encoding                                                        |

**Source:** `backend/core/config.py:1158-1227`, `.env.example:365`

### Feature Toggles

| Variable                              | Default | Description                   |
| ------------------------------------- | ------- | ----------------------------- |
| `VISION_EXTRACTION_ENABLED`           | true    | Enable Florence-2 extraction  |
| `REID_ENABLED`                        | true    | Enable CLIP re-identification |
| `IMAGE_QUALITY_ENABLED`               | true    | Enable BRISQUE quality scores |
| `FLORENCE_SCENE_CAPTIONS_ENABLED`     | true    | Scene captions                |
| `FLORENCE_DETECTION_CAPTIONS_ENABLED` | true    | Detection captions            |
| `FLORENCE_VQA_ENABLED`                | true    | Visual QA extraction          |

**Source:** `backend/core/config.py:1573-1593`

## Nested Settings Classes

### OrchestratorSettings

Container orchestrator configuration for Docker/Podman management.

**Source:** `backend/core/config.py:114-295`

| Variable                                | Default | Description             |
| --------------------------------------- | ------- | ----------------------- |
| `ORCHESTRATOR_ENABLED`                  | true    | Enable orchestration    |
| `ORCHESTRATOR_DOCKER_HOST`              | None    | Docker/Podman host URL  |
| `ORCHESTRATOR_HEALTH_CHECK_INTERVAL`    | 30      | Health check interval   |
| `ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES` | 5       | Failures before disable |

### TranscodeCacheSettings

Video transcoding cache configuration.

**Source:** `backend/core/config.py:41-112`

| Variable                            | Default                | Description     |
| ----------------------------------- | ---------------------- | --------------- |
| `TRANSCODE_CACHE_DIR`               | `data/transcode_cache` | Cache directory |
| `TRANSCODE_CACHE_MAX_CACHE_SIZE_GB` | 10.0                   | Max cache size  |
| `TRANSCODE_CACHE_MAX_FILE_AGE_DAYS` | 7                      | Max file age    |
| `TRANSCODE_CACHE_ENABLED`           | true                   | Enable caching  |

## Configuration Validation

Pydantic validators ensure configuration correctness at startup.

### URL Validation

AI service URLs are validated using `AnyHttpUrl`.

**Source:** `backend/core/config.py:820-853`

```python
@field_validator("yolo26_url", "nemotron_url", mode="before")
@classmethod
def validate_ai_service_urls(cls, v: Any) -> str:
    """Validate AI service URLs using Pydantic's AnyHttpUrl validator."""
    url_str = str(v)
    try:
        validated_url = AnyHttpUrl(url_str)
        return str(validated_url).rstrip("/")
    except Exception as e:
        raise ValueError(f"Invalid AI service URL '{url_str}'...") from None
```

### Grafana URL Validation

Grafana URLs include SSRF protection.

**Source:** `backend/core/config.py:883-914`

```python
@field_validator("grafana_url", mode="before")
@classmethod
def validate_grafana_url_field(cls, v: Any) -> str:
    """Validate Grafana URL with SSRF protection (NEM-1077)."""
    # Allows relative paths like /grafana for nginx proxy
    if url_str.startswith("/"):
        return url_str
    return validate_grafana_url(url_str)
```

## Environment Variable Cascade

![Environment Variable Cascade showing the hierarchy and precedence of configuration sources](../../images/architecture/env-variable-cascade.png)

The configuration system follows a clear precedence hierarchy where environment variables override file-based settings, enabling flexible deployment across different environments.

## Environment Files

| File           | Purpose                                                             |
| -------------- | ------------------------------------------------------------------- |
| `.env`         | Local configuration, created from the template by `python setup.py` |
| `.env.example` | Template with default values                                        |

### Example .env File

```bash
# Database
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=

# AI Services (Docker — single ai-gateway container)
YOLO26_URL=http://ai-gateway:8090/yolo26
NEMOTRON_URL=http://ai-llm:8091
FLORENCE_URL=http://ai-gateway:8090/florence
CLIP_URL=http://ai-gateway:8090/clip
ENRICHMENT_URL=http://ai-gateway:8090/enrichment
ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt

# Batch Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Detection
DETECTION_CONFIDENCE_THRESHOLD=0.5
FAST_PATH_ENABLED=false

# Retention
RETENTION_DAYS=30

# Environment
ENVIRONMENT=development
DEBUG=false
```

## Settings Access Pattern

```python
from backend.core import get_settings

# In route handlers
@router.get("/example")
async def example_endpoint():
    settings = get_settings()
    return {"batch_window": settings.batch_window_seconds}

# In services
class MyService:
    def __init__(self):
        self._settings = get_settings()
        self._timeout = self._settings.ai_health_timeout

# Type hints for IDE support
from backend.core.config import Settings

def configure_client(settings: Settings) -> None:
    url = settings.yolo26_url
```

## Configuration Best Practices

1. **Never hardcode values** - Use settings for all configurable values
2. **Validate early** - Pydantic validates at startup, fail fast on bad config
3. **Document defaults** - Every Field should have a description
4. **Use appropriate types** - Field constraints (ge, le, gt, lt) catch invalid values
5. **Environment-specific** - Use different .env files for dev/staging/prod

## Related Documentation

- [Deployment Topology](deployment-topology.md) - Container environment variables
- [Design Decisions](design-decisions.md) - Why these configuration choices
- [Environment Reference](/reference/config/env-reference.md) - Complete variable list
