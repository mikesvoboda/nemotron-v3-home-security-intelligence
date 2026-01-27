# Multi-GPU Support Design

**Date:** 2025-01-23
**Status:** Approved
**Author:** Claude (with Mike Svoboda)

## Overview

Enable multi-GPU support for AI services, allowing users to pin specific models to different GPUs. This improves performance, capacity, isolation, and future-proofs the system for larger model deployments.

## Goals

1. **Performance** - Run more models concurrently to reduce latency
2. **Capacity** - Utilize all available VRAM across GPUs
3. **Isolation** - Keep the LLM stable by separating it from smaller models
4. **Future-proofing** - Prepare for adding more/larger models later
5. **Generalization** - Support any multi-GPU configuration, not just the reference hardware

## Reference Hardware

| GPU   | Model     | VRAM  | Power | Best For            |
| ----- | --------- | ----- | ----- | ------------------- |
| GPU 0 | RTX A5500 | 24 GB | 230W  | Large models (LLM)  |
| GPU 1 | RTX A400  | 4 GB  | 50W   | Small/medium models |

## Design Decisions

| Decision               | Choice                                                 | Rationale                                       |
| ---------------------- | ------------------------------------------------------ | ----------------------------------------------- |
| Configuration approach | Hybrid (auto + manual)                                 | Sensible defaults with user override capability |
| Configuration location | UI settings panel                                      | User-friendly, no CLI required                  |
| Assignment strategies  | 5 options (manual, VRAM, latency, isolation, balanced) | Different users have different priorities       |
| When changes apply     | Container restart via UI                               | Reliable, atomic, user-controlled               |
| Storage                | Database + config file                                 | DB for runtime, file for inspection/recovery    |
| Validation             | Warn but allow                                         | Informative, not restrictive                    |
| Runtime errors         | Fallback to available GPU                              | Graceful degradation                            |

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         UI: GPU Configuration                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ ai-llm: GPU 0   │  │ ai-yolo26: 0  │  │ ai-enrichment: GPU 1   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
│                                                                         │
│  ⚠️ Warning: ai-enrichment VRAM budget (6.8GB) exceeds GPU 1 (4GB)     │
│                                                                         │
│                    [ Save ]  [ Apply & Restart Services ]               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Backend: GPU Config Service                        │
│                                                                         │
│  1. Save assignments to PostgreSQL                                      │
│  2. Generate docker-compose.gpu-override.yml                            │
│  3. Call podman-compose to recreate affected containers                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              docker-compose.gpu-override.yml (generated)                │
│                                                                         │
│  services:                                                              │
│    ai-llm:                                                              │
│      deploy:                                                            │
│        resources:                                                       │
│          reservations:                                                  │
│            devices:                                                     │
│              - driver: nvidia                                           │
│                device_ids: ['0']  # RTX A5500                           │
│                capabilities: [gpu]                                      │
│    ai-enrichment:                                                       │
│      deploy:                                                            │
│        resources:                                                       │
│          reservations:                                                  │
│            devices:                                                     │
│              - driver: nvidia                                           │
│                device_ids: ['1']  # RTX A400                            │
│                capabilities: [gpu]                                      │
│      environment:                                                       │
│        - VRAM_BUDGET_GB=3.5  # Auto-adjusted for smaller GPU            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Database Schema

### New Tables

```sql
CREATE TABLE gpu_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_name VARCHAR(64) NOT NULL UNIQUE,  -- 'ai-llm', 'ai-yolo26', etc.
    gpu_index INTEGER,                          -- NULL = auto-assign
    strategy VARCHAR(32) DEFAULT 'manual',      -- 'manual', 'vram_based', 'latency_optimized', 'isolation_first', 'balanced'
    vram_budget_override FLOAT,                 -- Override VRAM budget (for enrichment)
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE gpu_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gpu_index INTEGER NOT NULL UNIQUE,
    name VARCHAR(128),                          -- 'NVIDIA RTX A5500'
    vram_total_mb INTEGER,
    vram_available_mb INTEGER,
    compute_capability VARCHAR(16),             -- '8.6'
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE system_settings (
    key VARCHAR(64) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Example: key='gpu_assignment_strategy', value='{"default": "vram_based"}'
```

