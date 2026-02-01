# Model Zoo Management API Design

**Date:** 2025-01-31
**Status:** Ready for Implementation
**Priority:** HIGH
**Complexity:** Lightweight
**Linear Epic:** NEM-4780

## Problem Statement

The Model Zoo (`backend/services/model_zoo.py`) manages AI model lifecycle but has 7 unexposed methods. Operators cannot:

- See which models are currently loaded
- Load/unload models on demand
- Check VRAM usage per model
- Preload models before needed

## Goals

1. Expose model management via REST API
2. Add model status panel to AI Models settings
3. Enable on-demand model loading/unloading

## Non-Goals

- Model download/installation (models are pre-installed)
- Model fine-tuning
- Custom model upload

## Architecture Decisions

The following decisions were made during design review (2025-02-01):

### 1. Hybrid Aggregation Architecture

The system has two model management layers:

| Layer              | Location                         | Purpose                                       |
| ------------------ | -------------------------------- | --------------------------------------------- |
| Backend Model Zoo  | `backend/services/model_zoo.py`  | Registry of 22 available models (config only) |
| Enrichment Manager | `ai/enrichment/model_manager.py` | Runtime loading in GPU memory                 |

**Decision:** Backend API acts as an aggregation layer that combines:

- Static model metadata from the registry (name, category, estimated VRAM)
- Runtime state from enrichment services via HTTP proxy

```
Frontend → Backend API → HTTP calls → Enrichment Services → GPU
                ↓
         Model Zoo Registry (static config)
```

**Benefits:**

- Single API surface for frontend
- Backend already knows about both enrichment services
- Graceful degradation if enrichment service is down
- Frontend doesn't need to know service topology

### 2. Multi-GPU Visibility

Models are split across two enrichment services:

| Service               | Port | GPU   | VRAM Budget | Model Types                                   |
| --------------------- | ---- | ----- | ----------- | --------------------------------------------- |
| `ai-enrichment`       | 8094 | GPU 0 | 6.8 GB      | Heavy: vehicle, fashion, action, demographics |
| `ai-enrichment-light` | 8096 | GPU 1 | 1.2 GB      | Light: pose, threat, reid, pet, depth         |

**Decision:** UI will display GPU assignment and service info for each model. This helps operators:

- Debug VRAM issues
- Understand why certain models compete for memory
- See which service handles each model

### 3. Proxy to Existing Endpoints

The enrichment services already have model management endpoints:

- `GET /models/status` - Returns loaded models, VRAM usage
- `POST /models/preload?model_name=xxx` - Load a model

**Decision:** Backend will proxy to these existing endpoints. Minor addition:

- Add `POST /models/{name}/unload` to enrichment services

### 4. Per-GPU VRAM Breakdown

**Decision:** VRAM summary endpoint returns per-GPU breakdown, not flat totals:

```json
{
  "gpus": [
    { "gpu_id": 0, "service": "ai-enrichment", "budget_mb": 6800, "used_mb": 2100 },
    { "gpu_id": 1, "service": "ai-enrichment-light", "budget_mb": 1200, "used_mb": 450 }
  ]
}
```

## API Design

### New Backend Endpoints

| Method | Endpoint                           | Description                                   |
| ------ | ---------------------------------- | --------------------------------------------- |
| GET    | `/api/system/models`               | List all models with registry + runtime state |
| GET    | `/api/system/models/{name}/status` | Detailed status for specific model            |
| POST   | `/api/system/models/{name}/load`   | Proxy to enrichment service to load model     |
| POST   | `/api/system/models/{name}/unload` | Proxy to enrichment service to unload model   |
| POST   | `/api/system/models/{name}/reload` | Unload + load                                 |
| POST   | `/api/system/models/unload-all`    | Unload all models on both services            |
| GET    | `/api/system/models/vram-summary`  | Per-GPU VRAM breakdown                        |

### Response Schemas

#### GET /api/system/models

```json
{
  "models": [
    {
      "name": "threat-detection-yolov8n",
      "category": "detection",
      "estimated_vram_mb": 300,
      "enabled": true,
      "service": "ai-enrichment-light",
      "gpu_id": 1,
      "runtime": {
        "loaded": true,
        "actual_vram_mb": 287,
        "last_used": "2025-01-31T10:30:00Z",
        "load_count": 5
      }
    },
    {
      "name": "vehicle-segment-classification",
      "category": "classification",
      "estimated_vram_mb": 1500,
      "enabled": true,
      "service": "ai-enrichment",
      "gpu_id": 0,
      "runtime": {
        "loaded": false,
        "actual_vram_mb": null,
        "last_used": null,
        "load_count": 0
      }
    }
  ],
  "service_status": {
    "ai-enrichment": "healthy",
    "ai-enrichment-light": "healthy"
  }
}
```

