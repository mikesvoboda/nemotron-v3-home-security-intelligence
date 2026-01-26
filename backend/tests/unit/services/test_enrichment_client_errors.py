"""Error handling tests for enrichment client service.

This module provides comprehensive error handling tests for the EnrichmentClient,
covering scenarios not tested in test_enrichment_client.py:
- Malformed JSON responses
- Invalid response structure (missing required fields)
- Unexpected exceptions during request processing
- Rate limiting (HTTP 429)
- Network interruption during request
- Health check error scenarios
- Various HTTP error codes
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
    EnrichmentClient,
    EnrichmentUnavailableError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.enrichment_url = "http://localhost:8094"
    settings.enrichment_light_url = "http://localhost:8096"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    settings.enrichment_read_timeout = 60.0
    settings.enrichment_cb_failure_threshold = 3
    settings.enrichment_cb_recovery_timeout = 30.0
    settings.enrichment_cb_half_open_max_calls = 2
    settings.enrichment_max_retries = 3
    # Config-driven model routing - all models default to heavy service for tests
    settings.get_enrichment_url_for_model = MagicMock(return_value="http://localhost:8094")
    return settings


@pytest.fixture
def enrichment_client(mock_settings):
    """Create enrichment client instance with mocked HTTP clients."""
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    mock_health_client = AsyncMock()
    mock_health_client.aclose = AsyncMock()

    with (
        patch("backend.services.enrichment_client.get_settings", return_value=mock_settings),
        patch("httpx.AsyncClient", side_effect=[mock_http_client, mock_health_client]),
    ):
        client = EnrichmentClient()
        client._http_client = mock_http_client
        client._health_http_client = mock_health_client
        return client


@pytest.fixture
def sample_image():
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def sample_video_frames():
    """Create sample video frames for action classification testing."""
    return [Image.new("RGB", (224, 224), color=f"#{i * 30:02x}0000") for i in range(8)]


# =============================================================================
# Malformed JSON Response Tests
# =============================================================================


class TestMalformedJsonResponses:
    """Test handling of malformed JSON responses from the enrichment service."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Return invalid JSON that can't be parsed
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # JSONDecodeError is caught by the generic Exception handler
        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_pet_classify_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_pet(sample_image)

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_clothing_classify_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test clothing classification with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_clothing(sample_image)

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_pose_analyze_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.analyze_pose(sample_image)

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_depth_estimate_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test depth estimation with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_depth(sample_image)

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_object_distance_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test object distance estimation with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))

        assert "unexpected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_action_classify_malformed_json(
        self, enrichment_client: EnrichmentClient, sample_video_frames: list[Image.Image]
    ):
        """Test action classification with malformed JSON response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_action(sample_video_frames)

        assert "unexpected" in str(exc_info.value).lower()


# =============================================================================
# Invalid Response Structure Tests
# =============================================================================


class TestInvalidResponseStructure:
    """Test handling of responses with missing required fields."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing required 'vehicle_type' field
        mock_response.json.return_value = {
            "confidence": 0.85,
            "inference_time_ms": 42.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # KeyError is caught by generic Exception handler
        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_pet_classify_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing required 'pet_type' field
        mock_response.json.return_value = {
            "confidence": 0.95,
            "inference_time_ms": 20.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_pet(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_clothing_classify_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test clothing classification with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing multiple required fields
        mock_response.json.return_value = {"confidence": 0.80}
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_clothing(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_pose_analyze_missing_keypoints(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with missing keypoints field in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing 'keypoints' field
        mock_response.json.return_value = {
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 35.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.analyze_pose(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_pose_analyze_invalid_keypoint_structure(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with invalid keypoint structure in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Keypoints missing required 'name' field
        mock_response.json.return_value = {
            "keypoints": [{"x": 0.5, "y": 0.1}],  # Missing 'name' and 'confidence'
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 35.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.analyze_pose(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_depth_estimate_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test depth estimation with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing depth map
        mock_response.json.return_value = {
            "min_depth": 0.0,
            "max_depth": 1.0,
            "inference_time_ms": 45.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_depth(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_object_distance_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test object distance estimation with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing estimated_distance_m
        mock_response.json.return_value = {
            "relative_depth": 0.35,
            "inference_time_ms": 55.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_action_classify_missing_fields(
        self, enrichment_client: EnrichmentClient, sample_video_frames: list[Image.Image]
    ):
        """Test action classification with missing required fields in response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Response missing 'action' field
        mock_response.json.return_value = {
            "confidence": 0.78,
            "is_suspicious": True,
            "inference_time_ms": 200.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_action(sample_video_frames)

        assert exc_info.value.original_error is not None


# =============================================================================
# HTTP Error Code Tests
# =============================================================================


class TestHttpErrorCodes:
    """Test handling of various HTTP error codes."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_rate_limiting_429(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with HTTP 429 rate limiting response."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # 429 is a 4xx error, so it returns None (no retry)
        result = await enrichment_client.classify_vehicle(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_vehicle_classify_http_500_internal_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with HTTP 500 internal server error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vehicle_classify_http_502_bad_gateway(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with HTTP 502 bad gateway error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_vehicle_classify_http_504_gateway_timeout(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with HTTP 504 gateway timeout."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 504
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Gateway Timeout",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pet_classify_http_400_bad_request(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with HTTP 400 bad request (returns None)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.classify_pet(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_pet_classify_http_404_not_found(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with HTTP 404 not found (returns None)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.classify_pet(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_clothing_classify_http_422_validation_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test clothing classification with HTTP 422 validation error (returns None)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.classify_clothing(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_pose_analyze_http_503_service_unavailable(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with HTTP 503 service unavailable."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.analyze_pose(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_depth_estimate_http_413_payload_too_large(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test depth estimation with HTTP 413 payload too large (returns None)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 413
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Payload Too Large",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.estimate_depth(sample_image)
        assert result is None


# =============================================================================
# Network and Connection Error Tests
# =============================================================================


class TestNetworkErrors:
    """Test handling of network-related errors."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_read_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with network read error."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.ReadError("Connection reset by peer")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_vehicle(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_pet_classify_write_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with network write error."""
        enrichment_client._http_client.post = AsyncMock(side_effect=httpx.WriteError("Broken pipe"))

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_pet(sample_image)

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_clothing_classify_pool_timeout(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test clothing classification with connection pool timeout."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.PoolTimeout("Pool timeout")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_clothing(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pose_analyze_read_timeout(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with read timeout."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.ReadTimeout("Read timeout")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.analyze_pose(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_depth_estimate_connect_timeout(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test depth estimation with connection timeout."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.ConnectTimeout("Connect timeout")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_depth(sample_image)

        assert "failed after" in str(exc_info.value) and "retries" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_object_distance_remote_protocol_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test object distance with remote protocol error."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.RemoteProtocolError("Protocol error")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))

        assert exc_info.value.original_error is not None

    @pytest.mark.asyncio
    async def test_action_classify_local_protocol_error(
        self, enrichment_client: EnrichmentClient, sample_video_frames: list[Image.Image]
    ):
        """Test action classification with local protocol error."""
        enrichment_client._http_client.post = AsyncMock(
            side_effect=httpx.LocalProtocolError("Local protocol error")
        )

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await enrichment_client.classify_action(sample_video_frames)

        assert exc_info.value.original_error is not None


# =============================================================================
# Health Check Error Tests
# =============================================================================


class TestHealthCheckErrors:
    """Test error handling for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_http_status_error(self, enrichment_client: EnrichmentClient):
        """Test health check with HTTP status error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )
        enrichment_client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await enrichment_client.check_health()

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_unexpected_exception(self, enrichment_client: EnrichmentClient):
        """Test health check with unexpected exception."""
        enrichment_client._health_http_client.get = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        result = await enrichment_client.check_health()

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_json_decode_error(self, enrichment_client: EnrichmentClient):
        """Test health check with JSON decode error."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
        enrichment_client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await enrichment_client.check_health()

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_for_error_status(
        self, enrichment_client: EnrichmentClient
    ):
        """Test is_healthy returns False when health check returns error status."""
        with patch.object(
            enrichment_client, "check_health", return_value={"status": "error", "error": "test"}
        ):
            result = await enrichment_client.is_healthy()
            assert result is False


# =============================================================================
# EnrichmentUnavailableError Tests
# =============================================================================


class TestEnrichmentUnavailableError:
    """Test the EnrichmentUnavailableError exception class."""

    def test_error_message(self):
        """Test error message is set correctly."""
        error = EnrichmentUnavailableError("Service unavailable")
        assert str(error) == "Service unavailable"

    def test_error_with_original_error(self):
        """Test error with original exception."""
        original = ConnectionError("Connection refused")
        error = EnrichmentUnavailableError("Service unavailable", original_error=original)

        assert str(error) == "Service unavailable"
        assert error.original_error is original

    def test_error_without_original_error(self):
        """Test error without original exception."""
        error = EnrichmentUnavailableError("Service unavailable")
        assert error.original_error is None


# =============================================================================
# Unexpected Exception Tests
# =============================================================================


class TestUnexpectedExceptions:
    """Test handling of unexpected exceptions during request processing."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_memory_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification with memory error during processing."""
        with patch.object(
            enrichment_client, "_encode_image_to_base64", side_effect=MemoryError("Out of memory")
        ):
            # MemoryError during _encode_image_to_base64 is not caught (it's before try block)
            with pytest.raises(MemoryError) as exc_info:
                await enrichment_client.classify_vehicle(sample_image)

            assert "Out of memory" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pet_classify_value_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification with ValueError during processing."""
        with patch.object(
            enrichment_client, "_encode_image_to_base64", side_effect=ValueError("Invalid image")
        ):
            # ValueError during _encode_image_to_base64 is not caught (it's before try block)
            with pytest.raises(ValueError) as exc_info:
                await enrichment_client.classify_pet(sample_image)

            assert "Invalid image" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_clothing_classify_type_error(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test clothing classification with TypeError during processing."""
        with patch.object(
            enrichment_client, "_encode_image_to_base64", side_effect=TypeError("Wrong type")
        ):
            # TypeError during _encode_image_to_base64 is not caught (it's before try block)
            with pytest.raises(TypeError) as exc_info:
                await enrichment_client.classify_clothing(sample_image)

            assert "Wrong type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_action_classify_runtime_error(
        self, enrichment_client: EnrichmentClient, sample_video_frames: list[Image.Image]
    ):
        """Test action classification with RuntimeError during processing."""
        with patch.object(
            enrichment_client, "_encode_image_to_base64", side_effect=RuntimeError("Runtime error")
        ):
            # RuntimeError during _encode_image_to_base64 is not caught (it's before try block)
            with pytest.raises(RuntimeError) as exc_info:
                await enrichment_client.classify_action(sample_video_frames)

            assert "Runtime error" in str(exc_info.value)


# =============================================================================
# Response Type Tests
# =============================================================================


class TestResponseTypes:
    """Test handling of responses with wrong data types."""

    @pytest.mark.asyncio
    async def test_vehicle_classify_confidence_as_string(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test vehicle classification when confidence is returned as string."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        # Confidence as string instead of float - should still work due to dataclass
        mock_response.json.return_value = {
            "vehicle_type": "car",
            "display_name": "car",
            "confidence": "0.95",  # String instead of float
            "is_commercial": False,
            "all_scores": {"car": 0.95},
            "inference_time_ms": 42.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # This may succeed or fail depending on dataclass handling
        # The test verifies the behavior is consistent
        result = await enrichment_client.classify_vehicle(sample_image)
        # If it succeeds, confidence should be the string value
        assert result is not None
        assert result.confidence == "0.95"

    @pytest.mark.asyncio
    async def test_pet_classify_null_breed(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pet classification when breed is null/None."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "pet_type": "dog",
            "breed": None,  # Null value
            "confidence": 0.95,
            "is_household_pet": True,
            "inference_time_ms": 20.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.classify_pet(sample_image)
        assert result is not None
        assert result.breed is None

    @pytest.mark.asyncio
    async def test_pose_analyze_empty_keypoints_list(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test pose analysis with empty keypoints list."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "keypoints": [],  # Empty list - valid but no detections
            "posture": "unknown",
            "alerts": [],
            "inference_time_ms": 30.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.analyze_pose(sample_image)
        assert result is not None
        assert len(result.keypoints) == 0
        assert result.posture == "unknown"

    @pytest.mark.asyncio
    async def test_action_classify_empty_all_scores(
        self, enrichment_client: EnrichmentClient, sample_video_frames: list[Image.Image]
    ):
        """Test action classification with empty all_scores dict."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "action": "unknown",
            "confidence": 0.0,
            "is_suspicious": False,
            "risk_weight": 0.0,
            "all_scores": {},  # Empty dict
            "inference_time_ms": 150.0,
        }
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        result = await enrichment_client.classify_action(sample_video_frames)
        assert result is not None
        assert len(result.all_scores) == 0


# =============================================================================
# Concurrent Request Error Tests
# =============================================================================


class TestConcurrentRequestErrors:
    """Test error handling with concurrent requests."""

    @pytest.mark.asyncio
    async def test_multiple_requests_with_mixed_errors(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ):
        """Test handling of mixed errors in concurrent requests."""
        import asyncio

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # All errors are retryable, so they will be retried 3 times each
            if call_count % 3 == 1:
                raise httpx.ConnectError("Connection refused")
            elif call_count % 3 == 2:
                raise httpx.TimeoutException("Timeout")
            else:
                mock_response = MagicMock(spec=httpx.Response)
                mock_response.status_code = 503
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "Service Unavailable",
                    request=MagicMock(),
                    response=mock_response,
                )
                return mock_response

        enrichment_client._http_client.post = AsyncMock(side_effect=mock_post)

        # All three should raise EnrichmentUnavailableError
        tasks = [
            enrichment_client.classify_vehicle(sample_image),
            enrichment_client.classify_vehicle(sample_image),
            enrichment_client.classify_vehicle(sample_image),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be EnrichmentUnavailableError
        assert all(isinstance(r, EnrichmentUnavailableError) for r in results)
        # Each request retries 3 times, so 3 requests x 3 attempts = 9 total calls
        assert call_count == 9
