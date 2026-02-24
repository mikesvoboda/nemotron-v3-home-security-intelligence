"""Unit tests for violence detection loader and classification.

Tests cover:
- ViolenceDetectionResult dataclass
- load_violence_model function
- classify_violence function
- Integration with enrichment pipeline
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.violence_loader import (
    ViolenceDetectionResult,
    classify_violence,
    load_violence_model,
)


class TestViolenceDetectionResult:
    """Tests for ViolenceDetectionResult dataclass."""

    def test_violent_result(self) -> None:
        """Test creating a violent detection result."""
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.95,
            violent_score=0.95,
            non_violent_score=0.05,
        )

        assert result.is_violent is True
        assert result.confidence == 0.95
        assert result.violent_score == 0.95
        assert result.non_violent_score == 0.05

    def test_non_violent_result(self) -> None:
        """Test creating a non-violent detection result."""
        result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.85,
            violent_score=0.15,
            non_violent_score=0.85,
        )

        assert result.is_violent is False
        assert result.confidence == 0.85
        assert result.violent_score == 0.15
        assert result.non_violent_score == 0.85

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.9,
            violent_score=0.9,
            non_violent_score=0.1,
        )

        d = result.to_dict()

        assert d["is_violent"] is True
        assert d["confidence"] == 0.9
        assert d["violent_score"] == 0.9
        assert d["non_violent_score"] == 0.1


class TestLoadViolenceModel:
    """Tests for load_violence_model function."""

    @pytest.mark.asyncio
    async def test_load_violence_model_with_real_path(self, monkeypatch) -> None:
        """Test load_violence_model raises RuntimeError on CPU-only hosts (CUDA required)."""
        import sys

        model_path = "/models/model-zoo/violence-detection"

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with pytest.raises(RuntimeError, match="requires CUDA"):
            await load_violence_model(model_path)

    @pytest.mark.asyncio
    async def test_load_violence_model_missing_path(self) -> None:
        """Test that loading from a missing path raises an error."""
        with pytest.raises(RuntimeError) as exc_info:
            await load_violence_model("/nonexistent/path")

        assert "Failed to load violence detection model" in str(exc_info.value)


class TestClassifyViolence:
    """Tests for classify_violence function."""

    @pytest.mark.asyncio
    async def test_classify_violence_violent(self) -> None:
        """Test classifying an image as violent."""
        # Create mock model and processor
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Mock the model config
        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        # Mock the model parameters and cuda check
        mock_param = MagicMock()
        mock_param.is_cuda = False
        mock_model.parameters.return_value = iter([mock_param])

        # Create mock image
        mock_image = MagicMock()

        # Mock processor output
        mock_inputs = {"pixel_values": MagicMock()}
        mock_processor.return_value = mock_inputs

        # Mock model output with violent prediction
        mock_outputs = MagicMock()
        mock_logits = MagicMock()

        # Import torch for tensor mocking
        with patch("torch.no_grad"), patch("torch.nn.functional.softmax") as mock_softmax:
            # Mock softmax to return high violent score
            mock_probs = MagicMock()
            mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
                cpu=lambda: MagicMock(tolist=lambda: [0.1, 0.9])
            )
            mock_softmax.return_value = mock_probs

            mock_outputs.logits = mock_logits
            mock_model.return_value = mock_outputs

            model_data = {"model": mock_model, "processor": mock_processor}
            result = await classify_violence(model_data, mock_image)

            # Note: Due to complex mocking, we just verify the function runs
            # Real testing would require actual model inference
            assert isinstance(result, ViolenceDetectionResult)

    @pytest.mark.asyncio
    async def test_classify_violence_error_handling(self) -> None:
        """Test error handling during classification."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Make processor raise an error
        mock_processor.side_effect = RuntimeError("Processing failed")

        model_data = {"model": mock_model, "processor": mock_processor}
        mock_image = MagicMock()

        with pytest.raises(RuntimeError) as exc_info:
            await classify_violence(model_data, mock_image)

        assert "Violence classification failed" in str(exc_info.value)


