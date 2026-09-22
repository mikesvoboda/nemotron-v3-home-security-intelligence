# Unit Testing

Unit tests verify individual components in isolation with all external dependencies mocked. This document covers pytest patterns, fixtures, and mocking strategies used in the backend test suite.

## Overview

Unit tests form the foundation of the test pyramid (~80% of all tests). They are:

- **Fast**: Complete in <1 second per test
- **Isolated**: No external dependencies (database, Redis, network)
- **Deterministic**: Same input always produces same output

**Location**: `backend/tests/unit/` (~680 test files)

## Test Organization

### Directory Structure

```
backend/tests/unit/
  api/
    routes/           # API route unit tests (96 files)
    schemas/          # Pydantic schema validation tests (53 files)
    middleware/       # API middleware tests (22 files)
    helpers/          # API helper function tests
  core/               # Infrastructure tests (93 files)
  models/             # ORM model tests (49 files)
  services/           # Business logic tests (257 files)
```

Additional top-level directories exist under `unit/` (`evaluation/`,
`jobs/`, `repositories/`, `setup_lib/`, …) plus a large set of root-level
`test_*.py` files — the counts above cover the six largest trees only.

### Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test functions: `test_<function_name>_<scenario>`

## pytest Configuration

Configuration is defined in `pyproject.toml:487-527` (abridged — the real
file also carries the M3 T5 timeout-ruling comments and the full marker
list):

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests", "ai/*/tests", "ai/*/test_*.py", "setup_lib/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-n 8 --dist=worksteal -v --strict-markers --tb=short -p randomly -m 'not gpu'"
timeout = 5
timeout_method = "signal"
timeout_func_only = false
```

Note `addopts` already selects 8 xdist workers and skips `gpu`-marked
tests by default; a CLI `--timeout=N` governs every test that has no
explicit timeout marker (M3 T5 owner ruling, 2026-09-14 — per-item
stamps in `backend/tests/conftest.py` apply the same rule).

### Test Markers

Registered in `pyproject.toml:508-527`; `unit`/`integration` markers are
auto-applied by the `pytest_collection_modifyitems` hook in
`backend/tests/conftest.py:470` based on directory location.

| Marker        | Description                                        | Timeout          |
| ------------- | -------------------------------------------------- | ---------------- |
| `unit`        | Unit test (auto-applied for `unit/`)               | 5s (ini default) |
| `integration` | Integration test (auto-applied for `integration/`) | 5s               |
| `e2e`         | End-to-end pipeline test                           | 60s              |
| `slow`        | Legitimately slow test                             | 30s              |
| `gpu`         | GPU test (requires RTX A5500)                      | 60s              |
| `benchmark`   | Performance benchmark                              | N/A              |
| `flaky`       | Known flaky test (quarantined)                     | N/A              |
| `serial`      | Requires serial execution (no parallel)            | N/A              |

Running tests by marker:

```bash
# Run only unit tests
pytest -m unit backend/tests/

# Exclude slow tests
pytest -m "not slow" backend/tests/

# Run unit tests that aren't flaky
pytest -m "unit and not flaky" backend/tests/
```

## Fixtures

### Root Fixtures (`backend/tests/conftest.py`)

The root conftest.py provides shared fixtures for all tests.

#### Database Session Mock

From `backend/tests/conftest.py:1929-2001` (abridged):

```python
@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session with all common operations configured."""
    session = AsyncMock()

    # Synchronous operations
    session.add = MagicMock()
    session.add_all = MagicMock()

    # Async operations
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()

    # execute() returns a result object with the common read patterns
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_scalars.first.return_value = None
    mock_result.scalars.return_value = mock_scalars
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    # begin_nested for savepoint support
    ...
    return session
```

**Usage example**:

```python
@pytest.mark.asyncio
async def test_get_cameras(mock_db_session):
    """Test camera retrieval with mocked database."""
    from backend.tests.factories import CameraFactory

    camera = CameraFactory.build()
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = [camera]

    result = await get_cameras(mock_db_session)

    assert len(result) == 1
    mock_db_session.execute.assert_called_once()
```

#### HTTP Client Mock

From `backend/tests/conftest.py:2058-2099`:

```python
@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient with common HTTP methods."""
    client = AsyncMock()

    # Async context manager support
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    client.patch = AsyncMock()

    return client
