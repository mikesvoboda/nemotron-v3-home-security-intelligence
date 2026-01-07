"""Unit tests for enrichment client circuit breaker integration.

Tests cover:
- Circuit breaker initialization with configuration
- Circuit opens after consecutive failures
- Requests are rejected when circuit is open
- Circuit transitions to half-open after recovery timeout
- Circuit closes after successful request in half-open state
- Graceful degradation when circuit is open
- Circuit breaker state is reflected in health check
- get_circuit_breaker_state() method
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.core.circuit_breaker import CircuitState
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
    """Create mock settings for testing with circuit breaker config."""
    settings = MagicMock()
    settings.enrichment_url = "http://test-enrichment:8094"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
    # Circuit breaker settings
    settings.enrichment_cb_failure_threshold = 3
    settings.enrichment_cb_recovery_timeout = 30.0
    settings.enrichment_cb_half_open_max_calls = 2
    # Retry settings (NEM-1732)
    settings.enrichment_max_retries = 3
    return settings


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def client(mock_settings: MagicMock) -> EnrichmentClient:
    """Create an EnrichmentClient with mocked settings and persistent HTTP clients."""
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    mock_health_client = AsyncMock()
    mock_health_client.aclose = AsyncMock()

    with (
        patch("backend.services.enrichment_client.get_settings", return_value=mock_settings),
        patch("httpx.AsyncClient", side_effect=[mock_http_client, mock_health_client]),
    ):
        client = EnrichmentClient()
        # Ensure the mocked clients are properly attached
        client._http_client = mock_http_client
        client._health_http_client = mock_health_client
        return client


# =============================================================================
# Circuit Breaker Initialization Tests
# =============================================================================


class TestCircuitBreakerInitialization:
    """Tests for circuit breaker initialization."""

    def test_circuit_breaker_initialized_on_client_creation(self, mock_settings: MagicMock) -> None:
        """Test that circuit breaker is initialized when client is created."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert hasattr(client, "_circuit_breaker")
            assert client._circuit_breaker is not None

    def test_circuit_breaker_uses_config_values(self, mock_settings: MagicMock) -> None:
        """Test that circuit breaker uses configuration values."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            cb = client._circuit_breaker
            assert cb._failure_threshold == 3
            assert cb._recovery_timeout == 30.0
            assert cb._half_open_max_calls == 2

    def test_circuit_breaker_initial_state_is_closed(self, mock_settings: MagicMock) -> None:
        """Test that circuit breaker starts in CLOSED state."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert client._circuit_breaker.get_state() == CircuitState.CLOSED

    def test_circuit_breaker_name_is_enrichment(self, mock_settings: MagicMock) -> None:
        """Test that circuit breaker has correct service name."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert client._circuit_breaker._name == "enrichment"


# =============================================================================
# Circuit Breaker State Transition Tests
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Tests for circuit breaker state transitions during API calls."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_consecutive_failures(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that circuit opens after failure threshold is reached."""
        # Simulate connection failures on persistent HTTP client
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        # Mock asyncio.sleep to prevent actual delays during retries (NEM-1732)
        with patch("asyncio.sleep", new=AsyncMock()):
            # Make 3 failing calls (threshold is 3)
            for _ in range(3):
                with pytest.raises(EnrichmentUnavailableError):
                    await client.classify_vehicle(sample_image)

        # Circuit should now be OPEN
        assert client._circuit_breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_requests_rejected_when_circuit_is_open(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that requests are rejected when circuit is open."""
        # Force circuit to open
        for _ in range(3):
            client._circuit_breaker.record_failure()

        assert client._circuit_breaker.get_state() == CircuitState.OPEN

        # Attempt to make a request - should be rejected without making HTTP call
        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.classify_vehicle(sample_image)

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open_after_recovery(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        # Force circuit to open
        for _ in range(3):
            client._circuit_breaker.record_failure()

        assert client._circuit_breaker.get_state() == CircuitState.OPEN

        # Mock time to simulate recovery timeout
        original_monotonic = time.monotonic
        mock_time = original_monotonic() + 35.0  # Beyond recovery timeout (30s)

        with patch("time.monotonic", return_value=mock_time):
            # allow_request should transition to HALF_OPEN
            assert client._circuit_breaker.allow_request() is True
            assert client._circuit_breaker.get_state() == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_on_success_in_half_open(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that circuit closes on successful requests in HALF_OPEN state."""
        # Force circuit to open
        for _ in range(3):
            client._circuit_breaker.record_failure()

        # Mock time to trigger HALF_OPEN
        original_time = time.monotonic()

        with patch("time.monotonic", return_value=original_time + 35.0):
            # Transition to HALF_OPEN
            client._circuit_breaker.allow_request()
            assert client._circuit_breaker.get_state() == CircuitState.HALF_OPEN

            # Record successes - default success_threshold is 2
            client._circuit_breaker.record_success()
            client._circuit_breaker.record_success()

            # Circuit should now be CLOSED
            assert client._circuit_breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_request_resets_failure_count(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that successful request resets failure count."""
        # Add some failures but don't reach threshold
        client._circuit_breaker.record_failure()
        client._circuit_breaker.record_failure()
        assert client._circuit_breaker._failure_count == 2

        # Successful request should reset
        client._circuit_breaker.record_success()
        assert client._circuit_breaker._failure_count == 0


# =============================================================================
# Integration Tests - API Methods with Circuit Breaker
# =============================================================================


class TestEnrichmentClientMethodsWithCircuitBreaker:
    """Tests for enrichment client methods with circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_classify_vehicle_records_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that successful vehicle classification records success."""
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

        # Mock the persistent HTTP client's post method
        client._http_client.post = AsyncMock(return_value=mock_response)

        # Add a failure first
        client._circuit_breaker.record_failure()
        assert client._circuit_breaker._failure_count == 1

        # Successful call should reset failure count
        result = await client.classify_vehicle(sample_image)

        assert result is not None
        assert client._circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_classify_pet_records_failure(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that failed pet classification records failure."""
        # Mock the persistent HTTP client's post method to raise error
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_pet(sample_image)

        assert client._circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_classify_clothing_respects_circuit_breaker(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that clothing classification respects circuit breaker state."""
        # Open the circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        # Request should be rejected without making HTTP call
        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.classify_clothing(sample_image)

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_estimate_depth_respects_circuit_breaker(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that depth estimation respects circuit breaker state."""
        # Open the circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.estimate_depth(sample_image)

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_estimate_object_distance_respects_circuit_breaker(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that object distance estimation respects circuit breaker state."""
        # Open the circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_analyze_pose_respects_circuit_breaker(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that pose analysis respects circuit breaker state."""
        # Open the circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.analyze_pose(sample_image)

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_classify_action_respects_circuit_breaker(self, client: EnrichmentClient) -> None:
        """Test that action classification respects circuit breaker state."""
        frames = [Image.new("RGB", (100, 100), color="blue") for _ in range(8)]

        # Open the circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.classify_action(frames)

        assert "circuit open" in str(exc_info.value).lower()


# =============================================================================
# Circuit Breaker State API Tests
# =============================================================================


class TestCircuitBreakerStateAPI:
    """Tests for circuit breaker state access methods."""

    def test_get_circuit_breaker_state(self, client: EnrichmentClient) -> None:
        """Test get_circuit_breaker_state method."""
        assert client.get_circuit_breaker_state() == CircuitState.CLOSED

        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        assert client.get_circuit_breaker_state() == CircuitState.OPEN

    def test_is_circuit_open(self, client: EnrichmentClient) -> None:
        """Test is_circuit_open method."""
        assert client.is_circuit_open() is False

        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        assert client.is_circuit_open() is True

    def test_reset_circuit_breaker(self, client: EnrichmentClient) -> None:
        """Test reset_circuit_breaker method."""
        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()
        assert client.get_circuit_breaker_state() == CircuitState.OPEN

        # Reset
        client.reset_circuit_breaker()

        assert client.get_circuit_breaker_state() == CircuitState.CLOSED
        assert client._circuit_breaker._failure_count == 0


# =============================================================================
# Health Check Integration Tests
# =============================================================================


class TestCircuitBreakerHealthCheck:
    """Tests for circuit breaker state in health checks."""

    @pytest.mark.asyncio
    async def test_health_check_includes_circuit_breaker_state(
        self, client: EnrichmentClient
    ) -> None:
        """Test that health check includes circuit breaker state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy", "models": ["vehicle", "pet"]}
        mock_response.raise_for_status = MagicMock()

        # Mock the health HTTP client's get method
        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()

        assert "circuit_breaker_state" in result
        assert result["circuit_breaker_state"] == "closed"

    @pytest.mark.asyncio
    async def test_health_check_shows_open_circuit(self, client: EnrichmentClient) -> None:
        """Test that health check shows circuit open state."""
        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy", "models": []}
        mock_response.raise_for_status = MagicMock()

        # Mock the health HTTP client's get method
        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()

        assert result["circuit_breaker_state"] == "open"

    @pytest.mark.asyncio
    async def test_is_healthy_false_when_circuit_open(self, client: EnrichmentClient) -> None:
        """Test that is_healthy returns False when circuit is open."""
        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        # Even if service health check would pass, circuit being open = unhealthy
        assert await client.is_healthy() is False


# =============================================================================
# Graceful Degradation Tests
# =============================================================================


class TestGracefulDegradation:
    """Tests for graceful degradation when circuit is open."""

    @pytest.mark.asyncio
    async def test_no_http_call_when_circuit_open(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that no HTTP call is made when circuit is open."""
        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        # Setup mock on persistent HTTP client
        client._http_client.post = AsyncMock()

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_vehicle(sample_image)

        # Verify no HTTP call was made
        client._http_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_metrics_recorded_when_circuit_open(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that metrics are recorded when requests are rejected by circuit."""
        # Open circuit
        for _ in range(3):
            client._circuit_breaker.record_failure()

        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_circuit_open")
