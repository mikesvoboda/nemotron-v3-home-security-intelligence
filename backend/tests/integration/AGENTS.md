# Integration Tests Directory

## Purpose

Integration tests verify that multiple components work together correctly. Unlike unit tests that isolate individual functions, integration tests validate real interactions between database, models, API endpoints, WebSocket channels, and services using PostgreSQL via testcontainers and mocked Redis.

## Running Tests

### Parallel Execution (Recommended)

Integration tests now support **parallel execution** with pytest-xdist, achieving up to **5x speedup**:

```bash
# Parallel execution with 8 workers (recommended)
uv run pytest backend/tests/integration/ -n8 --dist=worksteal

# Parallel execution with auto workers (may use too many on high-core machines)
uv run pytest backend/tests/integration/ -n auto --dist=worksteal

# Benchmark results (1575 tests):
# - Serial (-n0):  ~169 seconds
# - 4 workers:     ~50 seconds  (3.4x speedup)
# - 8 workers:     ~33 seconds  (5.1x speedup)
# - 16 workers:    ~28 seconds  (6x speedup, but more flaky tests)
```

**Recommended:** Use `-n8` for the best balance of speed and reliability.

### Serial Execution

```bash
# All integration tests (serial - legacy mode)
pytest backend/tests/integration/ -v -n0

# Single test file
pytest backend/tests/integration/test_api.py -v

# Specific test
pytest backend/tests/integration/test_api.py::test_root_endpoint -v

# With coverage
pytest backend/tests/integration/ -v --cov=backend --cov-report=html

# With verbose output
pytest backend/tests/integration/ -vv -s --log-cli-level=DEBUG
```

## Directory Structure

```
backend/tests/integration/
├── AGENTS.md                              # This file
├── conftest.py                            # Integration-specific fixtures
├── __init__.py                            # Package initialization
├── .gitkeep                               # Directory placeholder
├── COVERAGE.md                            # Coverage documentation
├── README.md                              # Integration test documentation
├── api/                                   # API integration tests (5 files)
├── database/                              # Database isolation tests
├── repositories/                          # Repository pattern tests (5 files)
├── services/                              # Service integration tests (3 files)
├── websocket/                             # WebSocket integration tests (1 file)
└── test_*.py                              # Root test files (109 total)
```

## Test Files (109+ total at root level)

### API Endpoint Tests (21 files)

| File                          | Endpoints Tested                 |
| ----------------------------- | -------------------------------- |
| `test_api.py`                 | `/`, `/health`, CORS, lifecycle  |
| `test_admin_api.py`           | `/api/admin/*` admin operations  |
| `test_ai_audit_api.py`        | `/api/ai-audit/*` AI audit ops   |
| `test_alerts_api.py`          | `/api/alerts/*` alert rules      |
| `test_audit_api.py`           | `/api/audit/*` audit logs        |
| `test_cameras_api.py`         | `/api/cameras/*` CRUD operations |
| `test_detections_api.py`      | `/api/detections/*`              |
| `test_dlq_api.py`             | `/api/dlq/*` dead letter queue   |
| `test_entities_api.py`        | `/api/entities/*` entity mgmt    |
| `test_events_api.py`          | `/api/events/*` with filtering   |
| `test_logs_api.py`            | `/api/logs/*`                    |
| `test_media_api.py`           | `/api/media/*` file serving      |
| `test_metrics_api.py`         | `/api/metrics/*` metrics data    |
| `test_notification_api.py`    | `/api/notifications/*`           |
| `test_search_api.py`          | `/api/search/*`                  |
| `test_system_api.py`          | `/api/system/*`                  |
| `test_zones_api.py`           | `/api/zones/*` zone CRUD         |
| `test_websocket.py`           | `/ws/events`, `/ws/system`       |
| `test_websocket_auth.py`      | WebSocket authentication         |
| `test_websocket_broadcast.py` | WebSocket broadcasting           |

