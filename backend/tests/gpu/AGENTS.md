# GPU Tests Directory

## Purpose

GPU tests validate the RT-DETRv2 detector client connectivity and basic inference on the self-hosted GPU runner (NVIDIA RTX A5500). These tests are designed to run WITHOUT database dependencies, testing only HTTP client functionality.

## Running Tests

```bash
# Run GPU tests (requires GPU services)
pytest backend/tests/gpu/ -v -m gpu

# All tests in directory
pytest backend/tests/gpu/ -v

# Skip if GPU not available
pytest backend/tests/gpu/ -v -m "gpu" --ignore-missing-gpu
```

## Test Files (1 total)

### `test_detector_integration.py`

GPU service integration tests:

| Test                                  | Description                                 |
| ------------------------------------- | ------------------------------------------- |
| `test_detector_service_health_check`  | RT-DETRv2 service responds to health checks |
| `test_detector_inference_basic`       | Basic object detection inference            |
| `test_detector_inference_performance` | Inference performance measurement           |
| `test_detector_multiple_images`       | Multiple images processed sequentially      |
| `test_nemotron_service_health_check`  | Nemotron LLM service health check           |
| `test_cuda_availability`              | CUDA availability via nvidia-smi            |
| `test_gpu_memory_available`           | GPU memory check (4GB minimum)              |
| `test_detector_handles_invalid_image` | Invalid image error handling                |
| `test_detector_concurrent_requests`   | Concurrent request handling                 |

## Test Markers

All tests use `@pytest.mark.gpu` marker for CI/CD filtering:

```python
@pytest.mark.gpu
@pytest.mark.asyncio
async def test_detector_service_health_check():
    ...
```

## Configuration

### Environment Variables

| Variable       | Default                 | Description              |
| -------------- | ----------------------- | ------------------------ |
| `RTDETR_URL`   | `http://localhost:8090` | RT-DETRv2 service URL    |
| `NEMOTRON_URL` | `http://localhost:8091` | Nemotron LLM service URL |

### Helper Functions

```python
def get_detector_url() -> str:
    return os.environ.get("RTDETR_URL", "http://localhost:8090")

def get_nemotron_url() -> str:
    return os.environ.get("NEMOTRON_URL", "http://localhost:8091")

async def check_detector_health(timeout: float = 5.0) -> bool:
    # Returns True if detector is healthy

async def check_nemotron_health(timeout: float = 5.0) -> bool:
    # Returns True if Nemotron is healthy

def check_cuda_available() -> bool:
    # Returns True if nvidia-smi works

def create_test_image(path: Path, size: tuple = (640, 480)) -> None:
    # Creates a test JPEG image

async def send_detection_request(image_path: str, timeout: float = 60.0) -> dict:
    # Sends image to detector and returns response
```

## Skip Conditions

Tests skip gracefully when:

- RT-DETRv2 service is not available
- Nemotron service is not available
- CUDA is not available
- nvidia-smi command not found
- Insufficient GPU memory (<4GB free)
- Required test images cannot be created

Example:

```python
if not await check_detector_health():
    pytest.skip(f"RT-DETRv2 detector not available at {get_detector_url()}")
```

## Performance Expectations

On NVIDIA RTX A5500 (24GB VRAM):

| Operation                    | Expected Time |
| ---------------------------- | ------------- |
| First inference (cold start) | < 5000ms      |
| Subsequent inferences        | < 200ms       |
| Health check                 | < 50ms        |

## Test Image Creation

Tests create temporary JPEG images using PIL:

```python
from PIL import Image

def create_test_image(path: Path, size: tuple = (640, 480)) -> None:
    img = Image.new("RGB", size, color="red")
    img.save(path, "JPEG")
```

Image sizes tested:

- 640x480 (VGA)
- 1280x720 (720p)
- 1920x1080 (1080p)

## Detection Response Format

Expected RT-DETRv2 response:

```json
{
  "detections": [
    {
      "class": "person",
      "confidence": 0.95,
      "bbox": [100, 150, 200, 300]
    }
  ]
}
```

## CI/CD Integration

These tests run on the self-hosted GPU runner via `.github/workflows/gpu-tests.yml`:

```yaml
- name: Run GPU tests
  run: pytest backend/tests/gpu/ -v -m gpu
  if: runner.os == 'Linux' && runner.labels contains 'gpu'
```

## Troubleshooting

### "RT-DETRv2 detector not available"

- Check RT-DETRv2 service is running on configured port
- Verify `RTDETR_URL` environment variable
- Check network connectivity to GPU runner

### "Nemotron service not available"

- Check Nemotron/llama.cpp service is running
- Verify `NEMOTRON_URL` environment variable
- Check GPU memory for LLM loading

### "CUDA not available"

- Verify nvidia-smi is installed
- Check NVIDIA drivers are loaded
- Verify GPU is accessible in container

### "Insufficient GPU memory"

- Free GPU memory (kill other processes)
- Minimum 4GB free required for RT-DETRv2
- Check for memory leaks from previous runs

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/ai/rtdetr/AGENTS.md` - RT-DETRv2 detection server
- `/ai/nemotron/AGENTS.md` - Nemotron LLM risk analysis
