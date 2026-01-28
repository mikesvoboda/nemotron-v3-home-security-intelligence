# Service Control

> Start, stop, restart, and monitor services through the dashboard UI.

**Time to read:** ~7 min
**Prerequisites:** System running, dashboard access

---

## Overview

The Services Panel provides a unified interface for monitoring and controlling all system services. It combines real-time WebSocket updates with REST API fallback for reliable service management.

### Service Categories

Services are organized into three categories:

| Category       | Services                                | Purpose                       |
| -------------- | --------------------------------------- | ----------------------------- |
| Infrastructure | PostgreSQL, Redis                       | Data storage and messaging    |
| AI             | YOLO26, Nemotron                        | Object detection and analysis |
| Monitoring     | File Watcher, Batch Aggregator, Cleanup | Pipeline orchestration        |

---

## Service Management UI

### Accessing the Panel

The Services Panel is available on the System page of the dashboard. It displays:

- Category summary bar showing health counts
- Individual service cards with status and controls
- Real-time status updates via WebSocket

### Category Summary Bar

At the top of the panel, badges show health status per category:

```
[Infrastructure 2/2] [AI Services 2/2] [Monitoring 3/3]
```

- **Green badge**: All services healthy
- **Yellow badge**: Some services degraded
- **Red badge**: One or more services unhealthy

### Service Cards

Each service card displays:

| Element        | Description                                 |
| -------------- | ------------------------------------------- |
| Status Icon    | Green check, red X, or yellow warning       |
| Service Name   | Display name with port number if applicable |
| Description    | Brief description of service purpose        |
| Status Badge   | Current status (Healthy, Unhealthy, etc.)   |
| Restart Button | Manually restart the service                |
| Toggle Button  | Enable/disable the service                  |

---

## Service Status States

| Status     | Icon    | Badge Color | Description                             |
| ---------- | ------- | ----------- | --------------------------------------- |
| Healthy    | Check   | Green       | Service running and responding          |
| Unhealthy  | X       | Red         | Service down or not responding          |
| Degraded   | Warning | Yellow      | Service running but experiencing issues |
| Restarting | Spinner | Yellow      | Service is restarting                   |
| Disabled   | -       | Gray        | Service manually disabled               |
| Unknown    | Warning | Gray        | Status cannot be determined             |

---

## Starting and Stopping Services

### Starting a Stopped Service

**Via Dashboard:**

1. Locate the stopped service in the Services Panel
2. The Restart button initiates a start operation
3. Status updates to "Starting" then "Healthy" when ready

**Via API:**

```bash
# Start a specific service
curl -X POST "http://localhost:8000/api/system/services/{name}/start"
```

**Response:**

```json
{
  "success": true,
  "message": "Service 'yolo26' start initiated",
  "service": {
    "name": "yolo26",
    "display_name": "YOLO26",
    "status": "starting",
    ...
  }
}
```

### Disabling a Service

Disabling prevents automatic restarts:

**Via Dashboard:**

1. Click the toggle button (green when enabled)
2. Service status changes to "Disabled"
3. Self-healing restarts are prevented

**Via API:**

```bash
# Disable a service
curl -X POST "http://localhost:8000/api/system/services/{name}/disable"
```

### Enabling a Disabled Service

**Via Dashboard:**

1. Click the toggle button (gray when disabled)
2. Service becomes eligible for self-healing
3. May need manual restart to start immediately

**Via API:**

```bash
# Enable a service
curl -X POST "http://localhost:8000/api/system/services/{name}/enable"
```

---

## Restarting Services

### Manual Restart

**Via Dashboard:**

1. Click the **Restart** button on the service card
2. Confirm the restart in the dialog
3. Status changes to "Restarting"
4. Service recovers to "Healthy" when ready

**Via API:**

```bash
# Restart a specific service
curl -X POST "http://localhost:8000/api/system/services/{name}/restart"
```

### Restart Behavior

When you restart a service:

1. **Confirmation Required**: Dashboard prompts for confirmation
2. **Failure Count Reset**: Manual restarts reset the failure counter
3. **Status Broadcast**: WebSocket notifies all connected clients
4. **Temporary Interruption**: Service is briefly unavailable

### Restart Policies

The container orchestrator implements self-healing restart policies:

| Scenario             | Behavior                                   |
| -------------------- | ------------------------------------------ |
| Health check fails   | Automatic restart with exponential backoff |
| Max failures reached | Service disabled (requires manual enable)  |
| Manual restart       | Failure count reset, immediate restart     |
| Manual disable       | No automatic restarts                      |

---

## Service Health Monitoring

### Real-Time Updates

The Services Panel receives real-time status updates via WebSocket:

- **Service discovered**: When orchestrator finds a new container
- **Health recovered**: When service becomes healthy after failure
- **Health failed**: When health check fails
- **Restart initiated**: When restart begins
- **Restart completed**: When service is back up
- **Service disabled**: When max failures reached or manually disabled
- **Service enabled**: When manually re-enabled

### Polling Fallback

If WebSocket is unavailable, the panel falls back to polling:

- Default interval: 30 seconds
- Configurable via `pollingInterval` prop

### Health Endpoints

```bash
# Overall system health
curl http://localhost:8000/api/system/health

# List all services with status
curl http://localhost:8000/api/system/services

# Filter by category
curl "http://localhost:8000/api/system/services?category=ai"
```

---

## API Reference

### List Services

```bash
GET /api/system/services
GET /api/system/services?category=infrastructure
GET /api/system/services?category=ai
GET /api/system/services?category=monitoring
```

**Response:**

