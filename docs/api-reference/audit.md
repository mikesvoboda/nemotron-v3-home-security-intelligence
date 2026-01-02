---
title: Audit API
description: REST API endpoints for audit log management
source_refs:
  - backend/api/routes/audit.py
  - backend/api/schemas/audit.py
  - backend/models/audit.py
---

# Audit API

The Audit API provides endpoints for viewing and querying audit logs. Audit logs track security-sensitive operations in the system including camera management, configuration changes, and event acknowledgements.

## Endpoints Overview

| Method | Endpoint                | Description              |
| ------ | ----------------------- | ------------------------ |
| GET    | `/api/audit`            | List audit entries       |
| GET    | `/api/audit/stats`      | Get audit statistics     |
| GET    | `/api/audit/{audit_id}` | Get specific audit entry |

---

## GET /api/audit

List audit log entries with optional filtering and pagination.

**Source:** [`list_audit_logs`](../../backend/api/routes/audit.py:22)

**Parameters:**

| Name            | Type     | In    | Required | Description                             |
| --------------- | -------- | ----- | -------- | --------------------------------------- |
| `action`        | string   | query | No       | Filter by action type                   |
| `resource_type` | string   | query | No       | Filter by resource type                 |
| `resource_id`   | string   | query | No       | Filter by specific resource ID          |
| `actor`         | string   | query | No       | Filter by actor                         |
| `status`        | string   | query | No       | Filter by status (`success`, `failure`) |
| `start_date`    | datetime | query | No       | Filter from date (ISO format)           |
| `end_date`      | datetime | query | No       | Filter to date (ISO format)             |
| `limit`         | integer  | query | No       | Page size (1-1000, default: 100)        |
| `offset`        | integer  | query | No       | Page offset (default: 0)                |

**Response:** `200 OK`

```json
{
  "logs": [
    {
      "id": 1,
      "timestamp": "2025-12-23T10:30:00Z",
      "action": "camera_created",
      "resource_type": "camera",
      "resource_id": "123e4567-e89b-12d3-a456-426614174000",
      "actor": "anonymous",
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0...",
      "details": {
        "name": "Front Door",
        "folder_path": "/export/foscam/front_door"
      },
      "status": "success"
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
| `logs`   | array   | List of audit log entries    |
| `count`  | integer | Total count matching filters |
| `limit`  | integer | Page size used               |
| `offset` | integer | Page offset used             |

**Action Types:**

| Action               | Description                          |
| -------------------- | ------------------------------------ |
| `camera_created`     | A camera was added to the system     |
| `camera_updated`     | A camera configuration was modified  |
| `camera_deleted`     | A camera was removed from the system |
| `event_acknowledged` | An event was acknowledged by a user  |
| `event_archived`     | An event was archived                |
| `alert_created`      | A new alert rule was created         |
| `alert_updated`      | An alert rule was modified           |
| `alert_deleted`      | An alert rule was removed            |
| `settings_changed`   | System settings were modified        |

**Example Request:**

```bash
# List all audit logs
curl http://localhost:8000/api/audit

# Filter by action type
curl "http://localhost:8000/api/audit?action=camera_created"

# Filter by date range
curl "http://localhost:8000/api/audit?start_date=2025-12-01T00:00:00Z&end_date=2025-12-31T23:59:59Z"

