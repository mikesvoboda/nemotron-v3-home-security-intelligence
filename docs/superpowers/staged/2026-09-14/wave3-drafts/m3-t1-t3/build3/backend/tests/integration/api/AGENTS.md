# Integration Tests - API

## Purpose

The `backend/tests/integration/api/` directory contains integration tests for API endpoints that require database interaction and complex setup scenarios not suitable for unit tests.

## Directory Structure

```
backend/tests/integration/api/
├── AGENTS.md                          # This file
├── __init__.py                        # Package initialization
├── routes/                            # Route-specific integration tests
│   └── test_camera_cache_invalidation.py  # Camera cache invalidation tests (19KB)
├── test_calibration_routes.py         # Calibration endpoint tests (20KB)
├── test_cursor_pagination.py          # Cursor-based pagination tests (26KB)
├── test_feedback_routes.py            # Feedback endpoint tests (17KB)
└── test_jobs_api.py                   # Jobs API endpoint tests (15KB)
```

## Test Files (5 total)

| File                                       | Tests For                      | Key Coverage                        |
| ------------------------------------------ | ------------------------------ | ----------------------------------- |
| `test_calibration_routes.py`               | `/api/calibration/*` endpoints | Severity calibration, user settings |
| `test_cursor_pagination.py`                | Cursor-based pagination        | Keyset pagination, performance      |
| `test_feedback_routes.py`                  | `/api/feedback/*` endpoints    | Event feedback submission           |
| `test_jobs_api.py`                         | `/api/jobs/*` endpoints        | Background job management           |
| `routes/test_camera_cache_invalidation.py` | Camera cache invalidation      | Cache coherence on updates          |

## Running Tests

```bash
# All API integration tests
uv run pytest backend/tests/integration/api/ -v

# Specific test file
uv run pytest backend/tests/integration/api/test_cursor_pagination.py -v

# With coverage
uv run pytest backend/tests/integration/api/ -v --cov=backend.api
```

## Key Test Patterns

### Cursor Pagination Testing

Tests verify cursor-based pagination for large datasets:

```python
@pytest.mark.asyncio
async def test_cursor_pagination_forward(client, session):
    # Create test data
    for i in range(100):
        await create_event(session, camera_id="test_cam")

    # First page
    response = await client.get("/api/events?limit=10")
    data = response.json()
    assert len(data["items"]) == 10
    assert data["next_cursor"] is not None

    # Next page using cursor
    response = await client.get(f"/api/events?cursor={data['next_cursor']}")
    assert len(response.json()["items"]) == 10
```

### Cache Invalidation Testing

Tests verify cache coherence when data changes:

```python
@pytest.mark.asyncio
async def test_camera_update_invalidates_cache(client, session, mock_redis):
    # Fetch camera (populates cache)
    await client.get("/api/cameras/test_cam")

    # Update camera
    await client.patch("/api/cameras/test_cam", json={"name": "New Name"})

    # Verify cache was invalidated
    mock_redis.delete.assert_called_with("camera:test_cam")
```

## Related Documentation

- `/backend/tests/integration/AGENTS.md` - Integration tests overview
- `/backend/api/routes/AGENTS.md` - Route implementations
- `/backend/tests/unit/api/AGENTS.md` - Unit tests for API layer
