# Port Standardization (NEM-3148)

## Overview

Port configuration is standardized across all environments (development and Docker). The same internal ports are used for service-to-service communication in both environments - only the hostname/network location changes.

> **Scope:** AI traffic has two endpoints: the Triton `ai-gateway` on 8090
> (routers `/yolo26` and `/enrich-lt`; Prometheus metrics on 8002) and the
> llama.cpp `ai-vlm` verification server on 8098 (in the default compose set,
> container-side port fixed). `.env.example` and `docker-compose.prod.yml`
> remain the source of truth.

## Principle: "Build Once, Deploy Anywhere"

This standardization ensures:

- **Consistency**: Same port numbers across all environments
- **Predictability**: No surprises when moving from dev to production
- **Simplicity**: Configuration files don't need environment-specific port rewrites
- **Reduced errors**: No accidental hardcoded port mismatches

## Standardized Ports

### Internal Service Ports (Constant - Never Change)

These ports are used for service-to-service communication and remain the same in all environments:

| Service            | Port | Purpose                               | Network Location                                          |
| ------------------ | ---- | ------------------------------------- | --------------------------------------------------------- |
| Backend API        | 8000 | FastAPI server                        | Development: `localhost:8000` / Docker: `backend:8000`    |
| PostgreSQL         | 5432 | Database                              | Development: `localhost:5432` / Docker: `postgres:5432`   |
| Redis              | 6379 | Cache & Queue                         | Development: `localhost:6379` / Docker: `redis:6379`      |
| AI Gateway         | 8090 | Triton lane (`/yolo26`, `/enrich-lt`) | Development: `localhost:8090` / Docker: `ai-gateway:8090` |
| AI VLM             | 8098 | VLM verification (llama.cpp)          | Development: `localhost:8098` / Docker: `ai-vlm:8098`     |
| AI Gateway metrics | 8002 | Prometheus metrics                    | Docker: `ai-gateway:8002`                                 |

Detection traffic reaches Triton only through the gateway. The VLM server's
container-side port is fixed at 8098 (`AI_VLM_PORT` only rebinds the loopback
host mapping, and the service is in the default compose set):

```env
# .env.example (current)
AI_GATEWAY_PORT=8090
AI_GATEWAY_URL=http://ai-gateway:8090
USE_AI_GATEWAY=true
YOLO26_URL=http://localhost:8090/yolo26
AI_VLM_PORT=8098
AI_VLM_URL=http://localhost:8098
```

### External/Host Ports (Configurable)

These ports expose services to external hosts and can vary based on availability:

| Service        | Default | Purpose       | External Access                                                |
| -------------- | ------- | ------------- | -------------------------------------------------------------- |
| Frontend HTTP  | 8080    | Web UI        | http://localhost:8080, configurable via `FRONTEND_HTTP_PORT`   |
| Frontend HTTPS | 8444    | Web UI (SSL)  | https://localhost:8444, configurable via `FRONTEND_HTTPS_PORT` |
| Grafana        | 3002    | Dashboards    | http://localhost:3002, configurable via `GRAFANA_PORT`         |
| Prometheus     | 9090    | Metrics       | http://localhost:9090, configurable                            |
| Alertmanager   | 9093    | Alerts        | http://localhost:9093, configurable                            |
| Redis Exporter | 9121    | Redis metrics | http://localhost:9121, configurable                            |
| JSON Exporter  | 7979    | JSON metrics  | http://localhost:7979, configurable                            |

> **Frontend Port Notes:**
>
> - **Production containers (docker-compose.prod.yml):** nginx serves the React app on internal ports 8080 (HTTP) and 8443 (HTTPS), mapped to host ports `FRONTEND_HTTP_PORT` (8080) and `FRONTEND_HTTPS_PORT` (8444).
> - **Local development (npm run dev):** Vite dev server runs on 8444 with HTTPS (`frontend/vite.config.ts` `server.port`).
> - **SSL is disabled by default** in production (`SSL_ENABLED` defaults to `false`); set `SSL_ENABLED=true` to serve HTTPS with auto-generated self-signed certificates.

## Environment Separation

### Development Environment

Services are accessed via `localhost` with standard ports:

```env
# Development .env  # pragma: allowlist secret
DATABASE_URL=postgresql+asyncpg://security:password@localhost:5432/security  # pragma: allowlist secret
REDIS_URL=redis://localhost:6379/0
YOLO26_URL=http://localhost:8090/yolo26
AI_VLM_URL=http://localhost:8098
```

### Docker Compose Environment

Services are accessed via container service names with the same standard internal ports:

```yaml
# backend service environment (docker-compose.prod.yml)  # pragma: allowlist secret
DATABASE_URL=postgresql+asyncpg://security:password@postgres:5432/security  # pragma: allowlist secret
REDIS_URL=redis://redis:6379/0
AI_GATEWAY_URL=http://ai-gateway:8090
YOLO26_URL=http://ai-gateway:8090/yolo26
AI_VLM_URL=http://ai-vlm:8098
```

