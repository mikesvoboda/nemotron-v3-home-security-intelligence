# Unit Tests Directory

## Purpose

Unit tests verify individual components in isolation. Each test focuses on a single function, class, or module without dependencies on external services or other components. All external dependencies (Redis, HTTP, file system) are mocked.

## Test Files Overview

### Core Components

#### `test_config.py` (479 lines, 60+ tests)

Tests for application configuration and settings management (`backend/core/config.py`).

**Coverage:**

- Default configuration values (database_url, redis_url, API settings)
- Environment variable overrides for all settings
- Type coercion (strings to int, bool, list)
- Settings singleton pattern (caching behavior)
- Database URL validation and directory creation
- Edge cases (empty values, special characters, very long strings)

**Key patterns:**

- `clean_env` fixture for isolated environment testing
- `monkeypatch` for environment variable manipulation
- Tests for Pydantic Settings validation

**Example:**

```python
def test_database_url_override(clean_env, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    settings = get_settings()
    assert settings.database_url == "sqlite:///test.db"
```

#### `test_database.py` (263 lines, 12 tests)

Tests for database connection and session management (`backend/core/database.py`).

**Coverage:**

- Database initialization and cleanup (`init_db`, `close_db`)
- Engine and session factory creation
- Session context manager behavior
- Transaction rollback on errors
- Session isolation between tests
- FastAPI dependency injection (`get_db`)

**Key patterns:**

- `TestModel` for database operation testing
- Temporary database creation per test
- Async session management with context managers

**Example:**

```python
@pytest.mark.asyncio
async def test_session_transaction_rollback(isolated_db):
    async with get_session() as session:
        obj = TestModel(value="test")
        session.add(obj)
        await session.flush()
        # Force error
        await session.rollback()
```

#### `test_redis.py` (536 lines, 40+ tests)

Tests for Redis client operations (`backend/core/redis.py`).

**Coverage:**

- Connection establishment with retry logic
- Health check operations
- Queue operations (push, pop, length, peek, clear)
- Pub/sub messaging (publish, subscribe, listen)
- Cache operations (get, set, delete, exists)
- Error handling and connection failures
- Integration tests (optional, requires Redis)

**Key patterns:**

- Comprehensive mocking with `AsyncMock`
- Connection retry testing
- JSON serialization/deserialization testing
- Optional integration tests marked with `pytest.mark.skipif`

**Example:**

```python
@pytest.mark.asyncio
async def test_queue_operations():
    mock_client = AsyncMock()
    redis = RedisClient(client=mock_client)

    await redis.add_to_queue("test_queue", {"data": "value"})
    mock_client.rpush.assert_called_once()
```

### Database Models

#### `test_models.py` (692 lines, 50+ tests)

Tests for SQLAlchemy database models (`backend/models/`).

**Coverage:**

- **Camera model**: Creation, defaults, status updates, relationships
- **Detection model**: Creation, bounding boxes, relationships, cascade deletes
- **Event model**: Risk scoring, LLM data, review status, cascade deletes
- **GPUStats model**: Time series data, partial data handling
- **Relationships**: One-to-many between Camera and Detections/Events
- **Queries**: Filtering by time, risk level, camera ID
- **Integration scenarios**: Complete workflows across models

**Key patterns:**

- In-memory SQLite with `create_engine("sqlite:///:memory:")`
- Session-per-test with automatic rollback
- Comprehensive relationship testing

**Example:**

```python
def test_camera_detection_relationship(session):
    camera = Camera(id="cam1", name="Test")
    detection = Detection(camera_id="cam1", object_type="person")
    session.add_all([camera, detection])
    session.commit()

    assert len(camera.detections) == 1
    assert detection.camera.id == "cam1"
```

### AI Services

#### `test_file_watcher.py` (569 lines, 30+ tests)

Tests for file system monitoring service (`backend/services/file_watcher.py`).

**Coverage:**

