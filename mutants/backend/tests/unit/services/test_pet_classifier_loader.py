"""Unit tests for pet_classifier_loader service.

Tests for the ResNet-18 cat/dog classifier model loader and classification functions.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.pet_classifier_loader import (
    PET_LABELS,
    PetClassificationResult,
    classify_pet,
    format_pet_for_nemotron,
    is_likely_pet_false_positive,
    load_pet_classifier_model,
)

# =============================================================================
# Test PetClassificationResult dataclass
# =============================================================================


def test_pet_classification_result_creation():
    """Test PetClassificationResult dataclass creation."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.92,
        cat_score=0.92,
        dog_score=0.08,
        is_household_pet=True,
    )

    assert result.animal_type == "cat"
    assert result.confidence == 0.92
    assert result.cat_score == 0.92
    assert result.dog_score == 0.08
    assert result.is_household_pet is True


def test_pet_classification_result_dog():
    """Test PetClassificationResult for dog."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.88,
        cat_score=0.12,
        dog_score=0.88,
        is_household_pet=True,
    )

    assert result.animal_type == "dog"
    assert result.confidence == 0.88
    assert result.dog_score > result.cat_score


def test_pet_classification_result_default_household_pet():
    """Test PetClassificationResult default is_household_pet value."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.95,
        cat_score=0.95,
        dog_score=0.05,
    )

    # Default should be True
    assert result.is_household_pet is True


def test_pet_classification_result_to_dict():
    """Test PetClassificationResult.to_dict() method."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.87,
        cat_score=0.13,
        dog_score=0.87,
        is_household_pet=True,
    )

    d = result.to_dict()

    assert d["animal_type"] == "dog"
    assert d["confidence"] == 0.87
    assert d["cat_score"] == 0.13
    assert d["dog_score"] == 0.87
    assert d["is_household_pet"] is True


def test_pet_classification_result_to_dict_all_keys():
    """Test PetClassificationResult.to_dict() contains all expected keys."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.90,
        cat_score=0.90,
        dog_score=0.10,
    )

    d = result.to_dict()

    expected_keys = {"animal_type", "confidence", "cat_score", "dog_score", "is_household_pet"}
    assert set(d.keys()) == expected_keys


def test_pet_classification_result_to_context_string():
    """Test PetClassificationResult.to_context_string() method."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.92,
        cat_score=0.92,
        dog_score=0.08,
    )

    context = result.to_context_string()

    assert "Household pet detected" in context
    assert "cat" in context
    assert "92%" in context


def test_pet_classification_result_to_context_string_dog():
    """Test PetClassificationResult.to_context_string() for dog."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.85,
        cat_score=0.15,
        dog_score=0.85,
    )

    context = result.to_context_string()

    assert "dog" in context
    assert "85%" in context


# =============================================================================
# Test PET_LABELS constant
# =============================================================================


def test_pet_labels_defined():
    """Test PET_LABELS constant is defined correctly."""
    assert PET_LABELS == ["cat", "dog"]
    assert len(PET_LABELS) == 2


def test_pet_labels_immutable_list():
    """Test PET_LABELS is a list."""
    assert isinstance(PET_LABELS, list)


# =============================================================================
# Test is_likely_pet_false_positive
# =============================================================================


def test_is_likely_pet_false_positive_high_confidence():
    """Test is_likely_pet_false_positive with high confidence."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.92,
        cat_score=0.92,
        dog_score=0.08,
        is_household_pet=True,
    )

    assert is_likely_pet_false_positive(result) is True


def test_is_likely_pet_false_positive_low_confidence():
    """Test is_likely_pet_false_positive with low confidence."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.60,  # Below default 0.85 threshold
        cat_score=0.40,
        dog_score=0.60,
        is_household_pet=True,
    )

    assert is_likely_pet_false_positive(result) is False


def test_is_likely_pet_false_positive_none_result():
    """Test is_likely_pet_false_positive with None result."""
    assert is_likely_pet_false_positive(None) is False


def test_is_likely_pet_false_positive_custom_threshold():
    """Test is_likely_pet_false_positive with custom confidence threshold."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.75,
        cat_score=0.75,
        dog_score=0.25,
        is_household_pet=True,
    )

    # Default threshold is 0.85
    assert is_likely_pet_false_positive(result) is False

    # Custom threshold of 0.70
    assert is_likely_pet_false_positive(result, confidence_threshold=0.70) is True


def test_is_likely_pet_false_positive_exact_threshold():
    """Test is_likely_pet_false_positive at exact threshold boundary."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.85,  # Exactly at threshold
        cat_score=0.15,
        dog_score=0.85,
        is_household_pet=True,
    )

    assert is_likely_pet_false_positive(result, confidence_threshold=0.85) is True


