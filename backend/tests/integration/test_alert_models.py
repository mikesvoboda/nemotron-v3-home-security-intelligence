"""Unit tests for Alert and AlertRule SQLAlchemy models.

Tests use PostgreSQL via the isolated_db fixture since models use
PostgreSQL-specific features like JSONB and UUID.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from backend.models import (
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Camera,
    Event,
)
from backend.tests.conftest import unique_id


def utc_now_naive() -> datetime:
    """Return current UTC time as a naive datetime (for DB compatibility)."""
    return utc_now_naive().replace(tzinfo=None)


# Mark as integration since these tests require real PostgreSQL database
# NOTE: This file should be moved to backend/tests/integration/ in a future cleanup
pytestmark = pytest.mark.integration

# Note: The 'session' fixture is provided by conftest.py with transaction
# rollback isolation for parallel test execution.


@pytest.fixture
async def test_camera(session):
    """Create a test camera for use in alert tests."""
    camera_id = unique_id("test_camera")
    camera = Camera(
        id=camera_id,
        name="Test Camera",
        folder_path=f"/export/foscam/{camera_id}",
    )
    session.add(camera)
    await session.flush()
    return camera


@pytest.fixture
async def test_event(session, test_camera):
    """Create a test event for use in alert tests."""
    event = Event(
        batch_id=unique_id("batch"),
        camera_id=test_camera.id,
        started_at=utc_now_naive(),
        risk_score=75,
        risk_level="high",
    )
    session.add(event)
    await session.flush()
    return event


class TestAlertRuleModel:
    """Tests for the AlertRule model."""

    @pytest.mark.asyncio
    async def test_create_alert_rule_minimal(self, session):
        """Test creating an alert rule with minimal required fields."""
        rule = AlertRule(
            name="Test Rule",
        )
        session.add(rule)
        await session.flush()

        assert rule.id is not None
        assert rule.name == "Test Rule"
        assert rule.enabled is True
        assert rule.severity == AlertSeverity.MEDIUM
        assert rule.cooldown_seconds == 300
        assert isinstance(rule.created_at, datetime)
        assert isinstance(rule.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_create_alert_rule_full(self, session):
        """Test creating an alert rule with all fields."""
        rule = AlertRule(
            name="High Risk Person Alert",
            description="Alert when high-risk person detected",
            enabled=True,
            severity=AlertSeverity.HIGH,
            risk_threshold=70,
            object_types=["person", "vehicle"],
            camera_ids=["front_door", "backyard"],
            zone_ids=["entry_zone", "driveway"],
            min_confidence=0.8,
            schedule={
                "days": ["monday", "tuesday", "wednesday"],
                "start_time": "22:00",
                "end_time": "06:00",
                "timezone": "UTC",
            },
            dedup_key_template="{camera_id}:{object_type}:{rule_id}",
            cooldown_seconds=600,
            channels=["pushover", "webhook"],
        )
        session.add(rule)
        await session.flush()

        assert rule.name == "High Risk Person Alert"
        assert rule.description == "Alert when high-risk person detected"
        assert rule.severity == AlertSeverity.HIGH
        assert rule.risk_threshold == 70
        assert rule.object_types == ["person", "vehicle"]
        assert rule.camera_ids == ["front_door", "backyard"]
        assert rule.zone_ids == ["entry_zone", "driveway"]
        assert rule.min_confidence == 0.8
        assert rule.schedule["start_time"] == "22:00"
        assert rule.dedup_key_template == "{camera_id}:{object_type}:{rule_id}"
        assert rule.cooldown_seconds == 600
        assert rule.channels == ["pushover", "webhook"]

    @pytest.mark.asyncio
    async def test_alert_rule_severity_values(self, session):
        """Test all alert severity values."""
        severities = [
            AlertSeverity.LOW,
            AlertSeverity.MEDIUM,
            AlertSeverity.HIGH,
            AlertSeverity.CRITICAL,
        ]

        for i, severity in enumerate(severities):
            rule = AlertRule(
                name=f"Rule {i}",
                severity=severity,
            )
            session.add(rule)
            await session.flush()
            assert rule.severity == severity

    @pytest.mark.asyncio
    async def test_alert_rule_disabled(self, session):
        """Test creating a disabled alert rule."""
        rule = AlertRule(
            name="Disabled Rule",
            enabled=False,
        )
        session.add(rule)
        await session.flush()

        assert rule.enabled is False

    @pytest.mark.asyncio
    async def test_alert_rule_repr(self, session):
        """Test AlertRule string representation."""
        rule = AlertRule(
            name="Test Rule",
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)
        await session.flush()

        repr_str = repr(rule)
        assert "AlertRule" in repr_str
        assert "Test Rule" in repr_str
        assert "high" in repr_str

    @pytest.mark.asyncio
    async def test_query_enabled_rules(self, session):
        """Test querying only enabled rules."""
        # Create enabled and disabled rules
        for i in range(3):
            rule = AlertRule(
                name=f"Enabled Rule {i}",
                enabled=True,
            )
            session.add(rule)

        for i in range(2):
            rule = AlertRule(
                name=f"Disabled Rule {i}",
                enabled=False,
            )
            session.add(rule)

        await session.flush()

        # Query only enabled rules
        stmt = select(AlertRule).where(AlertRule.enabled.is_(True))
        result = await session.execute(stmt)
        enabled_rules = result.scalars().all()

        assert len(enabled_rules) == 3
        assert all(r.enabled for r in enabled_rules)


class TestAlertModel:
    """Tests for the Alert model."""

    @pytest.mark.asyncio
    async def test_create_alert_minimal(self, session, test_event):
        """Test creating an alert with minimal required fields."""
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test_camera:person",
        )
        session.add(alert)
        await session.flush()

        assert alert.id is not None
        assert alert.event_id == test_event.id
        assert alert.rule_id is None
        assert alert.severity == AlertSeverity.MEDIUM
        assert alert.status == AlertStatus.PENDING
        assert alert.dedup_key == "test_camera:person"
        assert isinstance(alert.created_at, datetime)
        assert isinstance(alert.updated_at, datetime)
        assert alert.delivered_at is None

    @pytest.mark.asyncio
    async def test_create_alert_full(self, session, test_event):
        """Test creating an alert with all fields."""
        # First create a rule
        rule = AlertRule(
            name="Test Rule",
            severity=AlertSeverity.HIGH,
        )
        session.add(rule)
        await session.flush()

        alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            severity=AlertSeverity.HIGH,
            status=AlertStatus.PENDING,
            dedup_key="test_camera:person:entry_zone",
            channels=["pushover", "email"],
            alert_metadata={"camera_name": "Test Camera", "risk_score": 85},
        )
        session.add(alert)
        await session.flush()

        assert alert.event_id == test_event.id
        assert alert.rule_id == rule.id
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.dedup_key == "test_camera:person:entry_zone"
        assert alert.channels == ["pushover", "email"]
        assert alert.alert_metadata["risk_score"] == 85

    @pytest.mark.asyncio
    async def test_alert_status_transitions(self, session, test_event):
        """Test alert status transitions."""
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test_camera:person",
            status=AlertStatus.PENDING,
        )
        session.add(alert)
        await session.flush()

        # Transition to delivered
        alert.status = AlertStatus.DELIVERED
        alert.delivered_at = utc_now_naive()
        await session.flush()
        assert alert.status == AlertStatus.DELIVERED
        assert alert.delivered_at is not None

        # Transition to acknowledged
        alert.status = AlertStatus.ACKNOWLEDGED
        await session.flush()
        assert alert.status == AlertStatus.ACKNOWLEDGED

        # Transition to dismissed
        alert.status = AlertStatus.DISMISSED
        await session.flush()
        assert alert.status == AlertStatus.DISMISSED

    @pytest.mark.asyncio
    async def test_alert_event_relationship(self, session, test_event):
        """Test the relationship between Alert and Event."""
        alert = Alert(
            event_id=test_event.id,
            dedup_key="test_camera:person",
        )
        session.add(alert)
        await session.flush()

        # Refresh to load relationship
        await session.refresh(alert, ["event"])
        assert alert.event is not None
        assert alert.event.id == test_event.id
        assert alert.event.batch_id.startswith("batch_")

    @pytest.mark.asyncio
    async def test_alert_rule_relationship(self, session, test_event):
        """Test the relationship between Alert and AlertRule."""
        rule = AlertRule(
            name="Test Rule",
        )
        session.add(rule)
        await session.flush()

        alert = Alert(
            event_id=test_event.id,
            rule_id=rule.id,
            dedup_key="test_camera:person",
        )
        session.add(alert)
        await session.flush()

        # Refresh to load relationship
        await session.refresh(alert, ["rule"])
        assert alert.rule is not None
        assert alert.rule.id == rule.id
        assert alert.rule.name == "Test Rule"

    @pytest.mark.asyncio
    async def test_alert_repr(self, session, test_event):
        """Test Alert string representation."""
        alert = Alert(
            event_id=test_event.id,
            severity=AlertSeverity.CRITICAL,
            status=AlertStatus.DELIVERED,
            dedup_key="test_camera:person",
        )
        session.add(alert)
        await session.flush()

        repr_str = repr(alert)
        assert "Alert" in repr_str
        assert "critical" in repr_str
        assert "delivered" in repr_str

    @pytest.mark.asyncio
    async def test_query_alerts_by_dedup_key(self, session, test_event):
        """Test querying alerts by deduplication key."""
        # Create alerts with different dedup keys
        for i in range(3):
            alert = Alert(
                event_id=test_event.id,
                dedup_key=f"camera_{i}:person",
            )
            session.add(alert)

        await session.flush()

        # Query by specific dedup key
        stmt = select(Alert).where(Alert.dedup_key == "camera_1:person")
        result = await session.execute(stmt)
        alerts = result.scalars().all()

        assert len(alerts) == 1
        assert alerts[0].dedup_key == "camera_1:person"

    @pytest.mark.asyncio
    async def test_query_alerts_by_status(self, session, test_event):
        """Test querying alerts by status."""
        statuses = [
            AlertStatus.PENDING,
            AlertStatus.PENDING,
            AlertStatus.DELIVERED,
            AlertStatus.ACKNOWLEDGED,
        ]

        for status in statuses:
            alert = Alert(
                event_id=test_event.id,
                dedup_key=f"camera:person:{status.value}",
                status=status,
            )
            session.add(alert)

        await session.flush()

        # Query pending alerts
        stmt = select(Alert).where(Alert.status == AlertStatus.PENDING)
        result = await session.execute(stmt)
        pending = result.scalars().all()

        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_alert_cascade_delete_on_event(self, session, test_camera):
        """Test that alerts are deleted when parent event is deleted."""
        # Create event with unique batch_id
        batch_id = unique_id("batch_cascade")
        dedup_prefix = unique_id("cascade_test")
        event = Event(
            batch_id=batch_id,
            camera_id=test_camera.id,
            started_at=utc_now_naive(),
        )
        session.add(event)
        await session.flush()

        # Create alerts for the event
        for i in range(3):
            alert = Alert(
                event_id=event.id,
                dedup_key=f"{dedup_prefix}_{i}",
            )
            session.add(alert)
        await session.flush()

        # Verify alerts exist
        stmt = select(Alert).where(Alert.event_id == event.id)
        result = await session.execute(stmt)
        alerts = result.scalars().all()
        assert len(alerts) == 3

        # Delete the event
        await session.delete(event)
        await session.flush()

        # Verify alerts are also deleted
        stmt = select(Alert).where(Alert.dedup_key.like(f"{dedup_prefix}%"))
        result = await session.execute(stmt)
        alerts = result.scalars().all()
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_alert_cascade_on_rule_delete(self, session, test_event):
        """Test that alerts are deleted when their rule is deleted.

        Note: The AlertRule.alerts relationship uses cascade="all, delete-orphan",
        which means SQLAlchemy will delete associated alerts at the ORM level.
        This overrides the database-level ondelete="SET NULL" behavior.
        """
        # Create rule
        rule = AlertRule(name="Deletable Rule")
        session.add(rule)
        await session.flush()

        # Create alerts referencing the rule
        dedup_prefix = unique_id("rule_delete")
        for i in range(2):
            alert = Alert(
                event_id=test_event.id,
                rule_id=rule.id,
                dedup_key=f"{dedup_prefix}_{i}",
            )
            session.add(alert)
        await session.flush()

        # Verify alerts exist
        stmt = select(Alert).where(Alert.dedup_key.like(f"{dedup_prefix}%"))
        result = await session.execute(stmt)
        alerts = result.scalars().all()
        assert len(alerts) == 2

        # Delete the rule (cascade deletes alerts via ORM relationship)
        await session.delete(rule)
        await session.flush()

        # Verify alerts are also deleted (due to ORM cascade="all, delete-orphan")
        stmt = select(Alert).where(Alert.dedup_key.like(f"{dedup_prefix}%"))
        result = await session.execute(stmt)
        alerts = result.scalars().all()
        assert len(alerts) == 0


class TestAlertIndexes:
    """Tests for alert table indexes and query performance."""

    @pytest.mark.asyncio
    async def test_query_by_dedup_key_and_created_at(self, session, test_event):
        """Test query using composite index on dedup_key and created_at."""
        now = utc_now_naive()

        # Create alerts at different times with same dedup_key
        for i in range(5):
            alert = Alert(
                event_id=test_event.id,
                dedup_key="test_camera:person",
                created_at=now - timedelta(minutes=i * 5),
            )
            session.add(alert)
        await session.flush()

        # Query alerts within a time window
        cutoff = now - timedelta(minutes=10)
        stmt = (
            select(Alert)
            .where(Alert.dedup_key == "test_camera:person")
            .where(Alert.created_at >= cutoff)
            .order_by(Alert.created_at.desc())
        )
        result = await session.execute(stmt)
        recent_alerts = result.scalars().all()

        # Should get alerts from 0, 5, and 10 minutes ago
        assert len(recent_alerts) == 3

    @pytest.mark.asyncio
    async def test_query_recent_alerts_by_severity(self, session, test_event):
        """Test querying recent alerts filtered by severity."""
        now = utc_now_naive()

        # Create alerts with different severities
        severities = [
            AlertSeverity.LOW,
            AlertSeverity.MEDIUM,
            AlertSeverity.HIGH,
            AlertSeverity.CRITICAL,
            AlertSeverity.HIGH,
        ]

        for i, severity in enumerate(severities):
            alert = Alert(
                event_id=test_event.id,
                dedup_key=f"camera:person:{i}",
                severity=severity,
                created_at=now - timedelta(minutes=i),
            )
            session.add(alert)
        await session.flush()

        # Query high severity alerts
        stmt = (
            select(Alert)
            .where(Alert.severity == AlertSeverity.HIGH)
            .order_by(Alert.created_at.desc())
        )
        result = await session.execute(stmt)
        high_alerts = result.scalars().all()

        assert len(high_alerts) == 2
