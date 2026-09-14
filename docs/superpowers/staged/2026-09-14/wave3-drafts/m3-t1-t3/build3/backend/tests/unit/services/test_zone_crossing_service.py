"""Unit tests for zone crossing detection service.

Tests cover:
- ZoneCrossingService initialization
- Entity ID and type computation
- Zone enter detection
- Zone exit detection
- Zone dwell detection
- Entity position tracking
- Zone occupant tracking
- WebSocket event emission
- Singleton management

Related: NEM-3194 (Backend WebSocket Zone Crossing Events)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Initialization Tests
# =============================================================================


class TestZoneCrossingServiceInit:
    """Tests for ZoneCrossingService initialization."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()
        assert service.DEFAULT_IMAGE_WIDTH == 1920
        assert service.DEFAULT_IMAGE_HEIGHT == 1080
        assert service.DWELL_THRESHOLD_SECONDS == 30.0
        assert service._redis is None
        assert service._entity_positions == {}
        assert len(service._zone_occupants) == 0

    def test_init_with_redis_client(self) -> None:
        """Test initialization with Redis client."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = MagicMock()
        service = ZoneCrossingService(redis_client=mock_redis)
        assert service._redis is mock_redis


# =============================================================================
# Entity Position Tests
# =============================================================================


class TestEntityPosition:
    """Tests for EntityPosition class."""

    def test_entity_position_init_defaults(self) -> None:
        """Test EntityPosition initialization with defaults."""
        from backend.services.zone_crossing_service import EntityPosition

        pos = EntityPosition(entity_id="test-123")
        assert pos.entity_id == "test-123"
        assert pos.entity_type == "unknown"
        assert pos.current_zone_id is None
        assert pos.entered_at is None
        assert pos.last_detection_id is None
        assert pos.last_thumbnail_url is None

    def test_entity_position_init_with_values(self) -> None:
        """Test EntityPosition initialization with all values."""
        from backend.services.zone_crossing_service import EntityPosition

        now = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        pos = EntityPosition(
            entity_id="entity-456",
            entity_type="person",
            current_zone_id="zone-abc",
            entered_at=now,
            last_detection_id="det-789",
            last_thumbnail_url="/thumbnails/test.jpg",
        )
        assert pos.entity_id == "entity-456"
        assert pos.entity_type == "person"
        assert pos.current_zone_id == "zone-abc"
        assert pos.entered_at == now
        assert pos.last_detection_id == "det-789"
        assert pos.last_thumbnail_url == "/thumbnails/test.jpg"


# =============================================================================
# Entity ID/Type Computation Tests
# =============================================================================


class TestComputeEntityId:
    """Tests for _compute_entity_id method."""

    def test_uses_enrichment_entity_id(self) -> None:
        """Test that enrichment data entity_id is preferred."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.enrichment_data = {"entity_id": "enriched-123"}
        detection.id = 456

        result = service._compute_entity_id(detection)
        assert result == "enriched-123"

    def test_uses_enrichment_track_id(self) -> None:
        """Test that track_id is used if entity_id not present."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.enrichment_data = {"track_id": "track-789"}
        detection.id = 456

        result = service._compute_entity_id(detection)
        assert result == "track-789"

    def test_falls_back_to_detection_id(self) -> None:
        """Test fallback to detection ID when no enrichment data."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.enrichment_data = None
        detection.id = 123

        result = service._compute_entity_id(detection)
        assert result == "detection_123"

    def test_falls_back_to_detection_id_empty_enrichment(self) -> None:
        """Test fallback when enrichment data is empty dict."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.enrichment_data = {}
        detection.id = 555

        result = service._compute_entity_id(detection)
        assert result == "detection_555"

    def test_generates_uuid_when_no_id(self) -> None:
        """Test UUID generation when detection has no ID."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock(spec=[])
        detection.enrichment_data = None
        detection.id = None

        result = service._compute_entity_id(detection)
        # Should be a valid UUID
        uuid.UUID(result)


class TestComputeEntityType:
    """Tests for _compute_entity_type method."""

    def test_uses_object_type(self) -> None:
        """Test that object_type is used first."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.object_type = "Person"
        detection.enrichment_data = {"entity_type": "vehicle"}

        result = service._compute_entity_type(detection)
        assert result == "person"

    def test_uses_enrichment_entity_type(self) -> None:
        """Test that enrichment entity_type is used if no object_type."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.object_type = None
        detection.enrichment_data = {"entity_type": "Vehicle"}

        result = service._compute_entity_type(detection)
        assert result == "vehicle"

    def test_uses_enrichment_class(self) -> None:
        """Test that enrichment class is used as fallback."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.object_type = None
        detection.enrichment_data = {"class": "CAR"}

        result = service._compute_entity_type(detection)
        assert result == "car"

    def test_returns_unknown_when_no_type(self) -> None:
        """Test that unknown is returned when no type available."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.object_type = None
        detection.enrichment_data = None

        result = service._compute_entity_type(detection)
        assert result == "unknown"


