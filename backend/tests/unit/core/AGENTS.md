# Unit Tests - Core Components

## Purpose

The `backend/tests/unit/core/` directory contains unit tests for the core infrastructure components in `backend/core/`. These tests validate database connection management, session handling, ILIKE pattern escaping, and error handling for uninitialized state.

## Test Files

| File               | Tests For                                                       | Test Count |
| ------------------ | --------------------------------------------------------------- | ---------- |
| `test_database.py` | Database initialization, sessions, transactions, ILIKE escaping | 18 tests   |

## `test_database.py`

**Tests:** `backend/core/database.py`

### Test Classes

| Class                    | Tests | Description                                             |
| ------------------------ | ----- | ------------------------------------------------------- |
| `TestEscapeIlikePattern` | 9     | SQL ILIKE pattern escaping for `%`, `_`, `\` characters |
| `TestGetEngine`          | 1     | RuntimeError when engine not initialized                |
| `TestGetSessionFactory`  | 1     | RuntimeError when session factory not initialized       |
| `TestInitDb`             | 1     | URL validation (must be `postgresql+asyncpg://`)        |
| `TestCloseDb`            | 4     | Engine disposal, None handling, greenlet error handling |
| `TestGetSession`         | 2     | Commit on success, rollback on exception                |
| `TestGetDb`              | 2     | FastAPI dependency commit/rollback behavior             |

### Coverage Details

**ILIKE Pattern Escaping (`TestEscapeIlikePattern`)**

- Escapes `%` (wildcard) → `\%`
- Escapes `_` (single char wildcard) → `\_`
- Escapes `\` (escape char) → `\\`
- Handles empty strings, consecutive special chars, unicode

**Engine/Factory Initialization (`TestGetEngine`, `TestGetSessionFactory`)**

- Verifies `RuntimeError` raised when accessing uninitialized globals
- Uses module patching to temporarily set `_engine = None`

**Database Lifecycle (`TestInitDb`, `TestCloseDb`)**

- Validates database URL must use `postgresql+asyncpg://` driver
- Tests `close_db()` disposal of engine and session factory
- Handles greenlet-related `ValueError` gracefully (common in async contexts)

**Session Management (`TestGetSession`, `TestGetDb`)**

- `get_session()` context manager commits on success, rolls back on exception
- `get_db()` FastAPI dependency properly closes session in finally block

## Running Tests

```bash
# Run all core unit tests
uv run pytest backend/tests/unit/core/ -v

# Run specific test file
uv run pytest backend/tests/unit/core/test_database.py -v

# Run with coverage
uv run pytest backend/tests/unit/core/ -v --cov=backend/core

# Run specific test class
uv run pytest backend/tests/unit/core/test_database.py::TestEscapeIlikePattern -v

# Run single test
uv run pytest backend/tests/unit/core/test_database.py::TestCloseDb::test_close_db_handles_greenlet_error -v
```

## Fixtures Used

From `backend/tests/conftest.py`:

| Fixture                | Scope              | Description                                                         |
| ---------------------- | ------------------ | ------------------------------------------------------------------- |
| `reset_settings_cache` | function (autouse) | Clears settings cache before/after each test, sets default env vars |
| `isolated_db`          | function           | Full PostgreSQL instance with schema, for tests needing real DB     |
| `session`              | function           | Transaction-isolated session with savepoint rollback                |
| `test_db`              | function           | Callable session factory for manual session management              |
| `mock_redis`           | function           | Mock Redis client for tests not needing real Redis                  |

**Helper Functions:**

- `unique_id(prefix)` - Generates unique IDs like `test_abc12345` for parallel test isolation

## Test Patterns

**State Isolation Pattern:**

```python
# Save original state
original_engine = db_module._engine
try:
    db_module._engine = None  # Set test condition
    # ... test assertions ...
finally:
    db_module._engine = original_engine  # Restore
```

**Async Mock Pattern:**

```python
mock_session = AsyncMock()
mock_session.commit = AsyncMock()
mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
```

## Related Documentation

- `/backend/core/AGENTS.md` - Core infrastructure documentation
- `/backend/core/database.py` - Source code being tested
- `/backend/tests/conftest.py` - Shared fixtures and helpers
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
- `/backend/tests/AGENTS.md` - Test infrastructure overview
