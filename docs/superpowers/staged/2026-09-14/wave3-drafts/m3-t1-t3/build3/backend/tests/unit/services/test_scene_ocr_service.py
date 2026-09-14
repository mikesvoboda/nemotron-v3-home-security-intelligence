"""Unit tests for SceneOCRService.

Tests cover:
- Dataclass creation and serialization (SceneTextResult, DetectionOCRResult, SceneOCRResult)
- Full frame OCR (mocked HTTP responses)
- Crop OCR (mocked HTTP responses)
- Deduplication logic (IoU > 70% overlap handling)
- Detection association (bbox overlap > 50%)
- Confidence filtering (>=0.80 include, 0.50-0.79 uncertain, <0.50 exclude)
- Service provider matching integration

Reference: docs/plans/2026-02-04-scene-ocr-design.md
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.scene_ocr_service import (
    CONFIDENCE_EXCLUDE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    DETECTION_OVERLAP_THRESHOLD,
    IOU_DEDUP_THRESHOLD,
    DetectionOCRResult,
    RawOCRResult,
    SceneOCRResult,
    SceneOCRService,
    SceneTextResult,
    _calculate_iou,
    _calculate_overlap_ratio,
    _classify_text_type,
    get_scene_ocr_service,
    reset_scene_ocr_service,
)
from backend.services.service_provider_matcher import ServiceMatch

# =============================================================================
# Mock DetectionInput and BoundingBox for testing
# =============================================================================


@dataclass
class MockBoundingBox:
    """Mock BoundingBox for testing."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_int_tuple(self) -> tuple[int, int, int, int]:
        return (int(self.x1), int(self.y1), int(self.x2), int(self.y2))


@dataclass
class MockDetectionInput:
    """Mock DetectionInput for testing."""

    id: int | None
    class_name: str
    confidence: float
    bbox: MockBoundingBox


# =============================================================================
# SceneTextResult Tests
# =============================================================================


class TestSceneTextResult:
    """Tests for SceneTextResult dataclass."""

    def test_scene_text_result_creation(self) -> None:
        """Test SceneTextResult creation with required fields."""
        result = SceneTextResult(
            value="STOP",
            confidence=0.95,
            bbox=(100, 200, 150, 230),
        )

        assert result.value == "STOP"
        assert result.confidence == 0.95
        assert result.bbox == (100, 200, 150, 230)
        assert result.text_type is None
        assert result.is_uncertain is False

    def test_scene_text_result_with_type(self) -> None:
        """Test SceneTextResult with text_type classification."""
        result = SceneTextResult(
            value="123",
            confidence=0.88,
            bbox=(50, 100, 90, 130),
            text_type="house_number",
        )

        assert result.text_type == "house_number"

    def test_scene_text_result_uncertain_confidence(self) -> None:
        """Test SceneTextResult with uncertain confidence flag."""
        result = SceneTextResult(
            value="Main St",
            confidence=0.65,
            bbox=(200, 300, 350, 330),
            text_type="street_sign",
            is_uncertain=True,
        )

        assert result.is_uncertain is True
        assert result.confidence == 0.65

    def test_scene_text_result_to_dict(self) -> None:
        """Test SceneTextResult.to_dict() serialization."""
        result = SceneTextResult(
            value="STOP",
            confidence=0.92,
            bbox=(100, 200, 150, 230),
            text_type="sign",
            is_uncertain=False,
        )

        data = result.to_dict()

        assert data["value"] == "STOP"
        assert data["confidence"] == 0.92
        assert data["bbox"] == [100, 200, 150, 230]
        assert data["type"] == "sign"
        assert "uncertain" not in data

    def test_scene_text_result_to_dict_uncertain(self) -> None:
        """Test SceneTextResult.to_dict() with uncertain flag."""
        result = SceneTextResult(
            value="?",
            confidence=0.55,
            bbox=(0, 0, 10, 10),
            is_uncertain=True,
        )

        data = result.to_dict()

        assert data["uncertain"] is True


# =============================================================================
# DetectionOCRResult Tests
# =============================================================================


