"""Unit tests for alert deduplication service.

Tests use PostgreSQL via the isolated_db fixture since models use
PostgreSQL-specific features.
"""

from datetime import datetime, timedelta

import pytest

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Camera, Event
from backend.services.alert_dedup import (
    AlertDeduplicationService,
    DedupResult,
    build_dedup_key,
)


@pytest.fixture
async def session(isolated_db):
    """Create a new database session for each test.

    Uses PostgreSQL via the isolated_db fixture from conftest.py.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session


@pytest.fixture
async def test_camera(session):
    """Create a test camera for use in dedup tests."""
    camera = Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_event(session, test_camera):
    """Create a test event for use in dedup tests."""
    event = Event(
        batch_id="batch_001",
        camera_id=test_camera.id,
        started_at=datetime.utcnow(),
        risk_score=80,
        risk_level="high",
    )
    session.add(event)
    await session.flush()
    return event


@pytest.fixture
async def dedup_service(session):
    """Create a deduplication service instance."""
    return AlertDeduplicationService(session)


class TestBuildDedupKey:
    """Tests for the build_dedup_key helper function."""

    def test_build_dedup_key_camera_only(self):
        """Test building dedup key with camera ID only."""
        key = build_dedup_key("front_door")
        assert key == "front_door"

    def test_build_dedup_key_camera_and_object(self):
        """Test building dedup key with camera and object type."""
        key = build_dedup_key("front_door", object_type="person")
        assert key == "front_door:person"

    def test_build_dedup_key_all_components(self):
        """Test building dedup key with all components."""
        key = build_dedup_key("front_door", object_type="person", zone="entry_zone")
        assert key == "front_door:person:entry_zone"

    def test_build_dedup_key_camera_and_zone(self):
        """Test building dedup key with camera and zone (no object type)."""
        key = build_dedup_key("front_door", zone="entry_zone")
        assert key == "front_door:entry_zone"

    def test_build_dedup_key_empty_strings(self):
        """Test that empty strings are treated as None."""
        # Empty strings should be falsy and excluded
        key = build_dedup_key("front_door", object_type="", zone="")
        assert key == "front_door"


class TestDedupResult:
    """Tests for the DedupResult dataclass."""

    def test_dedup_result_not_duplicate(self):
        """Test DedupResult when not a duplicate."""
        result = DedupResult(is_duplicate=False)
        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.existing_alert_id is None
        assert result.seconds_until_cooldown_expires is None

    def test_dedup_result_is_duplicate(self):
        """Test DedupResult when it is a duplicate."""

        # Create a mock alert-like object
        class MockAlert:
            id = "test-alert-123"

        result = DedupResult(
            is_duplicate=True,
            existing_alert=MockAlert(),
            seconds_until_cooldown_expires=180,
        )
        assert result.is_duplicate is True
        assert result.existing_alert_id == "test-alert-123"
        assert result.seconds_until_cooldown_expires == 180


class TestAlertDeduplicationService:
    """Tests for the AlertDeduplicationService."""

    @pytest.mark.asyncio
    async def test_check_duplicate_no_existing_alert(self, session, dedup_service, test_event):
        """Test check_duplicate when no existing alert."""
        result = await dedup_service.check_duplicate(
            dedup_key="front_door:person:entry_zone",
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.existing_alert_id is None

    @pytest.mark.asyncio
    async def test_check_duplicate_existing_alert_within_cooldown(
        self, session, dedup_service, test_event
    ):
        """Test check_duplicate when an alert exists within cooldown."""
        # Create an existing alert
        existing_alert = Alert(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            created_at=datetime.utcnow() - timedelta(minutes=2),  # 2 minutes ago
        )
        session.add(existing_alert)
        await session.flush()

        # Check for duplicate (5 minute cooldown)
        result = await dedup_service.check_duplicate(
            dedup_key="front_door:person:entry_zone",
            cooldown_seconds=300,
        )

        assert result.is_duplicate is True
        assert result.existing_alert_id == existing_alert.id
        assert result.seconds_until_cooldown_expires is not None
        # Should have about 3 minutes remaining (180 seconds, give or take)
        assert 170 <= result.seconds_until_cooldown_expires <= 190

    @pytest.mark.asyncio
    async def test_check_duplicate_existing_alert_outside_cooldown(
        self, session, dedup_service, test_event
    ):
        """Test check_duplicate when an alert exists but outside cooldown."""
        # Create an old alert
        old_alert = Alert(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            created_at=datetime.utcnow() - timedelta(minutes=10),  # 10 minutes ago
        )
        session.add(old_alert)
        await session.flush()

        # Check for duplicate (5 minute cooldown)
        result = await dedup_service.check_duplicate(
            dedup_key="front_door:person:entry_zone",
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False
        assert result.existing_alert is None

    @pytest.mark.asyncio
    async def test_check_duplicate_different_dedup_key(self, session, dedup_service, test_event):
        """Test check_duplicate with different dedup keys."""
        # Create an alert with one key
        existing_alert = Alert(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            created_at=datetime.utcnow(),
        )
        session.add(existing_alert)
        await session.flush()

        # Check with different key
        result = await dedup_service.check_duplicate(
            dedup_key="backyard:vehicle:driveway",
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_get_cooldown_for_rule_with_rule(self, session, dedup_service):
        """Test get_cooldown_for_rule with an existing rule."""
        rule = AlertRule(
            name="Test Rule",
            cooldown_seconds=600,
        )
        session.add(rule)
        await session.flush()

        cooldown = await dedup_service.get_cooldown_for_rule(rule.id)
        assert cooldown == 600

    @pytest.mark.asyncio
    async def test_get_cooldown_for_rule_no_rule(self, session, dedup_service):
        """Test get_cooldown_for_rule with no rule (None)."""
        cooldown = await dedup_service.get_cooldown_for_rule(None)
        assert cooldown == 300  # Default

    @pytest.mark.asyncio
    async def test_get_cooldown_for_rule_nonexistent(self, session, dedup_service):
        """Test get_cooldown_for_rule with non-existent rule ID."""
        cooldown = await dedup_service.get_cooldown_for_rule("nonexistent-rule-id-12345678")
        assert cooldown == 300  # Default

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_new_alert(
        self, session, dedup_service, test_event
    ):
        """Test create_alert_if_not_duplicate creates a new alert."""
        alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            severity=AlertSeverity.HIGH,
            channels=["pushover"],
            alert_metadata={"camera_name": "Front Door"},
        )

        assert is_new is True
        assert alert.event_id == test_event.id
        assert alert.dedup_key == "front_door:person:entry_zone"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.channels == ["pushover"]
        assert alert.alert_metadata == {"camera_name": "Front Door"}

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_returns_existing(
        self, session, dedup_service, test_event
    ):
        """Test create_alert_if_not_duplicate returns existing alert."""
        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            severity=AlertSeverity.HIGH,
        )
        assert is_new is True

        # Try to create duplicate
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person:entry_zone",
            severity=AlertSeverity.CRITICAL,  # Different severity
        )

        assert is_new is False
        assert second_alert.id == first_alert.id
        # Severity should be from original alert
        assert second_alert.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_uses_rule_cooldown(
        self, session, dedup_service, test_event
    ):
        """Test that create_alert uses rule's cooldown setting."""
        # Create rule with short cooldown
        rule = AlertRule(
            name="Short Cooldown Rule",
            cooldown_seconds=60,  # 1 minute
        )
        session.add(rule)
        await session.flush()

        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person",
            rule_id=rule.id,
        )
        assert is_new is True

        # Manually backdate the alert to 30 seconds ago
        first_alert.created_at = datetime.utcnow() - timedelta(seconds=30)
        await session.flush()

        # Try to create another - should be duplicate (within 60s cooldown)
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person",
            rule_id=rule.id,
        )
        assert is_new is False
        assert second_alert.id == first_alert.id

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_override_cooldown(
        self, session, dedup_service, test_event
    ):
        """Test create_alert with explicit cooldown override."""
        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person",
            cooldown_seconds=60,
        )
        assert is_new is True

        # Backdate to 90 seconds ago
        first_alert.created_at = datetime.utcnow() - timedelta(seconds=90)
        await session.flush()

        # Try to create with same 60s cooldown - should NOT be duplicate
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key="front_door:person",
            cooldown_seconds=60,
        )
        assert is_new is True
        assert second_alert.id != first_alert.id

    @pytest.mark.asyncio
    async def test_get_recent_alerts_for_key(self, session, dedup_service, test_event):
        """Test getting recent alerts for a dedup key."""
        now = datetime.utcnow()

        # Create alerts at different times
        for i in range(5):
            alert = Alert(
                event_id=test_event.id,
                dedup_key="front_door:person",
                created_at=now - timedelta(hours=i * 6),  # 0, 6, 12, 18, 24 hours ago
            )
            session.add(alert)
        await session.flush()

        # Get alerts from last 24 hours
        recent = await dedup_service.get_recent_alerts_for_key(
            dedup_key="front_door:person",
            hours=24,
        )

        # Should get all 5 alerts (24 hours lookback includes all)
        assert len(recent) == 5
        # Should be ordered by most recent first
        assert recent[0].created_at > recent[-1].created_at

    @pytest.mark.asyncio
    async def test_get_recent_alerts_for_key_limited(self, session, dedup_service, test_event):
        """Test getting recent alerts with limit."""
        now = datetime.utcnow()

        # Create 10 alerts
        for i in range(10):
            alert = Alert(
                event_id=test_event.id,
                dedup_key="front_door:person",
                created_at=now - timedelta(minutes=i),
            )
            session.add(alert)
        await session.flush()

        # Get only 3 most recent
        recent = await dedup_service.get_recent_alerts_for_key(
            dedup_key="front_door:person",
            hours=24,
            limit=3,
        )

        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_get_duplicate_stats(self, session, dedup_service, test_event):
        """Test getting deduplication statistics."""
        now = datetime.utcnow()

        # Create alerts with various dedup keys
        dedup_keys = [
            "front_door:person",
            "front_door:person",  # duplicate
            "backyard:vehicle",
            "garage:person",
            "front_door:person",  # another duplicate
        ]

        for key in dedup_keys:
            alert = Alert(
                event_id=test_event.id,
                dedup_key=key,
                created_at=now - timedelta(minutes=5),
            )
            session.add(alert)
        await session.flush()

        stats = await dedup_service.get_duplicate_stats(hours=24)

        assert stats["total_alerts"] == 5
        assert stats["unique_dedup_keys"] == 3
        assert stats["dedup_ratio"] == 0.6  # 3/5 = 0.6

    @pytest.mark.asyncio
    async def test_get_duplicate_stats_empty(self, session, dedup_service):
        """Test duplicate stats with no alerts."""
        stats = await dedup_service.get_duplicate_stats(hours=24)

        assert stats["total_alerts"] == 0
        assert stats["unique_dedup_keys"] == 0
        assert stats["dedup_ratio"] == 0


