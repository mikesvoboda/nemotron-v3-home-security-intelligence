"""Unit tests for Nemotron analyzer guided_json structured generation support (NEM-3726).

These tests verify the integration of NVIDIA NIM's structured generation feature
which enforces valid JSON output using the RISK_ANALYSIS_JSON_SCHEMA.

Tests cover:
- guided_json is included in request when supported
- guided_json is NOT included when not supported
- Fallback parsing works when guided_json disabled
- Configuration flags control behavior
- Endpoint support detection and caching
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.api.schemas.llm_response import RISK_ANALYSIS_JSON_SCHEMA
from backend.services.nemotron_analyzer import NemotronAnalyzer

# Mark all tests in this file as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.timeout(60)]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for Nemotron analyzer tests."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def mock_settings_with_guided_json():
    """Create mock settings with guided_json enabled."""
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
    mock.nemotron_url = "http://localhost:8091"
    mock.nemotron_api_key = None
    mock.ai_connect_timeout = 10.0
    mock.nemotron_read_timeout = 120.0
    mock.ai_health_timeout = 5.0
    mock.nemotron_max_retries = 2
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    mock.nemotron_context_window = 4096
    mock.nemotron_max_output_tokens = 1536
    mock.context_utilization_warning_threshold = 0.80
    mock.context_truncation_enabled = True
    mock.llm_tokenizer_encoding = "cl100k_base"
    mock.image_quality_enabled = False
    mock.ai_warmup_enabled = True
    mock.ai_cold_start_threshold_seconds = 300.0
    mock.nemotron_warmup_prompt = "Test warmup prompt"
    mock.scene_change_resize_width = 640
    mock.use_enrichment_service = False
    mock.ai_max_concurrent_inferences = 4
    # Guided JSON settings (NEM-3726)
    mock.nemotron_use_guided_json = True
    mock.nemotron_guided_json_fallback = True
    return mock


@pytest.fixture
def mock_settings_without_guided_json(mock_settings_with_guided_json):
    """Create mock settings with guided_json disabled."""
    mock_settings_with_guided_json.nemotron_use_guided_json = False
    return mock_settings_with_guided_json


@pytest.fixture
def analyzer_with_guided_json(mock_redis_client, mock_settings_with_guided_json):
    """Create NemotronAnalyzer instance with guided_json enabled."""
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings_with_guided_json,
        ),
        patch(
            "backend.services.severity.get_settings", return_value=mock_settings_with_guided_json
        ),
        patch(
            "backend.services.token_counter.get_settings",
            return_value=mock_settings_with_guided_json,
        ),
        patch("backend.core.config.get_settings", return_value=mock_settings_with_guided_json),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=mock_settings_with_guided_json,
        ),
    ):
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


@pytest.fixture
def analyzer_without_guided_json(mock_redis_client, mock_settings_without_guided_json):
    """Create NemotronAnalyzer instance with guided_json disabled."""
    with (
        patch(
            "backend.services.nemotron_analyzer.get_settings",
            return_value=mock_settings_without_guided_json,
        ),
        patch(
            "backend.services.severity.get_settings", return_value=mock_settings_without_guided_json
        ),
        patch(
            "backend.services.token_counter.get_settings",
            return_value=mock_settings_without_guided_json,
        ),
        patch("backend.core.config.get_settings", return_value=mock_settings_without_guided_json),
        patch(
            "backend.services.inference_semaphore.get_settings",
            return_value=mock_settings_without_guided_json,
        ),
    ):
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


# =============================================================================
# Test: Configuration Flags
# =============================================================================


class TestGuidedJsonConfiguration:
    """Tests for guided_json configuration flags."""

    def test_guided_json_enabled_by_default(self, analyzer_with_guided_json):
        """Test that guided_json is enabled when configured."""
        assert analyzer_with_guided_json.is_guided_json_enabled() is True

    def test_guided_json_disabled_when_configured(self, analyzer_without_guided_json):
        """Test that guided_json is disabled when configured."""
        assert analyzer_without_guided_json.is_guided_json_enabled() is False

    def test_fallback_enabled_by_default(self, analyzer_with_guided_json):
        """Test that fallback is enabled when configured."""
        assert analyzer_with_guided_json.is_guided_json_fallback_enabled() is True

    def test_build_guided_json_extra_body_when_enabled(self, analyzer_with_guided_json):
        """Test that extra_body is built correctly when enabled."""
        extra_body = analyzer_with_guided_json._build_guided_json_extra_body()

        assert "nvext" in extra_body
        assert "guided_json" in extra_body["nvext"]
        assert extra_body["nvext"]["guided_json"] == RISK_ANALYSIS_JSON_SCHEMA

    def test_build_guided_json_extra_body_when_disabled(self, analyzer_without_guided_json):
        """Test that extra_body is empty when disabled."""
        extra_body = analyzer_without_guided_json._build_guided_json_extra_body()

        assert extra_body == {}


# =============================================================================
# Test: Endpoint Support Detection
# =============================================================================


class TestGuidedJsonSupportDetection:
    """Tests for guided_json endpoint support detection."""

    @pytest.mark.asyncio
    async def test_check_support_returns_true_on_success(self, analyzer_with_guided_json):
        """Test that support check returns True when endpoint returns 2xx."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is True
        assert analyzer_with_guided_json._supports_guided_json is True

    @pytest.mark.asyncio
    async def test_check_support_returns_false_on_4xx(self, analyzer_with_guided_json):
        """Test that support check returns False when endpoint returns 4xx."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 422  # Unprocessable Entity

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is False
        assert analyzer_with_guided_json._supports_guided_json is False

    @pytest.mark.asyncio
    async def test_check_support_caches_result(self, analyzer_with_guided_json):
        """Test that support check result is cached."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # First call should make HTTP request
            result1 = await analyzer_with_guided_json._check_guided_json_support()
            # Second call should use cached result
            result2 = await analyzer_with_guided_json._check_guided_json_support()

        assert result1 is True
        assert result2 is True
        # HTTP client should only be called once due to caching
        assert mock_client_class.call_count == 1

    @pytest.mark.asyncio
    async def test_check_support_returns_false_on_connection_error(self, analyzer_with_guided_json):
        """Test that support check returns False on connection error after retries (NEM-3886)."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("asyncio.sleep") as mock_sleep,  # Mock sleep to speed up test
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is False
        # Should NOT cache on transient errors
        assert analyzer_with_guided_json._supports_guided_json is None
        # Should retry 3 times (max_retries)
        assert mock_client.post.call_count == 3
        # Should sleep between retries (2 sleeps for 3 attempts)
        assert mock_sleep.call_count == 2
        # Verify exponential backoff delays
        mock_sleep.assert_any_call(1.0)  # First retry delay
        mock_sleep.assert_any_call(2.0)  # Second retry delay

    @pytest.mark.asyncio
    async def test_check_support_returns_false_on_timeout(self, analyzer_with_guided_json):
        """Test that support check returns False on timeout after retries (NEM-3886)."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("asyncio.sleep") as mock_sleep,  # Mock sleep to speed up test
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is False
        # Should NOT cache on transient errors
        assert analyzer_with_guided_json._supports_guided_json is None
        # Should retry 3 times (max_retries)
        assert mock_client.post.call_count == 3
        # Should sleep between retries (2 sleeps for 3 attempts)
        assert mock_sleep.call_count == 2

    @pytest.mark.asyncio
    async def test_check_support_retries_and_succeeds_on_second_attempt(
        self, analyzer_with_guided_json
    ):
        """Test that support check retries and succeeds after transient error (NEM-3886)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("asyncio.sleep") as mock_sleep,  # Mock sleep to speed up test
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            # Fail first, succeed second
            mock_client.post.side_effect = [
                httpx.ConnectError("Connection refused"),
                mock_response,
            ]
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is True
        # Should cache successful result
        assert analyzer_with_guided_json._supports_guided_json is True
        # Should have made 2 attempts (fail, then succeed)
        assert mock_client.post.call_count == 2
        # Should sleep once between attempts
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_once_with(1.0)  # First retry delay

    @pytest.mark.asyncio
    async def test_check_support_retries_server_error_and_succeeds(self, analyzer_with_guided_json):
        """Test that support check retries 5xx errors and succeeds (NEM-3886)."""
        mock_error_response = MagicMock(spec=httpx.Response)
        mock_error_response.status_code = 503
        mock_success_response = MagicMock(spec=httpx.Response)
        mock_success_response.status_code = 200

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("asyncio.sleep") as mock_sleep,  # Mock sleep to speed up test
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            # Fail with 503, then succeed
            mock_client.post.side_effect = [
                httpx.HTTPStatusError(
                    "Service Unavailable", request=MagicMock(), response=mock_error_response
                ),
                mock_success_response,
            ]
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._check_guided_json_support()

        assert result is True
        # Should cache successful result
        assert analyzer_with_guided_json._supports_guided_json is True
        # Should have made 2 attempts (fail, then succeed)
        assert mock_client.post.call_count == 2
        # Should sleep once between attempts
        assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    async def test_reset_cache_clears_cached_result(self, analyzer_with_guided_json):
        """Test that reset_guided_json_support_cache clears the cached result."""
        # Set a cached result
        analyzer_with_guided_json._supports_guided_json = True

        # Reset the cache
        analyzer_with_guided_json.reset_guided_json_support_cache()

        assert analyzer_with_guided_json._supports_guided_json is None

    @pytest.mark.asyncio
    async def test_public_supports_method(self, analyzer_with_guided_json):
        """Test the public supports_guided_json method."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json.supports_guided_json()

        assert result is True