- Image file validation (format, size, corruption detection)
- Camera directory structure parsing
- File event handling (create, modify)
- Debouncing to prevent duplicate processing
- Queue integration for detected files
- Start/stop lifecycle management
- Path traversal security validation

**Key patterns:**

- `temp_camera_root` fixture for isolated file system
- PIL Image for creating test images
- Watchdog event simulation
- Async task scheduling and cancellation

**Example:**

```python
@pytest.mark.asyncio
async def test_file_detection(temp_camera_root, mock_redis):
    watcher = FileWatcher(redis_client=mock_redis)

    # Create test image
    image_path = temp_camera_root / "camera1" / "test.jpg"
    Image.new("RGB", (640, 480)).save(image_path)

    # Verify file is detected
    await watcher._handle_file_event(str(image_path))
    mock_redis.add_to_queue.assert_called()
```

#### `test_detector_client.py` (540 lines, 25+ tests)

Tests for RT-DETRv2 object detection client (`backend/services/detector_client.py`).

**Coverage:**

- Health check endpoint connectivity
- Object detection with bounding boxes
- Confidence threshold filtering
- Multiple object types in single image
- Error handling (timeout, connection, HTTP errors)
- Invalid JSON and malformed responses
- Database persistence of detections

**Key patterns:**

- Mock httpx for HTTP requests
- Sample detection responses
- File path mocking
- Database session mocking

**Example:**

```python
@pytest.mark.asyncio
async def test_detect_objects(mock_http_client, mock_session):
    mock_response = {"detections": [
        {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]}
    ]}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json = MagicMock(return_value=mock_response)

        client = DetectorClient()
        detections = await client.detect_objects("test.jpg", "cam1", mock_session)

        assert len(detections) == 1
        assert detections[0].object_type == "person"
```

#### `test_batch_aggregator.py` (515 lines, 30+ tests)

Tests for detection batch aggregation service (`backend/services/batch_aggregator.py`).

**Coverage:**

- New batch creation when no active batch exists
- Adding detections to existing batches
- Batch timeout detection (90-second window)
- Idle timeout detection (30-second idle)
- Manual batch closing
- Analysis queue integration
- Configuration value usage
- Concurrent camera batch handling

**Key patterns:**

- Mock Redis client with time-based logic
- UUID generation mocking
- Batch metadata tracking in Redis
- Queue format validation

**Example:**

```python
@pytest.mark.asyncio
async def test_batch_aggregation(mock_redis):
    aggregator = BatchAggregator(redis_client=mock_redis)

    batch_id = await aggregator.add_detection("cam1", "det1", "test.jpg")

    # Verify batch metadata
    camera_id = await mock_redis.get(f"batch:{batch_id}:camera_id")
    assert camera_id == "cam1"
```

#### `test_nemotron_analyzer.py` (688 lines, 35+ tests)

Tests for Nemotron LLM risk analysis service (`backend/services/nemotron_analyzer.py`).

**Coverage:**

- Health check for LLM endpoint
- Detection formatting for LLM prompt
- LLM response parsing (JSON extraction)
- Risk data validation and clamping (0-100)
- Risk level inference from score
- Complete batch analysis workflow
- Fallback behavior when LLM fails
- Event broadcasting via Redis pub/sub

**Key patterns:**

- Mock httpx for LLM API calls
- JSON parsing with error handling
- Database integration with `isolated_db`
- Sample detections fixture

**Example:**

```python
@pytest.mark.asyncio
async def test_analyze_batch(mock_http_client, mock_redis, isolated_db):
    mock_response = {"content": json.dumps({
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Person detected"
    })}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json = MagicMock(return_value=mock_response)

        analyzer = NemotronAnalyzer(redis_client=mock_redis)
        event = await analyzer.analyze_batch("batch_id")

        assert event.risk_score == 75
```

#### `test_thumbnail_generator.py` (807 lines, 45+ tests)

Tests for thumbnail generation with bounding boxes (`backend/services/thumbnail_generator.py`).

