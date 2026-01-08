"""Repository pattern implementations for database access abstraction."""

from backend.repositories.base import BaseRepository
from backend.repositories.camera_repository import CameraRepository
from backend.repositories.detection_repository import DetectionRepository
from backend.repositories.event_repository import EventRepository

__all__ = [
    "BaseRepository",
    "CameraRepository",
    "DetectionRepository",
    "EventRepository",
]
