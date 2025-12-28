# Integration Tests Directory

## Purpose

Integration tests verify that multiple components work together correctly. Unlike unit tests that isolate individual functions, integration tests validate real interactions between the database, models, API endpoints, WebSocket channels, and middleware using actual implementations where possible.

## Test Files Overview

| File                                    | Description                   | Tests For                        |
| --------------------------------------- | ----------------------------- | -------------------------------- |
| `test_api.py`                           | FastAPI application endpoints | Root, health, CORS, lifecycle    |
| `test_cameras_api.py`                   | Camera CRUD API               | `/api/cameras/*` endpoints       |
| `test_system_api.py`                    | System information            | `/api/system/*` endpoints        |
| `test_media_api.py`                     | Media file serving            | `/api/media/*` endpoints         |
| `test_detections_api.py`                | Detections API                | `/api/detections/*` endpoints    |
| `test_events_api.py`                    | Events API                    | `/api/events/*` endpoints        |
| `test_logs_api.py`                      | Logs API                      | `/api/logs/*` endpoints          |
| `test_websocket.py`                     | WebSocket endpoints           | `/ws/events`, `/ws/system`       |
| `test_full_stack.py`                    | Complete workflows            | Database, models, business logic |
| `test_batch_aggregator_integration.py`  | Batch aggregation             | BatchAggregator service          |
| `test_detector_client_integration.py`   | Detector client               | DetectorClient service           |
| `test_file_watcher_integration.py`      | File watcher                  | FileWatcher service              |
| `test_health_monitor_integration.py`    | Health monitoring             | HealthMonitor service            |
| `test_nemotron_analyzer_integration.py` | Nemotron analyzer             | NemotronAnalyzer service         |
| `test_pipeline_e2e.py`                  | Pipeline end-to-end           | Complete pipeline flow           |
| `test_github_workflows.py`              | CI/CD validation              | GitHub workflow files            |
| `conftest.py`                           | Shared fixtures               | Test setup and teardown          |

## Fixture Configuration

### `conftest.py`

The integration tests have their own `conftest.py` that provides fixtures specific to integration testing:

**Fixtures:**

- `integration_env`: Sets up isolated test environment (DATABASE_URL, REDIS_URL, HSI_RUNTIME_ENV_PATH)
- `integration_db`: Initializes temporary database with schema
- `mock_redis`: Mocked Redis client to avoid external dependency
- `db_session`: Direct database session access for test setup/verification
- `client`: AsyncClient with ASGITransport for API testing (no server needed)

**Usage:**