class TestDetectionOCRResult:
    """Tests for DetectionOCRResult dataclass."""

    def test_detection_ocr_result_creation(self) -> None:
        """Test DetectionOCRResult creation with required fields."""
        result = DetectionOCRResult(detection_id="det_001")

        assert result.detection_id == "det_001"
        assert result.texts == []
        assert result.service_match is None

    def test_detection_ocr_result_with_texts(self) -> None:
        """Test DetectionOCRResult with text entries."""
        result = DetectionOCRResult(
            detection_id="det_002",
            texts=[
                {"value": "FedEx", "confidence": 0.94, "region": "chest"},
                {"value": "Express", "confidence": 0.89, "region": "chest"},
            ],
        )

        assert len(result.texts) == 2
        assert result.texts[0]["value"] == "FedEx"

    def test_detection_ocr_result_with_service_match(self) -> None:
        """Test DetectionOCRResult with service provider match."""
        service_match = ServiceMatch(
            provider="FedEx",
            category="DELIVERY",
            confidence=0.97,
            risk_modifier="low_risk_service",
        )
        result = DetectionOCRResult(
            detection_id="det_003",
            texts=[{"value": "FedEx", "confidence": 0.94, "region": "side"}],
            service_match=service_match,
        )

        assert result.service_match is not None
        assert result.service_match.provider == "FedEx"

    def test_detection_ocr_result_to_dict(self) -> None:
        """Test DetectionOCRResult.to_dict() serialization."""
        service_match = ServiceMatch(
            provider="Amazon",
            category="DELIVERY",
            confidence=0.95,
            risk_modifier="low_risk_service",
        )
        result = DetectionOCRResult(
            detection_id="det_004",
            texts=[{"value": "Amazon Prime", "confidence": 0.92, "region": "side"}],
            service_match=service_match,
        )

        data = result.to_dict()

        assert data["detection_id"] == "det_004"
        assert len(data["texts"]) == 1
        assert "service_match" in data
        assert data["service_match"]["provider"] == "Amazon"


# =============================================================================
# SceneOCRResult Tests
# =============================================================================


class TestSceneOCRResult:
    """Tests for SceneOCRResult dataclass."""

    def test_scene_ocr_result_empty(self) -> None:
        """Test empty SceneOCRResult creation."""
        result = SceneOCRResult()

        assert result.scene_texts == []
        assert result.detection_ocr == {}
        assert result.processing_time_ms == 0.0

    def test_scene_ocr_result_has_scene_texts(self) -> None:
        """Test has_scene_texts property."""
        empty_result = SceneOCRResult()
        assert empty_result.has_scene_texts is False

        result_with_texts = SceneOCRResult(
            scene_texts=[SceneTextResult(value="123", confidence=0.9, bbox=(0, 0, 10, 10))]
        )
        assert result_with_texts.has_scene_texts is True

    def test_scene_ocr_result_has_detection_ocr(self) -> None:
        """Test has_detection_ocr property."""
        empty_result = SceneOCRResult()
        assert empty_result.has_detection_ocr is False

        result_with_ocr = SceneOCRResult(
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[{"value": "Test", "confidence": 0.9, "region": "chest"}],
                )
            }
        )
        assert result_with_ocr.has_detection_ocr is True

    def test_scene_ocr_result_has_service_matches(self) -> None:
        """Test has_service_matches property."""
        result_without_match = SceneOCRResult(
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[{"value": "Random", "confidence": 0.9, "region": "chest"}],
                )
            }
        )
        assert result_without_match.has_service_matches is False

        result_with_match = SceneOCRResult(
            detection_ocr={
                "det_002": DetectionOCRResult(
                    detection_id="det_002",
                    texts=[{"value": "UPS", "confidence": 0.95, "region": "side"}],
                    service_match=ServiceMatch(
                        provider="UPS",
                        category="DELIVERY",
                        confidence=1.0,
                        risk_modifier="low_risk_service",
                    ),
                )
            }
        )
        assert result_with_match.has_service_matches is True

    def test_scene_ocr_result_to_dict(self) -> None:
        """Test SceneOCRResult.to_dict() serialization."""
        result = SceneOCRResult(
            scene_texts=[
                SceneTextResult(
                    value="STOP",
                    confidence=0.95,
                    bbox=(100, 200, 150, 230),
                    text_type="sign",
                )
            ],
            detection_ocr={
                "det_001": DetectionOCRResult(
                    detection_id="det_001",
                    texts=[{"value": "FedEx", "confidence": 0.94, "region": "chest"}],
                )
            },
            processing_time_ms=150.5,
        )

        data = result.to_dict()

        assert len(data["scene_texts"]) == 1
        assert data["scene_texts"][0]["value"] == "STOP"
        assert "det_001" in data["detection_ocr"]
        assert data["processing_time_ms"] == 150.5


# =============================================================================
# IoU Calculation Tests
# =============================================================================


