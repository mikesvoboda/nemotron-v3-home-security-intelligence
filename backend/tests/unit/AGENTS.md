# Unit Tests Directory

## Purpose

Unit tests verify individual components in isolation. Each test focuses on a single function, class, or module without dependencies on external services or other components. All external dependencies (Redis, HTTP, file system) are mocked.

## Test Files Overview

### Core Components

| File               | Description                                | Tests For                  |
| ------------------ | ------------------------------------------ | -------------------------- |
| `test_config.py`   | Configuration and settings                 | `backend/core/config.py`   |
| `test_database.py` | Database connection and session management | `backend/core/database.py` |
| `test_redis.py`    | Redis client operations                    | `backend/core/redis.py`    |
| `test_logging.py`  | Structured logging module                  | `backend/core/logging.py`  |
| `test_metrics.py`  | Metrics collection                         | `backend/core/metrics.py`  |

### Database Models

| File                | Description                | Tests For                          |
| ------------------- | -------------------------- | ---------------------------------- |
| `test_models.py`    | SQLAlchemy database models | Camera, Detection, Event, GPUStats |
| `test_log_model.py` | Log model                  | `backend/models/log.py`            |

### AI Services

| File                          | Description                              | Tests For                                          |
| ----------------------------- | ---------------------------------------- | -------------------------------------------------- |
| `test_file_watcher.py`        | File system monitoring                   | `backend/services/file_watcher.py`                 |
| `test_detector_client.py`     | RT-DETRv2 object detection client        | `backend/services/detector_client.py`              |
| `test_batch_aggregator.py`    | Detection batch aggregation              | `backend/services/batch_aggregator.py`             |
| `test_nemotron_analyzer.py`   | Nemotron LLM risk analysis               | `backend/services/nemotron_analyzer.py`            |
| `test_thumbnail_generator.py` | Thumbnail generation with bounding boxes | `backend/services/thumbnail_generator.py`          |
| `test_video_support.py`       | Video file support (new)                 | Video detection, validation, streaming, thumbnails |
| `test_pipeline_worker.py`     | AI pipeline worker                       | `backend/services/pipeline_worker.py`              |
| `test_pipeline_workers.py`    | Worker orchestration                     | Pipeline worker management                         |

### Broadcaster Services

| File                         | Description                  | Tests For                                |
| ---------------------------- | ---------------------------- | ---------------------------------------- |
| `test_event_broadcaster.py`  | Event WebSocket broadcasting | `backend/services/event_broadcaster.py`  |
| `test_system_broadcaster.py` | System status broadcasting   | `backend/services/system_broadcaster.py` |
| `test_gpu_monitor.py`        | GPU monitoring service       | `backend/services/gpu_monitor.py`        |
| `test_cleanup_service.py`    | Data cleanup service         | `backend/services/cleanup_service.py`    |
| `test_health_monitor.py`     | Health monitoring            | `backend/services/health_monitor.py`     |
| `test_service_managers.py`   | Service lifecycle management | Service managers                         |

### API Routes

| File                           | Description                 | Tests For                          |
| ------------------------------ | --------------------------- | ---------------------------------- |
| `test_cameras_routes.py`       | Camera CRUD routes          | `backend/api/routes/cameras.py`    |
| `test_detections_routes.py`    | Detection API routes        | `backend/api/routes/detections.py` |
| `test_detections_api.py`       | Detections API (additional) | Detection endpoints                |
| `test_events_routes.py`        | Event API routes            | `backend/api/routes/events.py`     |
| `test_events_api.py`           | Events API (additional)     | Event endpoints                    |
| `test_system_routes.py`        | System API routes           | `backend/api/routes/system.py`     |
| `test_logs_routes.py`          | Logs API routes             | `backend/api/routes/logs.py`       |
| `test_media_routes.py`         | Media file serving          | `backend/api/routes/media.py`      |
| `test_websocket_routes.py`     | WebSocket handlers          | `backend/api/routes/websocket.py`  |
| `test_websocket.py`            | WebSocket functionality     | WebSocket connections              |
| `test_websocket_validation.py` | WebSocket validation        | Message validation                 |
| `test_admin_api.py`            | Admin API routes            | Admin endpoints                    |
| `test_dlq_api.py`              | Dead letter queue API       | DLQ endpoints                      |
| `test_telemetry_api.py`        | Telemetry API               | Telemetry endpoints                |

