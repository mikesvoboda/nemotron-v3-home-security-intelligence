---
title: SSL/HTTPS Configuration
source_refs:
  - frontend/nginx.conf:1
  - frontend/docker-entrypoint.sh:1
  - docker-compose.prod.yml:350
  - scripts/generate-ssl-cert.sh:1
---

# SSL/HTTPS Configuration

This guide covers enabling HTTPS for the frontend nginx server, including certificate generation, configuration options, and deployment considerations.

## Overview

The frontend nginx server supports both HTTP and HTTPS modes:

- **HTTPS mode (default):** SSL is enabled by default with auto-generated self-signed certificates
- **HTTP mode:** Can be used by setting `SSL_ENABLED=false`

HTTPS is conditionally enabled at container startup based on environment variables and certificate availability. When `SSL_ENABLED=true` (the default), nginx will auto-generate a self-signed certificate if none is provided.

## Quick Start (Development)

Generate a self-signed certificate and enable HTTPS:

```bash
# Generate self-signed certificate
./scripts/generate-ssl-cert.sh

# Enable HTTPS in .env
echo "SSL_ENABLED=true" >> .env

# Restart frontend container
docker compose -f docker-compose.prod.yml restart frontend
```

Access the application at `https://localhost:443` (or your configured HTTPS port).

## Configuration

### Environment Variables

| Variable              | Default                     | Description                                    |
| --------------------- | --------------------------- | ---------------------------------------------- |
| `SSL_ENABLED`         | `true`                      | Enable/disable HTTPS server (default: enabled) |
| `SSL_CERT_DIR`        | `./certs`                   | Host directory containing certificates         |
| `SSL_CERT_PATH`       | `/etc/nginx/certs/cert.pem` | Container path to certificate                  |
| `SSL_KEY_PATH`        | `/etc/nginx/certs/key.pem`  | Container path to private key                  |
| `FRONTEND_PORT`       | `5173`                      | HTTP port mapping (host:8080)                  |
| `FRONTEND_HTTPS_PORT` | `8443`                      | HTTPS port mapping (host:8443)                 |

> **Note:** The default HTTPS port is 8443 (not 443) to avoid requiring root/sudo privileges. Non-root users cannot bind to ports below 1024.

### Example .env Configuration

```bash
# Enable HTTPS
SSL_ENABLED=true

# Custom certificate directory
SSL_CERT_DIR=/path/to/certificates

# Custom ports (optional)
FRONTEND_PORT=80
FRONTEND_HTTPS_PORT=443
```

## Certificate Options

### Option 1: Self-Signed Certificate (Development)

Use the provided script to generate a self-signed certificate:

```bash
# Default output to ./certs directory
./scripts/generate-ssl-cert.sh

# Custom output directory
./scripts/generate-ssl-cert.sh /path/to/certs
```

The script generates:

- `cert.pem` - Self-signed certificate (valid 365 days)
- `key.pem` - 4096-bit RSA private key
- `cert.csr` - Certificate signing request (for reference)

**Certificate details:**

- Key size: 4096 bits
- Validity: 365 days
- SANs: localhost, \*.localhost, 127.0.0.1, ::1
- Protocols: TLS 1.2, TLS 1.3

**Browser warning:** Self-signed certificates will trigger browser security warnings. Accept the warning for development purposes.

### Option 2: Let's Encrypt (Production)

For public-facing deployments, use Let's Encrypt for free, trusted certificates:

```bash
# Using certbot
sudo certbot certonly --standalone -d your-domain.com

# Certificate location
SSL_CERT_DIR=/etc/letsencrypt/live/your-domain.com
SSL_CERT_PATH=/etc/nginx/certs/fullchain.pem
SSL_KEY_PATH=/etc/nginx/certs/privkey.pem
```

Mount the Let's Encrypt directory:

```yaml
# docker-compose.override.yml
services:
  frontend:
    volumes:
      - /etc/letsencrypt/live/your-domain.com:/etc/nginx/certs:ro
```

### Option 3: Commercial/Corporate CA

For enterprise deployments with internal PKI:

1. Generate a CSR using the provided script
2. Submit CSR to your CA
3. Place the signed certificate and key in the SSL directory
4. Update paths if your CA uses different naming

## SSL/TLS Configuration Details

The HTTPS server uses Mozilla's Modern SSL configuration profile:

### Protocols

```nginx
ssl_protocols TLSv1.2 TLSv1.3;
```

Only TLS 1.2 and 1.3 are enabled. Legacy protocols (TLS 1.0, 1.1, SSL) are disabled for security.

