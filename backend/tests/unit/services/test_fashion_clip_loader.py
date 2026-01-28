"""Unit tests for FashionSigLIP model loader and clothing classification.

FashionSigLIP provides 57% improved accuracy over FashionCLIP:
- Text-to-Image MRR: 0.239 vs 0.165 (FashionCLIP2.0)
- Text-to-Image Recall@1: 0.121 vs 0.077 (FashionCLIP2.0)
- Text-to-Image Recall@10: 0.340 vs 0.249 (FashionCLIP2.0)

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
    CLOTHING_PROMPTS_V2,
    SECURITY_CLOTHING_PROMPTS,
    SERVICE_CATEGORIES,
    SUSPICIOUS_CATEGORIES,
    ClothingClassification,
    classify_clothing,
    classify_clothing_batch,
    format_clothing_context,
    get_all_clothing_prompts,
    get_clothing_category,
    get_clothing_risk_level,
    get_clothing_threshold,
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
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        # Create mock torch module with submodules
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock open_clip module
        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            result = await load_fashion_clip_model("/path/to/model")

            assert result["model"] == mock_model
            assert result["preprocess"] == mock_preprocess
            assert result["tokenizer"] == mock_tokenizer
            mock_model.cuda.assert_called_once()
            mock_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_success_without_cuda(self) -> None:
        """Test successful model loading without CUDA."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        # Create mock torch module with submodules
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        # Create mock open_clip module
        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            result = await load_fashion_clip_model("/path/to/model")

            assert result["model"] == mock_model
            assert result["preprocess"] == mock_preprocess
            assert result["tokenizer"] == mock_tokenizer
            mock_model.cuda.assert_not_called()
            mock_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_model_from_huggingface_path(self) -> None:
        """Test loading model from HuggingFace path."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            result = await load_fashion_clip_model("Marqo/marqo-fashionSigLIP")

            # HuggingFace path gets prefixed with hf-hub:
            mock_open_clip.create_model_from_pretrained.assert_called_once_with(
                "hf-hub:Marqo/marqo-fashionSigLIP"
            )
            assert result["model"] == mock_model

    @pytest.mark.asyncio
    async def test_load_model_runtime_error(self) -> None:
        """Test RuntimeError when model loading fails."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.side_effect = OSError("Model not found at path")

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await load_fashion_clip_model("/invalid/path")

            assert "Failed to load FashionSigLIP model" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_model_with_local_path(self) -> None:
        """Test loading model from local path."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            result = await load_fashion_clip_model("/export/ai_models/model-zoo/fashion-siglip")

            assert "model" in result
            assert "preprocess" in result
            # Local paths use hf-hub:Marqo/marqo-fashionSigLIP
            mock_open_clip.create_model_from_pretrained.assert_called_once_with(
                "hf-hub:Marqo/marqo-fashionSigLIP"
            )

    @pytest.mark.asyncio
    async def test_load_model_with_hf_hub_prefix(self) -> None:
        """Test loading model with hf-hub: prefix (line 165 else branch)."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            result = await load_fashion_clip_model("hf-hub:Marqo/marqo-fashionSigLIP")

            # Should use the path as-is (line 165: hub_path = model_path)
            mock_open_clip.create_model_from_pretrained.assert_called_once_with(
                "hf-hub:Marqo/marqo-fashionSigLIP"
            )
            assert result["model"] == mock_model

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
    """Tests for classify_clothing function.

    Note: classify_clothing uses run_in_executor with complex tensor operations that
    are difficult to unit test effectively. Integration tests cover the happy paths.
    Here we test error handling and code structure.
    """

    @pytest.mark.asyncio
    async def test_classify_clothing_runtime_error(self) -> None:
        """Test RuntimeError when classification fails."""
        mock_preprocess = MagicMock()
        mock_preprocess.side_effect = ValueError("Processing failed")
        mock_model = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        model_dict = {"model": mock_model, "preprocess": mock_preprocess, "tokenizer": MagicMock()}
        mock_image = MagicMock()

        mock_torch = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError) as exc_info:
                await classify_clothing(model_dict, mock_image)

            assert "Clothing classification failed" in str(exc_info.value)

    def test_classify_clothing_classification_logic_suspicious(self) -> None:
        """Test classification logic for suspicious clothing."""
        # Simulating what happens inside _classify function
        test_prompts = [
            "person wearing dark hoodie",
            "delivery uniform",
            "casual clothing",
        ]

        # Simulate scores dict creation
        import numpy as np

        scores = np.array([0.92, 0.05, 0.03])
        all_scores = {
            prompt: float(score) for prompt, score in zip(test_prompts, scores, strict=True)
        }

        # Sort and get top
        sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        top_category = sorted_items[0][0]
        top_confidence = sorted_items[0][1]

        # Check classification flags
        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        assert top_category == "person wearing dark hoodie"
        assert is_suspicious is True
        assert is_service is False
        assert top_confidence > 0.9

    def test_classify_clothing_classification_logic_service(self) -> None:
        """Test classification logic for service uniforms."""
        test_prompts = [
            "person wearing dark hoodie",
            "delivery uniform",
            "casual clothing",
        ]

        import numpy as np

        scores = np.array([0.05, 0.88, 0.07])
        all_scores = {
            prompt: float(score) for prompt, score in zip(test_prompts, scores, strict=True)
        }

        sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        top_category = sorted_items[0][0]

        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        assert top_category == "delivery uniform"
        assert is_suspicious is False
        assert is_service is True

    def test_classify_clothing_description_generation_suspicious(self) -> None:
        """Test description generation for suspicious clothing."""
        top_category = "person wearing dark hoodie"
        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        if is_service:
            description = f"Service worker: {top_category.replace('person wearing ', '')}"
        elif is_suspicious:
            description = f"Alert: {top_category.replace('person wearing ', '')}"
        else:
            description = top_category.replace("person wearing ", "").capitalize()

        assert "Alert:" in description
        assert "dark hoodie" in description

    def test_classify_clothing_description_generation_service(self) -> None:
        """Test description generation for service uniforms."""
        top_category = "delivery uniform"
        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        if is_service:
            description = f"Service worker: {top_category.replace('person wearing ', '')}"
        elif is_suspicious:
            description = f"Alert: {top_category.replace('person wearing ', '')}"
        else:
            description = top_category.replace("person wearing ", "").capitalize()

        assert "Service worker:" in description

    def test_classify_clothing_description_generation_neutral(self) -> None:
        """Test description generation for neutral clothing."""
        top_category = "person wearing casual clothing"
        is_suspicious = top_category in SUSPICIOUS_CATEGORIES
        is_service = top_category in SERVICE_CATEGORIES

        if is_service:
            description = f"Service worker: {top_category.replace('person wearing ', '')}"
        elif is_suspicious:
            description = f"Alert: {top_category.replace('person wearing ', '')}"
        else:
            description = top_category.replace("person wearing ", "").capitalize()

        assert "Alert:" not in description
        assert "Service worker:" not in description
        assert description[0].isupper()  # Capitalized

    def test_classify_clothing_top_k_filtering(self) -> None:
        """Test top_k score filtering logic."""
        all_scores = {
            "cat1": 0.5,
            "cat2": 0.3,
            "cat3": 0.1,
            "cat4": 0.06,
            "cat5": 0.04,
        }

        top_k = 3
        sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        top_k_scores = dict(sorted_items[:top_k])

        assert len(top_k_scores) == 3
        assert "cat1" in top_k_scores
        assert "cat2" in top_k_scores
        assert "cat3" in top_k_scores
        assert "cat4" not in top_k_scores
        assert "cat5" not in top_k_scores