class TestViolenceDetectionIntegration:
    """Integration tests for violence detection with model zoo."""

    def test_violence_detection_model_in_zoo(self) -> None:
        """Test that violence detection model is registered in MODEL_ZOO."""
        from backend.services.model_zoo import get_model_config, reset_model_zoo

        reset_model_zoo()

        config = get_model_config("violence-detection")

        assert config is not None
        assert config.name == "violence-detection"
        assert config.category == "classification"
        assert config.vram_mb == 500
        assert config.enabled is True
        assert config.path == "/models/model-zoo/violence-detection"

        reset_model_zoo()

    def test_enrichment_result_has_violence_detection(self) -> None:
        """Test that EnrichmentResult has violence_detection field."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()

        assert hasattr(result, "violence_detection")
        assert result.violence_detection is None
        assert result.has_violence is False

    def test_enrichment_result_has_violence_true(self) -> None:
        """Test has_violence property when violence is detected."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.95,
            violent_score=0.95,
            non_violent_score=0.05,
        )

        assert result.has_violence is True

    def test_enrichment_result_has_violence_false(self) -> None:
        """Test has_violence property when no violence is detected."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.85,
            violent_score=0.15,
            non_violent_score=0.85,
        )

        assert result.has_violence is False

    def test_enrichment_result_to_dict_includes_violence(self) -> None:
        """Test that to_dict includes violence_detection."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.9,
            violent_score=0.9,
            non_violent_score=0.1,
        )

        d = result.to_dict()

        assert "violence_detection" in d
        assert d["violence_detection"]["is_violent"] is True
        assert d["violence_detection"]["confidence"] == 0.9

    def test_enrichment_result_to_context_string_violent(self) -> None:
        """Test to_context_string with violent detection."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.95,
            violent_score=0.95,
            non_violent_score=0.05,
        )

        context = result.to_context_string()

        assert "## Violence Detection" in context
        assert "**VIOLENCE DETECTED**" in context
        assert "95%" in context

    def test_enrichment_result_to_context_string_non_violent(self) -> None:
        """Test to_context_string with non-violent detection."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        result = EnrichmentResult()
        result.violence_detection = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.85,
            violent_score=0.15,
            non_violent_score=0.85,
        )

        context = result.to_context_string()

        assert "## Violence Detection" in context
        assert "No violence detected" in context
        assert "85%" in context


class TestEnrichmentPipelineViolenceDetection:
    """Tests for violence detection in EnrichmentPipeline."""

    def test_pipeline_has_violence_detection_enabled(self) -> None:
        """Test that pipeline has violence_detection_enabled parameter."""
        from backend.services.enrichment_pipeline import (
            EnrichmentPipeline,
            reset_enrichment_pipeline,
        )
        from backend.services.model_zoo import reset_model_manager, reset_model_zoo

        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

        # Check default is enabled
        pipeline = EnrichmentPipeline()
        assert hasattr(pipeline, "violence_detection_enabled")
        assert pipeline.violence_detection_enabled is True

        reset_enrichment_pipeline()
        reset_model_zoo()
        reset_model_manager()

    def test_pipeline_violence_detection_disabled(self) -> None:
        """Test that pipeline can disable violence detection."""
        from backend.services.enrichment_pipeline import (
            EnrichmentPipeline,
            reset_enrichment_pipeline,
        )
        from backend.services.model_zoo import reset_model_manager, reset_model_zoo

        reset_model_zoo()
        reset_model_manager()
        reset_enrichment_pipeline()

        pipeline = EnrichmentPipeline(violence_detection_enabled=False)
        assert pipeline.violence_detection_enabled is False

        reset_enrichment_pipeline()
        reset_model_zoo()
        reset_model_manager()


