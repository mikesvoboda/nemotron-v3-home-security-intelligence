# Logs Page Grafana/Loki Migration Design

> **Status:** Implemented — `frontend/src/components/logs/LogsPage.tsx` embeds the Grafana logs dashboard.

**Date:** 2026-01-20
**Status:** Approved
**Related Epic:** NEM-3090 (Loki, Pyroscope, and Alloy Observability Stack Integration)

## Overview

Replace the custom React-based logs page (`LogsDashboard.tsx`) with an embedded Grafana dashboard powered by Loki. This consolidates tooling, enhances features via LogQL, and reduces maintenance burden.

## Goals

1. **Consolidate tooling** - Remove custom code, use Grafana as single log viewer, leverage Loki's correlation features
2. **Feature enhancement** - LogQL queries, trace correlation, live streaming, pattern detection
3. **Maintenance reduction** - Less React code to maintain, Grafana handles updates

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (/logs)                         │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  LogsPage.tsx (new, ~120 lines)                       │ │
│  │  - Header with title + "Open in Grafana" + Refresh    │ │
│  │  - Grafana iframe (kiosk mode)                        │ │
│  │    └── hsi-logs dashboard                             │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Grafana Dashboard                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │ Service ▼   │ │ Level ▼     │ │ Search: [________]  │   │
│  └─────────────┘ └─────────────┘ └─────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Metrics from Logs + Volume + Distribution           │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Pattern Analysis + Errors by Service                │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Logs Panel (with trace_id links to Jaeger)          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                         Loki (LogQL)
```

## Grafana Dashboard Design

### Dashboard: `hsi-logs`

**Variables (top row):**

| Variable  | Type     | Query/Values                                    |
| --------- | -------- | ----------------------------------------------- |
| `service` | Query    | `label_values(container)` - all container names |
| `level`   | Custom   | `All, DEBUG, INFO, WARNING, ERROR, CRITICAL`    |
| `search`  | Text box | Free text for LogQL filter                      |
| `live`    | Custom   | Toggle for live tail mode                       |

### Panel Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Variables Row                                               │
│ [Service ▼] [Level ▼] [Search: ______] [🔴 Live Tail ○]    │
├─────────────────────────────────────────────────────────────┤
│ Row 1: Metrics from Logs                                    │
│ ┌──────────────────────────┐ ┌────────────────────────────┐ │
│ │ Error Rate (errors/min)  │ │ Log Throughput (lines/sec) │ │
│ │ rate({level="ERROR"}[1m])│ │ rate({}[1m])               │ │
│ └──────────────────────────┘ └────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Row 2: Volume + Distribution                                │
│ ┌─────────────────────────────────┐ ┌─────────────────────┐ │
│ │ Log Volume (stacked by level)   │ │ Level Distribution  │ │
│ │ + Annotation markers for errors │ │ (pie)               │ │
│ └─────────────────────────────────┘ └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Row 3: Pattern Analysis                                     │
│ ┌──────────────────────────────┐ ┌────────────────────────┐ │
│ │ Top Error Patterns (table)   │ │ Errors by Service     │ │
│ │ pattern `<_> error <_>`      │ │ (bar chart)           │ │
│ │ - Grouped similar messages   │ │                       │ │
│ └──────────────────────────────┘ └────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Row 4: Extracted Fields (collapsible)                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Parsed fields: camera, batch_id, duration_ms, trace_id  │ │
│ │ [Camera ▼] [Batch ID: ____] [Duration > ___ms]          │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ Row 5: Logs Panel (~50% height)                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 📜 Logs                                    [Dedup ▼]    │ │
│ │ ┌─────────────────────────────────────────────────────┐ │ │
│ │ │ 🔗 trace_id=abc123 → View Trace                     │ │ │
│ │ │ 📋 Show Context (±50 lines)                         │ │ │
│ │ │ 📥 Download filtered logs                           │ │ │
│ │ └─────────────────────────────────────────────────────┘ │ │
│ │ • Multi-line stack traces grouped                      │ │
│ │ • Duplicate lines collapsed with count                 │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Advanced Loki Features

| Feature                 | Implementation                                         |
| ----------------------- | ------------------------------------------------------ |
| **Log context**         | Built-in "Show context" button in Logs panel           |
| **Pattern detection**   | `pattern` parser groups similar error messages         |
| **Metrics from logs**   | Error rate and throughput panels using `rate()`        |
| **JSON/logfmt parsing** | Extract camera, batch_id, duration_ms, trace_id fields |
| **Log-based alerts**    | Grafana alerting rules on LogQL queries                |
| **Annotations overlay** | Error events as markers on volume graph                |
| **Live tail**           | Toggle variable + Logs panel live mode                 |
| **Deduplication**       | Built-in dedup option in Logs panel                    |
| **Download/export**     | Built-in export to CSV/JSON                            |
| **Multi-line support**  | Stack trace grouping via Loki config                   |

### Alert Rules

**File:** `monitoring/grafana/provisioning/alerting/log-alerts.yml`

| Alert           | Condition                                         | Severity |
| --------------- | ------------------------------------------------- | -------- |
| High Error Rate | `rate({level="ERROR"}[5m]) > 10`                  | Warning  |
| Error Spike     | `rate({level="ERROR"}[1m]) > 3x avg of last hour` | Critical |
| Service Silent  | No logs from service for 5 minutes                | Warning  |
| Pattern Surge   | Specific error pattern appears >50 times in 5m    | Warning  |

## Frontend Component

### LogsPage.tsx

Pattern matches `TracingPage.tsx` for consistency:

```
LogsPage
├── Header
│   ├── Icon (FileText) + Title "System Logs"
│   ├── Live Tail indicator (synced with Grafana var if possible)
│   ├── "Open in Grafana" button (external link)
│   ├── "Open in Explore" button (for ad-hoc LogQL)
│   └── Refresh button
├── Error banner (if config fetch fails)
└── Grafana iframe
    └── src: /grafana/d/hsi-logs/hsi-system-logs?orgId=1&kiosk=1&theme=dark&refresh=30s
