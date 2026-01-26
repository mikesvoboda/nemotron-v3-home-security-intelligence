"""Tests for AI/ML pipeline semantic conventions (NEM-3794).

This module tests the semantic attribute conventions and helper functions
for instrumenting AI/ML inference operations in the security monitoring pipeline.
"""

from unittest.mock import MagicMock

import pytest

from backend.core.telemetry_ai_conventions import (
    AI_INFERENCE_BATCH_SIZE,
    AI_INFERENCE_DEVICE,
    AI_INFERENCE_DURATION_MS,
    AI_INFERENCE_PRECISION,
    AI_INFERENCE_STATUS,
    AI_MODEL_NAME,
    AI_MODEL_PROVIDER,
    AI_MODEL_VERSION,
    DETECTION_CLASSES,
    DETECTION_CONFIDENCE_AVG,
    DETECTION_CONFIDENCE_MAX,
    DETECTION_CONFIDENCE_MIN,
    DETECTION_COUNT,
    DETECTION_IMAGE_HEIGHT,
    DETECTION_IMAGE_WIDTH,
    ENRICHMENT_CONFIDENCE,
    ENRICHMENT_MODEL,
    ENRICHMENT_RESULT,
    ENRICHMENT_TYPE,
    LLM_COMPLETION_TOKENS,
    LLM_MAX_TOKENS,
    LLM_PROMPT_TOKENS,
    LLM_PROMPT_VERSION,
    LLM_RISK_SCORE,
    LLM_TEMPERATURE,
    LLM_TOTAL_TOKENS,
    PIPELINE_BATCH_ID,
    PIPELINE_CAMERA_ID,
    PIPELINE_DETECTION_COUNT,
    PIPELINE_STAGE,
    AIModelAttributes,
    set_detection_attributes,
    set_enrichment_attributes,
    set_inference_result_attributes,
    set_llm_inference_attributes,
    set_pipeline_context_attributes,
)


class TestSemanticAttributeNames:
    """Tests for semantic attribute name constants."""

    def test_ai_model_attribute_names(self) -> None:
        """AI model attribute names should follow semantic convention format."""
        assert AI_MODEL_NAME == "ai.model.name"
        assert AI_MODEL_VERSION == "ai.model.version"
        assert AI_MODEL_PROVIDER == "ai.model.provider"

    def test_ai_inference_attribute_names(self) -> None:
        """AI inference attribute names should follow semantic convention format."""
        assert AI_INFERENCE_BATCH_SIZE == "ai.inference.batch_size"
        assert AI_INFERENCE_DURATION_MS == "ai.inference.duration_ms"
        assert AI_INFERENCE_DEVICE == "ai.inference.device"
        assert AI_INFERENCE_PRECISION == "ai.inference.precision"
        assert AI_INFERENCE_STATUS == "ai.inference.status"

    def test_detection_attribute_names(self) -> None:
        """Detection attribute names should follow semantic convention format."""
        assert DETECTION_COUNT == "detection.count"
        assert DETECTION_CONFIDENCE_AVG == "detection.confidence_avg"
        assert DETECTION_CONFIDENCE_MIN == "detection.confidence_min"
        assert DETECTION_CONFIDENCE_MAX == "detection.confidence_max"
        assert DETECTION_CLASSES == "detection.classes"
        assert DETECTION_IMAGE_WIDTH == "detection.image_width"
        assert DETECTION_IMAGE_HEIGHT == "detection.image_height"

    def test_llm_attribute_names(self) -> None:
        """LLM attribute names should follow semantic convention format."""
        assert LLM_PROMPT_TOKENS == "llm.prompt_tokens"
        assert LLM_COMPLETION_TOKENS == "llm.completion_tokens"
        assert LLM_TOTAL_TOKENS == "llm.total_tokens"
        assert LLM_TEMPERATURE == "llm.temperature"
        assert LLM_MAX_TOKENS == "llm.max_tokens"
        assert LLM_PROMPT_VERSION == "llm.prompt_version"
        assert LLM_RISK_SCORE == "llm.risk_score"

    def test_enrichment_attribute_names(self) -> None:
        """Enrichment attribute names should follow semantic convention format."""
        assert ENRICHMENT_MODEL == "enrichment.model"
        assert ENRICHMENT_TYPE == "enrichment.type"
        assert ENRICHMENT_CONFIDENCE == "enrichment.confidence"
        assert ENRICHMENT_RESULT == "enrichment.result"

    def test_pipeline_attribute_names(self) -> None:
        """Pipeline attribute names should follow semantic convention format."""
        assert PIPELINE_CAMERA_ID == "pipeline.camera_id"
        assert PIPELINE_BATCH_ID == "pipeline.batch_id"
        assert PIPELINE_STAGE == "pipeline.stage"
        assert PIPELINE_DETECTION_COUNT == "pipeline.detection_count"


