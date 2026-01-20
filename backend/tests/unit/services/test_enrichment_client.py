"""Unit tests for enrichment client service.

Tests cover:
- EnrichmentUnavailableError exception
- Result dataclass initialization and methods (to_dict, to_context_string)
- EnrichmentClient initialization
- Health check methods (check_health, is_healthy)
- Classification methods (vehicle, pet, clothing)
- Estimation methods (depth, object_distance)
- Analysis methods (pose, action)
- Error handling (connection errors, timeouts, HTTP errors)
- Global client management (get_enrichment_client, reset_enrichment_client)
"""

from __future__ import annotations

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
    DEFAULT_ENRICHMENT_URL,
    ActionClassificationResult,
    ClothingClassificationResult,
    DepthEstimationResult,
    EnrichmentClient,
    EnrichmentUnavailableError,
    KeypointData,
    ObjectDistanceResult,
    PetClassificationResult,
    PoseAnalysisResult,
    UnifiedClothingResult,
    UnifiedDemographicsResult,
    UnifiedEnrichmentResult,
    UnifiedPoseResult,
    UnifiedThreatResult,
    UnifiedVehicleResult,
    VehicleClassificationResult,
    get_enrichment_client,
    reset_enrichment_client,
)
from backend.tests.async_utils import (
    AsyncClientMock,
    create_mock_response,
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
    # Retry configuration (NEM-1732)
    settings.enrichment_max_retries = 3
    return settings


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def sample_frames() -> list[Image.Image]:
    """Create sample video frames for action classification."""
    return [Image.new("RGB", (100, 100), color=f"#{i:02x}0000") for i in range(8)]


@pytest.fixture
def client(mock_settings: MagicMock) -> EnrichmentClient:
    """Create an EnrichmentClient with mocked HTTP clients for testing.

    The EnrichmentClient uses persistent HTTP clients (NEM-1721), so we mock
    httpx.AsyncClient during construction to inject testable mock clients.
    """
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    mock_health_client = AsyncMock()
    mock_health_client.aclose = AsyncMock()

    with (
        patch("backend.services.enrichment_client.get_settings", return_value=mock_settings),
        patch("httpx.AsyncClient", side_effect=[mock_http_client, mock_health_client]),
    ):
        client = EnrichmentClient()
        # Store mocks for test access
        client._http_client = mock_http_client
        client._health_http_client = mock_health_client
        return client


@pytest.fixture
def client_custom_url() -> EnrichmentClient:
    """Create an EnrichmentClient with custom URL."""
    with patch("backend.services.enrichment_client.get_settings") as mock_settings_fn:
        mock_settings = MagicMock()
        mock_settings.ai_connect_timeout = 10.0
        mock_settings.ai_health_timeout = 5.0
        # Circuit breaker configuration
        mock_settings.enrichment_cb_failure_threshold = 5
        mock_settings.enrichment_cb_recovery_timeout = 60.0
        mock_settings.enrichment_cb_half_open_max_calls = 3
        mock_settings_fn.return_value = mock_settings
        return EnrichmentClient(base_url="http://custom-enrichment:8888/")


# =============================================================================
# EnrichmentUnavailableError Tests
# =============================================================================


class TestEnrichmentUnavailableError:
    """Tests for EnrichmentUnavailableError exception."""

    def test_init_with_message_only(self) -> None:
        """Test initialization with message only."""
        error = EnrichmentUnavailableError("Service down")
        assert str(error) == "Service down"
        assert error.original_error is None

    def test_init_with_original_error(self) -> None:
        """Test initialization with original error."""
        original = ConnectionError("Connection refused")
        error = EnrichmentUnavailableError("Service unavailable", original_error=original)
        assert str(error) == "Service unavailable"
        assert error.original_error is original

    def test_is_exception(self) -> None:
        """Test that EnrichmentUnavailableError is an Exception."""
        error = EnrichmentUnavailableError("Test")
        assert isinstance(error, Exception)

    def test_raise_and_catch(self) -> None:
        """Test raising and catching the exception."""
        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            raise EnrichmentUnavailableError(
                "Service down", original_error=ConnectionError("Network error")
            )
        assert "Service down" in str(exc_info.value)
        assert isinstance(exc_info.value.original_error, ConnectionError)


# =============================================================================
# VehicleClassificationResult Tests
# =============================================================================


class TestVehicleClassificationResult:
    """Tests for VehicleClassificationResult dataclass."""

    @pytest.fixture
    def vehicle_result(self) -> VehicleClassificationResult:
        """Create a sample vehicle classification result."""
        return VehicleClassificationResult(
            vehicle_type="pickup_truck",
            display_name="Pickup Truck",
            confidence=0.95,
            is_commercial=False,
            all_scores={"pickup_truck": 0.95, "sedan": 0.03, "suv": 0.02},
            inference_time_ms=45.5,
        )

    def test_to_dict(self, vehicle_result: VehicleClassificationResult) -> None:
        """Test to_dict serialization."""
        result = vehicle_result.to_dict()
        assert result["vehicle_type"] == "pickup_truck"
        assert result["display_name"] == "Pickup Truck"
        assert result["confidence"] == 0.95
        assert result["is_commercial"] is False
        assert "pickup_truck" in result["all_scores"]
        assert result["inference_time_ms"] == 45.5

    def test_to_context_string_non_commercial(
        self, vehicle_result: VehicleClassificationResult
    ) -> None:
        """Test context string for non-commercial vehicle."""
        context = vehicle_result.to_context_string()
        assert "Pickup Truck" in context
        assert "95%" in context
        assert "Commercial" not in context

    def test_to_context_string_commercial(self) -> None:
        """Test context string for commercial vehicle."""
        result = VehicleClassificationResult(
            vehicle_type="delivery_van",
            display_name="Delivery Van",
            confidence=0.88,
            is_commercial=True,
            all_scores={"delivery_van": 0.88},
            inference_time_ms=42.0,
        )
        context = result.to_context_string()
        assert "Delivery Van" in context
        assert "88%" in context
        assert "Commercial/delivery vehicle" in context


# =============================================================================
# PetClassificationResult Tests
# =============================================================================


class TestPetClassificationResult:
    """Tests for PetClassificationResult dataclass."""

    @pytest.fixture
    def pet_result(self) -> PetClassificationResult:
        """Create a sample pet classification result."""
        return PetClassificationResult(
            pet_type="dog",
            breed="labrador",
            confidence=0.92,
            is_household_pet=True,
            inference_time_ms=35.0,
        )

    def test_to_dict(self, pet_result: PetClassificationResult) -> None:
        """Test to_dict serialization."""
        result = pet_result.to_dict()
        assert result["pet_type"] == "dog"
        assert result["breed"] == "labrador"
        assert result["confidence"] == 0.92
        assert result["is_household_pet"] is True
        assert result["inference_time_ms"] == 35.0

    def test_to_context_string(self, pet_result: PetClassificationResult) -> None:
        """Test context string generation."""
        context = pet_result.to_context_string()
        assert "dog" in context
        assert "92%" in context
        assert "Household pet" in context


# =============================================================================
# ClothingClassificationResult Tests
# =============================================================================


class TestClothingClassificationResult:
    """Tests for ClothingClassificationResult dataclass."""

    @pytest.fixture
    def clothing_result(self) -> ClothingClassificationResult:
        """Create a sample clothing classification result."""
        return ClothingClassificationResult(
            clothing_type="hoodie",
            color="black",
            style="casual",
            confidence=0.85,
            top_category="outerwear",
            description="Black casual hoodie",
            is_suspicious=False,
            is_service_uniform=False,
            inference_time_ms=50.0,
        )

    def test_to_dict(self, clothing_result: ClothingClassificationResult) -> None:
        """Test to_dict serialization."""
        result = clothing_result.to_dict()
        assert result["clothing_type"] == "hoodie"
        assert result["color"] == "black"
        assert result["style"] == "casual"
        assert result["confidence"] == 0.85
        assert result["top_category"] == "outerwear"
        assert result["description"] == "Black casual hoodie"
        assert result["is_suspicious"] is False
        assert result["is_service_uniform"] is False
        assert result["inference_time_ms"] == 50.0

    def test_to_context_string_normal(self, clothing_result: ClothingClassificationResult) -> None:
        """Test context string for normal clothing."""
        context = clothing_result.to_context_string()
        assert "Black casual hoodie" in context
        assert "85.0%" in context
        assert "ALERT" not in context

    def test_to_context_string_suspicious(self) -> None:
        """Test context string for suspicious clothing."""
        result = ClothingClassificationResult(
            clothing_type="balaclava",
            color="black",
            style="concealing",
            confidence=0.90,
            top_category="face_covering",
            description="Black balaclava face covering",
            is_suspicious=True,
            is_service_uniform=False,
            inference_time_ms=48.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "suspicious" in context.lower()

    def test_to_context_string_service_uniform(self) -> None:
        """Test context string for service uniform."""
        result = ClothingClassificationResult(
            clothing_type="uniform",
            color="brown",
            style="work",
            confidence=0.88,
            top_category="uniform",
            description="Brown delivery uniform",
            is_suspicious=False,
            is_service_uniform=True,
            inference_time_ms=45.0,
        )
        context = result.to_context_string()
        assert "Service/delivery worker" in context


# =============================================================================
# DepthEstimationResult Tests
# =============================================================================


class TestDepthEstimationResult:
    """Tests for DepthEstimationResult dataclass."""

    @pytest.fixture
    def depth_result(self) -> DepthEstimationResult:
        """Create a sample depth estimation result."""
        return DepthEstimationResult(
            depth_map_base64="dGVzdGltYWdl",
            min_depth=0.1,
            max_depth=0.9,
            mean_depth=0.45,
            inference_time_ms=60.0,
        )

    def test_to_dict(self, depth_result: DepthEstimationResult) -> None:
        """Test to_dict serialization."""
        result = depth_result.to_dict()
        assert result["depth_map_base64"] == "dGVzdGltYWdl"
        assert result["min_depth"] == 0.1
        assert result["max_depth"] == 0.9
        assert result["mean_depth"] == 0.45
        assert result["inference_time_ms"] == 60.0

    def test_to_context_string(self, depth_result: DepthEstimationResult) -> None:
        """Test context string generation."""
        context = depth_result.to_context_string()
        assert "avg=0.45" in context
        assert "min=0.10" in context
        assert "max=0.90" in context


# =============================================================================
# ObjectDistanceResult Tests
# =============================================================================


class TestObjectDistanceResult:
    """Tests for ObjectDistanceResult dataclass."""

    @pytest.fixture
    def distance_result(self) -> ObjectDistanceResult:
        """Create a sample object distance result."""
        return ObjectDistanceResult(
            estimated_distance_m=2.5,
            relative_depth=0.3,
            proximity_label="close",
            inference_time_ms=55.0,
        )

    def test_to_dict(self, distance_result: ObjectDistanceResult) -> None:
        """Test to_dict serialization."""
        result = distance_result.to_dict()
        assert result["estimated_distance_m"] == 2.5
        assert result["relative_depth"] == 0.3
        assert result["proximity_label"] == "close"
        assert result["inference_time_ms"] == 55.0

    def test_to_context_string(self, distance_result: ObjectDistanceResult) -> None:
        """Test context string generation."""
        context = distance_result.to_context_string()
        assert "2.5m" in context
        assert "close" in context

    def test_is_close_true_very_close(self) -> None:
        """Test is_close returns True for very close objects."""
        result = ObjectDistanceResult(
            estimated_distance_m=0.5,
            relative_depth=0.1,
            proximity_label="very close",
            inference_time_ms=50.0,
        )
        assert result.is_close() is True

    def test_is_close_true_close(self, distance_result: ObjectDistanceResult) -> None:
        """Test is_close returns True for close objects."""
        assert distance_result.is_close() is True

    def test_is_close_false_far(self) -> None:
        """Test is_close returns False for far objects."""
        result = ObjectDistanceResult(
            estimated_distance_m=15.0,
            relative_depth=0.8,
            proximity_label="far",
            inference_time_ms=50.0,
        )
        assert result.is_close() is False


# =============================================================================
# KeypointData Tests
# =============================================================================


class TestKeypointData:
    """Tests for KeypointData dataclass."""

    def test_to_dict(self) -> None:
        """Test to_dict serialization."""
        keypoint = KeypointData(
            name="nose",
            x=0.5,
            y=0.3,
            confidence=0.95,
        )
        result = keypoint.to_dict()
        assert result["name"] == "nose"
        assert result["x"] == 0.5
        assert result["y"] == 0.3
        assert result["confidence"] == 0.95


# =============================================================================
# ActionClassificationResult Tests
# =============================================================================


class TestActionClassificationResult:
    """Tests for ActionClassificationResult dataclass."""

    @pytest.fixture
    def action_result(self) -> ActionClassificationResult:
        """Create a sample action classification result."""
        return ActionClassificationResult(
            action="a person walking",
            confidence=0.85,
            is_suspicious=False,
            risk_weight=0.2,
            all_scores={"a person walking": 0.85, "a person running": 0.10},
            inference_time_ms=120.0,
        )

    def test_to_dict(self, action_result: ActionClassificationResult) -> None:
        """Test to_dict serialization."""
        result = action_result.to_dict()
        assert result["action"] == "a person walking"
        assert result["confidence"] == 0.85
        assert result["is_suspicious"] is False
        assert result["risk_weight"] == 0.2
        assert "a person walking" in result["all_scores"]
        assert result["inference_time_ms"] == 120.0

    def test_to_context_string_normal(self, action_result: ActionClassificationResult) -> None:
        """Test context string for normal action."""
        context = action_result.to_context_string()
        assert "a person walking" in context
        assert "Risk weight: 20%" in context
        assert "85.0%" in context
        assert "ALERT" not in context

    def test_to_context_string_suspicious(self) -> None:
        """Test context string for suspicious action."""
        result = ActionClassificationResult(
            action="a person loitering",
            confidence=0.75,
            is_suspicious=True,
            risk_weight=0.8,
            all_scores={"a person loitering": 0.75},
            inference_time_ms=115.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "Suspicious behavior" in context
        assert "80%" in context

    def test_has_security_alerts_suspicious(self) -> None:
        """Test has_security_alerts for suspicious action."""
        result = ActionClassificationResult(
            action="loitering",
            confidence=0.80,
            is_suspicious=True,
            risk_weight=0.5,
            all_scores={},
            inference_time_ms=100.0,
        )
        assert result.has_security_alerts() is True

    def test_has_security_alerts_high_risk(self) -> None:
        """Test has_security_alerts for high risk weight."""
        result = ActionClassificationResult(
            action="running",
            confidence=0.90,
            is_suspicious=False,
            risk_weight=0.75,
            all_scores={},
            inference_time_ms=100.0,
        )
        assert result.has_security_alerts() is True

    def test_has_security_alerts_normal(self, action_result: ActionClassificationResult) -> None:
        """Test has_security_alerts for normal action."""
        assert action_result.has_security_alerts() is False


# =============================================================================
# PoseAnalysisResult Tests
# =============================================================================


class TestPoseAnalysisResult:
    """Tests for PoseAnalysisResult dataclass."""

    @pytest.fixture
    def pose_result(self) -> PoseAnalysisResult:
        """Create a sample pose analysis result."""
        keypoints = [
            KeypointData(name="nose", x=0.5, y=0.2, confidence=0.95),
            KeypointData(name="left_shoulder", x=0.4, y=0.4, confidence=0.90),
            KeypointData(name="right_shoulder", x=0.6, y=0.4, confidence=0.88),
        ]
        return PoseAnalysisResult(
            keypoints=keypoints,
            posture="standing",
            alerts=[],
            inference_time_ms=80.0,
        )

    def test_to_dict(self, pose_result: PoseAnalysisResult) -> None:
        """Test to_dict serialization."""
        result = pose_result.to_dict()
        assert len(result["keypoints"]) == 3
        assert result["keypoints"][0]["name"] == "nose"
        assert result["posture"] == "standing"
        assert result["alerts"] == []
        assert result["inference_time_ms"] == 80.0

    def test_to_context_string_no_alerts(self, pose_result: PoseAnalysisResult) -> None:
        """Test context string with no alerts."""
        context = pose_result.to_context_string()
        assert "standing" in context
        assert "3/17" in context
        assert "ALERT" not in context

    def test_to_context_string_crouching_alert(self) -> None:
        """Test context string with crouching alert."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="crouching",
            alerts=["crouching"],
            inference_time_ms=75.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "crouching" in context
        assert "hiding/break-in" in context

    def test_to_context_string_lying_down_alert(self) -> None:
        """Test context string with lying down alert."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="lying_down",
            alerts=["lying_down"],
            inference_time_ms=70.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "lying down" in context
        assert "medical emergency" in context

    def test_to_context_string_hands_raised_alert(self) -> None:
        """Test context string with hands raised alert."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="standing",
            alerts=["hands_raised"],
            inference_time_ms=72.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "Hands raised" in context
        assert "surrender/robbery" in context

    def test_to_context_string_fighting_stance_alert(self) -> None:
        """Test context string with fighting stance alert."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="fighting",
            alerts=["fighting_stance"],
            inference_time_ms=68.0,
        )
        context = result.to_context_string()
        assert "ALERT" in context
        assert "Fighting stance" in context
        assert "aggression" in context

    def test_to_context_string_unknown_alert(self) -> None:
        """Test context string with unknown alert type."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="unknown",
            alerts=["custom_alert"],
            inference_time_ms=65.0,
        )
        context = result.to_context_string()
        assert "[ALERT: custom_alert]" in context

    def test_has_security_alerts_with_alerts(self) -> None:
        """Test has_security_alerts with alerts present."""
        result = PoseAnalysisResult(
            keypoints=[],
            posture="crouching",
            alerts=["crouching"],
            inference_time_ms=75.0,
        )
        assert result.has_security_alerts() is True

    def test_has_security_alerts_no_alerts(self, pose_result: PoseAnalysisResult) -> None:
        """Test has_security_alerts without alerts."""
        assert pose_result.has_security_alerts() is False


# =============================================================================
# EnrichmentClient Initialization Tests
# =============================================================================


class TestEnrichmentClientInit:
    """Tests for EnrichmentClient initialization."""

    def test_init_with_default_url(self, mock_settings: MagicMock) -> None:
        """Test initialization with default URL from settings."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert client._base_url == "http://test-enrichment:8094"

    def test_init_with_custom_url(self, mock_settings: MagicMock) -> None:
        """Test initialization with custom URL."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient(base_url="http://custom:9000/")
            assert client._base_url == "http://custom:9000"

    def test_init_strips_trailing_slash(self, mock_settings: MagicMock) -> None:
        """Test that trailing slashes are stripped from URLs."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient(base_url="http://custom:9000///")
            assert client._base_url == "http://custom:9000"

    def test_init_uses_default_url_when_not_in_settings(self) -> None:
        """Test using DEFAULT_ENRICHMENT_URL when not in settings."""
        mock_settings = MagicMock(spec=[])  # No enrichment_url attribute
        mock_settings.ai_connect_timeout = 10.0
        mock_settings.ai_health_timeout = 5.0
        # Circuit breaker configuration is required
        mock_settings.enrichment_cb_failure_threshold = 5
        mock_settings.enrichment_cb_recovery_timeout = 60.0
        mock_settings.enrichment_cb_half_open_max_calls = 3
        # Retry configuration (NEM-1732)
        mock_settings.enrichment_max_retries = 3
        # Read timeout configuration (NEM-2524)
        mock_settings.enrichment_read_timeout = 120.0
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert client._base_url == DEFAULT_ENRICHMENT_URL.rstrip("/")

    def test_timeout_configuration(self, mock_settings: MagicMock) -> None:
        """Test timeout configuration is set correctly."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = EnrichmentClient()
            assert client._timeout.connect == 10.0
            assert client._health_timeout.connect == 5.0


# =============================================================================
# EnrichmentClient Health Check Tests
# =============================================================================


class TestEnrichmentClientHealthCheck:
    """Tests for health check methods."""

    @pytest.mark.asyncio
    async def test_check_health_success(self, client: EnrichmentClient) -> None:
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy", "models": ["vehicle", "pet"]}
        mock_response.raise_for_status = MagicMock()

        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()
        assert result["status"] == "healthy"
        assert "models" in result

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self, client: EnrichmentClient) -> None:
        """Test health check with connection error."""
        client._health_http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        result = await client.check_health()
        assert result["status"] == "unavailable"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, client: EnrichmentClient) -> None:
        """Test health check with timeout error."""
        client._health_http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = await client.check_health()
        assert result["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_check_health_http_error(self, client: EnrichmentClient) -> None:
        """Test health check with HTTP error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        client._health_http_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=mock_request, response=mock_response
            )
        )

        result = await client.check_health()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_check_health_unexpected_error(self, client: EnrichmentClient) -> None:
        """Test health check with unexpected error."""
        client._health_http_client.get = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        result = await client.check_health()
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_is_healthy_true_healthy(self, client: EnrichmentClient) -> None:
        """Test is_healthy returns True when status is healthy."""
        with patch.object(client, "check_health", return_value={"status": "healthy"}):
            assert await client.is_healthy() is True

    @pytest.mark.asyncio
    async def test_is_healthy_true_degraded(self, client: EnrichmentClient) -> None:
        """Test is_healthy returns True when status is degraded."""
        with patch.object(client, "check_health", return_value={"status": "degraded"}):
            assert await client.is_healthy() is True

    @pytest.mark.asyncio
    async def test_is_healthy_false_unavailable(self, client: EnrichmentClient) -> None:
        """Test is_healthy returns False when status is unavailable."""
        with patch.object(client, "check_health", return_value={"status": "unavailable"}):
            assert await client.is_healthy() is False


