# Security

---

title: Security
source_refs:

- backend/core/config.py:api_key_enabled:209
- backend/core/config.py:admin_enabled:48
- backend/core/config.py:tls_mode:510
- backend/core/config.py:rate_limit_enabled:290
- backend/core/config.py:cors_origins:65

---

> **Security considerations for self-hosted deployments.** This system is designed for local/trusted network use. Additional hardening is required for exposed deployments.

<!-- Nano Banana Pro Prompt:
"Technical illustration of network security and server protection,
shields and lock icons, firewall visualization,
dark background #121212, NVIDIA green #76B900 accent,
clean minimalist style, vertical 2:3 aspect ratio,
no text overlays"
-->

## Security Model

Home Security Intelligence is designed as a **single-user, local deployment**:

- **No authentication by default** - Assumes trusted network
- **No cloud connectivity** - All processing is local
- **No internet exposure** - Designed for LAN access only

```mermaid
flowchart TB
    subgraph Trusted["Trusted Network (LAN)"]
        USER[User Browser]
        FE[Frontend]
        BE[Backend API]
        AI[AI Services]
        DB[(PostgreSQL)]
        RD[(Redis)]
    end

    subgraph Untrusted["Internet"]
        ATK[Potential Attackers]
    end

    USER --> FE
    FE --> BE
    BE --> AI
    BE --> DB
    BE --> RD

    ATK -.->|Blocked| FE

    style Trusted fill:#76B900,color:#fff
    style Untrusted fill:#E74856,color:#fff
    style ATK fill:#E74856,color:#fff
```

---

## Default Security Posture

| Feature         | Default        | Production Recommendation      |
| --------------- | -------------- | ------------------------------ |
| Authentication  | Disabled       | Enable for exposed deployments |
| HTTPS/TLS       | Disabled       | Enable for production          |
| Rate Limiting   | Enabled        | Keep enabled                   |
| Admin Endpoints | Disabled       | Keep disabled unless needed    |
| Debug Mode      | Disabled       | Keep disabled                  |
| CORS            | Localhost only | Restrict to your domains       |

---

## Default Credentials Warning

> **CRITICAL: Never use default database credentials in production.**

The `docker-compose.prod.yml` includes default PostgreSQL credentials for development convenience:

```yaml
# Default (INSECURE) credentials in docker-compose.prod.yml
POSTGRES_USER: security
POSTGRES_PASSWORD: security_dev_password
POSTGRES_DB: security
```

### Changing Database Credentials

**Before production deployment:**

1. **Create a secure password:**

   ```bash
   # Generate a 32-character random password
   openssl rand -base64 32
   ```

2. **Set credentials in .env file:**

   ```bash
   # .env (never commit this file)
   POSTGRES_USER=security
   POSTGRES_PASSWORD=your-secure-generated-password-here
   POSTGRES_DB=security
   ```

3. **Update DATABASE_URL if connecting directly:**

   ```bash
   DATABASE_URL=postgresql+asyncpg://security:your-secure-generated-password-here@postgres:5432/security
   ```

4. **Verify .env is in .gitignore:**

   ```bash
   grep "^\.env$" .gitignore || echo ".env" >> .gitignore
   ```

### Production Checklist Item

Add to your deployment checklist:

- [ ] Database password changed from default `security_dev_password`
- [ ] Credentials stored in `.env` file (not committed to git)
- [ ] `.env` file permissions restricted (`chmod 600 .env`)

---

## Authentication

### API Key Authentication

Enable API key authentication for protected access:

```bash
# .env
API_KEY_ENABLED=true
API_KEYS=["your-secure-api-key-here", "another-key-if-needed"]
```

**Source:** [`backend/core/config.py:209-216`](../../backend/core/config.py)

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

#### Generate Secure Keys

```bash
# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# OpenSSL
openssl rand -base64 32
```

---

### Admin Endpoint Security

Admin endpoints require **both** conditions:

1. `DEBUG=true`
2. `ADMIN_ENABLED=true`

**Source:** [`backend/core/config.py:48-58`](../../backend/core/config.py)

```bash
# Enable admin endpoints (development only)
DEBUG=true
ADMIN_ENABLED=true

# Optional: Require API key for admin endpoints
ADMIN_API_KEY=your-admin-api-key
```

**Warning:** Never enable admin endpoints in production without the `ADMIN_API_KEY` protection.

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

**Source:** [`backend/core/config.py:510-533`](../../backend/core/config.py)

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

For development or internal LAN deployments, generate self-signed certificates:

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

Then configure in `.env`:

```bash
TLS_MODE=provided
TLS_CERT_PATH=data/certs/server.crt
TLS_KEY_PATH=data/certs/server.key
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

```mermaid
flowchart TB
    subgraph Insecure["HTTP (Insecure)"]
        BE1[Backend] -->|Plain Text| AI1[AI Service]
        ATK1[Attacker] -.->|Can Intercept| BE1
    end

    subgraph Secure["HTTPS (Secure)"]
        BE2[Backend] -->|Encrypted| AI2[AI Service]
        ATK2[Attacker] -.->|Cannot Read| BE2
    end

    style Insecure fill:#E74856,color:#fff
    style Secure fill:#76B900,color:#fff
    style ATK1 fill:#E74856,color:#fff
    style ATK2 fill:#E74856,color:#fff
