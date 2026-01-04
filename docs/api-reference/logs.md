---
title: Logs API
description: REST API endpoints for log management
source_refs:
  - backend/api/routes/logs.py
  - backend/api/schemas/logs.py
  - backend/models/log.py
---

# Logs API

The Logs API provides endpoints for viewing and querying application logs. This includes both backend server logs and frontend client logs submitted from the browser.

## Endpoints Overview

| Method | Endpoint             | Description               |
| ------ | -------------------- | ------------------------- |
| GET    | `/api/logs`          | List logs with filtering  |
| GET    | `/api/logs/stats`    | Get log statistics        |
| GET    | `/api/logs/{log_id}` | Get specific log entry    |
| POST   | `/api/logs/frontend` | Submit frontend log entry |

---

## GET /api/logs

List log entries with optional filtering and pagination.

**Source:** [`list_logs`](../../backend/api/routes/logs.py:22)

**Parameters:**

| Name         | Type     | In    | Required | Description                                                 |
| ------------ | -------- | ----- | -------- | ----------------------------------------------------------- |
| `level`      | string   | query | No       | Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `component`  | string   | query | No       | Filter by component/module name                             |
| `camera_id`  | string   | query | No       | Filter by associated camera ID                              |
| `source`     | string   | query | No       | Filter by source (`backend`, `frontend`)                    |
| `search`     | string   | query | No       | Search in message text                                      |
| `start_date` | datetime | query | No       | Filter from date (ISO format)                               |
| `end_date`   | datetime | query | No       | Filter to date (ISO format)                                 |
| `limit`      | integer  | query | No       | Page size (1-1000, default: 100)                            |
| `offset`     | integer  | query | No       | Page offset (default: 0)                                    |

**Response:** `200 OK`

```json
{
  "logs": [
    {
      "id": 1,
      "timestamp": "2025-12-23T10:30:00Z",
      "level": "INFO",
      "component": "detection_worker",
      "message": "Processing image from front_door camera",
      "camera_id": "front_door",
      "event_id": null,
      "request_id": "abc123",
      "detection_id": null,
      "duration_ms": 150,
      "extra": {
        "image_path": "/export/foscam/front_door/image.jpg"
      },
      "source": "backend"
    }
  ],
  "count": 1,
  "limit": 100,
  "offset": 0
}
```

**Response Fields:**

| Field    | Type    | Description                  |
| -------- | ------- | ---------------------------- |
| `logs`   | array   | List of log entries          |
| `count`  | integer | Total count matching filters |
| `limit`  | integer | Page size used               |
| `offset` | integer | Page offset used             |

**Log Levels:**

| Level      | Description                           |
| ---------- | ------------------------------------- |
| `DEBUG`    | Detailed debugging information        |
| `INFO`     | General informational messages        |
| `WARNING`  | Warning messages for potential issues |
| `ERROR`    | Error messages for failures           |
| `CRITICAL` | Critical errors requiring attention   |

**Example Request:**

```bash
# List all logs
curl http://localhost:8000/api/logs

# Filter by level
curl "http://localhost:8000/api/logs?level=ERROR"

# Filter by component
curl "http://localhost:8000/api/logs?component=detection_worker"

# Search in messages
curl "http://localhost:8000/api/logs?search=timeout"

# Filter by date range
curl "http://localhost:8000/api/logs?start_date=2025-12-23T00:00:00Z&end_date=2025-12-23T23:59:59Z"
```

---

## GET /api/logs/stats

Get log statistics for dashboard display.

**Source:** [`get_log_stats`](../../backend/api/routes/logs.py:74)

**Response:** `200 OK`

```json
{
  "total_today": 5000,
  "errors_today": 15,
  "warnings_today": 50,
  "by_component": {
    "detection_worker": 1500,
    "analysis_worker": 1000,
    "file_watcher": 800,
    "api": 500
  },
  "by_level": {
    "INFO": 4000,
    "DEBUG": 935,
    "WARNING": 50,
    "ERROR": 15
  },
  "top_component": "detection_worker"
}
```

**Response Fields:**

| Field            | Type    | Description                        |
| ---------------- | ------- | ---------------------------------- |
| `total_today`    | integer | Total number of logs today         |
| `errors_today`   | integer | Number of ERROR level logs today   |
| `warnings_today` | integer | Number of WARNING level logs today |
| `by_component`   | object  | Count breakdown by component       |
| `by_level`       | object  | Count breakdown by log level       |
| `top_component`  | string  | Most active component (nullable)   |

**Example Request:**

```bash
curl http://localhost:8000/api/logs/stats
```

---

## GET /api/logs/{log_id}

Get a specific log entry by its ID.

**Source:** [`get_log`](../../backend/api/routes/logs.py:134)

**Parameters:**

| Name     | Type    | In   | Required | Description  |
| -------- | ------- | ---- | -------- | ------------ |
| `log_id` | integer | path | Yes      | Log entry ID |

**Response:** `200 OK`

