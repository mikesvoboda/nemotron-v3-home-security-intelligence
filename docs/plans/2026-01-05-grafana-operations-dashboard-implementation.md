# Grafana Operations Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a comprehensive Grafana dashboard (`hsi-operations`) exposing all available Prometheus metrics in 8 collapsible rows with timeseries panels.

**Architecture:** Single JSON dashboard file with 8 row panels containing ~62 visualization panels. All panels use timeseries type with table legends showing Last/Min/Max/Avg. Dashboard auto-refreshes every 5 seconds with default 15-minute time window.

**Tech Stack:** Grafana 10.x dashboard JSON, Prometheus datasource, JSON datasource for API endpoints

---

## Prerequisites

Before starting, understand these key references:

- **Existing dashboard pattern:** `monitoring/grafana/dashboards/pipeline.json`
- **Available metrics:** `backend/core/metrics.py`
- **Prometheus config:** `monitoring/prometheus.yml`
- **Design spec:** `docs/plans/2026-01-05-grafana-operations-dashboard-design.md`

**Datasource UIDs (from existing dashboard):**

- Prometheus: `PBFA97CFB590B2093`
- JSON (Backend API): `P6CAC8AF542CA101E`

---

## Task 1: Create Dashboard Scaffold

**Files:**

- Create: `monitoring/grafana/dashboards/operations.json`

**Step 1: Create the dashboard scaffold with metadata and time settings**

```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": { "type": "grafana", "uid": "-- Grafana --" },
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "description": "Home Security Intelligence - Operations Dashboard with all metrics",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": true,
  "panels": [],
  "refresh": "5s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["hsi", "operations", "monitoring"],
  "templating": { "list": [] },
  "time": { "from": "now-15m", "to": "now" },
  "timepicker": {
    "refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h"]
  },
  "timezone": "browser",
  "title": "Home Security Intelligence - Operations",
  "uid": "hsi-operations",
  "version": 1,
  "weekStart": ""
}
```

**Step 2: Validate JSON syntax**

Run: `python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null && echo "Valid JSON"`
Expected: `Valid JSON`

**Step 3: Commit scaffold**

```bash
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add operations dashboard scaffold"
```

---

## Task 2: Add Quick Time Selector Row

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add time selector row with link panels**

Add to the `panels` array:

```json
{
  "collapsed": false,
  "gridPos": { "h": 1, "w": 24, "x": 0, "y": 0 },
  "id": 1,
  "panels": [],
  "title": "Quick Time Range",
  "type": "row"
},
{
  "datasource": { "type": "datasource", "uid": "-- Dashboard --" },
  "gridPos": { "h": 2, "w": 24, "x": 0, "y": 1 },
  "id": 2,
  "options": {
    "code": { "language": "plaintext", "showLineNumbers": false },
    "content": "<div style=\"display: flex; gap: 10px; justify-content: center; padding: 5px;\">\n  <a href=\"d/hsi-operations?from=now-15m&to=now\" style=\"padding: 8px 16px; background: #3274d9; color: white; border-radius: 4px; text-decoration: none;\">15m</a>\n  <a href=\"d/hsi-operations?from=now-1h&to=now\" style=\"padding: 8px 16px; background: #3274d9; color: white; border-radius: 4px; text-decoration: none;\">1h</a>\n  <a href=\"d/hsi-operations?from=now-6h&to=now\" style=\"padding: 8px 16px; background: #3274d9; color: white; border-radius: 4px; text-decoration: none;\">6h</a>\n  <a href=\"d/hsi-operations?from=now-24h&to=now\" style=\"padding: 8px 16px; background: #3274d9; color: white; border-radius: 4px; text-decoration: none;\">24h</a>\n  <a href=\"d/hsi-operations?from=now-7d&to=now\" style=\"padding: 8px 16px; background: #3274d9; color: white; border-radius: 4px; text-decoration: none;\">7d</a>\n</div>",
    "mode": "html"
  },
  "pluginVersion": "10.2.3",
  "title": "",
  "transparent": true,
  "type": "text"
}
```

