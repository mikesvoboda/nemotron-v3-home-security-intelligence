# Unit Tests - Core WebSocket Components

## Purpose

The `backend/tests/unit/core/websocket/` directory contains unit tests for the WebSocket infrastructure in `backend/core/websocket/`. These tests validate WebSocket event types, message batching, channel routing, and payload validation.

## Directory Structure

```
backend/tests/unit/core/websocket/
├── AGENTS.md                          # This file
├── test_enrichment_queue_events.py    # Enrichment and queue event types
└── test_message_batcher.py            # Message batching for high-frequency events
```

## Test Files

### Event Types and Channels

| File                              | Tests For                                     | Linear Issues      |
| --------------------------------- | --------------------------------------------- | ------------------ |
| `test_enrichment_queue_events.py` | Enrichment and queue metrics WebSocket events | NEM-3627, NEM-3637 |

**Coverage:**

- `WebSocketEventType` enum values for enrichment events (ENRICHMENT_STARTED, ENRICHMENT_PROGRESS, ENRICHMENT_COMPLETED, ENRICHMENT_FAILED)
- `WebSocketEventType` enum values for queue events (QUEUE_STATUS, PIPELINE_THROUGHPUT)
- Event metadata registration in `EVENT_TYPE_METADATA`
- Channel routing via `get_event_channel()`
- Required payload fields via `get_required_payload_fields()`
- Event type validation via `validate_event_type()`
- Event creation via `create_event()`
- Channel registry via `get_all_channels()`

### Message Batching

| File                      | Tests For                                  | Linear Issues |
| ------------------------- | ------------------------------------------ | ------------- |
| `test_message_batcher.py` | Intelligent message batching for WebSocket | NEM-3738      |

**Coverage:**

- `BatchedMessage` dataclass (defaults, serialization)
- `BatchMetrics` dataclass (defaults, efficiency calculation)
- `MessageBatcher` initialization (default and custom values)
- Start/stop lifecycle and idempotency
- Message queuing for batched vs non-batched channels
- Max batch size triggers
- Interval-based automatic flushing
- Flush operations (single channel, all channels)
- Pending message counting
- Metrics tracking
- Error handling (callback failures, missing callbacks)
- Concurrency safety
- Module-level singleton functions (`get_message_batcher`, `stop_message_batcher`)

## Running Tests

```bash
# All WebSocket unit tests in this directory
uv run pytest backend/tests/unit/core/websocket/ -v

# Enrichment and queue event tests
uv run pytest backend/tests/unit/core/websocket/test_enrichment_queue_events.py -v

# Message batcher tests
uv run pytest backend/tests/unit/core/websocket/test_message_batcher.py -v

# With coverage
uv run pytest backend/tests/unit/core/websocket/ -v --cov=backend/core/websocket

# Parallel execution
uv run pytest backend/tests/unit/core/websocket/ -n auto --dist=worksteal

# Single test class
uv run pytest backend/tests/unit/core/websocket/test_message_batcher.py::TestMessageBatcherFlush -v
```

## Fixtures Used

### From Test Files

| Fixture         | Scope    | Description                              |
| --------------- | -------- | ---------------------------------------- |
| `batcher`       | function | Fresh `MessageBatcher` instance per test |
| `send_callback` | function | Mock async send callback                 |
| `reset_state`   | autouse  | Resets module-level singleton state      |

### From `backend/tests/conftest.py`

| Fixture                | Scope              | Description                                  |
| ---------------------- | ------------------ | -------------------------------------------- |
| `reset_settings_cache` | function (autouse) | Clears settings cache before/after each test |

## Test Patterns

### Event Type Existence Pattern

```python
def test_event_type_exists(self):
    """Verify event type is defined in the enum."""
    assert hasattr(WebSocketEventType, "ENRICHMENT_STARTED")
    assert WebSocketEventType.ENRICHMENT_STARTED.value == "enrichment.started"
```

### Required Fields Validation Pattern

```python
def test_event_has_required_fields(self):
    """Verify event type has expected required payload fields."""
    fields = get_required_payload_fields(WebSocketEventType.ENRICHMENT_STARTED)
    assert "batch_id" in fields
    assert "camera_id" in fields
```

### Async Lifecycle Pattern

```python
@pytest.mark.asyncio
async def test_start_stop_lifecycle(self, batcher: MessageBatcher):
    """Test component start/stop lifecycle."""
    assert not batcher.is_running()
    await batcher.start()
    assert batcher.is_running()
    await batcher.stop()
    assert not batcher.is_running()
```

### Module Singleton Reset Pattern

```python
@pytest.fixture(autouse=True)
def reset_state(self):
    """Reset module state before each test."""
    reset_message_batcher_state()
    yield
    reset_message_batcher_state()
```

### Interval-Based Async Testing Pattern

```python
@pytest.mark.asyncio
async def test_interval_flush(self, send_callback: AsyncMock):
    """Test interval-based automatic flushing."""
    batcher = MessageBatcher(batch_interval_ms=50, max_batch_size=100)
    await batcher.start()
    try:
        await batcher.queue_message("detections", {"id": 1}, send_callback)
        await asyncio.sleep(0.1)  # Wait for interval
        send_callback.assert_called_once()
    finally:
        await batcher.stop()
```

## Related Documentation

- `/backend/core/websocket/AGENTS.md` - WebSocket infrastructure documentation
- `/backend/tests/unit/core/AGENTS.md` - Core unit tests overview
- `/backend/tests/unit/core/test_websocket*.py` - Additional WebSocket tests
- `/backend/tests/conftest.py` - Shared fixtures and helpers
- `/backend/tests/AGENTS.md` - Test infrastructure overview
