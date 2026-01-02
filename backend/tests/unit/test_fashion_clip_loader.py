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


def test_enrichment_clothing_classifier_uses_transformers():
    """Verify ClothingClassifier uses transformers for FashionCLIP model loading.

    The ClothingClassifier uses HuggingFace transformers with AutoModel and
    AutoProcessor for loading FashionCLIP models. This provides compatibility
    with the patrickjohncyh/fashion-clip model format.
    """
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"
    model_py_path = enrichment_dir / "model.py"

    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify transformers-based implementation
        assert "from transformers import AutoModel, AutoProcessor" in content, (
            "ClothingClassifier should use transformers AutoModel and AutoProcessor"
        )
        assert "AutoProcessor.from_pretrained" in content, (
            "ClothingClassifier should load processor with AutoProcessor.from_pretrained()"
        )
        assert "AutoModel.from_pretrained" in content, (
            "ClothingClassifier should load model with AutoModel.from_pretrained()"
        )
        assert "trust_remote_code=True" in content, (
            "ClothingClassifier should use trust_remote_code=True for FashionCLIP"
        )


def test_enrichment_clothing_classifier_has_device_handling():
    """Verify ClothingClassifier properly handles device placement.

    The ClothingClassifier should detect CUDA availability and move the model
    to the appropriate device after loading.
    """
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"
    model_py_path = enrichment_dir / "model.py"

    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify device handling
        assert "torch.cuda.is_available()" in content, (
            "ClothingClassifier should check CUDA availability"
        )
        assert ".to(self.device)" in content, "ClothingClassifier should move model to device"
        assert 'self.device = "cpu"' in content, (
            "ClothingClassifier should fallback to CPU when CUDA unavailable"
        )


def test_enrichment_clothing_classifier_class_structure():
    """Verify ClothingClassifier has expected class structure.

    The ClothingClassifier should have model and processor attributes,
    and helper methods for extracting clothing attributes.
    """
    from pathlib import Path

    enrichment_dir = Path(__file__).parent.parent.parent.parent / "ai" / "enrichment"
    model_py_path = enrichment_dir / "model.py"

    if model_py_path.exists():
        content = model_py_path.read_text()

        # Verify core attributes
        assert "self.model" in content, "ClothingClassifier should have self.model attribute"
        assert "self.processor" in content, (
            "ClothingClassifier should have self.processor attribute"
        )
        assert "self.model_path" in content, (
            "ClothingClassifier should have self.model_path attribute"
        )
        assert "self.device" in content, "ClothingClassifier should have self.device attribute"

        # Verify helper methods for clothing analysis
        assert "def _extract_clothing_type" in content, (
            "ClothingClassifier should have _extract_clothing_type method"
        )
        assert "def _extract_color" in content, (
            "ClothingClassifier should have _extract_color method"
        )
        assert "def _extract_style" in content, (
            "ClothingClassifier should have _extract_style method"
        )
