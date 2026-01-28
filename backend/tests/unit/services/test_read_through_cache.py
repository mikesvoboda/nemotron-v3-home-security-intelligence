"""Unit tests for read-through cache service (NEM-3765)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.services.read_through_cache import (
    ReadThroughCache,
    ReadThroughResult,
    get_camera_read_through_cache,
    reset_read_through_caches,
)


@pytest.fixture
def mock_settings():
    """Mock settings for read-through cache tests."""
    settings = MagicMock()
    settings.cache_default_ttl = 300
    settings.cache_short_ttl = 60
    settings.redis_key_prefix = "hsi"
    return settings


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
async def read_through_cache(mock_settings, mock_redis):
    """Create a read-through cache for testing."""
    await reset_read_through_caches()

    async def mock_loader(key: str) -> dict | None:
        if key == "existing":
            return {"id": "existing", "name": "Existing Item"}
        return None

    with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
        cache = ReadThroughCache(
            cache_prefix="test",
            loader=mock_loader,
            ttl=300,
        )
        cache._redis = mock_redis
        yield cache

    await reset_read_through_caches()


class TestReadThroughResult:
    """Tests for ReadThroughResult dataclass."""

    def test_result_from_cache(self):
        """Test result when value is from cache."""
        result = ReadThroughResult(
            value={"id": "1"},
            from_cache=True,
            cache_key="test:1",
            ttl_remaining=250,
        )
        assert result.from_cache is True
        assert result.value == {"id": "1"}

    def test_result_from_loader(self):
        """Test result when value is from loader."""
        result = ReadThroughResult(
            value={"id": "2"},
            from_cache=False,
            cache_key="test:2",
        )
        assert result.from_cache is False
        assert result.ttl_remaining is None


class TestReadThroughCache:
    """Tests for ReadThroughCache class."""

    def test_make_cache_key(self, mock_settings):
        """Test cache key generation."""
        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="cameras",
                loader=AsyncMock(),
            )
            key = cache._make_cache_key("cam1")

        assert key == "hsi:cache:cameras:cam1"

    def test_make_lock_key(self, mock_settings):
        """Test lock key generation for stampede protection."""
        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="cameras",
                loader=AsyncMock(),
            )
            key = cache._make_lock_key("cam1")

        assert key == "hsi:cache:cameras:cam1:loading"

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, read_through_cache, mock_redis):
        """Test cache hit returns cached value."""
        cached_data = {"id": "1", "name": "Cached Item"}
        mock_redis.get.return_value = cached_data

        result = await read_through_cache.get("1")

        assert result.from_cache is True
        assert result.value == cached_data
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cache_miss_loads_data(self, read_through_cache, mock_redis):
        """Test cache miss triggers loader and caches result."""
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        result = await read_through_cache.get("existing")

        assert result.from_cache is False
        assert result.value == {"id": "existing", "name": "Existing Item"}
        # Should have called set to cache the value (plus lock key for stampede protection)
        assert mock_redis.set.call_count == 2  # Lock key + cache key

    @pytest.mark.asyncio
    async def test_get_cache_miss_not_found(self, read_through_cache, mock_redis):
        """Test cache miss with loader returning None."""
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        result = await read_through_cache.get("nonexistent")

        assert result.from_cache is False
        assert result.value is None
        # Should only set the lock key (stampede protection), not cache None values
        assert mock_redis.set.call_count == 1  # Only lock key, no cache for None

    @pytest.mark.asyncio
    async def test_get_with_stampede_protection(self, mock_settings, mock_redis):
        """Test stampede protection with lock."""
        load_count = 0

        async def counting_loader(key: str) -> dict:
            nonlocal load_count
            load_count += 1
            await asyncio.sleep(0.05)  # Simulate slow load
            return {"id": key}

        # First request gets lock (returns True), second request doesn't (returns False)
        mock_redis.set.side_effect = [True, True]  # nx=True returns True on first call

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=counting_loader,
                ttl=300,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            result = await cache.get("key1")

        assert result.value == {"id": "key1"}

    @pytest.mark.asyncio
    async def test_get_without_stampede_protection(self, mock_settings, mock_redis):
        """Test loading without stampede protection."""

        async def simple_loader(key: str) -> dict:
            return {"id": key}

        mock_redis.get.return_value = None

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=simple_loader,
                ttl=300,
                stampede_protection=False,  # Disable stampede protection
            )
            cache._redis = mock_redis

            result = await cache.get("key1")

        assert result.value == {"id": "key1"}
        assert result.from_cache is False

    @pytest.mark.asyncio
    async def test_get_redis_error_fallback(self, mock_settings, mock_redis):
        """Test fallback to loader on Redis error."""

        async def fallback_loader(key: str) -> dict:
            return {"id": key, "source": "fallback"}

        mock_redis.get.side_effect = RedisConnectionError("Connection refused")

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=fallback_loader,
                ttl=300,
            )
            cache._redis = mock_redis

            result = await cache.get("key1")

        assert result.value == {"id": "key1", "source": "fallback"}
        assert result.from_cache is False

    @pytest.mark.asyncio
    async def test_invalidate(self, read_through_cache, mock_redis):
        """Test cache invalidation."""
        mock_redis.delete.return_value = 1

        deleted = await read_through_cache.invalidate("key1")

        assert deleted is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent(self, read_through_cache, mock_redis):
        """Test invalidating nonexistent key."""
        mock_redis.delete.return_value = 0

        deleted = await read_through_cache.invalidate("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_refresh(self, read_through_cache, mock_redis):
        """Test cache refresh."""
        mock_redis.delete.return_value = 1
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True

        result = await read_through_cache.refresh("existing")

        # Should delete first (invalidate), then load
        # Delete is called twice: once for invalidate, once for lock release
        assert mock_redis.delete.call_count == 2
        assert result.from_cache is False


class TestPreConfiguredCaches:
    """Tests for pre-configured read-through caches."""

    @pytest.mark.asyncio
    async def test_get_camera_cache_singleton(self, mock_settings):
        """Test camera cache is a singleton."""
        await reset_read_through_caches()

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache1 = await get_camera_read_through_cache()
            cache2 = await get_camera_read_through_cache()

        assert cache1 is cache2
        await reset_read_through_caches()

    @pytest.mark.asyncio
    async def test_camera_cache_prefix(self, mock_settings):
        """Test camera cache uses correct prefix."""
        await reset_read_through_caches()

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = await get_camera_read_through_cache()

        assert cache._prefix == "cameras"
        await reset_read_through_caches()


class TestStampedeProtection:
    """Tests for cache stampede protection."""

    @pytest.mark.asyncio
    async def test_wait_for_cache_success(self, mock_settings, mock_redis):
        """Test waiting for cache to be populated by another request."""
        # Initially None, then populated
        get_results = [None, None, {"id": "1", "name": "Item"}]
        mock_redis.get.side_effect = get_results

        async def slow_loader(key: str) -> dict:
            return {"id": key}

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=slow_loader,
                ttl=300,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            # Call _wait_for_cache directly to test the waiting logic
            result = await cache._wait_for_cache(
                "key1",
                "hsi:cache:test:key1",
                300,
                mock_redis,
                max_wait=0.5,
                poll_interval=0.05,
            )

        assert result.value == {"id": "1", "name": "Item"}
        assert result.from_cache is True

    @pytest.mark.asyncio
    async def test_wait_for_cache_timeout(self, mock_settings, mock_redis):
        """Test timeout while waiting for cache."""
        mock_redis.get.return_value = None  # Never populated
        mock_redis.set.return_value = True

        async def quick_loader(key: str) -> dict:
            return {"id": key}

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=quick_loader,
                ttl=300,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            # Short wait timeout to trigger fallback to direct load
            result = await cache._wait_for_cache(
                "key1",
                "hsi:cache:test:key1",
                300,
                mock_redis,
                max_wait=0.1,
                poll_interval=0.05,
            )

        # Should have loaded directly after timeout
        assert result.value == {"id": "key1"}
        assert result.from_cache is False


# ===========================================================================
# Test: Additional Coverage - Error Handling and Edge Cases
# ===========================================================================


class TestReadThroughCacheErrorHandling:
    """Additional tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_get_redis_initialization(self, mock_settings):
        """Test that _get_redis initializes Redis client."""
        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            with patch("backend.services.read_through_cache.init_redis") as mock_init:
                mock_redis_client = AsyncMock()
                mock_init.return_value = mock_redis_client

                cache = ReadThroughCache(
                    cache_prefix="test",
                    loader=AsyncMock(),
                )

                redis = await cache._get_redis()

                assert redis is mock_redis_client
                mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_uses_custom_ttl(self, mock_settings, mock_redis):
        """Test get uses custom TTL when provided."""

        async def simple_loader(key: str) -> dict:
            return {"id": key}

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=simple_loader,
                ttl=600,  # Custom TTL
                stampede_protection=False,
            )
            cache._redis = mock_redis

            await cache.get("key1")

        # Verify set was called with custom TTL
        set_call = mock_redis.set.call_args
        assert set_call[1]["expire"] == 600

    @pytest.mark.asyncio
    async def test_get_uses_default_ttl_when_none(self, mock_settings, mock_redis):
        """Test get uses default TTL from settings when ttl=None."""

        async def simple_loader(key: str) -> dict:
            return {"id": key}

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=simple_loader,
                ttl=None,  # Use default from settings
                stampede_protection=False,
            )
            cache._redis = mock_redis

            await cache.get("key1")

        # Verify set was called with default TTL from settings
        set_call = mock_redis.set.call_args
        assert set_call[1]["expire"] == 300  # From mock_settings

    @pytest.mark.asyncio
    async def test_load_with_lock_double_check_finds_cached(self, mock_settings, mock_redis):
        """Test _load_with_lock loads from source when cache is empty after lock."""

        async def slow_loader(key: str) -> dict:
            return {"id": key, "from": "loader"}

        # Lock acquired, cache still empty after double-check, loader is called
        mock_redis.set.return_value = True  # Lock acquired
        mock_redis.get.return_value = None  # Cache still empty after double-check
        mock_redis.delete.return_value = 1

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=slow_loader,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            result = await cache._load_with_lock(
                "key1",
                "hsi:cache:test:key1",
                300,
                mock_redis,
            )

        # Should load from loader and cache the result
        assert result.value == {"id": "key1", "from": "loader"}
        assert result.from_cache is False
        # Value should be cached (set called twice: once for lock, once for cache)
        assert mock_redis.set.call_count == 2
        # Lock should be released
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_load_with_lock_loads_and_caches_none(self, mock_settings, mock_redis):
        """Test _load_with_lock when loader returns None."""

        async def none_loader(key: str) -> None:
            return None

        mock_redis.set.return_value = True  # Lock acquired
        mock_redis.get.return_value = None
        mock_redis.delete.return_value = 1

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=none_loader,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            result = await cache._load_with_lock(
                "nonexistent",
                "hsi:cache:test:nonexistent",
                300,
                mock_redis,
            )

        # Should return None without caching
        assert result.value is None
        assert result.from_cache is False
        # set should only be called for lock, not for None value
        assert mock_redis.set.call_count == 1

    @pytest.mark.asyncio
    async def test_load_with_lock_releases_lock_on_exception(self, mock_settings, mock_redis):
        """Test _load_with_lock releases lock even when loader raises exception."""

        async def failing_loader(key: str) -> dict:
            raise ValueError("Loader failed")

        mock_redis.set.return_value = True  # Lock acquired
        mock_redis.get.return_value = None
        mock_redis.delete.return_value = 1

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=failing_loader,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            with pytest.raises(ValueError, match="Loader failed"):
                await cache._load_with_lock(
                    "key1",
                    "hsi:cache:test:key1",
                    300,
                    mock_redis,
                )

        # Lock should still be released
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_invalidate_handles_redis_error(self, mock_settings, mock_redis):
        """Test invalidate handles Redis errors gracefully."""
        from redis.exceptions import TimeoutError as RedisTimeoutError

        async def simple_loader(key: str) -> dict:
            return {"id": key}

        mock_redis.delete.side_effect = RedisTimeoutError("Timeout")

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=simple_loader,
            )
            cache._redis = mock_redis

            result = await cache.invalidate("key1")

        # Should return False on error
        assert result is False

    @pytest.mark.asyncio
    async def test_load_with_lock_waits_when_lock_not_acquired(self, mock_settings, mock_redis):
        """Test _load_with_lock waits when another request holds the lock."""

        async def simple_loader(key: str) -> dict:
            return {"id": key}

        # Lock not acquired (another request holds it)
        mock_redis.set.return_value = False

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = ReadThroughCache(
                cache_prefix="test",
                loader=simple_loader,
                stampede_protection=True,
            )
            cache._redis = mock_redis

            # Mock _wait_for_cache to return immediately
            with patch.object(cache, "_wait_for_cache") as mock_wait:
                mock_wait.return_value = ReadThroughResult(
                    value={"id": "key1"},
                    from_cache=True,
                    cache_key="hsi:cache:test:key1",
                )

                result = await cache._load_with_lock(
                    "key1",
                    "hsi:cache:test:key1",
                    300,
                    mock_redis,
                )

        # Should call _wait_for_cache
        mock_wait.assert_called_once()
        assert result.value == {"id": "key1"}


