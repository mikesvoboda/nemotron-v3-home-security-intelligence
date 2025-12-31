# API Reference Directory - Agent Guide

## Purpose

This directory contains comprehensive API documentation for the Home Security Intelligence system. These references are for developers integrating with or extending the system's APIs.

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

- `GET /api/v1/alerts` - List alerts
- `GET /api/v1/alerts/{id}` - Get alert by ID
- `POST /api/v1/alerts` - Create alert
- `PUT /api/v1/alerts/{id}` - Update alert
- `DELETE /api/v1/alerts/{id}` - Delete alert
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge alert

**When to use:** Working with alert management features.

### cameras.md

**Purpose:** Cameras API reference.

**Endpoints:**

- `GET /api/v1/cameras` - List cameras
- `GET /api/v1/cameras/{id}` - Get camera by ID
- `POST /api/v1/cameras` - Create camera
- `PUT /api/v1/cameras/{id}` - Update camera
- `DELETE /api/v1/cameras/{id}` - Delete camera
- `GET /api/v1/cameras/{id}/status` - Get camera status

**When to use:** Managing camera configurations.

### detections.md

**Purpose:** Detections API reference.

**Endpoints:**

- `GET /api/v1/detections` - List detections
- `GET /api/v1/detections/{id}` - Get detection by ID
- `GET /api/v1/detections/{id}/image` - Get detection image with bounding box

**When to use:** Querying object detection results.

### events.md

**Purpose:** Events API reference.

**Endpoints:**

- `GET /api/v1/events` - List events with filtering
- `GET /api/v1/events/{id}` - Get event by ID
- `GET /api/v1/events/{id}/detections` - Get event detections
- `GET /api/v1/events/stats` - Get event statistics

**When to use:** Querying security events and their associated data.

### system.md

**Purpose:** System API reference.

**Endpoints:**

- `GET /api/v1/system/health` - Health check
- `GET /api/v1/system/status` - System status
- `GET /api/v1/system/gpu` - GPU statistics
- `GET /api/v1/system/config` - System configuration
- `POST /api/v1/system/config` - Update configuration

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

All responses return JSON with consistent structure:

```json
{
  "data": { ... },
  "meta": { "page": 1, "total": 100 }
}
```

### Error Format

Errors return appropriate HTTP status codes with details:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Event not found"
  }
}
```

## Related Documentation

- **docs/AGENTS.md:** Documentation directory overview
- **docs/architecture/:** Technical architecture details
- **backend/api/routes/AGENTS.md:** Route implementation details
- **backend/api/schemas/AGENTS.md:** Pydantic schema definitions
