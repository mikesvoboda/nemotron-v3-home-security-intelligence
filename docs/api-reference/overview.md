---
title: API Reference Overview
description: REST API for the Home Security Intelligence system
source_refs:
  - backend/api/routes/
  - backend/api/schemas/
  - backend/main.py
---

# API Reference Overview

The Home Security Intelligence system exposes a REST API for managing cameras, events, detections, system configuration, and alerts. This documentation provides comprehensive reference for all available endpoints.

## Base URL

All API endpoints are relative to the base URL:

```
http://localhost:8000
```

For production deployments, replace `localhost:8000` with your server address.

## Content Types

### Request Content Type

All request bodies must use JSON format:

```
Content-Type: application/json
```

### Response Content Type

All responses are returned in JSON format:

```
Content-Type: application/json
```

Exceptions:

- Media endpoints return image/video content types
- CSV export returns `text/csv`
- Prometheus metrics returns `text/plain`

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

Protected endpoints that require authentication when enabled:

- `PATCH /api/system/config` - Update configuration
- `POST /api/system/cleanup` - Trigger data cleanup
- `POST /api/dlq/requeue/{queue_name}` - Requeue DLQ jobs
- `POST /api/dlq/requeue-all/{queue_name}` - Requeue all DLQ jobs
- `DELETE /api/dlq/{queue_name}` - Clear DLQ

## Error Format

All API errors follow a consistent JSON format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Validation Errors (422)

Validation errors include detailed field-level information:

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

### Common HTTP Status Codes

| Code | Description                                                      |
| ---- | ---------------------------------------------------------------- |
| 200  | Success                                                          |
| 201  | Created - Resource successfully created                          |
| 204  | No Content - Successful deletion                                 |
| 400  | Bad Request - Invalid request format or parameters               |
| 401  | Unauthorized - Missing or invalid API key                        |
| 403  | Forbidden - Access denied to resource                            |
| 404  | Not Found - Resource does not exist                              |
| 416  | Range Not Satisfiable - Invalid Range header for video streaming |
| 422  | Unprocessable Entity - Validation error                          |
| 500  | Internal Server Error - Server-side error                        |
| 503  | Service Unavailable - Service degraded or unhealthy              |

## Pagination

List endpoints support pagination with consistent query parameters:

| Parameter | Type    | Default | Max  | Description                         |
| --------- | ------- | ------- | ---- | ----------------------------------- |
| `limit`   | integer | 50      | 1000 | Maximum number of results to return |
| `offset`  | integer | 0       | -    | Number of results to skip           |

### Paginated Response Format

```json
{
  "events": [...],
  "count": 150,
  "limit": 50,
  "offset": 0
}
```

- The **array field name varies by endpoint** (e.g. `cameras`, `events`, `detections`, `logs`, `rules`).
- `count` - Total number of items matching filters (before pagination)
- `limit` - Applied limit value
- `offset` - Applied offset value

## Date/Time Format

All timestamps use ISO 8601 format with UTC timezone:

```
2025-12-23T12:00:00Z
```

Date filter parameters accept ISO 8601 format:

```
?start_date=2025-12-23T00:00:00Z&end_date=2025-12-24T00:00:00Z
```

## API Endpoints Summary

### Cameras API

| Method | Endpoint                            | Description         |
| ------ | ----------------------------------- | ------------------- |
| GET    | `/api/cameras`                      | List all cameras    |
| GET    | `/api/cameras/{camera_id}`          | Get camera by ID    |
| POST   | `/api/cameras`                      | Create new camera   |
| PATCH  | `/api/cameras/{camera_id}`          | Update camera       |
| DELETE | `/api/cameras/{camera_id}`          | Delete camera       |
| GET    | `/api/cameras/{camera_id}/snapshot` | Get latest snapshot |

See [cameras.md](cameras.md) for full documentation.

### Events API

| Method | Endpoint                            | Description                  |
| ------ | ----------------------------------- | ---------------------------- |
| GET    | `/api/events`                       | List events with filtering   |
| GET    | `/api/events/stats`                 | Get event statistics         |
| GET    | `/api/events/search`                | Full-text search events      |
| GET    | `/api/events/export`                | Export events as CSV         |
| GET    | `/api/events/{event_id}`            | Get event by ID              |
| PATCH  | `/api/events/{event_id}`            | Update event (review status) |
| GET    | `/api/events/{event_id}/detections` | Get detections for event     |

See [events.md](events.md) for full documentation.

### Detections API

| Method | Endpoint                                         | Description                    |
| ------ | ------------------------------------------------ | ------------------------------ |
| GET    | `/api/detections`                                | List detections with filtering |
| GET    | `/api/detections/{detection_id}`                 | Get detection by ID            |
| GET    | `/api/detections/{detection_id}/image`           | Get detection thumbnail        |
| GET    | `/api/detections/{detection_id}/video`           | Stream detection video         |
| GET    | `/api/detections/{detection_id}/video/thumbnail` | Get video thumbnail            |

See [detections.md](detections.md) for full documentation.

### System API

