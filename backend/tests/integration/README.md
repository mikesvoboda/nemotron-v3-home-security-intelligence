# Backend Integration Tests

This directory contains integration tests for the backend API and services.

## Test Files

### test_api.py
Tests for FastAPI application endpoints and middleware:

- **Root endpoint** (`/`) - Basic API health check
- **Health endpoint** (`/health`) - Detailed system health with database and Redis status
- **CORS middleware** - Cross-origin request handling and preflight requests
- **Lifespan events** - Application startup and shutdown behavior
- **Error handling** - Graceful degradation when services fail
- **Concurrent requests** - Multiple simultaneous requests handling

**Coverage:**
- 13 test cases covering API endpoints, middleware, and lifecycle management
- Mocks Redis to avoid requiring external services
- Uses in-memory SQLite for database tests
- Tests both success and failure scenarios

### test_full_stack.py
Tests for complete workflows across database, models, and business logic:

- **Camera operations** - Create, query, and manage cameras
- **Detection operations** - Link detections to cameras with metadata
- **Event operations** - Create security events from detection batches
- **Relationships** - Camera → Detection and Camera → Event relationships
- **Complete workflows** - End-to-end scenarios from camera creation through event generation
- **Time-based queries** - Filter detections and events by timestamps
- **Risk-based queries** - Filter events by risk level
- **Cascade deletes** - Verify foreign key constraints and cascade behavior
- **Data isolation** - Ensure multi-camera operations don't interfere

**Coverage:**
- 14 test cases covering full stack database operations
- Tests realistic multi-step workflows
- Validates SQLAlchemy relationships and cascade behavior
- Ensures data integrity across sessions

## Running Tests

### Run all integration tests:
```bash
pytest backend/tests/integration/ -v
```

### Run specific test file:
```bash
pytest backend/tests/integration/test_api.py -v
pytest backend/tests/integration/test_full_stack.py -v
```

### Run with coverage:
```bash
pytest backend/tests/integration/ -v --cov=backend --cov-report=html
```

### Run specific test:
```bash
pytest backend/tests/integration/test_api.py::test_root_endpoint -v
```

## Test Infrastructure

### Fixtures

**test_api.py fixtures:**
- `test_db_setup` - Temporary SQLite database for API tests
- `mock_redis` - Mocked Redis client to avoid external dependencies
- `client` - AsyncClient with ASGITransport for testing FastAPI app

**test_full_stack.py fixtures:**
- `test_db` - Full database setup with all models and tables created
- Automatically cleans up after each test

### Mocking Strategy

Integration tests mock external services while testing real interactions:
- **Redis**: Mocked to avoid requiring Redis server during tests
- **Database**: Real SQLite in-memory database for authentic testing
- **FastAPI app**: Real application tested via ASGITransport (no server needed)

## Test Dependencies

Required packages (from `backend/requirements.txt`):
- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `httpx>=0.25.0` - Async HTTP client for API testing

## Architecture Notes

### Why ASGITransport?
Tests use `httpx.AsyncClient` with `ASGITransport` instead of running a real server:
- Faster test execution (no server startup overhead)
- No port conflicts or cleanup issues
- Direct access to application without network layer
- Same behavior as production without complexity

### Database Isolation
Each test gets a fresh temporary database:
- Created in `tempfile.TemporaryDirectory()`
- Automatically cleaned up after test completes
- No cross-test pollution
- Fast in-memory operations

### Async Pattern
All tests use `pytest.mark.asyncio` decorator:
- Configured in `pytest.ini` with `asyncio_mode = auto`
- Properly handles async context managers
- Ensures database sessions are cleanly closed

## Coverage Summary

**API Integration Tests (test_api.py):**
- ✓ HTTP endpoints and routing
- ✓ CORS middleware configuration
- ✓ Application lifecycle (startup/shutdown)
- ✓ Error handling and graceful degradation
- ✓ Health check with service status
- ✓ Concurrent request handling

**Full Stack Integration Tests (test_full_stack.py):**
- ✓ CRUD operations for all models
- ✓ Foreign key relationships
- ✓ Cascade delete behavior
- ✓ Complex queries (time-based, filtered)
- ✓ Multi-step workflows
- ✓ Transaction isolation
- ✓ Data integrity across sessions

## Future Enhancements

Potential additions for comprehensive coverage:
- WebSocket endpoint tests (when implemented)
- Real Redis integration tests (optional, separate from mocked tests)
- Performance and load testing
- API rate limiting tests
- Authentication middleware tests (if added)
- File upload integration tests
