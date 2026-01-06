# Database Test Fixes Summary

## Problem Analysis

The database tests were failing with `sqlalchemy.exc.OperationalError: unable to open database file` errors. The root causes were:

1. **Global State Pollution**: The database module uses global variables (`_engine` and `_async_session_factory`) that persisted across tests
2. **Settings Cache Issues**: The `get_settings()` function uses `@lru_cache`, which cached settings and didn't pick up environment variable changes
3. **Insufficient Cleanup**: Tests didn't properly reset global state between runs
4. **Directory Creation Failures**: Config validator tried to create directories that didn't exist

## Fixes Implemented

### 1. Enhanced conftest.py (/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/conftest.py)

#### Added `isolated_db` Fixture

- Creates a temporary database file for each test
- Sets `DATABASE_URL` environment variable to temp database
- Clears settings cache before and after setting env var
- Closes any existing database connections before initialization
- Properly cleans up and restores original state after test

**Key improvements:**

```python
@pytest.fixture(scope="function")
async def isolated_db():
    # Save original state
    original_db_url = os.environ.get("DATABASE_URL")
    get_settings.cache_clear()

    # Create temp database in temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        # Ensure clean state
        await close_db()
        await init_db()

        yield

        # Cleanup
        await close_db()

    # Restore original state
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
```

#### Added `reset_settings_cache` Fixture (autouse)

- Automatically clears settings cache before and after each test
- Prevents cached settings from leaking between tests
- Non-async to avoid interfering with tests that check uninitialized state

### 2. Updated test_database.py (/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/unit/test_database.py)

#### Simplified `test_db` Fixture

Changed from:

```python
@pytest.fixture
async def test_db():
    # Complex setup with temp directory, env vars, etc.
    with tempfile.TemporaryDirectory() as tmpdir:
        # ... duplicate setup code ...
```

To:

```python
@pytest.fixture
async def test_db(isolated_db):
    # Just create test model table
    async with get_engine().begin() as conn:
        await conn.run_sync(TestModel.__table__.create, checkfirst=True)
    yield
```

#### Updated Standalone Tests

For tests that don't use `test_db` fixture (test_init_db, test_close_db):

- Added `get_settings.cache_clear()` calls
- Added `await close_db()` before initialization
- Properly restore environment and clear cache in finally blocks

Example:

```python
@pytest.mark.asyncio
async def test_init_db():
    original_db_url = os.environ.get("DATABASE_URL")
    get_settings.cache_clear()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_init.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"
        os.environ["DATABASE_URL"] = test_db_url
        get_settings.cache_clear()

        try:
            await close_db()  # Ensure clean state
            await init_db()
            # ... test assertions ...
        finally:
            await close_db()
            if original_db_url:
                os.environ["DATABASE_URL"] = original_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
            get_settings.cache_clear()
```

## Key Principles Applied

1. **Proper Isolation**: Each test gets its own temporary database
2. **Cache Management**: Settings cache cleared before and after each test
3. **Clean State**: Database connections closed before initialization
4. **Proper Cleanup**: Resources disposed and original state restored in finally blocks
5. **No Global State Leakage**: Each test starts with a clean slate

## Test Coverage

All 9 tests now have proper isolation:

1. `test_init_db` - Tests database initialization
2. `test_engine_without_init` - Tests error when engine accessed before init
3. `test_session_factory_without_init` - Tests error when factory accessed before init
4. `test_get_session_context_manager` - Tests session context manager
5. `test_get_session_rollback_on_error` - Tests rollback on exceptions
6. `test_get_db_dependency` - Tests FastAPI dependency injection
7. `test_multiple_sessions` - Tests multiple independent sessions
8. `test_session_isolation` - Tests transaction isolation
9. `test_table_creation` - Tests table creation
10. `test_close_db` - Tests cleanup and resource disposal

## Running the Tests

From the project root:

```bash
python3 -m pytest backend/tests/unit/test_database.py -v
```

Or use the provided script:

```bash
./backend/tests/run_db_tests.sh
```

## Files Modified

1. `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/conftest.py`

   - Added `isolated_db` fixture for database isolation
   - Added `reset_settings_cache` autouse fixture
   - Added path setup for imports

2. `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/unit/test_database.py`
   - Simplified `test_db` fixture to use `isolated_db`
   - Updated `test_init_db` with proper cache clearing
   - Updated `test_close_db` with proper cache clearing
   - Added `get_settings` import for cache management

## Files Created

1. `/home/msvoboda/github/nemotron-v3-home-security-intelligence/backend/tests/run_db_tests.sh`
   - Convenience script for running database tests

## Expected Results

All tests should now pass with proper isolation. Each test:

- Runs in its own temporary database
- Has no side effects on other tests
- Properly cleans up resources
- Doesn't leak global state

## Why This Works

1. **Temporary Directories**: Each test gets a fresh temp directory that's automatically cleaned up
2. **Cache Clearing**: The settings cache is cleared before and after tests, ensuring env var changes are picked up
3. **Proper Sequencing**: Database is closed before initialization, preventing "already open" errors
4. **Fixture Composition**: `test_db` builds on `isolated_db`, avoiding duplicate setup code
5. **Finally Blocks**: Cleanup happens even if tests fail, preventing cascading failures
