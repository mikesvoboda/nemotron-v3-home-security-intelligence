# Docker Secrets Management Guide

## Overview

Docker Secrets provide enhanced security for credential management in Docker Compose. Instead of storing sensitive credentials in environment variables, secrets are stored separately in files with restricted permissions and injected into containers at runtime.

## Key Benefits

- **Separation of Concerns**: Credentials stored separately from environment variables
- **Visibility Control**: Secrets not visible in `docker inspect` output
- **Ease of Rotation**: Update credentials without rebuilding images
- **File Permissions**: Secrets files have restrictive permissions (600)
- **Read-Only Access**: Mounted read-only in containers at `/run/secrets/`

## Quick Start

### 1. Create Secrets Directory and Files

```bash
# Create secrets directory with secure permissions
mkdir -p secrets
chmod 700 secrets

# Generate strong passwords
openssl rand -base64 32 > secrets/postgres_password.txt
openssl rand -base64 32 > secrets/redis_password.txt
openssl rand -base64 32 > secrets/grafana_admin_password.txt

# Ensure files have restrictive permissions
chmod 600 secrets/*.txt
```

### 2. Using setup.sh to Create Secrets Automatically

The interactive setup script can create secrets files for you:

```bash
# Quick mode (non-interactive)
./setup.sh

# Guided mode with explanations
./setup.sh --guided

# Then when prompted, select "y" to create Docker secrets files
```

This will create:

- `secrets/postgres_password.txt` - Database authentication
- `secrets/redis_password.txt` - Redis authentication (optional)
- `secrets/grafana_admin_password.txt` - Grafana dashboard (optional)

### 3. Enable Secrets in docker-compose.prod.yml

Uncomment the Docker Secrets section at the bottom of `docker-compose.prod.yml`:

```yaml
# At the bottom of docker-compose.prod.yml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  redis_password:
    file: ./secrets/redis_password.txt
  grafana_admin_password:
    file: ./secrets/grafana_admin_password.txt
```

Then uncomment the `secrets:` subsections in each service:

**PostgreSQL Service:**

```yaml
postgres:
  # ... existing configuration ...
  secrets:
    - postgres_password
  environment:
    - POSTGRES_USER=${POSTGRES_USER:-security}
    - POSTGRES_DB=${POSTGRES_DB:-security}
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

**Redis Service:**

```yaml
redis:
  # ... existing configuration ...
  secrets:
    - redis_password
  environment:
    - REDIS_PASSWORD_FILE=/run/secrets/redis_password
  # Note: Update the command to read from _FILE
  command: >-
    sh -c '
    if [ -f /run/secrets/redis_password ]; then
      REDIS_PASSWORD=$(cat /run/secrets/redis_password)
      echo "Starting Redis with password authentication"
      redis-server --appendonly yes --appendfsync everysec --requirepass "$REDIS_PASSWORD"
    else
      echo "Starting Redis without authentication (development mode)"
      redis-server --appendonly yes --appendfsync everysec
    fi
    '
```

**Backend Service:**

```yaml
backend:
  # ... existing configuration ...
  secrets:
    - postgres_password
    - redis_password
  environment:
    # For DATABASE_URL, you'll need to construct it in an entrypoint script
    # Or pass the password via environment variable from the secret file
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
    - REDIS_PASSWORD_FILE=/run/secrets/redis_password
```

### 4. Validate Configuration

After making changes, validate the docker-compose file:

```bash
docker compose -f docker-compose.prod.yml config
```

If secrets files are missing, you'll see helpful error messages indicating which files need to be created.

### 5. Start Services with Secrets

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 6. Verify Secrets Are Mounted

```bash
# Check that secrets are mounted in containers
docker compose -f docker-compose.prod.yml exec postgres ls -la /run/secrets/
docker compose -f docker-compose.prod.yml exec redis ls -la /run/secrets/
```

## Using Secrets in Containers

### For PostgreSQL

PostgreSQL has native support for `POSTGRES_PASSWORD_FILE`:

```yaml
postgres:
  environment:
    - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
```

### For Redis

Redis doesn't have a `_FILE` variant, so you need to read the file in the startup command:

```yaml
redis:
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

### For Backend Application

If your backend application needs credentials, you have two options:

**Option 1: Read secrets in application code**

```python
# In your application startup
import os
from pathlib import Path

def get_postgres_password():
    """Read password from Docker secret or environment variable."""
    secret_file = Path('/run/secrets/postgres_password')  # pragma: allowlist secret
    if secret_file.exists():
        return secret_file.read_text().strip()
    return os.getenv('POSTGRES_PASSWORD', '')

password = get_postgres_password()
# Construct DATABASE_URL using the password read from secret
db_host = os.getenv('DATABASE_HOST', 'postgres')
db_user = os.getenv('POSTGRES_USER', 'security')
db_name = os.getenv('POSTGRES_DB', 'security')
DATABASE_URL = f'postgresql://{db_user}:{password}@{db_host}:5432/{db_name}'
```

**Option 2: Use init container to write secrets to environment**

