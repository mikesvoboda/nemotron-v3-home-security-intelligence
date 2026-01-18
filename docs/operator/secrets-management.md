# Secrets Management

> Secure credential storage using Docker Secrets for production deployments.

This guide covers Docker Secrets configuration for Home Security Intelligence. For comprehensive implementation details, see [Administration Guide](admin/).

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

| Secret                 | File                         | Service                        | Purpose                 |
| ---------------------- | ---------------------------- | ------------------------------ | ----------------------- |
| PostgreSQL password    | `postgres_password.txt`      | postgres, backend              | Database authentication |
| Redis password         | `redis_password.txt`         | redis, backend, redis-exporter | Cache authentication    |
| Grafana admin password | `grafana_admin_password.txt` | grafana                        | Dashboard admin access  |

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

Alternatively, use the interactive setup script:

```bash
./setup.sh --guided
# Select "y" when prompted to create Docker secrets files
```

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

```yaml
backend:
  secrets:
    - postgres_password
    - redis_password
  environment:
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    - REDIS_PASSWORD_FILE=/run/secrets/redis_password
```

**Grafana (monitoring profile):**

```yaml
grafana:
  secrets:
    - grafana_admin_password
  environment:
    - GF_SECURITY_ADMIN_PASSWORD_FILE=/run/secrets/grafana_admin_password
```

### 4. Validate and Deploy

```bash
# Validate configuration
docker compose -f docker-compose.prod.yml config

# Start services
docker compose -f docker-compose.prod.yml up -d

# Verify secrets are mounted
docker compose -f docker-compose.prod.yml exec postgres ls -la /run/secrets/
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
   docker compose -f docker-compose.prod.yml restart postgres
   ```

3. **Restart dependent services:**

   ```bash
   docker compose -f docker-compose.prod.yml restart backend
   ```

4. **Verify the change:**

   ```bash
   docker compose -f docker-compose.prod.yml logs postgres | tail -20
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

### Backend Application

The backend can read secrets from files when `_FILE` environment variables are set:

```python
from pathlib import Path
import os

def get_secret(secret_name: str, env_var: str) -> str:
    """Read secret from Docker secret file or environment variable."""
    # Check for _FILE variant first
    file_path = Path(f'/run/secrets/{secret_name}')
    if file_path.exists():
        return file_path.read_text().strip()

    # Fall back to environment variable
    return os.getenv(env_var, '')

# Usage
postgres_password = get_secret('postgres_password', 'POSTGRES_PASSWORD')
redis_password = get_secret('redis_password', 'REDIS_PASSWORD')
```

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

### Grafana (Native Support)

Grafana supports `_FILE` suffix for environment variables:

```yaml
environment:
  - GF_SECURITY_ADMIN_PASSWORD_FILE=/run/secrets/grafana_admin_password
```

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

3. **Remove credentials from .env:**

   ```bash
   # Remove these lines from .env
   # POSTGRES_PASSWORD=...
   # REDIS_PASSWORD=...
   # GF_ADMIN_PASSWORD=...
   ```

4. **Restart services:**

   ```bash
   docker compose -f docker-compose.prod.yml down
   docker compose -f docker-compose.prod.yml up -d
   ```

5. **Verify migration:**

   ```bash
   # Check secrets are accessible
   docker compose exec postgres cat /run/secrets/postgres_password

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
docker compose exec postgres ls -la /run/secrets/

# Check secret content
docker compose exec postgres cat /run/secrets/postgres_password
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
   docker compose exec postgres psql -U security -c "SELECT 1"
   ```

2. If password mismatch, update the database password:

   ```bash
   docker compose exec postgres psql -U postgres -c \
     "ALTER USER security PASSWORD '$(cat secrets/postgres_password.txt)'"
   ```

---

## See Also

- [Administration Guide](admin/) - Comprehensive secrets and security guide
- [Redis Setup](redis.md) - Redis authentication configuration
- [Database Setup](database.md) - PostgreSQL configuration
- [Configuration Reference](../admin-guide/configuration.md) - All environment variables
