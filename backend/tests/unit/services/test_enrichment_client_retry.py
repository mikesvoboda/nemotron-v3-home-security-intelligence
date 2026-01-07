"""Unit tests for enrichment client retry logic with exponential backoff.

Tests cover:
- _retry_with_backoff method behavior
- Exponential backoff delay calculation with jitter
- Retry on transient errors (ConnectError, TimeoutException)
- No retry on non-transient errors (HTTP 4xx)
- Retry metrics recording
- Max retry configuration

NEM-1732: Add retry logic to enrichment client with exponential backoff.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
    EnrichmentClient,
    EnrichmentUnavailableError,
    reset_enrichment_client,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
async def reset_global_client() -> None:
    """Reset global enrichment client before and after each test."""
    await reset_enrichment_client()
    yield
    await reset_enrichment_client()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.enrichment_url = "http://test-enrichment:8094"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    # Circuit breaker configuration
    settings.enrichment_cb_failure_threshold = 5
    settings.enrichment_cb_recovery_timeout = 60.0
    settings.enrichment_cb_half_open_max_calls = 3
    # Retry configuration
    settings.enrichment_max_retries = 3
    return settings


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def client(mock_settings: MagicMock) -> EnrichmentClient:
    """Create an EnrichmentClient with mocked settings."""
    with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
        return EnrichmentClient()


@pytest.fixture
def client_with_custom_retries(mock_settings: MagicMock) -> EnrichmentClient:
    """Create an EnrichmentClient with custom retry count."""
    mock_settings.enrichment_max_retries = 5
    with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
        return EnrichmentClient()


# =============================================================================
# Retry Configuration Tests
# =============================================================================


class TestEnrichmentClientRetryConfig:
    """Tests for retry configuration in EnrichmentClient."""

    def test_client_has_max_retries_attribute(self, client: EnrichmentClient) -> None:
        """Test that client has max_retries attribute from settings."""
        assert hasattr(client, "_max_retries")
        assert client._max_retries == 3

    def test_client_respects_custom_max_retries(
        self, client_with_custom_retries: EnrichmentClient
    ) -> None:
        """Test that client respects custom max_retries from settings."""
        assert client_with_custom_retries._max_retries == 5


# =============================================================================
# Retry Behavior Tests - Vehicle Classification
# =============================================================================


class TestEnrichmentClientRetryVehicle:
    """Tests for retry behavior in classify_vehicle method."""

    @pytest.mark.asyncio
    async def test_classify_vehicle_retries_on_connect_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_vehicle retries on ConnectError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.92,
            "is_commercial": False,
            "all_scores": {"sedan": 0.92},
            "inference_time_ms": 42.0,
        }
        mock_response.raise_for_status = MagicMock()

        # Fail first 2 times, succeed on 3rd
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch(
                "backend.services.enrichment_client.increment_enrichment_retry"
            ) as mock_retry_metric,
        ):
            result = await client.classify_vehicle(sample_image)

            assert result is not None
            assert result.vehicle_type == "sedan"
            assert call_count == 3
            # Should have slept twice (between retries)
            assert mock_sleep.call_count == 2
            # Should have recorded retry metrics
            assert mock_retry_metric.call_count == 2

    @pytest.mark.asyncio
    async def test_classify_vehicle_retries_on_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_vehicle retries on TimeoutException."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vehicle_type": "truck",
            "display_name": "Truck",
            "confidence": 0.88,
            "is_commercial": True,
            "all_scores": {"truck": 0.88},
            "inference_time_ms": 45.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Request timed out")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_vehicle(sample_image)

            assert result is not None
            assert call_count == 2
            assert mock_sleep.call_count == 1

    @pytest.mark.asyncio
    async def test_classify_vehicle_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_vehicle raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError) as exc_info:
                await client.classify_vehicle(sample_image)

            # Should have tried 3 times (max_retries)
            assert mock_http_client.post.call_count == 3
            # Should have slept twice (between retries)
            assert mock_sleep.call_count == 2
            # Should record pipeline error after exhausting retries
            mock_record.assert_called_with("enrichment_vehicle_connection_error")
            # Error message should mention retry exhaustion
            assert (
                "after 3 retries" in str(exc_info.value).lower()
                or "connection" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_classify_vehicle_no_retry_on_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_vehicle does not retry on 4xx errors."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad request", request=mock_request, response=mock_response
            )
        )
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("backend.services.enrichment_client.record_pipeline_error"),
        ):
            result = await client.classify_vehicle(sample_image)

            # Should return None for client errors (no retry)
            assert result is None
            # Should only try once - no retries for client errors
            assert mock_http_client.post.call_count == 1
            # Should not sleep
            assert mock_sleep.call_count == 0


# =============================================================================
# Retry Behavior Tests - Pet Classification
# =============================================================================


class TestEnrichmentClientRetryPet:
    """Tests for retry behavior in classify_pet method."""

    @pytest.mark.asyncio
    async def test_classify_pet_retries_on_connect_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_pet retries on ConnectError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pet_type": "dog",
            "breed": "labrador",
            "confidence": 0.95,
            "is_household_pet": True,
            "inference_time_ms": 35.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_pet(sample_image)

            assert result is not None
            assert result.pet_type == "dog"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_classify_pet_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_pet raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_pet(sample_image)

            assert mock_http_client.post.call_count == 3


# =============================================================================
# Retry Behavior Tests - Clothing Classification
# =============================================================================


class TestEnrichmentClientRetryClothing:
    """Tests for retry behavior in classify_clothing method."""

    @pytest.mark.asyncio
    async def test_classify_clothing_retries_on_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_clothing retries on TimeoutException."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "clothing_type": "jacket",
            "color": "blue",
            "style": "casual",
            "confidence": 0.88,
            "top_category": "outerwear",
            "description": "Blue casual jacket",
            "is_suspicious": False,
            "is_service_uniform": False,
            "inference_time_ms": 55.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_clothing(sample_image)

            assert result is not None
            assert result.clothing_type == "jacket"
            assert call_count == 3


# =============================================================================
# Exponential Backoff Tests
# =============================================================================


class TestEnrichmentClientExponentialBackoff:
    """Tests for exponential backoff delay calculation."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that delays follow exponential backoff pattern with jitter."""
        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", side_effect=capture_sleep),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            # Should have 2 sleep calls (between 3 retries)
            assert len(sleep_calls) == 2

            # First delay: 2^0 = 1s (with jitter, should be ~0.9 to ~1.1)
            assert 0.8 <= sleep_calls[0] <= 1.2

            # Second delay: 2^1 = 2s (with jitter, should be ~1.8 to ~2.2)
            assert 1.6 <= sleep_calls[1] <= 2.4

    @pytest.mark.asyncio
    async def test_backoff_capped_at_30_seconds(self, mock_settings: MagicMock) -> None:
        """Test that backoff delay is capped at 30 seconds."""
        # Create client with many retries to test cap
        mock_settings.enrichment_max_retries = 10
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()

        sample_image = Image.new("RGB", (100, 100), color="red")
        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", side_effect=capture_sleep),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            # All delays should be capped at ~30s (with jitter variance)
            for delay in sleep_calls:
                # Allow for jitter variance
                assert delay <= 33.0  # 30s + 10% jitter


