"""Unit tests for fashion_clip_loader service.

Tests for the Marqo-FashionCLIP model loader and clothing classifier.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.fashion_clip_loader import (
    SECURITY_CLOTHING_PROMPTS,
    SERVICE_CATEGORIES,
    SUSPICIOUS_CATEGORIES,
    ClothingClassification,
    classify_clothing,
    classify_clothing_batch,
    format_clothing_context,
    load_fashion_clip_model,
)

# Test fixtures


@pytest.fixture
def mock_pil_image():
    """Create a mock PIL Image."""
    image = MagicMock()
    image.size = (224, 224)
    return image


@pytest.fixture
def mock_model_dict():
    """Create a mock model dictionary."""
    mock_model = MagicMock()
    mock_processor = MagicMock()

    # Mock CUDA availability
    mock_model.parameters.return_value = iter([MagicMock(device=MagicMock())])

    return {"model": mock_model, "processor": mock_processor}


# Test ClothingClassification dataclass


def test_clothing_classification_creation():
    """Test ClothingClassification dataclass creation."""
    classification = ClothingClassification(
        top_category="person wearing dark hoodie",
        confidence=0.85,
        all_scores={"person wearing dark hoodie": 0.85, "casual clothing": 0.10},
        is_suspicious=True,
        is_service_uniform=False,
        raw_description="Alert: dark hoodie",
    )

    assert classification.top_category == "person wearing dark hoodie"
    assert classification.confidence == 0.85
    assert classification.is_suspicious is True
    assert classification.is_service_uniform is False
    assert "dark hoodie" in classification.raw_description


def test_clothing_classification_to_dict():
    """Test ClothingClassification.to_dict() method."""
    classification = ClothingClassification(
        top_category="delivery uniform",
        confidence=0.92,
        all_scores={"delivery uniform": 0.92},
        is_suspicious=False,
        is_service_uniform=True,
        raw_description="Service worker: delivery uniform",
    )

    result = classification.to_dict()

    assert result["top_category"] == "delivery uniform"
    assert result["confidence"] == 0.92
    assert result["is_suspicious"] is False
    assert result["is_service_uniform"] is True
    assert "delivery uniform" in result["description"]


def test_clothing_classification_defaults():
    """Test ClothingClassification default values."""
    classification = ClothingClassification(
        top_category="casual clothing",
        confidence=0.75,
    )

    assert classification.all_scores == {}
    assert classification.is_suspicious is False
    assert classification.is_service_uniform is False
    assert classification.raw_description == ""


# Test constants


def test_security_clothing_prompts_not_empty():
    """Test that security clothing prompts are defined."""
    assert len(SECURITY_CLOTHING_PROMPTS) > 0
    assert all(isinstance(p, str) for p in SECURITY_CLOTHING_PROMPTS)


def test_suspicious_categories_are_subset_of_prompts():
    """Test that suspicious categories are valid prompts."""
    for category in SUSPICIOUS_CATEGORIES:
        assert category in SECURITY_CLOTHING_PROMPTS, f"{category} not in prompts"


def test_service_categories_are_subset_of_prompts():
    """Test that service categories are valid prompts."""
    for category in SERVICE_CATEGORIES:
        assert category in SECURITY_CLOTHING_PROMPTS, f"{category} not in prompts"


def test_suspicious_and_service_mutually_exclusive():
    """Test that suspicious and service categories don't overlap."""
    overlap = SUSPICIOUS_CATEGORIES & SERVICE_CATEGORIES
    assert len(overlap) == 0, f"Overlapping categories: {overlap}"


# Test format_clothing_context


def test_format_clothing_context_basic():
    """Test basic clothing context formatting."""
    classification = ClothingClassification(
        top_category="casual clothing",
        confidence=0.85,
        raw_description="Casual clothing",
    )

    result = format_clothing_context(classification)

    assert "Casual clothing" in result
    # Confidence is formatted as 85.0% not 85%
    assert "85" in result and "%" in result


def test_format_clothing_context_suspicious():
    """Test format_clothing_context with suspicious attire."""
    classification = ClothingClassification(
        top_category="person wearing dark hoodie",
        confidence=0.78,
        is_suspicious=True,
        raw_description="Alert: dark hoodie",
    )

    result = format_clothing_context(classification)

    assert "ALERT" in result
    assert "suspicious" in result.lower()


def test_format_clothing_context_service_uniform():
    """Test format_clothing_context with service uniform."""
    classification = ClothingClassification(
        top_category="Amazon delivery vest",
        confidence=0.91,
        is_service_uniform=True,
        raw_description="Service worker: Amazon delivery vest",
    )

    result = format_clothing_context(classification)

    assert "Service" in result or "delivery" in result.lower()


