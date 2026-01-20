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
- **Always-Loaded Models** - RT-DETRv2, Florence-2, CLIP, Nemotron
- **On-Demand Models** - Threat detection, pose estimation, demographics, clothing, vehicle, pet, re-ID, depth, action recognition
- **VRAM Management** - On-demand loading with LRU eviction and priority-based ordering
- **API Reference** - Unified enrichment endpoint and model management APIs
- **Environment Variables** - Configuration for all AI services
- **Adding New Models** - Step-by-step guide for extending the model zoo

## Quick Links

| Topic                      | Location                                                 |
| -------------------------- | -------------------------------------------------------- |
| Model zoo architecture     | [model-zoo.md](model-zoo.md)                             |
| AI service implementation  | [ai/AGENTS.md](../../ai/AGENTS.md)                       |
| RT-DETRv2 detection        | [ai/rtdetr/AGENTS.md](../../ai/rtdetr/AGENTS.md)         |
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

- Default budget: 6.8GB for on-demand models
- Configure via `VRAM_BUDGET_GB` environment variable
- Priority system controls eviction order

### Adding New Models

Follow the "Adding New Models" guide in [model-zoo.md](model-zoo.md):

1. Create model wrapper in `ai/enrichment/models/`
2. Register in `model_registry.py`
3. Add trigger conditions
4. (Optional) Add API endpoint
5. Update docker-compose volumes
6. Update documentation

### Debugging Model Loading

Check model status via API:

```bash
curl http://localhost:8094/models/status
```

Review logs for loading/eviction events:

```bash
docker logs ai-enrichment 2>&1 | grep -E "(Loading|Evicting|Unloaded)"
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
