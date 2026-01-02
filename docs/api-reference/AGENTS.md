# API Reference Directory - Agent Guide

## Purpose

This directory contains comprehensive API documentation for the Home Security Intelligence system. These references are for developers integrating with or extending the system's APIs.

> **Canonical location:** `docs/api-reference/`
>
> A second copy exists at `docs/reference/api/` (historical). To avoid drift, treat `docs/api-reference/` as the source of truth.

## Directory Contents

```
api-reference/
  AGENTS.md        # This file
  overview.md      # API overview and conventions
  alerts.md        # Alerts API reference
  cameras.md       # Cameras API reference
  detections.md    # Detections API reference
  events.md        # Events API reference
  system.md        # System API reference
  websocket.md     # WebSocket API reference
```

## Key Files

### overview.md

**Purpose:** API overview and common conventions.

**Topics Covered:**

- Base URL and versioning
- Authentication (if applicable)
- Request/response format (JSON)
- Error handling and status codes
- Pagination conventions
- Rate limiting

**When to use:** Starting to use any API, understanding common patterns.

### alerts.md

**Purpose:** Alerts API reference.

**Endpoints:**

- `GET /api/alerts/rules` - List alert rules
- `POST /api/alerts/rules` - Create alert rule
- `GET /api/alerts/rules/{rule_id}` - Get alert rule
- `PUT /api/alerts/rules/{rule_id}` - Update alert rule
- `DELETE /api/alerts/rules/{rule_id}` - Delete alert rule
- `POST /api/alerts/rules/{rule_id}/test` - Test rule against historical events
- `GET /api/notification/config` - Get notification configuration
- `POST /api/notification/test` - Test notification delivery

**When to use:** Working with alert management features.

### cameras.md

**Purpose:** Cameras API reference.

**Endpoints:**

- `GET /api/cameras` - List cameras
- `GET /api/cameras/{camera_id}` - Get camera by ID
- `POST /api/cameras` - Create camera
- `PATCH /api/cameras/{camera_id}` - Update camera
- `DELETE /api/cameras/{camera_id}` - Delete camera
- `GET /api/cameras/{camera_id}/snapshot` - Get latest snapshot image

**When to use:** Managing camera configurations.

### detections.md

**Purpose:** Detections API reference.

**Endpoints:**

- `GET /api/detections` - List detections
- `GET /api/detections/{detection_id}` - Get detection by ID
- `GET /api/detections/{detection_id}/image` - Get detection thumbnail
- `GET /api/detections/{detection_id}/video` - Stream detection video
- `GET /api/detections/{detection_id}/video/thumbnail` - Get video thumbnail frame

**When to use:** Querying object detection results.

### events.md

**Purpose:** Events API reference.

**Endpoints:**

- `GET /api/events` - List events with filtering
- `GET /api/events/stats` - Get event statistics
- `GET /api/events/search` - Full-text search
- `GET /api/events/export` - CSV export
- `GET /api/events/{event_id}` - Get event by ID
- `PATCH /api/events/{event_id}` - Update event (review/notes)
- `GET /api/events/{event_id}/detections` - Get detections for event

**When to use:** Querying security events and their associated data.

### system.md

**Purpose:** System API reference.

**Endpoints:**

- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe (root-level)
- `GET /api/system/health` - Detailed health check
- `GET /api/system/health/ready` - Detailed readiness
- `GET /api/system/gpu` - GPU statistics
- `GET /api/system/gpu/history` - GPU history
- `GET /api/system/stats` - System counters/uptime
- `GET /api/system/config` - Public config
- `PATCH /api/system/config` - Update config (requires API key when enabled)
- `GET /api/system/telemetry` - Pipeline telemetry
- `GET /api/system/pipeline-latency` - Pipeline latency percentiles
- `POST /api/system/cleanup` - Trigger cleanup (requires API key when enabled)
- `GET /api/system/severity` - Severity definitions
- `GET /api/system/storage` - Storage stats
- `GET /api/system/circuit-breakers` - Circuit breaker status
- `GET /api/system/pipeline` - Pipeline status
- `GET /api/system/cleanup/status` - Cleanup job status

**When to use:** Monitoring system health, managing configuration.

### websocket.md

**Purpose:** WebSocket API reference.

**Channels:**

- `/ws/events` - Real-time event and detection updates
- `/ws/system` - System status and GPU stats updates

**Topics Covered:**

- Connection establishment
- Message formats
- Subscription patterns
- Reconnection handling

**When to use:** Implementing real-time features, building custom dashboards.

## API Conventions

### Request Format

All requests use JSON:

```http
Content-Type: application/json
```

### Response Format

This API intentionally uses **resource-shaped responses** (e.g. `{ "events": [...] }`) rather than a single global `{data, meta}` wrapper. See `overview.md` for common pagination conventions.

### Error Format

Errors follow FastAPI’s standard shape:

```json
{ "detail": "Error message" }
```

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture details
- **backend/api/routes/AGENTS.md:** Route implementation details
- **backend/api/schemas/AGENTS.md:** Pydantic schema definitions