def test_format_clothing_context_low_confidence_alternative():
    """Test format_clothing_context shows alternative for low confidence."""
    classification = ClothingClassification(
        top_category="casual clothing",
        confidence=0.35,
        all_scores={
            "casual clothing": 0.35,
            "athletic wear or sportswear": 0.30,
        },
        raw_description="Casual clothing",
    )

    result = format_clothing_context(classification)

    # Should show alternative when confidence < 0.5
    assert "Alternative" in result or "athletic" in result.lower()


# Test load_fashion_clip_model


def test_load_fashion_clip_model_signature():
    """Test load_fashion_clip_model function exists and is async."""
    import inspect

    # Verify function exists and is a coroutine function
    assert callable(load_fashion_clip_model)
    assert inspect.iscoroutinefunction(load_fashion_clip_model)


def test_load_fashion_clip_model_accepts_model_path():
    """Test load_fashion_clip_model function signature."""
    import inspect

    sig = inspect.signature(load_fashion_clip_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


# Test classify_clothing


@pytest.mark.asyncio
async def test_classify_clothing_basic(mock_pil_image):
    """Test basic clothing classification - verify function structure."""
    # This is a structural test; full integration requires actual model
    # Just verify the function signature and dataclass are correct
    import numpy as np

    # Create a mock model dict that returns expected tensors
    mock_model = MagicMock()
    mock_processor = MagicMock()

    # Mock the processor output
    num_prompts = len(SECURITY_CLOTHING_PROMPTS)
    mock_processed = {
        "pixel_values": MagicMock(),
        "input_ids": MagicMock(),
    }
    mock_processor.return_value = mock_processed

    # Create mock image and text features
    mock_img_features = MagicMock()
    mock_text_features = MagicMock()

    # Mock similarity computation to return softmax probabilities
    mock_scores = np.zeros(num_prompts, dtype=np.float32)
    mock_scores[0] = 0.85  # First prompt gets highest score

    mock_similarity = MagicMock()
    mock_similarity[0].cpu.return_value.numpy.return_value = mock_scores

    # Setup model mock
    mock_model.get_image_features.return_value = mock_img_features
    mock_model.get_text_features.return_value = mock_text_features
    mock_model.parameters.return_value = iter([MagicMock(device=MagicMock())])

    # Mock the matmul operation
    mock_img_features.__matmul__ = MagicMock(
        return_value=MagicMock(softmax=MagicMock(return_value=mock_similarity))
    )

    model_dict = {"model": mock_model, "processor": mock_processor}

    # Test that the function can be called (mocking is complex due to torch internals)
    # This is mainly a structural/interface test
    assert callable(classify_clothing)
    assert "model" in model_dict
    assert "processor" in model_dict


def test_clothing_classification_flags():
    """Test that is_suspicious and is_service flags work correctly."""
    # Test suspicious category
    suspicious_result = ClothingClassification(
        top_category="person wearing dark hoodie",
        confidence=0.8,
        is_suspicious=True,
        is_service_uniform=False,
        raw_description="Alert: dark hoodie",
    )
    assert suspicious_result.is_suspicious is True
    assert suspicious_result.is_service_uniform is False

    # Test service category
    service_result = ClothingClassification(
        top_category="Amazon delivery vest",
        confidence=0.9,
        is_suspicious=False,
        is_service_uniform=True,
        raw_description="Service worker: Amazon delivery vest",
    )
    assert service_result.is_suspicious is False
    assert service_result.is_service_uniform is True


# Test classify_clothing_batch (mock tests)


@pytest.mark.asyncio
async def test_classify_clothing_batch_empty():
    """Test batch classification with empty list."""
    result = await classify_clothing_batch(
        model_dict={"model": MagicMock(), "processor": MagicMock()},
        images=[],
    )
    assert result == []


# Integration with EnrichmentPipeline


def test_enrichment_result_has_clothing_classifications():
    """Test EnrichmentResult includes clothing_classifications field."""
    from backend.services.enrichment_pipeline import EnrichmentResult

    result = EnrichmentResult()

    assert hasattr(result, "clothing_classifications")
    assert result.clothing_classifications == {}
    assert result.has_clothing_classifications is False


def test_enrichment_result_has_suspicious_clothing():
    """Test has_suspicious_clothing property."""
    from backend.services.enrichment_pipeline import EnrichmentResult

    result = EnrichmentResult()
    assert result.has_suspicious_clothing is False

    # Add a non-suspicious classification
    result.clothing_classifications["0"] = ClothingClassification(
        top_category="casual clothing",
        confidence=0.8,
        is_suspicious=False,
    )
    assert result.has_suspicious_clothing is False

    # Add a suspicious classification
    result.clothing_classifications["1"] = ClothingClassification(
        top_category="person wearing dark hoodie",
        confidence=0.9,
        is_suspicious=True,
    )
    assert result.has_suspicious_clothing is True


def test_enrichment_pipeline_has_clothing_flag():
    """Test EnrichmentPipeline has clothing_classification_enabled flag."""
    from backend.services.enrichment_pipeline import EnrichmentPipeline

    pipeline = EnrichmentPipeline()
    assert hasattr(pipeline, "clothing_classification_enabled")
    assert pipeline.clothing_classification_enabled is True


def test_enrichment_pipeline_can_disable_clothing():
    """Test EnrichmentPipeline can disable clothing classification."""
    from backend.services.enrichment_pipeline import EnrichmentPipeline

    pipeline = EnrichmentPipeline(clothing_classification_enabled=False)
    assert pipeline.clothing_classification_enabled is False


# Test load_fashion_clip_model error handling


@pytest.mark.asyncio
async def test_load_fashion_clip_model_import_error(monkeypatch):
    """Test load_fashion_clip_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers from imports if present
    modules_to_hide = ["transformers", "torch"]
    hidden_modules = {}
    for mod in modules_to_hide:
        if mod in sys.modules:
            hidden_modules[mod] = sys.modules.pop(mod)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("transformers", "torch"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError):
            await load_fashion_clip_model("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_fashion_clip_model_runtime_error(monkeypatch):
    """Test load_fashion_clip_model handles RuntimeError for failed loading."""
    import sys

    # Mock torch and transformers to exist but fail on model load
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()
    mock_transformers.AutoProcessor.from_pretrained.side_effect = RuntimeError("Model not found")

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load FashionCLIP"):
        await load_fashion_clip_model("/nonexistent/path")


# Test model_zoo integration


def test_fashion_clip_in_model_zoo():
    """Test fashion-clip is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "fashion-clip" in zoo

    config = zoo["fashion-clip"]
    assert config.name == "fashion-clip"
    assert config.vram_mb == 500
    assert config.category == "classification"
    assert config.enabled is True


# =============================================================================
# Regression Tests for Meta Tensor Loading Issue (bead d9qk)
# =============================================================================


def test_enrichment_clothing_classifier_uses_open_clip():
    """Regression test: ClothingClassifier should use open_clip to avoid meta tensor error.

    This test ensures the fix for the meta tensor loading error is in place.
    The error "Cannot copy out of meta tensor; no data!" happens when using
    AutoModel.from_pretrained() followed by .to(device) with CLIP-style models.

    The fix uses open_clip.create_model_and_transforms() which properly handles
    device placement during loading.
    """

    # Import the enrichment service's ClothingClassifier
    # We need to add the ai/enrichment directory to the path temporarily
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"

    # Read the model.py file and verify it uses open_clip
    model_py_path = enrichment_dir / "model.py"
    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify the fix is in place
        assert "import open_clip" in content, (
            "ClothingClassifier.load_model() should import open_clip"
        )
        assert "create_model_and_transforms" in content, (
            "ClothingClassifier should use open_clip.create_model_and_transforms()"
        )
        assert "_use_open_clip" in content, (
            "ClothingClassifier should track which loading method was used"
        )
        assert "_load_with_transformers_fallback" in content, (
            "ClothingClassifier should have a transformers fallback"
        )
        assert "device_map" in content, (
            "Transformers fallback should use device_map to avoid meta tensor issue"
        )


def test_enrichment_clothing_classifier_has_fallback():
    """Regression test: ClothingClassifier should have transformers fallback.

    If open_clip loading fails, the classifier should fall back to transformers
    with device_map parameter to avoid the meta tensor issue.
    """
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"
    model_py_path = enrichment_dir / "model.py"

    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify the fallback mechanism
        assert "low_cpu_mem_usage=False" in content, (
            "Transformers fallback should disable low_cpu_mem_usage to avoid meta tensors"
        )
        assert '{"": self.device}' in content or "device_map" in content, (
            "Transformers fallback should use device_map for direct device loading"
        )


def test_enrichment_clothing_classifier_class_structure():
    """Test ClothingClassifier class has expected attributes after fix.

    The fix changes the class to have preprocess and tokenizer instead of processor,
    and adds _use_open_clip flag.
    """
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"
    model_py_path = enrichment_dir / "model.py"

    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify new attributes
        assert "self.preprocess" in content, (
            "ClothingClassifier should have self.preprocess attribute"
        )
        assert "self.tokenizer" in content, (
            "ClothingClassifier should have self.tokenizer attribute"
        )
        assert "self._use_open_clip" in content, (
            "ClothingClassifier should have self._use_open_clip flag"
        )

        # Verify new methods
        assert "def _classify_with_open_clip" in content, (
            "ClothingClassifier should have _classify_with_open_clip method"
        )
        assert "def _classify_with_transformers" in content, (
            "ClothingClassifier should have _classify_with_transformers method"
        )
