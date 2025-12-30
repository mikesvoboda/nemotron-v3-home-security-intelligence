# Redis Quick Start Guide

## Setup

### 1. Start Redis Server

```bash
# Using Docker (recommended)
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Or using Docker Compose (add to docker-compose.yml)
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

### 2. Configure Connection

```bash
# .env file
REDIS_URL=redis://localhost:6379/0
```

## Basic Usage

### In FastAPI Routes

```python
from fastapi import APIRouter, Depends
from backend.core.redis import RedisClient, get_redis

router = APIRouter()

@router.post("/detections")
async def queue_detection(
    detection: dict,
    redis: RedisClient = Depends(get_redis)
):
    """Add detection to processing queue with proper backpressure handling."""
    from backend.core.redis import QueueOverflowPolicy

    result = await redis.add_to_queue_safe(
        "detections_queue",
        detection,
        overflow_policy=QueueOverflowPolicy.DLQ,  # Preserve data in dead-letter queue
    )
    if not result.success:
        return {"status": "rejected", "error": result.error}
    return {"status": "queued", "queue_length": result.queue_length}

@router.get("/detections/next")
async def get_next_detection(
    redis: RedisClient = Depends(get_redis)
):
    """Get next detection from queue."""
    detection = await redis.get_from_queue("detections_queue", timeout=5)
    if not detection:
        return {"status": "empty"}
    return detection
```

### Queue Operations

```python
from backend.core.redis import QueueOverflowPolicy

# Add items to queue with proper overflow handling (recommended)
result = await redis.add_to_queue_safe(
    "my_queue",
    {"data": "value"},
    overflow_policy=QueueOverflowPolicy.DLQ,  # Moves overflow to dead-letter queue
)
print(f"Success: {result.success}, Queue length: {result.queue_length}")

# Available overflow policies:
# - QueueOverflowPolicy.REJECT: Return error when full (safest)
# - QueueOverflowPolicy.DLQ: Move oldest to dead-letter queue (preserves all data)
# - QueueOverflowPolicy.DROP_OLDEST: Trim oldest with warning (for telemetry)

# Get items from queue (blocking with timeout)
item = await redis.get_from_queue("my_queue", timeout=10)

# Check queue length
length = await redis.get_queue_length("my_queue")

# Check queue pressure (useful for monitoring)
pressure = await redis.get_queue_pressure("my_queue")
print(f"Fill ratio: {pressure.fill_ratio:.1%}, Is full: {pressure.is_full}")

# Peek without removing
items = await redis.peek_queue("my_queue", start=0, end=9)

# Clear queue
await redis.clear_queue("my_queue")
```

### Pub/Sub for Real-time Updates

```python
# Publisher (in your API route)
await redis.publish("camera_events", {
    "type": "motion_detected",
    "camera_id": 1,
    "timestamp": datetime.now().isoformat()
})

# Subscriber (in background task or WebSocket)
pubsub = await redis.subscribe("camera_events", "system_alerts")

async for message in redis.listen(pubsub):
    event_type = message["data"]["type"]
    camera_id = message["data"]["camera_id"]
    # Broadcast to WebSocket clients...
    await websocket_manager.broadcast(message["data"])
```

### Cache Operations

```python
# Cache with TTL
await redis.set("camera:1:status", {
    "online": True,
    "fps": 30
}, expire=300)  # 5 minutes

# Get from cache
status = await redis.get("camera:1:status")

# Check existence
if await redis.exists("camera:1:status"):
    print("Cache hit!")

# Delete
await redis.delete("camera:1:status")
```

## Common Patterns

### Pattern 1: Batch Processing Queue

```python
from backend.core.redis import QueueOverflowPolicy

# Producer: Add images to processing queue with backpressure
async def on_new_image(image_path: str, camera_id: int):
    result = await redis.add_to_queue_safe(
        "images_to_process",
        {
            "image_path": image_path,
            "camera_id": camera_id,
            "timestamp": datetime.now().isoformat()
        },
        overflow_policy=QueueOverflowPolicy.DLQ,  # Preserve all data
    )
    if not result.success:
        logger.error(f"Failed to queue image: {result.error}")

# Consumer: Process images in batches
async def process_image_queue():
    batch = []
    while True:
        # Get with 30-second idle timeout
        image = await redis.get_from_queue("images_to_process", timeout=30)

        if image:
            batch.append(image)

            # Process batch when reaching size or timeout
            if len(batch) >= 10:
                await process_batch(batch)
                batch = []
        elif batch:
            # Timeout - process partial batch
            await process_batch(batch)
            batch = []
```

### Pattern 2: Event Broadcasting

```python
# WebSocket manager with Redis Pub/Sub
class WebSocketManager:
    def __init__(self):
        self.active_connections = []
        self.redis = None

    async def start(self):
        self.redis = RedisClient()
        await self.redis.connect()

        # Subscribe to events
        pubsub = await self.redis.subscribe(
            "camera_events",
            "risk_alerts",
            "system_status"
        )

        # Listen and broadcast
        asyncio.create_task(self._listen_and_broadcast(pubsub))

    async def _listen_and_broadcast(self, pubsub):
        async for message in self.redis.listen(pubsub):
            await self.broadcast(message["data"])

    async def broadcast(self, data: dict):
        for connection in self.active_connections:
            await connection.send_json(data)
