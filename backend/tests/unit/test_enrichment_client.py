"""Unit tests for enrichment client service."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
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

# Fixtures


@pytest.fixture
def enrichment_client():
    """Create enrichment client instance."""
    return EnrichmentClient(base_url="http://localhost:8094")


@pytest.fixture
def sample_image():
    """Create a sample PIL Image for testing."""
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def sample_vehicle_response():
    """Sample response from vehicle classification endpoint."""
    return {
        "vehicle_type": "pickup_truck",
        "display_name": "pickup truck",
        "confidence": 0.92,
        "is_commercial": False,
        "all_scores": {"pickup_truck": 0.92, "car": 0.05, "work_van": 0.02},
        "inference_time_ms": 45.2,
    }


@pytest.fixture
def sample_pet_response():
    """Sample response from pet classification endpoint."""
    return {
        "pet_type": "dog",
        "breed": "unknown",
        "confidence": 0.98,
        "is_household_pet": True,
        "inference_time_ms": 22.1,
    }


@pytest.fixture
def sample_clothing_response():
    """Sample response from clothing classification endpoint."""
    return {
        "clothing_type": "hoodie",
        "color": "dark",
        "style": "suspicious",
        "confidence": 0.85,
        "top_category": "person wearing dark hoodie",
        "description": "Alert: dark hoodie",
        "is_suspicious": True,
        "is_service_uniform": False,
        "inference_time_ms": 68.4,
    }


@pytest.fixture
def sample_pose_response():
    """Sample response from pose analysis endpoint."""
    return {
        "keypoints": [
            {"name": "nose", "x": 0.5, "y": 0.1, "confidence": 0.95},
            {"name": "left_shoulder", "x": 0.4, "y": 0.25, "confidence": 0.92},
            {"name": "right_shoulder", "x": 0.6, "y": 0.25, "confidence": 0.91},
            {"name": "left_hip", "x": 0.42, "y": 0.5, "confidence": 0.88},
            {"name": "right_hip", "x": 0.58, "y": 0.5, "confidence": 0.87},
            {"name": "left_knee", "x": 0.42, "y": 0.7, "confidence": 0.85},
            {"name": "right_knee", "x": 0.58, "y": 0.7, "confidence": 0.84},
            {"name": "left_ankle", "x": 0.42, "y": 0.9, "confidence": 0.80},
            {"name": "right_ankle", "x": 0.58, "y": 0.9, "confidence": 0.79},
        ],
        "posture": "standing",
        "alerts": [],
        "inference_time_ms": 35.6,
    }


@pytest.fixture
def sample_pose_response_with_alerts():
    """Sample response from pose analysis with security alerts."""
    return {
        "keypoints": [
            {"name": "nose", "x": 0.5, "y": 0.3, "confidence": 0.9},
            {"name": "left_shoulder", "x": 0.4, "y": 0.35, "confidence": 0.88},
            {"name": "right_shoulder", "x": 0.6, "y": 0.35, "confidence": 0.87},
            {"name": "left_hip", "x": 0.42, "y": 0.6, "confidence": 0.85},
            {"name": "right_hip", "x": 0.58, "y": 0.6, "confidence": 0.84},
            {"name": "left_knee", "x": 0.42, "y": 0.65, "confidence": 0.82},
            {"name": "right_knee", "x": 0.58, "y": 0.65, "confidence": 0.81},
        ],
        "posture": "crouching",
        "alerts": ["crouching"],
        "inference_time_ms": 38.2,
    }


# Test: Health Check


@pytest.mark.asyncio
async def test_health_check_success(enrichment_client):
    """Test health check when service is available."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "models": [
                {"name": "vehicle-segment-classification", "loaded": True, "vram_mb": 1500},
                {"name": "pet-classifier", "loaded": True, "vram_mb": 200},
                {"name": "fashion-clip", "loaded": True, "vram_mb": 800},
            ],
            "total_vram_used_gb": 2.5,
            "device": "cuda:0",
            "cuda_available": True,
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = await enrichment_client.check_health()

        assert result["status"] == "healthy"
        assert len(result["models"]) == 3