class TestLoadViolenceModelMocked:
    """Tests for load_violence_model using mocked dependencies."""

    @pytest.mark.asyncio
    async def test_load_violence_model_cpu_path(self, monkeypatch) -> None:
        """Test load_violence_model raises RuntimeError on CPU-only hosts (CUDA required)."""
        import sys

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        mock_transformers = MagicMock()
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with pytest.raises(RuntimeError, match="requires CUDA"):
            await load_violence_model("/test/model/cpu")

    @pytest.mark.asyncio
    async def test_load_violence_model_cuda_path(self, monkeypatch) -> None:
        """Test load_violence_model success path with CUDA available."""
        import sys

        # Create mock torch with CUDA
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        # Create mock model that supports cuda()
        mock_cuda_model = MagicMock()
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

        result = await load_violence_model("/test/model/cuda")

        assert "model" in result
        assert "processor" in result
        mock_model.cuda.assert_called_once()
        mock_cuda_model.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_violence_model_torch_import_error(self, monkeypatch) -> None:
        """Test load_violence_model raises RuntimeError when torch is not available.

        With the CUDA-only guard, the loader raises before reaching any model
        loading logic when torch cannot be imported.
        """
        import sys

        # Setting torch to None in sys.modules causes ImportError on 'import torch'
        monkeypatch.setitem(sys.modules, "torch", None)

        with pytest.raises((RuntimeError, ImportError)):
            await load_violence_model("/test/model/no-torch")

    @pytest.mark.asyncio
    async def test_load_violence_model_transformers_import_error(self, monkeypatch) -> None:
        """Test load_violence_model handles transformers ImportError."""
        import builtins
        import sys

        # Remove transformers from imports if present
        modules_to_hide = ["transformers"]
        hidden_modules = {}
        for mod in modules_to_hide:
            if mod in sys.modules:
                hidden_modules[mod] = sys.modules.pop(mod)

        # Mock import to raise ImportError for transformers
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No module named 'transformers'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        try:
            with pytest.raises(ImportError, match="transformers"):
                await load_violence_model("/fake/path")
        finally:
            # Restore hidden modules
            sys.modules.update(hidden_modules)

    @pytest.mark.asyncio
    async def test_load_violence_model_runtime_error(self, monkeypatch) -> None:
        """Test load_violence_model handles RuntimeError."""
        import sys

        # Mock transformers to exist but fail on model load
        mock_transformers = MagicMock()
        mock_transformers.AutoImageProcessor.from_pretrained.side_effect = RuntimeError(
            "Model not found"
        )

        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with pytest.raises(RuntimeError, match="Failed to load violence detection"):
            await load_violence_model("/nonexistent/path")


