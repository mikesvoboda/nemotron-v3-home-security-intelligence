# End-to-End (E2E) Pipeline Integration Tests

## Purpose

This directory contains comprehensive end-to-end tests for the complete AI pipeline, validating the integration of all major components from file detection through event creation and WebSocket broadcasting. E2E tests use real business logic and database operations while mocking only external AI services.

## Overview

The E2E tests validate the full pipeline flow:

```
File Upload -> Detection -> Batching -> Analysis -> Event Creation -> WebSocket Broadcast
   (1)          (2)          (3)         (4)           (5)              (6)
```

1. **File Detection**: Image file appears in camera folder
2. **RT-DETRv2 Detection**: Object detection service processes image
3. **Batch Aggregation**: Detections are grouped into time-based batches
4. **Nemotron Analysis**: LLM analyzes batch and generates risk assessment
5. **Event Creation**: Event record is created in database
6. **WebSocket Broadcast**: Event is broadcast to connected clients

## Test Files

### `conftest.py`

Shared fixtures for E2E pipeline tests.

**Fixtures:**

- `integration_db`: Creates isolated temporary SQLite database for E2E tests
  - Sets DATABASE_URL and REDIS_URL environment variables
  - Initializes database schema
  - Cleans up after test completion
  - Restores original environment state

**Usage:**

```python
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_flow(integration_db):
    # Test code with real database
    pass
```

### `test_pipeline_integration.py`

Comprehensive end-to-end pipeline tests covering the complete AI flow.

**Test Fixtures:**

- `test_camera`: Creates test camera in database
- `test_image_path`: Generates valid test JPEG image (640x480)
- `mock_redis_client`: In-memory Redis mock with all required methods
- `mock_detector_response`: Mock RT-DETRv2 detection response (person, car)
- `mock_nemotron_response`: Mock Nemotron LLM analysis response

**Tests:**

#### 1. `test_complete_pipeline_flow_with_mocked_services`

Complete end-to-end flow testing all components working together.

**Steps:**

1. Mock RT-DETRv2 detector response
2. Process image through detector (creates Detection records)
3. Add detections to batch aggregator
4. Verify batch metadata in Redis
5. Close batch and queue for analysis
6. Mock Nemotron LLM response
7. Run analyzer to create Event
8. Verify event in database
9. Verify WebSocket broadcast

**Validates:**

- Detection creation and database persistence
- Batch aggregation logic
- Redis metadata management
- LLM analysis and risk scoring
- Event creation with relationships
- WebSocket broadcasting

#### 2. `test_pipeline_with_multiple_detections_in_batch`

Tests batch aggregation with multiple detections.

**Validates:**

- Multiple detections aggregated into single batch
- Batch window logic works correctly
- All detections included in final event
- Detection count accuracy

#### 3. `test_pipeline_batch_timeout_logic`

Tests batch timeout behavior.

**Validates:**

- Batch window timeout (90 seconds)
- Idle timeout (30 seconds)
- Proper batch closure and queuing
- Timeout detection mechanism

#### 4. `test_pipeline_with_low_confidence_filtering`

Tests confidence threshold filtering.

**Validates:**

- Low confidence detections filtered (< 0.5 threshold)
- Only high-confidence detections stored
- Filtering happens at detection stage

#### 5. `test_pipeline_handles_detector_failure_gracefully`

Tests detector service failure handling.

**Validates:**

- Connection errors handled gracefully
- Empty detection list returned on failure
- Pipeline continues without crashing
- No database corruption on failure

#### 6. `test_pipeline_handles_nemotron_failure_gracefully`

Tests LLM service failure handling.

**Validates:**

- LLM connection errors handled
- Fallback risk data used (risk_score=50, level="medium")
- Event still created with default values
- Summary indicates analysis unavailable

#### 7. `test_pipeline_event_relationships`

Tests database relationships.

**Validates:**

