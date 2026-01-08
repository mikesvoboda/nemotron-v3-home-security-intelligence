"""Repository for Detection entity database operations.

This module provides the DetectionRepository class which extends the generic
Repository base class with detection-specific query methods.

Example:
    async with get_session() as session:
        repo = DetectionRepository(session)
        detections = await repo.get_by_camera_id("front_door")
        high_confidence = await repo.get_high_confidence(threshold=0.8)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select

from backend.models import Detection
from backend.repositories.base import Repository

if TYPE_CHECKING:
    from collections.abc import Sequence


class DetectionRepository(Repository[Detection]):
    """Repository for Detection entity database operations.

    Provides CRUD operations inherited from Repository base class plus
    detection-specific query methods for filtering and aggregating detections.

    Attributes:
        model_class: Set to Detection for type inference and query construction.

    Example:
        async with get_session() as session:
            repo = DetectionRepository(session)

            # Get detections by camera
            detections = await repo.get_by_camera_id("front_door")

            # Get high-confidence detections
            high_conf = await repo.get_high_confidence(threshold=0.85)

            # Get detection counts by object type
            counts = await repo.get_object_type_counts()
    """

    model_class = Detection

    async def get_by_camera_id(self, camera_id: str) -> Sequence[Detection]:
        """Get all detections for a specific camera.

        Args:
            camera_id: The ID of the camera to filter by.

        Returns:
            A sequence of detections from the specified camera.
        """
        stmt = select(Detection).where(Detection.camera_id == camera_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_object_type(self, object_type: str) -> Sequence[Detection]:
        """Get detections filtered by detected object type.

        Args:
            object_type: The type of object to filter by (e.g., "person", "car").

        Returns:
            A sequence of detections with the specified object type.
        """
        stmt = select(Detection).where(Detection.object_type == object_type)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_in_date_range(self, start: datetime, end: datetime) -> Sequence[Detection]:
        """Get detections within a date range.

        Args:
            start: The start of the date range (inclusive).
            end: The end of the date range (inclusive).

        Returns:
            A sequence of detections where detected_at is within the range.
        """
        stmt = select(Detection).where(Detection.detected_at >= start, Detection.detected_at <= end)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_high_confidence(self, threshold: float = 0.8) -> Sequence[Detection]:
        """Get detections with confidence at or above a threshold.

        Args:
            threshold: The minimum confidence score (inclusive). Default is 0.8.

        Returns:
            A sequence of detections with confidence >= threshold.
        """
        stmt = select(Detection).where(Detection.confidence >= threshold)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_recent(self, limit: int = 10) -> Sequence[Detection]:
        """Get the most recent detections.

        Args:
            limit: Maximum number of detections to return. Default is 10.

        Returns:
            A sequence of detections ordered by detected_at descending,
            limited to the specified count.
        """
        stmt = select(Detection).order_by(desc(Detection.detected_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_media_type(self, media_type: str) -> Sequence[Detection]:
        """Get detections filtered by media type.

        Args:
            media_type: The media type to filter by ("image" or "video").

        Returns:
            A sequence of detections with the specified media type.
        """
        stmt = select(Detection).where(Detection.media_type == media_type)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_file_path(self, file_path: str) -> Detection | None:
        """Find a detection by its source file path.

        Args:
            file_path: The file path of the detection's source image/video.

        Returns:
            The Detection if found, None otherwise.
        """
        stmt = select(Detection).where(Detection.file_path == file_path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_camera_detection_counts(self) -> dict[str, int]:
        """Get detection counts grouped by camera.

        Returns:
            A dictionary mapping camera_id to detection count.
        """
        stmt = select(Detection.camera_id, func.count(Detection.id)).group_by(Detection.camera_id)
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_object_type_counts(self) -> dict[str, int]:
        """Get detection counts grouped by object type.

        Returns:
            A dictionary mapping object_type to detection count.
            Excludes detections with NULL object_type.
        """
        stmt = (
            select(Detection.object_type, func.count(Detection.id))
            .where(Detection.object_type.isnot(None))
            .group_by(Detection.object_type)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
