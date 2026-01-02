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
    VehicleClassificationResult,
    get_enrichment_client,
    reset_enrichment_client,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_client() -> None:
    """Reset global enrichment client before and after each test."""
    reset_enrichment_client()
    yield
    reset_enrichment_client()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.enrichment_url = "http://test-enrichment:8094"
    settings.ai_connect_timeout = 10.0
    settings.ai_health_timeout = 5.0
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
    """Create an EnrichmentClient with mocked settings."""
    with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
        return EnrichmentClient()


@pytest.fixture
def client_custom_url() -> EnrichmentClient:
    """Create an EnrichmentClient with custom URL."""
    with patch("backend.services.enrichment_client.get_settings") as mock_settings_fn:
        mock_settings = MagicMock()
        mock_settings.ai_connect_timeout = 10.0
        mock_settings.ai_health_timeout = 5.0
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
            raise EnrichmentUnavailableError("Service down", ConnectionError("Network error"))
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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.check_health()
            assert result["status"] == "healthy"
            assert "models" in result

    @pytest.mark.asyncio
    async def test_check_health_connection_error(self, client: EnrichmentClient) -> None:
        """Test health check with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.check_health()
            assert result["status"] == "unavailable"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_check_health_timeout(self, client: EnrichmentClient) -> None:
        """Test health check with timeout error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.check_health()
            assert result["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_check_health_http_error(self, client: EnrichmentClient) -> None:
        """Test health check with HTTP error."""
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.check_health()
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_check_health_unexpected_error(self, client: EnrichmentClient) -> None:
        """Test health check with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=RuntimeError("Unexpected error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.observe_ai_request_duration") as mock_observe,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_vehicle(sample_image, bbox=(10.0, 20.0, 80.0, 90.0))

            assert result is not None
            # Verify bbox was included in request
            call_args = mock_client.post.call_args
            assert "bbox" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_classify_vehicle_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with connection error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_vehicle(sample_image)

            mock_record.assert_called_once_with("enrichment_vehicle_connection_error")

    @pytest.mark.asyncio
    async def test_classify_vehicle_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with timeout."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service unavailable", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_vehicle(sample_image)
            assert result is None
            mock_record.assert_called_once_with("enrichment_vehicle_client_error")

    @pytest.mark.asyncio
    async def test_classify_vehicle_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test vehicle classification with unexpected error."""
        with (
            patch("httpx.AsyncClient") as mock_client_class,
            patch("backend.services.enrichment_client.record_pipeline_error") as mock_record,
        ):
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_pet(sample_image, bbox=(5.0, 10.0, 95.0, 90.0))

            assert result is not None
            call_args = mock_client.post.call_args
            assert "bbox" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_classify_pet_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_pet(sample_image)

    @pytest.mark.asyncio
    async def test_classify_pet_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Internal error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Validation error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_pet(sample_image)
            assert result is None

    @pytest.mark.asyncio
    async def test_classify_pet_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pet classification with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ValueError("Unexpected"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_clothing(sample_image, bbox=(0.0, 0.0, 100.0, 100.0))

            assert result is not None
            assert result.is_service_uniform is True

    @pytest.mark.asyncio
    async def test_classify_clothing_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_clothing(sample_image)

    @pytest.mark.asyncio
    async def test_classify_clothing_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad gateway", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not found", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_clothing(sample_image)
            assert result is None

    @pytest.mark.asyncio
    async def test_classify_clothing_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test clothing classification with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=KeyError("Missing field"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.estimate_depth(sample_image)

            assert result is not None
            assert result.mean_depth == 0.42
            assert result.depth_map_base64 == "dGVzdGRlcHRobWFw"

    @pytest.mark.asyncio
    async def test_estimate_depth_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.estimate_depth(sample_image)

    @pytest.mark.asyncio
    async def test_estimate_depth_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.estimate_depth(sample_image)
            assert result is None

    @pytest.mark.asyncio
    async def test_estimate_depth_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test depth estimation with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=AttributeError("Bad response"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.estimate_object_distance(
                sample_image, bbox=(20.0, 30.0, 80.0, 90.0)
            )

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.estimate_object_distance(
                sample_image, bbox=(20.0, 30.0, 80.0, 90.0), method="median"
            )

            assert result is not None
            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"]["method"] == "median"

    @pytest.mark.asyncio
    async def test_estimate_object_distance_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.estimate_object_distance(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

    @pytest.mark.asyncio
    async def test_estimate_object_distance_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Service unavailable", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Validation error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.estimate_object_distance(
                sample_image, bbox=(10.0, 10.0, 90.0, 90.0)
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_estimate_object_distance_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test object distance estimation with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=TypeError("Type error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.analyze_pose(sample_image, bbox=(10.0, 10.0, 90.0, 90.0))

            assert result is not None
            call_args = mock_client.post.call_args
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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.analyze_pose(sample_image, min_confidence=0.5)

            assert result is not None
            call_args = mock_client.post.call_args
            assert call_args.kwargs["json"]["min_confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_analyze_pose_connection_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.analyze_pose(sample_image)

    @pytest.mark.asyncio
    async def test_analyze_pose_timeout(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.analyze_pose(sample_image)
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_pose_unexpected_error(
        self, client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test pose analysis with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=IndexError("Index error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            custom_labels = ["person walking", "person running", "person loitering"]
            result = await client.classify_action(sample_frames, labels=custom_labels)

            assert result is not None
            call_args = mock_client.post.call_args
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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await client.classify_action(sample_frames)

            call_args = mock_client.post.call_args
            assert len(call_args.kwargs["json"]["frames"]) == len(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_connection_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with connection error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(EnrichmentUnavailableError):
                await client.classify_action(sample_frames)

    @pytest.mark.asyncio
    async def test_classify_action_timeout(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server error", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Bad request", request=mock_request, response=mock_response
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await client.classify_action(sample_frames)
            assert result is None

    @pytest.mark.asyncio
    async def test_classify_action_unexpected_error(
        self, client: EnrichmentClient, sample_frames: list[Image.Image]
    ) -> None:
        """Test action classification with unexpected error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=MemoryError("Out of memory"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

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

    def test_reset_enrichment_client_clears_singleton(self, mock_settings: MagicMock) -> None:
        """Test reset_enrichment_client clears the singleton."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client1 = get_enrichment_client()
            reset_enrichment_client()
            client2 = get_enrichment_client()
            assert client1 is not client2

    def test_get_enrichment_client_returns_enrichment_client(
        self, mock_settings: MagicMock
    ) -> None:
        """Test get_enrichment_client returns EnrichmentClient instance."""
        with patch("backend.services.enrichment_client.get_settings", return_value=mock_settings):
            client = get_enrichment_client()
            assert isinstance(client, EnrichmentClient)
