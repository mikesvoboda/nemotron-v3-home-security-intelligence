# Integration Tests Directory

## Purpose

Integration tests verify that multiple components work together correctly. Unlike unit tests that isolate individual functions, integration tests validate real interactions between database, models, API endpoints, WebSocket channels, and services using PostgreSQL via testcontainers and mocked Redis.

## Running Tests

```bash
# All integration tests
pytest backend/tests/integration/ -v

# Single test file
pytest backend/tests/integration/test_api.py -v

# Specific test
pytest backend/tests/integration/test_api.py::test_root_endpoint -v

# With coverage
pytest backend/tests/integration/ -v --cov=backend --cov-report=html

# With verbose output
pytest backend/tests/integration/ -vv -s --log-cli-level=DEBUG
```

## Test Files (19 total)

### API Endpoint Tests

| File                     | Endpoints Tested                 |
| ------------------------ | -------------------------------- |
| `test_api.py`            | `/`, `/health`, CORS, lifecycle  |
| `test_cameras_api.py`    | `/api/cameras/*` CRUD operations |
| `test_events_api.py`     | `/api/events/*` with filtering   |
| `test_detections_api.py` | `/api/detections/*`              |
| `test_system_api.py`     | `/api/system/*`                  |
| `test_logs_api.py`       | `/api/logs/*`                    |
| `test_media_api.py`      | `/api/media/*` file serving      |
| `test_search_api.py`     | `/api/search/*`                  |
| `test_audit_api.py`      | `/api/audit/*`                   |
| `test_websocket.py`      | `/ws/events`, `/ws/system`       |

### Service Integration Tests

| File                                    | Service Tested   |
| --------------------------------------- | ---------------- |
| `test_batch_aggregator_integration.py`  | BatchAggregator  |
| `test_detector_client_integration.py`   | DetectorClient   |
| `test_file_watcher_integration.py`      | FileWatcher      |
| `test_health_monitor_integration.py`    | HealthMonitor    |
| `test_nemotron_analyzer_integration.py` | NemotronAnalyzer |

### Full Stack Tests

| File                         | Coverage                               |
| ---------------------------- | -------------------------------------- |
| `test_full_stack.py`         | Camera -> Detection -> Event workflows |
| `test_pipeline_e2e.py`       | Complete AI pipeline flow              |
| `test_alembic_migrations.py` | Database migration validation          |
| `test_github_workflows.py`   | CI/CD workflow validation              |

## Fixtures

Integration tests use shared fixtures from `backend/tests/conftest.py`:

| Fixture           | Description                                        |
| ----------------- | -------------------------------------------------- |
| `integration_env` | Sets DATABASE_URL, REDIS_URL, HSI_RUNTIME_ENV_PATH |
| `integration_db`  | Initializes PostgreSQL via testcontainers or local |
| `mock_redis`      | AsyncMock Redis client                             |
| `db_session`      | Direct AsyncSession access                         |
| `client`          | httpx AsyncClient with ASGITransport               |

The local `conftest.py` is minimal - it only documents that fixtures come from the parent.

## Key Test Patterns

### API Endpoint Testing

```python
@pytest.mark.asyncio
async def test_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
    data = response.json()
    assert "field" in data
```

### Database Workflow Testing

```python
@pytest.mark.asyncio
async def test_workflow(integration_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Create objects
        obj = Model(...)
        session.add(obj)
        await session.flush()

        # Query and verify
        result = await session.execute(select(Model))
        assert result.scalar_one() is not None
```

### Relationship Testing

```python
async with get_session() as session:
    result = await session.execute(select(Camera).where(...))
    camera = result.scalar_one()

    # Load relationships
    await session.refresh(camera, ["detections", "events"])

    assert len(camera.detections) > 0
    assert len(camera.events) > 0
```

### Concurrent Request Testing

```python
@pytest.mark.asyncio
async def test_concurrent_requests(client):
    import asyncio

    tasks = [client.get("/endpoint") for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    for response in responses:
        assert response.status_code == 200
```

### Security Testing

```python
def test_path_traversal_blocked(client, temp_foscam_dir):
    response = client.get("/api/media/cameras/test/../../../etc/passwd")
    assert response.status_code == 403
```

## Mocking Strategy

| Component    | Strategy             | Reason                      |
| ------------ | -------------------- | --------------------------- |
| Database     | Real (PostgreSQL)    | Test actual DB interactions |
| Redis        | Mocked               | Avoid external dependency   |
| FastAPI      | Real (ASGITransport) | Test actual app code        |
| HTTP clients | Mocked               | Control external responses  |
| File system  | Temp directories     | Isolated, clean state       |

## Test Coverage by File

### `test_api.py`

- Root endpoint (`/`)
- Health endpoint (`/health`)
- CORS middleware
- Application lifecycle
- Error handling
- Concurrent requests

### `test_cameras_api.py`

- CREATE: Camera creation, validation, defaults
- READ: List, get by ID, filter by status
- UPDATE: Name, status, folder_path
- DELETE: Cascade to related data
- Validation: Empty fields, long strings
- Edge cases: Concurrent creation, pagination

### `test_events_api.py`

- List events with filters (camera_id, risk_level, reviewed)
- Date range filtering (start_date, end_date)
- Pagination (limit, offset)
- Get event by ID
- Update event (PATCH)
- Get event detections

### `test_websocket.py`

- Events channel connection/disconnect
- System channel connection/disconnect
- Message broadcasting
- Multiple concurrent connections
- Reconnection handling
- Channel cleanup

### `test_media_api.py`

- Image file serving (JPG, PNG)
- Video file serving (MP4)
- Nested subdirectories
- 404 for non-existent files
- Path traversal prevention
- Disallowed file types

### `test_full_stack.py`

- Camera -> Detection -> Event workflow
- Time-based queries
- Risk-based queries
- Cascade deletes
- Multi-camera isolation
- Transaction boundaries

## Coverage Goals

- **Target**: 95%+ for integration paths
- **Focus**: Critical user workflows and API contracts
- **Areas**:
  - All API endpoints (CRUD operations)
  - Database relationships and constraints
  - Error handling and validation
  - Security (path traversal, file types)
  - Multi-component interactions

## Troubleshooting

### Database initialization fails

- Check `get_settings.cache_clear()` is called
- Verify environment variables are set
- Ensure `init_db()` is awaited

### Mock Redis not working

- Verify patch path matches actual import
- Check mock is created before client fixture
- Ensure AsyncMock is used for async methods

### Tests interfere with each other

- Each test should use `integration_db` fixture
- Clear settings cache between tests
- Use function-scoped fixtures

### API client errors

- Check ASGITransport is used (not running server)
- Verify base_url is set
- Ensure app import happens after env setup

## Related Documentation

- `/backend/tests/AGENTS.md` - Test infrastructure overview
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/AGENTS.md` - Backend architecture
