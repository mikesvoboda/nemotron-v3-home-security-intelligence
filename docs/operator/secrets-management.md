# Secrets Management

> Secure credential storage using Docker Secrets for production deployments.

This guide covers Docker Secrets configuration for Home Security Intelligence. For comprehensive implementation details, see [Administration Guide](admin/README.md).

---

## Overview

Docker Secrets provide enhanced security for credential management by storing sensitive data separately from environment variables and injecting them into containers at runtime.

### Why Use Docker Secrets?

| Feature                        | Environment Variables | Docker Secrets                |
| ------------------------------ | --------------------- | ----------------------------- |
| Visibility in `docker inspect` | Visible               | Hidden                        |
| File permissions               | N/A                   | 600 (restricted)              |
| Credential rotation            | Requires restart      | Update file, restart service  |
| Container access               | Read-write            | Read-only at `/run/secrets/`  |
| Git risk                       | Often in `.env` files | Separate `secrets/` directory |

### Supported Secrets

| Secret                 | File                         | Service (what actually consumes it)                                                                      |
| ---------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------- |
| PostgreSQL password    | `postgres_password.txt`      | postgres (`POSTGRES_PASSWORD_FILE`, native)                                                              |
| Redis password         | `redis_password.txt`         | redis (only via a modified startup command — the shipped command reads the `REDIS_PASSWORD` env var)     |
| Grafana admin password | `grafana_admin_password.txt` | grafana (requires a custom entrypoint — Grafana does not read `_FILE` vars and the repo image adds none) |

> [!IMPORTANT] > **Backend limitation:** the Python backend has **no `_FILE` secret support** —
> `backend/core/config.py` and `backend/entrypoint.sh` only read `DATABASE_URL` and
> `REDIS_PASSWORD` from the environment, and nothing in `backend/` reads `/run/secrets/`.
> Mounting secrets into `backend` alone changes nothing; the env-var credentials must
> still be correct. The compose file's commented sections wire secrets only for
> `postgres`; per-service wiring for redis/grafana needs the command/entrypoint edits
> below.

---

## Quick Setup

### 1. Create Secrets Directory

```bash
# Create directory with secure permissions
mkdir -p secrets
chmod 700 secrets

# Generate strong passwords
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/redis_password.txt
openssl rand -base64 32 > secrets/grafana_admin_password.txt

# Set restrictive file permissions
chmod 600 secrets/*.txt
```

Alternatively, `python setup.py --guided` creates the `secrets/` directory (mode 700) and
writes `postgres_password.txt`, `redis_password.txt` and `grafana_admin_password.txt` when
you opt in — there is no `setup.sh`.

### 2. Enable Secrets in docker-compose.prod.yml

Uncomment the secrets section at the bottom of `docker-compose.prod.yml`:

```yaml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  grafana_admin_password:
    file: ./secrets/grafana_admin_password.txt
```

### 3. Update Service Configurations

**PostgreSQL:**

```yaml
postgres:
  secrets:
    - postgres_password
  environment:
    - POSTGRES_USER=${POSTGRES_USER:-security}
    - POSTGRES_DB=${POSTGRES_DB:-security}
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

**Redis:**

```yaml
redis:
  secrets:
    - redis_password
  command: >-
    sh -c '
    if [ -f /run/secrets/redis_password ]; then
      REDIS_PASSWORD=$(cat /run/secrets/redis_password)
      redis-server --appendonly yes --requirepass "$REDIS_PASSWORD"
    else
      redis-server --appendonly yes
    fi
    '
```

**Backend:**

The backend has **no `_FILE` support** — `backend/core/config.py` and
`backend/entrypoint.sh` read only `DATABASE_URL` and `REDIS_PASSWORD` (nothing reads
`/run/secrets/`). When you switch Postgres to a secret, the compose `DATABASE_URL`
password still has to match it, so keep a working `POSTGRES_PASSWORD`/`DATABASE_URL` in
`.env` or add an init step that materializes the secret into the environment. The
`secrets:` mount alone changes nothing for the backend.

```yaml
backend:
  # Mounting the secret alone is not enough — see note above.
  secrets:
    - postgres_password
    - redis_password
```

**Grafana:**

`GF_SECURITY_ADMIN_PASSWORD_FILE` is **not** supported by Grafana's own env parsing, and
the repo's Grafana image (`monitoring/grafana/Dockerfile`) adds no entrypoint to read
`/run/secrets/` — so this path requires a custom wrapper before it works. Today compose
sets `GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD:-admin}`.

### 4. Validate and Deploy

```bash
# Validate configuration
podman compose -f docker-compose.prod.yml config

# Start services
podman compose -f docker-compose.prod.yml up -d

# Verify secrets are mounted
podman compose -f docker-compose.prod.yml exec postgres ls -la /run/secrets/
```

---

## Credential Rotation

### Zero-Downtime Rotation

1. **Update the secret file:**

   ```bash
   # Generate new password
   openssl rand -base64 32 > secrets/postgres_password.txt
   chmod 600 secrets/postgres_password.txt
   ```

2. **Restart the service:**

   ```bash
   podman compose -f docker-compose.prod.yml restart postgres
   ```

3. **Restart dependent services:**

   ```bash
   podman compose -f docker-compose.prod.yml restart backend
   ```

4. **Verify the change:**

   ```bash
   podman compose -f docker-compose.prod.yml logs postgres | tail -20
   curl http://localhost:8000/api/system/health
   ```

### Rotation Schedule

| Credential        | Recommended Rotation | Notes                                  |
| ----------------- | -------------------- | -------------------------------------- |
| Database password | Every 90 days        | Restart postgres, backend              |
| Redis password    | Every 90 days        | Restart redis, backend, redis-exporter |
| Grafana admin     | Every 90 days        | Restart grafana                        |
| **Compromised**   | Immediately          | Full rotation of affected credential   |

---

## Accessing Secrets in Application Code

### Backend

The backend reads credentials only from the environment (`DATABASE_URL`,
`REDIS_PASSWORD` via pydantic-settings) — there is no `/run/secrets/` or `_FILE` lookup in
`backend/core/` or `backend/entrypoint.sh`. If you adopt Docker Secrets, keep those
environment variables populated (matching the secret file's value), or add a wrapper that
materializes the secret into the environment before startup.

### PostgreSQL (Native Support)

PostgreSQL has native support for `POSTGRES_PASSWORD_FILE`:

```yaml
environment:
  - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