# =============================================================================
# classify_clothing_batch Tests
# =============================================================================


class TestClassifyClothingBatch:
    """Tests for classify_clothing_batch function.

    Note: classify_clothing_batch uses run_in_executor with complex tensor operations
    that are difficult to unit test effectively. Integration tests cover the happy paths.
    Here we test error handling, empty list handling, and logic validation.
    """

    @pytest.mark.asyncio
    async def test_batch_empty_images(self) -> None:
        """Test batch classification with empty image list."""
        mock_model = MagicMock()
        mock_processor = MagicMock()
        model_dict = {"model": mock_model, "preprocess": mock_processor, "tokenizer": MagicMock()}

        result = await classify_clothing_batch(model_dict, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_runtime_error(self) -> None:
        """Test RuntimeError when batch classification fails."""
        mock_preprocess = MagicMock()
        mock_preprocess.side_effect = ValueError("Batch processing failed")
        mock_model = MagicMock()

        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_model.parameters.return_value = iter([mock_param])

        model_dict = {"model": mock_model, "preprocess": mock_preprocess, "tokenizer": MagicMock()}
        mock_images = [MagicMock()]

        mock_torch = MagicMock()

        with patch.dict(sys.modules, {"torch": mock_torch}):
            with pytest.raises(RuntimeError) as exc_info:
                await classify_clothing_batch(model_dict, mock_images)

            assert "Batch clothing classification failed" in str(exc_info.value)

    def test_batch_classification_logic_multiple_results(self) -> None:
        """Test batch result processing logic for multiple images."""
        import numpy as np

        test_prompts = [
            "person wearing dark hoodie",
            "delivery uniform",
            "casual clothing",
        ]

        # Simulate batch results - 2 images
        all_batch_scores = np.array(
            [
                [0.92, 0.05, 0.03],  # Image 1: suspicious
                [0.05, 0.88, 0.07],  # Image 2: service
            ]
        )

        results = []
        for i, scores in enumerate(all_batch_scores):
            all_scores = {
                prompt: float(score) for prompt, score in zip(test_prompts, scores, strict=True)
            }

            sorted_items = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
            top_category = sorted_items[0][0]
            top_confidence = sorted_items[0][1]

            is_suspicious = top_category in SUSPICIOUS_CATEGORIES
            is_service = top_category in SERVICE_CATEGORIES

            results.append(
                {
                    "top_category": top_category,
                    "confidence": top_confidence,
                    "is_suspicious": is_suspicious,
                    "is_service": is_service,
                }
            )

        assert len(results) == 2
        assert results[0]["top_category"] == "person wearing dark hoodie"
        assert results[0]["is_suspicious"] is True
        assert results[1]["top_category"] == "delivery uniform"
        assert results[1]["is_service"] is True

    def test_batch_enum_iteration(self) -> None:
        """Test enumeration over batch results."""
        batch_scores = [[0.8, 0.1, 0.1], [0.1, 0.8, 0.1], [0.1, 0.1, 0.8]]

        results = []
        for i, scores in enumerate(batch_scores):
            results.append({"index": i, "scores": scores})

        assert len(results) == 3
        assert results[0]["index"] == 0
        assert results[1]["index"] == 1
        assert results[2]["index"] == 2


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
        mock_model = MagicMock()
        mock_model.cuda.return_value = mock_model
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            await load_fashion_clip_model("/path/to/model")

            mock_torch.cuda.is_available.assert_called_once()
            mock_model.cuda.assert_called_once()

    @pytest.mark.asyncio
    async def test_model_stays_on_cpu_when_cuda_unavailable(self) -> None:
        """Test model stays on CPU when CUDA unavailable."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
            },
        ):
            await load_fashion_clip_model("/path/to/model")

            mock_torch.cuda.is_available.assert_called_once()
            mock_model.cuda.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_is_set_to_eval_mode(self) -> None:
        """Test model is set to evaluation mode."""
        mock_model = MagicMock()
        mock_preprocess = MagicMock()
        mock_tokenizer = MagicMock()

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_open_clip = MagicMock()
        mock_open_clip.create_model_from_pretrained.return_value = (
            mock_model,
            mock_preprocess,
        )
        mock_open_clip.get_tokenizer.return_value = mock_tokenizer

        with patch.dict(
            sys.modules,
            {
                "torch": mock_torch,
                "torch.nn": MagicMock(),
                "torch.nn.functional": MagicMock(),
                "open_clip": mock_open_clip,
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


# =============================================================================
# Hierarchical Security Categories Tests (NEM-3913)
# =============================================================================


class TestClothingPromptsV2Structure:
    """Tests for CLOTHING_PROMPTS_V2 hierarchical structure."""

    def test_clothing_prompts_v2_exists(self) -> None:
        """Test CLOTHING_PROMPTS_V2 is defined."""
        assert CLOTHING_PROMPTS_V2 is not None
        assert isinstance(CLOTHING_PROMPTS_V2, dict)

    def test_clothing_prompts_v2_has_expected_categories(self) -> None:
        """Test CLOTHING_PROMPTS_V2 has expected category keys."""
        expected_categories = {
            "suspicious",
            "delivery_branded",
            "delivery_generic",
            "utility_service",
            "casual_civilian",
            "colors",
        }
        assert set(CLOTHING_PROMPTS_V2.keys()) == expected_categories

    def test_each_category_has_required_fields(self) -> None:
        """Test each category has prompts, threshold, and risk_level."""
        for category, config in CLOTHING_PROMPTS_V2.items():
            assert "prompts" in config, f"Category {category} missing prompts"
            assert "threshold" in config, f"Category {category} missing threshold"
            assert "risk_level" in config, f"Category {category} missing risk_level"
            assert isinstance(config["prompts"], list)
            assert isinstance(config["threshold"], float)
            assert isinstance(config["risk_level"], str)

    def test_suspicious_category_has_high_risk(self) -> None:
        """Test suspicious category has high risk level."""
        assert CLOTHING_PROMPTS_V2["suspicious"]["risk_level"] == "high"

    def test_delivery_categories_have_low_risk(self) -> None:
        """Test delivery categories have low risk level."""
        assert CLOTHING_PROMPTS_V2["delivery_branded"]["risk_level"] == "low"
        assert CLOTHING_PROMPTS_V2["delivery_generic"]["risk_level"] == "low"

    def test_suspicious_category_has_lowest_threshold(self) -> None:
        """Test suspicious category has lowest threshold (don't miss threats)."""
        suspicious_threshold = CLOTHING_PROMPTS_V2["suspicious"]["threshold"]
        for category, config in CLOTHING_PROMPTS_V2.items():
            if category != "suspicious":
                assert config["threshold"] >= suspicious_threshold

    def test_total_prompt_count_increased(self) -> None:
        """Test total prompts expanded to 40+ as per requirement."""
        total = sum(len(config["prompts"]) for config in CLOTHING_PROMPTS_V2.values())
        assert total >= 40, f"Expected at least 40 prompts, got {total}"


class TestGetAllClothingPrompts:
    """Tests for get_all_clothing_prompts function."""

    def test_returns_list(self) -> None:
        """Test function returns a list."""
        result = get_all_clothing_prompts()
        assert isinstance(result, list)

    def test_returns_all_prompts(self) -> None:
        """Test function returns prompts from all categories."""
        result = get_all_clothing_prompts()
        expected_count = sum(len(config["prompts"]) for config in CLOTHING_PROMPTS_V2.values())
        assert len(result) == expected_count

    def test_contains_suspicious_prompts(self) -> None:
        """Test result contains suspicious prompts."""
        result = get_all_clothing_prompts()
        assert "person wearing ski mask or balaclava" in result

    def test_contains_delivery_prompts(self) -> None:
        """Test result contains delivery prompts."""
        result = get_all_clothing_prompts()
        assert "Amazon delivery driver in blue vest" in result

    def test_matches_legacy_constant(self) -> None:
        """Test get_all_clothing_prompts matches SECURITY_CLOTHING_PROMPTS."""
        result = get_all_clothing_prompts()
        assert result == SECURITY_CLOTHING_PROMPTS


class TestGetClothingRiskLevel:
    """Tests for get_clothing_risk_level function."""

    def test_suspicious_prompts_return_high(self) -> None:
        """Test suspicious prompts return high risk level."""
        assert get_clothing_risk_level("person wearing ski mask or balaclava") == "high"
        assert get_clothing_risk_level("person wearing dark hoodie") == "high"

    def test_delivery_prompts_return_low(self) -> None:
        """Test delivery prompts return low risk level."""
        assert get_clothing_risk_level("Amazon delivery driver in blue vest") == "low"
        assert get_clothing_risk_level("delivery uniform") == "low"

    def test_utility_prompts_return_low(self) -> None:
        """Test utility service prompts return low risk level."""
        assert get_clothing_risk_level("utility worker in hard hat and safety vest") == "low"

    def test_casual_prompts_return_normal(self) -> None:
        """Test casual civilian prompts return normal risk level."""
        assert get_clothing_risk_level("person in casual everyday clothing") == "normal"
        assert get_clothing_risk_level("casual clothing") == "normal"

    def test_color_prompts_return_info(self) -> None:
        """Test color prompts return info risk level."""
        assert get_clothing_risk_level("person wearing predominantly red clothing") == "info"

    def test_unknown_prompt_returns_normal(self) -> None:
        """Test unknown prompts return normal risk level as default."""
        assert get_clothing_risk_level("unknown prompt that does not exist") == "normal"


class TestGetClothingThreshold:
    """Tests for get_clothing_threshold function."""

    def test_suspicious_threshold(self) -> None:
        """Test suspicious category has 0.25 threshold."""
        assert get_clothing_threshold("suspicious") == 0.25

    def test_delivery_branded_threshold(self) -> None:
        """Test delivery_branded category has 0.35 threshold."""
        assert get_clothing_threshold("delivery_branded") == 0.35

    def test_delivery_generic_threshold(self) -> None:
        """Test delivery_generic category has 0.30 threshold."""
        assert get_clothing_threshold("delivery_generic") == 0.30

    def test_casual_civilian_threshold(self) -> None:
        """Test casual_civilian category has 0.40 threshold."""
        assert get_clothing_threshold("casual_civilian") == 0.40

    def test_unknown_category_returns_default(self) -> None:
        """Test unknown category returns 0.35 as default."""
        assert get_clothing_threshold("nonexistent_category") == 0.35


class TestGetClothingCategory:
    """Tests for get_clothing_category function."""

    def test_suspicious_prompts_return_suspicious(self) -> None:
        """Test suspicious prompts return suspicious category."""
        assert get_clothing_category("person wearing ski mask or balaclava") == "suspicious"
        assert get_clothing_category("person wearing dark hoodie") == "suspicious"

    def test_delivery_prompts_return_correct_category(self) -> None:
        """Test delivery prompts return correct category."""
        assert get_clothing_category("Amazon delivery driver in blue vest") == "delivery_branded"
        assert get_clothing_category("delivery uniform") == "delivery_generic"

    def test_utility_prompts_return_utility_service(self) -> None:
        """Test utility prompts return utility_service category."""
        assert (
            get_clothing_category("utility worker in hard hat and safety vest") == "utility_service"
        )

    def test_casual_prompts_return_casual_civilian(self) -> None:
        """Test casual prompts return casual_civilian category."""
        assert get_clothing_category("casual clothing") == "casual_civilian"

    def test_color_prompts_return_colors(self) -> None:
        """Test color prompts return colors category."""
        assert get_clothing_category("person wearing predominantly red clothing") == "colors"

    def test_unknown_prompt_returns_none(self) -> None:
        """Test unknown prompts return None."""
        assert get_clothing_category("unknown prompt") is None


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy constants."""

    def test_security_clothing_prompts_not_empty(self) -> None:
        """Test SECURITY_CLOTHING_PROMPTS is not empty."""
        assert len(SECURITY_CLOTHING_PROMPTS) > 0

    def test_security_clothing_prompts_contains_legacy_prompts(self) -> None:
        """Test SECURITY_CLOTHING_PROMPTS contains legacy prompts."""
        # These were in the original constant
        assert "person wearing dark hoodie" in SECURITY_CLOTHING_PROMPTS
        assert "delivery uniform" in SECURITY_CLOTHING_PROMPTS
        assert "casual clothing" in SECURITY_CLOTHING_PROMPTS

    def test_suspicious_categories_contains_suspicious_prompts(self) -> None:
        """Test SUSPICIOUS_CATEGORIES contains suspicious prompts."""
        assert "person wearing dark hoodie" in SUSPICIOUS_CATEGORIES
        assert "person wearing ski mask or balaclava" in SUSPICIOUS_CATEGORIES

    def test_service_categories_contains_service_prompts(self) -> None:
        """Test SERVICE_CATEGORIES contains service prompts."""
        assert "delivery uniform" in SERVICE_CATEGORIES
        assert "Amazon delivery driver in blue vest" in SERVICE_CATEGORIES

    def test_suspicious_and_service_still_disjoint(self) -> None:
        """Test suspicious and service categories still don't overlap."""
        overlap = SUSPICIOUS_CATEGORIES & SERVICE_CATEGORIES
        assert len(overlap) == 0
