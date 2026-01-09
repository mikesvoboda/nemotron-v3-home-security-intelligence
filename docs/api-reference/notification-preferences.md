---
title: Notification Preferences API
description: API endpoints for managing notification settings
source_refs:
  - backend/api/routes/notification_preferences.py
  - backend/api/schemas/notification_preferences.py
---

# Notification Preferences API

The Notification Preferences API provides endpoints for managing global notification settings, per-camera notification configurations, and quiet hours periods.

## Base URL

```
/api/notification-preferences
```

## Risk Levels

| Level    | Value      | Description                      |
| -------- | ---------- | -------------------------------- |
| Low      | `low`      | Low-risk events (score 0-39)     |
| Medium   | `medium`   | Medium-risk events (score 40-59) |
| High     | `high`     | High-risk events (score 60-79)   |
| Critical | `critical` | Critical events (score 80-100)   |

## Notification Sounds

| Sound     | Description                 |
| --------- | --------------------------- |
| `none`    | No sound                    |
| `default` | System default notification |
| `alert`   | Alert tone                  |
| `chime`   | Gentle chime                |
| `urgent`  | Urgent notification sound   |

---

## Global Preferences

### Get Global Preferences

```
GET /api/notification-preferences
```

Returns the global notification settings.

#### Response

```json
{
  "id": 1,
  "enabled": true,
  "sound": "default",
  "risk_filters": ["critical", "high", "medium"]
}
```

#### Response Fields

| Field          | Type    | Description                                |
| -------------- | ------- | ------------------------------------------ |
| `id`           | int     | Preferences record ID (always 1)           |
| `enabled`      | boolean | Whether notifications are enabled globally |
| `sound`        | string  | Notification sound selection               |
| `risk_filters` | array   | Risk levels that trigger notifications     |

---

### Update Global Preferences

```
PUT /api/notification-preferences
```

Updates the global notification settings.

#### Request Body

```json
{
  "enabled": true,
  "sound": "alert",
  "risk_filters": ["critical", "high"]
}
```

| Field          | Type    | Required | Description                            |
| -------------- | ------- | -------- | -------------------------------------- |
| `enabled`      | boolean | No       | Whether notifications are enabled      |
| `sound`        | string  | No       | Notification sound                     |
| `risk_filters` | array   | No       | Risk levels that trigger notifications |

#### Response

Returns the updated preferences (same format as GET).

#### Error Responses

| Status | Description                               |
| ------ | ----------------------------------------- |
| 400    | Bad request - Invalid sound or risk level |
| 422    | Validation error                          |
| 500    | Internal server error                     |

---

## Camera Settings

### Get All Camera Settings

```
GET /api/notification-preferences/cameras
```

Returns notification settings for all cameras.

#### Response

```json
{
  "settings": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "camera_id": "front_door",
      "enabled": true,
      "risk_threshold": 50
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "camera_id": "driveway",
      "enabled": false,
      "risk_threshold": 0
    }
  ],
  "count": 2
}
```

#### Response Fields

| Field                       | Type    | Description                           |
| --------------------------- | ------- | ------------------------------------- |
| `settings`                  | array   | List of camera notification settings  |
| `settings[].id`             | string  | Setting UUID                          |
| `settings[].camera_id`      | string  | Camera identifier                     |
| `settings[].enabled`        | boolean | Whether notifications are enabled     |
| `settings[].risk_threshold` | int     | Minimum risk score to trigger (0-100) |
| `count`                     | int     | Total number of settings              |

---

### Get Camera Setting

```
GET /api/notification-preferences/cameras/{camera_id}
```

Returns notification setting for a specific camera.

#### Path Parameters

| Parameter   | Type   | Description       |
| ----------- | ------ | ----------------- |
| `camera_id` | string | Camera identifier |

