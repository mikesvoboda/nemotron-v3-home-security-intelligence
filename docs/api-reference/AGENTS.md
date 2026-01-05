# API Reference Directory - Agent Guide

## Purpose

This directory contains complete REST and WebSocket API documentation for the Home Security Intelligence system. This is the **canonical/authoritative location** for API documentation. These references are for developers integrating with or extending the system's APIs.

## Directory Contents

```
api-reference/
  AGENTS.md        # This file
  overview.md      # API overview and conventions
  alerts.md        # Alert rules API
  ai-audit.md      # AI audit API (placeholder - empty)
  audit.md         # Audit logging API
  cameras.md       # Cameras API
  detections.md    # Detections API
  dlq.md           # Dead Letter Queue API
  enrichment.md    # Prompt enrichment API
  entities.md      # Entity tracking API
  events.md        # Events API (placeholder - empty)
  logs.md          # Logs API
  media.md         # Media serving API
  model-zoo.md     # Model Zoo API (placeholder - empty)
  prompts.md       # Prompt management API
  system.md        # System API
  websocket.md     # WebSocket API
  zones.md         # Zones API
```

**Note:** Some files (ai-audit.md, events.md, model-zoo.md) are placeholders (0 bytes) awaiting content.

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

**When to use:** Configuring automated alerts based on event criteria.

### audit.md

**Purpose:** Audit logging API for tracking system activities.

**Topics Covered:**

- Audit log queries
- Event filtering by action, user, timestamp
- Retention and archival

**When to use:** Compliance, security audits, activity tracking.

### cameras.md

**Purpose:** Camera management API reference.

**Endpoints:**

- `GET /api/cameras` - List cameras
- `POST /api/cameras` - Create camera
- `GET /api/cameras/{id}` - Get camera by ID
- `PUT /api/cameras/{id}` - Update camera
- `DELETE /api/cameras/{id}` - Delete camera
- `GET /api/cameras/{id}/status` - Get camera status

**When to use:** Managing camera configurations programmatically.

### detections.md

**Purpose:** Object detection results API reference.

**Endpoints:**

- `GET /api/detections` - List detections with filtering
- `GET /api/detections/{id}` - Get detection by ID
- `GET /api/detections/{id}/image` - Get image with bounding box overlay

**When to use:** Querying raw detection data from RT-DETRv2.

### dlq.md

**Purpose:** Dead Letter Queue (DLQ) management API.

**Topics Covered:**

- Viewing failed jobs
- Retrying failed jobs
- Purging DLQ entries
- DLQ statistics

**When to use:** Managing and recovering from pipeline failures.

### enrichment.md

**Purpose:** Prompt enrichment API for AI context enhancement.

**Topics Covered:**

- Enrichment configuration
- Vision extraction settings
- Enrichment statistics

**When to use:** Configuring how prompts are enriched with additional context.

### entities.md

**Purpose:** Entity tracking API for object persistence across detections.

**Topics Covered:**

- Entity queries
- Entity linking and merging
- Entity statistics

**When to use:** Tracking the same object across multiple detections.

### logs.md

**Purpose:** Application logs API.

**Topics Covered:**

- Log retrieval and filtering
- Log levels
- Log export

**When to use:** Debugging, monitoring, and audit trails.

### media.md

**Purpose:** Media serving API for images and videos.

**Endpoints:**

- `GET /api/media/{path}` - Serve images/videos
- `GET /api/media/thumbnail/{id}` - Serve thumbnails

**When to use:** Retrieving detection images and event media.

### prompts.md

**Purpose:** Prompt management API for AI analysis configuration.

**Topics Covered:**

- Prompt templates
- Custom prompts
- Prompt testing

**When to use:** Customizing AI analysis behavior.

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

### zones.md

**Purpose:** Zone management API for spatial intelligence.

**Topics Covered:**

- Zone CRUD operations
- Zone-based filtering
- Zone statistics

**When to use:** Defining areas of interest within camera views.

## Placeholder Files

The following files exist but are empty (0 bytes) and awaiting content:

- **ai-audit.md** - AI audit trail API (planned)
- **events.md** - Events API (content needed)
- **model-zoo.md** - Model Zoo API (planned)

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
| **Frontend Devs**    | Event display, real-time updates | system.md, websocket.md |
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

- **docs/AGENTS.md:** Documentation directory overview
- **docs/reference/api/:** Alternative API reference (historical)
- **docs/reference/config/env-reference.md:** API configuration variables
- **docs/reference/glossary.md:** API terminology
- **backend/api/routes/AGENTS.md:** Route implementation details
- **backend/api/schemas/AGENTS.md:** Pydantic schema definitions