class TestClassifyViolenceMocked:
    """Tests for classify_violence using mocked dependencies."""

    @pytest.mark.asyncio
    async def test_classify_violence_cpu_path(self, monkeypatch) -> None:
        """Test classify_violence with CPU model (not on CUDA)."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return probabilities
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.2, 0.8])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model on CPU
        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}

        # Create mock image
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        assert isinstance(result, ViolenceDetectionResult)
        # Inputs should NOT be moved to CUDA since model is on CPU
        assert result.is_violent is True  # 0.8 > 0.2
        assert result.violent_score == 0.8
        assert result.non_violent_score == 0.2

    @pytest.mark.asyncio
    async def test_classify_violence_cuda_path(self, monkeypatch) -> None:
        """Test classify_violence with CUDA model (inputs moved to GPU)."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return probabilities
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.9, 0.1])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model on CUDA
        mock_param = MagicMock()
        mock_param.is_cuda = True

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        # Create mock processor with CUDA-movable inputs
        mock_pixel_values = MagicMock()
        mock_pixel_values.cuda.return_value = MagicMock()
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": mock_pixel_values}

        model_data = {"model": mock_model, "processor": mock_processor}

        # Create mock image
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        assert isinstance(result, ViolenceDetectionResult)
        # Inputs should be moved to CUDA since model is on CUDA
        mock_pixel_values.cuda.assert_called_once()
        assert result.is_violent is False  # 0.1 < 0.9
        assert result.violent_score == 0.1
        assert result.non_violent_score == 0.9

    @pytest.mark.asyncio
    async def test_classify_violence_single_output(self, monkeypatch) -> None:
        """Test classify_violence with binary single output (len(probs) < 2)."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return single probability (binary with single output)
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.75])  # Single output
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model on CPU
        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "violent"}  # Only one class
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}

        # Create mock image
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        assert isinstance(result, ViolenceDetectionResult)
        # With single output, violent_score = probs[0], non_violent = 1 - violent
        assert result.violent_score == 0.75
        assert result.non_violent_score == 0.25
        assert result.is_violent is True  # 0.75 > 0.25

    @pytest.mark.asyncio
    async def test_classify_violence_no_id2label(self, monkeypatch) -> None:
        """Test classify_violence when model has no id2label mapping."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return probabilities
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.3, 0.7])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model without id2label
        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        # Config without id2label attribute
        mock_config = MagicMock(spec=[])  # No id2label
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}

        # Create mock image
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        assert isinstance(result, ViolenceDetectionResult)
        # Default indices: non_violent=0, violent=1
        assert result.violent_score == 0.7
        assert result.non_violent_score == 0.3
        assert result.is_violent is True

    @pytest.mark.asyncio
    async def test_classify_violence_id2label_with_safe(self, monkeypatch) -> None:
        """Test classify_violence when id2label uses 'safe' instead of 'non-violent'."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return probabilities
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.6, 0.4])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model on CPU
        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        # Use 'safe' instead of 'non-violent' - should still be recognized
        mock_config.id2label = {0: "safe", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}

        # Create mock image
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        assert isinstance(result, ViolenceDetectionResult)
        # 'safe' should be recognized as non_violent_idx=0
        assert result.non_violent_score == 0.6
        assert result.violent_score == 0.4
        assert result.is_violent is False


class TestClassifyViolenceCallable:
    """Tests for classify_violence function signature."""

    def test_classify_violence_is_async(self) -> None:
        """Test classify_violence is an async function."""
        import inspect

        assert callable(classify_violence)
        assert inspect.iscoroutinefunction(classify_violence)

    def test_classify_violence_has_correct_parameters(self) -> None:
        """Test classify_violence has expected parameters."""
        import inspect

        sig = inspect.signature(classify_violence)
        assert "model_data" in sig.parameters
        assert "image" in sig.parameters


class TestViolenceDetectionResultEdgeCases:
    """Edge case tests for ViolenceDetectionResult."""

    def test_result_boundary_confidence(self) -> None:
        """Test result with boundary confidence values."""
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=1.0,
            violent_score=1.0,
            non_violent_score=0.0,
        )

        assert result.confidence == 1.0
        assert result.violent_score == 1.0
        assert result.non_violent_score == 0.0

    def test_result_equal_scores(self) -> None:
        """Test result with equal scores (edge case)."""
        result = ViolenceDetectionResult(
            is_violent=False,  # When equal, could go either way
            confidence=0.5,
            violent_score=0.5,
            non_violent_score=0.5,
        )

        d = result.to_dict()
        assert d["violent_score"] == d["non_violent_score"]

    def test_result_to_dict_serializable(self) -> None:
        """Test to_dict output is JSON serializable."""
        import json

        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.87,
            violent_score=0.87,
            non_violent_score=0.13,
        )

        d = result.to_dict()
        # Should be JSON serializable
        json_str = json.dumps(d)
        assert json_str is not None

        # Should round-trip correctly
        parsed = json.loads(json_str)
        assert parsed["is_violent"] is True
        assert parsed["confidence"] == 0.87


# =============================================================================
# TDD Tests for Violence Confidence Tier System (NEM-5483)
# =============================================================================
# These tests define the NEW behavior for confidence-based violence detection
# thresholding. They SHOULD FAIL against the current codebase.
#
# Tier definitions:
# - definitive: violent_score >= 70% -> is_violent=True
# - suspected:  violent_score 55-70% -> is_violent=False (flagged but not violent)
# - marginal:   violent_score < 55%  -> is_violent=False (excluded from prompts)
# =============================================================================


class TestViolenceConfidenceTiers:
    """TDD tests for violence detection confidence tier system.

    These tests define the expected behavior for the new three-tier confidence
    system. They will FAIL until the implementation is complete.

    The tier system addresses false positives by raising the threshold for
    definitive violence detection from 50% to 70%, while still flagging
    suspected violence (55-70%) for human review.
    """

    def test_confidence_tier_definitive(self) -> None:
        """75% violent score should result in 'definitive' tier and is_violent=True.

        Definitive tier (>=70%) represents high-confidence violence detection
        that should trigger immediate alerts and action.
        """
        # This test will FAIL because ViolenceDetectionResult does not have
        # a confidence_tier field yet
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.75,
            violent_score=0.75,
            non_violent_score=0.25,
            confidence_tier="definitive",  # NEW FIELD - will fail until added
        )

        assert result.confidence_tier == "definitive"
        assert result.is_violent is True

    def test_confidence_tier_suspected(self) -> None:
        """62% violent score should result in 'suspected' tier and is_violent=False.

        Suspected tier (55-70%) represents possible violence that should be
        flagged for human review but NOT treated as confirmed violence.
        This is the KEY BEHAVIOR CHANGE from the current 50% threshold.
        """
        # This test will FAIL because:
        # 1. ViolenceDetectionResult does not have confidence_tier field
        # 2. Current code would set is_violent=True for 62% (>50%)
        result = ViolenceDetectionResult(
            is_violent=False,  # NEW behavior - 62% is NOT violent
            confidence=0.62,
            violent_score=0.62,
            non_violent_score=0.38,
            confidence_tier="suspected",  # NEW FIELD
        )

        assert result.confidence_tier == "suspected"
        assert result.is_violent is False  # KEY: suspected tier is NOT violent

    def test_confidence_tier_marginal(self) -> None:
        """51% violent score should result in 'marginal' tier and is_violent=False.

        Marginal tier (<55%) represents low-confidence detections that should
        be excluded from LLM prompts entirely to avoid noise.
        """
        # This test will FAIL because ViolenceDetectionResult does not have
        # a confidence_tier field yet
        result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.51,
            violent_score=0.51,
            non_violent_score=0.49,
            confidence_tier="marginal",  # NEW FIELD
        )

        assert result.confidence_tier == "marginal"
        assert result.is_violent is False

    def test_boundary_70_percent_is_definitive(self) -> None:
        """70% exactly should be 'definitive' tier (boundary test).

        The boundary at 70% is inclusive for definitive tier.
        """
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.70,
            violent_score=0.70,
            non_violent_score=0.30,
            confidence_tier="definitive",  # NEW FIELD
        )

        assert result.confidence_tier == "definitive"
        assert result.is_violent is True

    def test_boundary_below_70_percent_is_suspected(self) -> None:
        """69.9% should be 'suspected' tier (just below definitive boundary).

        This test ensures the boundary condition is correctly handled.
        """
        result = ViolenceDetectionResult(
            is_violent=False,  # NOT violent at 69.9%
            confidence=0.699,
            violent_score=0.699,
            non_violent_score=0.301,
            confidence_tier="suspected",  # NEW FIELD
        )

        assert result.confidence_tier == "suspected"
        assert result.is_violent is False

    def test_boundary_55_percent_is_suspected(self) -> None:
        """55% exactly should be 'suspected' tier (boundary test).

        The boundary at 55% is inclusive for suspected tier.
        """
        result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.55,
            violent_score=0.55,
            non_violent_score=0.45,
            confidence_tier="suspected",  # NEW FIELD
        )

        assert result.confidence_tier == "suspected"
        assert result.is_violent is False

    def test_boundary_below_55_percent_is_marginal(self) -> None:
        """54.9% should be 'marginal' tier (just below suspected boundary).

        This test ensures the boundary condition is correctly handled.
        """
        result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.549,
            violent_score=0.549,
            non_violent_score=0.451,
            confidence_tier="marginal",  # NEW FIELD
        )

        assert result.confidence_tier == "marginal"
        assert result.is_violent is False

    def test_to_dict_includes_confidence_tier(self) -> None:
        """to_dict() should include the confidence_tier field.

        The confidence tier must be serialized for API responses and
        database storage.
        """
        result = ViolenceDetectionResult(
            is_violent=True,
            confidence=0.85,
            violent_score=0.85,
            non_violent_score=0.15,
            confidence_tier="definitive",  # NEW FIELD
        )

        d = result.to_dict()

        # This assertion will FAIL until to_dict() is updated
        assert "confidence_tier" in d
        assert d["confidence_tier"] == "definitive"

    def test_to_dict_confidence_tier_json_serializable(self) -> None:
        """Confidence tier in to_dict() should be JSON serializable."""
        import json

        result = ViolenceDetectionResult(
            is_violent=False,
            confidence=0.60,
            violent_score=0.60,
            non_violent_score=0.40,
            confidence_tier="suspected",  # NEW FIELD
        )

        d = result.to_dict()
        json_str = json.dumps(d)

        # Verify round-trip preserves confidence_tier
        parsed = json.loads(json_str)
        assert parsed["confidence_tier"] == "suspected"


class TestClassifyViolenceConfidenceTiers:
    """TDD tests for classify_violence function with confidence tier calculation.

    These tests verify that the classify_violence function correctly assigns
    confidence tiers based on the violent_score thresholds.
    """

    @pytest.mark.asyncio
    async def test_classify_violence_assigns_definitive_tier(self, monkeypatch) -> None:
        """classify_violence should assign 'definitive' tier for scores >= 70%."""
        import sys

        # Create mock torch
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return 80% violent score (definitive tier)
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.2, 0.8])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        # Create mock model
        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        # These assertions will FAIL until classify_violence is updated
        assert result.confidence_tier == "definitive"
        assert result.is_violent is True
        assert result.violent_score == 0.8

    @pytest.mark.asyncio
    async def test_classify_violence_assigns_suspected_tier(self, monkeypatch) -> None:
        """classify_violence should assign 'suspected' tier for scores 55-70%."""
        import sys

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return 62% violent score (suspected tier)
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.38, 0.62])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        # These assertions will FAIL:
        # 1. confidence_tier field doesn't exist
        # 2. is_violent would be True with current 50% threshold
        assert result.confidence_tier == "suspected"
        assert result.is_violent is False  # KEY: 62% should NOT be violent
        assert result.violent_score == 0.62

    @pytest.mark.asyncio
    async def test_classify_violence_assigns_marginal_tier(self, monkeypatch) -> None:
        """classify_violence should assign 'marginal' tier for scores < 55%."""
        import sys

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock()
        mock_torch.no_grad.return_value.__exit__ = MagicMock()

        # Mock softmax to return 52% violent score (marginal tier)
        mock_probs = MagicMock()
        mock_probs.__getitem__ = lambda _self, _idx: MagicMock(
            cpu=lambda: MagicMock(tolist=lambda: [0.48, 0.52])
        )
        mock_torch.nn.functional.softmax.return_value = mock_probs

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        mock_param = MagicMock()
        mock_param.is_cuda = False

        mock_model = MagicMock()
        mock_model.parameters.return_value = iter([mock_param])

        mock_config = MagicMock()
        mock_config.id2label = {0: "non-violent", 1: "violent"}
        mock_model.config = mock_config

        mock_outputs = MagicMock()
        mock_outputs.logits = MagicMock()
        mock_model.return_value = mock_outputs

        mock_processor = MagicMock()
        mock_processor.return_value = {"pixel_values": MagicMock()}

        model_data = {"model": mock_model, "processor": mock_processor}
        mock_image = MagicMock()

        result = await classify_violence(model_data, mock_image)

        # These assertions will FAIL:
        # 1. confidence_tier field doesn't exist
        # 2. is_violent would be True with current 50% threshold (52% > 50%)
        assert result.confidence_tier == "marginal"
        assert result.is_violent is False
        assert result.violent_score == 0.52
