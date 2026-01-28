# AI Common Infrastructure Tests

## Purpose

Unit tests for the TensorRT infrastructure shared across the Model Zoo. Tests verify TensorRT conversion utilities, inference base classes, and GPU detection functionality using mocks to run regardless of TensorRT availability.

## Directory Structure

```
ai/common/tests/
├── AGENTS.md                    # This file
├── __init__.py                  # Package marker
├── test_tensorrt_inference.py   # TensorRT inference base class tests
└── test_tensorrt_utils.py       # TensorRT utilities tests
```

## Key Files

### test_tensorrt_inference.py

Tests for the abstract base classes used by TensorRT-accelerated model implementations.

| Test Class                            | Purpose                                      |
| ------------------------------------- | -------------------------------------------- |
| `TestTensorRTInferenceBase`           | Backend selection and statistics tracking    |
| `TestTensorRTInferenceBaseAbstractMethods` | Abstract method requirements            |
| `TestTensorRTDetectionModel`          | Detection model specialized class            |
| `TestTensorRTClassificationModel`     | Classification model specialized class       |
| `TestEnvironmentVariableDefaults`     | TENSORRT_ENABLED, TENSORRT_PRECISION defaults|
| `TestNMSPostprocessing`               | Non-Maximum Suppression filtering            |
| `TestConcreteImplementation`          | Creating concrete model implementations      |

**Mock Classes:**
- `MockTensorRTInferenceModel`: Simulates TensorRT/PyTorch backend selection
- `MockDetectionModel`: Tests `format_detections()` and `apply_nms()`
- `MockClassificationModel`: Tests `get_top_predictions()` with softmax

**Key Tests:**
- Backend selection (PyTorch vs TensorRT)
- Inference statistics tracking
- Detection formatting with class names
- NMS confidence threshold filtering
- Top-k classification predictions

### test_tensorrt_utils.py

Tests for TensorRT conversion utilities and engine management.

| Test Class                  | Purpose                                        |
| --------------------------- | ---------------------------------------------- |
| `TestIsTensorRTAvailable`   | TensorRT installation detection                |
| `TestGetGpuComputeCapability` | GPU SM version detection (e.g., sm_86)       |
| `TestGetGpuName`            | GPU name string retrieval                      |
| `TestTensorRTConfig`        | Configuration dataclass and from_env()         |
| `TestTensorRTPrecision`     | Precision enum (FP32, FP16, INT8)              |
| `TestTensorRTConverter`     | ONNX to TensorRT conversion                    |
| `TestTensorRTEngine`        | Engine loading and inference wrapper           |
| `TestEnvironmentVariables`  | Environment variable defaults                  |
| `TestPackageExports`        | ai.common package __all__ exports              |

**Key Tests:**
- Graceful handling when TensorRT not installed
- GPU compute capability format (sm_XX)
- Config dataclass default and custom values
- Config from environment variables
- Precision enum string comparison
- Converter initialization without TensorRT
- Engine path format with SM version and precision
- File hash computation for cache keys

## Running Tests

```bash
# Run all common tests
uv run pytest ai/common/tests/ -v

# Run specific test file
uv run pytest ai/common/tests/test_tensorrt_utils.py -v

# Run specific test class
uv run pytest ai/common/tests/test_tensorrt_inference.py::TestTensorRTDetectionModel -v

# Run with verbose output
uv run pytest ai/common/tests/ -v --tb=short

# Run tests requiring PyTorch torchvision
TORCH_AVAILABLE=true uv run pytest ai/common/tests/ -v -k "nms"
```

## Test Patterns

### Mock-Based Testing

Tests use mocks to run without TensorRT installed:

```python
def test_initialization_without_tensorrt(self):
    with patch("ai.common.tensorrt_utils.is_tensorrt_available", return_value=False):
        with pytest.raises(ImportError, match="TensorRT is not available"):
            TensorRTConverter()
```

### Environment Variable Testing

Tests modify and restore environment variables:

```python
def test_from_env_custom(self):
    os.environ["TENSORRT_ENABLED"] = "false"
    os.environ["TENSORRT_PRECISION"] = "int8"
    try:
        config = TensorRTConfig.from_env()
        assert isinstance(config, TensorRTConfig)
    finally:
        del os.environ["TENSORRT_ENABLED"]
        del os.environ["TENSORRT_PRECISION"]
```

### Abstract Class Testing

Verifies abstract methods cannot be skipped:

```python
def test_abstract_class_cannot_instantiate(self):
    from ai.common.tensorrt_inference import TensorRTInferenceBase

    with pytest.raises(TypeError, match="abstract"):
        TensorRTInferenceBase(model_name="test")
```

### Concrete Implementation Testing

Tests creating concrete implementations:

```python
class ConcreteModel(TensorRTInferenceBase[np.ndarray, np.ndarray]):
    def _init_pytorch(self):
        self.pytorch_model = lambda x: {"output": x["input"] * 2}

    def _init_tensorrt(self, onnx_path, precision):
        raise ImportError("TensorRT not available")

    def preprocess(self, inputs):
        return {"input": inputs}

    def postprocess(self, outputs):
        return outputs["output"]
```

## Environment Variables

Tests verify these environment variable defaults:

| Variable                      | Default                   | Description                        |
| ----------------------------- | ------------------------- | ---------------------------------- |
| `TENSORRT_ENABLED`            | `True`                    | Global TensorRT toggle             |
| `TENSORRT_PRECISION`          | `"fp16"`                  | Default precision mode             |
| `TENSORRT_CACHE_DIR`          | `"models/tensorrt_cache"` | Engine cache directory             |
| `TENSORRT_MAX_WORKSPACE_SIZE` | `1073741824` (1GB)        | Max workspace memory               |
| `TENSORRT_VERBOSE`            | `False`                   | Enable verbose logging             |

## Conditional Tests

Some tests require specific environments:

```python
@pytest.mark.skipif(
    os.environ.get("TORCH_AVAILABLE", "true").lower() != "true",
    reason="PyTorch with torchvision not available",
)
def test_apply_nms_filters_low_confidence(self):
    ...

@pytest.mark.skipif(
    not os.environ.get("CUDA_VISIBLE_DEVICES", "").strip(),
    reason="CUDA not configured in environment",
)
def test_sm_version_format(self):
    ...

@pytest.mark.skipif(
    os.environ.get("TENSORRT_AVAILABLE", "false").lower() != "true",
    reason="TensorRT not available",
)
def test_initialization_with_tensorrt(self):
    ...
```

## Entry Points

1. **Utilities tests**: `test_tensorrt_utils.py`
2. **Inference tests**: `test_tensorrt_inference.py`
3. **Parent module**: `ai/common/AGENTS.md`
4. **TensorRT utilities**: `ai/common/tensorrt_utils.py`
5. **Inference base classes**: `ai/common/tensorrt_inference.py`

## Related Documentation

- Parent module documentation: `ai/common/AGENTS.md`
- Model implementations: `ai/enrichment-light/models/`
- Export scripts: `ai/enrichment/scripts/`
