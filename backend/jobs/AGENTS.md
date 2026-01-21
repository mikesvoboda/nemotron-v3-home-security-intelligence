# Backend Jobs - Agent Guide

## Purpose

This directory contains background job implementations for scheduled and periodic tasks. These jobs run independently of API requests and handle maintenance, cleanup, and monitoring functions.

## Files Overview

```
backend/jobs/
|-- __init__.py              # Package exports
|-- orphan_cleanup_job.py    # Orphaned file cleanup (NEM-2387)
|-- summary_job.py           # Summary generation job for periodic analytics
|-- timeout_checker_job.py   # Job timeout detection and handling
```

## `orphan_cleanup_job.py` - Orphan File Cleanup (NEM-2387)

Background job for cleaning up files that have no corresponding database records.

### OrphanCleanupJob Class

Periodically scans for and removes orphaned files with safety measures.

**Safety Features:**

| Feature       | Default | Description                              |
| ------------- | ------- | ---------------------------------------- |
| Age threshold | 24h     | Only delete files older than this        |
| Dry run mode  | True    | Log without actually deleting            |
| Size limit    | 10 GB   | Stop if cumulative deletion exceeds this |
| File patterns | -       | Only process known image/video patterns  |

**Constructor Parameters:**

| Parameter       | Type    | Default | Description                         |
| --------------- | ------- | ------- | ----------------------------------- |
| `min_age_hours` | int     | 24      | Minimum file age before deletion    |
| `dry_run`       | bool    | True    | If true, only log what would delete |
| `max_delete_gb` | float   | 10.0    | Max GB to delete in one run         |
| `scanner`       | Scanner | None    | Optional OrphanedFileScanner        |
| `job_tracker`   | Tracker | None    | Optional JobTracker for progress    |
| `base_path`     | Path    | None    | Base path to scan                   |

**Methods:**

| Method  | Description                            |
| ------- | -------------------------------------- |
| `run()` | Execute the cleanup job asynchronously |

### CleanupReport Dataclass

Report generated after cleanup operation:

| Field                | Type      | Description                 |
| -------------------- | --------- | --------------------------- |
| `scanned_files`      | int       | Total files scanned         |
| `orphaned_files`     | int       | Orphaned files found        |
| `deleted_files`      | int       | Files actually deleted      |
| `deleted_bytes`      | int       | Total bytes freed           |
| `failed_deletions`   | list[str] | Files that failed to delete |
| `duration_seconds`   | float     | Operation duration          |
| `dry_run`            | bool      | Whether was a dry run       |
| `skipped_young`      | int       | Files skipped (too young)   |
| `skipped_size_limit` | int       | Files skipped (size limit)  |

### OrphanCleanupScheduler Class

Scheduler for running cleanup jobs at configured intervals.

**Constructor Parameters:**

| Parameter        | Type    | Description                        |
| ---------------- | ------- | ---------------------------------- |
| `interval_hours` | int     | Hours between runs (from settings) |
| `min_age_hours`  | int     | Min file age (from settings)       |
| `dry_run`        | bool    | If true, don't delete files        |
| `job_tracker`    | Tracker | Optional JobTracker                |

**Methods:**

| Method    | Description                          |
| --------- | ------------------------------------ |
| `start()` | Start scheduled cleanup (idempotent) |
| `stop()`  | Stop scheduled cleanup               |

Supports async context manager (`async with`).

### Global Functions

| Function                           | Description                       |
| ---------------------------------- | --------------------------------- |
| `get_orphan_cleanup_scheduler()`   | Get or create singleton scheduler |
| `reset_orphan_cleanup_scheduler()` | Reset singleton (for testing)     |

### Configuration (from Settings)

| Setting                              | Description                  |
| ------------------------------------ | ---------------------------- |
| `orphan_cleanup_enabled`             | Enable/disable cleanup       |
| `orphan_cleanup_scan_interval_hours` | Hours between scans          |
| `orphan_cleanup_age_threshold_hours` | Min file age before deletion |

## `summary_job.py` - Summary Generation Job (NEM-2891)

Background job for generating dashboard summaries every 5 minutes using the Nemotron LLM.

### SummaryJob Class

Runs on a 5-minute interval to generate hourly and daily summaries of high/critical security events.

**What It Does:**

1. Calls `SummaryGenerator.generate_all_summaries()` to create summaries
2. Broadcasts updates via WebSocket to connected clients
3. Invalidates the Redis cache for summaries
4. Logs success/failure metrics

