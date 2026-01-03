"""Unit tests for florence_loader service.

Tests for the Florence-2-large vision-language model loader.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.florence_loader import load_florence_model

# =============================================================================
# Test load_florence_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_florence_model_import_error(monkeypatch):
    """Test load_florence_model handles ImportError."""
    import builtins
    import sys

    # Remove torch and transformers from imports if present
    modules_to_hide = ["torch", "transformers"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("torch", "transformers") or name.startswith(("torch.", "transformers.")):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="Florence-2 requires transformers and torch"):
            await load_florence_model("microsoft/Florence-2-large")
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_florence_model_runtime_error(monkeypatch):
    """Test load_florence_model handles RuntimeError."""
    import sys

    # Mock torch and transformers to exist but fail on processor load
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load Florence-2 model"):
        await load_florence_model("/nonexistent/path")


@pytest.mark.asyncio
async def test_load_florence_model_runtime_error_on_model_load(monkeypatch):
    """Test load_florence_model handles RuntimeError during model loading."""
    import sys

    # Mock torch and transformers
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.side_effect = RuntimeError(
        "Model weights not found"
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load Florence-2 model"):
        await load_florence_model("/nonexistent/path")


# =============================================================================
# Test load_florence_model success paths
# =============================================================================


@pytest.mark.asyncio
async def test_load_florence_model_success_cpu(monkeypatch):
    """Test load_florence_model success path with CPU."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    # Create mock model
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_florence_model("microsoft/Florence-2-large")

    # Should return tuple of (model, processor)
    assert isinstance(result, tuple)
    assert len(result) == 2
    model, processor = result
    assert model is mock_model
    assert processor is mock_processor

    # Verify model was moved to CPU and set to eval mode
    mock_model.to.assert_called_once_with("cpu")
    mock_model.eval.assert_called_once()

    # Verify model was loaded with float32 on CPU
    mock_transformers.AutoModelForCausalLM.from_pretrained.assert_called_once_with(
        "microsoft/Florence-2-large",
        torch_dtype="float32",
        trust_remote_code=True,
        attn_implementation="eager",
    )

    # Verify processor was loaded with trust_remote_code
    mock_transformers.AutoProcessor.from_pretrained.assert_called_once_with(
        "microsoft/Florence-2-large",
        trust_remote_code=True,
    )


@pytest.mark.asyncio
async def test_load_florence_model_success_cuda(monkeypatch):
    """Test load_florence_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.float16 = "float16"
    mock_torch.float32 = "float32"

    # Create mock model
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_florence_model("microsoft/Florence-2-large")

    # Should return tuple of (model, processor)
    assert isinstance(result, tuple)
    assert len(result) == 2

    # Verify model was moved to CUDA
    mock_model.to.assert_called_once_with("cuda")

    # Verify model was loaded with float16 on CUDA
    mock_transformers.AutoModelForCausalLM.from_pretrained.assert_called_once_with(
        "microsoft/Florence-2-large",
        torch_dtype="float16",
        trust_remote_code=True,
        attn_implementation="eager",
    )


# =============================================================================
# Test function signatures and types
# =============================================================================


def test_load_florence_model_is_async():
    """Test load_florence_model is an async function."""
    import inspect

    assert callable(load_florence_model)
    assert inspect.iscoroutinefunction(load_florence_model)


def test_load_florence_model_signature():
    """Test load_florence_model function signature."""
    import inspect

    sig = inspect.signature(load_florence_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_florence_in_model_zoo():
    """Test florence-2 is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "florence-2-large" in zoo

    config = zoo["florence-2-large"]
    assert config.name == "florence-2-large"
    assert config.category == "vision-language"
    # Florence-2 is currently disabled in model_zoo (enabled=False)
    assert config.enabled is False


def test_florence_model_config_load_fn():
    """Test florence-2 model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["florence-2-large"]
    assert config.load_fn is load_florence_model


def test_florence_model_vram_budget():
    """Test florence-2 model has reasonable VRAM budget."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["florence-2-large"]
    # Florence-2 should be around 1.2GB according to docs
    assert config.vram_mb > 0
    assert config.vram_mb <= 5000  # Should be less than 5GB


# =============================================================================
# Test docstring and documentation
# =============================================================================


def test_florence_loader_module_docstring():
    """Test florence_loader module has proper docstring."""
    from backend.services import florence_loader

    assert florence_loader.__doc__ is not None
    assert "Florence-2" in florence_loader.__doc__
    assert "vision-language" in florence_loader.__doc__.lower()


def test_florence_loader_function_docstring():
    """Test load_florence_model has proper docstring."""
    assert load_florence_model.__doc__ is not None
    assert "HuggingFace" in load_florence_model.__doc__
    assert "model_path" in load_florence_model.__doc__
    assert "Returns" in load_florence_model.__doc__
    assert "Raises" in load_florence_model.__doc__


# =============================================================================
# Test edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_load_florence_model_with_empty_path(monkeypatch):
    """Test load_florence_model handles empty model path."""
    import sys

    # Mock torch and transformers
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.side_effect = ValueError("Invalid model path")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load Florence-2 model"):
        await load_florence_model("")


@pytest.mark.asyncio
async def test_load_florence_model_returns_correct_types(monkeypatch):
    """Test load_florence_model returns correct types in tuple."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    # Create typed mock model and processor
    mock_model = MagicMock(name="MockFlorence2Model")
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    mock_processor = MagicMock(name="MockAutoProcessor")

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_florence_model("microsoft/Florence-2-large")

    # Verify the structure of the return value
    assert isinstance(result, tuple)
    _model, _processor = result
    # The model should have been set to eval mode
    assert mock_model.eval.called
    # The model should have been moved to a device
    assert mock_model.to.called


@pytest.mark.asyncio
async def test_load_florence_model_uses_eager_attention(monkeypatch):
    """Test load_florence_model uses eager attention implementation."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    await load_florence_model("microsoft/Florence-2-large")

    # Check that attn_implementation="eager" was passed
    call_kwargs = mock_transformers.AutoModelForCausalLM.from_pretrained.call_args
    assert call_kwargs.kwargs.get("attn_implementation") == "eager"


@pytest.mark.asyncio
async def test_load_florence_model_uses_trust_remote_code(monkeypatch):
    """Test load_florence_model uses trust_remote_code for custom model code."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForCausalLM.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    await load_florence_model("microsoft/Florence-2-large")

    # Check processor was loaded with trust_remote_code
    processor_call = mock_transformers.AutoProcessor.from_pretrained.call_args
    assert processor_call.kwargs.get("trust_remote_code") is True

    # Check model was loaded with trust_remote_code
    model_call = mock_transformers.AutoModelForCausalLM.from_pretrained.call_args
    assert model_call.kwargs.get("trust_remote_code") is True
