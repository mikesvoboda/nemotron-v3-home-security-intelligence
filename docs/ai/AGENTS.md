# AI Documentation - Agent Guide

## Purpose

This directory contains architecture and design documentation for the AI model zoo and inference pipeline. It provides comprehensive documentation for understanding, configuring, and extending the AI subsystem.

## Directory Contents

```
docs/ai/
├── AGENTS.md          # This file - navigation guide
└── model-zoo.md       # AI Model Zoo Architecture documentation
```

## Key Documents

### Model Zoo Architecture (`model-zoo.md`)

Comprehensive documentation covering:

- **Architecture Overview** - Detection pipeline and service topology
- **Always-Loaded Models** - YOLO26 (gateway Triton) and the `ai-vlm` reasoning engine
- **Lookup Models** - re-ID, threat, face, license-plate (identity lookups against your registrations)
- **VRAM Management** - On-demand loading with LRU eviction and priority-based ordering
- **API Reference** - Gateway routers and model management APIs
- **Environment Variables** - Configuration for all AI services
- **Adding New Models** - Step-by-step guide for extending the model zoo

> **Status:** since the R8 legacy retirement (2026-09-29) the compose stack
> boots two GPU AI services: `ai-gateway` (port 8090; Triton routers
> `/yolo26` and `/enrich-lt` only — `GATEWAY_MODEL_SET` resolves `vlm` and
> hard-raises otherwise) and `ai-vlm` (llama.cpp, port `AI_VLM_PORT` default
> 8098, compose profile `vlm`, model identity is config:
> `VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`). The per-model containers
> (`ai-yolo26`/`ai-florence`/`ai-clip`/`ai-enrichment`/`ai-enrichment-light`)
> and the legacy `ai-llm` Nemotron service no longer exist — their images,
> serve dirs and routers were deleted with R8 S1-S3. See
> [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md) for the gateway itself.

## Quick Links

| Topic                     | Location                                           |
| ------------------------- | -------------------------------------------------- |
| Model zoo architecture    | [model-zoo.md](model-zoo.md)                       |
| AI service implementation | [ai/AGENTS.md](../../ai/AGENTS.md)                 |
| AI gateway (current)      | [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md) |
| YOLO26 detection          | [ai/yolo26/AGENTS.md](../../ai/yolo26/AGENTS.md)   |
| VLM engine (shipped LLM)  | [ai/vlm/](../../ai/vlm/)                           |

> The Florence-2, CLIP, enrichment and Nemotron serving dirs this table used
> to link were deleted with R8 S1-S3 (2026-09-29); scene understanding moved
> to the `ai-vlm` engine.

## Common Tasks

### Understanding Model Capabilities

1. Read [model-zoo.md](model-zoo.md) for the complete model inventory
2. Each model section includes:
   - Model source (HuggingFace link)
   - VRAM requirements
   - Input/output formats
   - Trigger conditions

### Configuring VRAM Budget

See the "VRAM Management" section in [model-zoo.md](model-zoo.md):

- The backend model zoo evicts on-demand models by LRU under VRAM pressure;
  per-model footprints are the `vram_mb` rows in `models.yml`
- `backend/services/gpu_config_service.py` writes a `VRAM_BUDGET_GB` override
  into a service's environment when a GPU assignment sets one (the legacy
  `ai-enrichment` consumer of that variable retired with R8; the mechanism
  remains for GPU-assignment overrides)
- The VLM engine sizes itself via `VLM_GPU_LAYERS` (default `auto` = llama.cpp
  fits the card)

`ai-gateway` does not read `VRAM_BUDGET_GB`: Triton loads its models at
container start, so eviction ordering does not apply there.

### Adding New Models

`models.yml` is the single source of truth — see the Patterns section in
[ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md). For a backend model-zoo
(lookup) model, follow the "Adding New Models" guide in
[model-zoo.md](model-zoo.md):

1. Add the row to `models.yml` (size, `vram_mb`, phase, download method)
2. Implement the loader behind the model-zoo service
3. Add trigger conditions
4. (Optional) Add API endpoint
5. Update docker-compose volumes if the artifact needs a new mount
6. Update documentation

### Debugging Model Loading

Model status in a gateway deployment comes from the backend, not from an
enrichment port directly:

```bash
curl http://localhost:8000/api/system/models
curl http://localhost:8000/api/system/models/vram-summary
```

For the gateway itself, ask Triton which models it loaded:

```bash
curl http://localhost:8090/health
```

For the VLM engine, check the llama.cpp server logs:

```bash
podman logs ai-vlm 2>&1 | tail -30
```

## Related Documentation

- **Architecture Overview**: `docs/architecture/overview.md`
- **AI Pipeline API**: `docs/developer/api/ai-pipeline.md`
- **Deployment Guide**: `docs/operator/deployment/README.md`
- **Troubleshooting**: `docs/reference/troubleshooting/ai-issues.md`

## Entry Points

1. **Model zoo documentation**: [model-zoo.md](model-zoo.md) - Start here for AI architecture
2. **Implementation code**: [ai/AGENTS.md](../../ai/AGENTS.md) - For service implementation details
3. **Backend integration**: [backend/services/](../../backend/services/) - Client code for AI services
