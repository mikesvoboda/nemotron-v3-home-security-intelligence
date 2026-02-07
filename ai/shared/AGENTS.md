# AI Shared Utilities

## Purpose

Shared utility modules used across multiple AI services.

## Directory Contents

```
ai/shared/
├── AGENTS.md          # This file
├── __init__.py        # Package init
└── gpu_profiler.py    # GPU profiling utilities (VRAM usage, utilization tracking)
```

## Key Files

### gpu_profiler.py

GPU profiling utilities for monitoring VRAM usage, GPU utilization, and performance metrics across AI services. Used by model managers and inference servers to track resource consumption.
