# CLIP Embedding Server

## Purpose

FastAPI-based HTTP server that wraps CLIP ViT-L model for generating 768-dimensional embeddings. Used for entity re-identification across cameras and scene anomaly detection via cosine similarity comparisons.

## Port and Resources

- **Port**: 8093
- **Expected VRAM**: ~800 MB (PyTorch) / ~600 MB (TensorRT)
- **Embedding Dimension**: 768

## Directory Contents

```
ai/clip/
├── AGENTS.md              # This file
├── Dockerfile             # Container build (PyTorch + CUDA 12.4)
├── model.py               # FastAPI embedding server
├── tensorrt_inference.py  # TensorRT inference backend (NEM-3838)
├── export_onnx.py         # ONNX export script for TensorRT conversion
├── test_model.py          # Unit tests (pytest)
└── requirements.txt       # Python dependencies
```

## Key Files

### `model.py` (Main Server)

FastAPI server implementation using HuggingFace Transformers CLIPModel.

**Classes:**

| Class                     | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `EmbedRequest`            | Request: image (base64)                                |
| `EmbedResponse`           | Response: embedding[768], inference_time_ms            |
| `AnomalyScoreRequest`     | Request: image (base64), baseline_embedding[768]       |
| `AnomalyScoreResponse`    | Response: anomaly_score, similarity, inference_time_ms |
| `ClassifyRequest`         | Request: image (base64), labels (list of text)         |
| `ClassifyResponse`        | Response: scores (dict), top_label, inference_time_ms  |
| `SimilarityRequest`       | Request: image (base64), text (description)            |
| `SimilarityResponse`      | Response: similarity score, inference_time_ms          |
| `BatchSimilarityRequest`  | Request: image (base64), texts (list of descriptions)  |
| `BatchSimilarityResponse` | Response: similarities (dict), inference_time_ms       |
| `HealthResponse`          | Health: status, model, device, embedding_dimension     |
| `CLIPEmbeddingModel`      | Model wrapper with load_model(), extract_embedding()   |

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

### `test_model.py`

Unit tests covering:

- BatchSimilarityRequest batch size validation (NEM-1101 security requirement)
- Division by zero protection in anomaly score calculation (NEM-1100)
- Request model validation
- API endpoint behavior

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
nvidia-ml-py>=12.560.30
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

### POST /classify

Zero-shot classification against a list of text labels.

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "labels": ["person walking", "delivery driver", "suspicious activity"]
}
```

**Response:**

```json
{
  "scores": { "person walking": 0.75, "delivery driver": 0.2, "suspicious activity": 0.05 },
  "top_label": "person walking",
  "inference_time_ms": 32.5
}
```

### POST /similarity

Compute image-text similarity score.

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "text": "person wearing dark hoodie"
}
```

**Response:**

```json
{
  "similarity": 0.72,
  "inference_time_ms": 15.3
}
```

### POST /batch-similarity

Batch image-text similarity comparison (limited to MAX_BATCH_TEXTS_SIZE=100).

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "texts": ["delivery person", "suspicious individual", "resident"]
}
```

**Response:**

```json
{
  "similarities": { "delivery person": 0.65, "suspicious individual": 0.15, "resident": 0.45 },
  "inference_time_ms": 45.2
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

| Variable            | Default                                         | Description                             |
| ------------------- | ----------------------------------------------- | --------------------------------------- |
| `CLIP_MODEL_PATH`   | `/models/clip-vit-l`                            | HuggingFace model path                  |
| `HOST`              | `0.0.0.0`                                       | Bind address                            |
| `PORT`              | `8093`                                          | Server port                             |
| `HF_HOME`           | `/cache/huggingface`                            | HuggingFace cache dir                   |
| `CLIP_USE_TENSORRT` | `true`                                          | Enable TensorRT backend (true/false)    |
| `CLIP_ENGINE_PATH`  | `/models/clip-vit-l/vision_encoder_fp16.engine` | Path to TensorRT engine (auto-exported) |
| `PYROSCOPE_ENABLED` | `true`                                          | Enable/disable continuous profiling     |
| `PYROSCOPE_URL`     | `http://pyroscope:4040`                         | Pyroscope server address                |
| `ENVIRONMENT`       | `production`                                    | Environment tag for profiles            |

## TensorRT Acceleration (NEM-3838)

TensorRT provides 1.5-2x faster inference for embedding extraction.

### Auto-Export (Default)

TensorRT is **enabled by default** and **auto-exports** the engine on first startup:

- If `CLIP_USE_TENSORRT=true` and engine doesn't exist, it will be auto-exported
- Export takes ~2-5 minutes on first run (ONNX export + TensorRT build)
- Subsequent startups use the cached engine (~60s startup)
- Falls back to PyTorch automatically if TensorRT export fails

### Manual Export (Optional)

For pre-building engines before deployment:

```bash
# Full pipeline: export + validate + convert
python export_onnx.py pipeline \
    --model-path /models/clip-vit-l \
    --output-dir /models/clip-vit-l \
    --precision fp16
```

Or step-by-step:

```bash
# 1. Export ONNX Model
python export_onnx.py export \
    --model-path /models/clip-vit-l \
    --output /models/clip-vit-l/vision_encoder.onnx

# 2. Convert to TensorRT
python export_onnx.py tensorrt \
    --onnx /models/clip-vit-l/vision_encoder.onnx \
    --output /models/clip-vit-l/vision_encoder_fp16.engine \
    --precision fp16 \
    --max-batch 8
```

### Disabling TensorRT

To use PyTorch backend instead:

```bash
export CLIP_USE_TENSORRT=false
```

### Validation

The export process validates that TensorRT embeddings match PyTorch embeddings
with cosine similarity > 0.99, ensuring identical quality.

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
2. **Tests**: `test_model.py` - For API contracts and validation
3. **Dockerfile**: Container build configuration
4. **Requirements**: `requirements.txt` - Python dependencies