**Coverage:**

- Thumbnail generation from images
- Bounding box drawing for detections
- Object type color mapping
- Image resizing with aspect ratio preservation
- Multiple image formats (JPG, PNG, RGBA)
- File operations (create, delete)
- Edge cases (missing files, invalid images, permission errors)

**Key patterns:**

- PIL Image for image manipulation
- Temporary directories for output
- Font fallback testing
- Path validation

### Broadcaster Services

#### `test_event_broadcaster.py` (169 lines, 10+ tests)

Tests for event WebSocket broadcasting (`backend/services/event_broadcaster.py`).

**Coverage:**

- Event creation broadcasts
- Detection broadcasts
- Message format validation
- Redis pub/sub integration
- Multiple subscriber handling

#### `test_system_broadcaster.py` (380 lines, 20+ tests)

Tests for system status broadcasting (`backend/services/system_broadcaster.py`).

**Coverage:**

- GPU stats broadcasts
- Camera status broadcasts
- Health check broadcasts
- Message format validation
- Periodic broadcast scheduling

#### `test_gpu_monitor.py` (480 lines, 25+ tests)

Tests for GPU monitoring service (`backend/services/gpu_monitor.py`).

**Coverage:**

- GPU stats collection (pynvml)
- Database persistence
- Broadcast integration
- Error handling (no GPU, driver errors)
- Periodic monitoring

#### `test_cleanup_service.py` (650 lines, 31 tests)

Tests for data cleanup service (`backend/services/cleanup_service.py`).

**Coverage:**

- Old detection cleanup (30-day retention)
- Old event cleanup (30-day retention)
- Old GPU stats cleanup
- Old log cleanup
- Scheduled cleanup tasks
- Configuration override

### Logging

#### `test_logging.py` (260 lines, 15 tests)

Tests for structured logging module (`backend/core/logging.py`).

**Coverage:**

- Logger creation and configuration
- Request ID context management
- Custom JSON formatter
- SQLite handler for database logging
- Context filter functionality
- Log level configuration

**Key patterns:**

- Mocking settings for configuration testing
- Context variable testing
- Handler output testing

**Example:**

```python
def test_request_id_context():
    set_request_id("test-123")
    assert get_request_id() == "test-123"
    set_request_id(None)
    assert get_request_id() is None
```

#### `test_log_model.py` (49 lines, 3 tests)

Tests for Log SQLAlchemy model (`backend/models/log.py`).

**Coverage:**

- Log creation with required fields
- Optional metadata fields (camera_id, request_id, duration_ms, extra)
- String representation

### API Routes

#### `test_detections_api.py` (100 lines, 8 tests)

Tests for detection API route handlers (`backend/api/routes/detections.py`).

**Coverage:**

- List detections endpoint
- Get detection endpoint
- Filter validation
- Response schema validation

#### `test_events_api.py` (320 lines, 21 tests)

Tests for event API route handlers (`backend/api/routes/events.py`).

**Coverage:**

- List events endpoint
- Get event endpoint
- Update event (review status)
- Get event detections
- Filter and pagination validation
- Risk level filtering

#### `test_system_routes.py` (65 lines, 5 tests)

Tests for system API route handlers (`backend/api/routes/system.py`).

**Coverage:**

- Health check endpoint
- GPU stats endpoint
- Config endpoint
- Stats endpoint

#### `test_websocket.py` (600 lines, 30+ tests)

Tests for WebSocket route handlers (`backend/api/routes/websocket.py`).

**Coverage:**

- Connection establishment
- Message broadcasting
- Channel isolation (events vs system)
- Connection cleanup
- Error handling

#### `test_auth_middleware.py` (260 lines, 15+ tests)

Tests for authentication middleware (`backend/api/middleware/auth.py`).

**Coverage:**

- No-auth mode (default for single-user)
- Request validation
- Response headers

## Running Unit Tests

### All unit tests

```bash
pytest backend/tests/unit/ -v
```