class TestCalculateIoU:
    """Tests for _calculate_iou function."""

    def test_identical_boxes(self) -> None:
        """Test IoU of identical bounding boxes is 1.0."""
        bbox = (100, 100, 200, 200)
        iou = _calculate_iou(bbox, bbox)
        assert abs(iou - 1.0) < 0.001

    def test_no_overlap(self) -> None:
        """Test IoU of non-overlapping boxes is 0.0."""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (200, 200, 300, 300)
        iou = _calculate_iou(bbox1, bbox2)
        assert iou == 0.0

    def test_partial_overlap(self) -> None:
        """Test IoU of partially overlapping boxes."""
        bbox1 = (0, 0, 100, 100)
        bbox2 = (50, 50, 150, 150)

        # Intersection: 50x50 = 2500
        # Area1: 100x100 = 10000
        # Area2: 100x100 = 10000
        # Union: 10000 + 10000 - 2500 = 17500
        # IoU: 2500 / 17500 = 0.1428...

        iou = _calculate_iou(bbox1, bbox2)
        assert abs(iou - 0.1428) < 0.01

    def test_contained_box(self) -> None:
        """Test IoU when one box is contained within another."""
        outer = (0, 0, 200, 200)
        inner = (50, 50, 150, 150)

        # Intersection: 100x100 = 10000
        # Area outer: 200x200 = 40000
        # Area inner: 100x100 = 10000
        # Union: 40000 + 10000 - 10000 = 40000
        # IoU: 10000 / 40000 = 0.25

        iou = _calculate_iou(outer, inner)
        assert abs(iou - 0.25) < 0.001

    def test_high_iou_threshold(self) -> None:
        """Test that high IoU detects near-duplicate boxes."""
        bbox1 = (100, 100, 200, 200)
        bbox2 = (102, 102, 202, 202)  # Slightly shifted

        iou = _calculate_iou(bbox1, bbox2)
        assert iou > IOU_DEDUP_THRESHOLD  # Should be > 0.70


# =============================================================================
# Overlap Ratio Calculation Tests
# =============================================================================


class TestCalculateOverlapRatio:
    """Tests for _calculate_overlap_ratio function."""

    def test_fully_contained(self) -> None:
        """Test overlap ratio when OCR bbox is fully inside detection."""
        ocr_bbox = (50, 50, 100, 100)
        det_bbox = (0, 0, 200, 200)

        ratio = _calculate_overlap_ratio(ocr_bbox, det_bbox)
        assert abs(ratio - 1.0) < 0.001

    def test_no_overlap(self) -> None:
        """Test overlap ratio when boxes don't overlap."""
        ocr_bbox = (0, 0, 50, 50)
        det_bbox = (100, 100, 200, 200)

        ratio = _calculate_overlap_ratio(ocr_bbox, det_bbox)
        assert ratio == 0.0

    def test_partial_overlap(self) -> None:
        """Test overlap ratio with partial overlap."""
        ocr_bbox = (50, 50, 150, 150)  # 100x100 = 10000
        det_bbox = (100, 100, 200, 200)

        # Intersection: 50x50 = 2500
        # OCR area: 10000
        # Ratio: 2500 / 10000 = 0.25

        ratio = _calculate_overlap_ratio(ocr_bbox, det_bbox)
        assert abs(ratio - 0.25) < 0.001

    def test_threshold_check(self) -> None:
        """Test overlap ratio against association threshold."""
        ocr_bbox = (0, 0, 100, 100)  # 10000
        det_bbox = (25, 25, 200, 200)  # Overlaps 75x75 = 5625

        ratio = _calculate_overlap_ratio(ocr_bbox, det_bbox)
        assert ratio > DETECTION_OVERLAP_THRESHOLD  # > 0.50


# =============================================================================
# Text Type Classification Tests
# =============================================================================


class TestClassifyTextType:
    """Tests for _classify_text_type function."""

    def test_house_number(self) -> None:
        """Test house number classification."""
        assert _classify_text_type("123") == "house_number"
        assert _classify_text_type("5678") == "house_number"
        assert _classify_text_type("1") == "house_number"

    def test_street_sign(self) -> None:
        """Test street sign classification."""
        assert _classify_text_type("Main St") == "street_sign"
        assert _classify_text_type("Oak Avenue") == "street_sign"
        assert _classify_text_type("Elm Blvd") == "street_sign"

    def test_common_signs(self) -> None:
        """Test common sign classification."""
        assert _classify_text_type("STOP") == "sign"
        assert _classify_text_type("YIELD") == "sign"
        assert _classify_text_type("NO PARKING") == "sign"
        assert _classify_text_type("WARNING") == "sign"

    def test_unknown_text(self) -> None:
        """Test unknown text returns None."""
        assert _classify_text_type("FedEx") is None
        assert _classify_text_type("Random Text") is None
        assert _classify_text_type("123456789") is None  # Too long for house number