```

### Pattern 3: Result Caching

```python
# Cache expensive API results
async def get_camera_detections(camera_id: int, redis: RedisClient):
    cache_key = f"detections:camera:{camera_id}:recent"

    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return cached

    # Fetch from database
    detections = await fetch_from_db(camera_id)

    # Cache for 60 seconds
    await redis.set(cache_key, detections, expire=60)

    return detections
```

### Pattern 4: Distributed Locking

```python
# Ensure only one worker processes a camera at a time
async def process_camera_with_lock(camera_id: int, redis: RedisClient):
    lock_key = f"lock:camera:{camera_id}"

    # Try to acquire lock (set with NX flag)
    locked = await redis._ensure_connected().set(
        lock_key,
        "processing",
        nx=True,  # Only set if doesn't exist
        ex=300    # Auto-release after 5 minutes
    )

    if not locked:
        return {"status": "already_processing"}

    try:
        # Process camera...
        result = await process_camera(camera_id)
        return result
    finally:
        # Release lock
        await redis.delete(lock_key)
```

## Testing

### Unit Tests with Mocking

```python
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_my_route(mock_redis_client):
    with patch("backend.core.redis.Redis", return_value=mock_redis_client):
        # Your test here
        pass
```

### Integration Tests with Real Redis

```python
from backend.core.redis import QueueOverflowPolicy

@pytest.mark.skipif(
    os.environ.get("REDIS_URL") is None,
    reason="Redis not available"
)
@pytest.mark.asyncio
async def test_with_real_redis():
    redis = RedisClient("redis://localhost:6379/15")
    await redis.connect()

    try:
        # Test operations with proper overflow handling
        result = await redis.add_to_queue_safe(
            "test_queue",
            {"test": "data"},
            overflow_policy=QueueOverflowPolicy.REJECT,
        )
        assert result.success
        item = await redis.get_from_queue("test_queue", timeout=1)
        assert item["test"] == "data"
    finally:
        await redis.disconnect()
```

## Monitoring

### Check Redis Health

```bash
curl http://localhost:8000/health
```

### Redis CLI

```bash
# Connect to Redis
docker exec -it redis redis-cli

# Check queue length
LLEN detections_queue

# View queue items
LRANGE detections_queue 0 -1

# Check pub/sub channels
PUBSUB CHANNELS

# Monitor all commands
MONITOR

# Get info
INFO
```

## Troubleshooting

### Redis Not Connecting

```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs redis

# Test connection
redis-cli ping

# Check port
netstat -an | grep 6379
```

### Queue Growing Too Large

```python
# Monitor queue length
length = await redis.get_queue_length("my_queue")
if length > 1000:
    logger.warning(f"Queue growing large: {length}")

# Clear old items if needed
await redis.clear_queue("old_queue")
```

### Memory Usage

```bash
# Check Redis memory
redis-cli INFO memory

# Set max memory limit
redis-cli CONFIG SET maxmemory 256mb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## Best Practices

1. **Always use dependency injection** in FastAPI routes
2. **Set appropriate TTLs** on cached data
3. **Monitor queue lengths** to prevent backlog
4. **Use Pub/Sub for broadcasts**, not queues
5. **Handle connection failures** gracefully
6. **Clean up resources** in finally blocks
7. **Use separate DB indexes** for different environments (dev=1, test=15, prod=0)
8. **Log important operations** for debugging
9. **Use add_to_queue_safe()** instead of deprecated add_to_queue() for proper backpressure:
   - Use `QueueOverflowPolicy.REJECT` for critical data (caller handles retry)
   - Use `QueueOverflowPolicy.DLQ` to preserve all data in dead-letter queue
   - Use `QueueOverflowPolicy.DROP_OLDEST` only for telemetry that can tolerate loss

## Performance Tips

1. **Pipeline commands** when possible
2. **Use connection pooling** (enabled by default)
3. **Avoid large values** in queues (store references instead)
4. **Set reasonable TTLs** on all cache entries
5. **Use appropriate data structures** (Lists for queues, Hashes for objects)

## Security

1. **Use Redis password** in production:

   ```bash
   REDIS_URL=redis://:password@localhost:6379/0
   ```

2. **Bind to localhost** if not needed externally:

   ```bash
   redis-server --bind 127.0.0.1
   ```

3. **Use SSL/TLS** for remote connections:
   ```bash
   REDIS_URL=rediss://user:password@redis-server:6380/0
   ```

## Resources

- **Full Documentation**: `/backend/core/README_REDIS.md`
- **Examples**: `/backend/examples/redis_example.py`
- **Tests**: `/backend/tests/unit/test_redis.py`
- **Redis Documentation**: https://redis.io/docs/
- **redis-py Documentation**: https://redis-py.readthedocs.io/
