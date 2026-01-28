# Florence-2 Vision-Language Server

## Purpose

FastAPI-based HTTP server that wraps Florence-2-large model for vision-language queries. Supports various prompts for attribute extraction from security camera images including captions, object detection, OCR, and dense region captioning.

## Port and Resources

- **Port**: 8092
- **Expected VRAM**: ~1.2 GB
- **Inference Time**: 100-300ms per query

## Directory Contents

```
ai/florence/
├── AGENTS.md          # This file
├── __init__.py        # Package marker
├── Dockerfile         # Container build (PyTorch + CUDA 12.4)
├── model.py           # FastAPI vision-language server
├── requirements.txt   # Python dependencies
└── tests/             # Unit tests
    ├── __init__.py
    └── test_analyze_scene.py  # Tests for /analyze-scene endpoint
```

**Testing:** Run tests with `uv run pytest ai/florence/tests/ -v`

## Key Files

### `model.py` (Main Server)

FastAPI server implementation using HuggingFace Transformers AutoModelForCausalLM.

**Classes:**

| Class                    | Description                                                    |
| ------------------------ | -------------------------------------------------------------- |
| `ExtractRequest`         | Request: image (base64), prompt (Florence-2 task)              |
| `ExtractResponse`        | Response: result, prompt_used, inference_time_ms               |
| `ImageRequest`           | Request: image (base64) - for endpoints needing only an image  |
| `OCRResponse`            | Response: text, inference_time_ms                              |
| `OCRRegion`              | A text region with bounding box coordinates                    |
| `OCRWithRegionsResponse` | Response: regions (list of OCRRegion), inference_time_ms       |
| `Detection`              | A detected object with label, bbox, score                      |
| `DetectResponse`         | Response: detections (list), inference_time_ms                 |
| `CaptionedRegion`        | A region with caption and bbox                                 |
| `DenseCaptionResponse`   | Response: regions (list of CaptionedRegion), inference_time_ms |
| `HealthResponse`         | Health: status, model, device, vram_used_gb                    |
| `Florence2Model`         | Model wrapper with load_model(), extract(), extract_raw()      |

**Key Functions in Florence2Model:**

```python
def load_model(self) -> None:
    """Load model via AutoModelForCausalLM.from_pretrained() with trust_remote_code=True"""

def extract(self, image: Image.Image, prompt: str) -> tuple[str, float]:
    """Run Florence-2 inference, returns (result as string, inference_time_ms)"""

def extract_raw(self, image: Image.Image, prompt: str) -> tuple[Any, float]:
    """Run Florence-2 inference, returns (raw parsed result, inference_time_ms)"""
```

**Supported Prompts:**

```python
SUPPORTED_PROMPTS = {
    "<CAPTION>",              # Brief image caption
    "<DETAILED_CAPTION>",     # Detailed image description
    "<MORE_DETAILED_CAPTION>",# Very detailed description
    "<OD>",                   # Object detection
    "<DENSE_REGION_CAPTION>", # Dense region captioning
    "<REGION_PROPOSAL>",      # Region proposals
    "<OCR>",                  # Text recognition
    "<OCR_WITH_REGION>",      # OCR with bounding boxes
}

# VQA (Visual Question Answering) prompts use format: "<VQA>question text"
VQA_PROMPT_PREFIX = "<VQA>"
```

### `Dockerfile`

Container build configuration:

- **Base image**: `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime`
- **Non-root user**: `florence` for security
- **Health check**: 120s start period (larger model)
- **HuggingFace cache**: `/cache/huggingface`

### `requirements.txt`

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
torch>=2.0.0
transformers>=4.35.0
einops>=0.7.0      # Required by Florence-2
timm>=0.9.0        # Required by Florence-2
pillow>=10.0.0
numpy>=1.24.0
pydantic>=2.4.0
nvidia-ml-py>=12.560.30  # GPU monitoring
```

## API Endpoints

### GET /health

Returns server health status.

```json
{
  "status": "healthy",
  "model": "florence-2-large",
  "model_loaded": true,
  "device": "cuda:0",
  "cuda_available": true,
  "vram_used_gb": 1.2
}
```

### POST /extract

Extract information using a Florence-2 prompt.

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "prompt": "<CAPTION>"
}
```

