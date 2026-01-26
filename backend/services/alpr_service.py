"""ALPR (Automatic License Plate Recognition) Service.

This module provides the ALPRService class for managing license plate
recognition operations, including:
- Processing plate images with PaddleOCR
- Storing plate reads to the database
- Querying plate read history
- Computing recognition statistics

The service integrates with the PlateOCR model from the AI enrichment
pipeline for text extraction and quality assessment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.plate_read import (
    PlateReadCreate,
    PlateReadListResponse,
    PlateReadResponse,
    PlateRecognizeResponse,
    PlateStatisticsResponse,
)
from backend.core.logging import get_logger
from backend.models.plate_read import PlateRead

logger = get_logger(__name__)

# Default configuration
DEFAULT_MIN_OCR_CONFIDENCE = 0.3  # Minimum confidence to store a plate read
DEFAULT_RETENTION_DAYS = 30  # Days to retain plate reads


class ALPRService:
    """Service for Automatic License Plate Recognition operations.

    This service handles:
    - Processing images through PaddleOCR for plate text extraction
    - Storing and retrieving plate read records
    - Computing statistics for monitoring and analytics
    - Managing plate read retention and cleanup

    Attributes:
        db: The async database session for operations.
        min_ocr_confidence: Minimum OCR confidence threshold for storing reads.
        retention_days: Days to retain plate reads before pruning.
    """

    def __init__(
        self,
        db: AsyncSession,
        min_ocr_confidence: float = DEFAULT_MIN_OCR_CONFIDENCE,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> None:
        """Initialize the ALPR service.

        Args:
            db: An async SQLAlchemy session for database operations.
            min_ocr_confidence: Minimum OCR confidence to store a read.
            retention_days: Days to retain plate reads before cleanup.
        """
        self.db = db
        self.min_ocr_confidence = min_ocr_confidence
        self.retention_days = retention_days

    async def recognize_and_store(
        self,
        camera_id: str,
        image_data: bytes | np.ndarray,
        bbox: list[float],
        detection_confidence: float,
        timestamp: datetime | None = None,
        store: bool = True,
    ) -> PlateRecognizeResponse:
        """Recognize plate text from image and optionally store the result.

        This method processes an image through PaddleOCR, extracts plate
        text, and optionally stores the result to the database.

        Args:
            camera_id: ID of the camera that captured the image.
            image_data: Image as bytes or numpy array (RGB/BGR).
            bbox: Bounding box of plate region [x1, y1, x2, y2].
            detection_confidence: Confidence of plate detection.
            timestamp: Detection timestamp (defaults to now).
            store: Whether to store the result in the database.

        Returns:
            PlateRecognizeResponse with recognition results.

        Raises:
            ImportError: If PaddleOCR is not installed.
        """
        # Import PlateOCR lazily to avoid import errors when not installed
        try:
            from ai.enrichment.models import plate_ocr as _plate_ocr_module  # noqa: F401
        except ImportError as e:
            logger.error("PaddleOCR not installed. Install with: pip install paddleocr")
            raise ImportError(
                "paddleocr required for ALPR. Install with: pip install paddleocr"
            ) from e

        # Convert image data to numpy array if needed
        if isinstance(image_data, bytes):
            image = Image.open(BytesIO(image_data))
            image_array = np.array(image.convert("RGB"))
        else:
            image_array = image_data

        # Crop to bounding box if provided
        if bbox and len(bbox) == 4:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            h, w = image_array.shape[:2]
            # Clamp to image bounds
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)
            if x2 > x1 and y2 > y1:
                image_array = image_array[y1:y2, x1:x2]

        # Get or create PlateOCR instance
        ocr = _get_plate_ocr()

        # Run recognition
        result = ocr.recognize_text(image_array, auto_enhance=True)

        if timestamp is None:
            timestamp = datetime.now(UTC)

        # Determine if we should store
        plate_read_id: int | None = None
        stored = False

        if store and result.plate_text and result.ocr_confidence >= self.min_ocr_confidence:
            # Create plate read record
            plate_read = PlateRead(
                camera_id=camera_id,
                timestamp=timestamp,
                plate_text=result.plate_text,
                raw_text=result.raw_text,
                detection_confidence=detection_confidence,
                ocr_confidence=result.ocr_confidence,
                bbox=bbox,
                image_quality_score=result.image_quality_score,
                is_enhanced=result.is_enhanced,
                is_blurry=result.is_blurry,
            )
            self.db.add(plate_read)
            await self.db.flush()
            await self.db.refresh(plate_read)
            plate_read_id = plate_read.id
            stored = True

            logger.info(
                f"Stored plate read: {result.plate_text} from {camera_id}",
                extra={
                    "plate_text": result.plate_text,
                    "camera_id": camera_id,
                    "ocr_confidence": result.ocr_confidence,
                    "plate_read_id": plate_read_id,
                },
            )

        return PlateRecognizeResponse(
            plate_text=result.plate_text,
            raw_text=result.raw_text,
            ocr_confidence=result.ocr_confidence,
            image_quality_score=result.image_quality_score,
            is_enhanced=result.is_enhanced,
            is_blurry=result.is_blurry,
            stored=stored,
            plate_read_id=plate_read_id,
        )

    async def create_plate_read(self, data: PlateReadCreate) -> PlateReadResponse:
        """Create a new plate read record.

        Used for manual entry or importing from external ALPR systems.

        Args:
            data: PlateReadCreate schema with plate data.

        Returns:
            PlateReadResponse with the created record.
        """
        plate_read = PlateRead(
            camera_id=data.camera_id,
            timestamp=data.timestamp,
            plate_text=data.plate_text,
            raw_text=data.raw_text,
            detection_confidence=data.detection_confidence,
            ocr_confidence=data.ocr_confidence,
            bbox=data.bbox,
            image_quality_score=data.image_quality_score,
            is_enhanced=data.is_enhanced,
            is_blurry=data.is_blurry,
        )
        self.db.add(plate_read)
        await self.db.flush()
        await self.db.refresh(plate_read)

        logger.info(
            f"Created plate read: {data.plate_text} from {data.camera_id}",
            extra={
                "plate_text": data.plate_text,
                "camera_id": data.camera_id,
                "plate_read_id": plate_read.id,
            },
        )

        return PlateReadResponse.model_validate(plate_read)

    async def get_plate_read(self, plate_read_id: int) -> PlateReadResponse | None:
        """Get a single plate read by ID.

        Args:
            plate_read_id: Database ID of the plate read.

        Returns:
            PlateReadResponse if found, None otherwise.
        """
        stmt = select(PlateRead).where(PlateRead.id == plate_read_id)
        result = await self.db.execute(stmt)
        plate_read = result.scalar_one_or_none()

        if plate_read is None:
            return None

        return PlateReadResponse.model_validate(plate_read)

    async def get_plate_reads(
        self,
        camera_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        min_confidence: float | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PlateReadListResponse:
        """Get paginated list of plate reads with optional filters.

        Args:
            camera_id: Optional filter by camera ID.
            start_time: Optional start time filter (inclusive).
            end_time: Optional end time filter (inclusive).
            min_confidence: Optional minimum OCR confidence filter.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            PlateReadListResponse with paginated results.
        """
        # Validate pagination
        page = max(1, page)
        page_size = max(1, min(page_size, 1000))
        offset = (page - 1) * page_size

        # Build query
        base_query = select(PlateRead)

        if camera_id is not None:
            base_query = base_query.where(PlateRead.camera_id == camera_id)

        if start_time is not None:
            base_query = base_query.where(PlateRead.timestamp >= start_time)

        if end_time is not None:
            base_query = base_query.where(PlateRead.timestamp <= end_time)

        if min_confidence is not None:
            base_query = base_query.where(PlateRead.ocr_confidence >= min_confidence)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Fetch paginated results
        paginated_query = (
            base_query.order_by(PlateRead.timestamp.desc()).offset(offset).limit(page_size)
        )
        result = await self.db.execute(paginated_query)
        plate_reads = list(result.scalars().all())

        return PlateReadListResponse(
            plate_reads=[PlateReadResponse.model_validate(pr) for pr in plate_reads],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_reads_by_camera(
        self,
        camera_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PlateReadListResponse:
        """Get plate reads for a specific camera.

        Args:
            camera_id: Camera ID to filter by.
            start_time: Optional start time filter.
            end_time: Optional end time filter.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            PlateReadListResponse with results for the camera.
        """
        return await self.get_plate_reads(
            camera_id=camera_id,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size,
        )

    async def search_by_plate_text(
        self,
        text: str,
        exact: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> PlateReadListResponse:
        """Search plate reads by plate text.

        Args:
            text: Plate text to search for.
            exact: If True, match exactly. If False, partial match.
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            PlateReadListResponse with matching results.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 1000))
        offset = (page - 1) * page_size

        # Normalize search text
        search_text = text.upper().strip()

        # Build query
        if exact:
            base_query = select(PlateRead).where(PlateRead.plate_text == search_text)
        else:
            # Partial match using LIKE
            base_query = select(PlateRead).where(PlateRead.plate_text.ilike(f"%{search_text}%"))

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Fetch paginated results
        paginated_query = (
            base_query.order_by(PlateRead.timestamp.desc()).offset(offset).limit(page_size)
        )
        result = await self.db.execute(paginated_query)
        plate_reads = list(result.scalars().all())

        return PlateReadListResponse(
            plate_reads=[PlateReadResponse.model_validate(pr) for pr in plate_reads],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_statistics(self) -> PlateStatisticsResponse:
        """Get aggregate statistics for plate recognition.

        Returns:
            PlateStatisticsResponse with recognition metrics.
        """
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        # Total reads
        total_result = await self.db.execute(select(func.count(PlateRead.id)))
        total_reads = total_result.scalar_one()

        # Unique plates
        unique_result = await self.db.execute(select(func.count(distinct(PlateRead.plate_text))))
        unique_plates = unique_result.scalar_one()

        # Average OCR confidence
        avg_conf_result = await self.db.execute(select(func.avg(PlateRead.ocr_confidence)))
        avg_ocr_confidence = avg_conf_result.scalar_one() or 0.0

        # Average quality score
        avg_quality_result = await self.db.execute(select(func.avg(PlateRead.image_quality_score)))
        avg_quality_score = avg_quality_result.scalar_one() or 0.0

        # Enhanced count
        enhanced_result = await self.db.execute(
            select(func.count(PlateRead.id)).where(PlateRead.is_enhanced.is_(True))
        )
        enhanced_count = enhanced_result.scalar_one()

        # Blurry count
        blurry_result = await self.db.execute(
            select(func.count(PlateRead.id)).where(PlateRead.is_blurry.is_(True))
        )
        blurry_count = blurry_result.scalar_one()

        # Reads in last hour
        last_hour_result = await self.db.execute(
            select(func.count(PlateRead.id)).where(PlateRead.timestamp >= one_hour_ago)
        )
        reads_last_hour = last_hour_result.scalar_one()

        # Reads in last 24 hours
        last_day_result = await self.db.execute(
            select(func.count(PlateRead.id)).where(PlateRead.timestamp >= one_day_ago)
        )
        reads_last_24h = last_day_result.scalar_one()

        return PlateStatisticsResponse(
            total_reads=total_reads,
            unique_plates=unique_plates,
            avg_ocr_confidence=round(avg_ocr_confidence, 3),
            avg_quality_score=round(avg_quality_score, 3),
            enhanced_count=enhanced_count,
            blurry_count=blurry_count,
            reads_last_hour=reads_last_hour,
            reads_last_24h=reads_last_24h,
        )

    async def prune_old_reads(self, retention_days: int | None = None) -> int:
        """Delete plate reads older than the retention period.

        Args:
            retention_days: Days to retain. If None, uses instance default.

        Returns:
            Number of records deleted.
        """
        if retention_days is None:
            retention_days = self.retention_days

        cutoff_time = datetime.now(UTC) - timedelta(days=retention_days)

        stmt = delete(PlateRead).where(PlateRead.timestamp < cutoff_time)
        result = await self.db.execute(stmt)
        deleted_count: int = result.rowcount or 0  # type: ignore[attr-defined]

        if deleted_count > 0:
            logger.info(
                f"Pruned {deleted_count} plate reads older than {retention_days} days",
                extra={
                    "deleted_count": deleted_count,
                    "retention_days": retention_days,
                    "cutoff_time": cutoff_time.isoformat(),
                },
            )

        return deleted_count


# Singleton holder for PlateOCR to avoid reloading model on every request
class _PlateOCRHolder:
    """Singleton holder for PlateOCR instance."""

    _instance: Any = None

    @classmethod
    def get(cls) -> Any:
        """Get or create the PlateOCR instance."""
        if cls._instance is None:
            from ai.enrichment.models.plate_ocr import PlateOCR

            cls._instance = PlateOCR()
            cls._instance.load_model()
            logger.info("PlateOCR model loaded for ALPR service")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        if cls._instance is not None:
            cls._instance.unload()
            cls._instance = None


def _get_plate_ocr() -> Any:
    """Get the PlateOCR singleton instance."""
    return _PlateOCRHolder.get()


def reset_plate_ocr() -> None:
    """Reset the PlateOCR singleton (for testing)."""
    _PlateOCRHolder.reset()


# Service singleton pattern
class _ALPRServiceSingleton:
    """Singleton holder for ALPRService factory."""

    _default_min_confidence: float = DEFAULT_MIN_OCR_CONFIDENCE
    _default_retention_days: int = DEFAULT_RETENTION_DAYS

    @classmethod
    def configure(
        cls,
        min_ocr_confidence: float | None = None,
        retention_days: int | None = None,
    ) -> None:
        """Configure default settings for ALPRService instances."""
        if min_ocr_confidence is not None:
            cls._default_min_confidence = min_ocr_confidence
        if retention_days is not None:
            cls._default_retention_days = retention_days

    @classmethod
    def create(cls, db: AsyncSession) -> ALPRService:
        """Create an ALPRService instance with default configuration."""
        return ALPRService(
            db=db,
            min_ocr_confidence=cls._default_min_confidence,
            retention_days=cls._default_retention_days,
        )

    @classmethod
    def reset(cls) -> None:
        """Reset default configuration (for testing)."""
        cls._default_min_confidence = DEFAULT_MIN_OCR_CONFIDENCE
        cls._default_retention_days = DEFAULT_RETENTION_DAYS


def get_alpr_service(db: AsyncSession) -> ALPRService:
    """Get an ALPRService instance for the given session.

    Args:
        db: An async SQLAlchemy session.

    Returns:
        ALPRService instance bound to the session.
    """
    return _ALPRServiceSingleton.create(db)


def configure_alpr_service(
    min_ocr_confidence: float | None = None,
    retention_days: int | None = None,
) -> None:
    """Configure default settings for ALPRService instances.

    Args:
        min_ocr_confidence: Default minimum OCR confidence.
        retention_days: Default retention period in days.
    """
    _ALPRServiceSingleton.configure(
        min_ocr_confidence=min_ocr_confidence,
        retention_days=retention_days,
    )


def reset_alpr_service() -> None:
    """Reset ALPRService configuration to defaults (for testing)."""
    _ALPRServiceSingleton.reset()
    reset_plate_ocr()
