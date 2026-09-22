# Integration Testing

Integration tests verify multi-component workflows with real database connections. They ensure that services, repositories, and APIs work together correctly.

## Overview

Integration tests form the middle layer of the test pyramid (~15% of tests). They:

- Test multi-component interactions
- Use real PostgreSQL database (per-worker `security_test_gwN`)
- Use real Redis with per-worker database numbers, or a mocked Redis
  client — the `client` fixture mocks Redis; `real_redis` provides a live one
- Support parallel execution with worker-isolated databases

**Location**: `backend/tests/integration/` (~200 test files)

## Test Organization

### Directory Structure

```
backend/tests/integration/
  conftest.py             # Integration-specific fixtures (2020 lines)
  api/                    # Route-focused tests (+ api/routes/ snapshots)
  core/                   # Core infrastructure tests
  database/               # Database-level tests
  models/                 # ORM model tests
  repositories/           # Repository pattern tests
  services/               # Service tests (orchestrator, broadcaster, …)
  websocket/              # WebSocket broadcast tests
  test_*.py               # ~170 root-level suites: admin, alerts, analytics,
                          # cameras, events, auth, pipeline, migrations, …
```

### Test Categories

| Directory                | Files | Description                                      |
| ------------------------ | ----- | ------------------------------------------------ |
| Root-level `test_*.py`   | 170   | API, auth, WebSocket, pipeline, migration suites |
| `api/` (incl. `routes/`) | 10    | Route tests, snapshot-based response tests       |
| `services/`              | 15    | Batch aggregation, detector client, orchestrator |
| `repositories/`          | 7     | Repository pattern, cascades                     |
| `models/`                | 2     | ORM model behavior                               |
| `websocket/`             | 1     | Broadcast triggers                               |
| `core/` + `database/`    | 2     | Infrastructure and partition tests               |

## Parallel Execution

Integration tests support parallel execution via pytest-xdist with worker-isolated databases.

### How It Works

From `backend/tests/integration/conftest.py:312-331`:

```python
def get_worker_id(request: pytest.FixtureRequest) -> str:
    """Get the pytest-xdist worker ID ('gw0', 'gw1', etc.) or 'master'.

    When running without xdist (-n0 or no -n flag), returns 'master'.
    """
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
# Parallel — already the pyproject addopts default (-n 8 --dist=worksteal)
uv run pytest backend/tests/integration/

# Serial — what the project quick reference and the CI flaky-rerun tier
# use (-n0 overrides addopts): concurrent per-worker schema creation can
# deadlock on cold databases
uv run pytest backend/tests/integration/ -n0
```

## Fixtures

### Integration-Specific Fixtures (`backend/tests/integration/conftest.py`)

#### PostgreSQL Container

From `backend/tests/integration/conftest.py:377-412`:

```python
@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer | LocalPostgresService]:
    """Provide a session-scoped PostgreSQL service for all integration tests.

    Uses local PostgreSQL if available (development with Podman),
    otherwise starts a testcontainer for full isolation.
    """
    # Check for explicit environment variable override
    if os.environ.get("TEST_DATABASE_URL"):
        yield LocalPostgresService()
        return

    # Check for local PostgreSQL (development environment with Podman/Docker)
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
    try:
        wait_for_postgres_container(container)
        yield container
    finally:
        container.stop()
```

A matching `redis_container` fixture (`:416`) prefers local Redis and falls
back to a testcontainer; each xdist worker then uses a different Redis
database number (0-15) via `worker_redis_url`.

#### Worker Database URL

From `backend/tests/integration/conftest.py:699-729`:

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

    # Create the worker database (advisory-lock protected, :574)
    worker_url = _create_worker_database(base_url, db_name)

    try:
        yield worker_url
    finally:
        # Clean up the worker database at session end
        _drop_worker_database(base_url, db_name)
