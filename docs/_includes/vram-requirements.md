### Always-Loaded Core Services

| Service    | Container  | Model                          | VRAM    | Purpose                                 |
| ---------- | ---------- | ------------------------------ | ------- | --------------------------------------- |
| YOLO26     | ai-gateway | YOLO26 (TensorRT)              | ~2GB    | Primary object detection                |
| Nemotron   | ai-llm     | Nemotron-3-Nano-30B-A3B Q4_K_M | ~14.7GB | Risk reasoning and analysis             |
| Florence-2 | ai-gateway | Florence-2-base                | ~1.5GB  | Scene understanding, OCR                |
| Embeddings | ai-gateway | SigLIP 2 base (Triton `clip`)  | ~200MB  | Entity re-ID embeddings, anomaly detect |

Florence-2, YOLO26 and the embedding models all run inside the single `ai-gateway` container (host port `AI_GATEWAY_PORT`, default 8090) through routers `/yolo26`, `/florence`, `/clip`, `/enrichment` and `/enrich-lt`.

### VRAM Tiers

| Tier            | Min VRAM | Models Loaded                                                         | Use Case         |
| --------------- | -------- | --------------------------------------------------------------------- | ---------------- |
| **Minimum**     | ~8–12GB  | LLM partially offloaded via `GPU_LAYERS` (slow) + YOLO26 + embeddings | Development only |
| **Recommended** | 16GB     | LLM with reduced `GPU_LAYERS` + on-demand models                      | Production       |
| **Optimal**     | 24GB+    | All core models, LLM fully on GPU                                     | Full model zoo   |
