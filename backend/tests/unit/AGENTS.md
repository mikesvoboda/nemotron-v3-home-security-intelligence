# Unit Tests Directory

## Purpose

Unit tests verify individual components in isolation. Each test focuses on a single function, class, or module without dependencies on external services or other components.

## Test Files

### Core Components

#### `test_config.py` (479 lines, 60+ tests)

Tests for application configuration and settings management.

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

#### `test_database.py` (263 lines, 12 tests)

Tests for database connection and session management.

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

#### `test_redis.py` (536 lines, 40+ tests)

Tests for Redis client operations.

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

### Database Models

#### `test_models.py` (692 lines, 50+ tests)

Tests for SQLAlchemy database models.

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

### AI Services

#### `test_file_watcher.py` (569 lines, 30+ tests)

Tests for file system monitoring service.

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

#### `test_detector_client.py` (540 lines, 25+ tests)

Tests for RT-DETRv2 object detection client.

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

#### `test_batch_aggregator.py` (515 lines, 30+ tests)

Tests for detection batch aggregation service.

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

#### `test_nemotron_analyzer.py` (688 lines, 35+ tests)

Tests for Nemotron LLM risk analysis service.

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

#### `test_thumbnail_generator.py` (807 lines, 45+ tests)

Tests for thumbnail generation with bounding boxes.

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

## Common Fixtures

### From conftest.py

- `isolated_db`: Temporary database with clean state
- `reset_settings_cache`: Auto-clears settings cache

### Test-specific fixtures

- `engine`: In-memory SQLite engine (test_models.py)
- `session`: Database session with rollback (test_models.py)
- `mock_redis_client`: Mocked Redis with common operations
- `mock_session`: Mocked database session for services
- `temp_camera_root`: Temporary camera directory structure
- `sample_detections`: Pre-built detection objects

## Mocking Patterns

### Redis Mocking

```python
@pytest.fixture
def mock_redis_client():
    mock_client = AsyncMock(spec=Redis)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
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

## Testing Best Practices

### 1. Test Organization

- Group related tests in classes (`TestCameraModel`, `TestDetectionModel`)
- Use descriptive test names (`test_create_camera_with_default_status`)
- One assertion focus per test

### 2. Fixture Usage

- Use `isolated_db` for any database operations
- Create test-specific fixtures for complex setups
- Keep fixtures simple and reusable

### 3. Mocking Strategy

- Mock external services (HTTP, file system, Redis)
- Use real database (SQLite in-memory) for authentic testing
- Mock at the boundary (httpx.AsyncClient, not internal functions)

### 4. Error Testing

- Test both success and failure paths
- Verify error messages and types
- Test edge cases (empty data, None values, invalid formats)

### 5. Async Testing

- Always use `@pytest.mark.asyncio` decorator
- Await all async calls
- Use `async with` for context managers

## Coverage Goals

- **Target**: 98%+ coverage
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

### Database Tests Fail

- Use `isolated_db` fixture
- Clear settings cache with `get_settings.cache_clear()`
- Check database session is properly closed

## Next Steps for AI Agents

1. **Examine test structure**: Read test files to understand patterns
2. **Check fixtures**: Review conftest.py and test-specific fixtures
3. **Run tests**: Execute with pytest to verify current state
4. **Add tests**: Follow existing patterns for new functionality
5. **Verify coverage**: Ensure 98%+ coverage with --cov flag
