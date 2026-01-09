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

The API supports two pagination methods: **cursor-based** (recommended) and **offset-based** (deprecated).

### Cursor-Based Pagination (Recommended)

Cursor-based pagination offers better performance for large datasets by avoiding the performance degradation of OFFSET for large offsets.

| Parameter | Type    | Default | Max  | Description                                          |
| --------- | ------- | ------- | ---- | ---------------------------------------------------- |
| `limit`   | integer | 100     | 1000 | Maximum number of results to return                  |
| `cursor`  | string  | null    | -    | Opaque cursor from previous response's `next_cursor` |

**Request Example:**

```bash
# First request (no cursor)
GET /api/events?limit=50

# Subsequent requests (use next_cursor from previous response)
GET /api/events?limit=50&cursor=eyJpZCI6IDEyMywgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==
```

**Response Format with Cursor:**

```json
{
  "events": [...],
  "count": 150,
  "limit": 50,
  "offset": 0,
  "next_cursor": "eyJpZCI6IDEyMywgImNyZWF0ZWRfYXQiOiAiMjAyNS0xMi0yM1QxMjowMDowMFoifQ==", // pragma: allowlist secret
  "has_more": true,
  "deprecation_warning": null
}
```

**Response Fields:**

| Field                 | Type    | Description                                               |
| --------------------- | ------- | --------------------------------------------------------- |
| `next_cursor`         | string  | Opaque cursor for the next page (null if no more results) |
| `has_more`            | boolean | Whether more results are available                        |
| `deprecation_warning` | string  | Warning message if using deprecated offset pagination     |

**How Cursors Work:**

The cursor is a base64-encoded JSON object containing:

- `id`: The ID of the last item in the current page
- `created_at`: The timestamp of the last item (for tie-breaking)

Cursors are opaque - clients should treat them as strings and pass them back unchanged.

### Offset-Based Pagination (Deprecated)

> **Warning:** Offset pagination is deprecated and will be removed in a future version. Use cursor-based pagination instead.

| Parameter | Type    | Default | Max  | Description                         |
| --------- | ------- | ------- | ---- | ----------------------------------- |
| `limit`   | integer | 100     | 1000 | Maximum number of results to return |
| `offset`  | integer | 0       | -    | Number of results to skip           |

Using offset without cursor triggers a deprecation warning in the response:

```json
{
  "events": [...],
  "count": 150,
  "limit": 50,
  "offset": 50,
  "deprecation_warning": "Offset pagination is deprecated and will be removed in a future version. Please use cursor-based pagination instead by using the 'cursor' parameter with the 'next_cursor' value from the response."
}
```

### Endpoints Supporting Cursor Pagination

The following endpoints support cursor-based pagination:

- `GET /api/events` - Security events
- `GET /api/detections` - Object detections
- `GET /api/audit` - Audit logs
- `GET /api/logs` - System logs

### Pagination Best Practices

1. **Always use cursor pagination** for new integrations
2. **Store the cursor** between requests, not page numbers
3. **Don't modify cursors** - treat them as opaque strings
4. **Check `has_more`** to know when to stop iterating
5. **Handle cursor expiration** - cursors may become invalid if underlying data changes significantly

### Example: Iterating Through All Events

```python
import requests

def get_all_events():
    events = []
    cursor = None

    while True:
        params = {"limit": 100}
        if cursor:
            params["cursor"] = cursor

        response = requests.get("http://localhost:8000/api/events", params=params)
        data = response.json()

        events.extend(data["events"])

        if not data.get("has_more"):
            break

        cursor = data.get("next_cursor")

    return events
```

### Paginated Response Format (Legacy)

For compatibility, the basic response format remains:

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

See [dlq.md](dlq.md) for full documentation.

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

### Entities API

| Method | Endpoint                            | Description                    |
| ------ | ----------------------------------- | ------------------------------ |
| GET    | `/api/entities`                     | List tracked entities          |
| GET    | `/api/entities/{entity_id}`         | Get entity details             |
| GET    | `/api/entities/{entity_id}/history` | Get entity appearance timeline |

See [entities.md](entities.md) for full documentation.

### Enrichment API

| Method | Endpoint                                    | Description                                        |
| ------ | ------------------------------------------- | -------------------------------------------------- |
| GET    | `/api/detections/{detection_id}/enrichment` | Get enrichment data for a single detection         |
| GET    | `/api/events/{event_id}/enrichments`        | Get enrichment data for all detections in an event |

