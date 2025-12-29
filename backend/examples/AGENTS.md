# Backend Examples - Agent Guide

## Purpose

This directory contains practical code examples demonstrating how to use core backend infrastructure components. These examples serve as:

1. **Reference implementations** for developers
2. **Integration test templates** for validating services
3. **Onboarding material** for understanding system architecture
4. **Debugging tools** for troubleshooting Redis connectivity and operations

## Key Files

### `__init__.py`

Empty module initialization file. This directory is primarily for standalone example scripts.

### `redis_example.py`

Comprehensive demonstration of Redis client usage patterns in the home security intelligence system.

**Purpose:** Shows how to use the `RedisClient` class from `backend.core.redis` for:

- Queue operations (batch processing pipeline)
- Pub/sub messaging (real-time event broadcasting)
- Cache operations (temporary data storage)
- Health checking (service monitoring)

**Structure:**

- `example_queue_operations()` - Demonstrates batch processing queue
- `example_pubsub()` - Demonstrates real-time event broadcasting
- `example_cache_operations()` - Demonstrates temporary data caching
- `example_health_check()` - Demonstrates Redis connectivity verification
- `main()` - Runs all examples sequentially

## Redis Example Breakdown

### 1. Queue Operations (`example_queue_operations`)

**Use Case:** Batch processing pipeline for detections before Nemotron analysis

**Operations Demonstrated:**

- `clear_queue(queue_name)` - Reset queue state
- `add_to_queue(queue_name, data)` - Push detection to queue (RPUSH)
- `get_queue_length(queue_name)` - Check queue size (LLEN)
- `peek_queue(queue_name, start, end)` - View items without removing (LRANGE)
- `get_from_queue(queue_name, timeout)` - Pop item for processing (BLPOP)

**Example Flow:**

1. Add 5 mock detections to queue
2. Check queue length (expect 5)
3. Peek at first 3 items without removing
4. Process all items (FIFO order)
5. Verify queue is empty

**Real-World Usage:**

- File watcher service adds new detections to queue
- Batch aggregator pops detections for analysis
- 90-second time windows with 30-second idle timeout

### 2. Pub/Sub Operations (`example_pubsub`)

**Use Case:** Real-time WebSocket updates to frontend dashboard

**Operations Demonstrated:**

- `subscribe(channel)` - Create pub/sub subscription
- `listen(pubsub)` - Async iterator for messages
- `publish(channel, message)` - Broadcast event to subscribers
- `unsubscribe(channel)` - Close subscription

**Example Flow:**

1. Subscriber connects and listens on "example_events" channel
2. Publisher sends 3 motion detection events
3. Subscriber receives all 3 messages asynchronously
4. Subscriber unsubscribes and disconnects

**Real-World Usage:**

- Backend publishes new events to "security_events" channel
- WebSocket server subscribes and forwards to connected clients
- Frontend updates dashboard in real-time

### 3. Cache Operations (`example_cache_operations`)

**Use Case:** Temporary storage for frequently accessed data

**Operations Demonstrated:**

- `set(key, value, expire)` - Store data with TTL
- `get(key)` - Retrieve cached data
- `exists(key)` - Check if key exists
- `delete(key)` - Remove cached data

**Example Flow:**

1. Cache camera status with 300-second TTL
2. Retrieve cached status
3. Verify key exists
4. Delete key
5. Confirm deletion (returns None)

**Real-World Usage:**

- Cache camera online/offline status
- Store recent GPU metrics
- Temporary batch aggregation state

### 4. Health Check (`example_health_check`)

**Use Case:** Service monitoring and readiness probes

**Operations Demonstrated:**

- `health_check()` - Verify Redis connectivity and get server info

**Example Flow:**

1. Attempt health check before connection (expect RuntimeError)
2. Connect to Redis
3. Perform health check (returns status, connected, redis_version)
4. Disconnect

**Real-World Usage:**

- FastAPI health endpoint (`/api/system/health`)
- Docker container readiness checks
- Service startup validation

## Running the Examples

### Prerequisites

```bash
# Start Redis container
docker run -d -p 6379:6379 redis:7-alpine

# Activate Python virtual environment
source .venv/bin/activate

# Ensure dependencies are installed
pip install redis asyncio
```

### Execute Examples

```bash
# Run from project root
python -m backend.examples.redis_example

# Or with full path
python backend/examples/redis_example.py
```

### Expected Output

```
============================================================
Redis Client Examples for Home Security Intelligence System
============================================================

=== Health Check Example ===
1. Health check before connection:
   Expected error: Redis client not connected

2. Connecting to Redis...

3. Health check after connection:
   Status: healthy
   Connected: True
   Redis version: 7.x.x

=== Queue Operations Example ===
1. Adding detections to queue...
   Added detection 1, queue length: 1
   [...]

=== Cache Operations Example ===
[...]

=== Pub/Sub Example ===
[...]

============================================================
All examples completed successfully!
============================================================
```

## Integration with System Architecture

### Phase 4: AI Pipeline Integration

The Redis queue operations directly support the Phase 4 AI pipeline:

1. **File Watcher** - Pushes new image/video paths to `detection_queue`
2. **RT-DETRv2 Detector** - Pops images, runs inference, stores results
3. **Batch Aggregator** - Groups detections by camera and time window
4. **Nemotron Analyzer** - Analyzes batches and generates risk scores

### Phase 5: Real-time Updates

The pub/sub operations enable Phase 5 real-time features:

1. **Events API** - Publishes new events to `security_events` channel
2. **WebSocket Server** - Subscribes to Redis channels
3. **Frontend Dashboard** - Receives live updates via WebSocket

## Testing and Validation

These examples can be used as integration test templates:

```python
# Test queue operations
async def test_detection_queue_integration():
    """Validate file watcher -> detector queue flow."""
    client = RedisClient()
    await client.connect()

    # Simulate file watcher
    await client.add_to_queue("detection_queue", {
        "file_path": "/export/foscam/test/image.jpg",
        "camera_id": "test_camera",
        "media_type": "image"
    })

    # Simulate detector
    item = await client.get_from_queue("detection_queue", timeout=1)
    assert item["camera_id"] == "test_camera"
```

## Common Issues and Solutions

### Issue: "Connection refused"

**Cause:** Redis server not running
**Solution:**

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue: "Redis client not connected"

**Cause:** Called operations before `await client.connect()`
**Solution:** Always call `connect()` before any operations

### Issue: "BLPOP timeout"

**Cause:** Queue is empty and timeout exceeded
**Solution:** This is expected behavior; `get_from_queue()` returns `None` on timeout

## Related Documentation

- `/backend/core/redis.py` - RedisClient implementation
- `/backend/services/AGENTS.md` - Services using Redis (BatchAggregator, EventBroadcaster, etc.)
- `/docker-compose.yml` - Redis service configuration
