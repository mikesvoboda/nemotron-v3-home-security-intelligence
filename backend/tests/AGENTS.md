# Backend Tests Directory

## Purpose

This directory contains all automated tests for the backend Python application. Tests are organized into unit tests (isolated component testing) and integration tests (multi-component workflows).

## Directory Structure

```
backend/tests/
├── conftest.py           # Shared pytest fixtures and configuration
├── unit/                 # Unit tests for isolated components
├── integration/          # Integration tests for multi-component workflows
├── check_syntax.py       # Syntax validation script
└── verify_database.py    # Database verification script
```

## Test Organization

### Unit Tests (`unit/`)

Tests for individual components in isolation:

- **Models**: Database model definitions and relationships
- **Core**: Configuration, database connections, Redis client
- **Services**: Business logic (file watcher, detectors, analyzers, aggregators)

### Integration Tests (`integration/`)

Tests for complete workflows across multiple components:

- **API endpoints**: FastAPI routes and middleware
- **Full stack**: Database workflows from camera creation to event generation
- **Media serving**: File serving and security validation

## Shared Fixtures (conftest.py)

### `isolated_db`

- **Scope**: Function
- **Purpose**: Creates isolated temporary database for each test
- **Usage**: Ensures clean database state, no test pollution
- **Cleanup**: Automatically restores environment after test

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
```

### Unit tests only

```bash
pytest backend/tests/unit/ -v
```

### Integration tests only

```bash
pytest backend/tests/integration/ -v
```

### Specific test file

```bash
pytest backend/tests/unit/test_models.py -v
```

### Specific test

```bash
pytest backend/tests/unit/test_models.py::TestCameraModel::test_create_camera -v
```

## Coverage Requirements

- **Target**: 98%+ coverage for all backend code
- **Enforced by**: Pre-commit hooks and CI/CD
- **Command**: `pytest backend/tests/ -v --cov=backend --cov-report=term-missing`

## Test Patterns

### Database Testing

- Use `isolated_db` fixture for clean database state
- Tests run against temporary SQLite databases
- Each test gets fresh database instance
- Automatic cleanup after test completion

### Async Testing

- All async tests use `@pytest.mark.asyncio` decorator
- Configured in `pytest.ini` with `asyncio_mode = auto`
- Proper handling of async context managers and sessions

### Mocking Strategy

- **Unit tests**: Mock all external dependencies
- **Integration tests**: Mock only external services (Redis), use real database
- Common mocks: Redis client, HTTP clients, file system operations

### Fixture Organization

- Shared fixtures in `conftest.py`
- Test-specific fixtures in individual test files
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
4. **Speed**: Unit tests should be fast (<10s total), integration tests moderate (<30s total)
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

## Troubleshooting

### Tests fail with "Database not initialized"

- Ensure you're using `isolated_db` fixture
- Check that `get_settings.cache_clear()` is being called

### Tests interfere with each other

- Verify each test uses function-scoped fixtures
- Check for shared global state
- Use `isolated_db` for database tests

### Async errors

- Ensure test has `@pytest.mark.asyncio` decorator
- Check all async functions are awaited
- Verify async context managers use `async with`

### Coverage gaps

- Run with `--cov-report=term-missing` to see uncovered lines
- Check if branches are covered (use `--cov-branch`)
- Add tests for error conditions and edge cases

## Next Steps for AI Agents

1. **Read test file**: Use Read tool to examine test structure
2. **Understand fixtures**: Check conftest.py for available fixtures
3. **Run tests**: Use Bash tool with pytest command
4. **Add tests**: Follow existing patterns, use appropriate fixtures
5. **Verify coverage**: Run with --cov flag to ensure 98%+ coverage
