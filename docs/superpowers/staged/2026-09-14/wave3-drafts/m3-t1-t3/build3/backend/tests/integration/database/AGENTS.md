# Database Integration Tests

## Purpose

This directory contains integration tests for database-specific functionality, focusing on PostgreSQL transaction isolation levels, concurrent access patterns, and race condition prevention.

## Test Files

### test_isolation_levels.py

Comprehensive tests for PostgreSQL transaction isolation level behavior.

**Test Classes:**

1. **TestReadCommittedIsolation** - Tests for READ COMMITTED (default isolation level)

   - `test_read_committed_prevents_dirty_reads` - Verifies uncommitted changes aren't visible
   - `test_read_committed_allows_non_repeatable_reads` - Verifies data can change between reads
   - `test_read_committed_allows_phantom_reads` - Verifies new rows can appear between reads

2. **TestConcurrentReadBehavior** - Tests for concurrent read operations

   - `test_concurrent_reads_dont_block` - Verifies multiple readers execute simultaneously
   - `test_reads_dont_block_writes_in_read_committed` - Verifies reads don't prevent writes

3. **TestConcurrentWriteSerialization** - Tests for concurrent write operations

   - `test_concurrent_writes_to_same_row_serialized` - Verifies writes are properly serialized
   - `test_lost_update_prevention` - Verifies updates aren't lost in concurrent scenarios

4. **TestDeadlockDetectionAndRecovery** - Tests for deadlock handling

   - `test_deadlock_detected_and_reported` - Verifies deadlock detection raises appropriate errors
   - `test_deadlock_retry_logic` - Verifies retry patterns work correctly

5. **TestIsolationLevelConfiguration** - Tests for explicit isolation level settings
   - `test_read_committed_is_default` - Verifies default isolation level
   - `test_can_set_repeatable_read` - Verifies REPEATABLE READ can be configured
   - `test_can_set_serializable` - Verifies SERIALIZABLE can be configured
   - `test_repeatable_read_prevents_non_repeatable_reads` - Verifies REPEATABLE READ guarantees

## Key Patterns

### PostgreSQL Isolation Levels

| Isolation Level | Dirty Reads | Non-Repeatable Reads | Phantom Reads |
| --------------- | ----------- | -------------------- | ------------- |
| READ COMMITTED  | Prevented   | Possible             | Possible      |
| REPEATABLE READ | Prevented   | Prevented            | Possible      |
| SERIALIZABLE    | Prevented   | Prevented            | Prevented     |

### Testing Concurrent Access

Tests use `asyncio.gather()` to run concurrent operations:

```python
async def concurrent_operation(worker_id: int) -> bool:
    async with get_session() as session:
        # Perform database operation
        await session.commit()
        return True

tasks = [concurrent_operation(i) for i in range(10)]
results = await asyncio.gather(*tasks)
```

### Testing Isolation Behavior

Tests use multiple sessions to verify isolation:

```python
# Session 1: Start transaction
factory = get_session_factory()
session1 = factory()

try:
    # First read
    result = await session1.execute(select(Model).where(...))
    first_read = result.scalar_one()

    # Session 2: Make changes
    async with get_session() as session2:
        # Update data
        await session2.commit()

    # Session 1: Second read (may or may not see changes)
    session1.expire_all()  # Force fresh query
    result = await session1.execute(select(Model).where(...))
    second_read = result.scalar_one()

finally:
    await session1.close()
```

### Deadlock Simulation

Tests create deadlock scenarios by locking resources in opposite orders:

```python
async def transaction_1():
    async with get_session() as session:
        # Lock resource A, then B
        await session.execute(select(A).with_for_update())
        await asyncio.sleep(0.05)  # Create race condition window
        await session.execute(select(B).with_for_update())

async def transaction_2():
    async with get_session() as session:
        # Lock resource B, then A (opposite order)
        await session.execute(select(B).with_for_update())
        await asyncio.sleep(0.05)
        await session.execute(select(A).with_for_update())

# One will succeed, one will detect deadlock
await asyncio.gather(transaction_1(), transaction_2())
```

### Exception Handling

Always catch both `OperationalError` and `DBAPIError` for database errors:

```python
from sqlalchemy.exc import DBAPIError, OperationalError

try:
    await session.commit()
except (OperationalError, DBAPIError) as e:
    if "deadlock detected" in str(e).lower():
        # Handle deadlock
        pass
    else:
        raise
```

## Running Tests

```bash
# Run all isolation level tests
uv run pytest backend/tests/integration/database/test_isolation_levels.py -v

# Run specific test class
uv run pytest backend/tests/integration/database/test_isolation_levels.py::TestReadCommittedIsolation -v

# Run with serial execution (required for integration tests)
uv run pytest backend/tests/integration/database/test_isolation_levels.py -v -n0
```

## Related Documentation

- `/backend/core/database.py` - Database connection and session management
- `/backend/tests/integration/test_database_isolation.py` - Related isolation tests
- `/backend/tests/integration/test_transaction_rollback.py` - Transaction rollback tests
- `/docs/development/testing.md` - Comprehensive testing guide
- [PostgreSQL Isolation Levels](https://www.postgresql.org/docs/current/transaction-iso.html)
