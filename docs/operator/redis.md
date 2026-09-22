# Redis Setup and Configuration

> Complete guide to setting up, configuring, and securing Redis for Home Security Intelligence.

**Time to read:** ~10 min
**Prerequisites:** Container runtime (Docker/Podman), Redis basics

---

## Redis Overview

Home Security Intelligence uses **Redis 7.4+** as its in-memory data store for:

- **Pub/Sub messaging** - Real-time event broadcasting to WebSocket clients
- **Queue management** - Detection pipeline queues with backpressure handling
- **Caching** - File deduplication and temporary data
- **Rate limiting** - API rate limit tracking

> **Note:** Redis is required for normal operation. If the connection fails at startup the
> backend process still comes up but logs "Continuing without Redis" and skips the queue
> workers — `/api/system/health/ready` then reports `not_ready` (readiness fails when
> Redis is unhealthy or the detection/analysis workers are down).

### Data Stored in Redis

| Data Type             | Key Pattern             | Purpose                           |
| --------------------- | ----------------------- | --------------------------------- |
| Detection queues      | `hsi:queue:*`           | Pipeline processing queues        |
| Dead-letter queues    | `hsi:queue:dlq:*`       | Failed items for retry/inspection |
| Cache entries         | `hsi:cache:*`           | Temporary data caching            |
| File deduplication    | `dedupe:*`              | Prevent duplicate processing      |
| Batch aggregation     | `batch:*`               | Detection batching state          |
| Job tracking          | `job:*`                 | Background job status             |
| Service orchestration | `orchestrator:*`        | Container service state           |
| Entity embeddings     | `entity_embeddings:*`   | Re-ID person/vehicle tracking     |
| Pub/Sub channels      | `security_events`, etc. | Real-time event broadcasting      |

> **Developer Note:** For detailed key patterns and naming conventions, see [Redis Key Conventions](../developer/redis-key-conventions.md).

### Memory Usage Estimates

| Deployment | Cameras | Typical Memory |
| ---------- | ------- | -------------- |
| Small      | 1-4     | 50-100MB       |
| Medium     | 5-8     | 100-200MB      |
| Large      | 8+      | 200-512MB      |

---

## Initial Setup

### Option 1: Container-Based (Recommended)

```bash
# Start Redis container
podman compose -f docker-compose.prod.yml up -d redis

# Verify health
podman compose -f docker-compose.prod.yml ps redis
```

The Redis container (`docker.io/library/redis:7.4-alpine3.21`) is configured in
`docker-compose.prod.yml` with:

- Persistent storage via `redis_data` volume; AOF persistence (`--appendonly yes
--appendfsync everysec`)
- `--maxmemory 512mb --maxmemory-policy volatile-lru` and slow-log tuning
- Health check via `redis-cli ping` (with AUTH when a password is set)
- Optional password authentication (`REDIS_PASSWORD`)
- Host binding `127.0.0.1:${REDIS_PORT:-6379}` only (NEM-4496)
- Read-only rootfs and dropped capabilities (NEM-4978)

### Option 2: Native Redis

```bash
# Install (Ubuntu/Debian)
sudo apt install redis-server

# Install (Fedora/RHEL)
sudo dnf install redis

# Start and enable service
sudo systemctl enable --now redis
```

---

## Password Authentication

Redis authentication protects your data from unauthorized access. For production deployments, **always enable password authentication**.

### How Authentication Works

1. **Redis server** is started with `--requirepass <password>` flag
2. **Backend** reads `REDIS_PASSWORD` environment variable
3. **Backend** passes password to Redis connection pool
4. All Redis commands are authenticated automatically

### Setting Up Authentication

#### Step 1: Generate a Secure Password

```bash
# Generate a strong 32-character password
openssl rand -base64 32
```

Example output: `K7mP9xQ2nL4hR6wY8vB1tF3jD5gS0aZ/cE9uI2oA+Xk=`

#### Step 2: Set REDIS_PASSWORD in .env

Add to your `.env` file:

```bash
# Redis password authentication
# SECURITY: Use a strong password in production
REDIS_PASSWORD=K7mP9xQ2nL4hR6wY8vB1tF3jD5gS0aZ/cE9uI2oA+Xk=
```

