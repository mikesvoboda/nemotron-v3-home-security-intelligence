---
title: Analytics API
description: API endpoints for analytics and reporting data
source_refs:
  - backend/api/routes/analytics.py
  - backend/api/schemas/analytics.py
---

# Analytics API

The Analytics API provides endpoints for retrieving aggregated data for dashboards and reports, including detection trends, risk history, camera uptime, and object distribution statistics.

## Base URL

```
/api/analytics
```

## Endpoints

### Get Detection Trends

```
GET /api/analytics/detection-trends
```

Returns daily detection counts for a specified date range. Creates one data point per day even if there are no detections (fills gaps with 0).

#### Query Parameters

| Parameter    | Type | Required | Description                                 |
| ------------ | ---- | -------- | ------------------------------------------- |
| `start_date` | date | Yes      | Start date (ISO format, e.g., `2025-12-01`) |
| `end_date`   | date | Yes      | End date (ISO format, e.g., `2025-12-31`)   |

#### Response

```json
{
  "data_points": [
    {
      "date": "2025-12-01",
      "count": 45
    },
    {
      "date": "2025-12-02",
      "count": 32
    }
  ],
  "total_detections": 77,
  "start_date": "2025-12-01",
  "end_date": "2025-12-02"
}
```

#### Response Fields

| Field                 | Type  | Description                                 |
| --------------------- | ----- | ------------------------------------------- |
| `data_points`         | array | Array of daily detection counts             |
| `data_points[].date`  | date  | The date                                    |
| `data_points[].count` | int   | Number of detections on this date           |
| `total_detections`    | int   | Total detection count across the date range |
| `start_date`          | date  | Query start date                            |
| `end_date`            | date  | Query end date                              |

#### Error Responses

| Status | Description                                    |
| ------ | ---------------------------------------------- |
| 400    | Bad request - `start_date` is after `end_date` |
| 422    | Validation error - Invalid date format         |
| 500    | Internal server error                          |

---

### Get Risk History

```
GET /api/analytics/risk-history
```

Returns daily counts of events grouped by risk level (low, medium, high, critical). Creates one data point per day even if there are no events.

#### Query Parameters

| Parameter    | Type | Required | Description             |
| ------------ | ---- | -------- | ----------------------- |
| `start_date` | date | Yes      | Start date (ISO format) |
| `end_date`   | date | Yes      | End date (ISO format)   |

#### Response

```json
{
  "data_points": [
    {
      "date": "2025-12-01",
      "low": 10,
      "medium": 5,
      "high": 2,
      "critical": 0
    },
    {
      "date": "2025-12-02",
      "low": 8,
      "medium": 3,
      "high": 1,
      "critical": 1
    }
  ],
  "start_date": "2025-12-01",
  "end_date": "2025-12-02"
}
```

#### Response Fields

| Field                    | Type  | Description                      |
| ------------------------ | ----- | -------------------------------- |
| `data_points`            | array | Array of daily risk level counts |
| `data_points[].date`     | date  | The date                         |
| `data_points[].low`      | int   | Count of low-risk events         |
| `data_points[].medium`   | int   | Count of medium-risk events      |
| `data_points[].high`     | int   | Count of high-risk events        |
| `data_points[].critical` | int   | Count of critical-risk events    |
| `start_date`             | date  | Query start date                 |
| `end_date`               | date  | Query end date                   |

#### Error Responses

| Status | Description                                    |
| ------ | ---------------------------------------------- |
| 400    | Bad request - `start_date` is after `end_date` |
| 422    | Validation error - Invalid date format         |
| 500    | Internal server error                          |

---

### Get Camera Uptime

```
GET /api/analytics/camera-uptime
```

Returns uptime percentage and detection count for each camera. Uptime is calculated as the number of days with at least one detection divided by the total days in the date range.

#### Query Parameters

| Parameter    | Type | Required | Description             |
| ------------ | ---- | -------- | ----------------------- |
| `start_date` | date | Yes      | Start date (ISO format) |
| `end_date`   | date | Yes      | End date (ISO format)   |