### Single test file

```bash
pytest backend/tests/unit/test_models.py -v
```

### Specific test class

```bash
pytest backend/tests/unit/test_models.py::TestCameraModel -v
```

### Specific test

```bash
pytest backend/tests/unit/test_models.py::TestCameraModel::test_create_camera -v
```

### With coverage

```bash
pytest backend/tests/unit/ -v --cov=backend --cov-report=html
```

### Fast execution (no coverage)

```bash
pytest backend/tests/unit/ -v --no-cov
```

## Common Fixtures

### From conftest.py (project root)

- `isolated_db`: Temporary database with clean state
- `test_db`: Database session factory for unit tests
- `reset_settings_cache`: Auto-clears settings cache

### Test-specific fixtures

- `engine`: In-memory SQLite engine (test_models.py)
- `session`: Database session with rollback (test_models.py)
- `mock_redis_client`: Mocked Redis with common operations
- `mock_session`: Mocked database session for services
- `temp_camera_root`: Temporary camera directory structure
- `sample_detections`: Pre-built detection objects
- `mock_http_client`: Mocked httpx AsyncClient
- `clean_env`: Isolated environment for config tests

## Mocking Patterns

### Redis Mocking

```python
@pytest.fixture
def mock_redis_client():
    mock_client = AsyncMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.add_to_queue = AsyncMock()
    mock_client.publish = AsyncMock()
    return mock_client
```

### HTTP Client Mocking

```python
with patch("httpx.AsyncClient.post") as mock_post:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_post.return_value = mock_response
```

### File System Mocking

```python
with patch("pathlib.Path.exists", return_value=True):
    with patch("pathlib.Path.read_bytes", return_value=b"test_data"):
        # Test code here
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
    return session
```

## Testing Best Practices

### 1. Test Organization

- Group related tests in classes (`TestCameraModel`, `TestDetectionModel`)
- Use descriptive test names (`test_create_camera_with_default_status`)
- One assertion focus per test

```python
class TestCameraModel:
    def test_create_camera_with_defaults(self, session):
        camera = Camera(id="test", name="Test Camera")
        session.add(camera)
        session.commit()

        assert camera.status == "online"  # Default value
```

### 2. Fixture Usage

- Use `isolated_db` for any database operations
- Create test-specific fixtures for complex setups
- Keep fixtures simple and reusable

```python
@pytest.fixture
def sample_camera(isolated_db):
    async with get_session() as session:
        camera = Camera(id="test", name="Test")
        session.add(camera)
        await session.commit()
        yield camera
```

### 3. Mocking Strategy

- Mock external services (HTTP, file system, Redis)
- Use real database (SQLite in-memory) for authentic testing
- Mock at the boundary (httpx.AsyncClient, not internal functions)

```python
# Good: Mock at boundary
with patch("httpx.AsyncClient") as mock_http:
    # Test code

# Bad: Mock internal function
with patch("backend.services.detector_client._parse_response"):
    # Too granular, tests implementation not behavior
```

### 4. Error Testing

- Test both success and failure paths
- Verify error messages and types
- Test edge cases (empty data, None values, invalid formats)

```python
@pytest.mark.asyncio
async def test_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=ConnectionError):
        result = await detector.detect_objects("test.jpg", "cam1", session)
        assert result == []  # Graceful failure
```

### 5. Async Testing

- Always use `@pytest.mark.asyncio` decorator
- Await all async calls
- Use `async with` for context managers

```python
@pytest.mark.asyncio
async def test_async_operation(isolated_db):
    async with get_session() as session:
        result = await some_async_function(session)
        assert result is not None
```

## Coverage Goals

- **Target**: 98%+ coverage for unit tests
- **Focus areas**:
  - Happy path (normal operation)
  - Error conditions (exceptions, timeouts, bad data)
  - Edge cases (empty lists, None values, boundary conditions)
  - Validation logic (input validation, type checking)

## Common Test Patterns

### Database Model Testing