**Response (caption):**

```json
{
  "result": "A person in a blue jacket standing at a front door",
  "prompt_used": "<CAPTION>",
  "inference_time_ms": 145.2
}
```

**Response (object detection):**

```json
{
  "result": "{'<OD>': {'bboxes': [[100,150,300,400]], 'labels': ['person']}}",
  "prompt_used": "<OD>",
  "inference_time_ms": 180.5
}
```

### POST /ocr

Extract all text from an image.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "text": "LICENSE PLATE ABC123",
  "inference_time_ms": 120.3
}
```

### POST /ocr-with-regions

Extract text with quadrilateral bounding boxes.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "regions": [{ "text": "ABC123", "bbox": [100, 150, 200, 150, 200, 180, 100, 180] }],
  "inference_time_ms": 135.2
}
```

### POST /detect

Detect objects with bounding boxes.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "detections": [{ "label": "person", "bbox": [100, 150, 300, 400], "score": 1.0 }],
  "inference_time_ms": 145.8
}
```

### POST /dense-caption

Generate captions for all regions in an image.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "regions": [
    { "caption": "a person wearing a blue jacket", "bbox": [100, 150, 300, 400] },
    { "caption": "a white delivery van", "bbox": [400, 200, 600, 350] }
  ],
  "inference_time_ms": 210.5
}
```

### POST /analyze-scene

**NEW: Cascade prompt strategy for comprehensive scene analysis.**

Runs multiple Florence-2 tasks in sequence/parallel to extract maximum context:

1. `<MORE_DETAILED_CAPTION>` - Rich scene description
2. `<DENSE_REGION_CAPTION>` - Per-region captions with bounding boxes (parallel)
3. `<OCR_WITH_REGION>` - Text extraction with locations (parallel)

Tasks 2 and 3 run in parallel using `asyncio.gather` for optimal performance.

**Request:**

```json
{ "image": "<base64-encoded-image>" }
```

**Response:**

```json
{
  "caption": "A delivery person in a blue uniform is standing at the front door of a residential home. They are holding a brown cardboard package.",
  "regions": [
    { "caption": "delivery person in blue uniform", "bbox": [100, 150, 300, 400] },
    { "caption": "brown cardboard package", "bbox": [200, 350, 280, 420] }
  ],
  "text_regions": [{ "text": "PRIORITY MAIL", "bbox": [210, 360, 270, 360, 270, 380, 210, 380] }],
  "inference_time_ms": 450.5,
  "task_times_ms": {
    "caption": 200.0,
    "dense_regions": 150.0,
    "ocr_with_regions": 100.5
  }
}
```

**Use Case:** Primary endpoint for Nemotron prompt context generation. Provides structured output with all scene elements needed for security risk assessment.

### POST /describe-region (NEM-3911)

