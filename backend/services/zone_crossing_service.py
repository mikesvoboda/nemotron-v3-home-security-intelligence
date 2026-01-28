"""Zone crossing detection service for real-time boundary crossing events.

This module provides the ZoneCrossingService that detects when entities cross
zone boundaries (enter/exit) and emits WebSocket events via Redis pub/sub.

Features:
    - Zone enter detection (entity moves from outside to inside)
    - Zone exit detection (entity moves from inside to outside)
    - Dwell time tracking (entity remains in zone)
    - Entity position tracking per zone
    - WebSocket event emission for real-time alerts

Related: NEM-3194 (Backend WebSocket Zone Crossing Events)
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

from backend.core.config import get_settings
from backend.core.metrics import (
    observe_zone_dwell_time,
    record_zone_crossing,
    set_zone_occupancy,
)
from backend.core.redis import get_redis
from backend.core.time_utils import utc_now
from backend.services.zone_service import (
    _get_detection_center,
    point_in_zone,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.models.camera_zone import CameraZone
    from backend.models.detection import Detection

logger = logging.getLogger(__name__)


class EntityPosition:
    """Tracks an entity's position state across zones.

    Attributes:
        entity_id: Unique identifier for the entity.
        entity_type: Type of entity (e.g., "person", "vehicle").
        current_zone_id: ID of the zone the entity is currently in, or None.
        entered_at: Timestamp when entity entered current zone.
        last_detection_id: ID of the last detection associated with this entity.
        last_thumbnail_url: Thumbnail URL from the last detection.
    """

    __slots__ = (
        "current_zone_id",
        "entered_at",
        "entity_id",
        "entity_type",
        "last_detection_id",
        "last_thumbnail_url",
    )

    def __init__(
        self,
        entity_id: str,
        entity_type: str = "unknown",
        current_zone_id: str | None = None,
        entered_at: datetime | None = None,
        last_detection_id: str | None = None,
        last_thumbnail_url: str | None = None,
    ) -> None:
        """Initialize entity position tracker.

        Args:
            entity_id: Unique identifier for the entity.
            entity_type: Type of entity.
            current_zone_id: Current zone ID if in a zone.
            entered_at: When entity entered current zone.
            last_detection_id: Last detection ID.
            last_thumbnail_url: Last thumbnail URL.
        """
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.current_zone_id = current_zone_id
        self.entered_at = entered_at
        self.last_detection_id = last_detection_id
        self.last_thumbnail_url = last_thumbnail_url


class ZoneCrossingService:
    """Service for detecting zone boundary crossings and emitting events.

    Tracks entity positions across zones and detects enter/exit events.
    Emits WebSocket events via Redis pub/sub for real-time alerts.

    Attributes:
        DEFAULT_IMAGE_WIDTH: Default image width for bbox calculations (1920).
        DEFAULT_IMAGE_HEIGHT: Default image height for bbox calculations (1080).
        DWELL_THRESHOLD_SECONDS: Minimum seconds in zone before emitting dwell event (30).
    """

    DEFAULT_IMAGE_WIDTH = 1920
    DEFAULT_IMAGE_HEIGHT = 1080
    DWELL_THRESHOLD_SECONDS = 30.0

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        """Initialize the zone crossing service.

        Args:
            redis_client: Optional Redis client for WebSocket events.
        """
        self._redis = redis_client
        # Track entity positions: entity_id -> EntityPosition
        self._entity_positions: dict[str, EntityPosition] = {}
        # Track zone occupants: zone_id -> set of entity_ids
        self._zone_occupants: dict[str, set[str]] = defaultdict(set)
        # Track dwell events emitted to avoid duplicates: (entity_id, zone_id) -> last_dwell_emitted_at
        self._dwell_events_emitted: dict[tuple[str, str], datetime] = {}

    def _compute_entity_id(self, detection: Detection) -> str:
        """Compute a unique entity ID from a detection.

        Uses the enrichment_data entity_id if available, otherwise falls back
        to detection ID.

        Args:
            detection: The detection to get entity ID from.

        Returns:
            A unique entity identifier string.
        """
        enrichment = getattr(detection, "enrichment_data", None)
        if enrichment and isinstance(enrichment, dict):
            # Check for tracked entity ID from re-identification
            entity_id = enrichment.get("entity_id") or enrichment.get("track_id")
            if entity_id:
                return str(entity_id)

        # Fall back to detection ID
        detection_id = getattr(detection, "id", None)
        if detection_id is not None:
            return f"detection_{detection_id}"

        # Last resort: generate a UUID
        return str(uuid.uuid4())

    def _compute_entity_type(self, detection: Detection) -> str:
        """Determine the entity type from a detection.

        Args:
            detection: The detection to get entity type from.

        Returns:
            Entity type string (e.g., "person", "vehicle", "unknown").
        """
        object_type = getattr(detection, "object_type", None)
        if object_type:
            return str(object_type).lower()

        enrichment = getattr(detection, "enrichment_data", None)
        if enrichment and isinstance(enrichment, dict):
            entity_type = enrichment.get("entity_type") or enrichment.get("class")
            if entity_type:
                return str(entity_type).lower()

        return "unknown"

    def _get_detection_in_zone(
        self,
        detection: Detection,
        zone: CameraZone,
        image_width: int | None = None,
        image_height: int | None = None,
    ) -> bool:
        """Check if a detection is inside a zone.

        Args:
            detection: The detection to check.
            zone: The zone to check against.
            image_width: Image width for normalization.
            image_height: Image height for normalization.

        Returns:
            True if detection center is inside the zone, False otherwise.
        """
        if not zone.enabled:
            return False

        width = image_width or self.DEFAULT_IMAGE_WIDTH
        height = image_height or self.DEFAULT_IMAGE_HEIGHT

        center = _get_detection_center(detection, width, height)
        if center is None:
            return False

        return point_in_zone(center[0], center[1], zone)

    async def _handle_zone_exit(
        self,
        entity: EntityPosition,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
        previous_zone_id: str,
        zones: list[CameraZone],
    ) -> dict[str, Any] | None:
        """Handle entity exiting a zone.

        Args:
            entity: Entity position tracker.
            entity_id: Entity identifier.
            entity_type: Type of entity.
            detection_id: Detection identifier.
            timestamp: Event timestamp.
            thumbnail_url: Thumbnail URL if available.
            previous_zone_id: ID of zone being exited.
            zones: List of zones to search.

        Returns:
            Exit event dictionary if zone found, None otherwise.
        """
        prev_zone = next((z for z in zones if str(z.id) == previous_zone_id), None)
        if not prev_zone:
            return None

        dwell_time = None
        if entity.entered_at:
            dwell_time = (timestamp - entity.entered_at).total_seconds()

        exit_event = await self._emit_zone_exit(
            zone=prev_zone,
            entity_id=entity_id,
            entity_type=entity_type,
            detection_id=detection_id,
            timestamp=timestamp,
            thumbnail_url=thumbnail_url,
            dwell_time=dwell_time,
        )

        # Cleanup tracking
        if previous_zone_id in self._zone_occupants:
            self._zone_occupants[previous_zone_id].discard(entity_id)
        self._dwell_events_emitted.pop((entity_id, previous_zone_id), None)

        return exit_event

    async def _handle_zone_enter(
        self,
        entity: EntityPosition,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
        current_zone_id: str,
        zones: list[CameraZone],
    ) -> dict[str, Any] | None:
        """Handle entity entering a zone.

        Args:
            entity: Entity position tracker.
            entity_id: Entity identifier.
            entity_type: Type of entity.
            detection_id: Detection identifier.
            timestamp: Event timestamp.
            thumbnail_url: Thumbnail URL if available.
            current_zone_id: ID of zone being entered.
            zones: List of zones to search.

        Returns:
            Enter event dictionary if zone found, None otherwise.
        """
        curr_zone = next((z for z in zones if str(z.id) == current_zone_id), None)
        if not curr_zone:
            return None

        enter_event = await self._emit_zone_enter(
            zone=curr_zone,
            entity_id=entity_id,
            entity_type=entity_type,
            detection_id=detection_id,
            timestamp=timestamp,
            thumbnail_url=thumbnail_url,
        )

        self._zone_occupants[current_zone_id].add(entity_id)
        entity.entered_at = timestamp

        return enter_event

    async def _handle_zone_dwell(
        self,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
        current_zone_id: str,
        dwell_time: float,
        zones: list[CameraZone],
    ) -> dict[str, Any] | None:
        """Handle entity dwelling in a zone.

        Args:
            entity_id: Entity identifier.
            entity_type: Type of entity.
            detection_id: Detection identifier.
            timestamp: Event timestamp.
            thumbnail_url: Thumbnail URL if available.
            current_zone_id: ID of zone where dwelling.
            dwell_time: Current dwell time in seconds.
            zones: List of zones to search.

        Returns:
            Dwell event dictionary if emitted, None otherwise.
        """
        if dwell_time < self.DWELL_THRESHOLD_SECONDS:
            return None

        dwell_key = (entity_id, current_zone_id)
        last_emitted = self._dwell_events_emitted.get(dwell_key)

        should_emit = (
            last_emitted is None
            or (timestamp - last_emitted).total_seconds() >= self.DWELL_THRESHOLD_SECONDS
        )

        if not should_emit:
            return None

        curr_zone = next((z for z in zones if str(z.id) == current_zone_id), None)
        if not curr_zone:
            return None

        dwell_event = await self._emit_zone_dwell(
            zone=curr_zone,
            entity_id=entity_id,
            entity_type=entity_type,
            detection_id=detection_id,
            timestamp=timestamp,
            thumbnail_url=thumbnail_url,
            dwell_time=dwell_time,
        )
        self._dwell_events_emitted[dwell_key] = timestamp

        return dwell_event

    async def process_detection(
        self,
        detection: Detection,
        zones: list[CameraZone],
        image_width: int | None = None,
        image_height: int | None = None,
    ) -> list[dict[str, Any]]:
        """Process a detection and check for zone boundary crossings.

        Compares the detection's position against all provided zones and
        emits events for any enter/exit/dwell crossings detected.

        Args:
            detection: The detection to process.
            zones: List of zones to check against.
            image_width: Image width for bbox normalization.
            image_height: Image height for bbox normalization.

        Returns:
            List of emitted event dictionaries.
        """
        if not zones:
            return []

        entity_id = self._compute_entity_id(detection)
        entity_type = self._compute_entity_type(detection)
        detection_id = str(getattr(detection, "id", ""))
        thumbnail_url = getattr(detection, "thumbnail_path", None)
        timestamp = getattr(detection, "detected_at", None) or utc_now()

        # Get or create entity position tracker
        if entity_id not in self._entity_positions:
            self._entity_positions[entity_id] = EntityPosition(
                entity_id=entity_id,
                entity_type=entity_type,
            )

        entity = self._entity_positions[entity_id]
        entity.entity_type = entity_type
        entity.last_detection_id = detection_id
        entity.last_thumbnail_url = thumbnail_url

        events: list[dict[str, Any]] = []
        previous_zone_id = entity.current_zone_id
        current_zone_id: str | None = None

        # Determine which zone (if any) the detection is currently in
        width = image_width or self.DEFAULT_IMAGE_WIDTH
        height = image_height or self.DEFAULT_IMAGE_HEIGHT

        for zone in sorted(zones, key=lambda z: getattr(z, "priority", 0), reverse=True):
            if self._get_detection_in_zone(detection, zone, width, height):
                current_zone_id = str(zone.id)
                break

        # Detect zone transitions
        if previous_zone_id != current_zone_id:
            if previous_zone_id is not None:
                exit_event = await self._handle_zone_exit(
                    entity,
                    entity_id,
                    entity_type,
                    detection_id,
                    timestamp,
                    thumbnail_url,
                    previous_zone_id,
                    zones,
                )
                if exit_event:
                    events.append(exit_event)

            if current_zone_id is not None:
                enter_event = await self._handle_zone_enter(
                    entity,
                    entity_id,
                    entity_type,
                    detection_id,
                    timestamp,
                    thumbnail_url,
                    current_zone_id,
                    zones,
                )
                if enter_event:
                    events.append(enter_event)

            entity.current_zone_id = current_zone_id

        elif current_zone_id is not None and entity.entered_at is not None:
            dwell_time = (timestamp - entity.entered_at).total_seconds()
            dwell_event = await self._handle_zone_dwell(
                entity_id,
                entity_type,
                detection_id,
                timestamp,
                thumbnail_url,
                current_zone_id,
                dwell_time,
                zones,
            )
            if dwell_event:
                events.append(dwell_event)

        return events

    def get_entity_zone(self, entity_id: str) -> str | None:
        """Get the current zone ID for an entity.

        Args:
            entity_id: The entity identifier.

        Returns:
            Zone ID if entity is in a zone, None otherwise.
        """
        entity = self._entity_positions.get(entity_id)
        if entity is None:
            return None
        return entity.current_zone_id

    def get_zone_occupants(self, zone_id: str) -> list[str]:
        """Get all entity IDs currently in a zone.

        Args:
            zone_id: The zone identifier.

        Returns:
            List of entity IDs currently in the zone.
        """
        return list(self._zone_occupants.get(zone_id, set()))

    def get_entity_dwell_time(self, entity_id: str) -> float | None:
        """Get the current dwell time for an entity in its zone.

        Args:
            entity_id: The entity identifier.

        Returns:
            Dwell time in seconds if entity is in a zone, None otherwise.
        """
        entity = self._entity_positions.get(entity_id)
        if entity is None or entity.current_zone_id is None or entity.entered_at is None:
            return None

        return (utc_now() - entity.entered_at).total_seconds()

    def clear_entity(self, entity_id: str) -> None:
        """Clear tracking data for an entity.

        Args:
            entity_id: The entity identifier to clear.
        """
        entity = self._entity_positions.pop(entity_id, None)
        if entity and entity.current_zone_id and entity.current_zone_id in self._zone_occupants:
            self._zone_occupants[entity.current_zone_id].discard(entity_id)

        # Clear dwell tracking
        keys_to_remove = [key for key in self._dwell_events_emitted if key[0] == entity_id]
        for key in keys_to_remove:
            del self._dwell_events_emitted[key]

    def clear_all(self) -> None:
        """Clear all tracking data."""
        self._entity_positions.clear()
        self._zone_occupants.clear()
        self._dwell_events_emitted.clear()

    async def _emit_zone_enter(
        self,
        zone: CameraZone,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
    ) -> dict[str, Any]:
        """Emit a zone.enter event.

        Args:
            zone: The zone that was entered.
            entity_id: The entity that entered.
            entity_type: Type of entity.
            detection_id: Associated detection ID.
            timestamp: When the crossing occurred.
            thumbnail_url: Thumbnail URL if available.

        Returns:
            The emitted event dictionary.
        """
        zone_id = str(zone.id)
        event = {
            "type": "zone.enter",
            "data": {
                "zone_id": zone_id,
                "zone_name": zone.name,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "detection_id": detection_id,
                "timestamp": timestamp.isoformat(),
                "thumbnail_url": thumbnail_url,
                "dwell_time": None,
            },
        }

        # Record Prometheus metrics for zone crossing (enter direction)
        record_zone_crossing(zone_id=zone_id, direction="enter", entity_type=entity_type)

        # Update zone occupancy gauge
        occupancy = len(self._zone_occupants.get(zone_id, set())) + 1
        set_zone_occupancy(zone_id=zone_id, count=occupancy)

        await self._emit_websocket_event(event)
        return event

    async def _emit_zone_exit(
        self,
        zone: CameraZone,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
        dwell_time: float | None,
    ) -> dict[str, Any]:
        """Emit a zone.exit event.

        Args:
            zone: The zone that was exited.
            entity_id: The entity that exited.
            entity_type: Type of entity.
            detection_id: Associated detection ID.
            timestamp: When the crossing occurred.
            thumbnail_url: Thumbnail URL if available.
            dwell_time: How long the entity was in the zone.

        Returns:
            The emitted event dictionary.
        """
        zone_id = str(zone.id)
        event = {
            "type": "zone.exit",
            "data": {
                "zone_id": zone_id,
                "zone_name": zone.name,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "detection_id": detection_id,
                "timestamp": timestamp.isoformat(),
                "thumbnail_url": thumbnail_url,
                "dwell_time": dwell_time,
            },
        }

        # Record Prometheus metrics for zone crossing (exit direction)
        record_zone_crossing(zone_id=zone_id, direction="exit", entity_type=entity_type)

        # Record dwell time histogram if we have a valid dwell time
        if dwell_time is not None and dwell_time > 0:
            observe_zone_dwell_time(zone_id=zone_id, duration_seconds=dwell_time)

        # Update zone occupancy gauge (entity is leaving, so subtract 1)
        current_occupants = self._zone_occupants.get(zone_id, set())
        occupancy = max(0, len(current_occupants) - 1)
        set_zone_occupancy(zone_id=zone_id, count=occupancy)

        await self._emit_websocket_event(event)
        return event

    async def _emit_zone_dwell(
        self,
        zone: CameraZone,
        entity_id: str,
        entity_type: str,
        detection_id: str,
        timestamp: datetime,
        thumbnail_url: str | None,
        dwell_time: float,
    ) -> dict[str, Any]:
        """Emit a zone.dwell event.

        Args:
            zone: The zone where entity is dwelling.
            entity_id: The entity that is dwelling.
            entity_type: Type of entity.
            detection_id: Associated detection ID.
            timestamp: Current timestamp.
            thumbnail_url: Thumbnail URL if available.
            dwell_time: How long the entity has been in the zone.

        Returns:
            The emitted event dictionary.
        """
        zone_id = str(zone.id)
        event = {
            "type": "zone.dwell",
            "data": {
                "zone_id": zone_id,
                "zone_name": zone.name,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "detection_id": detection_id,
                "timestamp": timestamp.isoformat(),
                "thumbnail_url": thumbnail_url,
                "dwell_time": dwell_time,
            },
        }

        # Record dwell time histogram for ongoing dwell events
        if dwell_time > 0:
            observe_zone_dwell_time(zone_id=zone_id, duration_seconds=dwell_time)

        await self._emit_websocket_event(event)
        return event

    async def _emit_websocket_event(self, event: dict[str, Any]) -> None:
        """Emit an event via Redis pub/sub.

        Args:
            event: The event to emit.
        """
        try:
            redis = self._redis
            if redis is None:
                # get_redis() is an async generator, use anext() to get the client
                redis = await anext(get_redis())

            settings = get_settings()
            channel = getattr(settings, "redis_event_channel", "hsi:events")

            if redis is not None:
                await redis.publish(channel, event)

        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event for zone crossing: {e}")


# =============================================================================
# Singleton Management
# =============================================================================

_zone_crossing_service: ZoneCrossingService | None = None


def get_zone_crossing_service() -> ZoneCrossingService:
    """Get or create the singleton zone crossing service.

    Returns:
        The ZoneCrossingService singleton.
    """
    global _zone_crossing_service  # noqa: PLW0603
    if _zone_crossing_service is None:
        _zone_crossing_service = ZoneCrossingService()
    return _zone_crossing_service


def reset_zone_crossing_service() -> None:
    """Reset the singleton zone crossing service.

    Useful for testing.
    """
    global _zone_crossing_service  # noqa: PLW0603
    _zone_crossing_service = None
