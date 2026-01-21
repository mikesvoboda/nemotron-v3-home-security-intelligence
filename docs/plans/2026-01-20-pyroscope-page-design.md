# Pyroscope Profiling Page Design

**Date:** 2026-01-20
**Status:** Approved
**Author:** Claude (with Mike Svoboda)

## Overview

Add a dedicated Profiling page to the frontend that embeds Grafana with the Pyroscope datasource, providing continuous profiling visibility for CPU and memory performance across AI services and model zoo models.

## Goals

1. **Performance debugging** - Drill into CPU/memory hotspots when investigating slow requests
2. **Continuous profiling dashboard** - Always-on view of service performance over time
3. **Profile comparison** - Compare before/after profiles during optimization work
4. **Trace-linked profiles** - Jump to profiles from Jaeger traces (integration focus)

## Architecture Decision

**Chosen Approach:** Hybrid - Default dashboard view + Explore button for ad-hoc analysis

### Why This Approach

| Alternative               | Reason Not Chosen                                                    |
| ------------------------- | -------------------------------------------------------------------- |
| Single dashboard only     | Limits ad-hoc deep dives                                             |
| Explore only              | No curated experience for common workflows                           |
| Native React flame graphs | High development effort, Grafana already has excellent visualization |

### Benefits of Chosen Approach

- Curated dashboard for common profiling workflows
- Grafana Explore available for ad-hoc analysis
- Native Pyroscope UI accessible for power users
- Consistent with TracingPage pattern

## Technical Design

### 1. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PyroscopePage                            │
├─────────────────────────────────────────────────────────────────┤
│  Header                                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ 🔥 Profiling  [Open in Grafana] [Explore] [Pyroscope] [↻] │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Grafana Dashboard (iframe)                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Profile Timeline (clickable to view specific profiles)     ││
│  │  ───────────────────────────────────────────────────────────││
│  │  Service Flame Graphs:                                      ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       ││
│  │  │ Backend  │ │ RT-DETR  │ │ Nemotron │ │ Florence │       ││
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘       ││
│  │                                                             ││
│  │  Model Zoo (when Backend selected):                         ││
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                    ││
│  │  │ vitpose  │ │yolo-world│ │fashion-cl│  ... more          ││
│  │  └──────────┘ └──────────┘ └──────────┘                    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 2. Dashboard Panels

**Panel A: Profile Timeline**

- Time-series visualization of CPU/memory usage
- Clickable points to view specific profile snapshots
- Configurable time range (1h, 6h, 24h, 7d)

**Panel B: Service Flame Graphs**

- Filters: Service dropdown, Model dropdown, Profile type (CPU/Memory)
- Services: Backend, RT-DETR, Nemotron, Florence
- Model Zoo filter: When "Backend" selected, shows per-model breakdown via Pyroscope labels

**Model Zoo Models (17 total):**

| Model                          | Category           | VRAM    |
| ------------------------------ | ------------------ | ------- |
| yolo11-license-plate           | detection          | 300 MB  |
| yolo11-face                    | detection          | 200 MB  |
| paddleocr                      | ocr                | 100 MB  |
| clip-vit-l                     | embedding          | 800 MB  |
| yolo-world-s                   | detection          | 1500 MB |
| vitpose-small                  | pose               | 1500 MB |
| depth-anything-v2-small        | depth              | 150 MB  |
| violence-detection             | classification     | 500 MB  |
| weather-classification         | classification     | 200 MB  |
| segformer-b2-clothes           | segmentation       | 1500 MB |
| xclip-base                     | action-recognition | 2000 MB |
| fashion-clip                   | classification     | 500 MB  |
| brisque-quality                | quality (CPU)      | 0 MB    |
| vehicle-segment-classification | classification     | 1500 MB |
| vehicle-damage-detection       | detection          | 2000 MB |
| pet-classifier                 | classification     | 200 MB  |

### 3. Frontend Changes

#### PyroscopePage Component

**File:** `frontend/src/components/pyroscope/PyroscopePage.tsx`

```tsx
/**
 * PyroscopePage - Continuous profiling dashboard via Grafana/Pyroscope
 *
 * Embeds the HSI Profiling dashboard for:
 * - CPU/memory flame graphs per service
 * - Profile timeline with clickable snapshots
 * - Per-model filtering for model zoo
 * - Trace-to-profile correlation
 */

import { Flame, RefreshCw, ExternalLink, AlertCircle, Search } from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

export default function PyroscopePage() {
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

  // Construct Grafana Dashboard URL
  const getDashboardUrl = () => {
    return `${grafanaUrl}/d/hsi-profiling/hsi-profiling?orgId=1&kiosk=1&theme=dark&refresh=30s`;
  };

  // Construct Grafana Explore URL with Pyroscope
  const getExploreUrl = () => {
    return `${grafanaUrl}/explore?orgId=1&theme=dark&left={"datasource":"Pyroscope"}`;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="pyroscope-loading">
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
    <div className="min-h-screen bg-[#121212]" data-testid="pyroscope-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Flame className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Profiling</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* Open in Grafana */}
          <a
            href={`${grafanaUrl}/d/hsi-profiling/hsi-profiling?orgId=1&theme=dark`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="grafana-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open in Grafana
          </a>

          {/* Explore */}
          <a
            href={getExploreUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="explore-link"
          >
            <Search className="h-4 w-4" />
            Explore
          </a>

          {/* Open Pyroscope */}
          <a
            href="http://localhost:4040"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="pyroscope-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open Pyroscope
          </a>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="pyroscope-refresh-button"
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
          data-testid="pyroscope-error"
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
        title="Profiling"
        data-testid="pyroscope-iframe"
      />
    </div>
  );
}
```

