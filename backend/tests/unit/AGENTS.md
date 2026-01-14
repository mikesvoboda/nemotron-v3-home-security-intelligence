# Unit Tests Directory

## Purpose

Unit tests verify individual components in isolation. Each test focuses on a single function, class, or module without dependencies on external services. All external dependencies (Redis, HTTP, file system) are mocked.

## Directory Structure

```
backend/tests/unit/
├── AGENTS.md                  # This file
├── conftest.py                # Unit test-specific fixtures
├── __init__.py                # Package initialization
├── .gitkeep                   # Directory placeholder
├── test_websocket_README.md   # WebSocket testing documentation
├── api/                       # API layer tests (17 route tests + 5 schema tests)
│   ├── routes/                # Route handler tests
│   └── schemas/               # Pydantic schema tests
├── core/                      # Core infrastructure tests (28 files)
├── models/                    # ORM model tests (16 files)
├── routes/                    # Additional route tests (13 files)
├── services/                  # Service layer tests (71 files)
├── scripts/                   # Migration script tests (1 file)
└── test_*.py                  # Root-level test files (5 files)
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

## Test Files (150 total)

### Root Level Tests (5 files)

| File                              | Tests For                       |
| --------------------------------- | ------------------------------- |
| `test_benchmarks.py`              | Benchmark utilities and helpers |
| `test_benchmark_vram.py`          | VRAM usage benchmarks           |
| `test_business_metrics.py`        | Business metrics calculations   |
| `test_main.py`                    | Application entrypoint testing  |
| `test_migrate_sqlite_postgres.py` | SQLite to PostgreSQL migration  |

### API Routes (`api/routes/`) - 17 files

| File                         | Tests For                        |
| ---------------------------- | -------------------------------- |
| `test_ai_audit_prompts.py`   | AI audit prompt management       |
| `test_ai_audit.py`           | AI audit endpoints               |
| `test_cameras_baseline.py`   | Camera baseline endpoints        |
| `test_detections_api.py`     | Detection listing endpoints      |
| `test_dlq_api.py`            | Dead letter queue endpoints      |
| `test_enrichment.py`         | Enrichment endpoints             |
| `test_enrichment_storage.py` | Enrichment storage operations    |
| `test_entities.py`           | Entity management endpoints      |
| `test_event_clips.py`        | Event clip generation endpoints  |
| `test_events_api.py`         | Event management endpoints       |
| `test_events_export.py`      | Event export functionality       |
| `test_metrics.py`            | Metrics endpoints                |
| `test_prompt_management.py`  | Prompt management (empty file)   |
| `test_scene_changes.py`      | Scene change detection endpoints |
| `test_system_models.py`      | System model endpoints           |
| `test_telemetry_api.py`      | Telemetry endpoints              |

### API Schemas (`api/schemas/`) - 5 files

| File                                 | Tests For                      |
| ------------------------------------ | ------------------------------ |
| `test_detections.py`                 | Detection schema validation    |
| `test_enrichment_data_validation.py` | Enrichment data schemas        |
| `test_llm_response.py`               | LLM response schema validation |
| `test_performance_schemas.py`        | Performance schema models      |
| `test_system.py`                     | System schema validation       |

### Core Components (`core/`) - 28 files

| File                                | Tests For                           |
| ----------------------------------- | ----------------------------------- |
| `test_auth_middleware.py`           | Authentication middleware           |
| `test_config.py`                    | Settings, env vars, type coercion   |
| `test_database_init_lock.py`        | Database initialization locking     |
| `test_database_pool.py`             | Connection pool management          |
| `test_database.py`                  | Database operations, ILIKE escaping |
| `test_database_utils.py`            | Database utility functions          |
| `test_dockerfile_config.py`         | Docker configuration validation     |
| `test_health_monitor.py`            | Health monitoring service           |
| `test_json_utils.py`                | JSON serialization utilities        |
| `test_logging.py`                   | Structured logging                  |
| `test_logging_sanitization.py`      | Log sanitization (PII removal)      |
| `test_metrics.py`                   | Metrics collection                  |
| `test_middleware.py`                | Request/response middleware         |
| `test_mime_types.py`                | MIME type detection                 |
| `test_query_optimization.py`        | Query optimization utilities        |
| `test_rate_limit.py`                | Rate limiting middleware            |
| `test_redis.py`                     | Redis client operations             |
| `test_redis_retry.py`               | Redis retry logic                   |
| `test_sanitization.py`              | Input sanitization                  |
| `test_security_headers.py`          | Security header middleware          |
| `test_tls.py`                       | TLS/SSL configuration               |
| `test_url_validation.py`            | URL validation utilities            |
| `test_websocket_circuit_breaker.py` | WebSocket circuit breaker           |
| `test_websocket.py`                 | WebSocket core functionality        |
| `test_websocket_timeout.py`         | WebSocket timeout handling          |
| `test_websocket_validation.py`      | WebSocket message validation        |

### Database Models (`models/`) - 15 files

| File                         | Tests For                  |
| ---------------------------- | -------------------------- |
| `test_alert.py`              | Alert and AlertRule models |
| `test_audit_log.py`          | AuditLog model             |
| `test_baseline.py`           | Baseline models            |
| `test_camera.py`             | Camera model               |
| `test_detection.py`          | Detection model            |
| `test_enums.py`              | Severity and other enums   |
| `test_event_audit.py`        | EventAudit model           |
| `test_event.py`              | Event model                |
| `test_gpu_stats.py`          | GPUStats model             |
| `test_hypothesis_example.py` | Hypothesis property tests  |
| `test_log_model.py`          | Log model                  |
| `test_models_hypothesis.py`  | Model property-based tests |
| `test_prompt_version.py`     | PromptVersion model        |
| `test_zone.py`               | Zone model                 |

### Routes (`routes/`) - 13 files

| File                          | Tests For                  |
| ----------------------------- | -------------------------- |
| `test_admin_routes.py`        | Admin endpoints            |
| `test_ai_audit_routes.py`     | AI audit routes            |
| `test_alerts_routes.py`       | Alert rules CRUD           |
| `test_audit_routes.py`        | Audit log endpoints        |
| `test_cameras_routes.py`      | Camera CRUD endpoints      |
| `test_detections_routes.py`   | Detection endpoints        |
| `test_events_routes.py`       | Event management endpoints |
| `test_logs_routes.py`         | Log management endpoints   |
| `test_media_routes.py`        | Media file serving         |
| `test_notification_routes.py` | Notification endpoints     |
| `test_system_routes.py`       | System health and config   |
| `test_websocket_routes.py`    | WebSocket handlers         |
| `test_zones_routes.py`        | Zone CRUD endpoints        |

### Services (`services/`) - 71 files

**AI Pipeline Services:**

| File                        | Tests For                   |
| --------------------------- | --------------------------- |
| `test_batch_aggregator.py`  | Detection batch aggregation |
| `test_detector_client.py`   | RT-DETRv2 HTTP client       |
| `test_file_watcher.py`      | File system monitoring      |
| `test_nemotron_analyzer.py` | Nemotron LLM risk analysis  |
| `test_pipeline_worker.py`   | AI pipeline worker          |
| `test_pipeline_workers.py`  | Worker orchestration        |

**Enrichment and Vision Services:**

| File                               | Tests For                   |
| ---------------------------------- | --------------------------- |
| `test_clip_client.py`              | CLIP model client           |
| `test_clip_generator.py`           | Video clip generation       |
| `test_clip_loader.py`              | CLIP model loader           |
| `test_context_enricher.py`         | Context enrichment service  |
| `test_enrichment_client.py`        | Enrichment client           |
| `test_enrichment_client_errors.py` | Enrichment error handling   |
| `test_enrichment_pipeline.py`      | Enrichment pipeline         |
| `test_florence_client.py`          | Florence model client       |
| `test_florence_extractor.py`       | Florence feature extraction |
| `test_florence_loader.py`          | Florence model loader       |
| `test_vision_extractor.py`         | Vision feature extraction   |

**Model Loaders:**

| File                                | Tests For                     |
| ----------------------------------- | ----------------------------- |
| `test_depth_anything_loader.py`     | Depth estimation loader       |
| `test_fashion_clip_loader.py`       | Fashion CLIP loader           |
| `test_image_quality_loader.py`      | Image quality model loader    |
| `test_model_zoo.py`                 | Model zoo management          |
| `test_pet_classifier_loader.py`     | Pet classifier loader         |
| `test_segformer_loader.py`          | SegFormer segmentation loader |
| `test_vehicle_classifier_loader.py` | Vehicle classifier loader     |
| `test_vehicle_damage_loader.py`     | Vehicle damage loader         |
| `test_violence_loader.py`           | Violence detection loader     |
| `test_vitpose_loader.py`            | ViTPose pose estimation       |
| `test_weather_loader.py`            | Weather classification loader |
| `test_xclip_loader.py`              | X-CLIP video model loader     |
| `test_yolo_world_loader.py`         | YOLO World loader             |

**Broadcaster Services:**

| File                         | Tests For                    |
| ---------------------------- | ---------------------------- |
| `test_event_broadcaster.py`  | Event WebSocket broadcasting |
| `test_system_broadcaster.py` | System status broadcasting   |
| `test_gpu_monitor.py`        | GPU monitoring service       |

**Alert and Notification:**

| File                                | Tests For               |
| ----------------------------------- | ----------------------- |
| `test_alert_dedup.py`               | Alert deduplication     |
| `test_alert_engine.py`              | Alert rule engine       |
| `test_notification.py`              | Notification delivery   |
| `test_notification_webhook_ssrf.py` | Webhook SSRF prevention |

**Other Services:**

| File                                  | Tests For                     |
| ------------------------------------- | ----------------------------- |
| `test_audit.py`                       | Audit logging                 |
| `test_audit_service.py`               | Audit service operations      |
| `test_baseline.py`                    | Activity baseline service     |
| `test_bbox_validation.py`             | Bounding box validation       |
| `test_bbox_validation_integration.py` | BBox validation integration   |
| `test_cache_service.py`               | Cache service                 |
| `test_circuit_breaker.py`             | Circuit breaker pattern       |
| `test_cleanup_service.py`             | Data cleanup service          |
| `test_dedupe.py`                      | Deduplication logic           |
| `test_dedup_key.py`                   | Deduplication key generation  |
| `test_degradation_manager.py`         | Graceful degradation          |
| `test_face_detector.py`               | Face detection service        |
| `test_ocr_service.py`                 | OCR service                   |
| `test_performance_collector.py`       | Performance metrics collector |
| `test_plate_detector.py`              | License plate detection       |
| `test_prompt_formatters.py`           | Prompt formatting             |
| `test_prompt_service.py`              | Prompt service                |
| `test_prompts.py`                     | Prompt templates              |
| `test_prompt_version_service.py`      | Prompt versioning             |
| `test_reid_service.py`                | Re-identification service     |
| `test_retry_handler.py`               | Retry logic                   |
| `test_scene_baseline.py`              | Scene baseline detection      |
| `test_scene_change_detector.py`       | Scene change detection        |
| `test_search.py`                      | Search functionality          |
| `test_service_managers.py`            | Service lifecycle management  |
| `test_severity.py`                    | Severity classification       |
| `test_thumbnail_generator.py`         | Thumbnail generation          |
| `test_video_processor.py`             | Video processing service      |
| `test_video_support.py`               | Video detection/streaming     |
| `test_websocket_circuit_breaker.py`   | WS circuit breaker            |
| `test_zone_service.py`                | Zone management               |

### Scripts (`scripts/`) - 1 file

| File                              | Tests For                 |
| --------------------------------- | ------------------------- |
| `test_migrate_beads_to_linear.py` | Beads to Linear migration |

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
    mock_client.add_to_queue_safe = AsyncMock(
        return_value=QueueAddResult(success=True, queue_length=1)
    )
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

## Hypothesis Property-Based Testing

This project uses Hypothesis for property-based testing. Property tests discover edge cases that manual examples miss by generating random inputs and verifying invariants.

### Hypothesis Profiles

Defined in `pyproject.toml`:

| Profile   | `max_examples` | Use Case                      |
| --------- | -------------- | ----------------------------- |
| `default` | 100            | Local development             |
| `ci`      | 200            | CI pipeline (more thorough)   |
| `fast`    | 10             | Quick smoke tests             |
| `debug`   | 10             | Debugging with verbose output |

Run with specific profile:

```bash
uv run pytest backend/tests/unit/ -xvs -k "hypothesis" --hypothesis-profile=ci
```

### Custom Strategies

Located in `backend/tests/strategies.py`:

| Strategy                      | Description                             |
| ----------------------------- | --------------------------------------- |
| `risk_scores`                 | Risk scores (0-100 integers)            |
| `confidences`                 | Confidence values (0.0-1.0 floats)      |
| `bbox_coordinates`            | Bounding box pixel coordinates          |
| `sha256_hashes`               | Valid SHA256 hex strings                |
| `detection_strategy`          | Full Detection model instances          |
| `event_strategy`              | Full Event model instances              |
| `valid_bbox_xyxy_strategy`    | Valid bboxes (x1 < x2, y1 < y2)         |
| `invalid_bbox_xyxy_strategy`  | Invalid bboxes (zero/negative dims)     |
| `bbox_and_image_strategy`     | Bbox + image dimensions (within bounds) |
| `normalized_bbox_strategy`    | Normalized bbox (0-1 coordinates)       |
| `search_query_strategy`       | Search queries with optional operators  |
| `detection_ids_json_strategy` | JSON array of detection IDs             |
| `detection_ids_csv_strategy`  | CSV list of detection IDs               |
| `variable_names`              | Valid prompt variable names             |

### Property Categories

#### 1. Idempotence Properties

Test that applying an operation twice gives the same result:

```python
@given(score=st.integers(min_value=0, max_value=100))
def test_normalize_is_idempotent(self, score: int) -> None:
    """Property: normalize(normalize(x)) == normalize(x)"""
    result1 = normalize_score(score)
    result2 = normalize_score(result1)
    assert result1 == result2
