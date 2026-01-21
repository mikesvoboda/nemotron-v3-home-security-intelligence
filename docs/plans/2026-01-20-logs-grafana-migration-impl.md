# Logs Page Grafana/Loki Migration - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace custom LogsDashboard with embedded Grafana dashboard powered by Loki

**Architecture:** New LogsPage component embeds a Grafana dashboard via iframe. Dashboard uses Loki datasource with variables for filtering. All custom React log components and backend /api/logs endpoints are deleted.

**Tech Stack:** React, TypeScript, Grafana, Loki, LogQL

---

## Task 1: Create Grafana Logs Dashboard

**Files:**

- Create: `monitoring/grafana/dashboards/logs.json`

**Step 1: Create the dashboard JSON file**

Create `monitoring/grafana/dashboards/logs.json` with the following content:

```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": { "type": "loki", "uid": "loki" },
        "enable": true,
        "expr": "{level=\"ERROR\"} |= \"\"",
        "hide": false,
        "iconColor": "red",
        "name": "Errors",
        "target": { "limit": 100, "matchAny": false, "tags": [], "type": "tags" },
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [
    {
      "asDropdown": false,
      "icon": "external link",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": true,
      "title": "Open in Explore",
      "tooltip": "Open Loki Explore for ad-hoc queries",
      "type": "link",
      "url": "/grafana/explore?orgId=1&left=%7B%22datasource%22:%22loki%22%7D"
    }
  ],
  "liveNow": false,
  "panels": [
    {
      "collapsed": false,
      "gridPos": { "h": 1, "w": 24, "x": 0, "y": 0 },
      "id": 100,
      "panels": [],
      "title": "Metrics from Logs",
      "type": "row"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Error rate calculated from log entries",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 5 },
              { "color": "red", "value": 10 }
            ]
          },
          "unit": "errors/min"
        },
        "overrides": []
      },
      "gridPos": { "h": 4, "w": 8, "x": 0, "y": 1 },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "sum(count_over_time({container=~\"$service\"} |~ \"$search\" | level=\"ERROR\" [$__interval])) * 60 / $__interval_ms * 1000",
          "refId": "A"
        }
      ],
      "title": "Error Rate",
      "type": "stat"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Log throughput in lines per second",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          },
          "unit": "lines/sec"
        },
        "overrides": []
      },
      "gridPos": { "h": 4, "w": 8, "x": 8, "y": 1 },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "sum(count_over_time({container=~\"$service\"} |~ \"$search\" [$__interval])) / $__interval_ms * 1000",
          "refId": "A"
        }
      ],
      "title": "Log Throughput",
      "type": "stat"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Total log entries in selected time range",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "blue", "value": null }]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": { "h": 4, "w": 8, "x": 16, "y": 1 },
      "id": 3,
      "options": {
        "colorMode": "value",
        "graphMode": "none",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": { "calcs": ["sum"], "fields": "", "values": false },
        "textMode": "auto"
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "count_over_time({container=~\"$service\"} |~ \"$search\" [$__range])",
          "refId": "A"
        }
      ],
      "title": "Total Logs",
      "type": "stat"
    },
    {
      "collapsed": false,
      "gridPos": { "h": 1, "w": 24, "x": 0, "y": 5 },
      "id": 101,
      "panels": [],
      "title": "Volume & Distribution",
      "type": "row"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Log volume over time stacked by level",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": { "type": "linear" },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": { "group": "A", "mode": "normal" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          }
        },
        "overrides": [
          {
            "matcher": { "id": "byName", "options": "ERROR" },
            "properties": [{ "id": "color", "value": { "fixedColor": "red", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "WARNING" },
            "properties": [{ "id": "color", "value": { "fixedColor": "yellow", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "INFO" },
            "properties": [{ "id": "color", "value": { "fixedColor": "green", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "DEBUG" },
            "properties": [{ "id": "color", "value": { "fixedColor": "blue", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "CRITICAL" },
            "properties": [{ "id": "color", "value": { "fixedColor": "purple", "mode": "fixed" } }]
          }
        ]
      },
      "gridPos": { "h": 6, "w": 16, "x": 0, "y": 6 },
      "id": 4,
      "options": {
        "legend": { "calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true },
        "tooltip": { "mode": "multi", "sort": "desc" }
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "sum by (level) (count_over_time({container=~\"$service\"} |~ \"$search\" | level=~\"$level\" [$__interval]))",
          "legendFormat": "{{level}}",
          "refId": "A"
        }
      ],
      "title": "Log Volume by Level",
      "type": "timeseries"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Distribution of log levels",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "green", "value": null }]
          }
        },
        "overrides": [
          {
            "matcher": { "id": "byName", "options": "ERROR" },
            "properties": [{ "id": "color", "value": { "fixedColor": "red", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "WARNING" },
            "properties": [{ "id": "color", "value": { "fixedColor": "yellow", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "INFO" },
            "properties": [{ "id": "color", "value": { "fixedColor": "green", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "DEBUG" },
            "properties": [{ "id": "color", "value": { "fixedColor": "blue", "mode": "fixed" } }]
          },
          {
            "matcher": { "id": "byName", "options": "CRITICAL" },
            "properties": [{ "id": "color", "value": { "fixedColor": "purple", "mode": "fixed" } }]
          }
        ]
      },
      "gridPos": { "h": 6, "w": 8, "x": 16, "y": 6 },
      "id": 5,
      "options": {
        "displayLabels": ["percent"],
        "legend": {
          "displayMode": "table",
          "placement": "right",
          "showLegend": true,
          "values": ["value"]
        },
        "pieType": "pie",
        "reduceOptions": { "calcs": ["sum"], "fields": "", "values": false },
        "tooltip": { "mode": "single", "sort": "none" }
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "sum by (level) (count_over_time({container=~\"$service\"} |~ \"$search\" [$__range]))",
          "legendFormat": "{{level}}",
          "refId": "A"
        }
      ],
      "title": "Level Distribution",
      "type": "piechart"
    },
    {
      "collapsed": false,
      "gridPos": { "h": 1, "w": 24, "x": 0, "y": 12 },
      "id": 102,
      "panels": [],
      "title": "Pattern Analysis",
      "type": "row"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Top error messages grouped by pattern",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "thresholds" },
          "custom": {
            "align": "auto",
            "cellOptions": { "type": "auto" },
            "inspect": false
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "color": "green", "value": null },
              { "color": "yellow", "value": 10 },
              { "color": "red", "value": 50 }
            ]
          }
        },
        "overrides": [
          {
            "matcher": { "id": "byName", "options": "Count" },
            "properties": [{ "id": "custom.cellOptions", "value": { "type": "color-background" } }]
          }
        ]
      },
      "gridPos": { "h": 6, "w": 12, "x": 0, "y": 13 },
      "id": 6,
      "options": {
        "cellHeight": "sm",
        "footer": { "countRows": false, "fields": "", "reducer": ["sum"], "show": false },
        "showHeader": true,
        "sortBy": [{ "desc": true, "displayName": "Count" }]
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "topk(10, sum by (message) (count_over_time({container=~\"$service\"} | level=\"ERROR\" | pattern `<_> <message>` [$__range])))",
          "legendFormat": "",
          "refId": "A"
        }
      ],
      "title": "Top Error Patterns",
      "transformations": [
        {
          "id": "sortBy",
          "options": { "fields": {}, "sort": [{ "desc": true, "field": "Value" }] }
        }
      ],
      "type": "table"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Errors by service/container",
      "fieldConfig": {
        "defaults": {
          "color": { "mode": "palette-classic" },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": { "legend": false, "tooltip": false, "viz": false },
            "lineWidth": 1,
            "scaleDistribution": { "type": "linear" },
            "thresholdsStyle": { "mode": "off" }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [{ "color": "red", "value": null }]
          }
        },
        "overrides": []
      },
      "gridPos": { "h": 6, "w": 12, "x": 12, "y": 13 },
      "id": 7,
      "options": {
        "barRadius": 0,
        "barWidth": 0.8,
        "groupWidth": 0.7,
        "legend": { "calcs": [], "displayMode": "list", "placement": "bottom", "showLegend": true },
        "orientation": "horizontal",
        "showValue": "always",
        "stacking": "none",
        "tooltip": { "mode": "single", "sort": "none" },
        "xTickLabelRotation": 0,
        "xTickLabelSpacing": 0
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "topk(10, sum by (container) (count_over_time({container=~\".+\"} | level=\"ERROR\" [$__range])))",
          "legendFormat": "{{container}}",
          "refId": "A"
        }
      ],
      "title": "Errors by Service",
      "type": "barchart"
    },
    {
      "collapsed": false,
      "gridPos": { "h": 1, "w": 24, "x": 0, "y": 19 },
      "id": 103,
      "panels": [],
      "title": "Logs",
      "type": "row"
    },
    {
      "datasource": { "type": "loki", "uid": "loki" },
      "description": "Log entries with trace correlation and context",
      "gridPos": { "h": 15, "w": 24, "x": 0, "y": 20 },
      "id": 8,
      "options": {
        "dedupStrategy": "signature",
        "enableLogDetails": true,
        "prettifyLogMessage": false,
        "showCommonLabels": false,
        "showLabels": true,
        "showTime": true,
        "sortOrder": "Descending",
        "wrapLogMessage": true
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": { "type": "loki", "uid": "loki" },
          "expr": "{container=~\"$service\"} |~ \"$search\" | level=~\"$level\"",
          "refId": "A"
        }
      ],
      "title": "Logs",
      "type": "logs"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["logs", "loki", "hsi"],
  "templating": {
    "list": [
      {
        "allValue": ".+",
        "current": { "selected": true, "text": "All", "value": "$__all" },
        "datasource": { "type": "loki", "uid": "loki" },
        "definition": "label_values(container)",
        "hide": 0,
        "includeAll": true,
        "label": "Service",
        "multi": true,
        "name": "service",
        "options": [],
        "query": "label_values(container)",
        "refresh": 2,
        "regex": "",
        "skipUrlSync": false,
        "sort": 1,
        "type": "query"
      },
      {
        "allValue": ".+",
        "current": { "selected": true, "text": "All", "value": "$__all" },
        "hide": 0,
        "includeAll": true,
        "label": "Level",
        "multi": true,
        "name": "level",
        "options": [
          { "selected": true, "text": "All", "value": "$__all" },
          { "selected": false, "text": "DEBUG", "value": "DEBUG" },
          { "selected": false, "text": "INFO", "value": "INFO" },
          { "selected": false, "text": "WARNING", "value": "WARNING" },
          { "selected": false, "text": "ERROR", "value": "ERROR" },
          { "selected": false, "text": "CRITICAL", "value": "CRITICAL" }
        ],
        "query": "DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "queryValue": "",
        "skipUrlSync": false,
        "type": "custom"
      },
      {
        "current": { "selected": false, "text": "", "value": "" },
        "hide": 0,
        "label": "Search",
        "name": "search",
        "options": [{ "selected": true, "text": "", "value": "" }],
        "query": "",
        "skipUrlSync": false,
        "type": "textbox"
      }
    ]
  },
  "time": { "from": "now-1h", "to": "now" },
  "timepicker": {},
  "timezone": "",
  "title": "HSI System Logs",
  "uid": "hsi-logs",
  "version": 1,
  "weekStart": ""
}
```

