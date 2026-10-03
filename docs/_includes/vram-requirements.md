### Always-Loaded Services

| Service    | Container  | Model                                                            | VRAM                                               | Purpose                             |
| ---------- | ---------- | ---------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------- |
| VLM engine | ai-vlm     | GGUF pair — operator config (`VLM_MODEL_PATH`/`VLM_MMPROJ_PATH`) | config-driven; `VLM_GPU_LAYERS=auto` fits the card | Scene description + risk reasoning  |
| Detection  | ai-gateway | YOLO26 (Triton) + re-ID/threat specialists                       | Triton set `yolo26`/`reid`/`threat` (opt-in)       | Object detection + identity lookups |

The `ai-vlm` container sits behind the `vlm` compose profile — the stack runs
without it and events degrade (no verdicts) rather than fail to boot. No
measured residency figure exists yet for the shipped identity; the bring-up
record owns the per-card numbers. The gateway serves exactly two routers
(`/yolo26`, `/enrich-lt`); `GATEWAY_MODEL_SET` resolves only `vlm`, and
`GATEWAY_ENABLE_THREAT=false` ships the `threat` model opted-in rather than
resident by default.

### On-Demand Lookup Models (backend model zoo)

VRAM is from `models.yml` `vram_mb`; the enabled, GPU-resident rows sum to
~1.0GB when all are loaded (they load lazily on first use and stay resident —
there is no eviction pass; the two CPU face rows cost 0 VRAM):

| Model                    | VRAM    |
| ------------------------ | ------- |
| osnet-ain-x1-0           | ~100MB  |
| threat-detection-yolov8n | ~300MB  |
| yolo11-face              | ~200MB  |
| yolo11-license-plate     | ~300MB  |
| fast-alpr                | ~28MB   |
| paddleocr                | ~100MB  |
| face-detector-scrfd      | 0 (CPU) |
| face-recognizer          | 0 (CPU) |

### Sizing Guidance

Sizing is dominated by the VLM identity you configure: `VLM_GPU_LAYERS=auto`
(the default) offloads as many layers as the card allows, and the GGUF pair's
disk size and layer count set the floor. On top of that budget the gateway's
Triton process and ~1.0GB of lookup-model headroom. `ai-vlm` is the system's
only LLM service.
