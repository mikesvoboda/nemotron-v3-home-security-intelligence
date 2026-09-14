# Unit Tests - Background Jobs

## Purpose

The `backend/tests/unit/jobs/` directory contains unit tests for background job implementations that handle scheduled tasks like cleanup, timeout checking, and maintenance operations.

## Directory Structure

```
backend/tests/unit/jobs/
├── AGENTS.md                      # This file
├── __init__.py                    # Package initialization
├── test_orphan_cleanup_job.py     # Orphan record cleanup job tests (25KB)
└── test_timeout_checker_job.py    # Timeout checker job tests (8KB)
```

## Test Files (2 total)

| File                          | Job Tested        | Key Coverage                       |
| ----------------------------- | ----------------- | ---------------------------------- |
| `test_orphan_cleanup_job.py`  | OrphanCleanupJob  | Orphaned record detection/cleanup  |
| `test_timeout_checker_job.py` | TimeoutCheckerJob | Stale job timeout and cancellation |

## Running Tests

```bash
# All job unit tests
uv run pytest backend/tests/unit/jobs/ -v

# Specific job tests
uv run pytest backend/tests/unit/jobs/test_orphan_cleanup_job.py -v

# With coverage
uv run pytest backend/tests/unit/jobs/ -v --cov=backend.jobs
```

## Test Categories

### OrphanCleanupJob Tests (`test_orphan_cleanup_job.py`)

Tests for orphan record cleanup:

| Test Class              | Coverage                               |
| ----------------------- | -------------------------------------- |
| `TestOrphanDetection`   | Identifying orphaned records           |
| `TestOrphanCleanup`     | Safe deletion of orphaned records      |
| `TestCleanupScheduling` | Job scheduling and intervals           |
| `TestCleanupSafety`     | Protection against accidental deletion |

**Key Tests:**

- Detect detections without events
- Detect events without cameras
- Clean orphans older than retention period
- Skip active/recent records
- Batch deletion for performance
- Dry-run mode for verification

### TimeoutCheckerJob Tests (`test_timeout_checker_job.py`)

Tests for job timeout handling:

| Test Class                 | Coverage                        |
| -------------------------- | ------------------------------- |
| `TestTimeoutDetection`     | Identifying timed-out jobs      |
| `TestTimeoutHandling`      | Job cancellation and cleanup    |
| `TestTimeoutConfiguration` | Configurable timeout thresholds |

**Key Tests:**

- Detect jobs exceeding timeout
- Cancel stuck jobs gracefully
- Update job status to failed
- Notify on timeout (alerts/logs)
- Configurable timeout per job type

## Test Patterns

### Orphan Detection

```python
@pytest.mark.asyncio
async def test_detects_orphaned_detections(mock_session, cleanup_job):
    # Create detection without associated event
    orphan = Detection(id="orphan", camera_id="cam", event_id=None)
    mock_session.execute.return_value.scalars.return_value.all.return_value = [orphan]

    orphans = await cleanup_job.find_orphaned_detections()
    assert len(orphans) == 1
    assert orphans[0].id == "orphan"
```

### Timeout Handling

```python
@pytest.mark.asyncio
async def test_cancels_timed_out_job(mock_session, timeout_checker):
    # Create job that started 2 hours ago
    stale_job = Job(
        id="stale",
        status="running",
        started_at=datetime.utcnow() - timedelta(hours=2)
    )
    mock_session.execute.return_value.scalars.return_value.all.return_value = [stale_job]

    await timeout_checker.check_and_cancel_timeouts()

    # Verify job was cancelled
    assert stale_job.status == "failed"
    assert "timeout" in stale_job.error.lower()
```

## Related Documentation

- `/backend/jobs/AGENTS.md` - Job implementations
- `/backend/tests/unit/services/AGENTS.md` - Service unit tests
- `/backend/tests/unit/AGENTS.md` - Unit test patterns
