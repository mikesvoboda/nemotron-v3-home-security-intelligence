"""Repository pattern implementation for database access abstraction.

This module provides a clean interface for database operations, separating
data access logic from business logic and API routes.

Exports:
    Repository: Generic base class for all repositories
    CameraRepository: Repository for Camera entity
    EventRepository: Repository for Event entity
    DetectionRepository: Repository for Detection entity

Example:
    from backend.repositories import CameraRepository, EventRepository
    from backend.core import get_session

    async with get_session() as session:
        camera_repo = CameraRepository(session)
        event_repo = EventRepository(session)

        camera = await camera_repo.get_by_id("front_door")
        events = await event_repo.get_by_camera_id(camera.id)
"""

from backend.repositories.base import Repository
from backend.repositories.camera_repository import CameraRepository
from backend.repositories.detection_repository import DetectionRepository
from backend.repositories.event_repository import EventRepository

__all__ = [
    "CameraRepository",
    "DetectionRepository",
    "EventRepository",
    "Repository",
]
