"""Unit tests for FashionCLIP model loader and clothing classification.

Tests cover:
- ClothingClassification dataclass initialization and serialization
- load_fashion_clip_model loading behavior and error handling
- format_clothing_context output formatting
- Module constants (SECURITY_CLOTHING_PROMPTS, SUSPICIOUS_CATEGORIES, SERVICE_CATEGORIES)
- GPU/CPU device handling

Note: classify_clothing and classify_clothing_batch functions use run_in_executor
with dynamic torch imports, making them difficult to mock effectively. The tests
focus on the dataclass, formatting, model loading, and constants.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

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

# =============================================================================
# Module Constants Tests
# =============================================================================


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_security_clothing_prompts_not_empty(self) -> None:
        """Test SECURITY_CLOTHING_PROMPTS is not empty."""
        assert len(SECURITY_CLOTHING_PROMPTS) > 0

    def test_security_clothing_prompts_are_strings(self) -> None:
        """Test all prompts are strings."""
        for prompt in SECURITY_CLOTHING_PROMPTS:
            assert isinstance(prompt, str)

    def test_security_clothing_prompts_contain_suspicious(self) -> None:
        """Test prompts contain suspicious clothing items."""
        prompts_text = " ".join(SECURITY_CLOTHING_PROMPTS)
        assert "dark hoodie" in prompts_text
        assert "face mask" in prompts_text
        assert "gloves" in prompts_text

    def test_security_clothing_prompts_contain_service(self) -> None:
        """Test prompts contain service/delivery uniforms."""
        prompts_text = " ".join(SECURITY_CLOTHING_PROMPTS)
        assert "delivery" in prompts_text.lower()
        assert "uniform" in prompts_text.lower()

    def test_security_clothing_prompts_has_general_categories(self) -> None:
        """Test prompts contain general clothing categories."""
        prompts_text = " ".join(SECURITY_CLOTHING_PROMPTS)
        assert "casual" in prompts_text.lower()
        assert "business" in prompts_text.lower()

    def test_suspicious_categories_is_frozenset(self) -> None:
        """Test SUSPICIOUS_CATEGORIES is a frozenset."""
        assert isinstance(SUSPICIOUS_CATEGORIES, frozenset)

    def test_suspicious_categories_not_empty(self) -> None:
        """Test SUSPICIOUS_CATEGORIES is not empty."""
        assert len(SUSPICIOUS_CATEGORIES) > 0

    def test_suspicious_categories_subset_of_prompts(self) -> None:
        """Test all suspicious categories are in prompts."""
        for category in SUSPICIOUS_CATEGORIES:
            assert category in SECURITY_CLOTHING_PROMPTS

    def test_suspicious_categories_expected_items(self) -> None:
        """Test suspicious categories contain expected items."""
        assert "person wearing dark hoodie" in SUSPICIOUS_CATEGORIES
        assert "person wearing face mask" in SUSPICIOUS_CATEGORIES
        assert "person wearing gloves" in SUSPICIOUS_CATEGORIES

    def test_service_categories_is_frozenset(self) -> None:
        """Test SERVICE_CATEGORIES is a frozenset."""
        assert isinstance(SERVICE_CATEGORIES, frozenset)

    def test_service_categories_not_empty(self) -> None:
        """Test SERVICE_CATEGORIES is not empty."""
        assert len(SERVICE_CATEGORIES) > 0

    def test_service_categories_subset_of_prompts(self) -> None:
        """Test all service categories are in prompts."""
        for category in SERVICE_CATEGORIES:
            assert category in SECURITY_CLOTHING_PROMPTS

    def test_service_categories_expected_items(self) -> None:
        """Test service categories contain expected items."""
        assert "delivery uniform" in SERVICE_CATEGORIES
        assert "high-visibility vest or safety vest" in SERVICE_CATEGORIES

    def test_suspicious_and_service_disjoint(self) -> None:
        """Test suspicious and service categories don't overlap."""
        overlap = SUSPICIOUS_CATEGORIES & SERVICE_CATEGORIES
        assert len(overlap) == 0

    def test_prompts_count(self) -> None:
        """Test total number of prompts."""
        assert len(SECURITY_CLOTHING_PROMPTS) >= 18


# =============================================================================
# ClothingClassification Dataclass Tests
# =============================================================================


