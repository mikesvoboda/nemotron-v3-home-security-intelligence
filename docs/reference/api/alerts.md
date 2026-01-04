# Alert Rule Endpoints

> REST API endpoints for managing alert rules.

**Time to read:** ~5 min
**Prerequisites:** [API Overview](overview.md)

---

## Overview

Alert rules define conditions that trigger notifications when events match specific criteria. Rules can filter by risk threshold, object types, cameras, time schedules, and more.

**Base path:** `/api/alerts/rules`

## Endpoints

### List Rules

```
GET /api/alerts/rules
```

Returns all alert rules with filtering and pagination.

**Query Parameters:**

| Parameter  | Type    | Description                                             |
| ---------- | ------- | ------------------------------------------------------- |
| `enabled`  | boolean | Filter by enabled status                                |
| `severity` | string  | Filter by severity: `low`, `medium`, `high`, `critical` |
| `limit`    | int     | Max results (default: 50, max: 1000)                    |
| `offset`   | int     | Pagination offset                                       |

**Response:** `200 OK`

```json
{
  "rules": [
    {
      "id": "uuid-string",
      "name": "High Risk Person Alert",
      "description": "Alert when person detected with high risk",
      "enabled": true,
      "severity": "high",
      "risk_threshold": 60,
      "object_types": ["person"],
      "camera_ids": [],
      "zone_ids": [],
      "min_confidence": 0.8,
      "schedule": null,
      "conditions": null,
      "dedup_key_template": "{camera_id}:{object_type}",
      "cooldown_seconds": 300,
      "channels": ["email", "webhook"],
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T10:00:00Z"
    }
  ],
  "count": 5,
  "limit": 50,
  "offset": 0
}
```

### Create Rule

```
POST /api/alerts/rules
```

Creates a new alert rule.

**Request Body:**

```json
{
  "name": "Night Person Detection",
  "description": "Alert for any person detected at night",
  "enabled": true,
  "severity": "high",
  "risk_threshold": 30,
  "object_types": ["person"],
  "camera_ids": [],
  "min_confidence": 0.7,
  "schedule": {
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
    "start_time": "22:00",
    "end_time": "06:00"
  },
  "cooldown_seconds": 600,
  "channels": ["webhook"]
}
```

**Response:** `201 Created`

### Get Rule

```
GET /api/alerts/rules/{rule_id}
```

Returns a single rule by ID.

**Response:** `200 OK` or `404 Not Found`

### Update Rule

```
PUT /api/alerts/rules/{rule_id}
```

Updates an existing rule. Provide all fields you want to set.

**Response:** `200 OK` or `404 Not Found`

### Delete Rule

```
DELETE /api/alerts/rules/{rule_id}
```

Deletes an alert rule.

**Response:** `204 No Content` or `404 Not Found`

### Test Rule

```
POST /api/alerts/rules/{rule_id}/test
```

Tests a rule against historical events without creating alerts.

**Request Body:**

```json
{
  "event_ids": [1, 2, 3],
  "limit": 100,
  "test_time": "2025-01-15T14:00:00Z"
}
```

**Response:** `200 OK`

```json
{
  "rule_id": "uuid",
  "rule_name": "Night Person Detection",
  "events_tested": 100,
  "events_matched": 15,
  "match_rate": 0.15,
  "results": [
    {
      "event_id": 1,
      "camera_id": "front_door",
      "risk_score": 65,
      "object_types": ["person"],
      "matches": true,
      "matched_conditions": ["risk_threshold", "object_types"],
      "started_at": "2025-01-15T14:30:00Z"
    }
  ]
}
```

## Rule Fields

### Core Fields

| Field         | Type    | Description            |
| ------------- | ------- | ---------------------- |
| `name`        | string  | Rule name (required)   |
| `description` | string  | Optional description   |
| `enabled`     | boolean | Whether rule is active |
| `severity`    | string  | Alert severity level   |

### Filtering Fields

| Field            | Type  | Description                                            |
| ---------------- | ----- | ------------------------------------------------------ |
| `risk_threshold` | int   | Minimum risk score (0-100)                             |
| `object_types`   | array | Object types to match                                  |
| `camera_ids`     | array | Camera IDs to match (e.g., "front_door") (empty = all) |
| `zone_ids`       | array | Zone IDs to match                                      |
| `min_confidence` | float | Minimum detection confidence                           |

### Schedule

Optional time-based activation:

```json
{
  "days": ["monday", "friday"],
  "start_time": "22:00",
  "end_time": "06:00"
}
```

### Deduplication

- `dedup_key_template`: Template for dedup key (e.g., `{camera_id}:{object_type}`)
- `cooldown_seconds`: Minimum seconds between alerts with same dedup key

### Notification Channels

The `channels` array specifies where to send alerts:

| Channel   | Description                    |
| --------- | ------------------------------ |
| `email`   | Send email notification        |
| `webhook` | POST to configured webhook URL |

---

## Next Steps

- [Events API](events.md) - Understand events that trigger rules
- [Environment Variables](../config/env-reference.md) - Configure notification settings
- Back to [API Overview](overview.md)
