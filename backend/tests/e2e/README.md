# End-to-End (E2E) Pipeline Integration Tests

This directory contains comprehensive end-to-end tests for the complete AI pipeline, validating the integration of all major components from file detection through event creation and WebSocket broadcasting.

## Overview

The E2E tests validate the full pipeline flow:

```
File Upload → Detection → Batching → Analysis → Event Creation → WebSocket Broadcast
   (1)          (2)         (3)         (4)         (5)              (6)
```

1. **File Detection**: Image file appears in camera folder
2. **YOLO26 Detection**: Object detection service processes image
3. **Batch Aggregation**: Detections are grouped into time-based batches
4. **Nemotron Analysis**: LLM analyzes batch and generates risk assessment
5. **Event Creation**: Event record is created in database
6. **WebSocket Broadcast**: Event is broadcast to connected clients

## Test Files

### `test_pipeline_integration.py`

Comprehensive E2E pipeline tests covering:

- **Complete pipeline flow**: Full end-to-end flow with all components
- **Multiple detections in batch**: Batch aggregation with multiple detections
- **Batch timeout logic**: Window and idle timeout behavior
- **Low confidence filtering**: Confidence threshold filtering
- **Detector failure handling**: Graceful degradation when YOLO26 fails
- **Nemotron failure handling**: Fallback behavior when LLM fails
- **Event relationships**: Database relationships between cameras, detections, and events
- **Cleanup**: Proper cleanup of Redis batch data after processing

## Running Tests

### Run all E2E tests

```bash
pytest backend/tests/e2e/test_pipeline_integration.py -v
```

### Run with E2E marker filter

```bash
pytest backend/tests/e2e/test_pipeline_integration.py -v -m e2e
```

### Run specific test

```bash
pytest backend/tests/e2e/test_pipeline_integration.py::test_complete_pipeline_flow_with_mocked_services -v
```

### Run from project root

```bash
# All E2E tests
pytest backend/tests/e2e/ -v

# With marker
pytest -m e2e -v
```

## Test Architecture

### Fixtures

#### `integration_db` (conftest.py)

- Creates isolated temporary SQLite database
- Initializes database schema
- Cleans up after test completion
- Ensures no test pollution

#### `test_camera` (test_pipeline_integration.py)

- Creates a test camera in the database
- Used across multiple tests
- Properly linked to detections and events

#### `test_image_path` (test_pipeline_integration.py)

- Generates a valid test image file
- Uses PIL to create a simple RGB image
- Saved as JPEG format

#### `mock_redis_client` (test_pipeline_integration.py)

- In-memory Redis mock with all required methods
- Tracks batch data in Python dict
- Supports `get`, `set`, `delete`, `add_to_queue_safe`, `publish`, `keys`
- Provides `_test_data` for test verification

#### `mock_detector_response` (test_pipeline_integration.py)

- Mock YOLO26 detection response
- Contains person and car detections with bounding boxes

#### `mock_nemotron_response` (test_pipeline_integration.py)

- Mock Nemotron LLM analysis response
- Contains risk score, level, summary, and reasoning

### Mocking Strategy

The E2E tests use **targeted mocking** to isolate external dependencies while testing real integration logic:

#### Mocked Components

- **YOLO26 HTTP service**: `httpx.AsyncClient` for detector requests
- **Nemotron LLM HTTP service**: `httpx.AsyncClient` for LLM requests
- **Redis**: In-memory mock for queue and cache operations

#### Real Components

- **SQLite Database**: Real database with temporary file
- **SQLAlchemy ORM**: Real database operations and sessions
- **Batch Aggregator**: Real business logic
- **Nemotron Analyzer**: Real analysis orchestration
- **Detector Client**: Real HTTP client logic (with mocked responses)

This approach provides:

- **Realistic testing**: Tests use actual database and business logic
- **Isolation**: External services don't need to be running
- **Speed**: Tests run fast without network calls
- **Reliability**: Tests don't fail due to external service issues

## Test Coverage

### Happy Path Testing

