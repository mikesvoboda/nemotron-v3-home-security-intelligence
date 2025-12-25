# Backend Tests Directory

## Purpose

This directory contains all automated tests for the backend Python application. Tests are organized into three levels: unit tests (isolated component testing), integration tests (multi-component workflows), and end-to-end tests (complete pipeline validation).

## Directory Structure

```
backend/tests/
├── conftest.py              # Shared pytest fixtures and configuration
├── unit/                    # Unit tests for isolated components
├── integration/             # Integration tests for API and multi-component workflows
├── e2e/                     # End-to-end pipeline integration tests
├── check_syntax.py          # Syntax validation script
└── verify_database.py       # Database verification script
```

## Test Organization

### Unit Tests (`unit/`)

Tests for individual components in isolation:

- **Core**: Configuration, database connections, Redis client
- **Models**: Database model definitions and relationships
- **Services**: Business logic (file watcher, detectors, analyzers, aggregators, broadcasters)
- **API Routes**: Individual endpoint handlers
- **Mocking**: All external dependencies (HTTP, Redis, file system) are mocked

**Total**: 22 test files, 453 test cases

### Integration Tests (`integration/`)

Tests for complete workflows across multiple components:

- **API endpoints**: FastAPI routes with real database operations
- **Full stack**: Database workflows from camera creation to event generation
- **Media serving**: File serving and security validation
- **WebSocket**: Real-time communication channels
- **Mocking**: Redis mocked, database uses temporary SQLite

**Total**: 10 test files, 177 test cases

### End-to-End Tests (`e2e/`)

Tests for the complete AI pipeline flow:

- **Complete pipeline**: File detection → RT-DETRv2 → Batch aggregation → Nemotron → Event creation → WebSocket broadcast
- **Error handling**: Service failures, timeouts, fallback behavior
- **Batch logic**: Time windows, idle timeouts, cleanup
- **Relationships**: Database integrity across cameras, detections, events
- **Mocking**: External AI services mocked, database and business logic real

**Total**: 1 test file, 8+ comprehensive E2E scenarios

## Shared Fixtures (conftest.py)

### `isolated_db`

- **Scope**: Function
- **Purpose**: Creates isolated temporary database for each test
- **Usage**: Ensures clean database state, no test pollution
- **Cleanup**: Automatically restores environment after test

```python
@pytest.mark.asyncio
async def test_database_operation(isolated_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Test code here
        pass
```

### `test_db`

- **Scope**: Function
- **Purpose**: Provides a callable session factory for unit tests
- **Usage**: Returns `get_session` function for database access
- **Cleanup**: Automatic cleanup and environment restoration

### `reset_settings_cache`

- **Scope**: Auto-used for all tests
- **Purpose**: Clears settings cache before/after each test
- **Usage**: Prevents global state leakage between tests

## Running Tests

### All tests

```bash
# From project root
pytest backend/tests/ -v

# With coverage
pytest backend/tests/ -v --cov=backend --cov-report=html

# With coverage threshold check (95%+)
pytest backend/tests/ -v --cov=backend --cov-report=term-missing --cov-fail-under=95
```

### Unit tests only

```bash
pytest backend/tests/unit/ -v
```

### Integration tests only

```bash
pytest backend/tests/integration/ -v
```

### End-to-end tests only

```bash
pytest backend/tests/e2e/ -v

# With E2E marker
pytest -m e2e -v
```

### Specific test file

```bash
pytest backend/tests/unit/test_models.py -v
```

### Specific test

```bash
pytest backend/tests/unit/test_models.py::TestCameraModel::test_create_camera -v
```

### With verbose debugging

```bash
pytest backend/tests/ -vv -s --log-cli-level=DEBUG
```

## Coverage Requirements

- **Target**: 95%+ coverage for all backend code
- **Enforced by**: Pre-commit hooks (ruff, mypy, pytest)
- **Command**: `pytest backend/tests/ -v --cov=backend --cov-report=term-missing`
- **Current status**: Unit tests at 95%+, integration tests comprehensive

## Test Patterns

### Database Testing

- Use `isolated_db` fixture for clean database state
- Tests run against temporary SQLite databases
- Each test gets fresh database instance
- Automatic cleanup after test completion

```python
@pytest.mark.asyncio
async def test_create_camera(isolated_db):
    async with get_session() as session:
        camera = Camera(id="test", name="Test Camera")
        session.add(camera)
        await session.commit()
        assert camera.id == "test"
```

### Async Testing

- All async tests use `@pytest.mark.asyncio` decorator
- Configured in `pytest.ini` with `asyncio_mode = auto`
- Proper handling of async context managers and sessions

