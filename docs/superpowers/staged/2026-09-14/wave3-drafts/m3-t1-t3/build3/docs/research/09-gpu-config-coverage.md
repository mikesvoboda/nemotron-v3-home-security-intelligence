# GPU Configuration Coverage Analysis

## Executive Summary

GPU configuration feature is **~80% complete**. Core functionality (detection, configuration, strategy selection, preview) is fully implemented. Main gaps are **real container restart** (simulated), **VRAM budget override input**, and advanced features.

## Backend Endpoints

| Method | Endpoint                          | Description               | UI Status      |
| ------ | --------------------------------- | ------------------------- | -------------- |
| GET    | `/api/system/gpus`                | List detected GPUs        | ✅             |
| GET    | `/api/system/gpu-config`          | Get current configuration | ✅             |
| PUT    | `/api/system/gpu-config`          | Update assignments (save) | ✅             |
| POST   | `/api/system/gpu-config/apply`    | Apply and restart         | ✅ (simulated) |
| GET    | `/api/system/gpu-config/status`   | Apply progress            | ✅             |
| POST   | `/api/system/gpu-config/detect`   | Re-scan GPUs              | ✅             |
| GET    | `/api/system/gpu-config/preview`  | Preview strategy          | ✅             |
| GET    | `/api/system/ai-services`         | List AI services          | ✅             |
| GET    | `/api/system/gpu-config/services` | Service health            | ✅             |

## Backend Service Capabilities

### GpuConfigService (`backend/services/gpu_config_service.py`)

| Method                        | Purpose                   | Exposed       |
| ----------------------------- | ------------------------- | ------------- |
| `apply_gpu_config()`          | Full config orchestration | ✅            |
| `write_config_files()`        | Generate override files   | ✅ (internal) |
| `generate_override_content()` | Docker-compose YAML       | ✅ (internal) |
| `get_container_status()`      | Query Docker status       | ⚠️ Not used   |
| `get_operation_status()`      | Poll apply progress       | ✅            |
| `_diff_assignments()`         | Find changed services     | ✅ (internal) |
| `_recreate_service()`         | Restart service           | ⚠️ Simulated  |
| `_get_compose_command()`      | Detect compose tool       | ✅ (internal) |

### Assignment Strategies (5 total)

| Strategy          | Description          | UI Status |
| ----------------- | -------------------- | --------- |
| MANUAL            | User controls all    | ✅        |
| VRAM_BASED        | Largest to most VRAM | ✅        |
| LATENCY_OPTIMIZED | Critical on fastest  | ✅        |
| ISOLATION_FIRST   | LLM on dedicated GPU | ✅        |
| BALANCED          | Even distribution    | ✅        |

## Frontend Implementation

### Main Page: GpuSettingsPage

**Features:**

- Detected GPUs display
- Strategy selector with descriptions
- Assignment table
- Apply button with progress
- Empty state for no GPUs

### Components

| Component           | Purpose                         | Status |
| ------------------- | ------------------------------- | ------ |
| GpuDeviceCard       | GPU specs and assigned services | ✅     |
| GpuStrategySelector | Strategy selection with preview | ✅     |
| GpuAssignmentTable  | Service-to-GPU mapping          | ✅     |
| GpuApplyButton      | Save and apply actions          | ✅     |

### Hooks

| Hook               | Purpose                   | Status |
| ------------------ | ------------------------- | ------ |
| useGpus            | Fetch detected GPUs       | ✅     |
| useGpuConfig       | Fetch configuration       | ✅     |
| useGpuStatus       | Poll apply status         | ✅     |
| useServiceHealth   | Service health + GPU info | ✅     |
| useUpdateGpuConfig | Save configuration        | ✅     |
| useApplyGpuConfig  | Apply and restart         | ✅     |
| useDetectGpus      | Re-scan GPUs              | ✅     |
| usePreviewStrategy | Preview assignment        | ✅     |
| useAiServices      | List AI services          | ✅     |