**Step 2: Validate JSON and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add quick time selector row"
```

---

## Task 3: Add Row 1 - System Health (8 panels)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add System Health row header**

```json
{
  "collapsed": false,
  "gridPos": { "h": 1, "w": 24, "x": 0, "y": 3 },
  "id": 10,
  "panels": [],
  "title": "System Health",
  "type": "row"
}
```

**Step 2: Add Health Status panel (timeseries)**

```json
{
  "datasource": { "type": "marcusolsson-json-datasource", "uid": "P6CAC8AF542CA101E" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "barAlignment": 0,
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [
        {
          "options": { "ready": { "color": "#73BF69", "index": 0, "text": "Healthy" } },
          "type": "value"
        },
        {
          "options": { "degraded": { "color": "#FF9830", "index": 1, "text": "Degraded" } },
          "type": "value"
        },
        {
          "options": { "not_ready": { "color": "#F2495C", "index": 2, "text": "Unhealthy" } },
          "type": "value"
        }
      ],
      "thresholds": {
        "mode": "absolute",
        "steps": [{ "color": "#73BF69", "value": null }]
      }
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 6, "x": 0, "y": 4 },
  "id": 11,
  "options": {
    "legend": {
      "calcs": ["lastNotNull"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "marcusolsson-json-datasource", "uid": "P6CAC8AF542CA101E" },
      "fields": [{ "jsonPath": "$.status", "name": "Health Status" }],
      "method": "GET",
      "refId": "A",
      "urlPath": "/api/system/health/ready"
    }
  ],
  "title": "Health Status",
  "type": "timeseries"
}
```

**Step 3: Add Uptime panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
      "unit": "dtdurations"
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 6, "x": 6, "y": 4 },
  "id": 12,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "min", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_uptime_seconds",
      "legendFormat": "Uptime",
      "refId": "A"
    }
  ],
  "title": "Uptime",
  "type": "timeseries"
}
```

**Step 4: Add Database Status panel**

```json
{
  "datasource": { "type": "marcusolsson-json-datasource", "uid": "P6CAC8AF542CA101E" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "stepAfter",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [
        {
          "options": { "healthy": { "color": "#73BF69", "index": 0, "text": "Connected" } },
          "type": "value"
        },
        {
          "options": { "unhealthy": { "color": "#F2495C", "index": 1, "text": "Disconnected" } },
          "type": "value"
        }
      ],
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] }
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 3, "x": 12, "y": 4 },
  "id": 13,
  "options": {
    "legend": {
      "calcs": ["lastNotNull"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "marcusolsson-json-datasource", "uid": "P6CAC8AF542CA101E" },
      "fields": [{ "jsonPath": "$.services.database.status", "name": "Database" }],
      "method": "GET",
      "refId": "A",
      "urlPath": "/api/system/health"
    }
  ],
  "title": "Database",
  "type": "timeseries"
}
```

**Step 5: Add Redis Status panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "stepAfter",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [
        {
          "options": { "1": { "color": "#73BF69", "index": 0, "text": "Connected" } },
          "type": "value"
        },
        {
          "options": { "0": { "color": "#F2495C", "index": 1, "text": "Disconnected" } },
          "type": "value"
        }
      ],
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#F2495C", "value": null },
          { "color": "#73BF69", "value": 1 }
        ]
      }
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 3, "x": 15, "y": 4 },
  "id": 14,
  "options": {
    "legend": {
      "calcs": ["lastNotNull"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "redis_up",
      "legendFormat": "Redis",
      "refId": "A"
    }
  ],
  "title": "Redis",
  "type": "timeseries"
}
```

**Step 6: Add Active Cameras panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
      "unit": "short"
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 3, "x": 18, "y": 4 },
  "id": 15,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "min", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_total_cameras",
      "legendFormat": "Cameras",
      "refId": "A"
    }
  ],
  "title": "Active Cameras",
  "type": "timeseries"
}
```

**Step 7: Add Events Today panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#6ED0E0", "value": null }] },
      "unit": "short"
    },
    "overrides": []
  },
  "gridPos": { "h": 6, "w": 3, "x": 21, "y": 4 },
  "id": 16,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "min", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_total_events",
      "legendFormat": "Events",
      "refId": "A"
    }
  ],
  "title": "Events Today",
  "type": "timeseries"
}
```

**Step 8: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add system health row with 8 panels"
```

