# Container Orchestrator Design

**Date:** 2026-01-05
**Status:** Proposed
**Author:** Claude + Mike Svoboda

## Overview

Design for a backend service that manages the lifecycle of all deployment containers:

- **AI Services:** RT-DETR, Nemotron, Florence, CLIP, Enrichment
- **Infrastructure:** PostgreSQL, Redis
- **Monitoring:** Grafana, Prometheus, Redis Exporter, JSON Exporter

The orchestrator provides eager startup, health monitoring, and self-healing with automatic restarts and failure limits.

## Goals

- Start all enabled services on backend boot
- Monitor health of all containers every 30 seconds
- Auto-restart failed containers with exponential backoff
- Disable services after repeated failures to prevent restart loops
- Persist state across backend restarts
- Provide REST API and WebSocket updates for UI integration
- Cross-platform support (Linux, macOS, Windows)
- Respect service categories and dependencies (infrastructure vs AI vs monitoring)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              ContainerOrchestrator                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │  │
│  │  │ Discovery   │  │ Health      │  │ Lifecycle    │   │  │
│  │  │ Service     │  │ Monitor     │  │ Manager      │   │  │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘   │  │
│  │         │                │                │           │  │
│  │         └────────────────┼────────────────┘           │  │
│  │                          ▼                            │  │
│  │                 ┌─────────────────┐                   │  │
│  │                 │  Docker API     │                   │  │
│  │                 │  (docker-py)    │                   │  │
│  │                 └────────┬────────┘                   │  │
│  └──────────────────────────┼────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    INFRASTRUCTURE                           │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  PostgreSQL  │  │    Redis     │                        │
│  │    :5432     │  │    :6379     │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                      AI SERVICES                            │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐       │
│  │RT-DETR  │Nemotron │Florence │  CLIP   │Enrichment│       │
│  │ :8090   │ :8091   │ :8092   │ :8093   │  :8094  │       │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                      MONITORING                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Prometheus  │  │   Grafana    │  │Redis Exporter│      │
│  │    :9090     │  │    :3000     │  │    :9121     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**Components:**

- **Discovery Service:** Finds containers by name pattern on startup (AI, infrastructure, monitoring)
- **Health Monitor:** Periodic health checks (every 30s), tracks failure counts
- **Lifecycle Manager:** Start/stop/restart containers, respects backoff and failure limits

**Service Categories:**

| Category       | Services                                           | Restart Policy        |
| -------------- | -------------------------------------------------- | --------------------- |
| Infrastructure | PostgreSQL, Redis                                  | Critical - aggressive |
| AI Services    | RT-DETR, Nemotron, Florence, CLIP, Enrichment      | Standard backoff      |
| Monitoring     | Prometheus, Grafana, Redis Exporter, JSON Exporter | Lenient               |

## Key Decisions

| Decision            | Choice                     | Rationale                                    |
| ------------------- | -------------------------- | -------------------------------------------- |
| Architecture        | Background task in FastAPI | Simple, reuses existing infrastructure       |
| Container runtime   | Docker API (docker-py)     | Works with Docker and Podman                 |
| Startup mode        | Eager                      | All enabled services start on boot           |
| Failure handling    | Self-healing with limits   | Auto-restart up to 5 failures, then disable  |
| Container discovery | Inspect running containers | No need to track which compose file was used |
| State persistence   | Redis                      | Failure counts survive backend restarts      |

## Data Model

### ServiceCategory

```python
class ServiceCategory(Enum):
    INFRASTRUCTURE = "infrastructure"  # PostgreSQL, Redis - critical, aggressive restart
    AI = "ai"                          # RT-DETR, Nemotron, etc. - standard backoff
    MONITORING = "monitoring"          # Grafana, Prometheus - lenient, optional
```

### ManagedService

```python
@dataclass
class ManagedService:
    name: str                      # "postgres", "ai-detector", "grafana", etc.
    container_id: str | None       # Docker container ID
    image: str                     # "postgres:16-alpine", "ghcr.io/.../backend:latest"
    port: int                      # 5432, 8090, 3000, etc.
    health_endpoint: str | None    # "/health" or None for non-HTTP health checks
    health_cmd: str | None         # Alternative: "pg_isready", "redis-cli ping"

    # Classification
    category: ServiceCategory      # infrastructure, ai, monitoring

    # State
    status: ServiceStatus          # running, stopped, unhealthy, disabled
    enabled: bool                  # User can disable services

    # Self-healing tracking
    failure_count: int             # Consecutive failures
    last_failure_at: datetime | None
    last_restart_at: datetime | None
    restart_count: int             # Total restarts since backend boot

    # Limits (defaults vary by category)
    max_failures: int = 5          # Disable after N consecutive failures
    restart_backoff_base: float = 5.0   # Exponential backoff: 5s, 10s, 20s...
    restart_backoff_max: float = 300.0  # Cap at 5 minutes
```

