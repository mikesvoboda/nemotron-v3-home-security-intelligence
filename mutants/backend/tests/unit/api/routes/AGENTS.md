# Unit Tests - API Routes

## Purpose

The `backend/tests/unit/api/routes/` directory contains unit tests for FastAPI route handlers. These tests verify endpoint behavior with mocked dependencies (database sessions, Redis, external services).

## Directory Structure

```
backend/tests/unit/api/routes/
├── AGENTS.md                     # This file
├── __init__.py                   # Package initialization
├── test_ai_audit_prompts.py      # AI audit prompt management
├── test_ai_audit.py              # AI audit endpoints
├── test_cameras_baseline.py      # Camera baseline endpoints
├── test_detections_api.py        # Detection listing endpoints
├── test_dlq_api.py               # Dead letter queue endpoints
├── test_enrichment.py            # Enrichment endpoints
├── test_enrichment_storage.py    # Enrichment storage operations
├── test_entities.py              # Entity management endpoints
├── test_event_clips.py           # Event clip generation endpoints
├── test_events_api.py            # Event management endpoints
├── test_events_export.py         # Event export functionality
├── test_metrics.py               # Metrics endpoints
├── test_prompt_management.py     # Prompt management (placeholder)
├── test_scene_changes.py         # Scene change detection endpoints
├── test_system_models.py         # System model endpoints
└── test_telemetry_api.py         # Telemetry endpoints
```

## Test Files (17 files)

| File                         | Tests For                             | Endpoints                   |
| ---------------------------- | ------------------------------------- | --------------------------- |
| `test_ai_audit_prompts.py`   | AI audit prompt management            | `/api/ai-audit/prompts/*`   |
| `test_ai_audit.py`           | AI audit operations                   | `/api/ai-audit/*`           |
| `test_cameras_baseline.py`   | Camera baseline calculations          | `/api/cameras/*/baseline`   |
| `test_detections_api.py`     | Detection listing and filtering       | `/api/detections/*`         |
| `test_dlq_api.py`            | Dead letter queue management          | `/api/dlq/*`                |
| `test_enrichment.py`         | Enrichment data retrieval             | `/api/enrichment/*`         |
| `test_enrichment_storage.py` | Enrichment data storage               | `/api/enrichment/storage/*` |
| `test_entities.py`           | Entity management                     | `/api/entities/*`           |
| `test_event_clips.py`        | Event video clip generation           | `/api/events/*/clips`       |
| `test_events_api.py`         | Event CRUD and filtering              | `/api/events/*`             |
| `test_events_export.py`      | Event export (CSV, JSON)              | `/api/events/export`        |
| `test_metrics.py`            | Metrics endpoints                     | `/api/metrics/*`            |
| `test_prompt_management.py`  | Prompt management (empty/placeholder) | `/api/prompts/*`            |
| `test_scene_changes.py`      | Scene change detection                | `/api/scene-changes/*`      |
| `test_system_models.py`      | System model information              | `/api/system/models/*`      |
| `test_telemetry_api.py`      | Telemetry data collection             | `/api/telemetry/*`          |

## Running Tests

```bash
# All route tests
uv run pytest backend/tests/unit/api/routes/ -v

# Single test file
uv run pytest backend/tests/unit/api/routes/test_events_api.py -v

# Specific test
uv run pytest backend/tests/unit/api/routes/test_events_api.py::test_list_events -v

# With coverage
uv run pytest backend/tests/unit/api/routes/ -v --cov=backend/api/routes
```

## Test Categories

### CRUD Operation Tests

- **Create (POST)**: Request validation, database insertion, response format
- **Read (GET)**: List with pagination/filters, single item retrieval
- **Update (PUT/PATCH)**: Partial updates, validation, not found handling
- **Delete (DELETE)**: Cascade behavior, confirmation

### Filtering and Pagination Tests

- Query parameter parsing
- Filter application (date range, status, camera_id)
- Pagination (limit, offset, total count)
- Sort ordering

### Error Handling Tests

- 404 Not Found for missing resources
- 422 Validation errors for invalid input
- 400 Bad Request for malformed requests
- 500 Internal Server Error handling

## Common Mocking Patterns

### Database Session

```python
@pytest.fixture
def mock_session():
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result
    return session
```

### Route Dependencies

```python
from unittest.mock import patch

@pytest.mark.asyncio
async def test_endpoint(client, mock_session):
    with patch("backend.api.routes.events.get_db", return_value=mock_session):
        response = await client.get("/api/events")
        assert response.status_code == 200
```

### httpx AsyncClient

```python
@pytest.fixture
async def client():
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

## Related Documentation

- `/backend/api/routes/AGENTS.md` - Route implementation docs
- `/backend/tests/unit/routes/AGENTS.md` - Additional route tests
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/integration/AGENTS.md` - Integration tests for full API testing
