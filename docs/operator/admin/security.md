# Security Guide

> Security considerations for self-hosted deployments. This system is designed for local/trusted network use. Additional hardening is required for exposed deployments.

---

## Security Model

Home Security Intelligence is designed as a **single-user, local deployment**:

- **First-time admin registration required** - `SetupGuardMiddleware` returns 503 on the
  API until the first user is created. After registration the API is open (no per-request
  login) — the `127.0.0.1` service bindings are the primary security boundary. The global
  `AuthMiddleware` class exists for future multi-user support but is not active.
- **Per-route guards for sensitive operations** - the `/api/admin/*` seeding, cache-clearing
  and cleanup routes sit behind `require_admin_access`, which gates on `ADMIN_ENABLED` alone
  (default `true`). `DEBUG` is not consulted, and `ADMIN_API_KEY` is reserved and not
  enforced — no code path reads it and no `X-Admin-API-Key` header is validated — so the
  `127.0.0.1` bind is what actually protects them. The `verify_api_key` guard
  (`API_KEY_ENABLED`) protects the DLQ and inbound-webhook routes, not the admin ones. The
  `/api/admin/users` CRUD endpoints are a separate case: they require an authenticated admin
  session (`get_current_admin_user`).
- **No cloud connectivity** - All processing is local
- **No internet exposure** - Designed for LAN access only

---

## Default Security Posture

| Feature         | Default                                                               | Production Recommendation                                  |
| --------------- | --------------------------------------------------------------------- | ---------------------------------------------------------- |
| API auth        | Open after first admin registers; `API_KEY_ENABLED=false`             | Enable API keys if exposed                                 |
| HTTPS/TLS       | Disabled (`TLS_MODE=disabled`)                                        | Enable for production                                      |
| Rate Limiting   | Enabled                                                               | Keep enabled                                               |
| Admin Endpoints | `ADMIN_ENABLED=true` alone (default true); DEBUG irrelevant           | Keep off non-loopback interfaces, or `ADMIN_ENABLED=false` |
| Debug Mode      | Disabled                                                              | Keep disabled                                              |
| CORS            | `https://{localhost,127.0.0.1,0.0.0.0}:8444` + `http://frontend:8080` | Restrict to your domains                                   |

---

## Database Credentials (REQUIRED)

> **SECURITY: Database password is REQUIRED. No default passwords exist.**

As of the latest security update, **all default passwords have been removed** from docker-compose files. The system will **fail to start** if `POSTGRES_PASSWORD` is not set, preventing accidental deployment with insecure credentials.

```yaml
# docker-compose.prod.yml - password is REQUIRED
environment:
  - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}
```

### Setting Up Database Credentials

**Option 1: Interactive Setup (Recommended)**

The setup script generates secure passwords automatically (there is no `setup.sh`):

```bash
python setup.py              # Quick mode - generates secure password
python setup.py --guided     # Guided mode - explains each step
```

**Option 2: Manual .env File**

1. **Generate a secure password:**

   ```bash
   # Generate a 32-character random password
   openssl rand -base64 32
   ```

2. **Create .env file:**

   ```bash
   # .env (never commit this file)
   POSTGRES_USER=security
   POSTGRES_PASSWORD=your-secure-generated-password-here
   POSTGRES_DB=security
   DATABASE_URL=postgresql+asyncpg://security:your-secure-generated-password-here@postgres:5432/security  # pragma: allowlist secret
   ```

3. **Set secure file permissions:**

   ```bash
   chmod 600 .env
   ```

**Option 3: Docker Secrets (Enhanced Security)**

For production deployments, Docker secrets provide better security than environment variables:

```bash
# Create secrets directory
mkdir -p secrets

# Generate and store password
openssl rand -base64 32 > secrets/postgres_password.txt

# Set secure permissions
chmod 600 secrets/postgres_password.txt
```

Then uncomment the secrets sections in `docker-compose.prod.yml`:

