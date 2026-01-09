"""Unit tests for clip_loader service.

Tests for the CLIP ViT-L model loader for re-identification embeddings.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.clip_loader import CLIPLoader, load_clip_model

# =============================================================================
# Test load_clip_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_clip_model_import_error(monkeypatch):
    """Test load_clip_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers from imports if present
    modules_to_hide = ["transformers"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "transformers" or name.startswith("transformers."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="transformers package required"):
            await load_clip_model("openai/clip-vit-large-patch14")
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_clip_model_runtime_error_processor(monkeypatch):
    """Test load_clip_model handles RuntimeError during processor load."""
    import sys

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
        await load_clip_model("/nonexistent/path")


@pytest.mark.asyncio
async def test_load_clip_model_runtime_error_model(monkeypatch):
    """Test load_clip_model handles RuntimeError during model load."""
    import sys

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.side_effect = RuntimeError("Weights not found")

    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
        await load_clip_model("/nonexistent/path")


# =============================================================================
# Test load_clip_model success paths
# =============================================================================


@pytest.mark.asyncio
async def test_load_clip_model_success_cpu(monkeypatch):
    """Test load_clip_model success path without CUDA (CPU only)."""
    import sys

    # Create mock torch (simulating no CUDA available)
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    # Create mock processor and model
    mock_processor = MagicMock()
    mock_model = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_clip_model("openai/clip-vit-large-patch14")

    assert "model" in result
    assert "processor" in result
    assert result["model"] is mock_model
    assert result["processor"] is mock_processor

    # Verify from_pretrained was called
    mock_transformers.CLIPProcessor.from_pretrained.assert_called_once_with(
        "openai/clip-vit-large-patch14"
    )
    mock_transformers.CLIPModel.from_pretrained.assert_called_once_with(
        "openai/clip-vit-large-patch14"
    )

    # Model should NOT be moved to CUDA
    mock_model.cuda.assert_not_called()


@pytest.mark.asyncio
async def test_load_clip_model_success_cuda(monkeypatch):
    """Test load_clip_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    # Create mock model that supports cuda()
    mock_cuda_model = MagicMock()
    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_cuda_model

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_clip_model("openai/clip-vit-large-patch14")

    assert "model" in result
    assert "processor" in result
    mock_model.cuda.assert_called_once()


@pytest.mark.asyncio
async def test_load_clip_model_success_no_cuda(monkeypatch):
    """Test load_clip_model success path when CUDA is not available."""
    import sys

    # Create mock torch without CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    # Create mock model
    mock_model = MagicMock()

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_clip_model("openai/clip-vit-large-patch14")

    assert "model" in result
    assert "processor" in result
    # Model should not be moved to CUDA when not available
    mock_model.cuda.assert_not_called()


@pytest.mark.asyncio
async def test_load_clip_model_torch_import_error_handled(monkeypatch):
    """Test load_clip_model handles torch ImportError gracefully.

    The function imports torch inside the _load function to check CUDA availability.
    If torch import fails, it should still succeed with CPU-only model.
    """
    import sys

    # Create mock transformers
    mock_processor = MagicMock()
    mock_model = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    # Create mock torch that raises ImportError when cuda is checked
    # This simulates a partial torch installation without CUDA support
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.side_effect = ImportError("CUDA not available")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    # Should succeed - the function catches ImportError internally
    result = await load_clip_model("openai/clip-vit-large-patch14")

    assert "model" in result
    assert "processor" in result


# =============================================================================
# Test function signatures and types
# =============================================================================


def test_load_clip_model_is_async():
    """Test load_clip_model is an async function."""
    import inspect

    assert callable(load_clip_model)
    assert inspect.iscoroutinefunction(load_clip_model)


def test_load_clip_model_signature():
    """Test load_clip_model function signature."""
    import inspect

    sig = inspect.signature(load_clip_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_clip_in_model_zoo():
    """Test clip model is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "clip-vit-l" in zoo

    config = zoo["clip-vit-l"]
    assert config.name == "clip-vit-l"
    assert config.category == "embedding"
    assert config.enabled is True


def test_clip_model_config_load_fn():
    """Test clip model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["clip-vit-l"]
    assert config.load_fn is load_clip_model


def test_clip_model_vram_budget():
    """Test clip model has reasonable VRAM budget."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["clip-vit-l"]
    # CLIP ViT-L should be around 1-2GB
    assert config.vram_mb > 0
    assert config.vram_mb <= 3000  # Should be under 3GB


# =============================================================================
# Test docstring and documentation
# =============================================================================


def test_clip_loader_module_docstring():
    """Test clip_loader module has proper docstring."""
    from backend.services import clip_loader

    assert clip_loader.__doc__ is not None
    assert "CLIP" in clip_loader.__doc__
    assert "embedding" in clip_loader.__doc__.lower() or "re-identification" in clip_loader.__doc__


def test_clip_loader_function_docstring():
    """Test load_clip_model has proper docstring."""
    assert load_clip_model.__doc__ is not None
    assert "CLIP" in load_clip_model.__doc__
    assert "model_path" in load_clip_model.__doc__
    assert "Returns" in load_clip_model.__doc__
    assert "Raises" in load_clip_model.__doc__


# =============================================================================
# Test edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_load_clip_model_with_empty_path(monkeypatch):
    """Test load_clip_model handles empty model path."""
    import sys

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.side_effect = ValueError("Invalid model path")

    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load CLIP model"):
        await load_clip_model("")


@pytest.mark.asyncio
async def test_load_clip_model_returns_dict(monkeypatch):
    """Test load_clip_model returns dictionary with expected keys."""
    import sys

    # Create mock torch (no CUDA)
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_processor = MagicMock()
    mock_model = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_clip_model("openai/clip-vit-large-patch14")

    assert isinstance(result, dict)
    assert "model" in result
    assert "processor" in result
    assert len(result) == 2


@pytest.mark.asyncio
async def test_load_clip_model_local_path(monkeypatch):
    """Test load_clip_model works with local file paths."""
    import sys

    # Create mock torch (no CUDA)
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_processor = MagicMock()
    mock_model = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    local_path = "/export/ai_models/model-zoo/clip-vit-large"
    result = await load_clip_model(local_path)

    assert "model" in result
    assert "processor" in result

    # Verify the path was used
    mock_transformers.CLIPProcessor.from_pretrained.assert_called_once_with(local_path)
    mock_transformers.CLIPModel.from_pretrained.assert_called_once_with(local_path)


# =============================================================================
# Test embedding functionality (design verification)
# =============================================================================


def test_clip_model_outputs_embeddings():
    """Test that CLIP model produces 768-dimensional embeddings.

    This is a design verification test that checks the documentation
    matches expected behavior.
    """
    from backend.services import clip_loader

    # The docstring should mention 768-dimensional embeddings
    assert clip_loader.__doc__ is not None
    assert "768" in clip_loader.__doc__


def test_clip_supports_cosine_similarity():
    """Test that CLIP documentation mentions cosine similarity.

    Re-identification uses cosine similarity to match embeddings.
    """
    from backend.services import clip_loader

    assert clip_loader.__doc__ is not None
    assert "cosine" in clip_loader.__doc__.lower() or "similarity" in clip_loader.__doc__.lower()


# =============================================================================
# Test model loading uses correct transformers classes
# =============================================================================


@pytest.mark.asyncio
async def test_load_clip_model_uses_clip_classes(monkeypatch):
    """Test load_clip_model uses CLIPModel and CLIPProcessor."""
    import sys

    # Create mock torch (no CUDA)
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_processor = MagicMock()
    mock_model = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    await load_clip_model("test/model")

    # Verify correct transformers classes were used
    assert mock_transformers.CLIPProcessor.from_pretrained.called
    assert mock_transformers.CLIPModel.from_pretrained.called

    # Should NOT use AutoModel or other generic classes
    assert not hasattr(mock_transformers, "AutoModel") or not mock_transformers.AutoModel.called


# =============================================================================
# Test CLIPLoader class
# =============================================================================


class TestCLIPLoaderInit:
    """Tests for CLIPLoader initialization."""

    def test_init_with_model_path(self):
        """Test CLIPLoader initialization with model path."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        assert loader.model_path == "openai/clip-vit-large-patch14"
        assert loader._model is None

    def test_init_with_local_path(self):
        """Test CLIPLoader initialization with local path."""
        loader = CLIPLoader("/export/ai_models/model-zoo/clip-vit-large")

        assert loader.model_path == "/export/ai_models/model-zoo/clip-vit-large"
        assert loader._model is None


class TestCLIPLoaderProperties:
    """Tests for CLIPLoader properties."""

    def test_model_name_property(self):
        """Test model_name property returns correct identifier."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        assert loader.model_name == "clip-vit-l"

    def test_vram_mb_property(self):
        """Test vram_mb property returns correct VRAM estimate."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        assert loader.vram_mb == 800
        assert isinstance(loader.vram_mb, int)


class TestCLIPLoaderLoad:
    """Tests for CLIPLoader.load method."""

    @pytest.mark.asyncio
    async def test_load_default_device(self, monkeypatch):
        """Test load with default device (cuda)."""
        import sys

        # Create mock torch with CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock model that supports cuda()
        mock_cuda_model = MagicMock()
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_cuda_model

        # Create mock processor
        mock_processor = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load()

        assert "model" in result
        assert "processor" in result
        assert loader._model is not None
        assert loader._model == result

    @pytest.mark.asyncio
    async def test_load_cpu_device(self, monkeypatch):
        """Test load with CPU device."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock model that supports cpu()
        mock_cpu_model = MagicMock()
        mock_model = MagicMock()
        mock_model.cpu.return_value = mock_cpu_model
        mock_model.cuda.return_value = mock_model

        # Create mock processor
        mock_processor = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load(device="cpu")

        assert "model" in result
        assert "processor" in result
        # Model should be moved to CPU
        mock_model.cpu.assert_called_once()
        assert loader._model["model"] == mock_cpu_model

    @pytest.mark.asyncio
    async def test_load_specific_cuda_device(self, monkeypatch):
        """Test load with specific CUDA device (e.g., cuda:1)."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock model that supports cuda() and cuda(device_id)
        # First call is cuda() in load_clip_model, second is cuda(1) in CLIPLoader.load
        mock_cuda_model_default = MagicMock()
        mock_cuda_model_1 = MagicMock()
        mock_model = MagicMock()

        # Set up cuda() to be called twice: first with no args, then with device ID
        # The model returned from first cuda() call also needs to support cuda(device_id)
        cuda_calls = []

        def cuda_side_effect(*args):
            cuda_calls.append(args)
            if len(args) == 0:
                return mock_cuda_model_default
            return mock_cuda_model_1

        mock_model.cuda = MagicMock(side_effect=cuda_side_effect)
        # The model returned from first cuda() also needs cuda() method
        mock_cuda_model_default.cuda = MagicMock(side_effect=cuda_side_effect)

        # Create mock processor
        mock_processor = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load(device="cuda:1")

        assert "model" in result
        assert "processor" in result
        # Model should be moved to cuda() first in load_clip_model, then cuda(1) in CLIPLoader.load
        assert len(cuda_calls) == 2
        assert cuda_calls[0] == ()  # First call with no args
        assert cuda_calls[1] == (1,)  # Second call with device ID
        assert loader._model["model"] == mock_cuda_model_1

    @pytest.mark.asyncio
    async def test_load_cuda_device_parse_error(self, monkeypatch):
        """Test load handles ValueError when parsing cuda device ID."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False  # No CUDA for initial load

        # Create mock model that raises ValueError on invalid device
        mock_model = MagicMock()

        def cuda_side_effect(*args):
            if args and not isinstance(args[0], int):
                raise ValueError("Invalid device ID")
            return mock_model

        mock_model.cuda = MagicMock(side_effect=cuda_side_effect)

        # Create mock processor
        mock_processor = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        # The device parsing happens in CLIPLoader.load() line 138: int(device.split(":")[1])
        # If this raises ValueError, it's caught and model kept on default device
        result = await loader.load(device="cuda:invalid")

        assert "model" in result
        assert loader._model is not None

    @pytest.mark.asyncio
    async def test_load_torch_import_error_handled(self):
        """Test load handles ImportError when torch is not available for device move.

        This tests the ImportError handling in load() by mocking the import
        statement to raise ImportError for torch while allowing transformers.
        """
        import builtins
        from unittest.mock import patch

        # Create mock processor and model
        mock_processor = MagicMock()
        mock_model = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        # Track original import
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("No module named 'torch'")
            if name == "transformers" or name.startswith("transformers."):
                return mock_transformers
            return original_import(name, *args, **kwargs)

        # Pre-set the loader with a model to bypass the async loading
        loader = CLIPLoader("openai/clip-vit-large-patch14")
        loader._model = {"model": mock_model, "processor": mock_processor}

        # Test that device move handles ImportError gracefully
        with patch.object(builtins, "__import__", side_effect=mock_import):
            # Calling load again with different device should handle ImportError
            result = await loader.load(device="cpu")

        assert "model" in result
        assert loader._model is not None

    @pytest.mark.asyncio
    async def test_load_returns_same_model_dict(self, monkeypatch):
        """Test load returns the stored model dictionary."""
        import sys

        # Create mock torch (no CUDA)
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        result = await loader.load()

        assert result is loader._model


class TestCLIPLoaderUnload:
    """Tests for CLIPLoader.unload method."""

    @pytest.mark.asyncio
    async def test_unload_with_loaded_model(self, monkeypatch):
        """Test unload removes model and clears CUDA cache."""
        import sys

        # Create mock torch with CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.empty_cache = MagicMock()

        # Create mock model
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model

        # Create mock processor
        mock_processor = MagicMock()

        # Create mock transformers
        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        await loader.load()

        assert loader._model is not None

        await loader.unload()

        assert loader._model is None
        mock_torch.cuda.empty_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_unload_without_loaded_model(self):
        """Test unload does nothing when model is not loaded."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        assert loader._model is None

        # Should not raise
        await loader.unload()

        assert loader._model is None

    @pytest.mark.asyncio
    async def test_unload_cpu_only_environment(self, monkeypatch):
        """Test unload in CPU-only environment (no CUDA)."""
        import sys

        # Create mock torch without CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        await loader.load()

        assert loader._model is not None

        await loader.unload()

        assert loader._model is None
        # empty_cache should not be called when CUDA is not available
        mock_torch.cuda.empty_cache.assert_not_called()

    @pytest.mark.asyncio
    async def test_unload_torch_import_error_handled(self):
        """Test unload handles ImportError when torch is not available.

        This tests the ImportError handling in unload() by mocking the import
        statement to raise ImportError.
        """
        import builtins
        from unittest.mock import patch

        # Create a loader with a mock model
        loader = CLIPLoader("openai/clip-vit-large-patch14")
        mock_model = MagicMock()
        mock_processor = MagicMock()
        loader._model = {"model": mock_model, "processor": mock_processor}

        # Mock import to raise ImportError for torch
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("No module named 'torch'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            # Should not raise - ImportError is caught gracefully
            await loader.unload()

        # Model should still be cleared
        assert loader._model is None

    @pytest.mark.asyncio
    async def test_unload_deletes_model_and_processor_keys(self, monkeypatch):
        """Test unload deletes both model and processor keys."""
        import sys

        # Create mock torch (no CUDA)
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        await loader.load()

        assert "model" in loader._model
        assert "processor" in loader._model

        await loader.unload()

        assert loader._model is None

    @pytest.mark.asyncio
    async def test_unload_handles_missing_model_key(self):
        """Test unload handles case where model key is missing."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        # Manually set _model without model key
        loader._model = {"processor": MagicMock()}

        # Should not raise
        await loader.unload()

        assert loader._model is None

    @pytest.mark.asyncio
    async def test_unload_handles_missing_processor_key(self):
        """Test unload handles case where processor key is missing."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        # Manually set _model without processor key
        loader._model = {"model": MagicMock()}

        # Should not raise
        await loader.unload()

        assert loader._model is None


class TestCLIPLoaderIntegration:
    """Integration tests for CLIPLoader full workflow."""

    @pytest.mark.asyncio
    async def test_load_unload_cycle(self, monkeypatch):
        """Test complete load-unload cycle."""
        import sys

        # Create mock torch with CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.empty_cache = MagicMock()

        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model
        mock_processor = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")

        # Initial state
        assert loader._model is None

        # Load
        result = await loader.load()
        assert loader._model is not None
        assert result == loader._model

        # Unload
        await loader.unload()
        assert loader._model is None
        mock_torch.cuda.empty_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_unload_calls_safe(self, monkeypatch):
        """Test multiple unload calls don't cause errors."""
        import sys

        # Create mock torch (no CUDA)
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_model = MagicMock()
        mock_processor = MagicMock()

        mock_transformers = MagicMock()
        mock_transformers.CLIPProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.CLIPModel.from_pretrained.return_value = mock_model

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        loader = CLIPLoader("openai/clip-vit-large-patch14")
        await loader.load()
        await loader.unload()

        # Second unload should not raise
        await loader.unload()
        await loader.unload()

        assert loader._model is None

    @pytest.mark.asyncio
    async def test_loader_properties_work_before_load(self):
        """Test properties work before model is loaded."""
        loader = CLIPLoader("openai/clip-vit-large-patch14")

        # Should work even before load
        assert loader.model_name == "clip-vit-l"
        assert loader.vram_mb == 800
        assert loader.model_path == "openai/clip-vit-large-patch14"