### Middleware and Authentication

| File                      | Description               | Tests For                        |
| ------------------------- | ------------------------- | -------------------------------- |
| `test_auth_middleware.py` | Authentication middleware | `backend/api/middleware/auth.py` |
| `test_middleware.py`      | General middleware        | Request handling                 |

### Utility Components

| File                        | Description                    | Tests For           |
| --------------------------- | ------------------------------ | ------------------- |
| `test_dedupe.py`            | Deduplication logic            | Deduplication       |
| `test_retry_handler.py`     | Retry logic and error handling | Retry handler       |
| `test_benchmarks.py`        | Benchmark helper functions     | Benchmark utilities |
| `test_dockerfile_config.py` | Dockerfile configuration       | Docker config       |

## Key Test File Details

### `test_video_support.py` (NEW)

Tests for video file support in file watcher and detections API.

**Test Classes:**

- `TestVideoExtensionDetection`: Tests `is_video_file`, `is_supported_media_file`
- `TestGetMediaType`: Tests `get_media_type` function
- `TestVideoValidation`: Tests `is_valid_video`, `is_valid_media_file`
- `TestFileWatcherVideoProcessing`: Tests video processing in FileWatcher
- `TestVideoProcessor`: Tests VideoProcessor service
- `TestRangeHeaderParsing`: Tests HTTP Range header parsing
- `TestVideoStreamingEndpoint`: Tests video streaming API endpoint
- `TestVideoThumbnailEndpoint`: Tests video thumbnail API endpoint

**Coverage:**

- Video file extension detection (MP4, MKV, AVI, MOV)
- Video file validation (size checks, existence)
- Media type detection (image vs video)
- Video processing in file watcher queue
- Video streaming with range requests
- Video thumbnail generation and serving

### `test_config.py`

Tests for application configuration and settings management.

**Coverage:**

- Default configuration values (database_url, redis_url, API settings)
- Environment variable overrides for all settings
- Type coercion (strings to int, bool, list)
- Settings singleton pattern (caching behavior)
- Database URL validation and directory creation
- Edge cases (empty values, special characters, very long strings)

### `test_models.py`

Tests for SQLAlchemy database models.

**Coverage:**

- **Camera model**: Creation, defaults, status updates, relationships
- **Detection model**: Creation, bounding boxes, relationships, cascade deletes
- **Event model**: Risk scoring, LLM data, review status, cascade deletes
- **GPUStats model**: Time series data, partial data handling
- **Relationships**: One-to-many between Camera and Detections/Events
- **Queries**: Filtering by time, risk level, camera ID

### `test_file_watcher.py`

Tests for file system monitoring service.

**Coverage:**

- Image file validation (format, size, corruption detection)
- Video file validation (size checks)
- Camera directory structure parsing
- File event handling (create, modify)
- Debouncing to prevent duplicate processing
- Queue integration for detected files
- Path traversal security validation

### `test_batch_aggregator.py`

Tests for detection batch aggregation service.

**Coverage:**

- New batch creation when no active batch exists
- Adding detections to existing batches
- Batch timeout detection (90-second window)
- Idle timeout detection (30-second idle)
- Manual batch closing
- Analysis queue integration
- Concurrent camera batch handling

### `test_nemotron_analyzer.py`

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

### Test-specific fixtures (common patterns)

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

- **Total test files**: 42
- **Average execution time**: <10 seconds (unit tests only)
- **Coverage**: 98%+ for unit-tested components

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/integration/AGENTS.md` - Integration test patterns
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/tests/benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