```yaml
services:
  postgres:
    secrets:
      - postgres_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

### Password Requirements

The setup script enforces these security guidelines:

| Requirement        | Value           | Reason                       |
| ------------------ | --------------- | ---------------------------- |
| Minimum length     | 16 characters   | Prevents brute force attacks |
| Recommended length | 32 characters   | Industry best practice       |
| Character set      | URL-safe base64 | Avoids shell escaping issues |

**Weak passwords that trigger warnings:**

- `security_dev_password` (old default - removed)
- `password`, `admin`, `root`, `secret`
- Any password under 16 characters

---

## Authentication

### API Key Authentication

Enable API key authentication for protected access:

```bash
# .env
API_KEY_ENABLED=true
API_KEYS=["your-secure-api-key-here", "another-key-if-needed"]
```

#### Making Authenticated Requests

```bash
# Include X-API-Key header
curl -H "X-API-Key: your-secure-api-key-here" \
  http://localhost:8000/api/events
```

#### Key Requirements

- Use cryptographically secure random strings (32+ characters)
- Store keys securely (don't commit to git)
- Rotate keys periodically
- Keys are hashed on startup
- **Always use header-based authentication** (`X-API-Key` header) instead of query parameters

> **Security Warning:** Avoid passing API keys in URL query parameters (`?api_key=...`). Query parameters are logged in server access logs, stored in browser history, and exposed in HTTP Referer headers.

#### Generate Secure Keys

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

---

### Admin Endpoint Security

Admin endpoints are gated by **one** condition:

1. `ADMIN_ENABLED=true` (the default — `DEBUG` is not consulted)

```bash
# Admin endpoints are enabled by default; this is the only switch
ADMIN_ENABLED=true

# Reserved — NOT enforced: no code path reads ADMIN_API_KEY and no
# X-Admin-API-Key header is validated. Setting it changes nothing.
# ADMIN_API_KEY=your-admin-api-key
```

**Warning:** `ADMIN_API_KEY` enforces nothing, so there is no key-based protection to fall
back on. Admin exposure is controlled by setting `ADMIN_ENABLED=false` or by keeping the
service bound to `127.0.0.1` / a trusted network.

---

## TLS/HTTPS

### Why TLS Matters

Without TLS:

- Credentials sent in plaintext
- Camera images can be intercepted
- API responses can be modified (MITM attacks)

### TLS Configuration Modes

| Mode          | Use Case         | Certificate Source |
| ------------- | ---------------- | ------------------ |
| `disabled`    | Development only | None               |
| `self_signed` | LAN/internal use | Auto-generated     |
| `provided`    | Production       | Your certificates  |

### Self-Signed Certificates (LAN)

```bash
# .env
TLS_MODE=self_signed
TLS_CERT_DIR=data/certs

# Certificates will be auto-generated on first start
```

**Note:** Browsers will show security warnings for self-signed certificates. Add exceptions for LAN access.

### Production Certificates

```bash
# .env
TLS_MODE=provided
TLS_CERT_PATH=/etc/ssl/certs/server.crt
TLS_KEY_PATH=/etc/ssl/private/server.key
TLS_MIN_VERSION=TLSv1.2
```

#### Certificate Sources

- **Let's Encrypt** - Free, automated (requires public domain)
- **Internal CA** - For enterprise deployments
- **Purchased** - From certificate authorities

### mTLS (Mutual TLS)

For high-security deployments, require client certificates:

```bash
TLS_VERIFY_CLIENT=true
TLS_CA_PATH=/path/to/ca.crt
```

### Generating Self-Signed Certificates

For development or internal LAN deployments:

```bash
# Create certificate directory
mkdir -p data/certs
cd data/certs

# Generate private key
openssl genrsa -out server.key 2048

# Generate self-signed certificate (valid for 365 days)
openssl req -new -x509 -key server.key -out server.crt -days 365 \
  -subj "/CN=home-security-intelligence/O=Local Development"

