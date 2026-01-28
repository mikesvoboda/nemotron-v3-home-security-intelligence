# AI Services TLS Configuration

> Secure AI service communications with TLS certificates.

**Time to read:** ~5 min
**Prerequisites:** [AI Configuration](ai-configuration.md)

---

## When to Use TLS

TLS is **optional** for this system's MVP deployment:

| Scenario                    | TLS Recommended? |
| --------------------------- | ---------------- |
| Local development           | No               |
| Single-user home deployment | No               |
| Multi-user deployment       | Yes              |
| Exposed to network          | Yes              |
| Compliance requirements     | Yes              |

**Note:** AI services are designed for local/trusted network communication. For internet-facing deployments, use a reverse proxy (nginx, Traefik) with TLS termination.

---

## Certificate Generation

### Self-Signed Certificates (Development)

Generate certificates for testing:

```bash
# Create certificate directory
mkdir -p ai/certs
cd ai/certs

# Generate CA key and certificate
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
  -subj "/CN=AI Services CA"

# Generate server key
openssl genrsa -out server.key 2048

# Generate CSR
openssl req -new -key server.key -out server.csr \
  -subj "/CN=localhost"

# Create SAN extension file
cat > san.ext << EOF
subjectAltName = DNS:localhost, IP:127.0.0.1
EOF

# Sign certificate
openssl x509 -req -days 365 -in server.csr \
  -CA ca.crt -CAkey ca.key -CAcreateserial \
  -out server.crt -extfile san.ext

# Verify
openssl verify -CAfile ca.crt server.crt
```

### Let's Encrypt (Production)

For production, use Let's Encrypt with certbot:

```bash
sudo certbot certonly --standalone -d ai.yourdomain.com
```

Certificates stored in `/etc/letsencrypt/live/ai.yourdomain.com/`.

---

## YOLO26 TLS Setup

Modify `ai/yolo26/model.py` to enable SSL:

```python
# Add to uvicorn.run()
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8095,
    ssl_certfile="/path/to/server.crt",
    ssl_keyfile="/path/to/server.key"
)
```

**Environment variables:**

```bash
YOLO26_SSL_CERTFILE=/path/to/server.crt
YOLO26_SSL_KEYFILE=/path/to/server.key
```

---

## Nemotron TLS Setup

llama-server supports TLS directly:

```bash
llama-server \
  --model /path/to/model.gguf \
  --port 8091 \
  --host 0.0.0.0 \
  --ssl-cert-file /path/to/server.crt \
  --ssl-key-file /path/to/server.key
```

Modify `ai/start_llm.sh` to include TLS options.

---

## Backend Configuration

Update backend to use HTTPS for AI services:

```bash
# .env
YOLO26_URL=https://localhost:8095
NEMOTRON_URL=https://localhost:8091

# For self-signed certificates, disable verification (development only)
AI_VERIFY_SSL=false
```

**Warning:** Do not disable SSL verification in production.

### Custom CA Certificate

For self-signed or private CA:

```bash
# .env
AI_CA_CERT_PATH=/path/to/ca.crt
```

---

## Reverse Proxy Approach (Recommended)

Instead of configuring TLS on each service, use a reverse proxy:

### Nginx Example

```nginx
server {
    listen 443 ssl;
    server_name ai.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /detect {
        proxy_pass http://localhost:8095;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /completion {
        proxy_pass http://localhost:8091;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Traefik Example

```yaml
# docker-compose.override.yml
services:
  traefik:
    image: traefik:v2.10
    command:
      - '--entrypoints.websecure.address=:443'
      - '--certificatesresolvers.letsencrypt.acme.tlschallenge=true'
    ports:
      - '443:443'
    labels:
      - 'traefik.http.routers.ai.rule=Host(`ai.yourdomain.com`)'
      - 'traefik.http.routers.ai.tls=true'
```

---

## Verification

Test TLS connectivity:

```bash
# Test certificate
openssl s_client -connect localhost:8095 -CAfile ca.crt

# Test HTTPS endpoint
curl --cacert ca.crt https://localhost:8095/health

# Verify in browser
# Navigate to https://localhost:8095/health
```

---

## Security Considerations

| Practice             | Recommendation                   |
| -------------------- | -------------------------------- |
| Certificate rotation | Automate with certbot or similar |
| Key permissions      | `chmod 600` on private keys      |
| Cipher suites        | Use TLS 1.3 when possible        |
| Certificate pinning  | Consider for production          |

---

## Next Steps

- [AI Troubleshooting](ai-troubleshooting.md) - Common issues
- [AI Services](ai-services.md) - Service management

---

## See Also

- [AI Configuration](ai-configuration.md) - Environment variables
- [Environment Variable Reference](../reference/config/env-reference.md) - TLS configuration variables
- [AI Overview](ai-overview.md) - Architecture and capabilities

---

[Back to Operator Hub](./)
