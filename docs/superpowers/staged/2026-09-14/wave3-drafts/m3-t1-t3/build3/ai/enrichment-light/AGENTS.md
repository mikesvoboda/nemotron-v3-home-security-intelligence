# Enrichment Light Service

Lightweight enrichment service running on port 8096 (ENRICHMENT_LIGHT_PORT).

## Purpose

Provides lightweight model inference for pose estimation, person re-identification, and threat detection without requiring the full enrichment service. Designed to run on a secondary GPU (e.g., RTX A400 4GB) with a smaller VRAM budget (~1.2GB).

## Key Files

```
ai/enrichment-light/
├── AGENTS.md                    # This file
├── model.py                     # FastAPI server (main entry point)
├── security.py                  # Security utilities
├── models/
│   ├── __init__.py              # Package exports
│   ├── person_reid.py           # Person re-identification (OSNet)
│   ├── pose_estimator.py        # Pose estimation (YOLOv8n-pose)
│   └── threat_detector.py       # Threat/weapon detection
└── tests/
    ├── __init__.py              # Package init
    └── test_model_loading.py    # Model loading tests
```

## Docker Service

- **Service name**: ai-enrichment-light
- **Port**: 8096
- **Target GPU**: GPU 1 (secondary, smaller VRAM)
- **VRAM budget**: ~1.2GB