## Backend Features NOT in UI

### 1. VRAM Budget Override (HIGH)

**Backend:** Per-service VRAM budget override supported
**Frontend:** `onVramOverrideChange` callback exists but input field NOT implemented

**Gap:** Users cannot override VRAM budgets from UI

### 2. Real Container Restart (HIGH)

**Backend:** `_recreate_service()` with full podman-compose logic
**Frontend:** `/apply` endpoint currently SIMULATES restarts (NEM-3548)

**Gap:** Actual container restart disabled for MVP safety

### 3. Service Enable/Disable (MEDIUM)

**Backend:** `GpuConfiguration.enabled` boolean field
**Frontend:** Not exposed

**Gap:** Cannot disable specific services from assignment

### 4. Direct Docker Status (MEDIUM)

**Backend:** `get_container_status()` can query real Docker
**Frontend:** Only shows simulated status from apply state

**Gap:** No real container health in UI

### 5. AI Service Metadata (LOW)

**Backend:** `AI_SERVICE_METADATA` with display names
**Frontend:** Currently hardcoded

**Gap:** Not configurable

### 6. Strategy Persistence (LOW)

**Backend:** Stores strategy in `system_settings` table
**Frontend:** Shows strategy but no "default strategy" setting

## UX Improvements Needed

### High Priority

1. **VRAM Budget Override Input**

   - Add input in GpuAssignmentTable
   - Show suggested values for overages
   - Display in GB with validation

2. **VRAM Utilization Dashboard**

   - Bar chart per GPU
   - Total vs allocated vs used
   - Color coding (green <70%, yellow 70-90%, red >90%)

3. **Real Container Status**
   - Query actual Docker status
   - Show logs for failures
   - Display uptime/restart history

### Medium Priority

4. **Strategy Comparison View**

   - Side-by-side comparison
   - VRAM utilization per strategy
   - Recommendation engine

5. **Batch GPU Operations**

   - Assign all to single GPU
   - Reset to defaults
   - Auto-balance

6. **GPU Affinity Constraints**
   - Services that can't share GPU
   - Priority weighting

### Low Priority

7. **Detailed Apply Progress**

   - Step-by-step visualization
   - Per-service status
   - Estimated time remaining
   - Rollback option

8. **Configuration Version History**

   - Previous configurations
   - Diff between versions
   - Quick rollback

9. **Export/Import**
   - Export as YAML
   - Import previous configs

## Implementation Gaps

### 1. Real Service Restart (NEM-3548)

**Current:** Simulates with immediate completion
**Needed:** Enable `GpuConfigService.apply_gpu_config()` call

```python
# Currently in route:
# Simulated restart
return {"status": "completed", "message": "Simulated restart"}

# Needed:
result = await config_service.apply_gpu_config(assignments)
```

### 2. VRAM Budget Override UI

**Current:** Callback exists, no input
**Needed:** Add input field to GpuAssignmentTable

```typescript
// In GpuAssignmentTable:
<Input
  type="number"
  value={service.vram_override_gb}
  onChange={(e) => onVramOverrideChange(service.id, parseFloat(e.target.value))}
/>
```

### 3. Docker Client Integration

**Current:** Mocked status
**Needed:** Initialize with real Docker client

```python
# In dependency injection:
config_service = GpuConfigService(
    db=session,
    docker_client=docker.from_env()  # Currently None
)
```

## Files Reference

| Component         | Location                                    |
| ----------------- | ------------------------------------------- |
| API Routes        | `backend/api/routes/gpu_config.py`          |
| Service           | `backend/services/gpu_config_service.py`    |
| Detection Service | `backend/services/gpu_detection_service.py` |
| Models            | `backend/models/gpu_config.py`              |
| Frontend Page     | `frontend/src/pages/GpuSettingsPage.tsx`    |
| Frontend Hooks    | `frontend/src/hooks/useGpuConfig.ts`        |
| API Client        | `frontend/src/services/gpuConfigApi.ts`     |
