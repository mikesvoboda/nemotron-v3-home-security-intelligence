# Model Loader Migration Guide

## Overview

This document describes the migration of model loaders to use the `ModelLoaderBase` abstract base class. This establishes a consistent interface across all 14+ model loaders in the Model Zoo.

## Completed Work

### ✅ Phase 1: Abstract Base Class (NEM-1609)

**Created:** `/backend/services/model_loader_base.py`

- Abstract base class with required interface:
  - `model_name` property: Unique model identifier
  - `vram_mb` property: Estimated VRAM usage
  - `load(device)` method: Load model and return instance
  - `unload()` method: Unload model and free GPU memory
- Generic type support: `ModelLoaderBase[T]` where T is the model type
- Comprehensive test coverage: 24 tests in `test_model_loader_base.py`

### ✅ Phase 2: Reference Implementation

**Updated:** `/backend/services/clip_loader.py`

- Added `CLIPLoader` class implementing `ModelLoaderBase[dict[str, Any]]`
- Maintained backward compatibility with `load_clip_model()` function
- Class wraps functional interface for clean migration path
- All existing tests pass (20 tests)

## Migration Pattern

### Before (Functional Pattern)

```python
# backend/services/example_loader.py
async def load_example_model(model_path: str) -> Any:
    """Load example model."""
    # Loading logic here
    return model
```

### After (Class-Based Pattern)

```python
# backend/services/example_loader.py
from backend.services.model_loader_base import ModelLoaderBase

# Keep existing function for backward compatibility
async def load_example_model(model_path: str) -> Any:
    """Load example model."""
    # Loading logic here (unchanged)
    return model

# Add new class-based interface
class ExampleLoader(ModelLoaderBase[Any]):
    """Class-based loader implementing ModelLoaderBase."""

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._model: Any | None = None

    @property
    def model_name(self) -> str:
        return "example-model"

    @property
    def vram_mb(self) -> int:
        return 800  # Estimated VRAM usage

    async def load(self, device: str = "cuda") -> Any:
        self._model = await load_example_model(self.model_path)
        # Handle device placement if needed
        return self._model

    async def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            # Clear CUDA cache if applicable
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
```

## Remaining Loaders to Migrate

| Loader                         | Model Name                     | VRAM (MB) | Status      |
| ------------------------------ | ------------------------------ | --------- | ----------- |
| `clip_loader.py`               | clip-vit-l                     | 800       | ✅ Complete |
| `florence_loader.py`           | florence-2-large               | 1200      | Pending     |
| `yolo_world_loader.py`         | yolo-world-s                   | 1500      | Pending     |
| `vitpose_loader.py`            | vitpose-small                  | 1500      | Pending     |
| `depth_anything_loader.py`     | depth-anything-v2-small        | 150       | Pending     |
| `violence_loader.py`           | violence-detection             | 500       | Pending     |
| `weather_loader.py`            | weather-classification         | 200       | Pending     |
| `segformer_loader.py`          | segformer-b2-clothes           | 1500      | Pending     |
| `xclip_loader.py`              | xclip-base                     | 2000      | Pending     |
| `fashion_clip_loader.py`       | fashion-clip                   | 500       | Pending     |
| `image_quality_loader.py`      | brisque-quality                | 0         | Pending     |
| `vehicle_classifier_loader.py` | vehicle-segment-classification | 1500      | Pending     |
| `vehicle_damage_loader.py`     | vehicle-damage-detection       | 2000      | Pending     |
| `pet_classifier_loader.py`     | pet-classifier                 | 200       | Pending     |

## Benefits

1. **Consistent Interface:** All loaders expose the same methods and properties
2. **Type Safety:** Generic type parameter provides compile-time type checking
3. **Documentation:** Clear contract for implementing new loaders
4. **Backward Compatible:** Existing functional interfaces remain unchanged
5. **Future-Proof:** Easy to add new loaders following the pattern

## Testing Requirements

For each migrated loader:

1. Add class to the loader module (alongside existing function)
2. Verify existing functional tests still pass
3. Add class-based tests following `test_clip_loader.py` pattern
4. Test instantiation, load, unload, and property access
5. Verify VRAM estimates match Model Zoo registry

## Example Tests

```python
@pytest.mark.asyncio
async def test_example_loader_class():
    """Test ExampleLoader class interface."""
    loader = ExampleLoader("/path/to/model")

    # Check properties
    assert loader.model_name == "example-model"
    assert loader.vram_mb == 800

    # Mock the functional loader
    with patch("backend.services.example_loader.load_example_model") as mock:
        mock.return_value = {"loaded": True}

        # Load model
        model = await loader.load("cuda")
        assert model["loaded"] is True

        # Unload model
        await loader.unload()
        assert loader._model is None
```

## Migration Checklist

For each loader:

- [ ] Add import: `from backend.services.model_loader_base import ModelLoaderBase`
- [ ] Create class: `class XLoader(ModelLoaderBase[ReturnType])`
- [ ] Implement `__init__(self, model_path: str)`
- [ ] Implement `model_name` property (return model registry name)
- [ ] Implement `vram_mb` property (return VRAM estimate)
- [ ] Implement `load(device)` method (call functional loader)
- [ ] Implement `unload()` method (cleanup + CUDA cache clear)
- [ ] Add class-based tests
- [ ] Run full test suite
- [ ] Update Model Zoo registry if needed

## References

- Abstract base class: `/backend/services/model_loader_base.py`
- Base class tests: `/backend/tests/unit/services/test_model_loader_base.py`
- Reference implementation: `/backend/services/clip_loader.py` (CLIPLoader class)
- Reference tests: `/backend/tests/unit/services/test_clip_loader.py`
- Model Zoo registry: `/backend/services/model_zoo.py`