def test_is_likely_pet_false_positive_not_household_pet():
    """Test is_likely_pet_false_positive when is_household_pet is False."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.95,
        cat_score=0.95,
        dog_score=0.05,
        is_household_pet=False,  # Not a household pet
    )

    # Should return False because is_household_pet is False
    assert is_likely_pet_false_positive(result) is False


# =============================================================================
# Test format_pet_for_nemotron
# =============================================================================


def test_format_pet_for_nemotron_high_confidence():
    """Test format_pet_for_nemotron with high confidence."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.92,
        cat_score=0.92,
        dog_score=0.08,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    assert "Pet classification:" in formatted
    assert "cat" in formatted
    assert "92%" in formatted
    assert "low security risk" in formatted


def test_format_pet_for_nemotron_medium_confidence():
    """Test format_pet_for_nemotron with medium confidence."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.78,  # Between 0.70 and 0.85
        cat_score=0.22,
        dog_score=0.78,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    assert "dog" in formatted
    assert "78%" in formatted
    assert "likely household pet" in formatted or "minimal security concern" in formatted


def test_format_pet_for_nemotron_low_confidence():
    """Test format_pet_for_nemotron with low confidence."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.55,  # Below 0.70
        cat_score=0.55,
        dog_score=0.45,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    assert "cat" in formatted
    assert "55%" in formatted
    assert "uncertain" in formatted or "wildlife" in formatted


def test_format_pet_for_nemotron_none_result():
    """Test format_pet_for_nemotron with None result."""
    formatted = format_pet_for_nemotron(None)

    assert "Pet classification:" in formatted
    assert "unknown" in formatted
    assert "unavailable" in formatted


def test_format_pet_for_nemotron_confidence_boundary_85():
    """Test format_pet_for_nemotron at 85% confidence boundary."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.85,  # Exactly at high confidence boundary
        cat_score=0.15,
        dog_score=0.85,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    assert "low security risk" in formatted


def test_format_pet_for_nemotron_confidence_boundary_70():
    """Test format_pet_for_nemotron at 70% confidence boundary."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.70,  # Exactly at medium confidence boundary
        cat_score=0.70,
        dog_score=0.30,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    assert "likely household pet" in formatted or "minimal security concern" in formatted