@pytest.mark.asyncio
async def test_health_check_connection_error(enrichment_client):
    """Test health check when service is not reachable."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        result = await enrichment_client.check_health()

        assert result["status"] == "unavailable"


@pytest.mark.asyncio
async def test_health_check_timeout(enrichment_client):
    """Test health check when service times out."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        result = await enrichment_client.check_health()

        assert result["status"] == "unavailable"


@pytest.mark.asyncio
async def test_is_healthy_returns_true_for_healthy_status(enrichment_client):
    """Test is_healthy returns True when service is healthy."""
    with patch.object(enrichment_client, "check_health", return_value={"status": "healthy"}):
        result = await enrichment_client.is_healthy()
        assert result is True


@pytest.mark.asyncio
async def test_is_healthy_returns_true_for_degraded_status(enrichment_client):
    """Test is_healthy returns True when service is degraded."""
    with patch.object(enrichment_client, "check_health", return_value={"status": "degraded"}):
        result = await enrichment_client.is_healthy()
        assert result is True


@pytest.mark.asyncio
async def test_is_healthy_returns_false_for_unavailable_status(enrichment_client):
    """Test is_healthy returns False when service is unavailable."""
    with patch.object(enrichment_client, "check_health", return_value={"status": "unavailable"}):
        result = await enrichment_client.is_healthy()
        assert result is False


# Test: Vehicle Classification


@pytest.mark.asyncio
async def test_classify_vehicle_success(enrichment_client, sample_image, sample_vehicle_response):
    """Test vehicle classification success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_vehicle_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_vehicle(sample_image)

        assert isinstance(result, VehicleClassificationResult)
        assert result.vehicle_type == "pickup_truck"
        assert result.confidence == 0.92
        assert result.is_commercial is False


@pytest.mark.asyncio
async def test_classify_vehicle_with_bbox(enrichment_client, sample_image, sample_vehicle_response):
    """Test vehicle classification with bounding box."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_vehicle_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_vehicle(sample_image, bbox=(10, 20, 80, 90))

        assert isinstance(result, VehicleClassificationResult)
        # Verify the request included bbox
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs
        assert "bbox" in call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_classify_vehicle_connection_error(enrichment_client, sample_image):
    """Test vehicle classification raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.classify_vehicle(sample_image)


@pytest.mark.asyncio
async def test_classify_vehicle_timeout(enrichment_client, sample_image):
    """Test vehicle classification raises error on timeout."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.TimeoutException("Timeout"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.classify_vehicle(sample_image)


# Test: Pet Classification


@pytest.mark.asyncio
async def test_classify_pet_success(enrichment_client, sample_image, sample_pet_response):
    """Test pet classification success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_pet_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_pet(sample_image)

        assert isinstance(result, PetClassificationResult)
        assert result.pet_type == "dog"
        assert result.confidence == 0.98
        assert result.is_household_pet is True


@pytest.mark.asyncio
async def test_classify_pet_connection_error(enrichment_client, sample_image):
    """Test pet classification raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.classify_pet(sample_image)


# Test: Clothing Classification


@pytest.mark.asyncio
async def test_classify_clothing_success(enrichment_client, sample_image, sample_clothing_response):
    """Test clothing classification success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_clothing_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_clothing(sample_image)

        assert isinstance(result, ClothingClassificationResult)
        assert result.clothing_type == "hoodie"
        assert result.is_suspicious is True
        assert result.is_service_uniform is False


@pytest.mark.asyncio
async def test_classify_clothing_connection_error(enrichment_client, sample_image):
    """Test clothing classification raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.classify_clothing(sample_image)


# Test: Result Data Classes