```python
def test_create_model(session):
    obj = Model(field1="value1", field2="value2")
    session.add(obj)
    session.commit()

    assert obj.id is not None
    assert obj.field1 == "value1"
```

### Service Testing with Mocks

```python
@pytest.mark.asyncio
async def test_service_operation(mock_redis_client):
    service = Service(redis_client=mock_redis_client)
    result = await service.do_something()

    assert result is not None
    mock_redis_client.set.assert_called_once()
```

### Error Handling Testing

```python
@pytest.mark.asyncio
async def test_handles_error_gracefully():
    with patch("external.call", side_effect=Exception("Error")):
        result = await service.operation()

        assert result is None  # Graceful failure
```

### Relationship Testing

```python
def test_one_to_many_relationship(session):
    parent = Parent(id=1, name="Parent")
    child1 = Child(parent_id=1, name="Child1")
    child2 = Child(parent_id=1, name="Child2")

    session.add_all([parent, child1, child2])
    session.commit()

    assert len(parent.children) == 2
```

## Troubleshooting

### Import Errors

- Ensure backend path is in sys.path (conftest.py handles this)
- Check module names match file structure

### Async Errors

- Add `@pytest.mark.asyncio` decorator
- Ensure all async functions are awaited
- Check pytest-asyncio is installed

### Mock Not Working

- Verify mock path matches import path in source
- Use `spec=ClassName` to catch attribute errors
- Check mock is applied before function call

```python
# Correct: Match import path in source
with patch("backend.services.detector_client.httpx.AsyncClient"):
    # Works

# Incorrect: Wrong path
with patch("httpx.AsyncClient"):
    # May not work if imported differently
```

### Database Tests Fail

- Use `isolated_db` fixture
- Clear settings cache with `get_settings.cache_clear()`
- Check database session is properly closed

### Test Isolation Issues

- Verify fixtures use function scope
- Check for global state modifications
- Use fresh mocks for each test

## Test Statistics

- **Total test files**: 22
- **Total test cases**: 453
- **Average execution time**: <10 seconds (unit tests only)
- **Coverage**: 98%+ for unit-tested components

### Test Files Summary

| File                        | Tests | Description                 |
| --------------------------- | ----- | --------------------------- |
| test_auth_middleware.py     | 18    | Authentication middleware   |
| test_batch_aggregator.py    | 29    | Detection batch aggregation |
| test_cleanup_service.py     | 31    | Data cleanup service        |
| test_config.py              | 49    | Configuration and settings  |
| test_database.py            | 11    | Database connections        |
| test_detections_api.py      | 6     | Detections API routes       |
| test_detector_client.py     | 20    | RT-DETRv2 client            |
| test_event_broadcaster.py   | 7     | Event broadcasting          |
| test_events_api.py          | 21    | Events API routes           |
| test_file_watcher.py        | 34    | File system monitoring      |
| test_gpu_monitor.py         | 27    | GPU monitoring              |
| test_logging.py             | 15    | Structured logging          |
| test_log_model.py           | 3     | Log model                   |
| test_models.py              | 26    | Database models             |
| test_nemotron_analyzer.py   | 38    | Nemotron LLM analyzer       |
| test_redis.py               | 30    | Redis client                |
| test_system_broadcaster.py  | 23    | System broadcasting         |
| test_system_routes.py       | 4     | System API routes           |
| test_thumbnail_generator.py | 36    | Thumbnail generation        |
| test_websocket.py           | 25    | WebSocket handlers          |

## Next Steps for AI Agents

1. **Examine test structure**: Read test files to understand patterns
2. **Check fixtures**: Review conftest.py and test-specific fixtures
3. **Run tests**: Execute with pytest to verify current state
4. **Add tests**: Follow existing patterns for new functionality
5. **Verify coverage**: Ensure 98%+ coverage with --cov flag
6. **Test error paths**: Always test both success and failure cases

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/integration/AGENTS.md` - Integration test patterns
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
