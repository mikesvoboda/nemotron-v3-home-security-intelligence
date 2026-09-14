# Stream Manager Test Suite Summary (TDD Phase 2)

## Overview

Comprehensive test suite for StreamManager service following TDD RED-GREEN-REFACTOR cycle.

**Status:** RED phase (all tests skipped, implementation pending)
**Total Tests:** 50 tests (33 unit + 17 integration)
**Related Issue:** NEM-4196

## Test Coverage

### Unit Tests (33 tests)

Location: `backend/tests/unit/services/test_stream_manager.py`

#### Initialization Tests (3)

- ✓ `test_stream_manager_accepts_redis_client` - Redis client injection
- ✓ `test_stream_manager_initializes_with_default_state` - Default running=False
- ✓ `test_stream_manager_accepts_optional_dependencies` - Optional params

#### Start/Stop Tests (7)

- ✓ `test_start_initializes_running_state` - Sets running=True
- ✓ `test_start_captures_event_loop` - Captures asyncio loop
- ✓ `test_start_is_idempotent` - Multiple starts safe
- ✓ `test_start_without_event_loop_raises_error` - Fails outside async context
- ✓ `test_stop_sets_running_to_false` - Sets running=False
- ✓ `test_stop_cleans_up_all_streams` - Releases all captures
- ✓ `test_stop_without_start_is_safe` - Idempotent stop
- ✓ `test_stop_clears_event_loop_reference` - Clears \_loop

#### Stream Management Tests (7)

- ✓ `test_add_stream_registers_new_stream` - Creates VideoCapture
- ✓ `test_add_stream_uses_tcp_transport` - TCP transport only
- ✓ `test_add_stream_updates_health_in_redis` - Redis health tracking
- ✓ `test_add_stream_duplicate_camera_id_updates_url` - Replace stream on duplicate
- ✓ `test_remove_stream_closes_video_capture` - Calls capture.release()
- ✓ `test_remove_stream_deletes_redis_health_key` - Deletes health key
- ✓ `test_remove_stream_nonexistent_camera_is_safe` - No-op for missing stream

#### Health Tracking Tests (3)

- ✓ `test_get_stream_health_returns_health_dict` - Returns health data
- ✓ `test_get_stream_health_nonexistent_stream` - Returns None/empty
- ✓ `test_health_tracking_updates_periodically` - Periodic updates

#### Reconnection Tests (5)

- ✓ `test_exponential_backoff_calculation` - 5s, 10s, 20s, 40s, 60s
- ✓ `test_stream_failure_triggers_reconnection` - Retry on failure
- ✓ `test_reconnection_uses_exponential_backoff` - Increasing delays
- ✓ `test_max_backoff_capped_at_60_seconds` - Max 60s cap
- ✓ `test_successful_reconnection_resets_backoff` - Reset on success

#### Error Handling Tests (3)

- ✓ `test_stream_read_error_logged_not_raised` - Log errors, don't crash
- ✓ `test_redis_error_does_not_stop_stream` - Continue on Redis errors
- ✓ `test_invalid_rtsp_url_handled_gracefully` - Handle invalid URLs

#### Integration Tests (5)

- ✓ `test_multiple_concurrent_streams` - Multiple streams independently
- ✓ `test_graceful_shutdown_with_active_streams` - Clean shutdown
- ✓ `test_async_context_manager_support` - Context manager protocol
- ✓ `test_concurrent_add_remove_operations` - Thread-safe operations

### Integration Tests (17 tests)

Location: `backend/tests/integration/test_stream_manager.py`

#### Lifecycle Tests (2)

- ✓ `test_stream_manager_lifecycle_with_event_loop` - Event loop integration
- ✓ `test_start_stop_multiple_cycles` - Multiple lifecycle cycles

#### Redis Integration Tests (5)

- ✓ `test_redis_health_key_persistence` - Key format: hsi:stream:health:{camera_id}
- ✓ `test_redis_health_data_format` - Health data structure
- ✓ `test_redis_health_key_cleanup_on_remove` - Key deletion
- ✓ `test_get_stream_health_retrieves_from_redis` - Retrieve from Redis
- ✓ `test_redis_error_handling_during_health_update` - Handle Redis failures