def test_vehicle_result_to_dict():
    """Test VehicleClassificationResult to_dict method."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        display_name="car/sedan",
        confidence=0.95,
        is_commercial=False,
        all_scores={"car": 0.95, "pickup_truck": 0.03},
        inference_time_ms=42.5,
    )

    result_dict = result.to_dict()

    assert result_dict["vehicle_type"] == "car"
    assert result_dict["confidence"] == 0.95
    assert "all_scores" in result_dict


def test_vehicle_result_to_context_string():
    """Test VehicleClassificationResult to_context_string method."""
    result = VehicleClassificationResult(
        vehicle_type="work_van",
        display_name="work van/delivery van",
        confidence=0.88,
        is_commercial=True,
        all_scores={"work_van": 0.88},
        inference_time_ms=42.5,
    )

    context = result.to_context_string()

    assert "work van/delivery van" in context
    assert "88%" in context
    assert "Commercial" in context


def test_pet_result_to_dict():
    """Test PetClassificationResult to_dict method."""
    result = PetClassificationResult(
        pet_type="cat",
        breed="unknown",
        confidence=0.97,
        is_household_pet=True,
        inference_time_ms=20.0,
    )

    result_dict = result.to_dict()

    assert result_dict["pet_type"] == "cat"
    assert result_dict["is_household_pet"] is True


def test_pet_result_to_context_string():
    """Test PetClassificationResult to_context_string method."""
    result = PetClassificationResult(
        pet_type="dog",
        breed="unknown",
        confidence=0.95,
        is_household_pet=True,
        inference_time_ms=20.0,
    )

    context = result.to_context_string()

    assert "dog" in context
    assert "95%" in context


def test_clothing_result_to_dict():
    """Test ClothingClassificationResult to_dict method."""
    result = ClothingClassificationResult(
        clothing_type="vest",
        color="high-visibility",
        style="work",
        confidence=0.91,
        top_category="high-visibility vest or safety vest",
        description="Service worker: high-visibility vest",
        is_suspicious=False,
        is_service_uniform=True,
        inference_time_ms=65.0,
    )

    result_dict = result.to_dict()

    assert result_dict["clothing_type"] == "vest"
    assert result_dict["is_service_uniform"] is True


def test_clothing_result_to_context_string_suspicious():
    """Test ClothingClassificationResult to_context_string for suspicious clothing."""
    result = ClothingClassificationResult(
        clothing_type="masked",
        color="dark",
        style="suspicious",
        confidence=0.85,
        top_category="person wearing ski mask or balaclava",
        description="Alert: ski mask or balaclava",
        is_suspicious=True,
        is_service_uniform=False,
        inference_time_ms=65.0,
    )

    context = result.to_context_string()

    assert "ALERT" in context
    assert "suspicious" in context.lower()


def test_clothing_result_to_context_string_service():
    """Test ClothingClassificationResult to_context_string for service uniform."""
    result = ClothingClassificationResult(
        clothing_type="uniform",
        color="unknown",
        style="work",
        confidence=0.92,
        top_category="FedEx uniform",
        description="Service worker: FedEx uniform",
        is_suspicious=False,
        is_service_uniform=True,
        inference_time_ms=65.0,
    )

    context = result.to_context_string()

    assert "Service" in context or "uniform" in context.lower()


# Test: Global Client


def test_get_enrichment_client_returns_singleton():
    """Test that get_enrichment_client returns the same instance."""
    reset_enrichment_client()

    client1 = get_enrichment_client()
    client2 = get_enrichment_client()

    assert client1 is client2


def test_reset_enrichment_client():
    """Test that reset_enrichment_client creates new instance."""
    reset_enrichment_client()

    client1 = get_enrichment_client()
    reset_enrichment_client()
    client2 = get_enrichment_client()

    assert client1 is not client2


# Test: Pose Analysis


@pytest.mark.asyncio
async def test_analyze_pose_success(enrichment_client, sample_image, sample_pose_response):
    """Test pose analysis success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_pose_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.analyze_pose(sample_image)

        assert isinstance(result, PoseAnalysisResult)
        assert result.posture == "standing"
        assert len(result.keypoints) == 9
        assert len(result.alerts) == 0
        assert result.has_security_alerts() is False


