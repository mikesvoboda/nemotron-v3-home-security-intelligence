# synthbench/generate/comfy — Agent Guide

## Purpose

The pinned ComfyUI v0.37.0 renderer (spec §3.1-§3.2): its podman image, an HTTP client, an offline graph validator and one API-graph builder per model.

## Key Files

| Path                                      | What                                                                              |
| ----------------------------------------- | --------------------------------------------------------------------------------- |
| `Containerfile`, `extra_model_paths.yaml` | the renderer image (NGC PyTorch base); the farm mapping it loads                  |
| `serve.py`                                | `podman build/run/stop` arguments and readiness wait; CLI `build`, `up`, `down`   |
| `client.py`                               | HTTP client: upload, queue, wait, outputs, download, free                         |
| `validate.py`                             | offline check of an API graph against `/object_info`                              |
| `graphs.py`                               | one graph builder per model; the T2I, edit and I2V registries                     |
| `snapshot.py`, `object_info.v0.37.0.json` | the captured, filtered `/object_info` that the unit tests validate graphs against |
| `smoke.py`, `smoke_ref.png`               | live smoke CLI and its person-free reference image                                |

## Rules

- `extra_model_paths.yaml` is generated: a test checks it equals `weights.extra_model_paths_yaml(...)` for `/export/models/comfyui`.
- Builders follow the official v0.37.0 templates; the captured `/object_info` is the authority for input names and types.
- The renderer binds 127.0.0.1 only and carries the `synthbench.gpu=1` label, so the GPU window stops it before the flagship restarts.
- The image lives in the synthbench podman store: in shell, `$(uv run python -m synthbench.generate.podman) images`, never bare `podman`.
- Never let pip replace the base image's torch, torchvision or triton.