#### Response

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "camera_id": "front_door",
  "enabled": true,
  "risk_threshold": 50
}
```

#### Error Responses

| Status | Description                           |
| ------ | ------------------------------------- |
| 404    | Camera notification setting not found |
| 500    | Internal server error                 |

---

### Update Camera Setting

```
PUT /api/notification-preferences/cameras/{camera_id}
```

Creates or updates notification setting for a camera.

#### Path Parameters

| Parameter   | Type   | Description       |
| ----------- | ------ | ----------------- |
| `camera_id` | string | Camera identifier |

#### Request Body

```json
{
  "enabled": true,
  "risk_threshold": 75
}
```

| Field            | Type    | Required | Description                           |
| ---------------- | ------- | -------- | ------------------------------------- |
| `enabled`        | boolean | No       | Whether notifications are enabled     |
| `risk_threshold` | int     | No       | Minimum risk score to trigger (0-100) |

#### Response

Returns the updated camera setting (same format as GET).

#### Error Responses

| Status | Description           |
| ------ | --------------------- |
| 404    | Camera not found      |
| 422    | Validation error      |
| 500    | Internal server error |

---

## Quiet Hours

### Get Quiet Hours

```
GET /api/notification-preferences/quiet-hours
```

Returns all quiet hours periods.

#### Response

```json
{
  "periods": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "label": "Night Hours",
      "start_time": "22:00:00",
      "end_time": "23:59:00",
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "label": "Work Hours",
      "start_time": "09:00:00",
      "end_time": "17:00:00",
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
    }
  ],
  "count": 2
}
```

#### Response Fields

| Field                  | Type   | Description                     |
| ---------------------- | ------ | ------------------------------- |
| `periods`              | array  | List of quiet hours periods     |
| `periods[].id`         | string | Period UUID                     |
| `periods[].label`      | string | Human-readable period name      |
| `periods[].start_time` | string | Start time (HH:MM:SS format)    |
| `periods[].end_time`   | string | End time (HH:MM:SS format)      |
| `periods[].days`       | array  | Days when this period is active |
| `count`                | int    | Total number of periods         |

---

### Create Quiet Hours Period

```
POST /api/notification-preferences/quiet-hours
```

Creates a new quiet hours period.

#### Request Body

```json
{
  "label": "Dinner Time",
  "start_time": "18:00:00",
  "end_time": "20:00:00",
  "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
}
```

| Field        | Type   | Required | Description                     |
| ------------ | ------ | -------- | ------------------------------- |
| `label`      | string | Yes      | Human-readable period name      |
| `start_time` | string | Yes      | Start time (HH:MM:SS format)    |
| `end_time`   | string | Yes      | End time (HH:MM:SS format)      |
| `days`       | array  | Yes      | Days when this period is active |

**Valid day values:** `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`

#### Response

Returns the created period (status 201).

#### Error Responses

| Status | Description                              |
| ------ | ---------------------------------------- |
| 400    | Bad request - `start_time` >= `end_time` |
| 422    | Validation error                         |
| 500    | Internal server error                    |

---

### Delete Quiet Hours Period

```
DELETE /api/notification-preferences/quiet-hours/{period_id}
```

Deletes a quiet hours period.

#### Path Parameters

| Parameter   | Type   | Description |
| ----------- | ------ | ----------- |
| `period_id` | string | Period UUID |

#### Response

Status 204 (No Content) on success.

#### Error Responses

| Status | Description                  |
| ------ | ---------------------------- |
| 404    | Quiet hours period not found |
| 500    | Internal server error        |

---

## Usage Examples

### Python Example: Configure Notifications

```python
import requests

BASE_URL = "http://localhost:8000/api/notification-preferences"

# Enable notifications for critical and high-risk events only
response = requests.put(
    BASE_URL,
    json={
        "enabled": True,
        "sound": "alert",
        "risk_filters": ["critical", "high"]
    }
)
print(f"Global settings updated: {response.json()}")

# Set higher threshold for front door camera
response = requests.put(
    f"{BASE_URL}/cameras/front_door",
    json={
        "enabled": True,
        "risk_threshold": 75  # Only critical events
    }
)
print(f"Camera setting updated: {response.json()}")

# Add quiet hours for nighttime
response = requests.post(
    f"{BASE_URL}/quiet-hours",
    json={
        "label": "Sleep Hours",
        "start_time": "23:00:00",
        "end_time": "23:59:00",
        "days": ["sunday", "monday", "tuesday", "wednesday", "thursday"]
    }
)
print(f"Quiet hours created: {response.json()}")
```

### JavaScript Example: Managing Quiet Hours

```javascript
async function getQuietHours() {
  const response = await fetch('/api/notification-preferences/quiet-hours');
  const data = await response.json();
  return data.periods;
}

async function createQuietHours(label, startTime, endTime, days) {
  // Note: startTime and endTime should be in HH:MM:SS format
  const response = await fetch('/api/notification-preferences/quiet-hours', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      label,
      start_time: startTime, // e.g., "22:00:00"
      end_time: endTime, // e.g., "23:59:00"
      days,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }

  return response.json();
}

async function deleteQuietHours(periodId) {
  const response = await fetch(`/api/notification-preferences/quiet-hours/${periodId}`, {
    method: 'DELETE',
  });

  if (!response.ok && response.status !== 204) {
    const error = await response.json();
    throw new Error(error.detail);
  }
}
```

## Related Documentation

- [Alerts API](alerts.md) - Alert delivery and configuration
- [Events API](events.md) - Security event data
- [System API](system.md) - System health and status
