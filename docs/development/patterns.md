---
title: Code Patterns and Conventions
source_refs:
  - backend/core/config.py:1
  - backend/core/database.py:1
  - backend/core/redis.py:1
  - backend/services/AGENTS.md:1
  - backend/tests/unit/AGENTS.md:157
  - backend/tests/integration/AGENTS.md:76
  - frontend/src/hooks/AGENTS.md:1
---

# Code Patterns and Conventions

This document covers key patterns used throughout the codebase. Understanding these patterns will help you write consistent, maintainable code.

## Backend Patterns

### Settings Management

The application uses a cached singleton pattern for settings ([backend/core/config.py](../../backend/core/config.py:1)):

```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
```

**Usage:**

```python
from backend.core import get_settings

settings = get_settings()  # Cached, same instance every time
print(settings.database_url)
```

**Testing pattern - clear cache:**

```python
from backend.core.config import get_settings

def test_something():
    get_settings.cache_clear()  # Force reload
    # ... test code ...
```

### Database Sessions

#### Dependency Injection (API Routes)

Use FastAPI's dependency injection for API routes ([backend/core/database.py](../../backend/core/database.py:1)):

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db

@router.get("/cameras")
async def list_cameras(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera))
    return result.scalars().all()
```

#### Context Manager (Services)

Use context managers in services for proper cleanup:

```python
from backend.core.database import get_session

async def process_detections():
    async with get_session() as session:
        result = await session.execute(select(Detection))
        detections = result.scalars().all()
        # Auto-commit on success, rollback on exception
```

### Async/Await Patterns

**All I/O operations must be async:**

```python
# Database operations
async with get_session() as session:
    result = await session.execute(query)
    await session.commit()

# Redis operations
await redis.set("key", value)
result = await redis.get("key")

# HTTP operations
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)

# File watching (asyncio for debouncing)
async def debounced_handler():
    await asyncio.sleep(0.1)
    await process_file()
```

**Concurrent operations:**

```python
import asyncio

# Run multiple independent operations concurrently
results = await asyncio.gather(
    fetch_cameras(session),
    fetch_events(session),
    fetch_detections(session),
)
```

### Error Handling

#### Service Layer

```python
from backend.core.logging import get_logger

logger = get_logger(__name__)

async def detect_objects(image_path: str) -> list[Detection]:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={"image": image_path})
            response.raise_for_status()
            return parse_detections(response.json())
    except httpx.HTTPStatusError as e:
        logger.error("Detection failed", extra={
            "status_code": e.response.status_code,
            "image_path": image_path,
        })
        return []  # Graceful degradation
    except Exception as e:
        logger.exception("Unexpected error during detection")
        raise
```

#### API Routes

```python
from fastapi import HTTPException, status

@router.get("/cameras/{camera_id}")
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found"
        )

    return camera
```

### Type Hints

**All public functions must have type hints:**

```python
from typing import Optional
from datetime import datetime

async def get_events(
    camera_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Event]:
    """Fetch events with optional filtering."""
    ...
```

**SQLAlchemy 2.0 Mapped types:**

```python
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="online")

    detections: Mapped[list["Detection"]] = relationship(back_populates="camera")
```

### Redis Patterns

#### Queue Operations with Backpressure

```python
from backend.core.redis import RedisClient, OverflowPolicy

async def add_detection_to_queue(redis: RedisClient, detection: dict):
    success = await redis.add_to_queue_safe(
        queue_name="detection_queue",
        data=detection,
        max_size=1000,
        overflow_policy=OverflowPolicy.DLQ,  # Send to dead-letter queue on overflow
    )
    if not success:
        logger.warning("Queue full, detection sent to DLQ")
```

#### Pub/Sub Pattern

```python
# Publisher
await redis.publish("events", {"type": "new_event", "event_id": event.id})

# Subscriber
async for message in redis.listen("events"):
    await handle_event(message)
```

## Frontend Patterns

### Functional Components

All components use functional components with hooks:

```tsx
import { useState, useEffect } from 'react';
import { Camera } from '../types/api';
import { api } from '../services/api';

interface CameraCardProps {
  camera: Camera;
  onSelect: (camera: Camera) => void;
}

