# CLIP Embedding Server

## Purpose

FastAPI-based HTTP server that wraps CLIP ViT-L model for generating 768-dimensional embeddings. Used for entity re-identification across cameras and scene anomaly detection via cosine similarity comparisons.

## Port and Resources

- **Port**: 8093
- **Expected VRAM**: ~800 MB
- **Embedding Dimension**: 768

## Directory Contents

```
ai/clip/
├── AGENTS.md          # This file
├── Dockerfile         # Container build (PyTorch + CUDA 12.4)
├── model.py           # FastAPI embedding server
└── requirements.txt   # Python dependencies
```

## Key Files

### `model.py` (Main Server)

FastAPI server implementation using HuggingFace Transformers CLIPModel.

**Classes:**

| Class                  | Description                                            |
| ---------------------- | ------------------------------------------------------ |
| `EmbedRequest`         | Request: image (base64)                                |
| `EmbedResponse`        | Response: embedding[768], inference_time_ms            |
| `AnomalyScoreRequest`  | Request: image (base64), baseline_embedding[768]       |
| `AnomalyScoreResponse` | Response: anomaly_score, similarity, inference_time_ms |
| `HealthResponse`       | Health: status, model, device, embedding_dimension     |
| `CLIPEmbeddingModel`   | Model wrapper with load_model(), extract_embedding()   |

**Key Functions in CLIPEmbeddingModel:**

```python
def load_model(self) -> None:
    """Load model via CLIPModel.from_pretrained()"""

def extract_embedding(self, image: Image.Image) -> tuple[list[float], float]:
    """Generate 768-dim embedding, returns (embedding, inference_time_ms)"""

def compute_anomaly_score(self, image: Image.Image, baseline: list[float]) -> tuple[float, float, float]:
    """Compare to baseline, returns (anomaly_score, similarity, inference_time_ms)"""
```

**Constants:**

```python
EMBEDDING_DIMENSION = 768
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
```

### `Dockerfile`

Container build configuration:

- **Base image**: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`
- **Non-root user**: `clip` for security
- **Health check**: 60s start period
- **HuggingFace cache**: `/cache/huggingface`

### `requirements.txt`

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
torch>=2.0.0
transformers>=4.35.0
pillow>=10.0.0
numpy>=1.24.0
pydantic>=2.4.0
pynvml>=11.5.0
```

## API Endpoints

### GET /health

Returns server health status.

```json
{
  "status": "healthy",
  "model": "clip-vit-large-patch14",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "vram_used_gb": 0.8,
  "embedding_dimension": 768
}
```

### POST /embed

Generate CLIP embedding from an image.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "embedding": [0.123, -0.456, ...],  // 768 floats
  "inference_time_ms": 25.4
}
```

### POST /anomaly-score

Compare image to baseline embedding for anomaly detection.

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "baseline_embedding": [0.123, -0.456, ...]  // 768 floats
}
```

**Response:**

```json
{
  "anomaly_score": 0.35, // 0=identical to baseline, 1=completely different
  "similarity_to_baseline": 0.65, // cosine similarity (-1 to 1)
  "inference_time_ms": 28.1
}
```

## Use Cases

### Entity Re-identification

Track the same person or vehicle across multiple cameras:

```python
# Extract embedding from camera 1
emb1 = await clip_client.embed(person_crop_cam1)

# Extract embedding from camera 2
emb2 = await clip_client.embed(person_crop_cam2)

# Compare embeddings
similarity = cosine_similarity(emb1, emb2)
if similarity > 0.85:
    print("Same person detected!")
```

### Scene Anomaly Detection

Detect unusual changes in a camera's field of view:

```python
# Compute baseline from "normal" frames
baseline = average_embedding(normal_frames)

# Check new frame for anomalies
result = await clip_client.anomaly_score(new_frame, baseline)
if result.anomaly_score > 0.5:
    print("Significant scene change detected!")
```

## Environment Variables

| Variable          | Default              | Description            |
| ----------------- | -------------------- | ---------------------- |
| `CLIP_MODEL_PATH` | `/models/clip-vit-l` | HuggingFace model path |
| `HOST`            | `0.0.0.0`            | Bind address           |
| `PORT`            | `8093`               | Server port            |
| `HF_HOME`         | `/cache/huggingface` | HuggingFace cache dir  |

## Embedding Details

- **Model**: CLIP ViT-L/14
- **Dimension**: 768 floats
- **Normalization**: L2-normalized (unit vectors)
- **Similarity Metric**: Cosine similarity (dot product of normalized vectors)

## Starting the Server

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-clip
```

### Native (Development)

```bash
cd ai/clip && python model.py
```

## Backend Integration

The CLIP server is an optional service. When enabled, it can be used by the enrichment pipeline for entity tracking:

```python
# Example integration (not yet implemented in backend)
from httpx import AsyncClient

async def get_embedding(image_base64: str) -> list[float]:
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8093/embed",
            json={"image": image_base64}
        )
        return response.json()["embedding"]
```

## Entry Points

1. **Main server**: `model.py` - Start here for understanding the API
2. **Dockerfile**: Container build configuration
3. **Requirements**: `requirements.txt` - Python dependencies
