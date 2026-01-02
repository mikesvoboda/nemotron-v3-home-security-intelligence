# API Reference Directory - Agent Guide

## Purpose

This directory contains complete REST and WebSocket API documentation for the Home Security Intelligence system. These references are for developers integrating with or extending the system's APIs.

## Directory Contents

```
api/
  AGENTS.md        # This file
  overview.md      # API overview and conventions
  alerts.md        # Alert rules API
  cameras.md       # Cameras API
  detections.md    # Detections API
  events.md        # Events API
  system.md        # System API
  websocket.md     # WebSocket API
```

## Key Files

### overview.md

**Purpose:** API overview and common conventions.

**Topics Covered:**

- Base URL (`http://localhost:8000`)
- Authentication (optional API key)
- Response format (JSON)
- Error format and status codes
- Common query parameters (limit, offset)
- API groups and organization
- Health endpoints for monitoring
- Rate limiting tiers

**When to use:** Before using any API, understanding common patterns.

### alerts.md

**Purpose:** Alert rule management API reference.

**Endpoints:**

- `GET /api/alerts/rules` - List alert rules
- `POST /api/alerts/rules` - Create rule
- `GET /api/alerts/rules/{id}` - Get rule by ID
- `PUT /api/alerts/rules/{id}` - Update rule
- `DELETE /api/alerts/rules/{id}` - Delete rule
- `POST /api/alerts/rules/{id}/test` - Test rule against events

**Key Concepts:**

- Rule filtering (risk threshold, object types, cameras, zones)
- Schedule-based activation
- Deduplication and cooldown
- Notification channels (email, webhook)

**When to use:** Configuring automated alerts based on event criteria.

### cameras.md

**Purpose:** Camera management API reference.

**Endpoints:**

- `GET /api/cameras` - List cameras
- `POST /api/cameras` - Create camera
- `GET /api/cameras/{id}` - Get camera by ID
- `PUT /api/cameras/{id}` - Update camera
- `DELETE /api/cameras/{id}` - Delete camera
- `GET /api/cameras/{id}/status` - Get camera status

**Key Concepts:**

- Camera folder path mapping
- Status tracking (online, offline, error)
- Last seen timestamps

**When to use:** Managing camera configurations programmatically.

### detections.md

**Purpose:** Object detection results API reference.

**Endpoints:**

- `GET /api/detections` - List detections with filtering
- `GET /api/detections/{id}` - Get detection by ID
- `GET /api/detections/{id}/image` - Get image with bounding box overlay

**Key Concepts:**

- Detection attributes (object type, confidence, bounding box)
- Filtering by camera, time range, object type
- Image rendering with detection overlay

**When to use:** Querying raw detection data from RT-DETRv2.

### events.md

**Purpose:** Security event API reference.

**Endpoints:**

- `GET /api/events` - List events with filtering
- `GET /api/events/{id}` - Get event by ID
- `GET /api/events/{id}/detections` - Get event's detections
- `GET /api/events/stats` - Get event statistics
- `PUT /api/events/{id}` - Update event (mark reviewed, add notes)

**Key Concepts:**

- Event contains multiple detections
- Risk score and risk level from Nemotron
- AI-generated summary and reasoning
- Review status tracking

**When to use:** Querying security events and their analysis.

### system.md

**Purpose:** System management and monitoring API reference.

**Endpoints:**

- `GET /health` - Basic liveness probe
- `GET /ready` - Readiness probe
- `GET /api/system/health` - Detailed health status
- `GET /api/system/health/ready` - Worker status
- `GET /api/system/config` - System configuration
- `GET /api/system/gpu` - GPU statistics
- `GET /api/system/pipeline` - Pipeline status
- `GET /api/system/telemetry` - Queue depths, rate limits
- `GET /api/system/circuit-breakers` - Circuit breaker status
- `POST /api/system/cleanup` - Trigger data cleanup

**Key Concepts:**

- Service health (database, Redis, AI services)
- Worker status (detection, analysis, cleanup)
- Circuit breaker states
- Pipeline and queue monitoring

**When to use:** Monitoring system health, debugging issues, administration.

### websocket.md

**Purpose:** Real-time WebSocket API reference.

**Channels:**

- `/ws/events` - Security event and detection updates
- `/ws/system` - System status and GPU stats

**Topics Covered:**

- Connection establishment
- Message envelope format
- Event types and payloads
- Subscription patterns
- Reconnection handling
- Heartbeat/ping-pong

**When to use:** Implementing real-time dashboards, notifications.

## API Conventions

### Request Format

All requests use JSON:

```http
Content-Type: application/json
```

### Response Format

Successful responses return JSON with data:

```json
{
  "events": [...],
  "count": 42,
  "limit": 50,
  "offset": 0
}
```

### Error Format

Errors return appropriate HTTP status with detail:

```json
{
  "detail": "Event with id 999 not found"
}
```

### Pagination

List endpoints support:

| Parameter | Type | Default | Max  | Description           |
| --------- | ---- | ------- | ---- | --------------------- |
| `limit`   | int  | 50      | 1000 | Max results to return |
| `offset`  | int  | 0       | -    | Results to skip       |

## Target Audiences

| Audience             | Needs                            | Primary Documents       |
| -------------------- | -------------------------------- | ----------------------- |
| **Frontend Devs**    | Event display, real-time updates | events.md, websocket.md |
| **Integration Devs** | Third-party integrations         | overview.md, alerts.md  |
| **Operators**        | Monitoring, administration       | system.md               |
| **Mobile Devs**      | API consumption, notifications   | All files               |

## Interactive API Docs

When the backend is running, interactive Swagger UI is available at:

```
http://localhost:8000/docs
```

This provides:

- Try-it-now functionality
- Auto-generated request examples
- Response schema documentation

## Related Documentation

- **docs/reference/AGENTS.md:** Reference directory overview
- **docs/reference/config/env-reference.md:** API configuration variables
- **docs/reference/glossary.md:** API terminology
- **backend/api/routes/AGENTS.md:** Route implementation details
- **backend/api/schemas/AGENTS.md:** Pydantic schema definitions