**Step 2: Verify the dashboard file is valid JSON**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876 && python -c "import json; json.load(open('monitoring/grafana/dashboards/logs.json'))"`
Expected: No output (success)

**Step 3: Commit**

```bash
git add monitoring/grafana/dashboards/logs.json
git commit -m "feat: add Grafana logs dashboard with Loki integration

- Service, level, and search filtering via variables
- Error rate and throughput metrics from logs
- Log volume by level time series
- Level distribution pie chart
- Top error patterns table
- Errors by service bar chart
- Logs panel with dedup and trace correlation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Create LogsPage Frontend Component

**Files:**

- Create: `frontend/src/components/logs/LogsPage.tsx`
- Create: `frontend/src/components/logs/LogsPage.test.tsx`

**Step 1: Write the test file**

Create `frontend/src/components/logs/LogsPage.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import LogsPage from './LogsPage';

// Mock the API service
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn().mockResolvedValue({ grafana_url: 'http://localhost:3002' }),
}));

// Mock the grafanaUrl utility
vi.mock('../../utils/grafanaUrl', () => ({
  resolveGrafanaUrl: vi.fn((url: string) => url),
}));

describe('LogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByText('System Logs')).toBeInTheDocument();
    });
  });

  it('renders the Grafana iframe', async () => {
    render(<LogsPage />);
    await waitFor(() => {
      const iframe = screen.getByTestId('logs-iframe');
      expect(iframe).toBeInTheDocument();
      expect(iframe).toHaveAttribute('src', expect.stringContaining('hsi-logs'));
    });
  });

  it('renders external links', async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('grafana-external-link')).toBeInTheDocument();
      expect(screen.getByTestId('explore-external-link')).toBeInTheDocument();
    });
  });

  it('renders refresh button', async () => {
    render(<LogsPage />);
    await waitFor(() => {
      expect(screen.getByTestId('logs-refresh-button')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    render(<LogsPage />);
    expect(screen.getByTestId('logs-loading')).toBeInTheDocument();
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();
    render(<LogsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('logs-refresh-button')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTestId('logs-refresh-button');
    await user.click(refreshButton);

    // Button should show spinning state briefly
    expect(refreshButton).toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm test -- --run LogsPage.test.tsx`
