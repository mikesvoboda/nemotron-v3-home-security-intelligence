"""Detection-specific repository operations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.models.detection import Detection
from backend.repositories.base import BaseRepository


class DetectionRepository(BaseRepository[Detection, int]):
    """Repository for Detection-specific database operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the detection repository.

        Args:
            db: The async database session
        """
        super().__init__(Detection, db)

    async def get_by_id_with_camera(self, detection_id: int) -> Detection | None:
        """Get a detection with its camera eagerly loaded.

        Args:
            detection_id: The detection ID

        Returns:
            The detection with camera loaded, or None
        """
        stmt = (
            select(Detection)
            .options(joinedload(Detection.camera))
            .where(Detection.id == detection_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_camera_id(self, camera_id: str) -> list[Detection]:
        """Find all detections for a specific camera.

        Args:
            camera_id: The camera ID

        Returns:
            List of detections for the camera
        """
        stmt = select(Detection).where(Detection.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_object_type(self, object_type: str) -> list[Detection]:
        """Find all detections of a specific object type.

        Args:
            object_type: The object type (e.g., 'person', 'car')

        Returns:
            List of detections with matching object type
        """
        stmt = select(Detection).where(Detection.object_type == object_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_time_range(self, start_time: datetime, end_time: datetime) -> list[Detection]:
        """Find detections within a time range.

        Args:
            start_time: Start of the time range
            end_time: End of the time range

        Returns:
            List of detections within the range
        """
        stmt = select(Detection).where(
            Detection.detected_at >= start_time, Detection.detected_at <= end_time
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_high_confidence(self, min_confidence: float = 0.8) -> list[Detection]:
        """Find detections with high confidence scores.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            List of high-confidence detections
        """
        stmt = select(Detection).where(Detection.confidence >= min_confidence)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_file_path(self, file_path: str) -> Detection | None:
        """Find a detection by its file path.

        Args:
            file_path: The file path to search for

        Returns:
            The detection if found, None otherwise
        """
        stmt = select(Detection).where(Detection.file_path == file_path)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_videos(self) -> list[Detection]:
        """Find all video detections.

        Returns:
            List of video detections
        """
        stmt = select(Detection).where(Detection.media_type == "video")
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_camera(self, camera_id: str) -> int:
        """Count detections for a specific camera.

        Args:
            camera_id: The camera ID

        Returns:
            Number of detections for the camera
        """
        stmt = select(func.count()).select_from(Detection).where(Detection.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def count_by_object_type(self, object_type: str) -> int:
        """Count detections of a specific object type.

        Args:
            object_type: The object type

        Returns:
            Number of detections with matching type
        """
        stmt = (
            select(func.count()).select_from(Detection).where(Detection.object_type == object_type)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_object_type_counts(self) -> dict[str, int]:
        """Get counts of each object type.

        Returns:
            Dictionary mapping object types to counts
        """
        stmt = (
            select(Detection.object_type, func.count())
            .group_by(Detection.object_type)
            .where(Detection.object_type.isnot(None))
        )
        result = await self.db.execute(stmt)
        return {str(row[0]): int(row[1]) for row in result.all() if row[0] is not None}

    async def get_latest_by_camera(self, camera_id: str, limit: int = 10) -> list[Detection]:
        """Get the most recent detections for a camera.

        Args:
            camera_id: The camera ID
            limit: Maximum number of detections to return

        Returns:
            List of most recent detections
        """
        stmt = (
            select(Detection)
            .where(Detection.camera_id == camera_id)
            .order_by(Detection.detected_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_batch(self, detections: list[Detection]) -> list[Detection]:
        """Create multiple detections in a batch.

        Args:
            detections: List of detections to create

        Returns:
            List of created detections
        """
        self.db.add_all(detections)
        await self.db.flush()
        return detections