```

#### 2. Bounds Preservation Properties

Test that output stays within expected bounds:

```python
@given(score=st.integers(min_value=-100, max_value=200))
def test_score_is_bounded(self, score: int) -> None:
    """Property: 0 <= output_score <= 100"""
    result = normalize_score(score)
    assert 0 <= result <= 100
```

#### 3. Invariant Properties

Test relationships that always hold:

```python
@given(items=st.lists(st.integers()))
def test_filter_reduces_count(self, items: list[int]) -> None:
    """Property: len(filter(items)) <= len(items)"""
    result = filter_items(items, lambda x: x > 0)
    assert len(result) <= len(items)
```

#### 4. Roundtrip Properties

Test that serialize/deserialize preserves data:

```python
@given(bbox=valid_bbox_strategy())
def test_bbox_roundtrip(self, bbox: tuple) -> None:
    """Property: deserialize(serialize(x)) == x"""
    serialized = bbox_to_json(bbox)
    deserialized = json_to_bbox(serialized)
    assert bbox == deserialized
```

#### 5. Symmetry Properties

Test commutative operations:

```python
@given(bbox1=valid_bbox_strategy(), bbox2=valid_bbox_strategy())
def test_iou_is_symmetric(self, bbox1, bbox2) -> None:
    """Property: IoU(a, b) == IoU(b, a)"""
    assert calculate_iou(bbox1, bbox2) == calculate_iou(bbox2, bbox1)
