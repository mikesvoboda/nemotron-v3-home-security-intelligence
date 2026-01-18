"""Integration tests for AlertRepository and AlertRuleRepository.

Tests follow TDD approach covering CRUD operations, query methods with filters,
relationship loading, and error handling.

Run with: uv run pytest backend/tests/integration/repositories/test_alert_repository.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models import Alert, AlertRule, AlertSeverity, AlertStatus, Camera, Event
from backend.repositories.alert_repository import AlertRepository, AlertRuleRepository
from backend.tests.conftest import unique_id


@pytest.fixture
def alert_repo(test_db):
    """Create an AlertRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            return AlertRepository(session), session

    return _get_repo


@pytest.fixture
def alert_rule_repo(test_db):
    """Create an AlertRuleRepository instance with a test session."""

    async def _get_repo():
        async with test_db() as session:
            return AlertRuleRepository(session), session

    return _get_repo


class TestAlertRepositoryBasicCRUD:
    """Test basic CRUD operations inherited from Repository base class."""

    @pytest.mark.asyncio
    async def test_create_alert(self, test_db):
        """Test creating a new alert."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create camera and event first
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key=f"{camera.id}:test",
            )

            created = await repo.create(alert)

            assert created.id == alert_id
            assert created.event_id == event.id
            assert created.severity == AlertSeverity.HIGH
            assert created.status == AlertStatus.PENDING
            assert created.created_at is not None

    @pytest.mark.asyncio
    async def test_get_by_id_existing(self, test_db):
        """Test retrieving an existing alert by ID."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=50,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.PENDING,
                dedup_key="test-dedup",
            )
            await repo.create(alert)

            # Retrieve by ID
            retrieved = await repo.get_by_id(alert_id)

            assert retrieved is not None
            assert retrieved.id == alert_id
            assert retrieved.severity == AlertSeverity.MEDIUM

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, test_db):
        """Test retrieving a non-existent alert returns None."""
        async with test_db() as session:
            repo = AlertRepository(session)

            result = await repo.get_by_id("nonexistent_alert")

            assert result is None

    @pytest.mark.asyncio
    async def test_update_alert(self, test_db):
        """Test updating an alert's properties."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=60,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                dedup_key="test",
            )
            await repo.create(alert)

            # Update
            alert.severity = AlertSeverity.CRITICAL
            alert.status = AlertStatus.DELIVERED
            updated = await repo.update(alert)

            assert updated.severity == AlertSeverity.CRITICAL
            assert updated.status == AlertStatus.DELIVERED

            # Verify persistence
            retrieved = await repo.get_by_id(alert_id)
            assert retrieved.severity == AlertSeverity.CRITICAL
            assert retrieved.status == AlertStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_delete_alert(self, test_db):
        """Test deleting an alert."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=70,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test",
            )
            await repo.create(alert)

            # Delete
            await repo.delete(alert)

            # Verify deleted
            result = await repo.get_by_id(alert_id)
            assert result is None

    @pytest.mark.asyncio
    async def test_count_alerts(self, test_db):
        """Test counting alerts."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=80,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Get initial count
            initial_count = await repo.count()

            # Create alerts
            for i in range(3):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.MEDIUM,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-{i}",
                )
                await repo.create(alert)

            # Verify count increased
            new_count = await repo.count()
            assert new_count == initial_count + 3


class TestAlertRepositorySpecificMethods:
    """Test alert-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_by_event_id(self, test_db):
        """Test getting alerts by event ID."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event1 = Event(
                camera_id=camera.id,
                risk_score=70,
                summary="Event 1",
                occurred_at=datetime.now(UTC),
            )
            event2 = Event(
                camera_id=camera.id,
                risk_score=80,
                summary="Event 2",
                occurred_at=datetime.now(UTC),
            )
            session.add(event1)
            session.add(event2)
            await session.flush()

            # Create alerts for different events
            alert1 = Alert(
                id=unique_id("alert1"),
                event_id=event1.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test1",
            )
            alert2 = Alert(
                id=unique_id("alert2"),
                event_id=event1.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.PENDING,
                dedup_key="test2",
            )
            alert3 = Alert(
                id=unique_id("alert3"),
                event_id=event2.id,
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                dedup_key="test3",
            )
            await repo.create(alert1)
            await repo.create(alert2)
            await repo.create(alert3)

            # Get alerts for event1
            alerts = await repo.get_by_event_id(event1.id)

            alert_ids = [a.id for a in alerts]
            assert alert1.id in alert_ids
            assert alert2.id in alert_ids
            assert alert3.id not in alert_ids

    @pytest.mark.asyncio
    async def test_get_by_status(self, test_db):
        """Test getting alerts by status."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alerts with different statuses
            pending = Alert(
                id=unique_id("pending"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="pending",
            )
            delivered = Alert(
                id=unique_id("delivered"),
                event_id=event.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.DELIVERED,
                dedup_key="delivered",
            )
            await repo.create(pending)
            await repo.create(delivered)

            # Get pending alerts
            pending_alerts = await repo.get_by_status(AlertStatus.PENDING)

            alert_ids = [a.id for a in pending_alerts]
            assert pending.id in alert_ids
            assert delivered.id not in alert_ids

    @pytest.mark.asyncio
    async def test_get_by_severity(self, test_db):
        """Test getting alerts by severity."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=85,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alerts with different severities
            high = Alert(
                id=unique_id("high"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="high",
            )
            low = Alert(
                id=unique_id("low"),
                event_id=event.id,
                severity=AlertSeverity.LOW,
                status=AlertStatus.PENDING,
                dedup_key="low",
            )
            await repo.create(high)
            await repo.create(low)

            # Get high severity alerts
            high_alerts = await repo.get_by_severity(AlertSeverity.HIGH)

            alert_ids = [a.id for a in high_alerts]
            assert high.id in alert_ids
            assert low.id not in alert_ids

    @pytest.mark.asyncio
    async def test_get_by_dedup_key(self, test_db):
        """Test getting alerts by dedup key."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=70,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alerts with same dedup key at different times
            old_alert = Alert(
                id=unique_id("old"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="same-key",
                created_at=datetime.now(UTC) - timedelta(hours=2),
            )
            recent_alert = Alert(
                id=unique_id("recent"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="same-key",
            )
            different_alert = Alert(
                id=unique_id("different"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="different-key",
            )
            await repo.create(old_alert)
            await repo.create(recent_alert)
            await repo.create(different_alert)

            # Get all alerts with dedup key
            all_alerts = await repo.get_by_dedup_key("same-key")
            assert len(all_alerts) == 2

            # Get alerts with dedup key since 1 hour ago
            since = datetime.now(UTC) - timedelta(hours=1)
            recent_alerts = await repo.get_by_dedup_key("same-key", since=since)
            assert len(recent_alerts) == 1
            assert recent_alerts[0].id == recent_alert.id

    @pytest.mark.asyncio
    async def test_get_recent(self, test_db):
        """Test getting recent alerts."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=65,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alerts
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.MEDIUM,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-{i}",
                )
                await repo.create(alert)

            # Get recent alerts with limit
            recent = await repo.get_recent(limit=3)

            assert len(recent) == 3

    @pytest.mark.asyncio
    async def test_get_undelivered(self, test_db):
        """Test getting undelivered alerts."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=80,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create undelivered alert
            undelivered = Alert(
                id=unique_id("undelivered"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="undelivered",
                delivered_at=None,
            )
            # Create delivered alert
            delivered = Alert(
                id=unique_id("delivered"),
                event_id=event.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.DELIVERED,
                dedup_key="delivered",
                delivered_at=datetime.now(UTC),
            )
            await repo.create(undelivered)
            await repo.create(delivered)

            # Get undelivered
            undelivered_alerts = await repo.get_undelivered()

            alert_ids = [a.id for a in undelivered_alerts]
            assert undelivered.id in alert_ids
            assert delivered.id not in alert_ids

    @pytest.mark.asyncio
    async def test_mark_delivered(self, test_db):
        """Test marking an alert as delivered."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create pending alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test",
                delivered_at=None,
            )
            await repo.create(alert)

            # Mark as delivered
            updated = await repo.mark_delivered(alert_id)

            assert updated is not None
            assert updated.status == AlertStatus.DELIVERED
            assert updated.delivered_at is not None

            # Verify persistence
            retrieved = await repo.get_by_id(alert_id)
            assert retrieved.status == AlertStatus.DELIVERED
            assert retrieved.delivered_at is not None

    @pytest.mark.asyncio
    async def test_mark_acknowledged(self, test_db):
        """Test marking an alert as acknowledged."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=70,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create delivered alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.MEDIUM,
                status=AlertStatus.DELIVERED,
                dedup_key="test",
            )
            await repo.create(alert)

            # Mark as acknowledged
            updated = await repo.mark_acknowledged(alert_id)

            assert updated is not None
            assert updated.status == AlertStatus.ACKNOWLEDGED

            # Verify persistence
            retrieved = await repo.get_by_id(alert_id)
            assert retrieved.status == AlertStatus.ACKNOWLEDGED

    @pytest.mark.asyncio
    async def test_mark_dismissed(self, test_db):
        """Test marking an alert as dismissed."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=65,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create delivered alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.LOW,
                status=AlertStatus.DELIVERED,
                dedup_key="test",
            )
            await repo.create(alert)

            # Mark as dismissed
            updated = await repo.mark_dismissed(alert_id)

            assert updated is not None
            assert updated.status == AlertStatus.DISMISSED

            # Verify persistence
            retrieved = await repo.get_by_id(alert_id)
            assert retrieved.status == AlertStatus.DISMISSED

    @pytest.mark.asyncio
    async def test_check_duplicate_within_cooldown(self, test_db):
        """Test checking for duplicate alerts within cooldown period."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=80,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create recent alert
            alert = Alert(
                id=unique_id("alert"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="duplicate-test",
            )
            await repo.create(alert)

            # Check for duplicate within cooldown (should find one)
            is_duplicate = await repo.check_duplicate("duplicate-test", cooldown_seconds=300)
            assert is_duplicate is True

    @pytest.mark.asyncio
    async def test_check_duplicate_outside_cooldown(self, test_db):
        """Test checking for duplicate alerts outside cooldown period."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create old alert (outside cooldown)
            alert = Alert(
                id=unique_id("alert"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="old-duplicate",
                created_at=datetime.now(UTC) - timedelta(hours=2),
            )
            await repo.create(alert)

            # Check for duplicate with short cooldown (should not find one)
            is_duplicate = await repo.check_duplicate("old-duplicate", cooldown_seconds=300)
            assert is_duplicate is False


class TestAlertRuleRepositoryBasicCRUD:
    """Test basic CRUD operations for AlertRule."""

    @pytest.mark.asyncio
    async def test_create_alert_rule(self, test_db):
        """Test creating a new alert rule."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_id = unique_id("rule")
            rule = AlertRule(
                id=rule_id,
                name="High Risk Detection",
                description="Alert on high risk detections",
                enabled=True,
                severity=AlertSeverity.HIGH,
                risk_threshold=75,
                cooldown_seconds=300,
            )

            created = await repo.create(rule)

            assert created.id == rule_id
            assert created.name == "High Risk Detection"
            assert created.enabled is True
            assert created.severity == AlertSeverity.HIGH

    @pytest.mark.asyncio
    async def test_get_by_id_existing_rule(self, test_db):
        """Test retrieving an existing alert rule by ID."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_id = unique_id("rule")
            rule = AlertRule(
                id=rule_id,
                name="Test Rule",
                enabled=True,
                severity=AlertSeverity.MEDIUM,
            )
            await repo.create(rule)

            # Retrieve by ID
            retrieved = await repo.get_by_id(rule_id)

            assert retrieved is not None
            assert retrieved.id == rule_id
            assert retrieved.name == "Test Rule"

    @pytest.mark.asyncio
    async def test_update_alert_rule(self, test_db):
        """Test updating an alert rule."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_id = unique_id("rule")
            rule = AlertRule(
                id=rule_id,
                name="Original Name",
                enabled=True,
                severity=AlertSeverity.LOW,
            )
            await repo.create(rule)

            # Update
            rule.name = "Updated Name"
            rule.severity = AlertSeverity.CRITICAL
            updated = await repo.update(rule)

            assert updated.name == "Updated Name"
            assert updated.severity == AlertSeverity.CRITICAL

            # Verify persistence
            retrieved = await repo.get_by_id(rule_id)
            assert retrieved.name == "Updated Name"
            assert retrieved.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_delete_alert_rule(self, test_db):
        """Test deleting an alert rule."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_id = unique_id("rule")
            rule = AlertRule(
                id=rule_id,
                name="To Delete",
                enabled=True,
                severity=AlertSeverity.MEDIUM,
            )
            await repo.create(rule)

            # Delete
            await repo.delete(rule)

            # Verify deleted
            result = await repo.get_by_id(rule_id)
            assert result is None


class TestAlertRuleRepositorySpecificMethods:
    """Test alert rule-specific repository methods."""

    @pytest.mark.asyncio
    async def test_get_enabled_rules(self, test_db):
        """Test getting all enabled alert rules."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            # Create enabled and disabled rules
            enabled = AlertRule(
                id=unique_id("enabled"),
                name="Enabled Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            disabled = AlertRule(
                id=unique_id("disabled"),
                name="Disabled Rule",
                enabled=False,
                severity=AlertSeverity.MEDIUM,
            )
            await repo.create(enabled)
            await repo.create(disabled)

            # Get enabled rules
            enabled_rules = await repo.get_enabled_rules()

            rule_ids = [r.id for r in enabled_rules]
            assert enabled.id in rule_ids
            assert disabled.id not in rule_ids

    @pytest.mark.asyncio
    async def test_get_by_name(self, test_db):
        """Test finding an alert rule by name."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_name = f"Unique Rule {unique_id('name')}"
            rule = AlertRule(
                id=unique_id("rule"),
                name=rule_name,
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            await repo.create(rule)

            # Find by name
            found = await repo.get_by_name(rule_name)

            assert found is not None
            assert found.name == rule_name

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, test_db):
        """Test get_by_name returns None for non-existent name."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            result = await repo.get_by_name("Nonexistent Rule")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_severity(self, test_db):
        """Test getting alert rules by severity."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            # Create rules with different severities
            high = AlertRule(
                id=unique_id("high"),
                name="High Severity Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            low = AlertRule(
                id=unique_id("low"),
                name="Low Severity Rule",
                enabled=True,
                severity=AlertSeverity.LOW,
            )
            await repo.create(high)
            await repo.create(low)

            # Get high severity rules
            high_rules = await repo.get_by_severity(AlertSeverity.HIGH)

            rule_ids = [r.id for r in high_rules]
            assert high.id in rule_ids
            assert low.id not in rule_ids

    @pytest.mark.asyncio
    async def test_set_enabled(self, test_db):
        """Test enabling/disabling an alert rule."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            rule_id = unique_id("rule")
            rule = AlertRule(
                id=rule_id,
                name="Test Rule",
                enabled=True,
                severity=AlertSeverity.MEDIUM,
            )
            await repo.create(rule)

            # Disable the rule
            updated = await repo.set_enabled(rule_id, False)

            assert updated is not None
            assert updated.enabled is False

            # Verify persistence
            retrieved = await repo.get_by_id(rule_id)
            assert retrieved.enabled is False

            # Re-enable the rule
            updated = await repo.set_enabled(rule_id, True)
            assert updated.enabled is True

    @pytest.mark.asyncio
    async def test_set_enabled_not_found(self, test_db):
        """Test set_enabled returns None for non-existent rule."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            result = await repo.set_enabled("nonexistent", True)

            assert result is None

    @pytest.mark.asyncio
    async def test_get_rules_for_camera_all_cameras(self, test_db):
        """Test getting rules that apply to all cameras."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            # Create rule with empty camera_ids (applies to all)
            all_cameras_rule = AlertRule(
                id=unique_id("all"),
                name="All Cameras Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
                camera_ids=[],
            )
            await repo.create(all_cameras_rule)

            # Get rules for any camera
            rules = await repo.get_rules_for_camera("any_camera_id")

            rule_ids = [r.id for r in rules]
            assert all_cameras_rule.id in rule_ids

    @pytest.mark.asyncio
    async def test_get_rules_for_camera_specific(self, test_db):
        """Test getting rules for a specific camera."""
        async with test_db() as session:
            repo = AlertRuleRepository(session)

            camera_id = unique_id("camera")

            # Create rule for specific camera
            specific_rule = AlertRule(
                id=unique_id("specific"),
                name="Specific Camera Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
                camera_ids=[camera_id],
            )
            # Create rule for different camera
            other_rule = AlertRule(
                id=unique_id("other"),
                name="Other Camera Rule",
                enabled=True,
                severity=AlertSeverity.MEDIUM,
                camera_ids=["other_camera"],
            )
            await repo.create(specific_rule)
            await repo.create(other_rule)

            # Get rules for specific camera
            rules = await repo.get_rules_for_camera(camera_id)

            rule_ids = [r.id for r in rules]
            assert specific_rule.id in rule_ids
            assert other_rule.id not in rule_ids


class TestAlertRepositoryRelationshipLoading:
    """Test relationship loading for alerts."""

    @pytest.mark.asyncio
    async def test_alert_loads_event_relationship(self, test_db):
        """Test that alert properly loads its event relationship."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test",
            )
            await repo.create(alert)

            # Retrieve and access relationship
            retrieved = await repo.get_by_id(alert_id)
            assert retrieved is not None

            # Access event relationship (should be loaded)
            assert retrieved.event is not None
            assert retrieved.event.id == event.id
            assert retrieved.event.summary == "Test event"

    @pytest.mark.asyncio
    async def test_alert_loads_rule_relationship(self, test_db):
        """Test that alert properly loads its rule relationship."""
        async with test_db() as session:
            alert_repo = AlertRepository(session)
            rule_repo = AlertRuleRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=80,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create rule
            rule = AlertRule(
                id=unique_id("rule"),
                name="Test Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            await rule_repo.create(rule)

            # Create alert with rule
            alert_id = unique_id("alert")
            alert = Alert(
                id=alert_id,
                event_id=event.id,
                rule_id=rule.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test",
            )
            await alert_repo.create(alert)

            # Retrieve and access relationship
            retrieved = await alert_repo.get_by_id(alert_id)
            assert retrieved is not None

            # Access rule relationship (should be loaded)
            assert retrieved.rule is not None
            assert retrieved.rule.id == rule.id
            assert retrieved.rule.name == "Test Rule"


class TestAlertRepositoryErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_mark_delivered_nonexistent_alert(self, test_db):
        """Test mark_delivered returns None for non-existent alert."""
        async with test_db() as session:
            repo = AlertRepository(session)

            result = await repo.mark_delivered("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_mark_acknowledged_nonexistent_alert(self, test_db):
        """Test mark_acknowledged returns None for non-existent alert."""
        async with test_db() as session:
            repo = AlertRepository(session)

            result = await repo.mark_acknowledged("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_mark_dismissed_nonexistent_alert(self, test_db):
        """Test mark_dismissed returns None for non-existent alert."""
        async with test_db() as session:
            repo = AlertRepository(session)

            result = await repo.mark_dismissed("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_rule_id_with_no_matches(self, test_db):
        """Test get_by_rule_id returns empty list when no alerts match."""
        async with test_db() as session:
            repo = AlertRepository(session)

            alerts = await repo.get_by_rule_id("nonexistent_rule")

            assert len(alerts) == 0


class TestAlertRepositoryPagination:
    """Test pagination functionality for AlertRepository query methods."""

    @pytest.mark.asyncio
    async def test_get_by_event_id_pagination(self, test_db):
        """Test pagination for get_by_event_id method."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create 5 alerts for the event
            alert_ids = []
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-{i}",
                )
                await repo.create(alert)
                alert_ids.append(alert.id)

            # Test default pagination returns all (limit=100)
            all_alerts = await repo.get_by_event_id(event.id)
            assert len(all_alerts) == 5

            # Test with limit
            limited = await repo.get_by_event_id(event.id, limit=2)
            assert len(limited) == 2

            # Test with offset
            offset_alerts = await repo.get_by_event_id(event.id, limit=2, offset=2)
            assert len(offset_alerts) == 2

            # Test offset beyond results
            empty = await repo.get_by_event_id(event.id, limit=2, offset=10)
            assert len(empty) == 0

    @pytest.mark.asyncio
    async def test_get_by_rule_id_pagination(self, test_db):
        """Test pagination for get_by_rule_id method."""
        async with test_db() as session:
            alert_repo = AlertRepository(session)
            rule_repo = AlertRuleRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create rule
            rule = AlertRule(
                id=unique_id("rule"),
                name="Test Rule",
                enabled=True,
                severity=AlertSeverity.HIGH,
            )
            await rule_repo.create(rule)

            # Create 5 alerts for the rule
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    rule_id=rule.id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-{i}",
                )
                await alert_repo.create(alert)

            # Test default pagination
            all_alerts = await alert_repo.get_by_rule_id(rule.id)
            assert len(all_alerts) == 5

            # Test with limit
            limited = await alert_repo.get_by_rule_id(rule.id, limit=3)
            assert len(limited) == 3

            # Test with offset
            offset_alerts = await alert_repo.get_by_rule_id(rule.id, limit=2, offset=3)
            assert len(offset_alerts) == 2

    @pytest.mark.asyncio
    async def test_get_by_status_pagination(self, test_db):
        """Test pagination for get_by_status method."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create 5 pending alerts
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-pending-{i}",
                )
                await repo.create(alert)

            # Test default pagination
            all_pending = await repo.get_by_status(AlertStatus.PENDING)
            assert len(all_pending) >= 5

            # Test with limit
            limited = await repo.get_by_status(AlertStatus.PENDING, limit=3)
            assert len(limited) == 3

            # Test with offset
            offset_alerts = await repo.get_by_status(AlertStatus.PENDING, limit=2, offset=2)
            assert len(offset_alerts) >= 2

    @pytest.mark.asyncio
    async def test_get_by_severity_pagination(self, test_db):
        """Test pagination for get_by_severity method."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create 5 critical alerts
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.CRITICAL,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-critical-{i}",
                )
                await repo.create(alert)

            # Test default pagination
            all_critical = await repo.get_by_severity(AlertSeverity.CRITICAL)
            assert len(all_critical) >= 5

            # Test with limit
            limited = await repo.get_by_severity(AlertSeverity.CRITICAL, limit=3)
            assert len(limited) == 3

            # Test with offset
            offset_alerts = await repo.get_by_severity(AlertSeverity.CRITICAL, limit=2, offset=2)
            assert len(offset_alerts) >= 2

    @pytest.mark.asyncio
    async def test_get_by_dedup_key_pagination(self, test_db):
        """Test pagination for get_by_dedup_key method."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create 5 alerts with the same dedup key
            dedup_key = unique_id("dedup")
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=dedup_key,
                )
                await repo.create(alert)

            # Test default pagination
            all_alerts = await repo.get_by_dedup_key(dedup_key)
            assert len(all_alerts) == 5

            # Test with limit
            limited = await repo.get_by_dedup_key(dedup_key, limit=3)
            assert len(limited) == 3

            # Test with offset
            offset_alerts = await repo.get_by_dedup_key(dedup_key, limit=2, offset=2)
            assert len(offset_alerts) == 2

            # Test with since and pagination
            since = datetime.now(UTC) - timedelta(hours=1)
            recent = await repo.get_by_dedup_key(dedup_key, since=since, limit=2)
            assert len(recent) == 2

    @pytest.mark.asyncio
    async def test_pagination_preserves_ordering(self, test_db):
        """Test that pagination preserves the created_at desc ordering."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alerts with different timestamps
            base_time = datetime.now(UTC)
            alert_ids = []
            for i in range(5):
                alert = Alert(
                    id=unique_id(f"alert{i}"),
                    event_id=event.id,
                    severity=AlertSeverity.HIGH,
                    status=AlertStatus.PENDING,
                    dedup_key=f"test-order-{i}",
                    created_at=base_time - timedelta(minutes=i),
                )
                await repo.create(alert)
                alert_ids.append(alert.id)

            # Get first page
            page1 = await repo.get_by_event_id(event.id, limit=2, offset=0)
            # Get second page
            page2 = await repo.get_by_event_id(event.id, limit=2, offset=2)

            # First page should have the most recent alerts
            assert page1[0].id == alert_ids[0]  # Most recent
            assert page1[1].id == alert_ids[1]

            # Second page should have older alerts
            assert page2[0].id == alert_ids[2]
            assert page2[1].id == alert_ids[3]

    @pytest.mark.asyncio
    async def test_backward_compatibility_default_values(self, test_db):
        """Test that existing callers work without providing pagination params."""
        async with test_db() as session:
            repo = AlertRepository(session)

            # Create dependencies
            camera = Camera(
                id=unique_id("camera"),
                name="Test Camera",
                folder_path=f"/export/foscam/{unique_id('path')}",
            )
            session.add(camera)

            event = Event(
                camera_id=camera.id,
                risk_score=75,
                summary="Test event",
                occurred_at=datetime.now(UTC),
            )
            session.add(event)
            await session.flush()

            # Create alert
            alert = Alert(
                id=unique_id("alert"),
                event_id=event.id,
                severity=AlertSeverity.HIGH,
                status=AlertStatus.PENDING,
                dedup_key="test",
            )
            await repo.create(alert)

            # Call methods without pagination params (backward compatible)
            by_event = await repo.get_by_event_id(event.id)
            assert len(by_event) == 1

            by_status = await repo.get_by_status(AlertStatus.PENDING)
            assert len(by_status) >= 1

            by_severity = await repo.get_by_severity(AlertSeverity.HIGH)
            assert len(by_severity) >= 1

            by_dedup = await repo.get_by_dedup_key("test")
            assert len(by_dedup) == 1
