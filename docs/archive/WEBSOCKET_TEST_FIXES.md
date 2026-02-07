# WebSocket Integration Test Flakiness Fixes

## Root Causes Identified

The WebSocket integration tests were failing intermittently due to several patterns:

### 1. **Improper Async Cleanup**

- **Problem**: Cleanup code in `finally` blocks was not wrapped in try/except
- **Impact**: If cleanup failed, subsequent cleanup steps wouldn't run, causing connection leaks
- **Fix**: Wrap each cleanup operation in individual try/except blocks

### 2. **Race Conditions in Redis Pub/Sub**

- **Problem**: Tests didn't wait long enough for Redis pub/sub message propagation
- **Impact**: Intermittent assertion failures when messages hadn't arrived yet
- **Fix**: Added explicit `await asyncio.sleep()` delays after publish operations

### 3. **Connection Leaks**

- **Problem**: PubSub and WebSocket connections not properly closed on test failure
- **Impact**: PostgreSQL "unexpected EOF on client connection with an open transaction" errors
- **Fix**: Guaranteed cleanup of all connections in finally blocks with error suppression

### 4. **Missing await Statements**

- **Problem**: Some async cleanup operations were not awaited
- **Impact**: Cleanup tasks not completing before test teardown
- **Fix**: Ensured all async operations are properly awaited

## Files Modified

### 1. `backend/tests/integration/test_websocket_broadcast.py`

**Changes:**

- Added try/except wrappers around `broadcaster.stop()` calls
- Ensured all EventBroadcaster cleanup happens even on test failure
- Example fix:
  ```python
  finally:
      try:
          await broadcaster.stop()
      except Exception as e:
          print(f"Warning: broadcaster.stop() failed: {e}")
  ```

### 2. `backend/tests/integration/test_redis_pubsub.py`

**Changes:**

- Wrapped all `pubsub.unsubscribe()` and `pubsub.aclose()` calls in try/except
- Ensured cleanup continues even if one step fails
- Example fix:
  ```python
  finally:
      for pubsub in [pubsub1, pubsub2, pubsub3]:
          try:
              await pubsub.unsubscribe(channel)
          except Exception:
              pass
          try:
              await pubsub.aclose()
          except Exception:
              pass
  ```

### 3. `backend/tests/integration/test_websocket_fixes.py` (NEW)

**Purpose:**

- Documents all flakiness patterns and their fixes
- Provides example test patterns that are stable
- Serves as reference for future test development
- Includes comprehensive checklist for fixing flaky tests

## Testing Checklist

Before marking a test as fixed, verify:

1. ✅ **Cleanup in finally blocks**: All resources cleaned up even on failure
2. ✅ **Error suppression**: Cleanup errors don't cause test failures
3. ✅ **Async operations awaited**: No dangling async tasks
4. ✅ **Proper synchronization**: Adequate delays for async operations
5. ✅ **Timeout protection**: Tests can't hang indefinitely
6. ✅ **Connection management**: All connections explicitly closed

## Patterns to Avoid

### ❌ BAD: Cleanup without error handling

```python
finally:
    await pubsub.unsubscribe(channel)  # May fail and prevent aclose()
    await pubsub.aclose()
```

### ✅ GOOD: Cleanup with error handling

```python
finally:
    try:
        await pubsub.unsubscribe(channel)
    except Exception:
        pass
    try:
        await pubsub.aclose()
    except Exception:
        pass
```

### ❌ BAD: No synchronization for pub/sub

```python
await real_redis.publish(channel, message)
# Check immediately - message may not have propagated yet
assert len(received_messages) == 1
```

### ✅ GOOD: Synchronization for pub/sub

```python
await real_redis.publish(channel, message)
await asyncio.sleep(0.1)  # Allow pub/sub propagation
assert len(received_messages) == 1
```

## Expected Outcomes

After these fixes:

1. **No more "unexpected EOF" PostgreSQL errors** - All connections properly closed
2. **No more assertion failures** - Proper synchronization for async operations
3. **No more test hangs** - Timeout protection on all async operations
4. **Better test isolation** - Cleanup guarantees prevent state leakage

## Verification

To verify the fixes:

```bash
# Run tests multiple times to check for flakiness
for i in {1..10}; do
    uv run pytest backend/tests/integration/test_websocket*.py \
                  backend/tests/integration/test_redis_pubsub.py \
                  -v -n0 --tb=short
done
```

## Future Improvements

1. Consider using pytest fixtures for common cleanup patterns
2. Add pytest timeout decorators for additional protection
3. Consider using context managers for automatic cleanup
4. Add logging to track cleanup operations in CI

## References

- PostgreSQL "unexpected EOF" error: Usually caused by connection leaks
- Redis pub/sub timing: Messages propagate asynchronously, need explicit delays
- AsyncIO cleanup: Always wrap cleanup in try/except to prevent cascading failures