```

### Files with Property-Based Tests

| File                               | Properties Tested                  |
| ---------------------------------- | ---------------------------------- |
| `models/test_models_hypothesis.py` | Model invariants, enum values      |
| `services/test_severity.py`        | Risk score bounds, monotonicity    |
| `services/test_bbox_validation.py` | Bbox bounds, clamping idempotence  |
| `services/test_dedupe.py`          | Hash determinism, key generation   |
| `services/test_search.py`          | Query parsing, filter construction |
| `services/test_prompt_parser.py`   | Style detection, insertion bounds  |

### Writing Property Tests

1. Import strategies and Hypothesis:

```python
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st
from backend.tests.strategies import risk_scores, valid_bbox_xyxy_strategy
```

2. Use appropriate settings:

```python
@given(score=risk_scores)
@hypothesis_settings(max_examples=100)
def test_property_name(self, score: int) -> None:
    # Test implementation
```

3. Group related properties in test classes:

```python
class TestScoreProperties:
    """Property-based tests for score calculations."""

    @given(score=risk_scores)
    def test_score_is_bounded(self, score):
        ...

    @given(score=risk_scores)
    def test_score_is_idempotent(self, score):
        ...
```

### Best Practices

1. **Focus on properties, not examples**: Test invariants that hold for all inputs
2. **Use custom strategies**: Define reusable strategies in `strategies.py`
3. **Limit max_examples in CI**: Use the `ci` profile for thorough testing
4. **Add @hypothesis_settings**: Control example count per test
5. **Filter invalid inputs**: Use `.filter()` to exclude edge cases that are expected to fail

## Coverage Goals

- **Target**: 98%+ for unit-tested components
- **Focus areas**:
  - Happy path (normal operation)
  - Error conditions (exceptions, timeouts)
  - Edge cases (empty lists, None values)
  - Validation logic (input validation)
  - Property-based invariants (idempotence, bounds, roundtrips)

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