#### Step 3: Verify Configuration

The `docker-compose.prod.yml` file automatically configures Redis based on `REDIS_PASSWORD`:

```yaml
redis:
  image: docker.io/library/redis:7.4-alpine3.21
  command: >-
    sh -c '
    if [ -n "$$REDIS_PASSWORD" ]; then
      echo "Starting Redis with password authentication"
      redis-server --appendonly yes --appendfsync everysec --maxmemory 512mb --maxmemory-policy volatile-lru --slowlog-log-slower-than 10000 --slowlog-max-len 128 --stop-writes-on-bgsave-error no --requirepass "$$REDIS_PASSWORD"
    else
      echo "Starting Redis without authentication (development mode)"
      redis-server --appendonly yes --appendfsync everysec --maxmemory 512mb --maxmemory-policy volatile-lru --slowlog-log-slower-than 10000 --slowlog-max-len 128 --stop-writes-on-bgsave-error no
    fi
    '
  environment:
    - REDIS_PASSWORD=${REDIS_PASSWORD:-}
```

**Key points:**

- If `REDIS_PASSWORD` is set and non-empty, Redis requires authentication
- If `REDIS_PASSWORD` is empty or unset, Redis runs without authentication (development only)
- The backend automatically uses the same `REDIS_PASSWORD` for connections

### How the Backend Connects

The backend's Redis client (`backend/core/redis.py`) automatically handles authentication:

```python
# From RedisClient.connect()
if self._password:
    pool_kwargs["password"] = self._password

# Connection logging shows auth status
logger.info(f"Successfully connected to Redis{ssl_msg}{auth_msg}")
```

The password is read from settings (`backend/core/config.py`):

```python
redis_password: str | None = Field(
    default=None,
    description="Redis password for authentication..."
)
```

### Environment Variable Reference

| Variable         | Description                 | Default                    |
| ---------------- | --------------------------- | -------------------------- |
| `REDIS_URL`      | Redis connection URL        | `redis://localhost:6379/0` |
| `REDIS_PASSWORD` | Password for authentication | (none)                     |

**Container deployment example:**

```bash
# .env file
REDIS_URL=redis://redis:6379
REDIS_PASSWORD=your_secure_password_here
```

**Native development example:**

```bash
# .env file
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=  # Empty = no authentication (dev only)
```

---

## Monitoring Stack Integration

The Redis exporter ships in the default compose stack (no profile) and also needs
authentication:

```yaml
redis-exporter:
  image: docker.io/oliver006/redis_exporter:v1.55.0
  ports:
    - '127.0.0.1:${REDIS_EXPORTER_PORT:-9121}:9121'
  environment:
    - REDIS_ADDR=redis://redis:6379
    - REDIS_PASSWORD=${REDIS_PASSWORD:-}
```

The exporter automatically uses the same `REDIS_PASSWORD` to scrape Redis metrics;
Prometheus scrapes it via the `redis` job.

---

## Troubleshooting Authentication Issues

### Symptom: "NOAUTH Authentication required"

**Cause:** Redis requires a password but the backend is connecting without one.

**Solution:**

1. Verify `REDIS_PASSWORD` is set in your `.env` file
2. Restart the backend container to pick up the new environment variable

```bash
# Check if password is set in backend container
podman compose -f docker-compose.prod.yml exec backend printenv | grep REDIS

# Restart backend
podman compose -f docker-compose.prod.yml restart backend
```

### Symptom: "WRONGPASS invalid username-password pair"

**Cause:** Password mismatch between Redis and backend.

**Solution:**

1. Verify the password matches in both services:

```bash
# Check Redis container
podman compose -f docker-compose.prod.yml exec redis printenv REDIS_PASSWORD

# Check backend container
podman compose -f docker-compose.prod.yml exec backend printenv REDIS_PASSWORD
```

2. If they differ, fix `.env` and restart both services:

```bash
podman compose -f docker-compose.prod.yml down
podman compose -f docker-compose.prod.yml up -d
```

### Symptom: "Connection refused" after enabling auth

