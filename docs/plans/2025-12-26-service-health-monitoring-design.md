# Service Health Monitoring & Auto-Recovery Design

**Date:** 2025-12-26
**Epic:** home_security_intelligence-a2v
**Status:** Approved

## Overview

Implement automatic health monitoring and recovery for dependent services (Redis, RT-DETRv2, Nemotron). The system detects when services go offline, attempts automatic restarts with exponential backoff, and surfaces status to users via the dashboard.

## Goals

1. Detect when services go offline via periodic health checks
2. Automatically restart failed services with exponential backoff
3. Surface service status to users via WebSocket + dashboard alerts
4. Support both shell scripts (dev) and Docker (prod) via strategy pattern

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    main.py lifespan                      │
├─────────────────────────────────────────────────────────┤
│  ServiceHealthMonitor                                    │
│  ├── health_check_loop() - runs every N seconds         │
│  ├── ServiceManager (abstract)                          │
│  │   ├── ShellServiceManager (dev)                      │
│  │   └── DockerServiceManager (prod)                    │
│  └── services: [RedisService, RTDETRService, Nemotron]  │
└─────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   WebSocket broadcast    Structured logs
   (service_status)       (service health events)
```

## Components

### ServiceConfig (dataclass)

```python
@dataclass
class ServiceConfig:
    name: str                    # "rtdetr", "nemotron", "redis"
    health_url: str              # "http://localhost:8090/health"
    restart_cmd: str             # "./ai/start_detector.sh"
    health_timeout: float = 5.0  # seconds
    max_retries: int = 3
    backoff_base: float = 5.0    # seconds (5s, 10s, 20s...)
```

### ServiceManager (abstract base class)

```python
class ServiceManager(ABC):
    @abstractmethod
    async def check_health(self, config: ServiceConfig) -> bool:
        """Return True if service is healthy."""
        pass

    @abstractmethod
    async def restart(self, config: ServiceConfig) -> bool:
        """Attempt restart. Return True if successful."""
        pass
```

### ShellServiceManager

- Health check via `httpx` GET to health_url
- Restart via `asyncio.create_subprocess_shell()`
- Subprocess timeout: 60s default

### DockerServiceManager

- Same HTTP health checks
- Restart via `docker restart <container>`

### ServiceHealthMonitor

```python
class ServiceHealthMonitor:
    def __init__(
        self,
        manager: ServiceManager,
        services: list[ServiceConfig],
        broadcaster: EventBroadcaster,
        check_interval: float = 15.0,
    ):
        self._manager = manager
        self._services = services
        self._broadcaster = broadcaster
        self._check_interval = check_interval
        self._failure_counts: dict[str, int] = {}
        self._running = False
```

**Behavior:**

- Check all services every N seconds (configurable, default 15s)
- On failure: wait backoff → restart → verify health
- Backoff sequence: 5s, 10s, 20s (exponential)
- Max 3 retries before giving up
- Broadcast status changes via WebSocket
- Reset failure count on recovery

## Configuration

New settings in `backend/core/config.py`:

```python
# Service manager type
service_manager_type: str = "shell"  # or "docker"

# Health check interval
health_check_interval: float = 15.0  # seconds

# Restart commands
redis_restart_cmd: str = "sudo systemctl restart redis"
rtdetr_restart_cmd: str = "./ai/start_detector.sh"
nemotron_restart_cmd: str = "./ai/start_nemotron.sh"

# Health check settings
service_health_timeout: float = 5.0
service_max_retries: int = 3
service_backoff_base: float = 5.0
```

## WebSocket Events

```json
{
  "type": "service_status",
  "service": "rtdetr",
  "status": "restarting",
  "message": "Attempting restart (attempt 2/3)",
  "timestamp": "2025-12-26T02:30:00Z"
}
```

**Status values:**

- `healthy` - Service responding normally
- `unhealthy` - Health check failed
- `restarting` - Restart in progress
- `restart_failed` - Restart attempt failed
- `failed` - Max retries exceeded, giving up

## Frontend Integration

### useServiceStatus Hook

```typescript
interface ServiceStatus {
  service: 'redis' | 'rtdetr' | 'nemotron';
  status: 'healthy' | 'unhealthy' | 'restarting' | 'restart_failed' | 'failed';
  message?: string;
  timestamp: string;
}

function useServiceStatus(): {
  services: Record<string, ServiceStatus>;
  hasUnhealthy: boolean;
};
```

### ServiceStatusAlert Component

- Shows banner at top of dashboard when any service unhealthy
- Color coded: yellow (restarting), red (failed)
- Auto-dismisses after recovery
- Can be manually dismissed

## Error Handling

- **Restart command fails:** Log error, increment failure count, continue backoff
- **Health check timeout:** Treat as unhealthy
- **Redis down during broadcast:** Catch exception, log, don't crash monitor
- **Restart script hangs:** Subprocess timeout (60s), kill and mark failed
- **Service restarts but fails health check:** Continues retry loop with backoff

## File Locations

**Backend:**

- `backend/services/service_managers.py` - Strategy implementations
- `backend/services/health_monitor.py` - Main monitor service
- `backend/core/config.py` - New settings

**Frontend:**

- `frontend/src/hooks/useServiceStatus.ts` - WebSocket hook
- `frontend/src/components/common/ServiceStatusAlert.tsx` - Alert component

**Scripts:**

- `ai/start_detector.sh` - RT-DETRv2 startup
- `ai/start_nemotron.sh` - Nemotron startup

## Tasks

| ID     | Task                                  | Priority | Labels        |
| ------ | ------------------------------------- | -------- | ------------- |
| a2v.1  | Create ServiceManager abstraction     | P1       | backend       |
| a2v.2  | Create ServiceHealthMonitor service   | P1       | backend       |
| a2v.3  | Add health monitor config settings    | P1       | backend       |
| a2v.4  | Integrate into main.py                | P1       | backend       |
| a2v.12 | Create service startup scripts        | P1       | devops        |
| a2v.5  | Unit tests for ServiceHealthMonitor   | P2       | backend, tdd  |
| a2v.6  | Unit tests for ServiceManager         | P2       | backend, tdd  |
| a2v.7  | Integration tests for health monitor  | P2       | backend, tdd  |
| a2v.8  | Add service status WebSocket listener | P2       | frontend      |
| a2v.9  | Create ServiceStatusAlert component   | P2       | frontend      |
| a2v.10 | Add service status to dashboard       | P2       | frontend      |
| a2v.11 | Frontend tests                        | P3       | frontend, tdd |

## Acceptance Criteria

- All three services (Redis, RT-DETRv2, Nemotron) monitored
- Failed services automatically restart with exponential backoff
- Dashboard shows service status alerts in real-time
- Clean switch between shell/docker via config
- Unit and integration tests with >90% coverage
