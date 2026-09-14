# Florence-2 Tests Directory

## Purpose

Unit tests for the Florence-2 Vision-Language Server (`ai/florence/model.py`). Tests validate the `/analyze-scene` cascade prompt endpoint and related Pydantic models without requiring a GPU or actual model files.

## Directory Structure

```
ai/florence/tests/
├── AGENTS.md               # This file
├── __init__.py             # Package marker
└── test_analyze_scene.py   # /analyze-scene endpoint unit tests
```

## Running Tests

```bash
# Run all Florence-2 tests
uv run pytest ai/florence/tests/ -v

# Run with coverage
uv run pytest ai/florence/tests/ -v --cov=ai.florence
```

## Test Files

### `test_analyze_scene.py`

Comprehensive tests for the `/analyze-scene` cascade prompt endpoint that runs multiple Florence-2 tasks in parallel:

1. `MORE_DETAILED_CAPTION` - Rich scene description
2. `DENSE_REGION_CAPTION` - Per-region captions with bounding boxes
3. `OCR_WITH_REGION` - Text extraction with locations

**Test Classes:**

| Class                       | Description                            | Test Count |
| --------------------------- | -------------------------------------- | ---------- |
| `TestSceneAnalysisRequest`  | Pydantic request model validation      | 2 tests    |
| `TestSceneAnalysisResponse` | Pydantic response model structure      | 2 tests    |
| `TestAnalyzeSceneEndpoint`  | /analyze-scene endpoint behavior       | 6 tests    |
| `TestParallelExecution`     | Async parallel task execution          | 1 test     |
| `TestSecuritySceneTypes`    | Security-relevant scene analysis       | 4 tests    |
| `TestNemotronOutputFormat`  | Output format for Nemotron consumption | 3 tests    |

**Test Scenarios:**

- Successful scene analysis with all components (caption, regions, text)
- Scene with no text (empty OCR results)
- Scene with no distinct regions (single object)
- Model not loaded error (503)
- Invalid base64 encoding (400)
- Invalid image data (400)
- Parallel execution timing verification
- Security-relevant scenes (person at door, delivery, vehicle, animal)
- JSON serialization for Nemotron prompts

**Fixtures:**

| Fixture      | Description                             |
| ------------ | --------------------------------------- |
| `client`     | FastAPI TestClient for endpoint testing |
| `mock_model` | Mocked Florence2Model for isolation     |

**Helper Functions:**

```python
def create_test_image(width, height, color) -> str:
    """Create base64-encoded test image."""

def create_mock_florence_model() -> MagicMock:
    """Create mock Florence2Model with model/processor attributes."""
```

## Testing Patterns

### Mocking the Florence2Model

Tests mock the Florence2Model to avoid GPU requirements:

```python
from unittest.mock import MagicMock, patch

def mock_extract(image, prompt):
    if prompt == "<MORE_DETAILED_CAPTION>":
        return ("A delivery person...", 200.0)
    return ("", 0.0)

mock_model.extract = mock_extract
mock_model.extract_raw = mock_extract_raw

with patch("ai.florence.model.model", mock_model):
    response = client.post("/analyze-scene", json={"image": image_b64})
```

### Testing Parallel Execution

Verifies that DENSE_REGION_CAPTION and OCR_WITH_REGION run concurrently:

```python
@pytest.mark.asyncio
async def test_parallel_tasks_execute_concurrently():
    # Tasks with 100ms delay should complete in ~100ms total, not 200ms
    start = time.perf_counter()
    results = await asyncio.gather(mock_dense_regions(), mock_ocr_with_regions())
    elapsed = time.perf_counter() - start
    assert elapsed < 0.15  # Parallel execution confirmed
```

### Security Scene Types

Tests verify that security-relevant context is captured for Nemotron:

- **Person at door**: Detects dark clothing, nighttime, suspicious behavior
- **Delivery scene**: Captures Amazon branding, packages, uniforms
- **Vehicle scene**: Captures vehicle type, license plate text (OCR)
- **Animal scene**: Detects animal type, absence of owner

## Related Documentation

- `/ai/florence/AGENTS.md` - Florence-2 service documentation
- `/ai/florence/model.py` - Main server implementation
- `/ai/AGENTS.md` - AI pipeline overview