# Paginate results
curl "http://localhost:8000/api/audit?limit=50&offset=100"
```

---

## GET /api/audit/stats

Get aggregated audit log statistics for dashboard display.

**Source:** [`get_audit_stats`](../../backend/api/routes/audit.py:77)

**Response:** `200 OK`

```json
{
  "total_logs": 1234,
  "logs_today": 45,
  "by_action": {
    "camera_created": 10,
    "camera_updated": 25,
    "settings_changed": 5,
    "event_acknowledged": 100
  },
  "by_resource_type": {
    "camera": 35,
    "event": 100,
    "settings": 5
  },
  "by_status": {
    "success": 140,
    "failure": 0
  },
  "recent_actors": ["anonymous", "admin"]
}
```

**Response Fields:**

| Field              | Type    | Description                             |
| ------------------ | ------- | --------------------------------------- |
| `total_logs`       | integer | Total number of audit log entries       |
| `logs_today`       | integer | Number of entries created today         |
| `by_action`        | object  | Count breakdown by action type          |
| `by_resource_type` | object  | Count breakdown by resource type        |
| `by_status`        | object  | Count breakdown by status               |
| `recent_actors`    | array   | List of recently active actors (top 10) |

**Example Request:**

```bash
curl http://localhost:8000/api/audit/stats
```

---

## GET /api/audit/{audit_id}

Get a specific audit log entry by its ID.

**Source:** [`get_audit_log`](../../backend/api/routes/audit.py:155)

**Parameters:**

| Name       | Type    | In   | Required | Description        |
| ---------- | ------- | ---- | -------- | ------------------ |
| `audit_id` | integer | path | Yes      | Audit log entry ID |

**Response:** `200 OK`

```json
{
  "id": 1,
  "timestamp": "2025-12-23T10:30:00Z",
  "action": "camera_created",
  "resource_type": "camera",
  "resource_id": "123e4567-e89b-12d3-a456-426614174000",
  "actor": "anonymous",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "details": {
    "name": "Front Door",
    "folder_path": "/export/foscam/front_door"
  },
  "status": "success"
}
```

**Response Fields:**

| Field           | Type     | Description                                       |
| --------------- | -------- | ------------------------------------------------- |
| `id`            | integer  | Audit log entry ID                                |
| `timestamp`     | datetime | When the action occurred                          |
| `action`        | string   | The action performed                              |
| `resource_type` | string   | Type of resource (camera, event, alert, settings) |
| `resource_id`   | string   | ID of the specific resource (nullable)            |
| `actor`         | string   | User or system that performed the action          |
| `ip_address`    | string   | IP address of the client (nullable)               |
| `user_agent`    | string   | User agent string of the client (nullable)        |
| `details`       | object   | Action-specific details (nullable)                |
| `status`        | string   | Status of the action (`success` or `failure`)     |

**Errors:**

| Code | Description               |
| ---- | ------------------------- |
| 404  | Audit log entry not found |

**Example Request:**

```bash
curl http://localhost:8000/api/audit/1
```

---

## Data Models

### AuditLogResponse

Full audit log entry response model.

**Source:** [`AuditLogResponse`](../../backend/api/schemas/audit.py:11)

| Field           | Type     | Description                                |
| --------------- | -------- | ------------------------------------------ |
| `id`            | integer  | Audit log entry ID                         |
| `timestamp`     | datetime | When the action occurred                   |
| `action`        | string   | The action performed                       |
| `resource_type` | string   | Type of resource                           |
| `resource_id`   | string   | ID of the specific resource (nullable)     |
| `actor`         | string   | User or system that performed the action   |
| `ip_address`    | string   | IP address of the client (nullable)        |
| `user_agent`    | string   | User agent string of the client (nullable) |
| `details`       | object   | Action-specific details (nullable)         |
| `status`        | string   | Status of the action                       |

### AuditLogStats

Statistics response model.

**Source:** [`AuditLogStats`](../../backend/api/schemas/audit.py:39)

| Field              | Type    | Description                |
| ------------------ | ------- | -------------------------- |
| `total_logs`       | integer | Total number of audit logs |
| `logs_today`       | integer | Number of logs today       |
| `by_action`        | object  | Counts by action type      |
| `by_resource_type` | object  | Counts by resource type    |
| `by_status`        | object  | Counts by status           |
| `recent_actors`    | array   | Recently active actors     |

---

## Related Documentation

- [System API](system.md) - System configuration and monitoring
- [Cameras API](cameras.md) - Camera management
- [Events API](events.md) - Event management
