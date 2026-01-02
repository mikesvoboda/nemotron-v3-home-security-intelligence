# Unit Tests - Services

## Purpose

The `backend/tests/unit/services/` directory contains unit tests for business logic services in `backend/services/`. Tests verify service behavior with mocked external dependencies.

## Test Files (4 files)

| File                            | Tests For                     | Test Count |
| ------------------------------- | ----------------------------- | ---------- |
| `test_alert_engine.py`          | Alert rule engine             | ~50 tests  |
| `test_baseline.py`              | Activity baseline service     | ~30 tests  |
| `test_performance_collector.py` | Performance metrics collector | ~25 tests  |

## Additional Service Tests (in parent directory)

Many service tests are in `backend/tests/unit/` directly:

| File                          | Tests For                    |
| ----------------------------- | ---------------------------- |
| `test_file_watcher.py`        | File system monitoring       |
| `test_detector_client.py`     | RT-DETRv2 HTTP client        |
| `test_batch_aggregator.py`    | Detection batch aggregation  |
| `test_nemotron_analyzer.py`   | Nemotron LLM risk analysis   |
| `test_event_broadcaster.py`   | Event WebSocket broadcasting |
| `test_system_broadcaster.py`  | System status broadcasting   |
| `test_gpu_monitor.py`         | GPU monitoring service       |
| `test_cleanup_service.py`     | Data cleanup service         |
| `test_health_monitor.py`      | Health monitoring            |
| `test_thumbnail_generator.py` | Thumbnail generation         |
| `test_video_processor.py`     | Video processing             |
| `test_clip_generator.py`      | Video clip generation        |
| `test_pipeline_worker.py`     | AI pipeline worker           |
| `test_zone_service.py`        | Zone management              |
| `test_notification.py`        | Notification delivery        |
| `test_retry_handler.py`       | Retry logic                  |

## Test Categories

### Alert Engine Tests (`test_alert_engine.py`)

- Rule condition evaluation
- Risk threshold matching
- Object type filtering
- Camera ID filtering
- Zone matching
- Schedule-based conditions
- Cooldown and deduplication
- Alert generation

### Baseline Tests (`test_baseline.py`)

- Activity rate calculation
- Hourly/daily patterns
- Anomaly detection
- Baseline updates
- Exponential decay handling

### Performance Collector Tests (`test_performance_collector.py`)

- Metric collection
- GPU stats aggregation
- Host system metrics
- AI service metrics
- Time-series data handling

## Running Tests

```bash
# Run all service unit tests
pytest backend/tests/unit/services/ -v
pytest backend/tests/unit/test_*_service.py -v
pytest backend/tests/unit/test_*_monitor.py -v
pytest backend/tests/unit/test_*_broadcaster.py -v

# Run specific service tests
pytest backend/tests/unit/services/test_alert_engine.py -v

# Run with coverage
pytest backend/tests/unit/services/ -v --cov=backend/services
```

## Common Mocking Patterns

### Mocking Redis

```python
@pytest.fixture
def mock_redis():
    redis = AsyncMock(spec=RedisClient)
    redis.get.return_value = None
    redis.set.return_value = True
    redis.publish.return_value = True
    redis.add_to_queue.return_value = True
    return redis
```

### Mocking HTTP Client (for AI services)

```python
@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"result": "success"}
    client.post.return_value = response
    return client
```

### Mocking Database Session

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

## Testing Patterns

### Testing Async Services

```python
@pytest.mark.asyncio
async def test_process_detection(mock_redis, mock_session):
    service = DetectorClient(redis=mock_redis)
    result = await service.detect_objects(
        image_path="/path/to/image.jpg",
        camera_id="test_cam",
        session=mock_session,
    )
    assert result is not None
```

### Testing Background Tasks

```python
@pytest.mark.asyncio
async def test_background_processing(mock_redis):
    service = BatchAggregator(redis=mock_redis)

    # Start processing
    task = asyncio.create_task(service.process_batches())

    # Allow some processing
    await asyncio.sleep(0.1)

    # Cancel and verify
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
```

## Related Documentation

- `/backend/services/AGENTS.md` - Service documentation
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/AGENTS.md` - Test infrastructure overview
