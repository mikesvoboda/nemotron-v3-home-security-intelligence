# Grafana Directory - Agent Guide

## Purpose

This directory contains Grafana configuration for the Home Security Intelligence monitoring stack. Grafana provides visualization dashboards for system health, AI pipeline performance, GPU metrics, and security event statistics.

## Directory Structure

```
grafana/
  dashboards/              # Dashboard JSON definitions
    pipeline.json          # Main AI pipeline monitoring dashboard
  provisioning/            # Auto-provisioning configuration
    dashboards/            # Dashboard provider config
      dashboard.yml        # Tells Grafana where to find dashboards
    datasources/           # Datasource configuration
      prometheus.yml       # Prometheus + Backend API datasources
```

## Key Files

### dashboards/pipeline.json

**Purpose:** Main monitoring dashboard for the AI security pipeline.

**Dashboard Sections:**

1. **System Overview** (Row 1)

   - System Health status indicator (healthy/degraded/unhealthy)
   - Total Cameras count
   - Total Events count
   - Total Detections count
   - Uptime display

2. **Queue Depths** (Row 2)

   - Detection Queue Depth - items waiting for RT-DETRv2 processing
   - Analysis Queue Depth - batches waiting for Nemotron analysis
   - Queue Depths Over Time graph

3. **Pipeline Latencies** (Row 3)

   - Watch Latency (P95) - file watcher to queue time
   - Detection Latency (P95) - RT-DETRv2 inference time
   - Batch Latency (P95) - aggregation window time
   - Analysis Latency (P95) - Nemotron LLM processing time
   - Pipeline Latency Histogram - bar chart of all percentiles

4. **GPU Statistics** (Row 4)

   - GPU Utilization gauge (0-100%)
   - GPU Temperature
   - GPU Memory Used (VRAM in MB)
   - Inference FPS

5. **Service Health** (Row 5)
   - Database health indicator
   - Redis health indicator
   - AI Services health indicator
   - Readiness status (ready/degraded/not_ready)

**Dashboard Configuration:**

- UID: `hsi-pipeline`
- Auto-refresh: 10 seconds
- Default time range: Last 1 hour
- Timezone: Browser

### provisioning/dashboards/dashboard.yml

**Purpose:** Configures automatic dashboard provisioning.

**Settings:**

- Provider name: "Home Security Intelligence"
- Folder: "Home Security Intelligence" (folderUid: `hsi-dashboards`)
- Update interval: 30 seconds
- Allow UI updates: true (dashboards can be edited in UI)
- Dashboard path: `/var/lib/grafana/dashboards` (in container)

### provisioning/datasources/prometheus.yml

**Purpose:** Configures data sources for Grafana.

**Datasources:**

1. **Prometheus** (default)

   - Type: prometheus
   - URL: http://prometheus:9090
   - Time interval: 15s
   - HTTP method: POST

2. **Backend-API**
   - Type: marcusolsson-json-datasource
   - URL: http://backend:8000
   - Used for direct API calls from dashboard panels

## Usage

### Accessing Grafana

1. Start the monitoring stack:

   ```bash
   docker compose up -d grafana
   ```

2. Open http://localhost:3000

3. Default login: admin/admin (change on first login)

### Dashboard Navigation

1. Click the hamburger menu (top left)
2. Go to Dashboards
3. Select "Home Security Intelligence" folder
4. Click "Pipeline" dashboard

### Editing Dashboards

Dashboards can be edited in two ways:

**In Grafana UI:**

1. Open the dashboard
2. Click the gear icon (top right)
3. Make changes
4. Save dashboard

**In JSON files:**

1. Edit `dashboards/pipeline.json`
2. Restart Grafana or wait 30 seconds for auto-reload

### Adding New Dashboards

1. Create dashboard in Grafana UI
2. Export as JSON (Share > Export > Save to file)
3. Save JSON to `dashboards/` directory
4. Dashboard auto-provisions on next reload

## Important Patterns

### Panel Types Used

- **stat** - Single value display with optional sparkline
- **gauge** - Circular gauge for percentage values
- **timeseries** - Time-based line graphs
- **barchart** - Bar chart for histogram data

### Color Thresholds

Standard threshold patterns used:

```json
"thresholds": {
  "mode": "absolute",
  "steps": [
    { "color": "green", "value": null },
    { "color": "yellow", "value": 70 },
    { "color": "red", "value": 90 }
  ]
}
```

### Value Mappings

For text status to display values:

```json
"mappings": [
  {
    "options": {
      "healthy": { "color": "green", "text": "Healthy" },
      "unhealthy": { "color": "red", "text": "Unhealthy" }
    },
    "type": "value"
  }
]
```

### JSON Datasource Queries

For Backend-API datasource:

```json
"targets": [
  {
    "datasource": { "uid": "Backend-API" },
    "fields": [
      { "jsonPath": "$.status", "name": "Status" }
    ],
    "method": "GET",
    "urlPath": "/api/system/health"
  }
]
```

## Customization

### Changing Refresh Rate

Edit `pipeline.json`:

```json
"refresh": "10s"  // Change to "30s", "1m", etc.
```

### Adding New Panels

1. Copy an existing panel definition
2. Modify `id` (must be unique)
3. Update `gridPos` for positioning
4. Configure `targets` for data source
5. Set appropriate `fieldConfig` and `options`

### Creating New Dashboards

1. Create new JSON file in `dashboards/`
2. Set unique `uid` in dashboard JSON
3. Configure panels as needed
4. Dashboard auto-loads on Grafana restart

## Troubleshooting

### Dashboard Not Loading

1. Check Grafana logs: `docker compose logs grafana`
2. Verify JSON syntax: `jq . dashboards/pipeline.json`
3. Check provisioning path in `dashboard.yml`

### Datasource Connection Failed

1. Verify backend is running: `curl http://localhost:8000/api/system/health`
2. Check Prometheus is running: `curl http://localhost:9090/-/healthy`
3. Test from Grafana container: `docker compose exec grafana wget -qO- http://backend:8000/api/system/health`

### Panels Show "No Data"

1. Verify endpoint returns data: `curl http://localhost:8000/api/system/telemetry`
2. Check JSONPath in panel config matches API response structure
3. Ensure datasource UID matches

## Related Files

- `../prometheus.yml` - Prometheus scrape config
- `../json-exporter-config.yml` - JSON to metrics conversion
- `backend/api/routes/system.py` - API endpoints providing data
