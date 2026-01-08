# Test Utilities Package

## Purpose

Centralized test utilities package that consolidates reusable testing helpers, strategies, and assertions. This package improves discoverability and reuse of test utilities across the backend test suite.

## Package Structure

```
backend/tests/utils/
├── __init__.py          # Re-exports main utilities for convenience
├── async_helpers.py     # Async testing utilities (context managers, timeouts)
├── strategies.py        # Hypothesis strategies for property-based testing
├── assertions.py        # Common assertion helpers for response validation
└── AGENTS.md            # This file
```

## Module Overview

### async_helpers.py

Async testing utilities for mocking and concurrent testing:

| Component                      | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| `AsyncClientMock`              | Pre-configured mock for httpx.AsyncClient with HTTP methods |
| `mock_async_context_manager`   | Create mock async context managers easily                   |
| `create_async_session_mock`    | Mock SQLAlchemy async sessions                              |
| `create_mock_db_context`       | Mock database context managers                              |
| `async_timeout`                | Context manager for async operation timeouts                |
| `with_timeout`                 | Function wrapper for timeout protection                     |
| `run_concurrent_tasks`         | Run multiple coroutines concurrently                        |
| `simulate_concurrent_requests` | Test rate limiting and connection pooling                   |
| `create_mock_redis_client`     | Mock Redis client with common operations                    |
| `create_mock_response`         | Create mock HTTP response objects                           |

### strategies.py

Hypothesis strategies for property-based testing:

| Category         | Strategies                                                              |
| ---------------- | ----------------------------------------------------------------------- |
| **Basic Types**  | `confidence_scores`, `risk_scores`, `positive_integers`                 |
| **Camera**       | `camera_ids`, `camera_names`, `camera_folder_paths`                     |
| **Detection**    | `detection_dict_strategy`, `detection_list_strategy`, `object_types`    |
| **Event**        | `event_dict_strategy`, `batch_ids`, `risk_levels`                       |
| **Alert**        | `alert_rule_dict_strategy`, `severity_levels`, `dedup_key_strategy`     |
| **Bounding Box** | `bbox_strategy`, `valid_bbox_xyxy_strategy`, `normalized_bbox_strategy` |
| **Search**       | `search_query_strategy`, `phrase_search_strategy`                       |

### assertions.py

Common assertion helpers for HTTP response validation:

| Function                     | Description                                |
| ---------------------------- | ------------------------------------------ |
| `assert_status_ok`           | Assert response is 2xx                     |
| `assert_status_code`         | Assert specific status code                |
| `assert_json_contains`       | Assert response JSON has expected keys     |
| `assert_json_not_contains`   | Assert response JSON lacks forbidden keys  |
| `assert_validation_error`    | Assert 422 validation error for field      |
| `assert_error_response`      | Assert error with status and message       |
| `assert_json_schema`         | Assert response matches simple type schema |
| `assert_json_list`           | Assert response is list with constraints   |
| `assert_pagination_response` | Assert paginated response structure        |
| `assert_datetime_field`      | Assert field is valid ISO 8601 datetime    |
| `assert_uuid_field`          | Assert field is valid UUID                 |
| `assert_in_range`            | Assert numeric value is within range       |

## Usage Examples

### Importing

```python
# Preferred: Import from utils package
from backend.tests.utils import (
    AsyncClientMock,
    async_timeout,
    assert_status_ok,
    assert_json_contains,
    camera_ids,
    risk_scores,
)

# Alternative: Import from specific modules
from backend.tests.utils.async_helpers import AsyncClientMock
from backend.tests.utils.assertions import assert_status_ok
from backend.tests.utils.strategies import camera_ids
```

### Async Helpers

```python
# Mock HTTP client
mock = AsyncClientMock(
    get_responses={"/health": {"status": "healthy"}},
    post_responses={"/detect": {"detections": []}},
)
async with mock.client() as client:
    response = await client.get("/health")
    assert response.json() == {"status": "healthy"}

# Timeout protection
async with async_timeout(5.0, operation="health check"):
    await client.check_health()

# Concurrent testing
result = await run_concurrent_tasks(
    client.get("/endpoint1"),
    client.get("/endpoint2"),
)
assert result.all_succeeded
```

### Assertions

```python
# Response validation
response = await client.get("/api/cameras/front_door")
assert_status_ok(response)
assert_json_contains(response, ["id", "name", "status"])
assert_datetime_field(response, "last_seen", allow_none=True)

# Validation errors
response = await client.post("/api/cameras", json={"name": ""})
assert_validation_error(response, "name")

# Pagination
response = await client.get("/api/events?page=1")
data = assert_pagination_response(response)
assert data["total"] >= 0
```

### Hypothesis Strategies

```python
from hypothesis import given
from backend.tests.utils import detection_dict_strategy, risk_scores

@given(detection=detection_dict_strategy())
def test_detection_properties(detection):
    assert 0 <= detection["confidence"] <= 1
    assert detection["camera_id"]
    assert detection["object_type"]

@given(score=risk_scores)
def test_risk_score_range(score):
    assert 0 <= score <= 100
```

## Backwards Compatibility

The original files (`backend/tests/async_utils.py` and `backend/tests/strategies.py`) now re-export from this package for backwards compatibility. Existing imports continue to work:

```python
# Old imports (still work)
from backend.tests.async_utils import AsyncClientMock
from backend.tests.strategies import camera_ids

# New imports (preferred)
from backend.tests.utils import AsyncClientMock, camera_ids
```

## Related Documentation

- `backend/tests/AGENTS.md` - Main test infrastructure overview
- `backend/tests/conftest.py` - Shared pytest fixtures
- `backend/tests/factories.py` - factory_boy factories
