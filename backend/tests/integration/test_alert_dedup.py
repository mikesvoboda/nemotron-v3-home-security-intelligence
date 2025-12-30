"""Integration tests for alert deduplication service.

Tests use PostgreSQL via the isolated_db fixture since models use
PostgreSQL-specific features. Unit tests for pure functions (build_dedup_key,
DedupResult) are in backend/tests/unit/test_alert_dedup.py.
"""

from datetime import datetime, timedelta

import pytest

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Camera, Event
from backend.services.alert_dedup import AlertDeduplicationService
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
pytestmark = pytest.mark.integration

# Note: The 'session' fixture is provided by conftest.py with transaction
# rollback isolation for parallel test execution.


@pytest.fixture
def test_prefix():
    """Generate a unique prefix for this test run to ensure isolation."""
    return unique_id("dedup")


@pytest.fixture
async def test_camera(session, test_prefix):
    """Create a test camera for use in dedup tests."""
    camera_id = f"{test_prefix}_front_door"
    camera = Camera(
        id=camera_id,
        name="Front Door Camera",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_event(session, test_camera):
    """Create a test event for use in dedup tests."""
    event = Event(
        batch_id=unique_id("batch"),
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


class TestAlertDeduplicationService:
    """Tests for the AlertDeduplicationService."""

    @pytest.mark.asyncio
    async def test_check_duplicate_no_existing_alert(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test check_duplicate when no existing alert."""
        dedup_key = f"{test_prefix}:person:entry_zone"
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False
        assert result.existing_alert is None
        assert result.existing_alert_id is None

    @pytest.mark.asyncio
    async def test_check_duplicate_existing_alert_within_cooldown(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test check_duplicate when an alert exists within cooldown."""
        dedup_key = f"{test_prefix}:person:entry_zone"
        # Create an existing alert
        existing_alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key,
            created_at=datetime.utcnow() - timedelta(minutes=2),  # 2 minutes ago
        )
        session.add(existing_alert)
        await session.flush()

        # Check for duplicate (5 minute cooldown)
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=300,
        )

        assert result.is_duplicate is True
        assert result.existing_alert_id == existing_alert.id
        assert result.seconds_until_cooldown_expires is not None
        # Should have about 3 minutes remaining (180 seconds, give or take)
        assert 170 <= result.seconds_until_cooldown_expires <= 190

    @pytest.mark.asyncio
    async def test_check_duplicate_existing_alert_outside_cooldown(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test check_duplicate when an alert exists but outside cooldown."""
        dedup_key = f"{test_prefix}:person:entry_zone"
        # Create an old alert
        old_alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key,
            created_at=datetime.utcnow() - timedelta(minutes=10),  # 10 minutes ago
        )
        session.add(old_alert)
        await session.flush()

        # Check for duplicate (5 minute cooldown)
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False
        assert result.existing_alert is None

    @pytest.mark.asyncio
    async def test_check_duplicate_different_dedup_key(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test check_duplicate with different dedup keys."""
        dedup_key1 = f"{test_prefix}:person:entry_zone"
        dedup_key2 = f"{test_prefix}:vehicle:driveway"
        # Create an alert with one key
        existing_alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key1,
            created_at=datetime.utcnow(),
        )
        session.add(existing_alert)
        await session.flush()

        # Check with different key
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key2,
            cooldown_seconds=300,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_get_cooldown_for_rule_with_rule(self, session, dedup_service, test_prefix):
        """Test get_cooldown_for_rule with an existing rule."""
        rule = AlertRule(
            name=f"Test Rule {test_prefix}",
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
        import uuid

        # Use a valid UUID format since the rule_id column is UUID type
        nonexistent_uuid = str(uuid.uuid4())
        cooldown = await dedup_service.get_cooldown_for_rule(nonexistent_uuid)
        assert cooldown == 300  # Default

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_new_alert(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test create_alert_if_not_duplicate creates a new alert."""
        dedup_key = f"{test_prefix}:person:entry_zone"
        alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            severity=AlertSeverity.HIGH,
            channels=["pushover"],
            alert_metadata={"camera_name": "Front Door"},
        )

        assert is_new is True
        assert alert.event_id == test_event.id
        assert alert.dedup_key == dedup_key
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.channels == ["pushover"]
        assert alert.alert_metadata == {"camera_name": "Front Door"}

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_returns_existing(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test create_alert_if_not_duplicate returns existing alert."""
        dedup_key = f"{test_prefix}:person:entry_zone"
        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            severity=AlertSeverity.HIGH,
        )
        assert is_new is True

        # Try to create duplicate
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            severity=AlertSeverity.CRITICAL,  # Different severity
        )

        assert is_new is False
        assert second_alert.id == first_alert.id
        # Severity should be from original alert
        assert second_alert.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_uses_rule_cooldown(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test that create_alert uses rule's cooldown setting."""
        dedup_key = f"{test_prefix}:person"
        # Create rule with short cooldown
        rule = AlertRule(
            name=f"Short Cooldown Rule {test_prefix}",
            cooldown_seconds=60,  # 1 minute
        )
        session.add(rule)
        await session.flush()

        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            rule_id=rule.id,
        )
        assert is_new is True

        # Manually backdate the alert to 30 seconds ago
        first_alert.created_at = datetime.utcnow() - timedelta(seconds=30)
        await session.flush()

        # Try to create another - should be duplicate (within 60s cooldown)
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            rule_id=rule.id,
        )
        assert is_new is False
        assert second_alert.id == first_alert.id

    @pytest.mark.asyncio
    async def test_create_alert_if_not_duplicate_override_cooldown(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test create_alert with explicit cooldown override."""
        dedup_key = f"{test_prefix}:person"
        # Create first alert
        first_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            cooldown_seconds=60,
        )
        assert is_new is True

        # Backdate to 90 seconds ago
        first_alert.created_at = datetime.utcnow() - timedelta(seconds=90)
        await session.flush()

        # Try to create with same 60s cooldown - should NOT be duplicate
        second_alert, is_new = await dedup_service.create_alert_if_not_duplicate(
            event_id=test_event.id,
            dedup_key=dedup_key,
            cooldown_seconds=60,
        )
        assert is_new is True
        assert second_alert.id != first_alert.id

    @pytest.mark.asyncio
    async def test_get_recent_alerts_for_key(self, session, dedup_service, test_event, test_prefix):
        """Test getting recent alerts for a dedup key."""
        dedup_key = f"{test_prefix}:person"
        now = datetime.utcnow()

        # Create alerts at different times (all within 23 hours to avoid boundary issues)
        # The query uses >= cutoff_time, so we need to stay well within the window
        for i in range(5):
            alert = Alert(
                event_id=test_event.id,
                dedup_key=dedup_key,
                created_at=now - timedelta(hours=i * 4),  # 0, 4, 8, 12, 16 hours ago
            )
            session.add(alert)
        await session.flush()

        # Get alerts from last 24 hours
        recent = await dedup_service.get_recent_alerts_for_key(
            dedup_key=dedup_key,
            hours=24,
        )

        # Should get all 5 alerts (all well within the 24 hour lookback)
        assert len(recent) == 5
        # Should be ordered by most recent first
        assert recent[0].created_at > recent[-1].created_at

    @pytest.mark.asyncio
    async def test_get_recent_alerts_for_key_limited(
        self, session, dedup_service, test_event, test_prefix
    ):
        """Test getting recent alerts with limit."""
        dedup_key = f"{test_prefix}:person"
        now = datetime.utcnow()

        # Create 10 alerts
        for i in range(10):
            alert = Alert(
                event_id=test_event.id,
                dedup_key=dedup_key,
                created_at=now - timedelta(minutes=i),
            )
            session.add(alert)
        await session.flush()

        # Get only 3 most recent
        recent = await dedup_service.get_recent_alerts_for_key(
            dedup_key=dedup_key,
            hours=24,
            limit=3,
        )

        assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_get_duplicate_stats(self, session, dedup_service, test_event, test_prefix):
        """Test getting deduplication statistics.

        Note: This test creates alerts with unique prefixed dedup keys and
        verifies the count matches what was created in this test. With savepoint
        isolation, this test only sees its own data.
        """
        now = datetime.utcnow()

        # Create alerts with various dedup keys (all prefixed for isolation)
        dedup_keys = [
            f"{test_prefix}:person",
            f"{test_prefix}:person",  # duplicate
            f"{test_prefix}:vehicle",
            f"{test_prefix}:garage",
            f"{test_prefix}:person",  # another duplicate
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

        # With savepoint isolation, we should only see the 5 alerts we created
        assert stats["total_alerts"] == 5
        assert stats["unique_dedup_keys"] == 3
        assert stats["dedup_ratio"] == 0.6  # 3/5 = 0.6

    @pytest.mark.asyncio
    async def test_get_duplicate_stats_empty(self, session, dedup_service):
        """Test duplicate stats with no alerts.

        Note: With savepoint isolation, this test only sees its own data,
        so the database should appear empty from this test's perspective.
        """
        stats = await dedup_service.get_duplicate_stats(hours=24)

        assert stats["total_alerts"] == 0
        assert stats["unique_dedup_keys"] == 0
        assert stats["dedup_ratio"] == 0


class TestDedupCooldownBehavior:
    """Tests for cooldown window edge cases."""

    @pytest.mark.asyncio
    async def test_cooldown_boundary_exact(self, session, test_event, dedup_service, test_prefix):
        """Test behavior at exact cooldown boundary."""
        dedup_key = f"{test_prefix}:boundary"
        # Create an alert exactly at cooldown boundary
        cooldown_seconds = 300
        alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key,
            created_at=datetime.utcnow() - timedelta(seconds=cooldown_seconds),
        )
        session.add(alert)
        await session.flush()

        # This should NOT be a duplicate (at exact boundary)
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=cooldown_seconds,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_cooldown_just_inside(self, session, test_event, dedup_service, test_prefix):
        """Test behavior just inside cooldown window."""
        dedup_key = f"{test_prefix}:inside"
        cooldown_seconds = 300
        # Create alert 10 seconds inside the window (more buffer to avoid timing issues)
        alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key,
            created_at=datetime.utcnow() - timedelta(seconds=cooldown_seconds - 10),
        )
        session.add(alert)
        await session.flush()

        # This should be a duplicate (10 seconds inside window)
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=cooldown_seconds,
        )

        assert result.is_duplicate is True
        # Should have about 10 seconds remaining (give or take a few for test timing)
        assert 5 <= result.seconds_until_cooldown_expires <= 15

    @pytest.mark.asyncio
    async def test_zero_cooldown(self, session, test_event, dedup_service, test_prefix):
        """Test with zero cooldown (effectively no deduplication)."""
        dedup_key = f"{test_prefix}:zero"
        # Create an alert just now
        alert = Alert(
            event_id=test_event.id,
            dedup_key=dedup_key,
            created_at=datetime.utcnow(),
        )
        session.add(alert)
        await session.flush()

        # With zero cooldown, should NOT be duplicate
        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=0,
        )

        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_multiple_duplicates_returns_most_recent(
        self, session, test_event, dedup_service, test_prefix
    ):
        """Test that check_duplicate returns the most recent alert."""
        dedup_key = f"{test_prefix}:multiple"
        now = datetime.utcnow()

        # Create multiple alerts with same dedup_key at different times
        # The most recent alert (created last with smallest time offset) should be HIGH
        severities = [AlertSeverity.LOW, AlertSeverity.LOW, AlertSeverity.HIGH]
        for i in range(3):
            alert = Alert(
                event_id=test_event.id,
                dedup_key=dedup_key,
                severity=severities[i],
                # i=0: 2 min ago (oldest, LOW)
                # i=1: 1 min ago (middle, LOW)
                # i=2: 0 min ago (most recent, HIGH)
                created_at=now - timedelta(minutes=2 - i),
            )
            session.add(alert)
        await session.flush()

        result = await dedup_service.check_duplicate(
            dedup_key=dedup_key,
            cooldown_seconds=300,
        )

        assert result.is_duplicate is True
        # Should return the most recent (HIGH severity, created at 'now')
        assert result.existing_alert.severity == AlertSeverity.HIGH
