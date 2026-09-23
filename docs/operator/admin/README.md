# Administration Guide

> Configuration, secrets management, and security for Home Security Intelligence.

---

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Environment Variables](#environment-variables)
- [Secrets Management](#secrets-management)
- [Security Configuration](#security-configuration)
- [Database Configuration](#database-configuration)
- [Redis Configuration](#redis-configuration)
- [AI Service Configuration](#ai-service-configuration)
- [TLS/HTTPS Configuration](#tlshttps-configuration)
- [Rate Limiting](#rate-limiting)
- [Logging Configuration](#logging-configuration)
- [Data Retention](#data-retention)

---

## Configuration Overview

### Loading Order

Configuration loads in this order (later sources override earlier):

1. Default values in `backend/core/config.py`
2. `.env` file in project root
3. `data/runtime.env` (runtime overrides)
4. Environment variables (highest priority)

### Key Configuration Files

| File                     | Purpose                                         |
| ------------------------ | ----------------------------------------------- |
| `.env`                   | Local overrides (git ignored)                   |
| `.env.example`           | Template with documented defaults               |
| `data/runtime.env`       | Runtime overrides (survives container rebuilds) |
| `backend/core/config.py` | Source of truth for all settings                |

### Quick Setup

```bash
# Interactive setup (recommended)
python setup.py                 # Quick mode
python setup.py --guided        # Guided mode with explanations

# Manual setup
cp .env.example .env
# Edit .env with your settings
chmod 600 .env
```

---

## Environment Variables

### Essential Variables

```bash
# Database (REQUIRED - no default password)
DATABASE_URL=postgresql+asyncpg://security:<password>@postgres:5432/security

# Redis
REDIS_URL=redis://redis:6379

# AI Services (production - compose network)
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
NEMOTRON_URL=http://ai-llm:8091
YOLO26_URL=http://ai-gateway:8090/yolo26
FLORENCE_URL=http://ai-gateway:8090/florence
CLIP_URL=http://ai-gateway:8090/clip
ENRICHMENT_URL=http://ai-gateway:8090/enrichment
ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt

# Camera uploads
FOSCAM_BASE_PATH=/export/foscam

# Retention
RETENTION_DAYS=30
```

### Application Settings

| Variable        | Default                      | Description                                                    |
| --------------- | ---------------------------- | -------------------------------------------------------------- |
| `APP_NAME`      | `Home Security Intelligence` | Application display name                                       |
| `APP_VERSION`   | `0.1.0`                      | Version string                                                 |
| `DEBUG`         | `false`                      | Enable debug mode                                              |
| `ADMIN_ENABLED` | `true`                       | Enable admin endpoints — the only gate; DEBUG is not consulted |
| `ADMIN_API_KEY` | _none_                       | Reserved, not enforced — no code path reads it                 |

### Detection Settings

| Variable                         | Default      | Range      | Description            |
| -------------------------------- | ------------ | ---------- | ---------------------- |
| `DETECTION_CONFIDENCE_THRESHOLD` | `0.5`        | 0.0-1.0    | Minimum confidence     |
| `FAST_PATH_CONFIDENCE_THRESHOLD` | `0.90`       | 0.0-1.0    | Fast path threshold    |
| `FAST_PATH_OBJECT_TYPES`         | `["person"]` | JSON array | Fast path object types |

### Batch Processing

| Variable                     | Default | Range  | Description            |
| ---------------------------- | ------- | ------ | ---------------------- |
| `BATCH_WINDOW_SECONDS`       | `90`    | 1-3600 | Maximum batch duration |
| `BATCH_IDLE_TIMEOUT_SECONDS` | `30`    | 1-3600 | Close batch after idle |

### AI Service Timeouts

| Variable                | Default | Range      | Description              |
| ----------------------- | ------- | ---------- | ------------------------ |
| `AI_CONNECT_TIMEOUT`    | `10.0`  | 1.0-60.0   | Connection timeout (s)   |
| `AI_HEALTH_TIMEOUT`     | `5.0`   | 1.0-30.0   | Health check timeout (s) |
| `YOLO26_READ_TIMEOUT`   | `30.0`  | 5.0-120.0  | Detection timeout (s)    |
| `NEMOTRON_READ_TIMEOUT` | `120.0` | 30.0-600.0 | LLM timeout (s)          |

### GPU Monitoring

| Variable                    | Default | Range    | Description       |
| --------------------------- | ------- | -------- | ----------------- |
| `GPU_POLL_INTERVAL_SECONDS` | `5.0`   | 1.0-60.0 | GPU stats polling |
| `GPU_STATS_HISTORY_MINUTES` | `60`    | 1-1440   | In-memory history |

### Camera Integration

| Variable                        | Default          | Description                          |
| ------------------------------- | ---------------- | ------------------------------------ |
| `FOSCAM_BASE_PATH`              | `/export/foscam` | FTP upload directory                 |
| `FILE_WATCHER_POLLING`          | `false`          | Use polling instead of native events |
| `FILE_WATCHER_POLLING_INTERVAL` | `1.0`            | Polling interval (seconds)           |

---

## Secrets Management

### Docker Secrets (Recommended for Production)

Docker Secrets provide enhanced security over environment variables:

- Not visible in `docker inspect` output
- Mounted read-only in containers at `/run/secrets/`
- Stored with restrictive permissions (600)

#### Setup

```bash
# Create secrets directory
mkdir -p secrets && chmod 700 secrets

# Generate secure passwords
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/redis_password.txt
openssl rand -base64 32 > secrets/grafana_admin_password.txt

# Set permissions
chmod 600 secrets/*.txt
```

#### Enable in Docker Compose

Uncomment the secrets sections in `docker-compose.prod.yml`:

```yaml
# Bottom of docker-compose.prod.yml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  grafana_admin_password:
    file: ./secrets/grafana_admin_password.txt
```

```yaml
# PostgreSQL service
postgres:
  secrets:
    - postgres_password
  environment:
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

# Redis service
redis:
  secrets:
    - redis_password
  command: >-
    sh -c '
    if [ -f /run/secrets/redis_password ]; then
      REDIS_PASSWORD=$(cat /run/secrets/redis_password)
      redis-server --requirepass "$REDIS_PASSWORD"
    else
      redis-server
    fi
    '
```

#### Verify Secrets

```bash
# Check secrets are mounted
podman compose -f docker-compose.prod.yml exec postgres ls -la /run/secrets/
podman compose -f docker-compose.prod.yml exec redis ls -la /run/secrets/
```

### Secret Rotation

```bash
# 1. Update secret file
echo "new_password" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt

# 2. Restart affected service
podman compose -f docker-compose.prod.yml restart postgres

# 3. Restart dependent services
podman compose -f docker-compose.prod.yml restart backend
```

### Secrets vs Environment Variables

| Feature                    | Environment Variables | Docker Secrets |
| -------------------------- | --------------------- | -------------- |
| Setup complexity           | Simple                | Moderate       |
| Visible in docker inspect  | Yes                   | No             |
| Visible in process listing | Yes                   | No             |
| Credential rotation        | Rebuild required      | Restart only   |
| Best for                   | Development           | Production     |

---

## Security Configuration

### Default Security Posture

| Feature         | Default                                                                                                                                                                                                                                                              | Production Recommendation                                                                         |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Authentication  | Single-user model: `SetupGuardMiddleware` returns 503 until the first admin registers, then API endpoints are open (`verify_api_key` guards the DLQ/inbound-webhook routes, not admin; `/api/admin/*` is guarded by `require_admin_access` on `ADMIN_ENABLED` alone) | Keep network binding to `127.0.0.1` as the primary boundary; enable API keys for anything exposed |
| HTTPS/TLS       | Disabled                                                                                                                                                                                                                                                             | Enable                                                                                            |
| Rate Limiting   | Enabled                                                                                                                                                                                                                                                              | Keep enabled                                                                                      |
| Admin Endpoints | Enabled — `ADMIN_ENABLED=true` by default; `DEBUG` is not consulted, `ADMIN_API_KEY` enforces nothing                                                                                                                                                                | Keep off non-loopback interfaces, or set `ADMIN_ENABLED=false`                                    |
| Debug Mode      | Disabled                                                                                                                                                                                                                                                             | Keep disabled                                                                                     |
| CORS            | Localhost origins (incl. `https://localhost:8444`)                                                                                                                                                                                                                   | Restrict to your domains                                                                          |

### API Key Authentication

```bash
# Enable in .env
API_KEY_ENABLED=true
API_KEYS=["your-secure-api-key-here", "another-key-if-needed"]
```

**Making authenticated requests:**

```bash
curl -H "X-API-Key: your-secure-api-key-here" \
  http://localhost:8000/api/events
```

**Generate secure keys:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
# or
openssl rand -base64 32
```

### Admin Endpoint Security

Admin endpoints are gated by **one** condition:

- `ADMIN_ENABLED=true` (the default — `DEBUG` is not consulted)

```bash
# Admin endpoints are enabled by default; this is the only switch
ADMIN_ENABLED=true
# Reserved — NOT enforced: no code path reads ADMIN_API_KEY and no
# X-Admin-API-Key header is validated. Setting it changes nothing.
# ADMIN_API_KEY=your-admin-api-key
```

Admin exposure is therefore controlled by the network bind (`127.0.0.1` / a trusted
network) or by setting `ADMIN_ENABLED=false`.

### CORS Configuration

```bash
# Development
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Production
CORS_ORIGINS=["https://your-domain.com"]
```

### Firewall Configuration

Only expose necessary ports:

| Port        | Service                          | Exposure                                 |
| ----------- | -------------------------------- | ---------------------------------------- |
| 8080 / 8444 | Frontend (HTTP/HTTPS)            | User access                              |
| 8000        | Backend API                      | User access (binds 127.0.0.1 by default) |
| 5432        | PostgreSQL                       | **Internal only**                        |
| 6379        | Redis                            | **Internal only**                        |
| 8090, 8002  | ai-gateway (API, Triton metrics) | **Internal only**                        |
| 8091        | ai-llm (Nemotron)                | **Internal only**                        |

```bash
# UFW example (Linux)
ufw allow 8080/tcp
ufw allow 8444/tcp
ufw allow 8000/tcp
ufw deny 5432/tcp
ufw deny 6379/tcp
ufw enable
```

---

## Database Configuration

### Connection URL Format

```bash
# PostgreSQL (required - SQLite not supported)
DATABASE_URL=postgresql+asyncpg://username:password@host:port/database  # pragma: allowlist secret

# Examples:
# Docker Compose
DATABASE_URL=postgresql+asyncpg://security:your_password@postgres:5432/security  # pragma: allowlist secret

# Native development
DATABASE_URL=postgresql+asyncpg://security:your_password@localhost:5432/security  # pragma: allowlist secret
```

### Required Setup

> **SECURITY: Database password is REQUIRED. No default passwords exist.**

```bash
# Generate secure password
openssl rand -base64 32

# Create .env
POSTGRES_USER=security
POSTGRES_PASSWORD=your-secure-generated-password
POSTGRES_DB=security
DATABASE_URL=postgresql+asyncpg://security:your-secure-generated-password@postgres:5432/security  # pragma: allowlist secret
```

### Schema Migrations

There is **no Alembic step** — the Alembic migrations tree was removed in PR #4465. The
schema is created/synced by `init_db()` (`Base.metadata.create_all`) on backend
startup. See [Migrations](../../architecture/data-model/migrations.md) for the details.

### Database Operations

```bash
# Connect to database
podman compose -f docker-compose.prod.yml exec postgres psql -U security -d security

# Backup
podman compose -f docker-compose.prod.yml exec -T postgres pg_dump -U security -d security -F c > backup.dump

# Restore
podman compose -f docker-compose.prod.yml exec -T postgres pg_restore -U security -d security < backup.dump
```

---

## Redis Configuration

### Connection URL Format

```bash
# Standard Redis
REDIS_URL=redis://localhost:6379/0

# Redis with password
REDIS_URL=redis://:password@localhost:6379/0

# Redis TLS
REDIS_URL=rediss://localhost:6379/0
```

### Password Authentication

```bash
# Generate password
openssl rand -base64 32

# Add to .env
REDIS_PASSWORD=your_generated_password
```

When `REDIS_PASSWORD` is set, both Redis container and backend automatically use it.

### Redis Operations

```bash
# Test connection
podman compose -f docker-compose.prod.yml exec redis redis-cli ping

# Get info
podman compose -f docker-compose.prod.yml exec redis redis-cli INFO memory

# Clear cache (WARNING: loses cached data)
podman compose -f docker-compose.prod.yml exec redis redis-cli FLUSHALL
```

---

## AI Service Configuration

### Service URLs

All vision models live in the single `ai-gateway` container, so there are two base URLs;
the per-service variables carry the **router path**, not a per-model port (the old
8092-8096 ports no longer exist). See [Deployment Modes](../deployment-modes.md).

```bash
# Production (docker-compose.prod.yml defaults)
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
NEMOTRON_URL=http://ai-llm:8091
YOLO26_URL=http://ai-gateway:8090/yolo26
FLORENCE_URL=http://ai-gateway:8090/florence
CLIP_URL=http://ai-gateway:8090/clip
ENRICHMENT_URL=http://ai-gateway:8090/enrichment
ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt

# Development (AI on host; gateway/router listens on host port 8090)
AI_GATEWAY_URL=http://localhost:8090
NEMOTRON_URL=http://localhost:8091
YOLO26_URL=http://localhost:8090/yolo26

# Backend in container + AI on host (Docker Desktop macOS/Windows)
AI_GATEWAY_URL=http://host.docker.internal:8090
NEMOTRON_URL=http://host.docker.internal:8091
```

### Feature Toggles

| Variable                    | Default | Description                   |
| --------------------------- | ------- | ----------------------------- |
| `VISION_EXTRACTION_ENABLED` | `true`  | Enable Florence-2 extraction  |
| `REID_ENABLED`              | `true`  | Enable CLIP re-identification |
| `SCENE_CHANGE_ENABLED`      | `true`  | Enable scene change detection |

---

## TLS/HTTPS Configuration

### TLS Modes

| Mode          | Use Case         | Certificate Source |
| ------------- | ---------------- | ------------------ |
| `disabled`    | Development only | None               |
| `self_signed` | LAN/internal use | Auto-generated     |
| `provided`    | Production       | Your certificates  |

### Self-Signed Certificates

```bash
# .env
TLS_MODE=self_signed
TLS_CERT_DIR=data/certs
# Certificates auto-generated on first start
```

### Production Certificates

```bash
# .env
TLS_MODE=provided
TLS_CERT_PATH=/etc/ssl/certs/server.crt
TLS_KEY_PATH=/etc/ssl/private/server.key
TLS_MIN_VERSION=TLSv1.2
```

### Generate Self-Signed Certificates

```bash
mkdir -p data/certs
cd data/certs

# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate (365 days)
openssl req -new -x509 -key server.key -out server.crt -days 365 \
  -subj "/CN=home-security-intelligence/O=Local Development"

# Set permissions
chmod 600 server.key
chmod 644 server.crt
```

### TLS Variables

| Variable            | Default    | Description                     |
| ------------------- | ---------- | ------------------------------- |
| `TLS_MODE`          | `disabled` | disabled, self_signed, provided |
| `TLS_CERT_PATH`     | _none_     | Certificate file path           |
| `TLS_KEY_PATH`      | _none_     | Private key file path           |
| `TLS_CA_PATH`       | _none_     | CA certificate (for mTLS)       |
| `TLS_VERIFY_CLIENT` | `false`    | Enable mTLS                     |
| `TLS_MIN_VERSION`   | `TLSv1.2`  | Minimum TLS version             |

---

## Rate Limiting

Rate limiting is enabled by default:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE=120
RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE=100
RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE=30
```

### Rate Limit Tiers

| Endpoint Type             | Limit/min                   | Purpose                     |
| ------------------------- | --------------------------- | --------------------------- |
| General API               | 60                          | Normal operations           |
| Media (images/thumbnails) | 120                         | Higher for dashboards       |
| Search                    | 30                          | Lower (expensive operation) |
| WebSocket                 | 100 connection attempts/min | Prevent connection storms   |

---

## Logging Configuration

| Variable                | Default                  | Description                           |
| ----------------------- | ------------------------ | ------------------------------------- |
| `LOG_LEVEL`             | `WARNING`                | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `LOG_FILE_PATH`         | `data/logs/security.log` | Rotating log file                     |
| `LOG_FILE_MAX_BYTES`    | `10485760`               | Max log file size (10MB)              |
| `LOG_FILE_BACKUP_COUNT` | `7`                      | Number of backup files                |
| `LOG_DB_ENABLED`        | `true`                   | Write logs to database                |
| `LOG_DB_MIN_LEVEL`      | `DEBUG`                  | Minimum level for DB                  |

---

## Data Retention

### Retention Settings

| Variable             | Default | Range | Description                 |
| -------------------- | ------- | ----- | --------------------------- |
| `RETENTION_DAYS`     | `30`    | 1-365 | Events/detections retention |
| `LOG_RETENTION_DAYS` | `7`     | 1-365 | Database logs retention     |

### Automated Cleanup

Cleanup runs daily at 03:00.

```bash
# Preview cleanup (dry run) — the endpoint is guarded by verify_api_key, so send
# X-API-Key (validated against API_KEYS) when API_KEY_ENABLED=true
curl -X POST "http://localhost:8000/api/system/cleanup?dry_run=true"

# Execute cleanup
curl -X POST "http://localhost:8000/api/system/cleanup"
```

### Storage Estimates

| Deployment | Cameras | Recommended Disk | Retention  |
| ---------- | ------- | ---------------- | ---------- |
| Small      | 1-4     | 50GB             | 30 days    |
| Medium     | 5-8     | 100GB            | 30 days    |
| Large      | 8+      | 250GB+           | 14-30 days |

---

## Security Checklist

### Development

- [ ] Debug mode can be enabled
- [ ] Self-signed certs acceptable
- [ ] CORS allows localhost

### Production

- [ ] `DEBUG=false`
- [ ] `ADMIN_ENABLED=false`
- [ ] TLS with valid certificates
- [ ] API keys required
- [ ] POSTGRES_PASSWORD set (required)
- [ ] Strong, unique passwords (32+ chars)
- [ ] `.env` file permissions are `600`
- [ ] Docker secrets for credentials
- [ ] Firewall configured
- [ ] Database not exposed externally
- [ ] Redis not exposed externally
- [ ] AI services not exposed externally
- [ ] CORS restricted to your domain
- [ ] Log retention configured
- [ ] Backups encrypted

---

## Example Configurations

### Development

```bash
DATABASE_URL=postgresql+asyncpg://security:dev_password@localhost:5432/security  # pragma: allowlist secret
REDIS_URL=redis://localhost:6379/0
YOLO26_URL=http://localhost:8090/yolo26
NEMOTRON_URL=http://localhost:8091
FOSCAM_BASE_PATH=/export/foscam
DEBUG=true
LOG_LEVEL=DEBUG
```

### Production

```bash
DATABASE_URL=postgresql+asyncpg://security:secure_password@postgres:5432/security  # pragma: allowlist secret
REDIS_URL=redis://redis:6379
USE_AI_GATEWAY=true
AI_GATEWAY_URL=http://ai-gateway:8090
YOLO26_URL=http://ai-gateway:8090/yolo26
NEMOTRON_URL=http://ai-llm:8091
DEBUG=false
LOG_LEVEL=WARNING
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

```bash
# Check backend config loads correctly (run from the repo root; DATABASE_URL must be set)
uv run python -c "from backend.core.config import get_settings; s = get_settings(); print(s.model_dump_json(indent=2))"

# Test service connectivity
curl http://localhost:8000/api/system/health     # Backend
curl http://localhost:8090/yolo26/health         # ai-gateway /yolo26 router
curl http://localhost:8091/health                # Nemotron
redis-cli ping                                   # Redis
```

---

## See Also

- [Operator Hub](../README.md) - Main operator documentation
- [Deployment Guide](../deployment/README.md) - Service setup
- [Monitoring Guide](../monitoring/README.md) - Health checks and metrics
- [Backup and Recovery](../backup.md) - Database backup
- [Redis Setup](../redis.md) - Redis configuration