```

#### Integration Environment

From `backend/tests/integration/conftest.py:909-1013` (abridged):

```python
@pytest.fixture
def integration_env(
    worker_db_url: str,
    worker_redis_url: str,
) -> Generator[str]:
    """Set DATABASE_URL/REDIS_URL for integration tests, plus API-key auth.

    - API_KEY_ENABLED=true / API_KEYS=["test-api-key-12345"] so tests
      bypass session auth (which would need live Redis sessions)
    - HSI_RUNTIME_ENV_PATH points at a per-test temp file so PATCH
      /api/system/config writes never touch the developer's runtime.env
    - Sweeps leftover rate_limit:* keys from the worker's Redis DB at
      test start (bulk-tier counters otherwise leak across tests)
    """
    os.environ["DATABASE_URL"] = worker_db_url
    os.environ["REDIS_URL"] = worker_redis_url

    # Pool sizes: CI uses 10+5 for parallelism; local uses 5+5 so serial
    # runs don't exhaust PostgreSQL's max_connections
    if os.environ.get("CI"):
        os.environ["DATABASE_POOL_SIZE"] = "10"
        os.environ["DATABASE_POOL_OVERFLOW"] = "5"
    else:
        os.environ["DATABASE_POOL_SIZE"] = "5"
        os.environ["DATABASE_POOL_OVERFLOW"] = "5"

    get_settings.cache_clear()

    yield worker_db_url
    # Restore original environment...
```

#### Database Session

From `backend/tests/integration/conftest.py:1209-1225`:

```python
@pytest.fixture
async def db_session(integration_db: str, clean_tables):
    """Yield a live AsyncSession bound to the integration test database.

    `clean_tables` handles isolation between tests.

    Note: The session uses autocommit=False, so you must call
    `await session.commit()` to persist changes.
    """
    from backend.core.database import get_session

    async with get_session() as session:
        yield session
```

#### HTTP Test Client

From `backend/tests/integration/conftest.py:1540-1674` (abridged — the real
fixture mocks a dozen background services: broadcaster, GPU monitor,
cleanup service, file watcher, pipeline manager, health monitor, and the
SetupGuardMiddleware setup check, NEM-5312):

```python
@pytest.fixture
async def client(integration_db: str, mock_redis: AsyncMock):
    """Async HTTP client bound to the FastAPI app (no network, no server).

    - DB is pre-initialized by `integration_db`; data is cleaned up
      BEFORE and AFTER each test via _cleanup_test_data()
    - All background services and Redis are mocked
    - Requests carry X-API-Key (TEST_API_KEY from integration_env)
    """
    await _cleanup_test_data()

    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    with (
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=mock_redis)),
        patch("backend.main.FileWatcher", mock_file_watcher_class),
        patch(
            "backend.api.middleware.setup_guard.SetupGuardMiddleware"
            "._check_setup_complete",
            AsyncMock(return_value=True),
        ),
        # ... broadcaster/GPU/cleanup/pipeline patches
    ):
        try:
            headers = {"X-API-Key": TEST_API_KEY}
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers=headers,
            ) as ac:
                yield ac
        finally:
            await asyncio.wait_for(_cleanup_test_data(), timeout=10.0)
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

From `backend/tests/integration/conftest.py:1228-1273`:

```python
@pytest.fixture
async def isolated_db_session(integration_db: str, clean_tables):
    """Yield an isolated AsyncSession with transaction rollback.

    Implementation:
    1. Create a new session (transaction starts automatically on first use)
    2. Yield the session to the test
    3. Rollback the transaction after the test (success or failure)

    IMPORTANT: Do NOT use this fixture with `client` - use `db_session`
    instead (the `client` fixture handles cleanup itself).
    """
    from backend.core.database import get_session_factory

    factory = get_session_factory()
    session = factory()

    try:
        yield session
    finally:
        if session.in_transaction():
            await session.rollback()
        await session.close()
```

Usage:

```python
@pytest.mark.asyncio
async def test_with_rollback(isolated_db_session):
    """Test data is automatically rolled back after test."""
    camera = Camera(id="temp", name="Temporary", folder_path="/tmp/temp")
    isolated_db_session.add(camera)
    await isolated_db_session.commit()

    # Camera exists during test
    assert camera.id is not None

    # After test: transaction is rolled back (not persisted)
```

### WebSocket Testing

WebSocket routes are `/ws/events`, `/ws/system`, `/ws/detections` and
`/ws/jobs/{job_id}/logs` (`backend/api/routes/websocket.py:416, 642, 870,
1138`). Starlette's ASGI transport requires the sync `TestClient` for
`websocket_connect` (tests pair it with a mocked-Redis fixture), and the
subscription protocol is action-based:

```python
def test_websocket_subscribe(sync_client):
    """Subscribe to event patterns over /ws/events."""
    with sync_client.websocket_connect("/ws/events") as ws:
        # Send subscription message (patterns are globs)
        ws.send_json({"action": "subscribe", "events": ["alert.*"]})

        # Receive confirmation: {"action": "subscribed", "events": [...]}
        response = ws.receive_json()
        assert response["action"] == "subscribed"
```

## Data Cleanup

### Table Deletion Order

Integration tests use FK-safe deletion order computed from schema reflection:

From `backend/tests/integration/conftest.py:59-90` (abridged — the list is
the reflection-failure fallback; `get_table_deletion_order()` at `:173`
computes the real order from FK relationships):

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
    "zone_household_configs",
    "camera_zones",
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

From `backend/tests/integration/conftest.py:1128-1206` (abridged):

```python
@pytest.fixture
async def clean_tables(integration_db: str) -> AsyncGenerator[None]:
    """Delete all data from tables between tests.

    Uses DELETE, not TRUNCATE: TRUNCATE allocates a new relfilenode per
    call and defers unlinking the old one, which exhausted inodes across
    ~815 tables x per-test x per-worker DBs (ledger R-T7-ENOSPC-RECUR);
    on near-empty test tables DELETE is ~10x faster anyway.

    NOT autouse — tests request `db_session` / `isolated_db_session`
    (which depend on this), so DB-free tests skip it.
    """
    async def truncate_all() -> None:
        engine = get_engine()
        deletion_order = await get_table_deletion_order(engine)

        async with get_session() as session:
            # FK checks off for the sweep (children-first order above)
            await session.execute(text("SET session_replication_role = replica"))
            for table_name in deletion_order:
                await session.execute(text(f"DELETE FROM {table_name}"))
            await session.execute(text("SET session_replication_role = DEFAULT"))
            await session.commit()

    # Test runs first; cleanup happens after (with a 10s teardown timeout)
    yield
    await asyncio.wait_for(truncate_all(), timeout=10.0)
```

(The `client` fixture additionally sweeps data BEFORE each test via
`_cleanup_test_data()` (`:1381`), so API tests start fresh.)

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

From `backend/tests/integration/conftest.py:1291-1346` (abridged):

```python
@pytest.fixture
async def mock_redis() -> AsyncGenerator[AsyncMock]:
    """Mock Redis operations so tests don't require actual Redis."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    # Internal redis-py client mocked too: scan_iter (async generator),
    # script_load, evalsha for Lua rate-limit scripts
    mock_internal_client = AsyncMock()
    mock_redis_client._client = mock_internal_client
    mock_redis_client._ensure_connected = MagicMock(return_value=mock_internal_client)

    # Patch the shared singleton, initializer, and closer.
    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
        patch("backend.core.redis.close_redis", return_value=None),
    ):
        yield mock_redis_client
```

### Real Redis

From `backend/tests/integration/conftest.py:1348-1378`:

```python
@pytest.fixture
async def real_redis(worker_redis_url: str) -> AsyncGenerator[RedisClient]:
    """Provide a real Redis client for integration tests.

    Each xdist worker uses a different Redis database number for isolation.

    Note: does NOT flushdb (that would nuke parallel workers' keys) — use
    the test_prefix + cleanup_keys fixtures instead.
    """
    from backend.core.redis import RedisClient

    client = RedisClient(redis_url=worker_redis_url)
    await client.connect()

    try:
        yield client
    finally:
        await asyncio.wait_for(client.disconnect(), timeout=5.0)
```

## Best Practices

### 1. Use Unique IDs

From `backend/tests/integration/conftest.py:1682-1695` (a convenience
re-export of the root-conftest helper):

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
# Parallel — the addopts default already runs -n 8 --dist=worksteal
uv run pytest backend/tests/integration/

# Serial — preferred for debugging and used by the CI flaky-rerun tier
# (-n0 overrides addopts; avoids concurrent schema-creation deadlocks)
uv run pytest backend/tests/integration/ -n0

# Specific test file
uv run pytest backend/tests/integration/test_cameras_api.py -v

# With verbose output
uv run pytest backend/tests/integration/ -n0 -v --tb=long
```

## Related Documentation

- [Unit Testing](unit-testing.md) - Isolated component testing
- [Test Fixtures](test-fixtures.md) - Factory patterns
- [Coverage Requirements](coverage-requirements.md) - Coverage gates
