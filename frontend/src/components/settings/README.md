# Settings Components

Components for the Settings page (`/settings`) of the home security dashboard.
`AGENTS.md` in this directory is the authoritative file index; this README
covers the two things an agent usually comes here for: how a settings panel
gets its data, and what `AIModelsSettings` actually renders.

## How Settings Panels Get Their Data

There is no shared settings store. Each panel owns its own fetch:

- Reads go through the typed client in `../../services/api` (or a TanStack
  Query hook in `../../hooks/`).
- Writes POST/PUT to the matching backend route, then re-fetch. Several panels
  use the mutation hooks in `../../hooks/useServiceMutations`.
- `SettingsPage.tsx` only handles tab routing; it does not pass data down.

Backend model management lives in `backend/api/routes/model_management.py`
under `/api/system/models`:

- `GET /api/system/models` - list models with status
- `GET /api/system/models/{model_name}/status` - one model
- `POST /api/system/models/{model_name}/load` · `/unload` · `/reload`
- `POST /api/system/models/unload-all`
- `GET /api/system/models/vram-summary`

## AIModelsSettings

Renders AI model status and metrics for the detection model and the Nemotron
reasoning model.

### Props

```typescript
interface AIModelsSettingsProps {
  rtdetrModel?: ModelInfo;
  nemotronModel?: ModelInfo;
  totalMemory?: number | null; // MB
  className?: string;
}

interface ModelInfo {
  name: string;
  status: 'loaded' | 'unloaded' | 'error';
  memoryUsed: number | null; // MB
  inferenceFps: number | null;
  description: string;
}
```

Note the prop name: it is `rtdetrModel`, not `yolo26Model`. The component
label for the detection model follows whatever the backend reports.

### Default Behavior

Props are optional. With none supplied, the component calls `useAIMetrics()`
and derives both models from that, falling back to placeholder cards: both
models shown as unloaded, memory and FPS as `N/A`.

### Layout

- Two-column grid on large screens (`lg:grid-cols-2`), one column on mobile
- One card per model, each with a status badge and a Tremor `ProgressBar` for
  memory
- Optional total-memory summary card

### Status Colors

Loaded = green, unloaded = gray, error = red. NVIDIA green (`#76B900`) marks
active elements.

### Data Sources

`useAIMetrics` (`../../hooks/useAIMetrics.ts`) aggregates:

- `/api/system/health` - AI service health status
- `/api/system/telemetry` - queue depths and basic latency
- `/api/system/pipeline-latency` - latency percentiles
- `/api/metrics` - Prometheus histograms
- `/api/dlq/stats`, `/api/detections/stats`

### Testing

`AIModelsSettings.test.tsx` covers status badges for every state, memory and
FPS formatting, null and edge-case values, grid layout, and `className`.

```bash
cd frontend && npm test -- --run AIModelsSettings
```

## Related Components

- `frontend/src/components/dashboard/GpuStats.tsx` - GPU metrics display using
  the same GPU data
- `frontend/src/components/settings/ModelZooPanel.tsx` - the Model Zoo table
  (moved here from `system/` when the Infrastructure page was removed in #3471)
- `frontend/src/components/system/AGENTS.md` - the operations page that
  consumes the same health and telemetry endpoints
