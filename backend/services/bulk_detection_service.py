"""Service for high-throughput bulk detection ingestion.

This module provides optimized bulk INSERT operations with RETURNING clause
for high-throughput detection ingestion scenarios. It is designed to handle
large volumes of detections efficiently while maintaining data integrity.

Key features:
1. Bulk INSERT with RETURNING for immediate ID retrieval
2. Chunked inserts for very large batches
3. Input validation with filtering
4. Performance metrics tracking
5. Transaction management with rollback on failure

Related Linear issues:
- NEM-3753: Implement Bulk INSERT with RETURNING for Detection Ingestion

Usage:
    async with get_session() as session:
        service = BulkDetectionService(session)

        # Create detection inputs
        detections = [
            DetectionInput(
                camera_id="front_door",
                file_path="/path/to/image.jpg",
                object_type="person",
                confidence=0.95,
            )
            for _ in range(100)
        ]

        # Bulk insert with RETURNING
        result = await service.bulk_insert(detections)
        print(f"Inserted {result.inserted_count} detections")
        print(f"IDs: {result.inserted_ids}")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.core.logging import get_logger
from backend.models import Detection

if TYPE_CHECKING:
    from sqlalchemy.dialects.postgresql import Insert
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


@dataclass
class DetectionInput:
    """Input data for creating a detection record.

    Attributes:
        camera_id: ID of the camera that captured this detection
        file_path: Path to the source image/video file
        file_type: MIME type of the file (optional)
        object_type: Type of detected object (e.g., "person", "car")
        confidence: Detection confidence score (0.0 to 1.0)
        bbox_x: Bounding box X coordinate
        bbox_y: Bounding box Y coordinate
        bbox_width: Bounding box width
        bbox_height: Bounding box height
        detected_at: Timestamp of detection
        media_type: Type of media ("image" or "video")
        thumbnail_path: Path to thumbnail image
        enrichment_data: Additional enrichment data as JSONB
        labels: List of labels for the detection
    """

    camera_id: str
    file_path: str
    file_type: str | None = None
    object_type: str | None = None
    confidence: float | None = None
    bbox_x: int | None = None
    bbox_y: int | None = None
    bbox_width: int | None = None
    bbox_height: int | None = None
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    media_type: str | None = "image"
    duration: float | None = None
    video_codec: str | None = None
    video_width: int | None = None
    video_height: int | None = None
    thumbnail_path: str | None = None
    enrichment_data: dict[str, Any] | None = None
    labels: list[str] | None = None


@dataclass
class DetectionBatch:
    """A batch of detections for bulk processing.

    Attributes:
        batch_id: Unique identifier for this batch
        detections: List of detection inputs
        created_at: Timestamp when batch was created
    """

    batch_id: str
    detections: list[DetectionInput]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def size(self) -> int:
        """Get the number of detections in this batch."""
        return len(self.detections)


@dataclass
class BulkInsertResult:
    """Result of a bulk insert operation.

    Attributes:
        success: Whether the operation completed successfully
        inserted_count: Number of detections successfully inserted
        inserted_ids: List of IDs for inserted detections
        duration_ms: Duration of the operation in milliseconds
        error_message: Error message if operation failed
        failed_inputs: List of detection inputs that failed validation
    """

    success: bool
    inserted_count: int
    inserted_ids: list[int] = field(default_factory=list)
    duration_ms: float = 0.0
    error_message: str | None = None
    failed_inputs: list[DetectionInput] = field(default_factory=list)


class BulkDetectionService:
    """Service for high-throughput bulk detection ingestion.

    This service provides optimized bulk INSERT operations using PostgreSQL's
    INSERT ... RETURNING clause for efficient batch processing. It supports:

    - Bulk inserts with immediate ID retrieval via RETURNING
    - Chunked processing for very large batches
    - Input validation with invalid record filtering
    - ON CONFLICT handling for duplicate detection
    - Performance metrics tracking

    Example:
        async with get_session() as session:
            service = BulkDetectionService(session)

            # Prepare detections
            detections = [
                DetectionInput(camera_id="cam1", file_path="/path1.jpg", ...),
                DetectionInput(camera_id="cam1", file_path="/path2.jpg", ...),
            ]

            # Bulk insert
            result = await service.bulk_insert(detections)

            if result.success:
                print(f"Inserted {result.inserted_count} detections")
                for id in result.inserted_ids:
                    print(f"  - ID: {id}")
    """

    # Default chunk size for bulk inserts
    DEFAULT_CHUNK_SIZE = 100

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._stats: dict[str, Any] = {
            "total_inserts": 0,
            "total_batches": 0,
            "total_duration_ms": 0.0,
            "failed_inserts": 0,
        }

    def validate_detection(self, detection: DetectionInput) -> bool:
        """Validate a detection input.

        Args:
            detection: Detection input to validate

        Returns:
            True if valid, False otherwise
        """
        # Required fields check
        if not detection.camera_id or not detection.file_path:
            return False

        # Confidence range check
        confidence_invalid = detection.confidence is not None and (
            detection.confidence < 0.0 or detection.confidence > 1.0
        )
        if confidence_invalid:
            return False

        # Bounding box validation - all bbox values must be non-negative if set
        bbox_values = [
            detection.bbox_x,
            detection.bbox_y,
            detection.bbox_width,
            detection.bbox_height,
        ]
        if any(v is not None and v < 0 for v in bbox_values):
            return False

        # Media type validation
        valid_media_types = ("image", "video")
        return not (
            detection.media_type is not None and detection.media_type not in valid_media_types
        )

    async def bulk_insert(
        self,
        detections: list[DetectionInput],
        validate: bool = False,
        on_conflict: str | None = None,
    ) -> BulkInsertResult:
        """Bulk insert detections with RETURNING clause.

        Args:
            detections: List of detection inputs to insert
            validate: If True, validate and filter invalid detections
            on_conflict: Conflict handling strategy ("skip" or None for error)

        Returns:
            BulkInsertResult with inserted IDs and metrics
        """
        if not detections:
            return BulkInsertResult(
                success=True,
                inserted_count=0,
                inserted_ids=[],
                duration_ms=0.0,
            )

        start_time = time.perf_counter()
        failed_inputs: list[DetectionInput] = []

        # Validate if requested
        if validate:
            valid_detections = []
            for d in detections:
                if self.validate_detection(d):
                    valid_detections.append(d)
                else:
                    failed_inputs.append(d)
            detections = valid_detections

            if not detections:
                return BulkInsertResult(
                    success=True,
                    inserted_count=0,
                    inserted_ids=[],
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    failed_inputs=failed_inputs,
                )

        try:
            # Build values for bulk insert
            values = [self._detection_to_dict(d) for d in detections]

            # Create INSERT statement with RETURNING
            insert_stmt: Insert = pg_insert(Detection).values(values)

            # Handle ON CONFLICT if specified
            if on_conflict == "skip":
                # ON CONFLICT DO NOTHING - skip duplicates
                insert_stmt = insert_stmt.on_conflict_do_nothing(
                    index_elements=["camera_id", "file_path"]
                )

            # Add RETURNING clause and execute
            result = await self.session.execute(insert_stmt.returning(Detection.id))
            rows = result.fetchall()
            await self.session.commit()

            inserted_ids = [row[0] for row in rows]
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Update stats
            self._stats["total_inserts"] += len(inserted_ids)
            self._stats["total_batches"] += 1
            self._stats["total_duration_ms"] += duration_ms

            logger.info(
                f"Bulk inserted {len(inserted_ids)} detections",
                extra={
                    "inserted_count": len(inserted_ids),
                    "duration_ms": round(duration_ms, 2),
                    "failed_count": len(failed_inputs),
                },
            )

            return BulkInsertResult(
                success=True,
                inserted_count=len(inserted_ids),
                inserted_ids=inserted_ids,
                duration_ms=duration_ms,
                failed_inputs=failed_inputs,
            )

        except Exception as e:
            await self.session.rollback()
            duration_ms = (time.perf_counter() - start_time) * 1000

            self._stats["failed_inserts"] += len(detections)

            logger.error(
                f"Bulk insert failed: {e}",
                extra={
                    "detection_count": len(detections),
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return BulkInsertResult(
                success=False,
                inserted_count=0,
                inserted_ids=[],
                duration_ms=duration_ms,
                error_message=str(e),
                failed_inputs=detections,
            )

    async def bulk_insert_batch(self, batch: DetectionBatch) -> BulkInsertResult:
        """Bulk insert a DetectionBatch.

        Args:
            batch: DetectionBatch containing detections to insert

        Returns:
            BulkInsertResult with inserted IDs and metrics
        """
        return await self.bulk_insert(batch.detections)

    async def bulk_insert_chunked(
        self,
        detections: list[DetectionInput],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        validate: bool = False,
    ) -> BulkInsertResult:
        """Bulk insert detections in chunks for very large batches.

        This method splits large batches into smaller chunks to:
        - Avoid memory issues with very large INSERT statements
        - Allow partial progress on failure
        - Reduce transaction lock duration

        Args:
            detections: List of detection inputs to insert
            chunk_size: Maximum detections per chunk
            validate: If True, validate and filter invalid detections

        Returns:
            BulkInsertResult with aggregated results
        """
        if not detections:
            return BulkInsertResult(
                success=True,
                inserted_count=0,
                inserted_ids=[],
                duration_ms=0.0,
            )

        start_time = time.perf_counter()
        all_inserted_ids: list[int] = []
        all_failed: list[DetectionInput] = []
        total_inserted = 0

        # Split into chunks
        for i in range(0, len(detections), chunk_size):
            chunk = detections[i : i + chunk_size]
            result = await self.bulk_insert(chunk, validate=validate)

            all_inserted_ids.extend(result.inserted_ids)
            all_failed.extend(result.failed_inputs)
            total_inserted += result.inserted_count

            if not result.success:
                # Stop on first failure
                duration_ms = (time.perf_counter() - start_time) * 1000
                return BulkInsertResult(
                    success=False,
                    inserted_count=total_inserted,
                    inserted_ids=all_inserted_ids,
                    duration_ms=duration_ms,
                    error_message=result.error_message,
                    failed_inputs=all_failed,
                )

        duration_ms = (time.perf_counter() - start_time) * 1000

        return BulkInsertResult(
            success=True,
            inserted_count=total_inserted,
            inserted_ids=all_inserted_ids,
            duration_ms=duration_ms,
            failed_inputs=all_failed,
        )

    def _detection_to_dict(self, detection: DetectionInput) -> dict[str, Any]:
        """Convert DetectionInput to dictionary for INSERT.

        Args:
            detection: Detection input to convert

        Returns:
            Dictionary suitable for SQLAlchemy insert
        """
        return {
            "camera_id": detection.camera_id,
            "file_path": detection.file_path,
            "file_type": detection.file_type,
            "object_type": detection.object_type,
            "confidence": detection.confidence,
            "bbox_x": detection.bbox_x,
            "bbox_y": detection.bbox_y,
            "bbox_width": detection.bbox_width,
            "bbox_height": detection.bbox_height,
            "detected_at": detection.detected_at,
            "media_type": detection.media_type,
            "duration": detection.duration,
            "video_codec": detection.video_codec,
            "video_width": detection.video_width,
            "video_height": detection.video_height,
            "thumbnail_path": detection.thumbnail_path,
            "enrichment_data": detection.enrichment_data,
            "labels": detection.labels,
        }

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics for bulk inserts.

        Returns:
            Dictionary with performance metrics
        """
        total_batches = self._stats["total_batches"]
        total_inserts = self._stats["total_inserts"]
        total_duration = self._stats["total_duration_ms"]

        return {
            "total_inserts": total_inserts,
            "total_batches": total_batches,
            "failed_inserts": self._stats["failed_inserts"],
            "total_duration_ms": round(total_duration, 2),
            "avg_batch_size": total_inserts / total_batches if total_batches > 0 else 0,
            "avg_insert_time_ms": total_duration / total_batches if total_batches > 0 else 0,
        }

    def reset_stats(self) -> None:
        """Reset performance statistics."""
        self._stats = {
            "total_inserts": 0,
            "total_batches": 0,
            "total_duration_ms": 0.0,
            "failed_inserts": 0,
        }
