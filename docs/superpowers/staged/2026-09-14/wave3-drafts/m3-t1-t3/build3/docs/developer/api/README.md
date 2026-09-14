# API Reference

The Home Security Intelligence system exposes a comprehensive REST API for managing cameras, events, detections, AI pipeline operations, and system configuration.

## Base URL

```
http://localhost:8000
```

For production deployments, replace `localhost:8000` with your server address.

## Interactive Documentation

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Spec:** `GET /openapi.json`

## Authentication

The API supports optional API key authentication. When enabled (`API_KEY_ENABLED=true`), provide the API key via:

**HTTP Header (preferred):**

```
X-API-Key: your-api-key
```

**Query Parameter (fallback):**

```
?api_key=your-api-key
```

Protected endpoints requiring authentication:

- `PATCH /api/system/config` - Update configuration
- `POST /api/system/cleanup` - Trigger data cleanup
- `POST /api/dlq/requeue/{queue_name}` - Requeue DLQ jobs
- `DELETE /api/dlq/{queue_name}` - Clear DLQ

## Content Types

**Requests:** `Content-Type: application/json`

**Responses:** `Content-Type: application/json`

Exceptions:

- Media endpoints return `image/*` or `video/*`
- CSV export returns `text/csv`
- Prometheus metrics returns `text/plain`

## Pagination

The API supports two pagination methods:

### Cursor-Based Pagination (Recommended)

| Parameter | Type    | Default | Max  | Description                      |
| --------- | ------- | ------- | ---- | -------------------------------- |
| `limit`   | integer | 100     | 1000 | Maximum results to return        |
| `cursor`  | string  | null    | -    | Opaque cursor from `next_cursor` |

**Example:**

```bash
# First request
GET /api/events?limit=50

# Subsequent requests
GET /api/events?limit=50&cursor=eyJpZCI6IDEyM30=
```

**Response:**

```json
{
  "events": [...],
  "count": 150,
  "limit": 50,
  "next_cursor": "eyJpZCI6IDEyM30=",
  "has_more": true
}
```

### Offset-Based Pagination (Deprecated)

| Parameter | Type    | Default | Description     |
| --------- | ------- | ------- | --------------- |
| `limit`   | integer | 100     | Maximum results |
| `offset`  | integer | 0       | Number to skip  |

Using offset triggers a deprecation warning in responses.

## Error Handling

All errors follow a consistent JSON format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Validation Errors (422):**

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### HTTP Status Codes

| Code | Description                            |
| ---- | -------------------------------------- |
| 200  | Success                                |
| 201  | Created - Resource created             |
| 204  | No Content - Successful deletion       |
| 400  | Bad Request - Invalid parameters       |
| 401  | Unauthorized - Invalid/missing API key |
| 403  | Forbidden - Access denied              |
| 404  | Not Found - Resource doesn't exist     |
| 416  | Range Not Satisfiable - Invalid Range  |
| 422  | Unprocessable Entity - Validation      |
| 500  | Internal Server Error                  |
| 503  | Service Unavailable - Degraded         |

## Date/Time Format

All timestamps use ISO 8601 format with UTC timezone:

```
2025-12-23T12:00:00Z
```

Date filter parameters accept ISO 8601 format:

```
?start_date=2025-12-23T00:00:00Z&end_date=2025-12-24T00:00:00Z
```

## Rate Limiting

Rate limiting uses Redis-based sliding window counters:

| Tier      | Scope                      |
| --------- | -------------------------- |
| Standard  | Most API endpoints         |
| Media     | `/api/media/*`, snapshots  |
| Search    | `/api/events/search`       |
| WebSocket | New connections to `/ws/*` |

Configure via `RATE_LIMIT_*` environment variables.

## API Domain Guides

The API is organized into domain-specific guides:

| Guide                                     | Description                                             |
| ----------------------------------------- | ------------------------------------------------------- |
| [Core Resources](core-resources.md)       | Cameras, events, detections, zones, entities, analytics |
| [AI Pipeline](ai-pipeline.md)             | Enrichment, batches, AI audit, dead letter queue        |
| [System Operations](system-ops.md)        | Health, config, alerts, logs, notifications             |
| [System Monitoring](system-monitoring.md) | Worker supervisor, pipeline status, Prometheus          |
| [Real-time](realtime.md)                  | WebSocket streams for events and system status          |
| [Calibration](calibration.md)             | User risk threshold calibration                         |
| [Webhooks](webhooks.md)                   | External system integrations (Alertmanager)             |

## Quick Reference

### Cameras

| Method | Endpoint                     | Description         |
| ------ | ---------------------------- | ------------------- |
| GET    | `/api/cameras`               | List all cameras    |
| GET    | `/api/cameras/{id}`          | Get camera by ID    |
| POST   | `/api/cameras`               | Create camera       |
| PATCH  | `/api/cameras/{id}`          | Update camera       |
| DELETE | `/api/cameras/{id}`          | Delete camera       |
| GET    | `/api/cameras/{id}/snapshot` | Get latest snapshot |

### Events

| Method | Endpoint             | Description           |
| ------ | -------------------- | --------------------- |
| GET    | `/api/events`        | List events           |
| GET    | `/api/events/{id}`   | Get event by ID       |
| PATCH  | `/api/events/{id}`   | Update event (review) |
| GET    | `/api/events/stats`  | Event statistics      |
| GET    | `/api/events/search` | Full-text search      |
| GET    | `/api/events/export` | Export as CSV         |

### Detections

| Method | Endpoint                          | Description         |
| ------ | --------------------------------- | ------------------- |
| GET    | `/api/detections`                 | List detections     |
| GET    | `/api/detections/{id}`            | Get detection by ID |
| GET    | `/api/detections/{id}/image`      | Get thumbnail       |
| GET    | `/api/detections/{id}/video`      | Stream video        |
| GET    | `/api/detections/{id}/enrichment` | Get enrichment data |
| GET    | `/api/detections/export`          | Export as CSV/JSON  |

### System

| Method | Endpoint                   | Description           |
| ------ | -------------------------- | --------------------- |
| GET    | `/api/system/health`       | Detailed health check |
| GET    | `/health`                  | Liveness probe        |
| GET    | `/api/system/health/ready` | Readiness probe       |
| GET    | `/api/system/gpu`          | GPU statistics        |
| GET    | `/api/system/config`       | Get configuration     |
| PATCH  | `/api/system/config`       | Update configuration  |

### Real-time

| Protocol | Endpoint                 | Description                   |
| -------- | ------------------------ | ----------------------------- |
| WS       | `/ws/events`             | Security event stream         |
| WS       | `/ws/system`             | System status stream          |
| WS       | `/ws/detections`         | Real-time AI detection stream |
| WS       | `/ws/jobs/{job_id}/logs` | Job log streaming             |

### Calibration

| Method | Endpoint                    | Description                    |
| ------ | --------------------------- | ------------------------------ |
| GET    | `/api/calibration`          | Get risk threshold calibration |
| PUT    | `/api/calibration`          | Update calibration thresholds  |
| PATCH  | `/api/calibration`          | Partial calibration update     |
| POST   | `/api/calibration/reset`    | Reset to default thresholds    |
| GET    | `/api/calibration/defaults` | Get default threshold values   |

### Webhooks

| Method | Endpoint               | Description                   |
| ------ | ---------------------- | ----------------------------- |
| POST   | `/api/webhooks/alerts` | Receive Alertmanager webhooks |
