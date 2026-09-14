# Logs Components Directory

## Purpose

Contains the system logs page component that embeds a Grafana dashboard for viewing and analyzing logs from all services via Loki.

## Files

| File               | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `LogsPage.tsx`     | Main logs page embedding Grafana Loki dashboard    |
| `LogsPage.test.tsx`| Test suite for LogsPage                            |
| `AGENTS.md`        | This documentation file                            |

**Note:** No `index.ts` barrel export - import components directly.

## Architecture

This directory previously contained custom log viewing components (LogsDashboard, LogsTable, LogFilters, etc.). These have been replaced with a Grafana-embedded approach that leverages Loki for centralized log aggregation.

### Why Grafana/Loki?

- **Centralized logging**: All services (backend, AI pipeline, etc.) send logs to Loki
- **Powerful queries**: LogQL provides sophisticated filtering and aggregation
- **Real-time streaming**: Live tail functionality built-in
- **Production-ready**: Battle-tested log management infrastructure
- **Consistent with metrics**: Same Grafana instance used for system metrics

## Key Component

### LogsPage.tsx

**Purpose:** Embeds the HSI System Logs Grafana dashboard for centralized log viewing

**Key Features:**

- Fetches Grafana URL from backend config
- Embeds HSI System Logs dashboard (`hsi-logs`) in kiosk mode
- External links to open full Grafana dashboard and Explore
- Refresh button to reload the iframe
- Error handling with fallback messaging
- Loading state with skeleton animation

**Props:** None (standalone page component)

**State:**

```typescript
const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
const [isLoading, setIsLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [isRefreshing, setIsRefreshing] = useState(false);
```

**Dashboard URLs:**

- **Embedded view**: `{grafanaUrl}/d/hsi-logs/hsi-system-logs?orgId=1&kiosk=1&theme=dark&refresh=30s`
- **Full dashboard**: `{grafanaUrl}/d/hsi-logs/hsi-system-logs?orgId=1&theme=dark`
- **Explore (LogQL)**: `{grafanaUrl}/explore?orgId=1&left={datasource:loki}`

## Test Data IDs

```typescript
data-testid="logs-page"           // Main page container
data-testid="logs-loading"        // Loading state container
data-testid="logs-error"          // Error banner
data-testid="logs-iframe"         // Grafana iframe
data-testid="logs-refresh-button" // Refresh button
data-testid="grafana-external-link" // Open in Grafana link
data-testid="explore-external-link" // Open in Explore link
```

## Styling

- Page background: `bg-[#121212]`
- Header: Border bottom with `border-gray-800`
- Icons: NVIDIA green (`text-[#76B900]`)
- Buttons: `bg-gray-800 hover:bg-gray-700`
- Error banner: Yellow warning theme

## Dependencies

- `lucide-react` - Icons (FileText, RefreshCw, ExternalLink, AlertCircle)
- `react` - useState, useEffect, useRef, useCallback
- `../../services/api` - fetchConfig
- `../../utils/grafanaUrl` - resolveGrafanaUrl

## Related Infrastructure

- **Grafana Dashboard**: `hsi-logs` (HSI System Logs)
- **Data Source**: Loki
- **Log Collection**: Promtail or direct Loki push
- **Services logged**: backend, frontend, ai-pipeline, yolo26, nemotron

## Entry Points

**Start here:** `LogsPage.tsx` - Simple component that embeds Grafana dashboard

## Migration Notes

The following components were removed in favor of Grafana-embedded logging:

- `LogsDashboard.tsx` - Replaced by LogsPage with Grafana embed
- `LogsTable.tsx` - Loki provides log display
- `LogFilters.tsx` - LogQL provides filtering
- `LogDetailModal.tsx` - Grafana provides log details
- `LogStatsCards.tsx` - Grafana dashboard includes stats
- `LogStatsSummary.tsx` - Grafana dashboard includes summaries
- `logGrouping.ts` - LogQL handles grouping

The custom log API endpoints (`/api/logs`, `/api/logs/stats`) can be deprecated once all clients migrate to Loki.