**Safety Features:**

| Feature                 | Description                                |
| ----------------------- | ------------------------------------------ |
| 60-second timeout       | Prevents hanging if LLM is unresponsive    |
| Graceful error handling | Logs errors without crashing the scheduler |
| Circuit breaker         | Integrated via SummaryGenerator            |

**Constructor Parameters:**

| Parameter          | Type             | Default | Description                        |
| ------------------ | ---------------- | ------- | ---------------------------------- |
| `generator`        | SummaryGenerator | None    | Optional SummaryGenerator instance |
| `broadcaster`      | EventBroadcaster | None    | Optional EventBroadcaster instance |
| `cache_service`    | CacheService     | None    | Optional CacheService instance     |
| `interval_minutes` | int              | 5       | Minutes between job runs           |

**Methods:**

| Method    | Description                         |
| --------- | ----------------------------------- |
| `start()` | Start scheduled job (idempotent)    |
| `stop()`  | Stop scheduled job                  |
| `run()`   | Execute a single summary generation |

### Helper Functions

| Function                   | Description                                 |
| -------------------------- | ------------------------------------------- |
| `invalidate_summary_cache` | Invalidate summary-related cache keys       |
| `broadcast_summary_update` | Broadcast summary update via WebSocket      |
| `get_summary_job`          | Get or create singleton SummaryJob instance |
| `reset_summary_job`        | Reset singleton (for testing)               |

### Cache Keys Invalidated

- `summaries:latest`
- `summaries:hourly`
- `summaries:daily`

## `timeout_checker_job.py` - Job Timeout Detection

Background task that periodically checks for stuck/timed-out jobs.

### TimeoutCheckerJob Class

Runs every 30 seconds by default to detect and handle timed-out jobs.

**Actions on Timeout:**

1. Marks timed-out jobs as failed
2. Reschedules jobs with remaining retry attempts

**Constructor Parameters:**

| Parameter         | Type           | Default | Description              |
| ----------------- | -------------- | ------- | ------------------------ |
| `redis_client`    | RedisClient    | -       | Required Redis client    |
| `timeout_service` | TimeoutService | None    | Optional timeout service |
| `check_interval`  | int            | 30      | Seconds between checks   |

**Properties:**

| Property         | Type | Description                |
| ---------------- | ---- | -------------------------- |
| `check_interval` | int  | Check interval in seconds  |
| `is_running`     | bool | Whether checker is running |

**Methods:**

| Method       | Description                           |
| ------------ | ------------------------------------- |
| `start()`    | Start background task (idempotent)    |
| `stop()`     | Stop background task                  |
| `run_once()` | Run single check (for testing/manual) |

### Global Functions

| Function                         | Description                   |
| -------------------------------- | ----------------------------- |
| `get_timeout_checker_job(redis)` | Get or create singleton       |
| `reset_timeout_checker_job()`    | Reset singleton (for testing) |

### FastAPI Integration

```python
from backend.jobs.timeout_checker_job import get_timeout_checker_job
from backend.core.redis import get_redis_client

@app.on_event("startup")
async def startup():
    redis = await get_redis_client()
    checker = get_timeout_checker_job(redis)
    await checker.start()

@app.on_event("shutdown")
async def shutdown():
    redis = await get_redis_client()
    checker = get_timeout_checker_job(redis)
    await checker.stop()
```

## Usage Example

```python
from backend.jobs.orphan_cleanup_job import OrphanCleanupJob, get_orphan_cleanup_scheduler
from backend.jobs.timeout_checker_job import get_timeout_checker_job

# Run a one-time cleanup
job = OrphanCleanupJob(min_age_hours=24, dry_run=False)
report = await job.run()
print(f"Deleted {report.deleted_files} files, freed {report.deleted_bytes} bytes")

# Start scheduled cleanup
scheduler = get_orphan_cleanup_scheduler()
await scheduler.start()

# Start timeout checker
checker = get_timeout_checker_job(redis_client)
await checker.start()
```

## Related Documentation

- `/backend/services/job_tracker.py` - Job tracking service
- `/backend/services/job_timeout_service.py` - Timeout detection service
- `/backend/services/orphan_scanner_service.py` - Orphaned file scanner
- `/backend/core/config.py` - Configuration settings
- `/backend/AGENTS.md` - Backend architecture overview