class TestClothingClassificationInit:
    """Tests for ClothingClassification initialization."""

    def test_required_fields(self) -> None:
        """Test initialization with only required fields."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.85,
        )
        assert classification.top_category == "casual clothing"
        assert classification.confidence == 0.85
        assert classification.all_scores == {}
        assert classification.is_suspicious is False
        assert classification.is_service_uniform is False
        assert classification.raw_description == ""

    def test_all_fields(self) -> None:
        """Test initialization with all fields."""
        scores = {"casual clothing": 0.85, "business attire": 0.10}
        classification = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.92,
            all_scores=scores,
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: dark hoodie",
        )
        assert classification.top_category == "person wearing dark hoodie"
        assert classification.confidence == 0.92
        assert classification.all_scores == scores
        assert classification.is_suspicious is True
        assert classification.is_service_uniform is False
        assert classification.raw_description == "Alert: dark hoodie"

    def test_service_uniform_classification(self) -> None:
        """Test initialization for service uniform."""
        classification = ClothingClassification(
            top_category="delivery uniform",
            confidence=0.88,
            is_suspicious=False,
            is_service_uniform=True,
            raw_description="Service worker: delivery uniform",
        )
        assert classification.is_service_uniform is True
        assert classification.is_suspicious is False

    def test_default_all_scores_is_mutable(self) -> None:
        """Test default all_scores is an empty dict (mutable default)."""
        c1 = ClothingClassification(top_category="test", confidence=0.5)
        c2 = ClothingClassification(top_category="test", confidence=0.5)
        # Default factory should create new dicts
        assert c1.all_scores is not c2.all_scores

    def test_confidence_range(self) -> None:
        """Test classification with boundary confidence values."""
        # Minimum confidence
        c_min = ClothingClassification(top_category="test", confidence=0.0)
        assert c_min.confidence == 0.0

        # Maximum confidence
        c_max = ClothingClassification(top_category="test", confidence=1.0)
        assert c_max.confidence == 1.0

        # Mid-range confidence
        c_mid = ClothingClassification(top_category="test", confidence=0.5)
        assert c_mid.confidence == 0.5


class TestClothingClassificationToDict:
    """Tests for ClothingClassification.to_dict method."""

    def test_to_dict_basic(self) -> None:
        """Test to_dict with basic classification."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.75,
        )
        result = classification.to_dict()

        assert result["top_category"] == "casual clothing"
        assert result["confidence"] == 0.75
        assert result["is_suspicious"] is False
        assert result["is_service_uniform"] is False
        assert result["description"] == ""
        assert result["all_scores"] == {}

    def test_to_dict_with_all_fields(self) -> None:
        """Test to_dict with all fields populated."""
        scores = {"person wearing dark hoodie": 0.92, "casual clothing": 0.05}
        classification = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.92,
            all_scores=scores,
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: dark hoodie",
        )
        result = classification.to_dict()

        assert result["top_category"] == "person wearing dark hoodie"
        assert result["confidence"] == 0.92
        assert result["is_suspicious"] is True
        assert result["is_service_uniform"] is False
        assert result["description"] == "Alert: dark hoodie"
        assert result["all_scores"] == scores

    def test_to_dict_serializable(self) -> None:
        """Test to_dict produces JSON-serializable output."""
        import json

        classification = ClothingClassification(
            top_category="test",
            confidence=0.5,
            all_scores={"test": 0.5},
        )
        result = classification.to_dict()

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_to_dict_returns_dict(self) -> None:
        """Test to_dict returns a dictionary type."""
        classification = ClothingClassification(top_category="test", confidence=0.5)
        result = classification.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_has_expected_keys(self) -> None:
        """Test to_dict contains all expected keys."""
        classification = ClothingClassification(top_category="test", confidence=0.5)
        result = classification.to_dict()

        expected_keys = {
            "top_category",
            "confidence",
            "is_suspicious",
            "is_service_uniform",
            "description",
            "all_scores",
        }
        assert set(result.keys()) == expected_keys

    def test_to_dict_preserves_float_precision(self) -> None:
        """Test to_dict preserves float precision."""
        classification = ClothingClassification(
            top_category="test",
            confidence=0.123456789,
            all_scores={"test": 0.123456789},
        )
        result = classification.to_dict()
        assert result["confidence"] == 0.123456789


# =============================================================================
# load_fashion_clip_model Tests
# =============================================================================