# =============================================================================
# Test: Payload Construction
# =============================================================================


class TestGuidedJsonPayloadConstruction:
    """Tests for guided_json in LLM request payload."""

    @pytest.mark.asyncio
    async def test_payload_includes_guided_json_when_supported(
        self, analyzer_with_guided_json, mock_settings_with_guided_json
    ):
        """Test that payload includes guided_json when endpoint supports it."""
        # Setup mock for guided_json support check
        support_check_response = MagicMock(spec=httpx.Response)
        support_check_response.status_code = 200

        # Setup mock for actual LLM call
        llm_response = MagicMock(spec=httpx.Response)
        llm_response.status_code = 200
        llm_response.json.return_value = {
            "content": json.dumps(
                {
                    "risk_score": 25,
                    "risk_level": "low",
                    "summary": "Test summary",
                    "reasoning": "Test reasoning",
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        captured_payload = None

        async def capture_post(url, json=None, headers=None):
            nonlocal captured_payload
            # Support check uses shorter prompt
            if json and json.get("prompt") == "Say hello":
                return support_check_response
            # Main LLM call
            captured_payload = json
            return llm_response

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_with_guided_json,
            ),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = capture_post
            mock_client_class.return_value = mock_client

            # Call _call_llm which should include guided_json
            result = await analyzer_with_guided_json._call_llm(
                camera_name="test_camera",
                start_time="2025-01-26T10:00:00",
                end_time="2025-01-26T10:01:00",
                detections_list="1x person detected",
            )

        # Verify guided_json was included in the payload
        assert captured_payload is not None
        assert "nvext" in captured_payload
        assert "guided_json" in captured_payload["nvext"]
        assert captured_payload["nvext"]["guided_json"] == RISK_ANALYSIS_JSON_SCHEMA
        assert result["risk_score"] == 25

    @pytest.mark.asyncio
    async def test_payload_excludes_guided_json_when_disabled(
        self, analyzer_without_guided_json, mock_settings_without_guided_json
    ):
        """Test that payload excludes guided_json when disabled."""
        llm_response = MagicMock(spec=httpx.Response)
        llm_response.status_code = 200
        llm_response.json.return_value = {
            "content": json.dumps(
                {
                    "risk_score": 30,
                    "risk_level": "medium",
                    "summary": "Test summary",
                    "reasoning": "Test reasoning",
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        captured_payload = None

        async def capture_post(url, json=None, headers=None):
            nonlocal captured_payload
            captured_payload = json
            return llm_response

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_without_guided_json,
            ),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = capture_post
            mock_client_class.return_value = mock_client

            result = await analyzer_without_guided_json._call_llm(
                camera_name="test_camera",
                start_time="2025-01-26T10:00:00",
                end_time="2025-01-26T10:01:00",
                detections_list="1x person detected",
            )

        # Verify guided_json was NOT included in the payload
        assert captured_payload is not None
        assert "nvext" not in captured_payload
        assert result["risk_score"] == 30

    @pytest.mark.asyncio
    async def test_payload_excludes_guided_json_when_not_supported(
        self, analyzer_with_guided_json, mock_settings_with_guided_json
    ):
        """Test that payload excludes guided_json when endpoint doesn't support it."""
        # Setup mock for guided_json support check (returns 422)
        support_check_response = MagicMock(spec=httpx.Response)
        support_check_response.status_code = 422

        # Setup mock for actual LLM call
        llm_response = MagicMock(spec=httpx.Response)
        llm_response.status_code = 200
        llm_response.json.return_value = {
            "content": json.dumps(
                {
                    "risk_score": 45,
                    "risk_level": "medium",
                    "summary": "Test summary",
                    "reasoning": "Test reasoning",
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        captured_payload = None

        async def capture_post(url, json=None, headers=None):
            nonlocal captured_payload
            if json and json.get("prompt") == "Say hello":
                return support_check_response
            captured_payload = json
            return llm_response

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_with_guided_json,
            ),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = capture_post
            mock_client_class.return_value = mock_client

            result = await analyzer_with_guided_json._call_llm(
                camera_name="test_camera",
                start_time="2025-01-26T10:00:00",
                end_time="2025-01-26T10:01:00",
                detections_list="1x person detected",
            )

        # Verify guided_json was NOT included because endpoint doesn't support it
        assert captured_payload is not None
        assert "nvext" not in captured_payload
        assert result["risk_score"] == 45


# =============================================================================
# Test: Schema Correctness
# =============================================================================


class TestRiskAnalysisJsonSchema:
    """Tests for RISK_ANALYSIS_JSON_SCHEMA structure."""

    def test_schema_has_required_fields(self):
        """Test that schema defines required fields."""
        assert "required" in RISK_ANALYSIS_JSON_SCHEMA
        required = RISK_ANALYSIS_JSON_SCHEMA["required"]
        assert "risk_score" in required
        assert "risk_level" in required
        assert "summary" in required
        assert "reasoning" in required

    def test_schema_has_risk_score_constraints(self):
        """Test that risk_score has correct constraints."""
        props = RISK_ANALYSIS_JSON_SCHEMA["properties"]
        risk_score = props["risk_score"]
        assert risk_score["type"] == "integer"
        assert risk_score["minimum"] == 0
        assert risk_score["maximum"] == 100

    def test_schema_has_risk_level_enum(self):
        """Test that risk_level has correct enum values."""
        props = RISK_ANALYSIS_JSON_SCHEMA["properties"]
        risk_level = props["risk_level"]
        assert risk_level["type"] == "string"
        assert "enum" in risk_level
        assert set(risk_level["enum"]) == {"low", "medium", "high", "critical"}

    def test_schema_has_entities_array(self):
        """Test that entities is defined as an array."""
        props = RISK_ANALYSIS_JSON_SCHEMA["properties"]
        assert "entities" in props
        entities = props["entities"]
        assert entities["type"] == "array"
        assert "items" in entities

    def test_schema_has_recommended_action_enum(self):
        """Test that recommended_action has correct enum values."""
        props = RISK_ANALYSIS_JSON_SCHEMA["properties"]
        assert "recommended_action" in props
        recommended_action = props["recommended_action"]
        assert recommended_action["type"] == "string"
        assert "enum" in recommended_action
        assert set(recommended_action["enum"]) == {"none", "review", "alert", "immediate_response"}


# =============================================================================
# Test: Fallback Parsing
# =============================================================================


class TestFallbackParsing:
    """Tests for regex fallback parsing when guided_json is disabled or unsupported."""

    def test_parse_llm_response_extracts_json(self, analyzer_with_guided_json):
        """Test that _parse_llm_response correctly extracts JSON."""
        response_text = (
            '{"risk_score": 75, "risk_level": "high", "summary": "Test", "reasoning": "Test"}'
        )

        result = analyzer_with_guided_json._parse_llm_response(response_text)

        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"

    def test_parse_llm_response_handles_think_blocks(self, analyzer_with_guided_json):
        """Test that _parse_llm_response removes <think> blocks."""
        response_text = '<think>Let me analyze this...</think>{"risk_score": 50, "risk_level": "medium", "summary": "Test", "reasoning": "Test"}'

        result = analyzer_with_guided_json._parse_llm_response(response_text)

        assert result["risk_score"] == 50
        assert result["risk_level"] == "medium"

    def test_parse_llm_response_handles_preamble(self, analyzer_with_guided_json):
        """Test that _parse_llm_response handles text before JSON."""
        response_text = 'Based on my analysis, here is the assessment:\n{"risk_score": 35, "risk_level": "medium", "summary": "Test", "reasoning": "Test"}'

        result = analyzer_with_guided_json._parse_llm_response(response_text)

        assert result["risk_score"] == 35

    def test_parse_llm_response_raises_on_no_json(self, analyzer_with_guided_json):
        """Test that _parse_llm_response raises ValueError when no JSON found."""
        response_text = "This is just plain text without any JSON."

        with pytest.raises(ValueError, match="No JSON found"):
            analyzer_with_guided_json._parse_llm_response(response_text)

    def test_validate_risk_data_clamps_score(self, analyzer_with_guided_json):
        """Test that _validate_risk_data clamps out-of-range scores."""
        raw_data = {
            "risk_score": 150,
            "risk_level": "critical",
            "summary": "Test",
            "reasoning": "Test",
        }

        result = analyzer_with_guided_json._validate_risk_data(raw_data)

        assert result["risk_score"] == 100

    def test_validate_risk_data_normalizes_level(self, analyzer_with_guided_json):
        """Test that _validate_risk_data normalizes risk_level to lowercase."""
        raw_data = {
            "risk_score": 50,
            "risk_level": "MEDIUM",
            "summary": "Test",
            "reasoning": "Test",
        }

        result = analyzer_with_guided_json._validate_risk_data(raw_data)

        assert result["risk_level"] == "medium"
