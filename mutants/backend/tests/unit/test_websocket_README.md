# WebSocket Tests Documentation

This document describes the test suite for the WebSocket event and system channels.

## Overview

These tests follow **Test-Driven Development (TDD)** principles, defining the expected behavior of the WebSocket channels before implementation. The tests validate:

1. **Unit Tests** (`test_websocket.py`) - Broadcaster class behavior and message handling
2. **Integration Tests** (`../integration/test_websocket.py`) - Endpoint connections and real-time communication

## WebSocket Endpoints

### `/ws/events` - Event Channel

Broadcasts real-time event and detection updates to connected clients.

**Message Types:**

- `new_event` - New security event created

  ```json
  {
    "type": "new_event",
    "data": {
      "id": 1,
      "camera_id": "cam-123",
      "risk_score": 75,
      "risk_level": "high",
      "summary": "Person detected at front door",
      "reasoning": "Analysis text...",
      "started_at": "2025-12-23T12:00:00",
      "ended_at": "2025-12-23T12:01:30"
    }
  }
  ```

- `detection` - New object detection
  ```json
  {
    "type": "detection",
    "data": {
      "id": 1,
      "camera_id": "cam-123",
      "object_type": "person",
      "confidence": 0.95,
      "detected_at": "2025-12-23T12:00:00",
      "bbox_x": 100,
      "bbox_y": 150,
      "bbox_width": 200,
      "bbox_height": 400
    }
  }
  ```

### `/ws/system` - System Channel

Broadcasts system status updates to connected clients.

**Message Types:**

- `gpu_stats` - GPU performance metrics

  ```json
  {
    "type": "gpu_stats",
    "data": {
      "gpu_utilization": 75.5,
      "memory_used": 12345678900,
      "memory_total": 25769803776,
      "temperature": 72.0,
      "inference_fps": 30.5,
      "recorded_at": "2025-12-23T12:00:00"
    }
  }
  ```

- `camera_status` - Camera status changes
  ```json
  {
    "type": "camera_status",
    "data": {
      "camera_id": "cam-123",
      "status": "online",
      "last_seen_at": "2025-12-23T12:00:00"
    }
  }
  ```

## Test Structure

### Unit Tests (`test_websocket.py`)

Tests the broadcaster classes in isolation using mock WebSocket connections.

**Classes Tested:**

- `EventBroadcaster` - Manages `/ws/events` connections and broadcasts
- `SystemBroadcaster` - Manages `/ws/system` connections and broadcasts

**Test Coverage:**

1. **Connection Management**

   - Adding WebSocket connections
   - Removing WebSocket connections
   - Handling multiple concurrent connections
   - Graceful disconnect on errors

2. **Broadcasting**

   - Broadcasting to zero connections
   - Broadcasting to single connection
   - Broadcasting to multiple connections
   - Handling failed connections during broadcast

3. **Message Format**
   - Correct message type and data structure
   - JSON serialization
   - DateTime ISO format handling

**Key Tests:**

- `test_connect_websocket` - Verify connection tracking
- `test_broadcast_new_event_multiple_connections` - Multi-client broadcast
- `test_broadcast_new_event_with_failed_connection` - Error resilience
- `test_message_serialization` - JSON format validation

### Integration Tests (`../integration/test_websocket.py`)

Tests the actual WebSocket endpoints using Starlette's TestClient.

**Test Coverage:**

1. **Connection Tests**

   - Establishing WebSocket connections
   - Graceful disconnection
   - Reconnection after disconnect
   - Multiple concurrent connections

2. **Message Reception**

   - Receiving new_event broadcasts
   - Receiving detection broadcasts
   - Receiving gpu_stats broadcasts
   - Receiving camera_status broadcasts

3. **Connection Cleanup**

   - Proper cleanup on disconnect
   - No leaked connections
   - Mixed endpoint cleanup

4. **Error Handling**

   - Invalid WebSocket paths
   - Connection error handling

