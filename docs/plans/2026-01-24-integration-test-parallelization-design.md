# Integration Test Parallelization Design

> Accelerate integration tests via database-per-worker isolation

**Date:** 2026-01-24
**Status:** Proposed
**Goal:** Reduce integration test runtime from ~20 min to ~5 min

## Problem Statement

Integration tests currently run serially (`-n0`) to avoid database deadlocks when multiple tests modify schema or shared state. This results in:

- ~20 minute CI wait times for integration tests
- Slow developer feedback loop
- Bottleneck in the merge queue

## Solution: Database-per-Worker Isolation

Instead of sharing one database with locks, give each pytest-xdist worker its own database copy.

### Architecture

```
CI Runner starts
    └── Postgres container (single instance)
          ├── template_test (created once, schema applied)
          ├── test_db_gw0 (copied from template)
          ├── test_db_gw1 (copied from template)
          ├── test_db_gw2 (copied from template)
          └── test_db_gw3 (copied from template)
```

### Why This Works

- `CREATE DATABASE ... TEMPLATE` is nearly instant (filesystem copy)
- No locks between workers - completely independent execution
- Table truncation between tests is faster than schema recreation

## Implementation

### 1. Session Fixture: Template Database

Creates the template database once per CI run with full schema:

```python
@pytest.fixture(scope="session")
def template_database(base_database_url):
    """Create template database with schema for worker copies."""
    engine = create_engine(base_database_url.replace("/security_test", "/postgres"))
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # Exit transaction
        conn.execute(text("DROP DATABASE IF EXISTS template_test"))
        conn.execute(text("CREATE DATABASE template_test"))

    # Apply migrations to template
    template_engine = create_engine(base_database_url.replace("/security_test", "/template_test"))
    Base.metadata.create_all(template_engine)
    template_engine.dispose()

    yield "template_test"
```

### 2. Worker Fixture: Per-Worker Database

Each xdist worker gets its own database copy:

```python
@pytest.fixture(scope="session")
def worker_database(template_database, worker_id):
    """Create isolated database for this xdist worker."""
    db_name = f"test_db_{worker_id}"  # e.g., test_db_gw0

    engine = create_engine(base_url.replace("/security_test", "/postgres"))
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))
        conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
        conn.execute(text(f"CREATE DATABASE {db_name} TEMPLATE {template_database}"))

    yield db_name
```

### 3. Function Fixture: Table Cleanup

Truncate tables between tests (faster than recreating):

```python
@pytest.fixture(autouse=True)
async def clean_tables(async_session):
    """Truncate all tables between tests."""
    yield  # Test runs
    for table in reversed(Base.metadata.sorted_tables):
        await async_session.execute(text(f"TRUNCATE {table.name} CASCADE"))
    await async_session.commit()
```

### 4. CI Workflow Change

```yaml
# Before: -n0 (serial)
# After: -n auto (parallel)
- name: Run API integration tests
  run: |
    uv run pytest backend/tests/integration/ \
      -k "test_*_api" \
      -n auto \
      --timeout=30
```

## Edge Cases

### Database Connection Limits

Limit pool size per worker to stay under PostgreSQL's `max_connections`:

```python
@pytest.fixture(scope="session")
def async_engine(worker_database):
    return create_async_engine(
        f"postgresql+asyncpg://.../{worker_database}",
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True
    )
```

### Tests Requiring Serial Execution

Some tests legitimately need isolation. Keep `xdist_group` for these:

```python
@pytest.mark.xdist_group("schema_migrations")
def test_migration_rollback():
    ...

@pytest.mark.xdist_group("global_settings")
def test_settings_modification():
    ...
```

### Stale Database Cleanup

Remove leftover databases from failed runs:

```python
@pytest.fixture(scope="session", autouse=True)
def cleanup_stale_databases():
    """Remove leftover test databases from previous failed runs."""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT datname FROM pg_database WHERE datname LIKE 'test_db_gw%'"
        ))
        for row in result:
            conn.execute(text(f"DROP DATABASE IF EXISTS {row[0]}"))
```

### Redis Isolation

Use key prefixes per worker instead of separate instances:

```python
@pytest.fixture
def redis_prefix(worker_id):
    return f"test:{worker_id}:"

@pytest.fixture
def redis_client(redis_prefix):
    client = Redis(...)
    return PrefixedRedis(client, prefix=redis_prefix)
```

## Expected Performance

| Metric                 | Current    | After    |
| ---------------------- | ---------- | -------- |
| API integration tests  | ~15-20 min | ~4-5 min |
| Full integration suite | ~20 min    | ~6-8 min |
| Speedup                | -          | 3-4x     |

## Rollout Plan

### Phase 1: Implement Fixtures (Low Risk)

- Add `template_database` and `worker_database` fixtures
- Keep `-n0` in CI initially
- Fixtures work with serial execution too

### Phase 2: Enable Parallelization for Stable Tests

- Identify tests with no shared state dependencies
- Run subset with `-n auto`, keep others serial
- Monitor for flakiness

### Phase 3: Full Parallelization

- Convert remaining tests
- Remove `-n0` from CI
- Update documentation

## Rollback Plan

If flakiness increases, revert to `-n0` in CI while debugging. The fixtures work either way - no code changes needed to rollback.

## Files to Modify

| File                                    | Changes                                  |
| --------------------------------------- | ---------------------------------------- |
| `backend/tests/conftest.py`             | Add template/worker database fixtures    |
| `.github/workflows/ci.yml`              | Change `-n0` to `-n auto`                |
| `backend/tests/integration/conftest.py` | Add Redis prefix fixtures                |
| Various test files                      | Remove unnecessary `xdist_group` markers |

## Success Criteria

- [ ] Integration tests complete in <8 minutes
- [ ] No increase in test flakiness
- [ ] All 162 integration test files passing
- [ ] Local development also benefits from parallelization
