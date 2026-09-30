"""Integration tests for the ALPR (Automatic License Plate Recognition) service.

These tests verify the complete ALPR workflow including:
- Plate text recognition driven through the service's plate-OCR seam (driven by
  a stand-in engine injected at the one seam the shipped code still offers)
- Database operations for plate reads
- Search and filtering functionality
- Statistics computation

R8 S3 (owner ruling 4 — every retired serving dir swept) is the reason the
recognition half of this file reads the way it does. The OCR engine used to be
``ai/enrichment/models/plate_ocr.py::PlateOCR``; that module is deleted, so
nothing here imports, patches or names it as a live seam any more. What SURVIVES
is the ALPR service itself (``backend/services/alpr_service.py`` is MODIFIED in
this slice, not deleted): the plate-read storage half — create / query / search
/ statistics / retention — is DB lookup work the VLM path keeps, and the
recognize half keeps its machinery (crop, confidence gate, store-or-not branch,
response schema, and the route's ImportError -> 503 mapping at
``backend/api/routes/plate_reads.py:325-333``) with the engine itself only
reachable by injection. ``TestALPROcrEngineRetirement`` below pins the retired
half against live forms and proves its own non-vacuity.
"""

import base64
import importlib
import importlib.util
import pathlib
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.plate_read import (
    PlateReadCreate,
    PlateReadListResponse,
    PlateRecognizeRequest,
    PlateRecognizeResponse,
    PlateStatisticsResponse,
)
from backend.models.plate_read import PlateRead
from backend.services.alpr_service import (
    ALPRService,
    _PlateOCRHolder,
    get_alpr_service,
    reset_alpr_service,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


_SHIPPED_ROOTS = ("backend", "ai", "scripts", "services")
_SKIP_PARTS = {"tests", "__pycache__", "archive", ".venv", "node_modules"}


def _shipped_python_files() -> list[pathlib.Path]:
    """Every shipped python file, excluding test trees, caches and archives.

    Test trees are out of scope deliberately: a stand-in engine class inside a
    test file is not an engine the service can build, so a definition scan that
    counted this file's own stand-in would report a phantom.
    """
    files: list[pathlib.Path] = []
    for root in _SHIPPED_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if _SKIP_PARTS & set(path.parts):
                continue
            files.append(path)
    return files


class StandInPlateOCR:
    """A plate-OCR engine stand-in installed at the LIVE injection seam.

    R8 S3 retired the module that used to produce one, so
    ``_PlateOCRHolder`` no longer constructs an engine — it returns whatever has
    been injected and raises ``ImportError`` when nothing has
    (backend/services/alpr_service.py:548-562). The stand-in therefore has to be
    injected, not patched over the deleted import. It records the crop it was
    handed so a test can prove the recognize leg's geometry is still live.
    """

    last_crop = None

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
        StandInPlateOCR.last_crop = plate_crop
        return _StandInResult()


class _StandInResult:
    """Exactly the fields ``ALPRService`` reads off an engine result.

    Mirrored from the LIVE consumers — backend/services/alpr_service.py:151-189
    (plate_text, raw_text, ocr_confidence, image_quality_score, is_enhanced,
    is_blurry) — and deliberately no wider: the pre-S3 stand-in also carried a
    ``char_confidences`` attribute nothing in the shipped service ever read, and
    a stand-in wider than its consumer hides field removals.
    """

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
        self.image_quality_score = image_quality_score
        self.is_enhanced = is_enhanced
        self.is_blurry = is_blurry


@pytest.fixture
def mock_plate_ocr():
    """Hand the test a plate-OCR engine stand-in, against a clean holder.

    Setup clears the holder and teardown clears it again, so a test that
    injects cannot leak an engine into the shipped-build pins (and a pin that
    asserts the shipped build has NO engine can trust that it is watching the
    shipped build, not a neighbor's leftover). Each test then builds and injects
    its own instance — the same shape of drive the file had before S3, with the
    deleted-module patch taken out.
    """

    _PlateOCRHolder._instance = None
    try:
        yield StandInPlateOCR
    finally:
        StandInPlateOCR.last_crop = None
        _PlateOCRHolder._instance = None


def _make_image_bytes(width: int = 100, height: int = 50) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (width, height), color="white")
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


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
    """Sample image bytes for testing (100x50, matching the tests' bbox)."""
    return _make_image_bytes()


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
    """Plate recognition driven through the injection seam that survives S3.

    RETARGETED (R8 S3, owner ruling 4). What the pre-S3 drive pinned, and what
    still ships:

      * ``backend/services/alpr_service.py`` was MODIFIED by S3, not deleted.
        ``recognize_and_store`` still decodes the frame, clamps the bbox to the
        image, crops (lines 119-136), calls the engine at line 139, gates the
        write on ``plate_text`` + ``min_ocr_confidence`` (line 151), and builds a
        ``PlateRecognizeResponse`` (lines 181-190);
      * what died is only the ENGINE. ``_PlateOCRHolder`` can no longer build
        one — the module that had ``PlateOCR`` was swept with the rest of the
        retired serving tier — so ``get()`` raises ``ImportError`` unless
        something is injected (lines 548-562).

    So the drive moved from ``patch("ai.enrichment.models.plate_ocr.PlateOCR")``
    (a module that no longer exists, which is what errored at setup) onto the
    seam the service actually reads: assign ``_PlateOCRHolder._instance``. No
    assertion below was weakened; the crop geometry and the "did the row
    actually get written" checks are new, and they are what keep these two pins
    from passing if the recognize leg is gutted.
    """

    async def test_recognize_and_store_success(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """Test recognition and storage of a plate image."""
        # Reset the singleton to ensure the injected engine is used. reset_alpr_service()
        # also resets the OCR holder (alpr_service.py:645-648), so inject AFTER it.
        reset_alpr_service()
        engine = mock_plate_ocr()
        engine.load_model()
        _PlateOCRHolder._instance = engine

        service = get_alpr_service(db_session)

        # bbox inside the 100x50 frame, so the crop step really fires.
        result = await service.recognize_and_store(
            camera_id=test_camera.id,
            image_data=sample_image_data,
            bbox=[10.0, 10.0, 60.0, 40.0],
            detection_confidence=0.95,
            store=True,
        )

        assert isinstance(result, PlateRecognizeResponse)
        assert result.plate_text == "ABC1234"
        assert result.ocr_confidence == 0.95
        assert result.stored is True
        assert result.plate_read_id is not None

        # Live-geometry half: the engine was handed the bbox-cropped region, not
        # the whole frame. 100x50 frame, bbox (10,10)-(60,40) => a 30-row x 50-col
        # crop; an engine handed the unclipped frame would see 50x100. So this
        # assertion is satisfied only by the shipped clamp-and-crop code
        # (alpr_service.py:126-136) actually running.
        crop = mock_plate_ocr.last_crop
        assert crop is not None, "the engine was never driven; recognize is a stub"
        assert crop.shape[0] == 30 and crop.shape[1] == 50, crop.shape

        # The row the response advertises exists in the database.
        stmt = select(PlateRead).where(PlateRead.id == result.plate_read_id)
        row = (await db_session.execute(stmt)).scalar_one()
        assert row.plate_text == "ABC1234"
        assert row.raw_text == "ABC-1234"
        assert row.camera_id == test_camera.id

    async def test_recognize_without_storage(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """Test recognition without storing to database."""
        reset_alpr_service()
        engine = mock_plate_ocr()
        engine.load_model()
        _PlateOCRHolder._instance = engine

        before = (
            (
                await db_session.execute(
                    select(PlateRead).where(PlateRead.camera_id == test_camera.id)
                )
            )
            .scalars()
            .all()
        )

        service = get_alpr_service(db_session)

        result = await service.recognize_and_store(
            camera_id=test_camera.id,
            image_data=sample_image_data,
            bbox=[100.0, 200.0, 250.0, 240.0],
            detection_confidence=0.95,
            store=False,
        )

        assert result.stored is False
        assert result.plate_read_id is None
        # Non-vacuity for ``stored is False``: the read is still returned, and no
        # row was written. A recognize path that always wrote (or never wrote)
        # fails one half of this pair.
        assert result.plate_text == "ABC1234"
        assert result.ocr_confidence == 0.95
        after = (
            (
                await db_session.execute(
                    select(PlateRead).where(PlateRead.camera_id == test_camera.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(list(after)) == len(list(before))


@pytest.mark.integration
class TestALPROcrEngineRetirement:
    """TOMBSTONE: the plate-OCR ENGINE, not the ALPR service.

    What used to be true (pre-R8 S3): ``_PlateOCRHolder.get()`` built a
    ``PlateOCR`` from ``ai/enrichment/models/plate_ocr.py`` on first use, so
    ``ALPRService.recognize_and_store`` and ``POST /api/plate-reads/recognize``
    could recognize a plate on a shipped build with no injection at all, and a
    test could patch the class where it was imported.

    Why it died: owner ruling 4 in the R8 S3 scope packet swept EVERY retired
    serving directory, and ``ai/enrichment`` was one of them. The recognizing
    module is deleted (``git ls-files`` reports no ``ai/enrichment`` paths), so
    there is no engine to build and no module to patch.

    What deliberately SURVIVES, and is pinned live by the recognition class
    above: the whole plate-read record half (create/query/search/statistics/
    retention — DB lookups the VLM path keeps) and the recognize leg's
    MACHINERY, whose engine is now reachable only by injection.
    ``_PlateOCRHolder`` answers ``ImportError`` while nothing is injected, and
    the route maps that to 503 (backend/api/routes/plate_reads.py:325-333) — an
    accurate answer for a retired model rather than a 500.

    Vacuity statement, so this class has to earn its green: every absence below
    would ALSO pass if ``backend/services/alpr_service.py`` itself were deleted,
    if ``ai/`` were emptied, if the recognize path were gutted so that nothing
    could ever reach an engine again, or if the source corpus scan found no
    files at all. Each of those is pinned against, in the last three tests.
    """

    def test_plate_ocr_engine_module_is_gone_from_live_forms(self):
        """Absence, asserted against live forms only: file absence, forced
        import failure, and the absence of any engine definition in shipped
        source — never a text grep for a dead spelling of a live thing."""
        # (a) the swept serving dir is off disk.
        assert not (REPO_ROOT / "ai/enrichment").exists()
        assert not (REPO_ROOT / "ai/enrichment/models/plate_ocr.py").exists()
        # (b) import fails, and not with a bare "no attribute" — the package
        # itself is gone, so even resolving the name is impossible.
        with pytest.raises(ModuleNotFoundError, match=r"ai\.enrichment"):
            importlib.import_module("ai.enrichment.models.plate_ocr")
        with pytest.raises(ModuleNotFoundError):
            importlib.util.find_spec("ai.enrichment.models.plate_ocr")
        # (c) nothing in shipped source defines a plate-OCR engine any more, so
        # no code path can produce one.
        corpus = _shipped_python_files()
        # Measured 718 files at write time. The floor sits well below that so an
        # unrelated refactor cannot bite, and far above a collapsed scan — an
        # empty or trivially small corpus is the failure mode where "no shipped
        # file defines PlateOCR" stops meaning anything.
        assert len(corpus) > 400, (
            f"shipped corpus scan found only {len(corpus)} files; the absence below is vacuous"
        )
        alpr_path = REPO_ROOT / "backend/services/alpr_service.py"
        assert alpr_path in corpus, (
            "the ALPR service itself left the scanned corpus; this absence no longer covers it"
        )
        definitions = [
            p for p in corpus if "class PlateOCR" in p.read_text(encoding="utf-8", errors="replace")
        ]
        assert definitions == [], [str(p.relative_to(REPO_ROOT)) for p in definitions]

    def test_recognize_without_injection_raises_importerror(self):
        """Absence at the live seam: with nothing injected, ``get()`` refuses.

        The refusal is pinned as a TYPE plus a non-empty, actionable-in-the-right-
        way message; the exact sentence stays free, because the route already
        documents its 503 detail as unpinned wording (plate_reads.py:326-330).
        """
        _PlateOCRHolder._instance = None
        assert _PlateOCRHolder._instance is None, (
            "an engine leaked from another test; the raise below is not the shipped-build answer"
        )
        with pytest.raises(ImportError) as exc_info:
            _PlateOCRHolder.get()
        assert str(exc_info.value).strip(), "the refusal says nothing an operator can act on"

    async def test_recognize_on_shipped_build_raises_importerror(
        self,
        db_session: AsyncSession,
        test_camera,
        sample_image_data: bytes,
    ):
        """The shipped build's recognize call raises ImportError end-to-end.

        The message is pinned by its HAZARD, not its wording: alpr_service.py
        :527-533 argues the refusal must name the retirement rather than tell an
        operator to install a package, because the file is deleted rather than
        absent from the environment. So this asserts the advice is absent —
        install-the-back-end prose is the regression it catches — and leaves the
        sentence itself free to be reworded toward more truth.
        """
        reset_alpr_service()
        service = get_alpr_service(db_session)
        with pytest.raises(ImportError) as exc_info:
            await service.recognize_and_store(
                camera_id=test_camera.id,
                image_data=sample_image_data,
                bbox=[10.0, 10.0, 60.0, 40.0],
                detection_confidence=0.95,
                store=True,
            )
        message = str(exc_info.value).lower()
        for dead_advice in ("pip install", "paddleocr", "pip3 install"):
            assert dead_advice not in message, (message, dead_advice)

    async def test_route_answers_503_for_the_retired_engine(
        self,
        db_session: AsyncSession,
        test_camera,
        sample_image_data: bytes,
    ):
        """The wire contract for a retired engine is 503, not 500.

        Pinned on the STATUS CODE only. The route's own comment at
        backend/api/routes/plate_reads.py:326-330 says the detail string is not
        pinned anywhere so that the wording can keep telling the truth; making
        this test assert the sentence would contradict that and would fail a
        wording fix.
        """
        from backend.api.routes.plate_reads import recognize_plate

        reset_alpr_service()
        request = PlateRecognizeRequest(
            camera_id=test_camera.id,
            image_base64=base64.b64encode(sample_image_data).decode("ascii"),
            detection_bbox=[10.0, 10.0, 60.0, 40.0],
            detection_confidence=0.95,
        )
        with pytest.raises(HTTPException) as exc_info:
            await recognize_plate(request=request, db=db_session, store=True)
        assert exc_info.value.status_code == 503
        # 500 would mean the request reached an engine and blew up in it; this is
        # the refusal-before-work code, so it must NOT be the generic failure code.
        assert exc_info.value.status_code != 500

    async def test_retirement_is_not_a_dead_path_recognition_still_runs(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """NON-VACUITY for this class.

        A 503-and-ImportError pin passes just as happily when the recognize leg
        has been deleted outright. So the same call, on the same service, on the
        same session, must still recognize once an engine is injected at the live
        seam — the absence is the engine, not the machinery.
        """
        reset_alpr_service()
        engine = mock_plate_ocr()
        engine.load_model()
        _PlateOCRHolder._instance = engine

        service = get_alpr_service(db_session)
        result = await service.recognize_and_store(
            camera_id=test_camera.id,
            image_data=sample_image_data,
            bbox=[10.0, 10.0, 60.0, 40.0],
            detection_confidence=0.95,
            store=False,
        )
        assert isinstance(result, PlateRecognizeResponse)
        assert result.plate_text == "ABC1234"
        assert result.ocr_confidence == 0.95
        # And the surviving half of the service is not retired either.
        stats = await service.get_statistics()
        assert isinstance(stats, PlateStatisticsResponse)

    async def test_injection_seam_is_still_reachable_from_live_callers(
        self,
        db_session: AsyncSession,
        test_camera,
        mock_plate_ocr,
        sample_image_data: bytes,
    ):
        """NON-VACUITY for the holder itself.

        ``_PlateOCRHolder`` could have been kept as dead scaffolding — a class
        whose ``ImportError`` nothing on a live path can observe, which would
        make the three absence pins above unfalsifiable. It has not been: the
        module-level accessor ``_get_plate_ocr()`` (alpr_service.py:572-574, the
        call site at line 139) still routes through it, so injecting at the
        holder changes what the ACCESSOR returns, and the ALPR loader family that
        could install an engine stays wired in the model zoo
        (``model_zoo._LOADER_MAP["fast-alpr"]``).
        """
        import backend.services.alpr_service as alpr

        _PlateOCRHolder._instance = None
        with pytest.raises(ImportError):
            alpr._get_plate_ocr()
        engine = mock_plate_ocr()
        engine.load_model()
        _PlateOCRHolder._instance = engine
        assert alpr._get_plate_ocr() is engine
        # The accessor is the live call site: the service reads the engine
        # through it, so the same injection drives a real recognition.
        service = alpr.ALPRService(db_session)
        result = await service.recognize_and_store(
            camera_id=test_camera.id,
            image_data=sample_image_data,
            bbox=[10.0, 10.0, 60.0, 40.0],
            detection_confidence=0.95,
            store=False,
        )
        assert result.plate_text == "ABC1234"
        # The drive really went through the shipped crop code: 100x50 frame,
        # bbox (10,10)-(60,40) => a 30-row x 50-col crop reaches the engine.
        assert engine.last_crop is not None
        assert engine.last_crop.shape[:2] == (30, 50), engine.last_crop.shape
        # And a supplier that could install an engine is still registered, so
        # the seam is a live seam rather than a museum piece.
        from backend.services import model_zoo

        assert "fast-alpr" in model_zoo._LOADER_MAP
        assert (REPO_ROOT / "backend/services/fast_alpr_loader.py").exists()

    def test_surviving_ai_trees_are_still_scan_visible(self):
        """NON-VACUITY for the corpus scan: ``ai/`` did not collapse alongside
        ``ai/enrichment``, so 'absent from the scan' still means 'absent'.

        Read off the directory listing rather than ``pkgutil.iter_modules`` —
        several surviving trees (``ai/vlm``) ship no ``__init__.py``, so the
        import-based listing would report a false absence and the pin would pass
        for the wrong reason.
        """
        names = {p.name for p in (REPO_ROOT / "ai").iterdir() if p.is_dir()}
        assert {"gateway", "yolo26", "vlm", "triton"} <= names, names
        # The LIVE spellings, one more time — the adversarial review caught the
        # first version asserting "enrichment_light" (underscore), a name no
        # directory ever had: the swept serving dir was ai/enrichment-light
        # WITH A HYPHEN, so the underscore assert could never fail. An absence
        # pin has to spell the dead thing the way it existed.
        assert "enrichment" not in names, names
        assert "enrichment-light" not in names, names
        assert "clip" not in names, names
        assert "florence" not in names, names


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