# =============================================================================
# Test load_pet_classifier_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_pet_classifier_model_import_error(monkeypatch):
    """Test load_pet_classifier_model handles ImportError."""
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
        with pytest.raises(ImportError, match="Pet classifier requires transformers and torch"):
            await load_pet_classifier_model("/fake/path")
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_pet_classifier_model_runtime_error(monkeypatch):
    """Test load_pet_classifier_model handles RuntimeError."""
    import sys

    # Mock torch and transformers
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.side_effect = RuntimeError(
        "Model not found"
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load pet classifier model"):
        await load_pet_classifier_model("/nonexistent/path")


@pytest.mark.asyncio
async def test_load_pet_classifier_model_runtime_error_on_model(monkeypatch):
    """Test load_pet_classifier_model handles RuntimeError during model load."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_processor = MagicMock()

    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForImageClassification.from_pretrained.side_effect = RuntimeError(
        "Weights not found"
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load pet classifier model"):
        await load_pet_classifier_model("/nonexistent/path")


# =============================================================================
# Test load_pet_classifier_model success paths
# =============================================================================


@pytest.mark.asyncio
async def test_load_pet_classifier_model_success_cpu(monkeypatch):
    """Test load_pet_classifier_model success path with CPU."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    # Create mock model
    mock_model = MagicMock()
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForImageClassification.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_pet_classifier_model("/test/model/path")

    assert "model" in result
    assert "processor" in result
    assert result["model"] is mock_model
    assert result["processor"] is mock_processor
    mock_model.eval.assert_called_once()


@pytest.mark.asyncio
async def test_load_pet_classifier_model_success_cuda(monkeypatch):
    """Test load_pet_classifier_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    # Create mock model that supports cuda()
    mock_cuda_model = MagicMock()
    mock_cuda_model.half.return_value = mock_cuda_model
    mock_cuda_model.eval.return_value = None

    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_cuda_model

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForImageClassification.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_pet_classifier_model("/test/model/path")

    assert "model" in result
    assert "processor" in result
    mock_model.cuda.assert_called_once()
    mock_cuda_model.half.assert_called_once()  # Should use fp16 on CUDA


# =============================================================================
# Test classify_pet
# =============================================================================


def test_classify_pet_is_async():
    """Test classify_pet is an async function."""
    import inspect

    assert callable(classify_pet)
    assert inspect.iscoroutinefunction(classify_pet)


def test_classify_pet_signature():
    """Test classify_pet function signature."""
    import inspect

    sig = inspect.signature(classify_pet)
    params = list(sig.parameters.keys())

    assert "model_dict" in params
    assert "image" in params


@pytest.mark.asyncio
async def test_classify_pet_runtime_error():
    """Test classify_pet handles runtime errors."""
    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    # Create model dict with model that raises error
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    model_dict = {
        "model": mock_model,
        "processor": MagicMock(),
    }

    with pytest.raises(RuntimeError, match="Pet classification failed"):
        await classify_pet(model_dict, test_image)


@pytest.mark.asyncio
async def test_classify_pet_success(monkeypatch):
    """Test classify_pet success path."""
    import sys

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    # Create mock torch
    mock_torch = MagicMock()

    # Create mock no_grad context manager
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    # Create mock probabilities
    mock_probs = MagicMock()
    mock_argmax = MagicMock()
    mock_argmax.item.return_value = 0  # Cat wins
    mock_probs.argmax.return_value = mock_argmax
    mock_probs.__getitem__ = lambda _self, idx: MagicMock(item=lambda: 0.95 if idx == 0 else 0.05)

    mock_softmax_result = MagicMock()
    mock_softmax_result.__getitem__ = lambda _self, _idx: mock_probs
    mock_torch.nn.functional.softmax.return_value = mock_softmax_result

    # Create mock model
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_device.is_cuda = False
    mock_param = MagicMock()
    mock_param.is_cuda = False
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.config = MagicMock()
    mock_model.config.id2label = {"0": "cats", "1": "dogs"}

    mock_outputs = MagicMock()
    mock_outputs.logits = MagicMock()
    mock_model.return_value = mock_outputs

    # Create mock processor
    mock_processor = MagicMock()
    mock_inputs = {"pixel_values": MagicMock()}
    mock_processor.return_value = mock_inputs

    model_dict = {
        "model": mock_model,
        "processor": mock_processor,
    }

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    result = await classify_pet(model_dict, test_image)

    assert isinstance(result, PetClassificationResult)
    assert result.animal_type in ["cat", "cats"]  # May be normalized
    assert result.is_household_pet is True


# =============================================================================
# Test function signatures and types
# =============================================================================


def test_load_pet_classifier_model_is_async():
    """Test load_pet_classifier_model is an async function."""
    import inspect

    assert callable(load_pet_classifier_model)
    assert inspect.iscoroutinefunction(load_pet_classifier_model)


def test_load_pet_classifier_model_signature():
    """Test load_pet_classifier_model function signature."""
    import inspect

    sig = inspect.signature(load_pet_classifier_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


def test_is_likely_pet_false_positive_signature():
    """Test is_likely_pet_false_positive function signature."""
    import inspect

    sig = inspect.signature(is_likely_pet_false_positive)
    params = list(sig.parameters.keys())

    assert "pet_result" in params
    assert "confidence_threshold" in params
    assert sig.parameters["confidence_threshold"].default == 0.85


def test_format_pet_for_nemotron_signature():
    """Test format_pet_for_nemotron function signature."""
    import inspect

    sig = inspect.signature(format_pet_for_nemotron)
    params = list(sig.parameters.keys())
    assert "pet_result" in params


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_pet_classifier_in_model_zoo():
    """Test pet-classifier is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "pet-classifier" in zoo

    config = zoo["pet-classifier"]
    assert config.name == "pet-classifier"
    assert config.category == "classification"
    assert config.enabled is True


def test_pet_classifier_model_config_load_fn():
    """Test pet-classifier model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["pet-classifier"]
    assert config.load_fn is load_pet_classifier_model


def test_pet_classifier_vram_budget():
    """Test pet-classifier model has reasonable VRAM budget."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["pet-classifier"]
    # Pet classifier (ResNet-18) should be around 200MB
    assert config.vram_mb > 0
    assert config.vram_mb <= 500  # Should be under 500MB


# =============================================================================
# Test edge cases
# =============================================================================


def test_pet_classification_result_equal_scores():
    """Test PetClassificationResult with equal scores."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.50,
        cat_score=0.50,
        dog_score=0.50,
    )

    # Should still work, confidence should be 0.50
    assert result.confidence == 0.50
    assert result.cat_score == result.dog_score


def test_pet_classification_result_zero_confidence():
    """Test PetClassificationResult with zero confidence."""
    result = PetClassificationResult(
        animal_type="cat",
        confidence=0.0,
        cat_score=0.0,
        dog_score=0.0,
    )

    d = result.to_dict()
    assert d["confidence"] == 0.0

    # Should not be considered a false positive at 0% confidence
    assert is_likely_pet_false_positive(result) is False


def test_format_pet_for_nemotron_confidence_formatting():
    """Test format_pet_for_nemotron formats confidence correctly."""
    result = PetClassificationResult(
        animal_type="dog",
        confidence=0.999,  # High precision
        cat_score=0.001,
        dog_score=0.999,
        is_household_pet=True,
    )

    formatted = format_pet_for_nemotron(result)

    # Should format as percentage
    assert "100%" in formatted or "99%" in formatted


def test_pet_classification_result_label_normalization():
    """Test that label normalization is handled in classify_pet.

    The model may return "cats" or "dogs" which should be normalized
    to "cat" or "dog".
    """
    # This is a design check - the function should normalize labels
    import inspect

    source = inspect.getsource(classify_pet)
    # Check that normalization logic exists
    assert 'endswith("s")' in source or "cats" in source.lower() or "dogs" in source.lower()