5. **Broadcast Functionality** (TDD)
   - Broadcasting to all connected clients
   - Channel isolation (events vs system)

**Key Tests:**

- `test_events_websocket_connection` - Basic connection establishment
- `test_events_websocket_multiple_connections` - Concurrent connections
- `test_events_websocket_cleanup_on_disconnect` - Resource cleanup
- `test_isolated_channels` - Channel separation

## Running Tests

### Run Unit Tests Only

```bash
cd /home/msvoboda/github/nemotron-v3-home-security-intelligence
source .venv/bin/activate
python -m pytest backend/tests/unit/test_websocket.py -v
```

### Run Integration Tests Only

```bash
python -m pytest backend/tests/integration/test_websocket.py -v
```

### Run All WebSocket Tests

```bash
python -m pytest backend/tests/unit/test_websocket.py backend/tests/integration/test_websocket.py -v
```

### Run with Coverage

```bash
python -m pytest backend/tests/unit/test_websocket.py backend/tests/integration/test_websocket.py --cov=backend --cov-report=term-missing
```

## Implementation Requirements

When implementing the actual WebSocket channels (tasks 7z7.9 and 7z7.10), the implementation must:

1. **Create Broadcaster Classes**

   - `EventBroadcaster` in `backend/api/websocket.py` or similar
   - `SystemBroadcaster` in the same module
   - Implement connection management (connect/disconnect)
   - Implement broadcast methods matching test signatures

2. **Create WebSocket Routes**

   - Add `/ws/events` endpoint in `backend/api/routes/websocket.py`
   - Add `/ws/system` endpoint in the same file
   - Register routes in `backend/main.py`

3. **Integration Points**

   - `NemotronAnalyzer` should call `EventBroadcaster.broadcast_new_event()` after creating events
   - Detection pipeline should call `EventBroadcaster.broadcast_detection()` for real-time updates
   - GPU monitor service should call `SystemBroadcaster.broadcast_gpu_stats()` periodically
   - Camera status changes should call `SystemBroadcaster.broadcast_camera_status()`

4. **Message Format**
   - All messages must follow the format: `{"type": "message_type", "data": {...}}`
   - DateTime fields must be ISO 8601 formatted strings
   - All numeric values must be JSON-serializable

## Expected Test Results

### Before Implementation (Current State)

- **Unit tests**: ✅ PASS (25/25) - Using mock classes
- **Integration tests**: ⚠️ PASS (24/24) - Connections work but no actual broadcasting

### After Implementation (Expected)

- **Unit tests**: ✅ PASS (25/25) - Testing real broadcaster classes
- **Integration tests**: ✅ PASS (24/24) - Full end-to-end WebSocket communication

## Design Decisions

1. **Separate Channels**

   - `/ws/events` and `/ws/system` are isolated
   - Prevents event spam from affecting system status monitoring
   - Allows clients to subscribe only to needed updates

2. **Message Format**

   - Consistent `{type, data}` structure for all messages
   - Type field enables client-side routing
   - Data field contains message-specific payload

3. **Connection Management**

   - Connections stored in sets for O(1) add/remove
   - Failed sends are caught and logged (don't crash broadcaster)
   - Graceful cleanup on disconnect

4. **Broadcasting**
   - Non-blocking (doesn't wait for all clients to acknowledge)
   - Returns count of successful sends
   - Tolerates individual client failures

## Related Tasks

- **7z7.9** - Implement WebSocket event channel (`/ws/events`)
- **7z7.10** - Implement WebSocket system channel (`/ws/system`)
- **7z7.18** - Write tests for WebSocket channels (THIS TASK)

## References

- Design spec: `/home/msvoboda/github/nemotron-v3-home-security-intelligence/docs/plans/2024-12-21-dashboard-mvp-design.md`
- FastAPI WebSockets: https://fastapi.tiangolo.com/advanced/websockets/
- Starlette WebSockets: https://www.starlette.io/websockets/