@pytest.mark.asyncio
async def test_analyze_pose_with_alerts(
    enrichment_client, sample_image, sample_pose_response_with_alerts
):
    """Test pose analysis with security alerts."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_pose_response_with_alerts
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.analyze_pose(sample_image)

        assert isinstance(result, PoseAnalysisResult)
        assert result.posture == "crouching"
        assert "crouching" in result.alerts
        assert result.has_security_alerts() is True


@pytest.mark.asyncio
async def test_analyze_pose_with_bbox(enrichment_client, sample_image, sample_pose_response):
    """Test pose analysis with bounding box."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_pose_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.analyze_pose(sample_image, bbox=(10, 20, 80, 90))

        assert isinstance(result, PoseAnalysisResult)
        # Verify the request included bbox
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs
        assert "bbox" in call_args.kwargs["json"]


@pytest.mark.asyncio
async def test_analyze_pose_with_min_confidence(
    enrichment_client, sample_image, sample_pose_response
):
    """Test pose analysis with custom min_confidence."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_pose_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.analyze_pose(sample_image, min_confidence=0.5)

        assert isinstance(result, PoseAnalysisResult)
        # Verify the request included min_confidence
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs
        assert call_args.kwargs["json"]["min_confidence"] == 0.5


@pytest.mark.asyncio
async def test_analyze_pose_connection_error(enrichment_client, sample_image):
    """Test pose analysis raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.analyze_pose(sample_image)


