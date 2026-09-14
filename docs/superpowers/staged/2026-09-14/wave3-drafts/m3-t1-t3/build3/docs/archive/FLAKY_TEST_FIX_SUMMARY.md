# Flaky Integration Test Fix Summary

## Problem

Integration tests in `backend/tests/integration/services/` were failing intermittently in CI with:

- `duplicate key value violates unique constraint` - tests creating objects with IDs that already exist
- `violates foreign key constraint` - cleanup happening in wrong order
- `savepoint does not exist` - savepoint lifecycle issues with nested transactions

## Root Causes

1. **Missing cleanup dependency**: Tests using `db_session` didn't explicitly depend on `clean_tables`, leading to incomplete cleanup between tests
2. **Savepoint lifecycle issues**: The `isolated_db_session` fixture was creating savepoints that could become invalid during test execution
3. **Improper cleanup with savepoints**: The `clean_tables` and `_cleanup_test_data` functions used savepoints within cleanup transactions, causing "savepoint does not exist" errors
4. **Transaction management**: SQLAlchemy AsyncSession starts transactions automatically; calling `begin()` explicitly could cause issues

## Fixes Applied

### 1. Added `clean_tables` dependency to session fixtures

**File**: `backend/tests/integration/conftest.py`

```python
@pytest.fixture
async def db_session(integration_db: str, clean_tables):
    """Yield a live AsyncSession with explicit clean_tables dependency."""
    # ...
```

This ensures cleanup happens after every test that uses `db_session`.

### 2. Removed savepoints from `isolated_db_session` fixture

**Before**:

```python
await session.execute(text("SAVEPOINT test_savepoint"))
# ... test runs ...
await session.execute(text("ROLLBACK TO SAVEPOINT test_savepoint"))
```

**After**:

```python
# Session automatically starts transaction on first use
yield session
# Rollback transaction after test
if session.in_transaction():
    await session.rollback()
```

This avoids savepoint lifecycle issues while still providing transaction isolation.

### 3. Simplified cleanup functions to avoid nested savepoints

**Before**:

```python
for table_name in deletion_order:
    await session.execute(text(f"SAVEPOINT sp_{table_name}"))
    await session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
    await session.execute(text(f"RELEASE SAVEPOINT sp_{table_name}"))
```

**After**:

```python
# Disable FK checks for faster, safer cleanup
await session.execute(text("SET session_replication_role = replica"))

for table_name in deletion_order:
    await session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))

await session.execute(text("SET session_replication_role = DEFAULT"))
```

This approach:

- Avoids savepoint nesting issues
- Is faster (no savepoint overhead)
- Handles missing tables gracefully
- Properly disables/re-enables FK checks for cleanup

### 4. Fixed session fixture to properly yield

Changed `session` fixture from `return isolated_db_session` to `yield isolated_db_session` for proper async generator behavior.

## Testing

### New Validation Test

Created `backend/tests/integration/test_cleanup_isolation.py` with tests that verify:

- No leftover data between tests
- Duplicate ID creation works (proves cleanup is working)
- Foreign key cleanup order is correct
- No savepoint errors occur
- Multiple flushes work without errors

### Running Tests

```bash
# Run the new cleanup isolation tests
uv run pytest backend/tests/integration/test_cleanup_isolation.py -n0 -v

# Run the services integration tests that were failing
uv run pytest backend/tests/integration/services/ -n0 -v --tb=short

# Full integration test suite (as run in CI)
uv run pytest backend/tests/integration/ -n0 -v
```

## Expected Behavior

After these fixes:

1. ✅ Tests run cleanly without duplicate key violations
2. ✅ No "savepoint does not exist" errors
3. ✅ No foreign key constraint violations during cleanup
4. ✅ Tests can be re-run multiple times without data accumulation
5. ✅ CI integration tests pass consistently

## Technical Details

### Why This Works

1. **Transaction-based isolation**: Each test gets a fresh transaction that's rolled back after completion
2. **Explicit cleanup**: The `clean_tables` fixture ensures TRUNCATE runs after every test
3. **No savepoint nesting**: By avoiding savepoints within cleanup transactions, we eliminate "savepoint does not exist" errors
4. **FK-safe cleanup**: Disabling FK checks during cleanup prevents constraint violations while maintaining data integrity for tests
5. **Worker isolation**: Each pytest-xdist worker still gets its own database copy for parallel execution

### Trade-offs

- **Slightly slower**: TRUNCATE CASCADE is used after each test (but still faster than DELETE)
- **More explicit**: Tests must request `db_session` or `isolated_db_session` to get cleanup
- **Better isolation**: Each test is truly isolated with guaranteed cleanup

## Related Issues

- Addresses flaky "Integration Tests (Services) - Python 3.14" CI failures
- Fixes test retry issues (tests were retrying 3 times due to database constraint violations)
- Improves test reliability and developer experience

## Files Modified

1. `backend/tests/integration/conftest.py`:

   - `db_session` fixture - added `clean_tables` dependency
   - `isolated_db_session` fixture - removed savepoints, simplified transaction management
   - `clean_tables` fixture - removed nested savepoints, used FK disabling
   - `_cleanup_test_data` function - removed nested savepoints, used FK disabling
   - `session` fixture alias - fixed to properly yield

2. `backend/tests/integration/test_cleanup_isolation.py` (new):
   - Comprehensive cleanup validation tests