#### Module Export

**File:** `frontend/src/components/pyroscope/index.ts`

```tsx
export { default as PyroscopePage } from './PyroscopePage';
```

#### Route Configuration

**File:** `frontend/src/App.tsx`

```tsx
// Add lazy import (after AIAuditPage)
const PyroscopePage = lazy(() =>
  import('./components/pyroscope').then((module) => ({ default: module.PyroscopePage }))
);

// Add route (after /ai-audit)
<Route path="/pyroscope" element={<PyroscopePage />} />;
```

#### Navigation Configuration

**File:** `frontend/src/components/layout/sidebarNav.ts`

```tsx
// Add import
import { Flame } from 'lucide-react';

// Update AI group - add after AI Audit
{
  id: 'ai',
  label: 'AI',
  defaultExpanded: true,
  items: [
    { id: 'ai', label: 'AI Performance', icon: Brain, path: '/ai' },
    { id: 'ai-audit', label: 'AI Audit', icon: FileCheck, path: '/ai-audit' },
    { id: 'pyroscope', label: 'Profiling', icon: Flame, path: '/pyroscope' },
  ],
},
```

### 4. Backend Changes

#### Pyroscope Labels for Model Zoo

**File:** `backend/services/model_zoo.py`

Add Pyroscope tagging during model load to enable per-model filtering:

```python
async def _load_model(self, model_name: str) -> Any:
    """Load a model into memory with Pyroscope labeling."""
    config = get_model_config(model_name)
    if config is None:
        raise KeyError(f"Unknown model: {model_name}")

    if not config.enabled:
        raise RuntimeError(f"Model {model_name} is disabled")

    logger.info(f"Loading model {model_name} (~{config.vram_mb}MB VRAM)")

    try:
        # Add Pyroscope label for per-model profiling
        try:
            import pyroscope
            with pyroscope.tag_wrapper({"model": model_name}):
                model = await config.load_fn(config.path)
        except ImportError:
            # Pyroscope not installed, load without tagging
            model = await config.load_fn(config.path)

        self._loaded_models[model_name] = model
        config.available = True
        logger.info(f"Successfully loaded model {model_name}")
        return model
    except Exception:
        logger.error("Failed to load model", exc_info=True, extra={"model_name": model_name})
        raise
```

#### Telemetry Configuration

**File:** `backend/core/telemetry.py`

Ensure Pyroscope is configured with service labels:

```python
# Add to Pyroscope initialization
pyroscope.configure(
    application_name="nemotron-backend",
    server_address="http://pyroscope:4040",
    tags={
        "service": "backend",
        "environment": os.environ.get("ENVIRONMENT", "development"),
    },
)
```

### 5. Grafana Dashboard

**File:** `monitoring/grafana/dashboards/hsi-profiling.json`

Create dashboard with:

- UID: `hsi-profiling`
- Title: "HSI Profiling"
- Panels:
  1. Profile Timeline (time-series)
  2. Service Flame Graphs (4x grid: Backend, RT-DETR, Nemotron, Florence)
  3. Model Zoo Flame Graphs (variable-driven, shows when Backend selected)

Dashboard variables:

- `$service`: Backend, RT-DETR, Nemotron, Florence
- `$model`: Populated from Pyroscope labels when service=Backend
- `$profile_type`: CPU, Memory

## File Summary

| File                                                       | Action | Purpose                                     |
| ---------------------------------------------------------- | ------ | ------------------------------------------- |
| `frontend/src/components/pyroscope/PyroscopePage.tsx`      | Create | Main page component                         |
| `frontend/src/components/pyroscope/PyroscopePage.test.tsx` | Create | Unit tests                                  |
| `frontend/src/components/pyroscope/index.ts`               | Create | Module export                               |
| `frontend/src/components/pyroscope/AGENTS.md`              | Create | Directory documentation                     |
| `frontend/src/App.tsx`                                     | Edit   | Add route `/pyroscope`                      |
| `frontend/src/components/layout/sidebarNav.ts`             | Edit   | Add nav item under AI group                 |
| `monitoring/grafana/dashboards/hsi-profiling.json`         | Create | Grafana dashboard JSON                      |
| `backend/services/model_zoo.py`                            | Edit   | Add Pyroscope labels during model load      |
| `backend/core/telemetry.py`                                | Edit   | Ensure Pyroscope profiling labels propagate |

## Success Criteria

1. PyroscopePage renders with dark theme matching existing pages
2. Grafana dashboard iframe loads with profile timeline and flame graphs
3. Service filter shows Backend, RT-DETR, Nemotron, Florence
4. Model filter (when Backend selected) shows active model zoo models
5. All four header buttons work correctly (Open in Grafana, Explore, Open Pyroscope, Refresh)
6. Unit tests pass with >80% coverage
7. Per-model Pyroscope labels emit during model zoo loads
8. Navigation item appears in AI group after AI Audit