#### GET /api/system/models/vram-summary

```json
{
  "gpus": [
    {
      "gpu_id": 0,
      "service": "ai-enrichment",
      "budget_mb": 6800,
      "used_mb": 2100,
      "available_mb": 4700,
      "utilization_percent": 30.9,
      "loaded_models": ["fashion-clip", "vehicle-segment-classification"]
    },
    {
      "gpu_id": 1,
      "service": "ai-enrichment-light",
      "budget_mb": 1200,
      "used_mb": 450,
      "available_mb": 750,
      "utilization_percent": 37.5,
      "loaded_models": ["threat-detection-yolov8n", "osnet-x0-25"]
    }
  ],
  "totals": {
    "budget_mb": 8000,
    "used_mb": 2550,
    "available_mb": 5450,
    "model_count": 4
  }
}
```

#### POST /api/system/models/{name}/load

```json
{
  "success": true,
  "model_name": "threat-detection-yolov8n",
  "service": "ai-enrichment-light",
  "gpu_id": 1,
  "load_time_ms": 1250,
  "vram_mb": 287
}
```

#### POST /api/system/models/{name}/unload

```json
{
  "success": true,
  "model_name": "threat-detection-yolov8n",
  "freed_vram_mb": 287
}
```

### New Enrichment Service Endpoint

Add to both `ai-enrichment:8094` and `ai-enrichment-light:8096`:

```
POST /models/{name}/unload
  - Unload specific model from GPU memory
  - Returns: { success, freed_vram_mb }
```

### Backend Implementation

#### New Files

| File                                      | Purpose                                               |
| ----------------------------------------- | ----------------------------------------------------- |
| `backend/api/routes/model_management.py`  | API route handlers                                    |
| `backend/api/schemas/model_management.py` | Pydantic request/response schemas                     |
| `backend/services/enrichment_client.py`   | HTTP client for enrichment services (extend existing) |

#### Implementation Steps

1. **Create Pydantic schemas** for request/response types
2. **Extend enrichment client** with model management methods
3. **Create route handlers** that:
   - Read static config from `get_model_zoo()` registry
   - Proxy runtime operations to enrichment services
   - Aggregate responses from both services
4. **Add service routing logic** to determine which enrichment service handles each model

#### Service Routing

```python
# Model to service mapping (in config or derived from model category)
HEAVY_MODELS = {"vehicle-segment-classification", "fashion-clip", "xclip-base", ...}
LIGHT_MODELS = {"threat-detection-yolov8n", "osnet-x0-25", "vitpose-small", ...}

def get_service_for_model(model_name: str) -> str:
    """Return enrichment service URL for a model."""
    if model_name in LIGHT_MODELS:
        return settings.ENRICHMENT_LIGHT_URL  # http://ai-enrichment-light:8096
    return settings.ENRICHMENT_URL  # http://ai-enrichment:8094
```

#### Example Route Handler

```python
@router.get("/models")
async def list_models(
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ModelListResponse:
    """List all models with registry metadata and runtime state."""
    # Get static config from registry
    registry = get_model_zoo()

    # Fetch runtime state from both enrichment services
    heavy_status = await _fetch_service_status(http_client, settings.ENRICHMENT_URL)
    light_status = await _fetch_service_status(http_client, settings.ENRICHMENT_LIGHT_URL)

    # Merge registry config with runtime state
    models = []
    for name, config in registry.items():
        runtime = _get_runtime_for_model(name, heavy_status, light_status)
        models.append(ModelStatus(
            name=name,
            category=config.category,
            estimated_vram_mb=config.vram_mb,
            enabled=config.enabled,
            service=get_service_for_model(name),
            gpu_id=0 if name in HEAVY_MODELS else 1,
            runtime=runtime,
        ))

    return ModelListResponse(models=models, service_status={...})
```

## Frontend Implementation

### AI Models Settings Enhancement

Add "Model Zoo" panel to existing AI Models settings tab with per-GPU sections:

```typescript
<ModelZooPanel>
  {/* Per-GPU VRAM bars */}
  <VRAMSection>
    <VRAMUsageBar gpu={0} label="GPU 0 (Heavy Models)" budget={6800} used={2100} />
    <VRAMUsageBar gpu={1} label="GPU 1 (Light Models)" budget={1200} used={450} />
  </VRAMSection>

  {/* Models grouped by GPU */}
  <GPUSection gpu={0} service="ai-enrichment">
    <ModelCard name="vehicle-segment-classification" category="classification" ... />
    <ModelCard name="fashion-clip" category="classification" ... />
  </GPUSection>

  <GPUSection gpu={1} service="ai-enrichment-light">
    <ModelCard name="threat-detection-yolov8n" category="detection" loaded={true} ... />
    <ModelCard name="osnet-x0-25" category="embedding" loaded={false} ... />
  </GPUSection>
</ModelZooPanel>
```

### New Files

| File                                                 | Purpose               |
| ---------------------------------------------------- | --------------------- |
| `frontend/src/components/settings/ModelZooPanel.tsx` | Main panel component  |
| `frontend/src/components/settings/ModelCard.tsx`     | Individual model card |
| `frontend/src/components/settings/VRAMUsageBar.tsx`  | VRAM progress bar     |
| `frontend/src/components/settings/GPUSection.tsx`    | GPU grouping section  |
| `frontend/src/hooks/useModelZoo.ts`                  | React Query hooks     |
| `frontend/src/services/modelZooApi.ts`               | API client functions  |

### New Components

1. **ModelZooPanel** - Main container with VRAM summary and model grid
2. **GPUSection** - Groups models by GPU with collapsible header
3. **ModelCard** - Individual model with:
   - Name, category badge, VRAM usage
   - Load/Unload button with loading state
   - Status indicator (loaded/unloaded/loading)
   - Last used timestamp (if loaded)
4. **VRAMUsageBar** - Per-GPU progress bar with color coding

### New Hooks

```typescript
// useModelZoo.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { modelZooApi } from '@/services/modelZooApi';

export function useModels() {
  return useQuery({
    queryKey: ['system', 'models'],
    queryFn: modelZooApi.listModels,
    refetchInterval: 5000, // Poll for status changes
  });
}

export function useVRAMSummary() {
  return useQuery({
    queryKey: ['system', 'models', 'vram-summary'],
    queryFn: modelZooApi.getVRAMSummary,
    refetchInterval: 5000,
  });
}

export function useLoadModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: modelZooApi.loadModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'models'] });
    },
  });
}

export function useUnloadModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: modelZooApi.unloadModel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'models'] });
    },
  });
}
```

### API Client

```typescript
// modelZooApi.ts
import { fetchApi } from './api';

export const modelZooApi = {
  listModels: () => fetchApi<ModelListResponse>('/api/system/models'),

  getVRAMSummary: () => fetchApi<VRAMSummaryResponse>('/api/system/models/vram-summary'),

  getModelStatus: (name: string) =>
    fetchApi<ModelStatusResponse>(`/api/system/models/${name}/status`),

  loadModel: (name: string) =>
    fetchApi<LoadModelResponse>(`/api/system/models/${name}/load`, { method: 'POST' }),

  unloadModel: (name: string) =>
    fetchApi<UnloadModelResponse>(`/api/system/models/${name}/unload`, { method: 'POST' }),

  reloadModel: (name: string) =>
    fetchApi<LoadModelResponse>(`/api/system/models/${name}/reload`, { method: 'POST' }),

  unloadAll: () => fetchApi<UnloadAllResponse>('/api/system/models/unload-all', { method: 'POST' }),
};
```

## UI Behavior

- **Load button** - Shows spinner during load, disabled if insufficient VRAM
- **Unload button** - Confirmation dialog ("Model will need to reload on next use")
- **VRAM bar** - Color coded (green <70%, yellow 70-90%, red >90%)
- **Auto-refresh** - Poll every 5 seconds for status changes

## Testing

- Unit tests for API routes
- Integration test for load/unload cycle
- Frontend component tests

## Rollout

1. Backend API endpoints (1 issue)
2. Frontend hooks and API client (1 issue)
3. UI components in AI Models settings (1 issue)

## Resolved Questions

| Question                            | Decision                                        |
| ----------------------------------- | ----------------------------------------------- |
| Should unload require confirmation? | Yes - dialog with warning                       |
| Should we show inference count?     | Nice to have, not MVP                           |
| Backend architecture?               | Hybrid: registry + proxy to enrichment services |
| Show GPU info in UI?                | Yes - models grouped by GPU                     |
| VRAM summary format?                | Per-GPU breakdown with utilization              |
| Use existing enrichment endpoints?  | Yes - proxy existing, add unload endpoint       |
