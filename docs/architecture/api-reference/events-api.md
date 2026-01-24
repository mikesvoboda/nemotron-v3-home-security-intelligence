# Events API

The Events API provides endpoints for managing security events in the NEM home security monitoring system. Events are aggregated collections of detections that represent security-relevant activities.

**Source:** `backend/api/routes/events.py`

## Overview

Events are created when the AI pipeline detects security-relevant activity. Each event:

- Contains one or more detections
- Has an LLM-generated risk score (0-100)
- Includes a summary and reasoning from Nemotron
- Supports soft-delete for recovery

## Endpoints

### List Events

```
GET /api/events
```

List security events with optional filtering and pagination.

**Source:** `backend/api/routes/events.py:224-468`

#### Query Parameters

| Parameter         | Type     | Default | Description                                        |
| ----------------- | -------- | ------- | -------------------------------------------------- |
| `camera_id`       | string   | null    | Filter by camera ID                                |
| `risk_level`      | string   | null    | Filter by risk level (low, medium, high, critical) |
| `start_date`      | datetime | null    | Filter events after this date (ISO 8601)           |
| `end_date`        | datetime | null    | Filter events before this date (ISO 8601)          |
| `reviewed`        | boolean  | null    | Filter by review status                            |
| `object_type`     | string   | null    | Filter by detected object type                     |
| `limit`           | integer  | 50      | Maximum results (1-100)                            |
| `offset`          | integer  | 0       | Results to skip (deprecated, use cursor)           |
| `cursor`          | string   | null    | Pagination cursor from previous response           |
| `fields`          | string   | null    | Comma-separated fields for sparse fieldsets        |
| `include_deleted` | boolean  | false   | Include soft-deleted events                        |

#### Response

```json
{
  "items": [
    {
      "id": 1,
      "camera_id": "front_door",
      "started_at": "2026-01-23T12:00:00Z",
      "ended_at": "2026-01-23T12:02:30Z",
      "risk_score": 75,
      "risk_level": "medium",
      "summary": "Person detected near front entrance",
      "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
      "llm_prompt": "<|im_start|>system\nYou are a home security risk analyzer...",
      "reviewed": false,
      "notes": null,
      "snooze_until": null,
      "detection_count": 5,
      "detection_ids": [1, 2, 3, 4, 5],
      "thumbnail_url": "/api/detections/1/image",
      "enrichment_status": {
        "status": "full",
        "successful_models": ["violence", "weather", "face", "clothing"],
        "failed_models": [],
        "errors": {},
        "success_rate": 1.0
      },
      "deleted_at": null
    }
  ],
  "pagination": {
    "total": 150,
    "limit": 50,
    "offset": 0,
    "next_cursor": "eyJpZCI6IDUwLCAiY3JlYXRlZF9hdCI6ICIyMDI2LTAxLTIzVDEyOjAwOjAwWiJ9",  // pragma: allowlist secret
    "has_more": true
  },
  "deprecation_warning": null
}
```

**Source:** `backend/api/schemas/events.py:147-193`

#### HTTP Status Codes

| Code | Description                  |
| ---- | ---------------------------- |
| 200  | Success                      |
| 400  | Invalid date range or cursor |
| 422  | Validation error             |

---

### Get Event Statistics

```
GET /api/events/stats
```

Get aggregated event statistics including risk distribution and per-camera counts.

**Source:** `backend/api/routes/events.py:471-603`

#### Query Parameters

| Parameter    | Type     | Default | Description                 |
| ------------ | -------- | ------- | --------------------------- |
| `camera_id`  | string   | null    | Filter statistics by camera |
| `start_date` | datetime | null    | Start of date range         |
| `end_date`   | datetime | null    | End of date range           |

#### Response

```json
{
  "total_events": 44,
  "events_by_risk_level": {
    "critical": 2,
    "high": 5,
    "medium": 12,
    "low": 25
  },
  "risk_distribution": [
    { "risk_level": "critical", "count": 2 },
    { "risk_level": "high", "count": 5 },
    { "risk_level": "medium", "count": 12 },
    { "risk_level": "low", "count": 25 }
  ],
  "events_by_camera": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door",
      "event_count": 30
    },
    {
      "camera_id": "back_door",
      "camera_name": "Back Door",
      "event_count": 14
    }
  ]
}
```