```json
{
  "id": 1,
  "timestamp": "2025-12-23T10:30:00Z",
  "level": "INFO",
  "component": "detection_worker",
  "message": "Processing image from front_door camera",
  "camera_id": "front_door",
  "event_id": null,
  "request_id": "abc123",
  "detection_id": null,
  "duration_ms": 150,
  "extra": {
    "image_path": "/export/foscam/front_door/image.jpg"
  },
  "source": "backend"
}
```

**Response Fields:**

| Field          | Type     | Description                                   |
| -------------- | -------- | --------------------------------------------- |
| `id`           | integer  | Log entry ID                                  |
| `timestamp`    | datetime | Log timestamp                                 |
| `level`        | string   | Log level                                     |
| `component`    | string   | Component/module name                         |
| `message`      | string   | Log message                                   |
| `camera_id`    | string   | Associated camera ID (nullable)               |
| `event_id`     | integer  | Associated event ID (nullable)                |
| `request_id`   | string   | Request correlation ID (nullable)             |
| `detection_id` | integer  | Associated detection ID (nullable)            |
| `duration_ms`  | integer  | Operation duration in milliseconds (nullable) |
| `extra`        | object   | Additional structured data (nullable)         |
| `source`       | string   | Log source (`backend` or `frontend`)          |

**Errors:**

| Code | Description         |
| ---- | ------------------- |
| 404  | Log entry not found |

**Example Request:**

```bash
curl http://localhost:8000/api/logs/1
```

---

## POST /api/logs/frontend

Submit a log entry from the frontend application.

**Source:** [`create_frontend_log`](../../backend/api/routes/logs.py:153)

This endpoint allows the frontend React application to send logs to the backend for centralized logging and debugging.

**Request Body:**

```json
{
  "level": "ERROR",
  "component": "EventTimeline",
  "message": "Failed to load events",
  "extra": {
    "error": "Network timeout",
    "retryCount": 3
  },
  "user_agent": "Mozilla/5.0...",
  "url": "http://localhost:5173/events"
}
```

**Request Fields:**

| Field        | Type   | Required | Constraints                       | Description                        |
| ------------ | ------ | -------- | --------------------------------- | ---------------------------------- |
| `level`      | string | Yes      | DEBUG/INFO/WARNING/ERROR/CRITICAL | Log level                          |
| `component`  | string | Yes      | max 50 chars                      | Frontend component name            |
| `message`    | string | Yes      | max 2000 chars                    | Log message                        |
| `extra`      | object | No       | -                                 | Additional context data            |
| `user_agent` | string | No       | -                                 | Browser user agent (auto-detected) |
| `url`        | string | No       | -                                 | Page URL where log occurred        |

**Response:** `201 Created`

```json
{
  "status": "created"
}
```

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/logs/frontend \
  -H "Content-Type: application/json" \
  -d '{
    "level": "ERROR",
    "component": "EventTimeline",
    "message": "Failed to load events",
    "extra": {"error": "Network timeout"}
  }'
```

---

## Data Models

### LogEntry

Full log entry response model.

**Source:** [`LogEntry`](../../backend/api/schemas/logs.py:9)

| Field          | Type     | Description                                   |
| -------------- | -------- | --------------------------------------------- |
| `id`           | integer  | Log entry ID                                  |
| `timestamp`    | datetime | Log timestamp                                 |
| `level`        | string   | Log level                                     |
| `component`    | string   | Component/module name                         |
| `message`      | string   | Log message                                   |
| `camera_id`    | string   | Associated camera ID (nullable)               |
| `event_id`     | integer  | Associated event ID (nullable)                |
| `request_id`   | string   | Request correlation ID (nullable)             |
| `detection_id` | integer  | Associated detection ID (nullable)            |
| `duration_ms`  | integer  | Operation duration in milliseconds (nullable) |
| `extra`        | object   | Additional structured data (nullable)         |
| `source`       | string   | Log source (default: `backend`)               |

### LogStats

Statistics response model.

**Source:** [`LogStats`](../../backend/api/schemas/logs.py:37)

| Field            | Type    | Description                      |
| ---------------- | ------- | -------------------------------- |
| `total_today`    | integer | Total logs today                 |
| `errors_today`   | integer | Error count today                |
| `warnings_today` | integer | Warning count today              |
| `by_component`   | object  | Counts by component              |
| `by_level`       | object  | Counts by level                  |
| `top_component`  | string  | Most active component (nullable) |

### FrontendLogCreate

Request model for frontend log submission.

**Source:** [`FrontendLogCreate`](../../backend/api/schemas/logs.py:48)

| Field        | Type   | Required | Description             |
| ------------ | ------ | -------- | ----------------------- |
| `level`      | string | Yes      | Log level               |
| `component`  | string | Yes      | Frontend component name |
| `message`    | string | Yes      | Log message             |
| `extra`      | object | No       | Additional context      |
| `user_agent` | string | No       | Browser user agent      |
| `url`        | string | No       | Page URL                |

---

## Related Documentation

- [System API](system.md) - System monitoring and configuration
- [Audit API](audit.md) - Security audit logging
