"""Repository pattern implementation for database access abstraction.

This module provides a clean interface for database operations, separating
data access logic from business logic and API routes.

Exports:
    Repository: Generic base class for all repositories
    AlertRepository: Repository for Alert entity
    AlertRuleRepository: Repository for AlertRule entity
    CameraRepository: Repository for Camera entity
    DetectionRepository: Repository for Detection entity
    EntityRepository: Repository for Entity entity (re-identification tracking)
    EventRepository: Repository for Event entity
    ZoneRepository: Repository for Zone entity

Example:
    from backend.repositories import (
        AlertRepository,
        AlertRuleRepository,
        CameraRepository,
        EventRepository,
        EntityRepository,
        ZoneRepository,
    )
    from backend.core import get_session

    async with get_session() as session:
        camera_repo = CameraRepository(session)
        event_repo = EventRepository(session)
        entity_repo = EntityRepository(session)
        alert_repo = AlertRepository(session)
        zone_repo = ZoneRepository(session)

        camera = await camera_repo.get_by_id("front_door")
        events = await event_repo.get_by_camera_id(camera.id)
        persons = await entity_repo.get_by_type("person")
        alerts = await alert_repo.get_by_status("pending")
        zones = await zone_repo.get_by_camera_id(camera.id)
"""

from backend.repositories.alert_repository import AlertRepository, AlertRuleRepository
from backend.repositories.base import Repository
from backend.repositories.camera_repository import CameraRepository
from backend.repositories.detection_repository import DetectionRepository
from backend.repositories.entity_repository import EntityRepository
from backend.repositories.event_repository import EventRepository
from backend.repositories.zone_repository import ZoneRepository

__all__ = [
    "AlertRepository",
    "AlertRuleRepository",
    "CameraRepository",
    "DetectionRepository",
    "EntityRepository",
    "EventRepository",
    "Repository",
    "ZoneRepository",
]