### Redis (Command Script)

Redis requires reading the secret in the startup command:

```yaml
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

### Grafana (Requires a Wrapper)

Grafana does **not** read `_FILE`-suffixed variables, and the repo image
(`monitoring/grafana/Dockerfile`, FROM the upstream Grafana image) adds no entrypoint that
would. To feed it a secret you must run a custom entrypoint that exports
`GF_SECURITY_ADMIN_PASSWORD=$(cat /run/secrets/grafana_admin_password)` before starting
Grafana. As shipped, compose uses `GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD:-admin}`.

---

## Migration from Environment Variables

### Current Setup (Environment Variables)

```bash
# .env file
POSTGRES_PASSWORD=my_secret_password
REDIS_PASSWORD=redis_secret
GF_ADMIN_PASSWORD=grafana_secret
```

### Migration Steps

1. **Create secrets files:**

   ```bash
   mkdir -p secrets && chmod 700 secrets
   echo "my_secret_password" > secrets/postgres_password.txt
   echo "redis_secret" > secrets/redis_password.txt
   echo "grafana_secret" > secrets/grafana_admin_password.txt
   chmod 600 secrets/*.txt
   ```

2. **Update docker-compose.prod.yml:**

   - Uncomment the `secrets:` top-level section
   - Add `secrets:` to each service
   - Change environment variables to `_FILE` variants

3. **Remove credentials from .env — with limits:**

   ```bash
   # You can drop these from .env once the services read the secret files:
   # POSTGRES_PASSWORD=...        # only if postgres uses POSTGRES_PASSWORD_FILE end-to-end
   # GF_ADMIN_PASSWORD=...        # only after adding the Grafana wrapper entrypoint
   ```

   `REDIS_PASSWORD` (and a matching `DATABASE_URL` password) must stay in the backend's
   environment — see the backend limitation above.

4. **Restart services:**

   ```bash
   podman compose -f docker-compose.prod.yml down
   podman compose -f docker-compose.prod.yml up -d
   ```

5. **Verify migration:**

   ```bash
   # Check secrets are accessible
   podman compose exec postgres cat /run/secrets/postgres_password

   # Verify application connectivity
   curl http://localhost:8000/api/system/health
   ```

---

## Security Best Practices

### File Permissions

```bash
# Directory: owner read/write/execute only
chmod 700 secrets/

# Files: owner read/write only
chmod 600 secrets/*.txt

# Verify permissions
ls -la secrets/
```

### Version Control

The `secrets/` directory is already in `.gitignore`. Verify it is never committed:

```bash
# Should show nothing
git status secrets/

# Verify .gitignore includes secrets/
grep secrets .gitignore
```

### Access Control

- Restrict file system access to the secrets directory
- Use SELinux/AppArmor for additional container hardening
- Only Docker daemon needs read access to secret files

### Backup Considerations

- Back up secret files securely (encrypted storage)
- Never store unencrypted secrets in version control
- Document which services use which secrets
- Consider using a secrets manager (Vault, AWS Secrets Manager) for larger deployments

### Encryption at Rest

Docker Secrets are **not encrypted at rest** in standalone Docker mode. Protect secrets by:

- Using full-disk encryption (LUKS, BitLocker)
- Restricting physical access to the host
- Using encrypted backup storage

---

## Troubleshooting

### Secret File Not Found

```
Error: ENOENT: no such file or directory, open 'secrets/postgres_password.txt'
```

**Solution:**

```bash
mkdir -p secrets
openssl rand -base64 32 > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt
```

### Permission Denied

```
Error: EACCES: permission denied, open 'secrets/postgres_password.txt'
```

**Solution:**

```bash
chmod 700 secrets/
chmod 600 secrets/*.txt
```

### Container Cannot Read Secret

```bash
# Verify secret is mounted
podman compose exec postgres ls -la /run/secrets/

# Check secret content
podman compose exec postgres cat /run/secrets/postgres_password
```

### Trailing Whitespace in Secret

Trailing newlines can cause authentication failures:

```bash
# Create secret without trailing newline
echo -n "password_here" > secrets/postgres_password.txt

# Or trim existing file
tr -d '\n' < secrets/postgres_password.txt > secrets/temp.txt
mv secrets/temp.txt secrets/postgres_password.txt
```

### Database Connection Fails After Migration

1. Verify the password in the secret file matches the database:

   ```bash
   podman compose exec postgres psql -U security -c "SELECT 1"
   ```

2. If password mismatch, update the database password:

   ```bash
   podman compose exec postgres psql -U postgres -c \
     "ALTER USER security PASSWORD '$(cat secrets/postgres_password.txt)'"
   ```

---

## See Also

- [Administration Guide](admin/README.md) - Comprehensive secrets and security guide
- [Redis Setup](redis.md) - Redis authentication configuration
- [Database Setup](database.md) - PostgreSQL configuration
- [Configuration Reference](../reference/config/env-reference.md) - All environment variables
