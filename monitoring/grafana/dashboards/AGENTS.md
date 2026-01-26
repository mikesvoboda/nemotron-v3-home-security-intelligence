# Grafana Dashboards Directory - Agent Guide

## Purpose

This directory contains Grafana dashboard JSON definitions that are automatically provisioned when Grafana starts. Dashboards visualize the Home Security Intelligence system's health, performance, and AI pipeline metrics.

## Directory Contents

```
dashboards/
  AGENTS.md           # This file
  consolidated.json   # Main unified monitoring dashboard
  analytics.json      # Analytics dashboard
  hsi-profiling.json  # Profiling dashboard
  logs.json           # Logs dashboard
  tracing.json        # Tracing dashboard
```

## Key Files

### consolidated.json

**Purpose:** Main unified monitoring dashboard for the AI security pipeline.

**Dashboard UID:** `hsi-consolidated`

**Panels by Section:**

| Row                | Panel            | Type       | Data Source | Endpoint                        |
| ------------------ | ---------------- | ---------- | ----------- | ------------------------------- |
| System Overview    | System Health    | stat       | Backend-API | /api/system/health              |
| System Overview    | Total Cameras    | stat       | Backend-API | /api/system/stats               |
| System Overview    | Total Events     | stat       | Backend-API | /api/system/stats               |
| System Overview    | Total Detections | stat       | Backend-API | /api/system/stats               |
| System Overview    | Uptime           | stat       | Backend-API | /api/system/stats               |
| Queue Depths       | Detection Queue  | stat       | Backend-API | /api/system/telemetry           |
| Queue Depths       | Analysis Queue   | stat       | Backend-API | /api/system/telemetry           |
| Queue Depths       | Over Time        | timeseries | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Watch P95        | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Detect P95       | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Batch P95        | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Analysis P95     | stat       | Backend-API | /api/system/telemetry           |
| Pipeline Latencies | Histogram        | barchart   | Backend-API | /api/system/telemetry           |
| GPU Statistics     | GPU Utilization  | gauge      | Backend-API | /api/system/gpu                 |
| GPU Statistics     | GPU Temperature  | stat       | Backend-API | /api/system/gpu                 |
| GPU Statistics     | Memory Used      | stat       | Backend-API | /api/system/gpu                 |
| GPU Statistics     | Inference FPS    | stat       | AI-Detector | yolo26_inference_requests_total |
| Service Health     | Database         | stat       | Backend-API | /api/system/health              |
| Service Health     | Redis            | stat       | Backend-API | /api/system/health              |
| Service Health     | AI Services      | stat       | Backend-API | /api/system/health              |
| Service Health     | Readiness        | stat       | Backend-API | /api/system/health/ready        |

**Dashboard Settings:**

- Auto-refresh: 10 seconds
- Default time range: Last 1 hour
- Timezone: Browser

### analytics.json

**Purpose:** Analytics dashboard for system metrics and trends.

**Dashboard UID:** `hsi-analytics`

### hsi-profiling.json

**Purpose:** Profiling dashboard for performance analysis.

**Dashboard UID:** `hsi-profiling`

### logs.json

**Purpose:** Log aggregation and viewing dashboard.

**Dashboard UID:** `hsi-logs`

### tracing.json

**Purpose:** Distributed tracing dashboard.

**Dashboard UID:** `hsi-tracing`

## Dashboard Structure

### JSON Schema Overview

```json
{
  "title": "Dashboard name",
  "uid": "unique-id",
  "refresh": "10s",
  "panels": [
    {
      "id": 1,
      "type": "stat|gauge|timeseries|barchart",
      "title": "Panel title",
      "gridPos": { "h": 4, "w": 6, "x": 0, "y": 0 },
      "targets": [
        /* data queries */
      ],
      "fieldConfig": {
        /* display config */
      },
      "options": {
        /* panel-specific options */
      }
    }
  ]
}
```

### Grid Positioning

Grafana uses a 24-column grid:

- `w`: Width in columns (1-24)
- `h`: Height in rows
- `x`: X position (0-23)
- `y`: Y position (rows from top)

## Creating New Dashboards

### Manual Creation

1. Create new JSON file in this directory
2. Include required fields:
   ```json
   {
     "title": "My Dashboard",
     "uid": "my-dashboard-uid",
     "panels": [],
     "schemaVersion": 38
   }
   ```
3. Add panels as needed
4. Restart Grafana (`podman-compose -f docker-compose.prod.yml restart grafana`) or wait for auto-reload (30s)

### Export from Grafana UI

1. Create dashboard in Grafana UI
2. Go to Dashboard Settings (gear icon)
3. Click "JSON Model" in sidebar
4. Copy JSON content
5. Save to file in this directory

## Modifying Existing Dashboards

### Adding a Panel

1. Copy existing panel JSON as template
2. Change `id` to unique value
3. Update `gridPos` for positioning
4. Modify `targets` for data source
5. Adjust `fieldConfig` for display

### Changing Thresholds

```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    { "color": "green", "value": null },
    { "color": "yellow", "value": 50 },
    { "color": "red", "value": 80 }
  ]
}
```

### Updating JSONPath Queries

```json
"fields": [
  {
    "jsonPath": "$.queues.detection_queue",
    "name": "Detection Queue"
  }
]
```

## Troubleshooting

### Dashboard Not Appearing

1. Validate JSON syntax: `jq . consolidated.json`
2. Check for duplicate UIDs
3. Verify provisioning config: `../provisioning/dashboards/dashboard.yml`
4. Check Grafana logs: `docker compose logs grafana`

### Panel Shows Error

1. Check datasource UID matches `Backend-API` or `Prometheus`
2. Verify JSONPath matches API response structure
3. Test endpoint: `curl http://localhost:8000/api/system/health`

### No Data Displayed

1. Verify backend API is running
2. Check network connectivity between containers
3. Ensure API returns non-null values

## Related Files

- `../provisioning/dashboards/dashboard.yml` - Dashboard provisioning config
- `../provisioning/datasources/prometheus.yml` - Datasource definitions
- `../../prometheus.yml` - Prometheus scrape configuration
- `backend/api/routes/system.py` - Backend API endpoints