```python
@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

## Key Test File Details

### `test_api.py`

Tests for FastAPI application endpoints and middleware.

**Coverage:**

- Root endpoint (`/`) - Basic API health check
- Health endpoint (`/health`) - System health with service status
- CORS middleware - Cross-origin requests and preflight OPTIONS
- Application lifecycle - Startup/shutdown events
- Error handling - Graceful degradation when services fail
- Concurrent requests - Multiple simultaneous requests
- Content type validation
- 404 handling for non-existent endpoints

### `test_cameras_api.py`

Tests for camera CRUD API endpoints (`/api/cameras/*`).

**Coverage:**

- **CREATE**: Camera creation, validation, defaults
- **READ**: List cameras, get by ID, filter by status
- **UPDATE**: Update name, status, folder_path, multiple fields
- **DELETE**: Delete camera, cascade to related data
- **Validation**: Empty fields, long strings, missing required fields
- **Edge cases**: Concurrent creation, update after delete, pagination

### `test_events_api.py`

Tests for events API endpoints (`/api/events/*`).

**Coverage:**

- List events (`GET /api/events`)
  - Empty results, with data
  - Filter by camera_id, risk_level, reviewed status
  - Filter by date range (start_date, end_date)
  - Pagination (limit, offset)
  - Combined filters, ordering (newest first)
- Get event by ID (`GET /api/events/{id}`)
- Update event (`PATCH /api/events/{id}`)
- Get event detections (`GET /api/events/{id}/detections`)

### `test_websocket.py`

Tests for WebSocket endpoints (`/ws/events`, `/ws/system`).

**Coverage:**

- **Events channel** (`/ws/events`)
  - Connection establishment, graceful disconnect
  - Receive new_event broadcasts, detection broadcasts
  - Multiple concurrent connections, reconnection
  - Message format validation
- **System channel** (`/ws/system`)
  - Connection establishment, graceful disconnect
  - Receive gpu_stats broadcasts, camera_status broadcasts
  - Multiple concurrent connections, reconnection
- **Connection cleanup**: Events and system channel cleanup
- **Error handling**: Invalid paths, connection errors
- **Broadcast functionality**: Channel isolation

### `test_full_stack.py`

Tests for complete workflows across database, models, and business logic.

**Coverage:**

- Camera operations: Create, query, relationships
- Detection operations: Create, link to camera, bounding boxes
- Event operations: Create, risk scoring, LLM data
- Relationships: Camera -> Detection, Camera -> Event
- Complete workflows: Camera -> Detection -> Event
- Time-based queries: Filter detections by time range
- Risk-based queries: Filter events by risk level
- Cascade deletes: Verify foreign key constraints
- Data isolation: Multi-camera operation independence
- Transaction boundaries: Session isolation

### `test_media_api.py`

Tests for media file serving endpoints (`/api/media/*`).

**Coverage:**

- Camera files (`/api/media/cameras/{camera_id}/{filename}`)
  - Valid image files (JPG, PNG)
  - Valid video files (MP4)
  - Nested subdirectories
  - Non-existent files (404)
  - Security: Path traversal prevention (`../../../etc/passwd`)
  - Security: Disallowed file types (.exe, .sh, .bat)
- Thumbnails (`/api/media/thumbnails/{filename}`)
- Content-Type headers for different formats

## Running Integration Tests

### All integration tests

```bash
pytest backend/tests/integration/ -v
```

### Single test file

```bash
pytest backend/tests/integration/test_api.py -v
pytest backend/tests/integration/test_cameras_api.py -v
pytest backend/tests/integration/test_events_api.py -v
```

### Specific test

```bash
pytest backend/tests/integration/test_api.py::test_root_endpoint -v
```

### With coverage

```bash
pytest backend/tests/integration/ -v --cov=backend --cov-report=html
```

### With verbose output

```bash
pytest backend/tests/integration/ -vv -s --log-cli-level=DEBUG
```

## Test Infrastructure

### Database Setup Pattern

All integration tests use temporary databases with complete isolation:

```python
@pytest.fixture
async def integration_db(integration_env):
    from backend.core.database import init_db, close_db

    await init_db()

    try:
        yield integration_env
    finally:
        await close_db()
```

### API Testing with ASGITransport

Integration tests use `httpx.AsyncClient` with `ASGITransport` to test the FastAPI app:

```python
@pytest.fixture
async def client(integration_db, mock_redis):
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac
```

**Benefits:**

- No server startup overhead
- No port conflicts
- Direct access to application
- Same behavior as production
- Faster test execution

### Redis Mocking Strategy

Redis is mocked to avoid requiring external services:

```python
@pytest.fixture
async def mock_redis():
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with patch("backend.core.redis._redis_client", mock_redis_client):
        yield mock_redis_client
```

## Test Scenarios

### Scenario 1: Complete Detection Workflow

```python
async def test_complete_workflow_camera_to_event(test_db):
    # Step 1: Create camera
    camera = Camera(id="workflow_cam", ...)
    # Step 2: Add detections (separate session)
    detections = [...]
    # Step 3: Create event from detections
    event = Event(detection_ids="1,2,3", ...)
    # Step 4: Verify complete chain
```

### Scenario 2: API CRUD Operations

```python
async def test_camera_crud(client):
    # Create
    response = await client.post("/api/cameras", json={...})
    camera_id = response.json()["id"]

    # Read
    response = await client.get(f"/api/cameras/{camera_id}")

    # Update
    response = await client.patch(f"/api/cameras/{camera_id}", json={...})

    # Delete
    response = await client.delete(f"/api/cameras/{camera_id}")
```

### Scenario 3: Security Testing

```python
def test_path_traversal_blocked(client, temp_foscam_dir):
    # Try to access file outside allowed directory
    response = client.get("/api/media/cameras/test/../../../etc/passwd")

    # Should be blocked
    assert response.status_code == 403
```

## Mocking Strategy

| Component    | Test Type   | Strategy             | Reason                      |
| ------------ | ----------- | -------------------- | --------------------------- |
| Database     | Integration | Real (SQLite)        | Test actual DB interactions |
| Redis        | Integration | Mocked               | Avoid external dependency   |
| FastAPI      | Integration | Real (ASGITransport) | Test actual app code        |
| HTTP clients | Integration | Mocked               | Control external responses  |
| File system  | Media tests | Temp directories     | Isolated, clean state       |

## Common Patterns

### Testing API Endpoints

```python
@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
    data = response.json()
    assert "field" in data
```

### Testing Database Workflows

```python
@pytest.mark.asyncio
async def test_workflow(integration_db):
    async with get_session() as session:
        # Create objects
        obj = Model(...)
        session.add(obj)
        await session.flush()

        # Query and verify
        result = await session.execute(select(Model))
        assert result.scalar_one() is not None
```

### Testing Relationships

```python
async with get_session() as session:
    result = await session.execute(select(Camera).where(...))
    camera = result.scalar_one()

    # Load relationships
    await session.refresh(camera, ["detections", "events"])

    assert len(camera.detections) > 0
    assert len(camera.events) > 0
```

### Testing Concurrent Operations

```python
@pytest.mark.asyncio
async def test_concurrent_requests(client):
    import asyncio

    tasks = [client.get("/endpoint") for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    for response in responses:
        assert response.status_code == 200
```

## Coverage Goals

- **Target**: 95%+ coverage for integration paths
- **Focus**: Critical user workflows and API contracts
- **Areas**:
  - All API endpoints (CRUD operations)
  - Database relationships and constraints
  - Error handling and validation
  - Security (path traversal, file types)
  - Multi-component interactions

## Test Statistics

- **Total test files**: 18
- **Key test categories**:
  - API tests: test_api.py
  - Camera API tests: test_cameras_api.py
  - System API tests: test_system_api.py
  - Media API tests: test_media_api.py
  - Detections API tests: test_detections_api.py
  - Events API tests: test_events_api.py
  - Logs API tests: test_logs_api.py
  - WebSocket tests: test_websocket.py
  - Full stack tests: test_full_stack.py
  - Service integration tests: Multiple files

## Dependencies

All dependencies in `backend/requirements.txt`:

- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async support
- `pytest-cov>=4.1.0` - Coverage
- `httpx>=0.25.0` - HTTP client for API testing
- `sqlalchemy>=2.0.0` - Database ORM
- `aiosqlite>=0.19.0` - Async SQLite

## Troubleshooting

### Database initialization fails

- Check `get_settings.cache_clear()` is called
- Verify environment variables are set correctly
- Ensure `init_db()` is awaited

### Mock Redis not working

- Verify patch path matches actual import
- Check mock is created before client fixture
- Ensure AsyncMock is used for async methods

### Tests interfere with each other

- Each test should have independent database
- Clear settings cache between tests
- Use function-scoped fixtures

### API client errors

- Check ASGITransport is used (not running server)
- Verify base_url is set
- Ensure app import happens after env setup

## Next Steps for AI Agents

1. **Examine test files**: Read to understand test patterns
2. **Review fixtures**: Check fixture setup and teardown (conftest.py)
3. **Run tests**: Execute pytest to verify current state
4. **Add tests**: Follow patterns for new API endpoints
5. **Verify coverage**: Ensure 95%+ with --cov flag
6. **Test workflows**: Focus on end-to-end user scenarios

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/tests/benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
