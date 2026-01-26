"""Semantic conventions for AI/ML pipeline observability (NEM-3794).

This module defines semantic attribute names and helper functions for instrumenting
AI/ML inference operations in the security monitoring pipeline. Following OpenTelemetry
semantic conventions patterns, these attributes provide standardized observability
for AI model inference across all pipeline components.

Semantic Conventions:
    - ai.model.name: Name of the AI model (e.g., "yolo26-v2", "nemotron-mini")
    - ai.model.version: Model version string
    - ai.model.provider: Model provider (e.g., "huggingface", "nvidia")
    - ai.inference.batch_size: Number of items in inference batch
    - ai.inference.duration_ms: Inference duration in milliseconds
    - ai.inference.device: Device used for inference (e.g., "cuda:0", "cpu")
    - ai.inference.precision: Precision mode (e.g., "fp16", "fp32", "int8")
    - detection.count: Number of detections returned
    - detection.confidence_avg: Average confidence of detections
    - detection.confidence_min: Minimum confidence of detections
    - detection.confidence_max: Maximum confidence of detections
    - detection.classes: List of detected object classes
    - llm.prompt_tokens: Number of prompt tokens (LLM inference)
    - llm.completion_tokens: Number of completion tokens (LLM inference)
    - llm.total_tokens: Total tokens used (LLM inference)
    - llm.temperature: Sampling temperature (LLM inference)
    - llm.max_tokens: Maximum tokens configured (LLM inference)

Usage:
    from backend.core.telemetry_ai_conventions import (
        AIModelAttributes,
        set_detection_attributes,
        set_llm_inference_attributes,
    )

    with trace_span("detect_objects") as span:
        # Set model attributes
        AIModelAttributes.set_on_span(
            span,
            model_name="yolo26-v2",
            model_version="1.0.0",
            device="cuda:0",
        )

        # After inference, set results
        set_detection_attributes(
            span,
            detections=results,
            inference_time_ms=elapsed_ms,
        )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.core.telemetry import SpanProtocol


# =============================================================================
# AI Model Semantic Attribute Names
# =============================================================================

# Model identification
AI_MODEL_NAME = "ai.model.name"
AI_MODEL_VERSION = "ai.model.version"
AI_MODEL_PROVIDER = "ai.model.provider"

# Inference execution
AI_INFERENCE_BATCH_SIZE = "ai.inference.batch_size"
AI_INFERENCE_DURATION_MS = "ai.inference.duration_ms"
AI_INFERENCE_DEVICE = "ai.inference.device"
AI_INFERENCE_PRECISION = "ai.inference.precision"
AI_INFERENCE_STATUS = "ai.inference.status"  # success, error, timeout

# Detection-specific attributes
DETECTION_COUNT = "detection.count"
DETECTION_CONFIDENCE_AVG = "detection.confidence_avg"
DETECTION_CONFIDENCE_MIN = "detection.confidence_min"
DETECTION_CONFIDENCE_MAX = "detection.confidence_max"
DETECTION_CLASSES = "detection.classes"
DETECTION_IMAGE_WIDTH = "detection.image_width"
DETECTION_IMAGE_HEIGHT = "detection.image_height"

# LLM-specific attributes (Nemotron)
LLM_PROMPT_TOKENS = "llm.prompt_tokens"
LLM_COMPLETION_TOKENS = "llm.completion_tokens"
LLM_TOTAL_TOKENS = "llm.total_tokens"
LLM_TEMPERATURE = "llm.temperature"
LLM_MAX_TOKENS = "llm.max_tokens"
LLM_PROMPT_VERSION = "llm.prompt_version"
LLM_RISK_SCORE = "llm.risk_score"

# Enrichment pipeline attributes
ENRICHMENT_MODEL = "enrichment.model"
ENRICHMENT_TYPE = "enrichment.type"  # vehicle, pet, clothing, action, pose
ENRICHMENT_CONFIDENCE = "enrichment.confidence"
ENRICHMENT_RESULT = "enrichment.result"

# Pipeline context attributes
PIPELINE_CAMERA_ID = "pipeline.camera_id"
PIPELINE_BATCH_ID = "pipeline.batch_id"
PIPELINE_STAGE = "pipeline.stage"  # detect, enrich, analyze
PIPELINE_DETECTION_COUNT = "pipeline.detection_count"


class AIModelAttributes:
    """Helper class for setting AI model attributes on spans.

    Provides a fluent interface for setting standardized AI model
    attributes on OpenTelemetry spans.
    """

    @staticmethod
    def set_on_span(
        span: SpanProtocol,
        *,
        model_name: str | None = None,
        model_version: str | None = None,
        model_provider: str | None = None,
        device: str | None = None,
        precision: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        """Set AI model attributes on a span.

        Args:
            span: The span to set attributes on
            model_name: Name of the model (e.g., "yolo26-v2", "nemotron-mini")
            model_version: Version of the model
            model_provider: Provider of the model (e.g., "huggingface", "nvidia")
            device: Device used for inference (e.g., "cuda:0", "cpu")
            precision: Precision mode (e.g., "fp16", "fp32")
            batch_size: Number of items in batch
        """
        if model_name is not None:
            span.set_attribute(AI_MODEL_NAME, model_name)
        if model_version is not None:
            span.set_attribute(AI_MODEL_VERSION, model_version)
        if model_provider is not None:
            span.set_attribute(AI_MODEL_PROVIDER, model_provider)
        if device is not None:
            span.set_attribute(AI_INFERENCE_DEVICE, device)
        if precision is not None:
            span.set_attribute(AI_INFERENCE_PRECISION, precision)
        if batch_size is not None:
            span.set_attribute(AI_INFERENCE_BATCH_SIZE, batch_size)


def set_inference_result_attributes(
    span: SpanProtocol,
    *,
    duration_ms: float | None = None,
    status: str = "success",
) -> None:
    """Set inference result attributes on a span.

    Args:
        span: The span to set attributes on
        duration_ms: Inference duration in milliseconds
        status: Inference status ("success", "error", "timeout")
    """
    if duration_ms is not None:
        span.set_attribute(AI_INFERENCE_DURATION_MS, duration_ms)
    span.set_attribute(AI_INFERENCE_STATUS, status)


def set_detection_attributes(
    span: SpanProtocol,
    *,
    detections: list[dict[str, Any]] | None = None,
    detection_count: int | None = None,
    inference_time_ms: float | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
) -> None:
    """Set detection result attributes on a span.

    Args:
        span: The span to set attributes on
        detections: List of detection dictionaries with 'confidence' and 'class' keys
        detection_count: Number of detections (alternative to passing detections list)
        inference_time_ms: Inference time in milliseconds
        image_width: Input image width
        image_height: Input image height
    """
    if inference_time_ms is not None:
        span.set_attribute(AI_INFERENCE_DURATION_MS, inference_time_ms)

    if image_width is not None:
        span.set_attribute(DETECTION_IMAGE_WIDTH, image_width)
    if image_height is not None:
        span.set_attribute(DETECTION_IMAGE_HEIGHT, image_height)

    if detections is not None:
        count = len(detections)
        span.set_attribute(DETECTION_COUNT, count)

        if count > 0:
            confidences = [d.get("confidence", 0.0) for d in detections if "confidence" in d]
            if confidences:
                span.set_attribute(DETECTION_CONFIDENCE_AVG, sum(confidences) / len(confidences))
                span.set_attribute(DETECTION_CONFIDENCE_MIN, min(confidences))
                span.set_attribute(DETECTION_CONFIDENCE_MAX, max(confidences))

            classes = list({d.get("class", "unknown") for d in detections if "class" in d})
            if classes:
                # Limit to first 10 classes to avoid attribute bloat
                span.set_attribute(DETECTION_CLASSES, ",".join(classes[:10]))

    elif detection_count is not None:
        span.set_attribute(DETECTION_COUNT, detection_count)


def set_llm_inference_attributes(
    span: SpanProtocol,
    *,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    prompt_version: str | int | None = None,
    risk_score: int | None = None,
    inference_time_ms: float | None = None,
) -> None:
    """Set LLM inference attributes on a span.

    Args:
        span: The span to set attributes on
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used (prompt + completion)
        temperature: Sampling temperature
        max_tokens: Maximum tokens configured
        prompt_version: Version of the prompt template used
        risk_score: Risk score from the LLM response
        inference_time_ms: Inference time in milliseconds
    """
    if prompt_tokens is not None:
        span.set_attribute(LLM_PROMPT_TOKENS, prompt_tokens)
    if completion_tokens is not None:
        span.set_attribute(LLM_COMPLETION_TOKENS, completion_tokens)
    if total_tokens is not None:
        span.set_attribute(LLM_TOTAL_TOKENS, total_tokens)
    if temperature is not None:
        span.set_attribute(LLM_TEMPERATURE, temperature)
    if max_tokens is not None:
        span.set_attribute(LLM_MAX_TOKENS, max_tokens)
    if prompt_version is not None:
        span.set_attribute(LLM_PROMPT_VERSION, str(prompt_version))
    if risk_score is not None:
        span.set_attribute(LLM_RISK_SCORE, risk_score)
    if inference_time_ms is not None:
        span.set_attribute(AI_INFERENCE_DURATION_MS, inference_time_ms)


def set_enrichment_attributes(
    span: SpanProtocol,
    *,
    model_name: str | None = None,
    enrichment_type: str | None = None,
    confidence: float | None = None,
    result: str | None = None,
    inference_time_ms: float | None = None,
) -> None:
    """Set enrichment pipeline attributes on a span.

    Args:
        span: The span to set attributes on
        model_name: Name of the enrichment model
        enrichment_type: Type of enrichment (vehicle, pet, clothing, action, pose)
        confidence: Confidence score of the enrichment result
        result: String representation of the enrichment result
        inference_time_ms: Inference time in milliseconds
    """
    if model_name is not None:
        span.set_attribute(ENRICHMENT_MODEL, model_name)
    if enrichment_type is not None:
        span.set_attribute(ENRICHMENT_TYPE, enrichment_type)
    if confidence is not None:
        span.set_attribute(ENRICHMENT_CONFIDENCE, confidence)
    if result is not None:
        # Limit result string to avoid attribute bloat
        span.set_attribute(ENRICHMENT_RESULT, result[:500] if len(result) > 500 else result)
    if inference_time_ms is not None:
        span.set_attribute(AI_INFERENCE_DURATION_MS, inference_time_ms)


def set_pipeline_context_attributes(
    span: SpanProtocol,
    *,
    camera_id: str | None = None,
    batch_id: str | None = None,
    stage: str | None = None,
    detection_count: int | None = None,
) -> None:
    """Set pipeline context attributes on a span.

    Args:
        span: The span to set attributes on
        camera_id: Camera identifier
        batch_id: Batch identifier
        stage: Pipeline stage (detect, enrich, analyze)
        detection_count: Number of detections in the batch
    """
    if camera_id is not None:
        span.set_attribute(PIPELINE_CAMERA_ID, camera_id)
    if batch_id is not None:
        span.set_attribute(PIPELINE_BATCH_ID, batch_id)
    if stage is not None:
        span.set_attribute(PIPELINE_STAGE, stage)
    if detection_count is not None:
        span.set_attribute(PIPELINE_DETECTION_COUNT, detection_count)
