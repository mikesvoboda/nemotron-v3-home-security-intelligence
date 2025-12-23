# Integration Tests Directory

## Purpose

Integration tests verify that multiple components work together correctly. Unlike unit tests that isolate individual functions, integration tests validate real interactions between the database, models, API endpoints, and middleware.

## Test Files

### `test_api.py` (243 lines, 13 tests)

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

**Key patterns:**

- Uses `ASGITransport` to test app without running server
- Mocks Redis to avoid external dependencies
- Real temporary SQLite database
- Async HTTP client with httpx

**Fixtures:**

- `test_db_setup`: Temporary database with environment setup
- `mock_redis`: Mocked Redis client for health checks
- `client`: AsyncClient with ASGITransport for API testing

### `test_cameras_api.py` (647 lines, 35+ tests)

Tests for camera CRUD API endpoints.

**Coverage:**

- **CREATE**: Camera creation, validation, defaults
- **READ**: List cameras, get by ID, filter by status
- **UPDATE**: Update name, status, folder_path, multiple fields
- **DELETE**: Delete camera, cascade to related data
- **Validation**: Empty fields, long strings, missing required fields
- **Edge cases**: Concurrent creation, update after delete

**Key patterns:**

- Full CRUD test coverage
- Database cascade delete verification
- Concurrent operation testing
- Response schema validation

**Fixtures:**

- `test_db_setup`: Explicit database initialization
- `mock_redis`: Redis mocking
- `client`: FastAPI test client
- `get_test_db_session`: Direct database access for verification

### `test_system_api.py` (344 lines, 15 tests)

Tests for system information and monitoring endpoints.

**Coverage:**

- Health check (`/api/system/health`) - Service status reporting
- GPU stats (`/api/system/gpu`) - GPU utilization and memory
- Config (`/api/system/config`) - Public configuration exposure
- Stats (`/api/system/stats`) - System statistics and counts
- Concurrent request handling
- JSON content type validation

**Key patterns:**

- Health check with degraded services
- GPU data mocking for testing
- Security validation (no sensitive data exposed)
- Statistics aggregation testing

**Fixtures:**

- `test_db_setup`: Database initialization
- `mock_redis`: Redis client mocking
- `client`: FastAPI test client

### `test_media_api.py` (251 lines, 20+ tests)

Tests for media file serving endpoints.

**Coverage:**

- Camera files (`/api/media/cameras/{camera_id}/{filename}`)
  - Valid image files (JPG, PNG)
  - Valid video files (MP4)
  - Nested subdirectories
  - Non-existent files (404)
  - Security: Path traversal prevention
  - Security: Disallowed file types (.exe, .sh)
- Thumbnails (`/api/media/thumbnails/{filename}`)
  - Valid thumbnails (JPG, PNG)
  - Non-existent files (404)
  - Security: Path traversal prevention
  - Security: Disallowed file types
- Content-Type headers for different formats

**Key patterns:**

- TestClient (synchronous) for file serving
- Temporary directory fixtures with test files
- Path traversal attack testing
- File type validation

**Fixtures:**

- `client`: Synchronous TestClient
- `temp_foscam_dir`: Temporary camera directory with test files
- `temp_thumbnail_dir`: Temporary thumbnail directory

### `test_full_stack.py` (556 lines, 14 tests)

Tests for complete workflows across database, models, and business logic.

**Coverage:**

- Camera operations: Create, query, relationships
- Detection operations: Create, link to camera, bounding boxes
- Event operations: Create, risk scoring, LLM data
- Relationships: Camera → Detection, Camera → Event
- Complete workflows: Camera → Detection → Event
- Time-based queries: Filter detections by time range
- Risk-based queries: Filter events by risk level
- Cascade deletes: Verify foreign key constraints
- Data isolation: Multi-camera operation independence
- Transaction boundaries: Session isolation
- Event review status updates

**Key patterns:**

- Real database operations (not mocked)
- Multi-step workflows across sessions
- Relationship loading with `refresh()`
- Time-based and filtered queries
- Complete end-to-end scenarios

**Fixtures:**

- `test_db`: Full database setup with all tables created

## Running Integration Tests

### All integration tests

```bash
pytest backend/tests/integration/ -v
```

### Single test file

```bash
pytest backend/tests/integration/test_api.py -v
pytest backend/tests/integration/test_cameras_api.py -v
pytest backend/tests/integration/test_system_api.py -v
pytest backend/tests/integration/test_media_api.py -v
pytest backend/tests/integration/test_full_stack.py -v
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
pytest backend/tests/integration/ -vv -s
```

## Test Infrastructure

### Database Setup Pattern

All integration tests use temporary databases with complete isolation:

```python
@pytest.fixture
async def test_db_setup():
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store and override environment
        original_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = test_db_url

        # Clear settings cache and initialize
        get_settings.cache_clear()
        await init_db()

        yield test_db_url

        # Cleanup
        await close_db()
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()
```

### API Testing with ASGITransport

Integration tests use `httpx.AsyncClient` with `ASGITransport` to test the FastAPI app:

```python
@pytest.fixture
async def client(test_db_setup, mock_redis):
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

### Scenario 3: Cascade Delete Verification

```python
async def test_cascade_delete(test_db):
    # Create camera with children
    camera = Camera(...)
    detection = Detection(camera_id=camera.id, ...)
    event = Event(camera_id=camera.id, ...)

    # Delete camera
    await session.delete(camera)

    # Verify children deleted
    assert no detections exist
    assert no events exist
```

### Scenario 4: Security Testing

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
async def test_workflow(test_db):
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

- **Target**: 98%+ coverage for integration paths
- **Focus**: Critical user workflows and API contracts
- **Areas**:
  - All API endpoints (CRUD operations)
  - Database relationships and constraints
  - Error handling and validation
  - Security (path traversal, file types)
  - Multi-component interactions

## Test Statistics

- **Total test files**: 5
- **Total test cases**: 97+
- **API tests**: 13 (test_api.py)
- **Camera API tests**: 35+ (test_cameras_api.py)
- **System API tests**: 15 (test_system_api.py)
- **Media API tests**: 20+ (test_media_api.py)
- **Full stack tests**: 14 (test_full_stack.py)

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
2. **Review fixtures**: Check fixture setup and teardown
3. **Run tests**: Execute pytest to verify current state
4. **Add tests**: Follow patterns for new API endpoints
5. **Verify coverage**: Ensure 98%+ with --cov flag
6. **Test workflows**: Focus on end-to-end user scenarios