### Config File (synced from DB)

```yaml
# config/gpu-assignments.yml (auto-generated, do not edit manually)
generated_at: '2025-01-23T10:30:00Z'
strategy: vram_based
assignments:
  ai-llm: { gpu: 0, vram_budget: null }
  ai-yolo26: { gpu: 0, vram_budget: null }
  ai-enrichment: { gpu: 1, vram_budget: 3.5 }
```

## API Endpoints

| Method | Endpoint                         | Purpose                                                |
| ------ | -------------------------------- | ------------------------------------------------------ |
| GET    | `/api/system/gpus`               | Returns detected GPUs with current utilization         |
| GET    | `/api/system/gpu-config`         | Returns current GPU assignments + available strategies |
| PUT    | `/api/system/gpu-config`         | Updates assignments (saves to DB, syncs to YAML)       |
| POST   | `/api/system/gpu-config/apply`   | Applies config and restarts affected services          |
| GET    | `/api/system/gpu-config/status`  | Returns restart progress / container health            |
| POST   | `/api/system/gpu-config/detect`  | Re-scans GPUs (updates gpu_devices table)              |
| GET    | `/api/system/gpu-config/preview` | Preview auto-assignment for a given strategy           |

### Request/Response Examples

**GET /api/system/gpus**

```json
{
  "gpus": [
    {
      "index": 0,
      "name": "RTX A5500",
      "vram_total_mb": 24564,
      "vram_used_mb": 19304,
      "compute_capability": "8.6"
    },
    {
      "index": 1,
      "name": "RTX A400",
      "vram_total_mb": 4094,
      "vram_used_mb": 329,
      "compute_capability": "8.6"
    }
  ]
}
```

**PUT /api/system/gpu-config**

```json
{
  "strategy": "manual",
  "assignments": [
    { "service": "ai-llm", "gpu_index": 0 },
    { "service": "ai-yolo26", "gpu_index": 0 },
    { "service": "ai-enrichment", "gpu_index": 1, "vram_budget_override": 3.5 }
  ]
}
```

**Response:**

```json
{
  "success": true,
  "warnings": ["ai-enrichment VRAM budget (6.8 GB) exceeds GPU 1 (4 GB). Auto-adjusted to 3.5 GB."]
}
```

## Container Orchestration

### Override File Generation

```python
def generate_override_file(assignments: list[GpuAssignment]) -> str:
    """Generate docker-compose.gpu-override.yml content."""
    services = {}
    for assignment in assignments:
        service_config = {
            "deploy": {
                "resources": {
                    "reservations": {
                        "devices": [{
                            "driver": "nvidia",
                            "device_ids": [str(assignment.gpu_index)],
                            "capabilities": ["gpu"]
                        }]
                    }
                }
            }
        }
        if assignment.vram_budget_override:
            service_config["environment"] = [
                f"VRAM_BUDGET_GB={assignment.vram_budget_override}"
            ]
        services[assignment.service_name] = service_config

    return yaml.dump({"services": services})
```

### Container Restart Flow

```python
async def apply_gpu_config(self, assignments: list[GpuAssignment]) -> ApplyResult:
    # 1. Write override file
    override_path = Path("config/docker-compose.gpu-override.yml")
    override_path.write_text(generate_override_file(assignments))

    # 2. Determine which services changed
    changed = self._diff_assignments(current=self._get_current(), new=assignments)

    # 3. Recreate changed containers via subprocess
    for service in changed:
        await self._recreate_service(service)

    return ApplyResult(restarted=changed, success=True)

async def _recreate_service(self, service_name: str):
    """Recreate a single service with the new GPU config."""
    cmd = [
        "podman-compose",
        "-f", "docker-compose.prod.yml",
        "-f", "config/docker-compose.gpu-override.yml",
        "up", "-d", "--force-recreate", "--no-deps",
        service_name
    ]
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
```

