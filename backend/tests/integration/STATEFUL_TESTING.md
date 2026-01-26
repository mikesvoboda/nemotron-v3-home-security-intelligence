# Hypothesis Stateful Testing for API State Machines

This directory contains Hypothesis stateful tests for verifying API state machine correctness. These tests explore many possible sequences of operations to catch bugs where API behavior depends on the order of operations.

## Overview

Hypothesis stateful testing uses `RuleBasedStateMachine` to:

1. Define **rules** (API operations that can be performed)
2. Define **invariants** (properties that must hold after any sequence of operations)
3. Generate random sequences of operations and verify invariants

This approach catches bugs that traditional unit/integration tests miss, such as:

- Invalid state transitions
- Operations that should be forbidden in certain states
- Cascading side effects between related entities
- Race conditions in state management

## Test Files

### `test_stateful_api.py`

Pure state machine tests that track expected state without database operations. These are fast and validate the state machine logic.

**State Machines:**

- `EventLifecycleStateMachine`: Events (create → review → flag → snooze → delete → restore)
- `CameraStatusStateMachine`: Camera status transitions (online ↔ offline ↔ error ↔ unknown)
- `AlertStateMachine`: Alert states (pending → delivered → acknowledged → dismissed)
- `CombinedAPIStateMachine`: Cascading operations (camera deletion cascades to events)

**Run:**

```bash
# All stateful tests
pytest backend/tests/integration/test_stateful_api.py -v

# Single test with statistics
pytest backend/tests/integration/test_stateful_api.py::TestEventLifecycleStateMachine -v --hypothesis-show-statistics
```

### `test_stateful_api_with_db.py`

Extended tests that verify database state matches expected state. These are slower but provide end-to-end validation.

**State Machines:**

- `EventLifecycleAPIStateMachine`: Same as above, with DB verification
- `CameraStatusAPIStateMachine`: Same as above, with DB verification
- `AlertStateAPIStateMachine`: Same as above, with DB verification

**Run:**

```bash
# All DB stateful tests
pytest backend/tests/integration/test_stateful_api_with_db.py -v

# Run with fewer examples for faster execution
pytest backend/tests/integration/test_stateful_api_with_db.py -v --hypothesis-max-examples=10
```

## Example: Event Lifecycle State Machine

```python
class EventLifecycleStateMachine(RuleBasedStateMachine):
    """Test event lifecycle state transitions."""

    events = Bundle("events")  # Track created events
    cameras = Bundle("cameras")  # Track created cameras

    @rule(target=cameras)
    def create_camera(self) -> str:
        """Create a camera (rule: can always create cameras)."""
        camera_id = f"cam_{len(self.cameras)}"
        # Track state
        self.camera_states[camera_id] = {"status": "online"}
        return camera_id

    @rule(target=events, camera=cameras)
    def create_event(self, camera: str) -> int:
        """Create an event for a camera (rule: needs existing camera)."""
        event_id = len(self.events) + 1
        self.event_states[event_id] = {
            "camera_id": camera,
            "reviewed": False,
        }
        return event_id

    @rule(event=events)
    @precondition(lambda self: any(not e["reviewed"] for e in self.event_states.values()))
    def review_event(self, event: int) -> None:
        """Mark event as reviewed (rule: only if not already reviewed)."""
        assume(not self.event_states[event]["reviewed"])
        self.event_states[event]["reviewed"] = True

    @invariant()
    def reviewed_events_stay_reviewed(self) -> None:
        """Invariant: reviewed flag can only be set, never unset."""
        for event_id, state in self.event_states.items():
            if state["reviewed"]:
                assert state["reviewed"] is True
```

## Key Concepts

### Rules

Rules define operations that can be performed on the system. Each rule:

