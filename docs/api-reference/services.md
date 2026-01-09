---
title: Services API
description: API endpoints for container orchestrator service management
source_refs:
  - backend/api/routes/services.py
  - backend/api/schemas/services.py
---

# Services API

The Services API provides endpoints for managing container-based services through the container orchestrator. It allows listing service status, performing manual restarts, and enabling/disabling services.

## Base URL

```
/api/system/services
```

## Service Categories

Services are organized into categories:

| Category         | Description                                 |
| ---------------- | ------------------------------------------- |
| `infrastructure` | Core services (PostgreSQL, Redis, etc.)     |
| `ai`             | AI model services (RT-DETR, Nemotron, etc.) |
| `monitoring`     | Monitoring services (Prometheus, Grafana)   |

## Service Statuses

| Status      | Description                                      |
| ----------- | ------------------------------------------------ |
| `running`   | Service is healthy and running                   |
| `stopped`   | Service container is stopped                     |
| `starting`  | Service is starting up                           |
| `unhealthy` | Service is running but health checks are failing |
| `disabled`  | Service has been manually disabled               |

## Endpoints

### List Services

```
GET /api/system/services
```

Returns status of all managed services with optional category filtering.

#### Query Parameters

| Parameter  | Type   | Required | Description                                               |
| ---------- | ------ | -------- | --------------------------------------------------------- |
| `category` | string | No       | Filter by category (`infrastructure`, `ai`, `monitoring`) |

#### Response

```json
{
  "services": [
    {
      "name": "rtdetr",
      "display_name": "RT-DETR Object Detection",
      "category": "ai",
      "status": "running",
      "enabled": true,
      "container_id": "a1b2c3d4e5f6",
      "image": "ghcr.io/org/rtdetr:latest",
      "port": 8001,
      "failure_count": 0,
      "restart_count": 2,
      "last_restart_at": "2025-12-23T10:30:00Z",
      "uptime_seconds": 86400
    },
    {
      "name": "nemotron",
      "display_name": "Nemotron LLM",
      "category": "ai",
      "status": "running",
      "enabled": true,
      "container_id": "b2c3d4e5f6g7",
      "image": "ghcr.io/org/nemotron:latest",
      "port": 8002,
      "failure_count": 0,
      "restart_count": 0,
      "last_restart_at": null,
      "uptime_seconds": 172800
    }
  ],
  "by_category": {
    "infrastructure": {
      "total": 3,
      "healthy": 3,
      "unhealthy": 0
    },
    "ai": {
      "total": 5,
      "healthy": 4,
      "unhealthy": 1
    },
    "monitoring": {
      "total": 2,
      "healthy": 2,
      "unhealthy": 0
    }
  },
  "timestamp": "2025-12-23T12:00:00Z"
}
```

#### Response Fields

| Field                        | Type     | Description                               |
| ---------------------------- | -------- | ----------------------------------------- |
| `services`                   | array    | List of service information               |
| `services[].name`            | string   | Service identifier                        |
| `services[].display_name`    | string   | Human-readable service name               |
| `services[].category`        | string   | Service category                          |
| `services[].status`          | string   | Current service status                    |
| `services[].enabled`         | boolean  | Whether service is enabled                |
| `services[].container_id`    | string   | First 12 chars of container ID            |
| `services[].image`           | string   | Container image name                      |
| `services[].port`            | int      | Service port                              |
| `services[].failure_count`   | int      | Number of failures since last reset       |
| `services[].restart_count`   | int      | Total restart count                       |
| `services[].last_restart_at` | datetime | Timestamp of last restart (null if never) |
| `services[].uptime_seconds`  | int      | Uptime in seconds (null if not running)   |
| `by_category`                | object   | Category summaries                        |
| `by_category[].total`        | int      | Total services in category                |
| `by_category[].healthy`      | int      | Healthy services in category              |
| `by_category[].unhealthy`    | int      | Unhealthy services in category            |
| `timestamp`                  | datetime | Response timestamp                        |

#### Error Responses

| Status | Description                          |
| ------ | ------------------------------------ |
| 503    | Container orchestrator not available |
| 500    | Internal server error                |

---

### Restart Service

```
POST /api/system/services/{name}/restart
```

Manually restart a service. Resets the failure count (manual restart is intentional).

#### Path Parameters