@pytest.mark.asyncio
async def test_analyze_pose_timeout(enrichment_client, sample_image):
    """Test pose analysis raises error on timeout."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.TimeoutException("Timeout"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.analyze_pose(sample_image)


# Test: PoseAnalysisResult Data Class


def test_pose_result_to_dict():
    """Test PoseAnalysisResult to_dict method."""
    keypoints = [
        KeypointData(name="nose", x=0.5, y=0.1, confidence=0.95),
        KeypointData(name="left_shoulder", x=0.4, y=0.25, confidence=0.92),
    ]
    result = PoseAnalysisResult(
        keypoints=keypoints,
        posture="standing",
        alerts=[],
        inference_time_ms=35.0,
    )

    result_dict = result.to_dict()

    assert result_dict["posture"] == "standing"
    assert len(result_dict["keypoints"]) == 2
    assert result_dict["keypoints"][0]["name"] == "nose"
    assert result_dict["alerts"] == []


def test_pose_result_to_context_string_no_alerts():
    """Test PoseAnalysisResult to_context_string without alerts."""
    keypoints = [
        KeypointData(name="nose", x=0.5, y=0.1, confidence=0.95),
        KeypointData(name="left_shoulder", x=0.4, y=0.25, confidence=0.92),
    ]
    result = PoseAnalysisResult(
        keypoints=keypoints,
        posture="standing",
        alerts=[],
        inference_time_ms=35.0,
    )

    context = result.to_context_string()

    assert "standing" in context
    assert "2/17" in context  # Keypoints detected
    assert "ALERT" not in context


def test_pose_result_to_context_string_with_crouching_alert():
    """Test PoseAnalysisResult to_context_string with crouching alert."""
    result = PoseAnalysisResult(
        keypoints=[],
        posture="crouching",
        alerts=["crouching"],
        inference_time_ms=40.0,
    )

    context = result.to_context_string()

    assert "crouching" in context.lower()
    assert "ALERT" in context
    assert "hiding" in context.lower() or "break-in" in context.lower()


def test_pose_result_to_context_string_with_lying_down_alert():
    """Test PoseAnalysisResult to_context_string with lying down alert."""
    result = PoseAnalysisResult(
        keypoints=[],
        posture="lying_down",
        alerts=["lying_down"],
        inference_time_ms=40.0,
    )

    context = result.to_context_string()

    assert "lying" in context.lower()
    assert "ALERT" in context
    assert "medical" in context.lower() or "emergency" in context.lower()


def test_pose_result_to_context_string_with_hands_raised_alert():
    """Test PoseAnalysisResult to_context_string with hands raised alert."""
    result = PoseAnalysisResult(
        keypoints=[],
        posture="standing",
        alerts=["hands_raised"],
        inference_time_ms=40.0,
    )

    context = result.to_context_string()

    assert "ALERT" in context
    assert (
        "hands" in context.lower() or "surrender" in context.lower() or "robbery" in context.lower()
    )


def test_pose_result_to_context_string_with_fighting_stance_alert():
    """Test PoseAnalysisResult to_context_string with fighting stance alert."""
    result = PoseAnalysisResult(
        keypoints=[],
        posture="standing",
        alerts=["fighting_stance"],
        inference_time_ms=40.0,
    )

    context = result.to_context_string()

    assert "ALERT" in context
    assert "fighting" in context.lower() or "aggression" in context.lower()


def test_pose_result_has_security_alerts():
    """Test PoseAnalysisResult has_security_alerts method."""
    result_with_alerts = PoseAnalysisResult(
        keypoints=[],
        posture="crouching",
        alerts=["crouching"],
        inference_time_ms=40.0,
    )

    result_without_alerts = PoseAnalysisResult(
        keypoints=[],
        posture="standing",
        alerts=[],
        inference_time_ms=35.0,
    )

    assert result_with_alerts.has_security_alerts() is True
    assert result_without_alerts.has_security_alerts() is False


def test_keypoint_data_to_dict():
    """Test KeypointData to_dict method."""
    keypoint = KeypointData(name="nose", x=0.5, y=0.1, confidence=0.95)

    result = keypoint.to_dict()

    assert result["name"] == "nose"
    assert result["x"] == 0.5
    assert result["y"] == 0.1
    assert result["confidence"] == 0.95


# Test: Action Classification


@pytest.fixture
def sample_action_response():
    """Sample response from action classification endpoint."""
    return {
        "action": "a person loitering",
        "confidence": 0.78,
        "is_suspicious": True,
        "risk_weight": 0.7,
        "all_scores": {
            "a person loitering": 0.78,
            "a person walking normally": 0.12,
            "a person looking around suspiciously": 0.05,
        },
        "inference_time_ms": 245.6,
    }


@pytest.fixture
def sample_action_response_normal():
    """Sample response from action classification with normal activity."""
    return {
        "action": "a person delivering a package",
        "confidence": 0.85,
        "is_suspicious": False,
        "risk_weight": 0.2,
        "all_scores": {
            "a person delivering a package": 0.85,
            "a person walking normally": 0.08,
            "a person knocking on door": 0.04,
        },
        "inference_time_ms": 220.3,
    }


@pytest.fixture
def sample_video_frames():
    """Create sample video frames for testing."""
    return [Image.new("RGB", (224, 224), color=f"#{i * 30:02x}0000") for i in range(8)]


@pytest.mark.asyncio
async def test_classify_action_success(
    enrichment_client, sample_video_frames, sample_action_response
):
    """Test action classification success with suspicious action detected."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_action_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_action(sample_video_frames)

        assert result is not None
        assert result.action == "a person loitering"
        assert result.confidence == 0.78
        assert result.is_suspicious is True
        assert result.risk_weight == 0.7
        assert len(result.all_scores) == 3


@pytest.mark.asyncio
async def test_classify_action_normal_activity(
    enrichment_client, sample_video_frames, sample_action_response_normal
):
    """Test action classification with normal activity detected."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_action_response_normal
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_action(sample_video_frames)

        assert result is not None
        assert result.action == "a person delivering a package"
        assert result.is_suspicious is False
        assert result.risk_weight == 0.2


@pytest.mark.asyncio
async def test_classify_action_with_custom_labels(
    enrichment_client, sample_video_frames, sample_action_response
):
    """Test action classification with custom labels."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_action_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        custom_labels = ["running", "walking", "standing"]
        result = await enrichment_client.classify_action(sample_video_frames, labels=custom_labels)

        assert result is not None
        # Verify the custom labels were passed
        call_args = mock_post.call_args
        assert "labels" in call_args[1]["json"]
        assert call_args[1]["json"]["labels"] == custom_labels


