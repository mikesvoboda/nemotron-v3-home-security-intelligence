# Integration Tests - WebSocket

## Purpose

The `backend/tests/integration/websocket/` directory contains integration tests for WebSocket functionality, specifically testing broadcast triggers and event delivery.

## Directory Structure

```
backend/tests/integration/websocket/
├── AGENTS.md                       # This file
└── test_broadcast_triggers.py      # WebSocket broadcast trigger tests (28KB)
```

## Test Files (1 total)

### `test_broadcast_triggers.py`

Tests for WebSocket broadcast triggers when database state changes:

| Test Class                       | Coverage                                |
| -------------------------------- | --------------------------------------- |
| `TestEventBroadcastTriggers`     | Event creation triggers broadcast       |
| `TestDetectionBroadcastTriggers` | Detection creation triggers broadcast   |
| `TestCameraBroadcastTriggers`    | Camera status changes trigger broadcast |
| `TestBatchBroadcastTriggers`     | Batch completion triggers broadcast     |
| `TestBroadcastFiltering`         | Channel-specific filtering              |

## Running Tests

```bash
# All WebSocket integration tests
uv run pytest backend/tests/integration/websocket/ -v

# With verbose output
uv run pytest backend/tests/integration/websocket/ -vv -s

# With coverage
uv run pytest backend/tests/integration/websocket/ -v --cov=backend.api.routes.websocket
```

## Key Test Patterns

### Event Broadcast Trigger

```python
@pytest.mark.asyncio
async def test_event_creation_triggers_broadcast(
    session, mock_redis, event_broadcaster
):
    # Create event
    event = Event(
        camera_id="test_cam",
        risk_score=75,
        summary="Test event"
    )
    session.add(event)
    await session.commit()

    # Verify broadcast was triggered
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "events"  # channel
    assert "risk_score" in call_args[0][1]  # message contains event data
```

### Camera Status Broadcast

```python
@pytest.mark.asyncio
async def test_camera_offline_triggers_broadcast(
    session, mock_redis, system_broadcaster
):
    # Update camera status
    camera = await session.get(Camera, "test_cam")
    camera.status = "offline"
    await session.commit()

    # Verify system status broadcast
    mock_redis.publish.assert_called()
    assert any(
        "camera_status" in str(call)
        for call in mock_redis.publish.call_args_list
    )
```

## Broadcast Channels

| Channel  | Trigger Events                           |
| -------- | ---------------------------------------- |
| `events` | New event, event update, event deletion  |
| `system` | Camera status, GPU stats, health updates |
| `alerts` | New alert, alert acknowledgment          |

## Related Documentation

- `/backend/api/routes/websocket.py` - WebSocket route handlers
- `/backend/services/event_broadcaster.py` - Event broadcaster service
- `/backend/services/system_broadcaster.py` - System broadcaster service
- `/backend/tests/integration/AGENTS.md` - Integration tests overview
