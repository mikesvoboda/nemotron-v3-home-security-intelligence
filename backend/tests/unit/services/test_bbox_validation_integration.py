"""Integration tests for bounding box validation in services.

Tests verify that bbox validation is properly integrated into:
- EnrichmentClient.estimate_object_distance (NEM-1102)
- ReIdentificationService.generate_embedding (NEM-1073)
- Detection pipeline bbox clamping (NEM-1122)

These tests ensure that invalid bounding boxes are handled gracefully
without crashing the services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.bbox_validation import (
    InvalidBoundingBoxError,
    validate_and_clamp_bbox,
)
from backend.services.enrichment_client import (
    EnrichmentClient,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
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
    return Image.new("RGB", (640, 480), color="red")


@pytest.fixture
def enrichment_client(mock_settings: MagicMock) -> EnrichmentClient:
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
# NEM-1102: estimate_object_distance bbox validation tests
# =============================================================================


class TestEstimateObjectDistanceBboxValidation:
    """Tests for bounding box validation in estimate_object_distance.

    NEM-1102: Add comprehensive bounding box validation in estimate_object_distance
    """

    @pytest.mark.asyncio
    async def test_valid_bbox_passes_through(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that valid bounding boxes are processed normally."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 3.5,
            "relative_depth": 0.35,
            "proximity_label": "medium",
            "inference_time_ms": 58.0,
        }
        mock_response.raise_for_status = MagicMock()

        # Mock the persistent HTTP client's post method
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # Valid bbox within image bounds
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(100.0, 100.0, 300.0, 300.0)
        )

        assert result is not None
        assert result.estimated_distance_m == 3.5

    @pytest.mark.asyncio
    async def test_zero_width_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that zero-width bounding boxes return None (NEM-1102)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image,
            bbox=(100.0, 100.0, 100.0, 200.0),  # Zero width
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_zero_height_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that zero-height bounding boxes return None (NEM-1102)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image,
            bbox=(100.0, 100.0, 200.0, 100.0),  # Zero height
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_inverted_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that inverted (x2 < x1) bounding boxes return None (NEM-1102)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image,
            bbox=(200.0, 100.0, 100.0, 200.0),  # x2 < x1
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_nan_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that bounding boxes with NaN values return None (NEM-1102)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(float("nan"), 100.0, 200.0, 200.0)
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_infinite_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that bounding boxes with infinite values return None (NEM-1102)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(float("inf"), 100.0, 200.0, 200.0)
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_bbox_exceeding_image_is_clamped(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that bboxes exceeding image bounds are clamped (NEM-1122)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 2.5,
            "relative_depth": 0.25,
            "proximity_label": "close",
            "inference_time_ms": 55.0,
        }
        mock_response.raise_for_status = MagicMock()

        # Mock the persistent HTTP client's post method
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # Bbox exceeds image bounds (640x480)
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(500.0, 400.0, 700.0, 500.0)
        )

        assert result is not None
        # Verify the bbox was clamped in the request
        call_args = enrichment_client._http_client.post.call_args
        sent_bbox = call_args.kwargs["json"]["bbox"]
        # After clamping: (500, 400, 640, 480)
        assert sent_bbox[2] <= 640
        assert sent_bbox[3] <= 480

    @pytest.mark.asyncio
    async def test_completely_outside_bbox_returns_none(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that bboxes completely outside image return None (NEM-1122)."""
        result = await enrichment_client.estimate_object_distance(
            sample_image,
            bbox=(700.0, 500.0, 800.0, 600.0),  # Outside 640x480
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_negative_bbox_coordinates_are_clamped(
        self, enrichment_client: EnrichmentClient, sample_image: Image.Image
    ) -> None:
        """Test that negative bbox coordinates are clamped to 0 (NEM-1102)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "estimated_distance_m": 4.0,
            "relative_depth": 0.40,
            "proximity_label": "medium",
            "inference_time_ms": 60.0,
        }
        mock_response.raise_for_status = MagicMock()

        # Mock the persistent HTTP client's post method
        enrichment_client._http_client.post = AsyncMock(return_value=mock_response)

        # Negative coordinates
        result = await enrichment_client.estimate_object_distance(
            sample_image, bbox=(-50.0, -50.0, 200.0, 200.0)
        )

        assert result is not None
        # Verify the bbox was clamped in the request
        call_args = enrichment_client._http_client.post.call_args
        sent_bbox = call_args.kwargs["json"]["bbox"]
        assert sent_bbox[0] >= 0
        assert sent_bbox[1] >= 0


# =============================================================================
# NEM-1073: ReIdentificationService bbox validation tests
# =============================================================================


class TestReIdentificationServiceBboxValidation:
    """Tests for bounding box validation in ReIdentificationService.

    NEM-1073: Add bounding box validation in ReIdentificationService
    """

    @pytest.mark.asyncio
    async def test_valid_bbox_crops_image(self) -> None:
        """Test that valid bounding boxes properly crop the image."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.1] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="blue")

        # Valid bbox
        embedding = await service.generate_embedding(image, bbox=(100, 100, 300, 300))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Verify that a cropped image was passed to embed
        called_image = mock_client.embed.call_args[0][0]
        assert called_image.size == (200, 200)  # 300-100 x 300-100

    @pytest.mark.asyncio
    async def test_invalid_bbox_raises_error(self) -> None:
        """Test that invalid bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        mock_client = AsyncMock()
        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="green")

        # Zero-width bbox
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(100, 100, 100, 200))

    @pytest.mark.asyncio
    async def test_inverted_bbox_raises_error(self) -> None:
        """Test that inverted bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        mock_client = AsyncMock()
        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="yellow")

        # Inverted bbox (x2 < x1)
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(200, 100, 100, 200))

    @pytest.mark.asyncio
    async def test_nan_bbox_raises_error(self) -> None:
        """Test that NaN bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        mock_client = AsyncMock()
        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="purple")

        # NaN in bbox
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(float("nan"), 100, 200, 200))

    @pytest.mark.asyncio
    async def test_bbox_exceeding_image_is_clamped(self) -> None:
        """Test that bboxes exceeding image bounds are clamped (NEM-1073)."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.5] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="orange")

        # Bbox exceeds image bounds
        embedding = await service.generate_embedding(image, bbox=(500, 400, 700, 500))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Cropped image should be clamped to (500, 400, 640, 480) = 140x80
        called_image = mock_client.embed.call_args[0][0]
        assert called_image.size == (140, 80)

    @pytest.mark.asyncio
    async def test_completely_outside_bbox_raises_error(self) -> None:
        """Test that bboxes completely outside image raise error (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        mock_client = AsyncMock()
        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="pink")

        # Completely outside image bounds
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(700, 500, 800, 600))

    @pytest.mark.asyncio
    async def test_negative_bbox_is_clamped(self) -> None:
        """Test that negative bbox coordinates are clamped (NEM-1073)."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        mock_client = AsyncMock()
        mock_client.embed.return_value = [0.3] * EMBEDDING_DIMENSION

        service = ReIdentificationService(clip_client=mock_client)
        image = Image.new("RGB", (640, 480), color="cyan")

        # Negative coordinates
        embedding = await service.generate_embedding(image, bbox=(-50, -50, 200, 200))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Cropped image should be clamped to (0, 0, 200, 200)
        called_image = mock_client.embed.call_args[0][0]
        assert called_image.size == (200, 200)


