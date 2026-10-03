# Analytics API Endpoints

Complete reference for the video analytics API endpoints.

## Overview

The Analytics API provides access to aggregated detection data, risk analysis, camera performance
metrics, and trend analysis. Every endpoint is a read-only `GET`, takes a date range, and returns
JSON computed live from the database on each call.

**Base URL:** `/api/analytics` (`backend/api/routes/analytics.py:36`)

---

## Common Parameters

Every analytics endpoint except `/calibration` accepts these query parameters:

| Parameter    | Type | Required | Description                         |
| ------------ | ---- | -------- | ----------------------------------- |
| `start_date` | Date | Yes      | Start date (ISO format: YYYY-MM-DD) |
| `end_date`   | Date | Yes      | End date (ISO format: YYYY-MM-DD)   |

**Date validation** (`backend/api/routes/analytics.py:44`):

- `start_date` must be before or equal to `end_date`, otherwise the call returns 400
- The range, counted inclusively, may not exceed 365 days (`MAX_DATE_RANGE_DAYS`,
  `backend/api/routes/analytics.py:41`); a longer range returns 400 with a message naming the
  limit and the number of days you asked for
- Both dates are inclusive

**Aggregation scope:** these endpoints aggregate across all cameras. None of them accepts a
`camera_id` parameter. `GET /api/analytics/camera-activity` and
`GET /api/analytics/camera-uptime` return one row _per camera_, which is how you get a per-camera
breakdown today.

**Gap filling:** the daily endpoints (`detection-trends`, `risk-history`, `risk-score-trends`)
emit one data point for every calendar day in the range and fill days with no rows with zero, so a
quiet week appears as zeros rather than as missing entries.

---

## Detection Trends

Get daily detection counts over time.

### Endpoint

```
GET /api/analytics/detection-trends
```

Counts rows in the `detections` table by `detected_at`
(`backend/api/routes/analytics.py:75`).

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "data_points": [
    { "date": "2026-01-01", "count": 156 },
    { "date": "2026-01-02", "count": 203 },
    { "date": "2026-01-03", "count": 178 }
  ],
  "total_detections": 4521,
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                 | Type    | Description                  |
| --------------------- | ------- | ---------------------------- |
| `data_points`         | Array   | Daily detection counts       |
| `data_points[].date`  | Date    | The date                     |
| `data_points[].count` | Integer | Detection count for that day |
| `total_detections`    | Integer | Sum of all detections        |
| `start_date`          | Date    | Query start date             |
| `end_date`            | Date    | Query end date               |

### Example

```bash
curl "http://localhost:8000/api/analytics/detection-trends?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Risk History

Get risk level distribution over time.

### Endpoint

```
GET /api/analytics/risk-history
```

Groups events by `started_at` and the stored `risk_level`, skipping events whose `risk_level` is
null (`backend/api/routes/analytics.py:148`).

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "data_points": [
    {
      "date": "2026-01-01",
      "low": 45,
      "medium": 12,
      "high": 3,
      "critical": 0
    },
    {
      "date": "2026-01-02",
      "low": 52,
      "medium": 15,
      "high": 5,
      "critical": 1
    }
  ],
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                    | Type    | Description                   |
| ------------------------ | ------- | ----------------------------- |
| `data_points`            | Array   | Daily risk level breakdown    |
| `data_points[].date`     | Date    | The date                      |
| `data_points[].low`      | Integer | Low risk events (0-29)        |
| `data_points[].medium`   | Integer | Medium risk events (30-59)    |
| `data_points[].high`     | Integer | High risk events (60-84)      |
| `data_points[].critical` | Integer | Critical risk events (85-100) |

### Example

```bash
curl "http://localhost:8000/api/analytics/risk-history?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Camera Uptime

Get uptime percentage and detection counts per camera.

### Endpoint

```
GET /api/analytics/camera-uptime
```

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "cameras": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door",
      "uptime_percentage": 96.15,
      "detection_count": 1247
    },
    {
      "camera_id": "driveway",
      "camera_name": "Driveway",
      "uptime_percentage": 100.0,
      "detection_count": 892
    }
  ],
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                         | Type    | Description                        |
| ----------------------------- | ------- | ---------------------------------- |
| `cameras`                     | Array   | Per-camera uptime data             |
| `cameras[].camera_id`         | String  | Camera identifier                  |
| `cameras[].camera_name`       | String  | Human-readable camera name         |
| `cameras[].uptime_percentage` | Float   | Percentage of days with detections |
| `cameras[].detection_count`   | Integer | Total detections in period         |

