# Unit Tests Directory

## Purpose

Unit tests verify individual components in isolation. Each test focuses on a single function, class, or module without dependencies on external services. All external dependencies (Redis, HTTP, file system) are mocked.

## Directory Structure

```
backend/tests/unit/
├── AGENTS.md                  # This file
├── __init__.py                # Package initialization
├── .gitkeep                   # Directory placeholder
├── test_websocket_README.md   # WebSocket testing documentation
└── test_*.py                  # Test files (56 total)
```

## Running Tests

```bash
# All unit tests
pytest backend/tests/unit/ -v

# Single test file
pytest backend/tests/unit/test_config.py -v

# Specific test class
pytest backend/tests/unit/test_config.py::TestSettings -v

# Specific test
pytest backend/tests/unit/test_config.py::TestSettings::test_defaults -v

# With coverage
pytest backend/tests/unit/ -v --cov=backend --cov-report=html

# Fast execution (no coverage)
pytest backend/tests/unit/ -v --no-cov
```

## Test Files (56 total)

### Core Components

| File              | Tests For                                                    |
| ----------------- | ------------------------------------------------------------ |
| `test_config.py`  | `backend/core/config.py` - Settings, env vars, type coercion |
| `test_redis.py`   | `backend/core/redis.py` - Redis client operations            |
| `test_logging.py` | `backend/core/logging.py` - Structured logging               |
| `test_metrics.py` | `backend/core/metrics.py` - Metrics collection               |

### Database Models

| File                | Tests For               |
| ------------------- | ----------------------- |
| `test_log_model.py` | `backend/models/log.py` |

### AI Services

| File                          | Tests For                                      |
| ----------------------------- | ---------------------------------------------- |
| `test_file_watcher.py`        | File system monitoring, image/video validation |
| `test_detector_client.py`     | RT-DETRv2 HTTP client                          |
| `test_batch_aggregator.py`    | Detection batch aggregation, timeouts          |
| `test_nemotron_analyzer.py`   | Nemotron LLM risk analysis                     |
| `test_thumbnail_generator.py` | Thumbnail generation with bounding boxes       |
| `test_video_support.py`       | Video detection, validation, streaming         |
| `test_video_processor.py`     | Video processing service                       |
| `test_pipeline_worker.py`     | AI pipeline worker                             |
| `test_pipeline_workers.py`    | Worker orchestration                           |
| `test_clip_generator.py`      | Video clip generation                          |

### Broadcaster Services

| File                         | Tests For                    |
| ---------------------------- | ---------------------------- |
| `test_event_broadcaster.py`  | Event WebSocket broadcasting |
| `test_system_broadcaster.py` | System status broadcasting   |
| `test_gpu_monitor.py`        | GPU monitoring service       |
| `test_cleanup_service.py`    | Data cleanup service         |
| `test_health_monitor.py`     | Health monitoring            |
| `test_service_managers.py`   | Service lifecycle management |

### API Routes

| File                           | Tests For                     |
| ------------------------------ | ----------------------------- |
| `test_cameras_routes.py`       | `/api/cameras/*` endpoints    |
| `test_detections_routes.py`    | `/api/detections/*` endpoints |
| `test_detections_api.py`       | Detection API (additional)    |
| `test_events_routes.py`        | `/api/events/*` endpoints     |
| `test_events_api.py`           | Events API (additional)       |
| `test_system_routes.py`        | `/api/system/*` endpoints     |
| `test_logs_routes.py`          | `/api/logs/*` endpoints       |
| `test_media_routes.py`         | `/api/media/*` endpoints      |
| `test_websocket_routes.py`     | WebSocket handlers            |
| `test_websocket.py`            | WebSocket functionality       |
| `test_websocket_validation.py` | Message validation            |
| `test_admin_api.py`            | Admin endpoints               |
| `test_dlq_api.py`              | Dead letter queue endpoints   |
| `test_telemetry_api.py`        | Telemetry endpoints           |
| `test_zones_routes.py`         | Zone CRUD endpoints           |

### Middleware and Security

| File                          | Tests For                 |
| ----------------------------- | ------------------------- |
| `test_auth_middleware.py`     | Authentication middleware |
| `test_middleware.py`          | Request handling          |
| `test_circuit_breaker.py`     | Circuit breaker pattern   |
| `test_degradation_manager.py` | Graceful degradation      |
| `test_rate_limit.py`          | Rate limiting             |
| `test_tls.py`                 | TLS/SSL configuration     |