**Source:** `backend/api/schemas/events.py:243-284`

---

### Get Timeline Summary

```
GET /api/events/timeline-summary
```

Get bucketed event data for timeline visualization. Supports different zoom levels with varying bucket sizes.

**Source:** `backend/api/routes/events.py:621-779`

#### Query Parameters

| Parameter     | Type     | Default  | Description                   |
| ------------- | -------- | -------- | ----------------------------- |
| `start_date`  | datetime | required | Start of timeline range       |
| `end_date`    | datetime | required | End of timeline range         |
| `camera_id`   | string   | null     | Filter by camera              |
| `bucket_size` | string   | "hour"   | Bucket size (hour, day, week) |

#### Response

```json
{
  "buckets": [
    {
      "timestamp": "2026-01-15T06:00:00Z",
      "event_count": 5,
      "max_risk_score": 45
    },
    {
      "timestamp": "2026-01-15T07:00:00Z",
      "event_count": 12,
      "max_risk_score": 85
    }
  ],
  "total_events": 17,
  "start_date": "2026-01-15T06:00:00Z",
  "end_date": "2026-01-15T08:00:00Z"
}
```

**Source:** `backend/api/schemas/events.py:287-349`

---

### Search Events

```
GET /api/events/search
```

Full-text search across events using PostgreSQL text search.

**Source:** `backend/api/routes/events.py:782-892`

#### Query Parameters

| Parameter        | Type     | Default  | Description                    |
| ---------------- | -------- | -------- | ------------------------------ |
| `q`              | string   | required | Search query (min 1 character) |
| `camera_id`      | string   | null     | Filter by camera               |
| `min_risk_score` | integer  | null     | Minimum risk score (0-100)     |
| `start_date`     | datetime | null     | Filter after date              |
| `end_date`       | datetime | null     | Filter before date             |
| `limit`          | integer  | 50       | Maximum results (1-1000)       |
| `offset`         | integer  | 0        | Results to skip                |

#### Response

Results include a `relevance_score` field indicating search match quality.

---

### Export Events

```
GET /api/events/export
```

Export events as CSV or Excel file.

**Source:** `backend/api/routes/events.py:895-999`

#### Query Parameters

| Parameter    | Type     | Default | Description               |
| ------------ | -------- | ------- | ------------------------- |
| `format`     | string   | "csv"   | Export format (csv, xlsx) |
| `camera_id`  | string   | null    | Filter by camera          |
| `start_date` | datetime | null    | Filter after date         |
| `end_date`   | datetime | null    | Filter before date        |
| `risk_level` | string   | null    | Filter by risk level      |

#### Response

Returns file download with appropriate Content-Type header.

**Rate Limiting:** Export tier (5 requests/minute)

---

### Get Single Event

```
GET /api/events/{event_id}
```

Get detailed information about a specific event.

#### Path Parameters

| Parameter  | Type    | Description |
| ---------- | ------- | ----------- |
| `event_id` | integer | Event ID    |

#### Response

Returns full `EventResponse` object.

#### HTTP Status Codes

| Code | Description     |
| ---- | --------------- |
| 200  | Success         |
| 404  | Event not found |

---

### Update Event

```
PATCH /api/events/{event_id}
```

Update event metadata (reviewed status, notes, snooze).

#### Path Parameters

| Parameter  | Type    | Description |
| ---------- | ------- | ----------- |
| `event_id` | integer | Event ID    |

#### Request Body

```json
{
  "reviewed": true,
  "notes": "Verified - delivery person",
  "snooze_until": "2026-01-24T12:00:00Z"
}
```

**Source:** `backend/api/schemas/events.py:127-144`

#### HTTP Status Codes

| Code | Description      |
| ---- | ---------------- |
| 200  | Success          |
| 404  | Event not found  |
| 422  | Validation error |

---

### Delete Event

```
DELETE /api/events/{event_id}
```

Soft-delete an event. The event can be restored later.

#### Path Parameters

| Parameter  | Type    | Description |
| ---------- | ------- | ----------- |
| `event_id` | integer | Event ID    |

#### HTTP Status Codes

| Code | Description          |
| ---- | -------------------- |
| 204  | Success (no content) |
| 404  | Event not found      |