class TestAIModelAttributes:
    """Tests for AIModelAttributes helper class."""

    def test_set_on_span_all_attributes(self) -> None:
        """Should set all provided attributes on span."""
        mock_span = MagicMock()

        AIModelAttributes.set_on_span(
            mock_span,
            model_name="yolo26-v2",
            model_version="1.0.0",
            model_provider="huggingface",
            device="cuda:0",
            precision="fp16",
            batch_size=4,
        )

        assert mock_span.set_attribute.call_count == 6
        mock_span.set_attribute.assert_any_call(AI_MODEL_NAME, "yolo26-v2")
        mock_span.set_attribute.assert_any_call(AI_MODEL_VERSION, "1.0.0")
        mock_span.set_attribute.assert_any_call(AI_MODEL_PROVIDER, "huggingface")
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DEVICE, "cuda:0")
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_PRECISION, "fp16")
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_BATCH_SIZE, 4)

    def test_set_on_span_partial_attributes(self) -> None:
        """Should only set provided attributes."""
        mock_span = MagicMock()

        AIModelAttributes.set_on_span(
            mock_span,
            model_name="nemotron-mini",
            device="cuda:0",
        )

        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call(AI_MODEL_NAME, "nemotron-mini")
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DEVICE, "cuda:0")

    def test_set_on_span_no_attributes(self) -> None:
        """Should not set any attributes when none provided."""
        mock_span = MagicMock()

        AIModelAttributes.set_on_span(mock_span)

        mock_span.set_attribute.assert_not_called()


class TestSetInferenceResultAttributes:
    """Tests for set_inference_result_attributes helper function."""

    def test_set_inference_result_all_attributes(self) -> None:
        """Should set duration and status attributes."""
        mock_span = MagicMock()

        set_inference_result_attributes(
            mock_span,
            duration_ms=150.5,
            status="success",
        )

        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DURATION_MS, 150.5)
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_STATUS, "success")

    def test_set_inference_result_error_status(self) -> None:
        """Should set error status correctly."""
        mock_span = MagicMock()

        set_inference_result_attributes(mock_span, status="error")

        mock_span.set_attribute.assert_any_call(AI_INFERENCE_STATUS, "error")


class TestSetDetectionAttributes:
    """Tests for set_detection_attributes helper function."""

    def test_set_detection_attributes_with_detections(self) -> None:
        """Should compute and set detection statistics from detections list."""
        mock_span = MagicMock()

        detections = [
            {"confidence": 0.95, "class": "person"},
            {"confidence": 0.85, "class": "person"},
            {"confidence": 0.75, "class": "vehicle"},
        ]

        set_detection_attributes(
            mock_span,
            detections=detections,
            inference_time_ms=120.5,
            image_width=1920,
            image_height=1080,
        )

        # Should set count, confidence stats, and classes
        mock_span.set_attribute.assert_any_call(DETECTION_COUNT, 3)
        mock_span.set_attribute.assert_any_call(DETECTION_CONFIDENCE_AVG, pytest.approx(0.85))
        mock_span.set_attribute.assert_any_call(DETECTION_CONFIDENCE_MIN, 0.75)
        mock_span.set_attribute.assert_any_call(DETECTION_CONFIDENCE_MAX, 0.95)
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DURATION_MS, 120.5)
        mock_span.set_attribute.assert_any_call(DETECTION_IMAGE_WIDTH, 1920)
        mock_span.set_attribute.assert_any_call(DETECTION_IMAGE_HEIGHT, 1080)

    def test_set_detection_attributes_empty_detections(self) -> None:
        """Should handle empty detections list."""
        mock_span = MagicMock()

        set_detection_attributes(mock_span, detections=[])

        mock_span.set_attribute.assert_called_once_with(DETECTION_COUNT, 0)

    def test_set_detection_attributes_with_count_only(self) -> None:
        """Should accept detection_count as alternative to detections list."""
        mock_span = MagicMock()

        set_detection_attributes(mock_span, detection_count=5)

        mock_span.set_attribute.assert_called_once_with(DETECTION_COUNT, 5)

    def test_set_detection_attributes_classes_deduplication(self) -> None:
        """Should deduplicate classes before setting attribute."""
        mock_span = MagicMock()

        detections = [
            {"confidence": 0.9, "class": "person"},
            {"confidence": 0.8, "class": "person"},
            {"confidence": 0.7, "class": "person"},
        ]

        set_detection_attributes(mock_span, detections=detections)

        # Find the call that sets DETECTION_CLASSES
        classes_call = None
        for call in mock_span.set_attribute.call_args_list:
            if call[0][0] == DETECTION_CLASSES:
                classes_call = call
                break

        assert classes_call is not None
        assert classes_call[0][1] == "person"  # Only one unique class