- Events properly linked to cameras
- Detection IDs stored in events
- Relationships can be queried
- Foreign key integrity maintained

#### 8. `test_pipeline_cleanup_after_processing`

Tests cleanup behavior.

**Validates:**

- Batch metadata removed from Redis after close
- Detection data persists in database
- Event data persists in database
- No memory leaks or stale data

## Running E2E Tests

### Run all E2E tests

```bash
pytest backend/tests/e2e/test_pipeline_integration.py -v
```

### Run with E2E marker filter

```bash
pytest backend/tests/e2e/test_pipeline_integration.py -v -m e2e

# Or from anywhere:
pytest -m e2e -v
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

### Run with verbose debugging

```bash
pytest backend/tests/e2e/ -vv -s --log-cli-level=DEBUG
```

### Run with coverage

```bash
pytest backend/tests/e2e/ -v --cov=backend.services --cov-report=html
```

## Test Architecture

### Mocking Strategy

The E2E tests use **targeted mocking** to isolate external dependencies while testing real integration logic:

#### Mocked Components

- **RT-DETRv2 HTTP service**: `httpx.AsyncClient` for detector requests
  - Mocked to avoid requiring actual RT-DETRv2 server
  - Returns realistic detection responses
- **Nemotron LLM HTTP service**: `httpx.AsyncClient` for LLM requests
  - Mocked to avoid requiring actual Nemotron server
  - Returns realistic risk analysis responses
- **Redis**: In-memory mock for queue and cache operations
  - Tracks batch data in Python dict
  - Supports all required methods

#### Real Components

- **SQLite Database**: Real database with temporary file
- **SQLAlchemy ORM**: Real database operations and sessions
- **Batch Aggregator**: Real business logic (batch_aggregator.py)
- **Nemotron Analyzer**: Real analysis orchestration (nemotron_analyzer.py)
- **Detector Client**: Real HTTP client logic (detector_client.py)

This approach provides:

- **Realistic testing**: Tests use actual database and business logic
- **Isolation**: External services don't need to be running
- **Speed**: Tests run fast without network calls
- **Reliability**: Tests don't fail due to external service issues

### Mock Redis Implementation

The mock Redis client provides an in-memory implementation:

```python
@pytest.fixture
async def mock_redis_client():
    mock_redis = AsyncMock(spec=RedisClient)

    # Track batch data in memory
    batch_data = {}

    async def mock_get(key):
        return batch_data.get(key)

    async def mock_set(key, value):
        batch_data[key] = value

    async def mock_delete(*keys):
        for key in keys:
            batch_data.pop(key, None)

    async def mock_add_to_queue(queue_name, item):
        queue_key = f"queue:{queue_name}"
        if queue_key not in batch_data:
            batch_data[queue_key] = []
        batch_data[queue_key].append(item)

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.set = AsyncMock(side_effect=mock_set)
    # ...

    # Store batch_data for test verification
    mock_redis._test_data = batch_data

    return mock_redis
