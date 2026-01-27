"""Nemotron analyzer service for LLM-based risk assessment.

This service analyzes batches of detections using the Nemotron LLM
via llama.cpp server to generate risk scores and natural language summaries.

Analysis Flow:
    1. Fetch batch detections from Redis/database
    2. Enrich context with zones, baselines, and cross-camera activity
    3. Run enrichment pipeline for license plates, faces, OCR (optional)
    4. Format prompt with enriched detection details
    5. Acquire shared AI inference semaphore (NEM-1463)
    6. POST to llama.cpp completion endpoint (with retry on transient failures)
    7. Release semaphore
    8. Parse JSON response
    9. Create Event with risk assessment
    10. Store Event in database
    11. Broadcast via WebSocket (if available)

Concurrency Control (NEM-1463):
    Uses a shared asyncio.Semaphore to limit concurrent AI inference operations.
    This prevents GPU/AI service overload under high traffic. The limit is
    configurable via AI_MAX_CONCURRENT_INFERENCES setting (default: 4).

Retry Logic (NEM-1343):
    - Configurable max retries via NEMOTRON_MAX_RETRIES setting (default: 3)
    - Exponential backoff: 2^attempt seconds between retries (capped at 30s)
    - Only retries transient failures (connection, timeout, HTTP 5xx)
"""

__all__ = [
    "NEMOTRON_CONNECT_TIMEOUT",
    "NEMOTRON_HEALTH_TIMEOUT",
    "NEMOTRON_READ_TIMEOUT",
    "RISK_ANALYSIS_JSON_SCHEMA",
    "AnalyzerUnavailableError",
    "NemotronAnalyzer",
    "extract_reasoning_and_response",
]

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import select

from backend.api.middleware.correlation import get_correlation_headers
from backend.api.schemas.llm_response import (
    RISK_ANALYSIS_JSON_SCHEMA,
    LLMRawResponse,
    LLMRiskResponse,
)
from backend.api.schemas.outbound_webhook import WebhookEventType
from backend.core.config import get_settings
from backend.core.constants import CacheInvalidationReason
from backend.core.database import get_session
from backend.core.exceptions import AnalyzerUnavailableError
from backend.core.logging import get_logger, log_context, sanitize_error
from backend.core.metrics import (
    observe_ai_request_duration,
    observe_risk_score,
    observe_stage_duration,
    record_event_by_camera,
    record_event_by_risk_level,
    record_event_created,
    record_nemotron_tokens,
    record_pipeline_error,
    record_prompt_template_used,
)
from backend.core.redis import RedisClient
from backend.core.telemetry import (
    add_span_attributes,
    add_span_event,
    get_tracer,
    record_exception,
)
from backend.core.telemetry_ai_conventions import (
    AIModelAttributes,
    set_inference_result_attributes,
    set_llm_inference_attributes,
    set_pipeline_context_attributes,
)
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event

# Service facade for reduced coupling (NEM-3150)
# Instead of importing 8+ services directly, we use a facade that aggregates
# commonly-used service operations. Direct imports are kept only for:
# 1. Type hints needed in method signatures
# 2. Constants/enums that are part of the public API
from backend.services.analyzer_facade import (
    AnalyzerServiceFacade,
    get_analyzer_facade,
)
from backend.services.context_enricher import ContextEnricher, EnrichedContext
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
    EnrichmentStatus,
    EnrichmentTrackingResult,
)
from backend.services.prompt_sanitizer import (
    sanitize_camera_name,
    sanitize_detection_description,
)
from backend.services.prompts import (
    ENRICHED_RISK_ANALYSIS_PROMPT,
    FULL_ENRICHED_RISK_ANALYSIS_PROMPT,
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
    RISK_ANALYSIS_PROMPT,
    VISION_ENHANCED_RISK_ANALYSIS_PROMPT,
    format_action_recognition_context,
    format_camera_health_context,
    format_clothing_analysis_context,
    format_depth_context,
    format_detections_with_all_enrichment,
    format_household_context,
    format_image_quality_context,
    format_pet_classification_context,
    format_pose_analysis_context,
    format_vehicle_classification_context,
    format_vehicle_damage_context,
    format_violence_context,
    format_weather_context,
)
from backend.services.webhook_service import get_webhook_service

# Pre-compiled regex patterns for LLM response parsing
# These are compiled once at module load time for better performance
_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_EXTRACT_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)
_JSON_PATTERN = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)

logger = get_logger(__name__)


def extract_reasoning_and_response(text: str) -> tuple[str, str]:
    """Extract chain-of-thought reasoning and final JSON response from LLM output.

    Nemotron models with 'detailed thinking on' enabled output reasoning in
    <think>...</think> tags before the JSON response. This function separates
    the reasoning from the response for structured storage and analysis.

    Args:
        text: Raw LLM completion text that may contain <think>...</think> blocks
            followed by JSON response.

    Returns:
        A tuple of (reasoning, json_response) where:
        - reasoning: The content extracted from <think>...</think> tags,
            or empty string if no think block is present
        - json_response: The remaining text after removing think blocks,
            which should contain the JSON response

    Examples:
        >>> text = "<think>Analyzing the scene...</think>{\"risk_score\": 25}"
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        'Analyzing the scene...'
        >>> response
        '{"risk_score": 25}'

        >>> # Text without think blocks
        >>> text = '{"risk_score": 25, "risk_level": "low"}'
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        ''
        >>> response
        '{"risk_score": 25, "risk_level": "low"}'

        >>> # Handles malformed/incomplete tags gracefully
        >>> text = "<think>Incomplete reasoning"
        >>> reasoning, response = extract_reasoning_and_response(text)
        >>> reasoning
        ''  # No closing tag, so no reasoning extracted
        >>> response
        '<think>Incomplete reasoning'

    Note:
        This function is designed to work with Nemotron's chain-of-thought
        reasoning feature (NEM-3727). The reasoning content can be stored
        separately for debugging, auditing, and model improvement.
    """
    # Try to extract content from <think>...</think> blocks
    think_match = _THINK_EXTRACT_PATTERN.search(text)

    if think_match:
        # Extract reasoning content (strip whitespace for cleaner output)
        reasoning = think_match.group(1).strip()

        # Remove all think blocks from text to get the response
        # Uses the existing _THINK_PATTERN for consistency
        json_response = _THINK_PATTERN.sub("", text).strip()

        return reasoning, json_response

    # No think block found - return empty reasoning and original text
    return "", text.strip()


# OpenTelemetry tracer for LLM inference instrumentation (NEM-1467)
# Returns a no-op tracer if OTEL is not enabled
tracer = get_tracer(__name__)

# Timeout configuration for Nemotron LLM service
# - connect_timeout: Maximum time to establish connection (10s)
# - read_timeout: Maximum time to wait for LLM response (120s for complex inference)
NEMOTRON_CONNECT_TIMEOUT = 10.0
NEMOTRON_READ_TIMEOUT = 120.0
NEMOTRON_HEALTH_TIMEOUT = 5.0