# =============================================================================
# Retry Metrics Tests
# =============================================================================


class TestEnrichmentClientRetryMetrics:
    """Tests for retry metrics recording."""

    @pytest.mark.asyncio
    async def test_retry_metric_incremented_on_retry(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that retry metric is incremented on each retry."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.92,
            "is_commercial": False,
            "all_scores": {"sedan": 0.92},
            "inference_time_ms": 42.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch(
                "backend.services.enrichment_client.increment_enrichment_retry"
            ) as mock_retry_metric,
        ):
            await client.classify_vehicle(sample_image)

            # Should have called retry metric twice (for 2 retries)
            assert mock_retry_metric.call_count == 2
            # Check it was called with endpoint name
            mock_retry_metric.assert_called_with("vehicle")

    @pytest.mark.asyncio
    async def test_retry_metric_records_endpoint_type(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that retry metric records the correct endpoint type."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pet_type": "cat",
            "breed": "tabby",
            "confidence": 0.95,
            "is_household_pet": True,
            "inference_time_ms": 35.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch(
                "backend.services.enrichment_client.increment_enrichment_retry"
            ) as mock_retry_metric,
        ):
            await client.classify_pet(sample_image)

            # Should have called retry metric with "pet" endpoint
            mock_retry_metric.assert_called_with("pet")


# =============================================================================
# Server Error Retry Tests
# =============================================================================


class TestEnrichmentClientRetryServerErrors:
    """Tests for retry behavior on HTTP 5xx server errors."""

    @pytest.mark.asyncio
    async def test_retries_on_http_500(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that 5xx errors trigger retry."""
        mock_request = MagicMock()
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.92,
            "is_commercial": False,
            "all_scores": {"sedan": 0.92},
            "inference_time_ms": 42.0,
        }
        mock_response_success.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPStatusError(
                    "Internal server error",
                    request=mock_request,
                    response=mock_response_error,
                )
            return mock_response_success

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_vehicle(sample_image)

            assert result is not None
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_http_503(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that 503 Service Unavailable triggers retry."""
        mock_request = MagicMock()
        mock_response_error = MagicMock()
        mock_response_error.status_code = 503

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "clothing_type": "jacket",
            "color": "blue",
            "style": "casual",
            "confidence": 0.88,
            "top_category": "outerwear",
            "description": "Blue casual jacket",
            "is_suspicious": False,
            "is_service_uniform": False,
            "inference_time_ms": 55.0,
        }
        mock_response_success.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.HTTPStatusError(
                    "Service unavailable",
                    request=mock_request,
                    response=mock_response_error,
                )
            return mock_response_success

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_clothing(sample_image)

            assert result is not None
            assert call_count == 2


