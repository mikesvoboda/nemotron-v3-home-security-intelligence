# End-to-End (E2E) Pipeline Integration Tests

## Purpose

This directory contains comprehensive end-to-end tests for the complete AI pipeline, validating the integration of all major components from file detection through event creation and WebSocket broadcasting. E2E tests use real business logic and database operations while mocking only external AI services.

## Overview

The E2E tests validate the full pipeline flow:

```
File Upload -> Detection -> Batching -> Analysis -> Event Creation -> WebSocket Broadcast
   (1)          (2)          (3)         (4)           (5)              (6)
```

1. **File Detection**: Image/video file appears in camera folder
2. **RT-DETRv2 Detection**: Object detection service processes image
3. **Batch Aggregation**: Detections are grouped into time-based batches
4. **Nemotron Analysis**: LLM analyzes batch and generates risk assessment
5. **Event Creation**: Event record is created in database
6. **WebSocket Broadcast**: Event is broadcast to connected clients

## Test Files

| File                           | Description                            |
| ------------------------------ | -------------------------------------- |
| `conftest.py`                  | E2E-specific fixtures (integration_db) |
| `test_pipeline_integration.py` | Comprehensive E2E pipeline tests       |
| `README.md`                    | Additional E2E documentation           |
| `TEST_SUMMARY.md`              | Test execution summary                 |

### `conftest.py`

E2E-specific fixtures for pipeline tests.

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

| Test                                                | Description                                   |
| --------------------------------------------------- | --------------------------------------------- |
| `test_complete_pipeline_flow_with_mocked_services`  | Complete E2E flow testing all components      |
| `test_pipeline_with_multiple_detections_in_batch`   | Batch aggregation with multiple detections    |
| `test_pipeline_batch_timeout_logic`                 | Batch timeout behavior (90s window, 30s idle) |
| `test_pipeline_with_low_confidence_filtering`       | Confidence threshold filtering                |
| `test_pipeline_handles_detector_failure_gracefully` | Detector service failure handling             |
| `test_pipeline_handles_nemotron_failure_gracefully` | LLM service failure handling                  |
| `test_pipeline_event_relationships`                 | Database relationships                        |
| `test_pipeline_cleanup_after_processing`            | Cleanup behavior verification                 |

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
  - Supports all required methods (get, set, delete, add_to_queue, publish, scan_iter)

#### Real Components

- **SQLite Database**: Real database with temporary file
- **SQLAlchemy ORM**: Real database operations and sessions
- **Batch Aggregator**: Real business logic (batch_aggregator.py)
- **Nemotron Analyzer**: Real analysis orchestration (nemotron_analyzer.py)
- **Detector Client**: Real HTTP client logic (detector_client.py)

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

    async def mock_set(key, value, expire=None):
        batch_data[key] = value

    async def mock_delete(*keys):
        for key in keys:
            batch_data.pop(key, None)

    async def mock_add_to_queue(queue_name, item):
        queue_key = f"queue:{queue_name}"
        if queue_key not in batch_data:
            batch_data[queue_key] = []
        batch_data[queue_key].append(item)

    # ... more methods

    # Store batch_data for test verification
    mock_redis._test_data = batch_data

    return mock_redis
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