# =============================================================================
# Zone Detection Tests
# =============================================================================


class TestGetDetectionInZone:
    """Tests for _get_detection_in_zone method."""

    def test_returns_false_for_disabled_zone(self) -> None:
        """Test that disabled zones always return False."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 50
        detection.bbox_height = 100

        zone = MagicMock()
        zone.enabled = False
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        result = service._get_detection_in_zone(detection, zone)
        assert result is False

    def test_returns_true_when_inside(self) -> None:
        """Test detection inside zone returns True."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        zone = MagicMock()
        zone.enabled = True
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        result = service._get_detection_in_zone(
            detection, zone, image_width=1920, image_height=1080
        )
        assert result is True

    def test_returns_false_when_outside(self) -> None:
        """Test detection outside zone returns False."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.bbox_x = 1800
        detection.bbox_y = 1000
        detection.bbox_width = 100
        detection.bbox_height = 50

        zone = MagicMock()
        zone.enabled = True
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        result = service._get_detection_in_zone(
            detection, zone, image_width=1920, image_height=1080
        )
        assert result is False

    def test_returns_false_when_no_bbox(self) -> None:
        """Test detection without bbox returns False."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.bbox_x = None
        detection.bbox_y = None
        detection.bbox_width = None
        detection.bbox_height = None

        zone = MagicMock()
        zone.enabled = True
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        result = service._get_detection_in_zone(detection, zone)
        assert result is False


# =============================================================================
# Process Detection Tests
# =============================================================================