# Set proper permissions
chmod 600 server.key
chmod 644 server.crt
```

### Let's Encrypt Certificates

For internet-facing deployments with a domain name:

```bash
# Install certbot
sudo apt install certbot  # Debian/Ubuntu
sudo dnf install certbot  # Fedora/RHEL

# Generate certificate (requires port 80 accessible)
sudo certbot certonly --standalone -d yourdomain.com

# Certificates are stored in:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

Configure in `.env`:

```bash
TLS_MODE=provided
TLS_CERT_PATH=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
TLS_KEY_PATH=/etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### TLS Configuration Reference

| Variable            | Default      | Description                                |
| ------------------- | ------------ | ------------------------------------------ |
| `TLS_MODE`          | `disabled`   | `disabled`, `self_signed`, or `provided`   |
| `TLS_CERT_PATH`     | _none_       | Path to TLS certificate file               |
| `TLS_KEY_PATH`      | _none_       | Path to TLS private key file               |
| `TLS_CA_PATH`       | _none_       | Path to CA certificate (for mTLS)          |
| `TLS_VERIFY_CLIENT` | `false`      | Enable client certificate verification     |
| `TLS_MIN_VERSION`   | `TLSv1.2`    | Minimum TLS version (`TLSv1.2`, `TLSv1.3`) |
| `TLS_CERT_DIR`      | `data/certs` | Directory for auto-generated certs         |

---

## AI Service Security

### HTTPS for AI Services

**Critical:** AI service URLs use HTTP by default, which is vulnerable to MITM attacks.

| Environment        | Protocol | Acceptable     |
| ------------------ | -------- | -------------- |
| Localhost dev      | HTTP     | Yes            |
| Docker network     | HTTP     | Yes (internal) |
| Cross-machine LAN  | HTTPS    | Required       |
| Remote AI services | HTTPS    | Required       |

```bash
# Production AI service URLs — terminate TLS at a proxy (the AI containers
# themselves serve plain HTTP; see ../ai-tls.md)
USE_AI_GATEWAY=true
AI_GATEWAY_URL=https://your-ai-host
YOLO26_URL=https://your-ai-host/yolo26
NEMOTRON_URL=https://your-ai-host
```

> [!IMPORTANT]
> The backend's AI clients (`httpx.AsyncClient` with default verification) have **no**
> custom-CA setting — `AI_VERIFY_SSL` / `AI_CA_CERT_PATH` do not exist. An `https://` AI
> URL only works when the certificate chains to the OS trust store inside the backend
> container.

---

## Network Security

### Firewall Configuration

Only expose necessary ports:

| Port        | Service                 | Exposure                                   |
| ----------- | ----------------------- | ------------------------------------------ |
| 8080 (HTTP) | Frontend                | Published `0.0.0.0` — user access          |
| 8444 (TLS)  | Frontend + `/grafana/`  | Published `0.0.0.0` — user access          |
| 8000        | Backend API             | Bound `127.0.0.1:${API_PORT}` — host-local |
| 5432        | PostgreSQL              | Bound `127.0.0.1` — **internal only**      |
| 6379        | Redis                   | Bound `127.0.0.1` — **internal only**      |
| 8090        | ai-gateway (YOLO26 etc) | Bound `127.0.0.1` — **internal only**      |
| 8091        | ai-llm (Nemotron)       | Bound `127.0.0.1` — **internal only**      |

Most host bindings are already `127.0.0.1` (the compose files bind them that way), so the
firewall mainly needs to allow the frontend ports for LAN users:

```bash
# UFW example (Linux)
ufw allow from 192.168.1.0/24 to any port 8080 proto tcp
ufw allow from 192.168.1.0/24 to any port 8444 proto tcp
ufw enable
```

### Docker Network Security

Use internal networks for sensitive services:

```yaml
# docker-compose.yml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true # No external access

services:
  frontend:
    networks:
      - frontend
  backend:
    networks:
      - frontend
      - backend
  postgres:
    networks:
      - backend # Internal only
  redis:
    networks:
      - backend # Internal only
```