```yaml
backend:
  # Read secret and write to temp env file
  command: >-
    sh -c '
    cat /run/secrets/postgres_password > /tmp/pg_password.txt &&
    cat /run/secrets/redis_password > /tmp/redis_password.txt &&
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
    '
```

### For Grafana

Grafana supports environment variables with `_FILE` suffix:

```yaml
grafana:
  environment:
    - GF_SECURITY_ADMIN_PASSWORD_FILE=/run/secrets/grafana_admin_password
```

Alternatively, read the file in a startup script and set the environment variable.

## Secret Rotation Procedure

### Zero-Downtime Rotation

Update credentials without restarting all services:

1. **Update the secret file:**

   ```bash
   echo "new_postgres_password" > secrets/postgres_password.txt
   chmod 600 secrets/postgres_password.txt
   ```

2. **Restart the affected service:**

   ```bash
   docker compose -f docker-compose.prod.yml restart postgres
   ```

3. **Restart dependent services:**

   ```bash
   docker compose -f docker-compose.prod.yml restart backend redis-exporter
   ```

4. **Verify the change:**
   ```bash
   docker compose -f docker-compose.prod.yml logs postgres | tail -20
   ```

## Comparing Environment Variables vs Secrets

### Environment Variables (Current Default)

**Pros:**

- Simple setup
- Works everywhere
- Good for development

**Cons:**

- Visible in `docker inspect`
- Visible in process listing
- Harder to rotate without rebuild
- All credentials in `.env` file

### Docker Secrets

**Pros:**

- Not visible in `docker inspect`
- Mounted read-only with 600 permissions
- Easy credential rotation
- Better security posture
- Credentials not in `.env`

**Cons:**

- Requires explicit implementation per service
- Some applications don't support `_FILE` variables
- Not encrypted at rest (use full-disk encryption)
- Requires uncommenting sections

## Security Best Practices

1. **File Permissions**

   ```bash
   # Ensure correct permissions
   chmod 700 secrets/           # Directory: rwx------
   chmod 600 secrets/*.txt      # Files: rw-------
   ```

2. **Version Control**

   ```bash
   # Never commit secrets to git
   # .gitignore already includes secrets/
   git status secrets/          # Should show nothing
   ```

3. **Backups**

   - Back up secret files securely
   - Use encrypted storage for backups
   - Don't store unencrypted secrets in version control

4. **Access Control**

   - Only Docker can read secret files
   - Restrict file system access to `/home/user/secrets/`
   - Use SELinux/AppArmor for additional hardening

5. **Rotation Schedule**

   - Rotate credentials every 90 days
   - Immediately rotate if compromised
   - Document rotation procedures
   - Automate with scheduled scripts

6. **Encryption at Rest**
   - Use full-disk encryption on host system
   - Consider encrypted filesystems (LUKS)
   - Use encrypted backup storage

## Troubleshooting

### Error: Secret file not found

```
Error: ENOENT: no such file or directory, open 'secrets/postgres_password.txt'
```

**Solution:**

```bash
mkdir -p secrets
echo "your_password" > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt
```

### Error: Permission denied on secret file

```
Error: EACCES: permission denied, open 'secrets/postgres_password.txt'
```

**Solution:**

```bash
# Fix file permissions
chmod 600 secrets/postgres_password.txt
chmod 700 secrets/
```

### Secret file contains extra whitespace

```bash
# Remove trailing newlines when creating secrets
echo -n "password_without_newline" > secrets/postgres_password.txt

# Or use cat to trim
echo "password" | tr -d '\n' > secrets/postgres_password.txt
```

### Container can't read secret

```bash
# Verify secret is mounted
docker exec container_name cat /run/secrets/secret_name

# Check file permissions inside container
docker exec container_name ls -la /run/secrets/
```

## Hybrid Approach

You can use both environment variables and secrets:

- **Required credentials** (POSTGRES_PASSWORD): Use secrets
- **Optional/development** (REDIS_PASSWORD): Use environment variables
- **Configuration values** (RTDETR_CONFIDENCE): Use environment variables

Example:

```yaml
postgres:
  secrets:
    - postgres_password
  environment:
    POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

redis:
  # Optional: Use environment variable if not using secrets
  environment:
    REDIS_PASSWORD: ${REDIS_PASSWORD:-}
```

## Implementation Checklist

For each sensitive credential, follow this checklist:

- [ ] Identify all sensitive credentials
- [ ] Create secret files in `secrets/` directory
- [ ] Set proper file permissions (600)
- [ ] Add secrets section to docker-compose.prod.yml
- [ ] Add secrets reference to service definition
- [ ] Update service environment or startup script
- [ ] Test with `docker compose config`
- [ ] Verify with `docker exec ... cat /run/secrets/...`
- [ ] Document rotation procedure
- [ ] Update deployment scripts
- [ ] Train team on secret management

## References

- [Docker Compose Secrets Documentation](https://docs.docker.com/compose/compose-file/compose-file-v3/#secrets)
- [Docker Swarm Secrets](https://docs.docker.com/engine/swarm/secrets/)
- [PostgreSQL Password File](https://www.postgresql.org/docs/current/libpq-pgpass.html)
- [Redis ACL](https://redis.io/topics/acl)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