class TestProcessDetection:
    """Tests for process_detection method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_zones(self) -> None:
        """Test that empty list is returned when no zones provided."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = None
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 50
        detection.bbox_height = 100

        events = await service.process_detection(detection, zones=[])
        assert events == []

    @pytest.mark.asyncio
    async def test_emits_enter_event_when_entering_zone(self) -> None:
        """Test that zone.enter event is emitted when entity enters zone."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = "/thumbnails/test.jpg"
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            events = await service.process_detection(detection, zones=[zone])

            assert len(events) == 1
            assert events[0]["type"] == "zone.enter"
            assert events[0]["data"]["zone_id"] == "zone-abc"
            assert events[0]["data"]["zone_name"] == "Front Yard"
            assert events[0]["data"]["entity_id"] == "entity-001"
            assert events[0]["data"]["entity_type"] == "person"

    @pytest.mark.asyncio
    async def test_emits_exit_event_when_leaving_zone(self) -> None:
        """Test that zone.exit event is emitted when entity leaves zone."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # First, place entity in zone
        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone
            await service.process_detection(detection1, zones=[zone])

            # Now move outside the zone
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = datetime(2026, 1, 21, 14, 31, 0, tzinfo=UTC)
            detection2.thumbnail_path = "/thumbnails/test2.jpg"
            detection2.bbox_x = 1800
            detection2.bbox_y = 1000
            detection2.bbox_width = 50
            detection2.bbox_height = 100

            events = await service.process_detection(detection2, zones=[zone])

            assert len(events) == 1
            assert events[0]["type"] == "zone.exit"
            assert events[0]["data"]["zone_id"] == "zone-abc"
            assert events[0]["data"]["entity_id"] == "entity-001"
            # Check dwell time is calculated
            assert events[0]["data"]["dwell_time"] == 60.0

    @pytest.mark.asyncio
    async def test_emits_dwell_event_after_threshold(self) -> None:
        """Test that zone.dwell event is emitted after threshold."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        # Detection inside zone
        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = base_time
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone
            events1 = await service.process_detection(detection1, zones=[zone])
            assert len(events1) == 1
            assert events1[0]["type"] == "zone.enter"

            # Same position, 35 seconds later (exceeds threshold)
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = base_time + timedelta(seconds=35)
            detection2.thumbnail_path = None
            detection2.bbox_x = 100
            detection2.bbox_y = 100
            detection2.bbox_width = 100
            detection2.bbox_height = 100

            events2 = await service.process_detection(detection2, zones=[zone])

            assert len(events2) == 1
            assert events2[0]["type"] == "zone.dwell"
            assert events2[0]["data"]["dwell_time"] >= 30.0

    @pytest.mark.asyncio
    async def test_no_duplicate_dwell_events(self) -> None:
        """Test that dwell events are not emitted too frequently."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        # Create detection inside zone
        def make_detection(det_id: int, seconds_offset: int) -> MagicMock:
            det = MagicMock()
            det.id = det_id
            det.object_type = "person"
            det.enrichment_data = {"entity_id": "entity-001"}
            det.detected_at = base_time + timedelta(seconds=seconds_offset)
            det.thumbnail_path = None
            det.bbox_x = 100
            det.bbox_y = 100
            det.bbox_width = 100
            det.bbox_height = 100
            return det

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone
            await service.process_detection(make_detection(1, 0), zones=[zone])

            # First dwell event at 35 seconds
            events1 = await service.process_detection(make_detection(2, 35), zones=[zone])
            assert len(events1) == 1
            assert events1[0]["type"] == "zone.dwell"

            # No dwell event at 40 seconds (too soon)
            events2 = await service.process_detection(make_detection(3, 40), zones=[zone])
            assert len(events2) == 0

            # Second dwell event at 70 seconds (30+ seconds after first)
            events3 = await service.process_detection(make_detection(4, 70), zones=[zone])
            assert len(events3) == 1
            assert events3[0]["type"] == "zone.dwell"

    @pytest.mark.asyncio
    async def test_handles_zone_transition(self) -> None:
        """Test handling transition from one zone to another."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone1 = MagicMock()
        zone1.id = "zone-1"
        zone1.name = "Front Yard"
        zone1.enabled = True
        zone1.priority = 1
        zone1.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        zone2 = MagicMock()
        zone2.id = "zone-2"
        zone2.name = "Driveway"
        zone2.enabled = True
        zone2.priority = 1
        zone2.coordinates = [[0.5, 0.0], [1.0, 0.0], [1.0, 0.5], [0.5, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        # Detection in zone 1
        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = base_time
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone 1
            events1 = await service.process_detection(detection1, zones=[zone1, zone2])
            assert len(events1) == 1
            assert events1[0]["type"] == "zone.enter"
            assert events1[0]["data"]["zone_id"] == "zone-1"

            # Move to zone 2
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = base_time + timedelta(seconds=10)
            detection2.thumbnail_path = None
            detection2.bbox_x = 1500
            detection2.bbox_y = 100
            detection2.bbox_width = 100
            detection2.bbox_height = 100

            events2 = await service.process_detection(detection2, zones=[zone1, zone2])

            # Should have exit from zone-1 and enter to zone-2
            assert len(events2) == 2
            event_types = {e["type"] for e in events2}
            assert "zone.exit" in event_types
            assert "zone.enter" in event_types


# =============================================================================
# Entity/Zone Query Tests
# =============================================================================


class TestGetEntityZone:
    """Tests for get_entity_zone method."""

    def test_returns_none_for_unknown_entity(self) -> None:
        """Test that None is returned for unknown entity."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()
        result = service.get_entity_zone("nonexistent-entity")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_zone_id_for_entity_in_zone(self) -> None:
        """Test that correct zone ID is returned for entity in zone."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service.process_detection(detection, zones=[zone])

        result = service.get_entity_zone("entity-001")
        assert result == "zone-abc"


class TestGetZoneOccupants:
    """Tests for get_zone_occupants method."""

    def test_returns_empty_list_for_empty_zone(self) -> None:
        """Test that empty list is returned for zone with no occupants."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()
        result = service.get_zone_occupants("zone-xyz")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_occupant_list(self) -> None:
        """Test that list of entity IDs is returned for occupied zone."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Add two entities to zone
            for entity_id in ["entity-001", "entity-002"]:
                detection = MagicMock()
                detection.id = hash(entity_id) % 1000
                detection.object_type = "person"
                detection.enrichment_data = {"entity_id": entity_id}
                detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
                detection.thumbnail_path = None
                detection.bbox_x = 100
                detection.bbox_y = 100
                detection.bbox_width = 100
                detection.bbox_height = 100
                await service.process_detection(detection, zones=[zone])

        result = service.get_zone_occupants("zone-abc")
        assert len(result) == 2
        assert set(result) == {"entity-001", "entity-002"}


class TestGetEntityDwellTime:
    """Tests for get_entity_dwell_time method."""

    def test_returns_none_for_unknown_entity(self) -> None:
        """Test that None is returned for unknown entity."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()
        result = service.get_entity_dwell_time("nonexistent-entity")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dwell_time_for_entity_in_zone(self) -> None:
        """Test that dwell time is calculated for entity in zone."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service.process_detection(detection, zones=[zone])

        result = service.get_entity_dwell_time("entity-001")
        assert result is not None
        assert result >= 0


# =============================================================================
# Clear Methods Tests
# =============================================================================


class TestClearEntity:
    """Tests for clear_entity method."""

    @pytest.mark.asyncio
    async def test_clears_entity_tracking(self) -> None:
        """Test that entity tracking data is cleared."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service.process_detection(detection, zones=[zone])

        # Entity should be in zone
        assert service.get_entity_zone("entity-001") == "zone-abc"
        assert "entity-001" in service.get_zone_occupants("zone-abc")

        # Clear entity
        service.clear_entity("entity-001")

        # Entity should be removed
        assert service.get_entity_zone("entity-001") is None
        assert "entity-001" not in service.get_zone_occupants("zone-abc")

    def test_clear_nonexistent_entity_does_not_error(self) -> None:
        """Test that clearing nonexistent entity doesn't raise error."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()
        service.clear_entity("nonexistent-entity")  # Should not raise


class TestClearAll:
    """Tests for clear_all method."""

    @pytest.mark.asyncio
    async def test_clears_all_tracking_data(self) -> None:
        """Test that all tracking data is cleared."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Add two entities
            for entity_id in ["entity-001", "entity-002"]:
                detection = MagicMock()
                detection.id = hash(entity_id) % 1000
                detection.object_type = "person"
                detection.enrichment_data = {"entity_id": entity_id}
                detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
                detection.thumbnail_path = None
                detection.bbox_x = 100
                detection.bbox_y = 100
                detection.bbox_width = 100
                detection.bbox_height = 100
                await service.process_detection(detection, zones=[zone])

        assert len(service.get_zone_occupants("zone-abc")) == 2

        service.clear_all()

        assert service.get_entity_zone("entity-001") is None
        assert service.get_entity_zone("entity-002") is None
        assert len(service.get_zone_occupants("zone-abc")) == 0