Describe what's in specific bounding box regions of an image.

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "regions": [
    { "x1": 100, "y1": 150, "x2": 300, "y2": 400 },
    { "x1": 200, "y1": 350, "x2": 280, "y2": 420 }
  ]
}
```

**Response:**

```json
{
  "descriptions": [
    {
      "caption": "a person wearing a blue jacket and holding a brown package",
      "bbox": [100, 150, 300, 400]
    },
    { "caption": "a brown cardboard package on the ground", "bbox": [200, 350, 280, 420] }
  ],
  "inference_time_ms": 180.5
}
```

**Use Case:** Get detailed descriptions of YOLO26 detections for enriched context in Nemotron prompts.

### POST /phrase-grounding (NEM-3911)

Find objects in an image matching text descriptions (phrase grounding).

**Request:**

```json
{
  "image": "<base64-encoded-image>",
  "phrases": ["person in blue jacket", "brown package", "weapon"]
}
```

**Response:**

```json
{
  "grounded_phrases": [
    {
      "phrase": "person in blue jacket",
      "bboxes": [[100, 150, 300, 400]],
      "confidence_scores": [1.0]
    },
    { "phrase": "brown package", "bboxes": [[200, 350, 280, 420]], "confidence_scores": [1.0] },
    { "phrase": "weapon", "bboxes": [], "confidence_scores": [] }
  ],
  "inference_time_ms": 250.3
}
```

**Use Case:** Targeted object search for security-relevant items. Useful for finding specific objects described in natural language or verifying presence of suspicious items.

## Prompt Types and Use Cases

### Caption Prompts

| Prompt                    | Output                        | Use Case            |
| ------------------------- | ----------------------------- | ------------------- |
| `<CAPTION>`               | Brief 1-sentence description  | Quick scene summary |
| `<DETAILED_CAPTION>`      | Detailed paragraph            | Event logging       |
| `<MORE_DETAILED_CAPTION>` | Very detailed multi-paragraph | Full scene analysis |

### Detection Prompts

| Prompt                   | Output                      | Use Case                     |
| ------------------------ | --------------------------- | ---------------------------- |
| `<OD>`                   | Objects with bounding boxes | Object localization          |
| `<DENSE_REGION_CAPTION>` | Caption per detected region | Detailed scene understanding |
| `<REGION_PROPOSAL>`      | All region proposals        | Object discovery             |

### OCR Prompts

| Prompt              | Output                   | Use Case              |
| ------------------- | ------------------------ | --------------------- |
| `<OCR>`             | Detected text            | License plates, signs |
| `<OCR_WITH_REGION>` | Text with bounding boxes | Text localization     |

### Region-Based Prompts (NEM-3911)

| Prompt                          | Input               | Output                     | Use Case                    |
| ------------------------------- | ------------------- | -------------------------- | --------------------------- |
| `<REGION_TO_DESCRIPTION>`       | Bounding box region | Caption of region contents | Describe detected objects   |
| `<CAPTION_TO_PHRASE_GROUNDING>` | Text phrase         | Bounding boxes of matches  | Find objects by description |

## Environment Variables

| Variable              | Default                    | Description            |
| --------------------- | -------------------------- | ---------------------- |
| `FLORENCE_MODEL_PATH` | `/models/florence-2-large` | HuggingFace model path |
| `HOST`                | `0.0.0.0`                  | Bind address           |
| `PORT`                | `8092`                     | Server port            |
| `HF_HOME`             | `/cache/huggingface`       | HuggingFace cache dir  |

## Model Details

- **Model**: Microsoft Florence-2-large
- **Architecture**: Vision-language transformer with task-specific prompts
- **Special Requirements**:
  - `trust_remote_code=True` (custom model code)
  - `attn_implementation="eager"` (SDPA compatibility)
  - `use_cache=False` in generate() (past_key_values bug workaround)

## Starting the Server

### Container (Production)

```bash
docker compose -f docker-compose.prod.yml up ai-florence
```

### Native (Development)

```bash
cd ai/florence && python model.py
```

## Example Usage

```bash
# Get brief caption
curl -X POST http://localhost:8092/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image": "'$(base64 -w0 image.jpg)'",
    "prompt": "<CAPTION>"
  }'

# Detect objects
curl -X POST http://localhost:8092/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image": "'$(base64 -w0 image.jpg)'",
    "prompt": "<OD>"
  }'

# Extract text (OCR)
curl -X POST http://localhost:8092/extract \
  -H "Content-Type: application/json" \
  -d '{
    "image": "'$(base64 -w0 image.jpg)'",
    "prompt": "<OCR>"
  }'
```

## Backend Integration

The Florence-2 server is an optional service that can provide detailed scene descriptions for Nemotron risk analysis:

```python
# Example integration (not yet implemented in backend)
from httpx import AsyncClient

async def get_scene_description(image_base64: str) -> str:
    async with AsyncClient() as client:
        response = await client.post(
            "http://localhost:8092/extract",
            json={"image": image_base64, "prompt": "<DETAILED_CAPTION>"}
        )
        return response.json()["result"]
```

**Note**: Florence-2 integration is planned but not yet implemented in the backend. The service is available for future enhancements to the enrichment pipeline.

## Entry Points

1. **Main server**: `model.py` - Start here for understanding the API
2. **Dockerfile**: Container build configuration
3. **Requirements**: `requirements.txt` - Python dependencies (note: einops, timm required)