---

### Restore Event

```
POST /api/events/{event_id}/restore
```

Restore a soft-deleted event.

#### Path Parameters

| Parameter  | Type    | Description |
| ---------- | ------- | ----------- |
| `event_id` | integer | Event ID    |

#### HTTP Status Codes

| Code | Description          |
| ---- | -------------------- |
| 200  | Success              |
| 400  | Event is not deleted |
| 404  | Event not found      |

---

### List Deleted Events

```
GET /api/events/deleted
```

List soft-deleted events for the "trash" view.

**Source:** `backend/api/schemas/events.py:352-393`

#### Response

Returns `DeletedEventsListResponse` with same structure as list events.

---

## Bulk Operations

### Bulk Create Events

```
POST /api/events/bulk
```

Create multiple events in a single request.

**Rate Limiting:** Bulk tier (10 requests/minute)

#### Request Body

```json
{
  "events": [
    {
      "camera_id": "front_door",
      "started_at": "2026-01-23T12:00:00Z",
      "risk_score": 45
    }
  ]
}
```

#### Response

Returns HTTP 207 Multi-Status with per-item results.

---

### Bulk Update Events

```
PATCH /api/events/bulk
```

Update multiple events in a single request.

**Rate Limiting:** Bulk tier (10 requests/minute)

---

### Bulk Delete Events

```
DELETE /api/events/bulk
```

Delete multiple events in a single request.

**Rate Limiting:** Bulk tier (10 requests/minute)

---

## Related Endpoints

### Get Event Detections

```
GET /api/events/{event_id}/detections
```

Get all detections associated with an event.

### Get Event Enrichments

```
GET /api/events/{event_id}/enrichments
```

Get enrichment data for all detections in an event.

### Generate Event Clip

```
POST /api/events/{event_id}/clip
```

Generate a video clip for an event.

---

## Data Models

### EventResponse

**Source:** `backend/api/schemas/events.py:61-125`

| Field               | Type     | Description                              |
| ------------------- | -------- | ---------------------------------------- |
| `id`                | integer  | Event ID                                 |
| `camera_id`         | string   | Normalized camera ID                     |
| `started_at`        | datetime | Event start timestamp                    |
| `ended_at`          | datetime | Event end timestamp                      |
| `risk_score`        | integer  | Risk score (0-100)                       |
| `risk_level`        | string   | Risk level (low, medium, high, critical) |
| `summary`           | string   | LLM-generated summary                    |
| `reasoning`         | string   | LLM reasoning for risk score             |
| `llm_prompt`        | string   | Full prompt sent to Nemotron             |
| `reviewed`          | boolean  | Review status                            |
| `notes`             | string   | User notes                               |
| `snooze_until`      | datetime | Alert snooze timestamp                   |
| `detection_count`   | integer  | Number of detections                     |
| `detection_ids`     | array    | List of detection IDs                    |
| `thumbnail_url`     | string   | URL to thumbnail                         |
| `enrichment_status` | object   | Enrichment pipeline status               |
| `deleted_at`        | datetime | Soft-delete timestamp                    |

### EnrichmentStatusResponse

**Source:** `backend/api/schemas/events.py:27-58`

| Field               | Type   | Description                                     |
| ------------------- | ------ | ----------------------------------------------- |
| `status`            | string | Overall status (full, partial, failed, skipped) |
| `successful_models` | array  | List of models that succeeded                   |
| `failed_models`     | array  | List of models that failed                      |
| `errors`            | object | Model name to error mapping                     |
| `success_rate`      | float  | Success rate (0.0 to 1.0)                       |

---

## Validation Rules

### Date Range Validation

- `start_date` must be before `end_date`
- Dates are normalized to end-of-day for date-only inputs
- Maximum date range: 90 days

### Sparse Fieldsets

Valid fields for the `fields` parameter:

- `id`, `camera_id`, `started_at`, `ended_at`
- `risk_score`, `risk_level`, `summary`, `reasoning`
- `reviewed`, `notes`, `detection_count`, `thumbnail_url`

---

## Related Documentation

- [Detections API](detections-api.md) - Detection data endpoints
- [Error Handling](error-handling.md) - Error response formats
- [Request/Response Schemas](request-response-schemas.md) - Schema details