class TestLoadFashionClipModel:
    """Tests for load_fashion_clip_model function."""

    @pytest.mark.asyncio
    async def test_load_model_success_with_cuda(self) -> None:
        """Test successful model loading with CUDA available."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model

        # Create mock torch module
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock transformers module
        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            result = await load_fashion_clip_model("/path/to/model")

            assert result["model"] == mock_model
            assert result["processor"] == mock_processor
            mock_model.cuda.assert_called_once()
            mock_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_success_without_cuda(self) -> None:
        """Test successful model loading without CUDA."""
        mock_processor = MagicMock()
        mock_model = MagicMock()

        # Create mock torch module
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        # Create mock transformers module
        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            result = await load_fashion_clip_model("/path/to/model")

            assert result["model"] == mock_model
            assert result["processor"] == mock_processor
            mock_model.cuda.assert_not_called()
            mock_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_from_huggingface_path(self) -> None:
        """Test loading model from HuggingFace path."""
        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            await load_fashion_clip_model("Marqo/marqo-fashionCLIP")

            mock_transformers.AutoProcessor.from_pretrained.assert_called_once_with(
                "Marqo/marqo-fashionCLIP", trust_remote_code=True
            )
            mock_transformers.AutoModel.from_pretrained.assert_called_once_with(
                "Marqo/marqo-fashionCLIP", trust_remote_code=True
            )

    @pytest.mark.asyncio
    async def test_load_model_runtime_error(self) -> None:
        """Test RuntimeError when model loading fails."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.side_effect = OSError(
            "Model not found at path"
        )

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await load_fashion_clip_model("/invalid/path")

            assert "Failed to load FashionCLIP model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_model_with_local_path(self) -> None:
        """Test loading model from local path."""
        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            result = await load_fashion_clip_model("/export/ai_models/model-zoo/fashion-clip")

            assert "model" in result
            assert "processor" in result
            mock_transformers.AutoProcessor.from_pretrained.assert_called_once_with(
                "/export/ai_models/model-zoo/fashion-clip", trust_remote_code=True
            )

    @pytest.mark.asyncio
    async def test_load_model_import_error_torch(self) -> None:
        """Test ImportError when torch/transformers not installed."""
        # Create a module that raises ImportError when accessed

        # Remove torch from sys.modules and make import fail
        original_torch = sys.modules.get("torch")
        original_transformers = sys.modules.get("transformers")

        try:
            # Set up to raise ImportError on import
            sys.modules["torch"] = None  # This causes import to fail
            sys.modules["transformers"] = None

            # Need to reload the module to trigger ImportError path
            # But since load_fashion_clip_model does a local import,
            # we need to mock at that level
            with pytest.raises((ImportError, TypeError)):
                await load_fashion_clip_model("/path/to/model")
        finally:
            # Restore original modules
            if original_torch is not None:
                sys.modules["torch"] = original_torch
            elif "torch" in sys.modules:
                del sys.modules["torch"]
            if original_transformers is not None:
                sys.modules["transformers"] = original_transformers
            elif "transformers" in sys.modules:
                del sys.modules["transformers"]


# =============================================================================
# classify_clothing Tests
# =============================================================================


class TestClassifyClothing:
    """Tests for classify_clothing function error handling."""

    @pytest.mark.asyncio
    async def test_classify_clothing_runtime_error(self) -> None:
        """Test RuntimeError when classification fails."""
        mock_processor = MagicMock()
        mock_processor.side_effect = ValueError("Processing failed")
        mock_model = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        model_dict = {"model": mock_model, "processor": mock_processor}
        mock_image = MagicMock()

        mock_torch = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError) as exc_info:
                await classify_clothing(model_dict, mock_image)

            assert "Clothing classification failed" in str(exc_info.value)


# =============================================================================
# classify_clothing_batch Tests
# =============================================================================


class TestClassifyClothingBatch:
    """Tests for classify_clothing_batch function."""

    @pytest.mark.asyncio
    async def test_batch_empty_images(self) -> None:
        """Test batch classification with empty image list."""
        mock_model = MagicMock()
        mock_processor = MagicMock()
        model_dict = {"model": mock_model, "processor": mock_processor}

        result = await classify_clothing_batch(model_dict, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_runtime_error(self) -> None:
        """Test RuntimeError when batch classification fails."""
        mock_processor = MagicMock()
        mock_processor.side_effect = ValueError("Batch processing failed")
        mock_model = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        model_dict = {"model": mock_model, "processor": mock_processor}
        mock_images = [MagicMock()]

        mock_torch = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError) as exc_info:
                await classify_clothing_batch(model_dict, mock_images)

            assert "Batch clothing classification failed" in str(exc_info.value)


# =============================================================================
# format_clothing_context Tests
# =============================================================================