### Cipher Suites

```nginx
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

Strong cipher suites with forward secrecy (ECDHE, DHE) and AEAD encryption (GCM, CHACHA20-POLY1305).

### Session Configuration

```nginx
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
```

- Session caching improves performance for repeat connections
- Session tickets disabled for forward secrecy

### Security Headers

When HTTPS is enabled, additional security headers are added:

```nginx
# HTTP Strict Transport Security (HSTS)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

HSTS tells browsers to always use HTTPS for this domain for 1 year.

## Port Mapping

The frontend uses unprivileged ports inside the container (non-root cannot bind to ports < 1024):

| Protocol | External (Host) | Internal (Container) |
| -------- | --------------- | -------------------- |
| HTTP     | 5173 (default)  | 8080                 |
| HTTPS    | 8443 (default)  | 8443                 |

> **Why 8443?** The default HTTPS port is 8443 (not 443) because non-root users cannot bind to ports below 1024. Rootless containers (Podman, Docker with --userns) require unprivileged ports. If you need port 443, set `FRONTEND_HTTPS_PORT=443` and run with appropriate privileges.

## Behavior by Mode

### HTTP-Only Mode (SSL_ENABLED=false)

- HTTP server listens on port 8080
- HTTPS server block is not included
- No redirects or HSTS headers
- Suitable for development

### HTTPS Mode (SSL_ENABLED=true)

- HTTP server redirects to HTTPS (301)
- HTTPS server listens on port 8443
- HSTS header enabled
- Full security headers applied

### Fallback Behavior

If `SSL_ENABLED=true` but certificates are missing:

1. Warning message is logged
2. HTTP-only mode is used
3. No redirect is configured

## Verification

### Check Certificate

```bash
# View certificate details
openssl x509 -in certs/cert.pem -noout -text

# Check certificate expiration
openssl x509 -in certs/cert.pem -noout -dates

# Test SSL connection
openssl s_client -connect localhost:443 -servername localhost
```

### Check nginx Configuration

```bash
# Enter container and test config
docker compose -f docker-compose.prod.yml exec frontend nginx -t

# View generated config
docker compose -f docker-compose.prod.yml exec frontend cat /etc/nginx/conf.d/default.conf
```

### Test HTTPS Endpoint

```bash
# With curl (ignore self-signed warning)
curl -k https://localhost:443/health

# Check SSL grade (for public deployments)
# Use ssllabs.com or similar
```

## Troubleshooting

### Certificate Not Found

```
Warning: SSL_ENABLED=true but certificate files not found
```

**Solution:** Ensure certificates exist in the mounted directory:

```bash
ls -la certs/
# Should show cert.pem and key.pem
```

### Permission Denied

```
nginx: [emerg] cannot load certificate "/etc/nginx/certs/cert.pem"
```

**Solution:** Check file permissions:

```bash
chmod 644 certs/cert.pem
chmod 600 certs/key.pem
```

### Port Already in Use

```
bind() to 0.0.0.0:443 failed: Address already in use
```

**Solution:** Use a different port or stop the conflicting service:

```bash
# Check what's using port 443
sudo lsof -i :443

# Use alternative port
FRONTEND_HTTPS_PORT=8443 docker compose -f docker-compose.prod.yml up -d frontend
```

### Browser Certificate Warning

Self-signed certificates will show security warnings. To suppress:

1. **Development:** Accept the warning and proceed
2. **Production:** Use certificates from a trusted CA

## Security Considerations

### Certificate Storage

- **Never commit certificates to git** (certs/\*.pem is in .gitignore)
- Use file permissions: `chmod 600` for private keys
- Consider Docker secrets for production (see docker-compose.prod.yml comments)

### HSTS Preloading

The HSTS header does not include `preload` by default. To submit to browser preload lists:

1. Add `preload` to the HSTS header
2. Ensure all subdomains also support HTTPS
3. Submit to hstspreload.org

### Certificate Renewal

For Let's Encrypt certificates (90-day validity):

```bash
# Manual renewal
sudo certbot renew

# Automated renewal (cron)
0 0 * * * certbot renew --quiet && docker compose -f docker-compose.prod.yml restart frontend
```

## Related Documentation

- [Docker Compose Configuration](../../docker-compose.prod.yml) - Container and volume setup
- [Nginx Configuration](../../frontend/nginx.conf) - Full nginx config
- [Frontend AGENTS.md](../../frontend/AGENTS.md) - Frontend architecture overview