### Category-Specific Defaults

| Category       | max_failures | backoff_base | backoff_max | Grace Period |
| -------------- | ------------ | ------------ | ----------- | ------------ |
| Infrastructure | 10           | 2.0s         | 60s         | 10s          |
| AI             | 5            | 5.0s         | 300s        | 60-180s      |
| Monitoring     | 3            | 10.0s        | 600s        | 30s          |

### ServiceStatus

```python
class ServiceStatus(Enum):
    RUNNING = "running"       # Container up and healthy
    STARTING = "starting"     # Container starting, not yet healthy
    UNHEALTHY = "unhealthy"   # Running but failing health checks
    STOPPED = "stopped"       # Container not running
    DISABLED = "disabled"     # Exceeded failure limit, requires manual reset
    NOT_FOUND = "not_found"   # Container doesn't exist yet
```

### State Persistence

- In-memory for fast access during health checks
- Redis for persistence across backend restarts
- Redis key pattern: `orchestrator:service:{name}:state`

## Health Monitoring

### Health Check Methods

Services can use either HTTP health endpoints or Docker exec commands:

```python
async def check_health(service: ManagedService, docker: DockerClient) -> bool:
    """
    Check service health using appropriate method.

    - HTTP endpoint: GET request to health_endpoint
    - Command: Docker exec with health_cmd
    """
    if service.health_endpoint:
        # HTTP health check (AI services, Grafana, Prometheus)
        return await check_http_health(service)
    elif service.health_cmd:
        # Command health check (PostgreSQL, Redis)
        return await check_cmd_health(service, docker)
    else:
        # Fallback: container running = healthy
        return True

async def check_http_health(service: ManagedService, timeout: float = 5.0) -> bool:
    """HTTP GET to health endpoint."""
    url = f"http://localhost:{service.port}{service.health_endpoint}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False

async def check_cmd_health(service: ManagedService, docker: DockerClient) -> bool:
    """Execute health command inside container."""
    try:
        exit_code = await docker.exec_run(
            service.container_id,
            service.health_cmd,
            timeout=5,
        )
        return exit_code == 0
    except Exception:
        return False
```

### Main Loop (every 30 seconds)

```python
async def orchestration_loop():
    while True:
        for service in registry.get_enabled_services():
            # 1. Check container exists
            container = await docker.get_container(service.container_id)

            if container is None:
                await handle_missing_container(service)
                continue

            # 2. Check container status
            if container.status != "running":
                await handle_stopped_container(service)
                continue

            # 3. Check health (HTTP or command-based)
            healthy = await check_health(service, docker)

            if healthy:
                service.failure_count = 0  # Reset on success
                service.status = ServiceStatus.RUNNING
            else:
                await handle_unhealthy(service)

        await asyncio.sleep(30)
```

### Self-Healing Decision Tree

```
Container Missing/Stopped/Unhealthy
            │
            ▼
    ┌───────────────────┐
    │ failure_count >=  │──Yes──▶ Mark DISABLED, alert, skip
    │ max_failures?     │
    └───────────────────┘
            │ No
            ▼
    ┌───────────────────┐
    │ Backoff elapsed?  │──No───▶ Skip this cycle
    │ (exponential)     │
    └───────────────────┘
            │ Yes
            ▼
    ┌───────────────────┐
    │ Restart container │
    │ Increment counts  │
    │ Record timestamp  │
    └───────────────────┘
```

### Backoff Calculation

```python
backoff = min(base * 2^failure_count, max)
# 5s, 10s, 20s, 40s, 80s, 160s, 300s (cap)
```

## Container Lifecycle

### Discovery (on startup)

