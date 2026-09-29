"""Integration tests for bounding box validation in services.

Tests verify that bbox validation is properly integrated into:
- ReIdentificationService.generate_embedding (NEM-1073)
- Detection pipeline bbox clamping (NEM-1122)

These tests ensure that invalid bounding boxes are handled gracefully
without crashing the services.

R8 S2 removed the third section this file had — the NEM-1102 pins on
EnrichmentClient.estimate_object_distance — because enrichment_client is
deleted and no shipped code calls estimate_object_distance any more. The
NEM-1073 and NEM-1122 subjects are live and stay.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PIL import Image

from backend.services.bbox_validation import (
    InvalidBoundingBoxError,
    validate_and_clamp_bbox,
)

# =============================================================================
# NEM-1073: ReIdentificationService bbox validation tests
# =============================================================================


class TestReIdentificationServiceBboxValidation:
    """Tests for bounding box validation in ReIdentificationService.

    NEM-1073: Add bounding box validation in ReIdentificationService

    The full swap (ledger item 20) moved the producer from an injected CLIP
    client to the resident OSNet handle read off ``osnet_loader`` at call
    time, so these pins drive that seam and assert on the image the
    extractor was handed — the crop contract under test is unchanged.
    """

    @staticmethod
    def _install_extract_seam(monkeypatch):
        """A resident handle plus an extractor double recording images."""
        import numpy as np

        import backend.services.osnet_loader as ol
        from backend.services.osnet_loader import PersonEmbeddingResult

        calls: list = []

        async def _extract(model_dict, image, detection_id=None):
            calls.append(image)
            return PersonEmbeddingResult(
                embedding=np.ones(512, dtype=np.float32),
                detection_id=detection_id,
                model_id="osnet-test@weights@abc123",
            )

        monkeypatch.setattr(
            ol, "get_reid_handle", lambda: {"model": MagicMock(), "transform": MagicMock()}
        )
        monkeypatch.setattr(ol, "extract_person_embedding", _extract)
        return calls

    @pytest.mark.asyncio
    async def test_valid_bbox_crops_image(self, monkeypatch) -> None:
        """Test that valid bounding boxes properly crop the image."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        calls = self._install_extract_seam(monkeypatch)

        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="blue")

        # Valid bbox
        embedding, _belt = await service.generate_embedding(image, bbox=(100, 100, 300, 300))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Verify that a cropped image was passed to the extractor
        assert len(calls) == 1
        assert calls[0].size == (200, 200)  # 300-100 x 300-100

    @pytest.mark.asyncio
    async def test_invalid_bbox_raises_error(self, monkeypatch) -> None:
        """Test that invalid bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        calls = self._install_extract_seam(monkeypatch)
        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="green")

        # Zero-width bbox
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(100, 100, 100, 200))
        # validation happens before extraction — nothing was computed
        assert calls == []

    @pytest.mark.asyncio
    async def test_inverted_bbox_raises_error(self, monkeypatch) -> None:
        """Test that inverted bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        self._install_extract_seam(monkeypatch)
        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="yellow")

        # Inverted bbox (x2 < x1)
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(200, 100, 100, 200))

    @pytest.mark.asyncio
    async def test_nan_bbox_raises_error(self, monkeypatch) -> None:
        """Test that NaN bounding boxes raise InvalidBoundingBoxError (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        self._install_extract_seam(monkeypatch)
        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="purple")

        # NaN in bbox
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(float("nan"), 100, 200, 200))

    @pytest.mark.asyncio
    async def test_bbox_exceeding_image_is_clamped(self, monkeypatch) -> None:
        """Test that bboxes exceeding image bounds are clamped (NEM-1073)."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        calls = self._install_extract_seam(monkeypatch)

        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="orange")

        # Bbox exceeds image bounds
        embedding, _belt = await service.generate_embedding(image, bbox=(500, 400, 700, 500))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Cropped image should be clamped to (500, 400, 640, 480) = 140x80
        assert calls[0].size == (140, 80)

    @pytest.mark.asyncio
    async def test_completely_outside_bbox_raises_error(self, monkeypatch) -> None:
        """Test that bboxes completely outside image raise error (NEM-1073)."""
        from backend.services.reid_service import ReIdentificationService

        calls = self._install_extract_seam(monkeypatch)
        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="pink")

        # Completely outside image bounds
        with pytest.raises(InvalidBoundingBoxError):
            await service.generate_embedding(image, bbox=(700, 500, 800, 600))
        assert calls == []

    @pytest.mark.asyncio
    async def test_negative_bbox_is_clamped(self, monkeypatch) -> None:
        """Test that negative bbox coordinates are clamped (NEM-1073)."""
        from backend.services.reid_service import EMBEDDING_DIMENSION, ReIdentificationService

        calls = self._install_extract_seam(monkeypatch)

        service = ReIdentificationService()
        image = Image.new("RGB", (640, 480), color="cyan")

        # Negative coordinates
        embedding, _belt = await service.generate_embedding(image, bbox=(-50, -50, 200, 200))

        assert len(embedding) == EMBEDDING_DIMENSION
        # Cropped image should be clamped to (0, 0, 200, 200)
        assert calls[0].size == (200, 200)


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