## Frontend UI

### Component Structure

```
src/components/settings/
├── GpuSettings.tsx           # Main container
├── GpuDeviceCard.tsx         # Shows each GPU with stats
├── GpuAssignmentTable.tsx    # Service → GPU mapping table
├── GpuStrategySelector.tsx   # Strategy dropdown with descriptions
└── GpuApplyButton.tsx        # Apply & Restart with status
```

### UI Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Settings > GPU Configuration                                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Detected GPUs ─────────────────────────────────────────────────┐   │
│  │  GPU 0: RTX A5500    24 GB   ████████████░░░░ 19.3/24 GB used   │   │
│  │  GPU 1: RTX A400      4 GB   ██░░░░░░░░░░░░░░  0.3/4 GB used    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Assignment Strategy: [ VRAM-based (Recommended) ▼ ]                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ○ Manual         - You control each assignment                   │  │
│  │ ● VRAM-based     - Largest models on largest GPU                 │  │
│  │ ○ Latency-opt.   - Critical path models on fastest GPU           │  │
│  │ ○ Isolation      - LLM gets dedicated GPU                        │  │
│  │ ○ Balanced       - Distribute VRAM evenly                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Service Assignments ───────────────────────────────────────────┐   │
│  │  Service          Model              VRAM Est.   GPU            │   │
│  │  ────────────────────────────────────────────────────────────── │   │
│  │  ai-llm           Nemotron-30B       ~21.7 GB    [ GPU 0 ▼ ]    │   │
│  │  ai-yolo26      YOLO26          ~650 MB     [ GPU 0 ▼ ]    │   │
│  │  ai-florence      Florence-2-L       ~1.5 GB     [ GPU 0 ▼ ]    │   │
│  │  ai-clip          CLIP ViT-L         ~1.2 GB     [ GPU 0 ▼ ]    │   │
│  │  ai-enrichment    Model Zoo          ~6.8 GB     [ GPU 1 ▼ ]    │   │
│  │                   └─ VRAM Budget: [ 3.5 ] GB  ⚠️ Adjusted       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ⚠️ Warning: ai-enrichment budget (6.8 GB) exceeds GPU 1 (4 GB).       │
│     Budget auto-adjusted to 3.5 GB. Some models may not load.          │
│                                                                         │
│  [ Preview Changes ]  [ Save ]  [ Apply & Restart Services ]           │
│                                                                         │
│  Status: ● All services running                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Assignment Strategies

| Strategy              | Description                   | Algorithm                                                     |
| --------------------- | ----------------------------- | ------------------------------------------------------------- |
| **Manual**            | User controls each assignment | No auto-assignment                                            |
| **VRAM-based**        | Largest models on largest GPU | Sort models by VRAM desc, assign to GPU with most free space  |
| **Latency-optimized** | Critical path on fastest GPU  | ai-yolo26 + ai-llm on GPU 0, others distributed               |
| **Isolation-first**   | LLM gets dedicated GPU        | ai-llm alone on largest GPU, everything else shares remaining |
| **Balanced**          | Distribute VRAM evenly        | Bin-packing to minimize VRAM variance across GPUs             |

## Error Handling

### Validation Warnings (Non-blocking)

| Condition                          | Warning Message                                        |
| ---------------------------------- | ------------------------------------------------------ |
| VRAM exceeds GPU capacity          | "ai-enrichment budget (6.8 GB) exceeds GPU 1 (4 GB)"   |
| Multiple large models on small GPU | "Combined VRAM (~23 GB) exceeds GPU 1 capacity (4 GB)" |
| LLM on small GPU                   | "Nemotron-30B requires ~21.7 GB, GPU 1 only has 4 GB"  |

### Runtime Fallbacks

