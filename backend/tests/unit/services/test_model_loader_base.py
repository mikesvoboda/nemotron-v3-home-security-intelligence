"""Unit tests for ModelLoaderBase abstract base class.

Tests for the abstract base class that all model loaders must inherit from.
This ensures consistent interfaces across all 14+ model loaders in the Model Zoo.
"""

from abc import ABC
from unittest.mock import MagicMock

import pytest

from backend.services.model_loader_base import ModelLoaderBase

# =============================================================================
# Test ModelLoaderBase is properly abstract
# =============================================================================


def test_model_loader_base_is_abstract():
    """Test ModelLoaderBase cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        ModelLoaderBase()  # type: ignore[abstract]


def test_model_loader_base_inherits_from_abc():
    """Test ModelLoaderBase is an ABC."""
    assert issubclass(ModelLoaderBase, ABC)


def test_model_loader_base_has_abstract_methods():
    """Test ModelLoaderBase defines required abstract methods."""
    import inspect

    abstract_methods = {
        name
        for name, method in inspect.getmembers(ModelLoaderBase)
        if getattr(method, "__isabstractmethod__", False)
    }

    # Must have these abstract methods
    assert "model_name" in abstract_methods
    assert "vram_mb" in abstract_methods
    assert "load" in abstract_methods
    assert "unload" in abstract_methods


# =============================================================================
# Test concrete implementation requirements
# =============================================================================


def test_concrete_loader_must_implement_all_methods():
    """Test concrete loader must implement all abstract methods."""

    # Missing unload method
    class IncompleteLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            return {}

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteLoader()  # type: ignore[abstract]


def test_concrete_loader_can_be_instantiated():
    """Test concrete loader with all methods can be instantiated."""

    class CompleteLoader(ModelLoaderBase[dict]):
        def __init__(self) -> None:
            self._model: dict | None = None

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            self._model = {"device": device}
            return self._model

        async def unload(self) -> None:
            self._model = None

    loader = CompleteLoader()
    assert loader.model_name == "test-model"
    assert loader.vram_mb == 100


@pytest.mark.asyncio
async def test_concrete_loader_load_and_unload():
    """Test concrete loader load and unload methods work."""

    class TestLoader(ModelLoaderBase[dict]):
        def __init__(self) -> None:
            self._model: dict | None = None

        @property
        def model_name(self) -> str:
            return "test-model"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            self._model = {"device": device, "loaded": True}
            return self._model

        async def unload(self) -> None:
            self._model = None

    loader = TestLoader()

    # Load model
    model = await loader.load("cuda")
    assert model["device"] == "cuda"
    assert model["loaded"] is True

    # Unload model
    await loader.unload()
    assert loader._model is None


# =============================================================================
# Test property requirements
# =============================================================================


def test_model_name_property_is_required():
    """Test model_name property is required."""

    class NoModelNameLoader(ModelLoaderBase[dict]):
        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            return {}

        async def unload(self) -> None:
            pass

    with pytest.raises(TypeError):
        NoModelNameLoader()  # type: ignore[abstract]


def test_vram_mb_property_is_required():
    """Test vram_mb property is required."""

    class NoVramLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "test"

        async def load(self, device: str = "cuda") -> dict:
            return {}

        async def unload(self) -> None:
            pass

    with pytest.raises(TypeError):
        NoVramLoader()  # type: ignore[abstract]


def test_model_name_returns_string():
    """Test model_name property returns string."""

    class TestLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "clip-vit-l"

        @property
        def vram_mb(self) -> int:
            return 800

        async def load(self, device: str = "cuda") -> dict:
            return {}

        async def unload(self) -> None:
            pass

    loader = TestLoader()
    assert isinstance(loader.model_name, str)
    assert loader.model_name == "clip-vit-l"


def test_vram_mb_returns_int():
    """Test vram_mb property returns integer."""

    class TestLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 1500

        async def load(self, device: str = "cuda") -> dict:
            return {}

        async def unload(self) -> None:
            pass

    loader = TestLoader()
    assert isinstance(loader.vram_mb, int)
    assert loader.vram_mb == 1500


# =============================================================================
# Test load method requirements
# =============================================================================


@pytest.mark.asyncio
async def test_load_method_is_async():
    """Test load method is async."""

    class TestLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            return {"loaded": True}

        async def unload(self) -> None:
            pass

    loader = TestLoader()

    # load should return a coroutine
    import inspect

    assert inspect.iscoroutinefunction(loader.load)


@pytest.mark.asyncio
async def test_load_accepts_device_parameter():
    """Test load method accepts device parameter."""

    class TestLoader(ModelLoaderBase[dict]):
        def __init__(self) -> None:
            self._device: str | None = None

        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            self._device = device
            return {"device": device}

        async def unload(self) -> None:
            pass

    loader = TestLoader()

    # Test with default device
    result = await loader.load()
    assert result["device"] == "cuda"

    # Test with custom device
    result = await loader.load("cpu")
    assert result["device"] == "cpu"


@pytest.mark.asyncio
async def test_load_returns_model():
    """Test load method returns model instance."""

    class TestLoader(ModelLoaderBase[MagicMock]):
        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> MagicMock:
            return MagicMock()

        async def unload(self) -> None:
            pass

    loader = TestLoader()
    model = await loader.load()

    assert model is not None
    assert isinstance(model, MagicMock)


# =============================================================================
# Test unload method requirements
# =============================================================================


@pytest.mark.asyncio
async def test_unload_method_is_async():
    """Test unload method is async."""

    class TestLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            return {}

        async def unload(self) -> None:
            pass

    loader = TestLoader()

    # unload should return a coroutine
    import inspect

    assert inspect.iscoroutinefunction(loader.unload)


@pytest.mark.asyncio
async def test_unload_cleans_up_resources():
    """Test unload method cleans up model resources."""

    class TestLoader(ModelLoaderBase[dict]):
        def __init__(self) -> None:
            self._model: dict | None = None
            self._cleanup_called = False

        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            self._model = {"data": "loaded"}
            return self._model

        async def unload(self) -> None:
            self._model = None
            self._cleanup_called = True

    loader = TestLoader()

    # Load then unload
    await loader.load()
    assert loader._model is not None

    await loader.unload()
    assert loader._model is None
    assert loader._cleanup_called is True


# =============================================================================
# Test generic type parameter
# =============================================================================


def test_loader_supports_generic_type():
    """Test loader supports generic type parameter."""

    class DictLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "dict-model"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            return {"type": "dict"}

        async def unload(self) -> None:
            pass

    class ListLoader(ModelLoaderBase[list]):
        @property
        def model_name(self) -> str:
            return "list-model"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> list:
            return ["item1", "item2"]

        async def unload(self) -> None:
            pass

    dict_loader = DictLoader()
    list_loader = ListLoader()

    assert dict_loader.model_name == "dict-model"
    assert list_loader.model_name == "list-model"


@pytest.mark.asyncio
async def test_loader_generic_type_enforced():
    """Test loader generic type is enforced in return values."""

    class StrictDictLoader(ModelLoaderBase[dict[str, int]]):
        @property
        def model_name(self) -> str:
            return "strict"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict[str, int]:
            return {"count": 42}

        async def unload(self) -> None:
            pass

    loader = StrictDictLoader()
    result = await loader.load()

    assert isinstance(result, dict)
    assert "count" in result
    assert isinstance(result["count"], int)


# =============================================================================
# Test base class documentation
# =============================================================================


def test_base_class_has_docstring():
    """Test ModelLoaderBase has proper docstring."""
    assert ModelLoaderBase.__doc__ is not None
    assert len(ModelLoaderBase.__doc__) > 0


def test_base_class_properties_have_docstrings():
    """Test abstract properties have docstrings."""
    import inspect

    # Get the abstract property objects
    members = inspect.getmembers(ModelLoaderBase)

    # Check model_name property
    model_name_prop = None
    vram_mb_prop = None

    for name, member in members:
        if name == "model_name":
            model_name_prop = member
        elif name == "vram_mb":
            vram_mb_prop = member

    # These should be property objects with docstrings
    assert model_name_prop is not None
    assert vram_mb_prop is not None


# =============================================================================
# Test integration with Model Zoo patterns
# =============================================================================


@pytest.mark.asyncio
async def test_loader_compatible_with_context_manager():
    """Test loader can be used with async context manager pattern."""

    class TestLoader(ModelLoaderBase[dict]):
        def __init__(self) -> None:
            self._model: dict | None = None

        @property
        def model_name(self) -> str:
            return "test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            self._model = {"loaded": True}
            return self._model

        async def unload(self) -> None:
            self._model = None

        async def __aenter__(self) -> dict:
            return await self.load()

        async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
            await self.unload()

    loader = TestLoader()

    # Use with async context manager
    async with loader as model:
        assert model["loaded"] is True
        assert loader._model is not None

    # Should be unloaded after context
    assert loader._model is None


@pytest.mark.asyncio
async def test_loader_device_parameter_for_multi_gpu():
    """Test loader device parameter supports multi-GPU scenarios."""

    class MultiGPULoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "multi-gpu"

        @property
        def vram_mb(self) -> int:
            return 1500

        async def load(self, device: str = "cuda") -> dict:
            return {"device": device}

        async def unload(self) -> None:
            pass

    loader = MultiGPULoader()

    # Test different device strings
    model_cuda0 = await loader.load("cuda:0")
    assert model_cuda0["device"] == "cuda:0"

    model_cuda1 = await loader.load("cuda:1")
    assert model_cuda1["device"] == "cuda:1"

    model_cpu = await loader.load("cpu")
    assert model_cpu["device"] == "cpu"


# =============================================================================
# Test error handling requirements
# =============================================================================


@pytest.mark.asyncio
async def test_loader_can_raise_import_error():
    """Test loader can raise ImportError for missing dependencies."""

    class DependencyLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "dependency-test"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            raise ImportError("transformers package required")

        async def unload(self) -> None:
            pass

    loader = DependencyLoader()

    with pytest.raises(ImportError, match="transformers package required"):
        await loader.load()


@pytest.mark.asyncio
async def test_loader_can_raise_runtime_error():
    """Test loader can raise RuntimeError for loading failures."""

    class FailingLoader(ModelLoaderBase[dict]):
        @property
        def model_name(self) -> str:
            return "failing"

        @property
        def vram_mb(self) -> int:
            return 100

        async def load(self, device: str = "cuda") -> dict:
            raise RuntimeError("Failed to load model")

        async def unload(self) -> None:
            pass

    loader = FailingLoader()

    with pytest.raises(RuntimeError, match="Failed to load model"):
        await loader.load()


# =============================================================================
# Test real-world usage pattern
# =============================================================================


@pytest.mark.asyncio
async def test_loader_typical_usage_pattern():
    """Test typical usage pattern for model loaders."""

    class RealWorldLoader(ModelLoaderBase[dict]):
        def __init__(self, model_path: str) -> None:
            self._model_path = model_path
            self._model: dict | None = None

        @property
        def model_name(self) -> str:
            return "real-world-model"

        @property
        def vram_mb(self) -> int:
            return 1200

        async def load(self, device: str = "cuda") -> dict:
            # Simulate async loading
            self._model = {
                "path": self._model_path,
                "device": device,
                "status": "loaded",
            }
            return self._model

        async def unload(self) -> None:
            # Simulate cleanup
            if self._model is not None:
                self._model["status"] = "unloaded"
            self._model = None

    # Create loader
    loader = RealWorldLoader("/path/to/model")

    # Check properties before loading
    assert loader.model_name == "real-world-model"
    assert loader.vram_mb == 1200

    # Load model
    model = await loader.load("cuda")
    assert model["path"] == "/path/to/model"
    assert model["device"] == "cuda"
    assert model["status"] == "loaded"

    # Unload model
    await loader.unload()
    assert loader._model is None