```json
{
  "services": [
    {
      "name": "postgres",
      "display_name": "PostgreSQL",
      "category": "infrastructure",
      "status": "running",
      "enabled": true,
      "container_id": "abc123def456",
      "image": "postgres:16",
      "port": 5432,
      "failure_count": 0,
      "restart_count": 1,
      "last_restart_at": "2025-12-23T10:00:00Z",
      "uptime_seconds": 86400
    }
  ],
  "by_category": {
    "infrastructure": { "total": 2, "healthy": 2, "unhealthy": 0 },
    "ai": { "total": 2, "healthy": 2, "unhealthy": 0 },
    "monitoring": { "total": 3, "healthy": 3, "unhealthy": 0 }
  },
  "timestamp": "2025-12-23T10:30:00Z"
}
```

### Service Actions

| Endpoint                              | Method | Description             |
| ------------------------------------- | ------ | ----------------------- |
| `/api/system/services/{name}/restart` | POST   | Restart service         |
| `/api/system/services/{name}/start`   | POST   | Start stopped service   |
| `/api/system/services/{name}/enable`  | POST   | Enable disabled service |
| `/api/system/services/{name}/disable` | POST   | Disable service         |

### Error Responses

| Status | Description                          |
| ------ | ------------------------------------ |
| 400    | Service is disabled (enable first)   |
| 400    | Service is already running           |
| 404    | Service not found                    |
| 503    | Container orchestrator not available |

---

## Service Definitions

### Infrastructure Services

| Service    | Port | Description                                |
| ---------- | ---- | ------------------------------------------ |
| PostgreSQL | 5432 | Primary database for events and detections |
| Redis      | 6379 | Cache and message queue for pipeline       |

### AI Services

| Service  | Port | Description                              |
| -------- | ---- | ---------------------------------------- |
| YOLO26   | 8095 | Real-time object detection model         |
| Nemotron | 8091 | Risk analysis LLM for security reasoning |

### Monitoring Services

| Service          | Description                                    |
| ---------------- | ---------------------------------------------- |
| File Watcher     | Monitors camera FTP directories for new images |
| Batch Aggregator | Aggregates detections into analysis batches    |
| Cleanup Service  | Removes old data based on retention policy     |

---

## WebSocket Events

Service status changes are broadcast via the `/ws/system` channel:

**Event Structure:**

```json
{
  "type": "service_status",
  "data": {
    "name": "yolo26",
    "display_name": "YOLO26",
    "category": "ai",
    "status": "running",
    "enabled": true,
    "failure_count": 0,
    "restart_count": 5,
    "uptime_seconds": 3600
  },
  "message": "Service recovered"
}
```

**Event Types:**

| Message                  | Meaning                           |
| ------------------------ | --------------------------------- |
| Service discovered       | Container found during discovery  |
| Service recovered        | Health check passed after failure |
| Health check failed      | Service became unhealthy          |
| Manual restart initiated | User triggered restart            |
| Restart completed        | Restart finished successfully     |
| Restart failed           | Restart did not succeed           |
| Service disabled         | Max failures or manual disable    |
| Service enabled          | Manual re-enable                  |
| Service started          | Start operation completed         |

---

## Container Orchestrator

The backend's Container Orchestrator manages service lifecycle:

### Discovery

On startup, the orchestrator:

1. Connects to Docker daemon
2. Discovers containers matching name patterns
3. Registers services in the service registry
4. Loads persisted state from Redis
5. Starts health monitoring

### Health Monitoring

Continuous health checks:

- Configurable check interval
- Automatic restart on failure
- Exponential backoff between restarts
- Max failure threshold before disable

### Self-Healing

When a service fails health check:

1. Orchestrator initiates restart
2. Failure count incremented
3. If count exceeds threshold, service disabled
4. WebSocket broadcast notifies clients

### State Persistence

Service state (failure counts, restart history) is persisted to Redis:

- Survives backend restarts
- Provides accurate failure tracking
- Enables proper backoff timing

---

## Troubleshooting

### Service Won't Start

**Symptoms:** Start button clicked but service remains stopped

**Solutions:**

1. Check if service is disabled (enable first)
2. Verify container image exists
3. Check Docker/Podman daemon is running
4. Review backend logs for errors

### Service Keeps Restarting

**Symptoms:** Service cycles between running and restarting

**Solutions:**

1. Check service logs for crash reason
2. Verify resource availability (GPU memory, disk)
3. Check configuration for errors
4. May need to disable and investigate

### Orchestrator Not Available

**Symptoms:** 503 error when accessing services API

**Solutions:**

1. Verify backend is running
2. Check orchestrator is enabled in settings
3. Verify Docker socket is accessible
4. Review backend startup logs

### WebSocket Not Updating

**Symptoms:** Status changes not reflected in real-time

**Solutions:**

1. Check WebSocket connection status
2. Refresh the page
3. Verify backend is healthy
4. Polling fallback should still work

---

## Configuration Reference

| Variable                      | Default | Description                   |
| ----------------------------- | ------- | ----------------------------- |
| `ORCHESTRATOR_ENABLED`        | true    | Enable container orchestrator |
| `HEALTH_CHECK_INTERVAL`       | 30s     | Seconds between health checks |
| `MAX_FAILURES_BEFORE_DISABLE` | 5       | Failures before auto-disable  |

---

## Related Documentation

- [AI Services](ai-services.md) - Starting, stopping AI services
- [Monitoring Guide](monitoring.md) - System health monitoring
- [WebSocket API](../developer/api/realtime.md) - Real-time events
- [Troubleshooting](../reference/troubleshooting/index.md) - Common issues

---

[Back to Operator Hub](./)
