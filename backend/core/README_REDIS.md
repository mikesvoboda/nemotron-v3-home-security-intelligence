# Redis Connection Module

This module provides async Redis connection management and operations for the home security intelligence system.

## Features

- **Async Redis Client**: Built on `redis-py` with `redis.asyncio`
- **Connection Pooling**: Automatic connection pool management with configurable limits
- **Retry Logic**: Graceful connection handling with automatic retries
- **Queue Operations**: FIFO queue operations for batch processing
- **Pub/Sub Support**: Real-time message publishing and subscription
- **Cache Operations**: Key-value storage with optional TTL
- **Health Checks**: Built-in health monitoring
- **FastAPI Integration**: Dependency injection for route handlers

## Configuration

Redis settings are configured in `backend/core/config.py`:

```python
redis_url: str = "redis://localhost:6379/0"  # Redis connection URL
```

Or via environment variables:

```bash
REDIS_URL=redis://localhost:6379/0
```

## Usage

### Basic Connection

```python
from backend.core.redis import RedisClient

# Create client
client = RedisClient()

# Connect
await client.connect()

# Use client...

# Disconnect
await client.disconnect()
```

### FastAPI Dependency Injection

```python
from fastapi import APIRouter, Depends
from backend.core.redis import RedisClient, get_redis

router = APIRouter()

@router.post("/events")
async def create_event(
    event: Event,
    redis: RedisClient = Depends(get_redis)
):
    # Add event to processing queue
    await redis.add_to_queue("events_queue", event.dict())
    return {"status": "queued"}
```

### Application Startup/Shutdown

```python
from fastapi import FastAPI
from backend.core.redis import init_redis, close_redis

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_redis()

@app.on_event("shutdown")
async def shutdown():
    await close_redis()
```

## Queue Operations

### Add to Queue

```python
# Add dictionary (auto-serialized to JSON)
await redis.add_to_queue("detections", {
    "camera_id": 1,
    "timestamp": "2024-01-01T12:00:00",
    "objects": ["person", "car"]
})

# Add string
await redis.add_to_queue("logs", "System started")
```

### Get from Queue

```python
# Blocking get with timeout
item = await redis.get_from_queue("detections", timeout=5)
if item:
    process_detection(item)

# Non-blocking get (returns immediately)
item = await redis.get_from_queue("detections", timeout=0)
```

### Queue Management

```python
# Get queue length
length = await redis.get_queue_length("detections")

# Peek at items without removing
items = await redis.peek_queue("detections", start=0, end=9)  # First 10 items

# Clear queue
await redis.clear_queue("detections")
```

## Pub/Sub Operations

### Publishing Messages

```python
# Publish event (auto-serialized to JSON)
await redis.publish("camera_events", {
    "type": "motion_detected",
    "camera_id": 1,
    "timestamp": "2024-01-01T12:00:00"
})
```

### Subscribing to Channels

```python
# Subscribe to channels
pubsub = await redis.subscribe("camera_events", "system_alerts")

# Listen for messages
async for message in redis.listen(pubsub):
    print(f"Received: {message['data']} on {message['channel']}")

# Unsubscribe when done
await redis.unsubscribe("camera_events")
```

## Cache Operations

### Basic Cache

```python
# Set value with optional expiration (seconds)
await redis.set("camera:1:status", {"online": True}, expire=300)

# Get value
status = await redis.get("camera:1:status")

# Check if key exists
exists = await redis.exists("camera:1:status")

# Delete keys
await redis.delete("camera:1:status", "camera:2:status")
```

## Health Checks

```python
health = await redis.health_check()
# Returns:
# {
#     "status": "healthy",
#     "connected": True,
#     "redis_version": "7.0.0"
# }
```

## Error Handling

The module handles common Redis errors gracefully:

- **ConnectionError**: Automatic retry with exponential backoff
- **TimeoutError**: Retries connection attempts
- **RuntimeError**: Raised when operations attempted before connection

```python
from redis.exceptions import ConnectionError

try:
    await client.connect()
except ConnectionError:
    logger.error("Failed to connect to Redis after retries")
    # Handle gracefully (fallback to in-memory, etc.)
```

## Testing

### Unit Tests

Run unit tests with mocked Redis:

```bash
pytest backend/tests/unit/test_redis.py -v
```

### Integration Tests

Run integration tests with real Redis:

```bash
# Set Redis URL for integration tests
export REDIS_URL=redis://localhost:6379/15

# Run tests
pytest backend/tests/unit/test_redis.py -v
```

Integration tests are automatically skipped if `REDIS_URL` is not set.

## Architecture

### Connection Management

- **Connection Pool**: Reuses connections for better performance
- **Health Checks**: Automatic health checks every 30 seconds
- **Socket Keepalive**: Maintains long-lived connections
- **Graceful Shutdown**: Proper cleanup of resources

### Queue Design

Queues are implemented using Redis Lists:
- `RPUSH`: Add to end of queue
- `BLPOP`: Blocking pop from front (FIFO)
- `LLEN`: Get queue length
- `LRANGE`: Peek at items

### Pub/Sub Design

Real-time messaging using Redis Pub/Sub:
- Publishers use `PUBLISH` command
- Subscribers use `SUBSCRIBE` command
- Messages are fire-and-forget (not persisted)

### Serialization

- All non-string values are automatically JSON-serialized
- Retrieved values are automatically deserialized
- Plain strings are handled as-is

## Best Practices

1. **Always use dependency injection** in FastAPI routes
2. **Use queues for batch processing** to buffer high-volume events
3. **Use Pub/Sub for real-time updates** to frontend WebSockets
4. **Set appropriate TTLs** on cache entries to prevent memory bloat
5. **Handle connection failures gracefully** with fallback behavior
6. **Close connections** properly during application shutdown

## Examples

### Detection Processing Queue

```python
# Producer: Add detection to queue
await redis.add_to_queue("detections", {
    "camera_id": 1,
    "image_path": "/data/image.jpg",
    "timestamp": "2024-01-01T12:00:00"
})

# Consumer: Process detections in batch
async def process_detections():
    while True:
        detection = await redis.get_from_queue("detections", timeout=30)
        if detection:
            await run_object_detection(detection)
```

### Real-time Event Broadcasting

```python
# Publish event to all connected WebSocket clients
await redis.publish("events", {
    "type": "risk_alert",
    "risk_score": 85,
    "camera_id": 1,
    "message": "Suspicious activity detected"
})
```

### Camera Status Cache

```python
# Cache camera status for 5 minutes
await redis.set(
    f"camera:{camera_id}:status",
    {"online": True, "fps": 30},
    expire=300
)

# Get cached status
status = await redis.get(f"camera:{camera_id}:status")
```