### Uptime Calculation

Uptime is a **detection-activity** measure, not a liveness probe. It answers "how many days of
this window did this camera produce at least one detection":

```
uptime_percentage = (days_with_detections / total_days) * 100
```

`total_days` is the inclusive length of the requested range, and a day counts as active when the
camera has at least one detection row dated that day
(`backend/api/routes/analytics.py:266-290`). The value is rounded to two decimals.

A camera that is streaming fine but seeing nothing scores 0 here, and a camera that has been
offline all week simply reports a low number — this endpoint cannot tell you which. For actual
reachability, use the camera health endpoints in the
[Cameras API](../architecture/api-reference/cameras-api.md).

Every camera row in the database appears in the response, including cameras with no detections,
because the query outer-joins detections onto cameras and sorts by camera name.

### Example

```bash
curl "http://localhost:8000/api/analytics/camera-uptime?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Object Distribution

Get detection counts grouped by object type.

### Endpoint

```
GET /api/analytics/object-distribution
```

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "object_types": [
    {
      "object_type": "person",
      "count": 2847,
      "percentage": 63.02
    },
    {
      "object_type": "car",
      "count": 892,
      "percentage": 19.75
    },
    {
      "object_type": "dog",
      "count": 412,
      "percentage": 9.12
    }
  ],
  "total_detections": 4151,
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                        | Type    | Description                |
| ---------------------------- | ------- | -------------------------- |
| `object_types`               | Array   | Detections grouped by type |
| `object_types[].object_type` | String  | Object class name          |
| `object_types[].count`       | Integer | Detection count            |
| `object_types[].percentage`  | Float   | Percentage of total        |
| `total_detections`           | Integer | Sum over the listed types  |

The class names are whatever the detector wrote into `detections.object_type`; detections with a
null `object_type` are excluded and the percentages are computed over the included rows, so
`total_detections` here can sit below the total that `detection-trends` reports for the same
window. Results are ordered by count, descending.

### Example

```bash
curl "http://localhost:8000/api/analytics/object-distribution?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Risk Score Distribution

Get risk score histogram with customizable bucket sizes.

### Endpoint

```
GET /api/analytics/risk-score-distribution
```

### Parameters

| Parameter     | Type    | Required | Default | Description                        |
| ------------- | ------- | -------- | ------- | ---------------------------------- |
| `start_date`  | Date    | Yes      | -       | Start date                         |
| `end_date`    | Date    | Yes      | -       | End date                           |
| `bucket_size` | Integer | No       | 10      | Size of each bucket (allowed 1-50) |

### Response

```json
{
  "buckets": [
    { "min_score": 0, "max_score": 10, "count": 1247 },
    { "min_score": 10, "max_score": 20, "count": 892 },
    { "min_score": 20, "max_score": 30, "count": 456 },
    { "min_score": 30, "max_score": 40, "count": 234 },
    { "min_score": 40, "max_score": 50, "count": 123 },
    { "min_score": 50, "max_score": 60, "count": 67 },
    { "min_score": 60, "max_score": 70, "count": 34 },
    { "min_score": 70, "max_score": 80, "count": 12 },
    { "min_score": 80, "max_score": 90, "count": 5 },
    { "min_score": 90, "max_score": 100, "count": 2 }
  ],
  "total_events": 3072,
  "start_date": "2026-01-01",
  "end_date": "2026-01-26",
  "bucket_size": 10
}
```

### Response Fields

| Field                 | Type    | Description                |
| --------------------- | ------- | -------------------------- |
| `buckets`             | Array   | Score distribution buckets |
| `buckets[].min_score` | Integer | Minimum score in bucket    |
| `buckets[].max_score` | Integer | Maximum score in bucket    |
| `buckets[].count`     | Integer | Events in this bucket      |
| `total_events`        | Integer | Total events with scores   |
| `bucket_size`         | Integer | Size of each bucket        |