```

The response object comes from the companion `mock_http_response` fixture
(`backend/tests/conftest.py:2025`), so tests wire
`mock_http_client.post.return_value = mock_http_response` and then
customize `mock_http_response.json.return_value`.

#### Redis Client Mock

From `backend/tests/conftest.py:2165-2252` (abridged):

```python
@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a comprehensive mock Redis client."""
    client = AsyncMock()

    # Basic operations
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)

    # Pub/sub, lists, sets, hashes, expiration ...
    client.publish = AsyncMock(return_value=1)
    client.lpush = AsyncMock(return_value=1)
    client.sadd = AsyncMock(return_value=1)
    client.hget = AsyncMock(return_value=None)
    client.expire = AsyncMock(return_value=True)

    client.health_check = AsyncMock(return_value={
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    })
    # Queue with backpressure (QueueAddResult) and pipeline support
    client.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    return client
```

#### Factory Fixtures

From `backend/tests/conftest.py:2442-2487`:

```python
@pytest.fixture
def camera_factory():
    """Provide CameraFactory for creating Camera instances."""
    from backend.tests.factories import CameraFactory
    return CameraFactory

@pytest.fixture
def detection_factory():
    """Provide DetectionFactory for creating Detection instances."""
    from backend.tests.factories import DetectionFactory
    return DetectionFactory

@pytest.fixture
def event_factory():
    """Provide EventFactory for creating Event instances."""
    from backend.tests.factories import EventFactory
    return EventFactory
```

## Mocking Patterns

### Patching External Dependencies

Use `unittest.mock.patch` to replace external dependencies:

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_detector_client_health_check(mock_http_client, mock_http_response):
    """Detector health check reports healthy on a 2xx response."""
    mock_http_response.raise_for_status.return_value = None
    mock_http_client.get.return_value = mock_http_response

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        from backend.services.detector_client import DetectorClient
        # DetectorClient() reads its service URL from settings (AI gateway
        # or YOLO26_URL) — it takes no URL argument
        client = DetectorClient()
        assert await client.health_check() is True

    mock_http_client.get.assert_awaited()
```

`DetectorClient.detect_objects(image_path, camera_id, session, ...)` is
heavier — it parses the detector response (`result["detections"]`, each
item carrying `class`, `confidence`, `bbox`), filters by the class-specific
confidence thresholds, and stores `Detection` rows via the session — so
unit tests feed it a mocked `post` response plus `mock_db_session`.

### Mocking Async Context Managers

For services using `async with`:

```python
@pytest.mark.asyncio
async def test_with_async_context(mock_db_session, mock_db_session_context):
    """Test function using async with get_session()."""
    with patch("backend.core.database.get_session", return_value=mock_db_session_context):
        # Function uses: async with get_session() as session:
        await my_function_using_session()
        mock_db_session.commit.assert_called()
```

### Mocking Time

Use `freezegun` for time-dependent tests:

```python
from freezegun import freeze_time

@freeze_time("2024-01-15 10:30:00")
def test_event_timestamp():
    """Test event creation with frozen time."""
    from datetime import datetime, UTC
    from backend.tests.factories import EventFactory

    event = EventFactory()
    assert event.started_at == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
```

## Async Testing

### Automatic Async Mode

Tests are automatically detected as async via `asyncio_mode = "auto"`:

```python
# No decorator needed when function is async
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

### Async Utilities

`backend/tests/async_utils.py` is a backwards-compatibility shim — the
canonical home is `backend.tests.utils.async_helpers` (new code should
import from there):

```python
from backend.tests.utils import (
    AsyncClientMock,
    create_mock_db_context,
    async_timeout,
    run_concurrent_tasks,
)

# HTTP client with predefined responses
mock = AsyncClientMock(
    get_responses={"/health": {"status": "healthy"}},
    post_responses={"/detect": {"detections": []}},
)

# Timeout protection for flaky operations
async with async_timeout(5.0, operation="health check"):
    await client.check_health()
```

## Test Patterns

### Arrange-Act-Assert (AAA)

Standard unit test structure:

```python
def test_risk_score_calculation():
    """Test risk score is calculated correctly."""
    # Arrange
    from backend.tests.factories import EventFactory
    event = EventFactory(risk_score=85, risk_level="high")

    # Act
    severity = calculate_severity(event.risk_score)

    # Assert
    assert severity == "high"
    assert event.risk_level == severity
```

### Parametrized Tests

Use `@pytest.mark.parametrize` for testing multiple inputs:

From `backend/tests/unit/services/test_bbox_validation.py:79-91`:

```python
@pytest.mark.parametrize(
    "bbox,reason",
    [
        ((-10, 0, 100, 100), "negative x1"),
        ((0, -10, 100, 100), "negative y1"),
        ((-10, -10, 100, 100), "negative x1 and y1"),
    ],
)
def test_negative_coordinates_default_invalid(
    self, bbox: tuple[float, float, float, float], reason: str
) -> None:
    """Test that negative coordinates are invalid by default."""
    assert is_valid_bbox(bbox) is False, f"Should reject by default: {reason}"
```

### Property-Based Testing with Hypothesis

From `backend/tests/unit/services/test_bbox_validation.py:742-756` and
`:944-955`:

```python
from hypothesis import given, settings as hypothesis_settings
from hypothesis import strategies as st
from backend.tests.strategies import valid_bbox_xyxy_strategy

class TestBboxValidationProperties:
    """Property-based tests using Hypothesis."""

    @given(bbox=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_valid_bbox_always_passes_validation(
        self, bbox: tuple[float, float, float, float]
    ) -> None:
        """Property: Valid bboxes (x1 < x2, y1 < y2, non-negative) are always valid."""
        assert is_valid_bbox(bbox) is True

    @given(bbox1=valid_bbox_xyxy_strategy(), bbox2=valid_bbox_xyxy_strategy())
    @hypothesis_settings(max_examples=100)
    def test_iou_is_symmetric(
        self,
        bbox1: tuple[float, float, float, float],
        bbox2: tuple[float, float, float, float],
    ) -> None:
        """Property: IoU(a, b) == IoU(b, a) (symmetric)."""
        iou1 = calculate_bbox_iou(bbox1, bbox2)
        iou2 = calculate_bbox_iou(bbox2, bbox1)
        assert iou1 == pytest.approx(iou2)
```

### Testing Exceptions

```python
def test_invalid_bbox_raises_error():
    """Test that invalid bounding box raises appropriate error."""
    from backend.services.bbox_validation import (
        InvalidBoundingBoxError,
        validate_bbox,
    )

    with pytest.raises(InvalidBoundingBoxError) as exc_info:
        validate_bbox((50, 0, 50, 100))  # Zero width

    assert "zero or negative width" in str(exc_info.value)
    assert exc_info.value.bbox == (50, 0, 50, 100)
```

## Best Practices

### 1. One Assertion Per Concept

Each test should verify one logical concept:

```python
# Good: Focused tests
def test_camera_factory_creates_valid_id():
    camera = CameraFactory()
    assert camera.id.startswith("camera_")

def test_camera_factory_creates_valid_name():
    camera = CameraFactory()
    assert camera.name.startswith("Camera ")

# Avoid: Multiple unrelated assertions
def test_camera_factory():  # Too broad
    camera = CameraFactory()
    assert camera.id is not None
    assert camera.name is not None
    assert camera.status == "online"
```

### 2. Use Factories for Test Data

Prefer factories over inline object creation:

```python
# Good: Using factory
from backend.tests.factories import EventFactory

def test_high_risk_event():
    event = EventFactory(high_risk=True)
    assert event.risk_score >= 76

# Avoid: Inline creation
def test_high_risk_event():
    event = Event(
        batch_id="...",
        camera_id="...",
        started_at=datetime.now(UTC),
        risk_score=85,
        # ... many more required fields
    )
```

### 3. Mock at the Right Level

Mock dependencies, not implementation details:

```python
# Good: Mock the dependency injection point
with patch("httpx.AsyncClient", return_value=mock_http_client):
    result = await DetectorClient().detect_objects(image_path, camera_id, session)

# Avoid: Mocking internal implementation
with patch("backend.services.detector_client.DetectorClient._send_detection_request"):  # Too fragile
    ...
```

### 4. Descriptive Test Names

Test names should describe the scenario and expected behavior:

```python
# Good: Descriptive names
def test_validate_bbox_with_zero_width_raises_invalid_error():
    ...

def test_camera_status_offline_when_last_seen_exceeds_threshold():
    ...

# Avoid: Vague names
def test_validate():
    ...

def test_camera_status():
    ...
```

## Running Unit Tests

```bash
# All unit tests (parallel)
uv run pytest backend/tests/unit/ -n auto --dist=worksteal

# Specific test file
uv run pytest backend/tests/unit/services/test_bbox_validation.py -v

# Specific test class
uv run pytest backend/tests/unit/services/test_bbox_validation.py::TestIsValidBbox -v

# Specific test method
uv run pytest backend/tests/unit/services/test_bbox_validation.py::TestIsValidBbox::test_valid_bbox_returns_true -v

# With coverage
uv run pytest backend/tests/unit/ --cov=backend --cov-report=html
```

## Related Documentation

- [Test Fixtures](test-fixtures.md) - Factory patterns and Hypothesis strategies
- [Integration Testing](integration-testing.md) - Multi-component testing
- [Coverage Requirements](coverage-requirements.md) - Coverage gates
