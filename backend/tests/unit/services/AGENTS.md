# Unit Tests - Services

## Purpose

The `backend/tests/unit/services/` directory contains unit tests for business logic services in `backend/services/`. Tests verify service behavior with mocked external dependencies.

## Directory Structure

```
backend/tests/unit/services/
├── AGENTS.md                          # This file
├── __init__.py                        # Package initialization
│
│ # AI Pipeline Services
├── test_batch_aggregator.py           # Detection batch aggregation
├── test_detector_client.py            # RT-DETRv2 HTTP client
├── test_file_watcher.py               # File system monitoring
├── test_nemotron_analyzer.py          # Nemotron LLM risk analysis
├── test_pipeline_worker.py            # AI pipeline worker
├── test_pipeline_workers.py           # Worker orchestration
│
│ # Enrichment and Vision Services
├── test_clip_client.py                # CLIP model client
├── test_clip_generator.py             # Video clip generation
├── test_clip_loader.py                # CLIP model loader
├── test_context_enricher.py           # Context enrichment
├── test_enrichment_client.py          # Enrichment client
├── test_enrichment_client_errors.py   # Enrichment error handling
├── test_enrichment_pipeline.py        # Enrichment pipeline
├── test_florence_client.py            # Florence model client
├── test_florence_extractor.py         # Florence feature extraction
├── test_florence_loader.py            # Florence model loader
├── test_vision_extractor.py           # Vision feature extraction
│
│ # Model Loaders
├── test_depth_anything_loader.py      # Depth estimation
├── test_fashion_clip_loader.py        # Fashion CLIP
├── test_image_quality_loader.py       # Image quality
├── test_model_zoo.py                  # Model zoo management
├── test_pet_classifier_loader.py      # Pet classifier
├── test_segformer_loader.py           # SegFormer segmentation
├── test_vehicle_classifier_loader.py  # Vehicle classifier
├── test_vehicle_damage_loader.py      # Vehicle damage
├── test_violence_loader.py            # Violence detection
├── test_vitpose_loader.py             # ViTPose pose estimation
├── test_weather_loader.py             # Weather classification
├── test_xclip_loader.py               # X-CLIP video model
├── test_yolo_world_loader.py          # YOLO World
│
│ # Broadcaster Services
├── test_event_broadcaster.py          # Event WebSocket broadcasting
├── test_system_broadcaster.py         # System status broadcasting
├── test_gpu_monitor.py                # GPU monitoring
│
│ # Alert and Notification
├── test_alert_dedup.py                # Alert deduplication
├── test_alert_engine.py               # Alert rule engine
├── test_notification.py               # Notification delivery
├── test_notification_webhook_ssrf.py  # Webhook SSRF prevention
│
│ # Other Services
├── test_audit.py                      # Audit logging
├── test_audit_service.py              # Audit service
├── test_baseline.py                   # Activity baseline
├── test_bbox_validation.py            # Bounding box validation
├── test_bbox_validation_integration.py# BBox integration
├── test_cache_service.py              # Cache service
├── test_circuit_breaker.py            # Circuit breaker pattern
├── test_cleanup_service.py            # Data cleanup
├── test_dedupe.py                     # Deduplication logic
├── test_dedup_key.py                  # Dedup key generation
├── test_degradation_manager.py        # Graceful degradation
├── test_face_detector.py              # Face detection
├── test_ocr_service.py                # OCR service
├── test_performance_collector.py      # Performance metrics
├── test_plate_detector.py             # License plate detection
├── test_prompt_formatters.py          # Prompt formatting
├── test_prompt_service.py             # Prompt service
├── test_prompts.py                    # Prompt templates
├── test_prompt_version_service.py     # Prompt versioning
├── test_reid_service.py               # Re-identification
├── test_retry_handler.py              # Retry logic
├── test_scene_baseline.py             # Scene baseline
├── test_scene_change_detector.py      # Scene change detection
├── test_search.py                     # Search functionality
├── test_service_managers.py           # Service lifecycle
├── test_severity.py                   # Severity classification
├── test_thumbnail_generator.py        # Thumbnail generation
├── test_video_processor.py            # Video processing
├── test_video_support.py              # Video detection/streaming
├── test_websocket_circuit_breaker.py  # WS circuit breaker
└── test_zone_service.py               # Zone management
```

## Test Files (71 files)

### AI Pipeline Services (6 files)

| File                        | Tests For                   |
| --------------------------- | --------------------------- |
| `test_batch_aggregator.py`  | Detection batch aggregation |
| `test_detector_client.py`   | RT-DETRv2 HTTP client       |
| `test_file_watcher.py`      | File system monitoring      |
| `test_nemotron_analyzer.py` | Nemotron LLM risk analysis  |
| `test_pipeline_worker.py`   | AI pipeline worker          |
| `test_pipeline_workers.py`  | Worker orchestration        |

### Enrichment and Vision (11 files)

| File                               | Tests For                 |
| ---------------------------------- | ------------------------- |
| `test_clip_client.py`              | CLIP model client         |
| `test_clip_generator.py`           | Video clip generation     |
| `test_clip_loader.py`              | CLIP model loader         |
| `test_context_enricher.py`         | Context enrichment        |
| `test_enrichment_client.py`        | Enrichment client         |
| `test_enrichment_client_errors.py` | Error handling            |
| `test_enrichment_pipeline.py`      | Enrichment pipeline       |
| `test_florence_client.py`          | Florence model client     |
| `test_florence_extractor.py`       | Feature extraction        |
| `test_florence_loader.py`          | Florence model loader     |
| `test_vision_extractor.py`         | Vision feature extraction |

### Model Loaders (13 files)

| File                                | Tests For               |
| ----------------------------------- | ----------------------- |
| `test_depth_anything_loader.py`     | Depth estimation        |
| `test_fashion_clip_loader.py`       | Fashion CLIP            |
| `test_image_quality_loader.py`      | Image quality           |
| `test_model_zoo.py`                 | Model zoo management    |
| `test_pet_classifier_loader.py`     | Pet classifier          |
| `test_segformer_loader.py`          | SegFormer segmentation  |
| `test_vehicle_classifier_loader.py` | Vehicle classifier      |
| `test_vehicle_damage_loader.py`     | Vehicle damage          |
| `test_violence_loader.py`           | Violence detection      |
| `test_vitpose_loader.py`            | ViTPose pose estimation |
| `test_weather_loader.py`            | Weather classification  |
| `test_xclip_loader.py`              | X-CLIP video model      |
| `test_yolo_world_loader.py`         | YOLO World              |

### Broadcaster Services (3 files)

| File                         | Tests For                    |
| ---------------------------- | ---------------------------- |
| `test_event_broadcaster.py`  | Event WebSocket broadcasting |
| `test_system_broadcaster.py` | System status broadcasting   |
| `test_gpu_monitor.py`        | GPU monitoring               |

### Alert and Notification (4 files)

| File                                | Tests For               |
| ----------------------------------- | ----------------------- |
| `test_alert_dedup.py`               | Alert deduplication     |
| `test_alert_engine.py`              | Alert rule engine       |
| `test_notification.py`              | Notification delivery   |
| `test_notification_webhook_ssrf.py` | Webhook SSRF prevention |

### Other Services (34 files)

Including audit, baseline, bbox validation, cache, circuit breaker, cleanup, dedupe, degradation, face detector, OCR, performance, plate detector, prompt services, re-identification, retry, scene, search, severity, thumbnail, video, and zone services.

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
    redis.add_to_queue_safe.return_value = QueueAddResult(success=True, queue_length=1)
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