Bucket edges are `100 // bucket_size` buckets with the last one stretched to include a score of
exactly 100 (`backend/api/routes/analytics.py:413-455`). Only events with a non-null
`risk_score` and no `deleted_at` are counted, so soft-deleted events are excluded here and in
`risk-score-trends` and `camera-activity`, but **not** in `detection-trends`,
`risk-history`, `camera-uptime` or `object-distribution`, which have no soft-delete filter.

### Example

```bash
# Default 10-point buckets
curl "http://localhost:8000/api/analytics/risk-score-distribution?start_date=2026-01-01&end_date=2026-01-26"

# Custom 5-point buckets
curl "http://localhost:8000/api/analytics/risk-score-distribution?start_date=2026-01-01&end_date=2026-01-26&bucket_size=5"
```

---

## Risk Score Trends

Get average risk score trends over time.

### Endpoint

```
GET /api/analytics/risk-score-trends
```

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "data_points": [
    { "date": "2026-01-01", "avg_score": 24.5, "count": 45 },
    { "date": "2026-01-02", "avg_score": 28.3, "count": 52 },
    { "date": "2026-01-03", "avg_score": 22.1, "count": 38 }
  ],
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                     | Type    | Description                               |
| ------------------------- | ------- | ----------------------------------------- |
| `data_points`             | Array   | Daily average scores                      |
| `data_points[].date`      | Date    | The date                                  |
| `data_points[].avg_score` | Float   | Average risk score (rounded to 1 decimal) |
| `data_points[].count`     | Integer | Number of scored events that day          |

Days with no scored events come back as `{"avg_score": 0.0, "count": 0}` — check `count` before
treating a zero average as a real measurement.

### Example

```bash
curl "http://localhost:8000/api/analytics/risk-score-trends?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Camera Activity

Get per-camera event counts and the highest-risk thumbnail, for the dashboard heat map.

### Endpoint

```
GET /api/analytics/camera-activity
```

### Parameters

| Parameter    | Type | Required | Description |
| ------------ | ---- | -------- | ----------- |
| `start_date` | Date | Yes      | Start date  |
| `end_date`   | Date | Yes      | End date    |

### Response

```json
{
  "cameras": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door",
      "event_count": 84,
      "max_risk_score": 91,
      "risk_level": "critical",
      "thumbnail_path": "/data/thumbnails/2026/01/front_door_high.jpg"
    }
  ],
  "start_date": "2026-01-01",
  "end_date": "2026-01-26"
}
```

### Response Fields

| Field                      | Type            | Description                                           |
| -------------------------- | --------------- | ----------------------------------------------------- |
| `cameras`                  | Array           | One entry per camera                                  |
| `cameras[].camera_id`      | String          | Camera identifier                                     |
| `cameras[].camera_name`    | String          | Human-readable camera name                            |
| `cameras[].event_count`    | Integer         | Non-deleted events in the window                      |
| `cameras[].max_risk_score` | Integer \| null | Highest event risk score, null if no events           |
| `cameras[].risk_level`     | String \| null  | Tier for that score: `low`/`medium`/`high`/`critical` |
| `cameras[].thumbnail_path` | String \| null  | Thumbnail of the highest-risk detection               |

`risk_level` is derived from the score with the same thresholds the frontend uses — 0-29 low,
30-59 medium, 60-84 high, 85-100 critical (`backend/api/routes/analytics.py:578-584`). Cameras are
sorted by event count, highest first.

### Example

```bash
curl "http://localhost:8000/api/analytics/camera-activity?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Calibration Drift

Get the rolling risk-score distribution and whether any tier has drifted from its target.

### Endpoint

```
GET /api/analytics/calibration
```

Unlike the endpoints above, this one takes no parameters and reads a Redis-backed window rather
than the database.

### Response

```json
{
  "total_scores": 412,
  "window_seconds": 86400,
  "drift_threshold_pct": 5.0,
  "is_drifting": false,
  "drifting_tiers": [],
  "tiers": [
    {
      "tier": "low",
      "actual_pct": 71.2,
      "target_pct": 70.0,
      "deviation_pct": 1.2,
      "is_drifting": false
    }
  ]
}
```

