# Event Endpoints

> REST API endpoints for accessing security events.

**Time to read:** ~6 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

Events represent analyzed security incidents that may contain multiple detections. Each event has a risk score assigned by the Nemotron LLM.

**Base path:** `/api/events`

## Endpoints

### List Events

```
GET /api/events
```

Returns events with filtering and pagination.

**Query Parameters:**

| Parameter     | Type     | Description                                          |
| ------------- | -------- | ---------------------------------------------------- |
| `camera_id`   | string   | Filter by camera ID (e.g., "front_door")             |
| `risk_level`  | string   | Filter by level: `low`, `medium`, `high`, `critical` |
| `start_date`  | datetime | ISO 8601 date/time (events after this time)          |
| `end_date`    | datetime | ISO 8601 date/time (events before this time)         |
| `reviewed`    | boolean  | Filter by reviewed status                            |
| `object_type` | string   | Filter by detected object type                       |
| `limit`       | int      | Max results (default: 50, max: 1000)                 |
| `offset`      | int      | Pagination offset                                    |

**Response:** `200 OK`

```json
{
  "events": [
    {
      "id": 1,
      "camera_id": "front_door",
      "started_at": "2025-01-15T14:30:00Z",
      "ended_at": "2025-01-15T14:32:00Z",
      "risk_score": 75,
      "risk_level": "high",
      "summary": "Unknown person at front door",
      "reasoning": "AI analysis explaining the risk assessment...",
      "reviewed": false,
      "detection_count": 3,
      "detection_ids": [1, 2, 3]
    }
  ],
  "count": 42,
  "limit": 50,
  "offset": 0
}
```

### Get Event Statistics

```
GET /api/events/stats
```

Returns aggregated event statistics.

**Query Parameters:**

| Parameter    | Type     | Description            |
| ------------ | -------- | ---------------------- |
| `start_date` | datetime | Stats after this time  |
| `end_date`   | datetime | Stats before this time |

**Response:** `200 OK`

```json
{
  "total_events": 156,
  "events_by_risk_level": {
    "critical": 5,
    "high": 23,
    "medium": 48,
    "low": 80
  },
  "events_by_camera": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door",
      "event_count": 45
    }
  ]
}
```

### Search Events

```
GET /api/events/search
```

Full-text search across event summaries, reasoning, and object types.

**Query Parameters:**

| Parameter     | Type    | Description                  |
| ------------- | ------- | ---------------------------- |
| `q`           | string  | **Required.** Search query   |
| `camera_id`   | string  | Comma-separated camera IDs   |
| `severity`    | string  | Comma-separated risk levels  |
| `object_type` | string  | Comma-separated object types |
| `reviewed`    | boolean | Filter by reviewed status    |
| `limit`       | int     | Max results (default: 50)    |
| `offset`      | int     | Pagination offset            |

**Search Syntax:**

- Basic words: `person vehicle` (implicit AND)
- Phrase: `"suspicious person"` (exact phrase)
- Boolean: `person OR animal`, `person NOT cat`

### Export Events

```
GET /api/events/export
```

Export events as CSV file.

**Query Parameters:** Same as List Events

**Response:** CSV file download

### Get Event

```
GET /api/events/{event_id}
```

Returns a single event with full details.

**Response:** `200 OK` or `404 Not Found`

### Update Event

```
PATCH /api/events/{event_id}
```

Update event properties (e.g., mark as reviewed).

**Request Body:**

```json
{
  "reviewed": true,
  "notes": "False alarm - this is my neighbor"
}
```

**Response:** `200 OK` or `404 Not Found`

### Get Event Detections

```
GET /api/events/{event_id}/detections
```

Returns all detections associated with an event.

**Response:** `200 OK` with detection list

## Risk Levels

See [Risk Levels Reference](../config/risk-levels.md) for complete definitions.

| Level    | Score Range | Description              |
| -------- | ----------- | ------------------------ |
| Low      | 0-29        | Routine activity         |
| Medium   | 30-59       | Notable, worth reviewing |
| High     | 60-84       | Concerning, review soon  |
| Critical | 85-100      | Immediate attention      |

---

## Next Steps

- [Risk Levels Reference](../config/risk-levels.md) - Understand risk scoring
- [Detections API](detections.md) - Access detection images
- [WebSocket API](websocket.md) - Real-time event streaming
- Back to [API Overview](overview.md)
