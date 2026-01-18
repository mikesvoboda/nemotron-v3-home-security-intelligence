# Metrics Endpoint Production Hardening Guide

This document describes the security considerations and hardening recommendations for the `/api/metrics` Prometheus endpoint.

## Current State

The `/api/metrics` endpoint:

- **Location:** `backend/api/routes/metrics.py`
- **Purpose:** Exposes Prometheus-format metrics for scraping by monitoring systems
- **Authentication:** Currently exempt from API key authentication (see `backend/api/middleware/auth.py`)
- **Rate Limiting:** Not currently rate-limited

### Why Metrics is Unauthenticated

The endpoint is intentionally exempt from authentication to allow Prometheus to scrape metrics without complex authentication configuration. From `backend/api/middleware/auth.py`:

```python
# Prometheus Metrics (required for monitoring):
# - /api/metrics    : Prometheus scraping endpoint
#   NOTE: Consider restricting to internal network only in production
```

## Security Concerns

### Information Disclosure

The metrics endpoint exposes operational data that could be valuable to attackers:

| Metric Type               | Exposed Information                         | Risk Level |
| ------------------------- | ------------------------------------------- | ---------- |
| Queue depths              | System load patterns                        | Low        |
| Error counts              | Failure patterns, potential vulnerabilities | Medium     |
| AI request durations      | Service performance characteristics         | Low        |
| Detection counts by class | Activity patterns (when people detected)    | Medium     |
| Events by camera          | Camera names, activity patterns             | Medium     |
| Risk score distributions  | Security posture visibility                 | Medium     |

### Attack Vectors

1. **Reconnaissance:** Attackers can learn system architecture and timing patterns
2. **Timing Attacks:** Request duration metrics can reveal processing complexity
3. **Denial of Service:** Rapid scraping can impact performance
4. **Information Leakage:** Camera names and detection patterns expose home activity

## Hardening Recommendations

### 1. Network-Level IP Allowlisting (Recommended)

Restrict access to the metrics endpoint at the network/reverse proxy level:

#### Nginx Configuration

```nginx
# nginx.conf
location /api/metrics {
    # Allow only Prometheus server
    allow 10.0.0.50;      # Prometheus server IP
    allow 127.0.0.1;      # Localhost
    allow 172.16.0.0/12;  # Docker internal network
    deny all;

    proxy_pass http://backend:8000;
}
```

#### Traefik Middleware

```yaml
# traefik dynamic configuration
http:
  middlewares:
    metrics-allowlist:
      ipWhiteList:
        sourceRange:
          - '10.0.0.50/32' # Prometheus server
          - '127.0.0.1/32' # Localhost
          - '172.16.0.0/12' # Docker networks

  routers:
    metrics:
      rule: 'Path(`/api/metrics`)'
      middlewares:
        - metrics-allowlist
      service: backend
```

#### UFW Firewall (Linux Host)

If running without a reverse proxy:

```bash
# Allow metrics access only from Prometheus server
ufw allow from 10.0.0.50 to any port 8000 proto tcp comment "Prometheus metrics"

# Or for Docker network
ufw allow from 172.16.0.0/12 to any port 8000 proto tcp comment "Docker metrics access"
```

### 2. Authentication for Metrics Endpoint

For deployments where network-level restrictions are insufficient:

#### Option A: Bearer Token Authentication in Prometheus

Add authentication to the metrics endpoint and configure Prometheus to use it:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'home-security-intelligence'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/metrics'
    authorization:
      type: Bearer
      credentials: 'your-metrics-api-key'
```

**Implementation required in backend:** Remove `/api/metrics` from exempt paths in `backend/api/middleware/auth.py` and add a dedicated metrics API key.

#### Option B: Basic Auth via Reverse Proxy

```nginx
# nginx.conf
location /api/metrics {
    auth_basic "Metrics";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://backend:8000;
}
```

Configure Prometheus:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'home-security-intelligence'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/metrics'
    basic_auth:
      username: prometheus
      password: 'secure-password-here' # pragma: allowlist secret
```

### 3. Rate Limiting for Metrics

Add rate limiting to prevent abuse:

```python
# backend/api/routes/metrics.py
from backend.api.middleware.rate_limit import RateLimiter, RateLimitTier

@router.get("/metrics")
async def metrics(
    _: None = Depends(RateLimiter(requests_per_minute=30))
) -> Response:
    """Return Prometheus metrics with rate limiting."""
    metrics_data = get_metrics_response()
    return Response(
        content=metrics_data,
        media_type="text/plain; charset=utf-8",
    )
```