@pytest.mark.asyncio
async def test_classify_action_connection_error(enrichment_client, sample_video_frames):
    """Test action classification when connection fails."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(EnrichmentUnavailableError) as excinfo:
            await enrichment_client.classify_action(sample_video_frames)

        assert "connect" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_classify_action_timeout(enrichment_client, sample_video_frames):
    """Test action classification when request times out."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(EnrichmentUnavailableError) as excinfo:
            await enrichment_client.classify_action(sample_video_frames)

        assert "timeout" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_classify_action_server_error(enrichment_client, sample_video_frames):
    """Test action classification when server returns 5xx error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=mock_response,
        )
        mock_post.return_value = mock_response

        with pytest.raises(EnrichmentUnavailableError) as excinfo:
            await enrichment_client.classify_action(sample_video_frames)

        assert "503" in str(excinfo.value) or "server" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_classify_action_client_error(enrichment_client, sample_video_frames):
    """Test action classification when client error occurs (returns None, no retry)."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )
        mock_post.return_value = mock_response

        result = await enrichment_client.classify_action(sample_video_frames)

        assert result is None


# Test: ActionClassificationResult dataclass


def test_action_result_to_dict():
    """Test ActionClassificationResult to_dict method."""
    result = ActionClassificationResult(
        action="a person loitering",
        confidence=0.78,
        is_suspicious=True,
        risk_weight=0.7,
        all_scores={"a person loitering": 0.78, "a person walking normally": 0.12},
        inference_time_ms=245.6,
    )

    result_dict = result.to_dict()

    assert result_dict["action"] == "a person loitering"
    assert result_dict["confidence"] == 0.78
    assert result_dict["is_suspicious"] is True
    assert result_dict["risk_weight"] == 0.7
    assert result_dict["inference_time_ms"] == 245.6
    assert len(result_dict["all_scores"]) == 2


def test_action_result_to_context_string_suspicious():
    """Test ActionClassificationResult to_context_string for suspicious action."""
    result = ActionClassificationResult(
        action="a person loitering",
        confidence=0.78,
        is_suspicious=True,
        risk_weight=0.7,
        all_scores={"a person loitering": 0.78},
        inference_time_ms=245.6,
    )

    context = result.to_context_string()

    assert "loitering" in context.lower()
    assert "ALERT" in context
    assert "70%" in context or "0.7" in context


def test_action_result_to_context_string_normal():
    """Test ActionClassificationResult to_context_string for normal action."""
    result = ActionClassificationResult(
        action="a person delivering a package",
        confidence=0.85,
        is_suspicious=False,
        risk_weight=0.2,
        all_scores={"a person delivering a package": 0.85},
        inference_time_ms=220.3,
    )

    context = result.to_context_string()

    assert "delivering" in context.lower()
    assert "ALERT" not in context
    assert "20%" in context or "0.2" in context


def test_action_result_has_security_alerts_suspicious():
    """Test ActionClassificationResult has_security_alerts for suspicious action."""
    result = ActionClassificationResult(
        action="a person loitering",
        confidence=0.78,
        is_suspicious=True,
        risk_weight=0.7,
        all_scores={"a person loitering": 0.78},
        inference_time_ms=245.6,
    )

    assert result.has_security_alerts() is True


def test_action_result_has_security_alerts_high_risk():
    """Test ActionClassificationResult has_security_alerts for high risk weight."""
    result = ActionClassificationResult(
        action="a person checking windows",
        confidence=0.65,
        is_suspicious=False,  # Even if not marked suspicious
        risk_weight=0.8,  # High risk weight triggers alert
        all_scores={"a person checking windows": 0.65},
        inference_time_ms=230.0,
    )

    assert result.has_security_alerts() is True


