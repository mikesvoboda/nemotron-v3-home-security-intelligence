# Model Export Pipeline Directory

## Purpose

Scripts that convert HuggingFace/PyTorch models into Triton-servable artifacts: ONNX export -> ONNX Runtime validation (cosine similarity > 0.999 vs PyTorch) -> TensorRT FP16 engine where possible. Output `.plan`/`.onnx` files land in the Triton model repository. Part of the Triton migration (`docs/plans/triton-migration.md`).

## Key Files

| Script                    | Model                                    | Output type       |
| ------------------------- | ---------------------------------------- | ----------------- |
| `export_all.sh`           | Master orchestrator — runs every export  | —                 |
| `export_yolo26.py`        | YOLO26m                                  | ONNX              |
| `copy_yolo26_engine.py`   | Copies pre-built YOLO26 TensorRT engine into the repository | copy |
| `export_clip.py`          | SigLIP 2 Base vision encoder (pre-built ONNX copy) | ONNX    |
| `export_clip_text.py`     | SigLIP 2 Base text encoder               | ONNX              |
| `export_fashion_clip.py`  | FashionSigLIP (Marqo)                    | TensorRT          |
| `export_demographics.py`  | Age + Gender ViT classifiers             | ONNX              |
| `export_depth.py`         | Depth Anything V2 Tiny                   | ONNX              |
| `export_pet.py`           | Pet Classifier (ResNet-18)               | ONNX              |
| `export_vehicle.py`       | Vehicle Classifier (ResNet-50)           | ONNX              |
| `export_reid.py`          | Person Re-ID (OSNet-AIN x1.0)            | ONNX              |
| `export_stgcn.py`         | ST-GCN++ action recognition              | ONNX              |
| `export_yolo_pose.py`     | YOLOv8n-pose                             | TensorRT / ONNX   |
| `export_yolo_threat.py`   | YOLOv8n threat detection                 | TensorRT / ONNX   |

`README.md` has the full pipeline diagram, CLI flags (`--model-path`, `--output-path`, `--precision`) and engine paths.

## Patterns / Gotchas

- TensorRT engines are GPU-architecture-specific — rebuild after moving GPUs (see `ai/common/AGENTS.md` caching).
- Runs inside the ai-gateway image (`torch`/`transformers`/`ultralytics`/`onnx` are installed there for this pipeline), not in the backend env.
- Florence-2 and xclip_action are deliberately NOT here — they serve via Triton's Python backend, not exported.

## Related

- `../AGENTS.md` (gateway), `../../triton/AGENTS.md`