class TestDedupCooldownBehavior:
    """Tests for cooldown window edge cases."""

    @pytest.mark.asyncio
    async def test_cooldown_boundary_exact(self, session, test_event, dedup_service):
        """Test behavior at exact cooldown boundary."""
        # Create an alert exactly at cooldown boundary
        cooldown_seconds = 300
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test:boundary",
            created_at=datetime.utcnow() - timedelta(seconds=cooldown_seconds),
        )
        session.add(alert)
        await session.flush()

        # This should NOT be a duplicate (at exact boundary)
        result = await dedup_service.check_duplicate(
            dedup_key="test:boundary",
            cooldown_seconds=cooldown_seconds,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_cooldown_just_inside(self, session, test_event, dedup_service):
        """Test behavior just inside cooldown window."""
        cooldown_seconds = 300
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test:inside",
            created_at=datetime.utcnow() - timedelta(seconds=cooldown_seconds - 1),
        )
        session.add(alert)
        await session.flush()

        # This should be a duplicate (1 second inside window)
        result = await dedup_service.check_duplicate(
            dedup_key="test:inside",
            cooldown_seconds=cooldown_seconds,
        )

        assert result.is_duplicate is True
        assert result.seconds_until_cooldown_expires == 1

    @pytest.mark.asyncio
    async def test_zero_cooldown(self, session, test_event, dedup_service):
        """Test with zero cooldown (effectively no deduplication)."""
        # Create an alert just now
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test:zero",
            created_at=datetime.utcnow(),
        )
        session.add(alert)
        await session.flush()

        # With zero cooldown, should NOT be duplicate
        result = await dedup_service.check_duplicate(
            dedup_key="test:zero",
            cooldown_seconds=0,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_multiple_duplicates_returns_most_recent(
        self, session, test_event, dedup_service
    ):
        """Test that check_duplicate returns the most recent alert."""
        now = datetime.utcnow()

        # Create multiple alerts with same dedup_key
        for i in range(3):
            alert = Alert(
                event_id=test_event.id,
                dedup_key="test:multiple",
                severity=AlertSeverity.LOW if i < 2 else AlertSeverity.HIGH,
                created_at=now - timedelta(minutes=i),  # 0, 1, 2 minutes ago
            )
            session.add(alert)
        await session.flush()

        result = await dedup_service.check_duplicate(
            dedup_key="test:multiple",
            cooldown_seconds=300,
        )

        assert result.is_duplicate is True
        # Should return the most recent (HIGH severity, 0 minutes ago)
        assert result.existing_alert.severity == AlertSeverity.HIGH
