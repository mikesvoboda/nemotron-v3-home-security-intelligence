# AI Documentation - Agent Guide

## Purpose

This directory contains architecture and design documentation for the AI model
zoo and the inference pipeline. It is the reading list for understanding,
configuring, and extending the AI subsystem.

## Directory Contents

```
docs/ai/
├── AGENTS.md          # This file - navigation guide
└── model-zoo.md       # AI Model Zoo Architecture documentation
```

## Key Documents

### Model Zoo Architecture (`model-zoo.md`)

The inventory of everything the system serves, in present tense:

- **Overview** - the two AI services, `ai-gateway` and `ai-vlm`, plus the
  in-process lookup legs that are not services
- **How The Backend Reaches Each Model** - `AI_GATEWAY_URL`, `YOLO26_URL`,
  `ENRICHMENT_LIGHT_URL` and `AI_VLM_URL`, with their compose values
- **Model Details** - YOLO26 on the gateway, the `ai-vlm` llama.cpp engine, and
  the three lookup legs (faces, plates, person re-ID)
- **The Triton Model Repository** - which directories Triton scans and how
  residency is pruned
- **Backend Model Registry** - the `models.yml` rows and what provisioning and
  the boot sweep read from them
- **VRAM Management** - residency on the gateway, load-with-no-eviction in the
  backend, self-sizing on the VLM
- **Adding New Models** - the procedure per surface
- **Environment Variables** - the shipped default of every AI knob

`ai-vlm` is the system's only LLM service. For the gateway's own implementation
detail see [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md).

## Quick Links

| Topic                     | Location                                            |
| ------------------------- | --------------------------------------------------- |
| Model zoo architecture    | [model-zoo.md](model-zoo.md)                        |
| AI service implementation | [ai/AGENTS.md](../../ai/AGENTS.md)                  |
| AI gateway                | [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md)  |
| YOLO26 detection          | [ai/AGENTS.md](../../ai/AGENTS.md) (YOLO26 section) |
| VLM engine                | [ai/vlm/](../../ai/vlm/)                            |

## Common Tasks

### Understanding Model Capabilities

1. For what the shipped stack runs and what it costs, read `model-zoo.md` —
   the `models.yml` table and the Triton repository table answer most questions
   in one screen
2. For the measured end-to-end path, read
   [docs/architecture/ai-pipeline-current-state.md](../architecture/ai-pipeline-current-state.md)
3. For the per-model reference, read
   [docs/reference/models.md](../reference/models.md)

### Configuring VRAM Budget

- The backend `ModelManager` (`backend/services/model_zoo.py`) loads a row
  through `manager.load("...")`, reference-counted, and loads the
  `enabled: true` **and** `preload: true` rows at boot — three today,
  `osnet-ain-x1-0`, `face-detector-scrfd` and `face-recognizer`. The whole boot
  sweep is gated on `BACKEND_MODEL_PRELOAD`, which ships `false`; `setup.py`
  turns it on where detected VRAM is ≥ 24 GB. **There is no eviction pass**, so
  a loaded row stays resident and the `never_evict` / `priority` fields in
  `models.yml` are parsed and consulted by nothing. Per-model footprints are the
  `vram_mb` rows in `models.yml`
- Because those two legs are residency-gated, a host with
  `BACKEND_MODEL_PRELOAD=false` reports `unavailable: specialist did not run`
  for faces and person re-ID on every event. Nothing fails; the degradation is
  honest. `hsi_specialist_unavailable_total` is the metric that answers "has
  this ever run"
- `backend/services/gpu_config_service.py` writes a `VRAM_BUDGET_GB` override
  into a service's environment when a GPU assignment declares one
- The VLM engine sizes itself: `VLM_GPU_LAYERS` (default `auto`) lets llama.cpp
  fit the card

`ai-gateway` does not read `VRAM_BUDGET_GB`: Triton loads its models at
container start with `--model-control-mode=none`, so they are resident and
there is nothing to evict. The HTTP
`POST /api/system/models/{name}/load|unload` endpoints therefore return **501**
by design (`backend/api/routes/model_management.py`).

### Adding New Models

`models.yml` is the single source of truth — see the Patterns section in
[ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md). [model-zoo.md](model-zoo.md)
carries the full procedure for each surface — a backend model-zoo (lookup)
model and a Triton model on the gateway. The lookup shape is: add the row,
implement the loader in `backend/services/`, and give it an `unavailable` path
with a reason code rather than an empty result.

### Debugging Model Loading

Model status comes from the backend:

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

A `200` from `ai-vlm`'s `/health` does not prove the engine can see: a serve
started without its `VLM_MMPROJ_PATH` projector answers health and reads every
still as text.

## Related Documentation

- **Architecture Overview**: `docs/architecture/overview.md`
- **AI Pipeline API**: `docs/developer/api/ai-pipeline.md`
- **Deployment Guide**: `docs/operator/deployment/README.md`
- **Troubleshooting**: `docs/reference/troubleshooting/ai-issues.md`

## Entry Points

1. **Model zoo documentation**: [model-zoo.md](model-zoo.md) - Start here for AI architecture
2. **Implementation code**: [ai/AGENTS.md](../../ai/AGENTS.md) - For service implementation details
3. **Backend integration**: [backend/services/](../../backend/services/) - Client code for AI services