### Service Integration Tests (12 files)

| File                                    | Service Tested             |
| --------------------------------------- | -------------------------- |
| `test_batch_aggregator_integration.py`  | BatchAggregator            |
| `test_cache_service_integration.py`     | CacheService               |
| `test_cleanup_service.py`               | CleanupService             |
| `test_detector_client_integration.py`   | DetectorClient             |
| `test_dlq_retry_handler_integration.py` | DLQRetryHandler            |
| `test_file_watcher_filesystem.py`       | FileWatcher filesystem     |
| `test_file_watcher_integration.py`      | FileWatcher                |
| `test_health_monitor_integration.py`    | HealthMonitor              |
| `test_nemotron_analyzer_integration.py` | NemotronAnalyzer           |
| `test_nemotron_analyzer.py`             | NemotronAnalyzer (focused) |
| `test_system_broadcaster.py`            | SystemBroadcaster          |
| `test_video_streaming.py`               | VideoStreaming             |

### Model and Database Tests (8 files)

| File                     | Coverage                |
| ------------------------ | ----------------------- |
| `test_alert_dedup.py`    | Alert deduplication     |
| `test_alert_engine.py`   | Alert engine processing |
| `test_alert_models.py`   | Alert model operations  |
| `test_audit.py`          | Audit logging           |
| `test_baseline.py`       | Baseline calculations   |
| `test_database.py`       | Database operations     |
| `test_model_cascades.py` | Model cascade deletes   |
| `test_models.py`         | SQLAlchemy model tests  |

### Error Handling Tests (5 files)

| File                           | Coverage                         |
| ------------------------------ | -------------------------------- |
| `test_api_error_scenarios.py`  | API error scenarios              |
| `test_api_errors.py`           | API error handling               |
| `test_database_isolation.py`   | Savepoint, concurrency, cascades |
| `test_http_error_codes.py`     | HTTP error code validation       |
| `test_transaction_rollback.py` | Transaction rollback             |

### Pipeline and Full Stack Tests (7 files)

| File                                 | Coverage                          |
| ------------------------------------ | --------------------------------- |
| `test_circuit_breaker.py`            | Circuit breaker pattern           |
| `test_enrichment_pipeline.py`        | Enrichment pipeline               |
| `test_event_search.py`               | Event search functionality        |
| `test_full_stack.py`                 | Camera->Detection->Event workflow |
| `test_pipeline_e2e.py`               | Complete AI pipeline flow         |
| `test_redis_pubsub.py`               | Redis pub/sub                     |
| `test_vision_extraction_pipeline.py` | Vision extraction pipeline        |

### Infrastructure Tests (3 files)

| File                              | Coverage                      |
| --------------------------------- | ----------------------------- |
| `test_alembic_migrations.py`      | Database migration validation |
| `test_github_workflows.py`        | CI/CD workflow validation     |
| `test_object_types_trgm_index.py` | Trigram index tests           |

### Security Tests (1 file)

| File                     | Coverage                |
| ------------------------ | ----------------------- |
| `test_media_security.py` | Media endpoint security |

## Fixtures

Integration tests use fixtures from `backend/tests/integration/conftest.py`:

### Session-Scoped Fixtures (per xdist worker)

| Fixture              | Description                                         |
| -------------------- | --------------------------------------------------- |
| `postgres_container` | PostgreSQL container or local service               |
| `redis_container`    | Redis container or local service                    |
| `worker_db_url`      | Worker-specific database URL for parallel isolation |
| `worker_redis_url`   | Worker-specific Redis URL for parallel isolation    |

### Function-Scoped Fixtures (per test)