Notice: **Only the hostname changes, ports remain 5432, 6379, 8090, 8098, etc.**

## Configuration Files

### backend/core/config.py

Service URLs default to the gateway in Docker:

```python
yolo26_url: str = Field(
    default="http://ai-gateway:8090/yolo26",
    # Docker: http://ai-gateway:8090/yolo26 (via AI gateway)
)
ai_vlm_url: str = Field(
    default="http://localhost:8098",
    # Docker: http://ai-vlm:8098 (the ai-vlm service, container PORT fixed at 8098)
)
```

### .env.example

The example environment file documents the standardized ports and points all
model URLs at `AI_GATEWAY_PORT` (see the `AI SERVICE PORTS` section).

### setup.py

The setup script generates the `.env` for the host environment, reading port
values from `.env.example` as the single source of truth and probing for free
host ports before writing (`find_available_port` in
`setup_lib/core.py`). `.env` is the sole config source — no
`docker-compose.override.yml` is generated.

### docker-compose.prod.yml

Standard internal ports are exposed via environment variables:

```yaml
ai-gateway:
  ports:
    - '127.0.0.1:${AI_GATEWAY_PORT:-8090}:8090'
    - '127.0.0.1:${AI_GATEWAY_METRICS_PORT:-8002}:8002'
```

### Host port remapping

`docker-compose.prod.yml` itself does the host-to-internal mapping through the
`.env` variables — there is no separate override file:

```yaml
postgres:
  ports:
    - '127.0.0.1:${POSTGRES_PORT:-5432}:5432' # Host var -> Container 5432 (internal standard)

redis:
  ports:
    - '127.0.0.1:${REDIS_PORT:-6379}:6379' # Host var -> Container 6379 (internal standard)
```

If `setup.py` finds a host port taken, it writes a free alternative into `.env`;
the right-hand (container) side never changes.

## When Ports Are Standard vs. When They Can Vary

### Always Standard (Never Change)

- **Backend API**: 8000 (internal communication between frontend/backend)
- **PostgreSQL**: 5432 (internal communication with database)
- **Redis**: 6379 (internal communication with cache)
- **AI Gateway**: 8090 (internal communication with the Triton detection lane)
- **AI VLM**: 8098 (internal communication with the verification server; the container-side port is fixed)

These ports are embedded in configuration and service discovery.

### Can Vary Based on Availability

- **Frontend HTTP/HTTPS**: host ports remappable (`FRONTEND_HTTP_PORT`, `FRONTEND_HTTPS_PORT`)
- **Monitoring**: 3002, 9090, 9093, etc. (all configurable external ports)

These ports are for external access only and are safely remappable.

## Running setup.py

The `setup.py` script automatically:

1. **Reads** port values from `.env.example` (single source of truth)
2. **Generates** the `.env` with correct service URLs on standard ports
3. **Checks** for external port conflicts on this host
4. **Finds alternatives** for conflicting external ports and records them in `.env`

```bash
# Run once to set up standardized configuration
python setup.py
```

This ensures your configuration uses standard internal ports while automatically handling external port conflicts.

## Configuration Examples

### Development (All Services Local)

```bash
# All services on localhost with standard ports  # pragma: allowlist secret
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db  # pragma: allowlist secret
REDIS_URL=redis://localhost:6379/0
YOLO26_URL=http://localhost:8090/yolo26
AI_VLM_URL=http://localhost:8098
API_HOST=0.0.0.0
API_PORT=8000
```

### Docker Compose (Service Network)

```yaml
# Backend service environment (auto-generated)  # pragma: allowlist secret
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db  # pragma: allowlist secret
REDIS_URL=redis://redis:6379/0
YOLO26_URL=http://ai-gateway:8090/yolo26
AI_VLM_URL=http://ai-vlm:8098
```

### Mixed Environment (Local Services + Docker)

```env
# Custom setup for special cases  # pragma: allowlist secret
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db  # pragma: allowlist secret
REDIS_URL=redis://redis.example.com:6379/0                     # Remote redis
YOLO26_URL=http://ai-gateway:8090/yolo26                       # Docker network gateway
```

Note: Even in mixed environments, ports remain standard (5432, 6379, 8090).

## Troubleshooting

### Port Conflicts

If you see "Address already in use":

```bash
# 1. Run setup.py again - it will find available ports
python setup.py

# 2. Or check what's using the port
lsof -i :5432        # Check PostgreSQL port
lsof -i :6379        # Check Redis port
lsof -i :8000        # Check Backend port
```

### Service Can't Connect

If backend can't connect to Redis:

```bash
# Wrong: Using the remapped external host port (REDIS_PORT) inside a container
REDIS_URL=redis://localhost:6380  # ❌ This won't work!

# Right: Use internal standard port
REDIS_URL=redis://localhost:6379  # ✅ Correct for local dev
REDIS_URL=redis://redis:6379      # ✅ Correct for Docker
```

### Environment Variable Mismatch

If you see "Connection refused":

1. Check hostname matches environment (localhost for dev, service names for docker)
2. Verify port is standard (5432, 6379, 8090, not 5433, 6380)
3. Confirm DATABASE_URL is set in environment variables, not just .env.example

```bash
# Debug: Check what environment variables are set
env | grep -E "DATABASE_URL|REDIS_URL|YOLO26_URL"
```

## Monitoring Configuration Files

The monitoring stack configuration files (`monitoring/`) use Docker service names for all service-to-service communication, which means **no templating is required** even though they contain hardcoded port numbers.

### Why No Templating Is Needed

The `.env` port variables (e.g., `PROMETHEUS_PORT=9090`, `GRAFANA_PORT=3002`) only control **host port bindings** in docker-compose files. They define which port on the host machine maps to the container's internal port.

Inside the Docker network, all services communicate using:

- **Service names** (e.g., `prometheus`, `backend`, `alertmanager`)
- **Internal container ports** (fixed, not configurable)

For example, in `docker-compose.prod.yml`:

```yaml
prometheus:
  ports:
    - '127.0.0.1:${PROMETHEUS_PORT:-9090}:9090' # Host binding from .env
```

The `${PROMETHEUS_PORT}` only affects external access (`localhost:9090`). Internal services always connect to `prometheus:9090` regardless of what `PROMETHEUS_PORT` is set to.

### Files That Use Service Names (No Templating Needed)

| File                                                         | Example References                                                    | Notes                                |
| ------------------------------------------------------------ | --------------------------------------------------------------------- | ------------------------------------ |
| `monitoring/prometheus.yml`                                  | `alertmanager:9093`, `backend:8000`, `ai-vlm:8098`, `ai-gateway:8002` | All scrape targets use service names |
| `monitoring/alertmanager.yml`                                | `http://backend:8000/api/webhooks/alerts`                             | Webhook receivers use service names  |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | `http://prometheus:9090`, `http://loki:3100`                          | Datasource URLs use service names    |
| `monitoring/alloy/config.alloy`                              | `http://loki:3100`, `http://pyroscope:4040`, `tempo:4317`             | All endpoints use service names      |

### Internal vs External Ports

| Service       | Internal Port (Fixed) | External Port (Configurable via .env)       |
| ------------- | --------------------- | ------------------------------------------- |
| Prometheus    | 9090                  | `PROMETHEUS_PORT`                           |
| Alertmanager  | 9093                  | `ALERTMANAGER_PORT`                         |
| Grafana       | 3000                  | `GRAFANA_PORT` (default host 3002)          |
| Loki          | 3100                  | `LOKI_PORT`                                 |
| Tempo (OTLP)  | 4317                  | `TEMPO_OTLP_GRPC`                           |
| Pyroscope     | 4040                  | `PYROSCOPE_PORT`                            |
| Node Exporter | 9100                  | `NODE_EXPORTER_PORT`                        |
| cAdvisor      | systemd service       | `CADVISOR_PORT` (host service, not compose) |

Traces are served by Grafana Tempo; Alloy exports OTLP to `tempo:4317`.

### Special Case: DCGM Exporter

The `dcgm-exporter` job in `prometheus.yml` targets `host.containers.internal`
on port `9400` because:

- DCGM exporter runs in rootful Podman (requires elevated privileges)
- Prometheus runs in rootless Podman
- They are in separate network namespaces, so service-name DNS doesn't work

This is the only service that references a host-accessible endpoint, and `9400` is the standard DCGM exporter port. (cAdvisor moved to a rootful systemd service with the same pattern — see `monitoring/cadvisor/cadvisor.service`.)

### When Would Templating Be Needed?

Templating would only be necessary if:

1. A monitoring config file needed to reference a **host-accessible** endpoint (not service-name based)
2. That endpoint's port was configurable in `.env`

Currently, no monitoring configuration files have this requirement.

## Benefits

1. **Simplified Configuration**: No special port handling per environment
2. **Better Documentation**: Clear separation of hostname vs. port changes
3. **Fewer Bugs**: Reduces misconfigured ports causing connection failures
4. **Easier Migration**: Moving from dev to Docker/production requires only hostname changes
5. **Standard Compliance**: Uses industry-standard ports (PostgreSQL 5432, Redis 6379, etc.)
6. **Automated Setup**: `setup.py` handles complexity automatically

## References

- `docker-compose.prod.yml` - Production configuration
- `.env.example` - Environment template with port documentation
- `backend/core/config.py` - Configuration settings
- `setup.py` - Setup script with port standardization