**Note:** Be careful not to set limits too low - Prometheus typically scrapes every 10-30 seconds.

### 4. TLS/HTTPS Encryption

Always use TLS for metrics in production to prevent eavesdropping:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'home-security-intelligence'
    scheme: https
    tls_config:
      ca_file: /path/to/ca.crt
      # For self-signed certs in test environments only:
      # insecure_skip_verify: true
    static_configs:
      - targets: ['backend:8000']
```

### 5. Separate Metrics Port (Defense in Depth)

Consider exposing metrics on a different port that is only accessible internally:

```python
# Alternative: Run a separate metrics server
# This would require architectural changes to the backend
```

For Docker Compose:

```yaml
# docker-compose.prod.yml
services:
  backend:
    ports:
      - '8000:8000' # Main API (external)
      # Metrics port only exposed to internal network
    expose:
      - '9090' # Metrics (internal only)
```

### 6. Label Cardinality Protection

The codebase already includes protection against metric label cardinality explosion (see `backend/core/sanitization.py`). Ensure this remains in place:

- Object classes are allowlisted to known COCO classes
- Error types are sanitized to prevent arbitrary labels
- Camera IDs and names are length-limited

## Prometheus Configuration

### Recommended Scrape Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'home-security-intelligence'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/api/metrics'
    scrape_interval: 15s
    scrape_timeout: 10s

    # For authenticated setups:
    # authorization:
    #   type: Bearer
    #   credentials_file: /etc/prometheus/metrics_token

    # For TLS:
    # scheme: https
    # tls_config:
    #   ca_file: /etc/prometheus/ca.crt
```

### Current Monitoring Setup

The project includes a monitoring stack in `monitoring/` directory:

| Component      | Purpose                    | Port |
| -------------- | -------------------------- | ---- |
| Prometheus     | Metrics collection         | 9090 |
| Grafana        | Visualization              | 3002 |
| JSON Exporter  | JSON to metrics conversion | 7979 |
| Redis Exporter | Redis metrics              | 9121 |

See `monitoring/prometheus.yml` for the current configuration.

## Implementation Priority

| Recommendation                  | Priority | Effort | Impact |
| ------------------------------- | -------- | ------ | ------ |
| IP Allowlisting (reverse proxy) | P1       | Low    | High   |
| TLS Encryption                  | P1       | Medium | High   |
| Rate Limiting                   | P2       | Low    | Medium |
| Authentication                  | P2       | Medium | Medium |
| Separate Metrics Port           | P3       | High   | Medium |

## Deployment Scenarios

### Scenario 1: Local/Trusted Network (Current Default)

For single-user, LAN-only deployments:

- Accept current unauthenticated access
- Ensure firewall blocks external access to port 8000
- Use Docker internal networks for Prometheus

### Scenario 2: Exposed Deployment with Reverse Proxy

For deployments accessible from the internet:

1. Use nginx/Traefik as reverse proxy
2. Configure IP allowlisting for `/api/metrics`
3. Enable TLS termination at the proxy
4. Enable API key authentication for all other endpoints

### Scenario 3: High-Security Deployment

For deployments with strict security requirements:

1. All recommendations above, plus:
2. mTLS between Prometheus and backend
3. Separate network segment for monitoring
4. Audit logging for metrics access
5. Regular review of exposed metrics for sensitive data

## Audit Checklist

Before production deployment, verify:

- [ ] Metrics endpoint is not accessible from the public internet
- [ ] TLS is enabled for metrics scraping
- [ ] Prometheus server IP is allowlisted if using network restrictions
- [ ] Rate limiting is configured appropriately
- [ ] Metrics do not expose sensitive operational patterns
- [ ] Label cardinality protection is active
- [ ] Monitoring alert rules do not expose internal details externally

## Related Documentation

- [Security Guide](../../admin-guide/security.md) - Overall security configuration
- [Monitoring Guide](../../admin-guide/monitoring.md) - Monitoring setup and usage
- [Docker Deployment](../deployment/) - Container security considerations
- [Configuration Reference](../../reference/config/env-reference.md) - Environment variable reference

## References

- [Prometheus Security Best Practices](https://prometheus.io/docs/operating/security/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
