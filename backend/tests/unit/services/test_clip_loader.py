"""Unit tests for clip_loader service.

Tests for the CLIP ViT-L model loader for re-identification embeddings.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.clip_loader import load_clip_model

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
