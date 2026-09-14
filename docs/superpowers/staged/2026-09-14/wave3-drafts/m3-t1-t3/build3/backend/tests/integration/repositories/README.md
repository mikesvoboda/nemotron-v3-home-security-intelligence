# Repository Unit Tests

## Overview

Repository unit tests in this directory test database CRUD operations for the repository layer. These tests require special handling due to database state sharing.

## Important: Serial Execution Required

**These tests MUST run serially (`-n0`) and CANNOT be parallelized with pytest-xdist.**

### Why?

Repository unit tests use the `test_db` fixture from `/backend/tests/conftest.py`, which creates a single shared test database. Unlike integration tests (which use `worker_db_url` to create per-worker databases), unit tests do not have per-worker database isolation.

When multiple xdist workers try to run repository tests in parallel:

- They all access the same test database
- Concurrent DDL/DML operations cause PostgreSQL deadlocks
- Tests fail with `DeadlockDetectedError` or worker crashes

### Running Locally

```bash
# Correct - serial execution
pytest backend/tests/unit/repositories/ -n0 -v

# Wrong - will cause deadlocks
pytest backend/tests/unit/repositories/ -n auto
```

### CI Configuration

CI splits unit tests into two jobs:

1. **Parallelized tests** - All unit tests except repositories (with xdist)
2. **Serial tests** - Repository tests only (with `-n0`)

See `.github/workflows/ci.yml` for the implementation.

### Test Structure

- `test_camera_repository.py` - Camera repository tests
- `test_detection_repository.py` - Detection repository tests
- `test_event_repository.py` - Event repository tests

All files contain:

- `TestXxxRepositoryBasicCRUD` - Standard CRUD operations (create, read, update, delete, exists, count)
- `TestXxxRepositorySpecificMethods` - Domain-specific query methods

### Automatic Configuration

The `conftest.py` in this directory automatically:

1. Marks all tests with `pytest.mark.serial`
2. Groups tests with `pytest.mark.xdist_group(name="repository_tests_serial")`
3. Warns if xdist is enabled when running repository tests

### Future Improvements

To enable parallelization, repository tests would need:

1. Per-worker database isolation (like integration tests)
2. Refactor `test_db` fixture to use `worker_db_url` pattern
3. Add worker-specific database creation/cleanup logic

This is a larger refactoring and currently not prioritized.