```python
async def discover_services():
    """Find containers by name pattern and register them."""

    # Infrastructure services (critical)
    INFRASTRUCTURE_CONFIGS = {
        "postgres": ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
            health_cmd="pg_isready -U security",
            startup_grace_period=10,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        ),
        "redis": ServiceConfig(
            display_name="Redis",
            category=ServiceCategory.INFRASTRUCTURE,
            port=6379,
            health_cmd="redis-cli ping",
            startup_grace_period=10,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        ),
    }

    # AI services (standard)
    AI_CONFIGS = {
        "ai-detector": ServiceConfig(
            display_name="RT-DETRv2",
            category=ServiceCategory.AI,
            port=8090,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-llm": ServiceConfig(
            display_name="Nemotron",
            category=ServiceCategory.AI,
            port=8091,
            health_endpoint="/health",
            startup_grace_period=120,
        ),
        "ai-florence": ServiceConfig(
            display_name="Florence-2",
            category=ServiceCategory.AI,
            port=8092,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-clip": ServiceConfig(
            display_name="CLIP",
            category=ServiceCategory.AI,
            port=8093,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-enrichment": ServiceConfig(
            display_name="Enrichment",
            category=ServiceCategory.AI,
            port=8094,
            health_endpoint="/health",
            startup_grace_period=180,
        ),
    }

    # Monitoring services (optional profile)
    MONITORING_CONFIGS = {
        "prometheus": ServiceConfig(
            display_name="Prometheus",
            category=ServiceCategory.MONITORING,
            port=9090,
            health_endpoint="/-/healthy",
            startup_grace_period=30,
            max_failures=3,
            restart_backoff_base=10.0,
            restart_backoff_max=600.0,
        ),
        "grafana": ServiceConfig(
            display_name="Grafana",
            category=ServiceCategory.MONITORING,
            port=3000,
            health_endpoint="/api/health",
            startup_grace_period=30,
            max_failures=3,
            restart_backoff_base=10.0,
            restart_backoff_max=600.0,
        ),
        "redis-exporter": ServiceConfig(
            display_name="Redis Exporter",
            category=ServiceCategory.MONITORING,
            port=9121,
            health_endpoint="/metrics",
            startup_grace_period=15,
            max_failures=3,
        ),
        "json-exporter": ServiceConfig(
            display_name="JSON Exporter",
            category=ServiceCategory.MONITORING,
            port=7979,
            health_endpoint="/metrics",
            startup_grace_period=15,
            max_failures=3,
        ),
    }

    ALL_CONFIGS = {**INFRASTRUCTURE_CONFIGS, **AI_CONFIGS, **MONITORING_CONFIGS}

    containers = await docker.containers.list(all=True)

    for container in containers:
        for pattern, config in ALL_CONFIGS.items():
            if pattern in container.name:
                registry.register(ManagedService(
                    name=pattern,
                    container_id=container.id,
                    image=container.image.tags[0],
                    port=config.port,
                    health_endpoint=config.health_endpoint,
                    health_cmd=config.health_cmd,
                    category=config.category,
                ))
```

### Restart Operation

```python
async def restart_container(service: ManagedService):
    """Restart with the same image and config."""

    container = await docker.containers.get(service.container_id)

    # Stop gracefully (10s timeout)
    await container.stop(timeout=10)

    # Start same container
    await container.start()

    # Update tracking
    service.last_restart_at = datetime.now(UTC)
    service.restart_count += 1
    service.failure_count += 1
    service.status = ServiceStatus.STARTING

    # Persist to Redis
    await persist_service_state(service)

    # Notify UI via WebSocket
    await broadcast_service_status(service)
```

## Startup Sequence

```
Backend Starts
      │
      ▼
┌─────────────────────────┐
│ 1. Connect to Docker    │ ◄── Fail fast if Docker unavailable
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. Discover containers  │ ◄── Find existing AI containers
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. Load state from Redis│ ◄── Restore failure counts, disabled status
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. Start missing svc    │ ◄── Eager startup of enabled services
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. Begin health loop    │ ◄── Async task monitors every 30s
└─────────────────────────┘
```

### Graceful Shutdown

- Stop the monitoring loop
- Persist final state to Redis
- Do NOT stop AI containers (they should keep running independently)

## API Endpoints

### List Services

```
GET /api/system/services
GET /api/system/services?category=ai          # Filter by category
GET /api/system/services?category=infrastructure
```

Response:

```json
{
  "services": [
    {
      "name": "postgres",
      "display_name": "PostgreSQL",
      "category": "infrastructure",
      "status": "running",
      "enabled": true,
      "container_id": "def456...",
      "image": "postgres:16-alpine",
      "port": 5432,
      "failure_count": 0,
      "restart_count": 0,
      "last_restart_at": null,
      "uptime_seconds": 86400
    },
    {
      "name": "ai-detector",
      "display_name": "RT-DETRv2",
      "category": "ai",
      "status": "running",
      "enabled": true,
      "container_id": "abc123...",
      "image": "ghcr.io/.../rtdetr:latest",
      "port": 8090,
      "failure_count": 0,
      "restart_count": 2,
      "last_restart_at": "2026-01-05T10:30:00Z",
      "uptime_seconds": 3600
    },
    {
      "name": "grafana",
      "display_name": "Grafana",
      "category": "monitoring",
      "status": "running",
      "enabled": true,
      "container_id": "ghi789...",
      "image": "grafana/grafana:10.2.3",
      "port": 3000,
      "failure_count": 0,
      "restart_count": 0,
      "last_restart_at": null,
      "uptime_seconds": 7200
    }
  ],
  "by_category": {
    "infrastructure": { "total": 2, "healthy": 2, "unhealthy": 0 },
    "ai": { "total": 5, "healthy": 3, "unhealthy": 2 },
    "monitoring": { "total": 4, "healthy": 4, "unhealthy": 0 }
  },
  "timestamp": "2026-01-05T15:45:00Z"
}
```

