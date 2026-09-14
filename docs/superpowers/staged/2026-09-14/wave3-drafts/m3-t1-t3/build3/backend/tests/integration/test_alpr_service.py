"""Integration tests for the ALPR (Automatic License Plate Recognition) service.

These tests verify the complete ALPR workflow including:
- Plate text extraction using PaddleOCR (mocked for CI)
- Database operations for plate reads
- Search and filtering functionality
- Statistics computation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.plate_read import (
    PlateReadCreate,
    PlateReadListResponse,
    PlateRecognizeResponse,
    PlateStatisticsResponse,
)
from backend.models.plate_read import PlateRead
from backend.services.alpr_service import (
    ALPRService,
    get_alpr_service,
    reset_alpr_service,
)


@pytest.fixture
def mock_plate_ocr():
    """Create a mock PlateOCR instance for testing without GPU."""

    class MockPlateOCRResult:
        def __init__(
            self,
            plate_text: str = "ABC1234",
            raw_text: str = "ABC-1234",
            ocr_confidence: float = 0.95,
            image_quality_score: float = 0.85,
            is_enhanced: bool = False,
            is_blurry: bool = False,
        ):
            self.plate_text = plate_text
            self.raw_text = raw_text
            self.ocr_confidence = ocr_confidence
            self.char_confidences = [ocr_confidence] * len(raw_text)
            self.image_quality_score = image_quality_score
            self.is_enhanced = is_enhanced
            self.is_blurry = is_blurry

    class MockPlateOCR:
        def __init__(self, use_gpu=None, lang=None):
            self.use_gpu = use_gpu
            self.lang = lang
            self.model_loaded = False

        def load_model(self):
            self.model_loaded = True
            return self

        def unload(self):
            self.model_loaded = False

        def recognize_text(self, plate_crop, auto_enhance=True):
            # Return mock result based on image properties
            return MockPlateOCRResult()

    with patch(
        "backend.services.alpr_service._PlateOCRHolder._instance",
        None,
    ):
        with patch(
            "ai.enrichment.models.plate_ocr.PlateOCR",
            MockPlateOCR,
        ):
            yield MockPlateOCR


@pytest.fixture
def sample_plate_create() -> PlateReadCreate:
    """Create a sample plate read for testing."""
    return PlateReadCreate(
        camera_id="driveway",
        timestamp=datetime.now(UTC),
        plate_text="ABC1234",
        raw_text="ABC-1234",
        detection_confidence=0.95,
        ocr_confidence=0.92,
        bbox=[100.0, 200.0, 250.0, 240.0],
        image_quality_score=0.85,
        is_enhanced=False,
        is_blurry=False,
    )


@pytest.fixture
def sample_image_data() -> bytes:
    """Create sample image bytes for testing."""
    # Create a simple 100x50 white image
    from io import BytesIO

    from PIL import Image

    img = Image.new("RGB", (100, 50), color="white")
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.integration
class TestALPRServiceCreate:
    """Tests for creating plate read records."""

    async def test_create_plate_read_success(
        self,
        db_session: AsyncSession,
        test_camera,
        sample_plate_create: PlateReadCreate,
    ):
        """Test successfully creating a plate read record."""
        # Use the test camera ID
        sample_plate_create.camera_id = test_camera.id

        service = get_alpr_service(db_session)
        result = await service.create_plate_read(sample_plate_create)

        assert result.id is not None
        assert result.plate_text == "ABC1234"
        assert result.raw_text == "ABC-1234"
        assert result.ocr_confidence == 0.92
        assert result.camera_id == test_camera.id

        # Verify persisted in database
        stmt = select(PlateRead).where(PlateRead.id == result.id)
        db_result = await db_session.execute(stmt)
        plate_read = db_result.scalar_one()
        assert plate_read.plate_text == "ABC1234"

    async def test_create_plate_read_validates_bbox(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test that bbox must have exactly 4 elements."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            PlateReadCreate(
                camera_id=test_camera.id,
                timestamp=datetime.now(UTC),
                plate_text="ABC1234",
                raw_text="ABC1234",
                detection_confidence=0.95,
                ocr_confidence=0.92,
                bbox=[100.0, 200.0],  # Invalid - only 2 elements
                image_quality_score=0.85,
            )

        assert "bbox" in str(exc_info.value)


@pytest.mark.integration
class TestALPRServiceQuery:
    """Tests for querying plate read records."""

    async def test_get_plate_read_by_id(
        self,
        db_session: AsyncSession,
        test_camera,
        sample_plate_create: PlateReadCreate,
    ):
        """Test retrieving a plate read by ID."""
        sample_plate_create.camera_id = test_camera.id
        service = get_alpr_service(db_session)

        # Create a plate read
        created = await service.create_plate_read(sample_plate_create)
        await db_session.commit()

        # Retrieve it
        result = await service.get_plate_read(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.plate_text == created.plate_text

    async def test_get_plate_read_not_found(
        self,
        db_session: AsyncSession,
    ):
        """Test that get_plate_read returns None for non-existent ID."""
        service = get_alpr_service(db_session)
        result = await service.get_plate_read(99999)
        assert result is None

    async def test_get_plate_reads_paginated(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test paginated retrieval of plate reads."""
        service = get_alpr_service(db_session)

        # Create multiple plate reads
        for i in range(5):
            plate_read = PlateRead(
                camera_id=test_camera.id,
                timestamp=datetime.now(UTC) - timedelta(minutes=i),
                plate_text=f"ABC{i:04d}",
                raw_text=f"ABC-{i:04d}",
                detection_confidence=0.95,
                ocr_confidence=0.90,
                bbox=[100.0, 200.0, 250.0, 240.0],
                image_quality_score=0.85,
                is_enhanced=False,
                is_blurry=False,
            )
            db_session.add(plate_read)
        await db_session.commit()

        # Get first page
        result = await service.get_plate_reads(page=1, page_size=2)

        assert isinstance(result, PlateReadListResponse)
        assert len(result.plate_reads) == 2
        assert result.total == 5
        assert result.page == 1
        assert result.page_size == 2

    async def test_get_plate_reads_filter_by_camera(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test filtering plate reads by camera ID."""
        service = get_alpr_service(db_session)

        # Create plate read for test camera
        plate_read = PlateRead(
            camera_id=test_camera.id,
            timestamp=datetime.now(UTC),
            plate_text="XYZ9999",
            raw_text="XYZ-9999",
            detection_confidence=0.95,
            ocr_confidence=0.90,
            bbox=[100.0, 200.0, 250.0, 240.0],
            image_quality_score=0.85,
            is_enhanced=False,
            is_blurry=False,
        )
        db_session.add(plate_read)
        await db_session.commit()

        # Filter by camera
        result = await service.get_plate_reads(camera_id=test_camera.id)

        assert result.total >= 1
        assert all(pr.camera_id == test_camera.id for pr in result.plate_reads)

    async def test_get_plate_reads_filter_by_time_range(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test filtering plate reads by time range."""
        service = get_alpr_service(db_session)
        now = datetime.now(UTC)

        # Create plate reads at different times
        for hours_ago in [1, 3, 5]:
            plate_read = PlateRead(
                camera_id=test_camera.id,
                timestamp=now - timedelta(hours=hours_ago),
                plate_text=f"TIME{hours_ago}",
                raw_text=f"TIME-{hours_ago}",
                detection_confidence=0.95,
                ocr_confidence=0.90,
                bbox=[100.0, 200.0, 250.0, 240.0],
                image_quality_score=0.85,
                is_enhanced=False,
                is_blurry=False,
            )
            db_session.add(plate_read)
        await db_session.commit()

        # Filter to last 2 hours
        result = await service.get_plate_reads(
            start_time=now - timedelta(hours=2),
            end_time=now,
        )

        # Should only get the 1-hour-ago plate
        assert all(pr.timestamp >= now - timedelta(hours=2) for pr in result.plate_reads)


@pytest.mark.integration
class TestALPRServiceSearch:
    """Tests for searching plate reads by text."""

    async def test_search_by_plate_text_partial(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test partial text search for plates."""
        service = get_alpr_service(db_session)

        # Create plate reads with similar text
        for suffix in ["1234", "1235", "5678"]:
            plate_read = PlateRead(
                camera_id=test_camera.id,
                timestamp=datetime.now(UTC),
                plate_text=f"ABC{suffix}",
                raw_text=f"ABC-{suffix}",
                detection_confidence=0.95,
                ocr_confidence=0.90,
                bbox=[100.0, 200.0, 250.0, 240.0],
                image_quality_score=0.85,
                is_enhanced=False,
                is_blurry=False,
            )
            db_session.add(plate_read)
        await db_session.commit()

        # Search for "123" (partial match)
        result = await service.search_by_plate_text("123", exact=False)

        # Should match ABC1234 and ABC1235
        matching_texts = {pr.plate_text for pr in result.plate_reads}
        assert "ABC1234" in matching_texts
        assert "ABC1235" in matching_texts
        assert "ABC5678" not in matching_texts

    async def test_search_by_plate_text_exact(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test exact text search for plates."""
        service = get_alpr_service(db_session)

        # Create plate reads
        plate_read = PlateRead(
            camera_id=test_camera.id,
            timestamp=datetime.now(UTC),
            plate_text="EXACT123",
            raw_text="EXACT-123",
            detection_confidence=0.95,
            ocr_confidence=0.90,
            bbox=[100.0, 200.0, 250.0, 240.0],
            image_quality_score=0.85,
            is_enhanced=False,
            is_blurry=False,
        )
        db_session.add(plate_read)
        await db_session.commit()

        # Exact search should find it
        result = await service.search_by_plate_text("EXACT123", exact=True)
        assert result.total >= 1
        assert any(pr.plate_text == "EXACT123" for pr in result.plate_reads)

        # Partial search with exact=True should not find partial matches
        result = await service.search_by_plate_text("EXACT", exact=True)
        assert not any(pr.plate_text == "EXACT123" for pr in result.plate_reads)


@pytest.mark.integration
class TestALPRServiceStatistics:
    """Tests for plate recognition statistics."""

    async def test_get_statistics_empty(
        self,
        db_session: AsyncSession,
    ):
        """Test statistics with no plate reads."""
        service = get_alpr_service(db_session)
        stats = await service.get_statistics()

        assert isinstance(stats, PlateStatisticsResponse)
        assert stats.total_reads >= 0
        assert stats.unique_plates >= 0

    async def test_get_statistics_with_data(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test statistics with plate read data."""
        service = get_alpr_service(db_session)
        now = datetime.now(UTC)

        # Create plate reads with various attributes
        plate_reads_data = [
            {
                "plate_text": "STAT001",
                "ocr_confidence": 0.95,
                "is_enhanced": True,
                "is_blurry": False,
            },
            {
                "plate_text": "STAT002",
                "ocr_confidence": 0.85,
                "is_enhanced": False,
                "is_blurry": True,
            },
            {
                "plate_text": "STAT001",
                "ocr_confidence": 0.90,
                "is_enhanced": False,
                "is_blurry": False,
            },  # Duplicate plate
        ]

        for i, data in enumerate(plate_reads_data):
            plate_read = PlateRead(
                camera_id=test_camera.id,
                timestamp=now - timedelta(minutes=i),
                plate_text=data["plate_text"],
                raw_text=data["plate_text"],
                detection_confidence=0.95,
                ocr_confidence=data["ocr_confidence"],
                bbox=[100.0, 200.0, 250.0, 240.0],
                image_quality_score=0.85,
                is_enhanced=data["is_enhanced"],
                is_blurry=data["is_blurry"],
            )
            db_session.add(plate_read)
        await db_session.commit()

        stats = await service.get_statistics()

        assert stats.total_reads >= 3
        assert stats.unique_plates >= 2  # STAT001 and STAT002
        assert stats.enhanced_count >= 1
        assert stats.blurry_count >= 1
        assert stats.reads_last_hour >= 3


@pytest.mark.integration
class TestALPRServiceRetention:
    """Tests for plate read retention and cleanup."""

    async def test_prune_old_reads(
        self,
        db_session: AsyncSession,
        test_camera,
    ):
        """Test pruning old plate reads."""
        service = ALPRService(db_session, retention_days=7)
        now = datetime.now(UTC)

        # Create old and new plate reads
        old_read = PlateRead(
            camera_id=test_camera.id,
            timestamp=now - timedelta(days=10),
            plate_text="OLD0001",
            raw_text="OLD-0001",
            detection_confidence=0.95,
            ocr_confidence=0.90,
            bbox=[100.0, 200.0, 250.0, 240.0],
            image_quality_score=0.85,
            is_enhanced=False,
            is_blurry=False,
        )
        new_read = PlateRead(
            camera_id=test_camera.id,
            timestamp=now - timedelta(days=1),
            plate_text="NEW0001",
            raw_text="NEW-0001",
            detection_confidence=0.95,
            ocr_confidence=0.90,
            bbox=[100.0, 200.0, 250.0, 240.0],
            image_quality_score=0.85,
            is_enhanced=False,
            is_blurry=False,
        )
        db_session.add(old_read)
        db_session.add(new_read)
        await db_session.commit()

        old_id = old_read.id
        new_id = new_read.id

        # Prune old reads
        deleted_count = await service.prune_old_reads()
        await db_session.commit()

        # Verify old read is deleted
        old_result = await db_session.execute(select(PlateRead).where(PlateRead.id == old_id))
        assert old_result.scalar_one_or_none() is None

        # Verify new read still exists
        new_result = await db_session.execute(select(PlateRead).where(PlateRead.id == new_id))
        assert new_result.scalar_one_or_none() is not None


@pytest.mark.integration
class TestALPRServiceRecognition:
    """Tests for plate recognition with OCR (mocked)."""

    async def test_recognize_and_store_success(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """Test recognition and storage of a plate image."""
        # Reset the singleton to ensure mock is used
        reset_alpr_service()

        service = get_alpr_service(db_session)

        with patch("backend.services.alpr_service._PlateOCRHolder.get") as mock_get:
            mock_ocr = mock_plate_ocr()
            mock_ocr.load_model()
            mock_get.return_value = mock_ocr

            result = await service.recognize_and_store(
                camera_id=test_camera.id,
                image_data=sample_image_data,
                bbox=[100.0, 200.0, 250.0, 240.0],
                detection_confidence=0.95,
                store=True,
            )

            assert isinstance(result, PlateRecognizeResponse)
            assert result.plate_text == "ABC1234"
            assert result.ocr_confidence == 0.95
            assert result.stored is True
            assert result.plate_read_id is not None

    async def test_recognize_without_storage(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """Test recognition without storing to database."""
        reset_alpr_service()

        service = get_alpr_service(db_session)

        with patch("backend.services.alpr_service._PlateOCRHolder.get") as mock_get:
            mock_ocr = mock_plate_ocr()
            mock_ocr.load_model()
            mock_get.return_value = mock_ocr

            result = await service.recognize_and_store(
                camera_id=test_camera.id,
                image_data=sample_image_data,
                bbox=[100.0, 200.0, 250.0, 240.0],
                detection_confidence=0.95,
                store=False,
            )

            assert result.stored is False
            assert result.plate_read_id is None


@pytest.fixture
def test_camera(db_session: AsyncSession):
    """Create a test camera for ALPR tests."""
    from backend.models.camera import Camera

    camera = Camera(
        id="test_alpr_camera",
        name="Test ALPR Camera",
        folder_path="/test/alpr",
        status="online",
    )
    db_session.add(camera)
    return camera