# =============================================================================
# Retry Behavior Tests - Depth Estimation
# =============================================================================


class TestEnrichmentClientRetryDepth:
    """Tests for retry behavior in estimate_depth method."""

    @pytest.mark.asyncio
    async def test_estimate_depth_retries_on_connect_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that estimate_depth retries on ConnectError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "depth_map_base64": "base64_depth_data",
            "min_depth": 0.1,
            "max_depth": 0.9,
            "mean_depth": 0.5,
            "inference_time_ms": 50.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.estimate_depth(sample_image)

            assert result is not None
            assert result.min_depth == 0.1
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_estimate_depth_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that estimate_depth raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.estimate_depth(sample_image)

            assert mock_http_client.post.call_count == 3


# =============================================================================
# Retry Behavior Tests - Object Distance Estimation
# =============================================================================


class TestEnrichmentClientRetryDistance:
    """Tests for retry behavior in estimate_object_distance method."""

    @pytest.mark.asyncio
    async def test_estimate_distance_retries_on_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that estimate_object_distance retries on TimeoutException."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 3.5,
            "relative_depth": 0.4,
            "proximity_label": "medium",
            "inference_time_ms": 30.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        # Use valid bbox within image bounds
        bbox = (10.0, 10.0, 50.0, 50.0)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.estimate_object_distance(sample_image, bbox)

            assert result is not None
            assert result.estimated_distance_m == 3.5
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_estimate_distance_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that estimate_object_distance raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http_client = mock_http_client

        # Use valid bbox within image bounds
        bbox = (10.0, 10.0, 50.0, 50.0)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.estimate_object_distance(sample_image, bbox)

            assert mock_http_client.post.call_count == 3


# =============================================================================
# Retry Behavior Tests - Pose Analysis
# =============================================================================


class TestEnrichmentClientRetryPose:
    """Tests for retry behavior in analyze_pose method."""

    @pytest.mark.asyncio
    async def test_analyze_pose_retries_on_connect_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that analyze_pose retries on ConnectError."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keypoints": [
                {"name": "nose", "x": 0.5, "y": 0.3, "confidence": 0.9},
                {"name": "left_shoulder", "x": 0.4, "y": 0.5, "confidence": 0.85},
            ],
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 40.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.ConnectError("Connection refused")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.analyze_pose(sample_image)

            assert result is not None
            assert result.posture == "standing"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_pose_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that analyze_pose raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        client._http_client = mock_http_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.analyze_pose(sample_image)

            assert mock_http_client.post.call_count == 3


# =============================================================================
# Retry Behavior Tests - Action Classification
# =============================================================================


class TestEnrichmentClientRetryAction:
    """Tests for retry behavior in classify_action method."""

    @pytest.mark.asyncio
    async def test_classify_action_retries_on_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_action retries on TimeoutException."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "walking",
            "confidence": 0.85,
            "is_suspicious": False,
            "risk_weight": 0.2,
            "all_scores": {"walking": 0.85, "running": 0.1},
            "inference_time_ms": 100.0,
        }
        mock_response.raise_for_status = MagicMock()

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            return mock_response

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = mock_post
        client._http_client = mock_http_client

        # Create list of frames
        frames = [sample_image] * 8

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.observe_ai_request_duration"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            result = await client.classify_action(frames)

            assert result is not None
            assert result.action == "walking"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_classify_action_exhausts_retries_raises_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_action raises error after exhausting retries."""
        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http_client = mock_http_client

        # Create list of frames
        frames = [sample_image] * 8

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.services.enrichment_client.record_pipeline_error"),
            patch("backend.services.enrichment_client.increment_enrichment_retry"),
        ):
            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_action(frames)

            assert mock_http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_classify_action_no_retry_on_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that classify_action does not retry on 4xx errors."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        # Mock the client's _http_client directly
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad request", request=mock_request, response=mock_response
            )
        )
        client._http_client = mock_http_client

        # Create list of frames
        frames = [sample_image] * 8

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("backend.services.enrichment_client.record_pipeline_error"),
        ):
            result = await client.classify_action(frames)

            # Should return None for client errors (no retry)
            assert result is None
            # Should only try once - no retries for client errors
            assert mock_http_client.post.call_count == 1
            # Should not sleep
            assert mock_sleep.call_count == 0
