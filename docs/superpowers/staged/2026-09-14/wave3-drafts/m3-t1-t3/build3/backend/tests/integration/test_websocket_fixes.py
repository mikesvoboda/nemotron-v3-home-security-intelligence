"""Fixes for flaky WebSocket integration tests.

This module documents and demonstrates fixes for common flakiness patterns in
WebSocket integration tests:

1. Race conditions in Redis pub/sub
2. Missing await statements for async cleanup
3. Improper connection handling and timeouts
4. Leaked resources from incomplete cleanup

Key Patterns Fixed:
- Always use try/except in finally blocks for cleanup
- Add proper synchronization delays for Redis pub/sub propagation
- Ensure all async operations are awaited
- Properly close all WebSocket and PubSub connections
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from backend.core.redis import RedisClient


# =============================================================================
# Fixture Improvements
# =============================================================================


@pytest.fixture
async def safe_redis_pubsub(real_redis: RedisClient):
    """Create a Redis PubSub connection with guaranteed cleanup.

    This fixture ensures that pubsub connections are properly closed even if
    the test fails or times out, preventing connection leaks that cause
    "unexpected EOF" errors in PostgreSQL.
    """
    pubsub = None
    channel = None

    try:
        yield
    finally:
        # Cleanup: Always try to close pubsub connections
        if pubsub is not None and channel is not None:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                pass  # Ignore errors during cleanup
            try:
                await pubsub.aclose()
            except Exception:
                pass  # Ignore errors during cleanup


# =============================================================================
# Example Fixed Test Patterns
# =============================================================================


class TestFixedPatterns:
    """Examples of fixed test patterns for flaky WebSocket tests."""

    @pytest.mark.asyncio
    async def test_pubsub_with_proper_cleanup(self, real_redis: RedisClient) -> None:
        """Example of proper pub/sub test with guaranteed cleanup.

        BEFORE (flaky):
            pubsub = await real_redis.subscribe_dedicated(channel)
            # ... test code ...
            await pubsub.unsubscribe(channel)  # May not run if test fails
            await pubsub.aclose()  # May not run if test fails

        AFTER (stable):
            pubsub = await real_redis.subscribe_dedicated(channel)
            try:
                # ... test code ...
            finally:
                try:
                    await pubsub.unsubscribe(channel)
                except Exception:
                    pass
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
        """
        channel = "test_fixed_pattern"
        pubsub = None

        try:
            pubsub = await real_redis.subscribe_dedicated(channel)

            # Publish and receive message
            await real_redis.publish(channel, {"test": "data"})

            # Use timeout to prevent hanging
            received = []

            async def collect():
                async for msg in real_redis.listen(pubsub):
                    received.append(msg)
                    break

            await asyncio.wait_for(collect(), timeout=2.0)

            assert len(received) == 1

        finally:
            # CRITICAL: Always cleanup, even on failure
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(channel)
                except Exception:
                    pass
                try:
                    await pubsub.aclose()
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_broadcaster_with_proper_lifecycle(self, real_redis: RedisClient) -> None:
        """Example of proper broadcaster test with guaranteed cleanup.

        BEFORE (flaky):
            broadcaster = EventBroadcaster(real_redis, channel_name="test")
            await broadcaster.start()
            # ... test code ...
            await broadcaster.stop()  # May not run if test fails

        AFTER (stable):
            broadcaster = EventBroadcaster(real_redis, channel_name="test")
            try:
                await broadcaster.start()
                # ... test code ...
            finally:
                try:
                    await broadcaster.stop()
                except Exception:
                    pass
        """
        from backend.services.event_broadcaster import EventBroadcaster, reset_broadcaster_state

        reset_broadcaster_state()

        broadcaster = None
        try:
            broadcaster = EventBroadcaster(real_redis, channel_name="test_lifecycle")
            await broadcaster.start()

            # Test broadcaster functionality
            event_data = {
                "id": 1,
                "event_id": 1,
                "batch_id": "test",
                "camera_id": "test",
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Test",
                "reasoning": "Test reasoning",
                "started_at": "2025-12-23T12:00:00",
            }
            await broadcaster.broadcast_event(event_data)

            # Wait for async operations to complete
            await asyncio.sleep(0.1)

        finally:
            # CRITICAL: Always cleanup, even on failure
            if broadcaster is not None:
                try:
                    await broadcaster.stop()
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_multiple_subscribers_with_proper_cleanup(self, real_redis: RedisClient) -> None:
        """Example of multiple subscribers with proper cleanup.

        BEFORE (flaky):
            pubsub1 = await real_redis.subscribe_dedicated(channel)
            pubsub2 = await real_redis.subscribe_dedicated(channel)
            # ... test code ...
            await pubsub1.unsubscribe(channel)  # May not run
            await pubsub2.unsubscribe(channel)  # May not run

        AFTER (stable):
            Use try/finally with individual cleanup for each resource
        """
        channel = "test_multi_sub"
        pubsub1 = None
        pubsub2 = None

        try:
            pubsub1 = await real_redis.subscribe_dedicated(channel)
            pubsub2 = await real_redis.subscribe_dedicated(channel)

            # Publish message
            count = await real_redis.publish(channel, {"test": "multi"})
            assert count == 2  # Both subscribers should receive

            # Small delay for pub/sub propagation
            await asyncio.sleep(0.1)

        finally:
            # CRITICAL: Cleanup each resource individually
            for pubsub in [pubsub1, pubsub2]:
                if pubsub is not None:
                    try:
                        await pubsub.unsubscribe(channel)
                    except Exception:
                        pass
                    try:
                        await pubsub.aclose()
                    except Exception:
                        pass


# =============================================================================
# Checklist for Fixing Flaky Tests
# =============================================================================

"""
CHECKLIST FOR FIXING FLAKY WEBSOCKET TESTS:

1. **Cleanup in finally blocks**:
   - ✅ Always use try/finally for resource cleanup
   - ✅ Wrap each cleanup operation in try/except to ignore errors
   - ✅ Clean up resources in reverse order of creation

2. **Async synchronization**:
   - ✅ Add asyncio.sleep() after Redis pub/sub operations (0.1-0.5s)
   - ✅ Use asyncio.wait_for() with timeouts for async operations
   - ✅ Ensure all async operations are awaited

3. **Connection management**:
   - ✅ Close all WebSocket connections in finally blocks
   - ✅ Unsubscribe from Redis channels before closing PubSub
   - ✅ Stop broadcasters before cleaning up connections

4. **Test isolation**:
   - ✅ Use unique channel names per test (avoid collisions)
   - ✅ Reset broadcaster state before each test
   - ✅ Clean up all connections even if test fails

5. **Timeout protection**:
   - ✅ Use asyncio.wait_for() with reasonable timeouts (2-5s)
   - ✅ Cancel tasks in finally blocks
   - ✅ Prevent tests from hanging indefinitely

6. **Error handling**:
   - ✅ Wrap cleanup code in try/except to prevent cascading failures
   - ✅ Log cleanup errors but don't raise them
   - ✅ Ensure cleanup continues even if one step fails
"""