### Alert System

| File                   | Tests For             |
| ---------------------- | --------------------- |
| `test_alert_dedup.py`  | Alert deduplication   |
| `test_notification.py` | Notification delivery |

### Utility Components

| File                              | Tests For                  |
| --------------------------------- | -------------------------- |
| `test_audit.py`                   | Audit logging              |
| `test_baseline.py`                | Baseline detection         |
| `test_dedupe.py`                  | Deduplication logic        |
| `test_search.py`                  | Search functionality       |
| `test_zone_service.py`            | Zone management            |
| `test_severity.py`                | Severity classification    |
| `test_retry_handler.py`           | Retry logic                |
| `test_mime_types.py`              | MIME type detection        |
| `test_migrate_sqlite_postgres.py` | Database migration         |
| `test_dockerfile_config.py`       | Docker configuration       |
| `test_benchmarks.py`              | Benchmark utilities        |
| `test_performance_collector.py`   | Performance data collector |
| `test_performance_schemas.py`     | Performance schema models  |

## Common Fixtures

From `backend/tests/conftest.py`:

| Fixture                | Description                                    |
| ---------------------- | ---------------------------------------------- |
| `isolated_db`          | Temporary PostgreSQL database with clean state |
| `test_db`              | Database session factory                       |
| `reset_settings_cache` | Auto-clears settings cache (autouse)           |

Test-specific fixtures (common patterns):

| Fixture             | Description                           |
| ------------------- | ------------------------------------- |
| `engine`            | In-memory SQLite engine               |
| `session`           | Database session with rollback        |
| `mock_redis_client` | Mocked Redis with common operations   |
| `mock_session`      | Mocked database session               |
| `temp_camera_root`  | Temporary camera directory            |
| `sample_detections` | Pre-built detection objects           |
| `mock_http_client`  | Mocked httpx AsyncClient              |
| `clean_env`         | Isolated environment for config tests |

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
with patch("httpx.AsyncClient") as mock_http:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http.return_value.__aenter__.return_value = mock_client
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

Group related tests in classes with descriptive names:

```python
class TestConfigSettings:
    def test_default_values(self, clean_env):
        settings = get_settings()
        assert settings.database_url is not None
        assert settings.redis_url is not None
```

### 2. Fixture Usage

Use `isolated_db` for database operations (most unit tests use mocks instead):

```python
@pytest.fixture
def mock_redis_client():
    mock = AsyncMock(spec=RedisClient)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    return mock
```

### 3. Mocking at Boundaries

Mock at the boundary, not internal functions:

```python
# Good: Mock at boundary
with patch("httpx.AsyncClient") as mock_http:
    # Test code

# Bad: Mock internal function (tests implementation, not behavior)
with patch("backend.services.detector_client._parse_response"):
    # Too granular
```

### 4. Error Testing

Test both success and failure paths:

```python
@pytest.mark.asyncio
async def test_handles_connection_error():
    with patch("httpx.AsyncClient.post", side_effect=ConnectionError):
        result = await detector.detect_objects("test.jpg", "cam1", session)
        assert result == []  # Graceful failure
```

### 5. Async Testing

Always use `@pytest.mark.asyncio` decorator:

```python
@pytest.mark.asyncio
async def test_async_operation(isolated_db):
    async with get_session() as session:
        result = await some_async_function(session)
        assert result is not None
```

## Coverage Goals

- **Target**: 98%+ for unit-tested components
- **Focus areas**:
  - Happy path (normal operation)
  - Error conditions (exceptions, timeouts)
  - Edge cases (empty lists, None values)
  - Validation logic (input validation)

## Troubleshooting

### Import Errors

Backend path is auto-added in conftest.py. Check module names match file structure.

### Async Errors

Add `@pytest.mark.asyncio` decorator. Ensure all async functions are awaited.

### Mock Not Working

Verify mock path matches import path in source:

```python
# Correct: Match import path in source
with patch("backend.services.detector_client.httpx.AsyncClient"):
    # Works

# Incorrect: Wrong path
with patch("httpx.AsyncClient"):
    # May not work if imported differently
```

### Database Tests Fail

Use `isolated_db` fixture. Clear settings cache with `get_settings.cache_clear()`.

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/integration/AGENTS.md` - Integration test patterns
- `/backend/AGENTS.md` - Backend architecture