#### Concurrency Tests (3)

- ✓ `test_multiple_streams_concurrent_health_updates` - Concurrent updates
- ✓ `test_concurrent_add_remove_operations_integration` - Real async scheduling
- ✓ `test_stream_health_updates_with_real_timing` - Periodic updates with timing

#### Shutdown Tests (3)

- ✓ `test_graceful_shutdown_releases_all_captures` - Release all resources
- ✓ `test_shutdown_cancels_health_update_tasks` - Cancel background tasks
- ✓ `test_shutdown_with_failing_stream` - Handle failing streams

#### Context Manager Tests (2)

- ✓ `test_async_context_manager_full_lifecycle` - Full lifecycle
- ✓ `test_async_context_manager_exception_cleanup` - Cleanup on exception

#### Edge Cases (2)

- ✓ `test_stream_tasks_survive_event_loop_stress` - Event loop under load
- ✓ `test_rapid_add_remove_cycles` - Rapid cycling

## Implementation Requirements

### Core Components

1. **StreamManager class** - Main service class
2. **Redis integration** - Health tracking with hash keys
3. **OpenCV VideoCapture** - RTSP stream capture with TCP transport
4. **Exponential backoff** - Reconnection logic (5s, 10s, 20s, 40s, max 60s)
5. **Async context manager** - `__aenter__` and `__aexit__` support

### Key Methods

- `__init__(redis_client, **kwargs)` - Initialize with dependencies
- `start()` - Start service and capture event loop
- `stop()` - Stop service and clean up resources
- `add_stream(camera_id, rtsp_url)` - Register new stream
- `remove_stream(camera_id)` - Remove and clean up stream
- `get_stream_health(camera_id)` - Retrieve health data from Redis
- `_calculate_backoff(retry_count)` - Calculate exponential backoff delay

### Redis Schema

**Health Keys:** `hsi:stream:health:{camera_id}`

**Health Fields:**

- `status` - "connected" | "reconnecting" | "failed"
- `connection_time` - ISO timestamp
- `fps` - Frames per second
- `retry_count` - Number of reconnection attempts
- `last_error` - Last error message (if any)

### Design Pattern

Follow async service pattern from `file_watcher.py`:

- Capture event loop in `start()`
- Use asyncio tasks for background operations
- Graceful cleanup in `stop()`
- Idempotent start/stop methods

## Next Steps (TDD GREEN Phase)

1. **Create StreamManager stub** - Basic class structure
2. **Implement initialization** - Pass 3 init tests
3. **Implement start/stop** - Pass 7 lifecycle tests
4. **Implement add/remove streams** - Pass 7 stream management tests
5. **Implement health tracking** - Pass 3 health tests + 5 Redis integration tests
6. **Implement reconnection** - Pass 5 reconnection tests
7. **Implement error handling** - Pass 3 error tests
8. **Verify integration tests** - Pass all 17 integration tests

## Test Execution

```bash
# Run unit tests
uv run pytest backend/tests/unit/services/test_stream_manager.py -v

# Run integration tests
uv run pytest backend/tests/integration/test_stream_manager.py -v

# Run all stream manager tests
uv run pytest -k stream_manager -v

# Current status: All 50 tests SKIPPED (RED phase)
```

## Acceptance Criteria Checklist

- [ ] StreamManager accepts redis_client and dependencies
- [ ] start() initializes event loop and sets running=True
- [ ] stop() cleans up resources and sets running=False
- [ ] add_stream(camera_id, rtsp_url) creates VideoCapture with TCP
- [ ] remove_stream(camera_id) releases capture and removes Redis key
- [ ] get_stream_health(camera_id) returns health dict from Redis
- [ ] Exponential backoff: 5s, 10s, 20s, 40s, max 60s
- [ ] Stream failures trigger automatic reconnection
- [ ] Health persisted in Redis: hsi:stream:health:{camera_id}
- [ ] Multiple concurrent streams work independently
- [ ] Graceful shutdown with active streams
- [ ] Async context manager support