# =============================================================================
# Tests Using Improved Async Patterns (async_utils module)
# =============================================================================


class TestEnrichmentClientHealthCheckImproved:
    """Health check tests using improved async patterns from async_utils.

    These tests demonstrate the cleaner patterns provided by the async_utils
    module. Compare with TestEnrichmentClientHealthCheck to see the difference.
    """

    @pytest.mark.asyncio
    async def test_check_health_success_using_async_client_mock(
        self, client: EnrichmentClient
    ) -> None:
        """Test successful health check using AsyncClientMock.

        This demonstrates the improved pattern using AsyncClientMock which
        eliminates the verbose __aenter__/__aexit__ setup.
        """
        # AsyncClientMock handles the context manager protocol automatically
        http_mock = AsyncClientMock(
            get_responses={"/health": {"status": "healthy", "models": ["vehicle", "pet"]}},
        )

        # The mock tracks all calls for verification
        async with http_mock.client() as mock_client:
            # Simulate what the EnrichmentClient does internally
            response = await mock_client.get("/health")
            result = response.json()

        assert result["status"] == "healthy"
        assert "models" in result
        # Verify the call was tracked
        assert len(http_mock.calls) == 1
        assert http_mock.calls[0][0] == "GET"

    @pytest.mark.asyncio
    async def test_check_health_error_using_async_client_mock(
        self, client: EnrichmentClient
    ) -> None:
        """Test health check error using AsyncClientMock with exception.

        This demonstrates configuring AsyncClientMock to raise exceptions,
        which is useful for testing error handling paths.
        """
        # Configure the mock to raise an exception for the health endpoint
        http_mock = AsyncClientMock(
            get_responses={"/health": httpx.ConnectError("Connection refused")},
        )

        async with http_mock.client() as mock_client:
            with pytest.raises(httpx.ConnectError):
                await mock_client.get("/health")

    @pytest.mark.asyncio
    async def test_classify_response_using_create_mock_response(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test using create_mock_response helper.

        This demonstrates the create_mock_response helper for creating
        properly configured HTTP response mocks.
        """
        # create_mock_response provides a cleaner way to create response mocks
        mock_response = create_mock_response(
            json_data={
                "vehicle_type": "sedan",
                "display_name": "Sedan",
                "confidence": 0.92,
                "is_commercial": False,
                "all_scores": {"sedan": 0.92},
                "inference_time_ms": 42.0,
            },
            status_code=200,
        )

        # Verify the mock response has the expected shape
        assert mock_response.json()["vehicle_type"] == "sedan"
        assert mock_response.status_code == 200

        # raise_for_status should not raise for 200 status
        mock_response.raise_for_status()  # Should not raise


# =============================================================================
# EnrichmentClient Image Encoding Tests
# =============================================================================


class TestEnrichmentClientImageEncoding:
    """Tests for image encoding functionality."""

    def test_encode_image_to_base64(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test image encoding to base64."""
        encoded = client._encode_image_to_base64(sample_image)
        assert isinstance(encoded, str)
        # Verify it's valid base64 that can be decoded
        decoded = base64.b64decode(encoded)
        # Verify it's a valid PNG
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_encode_image_produces_png(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that encoded image is PNG format."""
        encoded = client._encode_image_to_base64(sample_image)
        decoded = base64.b64decode(encoded)
        # Load it back as an image to verify
        buffer = io.BytesIO(decoded)
        loaded_image = Image.open(buffer)
        assert loaded_image.format == "PNG"


# =============================================================================
# EnrichmentClient Vehicle Classification Tests
# =============================================================================


class TestEnrichmentClientClassifyVehicle:
    """Tests for classify_vehicle method."""

    @pytest.mark.asyncio
    async def test_classify_vehicle_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful vehicle classification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.92,
            "is_commercial": False,
            "all_scores": {"sedan": 0.92, "suv": 0.05},
            "inference_time_ms": 42.0,
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "backend.services.enrichment_client.observe_ai_request_duration"
        ) as mock_observe:
            client._http_client.post = AsyncMock(return_value=mock_response)

            result = await client.classify_vehicle(sample_image)

        assert result is not None
        assert result.vehicle_type == "sedan"
        assert result.confidence == 0.92
        mock_observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_vehicle_with_bbox(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with bounding box."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "vehicle_type": "truck",
            "display_name": "Truck",
            "confidence": 0.88,
            "is_commercial": True,
            "all_scores": {"truck": 0.88},
            "inference_time_ms": 40.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_vehicle(sample_image, bbox=(10.0, 20.0, 80.0, 90.0))

        assert result is not None
        # Verify bbox was included in request
        call_args = client._http_client.post.call_args
        assert "bbox" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_classify_vehicle_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with connection error."""
        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            client._http_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_vehicle_connection_error")

    @pytest.mark.asyncio
    async def test_classify_vehicle_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with timeout."""
        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            client._http_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_vehicle_timeout")

    @pytest.mark.asyncio
    async def test_classify_vehicle_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with 5xx server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            client._http_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service unavailable", request=mock_request, response=mock_response
                )
            )

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_vehicle_server_error")

    @pytest.mark.asyncio
    async def test_classify_vehicle_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with 4xx client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            client._http_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=mock_request, response=mock_response
                )
            )

            result = await client.classify_vehicle(sample_image)
        assert result is None
        mock_record.assert_called_once_with("enrichment_vehicle_client_error")

    @pytest.mark.asyncio
    async def test_classify_vehicle_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with unexpected error."""
        with patch("backend.services.enrichment_client.record_pipeline_error") as mock_record:
            client._http_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_vehicle_unexpected_error")


# =============================================================================
# EnrichmentClient Pet Classification Tests
# =============================================================================


class TestEnrichmentClientClassifyPet:
    """Tests for classify_pet method."""

    @pytest.mark.asyncio
    async def test_classify_pet_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful pet classification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pet_type": "cat",
            "breed": "tabby",
            "confidence": 0.95,
            "is_household_pet": True,
            "inference_time_ms": 35.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_pet(sample_image)

        assert result is not None
        assert result.pet_type == "cat"
        assert result.breed == "tabby"

    @pytest.mark.asyncio
    async def test_classify_pet_with_bbox(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with bounding box."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pet_type": "dog",
            "breed": "golden_retriever",
            "confidence": 0.90,
            "is_household_pet": True,
            "inference_time_ms": 38.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_pet(sample_image, bbox=(5.0, 10.0, 95.0, 90.0))

        assert result is not None
        call_args = client._http_client.post.call_args
        assert "bbox" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_classify_pet_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_pet(sample_image)

    @pytest.mark.asyncio
    async def test_classify_pet_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_pet(sample_image)

    @pytest.mark.asyncio
    async def test_classify_pet_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Internal error", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_pet(sample_image)

    @pytest.mark.asyncio
    async def test_classify_pet_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 422

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Validation error", request=mock_request, response=mock_response
            )
        )

        result = await client.classify_pet(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_classify_pet_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=ValueError("Unexpected"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_pet(sample_image)


# =============================================================================
# EnrichmentClient Clothing Classification Tests
# =============================================================================


class TestEnrichmentClientClassifyClothing:
    """Tests for classify_clothing method."""

    @pytest.mark.asyncio
    async def test_classify_clothing_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful clothing classification."""
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

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_clothing(sample_image)

        assert result is not None
        assert result.clothing_type == "jacket"
        assert result.color == "blue"

    @pytest.mark.asyncio
    async def test_classify_clothing_with_bbox(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with bounding box."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "clothing_type": "uniform",
            "color": "white",
            "style": "professional",
            "confidence": 0.91,
            "top_category": "uniform",
            "description": "White professional uniform",
            "is_suspicious": False,
            "is_service_uniform": True,
            "inference_time_ms": 52.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_clothing(sample_image, bbox=(0.0, 0.0, 100.0, 100.0))

        assert result is not None
        assert result.is_service_uniform is True

    @pytest.mark.asyncio
    async def test_classify_clothing_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_clothing(sample_image)

    @pytest.mark.asyncio
    async def test_classify_clothing_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_clothing(sample_image)

    @pytest.mark.asyncio
    async def test_classify_clothing_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 502

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad gateway", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_clothing(sample_image)

    @pytest.mark.asyncio
    async def test_classify_clothing_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not found", request=mock_request, response=mock_response
            )
        )

        result = await client.classify_clothing(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_classify_clothing_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=KeyError("Missing field"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_clothing(sample_image)


# =============================================================================
# EnrichmentClient Depth Estimation Tests
# =============================================================================


class TestEnrichmentClientEstimateDepth:
    """Tests for estimate_depth method."""

    @pytest.mark.asyncio
    async def test_estimate_depth_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful depth estimation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "depth_map_base64": "dGVzdGRlcHRobWFw",
            "min_depth": 0.05,
            "max_depth": 0.95,
            "mean_depth": 0.42,
            "inference_time_ms": 65.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.estimate_depth(sample_image)

        assert result is not None
        assert result.mean_depth == 0.42
        assert result.depth_map_base64 == "dGVzdGRlcHRobWFw"

    @pytest.mark.asyncio
    async def test_estimate_depth_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_depth(sample_image)

    @pytest.mark.asyncio
    async def test_estimate_depth_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_depth(sample_image)

    @pytest.mark.asyncio
    async def test_estimate_depth_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_depth(sample_image)

    @pytest.mark.asyncio
    async def test_estimate_depth_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad request", request=mock_request, response=mock_response
            )
        )

        result = await client.estimate_depth(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_depth_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=AttributeError("Bad response"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_depth(sample_image)


# =============================================================================
# EnrichmentClient Object Distance Tests
# =============================================================================


class TestEnrichmentClientEstimateObjectDistance:
    """Tests for estimate_object_distance method."""

    @pytest.mark.asyncio
    async def test_estimate_object_distance_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful object distance estimation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 3.5,
            "relative_depth": 0.35,
            "proximity_label": "medium",
            "inference_time_ms": 58.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.estimate_object_distance(sample_image, bbox=(20.0, 30.0, 80.0, 90.0))

        assert result is not None
        assert result.estimated_distance_m == 3.5
        assert result.proximity_label == "medium"

    @pytest.mark.asyncio
    async def test_estimate_object_distance_with_method(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with custom method."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 4.2,
            "relative_depth": 0.42,
            "proximity_label": "medium",
            "inference_time_ms": 60.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.estimate_object_distance(
            sample_image, bbox=(20.0, 30.0, 80.0, 90.0), method="median"
        )

        assert result is not None
        call_args = client._http_client.post.call_args
        assert call_args.kwargs["json"]["method"] == "median"

    @pytest.mark.asyncio
    async def test_estimate_object_distance_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

    @pytest.mark.asyncio
    async def test_estimate_object_distance_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

    @pytest.mark.asyncio
    async def test_estimate_object_distance_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Service unavailable", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

    @pytest.mark.asyncio
    async def test_estimate_object_distance_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 422

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Validation error", request=mock_request, response=mock_response
            )
        )

        result = await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=TypeError("Type error"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))


# =============================================================================
# EnrichmentClient Pose Analysis Tests
# =============================================================================


class TestEnrichmentClientAnalyzePose:
    """Tests for analyze_pose method."""

    @pytest.mark.asyncio
    async def test_analyze_pose_success(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test successful pose analysis."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keypoints": [
                {"name": "nose", "x": 0.5, "y": 0.15, "confidence": 0.95},
                {"name": "left_eye", "x": 0.48, "y": 0.12, "confidence": 0.92},
            ],
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 75.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.analyze_pose(sample_image)

        assert result is not None
        assert result.posture == "standing"
        assert len(result.keypoints) == 2
        assert result.keypoints[0].name == "nose"

    @pytest.mark.asyncio
    async def test_analyze_pose_with_bbox(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with bounding box."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keypoints": [],
            "posture": "unknown",
            "alerts": [],
            "inference_time_ms": 70.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.analyze_pose(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

        assert result is not None
        call_args = client._http_client.post.call_args
        assert "bbox" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_analyze_pose_with_min_confidence(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with min_confidence parameter."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "keypoints": [],
            "posture": "standing",
            "alerts": [],
            "inference_time_ms": 72.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.analyze_pose(sample_image, min_confidence=0.5)

        assert result is not None
        call_args = client._http_client.post.call_args
        assert call_args.kwargs["json"]["min_confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_analyze_pose_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.analyze_pose(sample_image)

    @pytest.mark.asyncio
    async def test_analyze_pose_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.analyze_pose(sample_image)

    @pytest.mark.asyncio
    async def test_analyze_pose_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.analyze_pose(sample_image)

    @pytest.mark.asyncio
    async def test_analyze_pose_client_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad request", request=mock_request, response=mock_response
            )
        )

        result = await client.analyze_pose(sample_image)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_pose_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=IndexError("Index error"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.analyze_pose(sample_image)


# =============================================================================
# EnrichmentClient Action Classification Tests
# =============================================================================


class TestEnrichmentClientClassifyAction:
    """Tests for classify_action method."""

    @pytest.mark.asyncio
    async def test_classify_action_success(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test successful action classification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "a person walking",
            "confidence": 0.88,
            "is_suspicious": False,
            "risk_weight": 0.15,
            "all_scores": {"a person walking": 0.88, "a person standing": 0.08},
            "inference_time_ms": 150.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.classify_action(sample_frames)

        assert result is not None
        assert result.action == "a person walking"
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    async def test_classify_action_with_labels(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with custom labels."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "person running",
            "confidence": 0.92,
            "is_suspicious": True,
            "risk_weight": 0.65,
            "all_scores": {"person running": 0.92, "person walking": 0.05},
            "inference_time_ms": 145.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        custom_labels = ["person walking", "person running", "person loitering"]
        result = await client.classify_action(sample_frames, labels=custom_labels)

        assert result is not None
        call_args = client._http_client.post.call_args
        assert call_args.kwargs["json"]["labels"] == custom_labels

    @pytest.mark.asyncio
    async def test_classify_action_encodes_all_frames(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test that all frames are encoded in the request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "action": "a person walking",
            "confidence": 0.80,
            "is_suspicious": False,
            "risk_weight": 0.1,
            "all_scores": {},
            "inference_time_ms": 140.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.classify_action(sample_frames)

        call_args = client._http_client.post.call_args
        assert len(call_args.kwargs["json"]["frames"]) == len(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_connection_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_action(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_timeout(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with timeout."""
        client._http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_action(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_server_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=mock_request, response=mock_response
            )
        )

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_action(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_client_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with client error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400

        client._http_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad request", request=mock_request, response=mock_response
            )
        )

        result = await client.classify_action(sample_frames)
        assert result is None

    @pytest.mark.asyncio
    async def test_classify_action_unexpected_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with unexpected error."""
        client._http_client.post = AsyncMock(side_effect=MemoryError("Out of memory"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_action(sample_frames)


# =============================================================================
# Global Client Management Tests
# =============================================================================


class TestGlobalClientManagement:
    """Tests for global client singleton management."""

    def test_get_enrichment_client_creates_singleton(self, mock_settings: MagicMock) -> None:
        """Test get_enrichment_client creates a singleton instance."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client1 = get_enrichment_client()
            client2 = get_enrichment_client()
            assert client1 is client2

    async def test_reset_enrichment_client_clears_singleton(self, mock_settings: MagicMock) -> None:
        """Test reset_enrichment_client clears the singleton."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client1 = get_enrichment_client()
            await reset_enrichment_client()
            client2 = get_enrichment_client()
            assert client1 is not client2

    def test_get_enrichment_client_returns_enrichment_client(
        self, mock_settings: MagicMock
    ) -> None:
        """Test get_enrichment_client returns EnrichmentClient instance."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = get_enrichment_client()
            assert isinstance(client, EnrichmentClient)


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestEnrichmentClientCircuitBreaker:
    """Tests for circuit breaker functionality."""

    def test_get_circuit_breaker_state(self, client: EnrichmentClient) -> None:
        """Test getting circuit breaker state."""
        from backend.services.circuit_breaker import CircuitState

        state = client.get_circuit_breaker_state()
        assert state == CircuitState.CLOSED

    def test_is_circuit_open_false(self, client: EnrichmentClient) -> None:
        """Test is_circuit_open returns False initially."""
        assert client.is_circuit_open() is False

    def test_reset_circuit_breaker(self, client: EnrichmentClient) -> None:
        """Test manually resetting circuit breaker."""
        from backend.services.circuit_breaker import CircuitState

        client.reset_circuit_breaker()
        assert client.get_circuit_breaker_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_requests_when_open(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that circuit breaker blocks requests when open."""
        from backend.services.circuit_breaker import CircuitState

        # Manually open the circuit
        client._circuit_breaker._state = CircuitState.OPEN

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.classify_vehicle(sample_image)

        assert "circuit open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_is_healthy_false_when_circuit_open(self, client: EnrichmentClient) -> None:
        """Test is_healthy returns False when circuit is open."""
        from backend.services.circuit_breaker import CircuitState

        # Manually open the circuit
        client._circuit_breaker._state = CircuitState.OPEN

        assert await client.is_healthy() is False

    @pytest.mark.asyncio
    async def test_check_health_includes_circuit_breaker_state(
        self, client: EnrichmentClient
    ) -> None:
        """Test check_health includes circuit breaker state in response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()

        client._health_http_client.get = AsyncMock(return_value=mock_response)

        result = await client.check_health()
        assert "circuit_breaker_state" in result


# =============================================================================
# Retry Logic Tests
# =============================================================================


class TestEnrichmentClientRetryLogic:
    """Tests for retry logic with exponential backoff."""

    def test_calculate_backoff_delay(self, client: EnrichmentClient) -> None:
        """Test exponential backoff delay calculation."""
        delay0 = client._calculate_backoff_delay(0)
        delay1 = client._calculate_backoff_delay(1)
        delay2 = client._calculate_backoff_delay(2)

        # Base delays should be approximately 1s, 2s, 4s (with jitter)
        assert 0.9 <= delay0 <= 1.1
        assert 1.8 <= delay1 <= 2.2
        assert 3.6 <= delay2 <= 4.4

    def test_calculate_backoff_delay_capped_at_30_seconds(self, client: EnrichmentClient) -> None:
        """Test that backoff delay is capped at 30 seconds."""
        delay = client._calculate_backoff_delay(10)  # 2^10 = 1024 seconds
        assert delay <= 30.0

    def test_is_retryable_error_connect_error(self, client: EnrichmentClient) -> None:
        """Test ConnectError is retryable."""
        error = httpx.ConnectError("Connection refused")
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_timeout(self, client: EnrichmentClient) -> None:
        """Test TimeoutException is retryable."""
        error = httpx.TimeoutException("Timeout")
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_5xx(self, client: EnrichmentClient) -> None:
        """Test 5xx HTTP errors are retryable."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)
        assert client._is_retryable_error(error) is True

    def test_is_retryable_error_4xx_not_retryable(self, client: EnrichmentClient) -> None:
        """Test 4xx HTTP errors are not retryable."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)
        assert client._is_retryable_error(error) is False

    def test_is_retryable_error_other_exceptions_not_retryable(
        self, client: EnrichmentClient
    ) -> None:
        """Test other exceptions are not retryable."""
        error = ValueError("Invalid value")
        assert client._is_retryable_error(error) is False

    @pytest.mark.asyncio
    async def test_classify_vehicle_retries_on_server_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification retries on server error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503

        # First two calls fail with 503, third succeeds
        success_response = MagicMock()
        success_response.json.return_value = {
            "vehicle_type": "sedan",
            "display_name": "Sedan",
            "confidence": 0.90,
            "is_commercial": False,
            "all_scores": {"sedan": 0.90},
            "inference_time_ms": 45.0,
        }
        success_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(
            side_effect=[
                httpx.HTTPStatusError(
                    "Service unavailable", request=mock_request, response=mock_response
                ),
                httpx.HTTPStatusError(
                    "Service unavailable", request=mock_request, response=mock_response
                ),
                success_response,
            ]
        )

        with patch("backend.services.enrichment_client.increment_enrichment_retry"):
            result = await client.classify_vehicle(sample_image)

        assert result is not None
        assert result.vehicle_type == "sedan"
        assert client._http_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_classify_vehicle_asyncio_timeout_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification handles asyncio.timeout() TimeoutError."""
        # AsyncIO timeout raises TimeoutError (not httpx.TimeoutException)
        client._http_client.post = AsyncMock(side_effect=TimeoutError("asyncio timeout"))

        with pytest.raises(EnrichmentUnavailableError) as exc_info:
            await client.classify_vehicle(sample_image)

        assert "failed after" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_classify_pet_retries_with_exponential_backoff(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification uses exponential backoff on retries."""
        # Mock time.sleep to track delays
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            client._http_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_pet(sample_image)

            # Should have called sleep with increasing delays
            assert mock_sleep.call_count == client._max_retries - 1

    @pytest.mark.asyncio
    async def test_classify_clothing_asyncio_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification handles asyncio TimeoutError."""
        client._http_client.post = AsyncMock(side_effect=TimeoutError("asyncio timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_clothing(sample_image)

    @pytest.mark.asyncio
    async def test_estimate_depth_retries_on_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation retries on connection error."""
        success_response = MagicMock()
        success_response.json.return_value = {
            "depth_map_base64": "dGVzdA==",
            "min_depth": 0.1,
            "max_depth": 0.9,
            "mean_depth": 0.5,
            "inference_time_ms": 60.0,
        }
        success_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                success_response,
            ]
        )

        result = await client.estimate_depth(sample_image)
        assert result is not None
        assert result.mean_depth == 0.5

    @pytest.mark.asyncio
    async def test_analyze_pose_asyncio_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis handles asyncio TimeoutError."""
        client._http_client.post = AsyncMock(side_effect=TimeoutError("asyncio timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.analyze_pose(sample_image)

    @pytest.mark.asyncio
    async def test_classify_action_asyncio_timeout(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification handles asyncio TimeoutError."""
        client._http_client.post = AsyncMock(side_effect=TimeoutError("asyncio timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.classify_action(sample_frames)


# =============================================================================
# Bbox Validation Tests
# =============================================================================


class TestEnrichmentClientBboxValidation:
    """Tests for bounding box validation in object distance estimation."""

    @pytest.mark.asyncio
    async def test_estimate_object_distance_invalid_bbox_nan(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with NaN in bbox."""
        result = await client.estimate_object_distance(
            sample_image, bbox=(float("nan"), 10.0, 90.0, 90.0)
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_invalid_bbox_zero_width(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with zero width bbox."""
        result = await client.estimate_object_distance(sample_image, bbox=(50.0, 10.0, 50.0, 90.0))
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_invalid_bbox_inverted(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with inverted bbox coordinates."""
        result = await client.estimate_object_distance(sample_image, bbox=(90.0, 90.0, 10.0, 10.0))
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_bbox_outside_image(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with bbox outside image boundaries."""
        # bbox completely outside image
        result = await client.estimate_object_distance(
            sample_image, bbox=(200.0, 200.0, 300.0, 300.0)
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_bbox_clamped(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation clamps bbox to image boundaries."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 5.0,
            "relative_depth": 0.5,
            "proximity_label": "medium",
            "inference_time_ms": 55.0,
        }
        mock_response.raise_for_status = MagicMock()

        client._http_client.post = AsyncMock(return_value=mock_response)

        # bbox extends beyond image boundaries (100x100 image)
        result = await client.estimate_object_distance(
            sample_image, bbox=(-10.0, -10.0, 110.0, 110.0)
        )

        assert result is not None
        # Verify clamped bbox was sent in request
        call_args = client._http_client.post.call_args
        sent_bbox = call_args.kwargs["json"]["bbox"]
        # Should be clamped to (0, 0, 100, 100)
        assert sent_bbox[0] >= 0
        assert sent_bbox[1] >= 0
        assert sent_bbox[2] <= 100
        assert sent_bbox[3] <= 100

    @pytest.mark.asyncio
    async def test_estimate_object_distance_asyncio_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation handles asyncio TimeoutError."""
        client._http_client.post = AsyncMock(side_effect=TimeoutError("asyncio timeout"))

        with pytest.raises(EnrichmentUnavailableError):
            await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))


# =============================================================================
# Client Lifecycle Tests
# =============================================================================


class TestEnrichmentClientLifecycle:
    """Tests for client lifecycle management."""

    @pytest.mark.asyncio
    async def test_close_client(self, client: EnrichmentClient) -> None:
        """Test closing HTTP client connections."""
        await client.close()

        # Verify both HTTP clients were closed
        client._http_client.aclose.assert_called_once()
        client._health_http_client.aclose.assert_called_once()


# =============================================================================
# Unified Enrichment Result Dataclass Tests (NEM-3040)
# =============================================================================


class TestUnifiedPoseResult:
    """Tests for UnifiedPoseResult dataclass."""

    @pytest.fixture
    def pose_result(self) -> UnifiedPoseResult:
        """Create a sample unified pose result."""
        from backend.services.enrichment_client import UnifiedPoseResult

        return UnifiedPoseResult(
            keypoints=[{"x": 0.5, "y": 0.3, "confidence": 0.95, "name": "nose"}],
            pose_class="standing",
            confidence=0.92,
            is_suspicious=False,
        )

    def test_to_dict(self, pose_result: UnifiedPoseResult) -> None:
        """Test to_dict serialization."""
        result = pose_result.to_dict()
        assert result["pose_class"] == "standing"
        assert result["confidence"] == 0.92
        assert result["is_suspicious"] is False
        assert len(result["keypoints"]) == 1

    def test_to_context_string(self, pose_result: UnifiedPoseResult) -> None:
        """Test context string generation."""
        context = pose_result.to_context_string()
        assert "standing" in context
        assert "92%" in context

    def test_to_context_string_suspicious(self) -> None:
        """Test context string with suspicious pose."""
        from backend.services.enrichment_client import UnifiedPoseResult

        result = UnifiedPoseResult(
            keypoints=[],
            pose_class="crouching",
            confidence=0.85,
            is_suspicious=True,
        )
        context = result.to_context_string()
        assert "crouching" in context
        assert "ALERT" in context


class TestUnifiedClothingResult:
    """Tests for UnifiedClothingResult dataclass."""

    @pytest.fixture
    def clothing_result(self) -> UnifiedClothingResult:
        """Create a sample unified clothing result."""
        from backend.services.enrichment_client import UnifiedClothingResult

        return UnifiedClothingResult(
            categories=[
                {"category": "casual", "confidence": 0.85},
                {"category": "delivery", "confidence": 0.10},
            ],
            is_suspicious=False,
        )

    def test_to_dict(self, clothing_result: UnifiedClothingResult) -> None:
        """Test to_dict serialization."""
        result = clothing_result.to_dict()
        assert len(result["categories"]) == 2
        assert result["is_suspicious"] is False

    def test_to_context_string(self, clothing_result: UnifiedClothingResult) -> None:
        """Test context string generation."""
        context = clothing_result.to_context_string()
        assert "casual" in context
        assert "85%" in context

    def test_to_context_string_suspicious(self) -> None:
        """Test context string with suspicious clothing."""
        from backend.services.enrichment_client import UnifiedClothingResult

        result = UnifiedClothingResult(
            categories=[{"category": "hoodie_dark", "confidence": 0.90}],
            is_suspicious=True,
        )
        context = result.to_context_string()
        assert "ALERT" in context


class TestUnifiedDemographicsResult:
    """Tests for UnifiedDemographicsResult dataclass."""

    @pytest.fixture
    def demographics_result(self) -> UnifiedDemographicsResult:
        """Create a sample unified demographics result."""
        from backend.services.enrichment_client import UnifiedDemographicsResult

        return UnifiedDemographicsResult(
            age_range="25-35",
            age_confidence=0.78,
            gender="male",
            gender_confidence=0.92,
        )

    def test_to_dict(self, demographics_result: UnifiedDemographicsResult) -> None:
        """Test to_dict serialization."""
        result = demographics_result.to_dict()
        assert result["age_range"] == "25-35"
        assert result["age_confidence"] == 0.78
        assert result["gender"] == "male"
        assert result["gender_confidence"] == 0.92

    def test_to_context_string(self, demographics_result: UnifiedDemographicsResult) -> None:
        """Test context string generation."""
        context = demographics_result.to_context_string()
        assert "male" in context
        assert "92%" in context
        assert "25-35" in context


class TestUnifiedVehicleResult:
    """Tests for UnifiedVehicleResult dataclass."""

    @pytest.fixture
    def vehicle_result(self) -> UnifiedVehicleResult:
        """Create a sample unified vehicle result."""
        from backend.services.enrichment_client import UnifiedVehicleResult

        return UnifiedVehicleResult(
            make="Toyota",
            model="Camry",
            color="silver",
            type="sedan",
            confidence=0.88,
        )

    def test_to_dict(self, vehicle_result: UnifiedVehicleResult) -> None:
        """Test to_dict serialization."""
        result = vehicle_result.to_dict()
        assert result["make"] == "Toyota"
        assert result["model"] == "Camry"
        assert result["color"] == "silver"
        assert result["type"] == "sedan"
        assert result["confidence"] == 0.88

    def test_to_context_string(self, vehicle_result: UnifiedVehicleResult) -> None:
        """Test context string generation."""
        context = vehicle_result.to_context_string()
        assert "Toyota" in context
        assert "Camry" in context
        assert "silver" in context
        assert "sedan" in context

    def test_to_context_string_partial_info(self) -> None:
        """Test context string with missing make/model."""
        from backend.services.enrichment_client import UnifiedVehicleResult

        result = UnifiedVehicleResult(
            make=None,
            model=None,
            color="red",
            type="pickup_truck",
            confidence=0.75,
        )
        context = result.to_context_string()
        assert "red" in context
        assert "pickup_truck" in context


class TestUnifiedThreatResult:
    """Tests for UnifiedThreatResult dataclass."""

    @pytest.fixture
    def threat_result(self) -> UnifiedThreatResult:
        """Create a sample unified threat result."""
        from backend.services.enrichment_client import UnifiedThreatResult

        return UnifiedThreatResult(
            threats=[{"type": "knife", "confidence": 0.85, "bbox": [10, 20, 50, 80]}],
            has_threat=True,
            max_severity="high",
        )

    def test_to_dict(self, threat_result: UnifiedThreatResult) -> None:
        """Test to_dict serialization."""
        result = threat_result.to_dict()
        assert len(result["threats"]) == 1
        assert result["has_threat"] is True
        assert result["max_severity"] == "high"

    def test_to_context_string_with_threat(self, threat_result: UnifiedThreatResult) -> None:
        """Test context string with detected threat."""
        context = threat_result.to_context_string()
        assert "THREAT DETECTED" in context
        assert "knife" in context
        assert "high" in context

    def test_to_context_string_no_threat(self) -> None:
        """Test context string without threats."""
        from backend.services.enrichment_client import UnifiedThreatResult

        result = UnifiedThreatResult(
            threats=[],
            has_threat=False,
            max_severity="none",
        )
        context = result.to_context_string()
        assert "No threats detected" in context


class TestUnifiedEnrichmentResult:
    """Tests for UnifiedEnrichmentResult dataclass."""

    @pytest.fixture
    def full_enrichment_result(self) -> UnifiedEnrichmentResult:
        """Create a full unified enrichment result with all fields."""
        from backend.services.enrichment_client import (
            UnifiedClothingResult,
            UnifiedDemographicsResult,
            UnifiedEnrichmentResult,
            UnifiedPoseResult,
            UnifiedThreatResult,
        )

        return UnifiedEnrichmentResult(
            pose=UnifiedPoseResult(
                keypoints=[{"x": 0.5, "y": 0.3, "confidence": 0.95, "name": "nose"}],
                pose_class="standing",
                confidence=0.92,
                is_suspicious=False,
            ),
            clothing=UnifiedClothingResult(
                categories=[{"category": "casual", "confidence": 0.85}],
                is_suspicious=False,
            ),
            demographics=UnifiedDemographicsResult(
                age_range="25-35",
                age_confidence=0.78,
                gender="male",
                gender_confidence=0.92,
            ),
            threat=UnifiedThreatResult(
                threats=[],
                has_threat=False,
                max_severity="none",
            ),
            reid_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            models_loaded=["pose", "clothing", "demographics", "reid"],
            inference_time_ms=125.5,
        )

    def test_to_dict(self, full_enrichment_result: UnifiedEnrichmentResult) -> None:
        """Test to_dict serialization."""
        result = full_enrichment_result.to_dict()
        assert "pose" in result
        assert "clothing" in result
        assert "demographics" in result
        assert "threat" in result
        assert "reid_embedding" in result
        assert result["models_loaded"] == ["pose", "clothing", "demographics", "reid"]
        assert result["inference_time_ms"] == 125.5

    def test_to_context_string(self, full_enrichment_result: UnifiedEnrichmentResult) -> None:
        """Test context string generation."""
        context = full_enrichment_result.to_context_string()
        assert "standing" in context
        assert "casual" in context
        assert "male" in context

    def test_has_security_alerts_no_alerts(
        self, full_enrichment_result: UnifiedEnrichmentResult
    ) -> None:
        """Test has_security_alerts with no alerts."""
        assert full_enrichment_result.has_security_alerts() is False

    def test_has_security_alerts_with_threat(self) -> None:
        """Test has_security_alerts with threat."""
        from backend.services.enrichment_client import (
            UnifiedEnrichmentResult,
            UnifiedThreatResult,
        )

        result = UnifiedEnrichmentResult(
            threat=UnifiedThreatResult(
                threats=[{"type": "gun", "confidence": 0.95}],
                has_threat=True,
                max_severity="critical",
            ),
        )
        assert result.has_security_alerts() is True

    def test_has_security_alerts_with_suspicious_pose(self) -> None:
        """Test has_security_alerts with suspicious pose."""
        from backend.services.enrichment_client import (
            UnifiedEnrichmentResult,
            UnifiedPoseResult,
        )

        result = UnifiedEnrichmentResult(
            pose=UnifiedPoseResult(
                keypoints=[],
                pose_class="crouching",
                confidence=0.85,
                is_suspicious=True,
            ),
        )
        assert result.has_security_alerts() is True

    def test_has_security_alerts_with_suspicious_clothing(self) -> None:
        """Test has_security_alerts with suspicious clothing."""
        from backend.services.enrichment_client import (
            UnifiedClothingResult,
            UnifiedEnrichmentResult,
        )

        result = UnifiedEnrichmentResult(
            clothing=UnifiedClothingResult(
                categories=[{"category": "ski_mask", "confidence": 0.90}],
                is_suspicious=True,
            ),
        )
        assert result.has_security_alerts() is True

    def test_empty_result(self) -> None:
        """Test empty UnifiedEnrichmentResult."""
        from backend.services.enrichment_client import UnifiedEnrichmentResult

        result = UnifiedEnrichmentResult()
        assert result.pose is None
        assert result.clothing is None
        assert result.has_security_alerts() is False
        assert result.to_context_string() == "No enrichment data available"


# =============================================================================
# Unified Enrichment Endpoint Tests (NEM-3040)
# =============================================================================


class TestEnrichmentClientEnrichDetection:
    """Tests for enrich_detection method calling unified /enrich endpoint."""

    @pytest.fixture
    def sample_image_bytes(self) -> bytes:
        """Create sample image bytes for testing."""
        img = Image.new("RGB", (100, 100), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_enrich_detection_person_success(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test successful person enrichment."""
        mock_response = create_mock_response(
            json_data={
                "pose": {
                    "keypoints": [{"x": 0.5, "y": 0.3, "confidence": 0.95, "name": "nose"}],
                    "pose_class": "standing",
                    "confidence": 0.92,
                    "is_suspicious": False,
                },
                "clothing": {
                    "categories": [{"category": "casual", "confidence": 0.85}],
                    "is_suspicious": False,
                },
                "threat": {
                    "threats": [],
                    "has_threat": False,
                    "max_severity": "none",
                },
                "reid_embedding": [0.1, 0.2, 0.3],
                "models_loaded": ["pose", "clothing", "threat", "reid"],
                "inference_time_ms": 150.5,
            },
            status_code=200,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
        )

        assert result.pose is not None
        assert result.pose.pose_class == "standing"
        assert result.clothing is not None
        assert result.clothing.is_suspicious is False
        assert result.threat is not None
        assert result.threat.has_threat is False
        assert result.reid_embedding == [0.1, 0.2, 0.3]
        assert result.models_loaded == ["pose", "clothing", "threat", "reid"]
        assert result.inference_time_ms == 150.5

    @pytest.mark.asyncio
    async def test_enrich_detection_vehicle_success(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test successful vehicle enrichment."""
        mock_response = create_mock_response(
            json_data={
                "vehicle": {
                    "make": "Ford",
                    "model": "F-150",
                    "color": "black",
                    "type": "pickup_truck",
                    "confidence": 0.91,
                },
                "depth": {
                    "relative_depth": 0.35,
                    "estimated_distance_m": 8.5,
                },
                "models_loaded": ["vehicle", "depth"],
                "inference_time_ms": 85.2,
            },
            status_code=200,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="vehicle",
            bbox=(50.0, 100.0, 300.0, 250.0),
        )

        assert result.vehicle is not None
        assert result.vehicle.make == "Ford"
        assert result.vehicle.model == "F-150"
        assert result.vehicle.type == "pickup_truck"
        assert result.depth is not None

    @pytest.mark.asyncio
    async def test_enrich_detection_with_frames(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test enrichment with video frames for action recognition."""
        mock_response = create_mock_response(
            json_data={
                "pose": {
                    "keypoints": [],
                    "pose_class": "running",
                    "confidence": 0.88,
                    "is_suspicious": True,
                },
                "action": {
                    "top_action": "person running",
                    "confidence": 0.92,
                    "all_scores": {"person running": 0.92, "person walking": 0.05},
                },
                "models_loaded": ["pose", "action"],
                "inference_time_ms": 320.0,
            },
            status_code=200,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        # Create sample frames
        frames = [sample_image_bytes for _ in range(8)]

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
            frames=frames,
            options={"suspicious_score": 75.0},
        )

        assert result.action is not None
        assert result.action["top_action"] == "person running"

    @pytest.mark.asyncio
    async def test_enrich_detection_with_demographics(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test enrichment with demographics when face is visible."""
        mock_response = create_mock_response(
            json_data={
                "pose": {
                    "keypoints": [],
                    "pose_class": "standing",
                    "confidence": 0.90,
                    "is_suspicious": False,
                },
                "demographics": {
                    "age_range": "30-40",
                    "age_confidence": 0.75,
                    "gender": "female",
                    "gender_confidence": 0.88,
                },
                "models_loaded": ["pose", "demographics"],
                "inference_time_ms": 180.0,
            },
            status_code=200,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
            options={"face_visible": True},
        )

        assert result.demographics is not None
        assert result.demographics.age_range == "30-40"
        assert result.demographics.gender == "female"

    @pytest.mark.asyncio
    async def test_enrich_detection_timeout_returns_empty_result(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test that timeout returns empty result instead of raising."""
        client._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
        )

        # Should return empty result, not raise
        assert result.pose is None
        assert result.clothing is None
        assert result.threat is None
        assert result.has_security_alerts() is False

    @pytest.mark.asyncio
    async def test_enrich_detection_connection_error_returns_empty_result(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test that connection error returns empty result."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
        )

        assert result.pose is None
        assert result.inference_time_ms == 0.0

    @pytest.mark.asyncio
    async def test_enrich_detection_http_error_returns_empty_result(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test that HTTP error returns empty result."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
        )

        assert result.pose is None

    @pytest.mark.asyncio
    async def test_enrich_detection_request_payload_format(
        self, client: EnrichmentClient, sample_image_bytes: bytes
    ) -> None:
        """Test that request payload is correctly formatted."""
        mock_response = create_mock_response(
            json_data={"models_loaded": [], "inference_time_ms": 50.0},
            status_code=200,
        )
        client._http_client.post = AsyncMock(return_value=mock_response)

        await client.enrich_detection(
            image=sample_image_bytes,
            detection_type="person",
            bbox=(10.0, 20.0, 90.0, 180.0),
            options={"face_visible": True, "suspicious_score": 25.0},
        )

        # Check call args
        call_args = client._http_client.post.call_args
        assert "http://test-enrichment:8094/enrich" in call_args.args[0]

        payload = call_args.kwargs["json"]
        assert "image" in payload
        assert payload["detection_type"] == "person"
        assert payload["bbox"] == {"x1": 10.0, "y1": 20.0, "x2": 90.0, "y2": 180.0}
        assert payload["options"]["face_visible"] is True
        assert payload["options"]["suspicious_score"] == 25.0


class TestEnrichmentClientModelStatus:
    """Tests for get_model_status method."""

    @pytest.mark.asyncio
    async def test_get_model_status_success(self, client: EnrichmentClient) -> None:
        """Test successful model status retrieval."""
        mock_response = create_mock_response(
            json_data={
                "loaded_models": ["pose", "clothing", "threat"],
                "vram_usage_mb": 1500,
                "vram_budget_mb": 6800,
                "model_specs": {
                    "pose": {"vram_mb": 300, "priority": "high"},
                    "clothing": {"vram_mb": 800, "priority": "high"},
                    "threat": {"vram_mb": 400, "priority": "critical"},
                },
            },
            status_code=200,
        )
        client._http_client.get = AsyncMock(return_value=mock_response)

        result = await client.get_model_status()

        assert result["loaded_models"] == ["pose", "clothing", "threat"]
        assert result["vram_usage_mb"] == 1500
        assert result["vram_budget_mb"] == 6800

    @pytest.mark.asyncio
    async def test_get_model_status_connection_error(self, client: EnrichmentClient) -> None:
        """Test model status with connection error."""
        client._http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await client.get_model_status()

        assert "error" in result
        assert result["loaded_models"] == []

    @pytest.mark.asyncio
    async def test_get_model_status_timeout(self, client: EnrichmentClient) -> None:
        """Test model status with timeout."""
        client._http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))

        result = await client.get_model_status()

        assert "error" in result
        assert result["loaded_models"] == []


class TestEnrichmentClientPreloadModel:
    """Tests for preload_model method."""

    @pytest.mark.asyncio
    async def test_preload_model_success(self, client: EnrichmentClient) -> None:
        """Test successful model preloading."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.preload_model("pose")

        assert result is True
        client._http_client.post.assert_called_once()
        call_args = client._http_client.post.call_args
        assert "models/preload" in call_args.args[0]
        assert call_args.kwargs["params"]["model_name"] == "pose"

    @pytest.mark.asyncio
    async def test_preload_model_not_found(self, client: EnrichmentClient) -> None:
        """Test preloading unknown model."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        client._http_client.post = AsyncMock(return_value=mock_response)

        result = await client.preload_model("unknown_model")

        assert result is False

    @pytest.mark.asyncio
    async def test_preload_model_connection_error(self, client: EnrichmentClient) -> None:
        """Test model preloading with connection error."""
        client._http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        result = await client.preload_model("pose")

        assert result is False

    @pytest.mark.asyncio
    async def test_preload_model_timeout(self, client: EnrichmentClient) -> None:
        """Test model preloading with timeout."""
        client._http_client.post = AsyncMock(
            side_effect=httpx.TimeoutException("Request timed out")
        )

        result = await client.preload_model("threat")

        assert result is False


class TestEnrichmentClientParseUnifiedResponse:
    """Tests for _parse_unified_response method."""

    def test_parse_full_response(self, client: EnrichmentClient) -> None:
        """Test parsing a full response with all fields."""
        data = {
            "pose": {
                "keypoints": [{"x": 0.5, "y": 0.3, "confidence": 0.95, "name": "nose"}],
                "pose_class": "standing",
                "confidence": 0.92,
                "is_suspicious": False,
            },
            "clothing": {
                "categories": [{"category": "casual", "confidence": 0.85}],
                "is_suspicious": False,
            },
            "demographics": {
                "age_range": "25-35",
                "age_confidence": 0.78,
                "gender": "male",
                "gender_confidence": 0.92,
            },
            "vehicle": {
                "make": "Toyota",
                "model": "Camry",
                "color": "silver",
                "type": "sedan",
                "confidence": 0.88,
            },
            "threat": {
                "threats": [{"type": "knife", "confidence": 0.85}],
                "has_threat": True,
                "max_severity": "high",
            },
            "reid_embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
            "pet": {"type": "dog", "breed": "labrador", "confidence": 0.95},
            "action": {"top_action": "walking", "confidence": 0.88},
            "depth": {"relative_depth": 0.4, "estimated_distance_m": 5.0},
            "models_loaded": ["pose", "clothing", "threat"],
            "inference_time_ms": 250.5,
        }

        result = client._parse_unified_response(data)

        assert result.pose is not None
        assert result.pose.pose_class == "standing"
        assert result.clothing is not None
        assert result.demographics is not None
        assert result.demographics.gender == "male"
        assert result.vehicle is not None
        assert result.vehicle.make == "Toyota"
        assert result.threat is not None
        assert result.threat.has_threat is True
        assert result.reid_embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert result.pet == {"type": "dog", "breed": "labrador", "confidence": 0.95}
        assert result.action == {"top_action": "walking", "confidence": 0.88}
        assert result.depth == {"relative_depth": 0.4, "estimated_distance_m": 5.0}
        assert result.models_loaded == ["pose", "clothing", "threat"]
        assert result.inference_time_ms == 250.5

    def test_parse_empty_response(self, client: EnrichmentClient) -> None:
        """Test parsing an empty response."""
        data = {"models_loaded": [], "inference_time_ms": 0.0}

        result = client._parse_unified_response(data)

        assert result.pose is None
        assert result.clothing is None
        assert result.demographics is None
        assert result.vehicle is None
        assert result.threat is None
        assert result.reid_embedding is None
        assert result.models_loaded == []
        assert result.inference_time_ms == 0.0

    def test_parse_partial_response(self, client: EnrichmentClient) -> None:
        """Test parsing a partial response with only some fields."""
        data = {
            "pose": {
                "keypoints": [],
                "pose_class": "crouching",
                "confidence": 0.85,
                "is_suspicious": True,
            },
            "models_loaded": ["pose"],
            "inference_time_ms": 75.0,
        }

        result = client._parse_unified_response(data)

        assert result.pose is not None
        assert result.pose.pose_class == "crouching"
        assert result.pose.is_suspicious is True
        assert result.clothing is None
        assert result.vehicle is None