class NemotronAnalyzer:
    """Analyzes detection batches using Nemotron LLM for risk assessment.

    This service coordinates with the batch aggregator to receive completed
    batches, queries the database for detection details, formats a prompt
    for the LLM, and creates Events with risk scores and summaries.

    Features:
        - Retry logic with exponential backoff for transient failures (NEM-1343)
        - Configurable timeouts and retry attempts via settings
        - Context enrichment with zone, baseline, and cross-camera data
        - Enrichment pipeline for license plates, faces, and OCR

    With context enrichment enabled, the analyzer will include zone information,
    baseline deviation data, and cross-camera activity in the prompt.

    With the enrichment pipeline enabled, the analyzer will also extract:
    - License plates from vehicle detections (with OCR)
    - Faces from person detections
    """

    def __init__(
        self,
        redis_client: RedisClient | None = None,
        context_enricher: ContextEnricher | None = None,
        enrichment_pipeline: EnrichmentPipeline | None = None,
        use_enriched_context: bool = True,
        use_enrichment_pipeline: bool = True,
        max_retries: int | None = None,
        service_facade: AnalyzerServiceFacade | None = None,
    ):
        """Initialize Nemotron analyzer with Redis client.

        Args:
            redis_client: Redis client instance for queue and cache operations.
            context_enricher: Optional context enricher for enhanced prompts.
                If not provided and use_enriched_context is True, will use the
                global singleton via the service facade.
            enrichment_pipeline: Optional enrichment pipeline for license plates,
                faces, and OCR. If not provided and use_enrichment_pipeline is True,
                will use the global singleton via the service facade.
            use_enriched_context: Whether to use enriched context in prompts.
                Set to False for basic analysis without zone/baseline data.
            use_enrichment_pipeline: Whether to run the enrichment pipeline for
                license plates and faces. Set to False to skip this step.
            max_retries: Maximum retry attempts for transient LLM failures.
                If not provided, uses NEMOTRON_MAX_RETRIES from settings (default: 3).
            service_facade: Optional service facade for accessing dependent services.
                If not provided, uses the global singleton. Passing a custom facade
                simplifies testing by providing a single mock target (NEM-3150).
        """
        self._redis = redis_client
        settings = get_settings()
        self._llm_url = settings.nemotron_url
        # Security: Store API key for authentication (None if not configured)
        self._api_key = settings.nemotron_api_key
        # Use httpx.Timeout for proper timeout configuration from Settings
        # connect: time to establish connection, read: time to wait for LLM response
        self._timeout = httpx.Timeout(
            connect=settings.ai_connect_timeout,
            read=settings.nemotron_read_timeout,
            write=settings.nemotron_read_timeout,
            pool=settings.ai_connect_timeout,
        )
        self._health_timeout = httpx.Timeout(
            connect=settings.ai_health_timeout,
            read=settings.ai_health_timeout,
            write=settings.ai_health_timeout,
            pool=settings.ai_health_timeout,
        )
        self._use_enriched_context = use_enriched_context
        self._use_enrichment_pipeline = use_enrichment_pipeline
        self._context_enricher = context_enricher
        self._enrichment_pipeline = enrichment_pipeline
        # Service facade for reduced coupling (NEM-3150)
        # Provides access to cache, cost tracking, inference semaphore, etc.
        self._facade = service_facade
        # Retry configuration (NEM-1343)
        self._max_retries = (
            max_retries if max_retries is not None else settings.nemotron_max_retries
        )
        # Cold start and warmup tracking (NEM-1670)
        self._last_inference_time: float | None = None
        self._is_warming: bool = False
        self._warmup_enabled = settings.ai_warmup_enabled
        self._cold_start_threshold = settings.ai_cold_start_threshold_seconds
        self._warmup_prompt = settings.nemotron_warmup_prompt

        # A/B Testing support (NEM-1667)
        self._ab_tester: Any | None = None  # PromptABTester when configured
        self._ab_config: Any | None = None  # ABTestConfig when configured

        # Prompt Experiment support (NEM-3023)
        self._experiment_config: Any | None = None  # PromptExperimentConfig when configured

        # A/B Rollout Manager support (NEM-3338)
        self._rollout_manager: Any | None = None  # ABRolloutManager when configured

        # Structured Generation support (NEM-3726)
        # NVIDIA NIM's guided_json parameter enforces valid JSON output
        self._use_guided_json = settings.nemotron_use_guided_json
        self._guided_json_fallback = settings.nemotron_guided_json_fallback
        self._supports_guided_json: bool | None = None  # Cached capability check

        logger.debug(
            f"NemotronAnalyzer initialized with max_retries={self._max_retries}, "
            f"timeout={settings.nemotron_read_timeout}s, "
            f"guided_json={self._use_guided_json}"
        )

    # =========================================================================
    # Structured Generation Support (NEM-3726)
    # =========================================================================

    async def _check_guided_json_support(self) -> bool:
        """Check if the Nemotron endpoint supports guided_json parameter.

        NVIDIA NIM endpoints support structured generation via the guided_json
        parameter in the nvext namespace. This method probes the endpoint with
        a minimal test request to detect support.

        The result is cached after the first check to avoid repeated probes.

        Returns:
            True if endpoint supports guided_json, False otherwise
        """
        # Return cached result if available
        if self._supports_guided_json is not None:
            return self._supports_guided_json

        # Try a minimal test request with guided_json
        test_schema = {"type": "object", "properties": {"test": {"type": "string"}}}
        result = False  # Default to not supported

        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                # Send a minimal completion request with guided_json
                response = await client.post(
                    f"{self._llm_url}/completion",
                    headers=self._get_auth_headers(),
                    json={
                        "prompt": "Say hello",
                        "max_tokens": 10,
                        "temperature": 0.0,
                        "nvext": {"guided_json": test_schema},
                    },
                )

                # If we get a 2xx response, the endpoint likely supports guided_json
                # Some endpoints may return 200 but ignore the parameter
                if response.status_code < 300:
                    self._supports_guided_json = True
                    logger.info(
                        "Nemotron endpoint supports guided_json structured generation",
                        extra={"llm_url": self._llm_url},
                    )
                    result = True
                # 4xx errors indicate the endpoint doesn't support guided_json
                # (e.g., 422 Unprocessable Entity for unknown parameters)
                elif 400 <= response.status_code < 500:
                    self._supports_guided_json = False
                    logger.info(
                        "Nemotron endpoint does not support guided_json, using regex fallback",
                        extra={"llm_url": self._llm_url, "status_code": response.status_code},
                    )

        except httpx.HTTPStatusError as e:
            # 4xx status errors indicate unsupported parameter
            if 400 <= e.response.status_code < 500:
                self._supports_guided_json = False
                logger.info(
                    "Nemotron endpoint does not support guided_json (HTTP error), using regex fallback",
                    extra={"llm_url": self._llm_url, "status_code": e.response.status_code},
                )
            else:
                # 5xx errors are transient - don't cache, try again later
                logger.warning(
                    "Failed to check guided_json support (server error), will retry",
                    extra={"llm_url": self._llm_url, "error": str(e)},
                )

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            # Connection issues are transient - don't cache, try again later
            logger.warning(
                "Failed to check guided_json support (connection error), will retry",
                extra={"llm_url": self._llm_url, "error": str(e)},
            )

        except Exception as e:
            # Unexpected errors - don't cache, try again later
            logger.warning(
                "Failed to check guided_json support (unexpected error), will retry",
                extra={"llm_url": self._llm_url, "error": str(e)},
            )

        return result

    def _build_guided_json_extra_body(self) -> dict[str, Any]:
        """Build the extra_body dict with guided_json schema for NVIDIA NIM.

        Returns:
            Dictionary with nvext.guided_json set to RISK_ANALYSIS_JSON_SCHEMA,
            or empty dict if guided_json is disabled
        """
        if not self._use_guided_json:
            return {}

        return {"nvext": {"guided_json": RISK_ANALYSIS_JSON_SCHEMA}}

    def is_guided_json_enabled(self) -> bool:
        """Check if guided_json is enabled via configuration.

        Returns:
            True if guided_json is enabled in settings
        """
        return self._use_guided_json

    def is_guided_json_fallback_enabled(self) -> bool:
        """Check if fallback to regex parsing is enabled.

        Returns:
            True if fallback is enabled in settings
        """
        return self._guided_json_fallback

    async def supports_guided_json(self) -> bool:
        """Check if the endpoint supports guided_json.

        Public method for checking guided_json support. Uses cached result
        when available.

        Returns:
            True if endpoint supports guided_json, False otherwise
        """
        return await self._check_guided_json_support()

    def reset_guided_json_support_cache(self) -> None:
        """Reset the cached guided_json support check.

        Useful for testing or when the endpoint configuration changes.
        """
        self._supports_guided_json = None

    # =========================================================================
    # A/B Testing Support (NEM-1667)
    # =========================================================================

    def set_ab_test_config(self, config: Any) -> None:
        """Configure A/B testing for prompt versions.

        Args:
            config: ABTestConfig instance
        """
        from backend.services.prompt_service import ABTestConfig, PromptABTester

        if not isinstance(config, ABTestConfig):
            raise TypeError("config must be an ABTestConfig instance")

        self._ab_config = config
        self._ab_tester = PromptABTester(config)
        logger.info(
            f"A/B testing configured: control=v{config.control_version}, "
            f"treatment=v{config.treatment_version}, split={config.traffic_split:.1%}"
        )

    async def get_prompt_version(self) -> tuple[int, bool]:
        """Get the prompt version to use for this request.

        Uses A/B testing if configured, otherwise returns default version.

        Returns:
            Tuple of (version_number, is_treatment)
        """
        if self._ab_tester is not None:
            result: tuple[int, bool] = self._ab_tester.select_prompt_version()
            return result
        return (1, False)  # Default version

    def _record_analysis_metrics(
        self,
        prompt_version: int,
        latency_seconds: float,
        risk_score: int | float,  # noqa: ARG002 - Reserved for future variance tracking
    ) -> None:
        """Record metrics for prompt analysis execution.

        Args:
            prompt_version: Prompt version used
            latency_seconds: Execution latency in seconds
            risk_score: Risk score returned (for future variance tracking)
        """
        from backend.core.metrics import record_prompt_latency

        record_prompt_latency(f"v{prompt_version}", latency_seconds)

    # =========================================================================
    # Prompt Experiment Support (NEM-3023)
    # =========================================================================

    def get_experiment_config(self) -> Any:
        """Get the prompt experiment configuration.

        Returns a PromptExperimentConfig with current settings. If no
        custom config has been set, returns the global singleton.

        Returns:
            PromptExperimentConfig instance
        """
        from backend.config.prompt_experiment import (
            get_prompt_experiment_config,
        )

        if self._experiment_config is not None:
            return self._experiment_config
        return get_prompt_experiment_config()

    def set_experiment_config(self, config: Any) -> None:
        """Set a custom experiment configuration.

        Args:
            config: PromptExperimentConfig instance

        Raises:
            TypeError: If config is not a PromptExperimentConfig
        """
        from backend.config.prompt_experiment import PromptExperimentConfig

        if not isinstance(config, PromptExperimentConfig):
            raise TypeError("config must be a PromptExperimentConfig instance")

        self._experiment_config = config
        logger.info(
            f"Experiment config set: shadow_mode={config.shadow_mode}, "
            f"treatment={config.treatment_percentage:.1%}, "
            f"experiment={config.experiment_name}"
        )

    def get_version_for_analysis(self, camera_id: str) -> Any:
        """Get the prompt version to use for a specific camera.

        Uses the experiment config to determine which prompt version
        to use. In shadow mode, always returns V1_ORIGINAL. In A/B
        test mode, uses hash-based assignment for consistency.

        Args:
            camera_id: Camera identifier for consistent version assignment

        Returns:
            PromptVersion to use for this camera
        """
        config = self.get_experiment_config()
        return config.get_version_for_camera(camera_id)

    async def run_shadow_analysis(
        self,
        camera_id: str,
        context: str,
    ) -> dict[str, Any]:
        """Run shadow mode analysis with both prompt versions.

        In shadow mode, runs both V1 and V2 prompts but returns V1 results
        as the primary output. V2 results are logged for comparison analysis.

        Args:
            camera_id: Camera identifier
            context: Detection context for analysis

        Returns:
            Dictionary containing:
            - primary_result: V1 analysis result (used as actual result)
            - shadow_result: V2 analysis result (for comparison only)
            - score_diff: Absolute difference in risk scores
            - v1_latency_ms: V1 prompt latency
            - v2_latency_ms: V2 prompt latency
        """
        import time as time_module

        from backend.config.prompt_experiment import PromptVersion

        config = self.get_experiment_config()

        # Run V1 (control) prompt
        v1_start = time_module.monotonic()
        try:
            v1_result = await self._call_llm_with_version(
                context, prompt_version=PromptVersion.V1_ORIGINAL.value
            )
        except Exception as e:
            logger.error(f"V1 prompt failed in shadow analysis: {e}")
            raise
        v1_latency_ms = (time_module.monotonic() - v1_start) * 1000

        # In shadow mode, also run V2 (treatment) prompt
        v2_result = None
        v2_latency_ms = 0.0
        score_diff = 0.0

        if config.shadow_mode:
            try:
                v2_start = time_module.monotonic()
                v2_result = await self._call_llm_with_version(
                    context, prompt_version=PromptVersion.V2_CALIBRATED.value
                )
                v2_latency_ms = (time_module.monotonic() - v2_start) * 1000

                # Calculate score difference
                v1_score = v1_result.get("risk_score", 0)
                v2_score = v2_result.get("risk_score", 0)
                score_diff = abs(v1_score - v2_score)

                # Log shadow result for analysis
                await self._log_shadow_result(
                    camera_id=camera_id,
                    v1_result=v1_result,
                    v2_result=v2_result,
                    v1_latency_ms=v1_latency_ms,
                    v2_latency_ms=v2_latency_ms,
                )

            except Exception as e:
                logger.warning(f"Shadow (V2) prompt failed, continuing with V1: {e}")

        return {
            "primary_result": v1_result,
            "shadow_result": v2_result,
            "score_diff": score_diff,
            "v1_latency_ms": v1_latency_ms,
            "v2_latency_ms": v2_latency_ms,
        }

    async def _call_llm_with_version(
        self,
        context: str,
        prompt_version: str = "v1_original",  # noqa: ARG002 - reserved for A/B testing
    ) -> dict[str, Any]:
        """Call LLM with a specific prompt version.

        This is a wrapper around the existing LLM call logic that selects
        the appropriate prompt template based on the version.

        Args:
            context: Detection context for analysis (pre-formatted prompt)
            prompt_version: Prompt version identifier ("v1_original" or "v2_calibrated")
                           Currently unused but reserved for NEM-3023 A/B testing.

        Returns:
            LLM response as dict

        Raises:
            httpx.HTTPError: If LLM request fails
            ValueError: If response cannot be parsed
        """
        # Use the context as the prompt directly
        # The prompt template selection based on version will be implemented later
        # For now, just call the LLM with the provided context
        from backend.core.config import get_settings

        settings = get_settings()
        max_output_tokens = settings.nemotron_max_output_tokens

        payload = {
            "prompt": context,
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": max_output_tokens,
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        headers = {"Content-Type": "application/json"}
        headers.update(self._get_auth_headers())

        # Make the HTTP call (this will be mocked in tests)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._llm_url}/completion",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            llm_result = response.json()

        # Extract completion text
        completion_text = llm_result.get("content", "")
        if not completion_text:
            raise ValueError("Empty completion from LLM")

        # Parse JSON from completion
        risk_data = self._parse_llm_response(completion_text)

        # Validate and normalize risk data
        risk_data = self._validate_risk_data(risk_data)

        return risk_data

    async def _log_shadow_result(
        self,
        camera_id: str,
        v1_result: dict[str, Any],
        v2_result: dict[str, Any],
        v1_latency_ms: float = 0.0,
        v2_latency_ms: float = 0.0,
    ) -> None:
        """Log shadow mode comparison result for analysis.

        Records the comparison between V1 and V2 results including:
        - Risk score difference
        - Latency difference
        - Camera ID for filtering

        This data is used to evaluate V2 prompt performance before
        transitioning from shadow mode to A/B testing.

        Args:
            camera_id: Camera identifier
            v1_result: V1 (control) analysis result
            v2_result: V2 (treatment) analysis result
            v1_latency_ms: V1 latency in milliseconds
            v2_latency_ms: V2 latency in milliseconds
        """
        from backend.core.metrics import record_shadow_comparison

        v1_score = v1_result.get("risk_score", 0)
        v2_score = v2_result.get("risk_score", 0)
        score_diff = abs(v1_score - v2_score)

        # Record metrics for monitoring
        record_shadow_comparison("nemotron")

        logger.info(
            "Shadow comparison result",
            extra={
                "camera_id": camera_id,
                "v1_score": v1_score,
                "v2_score": v2_score,
                "score_diff": score_diff,
                "v1_latency_ms": v1_latency_ms,
                "v2_latency_ms": v2_latency_ms,
                "latency_diff_ms": v2_latency_ms - v1_latency_ms,
            },
        )

    def _record_experiment_result(
        self,
        camera_id: str,
        version: Any,
        risk_score: int | float,
        latency_ms: float,
    ) -> None:
        """Record experiment result metrics.

        Args:
            camera_id: Camera identifier
            version: PromptVersion used
            risk_score: Risk score from analysis
            latency_ms: Analysis latency in milliseconds
        """
        from backend.core.metrics import record_prompt_latency

        record_prompt_latency(version.value, latency_ms / 1000)
        logger.debug(
            "Experiment result recorded",
            extra={
                "camera_id": camera_id,
                "version": version.value,
                "risk_score": risk_score,
                "latency_ms": latency_ms,
            },
        )

    # =========================================================================
    # A/B Rollout Manager Support (NEM-3338)
    # =========================================================================

    def set_rollout_manager(self, manager: Any) -> None:
        """Set the A/B rollout manager for experiment orchestration.

        The rollout manager handles:
        - Camera-to-group assignment (control vs treatment)
        - Metrics collection per group
        - Auto-rollback based on performance thresholds

        Args:
            manager: ABRolloutManager instance

        Raises:
            TypeError: If manager is not an ABRolloutManager instance
        """
        from backend.config.prompt_ab_rollout import ABRolloutManager

        if not isinstance(manager, ABRolloutManager):
            raise TypeError("manager must be an ABRolloutManager instance")

        self._rollout_manager = manager
        logger.info(
            f"A/B rollout manager configured: "
            f"experiment={manager.rollout_config.experiment_name}, "
            f"treatment={manager.rollout_config.treatment_percentage:.0%}, "
            f"active={manager.is_active}"
        )

    def get_rollout_manager(self) -> Any | None:
        """Get the configured rollout manager.

        Returns:
            ABRolloutManager instance if configured, None otherwise
        """
        return self._rollout_manager

    def get_experiment_group(self, camera_id: str) -> Any:
        """Get the experiment group for a camera.

        Uses the rollout manager to determine which group (control or treatment)
        the camera belongs to. Assignment is consistent based on camera_id hash.

        Args:
            camera_id: Camera identifier

        Returns:
            ExperimentGroup.CONTROL or ExperimentGroup.TREATMENT

        Raises:
            RuntimeError: If no rollout manager is configured
        """
        if self._rollout_manager is None:
            raise RuntimeError("No rollout manager configured")

        return self._rollout_manager.get_group_for_camera(camera_id)

    def get_prompt_version_for_rollout(self, camera_id: str) -> Any:
        """Get the prompt version to use based on rollout experiment group.

        Control group uses V1_ORIGINAL, treatment group uses V2_CALIBRATED.

        Args:
            camera_id: Camera identifier

        Returns:
            PromptVersion.V1_ORIGINAL or PromptVersion.V2_CALIBRATED
        """
        from backend.config.prompt_ab_rollout import ExperimentGroup
        from backend.config.prompt_experiment import PromptVersion

        if self._rollout_manager is None:
            return PromptVersion.V1_ORIGINAL

        group = self._rollout_manager.get_group_for_camera(camera_id)
        if group == ExperimentGroup.TREATMENT:
            return PromptVersion.V2_CALIBRATED
        return PromptVersion.V1_ORIGINAL

    def record_rollout_analysis(
        self,
        camera_id: str,
        latency_ms: float | None = None,
        risk_score: int | None = None,
        has_error: bool = False,
    ) -> None:
        """Record analysis metrics for the rollout experiment.

        Automatically routes metrics to the correct group based on camera_id.

        Args:
            camera_id: Camera identifier (determines group)
            latency_ms: Optional analysis latency in milliseconds
            risk_score: Optional risk score from analysis
            has_error: Whether the analysis resulted in an error
        """
        if self._rollout_manager is None:
            return

        from backend.config.prompt_ab_rollout import ExperimentGroup

        group = self._rollout_manager.get_group_for_camera(camera_id)
        if group == ExperimentGroup.CONTROL:
            self._rollout_manager.record_control_analysis(
                latency_ms=latency_ms,
                risk_score=risk_score,
                has_error=has_error,
            )
        else:
            self._rollout_manager.record_treatment_analysis(
                latency_ms=latency_ms,
                risk_score=risk_score,
                has_error=has_error,
            )

    def record_rollout_feedback(
        self,
        camera_id: str,
        is_false_positive: bool,
    ) -> None:
        """Record feedback for the rollout experiment.

        Automatically routes feedback to the correct group based on camera_id.

        Args:
            camera_id: Camera identifier (determines group)
            is_false_positive: Whether the feedback indicates a false positive
        """
        if self._rollout_manager is None:
            return

        from backend.config.prompt_ab_rollout import ExperimentGroup

        group = self._rollout_manager.get_group_for_camera(camera_id)
        if group == ExperimentGroup.CONTROL:
            self._rollout_manager.record_control_feedback(is_false_positive)
        else:
            self._rollout_manager.record_treatment_feedback(is_false_positive)

    def check_rollout_rollback(self) -> Any:
        """Check if the rollout experiment should be rolled back.

        Evaluates auto-rollback conditions based on:
        - FP rate increase
        - Latency increase
        - Error rate increase

        Returns:
            RollbackCheckResult with should_rollback and reason

        Raises:
            RuntimeError: If no rollout manager is configured
        """
        if self._rollout_manager is None:
            from backend.config.prompt_ab_rollout import RollbackCheckResult

            return RollbackCheckResult(
                should_rollback=False, reason="No rollout manager configured"
            )

        return self._rollout_manager.check_rollback_needed()

    def execute_rollout_rollback(self) -> None:
        """Execute rollback by stopping the experiment.

        Should be called when check_rollout_rollback returns should_rollback=True.
        Stops the experiment and logs the rollback event.
        """
        if self._rollout_manager is None:
            return

        from backend.core.metrics import record_prompt_rollback

        self._rollout_manager.stop()
        record_prompt_rollback("nemotron", "ab_rollout_failure")
        logger.warning(
            f"A/B rollout experiment stopped: "
            f"{self._rollout_manager.rollout_config.experiment_name}"
        )

    def get_rollout_summary(self) -> dict[str, Any]:
        """Get a summary of rollout experiment metrics.

        Returns:
            Dictionary with metrics for control and treatment groups,
            or empty dict if no rollout manager configured
        """
        if self._rollout_manager is None:
            return {}

        result: dict[str, Any] = self._rollout_manager.get_metrics_summary()
        return result

    def _get_facade(self) -> AnalyzerServiceFacade:
        """Get the service facade, creating global singleton if needed.

        The facade aggregates access to multiple dependent services (NEM-3150),
        reducing direct imports from 8+ to 2-3.

        Returns:
            AnalyzerServiceFacade instance
        """
        if self._facade is None:
            self._facade = get_analyzer_facade()
        return self._facade

    def _get_context_enricher(self) -> ContextEnricher:
        """Get the context enricher, using facade for lazy loading.

        Returns:
            ContextEnricher instance
        """
        if self._context_enricher is None:
            self._context_enricher = self._get_facade().get_context_enricher()
        return self._context_enricher

    def _get_enrichment_pipeline(self) -> EnrichmentPipeline:
        """Get the enrichment pipeline, using facade for lazy loading.

        Returns:
            EnrichmentPipeline instance
        """
        if self._enrichment_pipeline is None:
            self._enrichment_pipeline = self._get_facade().get_enrichment_pipeline()
        return self._enrichment_pipeline

    # =========================================================================
    # Cold Start Detection and Warmup (NEM-1670)
    # =========================================================================

    def _track_inference(self) -> None:
        """Record the timestamp of an inference operation.

        Called after each successful LLM inference to track model warmth.
        """
        self._last_inference_time = time.monotonic()

    def is_cold(self) -> bool:
        """Check if the model is considered cold (not recently used).

        A model is cold if:
        - It has never been used (_last_inference_time is None)
        - The time since last inference exceeds cold_start_threshold

        Returns:
            True if model is cold, False if warm
        """
        if self._last_inference_time is None:
            return True
        seconds_since_last = time.monotonic() - self._last_inference_time
        return seconds_since_last > self._cold_start_threshold

    def get_warmth_state(self) -> dict[str, Any]:
        """Get the current warmth state of the model.

        Returns:
            Dictionary containing:
            - state: 'cold', 'warming', or 'warm'
            - last_inference_seconds_ago: Seconds since last inference, or None
        """
        if self._is_warming:
            return {
                "state": "warming",
                "last_inference_seconds_ago": None,
            }

        if self._last_inference_time is None:
            return {
                "state": "cold",
                "last_inference_seconds_ago": None,
            }

        seconds_ago = time.monotonic() - self._last_inference_time
        is_cold = seconds_ago > self._cold_start_threshold
        return {
            "state": "cold" if is_cold else "warm",
            "last_inference_seconds_ago": seconds_ago,
        }

    async def model_readiness_probe(self) -> bool:
        """Perform model readiness probe with actual inference.

        Unlike health_check which only checks HTTP availability,
        this method sends a test prompt to verify the model can
        actually perform inference. This is used for warmup and
        to detect if the model is loaded and ready.

        Returns:
            True if model completed inference successfully, False otherwise
        """

        try:
            start_time = time.monotonic()
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Send a simple completion request
                response = await client.post(
                    f"{self._llm_url}/v1/completions",
                    headers=self._get_auth_headers(),
                    json={
                        "prompt": self._warmup_prompt,
                        "max_tokens": 50,
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                duration = time.monotonic() - start_time
                logger.debug(
                    f"Nemotron readiness probe completed in {duration:.2f}s",
                    extra={"duration": duration},
                )
                return True
        except httpx.ConnectError as e:
            logger.warning(f"Nemotron readiness probe connection error: {e}")
            return False
        except httpx.TimeoutException as e:
            logger.warning(f"Nemotron readiness probe timeout: {e}")
            return False
        except httpx.HTTPStatusError as e:
            logger.warning(f"Nemotron readiness probe HTTP error: {e}")
            return False
        except Exception as e:
            logger.warning(f"Nemotron readiness probe failed: {e}")
            return False

    async def warmup(self) -> bool:
        """Perform model warmup by running a test inference.

        Called on service startup to preload model weights into GPU memory.
        This reduces first-request latency for production traffic.

        Records metrics:
        - hsi_model_warmup_duration_seconds{model="nemotron"}
        - hsi_model_cold_start_total{model="nemotron"} (if model was cold)

        Returns:
            True if warmup succeeded, False otherwise
        """
        from backend.core.metrics import (
            observe_model_warmup_duration,
            record_model_cold_start,
            set_model_warmth_state,
        )

        if not self._warmup_enabled:
            logger.debug("Nemotron warmup disabled by configuration")
            return True

        was_cold = self.is_cold()
        self._is_warming = True
        set_model_warmth_state("nemotron", "warming")

        try:
            logger.info("Starting Nemotron model warmup...")
            start_time = time.monotonic()

            result = await self.model_readiness_probe()

            duration = time.monotonic() - start_time
            observe_model_warmup_duration("nemotron", duration)

            if result:
                self._track_inference()
                if was_cold:
                    record_model_cold_start("nemotron")
                set_model_warmth_state("nemotron", "warm")
                logger.info(
                    f"Nemotron warmup completed in {duration:.2f}s",
                    extra={"duration": duration, "was_cold": was_cold},
                )
                return True
            else:
                set_model_warmth_state("nemotron", "cold")
                logger.warning("Nemotron warmup failed - model not ready")
                return False
        finally:
            self._is_warming = False

    # =========================================================================
    # Idempotency Handling (NEM-1725)
    # =========================================================================

    async def _check_idempotency(self, batch_id: str) -> int | None:
        """Check if an Event was already created for this batch.

        This prevents duplicate Event creation when Nemotron analyzer retries
        after timeout or other transient failures.

        Args:
            batch_id: Batch identifier to check

        Returns:
            event_id if Event already exists for this batch, None otherwise
        """
        if not self._redis:
            return None

        try:
            key = f"batch_event:{batch_id}"
            event_id = await self._redis.get(key)
            if event_id is not None:
                logger.debug(
                    f"Idempotency check: batch {batch_id} already has event {event_id}",
                    extra={"batch_id": batch_id, "event_id": event_id},
                )
                return int(event_id)
            return None
        except Exception as e:
            # On Redis failure, proceed with creation (fail open)
            logger.warning(
                "Idempotency check failed, proceeding",
                extra={"batch_id": batch_id, "error": str(e)},
            )
            return None

    async def _set_idempotency(self, batch_id: str, event_id: int) -> None:
        """Store idempotency key after successful Event creation.

        Stores a mapping from batch_id to event_id with a 1-hour TTL.
        This allows subsequent retries to detect the prior creation
        and avoid duplicates.

        Args:
            batch_id: Batch identifier
            event_id: ID of the created Event
        """
        if not self._redis:
            return

        try:
            key = f"batch_event:{batch_id}"
            await self._redis.set(key, str(event_id), expire=3600)  # 1 hour TTL
            logger.debug(f"Idempotency key set: {key} -> {event_id}")
        except Exception as e:
            # On Redis failure, log warning but don't fail the request
            logger.warning(
                "Failed to set idempotency key for batch",
                extra={"batch_id": batch_id, "event_id": event_id, "error": str(e)},
            )

    async def _get_existing_event(self, event_id: int) -> Event | None:
        """Fetch an existing Event by ID from the database.

        Args:
            event_id: ID of the Event to fetch

        Returns:
            Event object if found, None otherwise
        """
        async with get_session() as session:
            result = await session.execute(select(Event).where(Event.id == event_id))
            return result.scalar_one_or_none()

    async def _get_enriched_context(
        self,
        batch_id: str,
        camera_id: str,
        detection_ids: list[int],
        session: Any,
    ) -> EnrichedContext | None:
        """Get enriched context for a batch if enabled.

        Args:
            batch_id: Batch identifier
            camera_id: Camera identifier
            detection_ids: List of detection IDs
            session: Database session

        Returns:
            EnrichedContext or None if enrichment is disabled or fails
        """
        if not self._use_enriched_context:
            return None

        try:
            enricher = self._get_context_enricher()
            context = await enricher.enrich(
                batch_id=batch_id,
                camera_id=camera_id,
                detection_ids=detection_ids,
                session=session,
            )
            logger.debug(
                f"Context enriched for batch {batch_id}: "
                f"{len(context.zones)} zones, "
                f"{len(context.cross_camera)} cross-camera activities"
            )
            return context
        except Exception as e:
            logger.warning(
                "Context enrichment failed, falling back to basic prompt",
                extra={"batch_id": batch_id, "error": str(e)},
                exc_info=True,
            )
            return None

    async def _get_recent_scene_changes(
        self,
        camera_id: str,
        session: Any,
    ) -> list[Any]:
        """Get recent unacknowledged scene changes for a camera.

        This method queries the SceneChange table for recent tampering alerts
        that have not been acknowledged by the user. These are used to inform
        the LLM about potential camera health issues that may affect detection
        confidence (NEM-3012).

        Args:
            camera_id: Camera identifier
            session: Database session

        Returns:
            List of SceneChange objects, ordered by detected_at DESC.
            Returns empty list if no unacknowledged scene changes exist.
        """
        from backend.models.scene_change import SceneChange

        try:
            # Query recent unacknowledged scene changes for this camera
            # Limit to last 5 to avoid prompt bloat, ordered by most recent first
            result = await session.execute(
                select(SceneChange)
                .where(SceneChange.camera_id == camera_id)
                .where(SceneChange.acknowledged == False)  # noqa: E712 - SQLAlchemy comparison
                .order_by(SceneChange.detected_at.desc())
                .limit(5)
            )
            scene_changes = list(result.scalars().all())
            if scene_changes:
                logger.debug(
                    f"Found {len(scene_changes)} unacknowledged scene changes for camera {camera_id}",
                    extra={"camera_id": camera_id, "count": len(scene_changes)},
                )
            return scene_changes
        except Exception as e:
            logger.warning(
                "Failed to query scene changes, continuing without camera health context",
                extra={"camera_id": camera_id, "error": str(e)},
            )
            return []

    async def _get_household_context(
        self,
        detections_data: list[dict[str, Any]],  # noqa: ARG002 - Reserved for future expansion
        enrichment_result: EnrichmentResult | None,
    ) -> str:
        """Format household matching results for prompt injection (NEM-3024, NEM-3314).

        This method retrieves pre-computed household matches from the enrichment
        pipeline and formats them into context for the Nemotron prompt. Matching
        is now performed during enrichment (NEM-3314) rather than here to avoid
        duplicate database queries and to ensure matches are available earlier
        in the pipeline.

        Matching is performed in EnrichmentPipeline._run_household_matching():
        - Persons: Matched via embeddings from person_embeddings against HouseholdMember
        - Vehicles: Matched via license plate text against registered vehicles

        Args:
            detections_data: List of detection data dictionaries (reserved for future use)
            enrichment_result: Results from enrichment pipeline (contains household matches)

        Returns:
            Formatted household context string, or empty string if no matches.
        """
        from datetime import UTC, datetime

        # Early exit if no enrichment result
        if enrichment_result is None:
            return ""

        # Get household matches from enrichment result (NEM-3314)
        # Matching is now performed during enrichment to avoid duplicate DB queries
        person_matches = enrichment_result.person_household_matches
        vehicle_matches = enrichment_result.vehicle_household_matches

        # Format the household context if any matches were found
        if person_matches or vehicle_matches:
            current_time = datetime.now(UTC)
            return format_household_context(
                person_matches=person_matches,
                vehicle_matches=vehicle_matches,
                current_time=current_time,
            )

        return ""

    async def _get_enrichment_result(
        self,
        batch_id: str,
        detections: list[Detection],
        camera_id: str | None = None,
    ) -> EnrichmentTrackingResult | None:
        """Get enrichment result (plates, faces) for detections if enabled.

        This method now returns an EnrichmentTrackingResult that tracks which
        enrichment models succeeded/failed, providing visibility into partial
        failures instead of silently degrading (NEM-1672).

        Args:
            batch_id: Batch identifier (for logging)
            detections: List of Detection objects
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentTrackingResult with status, model results, and data,
            or None if enrichment is disabled
        """
        if not self._use_enrichment_pipeline:
            return None

        try:
            tracking_result = await self._run_enrichment_pipeline(detections, camera_id=camera_id)

            if tracking_result:
                # Log partial failures if any models failed
                if tracking_result.is_partial:
                    logger.warning(
                        "Enrichment pipeline partial failure",
                        extra={
                            "batch_id": batch_id,
                            "succeeded": tracking_result.successful_models,
                            "failed": tracking_result.failed_models,
                            "success_rate": f"{tracking_result.success_rate:.0%}",
                        },
                    )
                elif tracking_result.all_failed:
                    logger.warning(
                        "Enrichment pipeline failed: all models failed",
                        extra={
                            "batch_id": batch_id,
                            "failed_models": tracking_result.failed_models,
                        },
                    )
                elif tracking_result.has_data:
                    result = tracking_result.data
                    if result:
                        logger.debug(
                            f"Enrichment pipeline for batch {batch_id}: "
                            f"{len(result.license_plates)} plates, "
                            f"{len(result.faces)} faces, "
                            f"{result.processing_time_ms:.1f}ms, "
                            f"status={tracking_result.status.value}"
                        )

            return tracking_result

        except Exception as e:
            logger.warning(
                "Enrichment pipeline failed, continuing without enrichment",
                extra={"batch_id": batch_id, "error": str(e)},
                exc_info=True,
            )
            # Return a failed tracking result instead of None
            return EnrichmentTrackingResult(
                status=EnrichmentStatus.FAILED,
                successful_models=[],
                failed_models=["all"],
                errors={"all": str(e)},
                data=None,
            )

    async def _get_enrichment_result_from_data(
        self,
        batch_id: str,
        detections_data: list[dict[str, Any]],
        camera_id: str | None = None,
    ) -> EnrichmentTrackingResult | None:
        """Get enrichment result from detection data dictionaries.

        This is a variant of _get_enrichment_result that works with plain
        dictionaries instead of ORM objects. This allows running enrichment
        outside of a database session context, preventing "idle-in-transaction"
        timeout issues during long-running enrichment operations.

        Args:
            batch_id: Batch identifier (for logging)
            detections_data: List of detection data dictionaries with keys:
                - id: Detection ID
                - object_type: Detected object type
                - confidence: Detection confidence
                - image_path: Path to detection image
                - bounding_box: Bounding box dict or None
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentTrackingResult with status, model results, and data,
            or None if enrichment is disabled
        """
        if not self._use_enrichment_pipeline:
            return None

        try:
            tracking_result = await self._run_enrichment_pipeline_from_data(
                detections_data, camera_id=camera_id
            )

            if tracking_result:
                # Log partial failures if any models failed
                if tracking_result.is_partial:
                    logger.warning(
                        "Enrichment pipeline partial failure",
                        extra={
                            "batch_id": batch_id,
                            "succeeded": tracking_result.successful_models,
                            "failed": tracking_result.failed_models,
                            "success_rate": f"{tracking_result.success_rate:.0%}",
                        },
                    )
                elif tracking_result.all_failed:
                    logger.warning(
                        "Enrichment pipeline failed: all models failed",
                        extra={
                            "batch_id": batch_id,
                            "failed_models": tracking_result.failed_models,
                        },
                    )
                elif tracking_result.has_data:
                    result = tracking_result.data
                    if result:
                        logger.debug(
                            f"Enrichment pipeline for batch {batch_id}: "
                            f"{len(result.license_plates)} plates, "
                            f"{len(result.faces)} faces, "
                            f"{result.processing_time_ms:.1f}ms, "
                            f"status={tracking_result.status.value}"
                        )

            return tracking_result

        except Exception as e:
            logger.warning(
                "Enrichment pipeline failed, continuing without enrichment",
                extra={"batch_id": batch_id, "error": str(e)},
                exc_info=True,
            )
            # Return a failed tracking result instead of None
            return EnrichmentTrackingResult(
                status=EnrichmentStatus.FAILED,
                successful_models=[],
                failed_models=["all"],
                errors={"all": str(e)},
                data=None,
            )

    async def _run_enrichment_pipeline_from_data(
        self,
        detections_data: list[dict[str, Any]],
        camera_id: str | None = None,
    ) -> EnrichmentTrackingResult | None:
        """Run the enrichment pipeline on detection data dictionaries.

        This is a variant of _run_enrichment_pipeline that works with plain
        dictionaries instead of ORM objects, allowing enrichment to run
        outside of a database session context.

        Args:
            detections_data: List of detection data dictionaries
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentTrackingResult with status, model results, and data,
            or None if no enrichment was needed
        """
        if not detections_data:
            return None

        pipeline = self._get_enrichment_pipeline()

        # Convert detection data dicts to DetectionInput format
        detection_inputs: list[DetectionInput] = []
        from pathlib import Path

        from PIL import Image

        # Type annotation matches EnrichmentPipeline.enrich_batch signature
        images: dict[int | None, Image.Image | Path | str] = {}

        for det_data in detections_data:
            # Get bounding box data
            bbox = det_data.get("bounding_box")
            object_type = det_data.get("object_type")

            # Skip detections without bounding boxes or object types
            if bbox is None or object_type is None:
                continue

            # Handle bbox as either dict or tuple/list
            if isinstance(bbox, dict):
                bbox_x = bbox.get("x") or bbox.get("bbox_x") or bbox.get("x1")
                bbox_y = bbox.get("y") or bbox.get("bbox_y") or bbox.get("y1")
                bbox_width = bbox.get("width") or bbox.get("bbox_width")
                bbox_height = bbox.get("height") or bbox.get("bbox_height")

                if bbox_width is None and "x2" in bbox:
                    bbox_width = bbox["x2"] - bbox_x
                if bbox_height is None and "y2" in bbox:
                    bbox_height = bbox["y2"] - bbox_y
            elif isinstance(bbox, list | tuple) and len(bbox) >= 4:
                bbox_x, bbox_y, bbox_width, bbox_height = bbox[:4]
            else:
                continue

            if any(v is None for v in [bbox_x, bbox_y, bbox_width, bbox_height]):
                continue

            # Cast to non-None after the check above (mypy can't narrow through any())
            bbox_x_val = float(bbox_x)  # type: ignore[arg-type]
            bbox_y_val = float(bbox_y)  # type: ignore[arg-type]
            bbox_w_val = float(bbox_width)  # type: ignore[arg-type]
            bbox_h_val = float(bbox_height)  # type: ignore[arg-type]

            # Create DetectionInput with bounding box
            detection_input = DetectionInput(
                id=det_data["id"],
                class_name=object_type,
                confidence=det_data.get("confidence") or 0.0,
                bbox=BoundingBox(
                    x1=bbox_x_val,
                    y1=bbox_y_val,
                    x2=bbox_x_val + bbox_w_val,
                    y2=bbox_y_val + bbox_h_val,
                ),
                video_width=det_data.get("video_width"),
                video_height=det_data.get("video_height"),
            )
            detection_inputs.append(detection_input)

            # Map detection ID to image path
            image_path = det_data.get("image_path") or det_data.get("file_path")
            if image_path:
                images[det_data["id"]] = image_path

        if not detection_inputs:
            return None

        # Set shared image for full-frame analysis (use first detection's image)
        # This enables vision extraction, scene change detection, and re-id
        if detections_data:
            first_image = detections_data[0].get("image_path") or detections_data[0].get(
                "file_path"
            )
            if first_image:
                images[None] = first_image

        # Run the enrichment pipeline with tracking for partial failure visibility
        tracking_result = await pipeline.enrich_batch_with_tracking(
            detection_inputs, images, camera_id=camera_id
        )

        return tracking_result

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication, correlation, and trace context headers for API requests.

        NEM-1729: Includes correlation headers for distributed tracing.
        NEM-XXXX: Includes W3C Trace Context headers (traceparent, tracestate)
                  for OpenTelemetry distributed tracing across service boundaries.
        Security: Returns X-API-Key header if API key is configured.

        Returns:
            Dictionary of headers to include in requests (auth + correlation + trace context)
        """
        headers: dict[str, str] = {}
        # Add correlation and W3C trace context headers for distributed tracing (NEM-1729, NEM-XXXX)
        # get_correlation_headers() now includes traceparent/tracestate for OpenTelemetry
        headers.update(get_correlation_headers())
        # Add API key if configured (support SecretStr and str)
        if self._api_key:
            api_key_value: str = (
                self._api_key.get_secret_value()
                if hasattr(self._api_key, "get_secret_value")
                else str(self._api_key)
            )
            headers["X-API-Key"] = api_key_value
        return headers

    async def analyze_batch(
        self,
        batch_id: str,
        camera_id: str | None = None,
        detection_ids: list[int | str] | None = None,
    ) -> Event:
        """Analyze a batch of detections and create Event.

        If camera_id and detection_ids are provided (from queue payload), uses them
        directly. Otherwise, fetches batch metadata from Redis (legacy behavior).

        This method uses split sessions to avoid holding database connections open
        during long-running external operations (LLM calls, enrichment pipeline).
        This prevents PostgreSQL "idle-in-transaction timeout" errors.

        Session Strategy:
            1. Session 1 (READ): Fetch camera and detection data
            2. No session: Run enrichment pipeline and LLM analysis (external calls)
            3. Session 2 (WRITE): Persist Event, junction table entries, and audit

        Args:
            batch_id: Batch identifier to analyze
            camera_id: Camera identifier (optional, from queue payload)
            detection_ids: List of detection IDs (optional, from queue payload)

        Returns:
            Event object with risk assessment

        Raises:
            ValueError: If batch not found or has no detections
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Idempotency check (NEM-1725): prevent duplicate Events on retry
        existing_event_id = await self._check_idempotency(batch_id)
        if existing_event_id is not None:
            logger.info(
                "Idempotency hit: batch already processed as event",
                extra={"batch_id": batch_id, "event_id": existing_event_id},
            )
            existing_event = await self._get_existing_event(existing_event_id)
            if existing_event:
                return existing_event
            # If event not found in DB (deleted?), proceed with creation
            logger.warning(
                "Idempotency key exists but event not found, proceeding with new Event creation",
                extra={"batch_id": batch_id, "event_id": existing_event_id},
            )

        # Use provided values or fall back to Redis lookup
        if camera_id is None:
            camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
            if not camera_id:
                raise ValueError(f"Batch {batch_id} not found in Redis")

        if detection_ids is None:
            detections_data = await self._redis.get(f"batch:{batch_id}:detections")
            detection_ids = json.loads(detections_data) if detections_data else []

        if not detection_ids:
            raise ValueError(f"Batch {batch_id} has no detections")

        analysis_start = time.time()

        # NEM-3797: Add span event for batch analysis start
        add_span_event(
            "batch_analysis.start",
            {
                "batch.id": batch_id,
                "camera.id": camera_id,
                "detection.count": len(detection_ids),
            },
        )

        # Use log_context to include batch_id in all subsequent logs during analysis
        # This ensures every log message within analyze_batch includes batch tracing
        with log_context(
            batch_id=batch_id, camera_id=camera_id, detection_count=len(detection_ids)
        ):
            logger.info("Batch analysis started")

        # Convert detection_ids to integers (may come as strings from queue payload)
        try:
            int_detection_ids = [int(d) for d in detection_ids]
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid detection_id in batch {batch_id}: {e}. "
                f"Detection IDs must be numeric (got: {detection_ids})"
            ) from None

        # =========================================================================
        # SESSION 1 (READ): Fetch camera and detection data
        # This session is short-lived - we only read data, then close it before
        # making external calls (LLM, enrichment) that can take minutes.
        # =========================================================================
        async with get_session() as session:
            # Get camera details
            camera_result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = camera_result.scalar_one_or_none()
            if not camera:
                logger.warning(
                    "Camera not found, using ID as name",
                    extra={"camera_id": camera_id},
                )  # pragma: no cover
                camera_name = camera_id  # pragma: no cover
            else:
                camera_name = camera.name

            # Use batch fetching via facade to handle large detection lists efficiently
            detections = await self._get_facade().fetch_detections(session, int_detection_ids)

            if not detections:
                logger.warning(
                    "No detections found in database for batch",
                    extra={"batch_id": batch_id, "detection_ids": detection_ids},
                )
                raise ValueError(f"No detections found for batch {batch_id}")

            # Determine time window
            detection_times = [d.detected_at for d in detections]
            start_time = min(detection_times)
            end_time = max(detection_times)

            # Format detections for prompt (extracts data from ORM objects)
            detections_list = self._format_detections(detections)

            # Enrich context if enabled (zone, baseline, cross-camera)
            # This makes additional DB queries but they're quick
            enriched_context = await self._get_enriched_context(
                batch_id, camera_id, int_detection_ids, session
            )

            # Query recent scene changes for camera health context (NEM-3012)
            recent_scene_changes = await self._get_recent_scene_changes(camera_id, session)
            camera_health_context = format_camera_health_context(camera_id, recent_scene_changes)

            # Fetch auto-tuning context from historical audit recommendations (NEM-3015)
            # This provides insights from self-evaluation to improve prompt quality
            auto_tuning_context = ""
            try:
                auto_tuner = self._get_facade().get_prompt_auto_tuner()
                auto_tuning_context = await auto_tuner.get_tuning_context(
                    session=session,
                    camera_id=camera_id,
                )
                if auto_tuning_context:
                    logger.debug(
                        "Auto-tuning context retrieved for batch",
                        extra={"batch_id": batch_id, "camera_id": camera_id},
                    )
            except Exception as e:
                # Auto-tuning is optional - don't fail the pipeline if it errors
                logger.warning(
                    "Failed to fetch auto-tuning context",
                    extra={"batch_id": batch_id, "camera_id": camera_id, "error": str(e)},
                )

            # Extract detection data needed for enrichment pipeline
            # We need to capture this before closing the session
            # Use explicit bbox fields since Detection doesn't have a bounding_box property
            detections_for_enrichment = [
                {
                    "id": d.id,
                    "object_type": d.object_type,
                    "confidence": d.confidence,
                    "file_path": d.file_path,
                    "bounding_box": {
                        "bbox_x": d.bbox_x,
                        "bbox_y": d.bbox_y,
                        "bbox_width": d.bbox_width,
                        "bbox_height": d.bbox_height,
                    }
                    if d.bbox_x is not None
                    else None,
                    "video_width": d.video_width,
                    "video_height": d.video_height,
                }
                for d in detections
            ]

        # Session 1 is now closed - connection returned to pool
        # =========================================================================

        # =========================================================================
        # EXTERNAL CALLS (NO SESSION): Run enrichment pipeline and LLM analysis
        # These can take 60-120+ seconds. We do NOT hold a DB connection during this.
        # =========================================================================

        # Run enrichment pipeline for license plates, faces, OCR
        # Returns EnrichmentTrackingResult which includes status and data (NEM-1672)
        enrichment_tracking = await self._get_enrichment_result_from_data(
            batch_id, detections_for_enrichment, camera_id=camera_id
        )

        # Extract the actual EnrichmentResult data from the tracking result
        enrichment_result: EnrichmentResult | None = None
        if enrichment_tracking is not None and enrichment_tracking.has_data:
            enrichment_result = enrichment_tracking.data

        # Build enrichment data map for persisting to detections later
        enrichment_data_map: dict[int, dict[str, Any]] = {}
        if enrichment_result is not None:
            for det_data in detections_for_enrichment:
                # det_data["id"] is guaranteed to be int from detections_for_enrichment extraction
                det_id = int(det_data["id"])  # type: ignore[arg-type]
                det_enrichment = enrichment_result.get_enrichment_for_detection(det_id)
                if det_enrichment:
                    enrichment_data_map[det_id] = det_enrichment
                    logger.debug(
                        f"Prepared enrichment data for detection {det_id}",
                        extra={
                            "detection_id": det_id,
                            "enrichment_keys": list(det_enrichment.keys()),
                        },
                    )

        # =========================================================================
        # HOUSEHOLD MATCHING (NEM-3024): Match persons/vehicles against household
        # This reduces risk scores for known household members and registered vehicles.
        # =========================================================================
        household_context = ""
        try:
            household_context = await self._get_household_context(
                detections_for_enrichment, enrichment_result
            )
            if household_context:
                logger.debug(
                    "Household matching completed for batch",
                    extra={"batch_id": batch_id, "has_matches": bool(household_context)},
                )
        except Exception as e:
            # Household matching is optional - don't fail the pipeline if it errors
            logger.warning(
                "Failed to perform household matching",
                extra={"batch_id": batch_id, "error": str(e)},
            )

        # Call LLM for risk analysis (can take 60-120+ seconds)
        llm_start = time.time()

        # NEM-3797: Add span event for Nemotron analysis start
        add_span_event(
            "nemotron_analysis.start",
            {
                "batch.id": batch_id,
                "camera.id": camera_id,
                "camera.name": camera_name,
                "detection.count": len(int_detection_ids),
                "has_enriched_context": enriched_context is not None,
                "has_enrichment_result": enrichment_result is not None,
                "has_household_context": bool(household_context),
            },
        )

        try:
            risk_data = await self._call_llm(
                camera_name=camera_name,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                detections_list=detections_list,
                enriched_context=enriched_context,
                enrichment_result=enrichment_result,
                camera_health_context=camera_health_context,
                auto_tuning_context=auto_tuning_context,
                household_context=household_context,
            )
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            llm_duration_seconds = time.time() - llm_start
            # Record Nemotron AI request duration
            observe_ai_request_duration("nemotron", llm_duration_seconds)

            # NEM-3797: Add span event for Nemotron analysis complete
            add_span_event(
                "nemotron_analysis.complete",
                {
                    "batch.id": batch_id,
                    "risk.score": risk_data.get("risk_score", 0),
                    "risk.level": risk_data.get("risk_level", "unknown"),
                    "analysis.duration_ms": llm_duration_ms,
                },
            )

            logger.debug(
                f"LLM analysis completed for batch {batch_id}",
                extra={
                    "camera_id": camera_id,
                    "batch_id": batch_id,
                    "duration_ms": llm_duration_ms,
                },
            )
        except Exception as e:
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            llm_duration_seconds = time.time() - llm_start
            # Record duration even on failure
            observe_ai_request_duration("nemotron", llm_duration_seconds)
            record_pipeline_error("nemotron_analysis_error")
            sanitized_error = sanitize_error(e)
            logger.error(
                "LLM analysis failed for batch",
                extra={
                    "camera_id": camera_id,
                    "batch_id": batch_id,
                    "duration_ms": llm_duration_ms,
                    "error": sanitized_error,
                },
                exc_info=True,
            )
            # Create fallback risk data - use sanitized error for user-facing content
            risk_data = {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Analysis unavailable - LLM service error",
                "reasoning": "Failed to analyze detections due to service error",
            }

        # =========================================================================
        # SESSION 2 (WRITE): Persist Event, junction table entries, and audit
        # This is a new, short-lived session for writing results to the database.
        # =========================================================================
        async with get_session() as session:
            # Create Event record with advanced risk analysis fields (NEM-3601)
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=start_time,
                ended_at=end_time,
                risk_score=risk_data.get("risk_score", 50),
                risk_level=risk_data.get("risk_level", "medium"),
                summary=risk_data.get("summary", "No summary available"),
                reasoning=risk_data.get("reasoning", "No reasoning available"),
                llm_prompt=risk_data.get("llm_prompt"),
                reviewed=False,
                # Advanced risk analysis fields (NEM-3601)
                entities=risk_data.get("entities"),
                flags=risk_data.get("flags"),
                confidence_factors=risk_data.get("confidence_factors"),
                recommended_action=risk_data.get("recommended_action"),
            )

            # NEM-2574: Batch database commits to reduce transaction overhead
            # Use flush() to persist objects and get IDs without committing.
            # A single commit happens at the end via get_session() context manager.
            # On any error, the context manager automatically rolls back the transaction.
            session.add(event)
            await session.flush()  # Persist event and get ID without committing

            # Populate event_detections junction table (NEM-1592, NEM-1998, NEM-3350)
            # Uses bulk INSERT with ON CONFLICT DO NOTHING to prevent race conditions
            # and improve performance by reducing round-trips to the database.
            # This is safe because the composite primary key (event_id, detection_id)
            # enforces uniqueness at the database level.
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            from backend.models.event_detection import event_detections

            if int_detection_ids:
                values = [
                    {"event_id": event.id, "detection_id": det_id} for det_id in int_detection_ids
                ]
                stmt = (
                    pg_insert(event_detections)
                    .values(values)
                    .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
                )
                await session.execute(stmt)

            # Persist enrichment data to detections (bulk update)
            if enrichment_data_map:
                from sqlalchemy import update as sql_update

                for det_id, enrichment_data in enrichment_data_map.items():
                    update_stmt = (
                        sql_update(Detection)
                        .where(Detection.id == det_id)
                        .values(enrichment_data=enrichment_data)
                    )
                    await session.execute(update_stmt)

            # Store idempotency key (NEM-1725) to prevent duplicates on retry
            # Note: This is stored in Redis, not the database transaction
            await self._set_idempotency(batch_id, event.id)

            # Create partial audit record for model contribution tracking
            try:
                from backend.services.pipeline_quality_audit_service import get_audit_service

                audit_service = get_audit_service()
                audit = audit_service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=risk_data.get("llm_prompt"),
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                session.add(audit)
                await session.flush()  # Persist audit and get ID without committing
                logger.debug(f"Created audit {audit.id} for event {event.id}")

                # Auto-enqueue for background evaluation (higher risk = higher priority)
                # This enables full AI audit evaluation when GPU is idle
                await self._enqueue_for_evaluation(event.id, event.risk_score or 50)

            except Exception as e:
                # NEM-2574: Audit failures should not roll back the Event creation
                # The audit is optional - we log a warning but continue
                logger.warning(
                    "Audit log write failed",
                    extra={
                        "action": "create_partial_audit",
                        "resource_id": str(event.id),
                        "resource_type": "event_audit",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )

            # NEM-2574: Single commit at end via get_session() context manager
            # The context manager handles: commit on success, rollback on any error

        # Session 2 is now closed - connection returned to pool
        # =========================================================================

        # NEM-3797: Add span event for database write completion
        add_span_event(
            "database_write.complete",
            {
                "batch.id": batch_id,
                "event.id": event.id,
                "detection.count": len(int_detection_ids),
                "enrichment_data.count": len(enrichment_data_map),
            },
        )

        total_duration_ms = int((time.time() - analysis_start) * 1000)
        total_duration_seconds = time.time() - analysis_start

        # Record stage duration and event creation metrics
        observe_stage_duration("analyze", total_duration_seconds)
        record_event_created()
        record_event_by_camera(camera_id, camera_name)

        # Log batch analysis completion with consistent batch_id context
        with log_context(batch_id=batch_id, camera_id=camera_id):
            logger.info(
                "Batch analysis completed",
                extra={
                    "event_id": event.id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "duration_ms": total_duration_ms,
                    "detection_count": len(int_detection_ids),
                },
            )

        # Broadcast via WebSocket if available (optional)
        try:
            await self._broadcast_event(event)
        except Exception as e:
            logger.warning(
                "Failed to broadcast event",
                extra={"event_id": event.id, "error": str(e)},
                exc_info=True,
            )

        # Invalidate event stats cache so stats endpoints return fresh data (NEM-1682)
        try:
            cache = await self._get_facade().get_cache_service()
            await cache.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)
        except Exception as e:
            logger.warning(
                "Failed to invalidate event stats cache",
                extra={"error": str(e)},
            )

        # Trigger outbound webhooks for EVENT_CREATED (NEM-3624)
        await self._trigger_event_created_webhook(event)

        # NEM-3797: Add span event for batch analysis complete (full pipeline)
        add_span_event(
            "batch_analysis.complete",
            {
                "batch.id": batch_id,
                "event.id": event.id,
                "camera.id": camera_id,
                "risk.score": event.risk_score or 0,
                "risk.level": event.risk_level or "unknown",
                "detection.count": len(int_detection_ids),
                "total.duration_ms": total_duration_ms,
            },
        )

        return event

    async def analyze_detection_fast_path(self, camera_id: str, detection_id: int | str) -> Event:
        """Analyze a single detection via fast path (high-priority).

        This method is called for high-confidence critical detections that bypass
        the normal batch aggregation process. Creates an Event immediately for
        the single detection.

        This method uses split sessions to avoid holding database connections open
        during long-running external operations (LLM calls, enrichment pipeline).
        This prevents PostgreSQL "idle-in-transaction timeout" errors.

        Session Strategy:
            1. Session 1 (READ): Fetch camera and detection data
            2. No session: Run enrichment pipeline and LLM analysis (external calls)
            3. Session 2 (WRITE): Persist Event, junction table entries, and audit

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (int or string, normalized to int internally)

        Returns:
            Event object with risk assessment and is_fast_path=True

        Raises:
            ValueError: If detection not found
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Convert detection_id to int if needed
        try:
            detection_id_int = int(detection_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid detection_id: {detection_id}") from None

        # Idempotency check (NEM-1725): prevent duplicate Events on retry
        # Generate batch_id upfront so we can check idempotency before DB query
        batch_id = f"fast_path_{detection_id_int}"
        existing_event_id = await self._check_idempotency(batch_id)
        if existing_event_id is not None:
            logger.info(
                "Idempotency hit: fast path already processed as event",
                extra={"batch_id": batch_id, "event_id": existing_event_id},
            )
            existing_event = await self._get_existing_event(existing_event_id)
            if existing_event:
                return existing_event
            # If event not found in DB (deleted?), proceed with creation
            logger.warning(
                "Idempotency key exists but event not found, proceeding with new Event creation",
                extra={"batch_id": batch_id, "event_id": existing_event_id},
            )

        analysis_start = time.time()

        # Use log_context to include batch_id in all subsequent logs during fast path analysis
        with log_context(batch_id=batch_id, camera_id=camera_id, detection_id=detection_id_int):
            logger.info("Batch analysis started")

        # =========================================================================
        # SESSION 1 (READ): Fetch camera and detection data
        # This session is short-lived - we only read data, then close it before
        # making external calls (LLM, enrichment) that can take minutes.
        # =========================================================================
        async with get_session() as session:
            # Get camera details
            camera_result = await session.execute(select(Camera).where(Camera.id == camera_id))
            camera = camera_result.scalar_one_or_none()
            if not camera:
                logger.warning(
                    "Camera not found, using ID as name",
                    extra={"camera_id": camera_id},
                )  # pragma: no cover
                camera_name = camera_id  # pragma: no cover
            else:
                camera_name = camera.name

            # Get detection details
            detection_result = await session.execute(
                select(Detection).where(Detection.id == detection_id_int)
            )
            detection = detection_result.scalar_one_or_none()

            if not detection:
                raise ValueError(f"Detection {detection_id} not found in database")

            # Extract data from ORM object before closing session
            detection_time = detection.detected_at
            detections_list = self._format_detections([detection])

            # Extract detection data for enrichment pipeline
            detection_data_for_enrichment = {
                "id": detection.id,
                "object_type": detection.object_type,
                "confidence": detection.confidence,
                "file_path": detection.file_path,
                "bounding_box": {
                    "bbox_x": detection.bbox_x,
                    "bbox_y": detection.bbox_y,
                    "bbox_width": detection.bbox_width,
                    "bbox_height": detection.bbox_height,
                }
                if detection.bbox_x is not None
                else None,
                "video_width": detection.video_width,
                "video_height": detection.video_height,
            }

            # Enrich context if enabled (zone, baseline, cross-camera)
            # This makes additional DB queries but they're quick
            enriched_context = await self._get_enriched_context(
                batch_id, camera_id, [detection_id_int], session
            )

            # Query recent scene changes for camera health context (NEM-3012)
            recent_scene_changes = await self._get_recent_scene_changes(camera_id, session)
            camera_health_context = format_camera_health_context(camera_id, recent_scene_changes)

        # Session 1 is now closed - connection returned to pool
        # =========================================================================

        # =========================================================================
        # EXTERNAL CALLS (NO SESSION): Run enrichment pipeline and LLM analysis
        # These can take 60-120+ seconds. We do NOT hold a DB connection during this.
        # =========================================================================

        # Run enrichment pipeline for license plates, faces, OCR
        # Returns EnrichmentTrackingResult which includes status and data (NEM-1672)
        enrichment_tracking = await self._get_enrichment_result_from_data(
            batch_id, [detection_data_for_enrichment], camera_id=camera_id
        )

        # Extract the actual EnrichmentResult data from the tracking result
        enrichment_result: EnrichmentResult | None = None
        if enrichment_tracking is not None and enrichment_tracking.has_data:
            enrichment_result = enrichment_tracking.data

        # Build enrichment data map for persisting to detections later
        enrichment_data_to_persist: dict[str, Any] | None = None
        if enrichment_result is not None:
            det_enrichment = enrichment_result.get_enrichment_for_detection(detection_id_int)
            if det_enrichment:
                enrichment_data_to_persist = det_enrichment
                logger.debug(
                    f"Prepared enrichment data for fast path detection {detection_id_int}",
                    extra={
                        "detection_id": detection_id_int,
                        "enrichment_keys": list(det_enrichment.keys()),
                    },
                )

        # Call LLM for risk analysis (can take 60-120+ seconds)
        llm_start = time.time()
        try:
            risk_data = await self._call_llm(
                camera_name=camera_name,
                start_time=detection_time.isoformat(),
                end_time=detection_time.isoformat(),
                detections_list=detections_list,
                enriched_context=enriched_context,
                enrichment_result=enrichment_result,
                camera_health_context=camera_health_context,
            )
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            llm_duration_seconds = time.time() - llm_start
            # Record Nemotron AI request duration
            observe_ai_request_duration("nemotron", llm_duration_seconds)
            logger.debug(
                f"Fast path LLM analysis completed for detection {detection_id}",
                extra={
                    "camera_id": camera_id,
                    "detection_id": detection_id_int,
                    "duration_ms": llm_duration_ms,
                },
            )
        except Exception as e:
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            llm_duration_seconds = time.time() - llm_start
            # Record duration even on failure
            observe_ai_request_duration("nemotron", llm_duration_seconds)
            record_pipeline_error("nemotron_fast_path_error")
            sanitized_error = sanitize_error(e)
            logger.error(
                "LLM analysis failed for fast path detection",
                extra={
                    "camera_id": camera_id,
                    "detection_id": detection_id_int,
                    "duration_ms": llm_duration_ms,
                    "error": sanitized_error,
                },
                exc_info=True,
            )
            # Create fallback risk data - use generic message for user-facing content
            risk_data = {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Analysis unavailable - LLM service error",
                "reasoning": "Failed to analyze detection due to service error",
            }

        # =========================================================================
        # SESSION 2 (WRITE): Persist Event, junction table entries, and audit
        # This is a new, short-lived session for writing results to the database.
        # =========================================================================
        async with get_session() as session:
            # Create Event record with is_fast_path=True and advanced risk fields (NEM-3601)
            event = Event(
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=detection_time,
                ended_at=detection_time,
                risk_score=risk_data.get("risk_score", 50),
                risk_level=risk_data.get("risk_level", "medium"),
                summary=risk_data.get("summary", "No summary available"),
                reasoning=risk_data.get("reasoning", "No reasoning available"),
                llm_prompt=risk_data.get("llm_prompt"),
                reviewed=False,
                is_fast_path=True,
                # Advanced risk analysis fields (NEM-3601)
                entities=risk_data.get("entities"),
                flags=risk_data.get("flags"),
                confidence_factors=risk_data.get("confidence_factors"),
                recommended_action=risk_data.get("recommended_action"),
            )

            # NEM-2574: Batch database commits to reduce transaction overhead
            # Use flush() to persist objects and get IDs without committing.
            # A single commit happens at the end via get_session() context manager.
            # On any error, the context manager automatically rolls back the transaction.
            session.add(event)
            await session.flush()  # Persist event and get ID without committing

            # Populate event_detections junction table (NEM-1592, NEM-1998)
            # Fast path has only one detection. Uses ON CONFLICT DO NOTHING
            # to prevent race conditions when concurrent requests try to create
            # the same junction records.
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            from backend.models.event_detection import event_detections

            stmt = (
                pg_insert(event_detections)
                .values(event_id=event.id, detection_id=detection_id_int)
                .on_conflict_do_nothing(index_elements=["event_id", "detection_id"])
            )
            await session.execute(stmt)

            # Persist enrichment data to detection (bulk update)
            if enrichment_data_to_persist:
                from sqlalchemy import update as sql_update

                update_stmt = (
                    sql_update(Detection)
                    .where(Detection.id == detection_id_int)
                    .values(enrichment_data=enrichment_data_to_persist)
                )
                await session.execute(update_stmt)

            # Store idempotency key (NEM-1725) to prevent duplicates on retry
            # Note: This is stored in Redis, not the database transaction
            await self._set_idempotency(batch_id, event.id)

            # Create partial audit record for model contribution tracking
            try:
                from backend.services.pipeline_quality_audit_service import get_audit_service

                audit_service = get_audit_service()
                audit = audit_service.create_partial_audit(
                    event_id=event.id,
                    llm_prompt=risk_data.get("llm_prompt"),
                    enriched_context=enriched_context,
                    enrichment_result=enrichment_result,
                )
                session.add(audit)
                await session.flush()  # Persist audit and get ID without committing
                logger.debug(f"Created audit {audit.id} for event {event.id}")

                # Auto-enqueue for background evaluation (higher risk = higher priority)
                # This enables full AI audit evaluation when GPU is idle
                await self._enqueue_for_evaluation(event.id, event.risk_score or 50)

            except Exception as e:
                # NEM-2574: Audit failures should not roll back the Event creation
                # The audit is optional - we log a warning but continue
                logger.warning(
                    "Audit log write failed",
                    extra={
                        "action": "create_partial_audit",
                        "resource_id": str(event.id),
                        "resource_type": "event_audit",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                )

            # NEM-2574: Single commit at end via get_session() context manager
            # The context manager handles: commit on success, rollback on any error

        # Session 2 is now closed - connection returned to pool
        # =========================================================================

        total_duration_ms = int((time.time() - analysis_start) * 1000)
        total_duration_seconds = time.time() - analysis_start

        # Record stage duration and event creation metrics
        observe_stage_duration("analyze", total_duration_seconds)
        record_event_created()
        record_event_by_camera(camera_id, camera_name)

        # Log batch analysis completion with consistent batch_id context
        with log_context(batch_id=batch_id, camera_id=camera_id):
            logger.info(
                "Batch analysis completed",
                extra={
                    "event_id": event.id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "duration_ms": total_duration_ms,
                    "detection_count": 1,
                    "is_fast_path": True,
                },
            )

        # Broadcast via WebSocket if available (optional)
        try:
            await self._broadcast_event(event)
        except Exception as e:
            logger.warning(
                "Failed to broadcast fast path event",
                extra={"event_id": event.id, "error": str(e)},
                exc_info=True,
            )

        # Invalidate event stats cache so stats endpoints return fresh data (NEM-1682)
        try:
            cache = await self._get_facade().get_cache_service()
            await cache.invalidate_event_stats(reason=CacheInvalidationReason.EVENT_CREATED)
        except Exception as e:
            logger.warning(
                "Failed to invalidate event stats cache",
                extra={"error": str(e)},
            )

        # Trigger outbound webhooks for EVENT_CREATED (NEM-3624)
        await self._trigger_event_created_webhook(event)

        return event

    async def health_check(self) -> bool:
        """Check if LLM server is healthy.

        Sends a simple health check request to the LLM endpoint.

        Returns:
            True if LLM server is responding, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                # Include auth headers in health check
                response = await client.get(
                    f"{self._llm_url}/health",
                    headers=self._get_auth_headers(),
                )
                return bool(response.status_code == 200)
        except Exception as e:
            logger.warning(
                "LLM health check failed",
                extra={"error": str(e)},
                exc_info=True,
            )
            return False

    def _format_detections(self, detections: list[Detection]) -> str:
        """Format detections into a human-readable list for the prompt.

        Args:
            detections: List of Detection objects

        Returns:
            Formatted string with detection details
        """
        lines = []
        for i, det in enumerate(detections, 1):
            time_str = det.detected_at.strftime("%H:%M:%S")
            obj_type = det.object_type or "unknown"
            confidence = f"{det.confidence:.2f}" if det.confidence else "N/A"
            lines.append(f"  {i}. {time_str} - {obj_type} (confidence: {confidence})")

        return "\n".join(lines)

    async def _run_enrichment_pipeline(
        self, detections: list[Detection], camera_id: str | None = None
    ) -> EnrichmentTrackingResult | None:
        """Run the enrichment pipeline on detections with tracking (NEM-1672).

        Converts Detection models to DetectionInput format and runs the
        enrichment pipeline to extract license plates, faces, and OCR.
        Now returns EnrichmentTrackingResult which tracks which models
        succeeded/failed for visibility into partial failures.

        Args:
            detections: List of Detection models from the database
            camera_id: Camera ID for scene change detection and re-id

        Returns:
            EnrichmentTrackingResult with status, model results, and data,
            or None if no enrichment was needed
        """
        if not detections:
            return None

        # Convert Detection models to DetectionInput format
        # Build input list BEFORE creating pipeline to avoid unnecessary pipeline creation
        detection_inputs: list[DetectionInput] = []
        from pathlib import Path

        from PIL import Image

        # Type annotation matches EnrichmentPipeline.enrich_batch signature
        images: dict[int | None, Image.Image | Path | str] = {}

        for det in detections:
            # Skip detections without bounding boxes or object types
            if (
                det.bbox_x is None
                or det.bbox_y is None
                or det.bbox_width is None
                or det.bbox_height is None
                or det.object_type is None
            ):
                continue

            # Create DetectionInput with bounding box and video dimensions for scaling
            detection_input = DetectionInput(
                id=det.id,
                class_name=det.object_type,
                confidence=det.confidence or 0.0,
                bbox=BoundingBox(
                    x1=float(det.bbox_x),
                    y1=float(det.bbox_y),
                    x2=float(det.bbox_x + det.bbox_width),
                    y2=float(det.bbox_y + det.bbox_height),
                ),
                video_width=det.video_width,
                video_height=det.video_height,
            )
            detection_inputs.append(detection_input)

            # Map detection ID to image path
            if det.file_path:
                images[det.id] = det.file_path

        if not detection_inputs:
            return None

        # Set shared image for full-frame analysis (use first detection's image)
        # This enables vision extraction, scene change detection, and re-id
        if detections and detections[0].file_path:
            images[None] = detections[0].file_path

        # Now that we know we have valid inputs, get the pipeline
        pipeline = self._get_enrichment_pipeline()

        # Run the enrichment pipeline with tracking for partial failure visibility
        tracking_result = await pipeline.enrich_batch_with_tracking(
            detection_inputs, images, camera_id=camera_id
        )

        return tracking_result

    async def _call_llm(
        self,
        camera_name: str,
        start_time: str,
        end_time: str,
        detections_list: str,
        enriched_context: EnrichedContext | None = None,
        enrichment_result: EnrichmentResult | None = None,
        camera_health_context: str = "",
        auto_tuning_context: str = "",
        household_context: str = "",
    ) -> dict[str, Any]:
        """Call Nemotron LLM for risk analysis.

        Args:
            camera_name: Name of the camera
            start_time: Start of detection window (ISO format)
            end_time: End of detection window (ISO format)
            detections_list: Formatted list of detections
            enriched_context: Optional enriched context for enhanced prompts
            enrichment_result: Optional enrichment result with plates/faces
            camera_health_context: Optional camera tampering/scene change context (NEM-3012)
            auto_tuning_context: Optional auto-tuning recommendations from historical
                analysis (NEM-3015). Injected into prompt to improve analysis quality.
            household_context: Optional household matching context (NEM-3024).
                Contains known person/vehicle matches that should reduce risk scores.

        Returns:
            Dictionary with risk_score, risk_level, summary, and reasoning

        Raises:
            httpx.HTTPError: If LLM request fails
            ValueError: If response cannot be parsed

        Security:
            Sanitizes user-controlled data (camera_name, detections_list) before
            prompt interpolation to prevent prompt injection attacks. See
            NEM-1722 and backend/services/prompt_sanitizer.py for details.
        """
        # Sanitize user-controlled data to prevent prompt injection (NEM-1722)
        # Camera names and detection descriptions can be influenced by attackers
        # through configuration or adversarial ML inputs
        camera_name = sanitize_camera_name(camera_name)
        detections_list = sanitize_detection_description(detections_list)

        # Format the prompt based on available context
        has_enriched_context = (
            enriched_context is not None and enriched_context.baselines is not None
        )
        has_enrichment_result = enrichment_result is not None and (
            enrichment_result.has_license_plates or enrichment_result.has_faces
        )
        has_vision_extraction = (
            enrichment_result is not None and enrichment_result.has_vision_extraction
        )

        # Check for full model zoo enrichment (clothing, violence, vehicle analysis, etc.)
        has_model_zoo_enrichment = enrichment_result is not None and (
            enrichment_result.has_violence
            or enrichment_result.has_clothing_classifications
            or enrichment_result.has_vehicle_classifications
            or enrichment_result.has_vehicle_damage
            or enrichment_result.has_pet_classifications
            or enrichment_result.has_image_quality
        )

        # Track which template is used for metrics
        template_name: str = "basic"  # Default, will be overwritten

        if has_model_zoo_enrichment and has_enriched_context:
            # Use MODEL_ZOO_ENHANCED prompt with full enrichment from all models
            template_name = "model_zoo"
            from backend.services.reid_service import format_full_reid_context
            from backend.services.vision_extractor import (
                format_scene_analysis,
            )

            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None

            enricher = self._get_context_enricher()

            # Determine time of day from environment context or vision extraction
            time_of_day = "day"
            if (
                enrichment_result.vision_extraction
                and enrichment_result.vision_extraction.environment_context
            ):
                time_of_day = enrichment_result.vision_extraction.environment_context.time_of_day

            # Format scene analysis
            scene_text = "No scene analysis available."
            if (
                enrichment_result.vision_extraction
                and enrichment_result.vision_extraction.scene_analysis
            ):
                scene_text = format_scene_analysis(
                    enrichment_result.vision_extraction.scene_analysis
                )

            # Format re-id context
            reid_text = format_full_reid_context(
                enrichment_result.person_reid_matches,
                enrichment_result.vehicle_reid_matches,
            )

            # Format all model zoo enrichment contexts
            prompt = MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                timestamp=f"{start_time} to {end_time}",
                day_of_week=enriched_context.baselines.day_of_week,
                time_of_day=time_of_day,
                # Environmental context
                weather_context=format_weather_context(enrichment_result.weather_classification),
                image_quality_context=format_image_quality_context(
                    enrichment_result.image_quality,
                    enrichment_result.quality_change_detected,
                    enrichment_result.quality_change_description,
                ),
                # Camera health/tampering context (NEM-3012)
                camera_health_context=camera_health_context,
                # Detections with all enrichment
                detections_with_all_attributes=format_detections_with_all_enrichment(
                    [],  # Will use enrichment_result.to_context_string() for now
                    enrichment_result,
                    enrichment_result.vision_extraction,
                )
                if enrichment_result.vision_extraction
                else enrichment_result.to_context_string(),
                # Violence analysis
                violence_context=format_violence_context(enrichment_result.violence_detection),
                # Behavioral analysis (ViTPose pose estimation, X-CLIP action recognition)
                pose_analysis=format_pose_analysis_context(
                    {
                        det_id: {
                            "classification": pose.pose_class,
                            "confidence": pose.pose_confidence,
                        }
                        for det_id, pose in enrichment_result.pose_results.items()
                    }
                    if enrichment_result.pose_results
                    else None
                ),
                action_recognition=format_action_recognition_context(
                    {"0": enrichment_result.action_results}
                    if enrichment_result.action_results
                    else None
                ),
                # Vehicle analysis
                vehicle_classification_context=format_vehicle_classification_context(
                    enrichment_result.vehicle_classifications
                ),
                vehicle_damage_context=format_vehicle_damage_context(
                    enrichment_result.vehicle_damage,
                    time_of_day=time_of_day,
                ),
                # Person analysis
                clothing_analysis_context=format_clothing_analysis_context(
                    enrichment_result.clothing_classifications,
                    enrichment_result.clothing_segmentation,
                ),
                # Pet detection
                pet_classification_context=format_pet_classification_context(
                    enrichment_result.pet_classifications
                ),
                # Spatial context (Depth Anything V2)
                depth_context=format_depth_context(enrichment_result.depth_analysis),
                # Re-identification
                reid_context=reid_text,
                # Zone, baseline, cross-camera
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                scene_analysis=scene_text,
                # On-demand enrichment (future: will contain threat/pose/demographics)
                ondemand_enrichment_context="",
            )
        elif has_vision_extraction and has_enriched_context:
            # Use vision-enhanced prompt with Florence-2 attributes, re-id, and scene analysis
            template_name = "vision"
            from backend.services.reid_service import format_full_reid_context
            from backend.services.vision_extractor import (
                format_scene_analysis,
            )

            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None
            assert enrichment_result.vision_extraction is not None

            enricher = self._get_context_enricher()

            # Determine time of day from environment context
            time_of_day = "day"
            if enrichment_result.vision_extraction.environment_context:
                time_of_day = enrichment_result.vision_extraction.environment_context.time_of_day

            # Format scene analysis
            scene_text = "No scene analysis available."
            if enrichment_result.vision_extraction.scene_analysis:
                scene_text = format_scene_analysis(
                    enrichment_result.vision_extraction.scene_analysis
                )

            # Format re-id context
            reid_text = format_full_reid_context(
                enrichment_result.person_reid_matches,
                enrichment_result.vehicle_reid_matches,
            )

            prompt = VISION_ENHANCED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                timestamp=f"{start_time} to {end_time}",
                day_of_week=enriched_context.baselines.day_of_week,
                time_of_day=time_of_day,
                # Camera health/tampering context (NEM-3012)
                camera_health_context=camera_health_context,
                detections_with_attributes=enrichment_result.to_context_string(),
                reid_context=reid_text,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                scene_analysis=scene_text,
            )
        elif has_enriched_context and has_enrichment_result:
            # Use full enriched prompt with zone, baseline, cross-camera, and pipeline context
            template_name = "full_enriched"
            # These assertions help mypy understand type narrowing
            assert enriched_context is not None
            assert enriched_context.baselines is not None
            assert enrichment_result is not None
            enricher = self._get_context_enricher()
            prompt = FULL_ENRICHED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                day_of_week=enriched_context.baselines.day_of_week,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                hour=enriched_context.baselines.hour_of_day,
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                enrichment_context=enrichment_result.to_context_string(),
                detections_list=detections_list,
            )
        elif has_enriched_context:
            # Use enriched prompt with zone, baseline, and cross-camera context (no pipeline)
            template_name = "enriched"
            # These assertions help mypy understand type narrowing
            assert enriched_context is not None
            assert enriched_context.baselines is not None
            enricher = self._get_context_enricher()
            prompt = ENRICHED_RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                day_of_week=enriched_context.baselines.day_of_week,
                zone_analysis=enricher.format_zone_analysis(enriched_context.zones),
                hour=enriched_context.baselines.hour_of_day,
                baseline_comparison=enricher.format_baseline_comparison(enriched_context.baselines),
                deviation_score=f"{enriched_context.baselines.deviation_score:.2f}",
                cross_camera_summary=enricher.format_cross_camera_summary(
                    enriched_context.cross_camera
                ),
                detections_list=detections_list,
            )
        else:
            # Fall back to basic prompt
            prompt = RISK_ANALYSIS_PROMPT.format(
                camera_name=camera_name,
                start_time=start_time,
                end_time=end_time,
                detections_list=detections_list,
            )

        # Inject household context if available (NEM-3024, NEM-3315)
        # This provides known person/vehicle matches that should reduce risk scores
        # NEM-3315: Household context must appear at the TOP of the user prompt,
        # right after the SCORING REFERENCE table, before EVENT CONTEXT/DETECTIONS
        if household_context:
            # Find the ## EVENT CONTEXT section and insert household context before it
            event_context_marker = "## EVENT CONTEXT"
            if event_context_marker in prompt:
                prompt = prompt.replace(
                    event_context_marker,
                    f"{household_context}\n\n{event_context_marker}",
                )
            else:
                # Fallback: Insert after SCORING REFERENCE table if EVENT CONTEXT not found
                scoring_ref_marker = "## SCORING REFERENCE"
                if scoring_ref_marker in prompt:
                    # Find the end of the SCORING REFERENCE section (look for next ## or newline gap)
                    # Insert after the table ends
                    idx = prompt.find(scoring_ref_marker)
                    # Find the next double newline after the marker (end of table)
                    table_end = prompt.find("\n\n", idx + len(scoring_ref_marker))
                    if table_end != -1:
                        prompt = (
                            prompt[: table_end + 2]
                            + household_context
                            + "\n\n"
                            + prompt[table_end + 2 :]
                        )
                    else:
                        # Final fallback: append before assistant marker
                        assistant_marker = "<|im_start|>assistant"
                        if assistant_marker in prompt:
                            prompt = prompt.replace(
                                assistant_marker,
                                f"\n{household_context}\n{assistant_marker}",
                            )
                        else:
                            prompt = f"{prompt}\n{household_context}"
                else:
                    # Very last fallback: append before assistant marker
                    assistant_marker = "<|im_start|>assistant"
                    if assistant_marker in prompt:
                        prompt = prompt.replace(
                            assistant_marker,
                            f"\n{household_context}\n{assistant_marker}",
                        )
                    else:
                        prompt = f"{prompt}\n{household_context}"

        # Inject auto-tuning context if available (NEM-3015)
        # This provides historical recommendations from self-evaluation to improve analysis
        if auto_tuning_context:
            # Insert before the assistant turn marker
            # Prompts end with: <|im_end|>\n<|im_start|>assistant
            assistant_marker = "<|im_start|>assistant"
            if assistant_marker in prompt:
                prompt = prompt.replace(
                    assistant_marker,
                    f"\n{auto_tuning_context}\n{assistant_marker}",
                )
            else:
                # Fallback: append to end (shouldn't happen with standard prompts)
                prompt = f"{prompt}\n{auto_tuning_context}"

        # Validate and potentially truncate prompt to fit context window (NEM-1666 + NEM-1723)
        prompt = self._validate_and_truncate_prompt(prompt)

        # Get max_tokens from settings (accounts for context window limits)
        settings = get_settings()
        max_output_tokens = settings.nemotron_max_output_tokens

        # Call llama.cpp completion endpoint with retry logic (NEM-1343)
        # Nemotron-3-Nano uses ChatML format with <|im_end|> as message terminator
        payload: dict[str, Any] = {
            "prompt": prompt,
            "temperature": 0.7,  # Slightly creative for detailed reasoning
            "top_p": 0.95,
            "max_tokens": max_output_tokens,  # Use settings-based value
            "stop": ["<|im_end|>", "<|im_start|>"],
        }

        # Check if guided_json should be used (NEM-3726)
        # NVIDIA NIM's structured generation ensures valid JSON output
        use_guided_json_for_request = False
        if self._use_guided_json:
            # Check if endpoint supports guided_json (result is cached)
            supports_guided = await self._check_guided_json_support()
            if supports_guided:
                # Add guided_json to payload via nvext namespace
                guided_json_body = self._build_guided_json_extra_body()
                payload.update(guided_json_body)
                use_guided_json_for_request = True
                logger.debug(
                    "Using guided_json for structured LLM output",
                    extra={
                        "schema_keys": list(RISK_ANALYSIS_JSON_SCHEMA.get("properties", {}).keys())
                    },
                )
            else:
                logger.debug(
                    "Endpoint does not support guided_json, using regex fallback",
                    extra={"llm_url": self._llm_url},
                )

        # Merge auth headers with JSON content-type
        headers = {"Content-Type": "application/json"}
        headers.update(self._get_auth_headers())

        # Acquire shared AI inference semaphore via facade (NEM-1463, NEM-3150)
        # This limits concurrent AI operations to prevent GPU/service overload
        inference_semaphore = self._get_facade().get_inference_semaphore()

        # Retry loop with exponential backoff for transient failures
        last_exception: Exception | None = None
        completion_text: str = ""
        llm_result: dict[str, Any] = {}  # Store full result for token metrics
        # Explicit timeout as defense-in-depth (NEM-1465)
        # Use nemotron_read_timeout from settings (default 120s) + connect timeout
        explicit_timeout = settings.nemotron_read_timeout + settings.ai_connect_timeout

        async with inference_semaphore:
            # OpenTelemetry span for LLM inference (NEM-1467)
            # Wraps the entire LLM call including retries for end-to-end correlation
            with tracer.start_as_current_span("llm_inference") as span:
                # NEM-3794: Set AI model semantic attributes for standardized telemetry
                AIModelAttributes.set_on_span(
                    span,
                    model_name="nemotron-mini-4b-instruct",
                    model_version="1.0.0",
                    model_provider="nvidia",
                    device="cuda:0",
                    batch_size=1,
                )
                # Set pipeline context attributes
                set_pipeline_context_attributes(
                    span,
                    camera_id=camera_name,
                    stage="analyze",
                )
                # Legacy attributes for backward compatibility
                add_span_attributes(
                    llm_service="nemotron",
                    llm_url=self._llm_url,
                    template_name=template_name,
                    prompt_length=len(prompt),
                    pipeline_stage="llm_analysis",
                    guided_json_enabled=use_guided_json_for_request,
                )

                for attempt in range(self._max_retries):
                    try:
                        llm_call_start = time.monotonic()
                        # Explicit asyncio.timeout() as defense-in-depth (NEM-1465)
                        async with asyncio.timeout(explicit_timeout):
                            async with httpx.AsyncClient(timeout=self._timeout) as client:
                                response = await client.post(
                                    f"{self._llm_url}/completion",
                                    json=payload,
                                    headers=headers,
                                )
                                response.raise_for_status()
                                llm_result = response.json()
                        llm_call_duration = time.monotonic() - llm_call_start

                        # Extract completion text
                        completion_text = llm_result.get("content", "")
                        if not completion_text:
                            raise ValueError("Empty completion from LLM")

                        # Record token usage metrics (NEM-1730)
                        usage = llm_result.get("usage", {})
                        input_tokens = usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0)
                        record_nemotron_tokens(
                            camera_id=camera_name,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            duration_seconds=llm_call_duration
                            if input_tokens > 0 or output_tokens > 0
                            else None,
                        )

                        # Record cost tracking metrics via facade (NEM-1673, NEM-3150)
                        cost_tracker = self._get_facade().get_cost_tracker()
                        cost_tracker.track_llm_usage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            model="nemotron",
                            duration_seconds=llm_call_duration,
                            camera_id=camera_name,
                        )
                        cost_tracker.increment_event_count()

                        # NEM-3794: Set LLM semantic attributes for standardized telemetry
                        set_llm_inference_attributes(
                            span,
                            prompt_tokens=input_tokens,
                            completion_tokens=output_tokens,
                            total_tokens=input_tokens + output_tokens,
                            inference_time_ms=llm_call_duration * 1000,
                        )
                        set_inference_result_attributes(
                            span,
                            duration_ms=llm_call_duration * 1000,
                            status="success",
                        )
                        # Legacy attributes for backward compatibility (NEM-1467)
                        add_span_attributes(
                            llm_duration_ms=llm_call_duration * 1000,
                            llm_success=True,
                            llm_attempts=attempt + 1,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                        )

                        break  # Success, exit retry loop

                    except httpx.ConnectError as e:
                        last_exception = e
                        # Record exception on span for tracing (NEM-1467)
                        record_exception(
                            e, {"error_type": "connection_error", "attempt": attempt + 1}
                        )
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)  # Cap at 30 seconds
                            logger.warning(
                                f"Nemotron connection error (attempt {attempt + 1}/{self._max_retries}), "
                                f"retrying in {delay}s: {e}",
                                extra={
                                    "attempt": attempt + 1,
                                    "max_retries": self._max_retries,
                                    "retry_delay": delay,
                                },
                            )
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error("nemotron_connection_error")
                            logger.error(
                                f"Nemotron connection error after {self._max_retries} attempts: {e}",
                                extra={"attempts": self._max_retries},
                                exc_info=True,
                            )

                    except httpx.TimeoutException as e:
                        last_exception = e
                        # Record exception on span for tracing (NEM-1467)
                        record_exception(e, {"error_type": "timeout", "attempt": attempt + 1})
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)  # Cap at 30 seconds
                            logger.warning(
                                f"Nemotron timeout (attempt {attempt + 1}/{self._max_retries}), "
                                f"retrying in {delay}s: {e}",
                                extra={
                                    "attempt": attempt + 1,
                                    "max_retries": self._max_retries,
                                    "retry_delay": delay,
                                },
                            )
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error("nemotron_timeout")
                            logger.error(
                                f"Nemotron timeout after {self._max_retries} attempts: {e}",
                                extra={"attempts": self._max_retries},
                                exc_info=True,
                            )

                    except TimeoutError as e:
                        # asyncio.timeout() raises TimeoutError (NEM-1465 defense-in-depth)
                        last_exception = e
                        # Record exception on span for tracing (NEM-1467)
                        record_exception(
                            e, {"error_type": "asyncio_timeout", "attempt": attempt + 1}
                        )
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)  # Cap at 30 seconds
                            logger.warning(
                                f"Nemotron asyncio timeout (attempt {attempt + 1}/{self._max_retries}), "
                                f"retrying in {delay}s: request timed out after {explicit_timeout}s",
                                extra={
                                    "attempt": attempt + 1,
                                    "max_retries": self._max_retries,
                                    "retry_delay": delay,
                                    "explicit_timeout": explicit_timeout,
                                },
                            )
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error("nemotron_asyncio_timeout")
                            logger.error(
                                f"Nemotron asyncio timeout after {self._max_retries} attempts: "
                                f"request timed out after {explicit_timeout}s",
                                extra={
                                    "attempts": self._max_retries,
                                    "explicit_timeout": explicit_timeout,
                                },
                                exc_info=True,
                            )

                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code

                        # 5xx errors are server-side failures that should be retried
                        if status_code >= 500:
                            last_exception = e
                            # Record exception on span for tracing (NEM-1467)
                            record_exception(
                                e,
                                {
                                    "error_type": "server_error",
                                    "status_code": status_code,
                                    "attempt": attempt + 1,
                                },
                            )
                            if attempt < self._max_retries - 1:
                                delay = min(2**attempt, 30)  # Cap at 30 seconds
                                logger.warning(
                                    f"Nemotron server error {status_code} "
                                    f"(attempt {attempt + 1}/{self._max_retries}), "
                                    f"retrying in {delay}s",
                                    extra={
                                        "status_code": status_code,
                                        "attempt": attempt + 1,
                                        "max_retries": self._max_retries,
                                        "retry_delay": delay,
                                    },
                                )
                                await asyncio.sleep(delay)
                            else:
                                record_pipeline_error("nemotron_server_error")
                                logger.error(
                                    f"Nemotron server error {status_code} after {self._max_retries} attempts",
                                    extra={
                                        "status_code": status_code,
                                        "attempts": self._max_retries,
                                    },
                                    exc_info=True,
                                )
                        else:
                            # 4xx errors are client errors - don't retry
                            record_pipeline_error("nemotron_client_error")
                            # Record exception on span for tracing (NEM-1467)
                            record_exception(
                                e, {"error_type": "client_error", "status_code": status_code}
                            )
                            logger.error(
                                f"Nemotron client error {status_code}: {e}",
                                extra={"status_code": status_code},
                            )
                            raise  # Re-raise immediately for client errors

                    except ValueError:
                        # Empty completion - not retryable, re-raise immediately
                        raise

                    except Exception as e:
                        last_exception = e
                        # Record exception on span for tracing (NEM-1467)
                        record_exception(e, {"error_type": "unexpected", "attempt": attempt + 1})
                        if attempt < self._max_retries - 1:
                            delay = min(2**attempt, 30)  # Cap at 30 seconds
                            logger.warning(
                                f"Unexpected Nemotron error (attempt {attempt + 1}/{self._max_retries}), "
                                f"retrying in {delay}s: {sanitize_error(e)}",
                                extra={
                                    "attempt": attempt + 1,
                                    "max_retries": self._max_retries,
                                    "retry_delay": delay,
                                },
                            )
                            await asyncio.sleep(delay)
                        else:
                            record_pipeline_error("nemotron_unexpected_error")
                            logger.error(
                                f"Unexpected Nemotron error after {self._max_retries} attempts: "
                                f"{sanitize_error(e)}",
                                extra={"attempts": self._max_retries},
                                exc_info=True,
                            )
                else:
                    # All retries exhausted without success
                    # Add failure attributes to span (NEM-1467)
                    add_span_attributes(
                        llm_success=False,
                        llm_attempts=self._max_retries,
                    )
                    error_msg = f"Nemotron LLM call failed after {self._max_retries} attempts"
                    if last_exception:
                        raise AnalyzerUnavailableError(
                            error_msg, original_error=last_exception
                        ) from last_exception
                    raise AnalyzerUnavailableError(error_msg)

        # Parse JSON from completion
        risk_data = self._parse_llm_response(completion_text)

        # Validate and normalize risk data
        risk_data = self._validate_risk_data(risk_data)

        # Record risk analysis metrics (NEM-769)
        observe_risk_score(risk_data["risk_score"])
        record_event_by_risk_level(risk_data["risk_level"])
        record_prompt_template_used(template_name)

        # Include the prompt in the response for debugging/improvement
        risk_data["llm_prompt"] = prompt

        return risk_data

    def _parse_llm_response(self, text: str) -> dict[str, Any]:
        """Parse JSON response from LLM completion.

        Handles Nemotron-3-Nano output which includes <think>...</think> reasoning
        blocks before the actual JSON response.

        Args:
            text: LLM completion text

        Returns:
            Parsed dictionary with risk assessment

        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Strip <think>...</think> reasoning blocks (Nemotron-3-Nano format)
        # The model outputs reasoning in <think> tags before the JSON
        # Uses pre-compiled _THINK_PATTERN for performance
        cleaned_text = _THINK_PATTERN.sub("", text).strip()

        # Also handle incomplete think blocks (model may not close the tag)
        if "<think>" in cleaned_text:
            # Find content after the last </think> or after <think>...
            parts = cleaned_text.split("</think>")
            if len(parts) > 1:
                cleaned_text = parts[-1].strip()
            else:
                # No closing tag, try to find JSON after <think> block
                think_start = cleaned_text.find("<think>")
                # Look for JSON start after think
                json_start = cleaned_text.find("{", think_start)
                if json_start != -1:
                    cleaned_text = cleaned_text[json_start:]

        # Handle "thinking out loud" without <think> tags
        # If text starts with non-JSON content, skip to first {
        first_brace = cleaned_text.find("{")
        if first_brace > 0:
            # Check if there's preamble text before the JSON
            preamble = cleaned_text[:first_brace].strip()
            if preamble and not preamble.startswith("{"):
                logger.debug(f"Skipping LLM preamble: {preamble[:100]}...")
                cleaned_text = cleaned_text[first_brace:]

        # Try to extract JSON from the cleaned text
        # Look for JSON object pattern (handles nested objects)
        # Uses pre-compiled _JSON_PATTERN for performance
        matches = _JSON_PATTERN.findall(cleaned_text)

        # If no matches in cleaned text, try original text as fallback
        if not matches:
            matches = _JSON_PATTERN.findall(text)

        if not matches:
            raise ValueError(f"No JSON found in LLM response: {text[:200]}")

        # Try each match until we get valid JSON
        for match in matches:
            try:
                data = json.loads(match)
                if "risk_score" in data and "risk_level" in data:
                    return dict(data)  # Ensure we return a dict
            except json.JSONDecodeError:  # pragma: no cover
                continue  # pragma: no cover

        raise ValueError(f"Could not parse valid risk JSON from: {text[:200]}")

    def _validate_risk_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize risk assessment data using Pydantic schemas.

        Uses LLMRawResponse for lenient parsing, then converts to validated
        LLMRiskResponse via to_validated_response(). This ensures:
        - risk_score is clamped to 0-100
        - risk_level is valid (inferred from score if invalid)
        - summary and reasoning have defaults if missing

        Args:
            data: Raw risk data dictionary from LLM JSON response

        Returns:
            Validated and normalized risk data dictionary

        Note:
            This method uses the default severity thresholds from the schema.
            For dynamic thresholds based on Settings, the SeverityService can
            still be used as a fallback when risk_level inference is needed.
        """
        try:
            # First try strict validation with LLMRiskResponse
            # This handles well-formed LLM responses directly
            validated = LLMRiskResponse.model_validate(data)
            return validated.model_dump()
        except ValidationError:
            # Fall back to lenient parsing with LLMRawResponse.
            # This handles malformed responses (out-of-range scores, invalid levels).
            # See: NEM-2540 for rationale
            pass

        try:
            # Parse with lenient schema, then normalize
            raw = LLMRawResponse.model_validate(data)
            validated = raw.to_validated_response()
            return validated.model_dump()
        except ValidationError as e:
            # If even lenient parsing fails, use defaults with any available data
            logger.warning(
                "Failed to validate LLM response, using defaults",
                extra={"validation_errors": str(e.errors()), "error": str(e)},
            )

            # Extract what we can from the raw data
            risk_score = 50  # Default
            if "risk_score" in data:
                try:
                    score = data["risk_score"]
                    if isinstance(score, int | float):
                        risk_score = max(0, min(100, int(score)))
                    elif isinstance(score, str):
                        risk_score = max(0, min(100, int(float(score))))
                except (ValueError, TypeError):
                    # Risk score extraction failed - use default score.
                    # Partial LLM response recovery is better than complete failure.
                    # See: NEM-2540 for rationale
                    pass

            # Infer risk_level from score using SeverityService for consistency
            from backend.services.severity import get_severity_service

            severity_service = get_severity_service()
            severity = severity_service.risk_score_to_severity(risk_score)

            return {
                "risk_score": risk_score,
                "risk_level": severity.value,
                "summary": data.get("summary", "Risk analysis completed"),
                "reasoning": data.get("reasoning", "No detailed reasoning provided"),
            }

    def _validate_and_truncate_prompt(self, prompt: str) -> str:
        """Validate prompt token count and truncate if necessary (NEM-1666).

        Checks if the prompt fits within the context window limits and
        intelligently truncates enrichment data if needed.

        Args:
            prompt: The formatted prompt to validate

        Returns:
            The original prompt if it fits, or a truncated version if not

        Raises:
            ValueError: If truncation is disabled and prompt exceeds limits
        """
        from backend.core.metrics import record_prompt_truncated
        from backend.services.token_counter import get_token_counter

        settings = get_settings()
        counter = get_token_counter()

        # Validate the prompt against context window limits
        validation = counter.validate_prompt(prompt, settings.nemotron_max_output_tokens)

        if validation.is_valid:
            # Prompt fits, return as-is (warnings already logged by token_counter)
            return prompt

        # Prompt exceeds context limits - need to truncate or fail
        if not settings.context_truncation_enabled:
            raise ValueError(
                f"Prompt exceeds context window limits ({validation.prompt_tokens} tokens, "
                f"max {validation.available_tokens}) and truncation is disabled. "
                "Enable context_truncation_enabled or reduce enrichment data."
            )

        # Attempt intelligent truncation
        truncation_result = counter.truncate_enrichment_data(prompt, validation.available_tokens)

        if truncation_result.was_truncated:
            record_prompt_truncated()
            logger.warning(
                "Prompt truncated to fit context window",
                extra={
                    "original_tokens": truncation_result.original_tokens,
                    "final_tokens": truncation_result.final_tokens,
                    "sections_removed": truncation_result.sections_removed,
                    "available_tokens": validation.available_tokens,
                },
            )

        return truncation_result.truncated_prompt

    async def _broadcast_event(self, event: Event) -> None:
        """Broadcast event via WebSocket (optional).

        Publishes to the canonical 'security_events' Redis channel with the standard
        message envelope format: {"type": "event", "data": {...}}.

        This allows EventBroadcaster (which subscribes to 'security_events') to forward
        the event to all connected /ws/events WebSocket clients.

        NEM-2661: Soft-deleted events are not broadcast to prevent console errors
        when frontend tries to fetch non-existent event details.

        Args:
            event: Event to broadcast
        """
        if not self._redis:
            return

        # NEM-2661: Skip broadcasting soft-deleted events
        if event.deleted_at is not None:
            logger.debug(
                f"Skipping broadcast of soft-deleted event {event.id}",
                extra={"event_id": event.id, "deleted_at": event.deleted_at.isoformat()},
            )
            return

        try:
            # Use the canonical message envelope format expected by EventBroadcaster
            # and frontend WebSocket clients: {"type": "event", "data": {...}}
            message = {
                "type": "event",
                "data": {
                    "id": event.id,
                    "event_id": event.id,  # Legacy field for compatibility
                    "batch_id": event.batch_id,
                    "camera_id": event.camera_id,
                    "risk_score": event.risk_score,
                    "risk_level": event.risk_level,
                    "summary": event.summary,
                    "reasoning": event.reasoning,
                    "started_at": event.started_at.isoformat() if event.started_at else None,
                },
            }

            # Use EventBroadcaster API instead of direct Redis publish
            from backend.services.event_broadcaster import get_broadcaster

            broadcaster = await get_broadcaster(self._redis)
            await broadcaster.broadcast_event(message)
            logger.debug(f"Broadcasted event {event.id} via WebSocket")
        except Exception as e:  # pragma: no cover
            logger.warning(f"Failed to broadcast event: {e}", exc_info=True)  # pragma: no cover

    async def _trigger_event_created_webhook(self, event: Event) -> None:
        """Trigger outbound webhooks for EVENT_CREATED (NEM-3624).

        Webhook failures are logged but do not fail event creation.

        Args:
            event: Event that was created.
        """
        # Skip webhook for soft-deleted events
        if event.deleted_at is not None:
            return

        try:
            webhook_service = get_webhook_service()
            # Use a fresh session for webhook operations to avoid session scope issues
            async with get_session() as db:
                await webhook_service.trigger_webhooks_for_event(
                    db,
                    WebhookEventType.EVENT_CREATED,
                    {
                        "event_id": event.id,
                        "batch_id": event.batch_id,
                        "camera_id": event.camera_id,
                        "risk_score": event.risk_score,
                        "risk_level": event.risk_level,
                        "summary": event.summary,
                        "started_at": event.started_at.isoformat() if event.started_at else None,
                        "ended_at": event.ended_at.isoformat() if event.ended_at else None,
                        "is_fast_path": event.is_fast_path,
                    },
                    event_id=str(event.id),
                )
        except Exception as e:
            # Log but don't fail the main operation if webhook triggering fails
            logger.warning(
                f"Failed to trigger EVENT_CREATED webhooks: {e}",
                extra={"event_id": event.id},
            )

    async def _enqueue_for_evaluation(self, event_id: int, risk_score: int) -> None:
        """Enqueue event for background AI audit evaluation.

        Events are queued for full evaluation (self-critique, rubric scoring,
        consistency check, prompt improvement) when the GPU is idle. Higher
        risk events get higher priority and are evaluated first.

        Args:
            event_id: ID of the event to enqueue
            risk_score: Risk score (0-100), used as priority for evaluation order
        """
        if not self._redis:
            return

        try:
            from backend.core.config import get_settings
            from backend.services.evaluation_queue import get_evaluation_queue

            settings = get_settings()
            if not settings.background_evaluation_enabled:
                logger.debug(f"Background evaluation disabled, not queueing event {event_id}")
                return

            queue = get_evaluation_queue(self._redis)
            await queue.enqueue(event_id=event_id, priority=risk_score)
            logger.debug(
                f"Enqueued event {event_id} for background evaluation (priority: {risk_score})"
            )
        except Exception as e:
            # Non-critical: log warning but don't fail event creation
            logger.warning(
                "Failed to enqueue event for evaluation",
                extra={"event_id": event_id, "error": str(e)},
            )

    # =========================================================================
    # Streaming Methods (NEM-1665)
    # =========================================================================

    def _build_prompt(
        self,
        camera_name: str,
        start_time: str,
        end_time: str,
        detections_list: str,
        enriched_context: EnrichedContext | None = None,
        enrichment_result: EnrichmentResult | None = None,
    ) -> str:
        """Build the LLM prompt for risk analysis (NEM-1665).

        This method extracts the prompt-building logic from _call_llm for
        reuse by streaming methods.

        Args:
            camera_name: Sanitized camera name
            start_time: Start of detection window (ISO format)
            end_time: End of detection window (ISO format)
            detections_list: Formatted list of detections
            enriched_context: Optional enriched context for enhanced prompts
            enrichment_result: Optional enrichment result with plates/faces

        Returns:
            Formatted prompt string ready for LLM
        """
        # Suppress unused variable warnings - these may be used in future
        _ = enriched_context
        _ = enrichment_result

        # Use basic prompt for streaming (enriched prompts are complex)
        return RISK_ANALYSIS_PROMPT.format(
            camera_name=camera_name,
            start_time=start_time,
            end_time=end_time,
            detections_list=detections_list,
        )

    async def analyze_batch_streaming(
        self,
        batch_id: str,
        camera_id: str | None = None,
        detection_ids: list[int | str] | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Analyze a batch with streaming progress updates (NEM-1665).

        This method provides progressive LLM response updates during long
        inference times, allowing the frontend to display partial results.

        Args:
            batch_id: Batch identifier to analyze
            camera_id: Camera identifier (optional, from queue payload)
            detection_ids: List of detection IDs (optional, from queue payload)

        Yields:
            Dictionary events with type 'progress', 'complete', or 'error'
        """
        from backend.services.nemotron_streaming import (
            analyze_batch_streaming as streaming_analyze,
        )

        async for update in streaming_analyze(
            analyzer=self,
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        ):
            yield update
