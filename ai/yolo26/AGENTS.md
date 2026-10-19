# YOLO26 Package

## Purpose

Holds `build_engine.py`, the TensorRT engine builder invoked by
`scripts/prebuild-tensorrt-engines.sh`. Production YOLO26 detection is served
by Triton inside the `ai-gateway` container (`ai/gateway/adapters/yolo26.py`).
O3.1 (ruling 210) pruned the unshipped host-run server modules.

## Directory Contents

```
ai/yolo26/
├── AGENTS.md            # This file
├── __init__.py          # Package init
└── build_engine.py      # TensorRT engine builder (scripts/prebuild-tensorrt-engines.sh)
```