---

## Task 4: Add Row 2 - Pipeline Overview (6 panels)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add Pipeline Overview row header at y=10**

```json
{
  "collapsed": false,
  "gridPos": { "h": 1, "w": 24, "x": 0, "y": 10 },
  "id": 20,
  "panels": [],
  "title": "Pipeline Overview",
  "type": "row"
}
```

**Step 2: Add End-to-End Latency panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisLabel": "Latency",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "line+area" }
      },
      "mappings": [],
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 5 },
          { "color": "#F2495C", "value": 15 }
        ]
      },
      "unit": "s"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 8, "x": 0, "y": 11 },
  "id": 21,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.50, rate(hsi_stage_duration_seconds_bucket[5m]))",
      "legendFormat": "P50",
      "refId": "A"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.95, rate(hsi_stage_duration_seconds_bucket[5m]))",
      "legendFormat": "P95",
      "refId": "B"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.99, rate(hsi_stage_duration_seconds_bucket[5m]))",
      "legendFormat": "P99",
      "refId": "C"
    }
  ],
  "title": "End-to-End Latency",
  "type": "timeseries"
}
```

**Step 3: Add Throughput panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisLabel": "per second",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
      "unit": "short"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 8, "x": 8, "y": 11 },
  "id": 22,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "rate(hsi_detections_processed_total[5m])",
      "legendFormat": "Detections/sec",
      "refId": "A"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "rate(hsi_events_created_total[5m])",
      "legendFormat": "Events/sec",
      "refId": "B"
    }
  ],
  "title": "Throughput",
  "type": "timeseries"
}
```

**Step 4: Add Detection Queue Depth panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisLabel": "Items",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 30 },
          { "color": "#F2495C", "value": 70 }
        ]
      },
      "unit": "short"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 4, "x": 16, "y": 11 },
  "id": 23,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_detection_queue_depth",
      "legendFormat": "Detection Queue",
      "refId": "A"
    }
  ],
  "title": "Detection Queue",
  "type": "timeseries"
}
```

**Step 5: Add Analysis Queue Depth panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisLabel": "Items",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 30 },
          { "color": "#F2495C", "value": 70 }
        ]
      },
      "unit": "short"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 4, "x": 20, "y": 11 },
  "id": 24,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_analysis_queue_depth",
      "legendFormat": "Analysis Queue",
      "refId": "A"
    }
  ],
  "title": "Analysis Queue",
  "type": "timeseries"
}
```

**Step 6: Add Pipeline Stage Breakdown panel (full width, below)**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisLabel": "Duration (s)",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "normal" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
      "unit": "s"
    },
    "overrides": [
      {
        "matcher": { "id": "byName", "options": "watch" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#3274d9", "mode": "fixed" } }]
      },
      {
        "matcher": { "id": "byName", "options": "detect" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#FF9830", "mode": "fixed" } }]
      },
      {
        "matcher": { "id": "byName", "options": "batch" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#B877D9", "mode": "fixed" } }]
      },
      {
        "matcher": { "id": "byName", "options": "analyze" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#73BF69", "mode": "fixed" } }]
      }
    ]
  },
  "gridPos": { "h": 6, "w": 24, "x": 0, "y": 19 },
  "id": 25,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "right",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.95, sum(rate(hsi_stage_duration_seconds_bucket{stage=\"detect\"}[5m])) by (le))",
      "legendFormat": "detect",
      "refId": "A"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.95, sum(rate(hsi_stage_duration_seconds_bucket{stage=\"batch\"}[5m])) by (le))",
      "legendFormat": "batch",
      "refId": "B"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "histogram_quantile(0.95, sum(rate(hsi_stage_duration_seconds_bucket{stage=\"analyze\"}[5m])) by (le))",
      "legendFormat": "analyze",
      "refId": "C"
    }
  ],
  "title": "Pipeline Stage Breakdown (P95)",
  "type": "timeseries"
}
```

**Step 7: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add pipeline overview row with 6 panels"
```

---

## Task 5: Add Row 3 - GPU Resources (6 panels)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add GPU Resources row header at y=25**

```json
{
  "collapsed": false,
  "gridPos": { "h": 1, "w": 24, "x": 0, "y": 25 },
  "id": 30,
  "panels": [],
  "title": "GPU Resources",
  "type": "row"
}
```

**Step 2: Add GPU Utilization panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [],
      "max": 100,
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 70 },
          { "color": "#F2495C", "value": 90 }
        ]
      },
      "unit": "percent"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 6, "x": 0, "y": 26 },
  "id": 31,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_gpu_utilization",
      "legendFormat": "GPU Utilization",
      "refId": "A"
    }
  ],
  "title": "GPU Utilization",
  "type": "timeseries"
}
```

**Step 3: Add VRAM Usage panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [],
      "max": 100,
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 75 },
          { "color": "#F2495C", "value": 90 }
        ]
      },
      "unit": "percent"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 6, "x": 6, "y": 26 },
  "id": 32,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "100 * hsi_gpu_memory_used_mb / hsi_gpu_memory_total_mb",
      "legendFormat": "VRAM Used %",
      "refId": "A"
    }
  ],
  "title": "VRAM Usage",
  "type": "timeseries"
}
```