# =============================================================================
# WebSocket Emission Tests
# =============================================================================


class TestEmitWebSocketEvent:
    """Tests for _emit_websocket_event method."""

    @pytest.mark.asyncio
    async def test_emits_event_to_redis(self) -> None:
        """Test that event is published to Redis."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        event = {
            "type": "zone.enter",
            "data": {
                "zone_id": "zone-abc",
                "zone_name": "Front Yard",
                "entity_id": "entity-001",
                "entity_type": "person",
                "detection_id": "123",
                "timestamp": "2026-01-21T14:30:00+00:00",
                "thumbnail_url": None,
                "dwell_time": None,
            },
        }

        with patch("backend.services.zone_crossing_service.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_websocket_event(event)

        mock_redis.publish.assert_called_once_with("hsi:events", event)

    @pytest.mark.asyncio
    async def test_gets_redis_if_not_provided(self) -> None:
        """Test that Redis is obtained from get_redis if not provided."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()  # No redis_client

        mock_redis = AsyncMock()

        async def mock_get_redis():
            yield mock_redis

        event = {"type": "zone.enter", "data": {}}

        with patch("backend.services.zone_crossing_service.get_redis", mock_get_redis):
            with patch("backend.core.config.get_settings") as mock_settings:
                mock_settings.return_value.redis_event_channel = "hsi:events"
                await service._emit_websocket_event(event)

        mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_redis_error_gracefully(self) -> None:
        """Test that Redis errors don't propagate."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis connection error")
        service = ZoneCrossingService(redis_client=mock_redis)

        event = {"type": "zone.enter", "data": {}}

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            # Should not raise
            await service._emit_websocket_event(event)


# =============================================================================
# Singleton Tests
# =============================================================================


class TestZoneCrossingSingleton:
    """Tests for zone crossing service singleton functions."""

    def test_get_zone_crossing_service_creates_singleton(self) -> None:
        """Test that get_zone_crossing_service creates singleton."""
        from backend.services.zone_crossing_service import (
            get_zone_crossing_service,
            reset_zone_crossing_service,
        )

        reset_zone_crossing_service()
        service1 = get_zone_crossing_service()
        service2 = get_zone_crossing_service()

        assert service1 is service2
        reset_zone_crossing_service()

    def test_reset_zone_crossing_service(self) -> None:
        """Test that reset_zone_crossing_service clears singleton."""
        from backend.services.zone_crossing_service import (
            get_zone_crossing_service,
            reset_zone_crossing_service,
        )

        service1 = get_zone_crossing_service()
        reset_zone_crossing_service()
        service2 = get_zone_crossing_service()

        assert service1 is not service2
        reset_zone_crossing_service()


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_detection_with_no_timestamp_uses_utc_now(self) -> None:
        """Test that detection without timestamp uses current time."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = None
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            events = await service.process_detection(detection, zones=[zone])

        assert len(events) == 1
        assert events[0]["type"] == "zone.enter"
        # Timestamp should be set
        assert events[0]["data"]["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_multiple_zones_uses_highest_priority(self) -> None:
        """Test that highest priority zone is selected when overlapping."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # Two overlapping zones
        zone_low = MagicMock()
        zone_low.id = "zone-low"
        zone_low.name = "Low Priority"
        zone_low.enabled = True
        zone_low.priority = 1
        zone_low.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        zone_high = MagicMock()
        zone_high.id = "zone-high"
        zone_high.name = "High Priority"
        zone_high.enabled = True
        zone_high.priority = 10
        zone_high.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            events = await service.process_detection(detection, zones=[zone_low, zone_high])

        assert len(events) == 1
        assert events[0]["type"] == "zone.enter"
        assert events[0]["data"]["zone_id"] == "zone-high"

    @pytest.mark.asyncio
    async def test_entity_exits_to_no_zone(self) -> None:
        """Test entity exiting zone to open space (no zone)."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        # First detection inside zone
        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter
            await service.process_detection(detection1, zones=[zone])

            # Second detection outside all zones
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = datetime(2026, 1, 21, 14, 31, 0, tzinfo=UTC)
            detection2.thumbnail_path = None
            detection2.bbox_x = 1800
            detection2.bbox_y = 900
            detection2.bbox_width = 50
            detection2.bbox_height = 100

            events = await service.process_detection(detection2, zones=[zone])

        assert len(events) == 1
        assert events[0]["type"] == "zone.exit"
        assert service.get_entity_zone("entity-001") is None

    def test_entity_type_normalization(self) -> None:
        """Test that entity types are normalized to lowercase."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        service = ZoneCrossingService()

        detection = MagicMock()
        detection.object_type = "PERSON"
        detection.enrichment_data = None

        result = service._compute_entity_type(detection)
        assert result == "person"

    @pytest.mark.asyncio
    async def test_disabled_zone_ignored(self) -> None:
        """Test that disabled zones are ignored."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = False
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            events = await service.process_detection(detection, zones=[zone])

        # No events since zone is disabled
        assert events == []


# =============================================================================
# Event Schema Validation Tests
# =============================================================================


class TestEventSchema:
    """Tests for event schema compliance."""

    @pytest.mark.asyncio
    async def test_enter_event_schema(self) -> None:
        """Test that enter events follow the expected schema."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = "/thumbnails/test.jpg"
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            events = await service.process_detection(detection, zones=[zone])

        event = events[0]
        assert event["type"] == "zone.enter"
        data = event["data"]
        assert "zone_id" in data
        assert "zone_name" in data
        assert "entity_id" in data
        assert "entity_type" in data
        assert "detection_id" in data
        assert "timestamp" in data
        assert "thumbnail_url" in data
        assert "dwell_time" in data

    @pytest.mark.asyncio
    async def test_exit_event_includes_dwell_time(self) -> None:
        """Test that exit events include dwell_time."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = base_time
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone
            await service.process_detection(detection1, zones=[zone])

            # Exit zone 60 seconds later
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = base_time + timedelta(seconds=60)
            detection2.thumbnail_path = None
            detection2.bbox_x = 1800
            detection2.bbox_y = 900
            detection2.bbox_width = 50
            detection2.bbox_height = 100

            events = await service.process_detection(detection2, zones=[zone])

        event = events[0]
        assert event["type"] == "zone.exit"
        assert event["data"]["dwell_time"] == 60.0

    @pytest.mark.asyncio
    async def test_dwell_event_schema(self) -> None:
        """Test that dwell events follow the expected schema."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        detection1 = MagicMock()
        detection1.id = 123
        detection1.object_type = "person"
        detection1.enrichment_data = {"entity_id": "entity-001"}
        detection1.detected_at = base_time
        detection1.thumbnail_path = None
        detection1.bbox_x = 100
        detection1.bbox_y = 100
        detection1.bbox_width = 100
        detection1.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone
            await service.process_detection(detection1, zones=[zone])

            # Stay in zone for 35 seconds
            detection2 = MagicMock()
            detection2.id = 124
            detection2.object_type = "person"
            detection2.enrichment_data = {"entity_id": "entity-001"}
            detection2.detected_at = base_time + timedelta(seconds=35)
            detection2.thumbnail_path = None
            detection2.bbox_x = 100
            detection2.bbox_y = 100
            detection2.bbox_width = 100
            detection2.bbox_height = 100

            events = await service.process_detection(detection2, zones=[zone])

        event = events[0]
        assert event["type"] == "zone.dwell"
        data = event["data"]
        assert data["dwell_time"] >= 30.0
        assert "zone_id" in data
        assert "zone_name" in data
        assert "entity_id" in data


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestAdditionalCoverage:
    """Additional tests to improve coverage."""

    @pytest.mark.asyncio
    async def test_uses_default_image_dimensions(self) -> None:
        """Test that default image dimensions are used when not provided."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            # No image dimensions provided - should use defaults
            events = await service.process_detection(detection, zones=[zone])

        assert len(events) == 1

    def test_entity_position_attributes_mutable(self) -> None:
        """Test that EntityPosition attributes can be modified."""
        from backend.services.zone_crossing_service import EntityPosition

        pos = EntityPosition(entity_id="test-123")
        pos.entity_type = "vehicle"
        pos.current_zone_id = "zone-xyz"
        pos.entered_at = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)
        pos.last_detection_id = "det-999"
        pos.last_thumbnail_url = "/path/to/thumb.jpg"

        assert pos.entity_type == "vehicle"
        assert pos.current_zone_id == "zone-xyz"

    @pytest.mark.asyncio
    async def test_emit_zone_enter_directly(self) -> None:
        """Test _emit_zone_enter method directly."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            event = await service._emit_zone_enter(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url="/thumb.jpg",
            )

        assert event["type"] == "zone.enter"
        assert event["data"]["thumbnail_url"] == "/thumb.jpg"

    @pytest.mark.asyncio
    async def test_emit_zone_exit_directly(self) -> None:
        """Test _emit_zone_exit method directly."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            event = await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=45.5,
            )

        assert event["type"] == "zone.exit"
        assert event["data"]["dwell_time"] == 45.5

    @pytest.mark.asyncio
    async def test_emit_zone_dwell_directly(self) -> None:
        """Test _emit_zone_dwell method directly."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            event = await service._emit_zone_dwell(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url="/thumb.jpg",
                dwell_time=60.0,
            )

        assert event["type"] == "zone.dwell"
        assert event["data"]["dwell_time"] == 60.0

    def test_get_entity_dwell_time_no_zone(self) -> None:
        """Test get_entity_dwell_time when entity has no zone."""
        from backend.services.zone_crossing_service import (
            EntityPosition,
            ZoneCrossingService,
        )

        service = ZoneCrossingService()

        # Create entity position with no zone
        service._entity_positions["entity-001"] = EntityPosition(
            entity_id="entity-001",
            current_zone_id=None,
        )

        result = service.get_entity_dwell_time("entity-001")
        assert result is None

    def test_get_entity_dwell_time_no_entered_at(self) -> None:
        """Test get_entity_dwell_time when entity has no entered_at."""
        from backend.services.zone_crossing_service import (
            EntityPosition,
            ZoneCrossingService,
        )

        service = ZoneCrossingService()

        # Create entity position with zone but no entered_at
        service._entity_positions["entity-001"] = EntityPosition(
            entity_id="entity-001",
            current_zone_id="zone-abc",
            entered_at=None,
        )

        result = service.get_entity_dwell_time("entity-001")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_entity_removes_dwell_tracking(self) -> None:
        """Test that clear_entity removes dwell event tracking."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        def make_detection(det_id: int, seconds_offset: int) -> MagicMock:
            det = MagicMock()
            det.id = det_id
            det.object_type = "person"
            det.enrichment_data = {"entity_id": "entity-001"}
            det.detected_at = base_time + timedelta(seconds=seconds_offset)
            det.thumbnail_path = None
            det.bbox_x = 100
            det.bbox_y = 100
            det.bbox_width = 100
            det.bbox_height = 100
            return det

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Enter zone and emit dwell event
            await service.process_detection(make_detection(1, 0), zones=[zone])
            await service.process_detection(make_detection(2, 35), zones=[zone])

            # Dwell events should be tracked
            assert len(service._dwell_events_emitted) > 0

            # Clear entity
            service.clear_entity("entity-001")

            # Dwell tracking should be cleared
            assert len(service._dwell_events_emitted) == 0

    @pytest.mark.asyncio
    async def test_zone_not_found_in_transition(self) -> None:
        """Test handling when zone is not found during transition."""
        from backend.services.zone_crossing_service import (
            EntityPosition,
            ZoneCrossingService,
        )

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # Manually set entity to be in a zone that won't be in the zones list
        service._entity_positions["entity-001"] = EntityPosition(
            entity_id="entity-001",
            entity_type="person",
            current_zone_id="nonexistent-zone",
            entered_at=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
        )
        service._zone_occupants["nonexistent-zone"].add("entity-001")

        zone = MagicMock()
        zone.id = "zone-abc"
        zone.name = "Front Yard"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        detection = MagicMock()
        detection.id = 123
        detection.object_type = "person"
        detection.enrichment_data = {"entity_id": "entity-001"}
        detection.detected_at = datetime(2026, 1, 21, 14, 31, 0, tzinfo=UTC)
        detection.thumbnail_path = None
        detection.bbox_x = 100
        detection.bbox_y = 100
        detection.bbox_width = 100
        detection.bbox_height = 100

        with patch("backend.core.config.get_settings") as mock_settings:
            mock_settings.return_value.redis_event_channel = "hsi:events"
            # Should handle missing zone gracefully
            events = await service.process_detection(detection, zones=[zone])

        # Should only emit enter event for new zone (no exit for nonexistent zone)
        assert len(events) == 1
        assert events[0]["type"] == "zone.enter"