---

## Rate Limiting

Rate limiting is enabled by default to prevent abuse:

```bash
# .env (defaults from backend/core/config.py shown)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE=120
RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE=100
RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE=30
RATE_LIMIT_EXPORT_REQUESTS_PER_MINUTE=10
```

### Rate Limit Tiers

| Endpoint Type             | Limit/min       | Burst | Purpose                      |
| ------------------------- | --------------- | ----- | ---------------------------- |
| General API               | 60              | 10    | Normal operations            |
| Media (images/thumbnails) | 120             | -     | Higher for dashboards        |
| Search                    | 30              | -     | Lower (expensive operation)  |
| CSV export                | 10              | -     | Limit bulk data exfiltration |
| WebSocket                 | 100 connections | -     | Prevent connection storms    |

---

## CORS Configuration

Restrict Cross-Origin Resource Sharing to trusted domains:

```bash
# Development
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Production
CORS_ORIGINS=["https://your-domain.com"]
```

**Warning:** Never use `["*"]` in production - allows any origin to make requests.

---

## Metrics Endpoint Security

The `/api/metrics` endpoint exposes Prometheus-format metrics and is **intentionally unauthenticated** to allow Prometheus scraping. This is a security consideration.

### Information Disclosed

| Metric Type               | Exposed Information                         | Risk Level |
| ------------------------- | ------------------------------------------- | ---------- |
| Queue depths              | System load patterns                        | Low        |
| Error counts              | Failure patterns, potential vulnerabilities | Medium     |
| AI request durations      | Service performance characteristics         | Low        |
| Detection counts by class | Activity patterns (when people detected)    | Medium     |
| Events by camera          | Camera names, activity patterns             | Medium     |

### Hardening Recommendations

1. **Network-Level IP Allowlisting (Recommended)**

   ```nginx
   # nginx.conf
   location /api/metrics {
       allow 10.0.0.50;      # Prometheus server IP
       allow 127.0.0.1;      # Localhost
       allow 172.16.0.0/12;  # Docker internal network
       deny all;
       proxy_pass http://backend:8000;
   }
   ```

2. **Basic Auth via Reverse Proxy**

   ```nginx
   location /api/metrics {
       auth_basic "Metrics";
       auth_basic_user_file /etc/nginx/.htpasswd;
       proxy_pass http://backend:8000;
   }
   ```

3. **Rate Limiting for Metrics**

   Be careful not to set limits too low - Prometheus typically scrapes every 10-30 seconds.

See [Prometheus Alerting](../prometheus-alerting.md) for full monitoring configuration.

---

## Path Traversal Protection

Media endpoints include path traversal protection:

```python
# Blocks attempts like:
# /api/media/cameras/../../../etc/passwd
# /api/media/thumbnails/../../sensitive.txt
```

The backend validates all file paths are within expected directories.

---

## Secrets Management

### Sensitive Variables

| Variable            | Contains               | Storage Recommendation                 |
| ------------------- | ---------------------- | -------------------------------------- |
| `POSTGRES_PASSWORD` | DB password            | .env file or Docker secrets (REQUIRED) |
| `DATABASE_URL`      | DB connection          | .env file (includes password)          |
| `API_KEYS`          | API credentials        | .env file or secrets manager           |
| `ADMIN_API_KEY`     | Reserved, not enforced | .env file or secrets manager           |
| `SMTP_PASSWORD`     | Email credentials      | .env file or secrets manager           |

### Docker Secrets (Recommended for Production)

This project supports Docker secrets for enhanced credential security:

```bash
# Create secrets with the setup script
python setup.py --create-secrets

# Or manually:
mkdir -p secrets
openssl rand -base64 32 > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt
```

Docker secrets advantages over environment variables:

- Not visible in `docker inspect` output
- Not exposed in container process listings
- Stored in RAM-backed tmpfs at `/run/secrets/`
- Automatically cleaned up when container stops

