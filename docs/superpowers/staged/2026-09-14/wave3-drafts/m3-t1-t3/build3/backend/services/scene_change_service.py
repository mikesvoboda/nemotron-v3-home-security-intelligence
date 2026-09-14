"""Scene change service for persisting and broadcasting scene changes (NEM-3555).

This service handles:
- Persisting scene changes to the database when detected by the enrichment pipeline
- Broadcasting scene changes via WebSocket for real-time frontend updates
- Classifying scene change types based on similarity scores
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.core.websocket.event_types import WebSocketEventType
from backend.models.scene_change import SceneChange, SceneChangeType
from backend.services.websocket_emitter import WebSocketEmitterService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def classify_scene_change_type(similarity_score: float) -> SceneChangeType:
    """Classify scene change type based on similarity score.

    Args:
        similarity_score: SSIM score between 0 and 1 (1 = identical).

    Returns:
        SceneChangeType based on how different the scene is.
    """
    if similarity_score < 0.3:
        return SceneChangeType.VIEW_BLOCKED
    elif similarity_score < 0.5:
        return SceneChangeType.VIEW_TAMPERED
    elif similarity_score < 0.7:
        return SceneChangeType.ANGLE_CHANGED
    else:
        return SceneChangeType.UNKNOWN


class SceneChangeService:
    """Service for managing scene change records with WebSocket notifications."""

    def __init__(
        self,
        session: AsyncSession,
        emitter: WebSocketEmitterService | None = None,
    ) -> None:
        """Initialize the scene change service.

        Args:
            session: SQLAlchemy async session for database operations.
            emitter: Optional WebSocket emitter for broadcasting events.
        """
        self._session = session
        self._emitter = emitter

    async def create_scene_change(
        self,
        camera_id: str,
        similarity_score: float,
        change_type: SceneChangeType = SceneChangeType.UNKNOWN,
        file_path: str | None = None,
        *,
        correlation_id: str | None = None,
    ) -> SceneChange:
        """Create and persist a new scene change record.

        Args:
            camera_id: ID of the camera that detected the change.
            similarity_score: SSIM similarity score (0-1).
            change_type: Type of scene change detected.
            file_path: Optional path to the frame that triggered detection.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            The created SceneChange record.
        """
        scene_change = SceneChange(
            camera_id=camera_id,
            similarity_score=similarity_score,
            change_type=change_type,
            file_path=file_path,
            detected_at=datetime.now(UTC),
            acknowledged=False,
            acknowledged_at=None,
        )
        self._session.add(scene_change)
        await self._session.flush()
        await self._session.refresh(scene_change)

        # Broadcast via WebSocket if emitter is available
        if self._emitter is not None:
            await self._emitter.emit(
                WebSocketEventType.SCENE_CHANGE_DETECTED,
                {
                    "id": scene_change.id,
                    "camera_id": scene_change.camera_id,
                    "similarity_score": scene_change.similarity_score,
                    "change_type": scene_change.change_type.value,
                    "file_path": scene_change.file_path,
                    "detected_at": scene_change.detected_at.isoformat(),
                    "acknowledged": scene_change.acknowledged,
                },
                correlation_id=correlation_id,
            )

        return scene_change

    async def get_scene_change(self, scene_change_id: int) -> SceneChange | None:
        """Get a scene change by ID.

        Args:
            scene_change_id: The ID of the scene change to retrieve.

        Returns:
            The SceneChange record or None if not found.
        """
        result = await self._session.execute(
            select(SceneChange).where(SceneChange.id == scene_change_id)
        )
        return result.scalar_one_or_none()

    async def acknowledge_scene_change(
        self,
        scene_change_id: int,
        *,
        correlation_id: str | None = None,
    ) -> SceneChange | None:
        """Acknowledge a scene change (idempotent operation).

        Args:
            scene_change_id: The ID of the scene change to acknowledge.
            correlation_id: Optional correlation ID for tracing.

        Returns:
            The updated SceneChange record or None if not found.
        """
        scene_change = await self.get_scene_change(scene_change_id)
        if scene_change is None:
            return None

        # Idempotent: if already acknowledged, just return
        if scene_change.acknowledged:
            return scene_change

        scene_change.acknowledged = True
        scene_change.acknowledged_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(scene_change)

        # Broadcast acknowledgment via WebSocket
        if self._emitter is not None:
            await self._emitter.emit(
                WebSocketEventType.SCENE_CHANGE_ACKNOWLEDGED,
                {
                    "id": scene_change.id,
                    "camera_id": scene_change.camera_id,
                    "acknowledged": scene_change.acknowledged,
                    "acknowledged_at": scene_change.acknowledged_at.isoformat()
                    if scene_change.acknowledged_at
                    else None,
                },
                correlation_id=correlation_id,
            )

        return scene_change

    async def get_unacknowledged_for_camera(
        self,
        camera_id: str,
        limit: int = 100,
    ) -> list[SceneChange]:
        """Get unacknowledged scene changes for a camera.

        Args:
            camera_id: The camera ID to query.
            limit: Maximum number of results.

        Returns:
            List of unacknowledged SceneChange records.
        """
        result = await self._session.execute(
            select(SceneChange)
            .where(SceneChange.camera_id == camera_id)
            .where(SceneChange.acknowledged.is_(False))
            .order_by(SceneChange.detected_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