### Service Actions

```
POST /api/system/services/{name}/restart  # Manual restart (resets failure count)
POST /api/system/services/{name}/enable   # Re-enable disabled service
POST /api/system/services/{name}/disable  # Manually disable service
POST /api/system/services/{name}/start    # Start stopped service
```

### WebSocket Events

```json
{
  "type": "service_status",
  "data": {
    "name": "ai-florence",
    "status": "unhealthy",
    "failure_count": 3,
    "message": "Health check failed, restart scheduled"
  }
}
```

## Configuration

### Settings

```python
class OrchestratorSettings(BaseModel):
    # Feature flag
    enabled: bool = True

    # Docker connection
    docker_host: str | None = None

    # Health monitoring
    health_check_interval: int = 30      # seconds
    health_check_timeout: int = 5        # seconds
    startup_grace_period: int = 60       # seconds

    # Self-healing limits
    max_consecutive_failures: int = 5
    restart_backoff_base: float = 5.0    # seconds
    restart_backoff_max: float = 300.0   # 5 minutes

class ServiceConfig(BaseModel):
    enabled: bool = True
    health_endpoint: str = "/health"
    startup_grace_period: int | None = None
    max_failures: int | None = None
```

### Environment Variables

```bash
ORCHESTRATOR_ENABLED=true
ORCHESTRATOR_HEALTH_CHECK_INTERVAL=30
ORCHESTRATOR_MAX_CONSECUTIVE_FAILURES=5
DOCKER_HOST=unix:///var/run/docker.sock
```

## Error Handling

| Scenario                          | Behavior                                                  |
| --------------------------------- | --------------------------------------------------------- |
| Docker API unavailable            | Log error, disable orchestration, backend continues       |
| Container image missing           | Mark as `NOT_FOUND`, alert, don't retry                   |
| GPU OOM during start              | Treat as failure, backoff and retry                       |
| Network port conflict             | Treat as failure, log detailed error                      |
| Container starts but health fails | Wait for grace period before counting failure             |
| Backend restarts mid-recovery     | Redis restores state, continues backoff                   |
| User manually stops container     | Restart if enabled, respect if disabled                   |
| PostgreSQL/Redis restart          | Backend has connection retry logic, orchestrator proceeds |
| Monitoring service down           | Lower priority, lenient restart policy                    |

### Dependency Considerations

The backend depends on PostgreSQL and Redis. When these services restart:

1. **PostgreSQL:** SQLAlchemy connection pool automatically reconnects
2. **Redis:** Redis client retries with exponential backoff

The orchestrator does NOT need to coordinate with the backend before restarting infrastructure services because:

- The backend has built-in connection resilience
- Brief downtime (< 30s) is acceptable for self-healing
- The orchestrator itself persists state to Redis, so it handles Redis restarts gracefully

**Restart Order (when multiple services need restart):**

1. Infrastructure (PostgreSQL, Redis) - highest priority
2. AI Services - standard priority
3. Monitoring - lowest priority

### Logging Strategy

- `INFO`: Service started, recovered, health passed
- `WARNING`: Health failed, restart scheduled, backoff waiting
- `ERROR`: Max failures reached, service disabled, Docker API error

## File Structure

```
backend/
├── services/
│   └── container_orchestrator.py    # Main orchestrator (~400 lines)
├── core/
│   └── docker_client.py             # Docker API wrapper (~150 lines)
├── api/
│   ├── routes/
│   │   └── services.py              # REST endpoints (~100 lines)
│   └── schemas/
│       └── services.py              # Pydantic models (~80 lines)
└── tests/
    ├── unit/services/
    │   └── test_container_orchestrator.py
    └── integration/
        └── test_orchestrator_integration.py
```

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "docker>=7.0.0",
]
```

## Implementation Order

1. `docker_client.py` - Docker API wrapper
2. `services.py` schemas - Data models
3. `container_orchestrator.py` - Core orchestration logic
4. `services.py` routes - REST API endpoints
5. FastAPI lifespan integration
6. Unit tests
7. Integration tests
8. UI components (System page)

## Testing Strategy

### Unit Tests (mocked Docker)

- Health check success resets failure count
- Health check failure increments failure count
- Max failures disables service
- Backoff respected between restarts
- Restart preserves original image
- Container discovery by name pattern

### Integration Tests (real Docker)

- Detect stopped container and restart
- Respect disabled service setting
- State persists across backend restart

## Future Considerations

- **Scaling:** Support multiple replicas of stateless services
- **Resource limits:** Monitor and enforce CPU/memory limits
- **Dependency ordering:** Start services in dependency order (e.g., Redis before backend)
- **Rolling updates:** Graceful container image updates without downtime