- Can have preconditions (when it's allowed to run)
- Can use values from bundles (previously created entities)
- Returns values that can be used by other rules

```python
@rule(target=events, camera=cameras)
def create_event(self, camera: str) -> int:
    """Create event (uses camera from cameras bundle)."""
    # Implementation
    return event_id
```

### Invariants

Invariants are properties that must hold after every operation. They verify system correctness.

```python
@invariant()
def events_reference_valid_cameras(self) -> None:
    """All events must reference existing cameras."""
    for event_id, state in self.event_states.items():
        camera_id = state["camera_id"]
        assert camera_id in self.camera_states
```

### Bundles

Bundles track created resources that can be used by other rules.

```python
events = Bundle("events")  # Store event IDs
cameras = Bundle("cameras")  # Store camera IDs

@rule(target=events)
def create_event(self) -> int:
    return event_id  # Added to events bundle

@rule(event=events)  # Uses value from events bundle
def review_event(self, event: int) -> None:
    pass
```

### Preconditions

Preconditions restrict when a rule can run.

```python
@rule(event=events)
@precondition(lambda self: any(not e["reviewed"] for e in self.event_states.values()))
def review_event(self, event: int) -> None:
    """Only run if there are unreviewed events."""
    assume(not self.event_states[event]["reviewed"])
```

## Debugging Failed Tests

### Reproducing Failures

When Hypothesis finds a failing sequence, it outputs:

```
Falsifying example: run_state_machine(
    state=EventLifecycleStateMachine(),
    steps=[
        Step(create_camera, {}),
        Step(create_event, {'camera': 'cam_0'}),
        Step(delete_camera, {'camera': 'cam_0'}),
        # Event now references deleted camera!
    ]
)
```

To reproduce:

```bash
# Use the seed from test output
pytest backend/tests/integration/test_stateful_api.py --hypothesis-seed=12345
```

### Adding Debug Output

Use `note()` to log operations:

```python
from hypothesis import note

@rule(event=events)
def review_event(self, event: int) -> None:
    note(f"Reviewing event {event}")
    self.event_states[event]["reviewed"] = True
```

### Viewing Statistics

```bash
pytest backend/tests/integration/test_stateful_api.py -v --hypothesis-show-statistics
```

## Configuration

Tests use these Hypothesis settings:

```python
settings(
    max_examples=50,        # Number of test sequences
    stateful_step_count=20, # Max steps per sequence
    deadline=None,          # No timeout for async operations
)
```

Adjust in `run_state_machine_test()` helper:

```python
run_state_machine_test(EventLifecycleStateMachine, max_examples=100)
```

## Best Practices

### 1. Keep State Minimal

Only track state necessary to verify invariants.

```python
# Good: Track only essential fields
self.event_states[event_id] = {"reviewed": False, "deleted": False}

# Bad: Track unnecessary fields
self.event_states[event_id] = {"reviewed": False, "deleted": False, "created_at": ..., "summary": ...}
```

### 2. Use Preconditions

Prevent invalid operations with preconditions.

```python
@rule(event=events)
@precondition(lambda self: any(not e["deleted"] for e in self.event_states.values()))
def review_event(self, event: int) -> None:
    """Only review non-deleted events."""
    assume(not self.event_states[event]["deleted"])
```

### 3. Test One Concern Per Invariant

Keep invariants focused and clear.

```python
# Good: Single concern
@invariant()
def reviewed_events_stay_reviewed(self) -> None:
    for event in self.event_states.values():
        if event["reviewed"]:
            assert event["reviewed"] is True

# Bad: Multiple concerns
@invariant()
def verify_all_event_properties(self) -> None:
    # Checks reviewed, deleted, camera, etc. - too broad
```

### 4. Use assume() for Dynamic Preconditions

When preconditions depend on runtime state:

```python
@rule(event=events)
def review_event(self, event: int) -> None:
    # Dynamic check: this specific event isn't deleted
    assume(not self.event_states[event]["deleted"])
    self.event_states[event]["reviewed"] = True
```

## Common Patterns

### Cascading Deletes

```python
@rule(camera=cameras)
def delete_camera(self, camera: str) -> None:
    """Delete camera and cascade to events."""
    self.camera_states[camera]["deleted"] = True

    # Cascade to events
    for event in self.event_states.values():
        if event["camera_id"] == camera:
            event["deleted"] = True

@invariant()
def deleted_cameras_have_no_active_events(self) -> None:
    """Verify cascade worked."""
    for camera in self.camera_states.values():
        if camera["deleted"]:
            for event in self.event_states.values():
                if event["camera_id"] == camera["id"]:
                    assert event["deleted"]
```

### State Machine Transitions

```python
VALID_TRANSITIONS = {
    "pending": ["delivered"],
    "delivered": ["acknowledged", "dismissed"],
    "acknowledged": ["dismissed"],
}

@rule(alert=alerts, new_status=sampled_from(["delivered", "acknowledged", "dismissed"]))
def change_alert_status(self, alert: str, new_status: str) -> None:
    """Change alert status following state machine rules."""
    current_status = self.alert_states[alert]["status"]

    # Only allow valid transitions
    assume(new_status in VALID_TRANSITIONS.get(current_status, []))

    self.alert_states[alert]["status"] = new_status
```

## Performance Tips

### 1. Adjust max_examples for CI vs Local

```python
# Local development: fast feedback
run_state_machine_test(MyStateMachine, max_examples=20)

# CI: thorough testing
run_state_machine_test(MyStateMachine, max_examples=100)
```

### 2. Use @pytest.mark.slow

```python
@pytest.mark.slow
@pytest.mark.integration
def test_stateful_api():
    """Mark as slow to skip during quick test runs."""
    run_state_machine_test(MyStateMachine)
```

### 3. Parallel Execution

Stateful tests can run in parallel with pytest-xdist:

```bash
pytest backend/tests/integration/test_stateful_api.py -n auto
```

## Related Documentation

- [Hypothesis Stateful Testing Docs](https://hypothesis.readthedocs.io/en/latest/stateful.html)
- [Testing Guide](/home/msvoboda/.claude-squad/worktrees/msvoboda/big2_188e4de2e2198f84/docs/development/testing.md)
- [Integration Test Patterns](/home/msvoboda/.claude-squad/worktrees/msvoboda/big2_188e4de2e2198f84/backend/tests/integration/AGENTS.md)
- [Hypothesis Strategies](/home/msvoboda/.claude-squad/worktrees/msvoboda/big2_188e4de2e2198f84/backend/tests/strategies.py)

## References

- **NEM-3746**: Implement Hypothesis Stateful Testing for API State Machines
- **NEM-3736**: Platform Technology Improvements - Context7 Research (Epic)