class TestPreConfiguredCachesExtended:
    """Extended tests for pre-configured caches."""

    @pytest.mark.asyncio
    async def test_get_event_cache_singleton(self, mock_settings):
        """Test event cache is a singleton."""
        from backend.services.read_through_cache import get_event_read_through_cache

        await reset_read_through_caches()

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache1 = await get_event_read_through_cache()
            cache2 = await get_event_read_through_cache()

        assert cache1 is cache2
        await reset_read_through_caches()

    @pytest.mark.asyncio
    async def test_get_alert_cache_singleton(self, mock_settings):
        """Test alert cache is a singleton."""
        from backend.services.read_through_cache import get_alert_read_through_cache

        await reset_read_through_caches()

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache1 = await get_alert_read_through_cache()
            cache2 = await get_alert_read_through_cache()

        assert cache1 is cache2
        await reset_read_through_caches()

    @pytest.mark.asyncio
    async def test_event_cache_uses_short_ttl(self, mock_settings):
        """Test event cache uses short TTL."""
        from backend.services.read_through_cache import get_event_read_through_cache

        await reset_read_through_caches()

        with patch("backend.services.read_through_cache.get_settings", return_value=mock_settings):
            cache = await get_event_read_through_cache()

        assert cache._ttl == 60  # Short TTL from settings
        await reset_read_through_caches()

    @pytest.mark.asyncio
    async def test_camera_loader_returns_none_for_nonexistent(self, mock_settings):
        """Test _load_camera returns None for nonexistent camera."""
        from backend.services.read_through_cache import _load_camera

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_camera("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_camera_loader_returns_dict(self, mock_settings):
        """Test _load_camera returns camera dict."""
        from datetime import datetime

        from backend.services.read_through_cache import _load_camera

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_camera = MagicMock()
            mock_camera.id = "cam1"
            mock_camera.name = "Front Door"
            mock_camera.folder_path = "/export/foscam/front_door"
            mock_camera.status = "online"
            mock_camera.created_at = datetime(2024, 1, 1)

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_camera
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_camera("cam1")

        assert result is not None
        assert result["id"] == "cam1"
        assert result["name"] == "Front Door"

    @pytest.mark.asyncio
    async def test_event_loader_returns_none_for_invalid_uuid(self, mock_settings):
        """Test _load_event returns None for invalid UUID."""
        from backend.services.read_through_cache import _load_event

        # Mock get_session to avoid database initialization
        with patch("backend.core.database.get_session"):
            result = await _load_event("not-a-uuid")

        assert result is None

    @pytest.mark.asyncio
    async def test_event_loader_returns_dict(self, mock_settings):
        """Test _load_event returns event dict."""
        from datetime import datetime
        from uuid import uuid4

        from backend.services.read_through_cache import _load_event

        event_id = str(uuid4())

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_event = MagicMock()
            mock_event.id = uuid4()
            mock_event.camera_id = "cam1"
            mock_event.risk_score = 85
            mock_event.risk_level = "high"
            mock_event.summary = "Test event"
            mock_event.reviewed = False
            mock_event.started_at = datetime(2024, 1, 1)

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_event
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_event(event_id)

        assert result is not None
        assert result["camera_id"] == "cam1"
        assert result["risk_score"] == 85

    @pytest.mark.asyncio
    async def test_alert_loader_returns_none_for_invalid_uuid(self, mock_settings):
        """Test _load_alert_rule returns None for invalid UUID."""
        from backend.services.read_through_cache import _load_alert_rule

        # Mock get_session to avoid database initialization
        with patch("backend.core.database.get_session"):
            result = await _load_alert_rule("not-a-uuid")

        assert result is None

    @pytest.mark.asyncio
    async def test_alert_loader_returns_dict(self, mock_settings):
        """Test _load_alert_rule returns alert dict."""
        from datetime import datetime
        from uuid import uuid4

        from backend.services.read_through_cache import _load_alert_rule

        alert_id = str(uuid4())

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_severity = MagicMock()
            mock_severity.value = "high"

            mock_alert = MagicMock()
            mock_alert.id = uuid4()
            mock_alert.name = "High Risk Alert"
            mock_alert.severity = mock_severity
            mock_alert.enabled = True
            mock_alert.created_at = datetime(2024, 1, 1)

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_alert
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_alert_rule(alert_id)

        assert result is not None
        assert result["name"] == "High Risk Alert"
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_camera_loader_handles_none_created_at(self, mock_settings):
        """Test _load_camera handles None created_at."""
        from backend.services.read_through_cache import _load_camera

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_camera = MagicMock()
            mock_camera.id = "cam1"
            mock_camera.name = "Front Door"
            mock_camera.folder_path = "/export/foscam/front_door"
            mock_camera.status = "online"
            mock_camera.created_at = None  # No created_at

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_camera
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_camera("cam1")

        assert result is not None
        assert result["created_at"] is None

    @pytest.mark.asyncio
    async def test_event_loader_handles_none_started_at(self, mock_settings):
        """Test _load_event handles None started_at."""
        from uuid import uuid4

        from backend.services.read_through_cache import _load_event

        event_id = str(uuid4())

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_event = MagicMock()
            mock_event.id = uuid4()
            mock_event.camera_id = "cam1"
            mock_event.risk_score = 85
            mock_event.risk_level = "high"
            mock_event.summary = "Test event"
            mock_event.reviewed = False
            mock_event.started_at = None  # No started_at

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_event
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_event(event_id)

        assert result is not None
        assert result["started_at"] is None

    @pytest.mark.asyncio
    async def test_alert_loader_handles_none_severity(self, mock_settings):
        """Test _load_alert_rule handles None severity."""
        from datetime import datetime
        from uuid import uuid4

        from backend.services.read_through_cache import _load_alert_rule

        alert_id = str(uuid4())

        with patch("backend.core.database.get_session") as mock_get_session:
            mock_alert = MagicMock()
            mock_alert.id = uuid4()
            mock_alert.name = "Test Alert"
            mock_alert.severity = None  # No severity
            mock_alert.enabled = True
            mock_alert.created_at = datetime(2024, 1, 1)

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_alert
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock()
            mock_get_session.return_value = mock_session

            result = await _load_alert_rule(alert_id)

        assert result is not None
        assert result["severity"] is None