# =============================================================================
# NEM-1122: Detection pipeline bbox clamping tests
# =============================================================================


class TestDetectionBboxClamping:
    """Tests for bounding box clamping in detection pipeline.

    NEM-1122: Add error handling for bounding boxes exceeding image boundaries
    """

    def test_clamp_bbox_exceeding_right_boundary(self) -> None:
        """Test clamping bbox that exceeds right boundary."""
        bbox = (500.0, 100.0, 700.0, 300.0)  # Exceeds 640 width
        result = validate_and_clamp_bbox(bbox, 640, 480)

        assert result.is_valid is True
        assert result.was_clamped is True
        assert result.clamped_bbox is not None
        assert result.clamped_bbox[2] == 640  # Clamped to image width

    def test_clamp_bbox_exceeding_bottom_boundary(self) -> None:
        """Test clamping bbox that exceeds bottom boundary."""
        bbox = (100.0, 400.0, 300.0, 500.0)  # Exceeds 480 height
        result = validate_and_clamp_bbox(bbox, 640, 480)

        assert result.is_valid is True
        assert result.was_clamped is True
        assert result.clamped_bbox is not None
        assert result.clamped_bbox[3] == 480  # Clamped to image height

    def test_clamp_bbox_exceeding_all_boundaries(self) -> None:
        """Test clamping bbox that exceeds all boundaries."""
        bbox = (-50.0, -50.0, 700.0, 500.0)
        result = validate_and_clamp_bbox(bbox, 640, 480)

        assert result.is_valid is True
        assert result.was_clamped is True
        assert result.clamped_bbox == (0, 0, 640, 480)

    def test_bbox_completely_outside_is_invalid(self) -> None:
        """Test that bbox completely outside image is invalid."""
        bbox = (700.0, 500.0, 800.0, 600.0)
        result = validate_and_clamp_bbox(bbox, 640, 480)

        assert result.is_valid is False
        assert result.was_empty_after_clamp is True

    def test_bbox_too_small_after_clamping_is_invalid(self) -> None:
        """Test that bbox too small after clamping is invalid."""
        # Bbox at edge of image that becomes too small
        bbox = (639.0, 479.0, 700.0, 500.0)
        result = validate_and_clamp_bbox(bbox, 640, 480, min_size=5.0)

        assert result.is_valid is False
        assert result.was_empty_after_clamp is True

    def test_valid_bbox_within_bounds_not_clamped(self) -> None:
        """Test that valid bbox within bounds is not modified."""
        bbox = (100.0, 100.0, 300.0, 300.0)
        result = validate_and_clamp_bbox(bbox, 640, 480)

        assert result.is_valid is True
        assert result.was_clamped is False
        assert result.clamped_bbox == bbox
