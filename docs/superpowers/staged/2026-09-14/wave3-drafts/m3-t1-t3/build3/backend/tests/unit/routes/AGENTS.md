# Unit Tests - API Routes

## Purpose

The `backend/tests/unit/routes/` directory contains unit tests for FastAPI route handlers in `backend/api/routes/`. Tests verify endpoint behavior with mocked dependencies.

## Directory Structure

```
backend/tests/unit/routes/
├── AGENTS.md                          # This file
├── __init__.py                        # Package initialization
├── test_admin_routes.py               # Admin endpoints
├── test_ai_audit_routes.py            # AI audit routes
├── test_alert_instance_routes.py      # Alert instance endpoints
├── test_alerts_routes.py              # Alert rules CRUD
├── test_audit_routes.py               # Audit log endpoints
├── test_cameras_routes.py             # Camera CRUD endpoints
├── test_detections_cache_invalidation.py # Detection cache tests
├── test_detections_routes.py          # Detection listing endpoints
├── test_events_cache_invalidation.py  # Event cache tests
├── test_events_routes.py              # Event management endpoints
├── test_logs_routes.py                # Log management endpoints
├── test_media_routes.py               # Media file serving
├── test_notification_routes.py        # Notification endpoints
├── test_restore_endpoints.py          # Restore endpoint tests
├── test_system_anomaly_config.py      # Anomaly config endpoints
├── test_system_performance_history.py # Performance history endpoints
├── test_system_routes.py              # System health and config
├── test_websocket_routes.py           # WebSocket handlers
└── test_zones_routes.py               # Zone CRUD endpoints
```

## Test Files (21 files)

| File                                    | Tests For                | Endpoints                |
| --------------------------------------- | ------------------------ | ------------------------ |
| `test_admin_routes.py`                  | Admin endpoints          | `/api/admin/*`           |
| `test_ai_audit_routes.py`               | AI audit routes          | `/api/ai-audit/*`        |
| `test_alert_instance_routes.py`         | Alert instances          | `/api/alert-instances/*` |
| `test_alerts_routes.py`                 | Alert rules CRUD         | `/api/alerts/*`          |
| `test_audit_routes.py`                  | Audit log endpoints      | `/api/audit/*`           |
| `test_cameras_routes.py`                | Camera CRUD endpoints    | `/api/cameras/*`         |
| `test_detections_cache_invalidation.py` | Detection cache          | `/api/detections/*`      |
| `test_detections_routes.py`             | Detection listing        | `/api/detections/*`      |
| `test_events_cache_invalidation.py`     | Event cache              | `/api/events/*`          |
| `test_events_routes.py`                 | Event management         | `/api/events/*`          |
| `test_logs_routes.py`                   | Log management           | `/api/logs/*`            |
| `test_media_routes.py`                  | Media file serving       | `/api/media/*`           |
| `test_notification_routes.py`           | Notification endpoints   | `/api/notifications/*`   |
| `test_restore_endpoints.py`             | Restore operations       | `/api/restore/*`         |
| `test_system_anomaly_config.py`         | Anomaly configuration    | `/api/system/anomaly/*`  |
| `test_system_performance_history.py`    | Performance history      | `/api/system/perf/*`     |
| `test_system_routes.py`                 | System health and config | `/api/system/*`          |
| `test_websocket_routes.py`              | WebSocket handlers       | `/ws/*`                  |
| `test_zones_routes.py`                  | Zone CRUD endpoints      | `/api/zones/*`           |

## Additional Route Tests

Additional route tests are in `backend/tests/unit/api/routes/` (17 files) covering:

- AI audit, DLQ, enrichment, entities, event clips, events export, metrics, scene changes, telemetry

## Test Categories

### CRUD Operation Tests

- Create (POST) - Request validation, database insertion
- Read (GET) - Single item, list with pagination/filters
- Update (PUT/PATCH) - Partial updates, validation
- Delete (DELETE) - Cascade behavior, not found handling

### Error Handling Tests

- 404 Not Found responses
- 422 Validation errors
- 401/403 Authentication/Authorization errors
- 500 Internal server errors

### Pagination Tests

- Default pagination values
- Custom limit/offset
- Maximum limit enforcement
- Response format verification

### Filter Tests

- Query parameter parsing
- Filter application
- Combined filter scenarios
- Invalid filter handling

## Running Tests

```bash
# Run all route unit tests
pytest backend/tests/unit/routes/ -v
pytest backend/tests/unit/test_*_routes.py -v

# Run specific route tests
pytest backend/tests/unit/routes/test_alerts_routes.py -v

# Run with coverage
pytest backend/tests/unit/routes/ -v --cov=backend/api/routes
```

## Common Mocking Patterns

### Mocking Database Session

```python
@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    )
    return session
```

### Mocking Route Dependencies

```python
from unittest.mock import patch

@pytest.mark.asyncio
async def test_endpoint(client, mock_session):
    with patch("backend.api.routes.cameras.get_db", return_value=mock_session):
        response = await client.get("/api/cameras")
        assert response.status_code == 200
```

### Testing with httpx AsyncClient

```python
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

## Related Documentation

- `/backend/api/routes/AGENTS.md` - Route documentation
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/integration/AGENTS.md` - Integration test patterns
