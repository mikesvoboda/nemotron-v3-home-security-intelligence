# Configuration

This document describes the settings architecture, environment variables, and configuration patterns for the Home Security Intelligence system.

## Settings Architecture

The application uses **Pydantic Settings** for type-safe configuration management with environment variable support.

**Source:** `backend/core/config.py:362-370`

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

Settings are loaded once and cached using the `@cache` decorator. The cache is cold again after the
settings API writes `data/runtime.env` (`backend/api/routes/settings_api.py:279`).

**Source:** `backend/core/config.py:3346-3352`

```python
@cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    runtime_env_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    # `_env_file` is evaluated at call time (unlike `model_config.env_file`, which is bound at
    # import time). This lets tests and deployments override runtime config cleanly.
    return Settings(_env_file=(".env", runtime_env_path))
```

**Usage:**

```python
from backend.core import get_settings

settings = get_settings()
print(settings.database_url)
```

## Environment Variables by Category

### Database Configuration

| Variable                 | Default                    | Description                       |
| ------------------------ | -------------------------- | --------------------------------- |
| `DATABASE_URL`           | `""` (compose supplies it) | PostgreSQL connection URL         |
| `DATABASE_POOL_SIZE`     | 20                         | Base connection pool size         |
| `DATABASE_POOL_OVERFLOW` | 30                         | Additional connections under load |
| `DATABASE_POOL_TIMEOUT`  | 30                         | Seconds to wait for connection    |
| `DATABASE_POOL_RECYCLE`  | 1800                       | Connection recycle interval       |

**Source:** `backend/core/config.py:377-420`

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

**Source:** `backend/core/config.py:465-563`

### Redis SSL/TLS Settings

| Variable                   | Default    | Description                   |
| -------------------------- | ---------- | ----------------------------- |
| `REDIS_SSL_ENABLED`        | false      | Enable SSL/TLS                |
| `REDIS_SSL_CERT_REQS`      | `required` | Certificate verification mode |
| `REDIS_SSL_CA_CERTS`       | None       | CA certificate path           |
| `REDIS_SSL_CERTFILE`       | None       | Client certificate path       |
| `REDIS_SSL_KEYFILE`        | None       | Client key path               |
| `REDIS_SSL_CHECK_HOSTNAME` | true       | Verify hostname               |

**Source:** `backend/core/config.py:593-624`

### Cache TTL Settings

| Variable              | Default | Description                   |
| --------------------- | ------- | ----------------------------- |
| `CACHE_DEFAULT_TTL`   | 300     | Default TTL (5 minutes)       |
| `CACHE_SHORT_TTL`     | 60      | Short TTL (1 minute)          |
| `CACHE_LONG_TTL`      | 3600    | Long TTL (1 hour)             |
| `CACHE_SWR_STALE_TTL` | 60      | Stale-while-revalidate window |
| `CACHE_SWR_ENABLED`   | true    | Enable SWR pattern            |
| `SNAPSHOT_CACHE_TTL`  | 3600    | Camera snapshot cache TTL     |

**Source:** `backend/core/config.py:698-736`

### AI Service Endpoints

The two AI services are `ai-gateway` (Triton) and `ai-vlm` (llama.cpp). `.env.example` defaults:

| Variable               | Default                           | Description                                                          |
| ---------------------- | --------------------------------- | -------------------------------------------------------------------- |
| `AI_GATEWAY_URL`       | `http://ai-gateway:8090`          | Gateway base URL (`USE_AI_GATEWAY=true` routes detection through it) |
| `USE_AI_GATEWAY`       | true                              | Build the detector URL from `AI_GATEWAY_URL` + `/yolo26`             |
| `YOLO26_URL`           | `http://localhost:8090/yolo26`    | Direct detector route (used when `USE_AI_GATEWAY` is not true)       |
| `AI_VLM_URL`           | `http://localhost:8098`           | ai-vlm base URL — the `vlm_assess` engine wire                       |
| `ENRICHMENT_LIGHT_URL` | `http://localhost:8090/enrich-lt` | `/enrich-lt` readiness lane (read by the backend's model management) |

In containers the same routes use `http://ai-gateway:8090/...` and `AI_VLM_URL=http://ai-vlm:8098`
(`docker-compose.prod.yml:557`). The gateway mounts exactly two routers — `/yolo26` and `/enrich-lt`
(`ai/gateway/main.py:276-277`). ai-vlm is the only LLM service.

### Pipeline Selection and Residency

| Variable                | Default | Description                                                                                                             |
| ----------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------- |
| `PIPELINE_MODE`         | `vlm`   | Only `vlm` parses; any other value raises at boot (`backend/core/config.py:1061-1063`)                                  |
| `GATEWAY_MODEL_SET`     | `vlm`   | Triton residency set; only `vlm` is accepted, anything else raises at container start (`ai/gateway/residency.py:79-83`) |
| `GATEWAY_ENABLE_THREAT` | false   | Opt the `threat` model into the Triton set                                                                              |
| `BACKEND_MODEL_PRELOAD` | false   | Boot sweep that loads `preload: true` rows from `models.yml`                                                            |

`PIPELINE_MODE` and `GATEWAY_MODEL_SET` ship as `vlm` in `.env.example` and are pinned to agree with
the compose defaults by `test_gateway_model_set_compose.py`.

### AI Service Timeouts

| Variable                      | Default | Description                            |
| ----------------------------- | ------- | -------------------------------------- |
| `AI_CONNECT_TIMEOUT`          | 10.0    | Connection timeout (seconds)           |
| `AI_HEALTH_TIMEOUT`           | 5.0     | Health check timeout                   |
| `YOLO26_READ_TIMEOUT`         | 30.0    | Detection response timeout             |
| `AI_VLM_READ_TIMEOUT`         | 25.0    | Per-`vlm_assess`-attempt ceiling       |
| `AI_VLM_WAKE_TIMEOUT_SECONDS` | 90.0    | Read timeout for the wake-on-open ping |

**Source:** `backend/core/config.py:1093-1134`; the VLM pair is threaded in `docker-compose.prod.yml:559-560`.

### Batch Processing

| Variable                       | Default | Description                  |
| ------------------------------ | ------- | ---------------------------- |
| `BATCH_WINDOW_SECONDS`         | 90      | Maximum batch window         |
| `BATCH_IDLE_TIMEOUT_SECONDS`   | 30      | Idle timeout for early close |
| `BATCH_CHECK_INTERVAL_SECONDS` | 5.0     | Timeout check frequency      |
| `BATCH_MAX_DETECTIONS`         | 500     | Max detections before split  |

**Source:** `backend/core/config.py:925-971`

### Fast Path Configuration

| Variable                         | Default in `Settings` | Default in compose / `.env.example`                      |
| -------------------------------- | --------------------- | -------------------------------------------------------- |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | 2.0 (above any score) | 0.90 (`docker-compose.prod.yml:625`, `.env.example:650`) |
| `FAST_PATH_OBJECT_TYPES`         | `[]` (empty)          | commented out, so empty                                  |

`BatchAggregator._should_use_fast_path` requires the detected type to appear in
`FAST_PATH_OBJECT_TYPES` (`backend/services/batch_aggregator.py:1185-1216`), and the shipped list is
empty, so no detection takes the fast path — every detection reaches the analyzer through the normal
batch gate regardless of the threshold. The threshold's own field default (2.0) is above any
possible confidence, which is the second guard.

**Source:** `backend/core/config.py:1892-1910`

### Application Settings

| Variable         | Default      | Description                                                        |
| ---------------- | ------------ | ------------------------------------------------------------------ |
| `DEBUG`          | false        | Enable debug mode                                                  |
| `ENVIRONMENT`    | `production` | Deployment environment                                             |
| `ADMIN_ENABLED`  | true         | Enable admin endpoints (compose threads `${ADMIN_ENABLED:-false}`) |
| `ADMIN_API_KEY`  | None         | Admin API key (reserved, not enforced)                             |
| `API_HOST`       | `0.0.0.0`    | API bind address                                                   |
| `API_PORT`       | 8000         | API port                                                           |
| `RETENTION_DAYS` | 30           | Data retention period                                              |

**Source:** `backend/core/config.py:812-922`

### CORS Settings

| Variable       | Default     | Description          |
| -------------- | ----------- | -------------------- |
| `CORS_ORIGINS` | (see below) | Allowed CORS origins |

Default CORS origins (see `backend/core/config.py:874-884`):

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

### LLM Context and Token Budgets

These feed `backend/services/token_counter.py`, which sizes prompts before they go to ai-vlm
(`backend/services/token_counter.py:144-145`).

Declared in `.env.example`:

| Variable       | Default | Settings field            | Description                                              |
| -------------- | ------- | ------------------------- | -------------------------------------------------------- |
| `CTX_SIZE`     | 262144  | `nemotron_context_window` | llama.cpp's total pool; aliased and divided by the slots |
| `PARALLEL`     | 8       | `llama_slot_count`        | llama.cpp slots sharing that pool                        |
| `VLM_CTX_SIZE` | 32768   | `vlm_context_window`      | The VLM serve's own pool, mirrored to the backend        |
| `VLM_PARALLEL` | 2       | —                         | Slots on the VLM serve (`docker-compose.prod.yml:587`)   |

These four resolve to their `Settings` defaults in every deployment — none appears in
`.env.example` or in any compose `environment:` block:

| Field                                   | Default       | Description                                                         |
| --------------------------------------- | ------------- | ------------------------------------------------------------------- |
| `nemotron_max_output_tokens`            | 1536          | Tokens reserved for output; prompts validated against window − this |
| `context_utilization_warning_threshold` | 0.80          | Warning threshold                                                   |
| `context_truncation_enabled`            | true          | Enable smart truncation                                             |
| `llm_tokenizer_encoding`                | `cl100k_base` | Token counting encoding                                             |

With the shipped values the per-request budget resolves to `262144 // 8 = 32768` tokens:
`CTX_SIZE` is read through a `validation_alias` and divided by the slot count before it becomes what
the token counter uses (`backend/core/config.py:1268-1287`), so the number in `.env` is not the number applied.

**Source:** `backend/core/config.py:1213-1300`, `.env.example:407-411`

### Feature Toggles

`GET/PATCH /api/settings` reports a `features` block whose keys are mapped to environment variables by
`SETTINGS_ENV_MAP` (`backend/api/routes/settings_api.py:40`); a PATCH writes them to
`data/runtime.env` and clears the settings cache (`backend/api/routes/settings_api.py:279`). Three of
the reported toggles have no consumer in the shipped pipeline — they are surfaced and mapped, and
nothing reads them:

| Variable                    | Default | What actually reads it                         |
| --------------------------- | ------- | ---------------------------------------------- |
| `VISION_EXTRACTION_ENABLED` | true    | nothing — reported and mapped only             |
| `REID_ENABLED`              | true    | nothing — reported and mapped only             |
| `IMAGE_QUALITY_ENABLED`     | true    | nothing — no BRISQUE model ships in this stack |

**Sources:** the fields at `backend/core/config.py:1674`, `backend/core/config.py:1699`, and
`backend/core/config.py:1704`; the response assembles them at
`backend/api/routes/settings_api.py:126-133`; the shipped-stack note on BRISQUE is at
`backend/api/routes/system.py:4821`.

Two neighbouring toggles in the same block do gate live code: `CLIP_GENERATION_ENABLED`
(`backend/services/clip_generator.py:176`) and `BACKGROUND_EVALUATION_ENABLED`
(`backend/main.py:1054`).

Whether a specialist leg actually runs on an event is decided by weight residency, not by any of these
toggles: the face and re-ID legs answer `unavailable` until the `BACKEND_MODEL_PRELOAD` boot sweep
loads them (`backend/services/osnet_loader.py:182-203`, `backend/services/face_recognizer_loader.py:466-490`).

## Nested Settings Classes

### OrchestratorSettings

Container orchestrator configuration for Docker/Podman management.

**Source:** `backend/core/config.py:115-359`

| Variable                                | Default | Description             |
| --------------------------------------- | ------- | ----------------------- |
| `ORCHESTRATOR_ENABLED`                  | true    | Enable orchestration    |
| `ORCHESTRATOR_DOCKER_HOST`              | None    | Docker/Podman host URL  |
| `ORCHESTRATOR_HEALTH_CHECK_INTERVAL`    | 30      | Health check interval   |
| `ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES` | 5       | Failures before disable |

### TranscodeCacheSettings

Video transcoding cache configuration.

**Source:** `backend/core/config.py:42-112`

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

Both AI service URL fields — `yolo26_url` and `ai_vlm_url` — go through one validator.

**Source:** `backend/core/config.py:1454-1487`

```python
@field_validator("yolo26_url", "ai_vlm_url", mode="before")
@classmethod
def validate_ai_service_urls(cls, v: Any) -> str:
    """Validate AI service URLs using Pydantic's AnyHttpUrl validator."""
    if v is None:
        raise ValueError("AI service URL cannot be None")
    url_str = str(v)
    try:
        validated_url = AnyHttpUrl(url_str)
        # Strip trailing slash to avoid double-slash when appending paths like /health
        return str(validated_url).rstrip("/")
    except Exception as e:
        raise ValueError(
            f"Invalid AI service URL '{url_str}': must be a valid HTTP/HTTPS URL. "
            ...
        ) from None
```

### Grafana URL Validation

Grafana URLs include SSRF protection.

**Source:** `backend/core/config.py:1590-1619`

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

# AI Services (Docker — ai-gateway + ai-vlm)
AI_GATEWAY_URL=http://ai-gateway:8090
USE_AI_GATEWAY=true
YOLO26_URL=http://ai-gateway:8090/yolo26
AI_VLM_URL=http://ai-vlm:8098
ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt

# Pipeline selection (both must stay `vlm`)
PIPELINE_MODE=vlm
GATEWAY_MODEL_SET=vlm
GATEWAY_ENABLE_THREAT=false
BACKEND_MODEL_PRELOAD=false

# Batch Processing
BATCH_WINDOW_SECONDS=90
BATCH_IDLE_TIMEOUT_SECONDS=30

# Detection
DETECTION_CONFIDENCE_THRESHOLD=0.5

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
