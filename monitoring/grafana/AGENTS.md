# Grafana Directory - Agent Guide

## Purpose

This directory contains Grafana configuration for the Home Security Intelligence monitoring stack. Grafana provides visualization dashboards for system health, AI pipeline performance, GPU metrics, and security event statistics.

## Directory Structure

```
grafana/
  AGENTS.md                  # This file
  dashboards/                # Dashboard JSON definitions
    AGENTS.md                # Dashboards guide
    consolidated.json        # Main unified monitoring dashboard
    analytics.json           # Analytics dashboard
    hsi-profiling.json       # Profiling dashboard
    logs.json                # Logs dashboard
    tracing.json             # Tracing dashboard
  provisioning/              # Auto-provisioning configuration
    AGENTS.md                # Provisioning guide
    dashboards/
      dashboard.yml          # Dashboard provider config
    datasources/
      prometheus.yml         # Datasource configuration
```

## Key Files

### dashboards/consolidated.json

**Purpose:** Main unified monitoring dashboard for the AI security pipeline.

**Dashboard UID:** `hsi-consolidated`

**Sections:**

1. **System Overview** - Health status, cameras, events, detections, uptime
2. **Queue Depths** - Detection queue, analysis queue, time series
3. **Pipeline Latencies** - Watch, detect, batch, analyze P95 latencies
4. **GPU Statistics** - Utilization, temperature, VRAM, inference FPS
5. **Service Health** - Database, Redis, AI services status

### provisioning/dashboards/dashboard.yml

**Purpose:** Configures automatic dashboard loading.

**Settings:**

- Provider name: "Home Security Intelligence"
- Folder: "Home Security Intelligence" (folderUid: `hsi-dashboards`)
- Update interval: 30 seconds
- Allow UI updates: true
- Dashboard path: `/var/lib/grafana/dashboards` (in container)

### provisioning/datasources/prometheus.yml

**Purpose:** Configures data sources for Grafana.

**Datasources:**

1. **Prometheus** (default)

   - Type: prometheus
   - URL: http://prometheus:9090
   - Time interval: 15s

2. **Backend-API**
   - Type: marcusolsson-json-datasource
   - URL: http://backend:8000
   - Used for direct API calls

## Usage

### Accessing Grafana

1. Start monitoring stack: `podman-compose --profile monitoring -f docker-compose.prod.yml up -d`
2. Open http://localhost:3002
3. Anonymous access allows viewing dashboards (Viewer role only)
4. To make changes, log in: admin/admin (change via `GF_ADMIN_PASSWORD` env var)

Note: This project uses **Podman** for container management, not Docker.

**Security:** Anonymous access is restricted to Viewer role. Administrators must log in to modify dashboards, data sources, or settings.

### Dashboard Navigation

1. Click hamburger menu (top left)
2. Go to Dashboards
3. Select "Home Security Intelligence" folder
4. Click "Pipeline" dashboard

### Editing Dashboards

**In Grafana UI:**

1. Open dashboard
2. Click gear icon (top right)
3. Make changes
4. Save dashboard

**In JSON files:**

1. Edit `dashboards/consolidated.json`
2. Restart Grafana or wait 30 seconds for auto-reload

### Adding New Dashboards

1. Create dashboard in Grafana UI
2. Export as JSON (Share > Export > Save to file)
3. Save JSON to `dashboards/` directory
4. Dashboard auto-provisions on reload

## Important Patterns

### Panel Types Used

- **stat** - Single value display with optional sparkline
- **gauge** - Circular gauge for percentage values
- **timeseries** - Time-based line graphs
- **barchart** - Bar chart for histogram data

### Color Thresholds

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

## Troubleshooting

### Dashboard Not Loading

1. Check Grafana logs: `docker compose logs grafana`
2. Verify JSON syntax: `jq . dashboards/consolidated.json`
3. Check provisioning path in `dashboard.yml`

### Datasource Connection Failed

1. Verify backend is running: `curl http://localhost:8000/api/system/health`
2. Check Prometheus: `curl http://localhost:9090/-/healthy`
3. Test from container: `docker compose exec grafana wget -qO- http://backend:8000/api/system/health`

### Panels Show "No Data"

1. Verify endpoint returns data: `curl http://localhost:8000/api/system/telemetry`
2. Check JSONPath in panel config
3. Ensure datasource UID matches

## Required Grafana Plugins

The Backend-API datasource requires:

- `marcusolsson-json-datasource` - JSON API datasource plugin

Install via environment variable:

```yaml
grafana:
  environment:
    - GF_INSTALL_PLUGINS=marcusolsson-json-datasource
```

## Related Files

- `../prometheus.yml` - Prometheus scrape config
- `../json-exporter-config.yml` - JSON to metrics conversion
- `backend/api/routes/system.py` - API endpoints providing data