| Method | Endpoint                       | Description                |
| ------ | ------------------------------ | -------------------------- |
| GET    | `/api/system/health`           | Detailed health check      |
| GET    | `/health` (root level)         | Kubernetes liveness probe  |
| GET    | `/ready` (root level)          | Kubernetes readiness probe |
| GET    | `/api/system/health/ready`     | Kubernetes readiness probe |
| GET    | `/api/system/gpu`              | Current GPU statistics     |
| GET    | `/api/system/gpu/history`      | GPU stats time series      |
| GET    | `/api/system/stats`            | System statistics          |
| GET    | `/api/system/config`           | Get configuration          |
| PATCH  | `/api/system/config`           | Update configuration       |
| GET    | `/api/system/telemetry`        | Pipeline telemetry         |
| GET    | `/api/system/pipeline-latency` | Pipeline latency metrics   |
| POST   | `/api/system/cleanup`          | Trigger data cleanup       |
| GET    | `/api/system/severity`         | Severity definitions       |
| GET    | `/api/system/storage`          | Storage statistics         |

See [system.md](system.md) for full documentation.

### Model Zoo API

| Method | Endpoint                                | Description                   |
| ------ | --------------------------------------- | ----------------------------- |
| GET    | `/api/system/models`                    | Get Model Zoo registry        |
| GET    | `/api/system/models/{model_name}`       | Get specific model status     |
| GET    | `/api/system/model-zoo/status`          | Get Model Zoo compact status  |
| GET    | `/api/system/model-zoo/latency/history` | Get model latency time series |

See [model-zoo.md](model-zoo.md) for full documentation.

### Alerts API

| Method | Endpoint                           | Description              |
| ------ | ---------------------------------- | ------------------------ |
| GET    | `/api/alerts/rules`                | List alert rules         |
| POST   | `/api/alerts/rules`                | Create alert rule        |
| GET    | `/api/alerts/rules/{rule_id}`      | Get alert rule           |
| PUT    | `/api/alerts/rules/{rule_id}`      | Update alert rule        |
| DELETE | `/api/alerts/rules/{rule_id}`      | Delete alert rule        |
| POST   | `/api/alerts/rules/{rule_id}/test` | Test rule against events |

See [alerts.md](alerts.md) for full documentation.

### Notification API

| Method | Endpoint                   | Description                    |
| ------ | -------------------------- | ------------------------------ |
| GET    | `/api/notification/config` | Get notification configuration |
| POST   | `/api/notification/test`   | Test notification delivery     |

See [alerts.md](alerts.md) for notification endpoints.

### WebSocket API

| Protocol | Endpoint     | Description               |
| -------- | ------------ | ------------------------- |
| WS       | `/ws/events` | Real-time security events |
| WS       | `/ws/system` | Real-time system status   |

See [websocket.md](websocket.md) for full documentation.

### Dead Letter Queue API

| Method | Endpoint                            | Description        |
| ------ | ----------------------------------- | ------------------ |
| GET    | `/api/dlq/stats`                    | Get DLQ statistics |
| GET    | `/api/dlq/jobs/{queue_name}`        | List jobs in DLQ   |
| POST   | `/api/dlq/requeue/{queue_name}`     | Requeue oldest job |
| POST   | `/api/dlq/requeue-all/{queue_name}` | Requeue all jobs   |
| DELETE | `/api/dlq/{queue_name}`             | Clear DLQ          |

### AI Audit API

| Method | Endpoint                                   | Description                           |
| ------ | ------------------------------------------ | ------------------------------------- |
| GET    | `/api/ai-audit/events/{event_id}`          | Get audit for a specific event        |
| POST   | `/api/ai-audit/events/{event_id}/evaluate` | Trigger full evaluation for an event  |
| GET    | `/api/ai-audit/stats`                      | Get aggregate audit statistics        |
| GET    | `/api/ai-audit/leaderboard`                | Get model leaderboard by contribution |
| GET    | `/api/ai-audit/recommendations`            | Get aggregated prompt recommendations |
| POST   | `/api/ai-audit/batch`                      | Trigger batch audit processing        |

See [ai-audit.md](ai-audit.md) for full documentation.

### Prompt Management API

| Method | Endpoint                                     | Description                                   |
| ------ | -------------------------------------------- | --------------------------------------------- |
| GET    | `/api/ai-audit/prompts`                      | Get all model prompt configurations           |
| GET    | `/api/ai-audit/prompts/{model}`              | Get prompt configuration for a specific model |
| PUT    | `/api/ai-audit/prompts/{model}`              | Update prompt configuration for a model       |
| GET    | `/api/ai-audit/prompts/export`               | Export all prompt configurations              |
| GET    | `/api/ai-audit/prompts/history`              | Get version history for prompts               |
| POST   | `/api/ai-audit/prompts/history/{version_id}` | Restore a specific prompt version             |
| POST   | `/api/ai-audit/prompts/test`                 | Test a prompt configuration                   |
| POST   | `/api/ai-audit/prompts/import`               | Import prompt configurations                  |
| POST   | `/api/ai-audit/prompts/import/preview`       | Preview import changes before applying        |

See [prompts.md](prompts.md) for full documentation.

## Rate Limiting

Rate limiting is implemented via Redis-based sliding window counters. It can be disabled for trusted LAN deployments, but is recommended when the API is reachable beyond localhost.

**Default tiers (per minute):**

- **Standard**: most API endpoints
- **Media**: image/video endpoints (`/api/media/*`, snapshots, thumbnails)
- **Search**: `/api/events/search`
- **WebSocket**: new connections to `/ws/*`

Configure via `RATE_LIMIT_*` environment variables (see `docs/reference/config/env-reference.md` and `docs/RUNTIME_CONFIG.md`).

## CORS

The API allows cross-origin requests from any origin for local development. Production deployments should configure appropriate CORS settings.

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

The OpenAPI specification is available at:

```
GET /openapi.json
```