class TestFormatClothingContext:
    """Tests for format_clothing_context function."""

    def test_format_basic_classification(self) -> None:
        """Test formatting basic classification."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.85,
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        assert "Clothing: Casual clothing" in result
        assert "85.0%" in result

    def test_format_suspicious_classification(self) -> None:
        """Test formatting suspicious classification."""
        classification = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.92,
            is_suspicious=True,
            raw_description="Alert: dark hoodie",
        )
        result = format_clothing_context(classification)

        assert "Clothing: Alert: dark hoodie" in result
        assert "[ALERT: Potentially suspicious attire detected]" in result
        assert "92.0%" in result

    def test_format_service_uniform_classification(self) -> None:
        """Test formatting service uniform classification."""
        classification = ClothingClassification(
            top_category="delivery uniform",
            confidence=0.88,
            is_service_uniform=True,
            raw_description="Service worker: delivery uniform",
        )
        result = format_clothing_context(classification)

        assert "Clothing: Service worker: delivery uniform" in result
        assert "[Service/delivery worker uniform detected]" in result
        assert "88.0%" in result

    def test_format_low_confidence_with_alternative(self) -> None:
        """Test formatting low confidence shows alternative."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.35,
            all_scores={
                "casual clothing": 0.35,
                "business attire or suit": 0.30,
                "athletic wear": 0.20,
            },
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        assert "Alternative:" in result
        assert "business attire or suit" in result
        assert "30.0%" in result

    def test_format_high_confidence_no_alternative(self) -> None:
        """Test formatting high confidence doesn't show alternative."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.85,
            all_scores={
                "casual clothing": 0.85,
                "business attire or suit": 0.10,
            },
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        assert "Alternative:" not in result

    def test_format_low_confidence_single_score(self) -> None:
        """Test formatting low confidence with single score."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.35,
            all_scores={"casual clothing": 0.35},
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        # Should not show alternative when only one score
        assert "Alternative:" not in result

    def test_format_multiline_output(self) -> None:
        """Test formatting produces multiline output."""
        classification = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.92,
            is_suspicious=True,
            raw_description="Alert: dark hoodie",
        )
        result = format_clothing_context(classification)

        lines = result.split("\n")
        assert len(lines) >= 2

    def test_format_exact_threshold_boundary(self) -> None:
        """Test formatting at exact confidence threshold (0.5)."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.5,
            all_scores={
                "casual clothing": 0.5,
                "business attire": 0.3,
            },
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        # At exactly 0.5, should NOT show alternative (< 0.5 required)
        assert "Alternative:" not in result

    def test_format_just_below_threshold(self) -> None:
        """Test formatting just below confidence threshold."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.49,
            all_scores={
                "casual clothing": 0.49,
                "business attire": 0.3,
            },
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        # Just below 0.5, should show alternative
        assert "Alternative:" in result

    def test_format_neutral_no_flags(self) -> None:
        """Test formatting neutral classification has no flags."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.75,
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="Casual clothing",
        )
        result = format_clothing_context(classification)

        assert "ALERT" not in result
        assert "Service/delivery worker" not in result

    def test_format_confidence_formatting(self) -> None:
        """Test confidence is formatted with one decimal place."""
        classification = ClothingClassification(
            top_category="test",
            confidence=0.123456,
            raw_description="Test",
        )
        result = format_clothing_context(classification)

        assert "12.3%" in result

    def test_format_returns_string(self) -> None:
        """Test format_clothing_context returns a string."""
        classification = ClothingClassification(
            top_category="test",
            confidence=0.5,
            raw_description="Test",
        )
        result = format_clothing_context(classification)
        assert isinstance(result, str)


# =============================================================================
# GPU/CPU Device Handling Tests
# =============================================================================


class TestDeviceHandling:
    """Tests for GPU/CPU device handling."""

    @pytest.mark.asyncio
    async def test_model_moves_to_cuda_when_available(self) -> None:
        """Test model is moved to CUDA when available."""
        mock_processor = MagicMock()
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            await load_fashion_clip_model("/path/to/model")

            mock_torch.cuda.is_available.assert_called_once()
            mock_model.cuda.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_stays_on_cpu_when_cuda_unavailable(self) -> None:
        """Test model stays on CPU when CUDA unavailable."""
        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            await load_fashion_clip_model("/path/to/model")

            mock_torch.cuda.is_available.assert_called_once()
            mock_model.cuda.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_is_set_to_eval_mode(self) -> None:
        """Test model is set to evaluation mode."""
        mock_processor = MagicMock()
        mock_model = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        mock_transformers.AutoProcessor.from_pretrained.return_value = mock_processor
        mock_transformers.AutoModel.from_pretrained.return_value = mock_model

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "transformers": mock_transformers,
            },
        ):
            await load_fashion_clip_model("/path/to/model")

            mock_model.eval.assert_called_once()


# =============================================================================
# Edge Cases Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_classification_zero_confidence(self) -> None:
        """Test classification with zero confidence."""
        classification = ClothingClassification(
            top_category="unknown",
            confidence=0.0,
        )
        assert classification.confidence == 0.0
        result = format_clothing_context(classification)
        assert "0.0%" in result

    def test_classification_perfect_confidence(self) -> None:
        """Test classification with perfect confidence."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=1.0,
        )
        assert classification.confidence == 1.0
        result = format_clothing_context(classification)
        assert "100.0%" in result

    def test_classification_empty_description(self) -> None:
        """Test classification with empty description."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.5,
            raw_description="",
        )
        result = format_clothing_context(classification)
        assert "Clothing:" in result

    def test_classification_long_category_name(self) -> None:
        """Test classification with long category name."""
        long_category = "person wearing very elaborate and detailed clothing description"
        classification = ClothingClassification(
            top_category=long_category,
            confidence=0.75,
            raw_description=long_category,
        )
        result = format_clothing_context(classification)
        assert long_category in result

    def test_all_scores_ordering(self) -> None:
        """Test that all_scores can have arbitrary ordering."""
        scores = {
            "c": 0.1,
            "a": 0.5,
            "b": 0.4,
        }
        classification = ClothingClassification(
            top_category="a",
            confidence=0.5,
            all_scores=scores,
            raw_description="A",
        )
        # When formatted, alternatives should be sorted by score
        _result = format_clothing_context(classification)
        # With confidence 0.5 (not < 0.5), no alternative shown
        # But the data should be preserved
        assert classification.all_scores == scores


# =============================================================================
# Integration-style Tests (with minimal mocking)
# =============================================================================


class TestClothingClassificationIntegration:
    """Integration-style tests for ClothingClassification."""

    def test_full_workflow_suspicious(self) -> None:
        """Test full workflow for suspicious classification."""
        classification = ClothingClassification(
            top_category="person wearing dark hoodie",
            confidence=0.92,
            all_scores={
                "person wearing dark hoodie": 0.92,
                "casual clothing": 0.05,
                "business attire or suit": 0.03,
            },
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Alert: dark hoodie",
        )

        # Test serialization
        dict_result = classification.to_dict()
        assert dict_result["is_suspicious"] is True

        # Test formatting
        context = format_clothing_context(classification)
        assert "ALERT" in context
        assert "dark hoodie" in context

    def test_full_workflow_service_uniform(self) -> None:
        """Test full workflow for service uniform classification."""
        classification = ClothingClassification(
            top_category="Amazon delivery vest",
            confidence=0.88,
            all_scores={
                "Amazon delivery vest": 0.88,
                "FedEx uniform": 0.08,
                "casual clothing": 0.04,
            },
            is_suspicious=False,
            is_service_uniform=True,
            raw_description="Service worker: Amazon delivery vest",
        )

        # Test serialization
        dict_result = classification.to_dict()
        assert dict_result["is_service_uniform"] is True

        # Test formatting
        context = format_clothing_context(classification)
        assert "Service/delivery worker" in context

    def test_full_workflow_neutral(self) -> None:
        """Test full workflow for neutral classification."""
        classification = ClothingClassification(
            top_category="casual clothing",
            confidence=0.75,
            all_scores={
                "casual clothing": 0.75,
                "athletic wear or sportswear": 0.15,
                "outdoor or hiking clothing": 0.10,
            },
            is_suspicious=False,
            is_service_uniform=False,
            raw_description="Casual clothing",
        )

        # Test serialization
        dict_result = classification.to_dict()
        assert dict_result["is_suspicious"] is False
        assert dict_result["is_service_uniform"] is False

        # Test formatting
        context = format_clothing_context(classification)
        assert "ALERT" not in context
        assert "Service/delivery worker" not in context

    def test_round_trip_serialization(self) -> None:
        """Test that to_dict produces data that could recreate the object."""
        import json

        original = ClothingClassification(
            top_category="test category",
            confidence=0.777,
            all_scores={"test category": 0.777, "other": 0.223},
            is_suspicious=True,
            is_service_uniform=False,
            raw_description="Test description",
        )

        # Serialize to JSON and back
        dict_data = original.to_dict()
        json_str = json.dumps(dict_data)
        loaded_data = json.loads(json_str)

        # Verify data integrity
        assert loaded_data["top_category"] == "test category"
        assert loaded_data["confidence"] == 0.777
        assert loaded_data["is_suspicious"] is True
        assert loaded_data["is_service_uniform"] is False
        assert loaded_data["description"] == "Test description"
        assert "test category" in loaded_data["all_scores"]