```

### Route Update

```tsx
// In App.tsx, change:
const LogsDashboard = lazy(() => import('./components/logs/LogsDashboard'));
// To:
const LogsPage = lazy(() => import('./components/logs/LogsPage'));

// Route stays the same:
<Route path="/logs" element={<LogsPage />} />;
```

## Files to Create

| File                                                      | Purpose                           |
| --------------------------------------------------------- | --------------------------------- |
| `frontend/src/components/logs/LogsPage.tsx`               | New iframe component (~120 lines) |
| `monitoring/grafana/dashboards/logs.json`                 | Grafana dashboard definition      |
| `monitoring/grafana/provisioning/alerting/log-alerts.yml` | Log-based alert rules             |

## Files to Modify

| File                                                         | Change                                           |
| ------------------------------------------------------------ | ------------------------------------------------ |
| `frontend/src/App.tsx`                                       | Update lazy import from LogsDashboard → LogsPage |
| `monitoring/alloy/config.alloy`                              | Add enhanced JSON field parsing                  |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Ensure Loki derived fields configured            |

## Files to Delete

### Frontend Components

| File                                                   | Lines | Reason                               |
| ------------------------------------------------------ | ----- | ------------------------------------ |
| `frontend/src/components/logs/LogsDashboard.tsx`       | 265   | Replaced by LogsPage                 |
| `frontend/src/components/logs/LogsDashboard.test.tsx`  | ~200  | Tests for deleted component          |
| `frontend/src/components/logs/LogFilters.tsx`          | ~150  | Grafana variables replace this       |
| `frontend/src/components/logs/LogFilters.test.tsx`     | ~100  | Tests for deleted component          |
| `frontend/src/components/logs/LogsTable.tsx`           | ~200  | Grafana Logs panel replaces this     |
| `frontend/src/components/logs/LogsTable.test.tsx`      | ~150  | Tests for deleted component          |
| `frontend/src/components/logs/LogStatsCards.tsx`       | ~100  | Grafana panels replace this          |
| `frontend/src/components/logs/LogStatsCards.test.tsx`  | ~80   | Tests for deleted component          |
| `frontend/src/components/logs/LogStatsSummary.tsx`     | ~50   | Grafana panels replace this          |
| `frontend/src/components/logs/LogDetailModal.tsx`      | ~100  | Log context in Grafana replaces this |
| `frontend/src/components/logs/LogDetailModal.test.tsx` | ~80   | Tests for deleted component          |

### Backend

| File/Code                  | Description                            |
| -------------------------- | -------------------------------------- |
| `/api/logs` endpoint       | Route handler in `backend/api/routes/` |
| `/api/logs/stats` endpoint | Stats aggregation endpoint             |
| Log query service          | Business logic for log fetching        |
| Log models/schemas         | Pydantic models for log responses      |

**Estimated reduction:** ~1,500+ lines of code removed

### What Stays

- Backend logging itself (logs still written, Alloy collects them)
- `LogLevelPanel.tsx` (developer tool for changing log levels - different purpose)
- Audit log functionality (separate from system logs)

## Alloy Configuration Update

Add enhanced JSON field parsing to `monitoring/alloy/config.alloy`:

```hcl
// Enhanced parsing for structured fields
loki.process "parse" {
  stage.docker {}

  // Extract log level
  stage.regex {
    expression = "(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)"
  }

  // Extract structured fields from JSON logs
  stage.json {
    expressions = {
      camera = "camera",
      batch_id = "batch_id",
      duration_ms = "duration_ms",
      trace_id = "trace_id",
      span_id = "span_id"
    }
  }

  // Extract camera name from AI pipeline logs (fallback for non-JSON)
  stage.regex {
    expression = "camera[=: ]+(?P<camera>[a-z_]+)"
  }

  stage.labels {
    values = { level = "", camera = "", batch_id = "", trace_id = "", span_id = "" }
  }

  // Multi-line stack trace support
  stage.multiline {
    firstline = "^\\d{4}-\\d{2}-\\d{2}"
    max_wait_time = "3s"
  }

  forward_to = [loki.write.local.receiver]
}
```

## Success Criteria

- [ ] `/logs` route shows embedded Grafana dashboard
- [ ] Can filter by service, level, and search text
- [ ] Can click trace_id to open Jaeger trace
- [ ] Live tail works
- [ ] Log context (surrounding lines) accessible
- [ ] Pattern detection groups similar errors
- [ ] Alerts fire on error spikes
- [ ] All old logs components deleted
- [ ] Backend `/api/logs` endpoint removed
- [ ] ~1,500 lines of code removed

## References

- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [LogQL Query Language](https://grafana.com/docs/loki/latest/query/)
- [Grafana Logs Panel](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/logs/)
- Related: `docs/plans/2026-01-20-loki-pyroscope-alloy-design.md`
