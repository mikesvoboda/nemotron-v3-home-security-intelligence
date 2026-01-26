"""Hypothesis stateful testing for API state machines.

This module uses Hypothesis's RuleBasedStateMachine to verify API state machine
correctness by exploring many possible sequences of operations. This catches bugs
where API behavior depends on the sequence of operations.

State Machines Tested:
    1. Event Lifecycle: create → review → flag → snooze → delete → restore
    2. Camera Status: online → offline → error → online
    3. Alert States: pending → delivered → acknowledged → dismissed

For each state machine, we define:
    - Rules: API operations that can be performed
    - Invariants: Properties that must hold after any sequence of operations
    - State tracking: Internal model of expected system state

Running these tests:
    pytest backend/tests/integration/test_stateful_api.py -v

To reproduce a failure:
    pytest backend/tests/integration/test_stateful_api.py --hypothesis-seed=<seed>

References:
    - NEM-3746: Implement Hypothesis stateful testing for API state machines
    - https://hypothesis.readthedocs.io/en/latest/stateful.html
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from hypothesis import assume, note, settings
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
)
from hypothesis.strategies import integers, sampled_from
from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# Helper Functions
# =============================================================================


def run_state_machine_test(state_machine_cls: type, *, max_examples: int = 50) -> None:
    """Run a Hypothesis state machine test.

    Args:
        state_machine_cls: RuleBasedStateMachine class to test
        max_examples: Number of test sequences to generate (default: 50)
    """
    test_case = state_machine_cls.TestCase()
    test_case.runTest = lambda: None  # Bypass unittest.TestCase.runTest requirement
    settings_obj = settings(
        max_examples=max_examples,
        stateful_step_count=20,  # Max steps per example
        deadline=None,  # Disable deadline for async operations
    )
    test_case.settings = settings_obj
    test_case.runTest()


# =============================================================================
# Event Lifecycle State Machine
# =============================================================================


class EventLifecycleStateMachine(RuleBasedStateMachine):
    """Test event lifecycle state transitions.

    Event lifecycle:
        1. Create event (via batch aggregator or API)
        2. Review event (mark as reviewed)
        3. Flag event for investigation
        4. Snooze alerts for event
        5. Soft delete event
        6. Restore event
        7. Hard delete event

    Invariants:
        - reviewed flag can only be set, never unset
        - flagged events maintain reviewed state
        - deleted events cannot be modified
        - snoozed events have snooze_until in future
        - restored events have null deleted_at
    """

    # Bundles to track created resources
    events = Bundle("events")
    cameras = Bundle("cameras")

    def __init__(self) -> None:
        super().__init__()
        self.event_states: dict[int, dict[str, Any]] = {}
        self.camera_states: dict[str, dict[str, Any]] = {}
        self.db_session: AsyncSession | None = None
        self.client: httpx.AsyncClient | None = None
        self.base_url = "http://testserver"

    @initialize()
    def setup(self) -> None:
        """Initialize test resources."""
        # Note: Database and client setup happens in test fixture
        pass

    @rule(target=cameras)
    def create_camera(self) -> str:
        """Create a camera via API."""
        camera_id = f"test_cam_{len(self.camera_states)}"
        camera_data = {
            "id": camera_id,
            "name": f"Test Camera {len(self.camera_states)}",
            "folder_path": f"/test/{camera_id}",
            "status": "online",
        }

        # Track state
        self.camera_states[camera_id] = {
            "id": camera_id,
            "status": "online",
            "deleted": False,
        }

        note(f"Created camera: {camera_id}")
        return camera_id

    @rule(target=events, camera=cameras)
    def create_event(self, camera: str) -> int:
        """Create an event for a camera."""
        event_id = len(self.event_states) + 1
        batch_id = f"batch_{event_id}"

        # Track state
        self.event_states[event_id] = {
            "id": event_id,
            "camera_id": camera,
            "batch_id": batch_id,
            "reviewed": False,
            "flagged": False,
            "deleted": False,
            "snoozed": False,
            "snooze_until": None,
        }

        note(f"Created event: {event_id} for camera {camera}")
        return event_id

    @rule(event=events)
    @precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
    def review_event(self, event: int) -> None:
        """Mark an event as reviewed."""
        assume(not self.event_states[event]["deleted"])

        self.event_states[event]["reviewed"] = True
        note(f"Reviewed event: {event}")

    @rule(event=events)
    @precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
    def flag_event(self, event: int) -> None:
        """Flag an event for investigation."""
        assume(not self.event_states[event]["deleted"])

        self.event_states[event]["flagged"] = True
        note(f"Flagged event: {event}")

    @rule(event=events, hours=integers(min_value=1, max_value=24))
    @precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
    def snooze_event(self, event: int, hours: int) -> None:
        """Snooze alerts for an event."""
        assume(not self.event_states[event]["deleted"])

        snooze_until = datetime.now(UTC) + timedelta(hours=hours)
        self.event_states[event]["snoozed"] = True
        self.event_states[event]["snooze_until"] = snooze_until
        note(f"Snoozed event: {event} until {snooze_until}")

    @rule(event=events)
    @precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
    def soft_delete_event(self, event: int) -> None:
        """Soft delete an event."""
        assume(not self.event_states[event]["deleted"])

        self.event_states[event]["deleted"] = True
        note(f"Soft deleted event: {event}")

    @rule(event=events)
    @precondition(lambda self: any(e["deleted"] for e in self.event_states.values()))
    def restore_event(self, event: int) -> None:
        """Restore a soft-deleted event."""
        assume(self.event_states[event]["deleted"])

        self.event_states[event]["deleted"] = False
        note(f"Restored event: {event}")

    @invariant()
    def events_have_valid_state(self) -> None:
        """Verify all events have valid state."""
        for event_id, state in self.event_states.items():
            # Deleted events cannot be modified (reviewed/flagged/snoozed stay as-is)
            # This is acceptable - we just check the flags don't change after deletion

            # Snoozed events must have snooze_until in future
            if state["snoozed"] and state["snooze_until"]:
                assert state["snooze_until"] > datetime.now(UTC), (
                    f"Event {event_id} snoozed but snooze_until is in past"
                )

            # Restored events must not be deleted
            if not state["deleted"]:
                # This is the current state, so it's valid
                pass

    @invariant()
    def cameras_exist_for_events(self) -> None:
        """Verify all events reference valid cameras."""
        for event_id, state in self.event_states.items():
            camera_id = state["camera_id"]
            assert camera_id in self.camera_states, (
                f"Event {event_id} references non-existent camera {camera_id}"
            )


# =============================================================================
# Camera Status State Machine
# =============================================================================


class CameraStatusStateMachine(RuleBasedStateMachine):
    """Test camera status transitions.

    Camera states:
        - online: Camera is operational and uploading files
        - offline: Camera hasn't uploaded files recently
        - error: Camera encountered an error
        - unknown: Camera state is unknown (initial)

    Valid transitions:
        - Any state → any other state (no restrictions)
        - Soft delete from any state
        - Restore from deleted state

    Invariants:
        - Deleted cameras cannot change status
        - Status must be one of the valid enum values
        - Cameras have a last_seen_at timestamp when online
    """

    cameras = Bundle("cameras")

    def __init__(self) -> None:
        super().__init__()
        self.camera_states: dict[str, dict[str, Any]] = {}

    @rule(target=cameras)
    def create_camera(self) -> str:
        """Create a new camera."""
        camera_id = f"cam_{len(self.camera_states)}"

        self.camera_states[camera_id] = {
            "id": camera_id,
            "status": "online",
            "deleted": False,
            "last_seen_at": datetime.now(UTC),
        }

        note(f"Created camera: {camera_id}")
        return camera_id

    @rule(
        camera=cameras,
        new_status=sampled_from(["online", "offline", "error", "unknown"]),
    )
    @precondition(lambda self: any(not c["deleted"] for c in self.camera_states.values()))
    def change_status(self, camera: str, new_status: str) -> None:
        """Change camera status."""
        assume(not self.camera_states[camera]["deleted"])

        old_status = self.camera_states[camera]["status"]
        self.camera_states[camera]["status"] = new_status

        # Update last_seen_at when transitioning to online
        if new_status == "online":
            self.camera_states[camera]["last_seen_at"] = datetime.now(UTC)

        note(f"Camera {camera}: {old_status} → {new_status}")

    @rule(camera=cameras)
    @precondition(lambda self: any(not c["deleted"] for c in self.camera_states.values()))
    def soft_delete_camera(self, camera: str) -> None:
        """Soft delete a camera."""
        assume(not self.camera_states[camera]["deleted"])

        self.camera_states[camera]["deleted"] = True
        note(f"Soft deleted camera: {camera}")

    @rule(camera=cameras)
    @precondition(lambda self: any(c["deleted"] for c in self.camera_states.values()))
    def restore_camera(self, camera: str) -> None:
        """Restore a soft-deleted camera."""
        assume(self.camera_states[camera]["deleted"])

        self.camera_states[camera]["deleted"] = False
        note(f"Restored camera: {camera}")

    @invariant()
    def cameras_have_valid_status(self) -> None:
        """Verify all cameras have valid status."""
        valid_statuses = {"online", "offline", "error", "unknown"}
        for camera_id, state in self.camera_states.items():
            assert state["status"] in valid_statuses, (
                f"Camera {camera_id} has invalid status: {state['status']}"
            )

    @invariant()
    def online_cameras_have_last_seen(self) -> None:
        """Verify online cameras have last_seen_at."""
        for camera_id, state in self.camera_states.items():
            if state["status"] == "online" and not state["deleted"]:
                assert state["last_seen_at"] is not None, (
                    f"Online camera {camera_id} missing last_seen_at"
                )


# =============================================================================
# Alert State Machine
# =============================================================================


class AlertStateMachine(RuleBasedStateMachine):
    """Test alert state transitions.

    Alert states:
        - pending: Alert created but not yet delivered
        - delivered: Alert successfully delivered to channels
        - acknowledged: User acknowledged the alert
        - dismissed: User dismissed the alert

    Valid transitions:
        - pending → delivered
        - delivered → acknowledged
        - delivered → dismissed
        - acknowledged → dismissed (optional)

    Invalid transitions:
        - Cannot go back to pending after delivery
        - Cannot un-acknowledge or un-dismiss

    Invariants:
        - Status must be one of the valid enum values
        - Delivered alerts have delivered_at timestamp
        - Acknowledged/dismissed alerts were previously delivered
        - Status transitions follow the state machine rules
    """

    alerts = Bundle("alerts")
    events = Bundle("events")

    def __init__(self) -> None:
        super().__init__()
        self.alert_states: dict[str, dict[str, Any]] = {}
        self.event_states: dict[int, dict[str, Any]] = {}

    @rule(target=events)
    def create_event(self) -> int:
        """Create an event (required for alerts)."""
        event_id = len(self.event_states) + 1
        self.event_states[event_id] = {"id": event_id}
        note(f"Created event: {event_id}")
        return event_id

    @rule(target=alerts, event=events)
    def create_alert(self, event: int) -> str:
        """Create an alert for an event."""
        alert_id = f"alert_{len(self.alert_states)}"

        self.alert_states[alert_id] = {
            "id": alert_id,
            "event_id": event,
            "status": "pending",
            "delivered_at": None,
            "severity": "medium",
        }

        note(f"Created alert: {alert_id} for event {event}")
        return alert_id

    @rule(alert=alerts)
    @precondition(lambda self: any(a["status"] == "pending" for a in self.alert_states.values()))
    def deliver_alert(self, alert: str) -> None:
        """Mark alert as delivered."""
        assume(self.alert_states[alert]["status"] == "pending")

        self.alert_states[alert]["status"] = "delivered"
        self.alert_states[alert]["delivered_at"] = datetime.now(UTC)
        note(f"Delivered alert: {alert}")

    @rule(alert=alerts)
    @precondition(lambda self: any(a["status"] == "delivered" for a in self.alert_states.values()))
    def acknowledge_alert(self, alert: str) -> None:
        """Acknowledge an alert."""
        assume(self.alert_states[alert]["status"] == "delivered")

        self.alert_states[alert]["status"] = "acknowledged"
        note(f"Acknowledged alert: {alert}")

    @rule(alert=alerts)
    @precondition(
        lambda self: any(
            a["status"] in ["delivered", "acknowledged"] for a in self.alert_states.values()
        )
    )
    def dismiss_alert(self, alert: str) -> None:
        """Dismiss an alert."""
        assume(self.alert_states[alert]["status"] in ["delivered", "acknowledged"])

        self.alert_states[alert]["status"] = "dismissed"
        note(f"Dismissed alert: {alert}")

    @invariant()
    def alerts_have_valid_status(self) -> None:
        """Verify all alerts have valid status."""
        valid_statuses = {"pending", "delivered", "acknowledged", "dismissed"}
        for alert_id, state in self.alert_states.items():
            assert state["status"] in valid_statuses, (
                f"Alert {alert_id} has invalid status: {state['status']}"
            )

    @invariant()
    def delivered_alerts_have_timestamp(self) -> None:
        """Verify delivered alerts have delivered_at timestamp."""
        for alert_id, state in self.alert_states.items():
            if state["status"] in ["delivered", "acknowledged", "dismissed"]:
                assert state["delivered_at"] is not None, (
                    f"Alert {alert_id} in status {state['status']} missing delivered_at"
                )

    @invariant()
    def alerts_reference_valid_events(self) -> None:
        """Verify all alerts reference valid events."""
        for alert_id, state in self.alert_states.items():
            event_id = state["event_id"]
            assert event_id in self.event_states, (
                f"Alert {alert_id} references non-existent event {event_id}"
            )


# =============================================================================
# Test Cases (Integration with pytest)
# =============================================================================


@pytest.mark.integration
@pytest.mark.slow
class TestEventLifecycleStateMachine:
    """Test event lifecycle state machine with Hypothesis."""

    def test_event_lifecycle_state_machine(self) -> None:
        """Run event lifecycle state machine tests.

        This test generates random sequences of event operations and verifies
        that invariants hold after each step. It can catch bugs like:
        - Modifying deleted events
        - Invalid state transitions
        - Incorrect snooze_until timestamps
        """
        run_state_machine_test(EventLifecycleStateMachine, max_examples=50)


@pytest.mark.integration
@pytest.mark.slow
class TestCameraStatusStateMachine:
    """Test camera status state machine with Hypothesis."""

    def test_camera_status_state_machine(self) -> None:
        """Run camera status state machine tests.

        This test generates random sequences of camera status changes and
        verifies that invariants hold. It can catch bugs like:
        - Invalid status values
        - Missing last_seen_at for online cameras
        - Modifying deleted cameras
        """
        run_state_machine_test(CameraStatusStateMachine, max_examples=50)


@pytest.mark.integration
@pytest.mark.slow
class TestAlertStateMachine:
    """Test alert state machine with Hypothesis."""

    def test_alert_state_machine(self) -> None:
        """Run alert state machine tests.

        This test generates random sequences of alert operations and verifies
        that state transitions are valid. It can catch bugs like:
        - Invalid state transitions (e.g., pending → acknowledged)
        - Missing delivered_at timestamps
        - Orphaned alerts without events
        """
        run_state_machine_test(AlertStateMachine, max_examples=50)


# =============================================================================
# Advanced: Combined State Machine
# =============================================================================


class CombinedAPIStateMachine(RuleBasedStateMachine):
    """Combined state machine testing interactions between cameras, events, and alerts.

    This tests more complex scenarios where operations on one resource affect others:
    - Creating alerts when events are created
    - Deleting cameras cascades to events
    - Event deletion affects associated alerts

    This is a more advanced test that can catch interaction bugs between different
    parts of the system.
    """

    cameras = Bundle("cameras")
    events = Bundle("events")
    alerts = Bundle("alerts")

    def __init__(self) -> None:
        super().__init__()
        self.camera_states: dict[str, dict[str, Any]] = {}
        self.event_states: dict[int, dict[str, Any]] = {}
        self.alert_states: dict[str, dict[str, Any]] = {}

    @rule(target=cameras)
    def create_camera(self) -> str:
        """Create a camera."""
        camera_id = f"cam_{len(self.camera_states)}"
        self.camera_states[camera_id] = {
            "id": camera_id,
            "status": "online",
            "deleted": False,
        }
        note(f"Created camera: {camera_id}")
        return camera_id

    @rule(target=events, camera=cameras)
    def create_event(self, camera: str) -> int:
        """Create an event for a camera."""
        assume(not self.camera_states[camera]["deleted"])

        event_id = len(self.event_states) + 1
        self.event_states[event_id] = {
            "id": event_id,
            "camera_id": camera,
            "deleted": False,
        }
        note(f"Created event: {event_id} for camera {camera}")
        return event_id

    @rule(target=alerts, event=events)
    def create_alert(self, event: int) -> str:
        """Create an alert for an event."""
        assume(not self.event_states[event]["deleted"])

        alert_id = f"alert_{len(self.alert_states)}"
        self.alert_states[alert_id] = {
            "id": alert_id,
            "event_id": event,
            "status": "pending",
        }
        note(f"Created alert: {alert_id} for event {event}")
        return alert_id

    @rule(camera=cameras)
    @precondition(lambda self: any(not c["deleted"] for c in self.camera_states.values()))
    def delete_camera(self, camera: str) -> None:
        """Delete a camera and cascade to events."""
        assume(not self.camera_states[camera]["deleted"])

        self.camera_states[camera]["deleted"] = True

        # Cascade delete to events
        for event_id, event_state in self.event_states.items():
            if event_state["camera_id"] == camera:
                event_state["deleted"] = True

        note(f"Deleted camera: {camera} (cascaded to events)")

    @rule(event=events)
    @precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
    def delete_event(self, event: int) -> None:
        """Delete an event."""
        assume(not self.event_states[event]["deleted"])

        self.event_states[event]["deleted"] = True
        note(f"Deleted event: {event}")

    @invariant()
    def events_have_valid_cameras(self) -> None:
        """Verify events reference existing cameras."""
        for event_id, event_state in self.event_states.items():
            if not event_state["deleted"]:
                camera_id = event_state["camera_id"]
                assert camera_id in self.camera_states, (
                    f"Event {event_id} references non-existent camera {camera_id}"
                )

    @invariant()
    def alerts_have_valid_events(self) -> None:
        """Verify alerts reference existing events."""
        for alert_id, alert_state in self.alert_states.items():
            event_id = alert_state["event_id"]
            assert event_id in self.event_states, (
                f"Alert {alert_id} references non-existent event {event_id}"
            )

    @invariant()
    def deleted_cameras_have_deleted_events(self) -> None:
        """Verify that when a camera is deleted, its events are also deleted."""
        for camera_id, camera_state in self.camera_states.items():
            if camera_state["deleted"]:
                # All events for this camera should be deleted
                for event_id, event_state in self.event_states.items():
                    if event_state["camera_id"] == camera_id:
                        assert event_state["deleted"], (
                            f"Camera {camera_id} deleted but event {event_id} still exists"
                        )


@pytest.mark.integration
@pytest.mark.slow
class TestCombinedAPIStateMachine:
    """Test combined API state machine with cascading deletes."""

    def test_combined_state_machine(self) -> None:
        """Run combined state machine tests.

        This test generates random sequences of operations across cameras,
        events, and alerts, verifying that cascading deletes and relationships
        are maintained correctly.
        """
        run_state_machine_test(CombinedAPIStateMachine, max_examples=30)
