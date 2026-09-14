### Always-Loaded Core Services

| Service    | Container   | Model                   | VRAM    | Purpose                     |
| ---------- | ----------- | ----------------------- | ------- | --------------------------- |
| YOLO26     | ai-yolo26   | YOLO26m (TensorRT FP16) | ~2GB    | Primary object detection    |
| Nemotron   | ai-llm      | Nemotron-3-Nano-30B-A3B | ~14.7GB | Risk reasoning and analysis |
| Florence-2 | ai-florence | Florence-2-Large        | ~1.2GB  | Scene understanding, OCR    |
| CLIP       | ai-clip     | CLIP ViT-L/14           | ~800MB  | Embeddings, anomaly detect  |

### VRAM Tiers

| Tier            | Min VRAM | Models Loaded                   | Use Case          |
| --------------- | -------- | ------------------------------- | ----------------- |
| **Minimum**     | 8GB      | YOLO26 + Nemotron Mini 4B (dev) | Development only  |
| **Recommended** | 16GB     | YOLO26 + Nemotron 30B           | Production (core) |
| **Optimal**     | 24GB+    | All core + enrichment on-demand | Full model zoo    |
