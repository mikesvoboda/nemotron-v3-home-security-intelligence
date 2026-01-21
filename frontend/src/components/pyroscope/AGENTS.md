# Continuous Profiling Components

## Overview

The pyroscope directory contains the continuous profiling page that integrates Grafana's dashboard and Explore views with Pyroscope as the datasource. This provides CPU and memory profiling visibility across the backend, AI models, and model zoo with flame graph analysis and timeline visualization.

## Architecture

The profiling page follows an iframe embedding pattern similar to the TracingPage, allowing users to visualize continuous profiles across services and models while maintaining consistent styling with the rest of the application.

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR APP                                 │
├─────────────────────────────────────────────────────────────────┤
│  Sidebar              │  PyroscopePage                          │
│  ───────              │  ──────────────                          │
│  OPERATIONS           │  ┌───────────────────────────────────┐  │
│  ├─ Jobs              │  │ [Grafana][Explore][Pyroscope][↻] │  │
│  ├─ Pipeline          │  ├───────────────────────────────────┤  │
│  ├─ AI                │  │                                   │  │
│  │  ├─ Performance    │  │   Grafana Dashboard (iframe)      │  │
│  │  ├─ Audit          │  │   with Pyroscope datasource       │  │
│  │  └─ Profiling ◄────┼──│                                   │  │
│  └─ Logs              │  │   Profile Timeline + Flame Graphs │  │
│                       │  │                                   │  │
│                       │  └───────────────────────────────────┘  │
└───────────────────────┴─────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        ┌──────────┐         ┌──────────┐         ┌──────────┐
        │Pyroscope │ ◄────── │ Grafana  │ ──────► │Prometheus│
        │:4040     │  query  │  :3002   │  query  │  :9090   │
        └──────────┘         └──────────┘         └──────────┘
              ▲
              │ profiles
        ┌─────┴──────────┐
        │  Backend       │
        │  AI Services   │
        │  Model Zoo     │
        └────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `PyroscopePage.tsx` | Main page component embedding Grafana dashboard with Pyroscope datasource |
| `PyroscopePage.test.tsx` | Unit tests covering rendering, refresh, external links, and config loading |
| `index.ts` | Barrel export for PyroscopePage component |

## Features

### Profile Timeline
- Time-series visualization of CPU/memory usage across services
- Clickable timeline to view specific profile snapshots
- Configurable time range (1h, 6h, 24h, 7d)
- Real-time updates with refresh capability

### Service Flame Graphs
- Per-service flame graph visualization
- Supported services: Backend, RT-DETR, Nemotron, Florence
- Profile type selection: CPU or Memory
- Drill-down into hot code paths and resource consumption

### Model Zoo Filtering
When Backend service is selected, dashboard shows per-model profiling breakdown for:
- `yolo11-license-plate` (300 MB VRAM)
- `yolo11-face` (200 MB VRAM)
- `paddleocr` (100 MB VRAM)
- `clip-vit-l` (800 MB VRAM)
- `yolo-world-s` (1500 MB VRAM)
- `vitpose-small` (1500 MB VRAM)
- `depth-anything-v2-small` (150 MB VRAM)
- `violence-detection` (500 MB VRAM)
- `weather-classification` (200 MB VRAM)
- `segformer-b2-clothes` (1500 MB VRAM)
- `xclip-base` (2000 MB VRAM)
- `fashion-clip` (500 MB VRAM)
- `brisque-quality` (0 MB VRAM - CPU only)
- `vehicle-segment-classification` (1500 MB VRAM)
- `vehicle-damage-detection` (2000 MB VRAM)
- `pet-classifier` (200 MB VRAM)

### External Links
- **Open in Grafana**: Direct link to dashboard for kiosk-free editing
- **Explore**: Opens Grafana Explore for ad-hoc profiling queries with Pyroscope datasource
- **Open Pyroscope**: Direct access to native Pyroscope UI on localhost:4040 for power users
- **Refresh**: Manual iframe refresh to reload latest profile data

## URL Construction

The profiling page constructs Grafana URLs dynamically:

```typescript
// Dashboard URL - HSI Profiling dashboard with kiosk mode and dark theme
const getDashboardUrl = () => {
  return `${grafanaUrl}/d/hsi-profiling/hsi-profiling?orgId=1&kiosk=1&theme=dark&refresh=30s`;
};

// Explore URL - Pyroscope datasource with dark theme
const getExploreUrl = () => {
  return `${grafanaUrl}/explore?orgId=1&theme=dark&left={"datasource":"Pyroscope"}`;
};

// External Grafana link - Dashboard without kiosk mode for editing
const grafanaExternalLink = `${grafanaUrl}/d/hsi-profiling/hsi-profiling?orgId=1&theme=dark`;

// Pyroscope native UI
const pyroscopeLink = 'http://localhost:4040';
```

Parameters:
- `orgId=1`: Grafana organization ID
- `kiosk=1`: Kiosk mode for cleaner embedded UI (dashboard only)
- `theme=dark`: Dark theme matching application styling
- `refresh=30s`: Auto-refresh dashboard every 30 seconds
- `datasource`: Pyroscope datasource name for Explore

## Dependencies

### External Services
- **Grafana**: Provides dashboard and Explore UI with iframe embedding
- **Pyroscope**: Profiling backend collecting CPU/memory profiles
- **Prometheus**: Metrics backend for correlation queries
- **Backend**: Profiling instrumentation sending profiles to Pyroscope with service labels
- **AI Services**: Model inference profiling with per-model labels

### React Hooks
- `useState`: Managing loading, error, and refresh states
- `useEffect`: Fetching Grafana configuration
- `useRef`: Accessing iframe for refresh functionality
- `useCallback`: Memoizing refresh handler

### Icons (lucide-react)
- `Flame`: Page header icon for profiling
- `RefreshCw`: Refresh button icon
- `ExternalLink`: External link icons
- `AlertCircle`: Error notification icon
- `Search`: Explore button icon

## Testing Instructions

### Run Unit Tests
```bash
cd frontend
npm test pyroscope/PyroscopePage.test.tsx
```

### Test Coverage
Unit tests cover:
1. **Rendering**: Loading state, loaded state, error state
2. **Config Loading**: Fetching Grafana URL from backend config
3. **Error Handling**: Display error banner on config fetch failure
4. **External Links**: Open in Grafana, Explore, and Open Pyroscope buttons
5. **Refresh**: Manual iframe refresh functionality
6. **Dashboard URL**: Correct URL construction with kiosk mode and dark theme
7. **Explore URL**: Correct Pyroscope datasource configuration

### Manual Testing
1. Navigate to `/pyroscope` in application
2. Verify Grafana dashboard loads within iframe showing profile timeline
3. Click "Open in Grafana" - should open dashboard in new tab (editable)
4. Click "Explore" - should open Grafana Explore with Pyroscope datasource
5. Click "Open Pyroscope" - should open native Pyroscope UI
6. Click "Refresh" - iframe should reload with latest profile data
7. Verify service filters show Backend, RT-DETR, Nemotron, Florence
8. Verify model filter shows active model zoo models when Backend selected
9. Verify no console errors in browser DevTools

## Design Document

For detailed architecture decisions, feature rationale, dashboard panels, and implementation notes, see:
[Pyroscope Profiling Page Design](../../docs/plans/2026-01-20-pyroscope-page-design.md)

## Pattern Reference

This component follows the same iframe embedding pattern as:
- `TracingPage.tsx` - Distributed tracing with Grafana/Jaeger
- `AIPerformancePage.tsx` - AI metrics with Grafana panels

Key pattern principles:
- Use `resolveGrafanaUrl()` utility for URL resolution
- Construct Grafana URLs with proper encoding
- Provide external links for direct access to underlying tools
- Handle loading and error states gracefully
- Implement refresh functionality for iframe reloading
- Dark theme integration via Grafana theme parameter
- Config-driven URL resolution for flexible deployments

## Related Components

- `../tracing/TracingPage.tsx` - Distributed tracing page (same pattern)
- `../ai/AIPerformancePage.tsx` - AI metrics page (same pattern)

## Entry Points

**Start here:** `PyroscopePage.tsx` - Understand the main component structure and URL construction
**Then explore:** `index.ts` - See the barrel export pattern
**Review patterns:** Compare with `../tracing/AGENTS.md` - Similar iframe embedding approach