```python
def get_target_gpu() -> int:
    """Get assigned GPU, fall back to any available if assignment fails."""
    assigned = os.environ.get("CUDA_VISIBLE_DEVICES")
    if assigned:
        try:
            torch.cuda.set_device(int(assigned))
            return int(assigned)
        except RuntimeError as e:
            logger.warning(f"Assigned GPU {assigned} unavailable: {e}, falling back")

    if torch.cuda.is_available():
        return 0
    raise RuntimeError("No GPU available")
```

### Edge Cases

| Scenario                     | Behavior                                          |
| ---------------------------- | ------------------------------------------------- |
| GPU removed/failed           | Service falls back to available GPU, logs warning |
| User assigns same GPU to all | Allowed (current behavior)                        |
| No GPUs detected             | UI shows "No GPUs detected", disables controls    |
| Container restart fails      | UI shows error, rollback option offered           |
| Config file write fails      | API returns 500, DB transaction rolled back       |
| Podman API unavailable       | Graceful error message in UI                      |

## Implementation Phases

### Phase 1: Backend Foundation

- Add `gpu_configurations` and `gpu_devices` tables + Alembic migration
- Create `GpuConfigService` with GPU detection via `pynvml` or `nvidia-smi`
- Implement API endpoints: `GET /gpus`, `GET/PUT /gpu-config`
- Add model VRAM estimates to existing model registry

### Phase 2: Override File Generation

- Implement `generate_override_file()` for docker-compose override
- Add config file sync on save (`config/docker-compose.gpu-override.yml`)
- Add `config/gpu-assignments.yml` generation for human inspection
- Unit tests for YAML generation

### Phase 3: Container Orchestration

- Implement `apply_gpu_config()` with `podman-compose` subprocess
- Add restart status tracking and polling endpoint
- Add rollback capability (restore previous override file)
- Integration tests with container mocking

### Phase 4: Frontend UI

- GPU device cards with real-time VRAM display
- Strategy selector with descriptions
- Assignment table with dropdowns
- Warning display for VRAM overages
- Apply & Restart button with progress indicator

### Phase 5: Polish & Documentation

- Auto-adjustment of VRAM budget when assigning to smaller GPU
- "Preview Changes" diff view
- Update CLAUDE.md and docs with multi-GPU setup instructions
- Add GPU config to system backup/restore

## File Changes Summary

| Area     | New/Modified Files                                   |
| -------- | ---------------------------------------------------- |
| Database | `alembic/versions/xxx_add_gpu_config.py`             |
| Models   | `backend/models/gpu_config.py`                       |
| Services | `backend/services/gpu_config_service.py`             |
| API      | `backend/api/routes/gpu_config.py`                   |
| Frontend | `frontend/src/components/settings/Gpu*.tsx`          |
| Frontend | `frontend/src/services/gpuConfigApi.ts`              |
| Config   | `config/docker-compose.gpu-override.yml` (generated) |
| Docs     | `docs/development/multi-gpu.md`                      |

## Model VRAM Estimates

| Service       | Model                        | VRAM Estimate  |
| ------------- | ---------------------------- | -------------- |
| ai-llm        | Nemotron-3-Nano-30B (Q4_K_M) | ~21.7 GB       |
| ai-yolo26     | YOLO26                       | ~650 MB        |
| ai-florence   | Florence-2-Large             | ~1.5 GB        |
| ai-clip       | CLIP ViT-L                   | ~1.2 GB        |
| ai-enrichment | Model Zoo (9 models)         | ~6.8 GB budget |

## Usage Example

After implementation, users with multiple GPUs would:

1. Navigate to **Settings > GPU Configuration**
2. See detected GPUs with current utilization
3. Either select an auto-assignment strategy or manually assign services
4. Review warnings if VRAM allocations exceed capacity
5. Click **Apply & Restart Services**
6. Monitor restart progress in the UI
7. Verify services are healthy on their assigned GPUs

## Future Considerations

- Support for AMD GPUs (ROCm) - would require separate detection path
- Multi-node GPU support (distributed across machines)
- Dynamic model migration between GPUs without restart
- GPU memory fragmentation monitoring
- Automatic strategy recommendation based on workload patterns