See [enrichment.md](enrichment.md) for full documentation.

### Media API

| Method | Endpoint                                    | Description                          |
| ------ | ------------------------------------------- | ------------------------------------ |
| GET    | `/api/media/cameras/{camera_id}/{filename}` | Serve camera image or video          |
| GET    | `/api/media/thumbnails/{filename}`          | Serve detection thumbnail            |
| GET    | `/api/media/detections/{detection_id}`      | Serve image for a detection          |
| GET    | `/api/media/clips/{filename}`               | Serve event video clip               |
| GET    | `/api/media/{path}`                         | Compatibility route (legacy support) |

See [media.md](media.md) for full documentation.

### Logs API

| Method | Endpoint             | Description               |
| ------ | -------------------- | ------------------------- |
| GET    | `/api/logs`          | List logs with filtering  |
| GET    | `/api/logs/stats`    | Get log statistics        |
| GET    | `/api/logs/{log_id}` | Get specific log entry    |
| POST   | `/api/logs/frontend` | Submit frontend log entry |

See [logs.md](logs.md) for full documentation.

### Zones API

| Method | Endpoint                                   | Description       |
| ------ | ------------------------------------------ | ----------------- |
| GET    | `/api/cameras/{camera_id}/zones`           | List zones        |
| POST   | `/api/cameras/{camera_id}/zones`           | Create zone       |
| GET    | `/api/cameras/{camera_id}/zones/{zone_id}` | Get specific zone |
| PUT    | `/api/cameras/{camera_id}/zones/{zone_id}` | Update zone       |
| DELETE | `/api/cameras/{camera_id}/zones/{zone_id}` | Delete zone       |

See [zones.md](zones.md) for full documentation.

### Audit API

| Method | Endpoint                | Description              |
| ------ | ----------------------- | ------------------------ |
| GET    | `/api/audit`            | List audit entries       |
| GET    | `/api/audit/stats`      | Get audit statistics     |
| GET    | `/api/audit/{audit_id}` | Get specific audit entry |

See [audit.md](audit.md) for full documentation.

### Analytics API

| Method | Endpoint                             | Description                         |
| ------ | ------------------------------------ | ----------------------------------- |
| GET    | `/api/analytics/detection-trends`    | Get detection counts by day         |
| GET    | `/api/analytics/risk-history`        | Get risk score distribution         |
| GET    | `/api/analytics/camera-uptime`       | Get uptime percentage per camera    |
| GET    | `/api/analytics/object-distribution` | Get detection counts by object type |

See [analytics.md](analytics.md) for full documentation.

### Services API (Container Orchestrator)

| Method | Endpoint                              | Description                  |
| ------ | ------------------------------------- | ---------------------------- |
| GET    | `/api/system/services`                | List all managed services    |
| POST   | `/api/system/services/{name}/restart` | Manually restart a service   |
| POST   | `/api/system/services/{name}/enable`  | Re-enable a disabled service |
| POST   | `/api/system/services/{name}/disable` | Disable a service            |
| POST   | `/api/system/services/{name}/start`   | Start a stopped service      |

See [services.md](services.md) for full documentation.

### Notification Preferences API

| Method | Endpoint                                         | Description                            |
| ------ | ------------------------------------------------ | -------------------------------------- |
| GET    | `/api/notification-preferences`                  | Get global notification preferences    |
| PUT    | `/api/notification-preferences`                  | Update global notification preferences |
| GET    | `/api/notification-preferences/cameras`          | Get all camera notification settings   |
| GET    | `/api/notification-preferences/cameras/{id}`     | Get notification setting for a camera  |
| PUT    | `/api/notification-preferences/cameras/{id}`     | Update camera notification setting     |
| GET    | `/api/notification-preferences/quiet-hours`      | Get all quiet hours periods            |
| POST   | `/api/notification-preferences/quiet-hours`      | Create a new quiet hours period        |
| DELETE | `/api/notification-preferences/quiet-hours/{id}` | Delete a quiet hours period            |

See [notification-preferences.md](notification-preferences.md) for full documentation.

### Prompt Configuration API (Database-backed)

| Method | Endpoint                              | Description                             |
| ------ | ------------------------------------- | --------------------------------------- |
| GET    | `/api/ai-audit/prompt-config/{model}` | Get prompt configuration for a model    |
| PUT    | `/api/ai-audit/prompt-config/{model}` | Update prompt configuration for a model |

See [prompts.md](prompts.md) for database-backed prompt management.

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
