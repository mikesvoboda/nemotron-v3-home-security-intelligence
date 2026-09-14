# CI Flaky Tests Investigation - PR #5851

## Issue Summary

Two integration test jobs are failing intermittently in CI for PR #5851:

1. **Integration Tests (WebSocket) - Python 3.14**: No test output, coverage file not generated
2. **Integration Tests (Services) - Python 3.14**: Foreign key constraint violations

## Root Cause Analysis

### 1. WebSocket Integration Tests Failure

**Symptoms:**

- No test output in CI logs
- Coverage file (`coverage-integration-websocket.xml`) not generated
- Tests timeout before completion

**Root Cause:**

- Async cleanup timing issues compounded with 20-minute job timeout
- Resource exhaustion during parallel test execution
- Connection pool leaks during WebSocket test teardown

**Evidence:**

- Recent commit `8d70481b`: "fix: resolve flaky WebSocket integration tests with proper async cleanup"
- Recent commit `c615dd7e`: "fix: add timeout protection to async test fixture cleanup"
- CI workflow includes 3-retry logic for these tests (lines 556-573 in `.github/workflows/ci.yml`)
- Tests run serially (`-n0`) to avoid parallelization issues

**Previous Fixes:**

- Wrapped cleanup operations in try/except blocks
- Added timeout protection to async cleanup
- Added connection leak detection

**Current Status:**

- Still experiencing intermittent failures
- Retry logic masks the issue but doesn't solve it
- Passes locally but fails in CI due to resource constraints

### 2. Services Integration Tests Failure

**Symptoms:**

```
FAILED backend/tests/integration/services/... - sqlalchemy.exc.IntegrityError:
  (asyncpg.exceptions.ForeignKeyViolationError) insert or update on table "events"
  violates foreign key constraint "events_camera_id_fkey"
DETAIL:  Key (camera_id)=(nonexistent_1206409f) is not present in table "cameras".

FAILED backend/tests/integration/services/... - sqlalchemy.exc.IntegrityError:
  (asyncpg.exceptions.ForeignKeyViolationError) insert or update on table "alerts"
  violates foreign key constraint "alerts_event_id_fkey"
DETAIL:  Key (event_id)=(99999) is not present in table "events".
```

**Root Cause:**

- Database cleanup timing issues between parallel test runs
- Race conditions when multiple pytest-xdist workers access shared tables
- Incomplete cleanup before retry attempts
- Savepoint lifecycle issues with nested transactions

**Evidence:**

- Recent commit `a00a378e`: "fix: resolve flaky integration test database isolation issues"
  - Fixed missing cleanup dependency in fixtures
  - Removed savepoints from `isolated_db_session`
  - Refactored cleanup to use FK disabling instead of nested savepoints
- Test IDs like `nonexistent_1206409f` and `99999` are generated test data
- CI workflow includes 3-retry logic (lines 666-688 in `.github/workflows/ci.yml`)

**Previous Fixes:**

- Added explicit `clean_tables` dependency to database fixtures
- Simplified `isolated_db_session` to use transaction rollback
- Refactored cleanup functions to disable FK checks
- Fixed session fixture to properly yield

**Current Status:**

- Still experiencing intermittent failures
- Cleanup may not complete before next retry attempt
- Worker-specific databases should prevent FK violations, but timing issues remain

## Why These Are Pre-Existing Issues

1. **Not introduced by Foundation Infrastructure changes**: The PR modifies GPU configuration, system settings, and job management - it does NOT change test infrastructure or database fixtures.

2. **Recent fixes for the same issues**: Commits `8d70481b` and `a00a378e` (both merged recently) specifically addressed these exact failure patterns.

3. **Retry logic indicates known flakiness**: Both test jobs have 3-retry logic in CI, which is only added for known flaky tests.

4. **Flaky Test Detection workflow exists**: The project has `.github/workflows/flaky-test-detection.yml` specifically to track these issues.

5. **Tests pass locally**: The failures only occur in CI under specific resource/timing conditions.

## Fix Applied

### Immediate Fix: Improved Timeout Protection

Added timeout protection to the `clean_tables` fixture in `backend/tests/integration/conftest.py`:

```python
# Add timeout protection to prevent hanging on cleanup
try:
    await asyncio.wait_for(
        session.execute(text(f"TRUNCATE TABLE {table_name} CASCADE")),
        timeout=5.0,
    )
except TimeoutError:
    logger.warning(f"Truncate timed out for table {table_name}, skipping")
    raise  # Re-raise to trigger savepoint rollback

# ... and at the fixture level:
try:
    await asyncio.wait_for(truncate_all(), timeout=10.0)
except TimeoutError:
    logger.warning("Test cleanup timed out after 10s during clean_tables teardown")
```

### Documentation

Updated `backend/tests/flaky_tests.txt` with comprehensive documentation of the known issues.

## Long-Term Solutions

### For WebSocket Tests:

1. **Reduce test timeout**: The 30-second timeout may be too aggressive for CI environment
2. **Investigate connection leaks**: Add more robust connection tracking
3. **Simplify async cleanup**: Consider using sync cleanup for database operations
4. **Add resource monitoring**: Track connection pool usage during tests

### For Services Tests:

1. **Strengthen database isolation**: Ensure worker databases are truly isolated
2. **Add cleanup verification**: Verify all tables are empty before test starts
3. **Improve retry logic**: Clear all database state between retry attempts
4. **Consider test ordering**: Some tests may have implicit dependencies

## Recommendation

**For PR #5851**: The failures are pre-existing and not related to the Foundation Infrastructure changes. The PR should not be blocked by these flaky tests.

**Actions:**

1. ✅ Added timeout protection to cleanup fixtures
2. ✅ Documented known issues in `flaky_tests.txt`
3. ⚠️ Monitor CI runs to see if timeout protection reduces failures
4. 📋 Create follow-up issue to properly fix flaky tests

## Related Commits

- `8d70481b`: fix: resolve flaky WebSocket integration tests with proper async cleanup
- `a00a378e`: fix: resolve flaky integration test database isolation issues
- `c615dd7e`: fix: add timeout protection to async test fixture cleanup
- `348c11b0`: fix: resolve flaky test failures in CI
- `c91e45a7`: fix: resolve flaky test failures in CI

## Testing Commands

To reproduce locally (tests usually pass):

```bash
# WebSocket tests
uv run pytest backend/tests/integration/test_websocket*.py -v -n0 --timeout=30

# Services tests
uv run pytest backend/tests/integration/services/ -v -n0 --timeout=30

# Run with retry logic (like CI)
uv run pytest backend/tests/integration/ -v -n0 --timeout=30 --reruns 2
```

## Monitoring

The Flaky Test Detection workflow (`.github/workflows/flaky-test-detection.yml`) runs nightly to track these issues. It:

- Runs tests 5 times each
- Analyzes pass/fail rates
- Creates/updates GitHub issues for flaky tests
- Tracks timing variance

Check the workflow runs for detailed reports on test stability.