Expected: FAIL - LogsPage module not found

**Step 3: Write the LogsPage component**

Create `frontend/src/components/logs/LogsPage.tsx`:

```tsx
/**
 * LogsPage - System logs dashboard via Grafana/Loki
 *
 * Embeds the HSI System Logs dashboard for:
 * - Centralized log aggregation via Loki
 * - LogQL filtering by service, level, and search text
 * - Trace correlation (click trace_id to open Jaeger)
 * - Live tail and log context features
 */

import { FileText, RefreshCw, ExternalLink, AlertCircle } from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

export default function LogsPage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch Grafana URL from config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          const resolvedUrl = resolveGrafanaUrl(configWithGrafana.grafana_url);
          setGrafanaUrl(resolvedUrl);
        }
        setIsLoading(false);
      } catch (err) {
        console.error('Failed to fetch config:', err);
        setError('Failed to load configuration. Using default Grafana URL.');
        setIsLoading(false);
      }
    };
    void loadConfig();
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    if (iframeRef.current) {
      const currentSrc = iframeRef.current.src;
      iframeRef.current.src = '';
      setTimeout(() => {
        if (iframeRef.current) {
          iframeRef.current.src = currentSrc;
        }
        setIsRefreshing(false);
      }, 100);
    } else {
      setIsRefreshing(false);
    }
  }, []);

  // Construct Grafana Dashboard URL (HSI System Logs dashboard)
  const getDashboardUrl = () => {
    return `${grafanaUrl}/d/hsi-logs/hsi-system-logs?orgId=1&kiosk=1&theme=dark&refresh=30s`;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="logs-loading">
        <div className="mx-auto max-w-[1920px]">
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>
          <div className="h-[calc(100vh-200px)] animate-pulse rounded-lg bg-gray-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212]" data-testid="logs-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <FileText className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">System Logs</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Open in Grafana */}
          <a
            href={`${grafanaUrl}/d/hsi-logs/hsi-system-logs?orgId=1&theme=dark`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="grafana-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Grafana
          </a>

          {/* Open in Explore */}
          <a
            href={`${grafanaUrl}/explore?orgId=1&left=%7B%22datasource%22:%22loki%22%7D`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="explore-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Explore
          </a>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="logs-refresh-button"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="mx-8 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4"
          data-testid="logs-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Grafana Dashboard iframe */}
      <iframe
        ref={iframeRef}
        src={getDashboardUrl()}
        className="h-[calc(100vh-73px)] w-full border-0"
        title="System Logs"
        data-testid="logs-iframe"
      />
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm test -- --run LogsPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/logs/LogsPage.tsx frontend/src/components/logs/LogsPage.test.tsx
git commit -m "feat: add LogsPage component with Grafana iframe

- Embeds hsi-logs Grafana dashboard in kiosk mode
- Header with Open in Grafana/Explore external links
- Refresh button to reload iframe
- Loading and error states
- Matches TracingPage pattern for consistency

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Update App.tsx Routing

**Files:**

- Modify: `frontend/src/App.tsx`

**Step 1: Update the lazy import**

In `frontend/src/App.tsx`, find:

```tsx
const LogsDashboard = lazy(() => import('./components/logs/LogsDashboard'));
```

Replace with:

```tsx
const LogsPage = lazy(() => import('./components/logs/LogsPage'));
```

**Step 2: Update the route element**

In `frontend/src/App.tsx`, find:

```tsx
<Route path="/logs" element={<LogsDashboard />} />
```

Replace with:

```tsx
<Route path="/logs" element={<LogsPage />} />
```

**Step 3: Run frontend tests**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm test -- --run`
Expected: PASS (or failures only in tests we're about to delete)

**Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "refactor: update /logs route to use LogsPage

Replace LogsDashboard with new LogsPage component that
embeds Grafana dashboard.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Update Alloy Config for Enhanced Parsing

**Files:**

- Modify: `monitoring/alloy/config.alloy`

**Step 1: Update the loki.process stage**

In `monitoring/alloy/config.alloy`, find the `loki.process "parse"` block and update it to add JSON field extraction and multiline support:

```hcl
// Parse and enrich logs
loki.process "parse" {
  // Add static job label (required by Loki)
  stage.static_labels {
    values = {
      job = "podman-containers",
    }
  }

  stage.docker {}

  // Extract log level
  stage.regex {
    expression = "(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)"
  }

  // Extract camera name from AI pipeline logs
  stage.regex {
    expression = "camera[=: ]+(?P<camera>[a-z_]+)"
  }

  // Extract trace context for log-trace correlation
  stage.regex {
    expression = "trace_id[=:]\\s*(?P<trace_id>[a-f0-9]{32})"
  }

  // Extract span_id for profile correlation
  stage.regex {
    expression = "span_id[=:]\\s*(?P<span_id>[a-f0-9]{16})"
  }

  // Extract batch_id from batch processing logs
  stage.regex {
    expression = "batch_id[=:]\\s*(?P<batch_id>[a-f0-9-]+)"
  }

  // Extract duration_ms from performance logs
  stage.regex {
    expression = "duration[=:]\\s*(?P<duration_ms>\\d+)\\s*ms"
  }

  stage.labels {
    values = {
      level = "",
      camera = "",
      trace_id = "",
      span_id = "",
      batch_id = "",
      duration_ms = "",
    }
  }

  forward_to = [loki.write.local.receiver]
}
```

**Step 2: Verify Alloy config syntax**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876 && cat monitoring/alloy/config.alloy | head -80`
Expected: Valid HCL syntax with updated stages

**Step 3: Commit**

```bash
git add monitoring/alloy/config.alloy
git commit -m "feat: enhance Alloy log parsing for trace correlation

- Extract trace_id for log-to-trace linking
- Extract span_id for profile correlation
- Extract batch_id from batch processing logs
- Extract duration_ms from performance logs
- All fields available as Loki labels for filtering

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Create Log-Based Alert Rules

**Files:**

- Create: `monitoring/grafana/provisioning/alerting/log-alerts.yml`

**Step 1: Create alerting directory if needed**

Run: `mkdir -p /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/monitoring/grafana/provisioning/alerting`

**Step 2: Create alert rules file**

Create `monitoring/grafana/provisioning/alerting/log-alerts.yml`:

```yaml
# Log-based alert rules using Loki
# These alerts fire based on LogQL queries

apiVersion: 1

groups:
  - orgId: 1
    name: log-alerts
    folder: HSI Alerts
    interval: 1m
    rules:
      - uid: high-error-rate
        title: High Error Rate
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: sum(count_over_time({level="ERROR"}[5m])) > 10
              refId: A
        noDataState: OK
        execErrState: Error
        for: 2m
        annotations:
          summary: High error rate detected in logs
          description: More than 10 errors in the last 5 minutes
        labels:
          severity: warning

      - uid: error-spike
        title: Error Spike
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 60
              to: 0
            datasourceUid: loki
            model:
              expr: sum(count_over_time({level="ERROR"}[1m])) > 20
              refId: A
        noDataState: OK
        execErrState: Error
        for: 1m
        annotations:
          summary: Sudden spike in error logs
          description: More than 20 errors in the last minute
        labels:
          severity: critical

      - uid: service-silent
        title: Service Silent
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: absent_over_time({container="backend"}[5m])
              refId: A
        noDataState: Alerting
        execErrState: Error
        for: 5m
        annotations:
          summary: Backend service not producing logs
          description: No logs from backend container for 5 minutes
        labels:
          severity: warning

      - uid: critical-error
        title: Critical Error Detected
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 60
              to: 0
            datasourceUid: loki
            model:
              expr: count_over_time({level="CRITICAL"}[1m]) > 0
              refId: A
        noDataState: OK
        execErrState: Error
        for: 0s
        annotations:
          summary: Critical error in logs
          description: A CRITICAL level log entry was detected
        labels:
          severity: critical
```

**Step 3: Commit**

```bash
git add monitoring/grafana/provisioning/alerting/log-alerts.yml
git commit -m "feat: add log-based alert rules via Loki

- High error rate (>10 errors in 5min) - warning
- Error spike (>20 errors in 1min) - critical
- Service silent (no backend logs for 5min) - warning
- Critical error detected - immediate critical

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Delete Old Frontend Log Components

**Files:**

- Delete: `frontend/src/components/logs/LogsDashboard.tsx`
- Delete: `frontend/src/components/logs/LogsDashboard.test.tsx`
- Delete: `frontend/src/components/logs/LogFilters.tsx`
- Delete: `frontend/src/components/logs/LogFilters.test.tsx`
- Delete: `frontend/src/components/logs/LogsTable.tsx`
- Delete: `frontend/src/components/logs/LogsTable.test.tsx`
- Delete: `frontend/src/components/logs/LogStatsCards.tsx`
- Delete: `frontend/src/components/logs/LogStatsCards.test.tsx`
- Delete: `frontend/src/components/logs/LogStatsSummary.tsx`
- Delete: `frontend/src/components/logs/LogDetailModal.tsx`
- Delete: `frontend/src/components/logs/LogDetailModal.test.tsx`
- Delete: `frontend/src/components/logs/logGrouping.ts`

**Step 1: Delete all old log component files**

```bash
cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876
rm -f frontend/src/components/logs/LogsDashboard.tsx
rm -f frontend/src/components/logs/LogsDashboard.test.tsx
rm -f frontend/src/components/logs/LogFilters.tsx
rm -f frontend/src/components/logs/LogFilters.test.tsx
rm -f frontend/src/components/logs/LogsTable.tsx
rm -f frontend/src/components/logs/LogsTable.test.tsx
rm -f frontend/src/components/logs/LogStatsCards.tsx
rm -f frontend/src/components/logs/LogStatsCards.test.tsx
rm -f frontend/src/components/logs/LogStatsSummary.tsx
rm -f frontend/src/components/logs/LogDetailModal.tsx
rm -f frontend/src/components/logs/LogDetailModal.test.tsx
rm -f frontend/src/components/logs/logGrouping.ts
```

**Step 2: Update AGENTS.md for logs directory**

Update `frontend/src/components/logs/AGENTS.md` to reflect the new structure:

```markdown
# Logs Components

## Purpose

This directory contains the LogsPage component that embeds a Grafana dashboard powered by Loki for centralized log viewing.

## Key Files

| File                | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `LogsPage.tsx`      | Main page component embedding Grafana logs dashboard |
| `LogsPage.test.tsx` | Unit tests for LogsPage                              |

## Architecture

The logs page embeds the `hsi-logs` Grafana dashboard in an iframe with kiosk mode. All log aggregation, filtering, and querying is handled by Loki via LogQL.

**Features provided by Grafana/Loki:**

- Service and level filtering via dashboard variables
- Full-text search
- Log volume visualization
- Error pattern detection
- Trace correlation (click trace_id to open Jaeger)
- Live tail mode
- Log context (surrounding lines)
- Download/export

## Related Files

- `monitoring/grafana/dashboards/logs.json` - Grafana dashboard definition
- `monitoring/alloy/config.alloy` - Log collection and parsing
- `monitoring/loki/loki-config.yml` - Loki storage configuration
```

**Step 3: Run frontend tests to verify no import errors**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm test -- --run`
Expected: PASS

**Step 4: Run frontend type check**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm run typecheck`
Expected: PASS

**Step 5: Commit**

```bash
git add -A frontend/src/components/logs/
git commit -m "refactor: remove old custom log components

Delete replaced components:
- LogsDashboard.tsx (265 lines)
- LogFilters.tsx (~150 lines)
- LogsTable.tsx (~200 lines)
- LogStatsCards.tsx (~100 lines)
- LogStatsSummary.tsx (~50 lines)
- LogDetailModal.tsx (~100 lines)
- logGrouping.ts
- All associated test files

Total: ~1,200 lines removed, replaced by Grafana/Loki

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Delete Backend Logs API

**Files:**

- Delete: `backend/api/routes/logs.py`
- Delete: `backend/api/schemas/logs.py`
- Modify: `backend/api/routes/__init__.py` (remove logs router import)
- Delete: `backend/tests/unit/routes/test_logs_routes.py`
- Delete: `backend/tests/unit/api/routes/test_logs_pagination.py`
- Delete: `backend/tests/integration/test_logs_api.py`

**Step 1: Find and check router registration**

Run: `grep -r "logs" /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/backend/api/routes/__init__.py`

**Step 2: Remove logs router from **init**.py**

Find in `backend/api/routes/__init__.py`:

```python
from backend.api.routes.logs import router as logs_router
```

and

```python
app.include_router(logs_router)
```

Remove both lines.

**Step 3: Delete backend logs files**

```bash
cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876
rm -f backend/api/routes/logs.py
rm -f backend/api/schemas/logs.py
rm -f backend/tests/unit/routes/test_logs_routes.py
rm -f backend/tests/unit/api/routes/test_logs_pagination.py
rm -f backend/tests/integration/test_logs_api.py
```

**Step 4: Check for any remaining imports of logs schemas**

Run: `grep -r "from backend.api.schemas.logs" /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/backend/`

If any found, remove those imports.

**Step 5: Run backend tests**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876 && uv run pytest backend/tests/unit/ -n auto --dist=worksteal -x`
Expected: PASS

**Step 6: Run backend type check**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876 && uv run mypy backend/`
Expected: PASS

**Step 7: Commit**

```bash
git add -A backend/
git commit -m "refactor: remove /api/logs endpoint

Delete backend logs API (replaced by Loki):
- backend/api/routes/logs.py (~400 lines)
- backend/api/schemas/logs.py
- All associated test files

Logs are now collected by Alloy and stored in Loki.
Query via Grafana or LogQL API directly.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Cleanup and Validation

**Step 1: Run full validation**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876 && ./scripts/validate.sh`
Expected: PASS

**Step 2: Verify frontend builds**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npm run build`
Expected: PASS

**Step 3: Check for dead code**

Run: `cd /home/msvoboda/.claude-squad/worktrees/msvoboda/clean2_188c8be343a06876/frontend && npx knip`

If any orphaned imports related to old logs components found, clean them up.

**Step 4: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: cleanup orphaned imports after logs migration

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Summary

| Task                  | Files Changed | Lines Removed | Lines Added |
| --------------------- | ------------- | ------------- | ----------- |
| 1. Grafana Dashboard  | +1            | 0             | ~350        |
| 2. LogsPage Component | +2            | 0             | ~200        |
| 3. App.tsx Routing    | 1 modified    | 2             | 2           |
| 4. Alloy Config       | 1 modified    | 0             | ~30         |
| 5. Alert Rules        | +1            | 0             | ~80         |
| 6. Delete Frontend    | -12           | ~1,200        | 0           |
| 7. Delete Backend     | -5            | ~600          | 0           |
| 8. Cleanup            | varies        | varies        | varies      |

**Net result:** ~1,800 lines removed, ~660 lines added = **~1,140 lines reduced**