| Condition                                             | Result                                                   |
| ----------------------------------------------------- | -------------------------------------------------------- |
| Calibration monitor unavailable (Redis not connected) | `503` with a message naming the monitor                  |
| Monitor available                                     | `200` with the current window, target and per-tier drift |

`window_seconds` defaults to 24 hours and `drift_threshold_pct` to 5.0 percentage points
(`backend/services/calibration_monitor.py:34`, `backend/services/calibration_monitor.py:40`).
Scores accumulate in a Redis sorted set, so the window is only populated while the pipeline is
running.

### Example

```bash
curl "http://localhost:8000/api/analytics/calibration"
```

---

## Error Responses

Errors from a route's `HTTPException` are rendered by the registered handler in
RFC 7807 Problem Details format with media type `application/problem+json`
(`backend/api/exception_handlers.py:748`, `backend/api/exception_handlers.py:121`). FastAPI's
stock `{"detail": ...}` shape does not appear.

### 400 Bad Request

Invalid date range or parameters:

```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "start_date must be before or equal to end_date",
  "instance": "/api/analytics/detection-trends"
}
```

The unbounded-range variant reads
`"Date range exceeds maximum allowed (365 days). Requested range: <n> days. Please narrow your date range."`

### 422 Validation Error

Missing or malformed query parameters are handled by a different handler and use a different
envelope — `{error: {code, message, errors[]}}` (`backend/api/exception_handlers.py:358`,
`backend/api/exception_handlers.py:371`):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "errors": [{ "field": "query.start_date", "message": "Field required", "value": null }]
  }
}
```

`request_id` and `timestamp` are added to `error` when a request id was assigned.

### 500 Internal Server Error

Anything unhandled falls to the catch-all handler, which also uses the `{error: {...}}` envelope
with `code: "INTERNAL_ERROR"` (`backend/api/exception_handlers.py:453`), and sanitises the message
before returning it.

---

## Caching And Rate Limits

There is no caching layer and no rate limiter on the analytics routes. Each request runs its
aggregate query against PostgreSQL and returns fresh results; no `Cache-Control`, `ETag` or
`Retry-After` headers are set by these handlers, and the analytics router has no rate-limit
dependency (its only `Depends` is `get_db`, `backend/api/routes/analytics.py:87`).

The 365-day range cap is the protection that exists, and it is enforced at the query layer rather
than by a limiter — it bounds the cost of a single request instead of the number of requests. Two
consequences worth designing around:

- Repeated dashboard refreshes re-scan the window each time, so keep dashboards on short windows
  and fetch long ranges only on explicit user action.
- If you add a limiter, follow the pattern the routes that have one already use: construct a
  `RateLimiter` and inject it as a dependency, as `backend/api/routes/cameras.py:89` does for
  snapshot endpoints. Do not assume a global middleware will do it — none is registered in
  `backend/main.py`.

---

## Usage Examples

### Python

```python
import requests
from datetime import date, timedelta

# Get last 30 days of detection trends
end_date = date.today()
start_date = end_date - timedelta(days=30)

response = requests.get(
    "http://localhost:8000/api/analytics/detection-trends",
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
)
response.raise_for_status()

data = response.json()
for point in data["data_points"]:
    print(f"{point['date']}: {point['count']} detections")
```

### JavaScript

```javascript
const fetchAnalytics = async () => {
  const endDate = new Date().toISOString().split('T')[0];
  const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  const response = await fetch(
    `/api/analytics/detection-trends?start_date=${startDate}&end_date=${endDate}`
  );

  const data = await response.json();
  console.log(`Total detections: ${data.total_detections}`);
};
```

### cURL

```bash
# Get this week's data
START=$(date -d "7 days ago" +%Y-%m-%d)
END=$(date +%Y-%m-%d)

