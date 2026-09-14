# Integration Tests for Backend Core

## Purpose

This directory contains integration tests for the `backend/core/` module that require a real database connection. These tests validate query explain logging and other database-level infrastructure against actual PostgreSQL operations.

## Key Files

| File                    | Tests For                             | Test Count |
| ----------------------- | ------------------------------------- | ---------- |
| `test_query_explain.py` | `QueryExplainLogger`, EXPLAIN ANALYZE | ~3         |

## Test Markers

All tests in this directory are marked as integration tests:

```python
pytestmark = pytest.mark.integration
```

## Test Patterns

### Query Explain Integration Tests

Tests verify EXPLAIN logging with real database queries:

```python
@pytest.mark.asyncio
async def test_explain_logging_with_real_query(session):
    """Test EXPLAIN logging with a real database query.

    This validates that the QueryExplainLogger integrates properly with
    SQLAlchemy's event system and can execute queries without errors.
    """
    engine = get_engine()
    setup_explain_logging(engine.sync_engine)

    # Execute a query that should trigger timing
    result = await session.execute(text("SELECT 1"))
    result.fetchall()

    # Test passes if no exceptions were raised
```

### EXPLAIN Output Verification

Tests verify EXPLAIN ANALYZE produces expected output structure:

```python
@pytest.mark.asyncio
async def test_explain_on_actual_table_query(session):
    """Test EXPLAIN output on actual table query."""
    # Create a simple query on the cameras table
    result = await session.execute(text("SELECT * FROM cameras LIMIT 10"))
    result.fetchall()

    # Manually run EXPLAIN to verify it works
    explain_result = await session.execute(
        text("EXPLAIN ANALYZE SELECT * FROM cameras LIMIT 10")
    )
    explain_rows = explain_result.fetchall()

    # Verify EXPLAIN output has expected structure
    assert len(explain_rows) > 0
    explain_text = " ".join(row[0] for row in explain_rows)
    assert "Scan" in explain_text or "Planning" in explain_text
```

## Fixtures Used

| Fixture   | Source                      | Purpose                                         |
| --------- | --------------------------- | ----------------------------------------------- |
| `session` | `backend/tests/conftest.py` | Async database session with savepoint isolation |

## Running Tests

```bash
# Run all core integration tests
uv run pytest backend/tests/integration/core/ -v -n0

# Run specific test file
uv run pytest backend/tests/integration/core/test_query_explain.py -v -n0

# Run with verbose output
uv run pytest backend/tests/integration/core/ -v -n0 --capture=no
```

## Test Requirements

- **Database**: Requires PostgreSQL database connection (via `DATABASE_URL`)
- **Tables**: Tests assume `cameras` table exists (created by Alembic migrations)
- **Isolation**: Uses savepoint-based transaction isolation for test cleanup

## What These Tests Validate

1. **SQLAlchemy Event Integration**: QueryExplainLogger properly hooks into SQLAlchemy's `before_cursor_execute` and `after_cursor_execute` events
2. **EXPLAIN ANALYZE Execution**: The ability to run `EXPLAIN ANALYZE` on queries without errors
3. **Output Structure**: EXPLAIN output contains expected plan elements (Scan, Planning, etc.)
4. **No Side Effects**: Queries with explain logging don't cause errors or unexpected behavior

## Related Documentation

| Path                             | Purpose                           |
| -------------------------------- | --------------------------------- |
| `/backend/core/AGENTS.md`        | Core module documentation         |
| `/backend/core/query_explain.py` | QueryExplainLogger implementation |
| `/backend/tests/AGENTS.md`       | Test infrastructure overview      |
