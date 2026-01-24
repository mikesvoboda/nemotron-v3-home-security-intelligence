# Distributed Tracing Components

## Overview

The tracing directory contains the distributed tracing visualization page that integrates Grafana's Explore view with Jaeger as the datasource. This provides unified trace visualization with consistent dark theme styling and rich metric correlations without requiring infrastructure migration.

## Architecture

The tracing page follows an iframe embedding pattern similar to the AI Performance page, allowing users to visualize distributed traces across the system while maintaining consistent styling with the rest of the application.

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR APP                                 │
├─────────────────────────────────────────────────────────────────┤
│  Sidebar              │  TracingPage                            │
│  ───────              │  ───────────                            │
│  OPERATIONS           │  ┌───────────────────────────────────┐  │
│  ├─ Jobs              │  │ [Search|Map] [Compare] [Jaeger]   │  │
│  ├─ Pipeline          │  ├───────────────────────────────────┤  │
│  ├─ Tracing  ◄────────┼──│                                   │  │
│  └─ Logs              │  │   Grafana Explore (iframe)        │  │
│                       │  │   with Jaeger datasource          │  │
│                       │  │                                   │  │
│                       │  │   Click span → 50+ metrics        │  │
│                       │  └───────────────────────────────────┘  │
└───────────────────────┴─────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        ┌──────────┐         ┌──────────┐         ┌──────────┐
        │  Jaeger  │ ◄────── │ Grafana  │ ──────► │Prometheus│
        │  :16686  │  query  │  :3002   │  query  │  :9090   │
        └──────────┘         └──────────┘         └──────────┘
              ▲
              │ OTLP traces
        ┌─────┴─────┐
        │  Backend  │
        │  (OTEL)   │
        └───────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `TracingPage.tsx` | Main page component embedding Grafana Explore with Jaeger datasource |
| `TracingPage.test.tsx` | Unit tests covering rendering, view modes, external links, and refresh |
| `index.ts` | Barrel export for TracingPage component |

## Features

### Trace Search
- Full trace search and visualization via Grafana's Explore interface
- Drill-down into individual spans with timeline view
- Span tag filtering and search

### Service Dependency Graph
- View service dependencies and call patterns
- Visualize request flow across services
- Identify bottlenecks and latency issues

### Trace Comparison
- Split-view comparison of two traces
- Side-by-side span analysis
- Latency comparison across services

### Metrics Correlation
The tracing page correlates traces with 50+ Prometheus metrics including:
- Pipeline health (errors, queue depth, circuit breaker state)
- AI service latencies (RT-DETR, Nemotron, Florence, CLIP, Enrichment)
- Batch processing metrics
- Database performance
- Redis/Cache metrics
- GPU metrics
- Event and detection metrics
- Cost tracking
- SLO metrics
- Worker pool status

When viewing a trace, users can click on spans to see related metrics from the same time window.

### External Links
- **Compare Traces**: Opens Grafana Explore in split-view mode for trace comparison
- **Open Jaeger**: Provides direct access to native Jaeger UI for power users

## View Modes

### Search Mode
Default mode for querying and analyzing individual traces. Allows:
- Searching by service, operation, tags, duration
- Viewing full trace waterfall with latency breakdown
- Inspecting individual span details
- Viewing logs and metrics for spans

### Service Map Mode
Displays service dependency graph showing:
- All services in the system
- Request patterns between services
- Error rates by service
- Latency percentiles

## URL Construction

The tracing page constructs Grafana Explore URLs dynamically:

```typescript
// Base parameters
const baseParams = 'orgId=1&kiosk=1&theme=dark';

// Jaeger query payload
const jaegerQuery = encodeURIComponent(JSON.stringify({
  datasource: 'Jaeger',
  queries: [{
    refId: 'A',
    queryType: viewMode === 'search' ? 'search' : 'dependencyGraph',
    service: 'nemotron-backend'
  }]
}));

// Final URL
${grafanaUrl}/explore?${baseParams}&left=${jaegerQuery}
```

Parameters:
- `orgId=1`: Grafana organization ID
- `kiosk=1`: Kiosk mode for cleaner UI
- `theme=dark`: Dark theme matching application styling
- `datasource`: Jaeger datasource name
- `queryType`: Either 'search' or 'dependencyGraph'
- `service`: Initial service to query (nemotron-backend)

## Dependencies

### External Services
- **Grafana**: Provides Explore UI and iframe embedding
- **Jaeger**: Tracing backend storing OTLP traces
- **Prometheus**: Metrics backend for correlation queries
- **Backend**: OTEL instrumentation sending traces to Jaeger

### React Hooks
- `useState`: Managing loading, error, refresh states
- `useEffect`: Fetching Grafana configuration
- `useRef`: Accessing iframe for refresh functionality
- `useCallback`: Memoizing refresh handler

### Icons (lucide-react)
- `Activity`: Page header icon
- `RefreshCw`: Refresh button icon
- `ExternalLink`: External link icons
- `AlertCircle`: Error notification icon
- `SplitSquareHorizontal`: Trace comparison icon

## Testing Instructions

### Run Unit Tests
```bash
cd frontend
npm test tracing/TracingPage.test.tsx
```

### Test Coverage
Unit tests cover:
1. **Rendering**: Loading state, loaded state, error state
2. **View Mode Toggle**: Switching between search and service map
3. **External Links**: Compare Traces and Open Jaeger links
4. **Refresh**: Manual iframe refresh functionality
5. **Config Loading**: Fetching Grafana URL from backend config
6. **Error Handling**: Display error banner on config fetch failure
7. **Iframe URL**: Correct URL construction with proper encoding

### Manual Testing
1. Navigate to `/tracing` in application
2. Verify Grafana Explore loads within iframe
3. Test view mode toggle between "Trace Search" and "Service Map"
4. Click "Compare Traces" - should open new window
5. Click "Open Jaeger" - should open native Jaeger UI
6. Click "Refresh" - iframe should reload
7. Verify no console errors in browser DevTools

## Design Document

For detailed architecture decisions, feature rationale, and implementation notes, see:
[Distributed Tracing Page Design](../../../../docs/plans/2026-01-20-distributed-tracing-page-design.md)

## Pattern Reference

This component follows the same iframe embedding pattern as:
- `ai/AIPerformancePage.tsx` - Another Grafana-embedded page

Key pattern principles:
- Use `resolveGrafanaUrl()` utility for URL resolution
- Construct Grafana URLs with proper encoding
- Provide external links for direct access to underlying tools
- Handle loading and error states gracefully
- Implement refresh functionality for iframe reloading
- Dark theme integration via Grafana theme parameter
