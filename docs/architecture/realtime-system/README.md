# Real-time System Hub

Documentation hub for the WebSocket-based real-time event broadcasting system.

## System Overview

```
Publishers --> Redis Pub/Sub --> EventBroadcaster --> SubscriptionManager --> WebSocketManager --> Clients
```

The real-time system enables instant dashboard updates without polling by using WebSocket connections backed by Redis pub/sub for multi-instance scalability.

## Architecture Diagram

```mermaid
flowchart LR
    subgraph Publishers["Event Publishers"]
        NA[NemotronAnalyzer]
        GPU[GPUMonitor]
        HM[HealthMonitor]
        CS[CameraService]
    end

    subgraph Redis["Redis"]
        PubSub[(Pub/Sub Channel<br/>security_events)]
    end

    subgraph Backend["Backend Services"]
        EB[EventBroadcaster]
        SM[SubscriptionManager]
    end

    subgraph WebSocket["WebSocket Layer"]
        WS1[/ws/events]
        WS2[/ws/system]
        WS3[/ws/jobs/{id}/logs]
    end

    subgraph Clients["Frontend Clients"]
        C1[useWebSocket]
        C2[useEventStream]
        C3[WebSocketManager]
    end

    Publishers -->|publish| PubSub
    PubSub -->|subscribe| EB
    EB -->|filter| SM
    SM -->|route| WebSocket
    WebSocket -->|messages| Clients
```

## Key Components

| Component                                      | Location                                         | Description                                                    |
| ---------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------- |
| [EventBroadcaster](event-broadcaster.md)       | `backend/services/event_broadcaster.py`          | Manages Redis subscription and broadcasts to WebSocket clients |
| [SubscriptionManager](subscription-manager.md) | `backend/core/websocket/subscription_manager.py` | Filters events per client using wildcard patterns              |
| [WebSocket Routes](websocket-server.md)        | `backend/api/routes/websocket.py`                | FastAPI WebSocket endpoints and connection lifecycle           |
| [Message Schemas](message-formats.md)          | `backend/api/schemas/websocket.py`               | Pydantic schemas for all message types                         |
| [Frontend Hooks](client-integration.md)        | `frontend/src/hooks/`                            | React hooks for WebSocket connections                          |

## WebSocket Endpoints

| Endpoint                 | Purpose                      | Message Frequency |
| ------------------------ | ---------------------------- | ----------------- |
| `/ws/events`             | Security event notifications | On event creation |
| `/ws/system`             | System health and GPU stats  | Every 5 seconds   |
| `/ws/jobs/{job_id}/logs` | Real-time job log streaming  | On log emission   |

## Data Flow

1. **Event Creation**: AI pipeline components (NemotronAnalyzer, health monitors) create events
2. **Redis Publishing**: Events are published to the `security_events` Redis channel
3. **Subscription Filtering**: EventBroadcaster receives events and uses SubscriptionManager to determine recipients
4. **WebSocket Delivery**: Messages are sent to connected clients with sequence numbers
5. **Client Processing**: Frontend hooks parse messages and update React state

## Message Delivery Guarantees

- **Sequence Numbers**: All messages include monotonically increasing sequence numbers
- **Message Buffering**: Last 100 messages are buffered for replay on reconnection
- **Acknowledgment**: High-priority messages (risk_score >= 80 or critical) require acknowledgment
- **Retry Logic**: Failed broadcasts use exponential backoff with configurable retries

## Documents in This Hub

1. [README.md](README.md) - This overview document
2. [websocket-server.md](websocket-server.md) - WebSocket endpoints and connection lifecycle
3. [subscription-manager.md](subscription-manager.md) - Event filtering with pattern matching
4. [event-broadcaster.md](event-broadcaster.md) - Redis pub/sub integration and broadcasting
5. [message-formats.md](message-formats.md) - Message schemas and JSON examples
6. [client-integration.md](client-integration.md) - Frontend hooks and reconnection flow

## Quick Reference

### Configuration Settings

| Setting                           | Default           | Description                     |
| --------------------------------- | ----------------- | ------------------------------- |
| `redis_event_channel`             | `security_events` | Redis pub/sub channel name      |
| `websocket_idle_timeout_seconds`  | `300`             | Connection idle timeout         |
| `websocket_ping_interval_seconds` | `30`              | Server heartbeat interval       |
| `websocket_compression_threshold` | `1024`            | Bytes threshold for compression |

### Source Files

```
backend/
  services/
    event_broadcaster.py     # EventBroadcaster, retry logic
    system_broadcaster.py    # SystemBroadcaster for /ws/system
  core/
    websocket/
      subscription_manager.py  # Pattern-based event filtering
      sequence_tracker.py      # Message sequence tracking
      compression.py           # Message compression
  api/
    routes/
      websocket.py            # WebSocket endpoints
    schemas/
      websocket.py            # Pydantic message schemas

frontend/
  src/
    hooks/
      useWebSocket.ts         # Core WebSocket hook
      useEventStream.ts       # Security event stream hook
      webSocketManager.ts     # Connection deduplication
      sequenceValidator.ts    # Gap detection
    components/
      common/
        ConnectionStatusBanner.tsx  # Disconnection banner
        WebSocketStatus.tsx         # Status indicator
```

## Related Documentation

- [Real-Time Architecture Overview](../real-time.md)
- [Resilience Patterns](../resilience-patterns/README.md)
- [API Reference](../api-reference/README.md)
