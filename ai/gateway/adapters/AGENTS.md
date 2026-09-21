# AI Gateway Adapters Directory

## Purpose

One FastAPI router module per legacy AI service. Each adapter translates the service's existing REST API (multipart uploads or base64 JSON) into Triton gRPC inference calls, so response shapes match the legacy containers exactly. Routers are mounted in `ai/gateway/main.py`.

## Key Files

| File                   | Mount prefix    | Legacy service         | Notes                                       |
| ---------------------- | --------------- | ---------------------- | ------------------------------------------- |
| `yolo26.py`            | `/yolo26`       | YOLO26 detection       | multipart upload; `/detect`, `/detect/batch`, `/segment` |
| `clip.py`              | `/clip`         | CLIP embeddings        | backed by SigLIP 2 Base (swapped from ViT-L/14 to save VRAM); `/embed`, `/classify`, `/similarity`, `/anomaly-score` |
| `florence.py`          | `/florence`     | Florence-2             | Triton Python backend; `/extract`, `/ocr`, region endpoints |
| `enrichment.py`        | `/enrichment`   | Heavy enrichment       | fans out to per-model Triton models; `/enrich` dispatches on detection_type |
| `enrichment_light.py`  | `/enrich-lt`    | Light enrichment       | `/pose-analyze`, `/threat-detect`, `/person-reid`, `/pet-classify`, `/depth-estimate` |

## Patterns / Gotchas

- Shared helpers (base64 decode, letterbox, normalization) live in `ai/gateway/utils.py` — don't reimplement per adapter.
- All calls go through `ai/gateway/triton_client.py`; adapters never talk gRPC directly.
- Model names match Triton repository names (`yolo26`, `clip`, `florence2`, `vehicle`, `fashion_clip`, `pose`, `threat`, `reid`, `pet`, `depth`, ...).
- Tests for each adapter live in `ai/gateway/tests/test_adapters_<name>.py` and mock the Triton client (no GPU needed).

## Related

- `../AGENTS.md` (gateway), `../tests/AGENTS.md`, `../../triton/AGENTS.md`
