# Model Export Pipeline Directory

## Purpose

Scripts that convert HuggingFace/PyTorch models into Triton-servable artifacts: ONNX export -> ONNX Runtime validation (cosine similarity > 0.999 vs PyTorch) -> TensorRT FP16 engine where possible. Output `.plan`/`.onnx` files land in the Triton model repository. Part of the Triton migration (`docs/plans/triton-migration.md`).

## Key Files

| Script                  | Model                                                                          | Output type     |
| ----------------------- | ------------------------------------------------------------------------------ | --------------- |
| `export_all.sh`         | Master orchestrator — runs every export                                        | —               |
| `export_yolo26.py`      | YOLO26m                                                                        | ONNX            |
| `copy_yolo26_engine.py` | Copies pre-built YOLO26 TensorRT engine into the repository                    | copy            |
| `export_reid.py`        | Person Re-ID (OSNet-AIN x1.0)                                                  | ONNX / TensorRT |
| `export_face.py`        | Face leg SCRFD (`scrfd_10g_bnkps.onnx`) + ArcFace (`w600k_r50.onnx`) ([r307a]) | ONNX / TensorRT |
| `export_yolo_threat.py` | YOLOv8n threat detection                                                       | TensorRT / ONNX |

`README.md` has the full pipeline diagram, CLI flags (`--model-path`, `--output-path`, `--precision`) and engine paths.

## Patterns / Gotchas

- TensorRT engines are GPU-architecture-specific — rebuild after moving GPUs.
- Runs inside the ai-gateway image (`torch`/`transformers`/`ultralytics`/`onnx` are installed there for this pipeline), not in the backend env.
- Florence-2 is deliberately NOT here — it serves via Triton's Python backend, not exported. (xclip_action used to be in that same boat; it was retired with NEM-5563, superseded by the exported `stgcn_action` ONNX + the gateway's per-frame pose stage.)

Related: `../AGENTS.md` (gateway), `../../AGENTS.md` (AI tier).
