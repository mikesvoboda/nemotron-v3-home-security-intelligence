"""Unit tests for the EnrichmentQueryService.

Tests cover:
- Querying license plate detections
- Querying face detections
- Querying vehicle data
- Getting enrichment summaries
- Search functionality
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.enrichment_queries import EnrichmentQueryService


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: AsyncMock) -> EnrichmentQueryService:
    """Create an EnrichmentQueryService with mocked session."""
    return EnrichmentQueryService(mock_session)


class TestEnrichmentQueryService:
    """Tests for EnrichmentQueryService."""

    @pytest.mark.asyncio
    async def test_get_license_plate_detections(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying license plate detections."""
        mock_row = MagicMock()
        mock_row.detection_id = 123
        mock_row.camera_id = "front_door"
        mock_row.detected_at = datetime(2026, 1, 23, 14, 30, tzinfo=UTC)
        mock_row.plate_text = "ABC-1234"
        mock_row.plate_confidence = 0.92
        mock_row.ocr_confidence = 0.88
        mock_row.bbox = [100, 200, 300, 250]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_license_plate_detections(
            camera_id="front_door",
            min_confidence=0.8,
        )

        assert len(results) == 1
        assert results[0]["detection_id"] == 123
        assert results[0]["plate_text"] == "ABC-1234"
        assert results[0]["plate_confidence"] == 0.92
        assert results[0]["ocr_confidence"] == 0.88

    @pytest.mark.asyncio
    async def test_get_license_plate_detections_with_date_range(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying license plates with date range."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        start = datetime(2026, 1, 20, tzinfo=UTC)
        end = datetime(2026, 1, 23, tzinfo=UTC)

        results = await service.get_license_plate_detections(
            start_date=start,
            end_date=end,
        )

        # Verify the query was called with parameters
        call_args = mock_session.execute.call_args
        assert call_args is not None
        params = call_args[0][1]
        assert params["start_date"] == start
        assert params["end_date"] == end

    @pytest.mark.asyncio
    async def test_get_face_detections(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying face detections."""
        mock_row = MagicMock()
        mock_row.detection_id = 456
        mock_row.camera_id = "back_door"
        mock_row.detected_at = datetime(2026, 1, 23, 10, 0, tzinfo=UTC)
        mock_row.face_confidence = 0.95
        mock_row.bbox = [150, 50, 200, 120]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_face_detections(
            camera_id="back_door",
            min_confidence=0.9,
        )

        assert len(results) == 1
        assert results[0]["detection_id"] == 456
        assert results[0]["face_confidence"] == 0.95
        assert results[0]["bbox"] == [150, 50, 200, 120]

    @pytest.mark.asyncio
    async def test_get_vehicle_data(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying vehicle classification data."""
        mock_row = MagicMock()
        mock_row.detection_id = 789
        mock_row.camera_id = "driveway"
        mock_row.detected_at = datetime(2026, 1, 23, 8, 0, tzinfo=UTC)
        mock_row.source_detection_id = "1"
        mock_row.vehicle_type = "sedan"
        mock_row.classification_confidence = 0.91
        mock_row.is_commercial = False
        mock_row.has_damage = True
        mock_row.damage_confidence = 0.75

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_vehicle_data(camera_id="driveway")

        assert len(results) == 1
        assert results[0]["detection_id"] == 789
        assert results[0]["vehicle_type"] == "sedan"
        assert results[0]["is_commercial"] is False
        assert results[0]["has_damage"] is True
        assert results[0]["damage_confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_get_detection_enrichment_summary(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test getting enrichment summary for a detection."""
        mock_row = MagicMock()
        mock_row.detection_id = 100
        mock_row.has_license_plates = True
        mock_row.license_plate_count = 1
        mock_row.has_faces = True
        mock_row.face_count = 2
        mock_row.has_violence_detection = True
        mock_row.is_violent = False
        mock_row.has_vehicle_classification = True
        mock_row.vehicle_types = ["sedan", "suv"]
        mock_row.has_pet_classification = False
        mock_row.has_image_quality = True
        mock_row.image_quality_score = 85.0
        mock_row.processing_time_ms = 125.5
        mock_row.error_count = 0

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        result = await service.get_detection_enrichment_summary(detection_id=100)

        assert result is not None
        assert result["detection_id"] == 100
        assert result["has_license_plates"] is True
        assert result["license_plate_count"] == 1
        assert result["has_faces"] is True
        assert result["face_count"] == 2
        assert result["is_violent"] is False
        assert result["vehicle_types"] == ["sedan", "suv"]
        assert result["image_quality_score"] == 85.0
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_get_detection_enrichment_summary_not_found(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test getting enrichment summary for non-existent detection."""
        mock_row = MagicMock()
        mock_row.detection_id = None  # Indicates not found

        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        result = await service.get_detection_enrichment_summary(detection_id=99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_enrichment_statistics(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test getting aggregated enrichment statistics."""
        mock_row = MagicMock()
        mock_row.camera_id = "front_door"
        mock_row.total_detections = 1000
        mock_row.with_license_plates = 50
        mock_row.with_faces = 200
        mock_row.with_violence_detection = 100
        mock_row.violent_detections = 2
        mock_row.with_vehicle_classification = 80
        mock_row.with_pet_classification = 30
        mock_row.with_image_quality = 950
        mock_row.avg_quality_score = 75.5
        mock_row.avg_processing_time_ms = 120.0
        mock_row.with_errors = 5

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_enrichment_statistics(camera_id="front_door")

        assert len(results) == 1
        assert results[0]["camera_id"] == "front_door"
        assert results[0]["total_detections"] == 1000
        assert results[0]["with_license_plates"] == 50
        assert results[0]["violent_detections"] == 2
        assert results[0]["avg_quality_score"] == 75.5

    @pytest.mark.asyncio
    async def test_search_license_plates(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test searching for license plates by text."""
        mock_row = MagicMock()
        mock_row.detection_id = 111
        mock_row.camera_id = "driveway"
        mock_row.detected_at = datetime(2026, 1, 23, tzinfo=UTC)
        mock_row.plate_text = "ABC-1234"
        mock_row.plate_confidence = 0.92
        mock_row.ocr_confidence = 0.88
        mock_row.bbox = [100, 200, 300, 250]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.search_license_plates(
            plate_text="ABC",
            camera_id="driveway",
        )

        assert len(results) == 1
        assert results[0]["plate_text"] == "ABC-1234"

        # Verify pattern was passed correctly
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["plate_pattern"] == "%ABC%"

    @pytest.mark.asyncio
    async def test_get_violent_detections(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying violent detections."""
        mock_row = MagicMock()
        mock_row.detection_id = 222
        mock_row.camera_id = "front_door"
        mock_row.detected_at = datetime(2026, 1, 23, tzinfo=UTC)
        mock_row.object_type = "person"
        mock_row.confidence = 0.9
        mock_row.is_violent = True
        mock_row.violence_confidence = 0.85
        mock_row.predicted_class = "fight"

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_violent_detections()

        assert len(results) == 1
        assert results[0]["detection_id"] == 222
        assert results[0]["is_violent"] is True
        assert results[0]["violence_confidence"] == 0.85
        assert results[0]["predicted_class"] == "fight"

    @pytest.mark.asyncio
    async def test_get_low_quality_detections(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test querying low quality detections."""
        mock_row = MagicMock()
        mock_row.detection_id = 333
        mock_row.camera_id = "garage"
        mock_row.detected_at = datetime(2026, 1, 23, tzinfo=UTC)
        mock_row.object_type = "person"
        mock_row.quality_score = 35.0
        mock_row.is_blurry = True
        mock_row.is_low_quality = True
        mock_row.quality_issues = ["blur", "dark"]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        mock_session.execute.return_value = mock_result

        results = await service.get_low_quality_detections(
            max_quality_score=50.0,
        )

        assert len(results) == 1
        assert results[0]["detection_id"] == 333
        assert results[0]["quality_score"] == 35.0
        assert results[0]["is_blurry"] is True
        assert results[0]["quality_issues"] == ["blur", "dark"]

    @pytest.mark.asyncio
    async def test_empty_results(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test handling empty results."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        results = await service.get_license_plate_detections()

        assert results == []

    @pytest.mark.asyncio
    async def test_limit_parameter(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test that limit parameter is passed correctly."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await service.get_license_plate_detections(limit=25)

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 25

    @pytest.mark.asyncio
    async def test_default_parameters(
        self, service: EnrichmentQueryService, mock_session: AsyncMock
    ) -> None:
        """Test that default parameters work correctly."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await service.get_license_plate_detections()

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["camera_id"] is None
        assert params["start_date"] is None
        assert params["end_date"] is None
        assert params["min_confidence"] == 0.0
        assert params["limit"] == 100
