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

**Note:** `ai-gateway` (:8090) and `ai-llm` (:8091) serve **plain HTTP only** — nothing in
`ai/gateway/` passes `ssl_certfile`/`ssl_keyfile` to uvicorn or Triton, and llama.cpp's
`llama-server` has no TLS listener. Both containers bind `127.0.0.1` on the host by
default, which is the primary boundary. For any network exposure, terminate TLS at a
reverse proxy.

> [!IMPORTANT] > **Backend trust:** the AI clients (`backend/services/detector_client.py`,
> `nemotron_analyzer.py`, …) use default-verification `httpx.AsyncClient` instances, and
> there is **no** `AI_VERIFY_SSL` / `AI_CA_CERT_PATH` setting in
> `backend/core/config.py` or `.env.example`. Pointing `*_URL` variables at an
> `https://` endpoint with a self-signed certificate will fail TLS verification. Either
> use a proxy with a certificate the OS trust store accepts, or add trust configuration
> before going down this path. (`TLS_MODE` / `TLS_CERT_PATH` in the backend configure the
> **backend's own** API server, not its AI clients.)

---

## Certificate Generation

### Self-Signed Certificates (Development)

Generate certificates for testing (they will be presented by the **proxy**, not the AI
services themselves):

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

## Reverse Proxy Approach (Recommended)

Since neither AI container speaks TLS, a TLS-terminating proxy in front of `127.0.0.1:8090`
and `127.0.0.1:8091` is the supported pattern.

### Nginx Example

```nginx
server {
    listen 443 ssl;
    server_name ai.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # ai-gateway routers (pass the router path through)
    location ~ ^/(yolo26|florence|clip|enrichment|enrich-lt|health|metrics) {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # ai-llm (llama.cpp) — detection worker sends POST /completion
    location /completion {
        proxy_pass http://127.0.0.1:8091;
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

### Backend Configuration

Once the proxy presents certificates the backend's trust store accepts:

```bash
# .env — host-run backend against a TLS-terminating proxy
USE_AI_GATEWAY=true
AI_GATEWAY_URL=https://ai.yourdomain.com
YOLO26_URL=https://ai.yourdomain.com/yolo26
NEMOTRON_URL=https://ai.yourdomain.com
```

**Warning:** Do not disable SSL verification in production. Remember the trust limitation
above: with the code as shipped, self-signed proxy certs require an added trust mechanism
(OS trust store entry for the CA is enough — `httpx` uses it).

---

## Verification

Test TLS connectivity through the proxy:

```bash
# Test certificate
openssl s_client -connect localhost:443 -CAfile ai/certs/ca.crt -servername ai.yourdomain.com

# Test HTTPS endpoints
curl --cacert ai/certs/ca.crt https://ai.yourdomain.com/health
curl --cacert ai/certs/ca.crt https://ai.yourdomain.com/yolo26/health
```

---

## Security Considerations

| Practice             | Recommendation                                           |
| -------------------- | -------------------------------------------------------- |
| Certificate rotation | Automate with certbot or similar                         |
| Key permissions      | `chmod 600` on private keys                              |
| Cipher suites        | Use TLS 1.3 when possible                                |
| Certificate pinning  | Consider for production                                  |
| Binding              | Keep the AI ports on `127.0.0.1`; publish only the proxy |

---

## Next Steps

- [AI Troubleshooting](ai-troubleshooting.md) - Common issues
- [AI Services](ai-services.md) - Service management

---

## See Also

- [AI Configuration](ai-configuration.md) - Environment variables
- [Environment Variable Reference](../reference/config/env-reference.md) - TLS configuration variables
- [AI Overview](ai-overview.md) - Architecture and capabilities
- [Deployment Modes](deployment-modes.md) - Network layout options

---

[Back to Operator Hub](README.md)
