# API Overview

> Introduction to the Home Security Intelligence REST and WebSocket APIs.

**Time to read:** ~5 min
**Prerequisites:** None

---

## Base URL

The API is served from the backend service at:

```
http://localhost:8000
```

For production deployments with TLS enabled:

```
https://your-domain:8000
```

## Authentication

By default, the API does **not require authentication**. This is intentional for single-user local deployments.

To enable API key authentication:

1. Set `API_KEY_ENABLED=true` in your `.env` file
2. Add API keys to `API_KEYS=["your-key-here"]`
3. Include the key in requests via `X-API-Key` header

```bash
curl -H "X-API-Key: your-key-here" http://localhost:8000/api/events
```

See [Environment Variable Reference](../config/env-reference.md) for all authentication options.

## Response Format

All API responses are JSON. Successful responses include the requested data:

```json
{
  "events": [...],
  "count": 42,
  "limit": 50,
  "offset": 0
}
```

Error responses follow a consistent format:

```json
{
  "detail": "Event with id 999 not found"
}
```

## Common Query Parameters

Many list endpoints support:

| Parameter | Type | Description                                        |
| --------- | ---- | -------------------------------------------------- |
| `limit`   | int  | Maximum results to return (default: 50, max: 1000) |
| `offset`  | int  | Number of results to skip for pagination           |

## API Groups

The API is organized into these resource groups:

### Core APIs (Documented)

| Group                       | Prefix            | Description                    |
| --------------------------- | ----------------- | ------------------------------ |
| [Cameras](cameras.md)       | `/api/cameras`    | Camera management              |
| [Events](events.md)         | `/api/events`     | Security event access          |
| [Detections](detections.md) | `/api/detections` | Object detection results       |
| [Alerts](alerts.md)         | `/api/alerts`     | Alert rule configuration       |
| [System](system.md)         | `/api/system`     | Health, config, and monitoring |
| [WebSocket](websocket.md)   | `/ws/`            | Real-time streaming            |

### Additional APIs

| Group        | Prefix              | Description                                |
| ------------ | ------------------- | ------------------------------------------ |
| Media        | `/api/media`        | Serve camera images/videos with protection |
| Audit        | `/api/audit`        | Audit log access (admin operations)        |
| DLQ          | `/api/dlq`          | Dead-letter queue inspection and requeue   |
| Logs         | `/api/logs`         | Application log streaming                  |
| Zones        | `/api/zones`        | Detection zone configuration               |
| Notification | `/api/notification` | Push notification settings                 |
| Metrics      | `/api/metrics`      | Prometheus-format metrics export           |
| Admin        | `/api/admin`        | Administrative operations                  |

## Health Endpoints

For container orchestration and monitoring:

| Endpoint                       | Purpose                                |
| ------------------------------ | -------------------------------------- |
| `GET /health`                  | Basic liveness probe                   |
| `GET /ready`                   | Readiness probe with dependency checks |
| `GET /api/system/health`       | Detailed health with service status    |
| `GET /api/system/health/ready` | Detailed readiness with worker status  |

### When to Use Each Health Endpoint

| Endpoint                   | Use Case           | When to Use                                                                    |
| -------------------------- | ------------------ | ------------------------------------------------------------------------------ |
| `/health`                  | Liveness (K8s)     | Container crash detection - restarts container if probe fails                  |
| `/ready`                   | Readiness (K8s)    | Load balancer routing - removes instance from traffic until dependencies ready |
| `/api/system/health`       | Detailed diagnosis | Operator debugging - shows individual service status and error details         |
| `/api/system/health/ready` | Worker diagnosis   | Pipeline debugging - shows worker health and queue status                      |

## Rate Limiting

Rate limiting is enabled by default to protect the API:

| Tier      | Default Limit | Endpoints             |
| --------- | ------------- | --------------------- |
| Standard  | 60 req/min    | Most API endpoints    |
| Media     | 120 req/min   | Image/video serving   |
| Search    | 30 req/min    | Full-text search      |
| WebSocket | 10 conn/min   | WebSocket connections |

Configure via `RATE_LIMIT_*` environment variables.

---

## Next Steps

- [Environment Variable Reference](../config/env-reference.md) - Configuration reference
- [Troubleshooting Index](../troubleshooting/index.md) - API issues

---

## See Also

- [Data Model](../../developer/data-model.md) - Database schema for API objects
- [Alerts](../../developer/alerts.md) - Alert system architecture
- [Glossary](../glossary.md) - API terminology

---

[Back to Operator Hub](../../operator-hub.md) | [Developer Hub](../../developer-hub.md)