curl "http://localhost:8000/api/analytics/detection-trends?start_date=$START&end_date=$END"
```

---

## Related Endpoints

| Endpoint                       | Description                         |
| ------------------------------ | ----------------------------------- |
| `/api/system/telemetry`        | Real-time pipeline metrics          |
| `/api/system/pipeline-latency` | Processing latency stats            |
| `/api/events`                  | Individual event records            |
| `/api/detections`              | Individual detection records        |
| `/api/analytics-zones`         | Polygon analytics zones (see below) |

Detection-zone configuration — the rectangles with dwell-time and line-crossing rules — lives on a
different router from these aggregate endpoints:
[Zone Anomalies And Baselines API](../guides/zone-configuration.md#zone-anomalies-and-baselines-api).
`GET /api/analytics-zones` and its sub-resources are the polygon-zone API, and
`/api/zones/*` still resolves as an unlisted redirect onto it.

---

## Baseline Configuration API

The Baseline Configuration API provides per-camera control over anomaly detection settings,
allowing users to tune sensitivity and reset learned patterns.

These routes are mounted on the cameras router, not the analytics router
(`backend/api/routes/cameras.py:86`).

**Base URL:** `/api/cameras/{camera_id}/baseline`

| Route                                          | Handler | Location                             |
| ---------------------------------------------- | ------- | ------------------------------------ |
| `GET /api/cameras/{camera_id}/baseline/config` | get     | `backend/api/routes/cameras.py:2186` |
| `PUT /api/cameras/{camera_id}/baseline/config` | update  | `backend/api/routes/cameras.py:2112` |
| `POST /api/cameras/{camera_id}/baseline/reset` | reset   | `backend/api/routes/cameras.py:2158` |

---

### Get Baseline Configuration

Get the active configuration for a camera's anomaly detection.

#### Endpoint

```
GET /api/cameras/{camera_id}/baseline/config
```

#### Path Parameters

| Parameter   | Type   | Required | Description       |
| ----------- | ------ | -------- | ----------------- |
| `camera_id` | String | Yes      | Camera identifier |

#### Response

The active values are the per-camera overrides when `override_global_config` is true and the
global defaults otherwise; `global_config` is always the unmodified global set
(`backend/api/schemas/baseline.py:585`).

```json
{
  "threshold_stdev": 2.0,
  "min_samples": 10,
  "override_global_config": false,
  "global_config": {
    "threshold_stdev": 2.0,
    "min_samples": 10,
    "decay_factor": 0.1,
    "window_days": 7
  }
}
```

#### Response Fields

| Field                    | Type    | Description                                          |
| ------------------------ | ------- | ---------------------------------------------------- |
| `threshold_stdev`        | Float   | Active threshold in standard deviations              |
| `min_samples`            | Integer | Minimum samples before anomaly detection is reliable |
| `override_global_config` | Boolean | Whether per-camera settings are active               |
| `global_config`          | Object  | Global default configuration for reference           |

`global_config.decay_factor` and `global_config.window_days` are optional fields
(`backend/api/schemas/baseline.py:564`), so treat them as possibly absent.

#### Example

```bash
curl "http://localhost:8000/api/cameras/front_door/baseline/config"
```

---

### Update Baseline Configuration

Update per-camera anomaly detection settings.

#### Endpoint

```
PUT /api/cameras/{camera_id}/baseline/config
```

#### Path Parameters

| Parameter   | Type   | Required | Description       |
| ----------- | ------ | -------- | ----------------- |
| `camera_id` | String | Yes      | Camera identifier |

#### Request Body

```json
{
  "threshold_stdev": 3.0,
  "min_samples": 15,
  "override_global_config": true
}
```

#### Request Fields

| Field                    | Type    | Required | Description                                     |
| ------------------------ | ------- | -------- | ----------------------------------------------- |
| `threshold_stdev`        | Float   | No       | New threshold, at least 0.5 standard deviations |
| `min_samples`            | Integer | No       | New minimum samples requirement (>= 1)          |
| `override_global_config` | Boolean | No       | Enable/disable per-camera overrides             |

All three fields are optional and omitted fields keep their current value
(`BaselineConfigUpdate`, `backend/api/schemas/camera.py:750`).

#### Validation Rules

The bounds are checked in the handler, not declared as schema constraints
(`backend/api/routes/cameras.py:2136-2139`), and that distinction is visible to the client:

- `threshold_stdev` below 0.5 and `min_samples` below 1 raise `ValueError` inside the handler.
  There is no `ValueError` exception handler registered, so the catch-all takes it and the client
  sees **500** `INTERNAL_ERROR`, not a 4xx validation response. Validate on the client side before
  sending.
- A `threshold_stdev` above the range is not rejected at all — only the lower bound is checked.
- An unknown `camera_id` is checked _after_ the bounds, so a bad value plus a bad camera id
  returns the 500 rather than the 404.
- `override_global_config: false` makes the service fall back to global values on read; the
  per-camera values are not cleared by it.

#### Response

Returns the updated configuration (same format as GET).

#### Example

```bash
# Enable custom settings for a camera
curl -X PUT "http://localhost:8000/api/cameras/front_door/baseline/config" \
  -H "Content-Type: application/json" \
  -d '{
    "threshold_stdev": 3.0,
    "min_samples": 15,
    "override_global_config": true
  }'

# Revert to global settings
curl -X PUT "http://localhost:8000/api/cameras/front_door/baseline/config" \
  -H "Content-Type: application/json" \
  -d '{"override_global_config": false}'
```

---

### Reset Baseline Data

Delete all learned baseline data for a camera, forcing re-learning from new detections.

#### Endpoint

```
POST /api/cameras/{camera_id}/baseline/reset
```

#### Path Parameters

| Parameter   | Type   | Required | Description       |
| ----------- | ------ | -------- | ----------------- |
| `camera_id` | String | Yes      | Camera identifier |

#### Response

```json
{
  "activity_baselines_deleted": 168,
  "class_baselines_deleted": 42
}
```

#### Response Fields

| Field                        | Type    | Description                                |
| ---------------------------- | ------- | ------------------------------------------ |
| `activity_baselines_deleted` | Integer | Number of ActivityBaseline records deleted |
| `class_baselines_deleted`    | Integer | Number of ClassBaseline records deleted    |

The delete is immediate and unconditional — run it after physically moving a camera or changing
its field of view, not as a way to make an alert go away.

#### Example

```bash
curl -X POST "http://localhost:8000/api/cameras/front_door/baseline/reset"
```

---

### Error Responses

#### 404 Not Found

Camera does not exist. Rendered as RFC 7807 by the HTTP-exception handler:

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "Camera with id front_door not found",
  "instance": "/api/cameras/front_door/baseline/config"
}
```

The `detail` string comes from the shared lookup dependency
(`get_camera_or_404`, `backend/api/dependencies.py:431`, message at `:469`).

#### 422 Validation Error

Only request bodies and query parameters that fail **schema** validation produce a 422, and the
envelope is the `{error: {...}}` shape, not Problem Details:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "errors": [
      {
        "field": "body.threshold_stdev",
        "message": "Input should be a valid number",
        "value": "wide"
      }
    ]
  }
}
```

Out-of-range numeric values do **not** produce a 422 on these routes; see
[Validation Rules](#validation-rules).

---

### Usage Examples

#### Python

```python
import requests

# Get current configuration
config = requests.get(
    "http://localhost:8000/api/cameras/front_door/baseline/config"
).json()

print(f"Using {'custom' if config['override_global_config'] else 'global'} settings")
print(f"Threshold: {config['threshold_stdev']} std dev")

# Make camera more sensitive
requests.put(
    "http://localhost:8000/api/cameras/front_door/baseline/config",
    json={
        "threshold_stdev": 1.5,
        "override_global_config": True
    }
)

# Reset baseline after camera moved
result = requests.post(
    "http://localhost:8000/api/cameras/front_door/baseline/reset"
).json()

print(f"Deleted {result['activity_baselines_deleted']} activity baselines")
```

#### JavaScript

```javascript
// Get configuration
const config = await fetch('/api/cameras/front_door/baseline/config').then((r) => r.json());

// Update settings
await fetch('/api/cameras/front_door/baseline/config', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    threshold_stdev: 2.5,
    min_samples: 20,
    override_global_config: true,
  }),
});

// Reset baseline
const resetResult = await fetch('/api/cameras/front_door/baseline/reset', {
  method: 'POST',
}).then((r) => r.json());

console.log(`Deleted ${resetResult.activity_baselines_deleted} baselines`);
```

---

## Related Documentation

- [Video Analytics Guide](../guides/video-analytics.md) - Feature overview
- [Zone Configuration Guide](../guides/zone-configuration.md) - Zone setup
- [Analytics UI](../ui/analytics.md) - Dashboard usage