# =============================================================================
# SceneOCRService Tests
# =============================================================================


class TestSceneOCRService:
    """Tests for SceneOCRService class."""

    @pytest.fixture
    def service(self) -> SceneOCRService:
        """Create a SceneOCRService instance for testing."""
        reset_scene_ocr_service()
        return SceneOCRService(
            florence_url="http://test-florence:8092",
            enabled=True,
        )

    @pytest.fixture
    def test_image(self) -> Image.Image:
        """Create a test image."""
        return Image.new("RGB", (640, 480), color="white")

    @pytest.fixture
    def mock_detections(self) -> list[MockDetectionInput]:
        """Create mock detection inputs."""
        return [
            MockDetectionInput(
                id=1,
                class_name="person",
                confidence=0.92,
                bbox=MockBoundingBox(100, 50, 300, 400),
            ),
            MockDetectionInput(
                id=2,
                class_name="car",
                confidence=0.88,
                bbox=MockBoundingBox(400, 200, 600, 400),
            ),
        ]

    def test_service_initialization(self, service: SceneOCRService) -> None:
        """Test service initializes with correct parameters."""
        assert service.florence_url == "http://test-florence:8092"
        assert service.enabled is True
        assert service.service_matcher is not None

    @pytest.mark.asyncio
    async def test_service_disabled(self) -> None:
        """Test service returns empty result when disabled."""
        service = SceneOCRService(enabled=False)

        # Should return immediately without making HTTP requests
        result = await service.process_frame(Image.new("RGB", (100, 100)), [])

        assert result.scene_texts == []
        assert result.detection_ocr == {}

    @pytest.mark.asyncio
    async def test_full_frame_ocr_success(
        self, service: SceneOCRService, test_image: Image.Image
    ) -> None:
        """Test successful full-frame OCR HTTP request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {"text": "123", "confidence": 0.88, "bbox": [50, 20, 90, 45]},
                {"text": "STOP", "confidence": 0.96, "bbox": [600, 30, 680, 110]},
            ]
        }

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await service._run_full_frame_ocr(test_image)

        assert len(results) == 2
        assert results[0].text == "123"
        assert results[0].confidence == 0.88
        assert results[0].source == "frame"
        assert results[1].text == "STOP"

    @pytest.mark.asyncio
    async def test_full_frame_ocr_filters_low_confidence(
        self, service: SceneOCRService, test_image: Image.Image
    ) -> None:
        """Test that low-confidence OCR results are filtered out."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                {"text": "GOOD", "confidence": 0.85, "bbox": [0, 0, 10, 10]},
                {"text": "BAD", "confidence": 0.30, "bbox": [0, 0, 10, 10]},  # Below threshold
                {"text": "UNCERTAIN", "confidence": 0.60, "bbox": [0, 0, 10, 10]},
            ]
        }

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await service._run_full_frame_ocr(test_image)

        # BAD should be filtered (below CONFIDENCE_EXCLUDE = 0.50)
        assert len(results) == 2
        texts = [r.text for r in results]
        assert "GOOD" in texts
        assert "UNCERTAIN" in texts
        assert "BAD" not in texts

    @pytest.mark.asyncio
    async def test_full_frame_ocr_http_error(
        self, service: SceneOCRService, test_image: Image.Image
    ) -> None:
        """Test graceful handling of HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await service._run_full_frame_ocr(test_image)

        assert results == []

    @pytest.mark.asyncio
    async def test_crop_ocr_filters_relevant_classes(
        self,
        service: SceneOCRService,
        test_image: Image.Image,
        mock_detections: list[MockDetectionInput],
    ) -> None:
        """Test that only relevant detection classes are processed."""
        # Add an irrelevant detection (e.g., "chair")
        mock_detections.append(
            MockDetectionInput(
                id=3,
                class_name="chair",  # Not in ocr_classes
                confidence=0.90,
                bbox=MockBoundingBox(0, 0, 50, 50),
            )
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"regions": []}

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await service._run_crop_ocr(test_image, mock_detections)

        # Chair detection should not trigger OCR call
        # Only person and car should be processed
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_crop_ocr_coordinate_conversion(
        self, service: SceneOCRService, test_image: Image.Image
    ) -> None:
        """Test that crop OCR converts coordinates to frame space."""
        detection = MockDetectionInput(
            id=1,
            class_name="person",
            confidence=0.92,
            bbox=MockBoundingBox(100, 50, 300, 400),  # Crop starts at (100, 50)
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "regions": [
                # Coordinates relative to crop
                {"text": "FedEx", "confidence": 0.94, "bbox": [50, 100, 150, 130]},
            ]
        }

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            results = await service._run_crop_ocr(test_image, [detection])

        # Should convert to frame coordinates: (50+100, 100+50, 150+100, 130+50)
        assert "1" in results
        ocr_result = results["1"][0]
        assert ocr_result.bbox == (150, 150, 250, 180)

    def test_deduplicate_prefers_crop_over_frame(
        self, service: SceneOCRService, mock_detections: list[MockDetectionInput]
    ) -> None:
        """Test deduplication prefers crop OCR over frame OCR when similar confidence."""
        frame_results = [
            RawOCRResult(
                text="FedEx",
                confidence=0.90,
                bbox=(150, 100, 250, 130),
                source="frame",
            )
        ]
        crop_results = {
            "1": [
                RawOCRResult(
                    text="FedEx",
                    confidence=0.91,  # Similar confidence
                    bbox=(148, 98, 252, 132),  # High IoU overlap
                    source="crop",
                    detection_id="1",
                )
            ]
        }

        result = service._deduplicate(frame_results, crop_results, mock_detections)

        # Frame result should be filtered as duplicate
        # Only crop result should remain (in detection_ocr)
        assert len(result.scene_texts) == 0
        assert "1" in result.detection_ocr
        assert len(result.detection_ocr["1"].texts) == 1

    def test_deduplicate_keeps_higher_confidence(
        self, service: SceneOCRService, mock_detections: list[MockDetectionInput]
    ) -> None:
        """Test deduplication keeps higher confidence when significantly different."""
        frame_results = [
            RawOCRResult(
                text="FedEx",
                confidence=0.98,  # Significantly higher
                bbox=(150, 100, 250, 130),
                source="frame",
            )
        ]
        crop_results = {
            "1": [
                RawOCRResult(
                    text="FedEx",
                    confidence=0.80,  # Lower confidence
                    bbox=(148, 98, 252, 132),  # High IoU overlap
                    source="crop",
                    detection_id="1",
                )
            ]
        }

        result = service._deduplicate(frame_results, crop_results, mock_detections)

        # Frame result has higher confidence, so it should be associated with detection
        assert "1" in result.detection_ocr
        # Both results should be present (crop and frame's association)
        texts = result.detection_ocr["1"].texts
        # Crop OCR is always added first, frame may be added if overlap threshold met
        assert len(texts) >= 1

    def test_deduplicate_scene_text_classification(
        self, service: SceneOCRService, mock_detections: list[MockDetectionInput]
    ) -> None:
        """Test that non-overlapping frame OCR becomes scene text."""
        frame_results = [
            RawOCRResult(
                text="123",
                confidence=0.88,
                bbox=(10, 10, 50, 40),  # Far from any detection
                source="frame",
            ),
            RawOCRResult(
                text="STOP",
                confidence=0.96,
                bbox=(600, 30, 680, 110),  # Far from any detection
                source="frame",
            ),
        ]
        crop_results = {}

        result = service._deduplicate(frame_results, crop_results, mock_detections)

        assert len(result.scene_texts) == 2
        assert result.scene_texts[0].value == "123"
        assert result.scene_texts[0].text_type == "house_number"
        assert result.scene_texts[1].value == "STOP"
        assert result.scene_texts[1].text_type == "sign"

    def test_deduplicate_uncertain_confidence_flag(
        self, service: SceneOCRService, mock_detections: list[MockDetectionInput]
    ) -> None:
        """Test that uncertain confidence (0.50-0.79) sets is_uncertain flag."""
        frame_results = [
            RawOCRResult(
                text="Uncertain",
                confidence=0.65,  # In uncertain range
                bbox=(10, 10, 50, 40),
                source="frame",
            ),
            RawOCRResult(
                text="High",
                confidence=0.85,  # Above uncertain range
                bbox=(600, 30, 680, 110),
                source="frame",
            ),
        ]
        crop_results = {}

        result = service._deduplicate(frame_results, crop_results, mock_detections)

        uncertain_texts = [t for t in result.scene_texts if t.value == "Uncertain"]
        high_texts = [t for t in result.scene_texts if t.value == "High"]

        assert len(uncertain_texts) == 1
        assert uncertain_texts[0].is_uncertain is True
        assert len(high_texts) == 1
        assert high_texts[0].is_uncertain is False

    def test_determine_region_chest(self, service: SceneOCRService) -> None:
        """Test region determination for chest area."""
        text_bbox = (150, 200, 250, 250)  # Middle center of detection
        det_bbox = (100, 50, 300, 400)

        region = service._determine_region(text_bbox, det_bbox)
        assert region == "chest"

    def test_determine_region_top(self, service: SceneOCRService) -> None:
        """Test region determination for top area."""
        text_bbox = (150, 60, 250, 100)  # Top of detection
        det_bbox = (100, 50, 300, 400)

        region = service._determine_region(text_bbox, det_bbox)
        assert region == "top"

    def test_determine_region_bottom(self, service: SceneOCRService) -> None:
        """Test region determination for bottom area."""
        text_bbox = (150, 350, 250, 390)  # Bottom of detection
        det_bbox = (100, 50, 300, 400)

        region = service._determine_region(text_bbox, det_bbox)
        assert region == "bottom"

    @pytest.mark.asyncio
    async def test_process_frame_integration(
        self,
        service: SceneOCRService,
        test_image: Image.Image,
        mock_detections: list[MockDetectionInput],
    ) -> None:
        """Test full process_frame integration with mocked HTTP."""
        # Mock responses for frame and crop OCR
        # Florence /ocr-with-regions returns {"regions": [...]}
        frame_response = MagicMock()
        frame_response.status_code = 200
        frame_response.json.return_value = {
            "regions": [
                {"text": "123", "confidence": 0.88, "bbox": [10, 10, 50, 40]},
                {"text": "FedEx", "confidence": 0.90, "bbox": [150, 200, 250, 230]},
            ]
        }

        crop_response = MagicMock()
        crop_response.status_code = 200
        crop_response.json.return_value = {
            "regions": [
                {"text": "FedEx Ground", "confidence": 0.94, "bbox": [50, 150, 150, 180]},
            ]
        }

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            # Default to frame_response, the first call is always the frame OCR
            mock_client.post.return_value = frame_response

            # All calls go to the same Florence /ocr-with-regions endpoint;
            # differentiate by call order (first = frame, rest = crops)
            call_count = 0

            async def mock_post(url: str, **kwargs: object) -> MagicMock:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return frame_response
                return crop_response

            mock_client.post.side_effect = mock_post
            mock_get_client.return_value = mock_client

            result = await service.process_frame(test_image, mock_detections)

        # Should have scene text for "123" (not overlapping with detections)
        assert result.has_scene_texts
        # Should have detection OCR for person/car
        assert result.has_detection_ocr
        # Should have processing time
        assert result.processing_time_ms > 0


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSceneOCRServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_scene_ocr_service_returns_singleton(self) -> None:
        """Test that get_scene_ocr_service returns the same instance."""
        reset_scene_ocr_service()

        service1 = get_scene_ocr_service()
        service2 = get_scene_ocr_service()

        assert service1 is service2

    def test_reset_scene_ocr_service(self) -> None:
        """Test that reset clears the singleton."""
        reset_scene_ocr_service()

        service1 = get_scene_ocr_service()
        reset_scene_ocr_service()
        service2 = get_scene_ocr_service()

        assert service1 is not service2


# =============================================================================
# Confidence Threshold Tests
# =============================================================================


class TestConfidenceThresholds:
    """Tests for confidence threshold constants."""

    def test_confidence_high_threshold(self) -> None:
        """Test CONFIDENCE_HIGH is 0.80."""
        assert CONFIDENCE_HIGH == 0.80

    def test_confidence_low_threshold(self) -> None:
        """Test CONFIDENCE_LOW is 0.50."""
        assert CONFIDENCE_LOW == 0.50

    def test_confidence_exclude_threshold(self) -> None:
        """Test CONFIDENCE_EXCLUDE is 0.50."""
        assert CONFIDENCE_EXCLUDE == 0.50

    def test_iou_dedup_threshold(self) -> None:
        """Test IOU_DEDUP_THRESHOLD is 0.70."""
        assert IOU_DEDUP_THRESHOLD == 0.70

    def test_detection_overlap_threshold(self) -> None:
        """Test DETECTION_OVERLAP_THRESHOLD is 0.50."""
        assert DETECTION_OVERLAP_THRESHOLD == 0.50