- ✅ Complete pipeline flow from detection to event creation
- ✅ Multiple detections aggregated into single batch
- ✅ Batch timeout logic (window and idle timeouts)
- ✅ Event relationships with cameras and detections
- ✅ WebSocket broadcast of events

### Error Handling Testing

- ✅ Detector service unavailable (connection errors)
- ✅ Nemotron service unavailable (LLM errors)
- ✅ Low confidence detections filtered out
- ✅ Graceful fallback to default risk scores
- ✅ Empty detection lists handled

### Data Integrity Testing

- ✅ Redis batch data cleaned up after processing
- ✅ Database detection records persist
- ✅ Database event records persist
- ✅ Detection IDs stored in events
- ✅ Relationships between models work correctly

## Key Testing Patterns

### 1. Async Test Structure

All tests use `@pytest.mark.asyncio` for async/await support:

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_pipeline_flow(integration_db, test_camera, ...):
    # Test implementation
    pass
```

### 2. Database Session Management

Tests use context managers for database sessions:

```python
async with get_session() as session:
    # Database operations
    await session.commit()
    await session.refresh(model)
```

### 3. Mock HTTP Responses

HTTP responses are mocked using `unittest.mock`:

```python
with patch("httpx.AsyncClient") as mock_http_client:
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=expected_data)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http_client.return_value.__aenter__.return_value = mock_client
```

### 4. Batch Data Verification

Tests verify batch data in Redis mock:

```python
assert analysis_queue_key in mock_redis_client._test_data
assert len(mock_redis_client._test_data[analysis_queue_key]) == 1
```

### 5. Event Broadcasting Verification

Tests verify WebSocket broadcasts were called:

```python
mock_redis_client.publish.assert_called()
publish_calls = mock_redis_client.publish.call_args_list
assert len(publish_calls) > 0
```

## Test Data

### Camera

- ID: `e2e_test_camera`
- Name: `E2E Test Camera`
- Folder Path: `/tmp/e2e_test_camera`

### Test Image

- Format: JPEG
- Size: 640x480
- Color: RGB (100, 150, 200)

### Mock Detections

- Person: confidence 0.95, bbox [100, 150, 200, 300]
- Car: confidence 0.88, bbox [400, 200, 250, 180]

### Mock Risk Assessment

- Risk Score: 75
- Risk Level: high
- Summary: "Person and vehicle detected near entrance"

## Debugging

### Enable verbose logging

```bash
pytest backend/tests/e2e/ -v -s --log-cli-level=DEBUG
```

### Run with pdb debugger

```bash
pytest backend/tests/e2e/ -v --pdb
```

### Check coverage

```bash
pytest backend/tests/e2e/ -v --cov=backend.services --cov-report=html
```

## Common Issues

### Test fails with "Database not initialized"

- Ensure `integration_db` fixture is included in test parameters
- Check that settings cache is cleared properly

### Test fails with "Mock object has no attribute"

- Verify mock Redis client has all required methods
- Check that `_client` internal mock is configured

### Test fails with "coroutine was never awaited"

- Ensure async methods are properly awaited
- Check mock response methods are not AsyncMock

### Timeout errors

- Verify batch timeout logic uses correct Redis keys
- Check that `started_at` and `last_activity` are set properly

## Integration with Phase 8

These E2E tests fulfill **Phase 8, Task .3** of the project roadmap:

- ✅ Created comprehensive E2E pipeline integration tests
- ✅ Tests cover full flow from detection to event creation
- ✅ Mocks external services (YOLO26, Nemotron)
- ✅ Verifies batch aggregation logic
- ✅ Validates error handling and fallbacks
- ✅ Tests WebSocket broadcasting
- ✅ Verifies data cleanup

## Next Steps

After E2E tests are passing, proceed to:

1. **Integration testing** with real services (if available)
2. **Load testing** with multiple concurrent detections
3. **Performance profiling** of batch aggregation
4. **End-to-end manual testing** with actual cameras
5. **Deployment verification** in staging environment

## Related Documentation

- `/backend/services/AGENTS.md` - Services architecture overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/integration/README.md` - Integration tests documentation
- `/CLAUDE.md` - Project instructions and phase overview