```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

### Mocking Strategy

- **Unit tests**: Mock all external dependencies (HTTP, Redis, file system)
- **Integration tests**: Mock Redis, use real database
- **E2E tests**: Mock external AI services, use real business logic and database
- Common mocks: Redis client, HTTP clients (httpx), file system operations

### Fixture Organization

- Shared fixtures in `conftest.py`
- Test-specific fixtures in individual test files or subdirectory conftest
- Use function scope for isolation, session scope sparingly

## Test Dependencies

All test dependencies are in `backend/requirements.txt`:

- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `pytest-cov>=4.1.0` - Coverage reporting
- `httpx>=0.25.0` - Async HTTP client for API testing

## Testing Philosophy

1. **Isolation**: Each test should be independent and not rely on others
2. **Clarity**: Test names describe what is being tested and expected outcome
3. **Coverage**: Test both happy paths and error conditions
4. **Speed**: Unit tests fast (<10s total), integration moderate (<30s), E2E comprehensive (<1min)
5. **Maintainability**: Keep tests simple and readable, avoid complex test logic

## Common Test Scenarios

### Testing Database Operations

```python
@pytest.mark.asyncio
async def test_database_operation(isolated_db):
    from backend.core.database import get_session

    async with get_session() as session:
        # Test code here
        pass
```

### Testing API Endpoints

```python
@pytest.mark.asyncio
async def test_api_endpoint(client):
    response = await client.get("/api/endpoint")
    assert response.status_code == 200
```

### Testing with Mocked Redis

```python
@pytest.mark.asyncio
async def test_with_redis(mock_redis_client):
    mock_redis_client.get.return_value = "test_value"
    # Test code here
```

### Testing with Mocked HTTP

```python
with patch("httpx.AsyncClient") as mock_http:
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value={"result": "success"})
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_http.return_value.__aenter__.return_value = mock_client
    # Test code here
```

## Test Statistics

### Overall Test Count

- **Unit tests**: 453 test cases across 22 files
- **Integration tests**: 177 test cases across 10 files
- **E2E tests**: 8+ comprehensive scenarios in 1 file
- **Total**: 630+ test cases covering 95%+ of backend code

### Coverage by Component

- **Core** (config, database, redis, logging): 98%+
- **Models** (Camera, Detection, Event, GPUStats, Log): 98%+
- **Services** (AI pipeline, broadcasters, cleanup): 95%+
- **API Routes** (REST endpoints, logs): 95%+
- **WebSocket** (real-time channels): 90%+

## Troubleshooting

### Tests fail with "Database not initialized"

- Ensure you're using `isolated_db` fixture
- Check that `get_settings.cache_clear()` is being called
- Verify `await init_db()` is called after setting environment

### Tests interfere with each other

- Verify each test uses function-scoped fixtures
- Check for shared global state
- Use `isolated_db` for database tests
- Clear settings cache between tests

### Async errors

- Ensure test has `@pytest.mark.asyncio` decorator
- Check all async functions are awaited
- Verify async context managers use `async with`

### Coverage gaps

- Run with `--cov-report=term-missing` to see uncovered lines
- Check if branches are covered (use `--cov-branch`)
- Add tests for error conditions and edge cases

### Import errors

- Ensure backend path is in sys.path (conftest.py handles this)
- Check module names match file structure

### Mock not working

- Verify mock path matches import path in source
- Use `spec=ClassName` to catch attribute errors
- Check mock is applied before function call

## Pre-commit Integration

All tests are run automatically on commit via pre-commit hooks:

```bash
# Run pre-commit checks manually
pre-commit run --all-files

# Tests included in pre-commit:
# - ruff check (linting)
# - ruff format (formatting)
# - mypy (type checking)
# - pytest (95% coverage required)
```

**CRITICAL**: Never bypass pre-commit hooks with `--no-verify`

## Test Development Workflow

1. **Read AGENTS.md**: Understand test structure for the area you're working on
2. **Write test first** (TDD): Define expected behavior before implementation
3. **Run test** (should fail): Verify test catches the missing functionality
4. **Implement feature**: Write minimal code to make test pass
5. **Run test** (should pass): Verify implementation works
6. **Refactor**: Clean up code while keeping tests green
7. **Check coverage**: Ensure 95%+ coverage maintained

## Next Steps for AI Agents

1. **Read subdirectory AGENTS.md**: Explore `unit/`, `integration/`, or `e2e/` for specific test patterns
2. **Understand fixtures**: Check conftest.py files for available test fixtures
3. **Run tests**: Use Bash tool with pytest command to verify current state
4. **Add tests**: Follow existing patterns for new functionality
5. **Verify coverage**: Run with --cov flag to ensure 95%+ coverage
6. **Never skip tests**: All features must have tests before being marked complete

## Related Documentation

- `/backend/tests/unit/AGENTS.md` - Unit test patterns and fixtures
- `/backend/tests/integration/AGENTS.md` - Integration test architecture
- `/backend/tests/e2e/AGENTS.md` - End-to-end pipeline testing
- `/backend/AGENTS.md` - Backend architecture overview
- `/CLAUDE.md` - Project instructions and testing requirements