```

| Environment        | Protocol | Acceptable     |
| ------------------ | -------- | -------------- |
| Localhost dev      | HTTP     | Yes            |
| Docker network     | HTTP     | Yes (internal) |
| Cross-machine LAN  | HTTPS    | Required       |
| Remote AI services | HTTPS    | Required       |

```bash
# Production AI service URLs
RTDETR_URL=https://your-rtdetr-host:8090
NEMOTRON_URL=https://your-nemotron-host:8091
```

---

## Network Security

### Firewall Configuration

Only expose necessary ports:

| Port   | Service     | Exposure          |
| ------ | ----------- | ----------------- |
| 80/443 | Frontend    | User access       |
| 8000   | Backend API | User access       |
| 5432   | PostgreSQL  | **Internal only** |
| 6379   | Redis       | **Internal only** |
| 8090   | RT-DETRv2   | **Internal only** |
| 8091   | Nemotron    | **Internal only** |

```bash
# UFW example (Linux)
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
ufw deny 5432/tcp
ufw deny 6379/tcp
ufw enable
```

### Network Isolation

```mermaid
flowchart TB
    subgraph Public["Public Zone"]
        USER[Users]
    end

    subgraph DMZ["DMZ"]
        FE[Frontend<br/>:80/:443]
        BE[Backend API<br/>:8000]
    end

    subgraph Internal["Internal Zone"]
        DB[(PostgreSQL<br/>:5432)]
        RD[(Redis<br/>:6379)]
        AI[AI Services<br/>:8090/:8091]
    end

    USER --> FE
    USER --> BE
    FE --> BE
    BE --> DB
    BE --> RD
    BE --> AI

    style Public fill:#3B82F6,color:#fff
    style DMZ fill:#76B900,color:#fff
    style Internal fill:#A855F7,color:#fff
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
# .env (defaults shown)
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
RATE_LIMIT_MEDIA_REQUESTS_PER_MINUTE=120
RATE_LIMIT_WEBSOCKET_CONNECTIONS_PER_MINUTE=10
RATE_LIMIT_SEARCH_REQUESTS_PER_MINUTE=30
```

**Source:** [`backend/core/config.py:290-324`](../../backend/core/config.py)

### Rate Limit Tiers

| Endpoint Type             | Limit/min      | Burst | Purpose                     |
| ------------------------- | -------------- | ----- | --------------------------- |
| General API               | 60             | 10    | Normal operations           |
| Media (images/thumbnails) | 120            | -     | Higher for dashboards       |
| Search                    | 30             | -     | Lower (expensive operation) |
| WebSocket                 | 10 connections | -     | Prevent connection storms   |

---

## CORS Configuration

Restrict Cross-Origin Resource Sharing to trusted domains:

```bash
# Development
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173"]

# Production
CORS_ORIGINS=["https://your-domain.com"]
```

**Source:** [`backend/core/config.py:65-68`](../../backend/core/config.py)

**Warning:** Never use `["*"]` in production - allows any origin to make requests.

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

## No-Auth Implications

Without authentication enabled:

| Risk                              | Mitigation                       |
| --------------------------------- | -------------------------------- |
| Anyone on network can view events | Restrict network access          |
| Anyone can modify camera config   | Use API keys for production      |
| Anyone can clear DLQ              | Enable admin endpoint protection |
| Anyone can access media           | Use TLS + API keys               |

### Minimum Security for Exposed Deployments

If you must expose to the internet:

```bash
# .env
API_KEY_ENABLED=true
API_KEYS=["strong-random-key-here"]
TLS_MODE=provided
TLS_CERT_PATH=/path/to/cert.pem
TLS_KEY_PATH=/path/to/key.pem
DEBUG=false
ADMIN_ENABLED=false
```

Plus:

- Firewall rules
- Reverse proxy with additional auth (nginx, Traefik)
- VPN for remote access (recommended)

---

## Secrets Management

### Sensitive Variables

| Variable        | Contains          | Storage Recommendation       |
| --------------- | ----------------- | ---------------------------- |
| `DATABASE_URL`  | DB password       | .env file (not in git)       |
| `API_KEYS`      | API credentials   | .env file or secrets manager |
| `ADMIN_API_KEY` | Admin credential  | .env file or secrets manager |
| `SMTP_PASSWORD` | Email credentials | .env file or secrets manager |

### Best Practices

1. **Never commit `.env` to git**

   ```bash
   # .gitignore
   .env
   data/runtime.env
   ```

2. **Use different credentials per environment**

   - Development: weak passwords OK
   - Production: strong, unique passwords

3. **Rotate credentials periodically**

   - API keys: quarterly
   - Database passwords: annually

4. **Use secrets managers for production**
   - Docker secrets
   - HashiCorp Vault
   - Cloud provider secrets (AWS SSM, etc.)

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
- [ ] **Database password changed from default** (see [Default Credentials Warning](#default-credentials-warning))
- [ ] Strong, unique passwords for all services
- [ ] Firewall configured
- [ ] Database not exposed
- [ ] Redis not exposed
- [ ] AI services not exposed
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
   # Python dependencies
   pip install --upgrade -r requirements.txt

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

- [Configuration](configuration.md) - Security-related settings
- [Troubleshooting](troubleshooting.md) - Security error resolution
- [Monitoring](monitoring.md) - Security monitoring