#### Response

```json
{
  "cameras": [
    {
      "camera_id": "front_door",
      "camera_name": "Front Door Camera",
      "uptime_percentage": 95.5,
      "detection_count": 1250
    },
    {
      "camera_id": "driveway",
      "camera_name": "Driveway Camera",
      "uptime_percentage": 88.2,
      "detection_count": 980
    }
  ],
  "start_date": "2025-12-01",
  "end_date": "2025-12-31"
}
```

#### Response Fields

| Field                         | Type   | Description                              |
| ----------------------------- | ------ | ---------------------------------------- |
| `cameras`                     | array  | Array of camera uptime data              |
| `cameras[].camera_id`         | string | Camera identifier                        |
| `cameras[].camera_name`       | string | Human-readable camera name               |
| `cameras[].uptime_percentage` | float  | Percentage of days with activity (0-100) |
| `cameras[].detection_count`   | int    | Total detections from this camera        |
| `start_date`                  | date   | Query start date                         |
| `end_date`                    | date   | Query end date                           |

#### Error Responses

| Status | Description                                    |
| ------ | ---------------------------------------------- |
| 400    | Bad request - `start_date` is after `end_date` |
| 422    | Validation error - Invalid date format         |
| 500    | Internal server error                          |

---

### Get Object Distribution

```
GET /api/analytics/object-distribution
```

Returns detection counts grouped by object type with percentages. Only includes detections with non-null object types.

#### Query Parameters

| Parameter    | Type | Required | Description             |
| ------------ | ---- | -------- | ----------------------- |
| `start_date` | date | Yes      | Start date (ISO format) |
| `end_date`   | date | Yes      | End date (ISO format)   |

#### Response

```json
{
  "object_types": [
    {
      "object_type": "person",
      "count": 450,
      "percentage": 65.2
    },
    {
      "object_type": "car",
      "count": 180,
      "percentage": 26.1
    },
    {
      "object_type": "dog",
      "count": 60,
      "percentage": 8.7
    }
  ],
  "total_detections": 690,
  "start_date": "2025-12-01",
  "end_date": "2025-12-31"
}
```

#### Response Fields

| Field                        | Type   | Description                              |
| ---------------------------- | ------ | ---------------------------------------- |
| `object_types`               | array  | Array of object type statistics          |
| `object_types[].object_type` | string | Object type name (e.g., "person", "car") |
| `object_types[].count`       | int    | Detection count for this object type     |
| `object_types[].percentage`  | float  | Percentage of total detections (0-100)   |
| `total_detections`           | int    | Total detections across all object types |
| `start_date`                 | date   | Query start date                         |
| `end_date`                   | date   | Query end date                           |

#### Error Responses

| Status | Description                                    |
| ------ | ---------------------------------------------- |
| 400    | Bad request - `start_date` is after `end_date` |
| 422    | Validation error - Invalid date format         |
| 500    | Internal server error                          |

---

## Usage Examples

### Python Example: Fetching Detection Trends

```python
import requests
from datetime import date, timedelta

# Get detection trends for the last 7 days
end_date = date.today()
start_date = end_date - timedelta(days=7)

response = requests.get(
    "http://localhost:8000/api/analytics/detection-trends",
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
)

data = response.json()
print(f"Total detections: {data['total_detections']}")
for point in data['data_points']:
    print(f"  {point['date']}: {point['count']} detections")
```

### JavaScript Example: Building a Risk Chart

```javascript
async function fetchRiskHistory(startDate, endDate) {
  const response = await fetch(
    `/api/analytics/risk-history?start_date=${startDate}&end_date=${endDate}`
  );
  const data = await response.json();

  // Transform for charting library
  return data.data_points.map((point) => ({
    date: point.date,
    Low: point.low,
    Medium: point.medium,
    High: point.high,
    Critical: point.critical,
  }));
}
```

## Related Documentation

- [Events API](events.md) - Query individual security events
- [Detections API](detections.md) - Query individual detections
- [System API](system.md) - System health and statistics
