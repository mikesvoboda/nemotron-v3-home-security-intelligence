"""Unit tests for cache warming service (NEM-3762)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.cache_warming import (
    CacheWarmer,
    WarmingReport,
    WarmingResult,
    WarmingStrategy,
    get_cache_warmer,
    reset_cache_warmer,
    warm_caches_on_startup,
)


@pytest.fixture
def mock_settings():
    """Mock settings for cache warming tests."""
    settings = MagicMock()
    settings.cache_warming_enabled = True
    settings.cache_warming_strategy = "parallel"
    settings.cache_warming_timeout = 30.0
    settings.cache_default_ttl = 300
    settings.app_name = "Test App"
    settings.app_version = "1.0.0"
    settings.environment = "test"
    settings.redis_key_prefix = "hsi"
    return settings


@pytest.fixture
async def cache_warmer():
    """Create a fresh cache warmer for testing."""
    await reset_cache_warmer()
    warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL, timeout_seconds=5.0)
    yield warmer
    await reset_cache_warmer()


class TestWarmingStrategy:
    """Tests for WarmingStrategy enum."""

    def test_strategy_values(self):
        """Test warming strategy values."""
        assert WarmingStrategy.EAGER.value == "eager"
        assert WarmingStrategy.LAZY.value == "lazy"
        assert WarmingStrategy.PARALLEL.value == "parallel"
        assert WarmingStrategy.SEQUENTIAL.value == "sequential"

    def test_strategy_from_string(self):
        """Test creating strategy from string value."""
        assert WarmingStrategy("parallel") == WarmingStrategy.PARALLEL
        assert WarmingStrategy("sequential") == WarmingStrategy.SEQUENTIAL


class TestWarmingResult:
    """Tests for WarmingResult dataclass."""

    def test_warming_result_success(self):
        """Test successful warming result."""
        result = WarmingResult(
            cache_name="test_cache",
            success=True,
            duration_ms=50.5,
            items_cached=10,
        )
        assert result.success is True
        assert result.cache_name == "test_cache"
        assert result.duration_ms == 50.5
        assert result.items_cached == 10
        assert result.error is None

    def test_warming_result_failure(self):
        """Test failed warming result."""
        result = WarmingResult(
            cache_name="test_cache",
            success=False,
            duration_ms=100.0,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"
        assert result.items_cached == 0


class TestWarmingReport:
    """Tests for WarmingReport dataclass."""

    def test_warming_report_counts(self):
        """Test warming report success/failure counts."""
        results = [
            WarmingResult("cache1", True, 50.0, 5),
            WarmingResult("cache2", True, 30.0, 10),
            WarmingResult("cache3", False, 100.0, 0, "Error"),
        ]
        report = WarmingReport(
            strategy=WarmingStrategy.PARALLEL,
            total_duration_ms=150.0,
            results=results,
        )

        assert report.successful_count == 2
        assert report.failed_count == 1
        assert report.total_items_cached == 15

    def test_warming_report_empty(self):
        """Test warming report with no results."""
        report = WarmingReport(
            strategy=WarmingStrategy.PARALLEL,
            total_duration_ms=0,
            results=[],
        )

        assert report.successful_count == 0
        assert report.failed_count == 0
        assert report.total_items_cached == 0


class TestCacheWarmer:
    """Tests for CacheWarmer class."""

    @pytest.mark.asyncio
    async def test_init_default_strategy(self):
        """Test default warming strategy."""
        warmer = CacheWarmer()
        assert warmer._strategy == WarmingStrategy.PARALLEL

    @pytest.mark.asyncio
    async def test_init_custom_strategy(self):
        """Test custom warming strategy."""
        warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL)
        assert warmer._strategy == WarmingStrategy.SEQUENTIAL

    @pytest.mark.asyncio
    async def test_register_warmer(self, cache_warmer):
        """Test registering a custom warmer."""

        async def mock_warmer():
            return 5

        cache_warmer.register_warmer("test", mock_warmer)
        assert len(cache_warmer._warmers) == 1
        assert cache_warmer._warmers[0][0] == "test"

    @pytest.mark.asyncio
    async def test_warm_all_disabled(self, mock_settings):
        """Test warming is skipped when disabled."""
        mock_settings.cache_warming_enabled = False

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer()
            report = await warmer.warm_all()

        assert report.total_duration_ms == 0
        assert len(report.results) == 0

    @pytest.mark.asyncio
    async def test_warm_parallel_success(self, mock_settings):
        """Test parallel warming with successful warmers."""
        call_order = []

        async def warmer1():
            call_order.append("warmer1")
            await asyncio.sleep(0.01)
            return 5

        async def warmer2():
            call_order.append("warmer2")
            await asyncio.sleep(0.01)
            return 10

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL)
            warmer.register_warmer("cache1", warmer1)
            warmer.register_warmer("cache2", warmer2)
            report = await warmer.warm_all()

        assert report.successful_count == 2
        assert report.total_items_cached == 15

    @pytest.mark.asyncio
    async def test_warm_sequential_success(self, mock_settings):
        """Test sequential warming."""
        call_order = []

        async def warmer1():
            call_order.append("warmer1_start")
            await asyncio.sleep(0.01)
            call_order.append("warmer1_end")
            return 5

        async def warmer2():
            call_order.append("warmer2_start")
            await asyncio.sleep(0.01)
            call_order.append("warmer2_end")
            return 10

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer(strategy=WarmingStrategy.SEQUENTIAL)
            warmer.register_warmer("cache1", warmer1)
            warmer.register_warmer("cache2", warmer2)
            report = await warmer.warm_all()

        assert report.successful_count == 2
        # Sequential order: first warmer completes before second starts
        assert call_order == ["warmer1_start", "warmer1_end", "warmer2_start", "warmer2_end"]

    @pytest.mark.asyncio
    async def test_warm_handles_failure(self, mock_settings):
        """Test warming handles individual warmer failures gracefully."""

        async def success_warmer():
            return 5

        async def failing_warmer():
            raise ValueError("Test error")

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL)
            warmer.register_warmer("success", success_warmer)
            warmer.register_warmer("failure", failing_warmer)
            report = await warmer.warm_all()

        assert report.successful_count == 1
        assert report.failed_count == 1
        # Find the failed result
        failed_result = next(r for r in report.results if not r.success)
        assert "Test error" in failed_result.error

    @pytest.mark.asyncio
    async def test_warm_timeout(self, mock_settings):
        """Test warming handles timeout."""

        async def slow_warmer():
            await asyncio.sleep(10)  # Will timeout
            return 5

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer(strategy=WarmingStrategy.PARALLEL, timeout_seconds=0.1)
            warmer.register_warmer("slow", slow_warmer)
            report = await warmer.warm_all()

        assert report.failed_count == 1
        failed_result = report.results[0]
        assert not failed_result.success
        assert "Timeout" in failed_result.error


class TestGetCacheWarmer:
    """Tests for get_cache_warmer singleton function."""

    @pytest.mark.asyncio
    async def test_singleton_creation(self, mock_settings):
        """Test cache warmer singleton is created."""
        await reset_cache_warmer()

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer1 = await get_cache_warmer()
            warmer2 = await get_cache_warmer()

        assert warmer1 is warmer2
        await reset_cache_warmer()

    @pytest.mark.asyncio
    async def test_singleton_reset(self, mock_settings):
        """Test cache warmer singleton can be reset."""
        await reset_cache_warmer()

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer1 = await get_cache_warmer()
            await reset_cache_warmer()
            warmer2 = await get_cache_warmer()

        assert warmer1 is not warmer2
        await reset_cache_warmer()


class TestWarmCachesOnStartup:
    """Tests for warm_caches_on_startup convenience function."""

    @pytest.mark.asyncio
    async def test_warm_caches_on_startup(self, mock_settings):
        """Test warm_caches_on_startup function."""
        await reset_cache_warmer()
        mock_settings.cache_warming_enabled = False  # Skip actual warming

        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            report = await warm_caches_on_startup()

        assert isinstance(report, WarmingReport)
        await reset_cache_warmer()


class TestDefaultWarmers:
    """Tests for default cache warmers."""

    @pytest.mark.asyncio
    async def test_register_default_warmers(self, mock_settings):
        """Test default warmers are registered."""
        with patch("backend.services.cache_warming.get_settings", return_value=mock_settings):
            warmer = CacheWarmer()
            warmer._register_default_warmers()

        # Should have cameras, system_status, and alert_rules warmers
        warmer_names = [name for name, _ in warmer._warmers]
        assert "cameras" in warmer_names
        assert "system_status" in warmer_names
        assert "alert_rules" in warmer_names

    @pytest.mark.asyncio
    async def test_warm_cameras_returns_count(self, mock_settings):
        """Test camera warmer returns camera count."""
        mock_camera = MagicMock()
        mock_camera.id = "cam1"
        mock_camera.name = "Camera 1"
        mock_camera.folder_path = "/path/to/cam1"
        mock_camera.status = "online"
        mock_camera.created_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_camera]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        mock_cache = AsyncMock()

        # Create an async context manager mock
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session
        mock_session_cm.__aexit__.return_value = None

        with (
            patch("backend.services.cache_warming.get_settings", return_value=mock_settings),
            patch("backend.core.database.get_session", return_value=mock_session_cm),
            patch(
                "backend.services.cache_service.get_cache_service",
                return_value=mock_cache,
            ),
        ):
            warmer = CacheWarmer()
            count = await warmer._warm_cameras()

        assert count == 1
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_system_status(self, mock_settings):
        """Test system status warmer."""
        mock_cache = AsyncMock()

        with (
            patch("backend.services.cache_warming.get_settings", return_value=mock_settings),
            patch(
                "backend.services.cache_service.get_cache_service",
                return_value=mock_cache,
            ),
        ):
            warmer = CacheWarmer()
            count = await warmer._warm_system_status()

        assert count == 1
        mock_cache.set.assert_called_once()
        # Verify the cached data
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "system:status:basic"
        data = call_args[0][1]
        assert data["app_name"] == "Test App"
        assert data["app_version"] == "1.0.0"
