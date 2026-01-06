# End-to-End (E2E) Tests Directory

## Purpose

End-to-end tests validate the complete AI pipeline from file detection through event creation and WebSocket broadcasting. These tests use real business logic and database operations while mocking only external AI services (RT-DETRv2, Nemotron).

## Pipeline Flow Tested

```
File Upload -> Detection -> Batching -> Analysis -> Event Creation -> WebSocket Broadcast
   (1)          (2)          (3)         (4)           (5)              (6)
```

1. **File Detection**: Image/video file appears in camera folder
2. **RT-DETRv2 Detection**: Object detection service processes image
3. **Batch Aggregation**: Detections grouped into time-based batches
4. **Nemotron Analysis**: LLM analyzes batch and generates risk assessment
5. **Event Creation**: Event record created in database
6. **WebSocket Broadcast**: Event broadcast to connected clients

## Directory Structure

```
backend/tests/e2e/
├── AGENTS.md                      # This file
├── conftest.py                    # E2E-specific fixtures
├── __init__.py                    # Package initialization
├── README.md                      # E2E test documentation
├── TEST_SUMMARY.md                # Test execution summary
├── test_gpu_pipeline.py           # GPU pipeline E2E tests (36KB)
└── test_pipeline_integration.py   # Mocked pipeline E2E tests (24KB)
```

## Running Tests

```bash
# All E2E tests
pytest backend/tests/e2e/ -v

# With E2E marker
pytest backend/tests/e2e/ -v -m e2e

# Specific test file
pytest backend/tests/e2e/test_pipeline_integration.py -v

# GPU tests (requires running AI services)
pytest backend/tests/e2e/test_gpu_pipeline.py -v -m gpu

# With verbose debugging
pytest backend/tests/e2e/ -vv -s --log-cli-level=DEBUG

# With coverage
pytest backend/tests/e2e/ -v --cov=backend.services --cov-report=html
```

## Test Files (2 total)

### `test_pipeline_integration.py`

E2E pipeline tests with mocked AI services:

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

### `test_gpu_pipeline.py`

GPU-specific tests with real or mocked AI services:

| Test                                             | Description                          |
| ------------------------------------------------ | ------------------------------------ |
| `test_gpu_detector_client_health_check`          | RT-DETRv2 service health check       |
| `test_gpu_nemotron_analyzer_health_check`        | Nemotron LLM service health check    |
| `test_gpu_full_pipeline_with_real_services`      | Complete E2E with real AI services   |
| `test_gpu_detector_client_inference_performance` | RT-DETRv2 performance measurement    |
| `test_gpu_nemotron_analysis_performance`         | Nemotron LLM performance measurement |
| `test_detector_client_integration_mocked`        | DetectorClient with mocked HTTP      |
| `test_nemotron_analyzer_integration_mocked`      | NemotronAnalyzer with mocked HTTP    |
| `test_full_pipeline_integration_mocked`          | Complete pipeline with mocks         |
| `test_detector_unavailable_error_handling`       | Error handling for detector failures |
| `test_nemotron_llm_failure_fallback`             | Fallback when LLM fails              |
| `test_fast_path_analysis`                        | High-priority detection handling     |
| `test_batch_aggregation_and_handoff`             | Batch to analyzer handoff            |

## Fixtures

E2E tests use shared fixtures from `backend/tests/conftest.py`:

| Fixture          | Description                            |
| ---------------- | -------------------------------------- |
| `integration_db` | PostgreSQL database via testcontainers |
| `mock_redis`     | AsyncMock Redis client                 |
| `client`         | httpx AsyncClient for API testing      |

Test-specific fixtures in each file:

| Fixture                  | Description                               |
| ------------------------ | ----------------------------------------- |
| `test_camera`            | Creates test camera in database           |
| `test_image_path`        | Generates valid test JPEG image           |
| `mock_redis_client`      | In-memory Redis mock for batch operations |
| `mock_detector_response` | Mock RT-DETRv2 detection response         |
| `mock_nemotron_response` | Mock Nemotron LLM analysis response       |
| `clean_pipeline`         | Truncates all tables before test          |

## Mocking Strategy

### Mocked Components

- **RT-DETRv2 HTTP service**: `httpx.AsyncClient` for detector requests
- **Nemotron LLM HTTP service**: `httpx.AsyncClient` for LLM requests
- **Redis**: In-memory mock with queue and cache operations

### Real Components

- **PostgreSQL Database**: Real database via testcontainers
- **SQLAlchemy ORM**: Real database operations
- **Batch Aggregator**: Real business logic
- **Nemotron Analyzer**: Real analysis orchestration
- **Detector Client**: Real HTTP client logic

## Mock Redis Implementation

The E2E tests use an in-memory Redis mock:

```python
class MockRedisClient:
    def __init__(self):
        self._store: dict = {}
        self._queues: dict = {}

    async def get(self, key): return self._store.get(key)
    async def set(self, key, value, expire=None): self._store[key] = value
    async def delete(self, *keys): ...
    async def add_to_queue_safe(self, queue_name, data, **kwargs): ...
    async def get_from_queue(self, queue_name, timeout=0): ...
    async def publish(self, channel, message): return 1
```

## Test Data

### Camera

- ID: `e2e_test_camera` (or `unique_id("gpu_test_camera")`)
- Name: `E2E Test Camera`
- Folder Path: Temporary directory

### Test Image

- Format: JPEG
- Size: 640x480 (default), 1920x1080 (performance tests)
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

## Test Markers

| Marker                                              | Usage                          |
| --------------------------------------------------- | ------------------------------ |
| `@pytest.mark.e2e`                                  | E2E tests with mocked services |
| `@pytest.mark.gpu`                                  | Tests requiring GPU services   |
| `@pytest.mark.xdist_group(name="gpu_pipeline_e2e")` | Sequential execution group     |

## Coverage

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

## Troubleshooting

### Test fails with "Database not initialized"

- Use `integration_db` fixture in test parameters
- Check settings cache is cleared properly
- Verify environment variables set before `init_db()`

### Test fails with "Mock object has no attribute"

- Verify mock Redis client has all required methods
- Check `_client` internal mock is configured
- Ensure `_test_data` dict is attached for verification

### Test fails with "coroutine was never awaited"

- Ensure async methods are properly awaited
- Check mock response methods are MagicMock (not AsyncMock for .json())
- Verify async context managers use `async with`

### Timeout errors

- Verify batch timeout logic uses correct Redis keys
- Check `started_at` and `last_activity` are set properly
- Ensure time.time() is mocked if testing specific timeouts

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/gpu/AGENTS.md` - GPU-specific tests
- `/backend/services/AGENTS.md` - Services architecture
- `/backend/AGENTS.md` - Backend architecture
