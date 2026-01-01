"""Unit tests for enrichment client service."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from backend.services.enrichment_client import (
    ClothingClassificationResult,
    EnrichmentClient,
    EnrichmentUnavailableError,
    PetClassificationResult,
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
