# Integration Testing

Integration tests verify multi-component workflows with real database connections. They ensure that services, repositories, and APIs work together correctly.

## Overview

Integration tests form the middle layer of the test pyramid (~15% of tests). They:

- Test multi-component interactions
- Use real PostgreSQL database
- Use mocked Redis (worker-isolated)
- Support parallel execution with worker-isolated databases

**Location**: `backend/tests/integration/` (109+ test files)

## Test Organization

### Directory Structure

```
backend/tests/integration/
  conftest.py             # Integration-specific fixtures
  repositories/           # Repository pattern tests (4 files)
  test_admin_*.py         # Admin API tests
  test_alerts_*.py        # Alert system tests
  test_analytics_*.py     # Analytics API tests
  test_cameras_*.py       # Camera management tests
  test_events_*.py        # Event processing tests
  test_websocket_*.py     # WebSocket tests
  test_pipeline_*.py      # AI pipeline tests
  ...
```

### Test Categories

| Category        | Files | Description                                      |
| --------------- | ----- | ------------------------------------------------ |
| API endpoints   | 24    | Admin, alerts, analytics, cameras, events, etc.  |
| WebSocket       | 4     | Connection handling, broadcasting, cleanup       |
| Services        | 14    | Batch aggregation, detector client, orchestrator |
| Models/Database | 10    | Alert models, cascades, partitions               |
| Error Handling  | 6     | API errors, transaction rollback                 |
| Pipeline        | 5     | Circuit breaker, enrichment, E2E                 |

## Parallel Execution

Integration tests support parallel execution via pytest-xdist with worker-isolated databases.

### How It Works

From `backend/tests/integration/conftest.py:248-268`:

```python
def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Get the pytest-xdist worker ID ('gw0', 'gw1', etc.) or 'master'."""
    return xdist.get_xdist_worker_id(request)

def get_worker_db_name(worker_id: str) -> str:
    """Generate a unique database name for the xdist worker.

    Args:
        worker_id: The xdist worker ID ('gw0', 'gw1', 'master')

    Returns:
        Database name like 'security_test_gw0' or 'security_test' for master
    """
    if worker_id == "master":
        return "security_test"
    return f"security_test_{worker_id}"
```

Each worker creates its own database:

- `gw0` -> `security_test_gw0`
- `gw1` -> `security_test_gw1`
- `gw2` -> `security_test_gw2`
- etc.

### Running Parallel Tests

```bash
# Parallel with 8 workers (recommended)
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

# Serial execution (legacy, slower)
uv run pytest backend/tests/integration/ -n0

# Performance comparison
# Serial: ~169s for 1575 tests
# 8 workers: ~33s (5.1x speedup)
```

## Fixtures

### Integration-Specific Fixtures (`backend/tests/integration/conftest.py`)

#### PostgreSQL Container

From `backend/tests/integration/conftest.py:313-349`:

```python
@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer | LocalPostgresService]:
    """Provide a session-scoped PostgreSQL service.

    Uses local PostgreSQL if available (development with Podman),
    otherwise starts a testcontainer for full isolation.
    """
    # Check for explicit environment variable override
    if os.environ.get("TEST_DATABASE_URL"):
        yield LocalPostgresService()
        return

    # Check for local PostgreSQL (development environment)
    if _check_local_postgres():
        yield LocalPostgresService()
        return

    # Fall back to testcontainer
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(
        "postgres:16-alpine",
        username="postgres",
        password="postgres",  # pragma: allowlist secret
        dbname="security_test",
        driver="asyncpg",
    )
    container.start()
    yield container
    container.stop()
```

#### Worker Database URL

From `backend/tests/integration/conftest.py:562-593`:

```python
@pytest.fixture(scope="session")
def worker_db_url(
    request: pytest.FixtureRequest,
    postgres_container: PostgresContainer | LocalPostgresService,
) -> Generator[str]:
    """Create and provide a worker-specific database URL.

    Each pytest-xdist worker gets its own database:
    - gw0 -> security_test_gw0
    - gw1 -> security_test_gw1
    - master (serial) -> security_test
    """
    worker_id = get_worker_id(request)
    db_name = get_worker_db_name(worker_id)
    base_url = _get_postgres_url(postgres_container)

    # Create the worker database
    worker_url = _create_worker_database(base_url, db_name)

    try:
        yield worker_url
    finally:
        # Clean up the worker database at session end
        _drop_worker_database(base_url, db_name)
```

#### Integration Environment

From `backend/tests/integration/conftest.py:627-696`:

```python
@pytest.fixture
def integration_env(
    worker_db_url: str,
    worker_redis_url: str,
) -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL for integration tests.

    Configures environment variables pointing to worker-isolated
    PostgreSQL and Redis databases.
    """
    original_db_url = os.environ.get("DATABASE_URL")
    original_redis_url = os.environ.get("REDIS_URL")

    os.environ["DATABASE_URL"] = worker_db_url
    os.environ["REDIS_URL"] = worker_redis_url

    # Configure pool sizes for integration tests
    if os.environ.get("CI"):
        os.environ["DATABASE_POOL_SIZE"] = "10"
        os.environ["DATABASE_POOL_OVERFLOW"] = "5"
    else:
        os.environ["DATABASE_POOL_SIZE"] = "5"
        os.environ["DATABASE_POOL_OVERFLOW"] = "2"

    get_settings.cache_clear()

    yield worker_db_url
    # Restore original environment...
```

#### Database Session

From `backend/tests/integration/conftest.py:907-924`:

```python
@pytest.fixture
async def db_session(integration_db: str):
    """Yield a live AsyncSession bound to the integration test database.

    Note: The session uses autocommit=False, so you must call
    `await session.commit()` to persist changes.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session
```

#### HTTP Test Client

From `backend/tests/integration/conftest.py:1117-1225`:

```python
@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock):
    """Async HTTP client bound to the FastAPI app.

    Notes:
    - DB is pre-initialized by `integration_db`
    - All background services are mocked
    - Test data is cleaned up before/after each test
    """
    await _cleanup_test_data()

    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    # Mock all background services
    with (
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=mock_redis)),
        # ... more patches
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as ac:
            yield ac

        await _cleanup_test_data()
```

## Test Patterns

### API Endpoint Testing

```python
@pytest.mark.asyncio
async def test_get_cameras_returns_list(client, db_session):
    """Test GET /api/cameras returns camera list."""
    # Arrange: Create test data
    from backend.models.camera import Camera

    camera = Camera(
        id="test_camera",
        name="Test Camera",
        folder_path="/export/foscam/test",
        status="online",
    )
    db_session.add(camera)
    await db_session.commit()

    # Act: Make API request
    response = await client.get("/api/cameras")

    # Assert: Verify response
    assert response.status_code == 200
    data = response.json()
    assert len(data["cameras"]) == 1
    assert data["cameras"][0]["id"] == "test_camera"
```

### Database Transaction Testing

```python
@pytest.mark.asyncio
async def test_event_creation_transaction(db_session):
    """Test event creation uses proper transaction handling."""
    from backend.models.event import Event
    from backend.tests.factories import CameraFactory

    # Create camera first (foreign key)
    camera = CameraFactory.build()
    db_session.add(camera)
    await db_session.commit()

    # Create event
    event = Event(
        batch_id="test_batch",
        camera_id=camera.id,
        started_at=datetime.now(UTC),
        risk_score=50,
        risk_level="medium",
        summary="Test event",
    )
    db_session.add(event)
    await db_session.commit()

    # Verify persistence
    await db_session.refresh(event)
    assert event.id is not None
```

### Isolated Session Testing

From `backend/tests/integration/conftest.py:927-966`:

```python
@pytest.fixture
async def isolated_db_session(integration_db: str):
    """Yield an isolated AsyncSession with transaction rollback.

    Uses PostgreSQL savepoints:
    1. Create savepoint before test
    2. Yield session to test
    3. Rollback to savepoint after test
    """
    from sqlalchemy import text
    from backend.core.database import get_session_factory

    factory = get_session_factory()
    session = factory()

    try:
        await session.execute(text("SAVEPOINT test_savepoint"))
        yield session
    finally:
        await session.execute(text("ROLLBACK TO SAVEPOINT test_savepoint"))
        await session.close()
```

Usage:

```python
@pytest.mark.asyncio
async def test_with_rollback(isolated_db_session):
    """Test data is automatically rolled back after test."""
    camera = Camera(id="temp", name="Temporary", ...)
    isolated_db_session.add(camera)
    await isolated_db_session.commit()

    # Camera exists during test
    assert camera.id is not None

    # After test: Camera is rolled back (not persisted)
```

### WebSocket Testing

```python
@pytest.mark.asyncio
async def test_websocket_connection(client):
    """Test WebSocket connection and message handling."""
    async with client.websocket_connect("/ws/events") as ws:
        # Send subscription message
        await ws.send_json({"type": "subscribe", "channel": "events"})

        # Receive confirmation
        response = await ws.receive_json()
        assert response["type"] == "subscribed"
```

## Data Cleanup

### Table Deletion Order

Integration tests use FK-safe deletion order computed from schema reflection:

From `backend/tests/integration/conftest.py:60-86`:

```python
HARDCODED_TABLE_DELETION_ORDER = [
    # First: Delete tables with foreign key references (leaf tables)
    "alerts",
    "event_audits",
    "detections",
    "activity_baselines",
    "class_baselines",
    "events",
    "scene_changes",
    "camera_notification_settings",
    "zones",
    # Second: Delete tables without FK references
    "alert_rules",
    "audit_logs",
    "gpu_stats",
    # ...
    # Last: Delete parent tables
    "cameras",
]
```

### Cleanup Fixture

From `backend/tests/integration/conftest.py:863-904`:

```python
@pytest.fixture
async def clean_tables(integration_db: str) -> AsyncGenerator[None]:
    """Delete all data from tables before and after test.

    Uses DELETE instead of TRUNCATE to avoid AccessExclusiveLock deadlocks.
    """
    async def delete_all() -> None:
        engine = get_engine()
        deletion_order = get_table_deletion_order(engine)

        async with get_session() as session:
            for table_name in deletion_order:
                try:
                    await session.execute(text(f"DELETE FROM {table_name}"))
                except Exception as e:
                    logger.debug(f"Skipping table {table_name}: {e}")
            await session.commit()

    await delete_all()
    yield
    await delete_all()
```

## Error Handling Tests

### Transaction Rollback

```python
@pytest.mark.asyncio
async def test_failed_transaction_rolls_back(db_session):
    """Test that failed transactions are properly rolled back."""
    from backend.models.camera import Camera

    camera = Camera(id="test", name="Test", ...)
    db_session.add(camera)

    # Simulate error
    try:
        await db_session.commit()
        raise ValueError("Simulated error")
    except ValueError:
        await db_session.rollback()

    # Verify rollback
    result = await db_session.execute(
        select(Camera).where(Camera.id == "test")
    )
    assert result.scalar_one_or_none() is None
```

### API Error Responses

```python
@pytest.mark.asyncio
async def test_not_found_returns_404(client):
    """Test that missing resources return 404."""
    response = await client.get("/api/cameras/nonexistent")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()
```

## Redis Testing

### Mock Redis

From `backend/tests/integration/conftest.py:985-1008`:

```python
@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations for tests that don't need real Redis."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
    }
    mock_redis_client._client = None

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client
```

### Real Redis

From `backend/tests/integration/conftest.py:1011-1038`:

```python
@pytest.fixture
async def real_redis(worker_redis_url: str) -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client for integration tests.

    Each xdist worker uses a different Redis database number for isolation.
    """
    from backend.core.redis import RedisClient

    client = RedisClient(redis_url=worker_redis_url)
    await client.connect()

    try:
        yield client
    finally:
        await client.disconnect()
```

## Best Practices

### 1. Use Unique IDs

From `backend/tests/integration/conftest.py:1232-1246`:

```python
def unique_id(prefix: str = "test") -> str:
    """Generate a unique ID for test objects to prevent conflicts."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
```

Usage:

```python
async def test_camera_creation(db_session):
    camera_id = unique_id("camera")
    camera = Camera(id=camera_id, name=f"Camera {camera_id}", ...)
    # No conflicts with parallel tests
```

### 2. Clean Up Test Data

Always clean up test data to prevent state leakage:

```python
@pytest.fixture
async def test_camera(db_session):
    """Create a camera and clean up after test."""
    camera = Camera(id=unique_id("cam"), ...)
    db_session.add(camera)
    await db_session.commit()

    yield camera

    # Cleanup
    await db_session.delete(camera)
    await db_session.commit()
```

### 3. Avoid Shared State

Don't rely on test execution order:

```python
# Bad: Depends on another test's data
async def test_get_camera():
    response = await client.get("/api/cameras/front_door")
    # May fail if other test didn't create this camera

# Good: Create own test data
async def test_get_camera(db_session, client):
    camera = Camera(id=unique_id("cam"), ...)
    db_session.add(camera)
    await db_session.commit()

    response = await client.get(f"/api/cameras/{camera.id}")
    assert response.status_code == 200
```

## Running Integration Tests

```bash
# Parallel (recommended)
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

# Serial (for debugging)
uv run pytest backend/tests/integration/ -n0

# Specific test file
uv run pytest backend/tests/integration/test_cameras_api.py -v

# With verbose output
uv run pytest backend/tests/integration/ -n8 -v --tb=long
```

## Related Documentation

- [Unit Testing](unit-testing.md) - Isolated component testing
- [Test Fixtures](test-fixtures.md) - Factory patterns
- [Coverage Requirements](coverage-requirements.md) - Coverage gates