**Cause:** Redis container hasn't restarted with the new password.

**Solution:**

```bash
# Force recreation of Redis container
podman compose -f docker-compose.prod.yml up -d --force-recreate redis

# Wait for health check to pass
podman compose -f docker-compose.prod.yml ps redis
```

### Symptom: Backend starts but can't connect to Redis

**Cause:** Environment variable not loaded or typo in variable name.

**Solution:**

1. Check variable name (case-insensitive, but verify):

```bash
# Correct
REDIS_PASSWORD=secret

# Wrong (these won't work)
REDIS_PASS=secret
redis_password=secret  # Works, but use consistent casing
```

2. Check for leading/trailing whitespace in `.env`:

```bash
# Wrong (has trailing space)
REDIS_PASSWORD=secret

# Correct
REDIS_PASSWORD=secret
```

### Testing Redis Authentication Manually

```bash
# Test from outside container (if port is exposed)
redis-cli -h localhost -p 6379 -a "your_password" ping

# Test from inside Redis container
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping

# Expected output: PONG
```

### Checking Connection Logs

```bash
# Backend logs show connection status
podman compose -f docker-compose.prod.yml logs backend | grep -i redis

# Look for:
# "Successfully connected to Redis with authentication"  (good)
# "NOAUTH Authentication required"                       (password missing)
# "WRONGPASS invalid username-password pair"             (password mismatch)
```

---

## SSL/TLS Configuration

For encrypted Redis connections, see the SSL/TLS settings in `.env.example`:

| Variable                   | Description                       | Default    |
| -------------------------- | --------------------------------- | ---------- |
| `REDIS_SSL_ENABLED`        | Enable SSL/TLS encryption         | `false`    |
| `REDIS_SSL_CERT_REQS`      | Certificate verification mode     | `required` |
| `REDIS_SSL_CA_CERTS`       | Path to CA certificate            | (none)     |
| `REDIS_SSL_CERTFILE`       | Path to client certificate (mTLS) | (none)     |
| `REDIS_SSL_KEYFILE`        | Path to client key (mTLS)         | (none)     |
| `REDIS_SSL_CHECK_HOSTNAME` | Verify server hostname            | `true`     |

> **Note:** SSL/TLS is typically not needed for local deployments where Redis runs in the same Docker network as the backend. Use SSL/TLS for remote Redis instances or when Redis traffic crosses untrusted networks.

---

## Quick Reference

### Essential Commands

```bash
# Start Redis
podman compose -f docker-compose.prod.yml up -d redis

# Check health
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping

# View Redis info
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" info

# Check memory usage
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" info memory

# List all keys (use sparingly)
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" keys '*'

# Clear all data (DANGER - development only)
podman compose -f docker-compose.prod.yml exec redis redis-cli -a "$REDIS_PASSWORD" flushall
```

### Health Check Endpoint

The backend health endpoint reports Redis status:

```bash
curl http://localhost:8000/api/system/health/ready | jq '.services.redis'
```

Expected output when healthy (the readiness response groups infrastructure under
`services`):

```json
{
  "status": "healthy",
  "message": "Redis connected",
  "details": { "redis_version": "7.4.1" }
}
```

---

## Security Best Practices

1. **Always use password authentication in production** - Never run Redis without a password on production systems

2. **Use strong passwords** - Generate with `openssl rand -base64 32`

3. **Don't expose Redis port publicly** - Keep Redis on internal Docker network only

4. **Use SSL/TLS for remote Redis** - If Redis is on a different host, encrypt the connection

5. **Rotate passwords periodically** - Update `REDIS_PASSWORD` and restart services

6. **Monitor for auth failures** - Check logs for repeated authentication failures (potential attacks)

---

## Next Steps

- [Database Setup](database.md) - PostgreSQL configuration
- [Backup and Recovery](backup.md) - Data backup procedures
- [Deployment Modes](deployment-modes.md) - Container networking options

---

## See Also

- [Environment Variable Reference](../reference/config/env-reference.md) - Complete configuration reference
- [Troubleshooting](../reference/troubleshooting/index.md) - General troubleshooting guide

---

[Back to Operator Hub](README.md)