**Step 4: Add GPU Temperature panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "continuous-YlRd" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "scheme",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "line" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#73BF69", "value": null },
          { "color": "#FF9830", "value": 75 },
          { "color": "#F2495C", "value": 85 }
        ]
      },
      "unit": "celsius"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 4, "x": 12, "y": 26 },
  "id": 33,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_gpu_temperature",
      "legendFormat": "Temperature",
      "refId": "A"
    }
  ],
  "title": "GPU Temperature",
  "type": "timeseries"
}
```

**Step 5: Add Inference FPS panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "thresholds" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 30,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "area" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "#F2495C", "value": null },
          { "color": "#FF9830", "value": 15 },
          { "color": "#73BF69", "value": 25 }
        ]
      },
      "unit": "fps"
    },
    "overrides": []
  },
  "gridPos": { "h": 8, "w": 4, "x": 16, "y": 26 },
  "id": 34,
  "options": {
    "legend": {
      "calcs": ["lastNotNull", "mean", "max"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_inference_fps",
      "legendFormat": "Inference FPS",
      "refId": "A"
    }
  ],
  "title": "Inference FPS",
  "type": "timeseries"
}
```

**Step 6: Add GPU Memory Absolute panel**

```json
{
  "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
  "fieldConfig": {
    "defaults": {
      "color": { "mode": "palette-classic" },
      "custom": {
        "axisCenteredZero": false,
        "axisColorMode": "text",
        "axisPlacement": "auto",
        "drawStyle": "line",
        "fillOpacity": 20,
        "gradientMode": "opacity",
        "hideFrom": { "legend": false, "tooltip": false, "viz": false },
        "lineInterpolation": "smooth",
        "lineWidth": 2,
        "pointSize": 5,
        "scaleDistribution": { "type": "linear" },
        "showPoints": "never",
        "spanNulls": false,
        "stacking": { "group": "A", "mode": "none" },
        "thresholdsStyle": { "mode": "off" }
      },
      "mappings": [],
      "min": 0,
      "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
      "unit": "decmbytes"
    },
    "overrides": [
      {
        "matcher": { "id": "byName", "options": "Used" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#FF9830", "mode": "fixed" } }]
      },
      {
        "matcher": { "id": "byName", "options": "Total" },
        "properties": [{ "id": "color", "value": { "fixedColor": "#73BF69", "mode": "fixed" } }]
      }
    ]
  },
  "gridPos": { "h": 8, "w": 4, "x": 20, "y": 26 },
  "id": 35,
  "options": {
    "legend": {
      "calcs": ["lastNotNull"],
      "displayMode": "table",
      "placement": "bottom",
      "showLegend": true
    },
    "tooltip": { "mode": "multi", "sort": "desc" }
  },
  "targets": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_gpu_memory_used_mb",
      "legendFormat": "Used",
      "refId": "A"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "expr": "hsi_gpu_memory_total_mb",
      "legendFormat": "Total",
      "refId": "B"
    }
  ],
  "title": "GPU Memory (MB)",
  "type": "timeseries"
}
```

