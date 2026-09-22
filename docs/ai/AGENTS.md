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
- **Always-Loaded Models** - YOLO26, Florence-2, CLIP, Nemotron
- **On-Demand Models** - Threat detection, pose estimation, demographics, clothing, vehicle, pet, re-ID, depth, action recognition
- **VRAM Management** - On-demand loading with LRU eviction and priority-based ordering
- **API Reference** - Unified enrichment endpoint and model management APIs
- **Environment Variables** - Configuration for all AI services
- **Adding New Models** - Step-by-step guide for extending the model zoo

> **Status:** `model-zoo.md` covers both runtimes: `ai-gateway` (port 8090,
> the only AI service in `docker-compose.prod.yml`) is production; the
> per-model containers (`ai-yolo26`/`ai-florence`/`ai-clip`/`ai-enrichment`/
> `ai-enrichment-light`, legacy ports 8095/8092/8093/8094/8096) are legacy —
> their images are still built but they are not compose services. See
> [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md) for the gateway itself.

## Quick Links

| Topic                      | Location                                                 |
| -------------------------- | -------------------------------------------------------- |
| Model zoo architecture     | [model-zoo.md](model-zoo.md)                             |
| AI service implementation  | [ai/AGENTS.md](../../ai/AGENTS.md)                       |
| AI gateway (current)       | [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md)       |
| YOLO26 detection           | [ai/yolo26/AGENTS.md](../../ai/yolo26/AGENTS.md)         |
| Florence-2 vision-language | [ai/florence/AGENTS.md](../../ai/florence/AGENTS.md)     |
| CLIP embeddings            | [ai/clip/AGENTS.md](../../ai/clip/AGENTS.md)             |
| Enrichment service         | [ai/enrichment/AGENTS.md](../../ai/enrichment/AGENTS.md) |
| Nemotron LLM               | [ai/nemotron/AGENTS.md](../../ai/nemotron/AGENTS.md)     |

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

- Default budget: 6.8GB for on-demand models, from `VRAM_BUDGET_GB` in
  `ai/enrichment/model.py`
- `backend/services/gpu_config_service.py` writes a `VRAM_BUDGET_GB` override
  into a service's environment when a GPU assignment sets one
- Priority system controls eviction order in the legacy enrichment container

`ai-gateway` does not read `VRAM_BUDGET_GB`: Triton loads its models at
container start, so eviction ordering does not apply there.

### Adding New Models

For the gateway, `models.yml` is the single source of truth — see the
Patterns section in [ai/gateway/AGENTS.md](../../ai/gateway/AGENTS.md). For the
legacy enrichment container, follow the "Adding New Models" guide in
[model-zoo.md](model-zoo.md):

1. Create model wrapper in `ai/enrichment/models/`
2. Register in `ai/enrichment/model_registry.py`
3. Add trigger conditions
4. (Optional) Add API endpoint
5. Update docker-compose volumes
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

For the legacy enrichment container, model loading/eviction events are in its
logs:

```bash
podman logs ai-enrichment 2>&1 | grep -E "(Loading|Evicting|Unloaded)"
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
