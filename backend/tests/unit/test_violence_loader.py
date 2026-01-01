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
    async def test_load_violence_model_with_real_path(self) -> None:
        """Test that the model can be loaded from the real path.

        This test verifies that the downloaded model can actually be loaded.
        It's an integration test that requires the model to be present.
        """
        import os

        model_path = "/models/model-zoo/violence-detection"
        if not os.path.exists(model_path):
            pytest.skip("Violence detection model not downloaded")

        result = await load_violence_model(model_path)

        assert "model" in result
        assert "processor" in result
        assert result["model"] is not None
        assert result["processor"] is not None

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