| Parameter | Type   | Description             |
| --------- | ------ | ----------------------- |
| `name`    | string | Service name to restart |

#### Response

```json
{
  "success": true,
  "message": "Service 'rtdetr' restart initiated",
  "service": {
    "name": "rtdetr",
    "display_name": "RT-DETR Object Detection",
    "category": "ai",
    "status": "starting",
    "enabled": true,
    "container_id": null,
    "image": "ghcr.io/org/rtdetr:latest",
    "port": 8001,
    "failure_count": 0,
    "restart_count": 3,
    "last_restart_at": "2025-12-23T12:00:00Z",
    "uptime_seconds": null
  }
}
```

#### Error Responses

| Status | Description                          |
| ------ | ------------------------------------ |
| 400    | Bad request - Service is disabled    |
| 404    | Service not found                    |
| 503    | Container orchestrator not available |
| 500    | Internal server error                |

---

### Enable Service

```
POST /api/system/services/{name}/enable
```

Re-enable a disabled service. Resets failure count and allows self-healing to resume.

#### Path Parameters

| Parameter | Type   | Description            |
| --------- | ------ | ---------------------- |
| `name`    | string | Service name to enable |

#### Response

```json
{
  "success": true,
  "message": "Service 'rtdetr' enabled",
  "service": {
    "name": "rtdetr",
    "status": "stopped",
    "enabled": true,
    "failure_count": 0
  }
}
```

#### Error Responses

| Status | Description                          |
| ------ | ------------------------------------ |
| 404    | Service not found                    |
| 503    | Container orchestrator not available |
| 500    | Internal server error                |

---

### Disable Service

```
POST /api/system/services/{name}/disable
```

Manually disable a service. Prevents self-healing restarts.

#### Path Parameters

| Parameter | Type   | Description             |
| --------- | ------ | ----------------------- |
| `name`    | string | Service name to disable |

#### Response

```json
{
  "success": true,
  "message": "Service 'rtdetr' disabled",
  "service": {
    "name": "rtdetr",
    "status": "disabled",
    "enabled": false
  }
}
```

#### Error Responses

| Status | Description                          |
| ------ | ------------------------------------ |
| 404    | Service not found                    |
| 503    | Container orchestrator not available |
| 500    | Internal server error                |

---

### Start Service

```
POST /api/system/services/{name}/start
```

Start a stopped service container.

#### Path Parameters

| Parameter | Type   | Description           |
| --------- | ------ | --------------------- |
| `name`    | string | Service name to start |

#### Response

```json
{
  "success": true,
  "message": "Service 'rtdetr' start initiated",
  "service": {
    "name": "rtdetr",
    "status": "starting",
    "enabled": true
  }
}
```

#### Error Responses

| Status | Description                                       |
| ------ | ------------------------------------------------- |
| 400    | Bad request - Service already running or disabled |
| 404    | Service not found                                 |
| 503    | Container orchestrator not available              |
| 500    | Internal server error                             |

---

## Usage Examples

### Python Example: Monitoring Service Health

```python
import requests

def check_ai_services():
    response = requests.get(
        "http://localhost:8000/api/system/services",
        params={"category": "ai"}
    )
    data = response.json()

    unhealthy = [s for s in data['services'] if s['status'] != 'running']

    if unhealthy:
        print(f"Unhealthy AI services: {[s['name'] for s in unhealthy]}")
        for service in unhealthy:
            print(f"  - {service['display_name']}: {service['status']}")
    else:
        print("All AI services are healthy")

    return data['by_category']['ai']
```

### JavaScript Example: Restarting a Service

```javascript
async function restartService(serviceName) {
  try {
    const response = await fetch(`/api/system/services/${serviceName}/restart`, { method: 'POST' });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to restart service');
    }

    const result = await response.json();
    console.log(result.message);
    return result.service;
  } catch (error) {
    console.error(`Error restarting ${serviceName}:`, error);
    throw error;
  }
}
```

### cURL Example: Disabling a Service

```bash
# Disable the nemotron service
curl -X POST http://localhost:8000/api/system/services/nemotron/disable

# Re-enable it later
curl -X POST http://localhost:8000/api/system/services/nemotron/enable
```

## Related Documentation

- [System API](system.md) - System health and GPU status
- [DLQ API](dlq.md) - Dead letter queue management
- [Architecture: Resilience](../architecture/resilience.md) - Self-healing patterns
