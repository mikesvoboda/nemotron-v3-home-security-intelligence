# Dependency Injection Patterns

**Guide to dependency injection patterns, container usage, and testing strategies for the Home Security Intelligence backend.**

This document explains the lightweight DI container introduced in NEM-1636, how to register and resolve services, and patterns for mocking dependencies in tests.

---

## Table of Contents

1. [Overview](#overview)
2. [Container Architecture](#container-architecture)
3. [Service Registration](#service-registration)
4. [Service Resolution](#service-resolution)
5. [FastAPI Integration](#fastapi-integration)
6. [Testing Patterns](#testing-patterns)
7. [Wire Services Function](#wire-services-function)
8. [Best Practices](#best-practices)
9. [Common Patterns](#common-patterns)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The backend uses a lightweight dependency injection container (`backend/core/container.py`) that provides:

- **Singleton services** - Created once, reused for all requests
- **Factory services** - New instance created on each request
- **Async service initialization** - Support for services requiring async setup
- **FastAPI `Depends()` integration** - Seamless injection into route handlers
- **Thread-safe concurrent access** - Safe for async concurrent operations
- **Service override for testing** - Easy mocking of dependencies
- **Graceful shutdown** - Automatic cleanup of services with `close()`/`disconnect()` methods

### Key Components

| Module                         | Purpose                                          |
| ------------------------------ | ------------------------------------------------ |
| `backend/core/container.py`    | DI container implementation                      |
| `backend/core/dependencies.py` | FastAPI dependency functions using the container |

### When to Use DI Container vs Direct Imports

| Use DI Container                                 | Use Direct Import              |
| ------------------------------------------------ | ------------------------------ |
| Services with async initialization (Redis, etc.) | Pure functions and utilities   |
| Services needing lifecycle management            | Stateless helpers              |
| Dependencies that need mocking in tests          | Constants and configuration    |
| Services with complex dependency graphs          | Simple factories without state |

---

## Container Architecture

### Container Class

The `Container` class is the core of the DI system:

```python
from backend.core.container import Container

container = Container()
```

**Key attributes:**

- `_registrations` - Dictionary of registered services
- `_overrides` - Dictionary of overridden services (for testing)
- `_resolution_stack` - Stack for circular dependency detection
- `_async_locks` - Per-service locks for thread-safe async initialization

### Global Container Singleton

The container is accessed via a global singleton pattern:

```python
from backend.core.container import get_container, reset_container

# Get the global container (creates one if needed)
container = get_container()

# Reset the container (useful for testing)
reset_container()
```

### Exceptions

| Exception                       | When Raised                                    |
| ------------------------------- | ---------------------------------------------- |
| `ServiceNotFoundError`          | Requested service is not registered            |
| `ServiceAlreadyRegisteredError` | Attempting to register a duplicate service     |
| `CircularDependencyError`       | Circular dependency detected during resolution |

---

## Service Registration

### Singleton Registration

Singleton services are created once on first access and reused:

```python
from backend.core.container import Container

container = Container()

# Option 1: Register a class (instantiated on first get())
class MyService:
    def do_work(self) -> str:
        return "done"

container.register_singleton("my_service", MyService)

# Option 2: Register a factory function
def create_service() -> MyService:
    service = MyService()
    service.configure()
    return service

container.register_singleton("my_service", create_service)
```

### Factory Registration

Factory services create a new instance on every access:

```python
container.register_factory("request_context", lambda: {"request_id": generate_id()})

# Each call returns a new instance
ctx1 = container.get("request_context")
ctx2 = container.get("request_context")
assert ctx1 is not ctx2
```

### Async Singleton Registration

For services requiring async initialization (database connections, etc.):

```python
from backend.core.redis import RedisClient

async def redis_factory() -> RedisClient:
    client = RedisClient()
    await client.connect()
    return client

container.register_async_singleton("redis_client", redis_factory)

# Must use get_async() to retrieve
redis = await container.get_async("redis_client")
```

### Services with Dependencies

Services can depend on other services by resolving them in their factory:

```python
class Repository:
    def __init__(self, redis: RedisClient) -> None:
        self.redis = redis

async def repository_factory() -> Repository:
    redis = await container.get_async("redis_client")
    return Repository(redis=redis)

container.register_async_singleton("repository", repository_factory)
```

---

## Service Resolution

### Synchronous Resolution

For services registered with `register_singleton()` or `register_factory()`:

```python
service = container.get("my_service")
```

### Asynchronous Resolution

For services registered with `register_async_singleton()`:

```python
service = await container.get_async("redis_client")
```

**Note:** Calling `get()` on an async service raises `RuntimeError`. Always use `get_async()` for async services.

### Checking Registered Services

```python
# List all registered service names
services = container.registered_services
# Returns: ["redis_client", "context_enricher", "detector_client", ...]
```

---

## FastAPI Integration

### Using Container Dependencies

The container provides a `get_dependency()` method that returns a FastAPI-compatible dependency:

```python
from fastapi import APIRouter, Depends
from backend.core.container import get_container

router = APIRouter()

container = get_container()

@router.get("/detections")
async def get_detections(
    redis = Depends(container.get_dependency("redis_client"))
):
    # redis is injected from the container
    await redis.publish("events", {"type": "detection"})
    return {"status": "ok"}
```

### Pre-built Dependency Functions

For convenience, `backend/core/dependencies.py` provides pre-built dependency functions:

```python
from fastapi import Depends
from backend.core.dependencies import (
    get_redis_dependency,
    get_detector_dependency,
    get_context_enricher_dependency,
    get_enrichment_pipeline_dependency,
    get_nemotron_analyzer_dependency,
)

@router.post("/analyze")
async def analyze(
    redis = Depends(get_redis_dependency),
    detector = Depends(get_detector_dependency),
):
    # Both services injected from container
    ...
```

### How get_dependency Works

The `get_dependency()` method returns an async generator function compatible with FastAPI's `Depends()`:

```python
def get_dependency(self, name: str) -> Callable[[], AsyncGenerator[Any]]:
    async def dependency() -> AsyncGenerator[Any]:
        registration = self._registrations.get(name)
        if registration is not None and registration.is_async:
            service = await self.get_async(name)
        else:
            service = self.get(name)
        yield service
    return dependency
```

### Combining with Other Dependencies

Container dependencies work alongside other FastAPI dependencies:

```python
from backend.core.database import get_db
from backend.core.dependencies import get_redis_dependency

@router.post("/events")
async def create_event(
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis_dependency),
    event_data: EventCreate,
):
    # db from get_db, redis from container
    ...
```

---

## Testing Patterns

### Service Override Mechanism

The container supports overriding services for testing:

```python
from backend.core.container import Container

container = Container()

class RealService:
    name = "real"

class MockService:
    name = "mock"

container.register_singleton("my_service", RealService)

# Before override
assert container.get("my_service").name == "real"

# Override with mock
container.override("my_service", MockService())

# After override - returns mock
assert container.get("my_service").name == "mock"
```

### Clearing Overrides

```python
# Clear a single override
container.clear_override("my_service")

# Clear all overrides
container.clear_all_overrides()
```

### Override Pattern in Tests

Always clean up overrides after tests:

```python
import pytest
from backend.core.container import Container

@pytest.fixture
def container_with_mock():
    container = Container()
    container.register_singleton("service", RealService)

    # Set override
    mock = MagicMock()
    container.override("service", mock)

    yield container, mock

    # Clean up
    container.clear_override("service")
```

### Using reset_container()

For complete isolation between tests:

```python
from backend.core.container import get_container, reset_container

@pytest.fixture(autouse=True)
def reset_global_container():
    reset_container()
    yield
    reset_container()
```

### FastAPI dependency_overrides

For API tests, use FastAPI's built-in `dependency_overrides`:

```python
from backend.main import app
from backend.core.database import get_db

@pytest.fixture
def client(app):
    # Save original overrides
    original = app.dependency_overrides.copy()

    async def mock_get_db():
        mock_session = AsyncMock()
        yield mock_session

    app.dependency_overrides[get_db] = mock_get_db

    yield TestClient(app)

    # Restore original
    app.dependency_overrides.clear()
    app.dependency_overrides.update(original)
```

### Mock Database Session Pattern

```python
from unittest.mock import AsyncMock, MagicMock

def create_mock_db_session():
    """Create a mock database session with common operations."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.rollback = AsyncMock()

    # Configure execute to return a result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    return session
```

### Mock Redis Client Pattern

```python
from unittest.mock import AsyncMock
from backend.core.redis import QueueAddResult

def create_mock_redis():
    """Create a mock Redis client with common operations."""
    mock = AsyncMock()

    # Basic operations
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.publish.return_value = 1

    # Queue operations
    mock.add_to_queue_safe.return_value = QueueAddResult(success=True, queue_length=1)

    # Health check
    mock.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    return mock
```

### Mock External Service Pattern

```python
def create_mock_detector():
    """Create a mock detector client."""
    mock = AsyncMock()
    mock.detect_objects.return_value = [
        {"label": "person", "confidence": 0.95, "bbox": [100, 200, 300, 400]}
    ]
    mock.health_check.return_value = True
    return mock
```

### Integration Test with Container Override

```python
@pytest.mark.asyncio
async def test_service_integration():
    container = Container()

    # Register real services
    container.register_singleton("database", Database)
    container.register_singleton(
        "repository",
        lambda: Repository(container.get("database"))
    )

    # Override database for testing
    mock_db = MagicMock()
    mock_db.query.return_value = [{"id": 1, "name": "test"}]
    container.override("database", mock_db)

    # Test with mocked dependency
    repo = container.get("repository")
    result = repo.get_all()

    assert len(result) == 1
    mock_db.query.assert_called_once()
```

---

## Wire Services Function

The `wire_services()` function registers all application services in the correct order:

```python
from backend.core.container import get_container, wire_services

container = get_container()
await wire_services(container)
```

### Services Wired

| Service Name          | Type            | Dependencies                                              |
| --------------------- | --------------- | --------------------------------------------------------- |
| `redis_client`        | async singleton | None (requires `connect()`)                               |
| `context_enricher`    | sync singleton  | None                                                      |
| `enrichment_pipeline` | async singleton | `redis_client`                                            |
| `nemotron_analyzer`   | async singleton | `redis_client`, `context_enricher`, `enrichment_pipeline` |
| `detector_client`     | sync singleton  | None                                                      |

### Application Startup

In `main.py`, services are wired during the lifespan startup:

```python
from contextlib import asynccontextmanager
from backend.core.container import get_container, wire_services

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    container = get_container()
    await wire_services(container)

    yield

    # Shutdown
    await container.shutdown()
```

---

## Best Practices

### 1. Use Async Registration for Services with Async Init

```python
# Good: Async service uses async registration
async def redis_factory():
    client = RedisClient()
    await client.connect()
    return client

container.register_async_singleton("redis", redis_factory)

# Bad: Forcing async into sync
def bad_redis_factory():
    client = RedisClient()
    asyncio.run(client.connect())  # Don't do this!
    return client
```

### 2. Declare Dependencies in Factory Functions

```python
# Good: Dependencies declared in factory
async def analyzer_factory():
    redis = await container.get_async("redis_client")
    enricher = container.get("context_enricher")
    return NemotronAnalyzer(redis=redis, enricher=enricher)

# Bad: Hidden dependencies
class BadAnalyzer:
    def __init__(self):
        self.redis = get_container().get("redis_client")  # Hidden!
```

### 3. Always Clean Up Overrides in Tests

```python
# Good: Using try/finally
try:
    container.override("service", mock)
    # Test code
finally:
    container.clear_override("service")

# Good: Using pytest fixture
@pytest.fixture
def mocked_container():
    container = Container()
    container.override("service", mock)
    yield container
    container.clear_all_overrides()
```

### 4. Use reset_container() for Test Isolation

```python
@pytest.fixture(autouse=True)
def isolate_container():
    """Reset container before and after each test."""
    reset_container()
    yield
    reset_container()
```

### 5. Prefer Pre-built Dependencies

```python
# Good: Use pre-built dependencies
from backend.core.dependencies import get_redis_dependency

@router.get("/")
async def endpoint(redis = Depends(get_redis_dependency)):
    ...

# Acceptable: Custom dependency for special cases
@router.get("/")
async def endpoint(redis = Depends(get_container().get_dependency("redis_client"))):
    ...
```

---

## Common Patterns

### Pattern: Service with Configuration

```python
from backend.core.config import get_settings

class ConfiguredService:
    def __init__(self, timeout: int, retries: int):
        self.timeout = timeout
        self.retries = retries

def service_factory():
    settings = get_settings()
    return ConfiguredService(
        timeout=settings.service_timeout,
        retries=settings.service_retries,
    )

container.register_singleton("configured_service", service_factory)
```

### Pattern: Conditional Service Registration

```python
from backend.core.config import get_settings

async def wire_services(container: Container):
    settings = get_settings()

    if settings.cache_enabled:
        container.register_singleton("cache", RedisCache)
    else:
        container.register_singleton("cache", NoOpCache)
```

### Pattern: Service with Cleanup

```python
class ServiceWithCleanup:
    async def close(self):
        # Cleanup resources
        await self.connection.close()

async def factory():
    service = ServiceWithCleanup()
    await service.connect()
    return service

container.register_async_singleton("service", factory)

# shutdown() automatically calls close() on services
await container.shutdown()
```

### Pattern: Testing Dependency Chains

```python
def test_dependency_chain():
    container = Container()

    # Register chain: A -> B -> C
    container.register_singleton("c", ServiceC)
    container.register_singleton("b", lambda: ServiceB(container.get("c")))
    container.register_singleton("a", lambda: ServiceA(container.get("b")))

    # Override middle of chain
    mock_b = MagicMock()
    container.override("b", mock_b)

    # Clear cached instance of A to force re-resolution
    container._registrations["a"].instance = None

    # A now uses mocked B
    a = container.get("a")
    assert a.b is mock_b
```

---

## Troubleshooting

### "Service not found" Error

**Cause:** Service not registered or wrong name used.

**Fix:**

```python
# Check registered services
print(container.registered_services)

# Ensure service is registered before use
container.register_singleton("my_service", MyService)
```

### "RuntimeError: Service is async"

**Cause:** Using `get()` for an async service.

**Fix:**

```python
# Wrong
service = container.get("redis_client")

# Correct
service = await container.get_async("redis_client")
```

### Circular Dependency Error

**Cause:** Services depend on each other in a cycle.

**Fix:** Refactor to break the cycle or use lazy resolution:

```python
# Instead of direct resolution in constructor
class ServiceA:
    def __init__(self):
        self.b = None  # Lazy

    def get_b(self):
        if self.b is None:
            self.b = get_container().get("service_b")
        return self.b
```

### Override Not Working

**Cause:** Override set after service already resolved.

**Fix:** Set override before first resolution:

```python
# Wrong order
service = container.get("service")  # Already cached!
container.override("service", mock)  # Too late

# Correct order
container.override("service", mock)
service = container.get("service")  # Returns mock
```

### Test Pollution Between Tests

**Cause:** Overrides or container state not cleaned up.

**Fix:** Use `reset_container()` or `clear_all_overrides()`:

```python
@pytest.fixture(autouse=True)
def clean_container():
    reset_container()
    yield
    reset_container()
```

---

## Related Documentation

- `/backend/core/container.py` - Container implementation
- `/backend/core/dependencies.py` - FastAPI dependency functions
- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/docs/TESTING_GUIDE.md` - Testing patterns and fixtures
- `/backend/tests/unit/core/test_container.py` - Container unit tests
- `/backend/tests/integration/test_di_container_overrides.py` - Integration tests

---

## Summary

The DI container provides a lightweight but powerful dependency injection system:

1. **Register services** using `register_singleton()`, `register_factory()`, or `register_async_singleton()`
2. **Resolve services** using `get()` or `get_async()`
3. **Integrate with FastAPI** using `get_dependency()` or pre-built dependencies from `dependencies.py`
4. **Test with overrides** using `override()` and `clear_override()`
5. **Clean up** by calling `shutdown()` during application teardown

The container is designed to be simple yet effective, avoiding the complexity of full-featured DI frameworks while providing the essential features needed for clean, testable code.