```

### Mock HTTP Responses

HTTP responses are mocked using `unittest.mock`:

```python
with patch("httpx.AsyncClient") as mock_http_client:
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=expected_data)
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http_client.return_value.__aenter__.return_value = mock_client
```

## Test Coverage

### Happy Path Testing

- Complete pipeline flow from detection to event creation
- Multiple detections aggregated into single batch
- Batch timeout logic (window and idle timeouts)
- Event relationships with cameras and detections
- WebSocket broadcast of events

### Error Handling Testing

- Detector service unavailable (connection errors)
- Nemotron service unavailable (LLM errors)
- Low confidence detections filtered out
- Graceful fallback to default risk scores
- Empty detection lists handled

### Data Integrity Testing

- Redis batch data cleaned up after processing
- Database detection records persist
- Database event records persist
- Detection IDs stored in events
- Relationships between models work correctly

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

### 3. Batch Data Verification

Tests verify batch data in Redis mock:

```python
assert analysis_queue_key in mock_redis_client._test_data
assert len(mock_redis_client._test_data[analysis_queue_key]) == 1
```

### 4. Event Broadcasting Verification

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
- Folder Path: `/tmp/e2e_test_camera` (temporary)

### Test Image

- Format: JPEG
- Size: 640x480
- Color: RGB (100, 150, 200)
- Created with PIL

### Mock Detections

- **Person**: confidence 0.95, bbox [100, 150, 200, 300]
- **Car**: confidence 0.88, bbox [400, 200, 250, 180]

### Mock Risk Assessment

- Risk Score: 75
- Risk Level: high
- Summary: "Person and vehicle detected near entrance"
- Reasoning: "Multiple detections indicate potential security concern"

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

### Inspect mock data

```python
# In test, after operations:
print("Batch data:", mock_redis_client._test_data)
print("Publish calls:", mock_redis_client.publish.call_args_list)
```

## Common Issues

### Test fails with "Database not initialized"

- Ensure `integration_db` fixture is included in test parameters
- Check that settings cache is cleared properly
- Verify environment variables set before `init_db()`

### Test fails with "Mock object has no attribute"

- Verify mock Redis client has all required methods
- Check that `_client` internal mock is configured
- Ensure `_test_data` dict is attached for verification

### Test fails with "coroutine was never awaited"

- Ensure async methods are properly awaited
- Check mock response methods are not AsyncMock (should be MagicMock)
- Verify async context managers use `async with`

### Timeout errors

- Verify batch timeout logic uses correct Redis keys
- Check that `started_at` and `last_activity` are set properly
- Ensure time.time() is mocked if testing specific timeouts

## Integration with Project Phases

These E2E tests fulfill **Phase 8, Task 8.3** of the project roadmap:

- Created comprehensive E2E pipeline integration tests
- Tests cover full flow from detection to event creation
- Mocks external services (RT-DETRv2, Nemotron)
- Verifies batch aggregation logic
- Validates error handling and fallbacks
- Tests WebSocket broadcasting
- Verifies data cleanup

## Next Steps

After E2E tests are passing, proceed to:

1. **Integration testing** with real services (if available)
   - Run RT-DETRv2 server locally
   - Run Nemotron LLM server locally
   - Test with actual AI inference
2. **Load testing** with multiple concurrent detections
   - Multiple cameras detecting simultaneously
   - Batch aggregation under load
   - Database performance validation
3. **Performance profiling** of batch aggregation
   - Identify bottlenecks
   - Optimize Redis operations
   - Tune batch timeout values
4. **End-to-end manual testing** with actual cameras
   - Connect real Foscam cameras
   - Upload real images via FTP
   - Verify entire pipeline in production-like environment
5. **Deployment verification** in staging environment
   - Docker deployment
   - Service orchestration
   - Health monitoring

## Test Statistics

- **Total test files**: 1 (test_pipeline_integration.py)
- **Total test cases**: 8+ comprehensive E2E scenarios
- **Coverage**: Validates all major pipeline components
- **Execution time**: <10 seconds (all mocked services)
- **Markers**: `@pytest.mark.e2e` for filtering

## Test Philosophy

E2E tests strike a balance between:

- **Comprehensiveness**: Test complete workflows, not just isolated units
- **Speed**: Mock slow external services for fast execution
- **Realism**: Use real business logic and database operations
- **Reliability**: Tests should pass consistently without flakiness
- **Maintainability**: Clear test structure and descriptive names

## Related Documentation

- `/backend/services/AGENTS.md` - Services architecture overview
- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/integration/AGENTS.md` - Integration tests documentation
- `/backend/tests/benchmarks/AGENTS.md` - Performance benchmarks
- `/backend/tests/e2e/README.md` - Additional E2E test documentation
- `/CLAUDE.md` - Project instructions and phase overview
