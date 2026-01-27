# Analytics API Endpoints

Complete reference for the video analytics API endpoints.

## Overview

The Analytics API provides access to aggregated detection data, risk analysis, camera performance metrics, and trend analysis. All endpoints require date range parameters and return JSON responses.

**Base URL:** `/api/analytics`

---

## Common Parameters

All analytics endpoints accept these query parameters:

| Parameter    | Type   | Required | Description                         |
| ------------ | ------ | -------- | ----------------------------------- |
| `start_date` | Date   | Yes      | Start date (ISO format: YYYY-MM-DD) |
| `end_date`   | Date   | Yes      | End date (ISO format: YYYY-MM-DD)   |
| `camera_id`  | String | No       | Filter by camera ID                 |

**Date Validation:**

- `start_date` must be before or equal to `end_date`
- Maximum range: 365 days
- Dates are inclusive

---

## Detection Trends

Get daily detection counts over time.

### Endpoint

```
GET /api/analytics/detection-trends
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

Uptime is calculated as:

```
uptime_percentage = (days_with_detections / total_days) * 100
```

A day is considered "active" if at least one detection occurred.

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
    },
    {
      "object_type": "cat",
      "count": 156,
      "percentage": 3.45
    }
  ],
  "total_detections": 4518,
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
| `total_detections`           | Integer | Sum of all detections      |

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

| Parameter     | Type    | Required | Default | Description                |
| ------------- | ------- | -------- | ------- | -------------------------- |
| `start_date`  | Date    | Yes      | -       | Start date                 |
| `end_date`    | Date    | Yes      | -       | End date                   |
| `bucket_size` | Integer | No       | 10      | Size of each bucket (1-50) |

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
| `data_points[].count`     | Integer | Number of events that day                 |

### Example

```bash
curl "http://localhost:8000/api/analytics/risk-score-trends?start_date=2026-01-01&end_date=2026-01-26"
```

---

## Error Responses

### 400 Bad Request

Invalid date range or parameters:

```json
{
  "detail": "start_date must be before or equal to end_date"
}
```

### 422 Validation Error

Missing or malformed parameters:

```json
{
  "detail": [
    {
      "loc": ["query", "start_date"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error

Server-side error:

```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

Analytics endpoints are subject to rate limiting:

| Tier    | Limit        | Window     |
| ------- | ------------ | ---------- |
| Default | 100 requests | Per minute |
| Burst   | 20 requests  | Per second |

Exceeding limits returns HTTP 429:

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds."
}
```

---

## Caching

Analytics responses are cached:

| Endpoint                | Cache Duration |
| ----------------------- | -------------- |
| detection-trends        | 5 minutes      |
| risk-history            | 5 minutes      |
| camera-uptime           | 5 minutes      |
| object-distribution     | 5 minutes      |
| risk-score-distribution | 5 minutes      |
| risk-score-trends       | 5 minutes      |

Cache headers are included in responses:

```
Cache-Control: max-age=300
ETag: "abc123..."
```

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

| Endpoint                       | Description                  |
| ------------------------------ | ---------------------------- |
| `/api/system/telemetry`        | Real-time pipeline metrics   |
| `/api/system/pipeline-latency` | Processing latency stats     |
| `/api/events`                  | Individual event records     |
| `/api/detections`              | Individual detection records |

---

## Related Documentation

- [Video Analytics Guide](../guides/video-analytics.md) - Feature overview
- [Zone Configuration Guide](../guides/zone-configuration.md) - Zone setup
- [Analytics UI](../ui/analytics.md) - Dashboard usage
