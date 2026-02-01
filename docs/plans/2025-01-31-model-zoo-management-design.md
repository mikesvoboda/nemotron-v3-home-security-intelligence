# Model Zoo Management API Design

**Date:** 2025-01-31
**Status:** Draft
**Priority:** HIGH
**Complexity:** Lightweight

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

## API Design

### New Endpoints

```
GET /api/system/models
  - List all available models with load status
  - Returns: { models: [{ name, loaded, vram_mb, load_time_ms }] }

GET /api/system/models/{model}/status
  - Get detailed status for specific model
  - Returns: { name, loaded, vram_mb, last_used, inference_count }

POST /api/system/models/{model}/load
  - Load model into GPU memory
  - Returns: { success, load_time_ms, vram_mb }

POST /api/system/models/{model}/unload
  - Unload model from GPU memory
  - Returns: { success, freed_vram_mb }

POST /api/system/models/{model}/reload
  - Reload model (unload + load)
  - Returns: { success, load_time_ms }

POST /api/system/models/unload-all
  - Unload all models (emergency/maintenance)
  - Returns: { success, freed_vram_mb, unloaded_count }

GET /api/system/models/vram-summary
  - Get VRAM usage summary
  - Returns: { total_vram_mb, used_vram_mb, available_vram_mb, per_model: {...} }
```

### Backend Implementation

1. Create `backend/api/routes/model_management.py`
2. Wrap `ModelZoo` service methods
3. Add proper error handling for load failures

```python
@router.post("/models/{model_name}/load")
async def load_model(
    model_name: str,
    model_zoo: ModelZoo = Depends(get_model_zoo)
):
    try:
        async for progress in model_zoo.load(model_name):
            pass  # Could emit WebSocket progress
        return {"success": True, "vram_mb": model_zoo.get_model_vram(model_name)}
    except Exception as e:
        raise HTTPException(400, str(e))
```

## Frontend Implementation

### AI Models Settings Enhancement

Add "Model Status" panel to existing AI Models settings tab:

```typescript
// Components
<ModelStatusPanel>
  <ModelCard name="yolo26" loaded={true} vram={2048} onUnload={...} />
  <ModelCard name="nemotron" loaded={true} vram={8192} onUnload={...} />
  <ModelCard name="clip" loaded={false} vram={0} onLoad={...} />
</ModelStatusPanel>

<VRAMUsageBar total={24576} used={10240} />
```

### New Components

1. `ModelStatusPanel` - Grid of model cards
2. `ModelCard` - Individual model with load/unload button
3. `VRAMUsageBar` - Visual VRAM usage indicator

### New Hooks

```typescript
// useModelZoo.ts
export function useModels() {
  return useQuery({
    queryKey: ['system-models'],
    queryFn: () => fetchApi('/api/system/models'),
    refetchInterval: 5000, // Poll for status changes
  });
}

export function useLoadModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (model: string) => fetchApi(`/api/system/models/${model}/load`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries(['system-models']),
  });
}

export function useUnloadModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (model: string) =>
      fetchApi(`/api/system/models/${model}/unload`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries(['system-models']),
  });
}
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

## Open Questions

1. Should unload require confirmation? **Yes - dialog with warning**
2. Should we show inference count? **Nice to have, not MVP**
