# Contract Tests

This directory contains contract tests for API compatibility verification.

## Purpose

Contract tests verify that API responses conform to their documented schemas, ensuring:

- Response schemas match OpenAPI definitions
- Error responses follow consistent patterns (404, 422, 400)
- API compatibility is maintained across code changes
- Breaking changes are caught before deployment

## Test Coverage

The contract tests cover these critical endpoints:

### Events API

- `GET /api/events` - List events with pagination and filtering
- `GET /api/events/{id}` - Get single event by ID
- `GET /api/events/stats` - Get aggregated event statistics

### Cameras API

- `GET /api/cameras` - List cameras with optional status filter
- `GET /api/cameras/{id}` - Get single camera by ID

### System API

- `GET /health` - Simple liveness probe
- `GET /ready` - Readiness probe with dependency checks
- `GET /api/system/health` - Detailed health status with services
- `GET /api/system/gpu` - GPU statistics
- `GET /api/system/stats` - System-wide statistics

### Detections API

- `GET /api/detections` - List detections with pagination and filtering
- `GET /api/detections/{id}` - Get single detection by ID
- `GET /api/detections/stats` - Detection class distribution

### AI Audit API

- `GET /api/ai-audit/stats` - AI pipeline audit statistics
- `GET /api/ai-audit/leaderboard` - Model contribution leaderboard

### Error Response Contracts

- 404 responses include `detail` field
- 422 validation errors include `detail` field
- 400 bad request errors include `detail` field

### Pagination Contracts

- Default pagination values (limit=50, offset=0)
- Maximum limit enforcement (1000)

### WebSocket Message Contracts (NEM-1684)

Schema validation tests for WebSocket message formats:

- `WebSocketEventMessage` - Event notification structure
- `WebSocketEventData` - Event data payload with risk score constraints
- `WebSocketServiceStatusMessage` - Service status updates
- `WebSocketServiceStatusData` - Service health information
- `WebSocketSceneChangeMessage` - Camera scene change alerts
- `WebSocketSceneChangeData` - Scene change details
- `WebSocketErrorResponse` - Error message format
- `WebSocketPongResponse` - Heartbeat response
- `RiskLevel` enum - Risk level values (low, medium, high, critical)

### Health API Contracts (NEM-1684)

- `GET /api/system/health` - HealthResponse schema validation
- `GET /api/system/health/ready` - ReadinessResponse schema validation

## File Structure

```
backend/tests/contracts/
├── AGENTS.md                        # This documentation
├── __init__.py                      # Package marker
├── conftest.py                      # Shared fixtures (mock clients, sessions)
├── test_api_contracts.py            # Core API contract tests (32+ tests)
├── test_openapi_schema_validation.py # OpenAPI schema validation tests
├── test_schemathesis_contracts.py   # Property-based schema testing with Schemathesis
└── test_websocket_contracts.py      # WebSocket message contract tests
```

## Test Files (4 total)

| File                                | Focus                           | Key Coverage                    |
| ----------------------------------- | ------------------------------- | ------------------------------- |
| `test_api_contracts.py`             | Core REST API contracts         | Events, cameras, system, etc.   |
| `test_openapi_schema_validation.py` | OpenAPI spec validation         | Schema conformance              |
| `test_schemathesis_contracts.py`    | Property-based contract testing | Fuzzing with schema constraints |
| `test_websocket_contracts.py`       | WebSocket message contracts     | Event, status, scene messages   |

## Running Contract Tests

```bash
# Run all contract tests
uv run pytest backend/tests/contracts/ -v

# Run with coverage
uv run pytest backend/tests/contracts/ --cov=backend/api --cov-report=term-missing

# Run specific test class
uv run pytest backend/tests/contracts/test_api_contracts.py::TestEventsAPIContract -v
```

## Key Patterns

### Mock Database Sessions

Tests use mock database sessions to avoid needing a real database:

```python
with patch("backend.api.routes.events.get_db") as mock_get_db:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_event
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def mock_db_generator():
        yield mock_session

    mock_get_db.return_value = mock_db_generator()
```

### Mock Data Factories

Helper functions create consistent test data:

- `create_mock_event()` - Mock Event objects
- `create_mock_camera()` - Mock Camera objects
- `create_mock_detection()` - Mock Detection objects
- `create_mock_gpu_stats()` - Mock GPU statistics

### ASGI Test Client

Tests use httpx AsyncClient with ASGITransport for direct ASGI testing:

```python
transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://testserver") as client:
    response = await client.get("/api/events")
```

## CI Integration

Contract tests run in CI via the `contract-tests` job in `.github/workflows/ci.yml`:

- Runs on every PR and push to main
- Uses PostgreSQL and Redis service containers
- Reports test results as artifacts

## Adding New Contract Tests

1. Add mock factory if testing a new model type
2. Create test class named `Test{Resource}APIContract`
3. Test both success and error cases:
   - Valid response schema
   - 404 for not found
   - 422 for validation errors
   - 400 for bad requests
4. Verify pagination if applicable

## Frontend Contract Tests (NEM-1684)

Companion frontend tests verify TypeScript types match API responses:

```bash
# Run frontend contract tests
cd frontend && npm test -- --run api-contracts
```

See: `frontend/src/__tests__/api-contracts.test.ts`

## Contract Verification Script

Run both backend and frontend contract tests:

```bash
# Run all contract tests
./scripts/check-api-contracts.sh

# Backend only
./scripts/check-api-contracts.sh --backend

# Frontend only
./scripts/check-api-contracts.sh --frontend

# Verbose output
./scripts/check-api-contracts.sh --verbose
```

## Related Documentation

- Backend API routes: `backend/api/routes/AGENTS.md`
- API schemas: `backend/api/schemas/AGENTS.md`
- Integration tests: `backend/tests/integration/AGENTS.md`
- Frontend contract tests: `frontend/src/__tests__/api-contracts.test.ts`
- Contract verification script: `scripts/check-api-contracts.sh`