def test_action_result_has_security_alerts_normal():
    """Test ActionClassificationResult has_security_alerts for normal action."""
    result = ActionClassificationResult(
        action="a person walking normally",
        confidence=0.92,
        is_suspicious=False,
        risk_weight=0.2,
        all_scores={"a person walking normally": 0.92},
        inference_time_ms=200.0,
    )

    assert result.has_security_alerts() is False


# =============================================================================
# Depth Estimation Tests
# =============================================================================


@pytest.fixture
def sample_depth_response():
    """Sample response from depth estimation endpoint."""
    return {
        "depth_map_base64": "iVBORw0KGgo=",  # Minimal valid base64 PNG
        "min_depth": 0.0,
        "max_depth": 1.0,
        "mean_depth": 0.45,
        "inference_time_ms": 52.3,
    }


@pytest.fixture
def sample_object_distance_response():
    """Sample response from object distance endpoint."""
    return {
        "estimated_distance_m": 3.5,
        "relative_depth": 0.35,
        "proximity_label": "close",
        "inference_time_ms": 55.8,
    }


# Test: Depth Estimation


@pytest.mark.asyncio
async def test_estimate_depth_success(enrichment_client, sample_image, sample_depth_response):
    """Test depth estimation success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_depth_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.estimate_depth(sample_image)

        assert isinstance(result, DepthEstimationResult)
        assert result.min_depth == 0.0
        assert result.max_depth == 1.0
        assert result.mean_depth == 0.45
        assert result.inference_time_ms == 52.3


@pytest.mark.asyncio
async def test_estimate_depth_connection_error(enrichment_client, sample_image):
    """Test depth estimation raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_depth(sample_image)


@pytest.mark.asyncio
async def test_estimate_depth_timeout(enrichment_client, sample_image):
    """Test depth estimation raises error on timeout."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.TimeoutException("Timeout"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_depth(sample_image)


@pytest.mark.asyncio
async def test_estimate_depth_server_error(enrichment_client, sample_image):
    """Test depth estimation raises error on server error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=mock_response
    )

    with (
        patch("httpx.AsyncClient.post", return_value=mock_response),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_depth(sample_image)


@pytest.mark.asyncio
async def test_estimate_depth_client_error_returns_none(enrichment_client, sample_image):
    """Test depth estimation returns None on client error (4xx)."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await enrichment_client.estimate_depth(sample_image)
        assert result is None


# Test: Object Distance Estimation


@pytest.mark.asyncio
async def test_estimate_object_distance_success(
    enrichment_client, sample_image, sample_object_distance_response
):
    """Test object distance estimation success."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_object_distance_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(10, 20, 80, 90)
        )

        assert isinstance(result, ObjectDistanceResult)
        assert result.estimated_distance_m == 3.5
        assert result.relative_depth == 0.35
        assert result.proximity_label == "close"
        assert result.inference_time_ms == 55.8


@pytest.mark.asyncio
async def test_estimate_object_distance_with_method(
    enrichment_client, sample_image, sample_object_distance_response
):
    """Test object distance estimation with different sampling method."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_object_distance_response
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(10, 20, 80, 90), method="mean"
        )

        assert isinstance(result, ObjectDistanceResult)
        # Verify the request included method
        call_args = mock_post.call_args
        assert "json" in call_args.kwargs
        assert call_args.kwargs["json"]["method"] == "mean"


@pytest.mark.asyncio
async def test_estimate_object_distance_connection_error(enrichment_client, sample_image):
    """Test object distance estimation raises error on connection failure."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))


@pytest.mark.asyncio
async def test_estimate_object_distance_timeout(enrichment_client, sample_image):
    """Test object distance estimation raises error on timeout."""
    with (
        patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.TimeoutException("Timeout"),
        ),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))


@pytest.mark.asyncio
async def test_estimate_object_distance_server_error(enrichment_client, sample_image):
    """Test object distance estimation raises error on server error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=mock_response
    )

    with (
        patch("httpx.AsyncClient.post", return_value=mock_response),
        pytest.raises(EnrichmentUnavailableError),
    ):
        await enrichment_client.estimate_object_distance(sample_image, bbox=(10, 20, 80, 90))


@pytest.mark.asyncio
async def test_estimate_object_distance_client_error_returns_none(enrichment_client, sample_image):
    """Test object distance estimation returns None on client error (4xx)."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=mock_response
    )

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(10, 20, 80, 90)
        )
        assert result is None