**Step 7: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add GPU resources row with 6 panels"
```

---

## Task 6: Add Row 4 - AI Models (8 panels, collapsed)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add AI Models collapsible row at y=34**

This row is collapsed by default and contains 8 panels for AI service metrics.

```json
{
  "collapsed": true,
  "gridPos": { "h": 1, "w": 24, "x": 0, "y": 34 },
  "id": 40,
  "panels": [
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#FF9830", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "line" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "#73BF69", "value": null },
              { "color": "#FF9830", "value": 0.5 }
            ]
          },
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 0, "y": 35 },
      "id": 41,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.50, rate(hsi_ai_request_duration_seconds_bucket{service=\"rtdetr\"}[5m]))",
          "legendFormat": "P50",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"rtdetr\"}[5m]))",
          "legendFormat": "P95",
          "refId": "B"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.99, rate(hsi_ai_request_duration_seconds_bucket{service=\"rtdetr\"}[5m]))",
          "legendFormat": "P99",
          "refId": "C"
        }
      ],
      "title": "RT-DETR Latency",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#FF9830", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "min": 0,
          "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 6, "y": 35 },
      "id": 42,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_ai_request_duration_seconds_count{service=\"rtdetr\"}[1m])",
          "legendFormat": "RT-DETR req/s",
          "refId": "A"
        }
      ],
      "title": "RT-DETR Request Rate",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#B877D9", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "line" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "#73BF69", "value": null },
              { "color": "#FF9830", "value": 5 }
            ]
          },
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 12, "y": 35 },
      "id": 43,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.50, rate(hsi_ai_request_duration_seconds_bucket{service=\"nemotron\"}[5m]))",
          "legendFormat": "P50",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"nemotron\"}[5m]))",
          "legendFormat": "P95",
          "refId": "B"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.99, rate(hsi_ai_request_duration_seconds_bucket{service=\"nemotron\"}[5m]))",
          "legendFormat": "P99",
          "refId": "C"
        }
      ],
      "title": "Nemotron Latency",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#B877D9", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "min": 0,
          "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 18, "y": 35 },
      "id": 44,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_ai_request_duration_seconds_count{service=\"nemotron\"}[1m])",
          "legendFormat": "Nemotron req/s",
          "refId": "A"
        }
      ],
      "title": "Nemotron Request Rate",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#3274d9", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "line" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "#73BF69", "value": null },
              { "color": "#FF9830", "value": 1 }
            ]
          },
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 0, "y": 43 },
      "id": 45,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.50, rate(hsi_ai_request_duration_seconds_bucket{service=\"florence\"}[5m]))",
          "legendFormat": "P50",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"florence\"}[5m]))",
          "legendFormat": "P95",
          "refId": "B"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.99, rate(hsi_ai_request_duration_seconds_bucket{service=\"florence\"}[5m]))",
          "legendFormat": "P99",
          "refId": "C"
        }
      ],
      "title": "Florence Latency",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "normal" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "min": 0,
          "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 6, "y": 43 },
      "id": 46,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_florence_task_total{task=\"caption\"}[5m])",
          "legendFormat": "caption",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_florence_task_total{task=\"ocr\"}[5m])",
          "legendFormat": "ocr",
          "refId": "B"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_florence_task_total{task=\"detect\"}[5m])",
          "legendFormat": "detect",
          "refId": "C"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "rate(hsi_florence_task_total{task=\"dense_caption\"}[5m])",
          "legendFormat": "dense_caption",
          "refId": "D"
        }
      ],
      "title": "Florence Tasks",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "fixedColor": "#73BF69", "mode": "fixed" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 20,
            "gradientMode": "opacity",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "line" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "#73BF69", "value": null },
              { "color": "#FF9830", "value": 0.2 }
            ]
          },
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": { "h": 8, "w": 6, "x": 12, "y": 43 },
      "id": 47,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.50, rate(hsi_ai_request_duration_seconds_bucket{service=\"clip\"}[5m]))",
          "legendFormat": "P50",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"clip\"}[5m]))",
          "legendFormat": "P95",
          "refId": "B"
        }
      ],
      "title": "CLIP Latency",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisPlacement": "auto",
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "smooth",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "none" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "thresholds": { "mode": "absolute", "steps": [{ "color": "#73BF69", "value": null }] },
          "unit": "s"
        },
        "overrides": [
          {
            "matcher": { "id": "byName", "options": "RT-DETR" },
            "properties": [{ "id": "color", "value": { "fixedColor": "#FF9830", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "Nemotron" },
            "properties": [{ "id": "color", "value": { "fixedColor": "#B877D9", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "Florence" },
            "properties": [{ "id": "color", "value": { "fixedColor": "#3274d9", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "CLIP" },
            "properties": [{ "id": "color", "value": { "fixedColor": "#73BF69", "mode": "fixed" } }]
          }
        ]
      },
      "gridPos": { "h": 8, "w": 6, "x": 18, "y": 43 },
      "id": 48,
      "options": {
        "legend": {
          "calcs": ["lastNotNull", "mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "targets": [
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"rtdetr\"}[5m]))",
          "legendFormat": "RT-DETR",
          "refId": "A"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"nemotron\"}[5m]))",
          "legendFormat": "Nemotron",
          "refId": "B"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"florence\"}[5m]))",
          "legendFormat": "Florence",
          "refId": "C"
        },
        {
          "datasource": { "type": "prometheus", "uid": "PBFA97CFB590B2093" },
          "expr": "histogram_quantile(0.95, rate(hsi_ai_request_duration_seconds_bucket{service=\"clip\"}[5m]))",
          "legendFormat": "CLIP",
          "refId": "D"
        }
      ],
      "title": "All Models Comparison (P95)",
      "type": "timeseries"
    }
  ],
  "title": "AI Models",
  "type": "row"
}
```

**Step 2: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add AI models row with 8 panels (collapsed)"
```

---

## Task 7: Add Row 5 - Detection Analytics (8 panels, collapsed)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add Detection Analytics collapsible row at y=35**

Add as a collapsed row with 8 panels for detection metrics (confidence, classes, cameras).

The full JSON for this row should include panels for:

1. Detection Confidence Distribution (heatmap)
2. Avg Confidence (timeseries)
3. Detections by Class (stacked timeseries)
4. Top Classes Bar Chart
5. Detections by Camera (stacked timeseries)
6. Camera Activity Ranking (bar chart)
7. Detection Rate (timeseries)
8. Detections Filtered (timeseries)

**Step 2: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add detection analytics row with 8 panels (collapsed)"
```

---

## Task 8: Add Row 6 - Risk Analysis (8 panels, collapsed)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add Risk Analysis collapsible row at y=36**

Add as a collapsed row with panels for:

1. Risk Score Distribution (heatmap)
2. Avg Risk Score (timeseries)
3. Current Risk Level (timeseries with thresholds)
4. Events by Risk Level (stacked timeseries)
5. Risk Level Breakdown (pie/bar)
6. High Risk Event Rate (timeseries)
7. Prompt Template Usage (stacked timeseries)
8. Events Reviewed (timeseries)

**Step 2: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add risk analysis row with 8 panels (collapsed)"
```

---

## Task 9: Add Row 7 - Queue Health (8 panels, collapsed)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add Queue Health collapsible row at y=37**

Add as a collapsed row with panels for:

1. Queue Overflow Events (timeseries, threshold at >0)
2. Items Moved to DLQ (timeseries)
3. Items Dropped (timeseries, red threshold)
4. Items Rejected (timeseries)
5. DLQ Total Size (timeseries)
6. Queue Health Summary (multi-line)
7. Pipeline Errors by Type (stacked timeseries)
8. Error Rate (timeseries)

**Step 2: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add queue health row with 8 panels (collapsed)"
```

---

## Task 10: Add Row 8 - Model Zoo (10 panels, collapsed)

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`

**Step 1: Add Model Zoo collapsible row at y=38**

Add as a collapsed row with panels for:

1. Enrichment Model Calls (stacked by model)
2. Model Call Volume (bar chart)
3. Vehicle Detection Latency
4. Pet Detection Latency
5. Clothing Detection Latency
6. Violence Detection Latency
7. All Models Latency Comparison
8. BRISQUE Latency
9. Model Error Rate
10. Model Throughput

**Step 2: Validate and commit**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null
git add monitoring/grafana/dashboards/operations.json
git commit -m "feat(grafana): add model zoo row with 10 panels (collapsed)"
```

---

## Task 11: Final Validation and Documentation

**Files:**

- Modify: `monitoring/grafana/dashboards/operations.json`
- Update: `monitoring/grafana/dashboards/AGENTS.md`

**Step 1: Validate complete dashboard JSON**

```bash
python -m json.tool monitoring/grafana/dashboards/operations.json > /dev/null && echo "Dashboard JSON is valid"
```

**Step 2: Test dashboard loads in Grafana**

```bash
# Start monitoring stack if not running
podman-compose --profile monitoring -f docker-compose.prod.yml up -d

# Wait for Grafana to be ready
sleep 10

# Test dashboard API endpoint
curl -s http://localhost:3002/api/dashboards/uid/hsi-operations | python -m json.tool | head -5
```

Expected: Dashboard metadata returned without errors

**Step 3: Update AGENTS.md documentation**

Add to `monitoring/grafana/dashboards/AGENTS.md`:

```markdown
### operations.json

Comprehensive operations dashboard with all available metrics.

- **UID:** `hsi-operations`
- **Default:** 15-minute window, 5-second refresh
- **Rows:** 8 collapsible sections (3 expanded, 5 collapsed by default)

| Row | Name                | Panels | State     |
| --- | ------------------- | ------ | --------- |
| 1   | System Health       | 8      | Expanded  |
| 2   | Pipeline Overview   | 6      | Expanded  |
| 3   | GPU Resources       | 6      | Expanded  |
| 4   | AI Models           | 8      | Collapsed |
| 5   | Detection Analytics | 8      | Collapsed |
| 6   | Risk Analysis       | 8      | Collapsed |
| 7   | Queue Health        | 8      | Collapsed |
| 8   | Model Zoo           | 10     | Collapsed |

**Total: 62 panels**
```

**Step 4: Final commit**

```bash
git add monitoring/grafana/dashboards/AGENTS.md
git commit -m "docs: update AGENTS.md with operations dashboard documentation"
```

---

## Task 12: Create Pull Request

**Step 1: Push branch and create PR**

```bash
git push -u origin fix-contract-tests-ci
```

**Step 2: Create PR with summary**

```bash
gh pr create --title "feat(grafana): add comprehensive operations dashboard" --body "$(cat <<'EOF'
## Summary
- Adds new `hsi-operations` Grafana dashboard exposing all available Prometheus metrics
- 62 panels organized in 8 collapsible rows
- Real-time focus: 15-minute default window, 5-second refresh
- Supplements existing `pipeline.json` dashboard with comprehensive visibility

## Rows
1. System Health (expanded) - 8 panels
2. Pipeline Overview (expanded) - 6 panels
3. GPU Resources (expanded) - 6 panels
4. AI Models (collapsed) - 8 panels
5. Detection Analytics (collapsed) - 8 panels
6. Risk Analysis (collapsed) - 8 panels
7. Queue Health (collapsed) - 8 panels
8. Model Zoo (collapsed) - 10 panels

## Test plan
- [ ] Dashboard JSON validates: `python -m json.tool monitoring/grafana/dashboards/operations.json`
- [ ] Start monitoring stack: `podman-compose --profile monitoring -f docker-compose.prod.yml up -d`
- [ ] Access Grafana at http://localhost:3002
- [ ] Navigate to "Home Security Intelligence - Operations" dashboard
- [ ] Verify all 8 rows load without errors
- [ ] Verify time range selector works (15m/1h/6h/24h/7d)
- [ ] Expand collapsed rows and verify panels render

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Summary

| Task | Description             | Panels Added |
| ---- | ----------------------- | ------------ |
| 1    | Dashboard scaffold      | 0            |
| 2    | Quick time selector     | 1            |
| 3    | System Health row       | 8            |
| 4    | Pipeline Overview row   | 6            |
| 5    | GPU Resources row       | 6            |
| 6    | AI Models row           | 8            |
| 7    | Detection Analytics row | 8            |
| 8    | Risk Analysis row       | 8            |
| 9    | Queue Health row        | 8            |
| 10   | Model Zoo row           | 10           |
| 11   | Final validation        | 0            |
| 12   | Create PR               | 0            |

**Total: 62 panels + 1 text panel = 63 panels**