export function CameraCard({ camera, onSelect }: CameraCardProps) {
  const [status, setStatus] = useState(camera.status);

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      // Cancel subscriptions
    };
  }, [camera.id]);

  return (
    <div onClick={() => onSelect(camera)}>
      <h3>{camera.name}</h3>
      <span>{status}</span>
    </div>
  );
}
```

### Custom Hooks

Extract reusable logic into custom hooks:

```tsx
// useWebSocket.ts
export function useWebSocket(channel: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/${channel}`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      setMessages((prev) => [...prev, JSON.parse(event.data)]);
    };

    return () => ws.close();
  }, [channel]);

  return { messages, connected };
}

// Usage
function EventFeed() {
  const { messages, connected } = useWebSocket('events');
  // ...
}
```

### Tailwind CSS Patterns

Use design system classes consistently:

```tsx
// Use semantic color classes
<div className="bg-background-primary text-text-primary">
  <button className="bg-nvidia-green hover:bg-nvidia-green-dark">
    Action
  </button>
</div>

// Responsive design
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Grid items */}
</div>

// Component composition
<Card>
  <CardHeader>Title</CardHeader>
  <CardContent>Content</CardContent>
</Card>
```

## Testing Patterns

### Mocking at Boundaries

Mock at the boundary, not internal functions:

```python
# GOOD: Mock at boundary
with patch("httpx.AsyncClient") as mock_http:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http.return_value.__aenter__.return_value = mock_client
    # Test code...

# BAD: Mock internal function (tests implementation, not behavior)
with patch("backend.services.detector_client._parse_response"):
    # Too granular
```

### Redis Mocking Pattern

```python
@pytest.fixture
def mock_redis_client():
    mock_client = AsyncMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.add_to_queue = AsyncMock()
    mock_client.publish = AsyncMock()
    mock_client.health_check = AsyncMock(return_value={"status": "healthy"})
    return mock_client
```

### HTTP Client Mocking Pattern

```python
@pytest.fixture
def mock_http_client():
    with patch("httpx.AsyncClient") as mock_http:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.get = AsyncMock(return_value=mock_response)

        mock_http.return_value.__aenter__.return_value = mock_client
        yield mock_client
```

### Database Session Mocking

```python
@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session
```

### Integration Test Patterns

```python
@pytest.mark.asyncio
async def test_full_workflow(client, integration_db):
    """Test complete camera -> detection -> event workflow."""
    # Create camera
    response = await client.post("/api/cameras", json={
        "id": "test_cam",
        "name": "Test Camera"
    })
    assert response.status_code == 201

    # Trigger detection
    response = await client.post("/api/detections", json={
        "camera_id": "test_cam",
        "image_path": "/path/to/image.jpg",
        "objects": [{"class": "person", "confidence": 0.95}]
    })
    assert response.status_code == 201

    # Verify event created
    response = await client.get("/api/events?camera_id=test_cam")
    assert response.status_code == 200
    assert len(response.json()["events"]) > 0
```

### Parallel Test Isolation

Use `unique_id()` for test data to avoid conflicts:

```python
from backend.tests.conftest import unique_id

@pytest.mark.asyncio
async def test_camera_creation(isolated_db):
    camera_id = unique_id("camera")  # e.g., "camera_abc12345"

    async with get_session() as session:
        camera = Camera(id=camera_id, name="Test Camera")
        session.add(camera)
        await session.commit()

        # Query uses unique ID, no conflicts with parallel tests
        result = await session.execute(
            select(Camera).where(Camera.id == camera_id)
        )
        assert result.scalar_one().name == "Test Camera"
```

## Logging Patterns

### Structured Logging

```python
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Include structured context
logger.info("Processing detection", extra={
    "camera_id": camera.id,
    "detection_id": detection.id,
    "confidence": detection.confidence,
    "duration_ms": elapsed_ms,
})

# Error with exception
try:
    await process()
except Exception:
    logger.exception("Processing failed", extra={
        "camera_id": camera.id,
    })
```

### Request ID Propagation

Request IDs are automatically propagated via middleware:

```python
# In API routes, request_id is in request state
@router.get("/cameras")
async def list_cameras(request: Request):
    request_id = request.state.request_id
    logger.info("Listing cameras", extra={"request_id": request_id})
```

## Service Architecture Patterns

### Worker Pattern

Background workers follow this pattern:

```python
class DetectionQueueWorker:
    def __init__(self, redis: RedisClient):
        self.redis = redis
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        while self._running:
            try:
                item = await self.redis.pop_from_queue("detection_queue", timeout=1)
                if item:
                    await self._process(item)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker error")
                await asyncio.sleep(1)  # Back off on error
```

### Circuit Breaker Pattern

```python
from backend.services.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30,
    half_open_max_calls=3,
)

async def call_external_service():
    async with breaker:
        return await external_api.call()
```

### Retry Pattern

```python
from backend.services.retry_handler import RetryHandler

retry = RetryHandler(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2,
)

async def unreliable_operation():
    return await retry.execute(
        operation=lambda: external_api.call(),
        on_retry=lambda attempt, error: logger.warning(f"Retry {attempt}: {error}"),
    )
```

## Related Documentation

- [Setup Guide](setup.md) - Development environment setup
- [Testing Guide](testing.md) - Test strategy and running tests
- [Contributing Guide](contributing.md) - PR process and code standards
- [Backend AGENTS.md](../../backend/AGENTS.md) - Backend architecture
- [Services AGENTS.md](../../backend/services/AGENTS.md) - Service layer patterns