# Test: DepthEstimationResult dataclass


def test_depth_estimation_result_to_dict():
    """Test DepthEstimationResult to_dict serialization."""
    result = DepthEstimationResult(
        depth_map_base64="iVBORw0KGgo=",
        min_depth=0.1,
        max_depth=0.9,
        mean_depth=0.5,
        inference_time_ms=45.0,
    )

    data = result.to_dict()

    assert data["depth_map_base64"] == "iVBORw0KGgo="
    assert data["min_depth"] == 0.1
    assert data["max_depth"] == 0.9
    assert data["mean_depth"] == 0.5
    assert data["inference_time_ms"] == 45.0


def test_depth_estimation_result_to_context_string():
    """Test DepthEstimationResult generates context string."""
    result = DepthEstimationResult(
        depth_map_base64="iVBORw0KGgo=",
        min_depth=0.1,
        max_depth=0.9,
        mean_depth=0.5,
        inference_time_ms=45.0,
    )

    context = result.to_context_string()

    assert "depth" in context.lower()
    assert "0.5" in context or "0.50" in context  # Mean depth
    assert "0.1" in context or "0.10" in context  # Min depth
    assert "0.9" in context or "0.90" in context  # Max depth


# Test: ObjectDistanceResult dataclass


def test_object_distance_result_to_dict():
    """Test ObjectDistanceResult to_dict serialization."""
    result = ObjectDistanceResult(
        estimated_distance_m=3.5,
        relative_depth=0.35,
        proximity_label="close",
        inference_time_ms=55.0,
    )

    data = result.to_dict()

    assert data["estimated_distance_m"] == 3.5
    assert data["relative_depth"] == 0.35
    assert data["proximity_label"] == "close"
    assert data["inference_time_ms"] == 55.0


def test_object_distance_result_to_context_string():
    """Test ObjectDistanceResult generates context string."""
    result = ObjectDistanceResult(
        estimated_distance_m=3.5,
        relative_depth=0.35,
        proximity_label="close",
        inference_time_ms=55.0,
    )

    context = result.to_context_string()

    assert "3.5" in context
    assert "close" in context


def test_object_distance_result_is_close_very_close():
    """Test ObjectDistanceResult is_close returns True for very close."""
    result = ObjectDistanceResult(
        estimated_distance_m=0.8,
        relative_depth=0.1,
        proximity_label="very close",
        inference_time_ms=50.0,
    )

    assert result.is_close() is True


def test_object_distance_result_is_close_close():
    """Test ObjectDistanceResult is_close returns True for close."""
    result = ObjectDistanceResult(
        estimated_distance_m=2.5,
        relative_depth=0.3,
        proximity_label="close",
        inference_time_ms=50.0,
    )

    assert result.is_close() is True


def test_object_distance_result_is_close_moderate():
    """Test ObjectDistanceResult is_close returns False for moderate distance."""
    result = ObjectDistanceResult(
        estimated_distance_m=5.0,
        relative_depth=0.5,
        proximity_label="moderate distance",
        inference_time_ms=50.0,
    )

    assert result.is_close() is False


def test_object_distance_result_is_close_far():
    """Test ObjectDistanceResult is_close returns False for far."""
    result = ObjectDistanceResult(
        estimated_distance_m=10.0,
        relative_depth=0.8,
        proximity_label="far",
        inference_time_ms=50.0,
    )

    assert result.is_close() is False


def test_object_distance_result_is_close_very_far():
    """Test ObjectDistanceResult is_close returns False for very far."""
    result = ObjectDistanceResult(
        estimated_distance_m=14.0,
        relative_depth=0.95,
        proximity_label="very far",
        inference_time_ms=50.0,
    )

    assert result.is_close() is False