| Fixture               | Description                                        |
| --------------------- | -------------------------------------------------- |
| `integration_env`     | Sets DATABASE_URL, REDIS_URL, HSI_RUNTIME_ENV_PATH |
| `integration_db`      | Initializes PostgreSQL via testcontainers or local |
| `mock_redis`          | AsyncMock Redis client                             |
| `db_session`          | Direct AsyncSession access                         |
| `isolated_db_session` | AsyncSession with savepoint rollback               |
| `session`             | Alias for `isolated_db_session` (compatibility)    |
| `client`              | httpx AsyncClient with ASGITransport               |
| `clean_tables`        | DELETE all data before/after test                  |

## Parallel Execution Architecture (NEM-1363)

Integration tests support parallel execution via pytest-xdist with worker-isolated databases.

### How Worker Isolation Works

```
┌────────────────────────────────────────────────────────────────┐
│                    pytest-xdist Controller                       │
├────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │  gw0    │  │  gw1    │  │  gw2    │  │  gw3    │  ...      │
│  │ worker  │  │ worker  │  │ worker  │  │ worker  │           │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘           │
│       │            │            │            │                  │
│       ▼            ▼            ▼            ▼                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │security │  │security │  │security │  │security │           │
│  │_test_gw0│  │_test_gw1│  │_test_gw2│  │_test_gw3│           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
│                                                                  │
│                   PostgreSQL Server                              │
└────────────────────────────────────────────────────────────────┘
```

1. **Session-scoped containers**: PostgreSQL and Redis containers are started once per session
2. **Worker-specific databases**: Each xdist worker creates its own database (`security_test_gw0`, `security_test_gw1`, etc.)
3. **Worker-specific Redis DBs**: Each worker uses a different Redis database number (0-15)
4. **Automatic cleanup**: Worker databases are dropped at session end

### Key Implementation Details

```python
# Worker ID detection (from xdist)
worker_id = xdist.get_xdist_worker_id(request)  # 'gw0', 'gw1', or 'master'

# Database naming
db_name = f"security_test_{worker_id}"  # security_test_gw0, etc.

# Redis database selection
redis_db = int(worker_id.replace('gw', ''))  # 0, 1, 2, etc.
```

### Fixture Chain for Parallel Execution

```
worker_db_url (session) ─┐
                         ├─► integration_env ─► integration_db ─► session/client
worker_redis_url (session)┘
```

## Database Isolation (Per-Test)

Integration tests use automatic cleanup to prevent data leakage between tests:

### How It Works

1. **`client` fixture**: Cleans up ALL tables before and after each test

   - Uses DELETE statements (not TRUNCATE) to avoid locking
   - Cleans in FK-safe order: alerts -> detections -> events -> cameras, etc.
   - Ensures tests start with empty tables and don't leave data behind

2. **`db_session` fixture**: Standard session for use with `client`

   - When used with `client`, cleanup is handled by the `client` fixture
   - When used standalone, consider using `isolated_db_session` instead

3. **`isolated_db_session` fixture**: Savepoint-based isolation
   - Creates a savepoint before the test
   - Rolls back to savepoint after test (even on failure)
   - Best for tests that don't use `client` fixture

### Best Practices

```python
# For API tests - client handles cleanup
@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.post("/api/cameras", json={...})
    assert response.status_code == 201
    # Data is automatically cleaned up after test

# For API tests with direct DB access
@pytest.mark.asyncio
async def test_with_db(client, db_session):
    # Create data via API
    await client.post("/api/cameras", json={...})
    # Query via db_session
    result = await db_session.execute(select(Camera))
    # client fixture handles cleanup

# For standalone DB tests (no client)
@pytest.mark.asyncio
async def test_db_only(isolated_db_session):
    session = isolated_db_session
    camera = Camera(...)
    session.add(camera)
    await session.flush()
    # Data automatically rolled back after test
```

### Cleaned Tables

The cleanup function handles all tables in FK-safe order:

- alerts, event_audits, detections, activity_baselines, class_baselines, events
- alert_rules, audit_logs, gpu_stats, logs, zones
- cameras (parent table, deleted last)

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

- **Combined Target**: 95%+ for all backend code (unit + integration)
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