class TestSetLLMInferenceAttributes:
    """Tests for set_llm_inference_attributes helper function."""

    def test_set_llm_inference_all_attributes(self) -> None:
        """Should set all LLM inference attributes."""
        mock_span = MagicMock()

        set_llm_inference_attributes(
            mock_span,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            temperature=0.7,
            max_tokens=2048,
            prompt_version="v2",
            risk_score=75,
            inference_time_ms=500.0,
        )

        assert mock_span.set_attribute.call_count == 8
        mock_span.set_attribute.assert_any_call(LLM_PROMPT_TOKENS, 100)
        mock_span.set_attribute.assert_any_call(LLM_COMPLETION_TOKENS, 50)
        mock_span.set_attribute.assert_any_call(LLM_TOTAL_TOKENS, 150)
        mock_span.set_attribute.assert_any_call(LLM_TEMPERATURE, 0.7)
        mock_span.set_attribute.assert_any_call(LLM_MAX_TOKENS, 2048)
        mock_span.set_attribute.assert_any_call(LLM_PROMPT_VERSION, "v2")
        mock_span.set_attribute.assert_any_call(LLM_RISK_SCORE, 75)
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DURATION_MS, 500.0)

    def test_set_llm_inference_partial_attributes(self) -> None:
        """Should only set provided attributes."""
        mock_span = MagicMock()

        set_llm_inference_attributes(
            mock_span,
            prompt_tokens=100,
            completion_tokens=50,
        )

        assert mock_span.set_attribute.call_count == 2

    def test_set_llm_inference_prompt_version_conversion(self) -> None:
        """Should convert prompt version to string."""
        mock_span = MagicMock()

        set_llm_inference_attributes(mock_span, prompt_version=1)

        mock_span.set_attribute.assert_called_with(LLM_PROMPT_VERSION, "1")


class TestSetEnrichmentAttributes:
    """Tests for set_enrichment_attributes helper function."""

    def test_set_enrichment_all_attributes(self) -> None:
        """Should set all enrichment attributes."""
        mock_span = MagicMock()

        set_enrichment_attributes(
            mock_span,
            model_name="vehicle-classifier",
            enrichment_type="vehicle",
            confidence=0.92,
            result="pickup_truck",
            inference_time_ms=45.0,
        )

        assert mock_span.set_attribute.call_count == 5
        mock_span.set_attribute.assert_any_call(ENRICHMENT_MODEL, "vehicle-classifier")
        mock_span.set_attribute.assert_any_call(ENRICHMENT_TYPE, "vehicle")
        mock_span.set_attribute.assert_any_call(ENRICHMENT_CONFIDENCE, 0.92)
        mock_span.set_attribute.assert_any_call(ENRICHMENT_RESULT, "pickup_truck")
        mock_span.set_attribute.assert_any_call(AI_INFERENCE_DURATION_MS, 45.0)

    def test_set_enrichment_result_truncation(self) -> None:
        """Should truncate long result strings to 500 characters."""
        mock_span = MagicMock()

        long_result = "x" * 1000

        set_enrichment_attributes(mock_span, result=long_result)

        # Find the result call
        result_call = None
        for call in mock_span.set_attribute.call_args_list:
            if call[0][0] == ENRICHMENT_RESULT:
                result_call = call
                break

        assert result_call is not None
        assert len(result_call[0][1]) == 500


class TestSetPipelineContextAttributes:
    """Tests for set_pipeline_context_attributes helper function."""

    def test_set_pipeline_context_all_attributes(self) -> None:
        """Should set all pipeline context attributes."""
        mock_span = MagicMock()

        set_pipeline_context_attributes(
            mock_span,
            camera_id="front_door",
            batch_id="batch-123",
            stage="detect",
            detection_count=5,
        )

        assert mock_span.set_attribute.call_count == 4
        mock_span.set_attribute.assert_any_call(PIPELINE_CAMERA_ID, "front_door")
        mock_span.set_attribute.assert_any_call(PIPELINE_BATCH_ID, "batch-123")
        mock_span.set_attribute.assert_any_call(PIPELINE_STAGE, "detect")
        mock_span.set_attribute.assert_any_call(PIPELINE_DETECTION_COUNT, 5)

    def test_set_pipeline_context_partial_attributes(self) -> None:
        """Should only set provided attributes."""
        mock_span = MagicMock()

        set_pipeline_context_attributes(mock_span, camera_id="back_door")

        mock_span.set_attribute.assert_called_once_with(PIPELINE_CAMERA_ID, "back_door")