### Best Practices

1. **Never commit secrets to git**

   ```bash
   # .gitignore (already configured)
   .env
   secrets/*
   !secrets/.gitkeep
   ```

2. **Use different credentials per environment**

   - Development: auto-generated passwords from `./setup.sh`
   - Production: Docker secrets or external secrets manager

3. **Rotate credentials periodically**

   - API keys: quarterly
   - Database passwords: annually
   - After any suspected compromise: immediately

4. **Use secrets managers for production**

   - Docker secrets (built-in support)
   - HashiCorp Vault
   - Cloud provider secrets (AWS SSM, GCP Secret Manager, etc.)

5. **Verify file permissions**

   ```bash
   # .env should be owner-only
   ls -la .env
   # Expected: -rw------- (600)

   # secrets/ files should be owner-only
   ls -la secrets/
   # Expected: -rw------- (600) for each file
   ```

---

## Logging Security

### Sensitive Data in Logs

The logging system sanitizes sensitive data:

- Passwords are masked
- API keys are truncated
- Personal data is redacted

### Log Retention

```bash
# Shorter retention for sensitive environments
LOG_RETENTION_DAYS=7
LOG_FILE_BACKUP_COUNT=3
```

### Log Access

Restrict access to log files:

```bash
chmod 600 data/logs/security.log
chown app:app data/logs/
```

---

## Security Checklist

### Development

- [ ] Debug mode can be enabled
- [ ] Self-signed certs acceptable
- [ ] Default passwords acceptable
- [ ] CORS allows localhost

### Staging/Testing

- [ ] TLS enabled (self-signed OK)
- [ ] API keys enabled
- [ ] Strong passwords used
- [ ] Rate limiting enabled
- [ ] CORS restricted

### Production

- [ ] `DEBUG=false`
- [ ] `ADMIN_ENABLED=false`
- [ ] TLS with valid certificates
- [ ] API keys required
- [ ] **POSTGRES_PASSWORD set** (required)
- [ ] Strong, unique passwords for all services (32+ characters recommended)
- [ ] `.env` file permissions are `600` (owner read/write only)
- [ ] Docker secrets used for enhanced security (optional)
- [ ] Firewall configured
- [ ] Database not exposed externally
- [ ] Redis not exposed externally
- [ ] AI services not exposed externally
- [ ] CORS restricted to your domain
- [ ] Log retention configured
- [ ] Backups encrypted

---

## Security Updates

### Keeping Current

1. **Monitor dependencies:**

   ```bash
   # Python
   pip-audit

   # Node
   npm audit
   ```

2. **Update regularly:**

   ```bash
   # Python dependencies (using uv)
   uv sync --extra dev --upgrade

   # Node dependencies
   cd frontend && npm update
   ```

3. **Subscribe to security advisories:**
   - FastAPI: GitHub security advisories
   - React: npm security advisories
   - PostgreSQL: postgresql.org/support/security

---

## Incident Response

### If Compromised

1. **Isolate:** Disconnect from network
2. **Preserve:** Save logs before rotation
3. **Investigate:** Check access logs and audit trail
4. **Rotate:** Change all credentials
5. **Patch:** Apply security updates
6. **Monitor:** Watch for continued attacks

### Audit Trail

Review logs for suspicious activity:

```bash
# Failed authentication attempts
grep "authentication failed" data/logs/security.log

# Unusual API access patterns
grep "rate limit exceeded" data/logs/security.log

# Admin endpoint access
grep "admin" data/logs/security.log
```

---

## See Also

- [Environment Variable Reference](../../reference/config/env-reference.md) - All configuration options
- [Secrets Management](../secrets-management.md) - Detailed secrets guide
- [API Keys](api-keys.md) - API key management
- [Troubleshooting](../../reference/troubleshooting/index.md) - Common issues
- [Monitoring](../monitoring.md) - Security monitoring
- [Prometheus Alerting](../prometheus-alerting.md) - Alert configuration