# =============================================================================
# Prometheus Metrics Integration Tests (NEM-4141)
# =============================================================================


class TestZoneCrossingMetrics:
    """Tests for Prometheus metrics emission in zone crossing events."""

    @pytest.mark.asyncio
    async def test_emit_zone_enter_records_crossing_metric(self) -> None:
        """Test that _emit_zone_enter records hsi_zone_crossings_total metric."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-001"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.record_zone_crossing"
            ) as mock_record_crossing,
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy"
            ) as mock_set_occupancy,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_enter(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
            )

        # Verify crossing metric was recorded with enter direction
        mock_record_crossing.assert_called_once_with(
            zone_id="zone-metrics-001", direction="enter", entity_type="person"
        )
        # Verify occupancy was updated
        mock_set_occupancy.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_zone_exit_records_crossing_metric(self) -> None:
        """Test that _emit_zone_exit records hsi_zone_crossings_total metric."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-002"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.record_zone_crossing"
            ) as mock_record_crossing,
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time"
            ) as mock_observe_dwell,
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy"
            ) as mock_set_occupancy,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="vehicle",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=45.5,
            )

        # Verify crossing metric was recorded with exit direction
        mock_record_crossing.assert_called_once_with(
            zone_id="zone-metrics-002", direction="exit", entity_type="vehicle"
        )
        # Verify dwell time was recorded
        mock_observe_dwell.assert_called_once_with(
            zone_id="zone-metrics-002", duration_seconds=45.5
        )
        # Verify occupancy was updated
        mock_set_occupancy.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_zone_exit_skips_dwell_time_when_none(self) -> None:
        """Test that _emit_zone_exit skips dwell time metric when None."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-003"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.record_zone_crossing"
            ) as mock_record_crossing,
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time"
            ) as mock_observe_dwell,
            patch("backend.services.zone_crossing_service.set_zone_occupancy"),
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=None,  # No dwell time
            )

        # Crossing metric should still be recorded
        mock_record_crossing.assert_called_once()
        # Dwell time should NOT be recorded when None
        mock_observe_dwell.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_zone_exit_skips_dwell_time_when_zero(self) -> None:
        """Test that _emit_zone_exit skips dwell time metric when zero."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-004"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch("backend.services.zone_crossing_service.record_zone_crossing"),
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time"
            ) as mock_observe_dwell,
            patch("backend.services.zone_crossing_service.set_zone_occupancy"),
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=0.0,  # Zero dwell time
            )

        # Dwell time should NOT be recorded when zero
        mock_observe_dwell.assert_not_called()

    @pytest.mark.asyncio
    async def test_emit_zone_dwell_records_dwell_time_metric(self) -> None:
        """Test that _emit_zone_dwell records hsi_zone_dwell_time_seconds metric."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-005"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time"
            ) as mock_observe_dwell,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_dwell(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url="/thumb.jpg",
                dwell_time=120.0,
            )

        # Verify dwell time metric was recorded
        mock_observe_dwell.assert_called_once_with(
            zone_id="zone-metrics-005", duration_seconds=120.0
        )

    @pytest.mark.asyncio
    async def test_emit_zone_dwell_skips_zero_dwell_time(self) -> None:
        """Test that _emit_zone_dwell skips metric when dwell_time is zero."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-metrics-006"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time"
            ) as mock_observe_dwell,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_dwell(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=0.0,
            )

        # Dwell time should NOT be recorded when zero
        mock_observe_dwell.assert_not_called()

    @pytest.mark.asyncio
    async def test_zone_enter_occupancy_gauge_incremented(self) -> None:
        """Test that zone occupancy gauge is incremented on zone enter."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # Pre-populate zone with one occupant
        service._zone_occupants["zone-metrics-007"].add("existing-entity")

        zone = MagicMock()
        zone.id = "zone-metrics-007"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch("backend.services.zone_crossing_service.record_zone_crossing"),
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy"
            ) as mock_set_occupancy,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_enter(
                zone=zone,
                entity_id="new-entity",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
            )

        # Occupancy should be set to 2 (existing + new)
        mock_set_occupancy.assert_called_once_with(zone_id="zone-metrics-007", count=2)

    @pytest.mark.asyncio
    async def test_zone_exit_occupancy_gauge_decremented(self) -> None:
        """Test that zone occupancy gauge is decremented on zone exit."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # Pre-populate zone with two occupants
        service._zone_occupants["zone-metrics-008"].add("entity-001")
        service._zone_occupants["zone-metrics-008"].add("entity-002")

        zone = MagicMock()
        zone.id = "zone-metrics-008"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch("backend.services.zone_crossing_service.record_zone_crossing"),
            patch("backend.services.zone_crossing_service.observe_zone_dwell_time"),
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy"
            ) as mock_set_occupancy,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=30.0,
            )

        # Occupancy should be set to 1 (2 - 1)
        mock_set_occupancy.assert_called_once_with(zone_id="zone-metrics-008", count=1)

    @pytest.mark.asyncio
    async def test_zone_exit_occupancy_does_not_go_negative(self) -> None:
        """Test that zone occupancy gauge does not go below zero."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        # Empty zone (edge case)
        zone = MagicMock()
        zone.id = "zone-metrics-009"
        zone.name = "Test Zone"

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch("backend.services.zone_crossing_service.record_zone_crossing"),
            patch("backend.services.zone_crossing_service.observe_zone_dwell_time"),
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy"
            ) as mock_set_occupancy,
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"
            await service._emit_zone_exit(
                zone=zone,
                entity_id="entity-001",
                entity_type="person",
                detection_id="123",
                timestamp=datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC),
                thumbnail_url=None,
                dwell_time=10.0,
            )

        # Occupancy should be 0, not negative
        mock_set_occupancy.assert_called_once_with(zone_id="zone-metrics-009", count=0)

    @pytest.mark.asyncio
    async def test_full_enter_exit_flow_emits_all_metrics(self) -> None:
        """Test that a full enter-exit flow emits all expected metrics."""
        from backend.services.zone_crossing_service import ZoneCrossingService

        mock_redis = AsyncMock()
        service = ZoneCrossingService(redis_client=mock_redis)

        zone = MagicMock()
        zone.id = "zone-flow-test"
        zone.name = "Flow Test Zone"
        zone.enabled = True
        zone.priority = 1
        zone.coordinates = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]

        base_time = datetime(2026, 1, 21, 14, 30, 0, tzinfo=UTC)

        def make_detection(det_id: int, seconds_offset: int, inside_zone: bool) -> MagicMock:
            det = MagicMock()
            det.id = det_id
            det.object_type = "person"
            det.enrichment_data = {"entity_id": "flow-entity"}
            det.detected_at = base_time + timedelta(seconds=seconds_offset)
            det.thumbnail_path = None
            # Inside zone: (100, 100) -> normalized (0.05, 0.09) -> inside [0,0.5]x[0,0.5]
            # Outside zone: (1200, 800) -> normalized (0.625, 0.74) -> outside
            if inside_zone:
                det.bbox_x = 100
                det.bbox_y = 100
            else:
                det.bbox_x = 1200
                det.bbox_y = 800
            det.bbox_width = 100
            det.bbox_height = 100
            return det

        crossing_calls = []
        occupancy_calls = []
        dwell_calls = []

        def capture_crossing(*args, **kwargs):
            crossing_calls.append(kwargs)

        def capture_occupancy(*args, **kwargs):
            occupancy_calls.append(kwargs)

        def capture_dwell(*args, **kwargs):
            dwell_calls.append(kwargs)

        with (
            patch("backend.core.config.get_settings") as mock_settings,
            patch(
                "backend.services.zone_crossing_service.record_zone_crossing",
                side_effect=capture_crossing,
            ),
            patch(
                "backend.services.zone_crossing_service.set_zone_occupancy",
                side_effect=capture_occupancy,
            ),
            patch(
                "backend.services.zone_crossing_service.observe_zone_dwell_time",
                side_effect=capture_dwell,
            ),
        ):
            mock_settings.return_value.redis_event_channel = "hsi:events"

            # Detection 1: Outside zone (no events)
            await service.process_detection(make_detection(1, 0, inside_zone=False), zones=[zone])

            # Detection 2: Enter zone
            await service.process_detection(make_detection(2, 10, inside_zone=True), zones=[zone])

            # Detection 3: Still in zone (dwell event after threshold)
            await service.process_detection(make_detection(3, 45, inside_zone=True), zones=[zone])

            # Detection 4: Exit zone
            await service.process_detection(make_detection(4, 60, inside_zone=False), zones=[zone])

        # Verify crossing metrics: 1 enter + 1 exit
        assert len(crossing_calls) == 2
        assert crossing_calls[0]["direction"] == "enter"
        assert crossing_calls[1]["direction"] == "exit"

        # Verify occupancy updates: enter sets to 1, exit sets to 0
        assert len(occupancy_calls) == 2
        assert occupancy_calls[0]["count"] == 1  # Enter
        assert occupancy_calls[1]["count"] == 0  # Exit

        # Verify dwell time metrics: dwell event + exit dwell time
        assert len(dwell_calls) >= 1  # At least exit dwell time
