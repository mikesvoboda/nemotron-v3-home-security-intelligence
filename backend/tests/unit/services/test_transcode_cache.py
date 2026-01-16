"""Unit tests for TranscodeCache service.

This module tests the disk-based transcode cache with LRU eviction.
Uses temporary directories for filesystem operations to ensure tests are isolated.
"""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.config import TranscodeCacheSettings
from backend.services.transcode_cache import (
    CacheEntry,
    CacheStats,
    TranscodeCache,
    get_transcode_cache,
    reset_transcode_cache,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_dir():
    """Create a temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_config(temp_dir):
    """Create a TranscodeCacheSettings with temp directory."""
    return TranscodeCacheSettings(
        cache_dir=temp_dir,
        max_cache_size_gb=1.0,
        max_file_age_days=7,
        cleanup_threshold_percent=0.9,
        cleanup_target_percent=0.8,
        lock_timeout_seconds=30,
        enabled=True,
    )


@pytest.fixture
def disabled_config(temp_dir):
    """Create a disabled TranscodeCacheSettings."""
    return TranscodeCacheSettings(
        cache_dir=temp_dir,
        enabled=False,
    )


@pytest.fixture
def cache(mock_config):
    """Create a TranscodeCache instance with mock config."""
    return TranscodeCache(config=mock_config)


@pytest.fixture
def disabled_cache(disabled_config):
    """Create a disabled TranscodeCache instance."""
    return TranscodeCache(config=disabled_config)


@pytest.fixture
def source_video(temp_dir):
    """Create a mock source video file."""
    source_path = Path(temp_dir) / "source" / "test.mp4"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"fake video content")
    return source_path


@pytest.fixture
def transcoded_video(temp_dir):
    """Create a mock transcoded video file."""
    transcoded_path = Path(temp_dir) / "transcoded" / "output.mp4"
    transcoded_path.parent.mkdir(parents=True, exist_ok=True)
    transcoded_path.write_bytes(b"fake transcoded content" * 1000)
    return transcoded_path


# =============================================================================
# TranscodeCache Initialization Tests
# =============================================================================


def test_cache_initialization(mock_config):
    """Test TranscodeCache initializes with configuration."""
    cache = TranscodeCache(config=mock_config)

    assert cache.config == mock_config
    assert cache._metadata == {}
    assert cache._hits == 0
    assert cache._misses == 0
    assert cache._initialized is False


def test_cache_initialization_default_config():
    """Test TranscodeCache uses default config when none provided."""
    with patch("backend.core.config.get_settings") as mock_settings:
        mock_transcode_config = TranscodeCacheSettings()
        mock_settings.return_value.transcode_cache = mock_transcode_config
        cache = TranscodeCache()

        assert cache.config is not None
        assert cache.config.cache_dir == "data/transcode_cache"


@pytest.mark.asyncio
async def test_cache_initialize_creates_directory(mock_config, temp_dir):
    """Test initialize creates cache directory."""
    # Use a subdirectory that doesn't exist yet
    mock_config.cache_dir = str(Path(temp_dir) / "new_cache_dir")
    cache = TranscodeCache(config=mock_config)

    await cache.initialize()

    assert cache.cache_dir.exists()
    assert cache._initialized is True


@pytest.mark.asyncio
async def test_cache_initialize_idempotent(cache):
    """Test initialize is idempotent."""
    await cache.initialize()
    first_init_time = cache._initialized

    await cache.initialize()
    second_init_time = cache._initialized

    # Both should be True, and no errors
    assert first_init_time is True
    assert second_init_time is True


# =============================================================================
# Cache Key Generation Tests
# =============================================================================


def test_get_cache_key_generates_hash(cache, source_video):
    """Test _get_cache_key generates consistent hash."""
    key1 = cache._get_cache_key(source_video)
    key2 = cache._get_cache_key(source_video)

    assert key1 == key2
    assert len(key1) == 16  # 16 hex characters


def test_get_cache_key_different_mtime_different_key(cache, source_video):
    """Test different mtime generates different key."""
    key1 = cache._get_cache_key(source_video)

    # Modify the file to change mtime
    time.sleep(0.01)  # Ensure mtime changes
    source_video.write_bytes(b"modified content")

    key2 = cache._get_cache_key(source_video)

    assert key1 != key2


def test_get_cache_key_handles_missing_file(cache, temp_dir):
    """Test _get_cache_key handles missing file gracefully."""
    source_path = Path(temp_dir) / "nonexistent" / "test.mp4"

    # stat() will raise OSError for missing file
    key = cache._get_cache_key(source_path)

    # Should still generate a key (with mtime=0)
    assert len(key) == 16


# =============================================================================
# Cache Get Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_get_returns_none_on_miss(cache, source_video):
    """Test get returns None when key not in cache."""
    await cache.initialize()

    result = await cache.get(source_video)

    assert result is None
    assert cache._misses == 1


@pytest.mark.asyncio
async def test_cache_get_returns_cached_path_on_hit(cache, source_video):
    """Test get returns cached path when entry exists."""
    await cache.initialize()

    # Create a cached file
    cache_key = cache._get_cache_key(source_video)
    cached_path = cache.cache_dir / f"{cache_key}.mp4"
    cached_path.write_bytes(b"cached content")

    # Pre-populate cache metadata
    cache._metadata[cache_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(cached_path),
        cached_at=time.time(),
        last_accessed=time.time() - 100,
        size_bytes=cached_path.stat().st_size,
    )

    result = await cache.get(source_video)

    assert result == cached_path
    assert cache._hits == 1


@pytest.mark.asyncio
async def test_cache_get_invalidates_on_source_change(cache, source_video):
    """Test get invalidates cache when source file mtime changes."""
    await cache.initialize()

    # Create a cached file with old mtime
    cache_key = cache._get_cache_key(source_video)
    cached_path = cache.cache_dir / f"{cache_key}.mp4"
    cached_path.write_bytes(b"cached content")

    old_mtime = source_video.stat().st_mtime

    cache._metadata[cache_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=old_mtime - 100,  # Old mtime (different from current)
        cached_path=str(cached_path),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=cached_path.stat().st_size,
    )

    result = await cache.get(source_video)

    assert result is None
    assert cache._misses == 1


@pytest.mark.asyncio
async def test_cache_get_handles_missing_cached_file(cache, source_video):
    """Test get handles case where cached file is missing."""
    await cache.initialize()

    cache_key = cache._get_cache_key(source_video)
    nonexistent_path = cache.cache_dir / "nonexistent.mp4"

    cache._metadata[cache_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(nonexistent_path),
        cached_at=time.time(),
        last_accessed=time.time(),
        size_bytes=1000000,
    )

    result = await cache.get(source_video)

    assert result is None
    assert cache_key not in cache._metadata


@pytest.mark.asyncio
async def test_cache_get_disabled_returns_none(disabled_cache, source_video):
    """Test get returns None when cache is disabled."""
    result = await disabled_cache.get(source_video)

    assert result is None
    assert disabled_cache._misses == 1


# =============================================================================
# Cache Put Operation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_put_stores_file(cache, source_video, transcoded_video):
    """Test put stores transcoded file in cache."""
    await cache.initialize()

    result = await cache.put(source_video, transcoded_video)

    assert result.exists()
    assert result.parent == cache.cache_dir

    # Check metadata
    cache_key = cache._get_cache_key(source_video)
    assert cache_key in cache._metadata
    entry = cache._metadata[cache_key]
    assert entry.source_path == str(source_video)


@pytest.mark.asyncio
async def test_cache_put_with_duration(cache, source_video, transcoded_video):
    """Test put stores duration metadata."""
    await cache.initialize()

    await cache.put(source_video, transcoded_video, duration_seconds=120.5)

    cache_key = cache._get_cache_key(source_video)
    entry = cache._metadata[cache_key]
    assert entry.duration_seconds == 120.5


@pytest.mark.asyncio
async def test_cache_put_disabled_returns_original_path(
    disabled_cache, source_video, transcoded_video
):
    """Test put returns original path when cache is disabled."""
    result = await disabled_cache.put(source_video, transcoded_video)

    assert result == transcoded_video


# =============================================================================
# Cache Cleanup Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_cleanup_removes_lru_entries(cache, temp_dir):
    """Test cleanup removes least recently used entries."""
    await cache.initialize()

    # Create cached files
    now = time.time()
    total_size = 0

    for i, age_offset in enumerate([1000, 500, 100]):  # Oldest to newest
        cached_path = cache.cache_dir / f"entry{i}.mp4"
        content = b"x" * 400_000_000  # 400 MB each
        cached_path.write_bytes(content)
        total_size += len(content)

        cache._metadata[f"entry{i}"] = CacheEntry(
            source_path=f"/video/{i}.mp4",
            source_mtime=1234567890.0 + i,
            cached_path=str(cached_path),
            cached_at=now - age_offset,
            last_accessed=now - age_offset,
            size_bytes=len(content),
        )

    # Total: ~1.2 GB, target is 0.8 GB (80% of 1 GB max)
    removed = await cache.cleanup()

    # Should remove at least one entry
    assert removed >= 1


@pytest.mark.asyncio
async def test_maybe_cleanup_triggers_when_over_threshold(cache):
    """Test _maybe_cleanup triggers cleanup when over threshold."""
    await cache.initialize()

    # Mock get_stats to return size over threshold
    mock_stats = CacheStats(
        total_entries=5,
        total_size_bytes=950_000_000,  # 950 MB
        total_size_gb=0.95,  # Over 0.9 threshold
        oldest_entry_age_hours=24.0,
        hit_rate=0.5,
        hits=10,
        misses=10,
    )

    with patch.object(cache, "get_stats", new_callable=AsyncMock, return_value=mock_stats):
        with patch.object(cache, "cleanup", new_callable=AsyncMock) as mock_cleanup:
            await cache._maybe_cleanup()

    mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_maybe_cleanup_skips_when_under_threshold(cache):
    """Test _maybe_cleanup skips cleanup when under threshold."""
    await cache.initialize()

    mock_stats = CacheStats(
        total_entries=5,
        total_size_bytes=500_000_000,  # 500 MB
        total_size_gb=0.5,  # Under 0.9 threshold
        oldest_entry_age_hours=24.0,
        hit_rate=0.5,
        hits=10,
        misses=10,
    )

    with patch.object(cache, "get_stats", new_callable=AsyncMock, return_value=mock_stats):
        with patch.object(cache, "cleanup", new_callable=AsyncMock) as mock_cleanup:
            await cache._maybe_cleanup()

    mock_cleanup.assert_not_called()


# =============================================================================
# Cache Statistics Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_returns_correct_values(cache):
    """Test get_stats returns correct statistics."""
    await cache.initialize()

    now = time.time()
    cache._metadata = {
        "entry1": CacheEntry(
            source_path="/video/1.mp4",
            source_mtime=1234567890.0,
            cached_path="/tmp/test_cache/1.mp4",  # noqa: S108
            cached_at=now - 3600,
            last_accessed=now - 7200,  # 2 hours ago
            size_bytes=100_000_000,
        ),
        "entry2": CacheEntry(
            source_path="/video/2.mp4",
            source_mtime=1234567891.0,
            cached_path="/tmp/test_cache/2.mp4",  # noqa: S108
            cached_at=now - 1800,
            last_accessed=now - 3600,  # 1 hour ago
            size_bytes=200_000_000,
        ),
    }
    cache._hits = 5
    cache._misses = 3

    stats = await cache.get_stats()

    assert stats.total_entries == 2
    assert stats.total_size_bytes == 300_000_000
    assert stats.total_size_gb == pytest.approx(300_000_000 / 1024 / 1024 / 1024, rel=0.01)
    assert stats.oldest_entry_age_hours == pytest.approx(2.0, rel=0.1)
    assert stats.hit_rate == pytest.approx(5 / 8, rel=0.01)
    assert stats.hits == 5
    assert stats.misses == 3


@pytest.mark.asyncio
async def test_get_stats_empty_cache(cache):
    """Test get_stats with empty cache."""
    await cache.initialize()

    stats = await cache.get_stats()

    assert stats.total_entries == 0
    assert stats.total_size_bytes == 0
    assert stats.total_size_gb == 0.0
    assert stats.oldest_entry_age_hours == 0.0
    assert stats.hit_rate == 0.0


# =============================================================================
# Cache Clear Tests
# =============================================================================


@pytest.mark.asyncio
async def test_clear_removes_all_entries(cache):
    """Test clear removes all cache entries."""
    await cache.initialize()

    # Create a cached file
    cached_path = cache.cache_dir / "test.mp4"
    cached_path.write_bytes(b"test content")

    now = time.time()
    cache._metadata = {
        "entry1": CacheEntry(
            source_path="/video/1.mp4",
            source_mtime=1234567890.0,
            cached_path=str(cached_path),
            cached_at=now,
            last_accessed=now,
            size_bytes=12,
        ),
    }

    await cache.clear()

    assert len(cache._metadata) == 0
    assert not cached_path.exists()


# =============================================================================
# Cache Invalidate Tests
# =============================================================================


@pytest.mark.asyncio
async def test_invalidate_removes_specific_entry(cache, source_video):
    """Test invalidate removes a specific source file's cache entry."""
    await cache.initialize()

    cache_key = cache._get_cache_key(source_video)
    cached_path = cache.cache_dir / f"{cache_key}.mp4"
    cached_path.write_bytes(b"cached content")

    now = time.time()
    cache._metadata[cache_key] = CacheEntry(
        source_path=str(source_video),
        source_mtime=source_video.stat().st_mtime,
        cached_path=str(cached_path),
        cached_at=now,
        last_accessed=now,
        size_bytes=14,
    )

    result = await cache.invalidate(source_video)

    assert result is True
    assert cache_key not in cache._metadata
    assert not cached_path.exists()


@pytest.mark.asyncio
async def test_invalidate_returns_false_when_not_found(cache, source_video):
    """Test invalidate returns False when entry not found."""
    await cache.initialize()

    result = await cache.invalidate(source_video)

    assert result is False


# =============================================================================
# Metadata Persistence Tests
# =============================================================================


@pytest.mark.asyncio
async def test_metadata_persists_across_instances(mock_config, source_video, transcoded_video):
    """Test metadata persists to disk and can be reloaded."""
    # First instance - store a file
    cache1 = TranscodeCache(config=mock_config)
    await cache1.initialize()
    await cache1.put(source_video, transcoded_video)

    cache_key = cache1._get_cache_key(source_video)
    assert cache_key in cache1._metadata

    # Second instance - should load metadata
    cache2 = TranscodeCache(config=mock_config)
    await cache2.initialize()

    assert cache_key in cache2._metadata
    entry = cache2._metadata[cache_key]
    assert entry.source_path == str(source_video)


@pytest.mark.asyncio
async def test_load_metadata_handles_missing_file(cache):
    """Test _load_metadata handles missing file gracefully."""
    # metadata_file doesn't exist yet
    await cache._load_metadata()

    assert cache._metadata == {}


@pytest.mark.asyncio
async def test_load_metadata_handles_corrupted_file(cache):
    """Test _load_metadata handles corrupted JSON gracefully."""
    await cache.initialize()

    # Write corrupted JSON
    cache.metadata_file.write_text("{ invalid json }")

    # Create new cache instance to trigger load
    cache._metadata = {}
    await cache._load_metadata()

    assert cache._metadata == {}


# =============================================================================
# Singleton Pattern Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_transcode_cache_returns_singleton():
    """Test get_transcode_cache returns singleton instance."""
    await reset_transcode_cache()

    with patch("backend.services.transcode_cache.TranscodeCache") as MockCache:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        MockCache.return_value = mock_instance

        cache1 = await get_transcode_cache()
        cache2 = await get_transcode_cache()

        # Should only create one instance
        MockCache.assert_called_once()
        assert cache1 is cache2

        await reset_transcode_cache()


@pytest.mark.asyncio
async def test_reset_transcode_cache_clears_singleton():
    """Test reset_transcode_cache clears the singleton."""
    await reset_transcode_cache()

    with patch("backend.services.transcode_cache.TranscodeCache") as MockCache:
        mock_instance = AsyncMock()
        mock_instance.initialize = AsyncMock()
        MockCache.return_value = mock_instance

        await get_transcode_cache()
        await reset_transcode_cache()
        await get_transcode_cache()

        # Should create two instances (before and after reset)
        assert MockCache.call_count == 2

        await reset_transcode_cache()


# =============================================================================
# CacheEntry and CacheStats Dataclass Tests
# =============================================================================


def test_cache_entry_dataclass():
    """Test CacheEntry dataclass works correctly."""
    entry = CacheEntry(
        source_path="/video/test.mp4",
        source_mtime=1234567890.0,
        cached_path="/cache/abc123.mp4",
        cached_at=1700000000.0,
        last_accessed=1700000000.0,
        size_bytes=1000000,
        duration_seconds=60.5,
    )

    assert entry.source_path == "/video/test.mp4"
    assert entry.source_mtime == 1234567890.0
    assert entry.cached_path == "/cache/abc123.mp4"
    assert entry.size_bytes == 1000000
    assert entry.duration_seconds == 60.5


def test_cache_entry_optional_duration():
    """Test CacheEntry duration_seconds is optional."""
    entry = CacheEntry(
        source_path="/video/test.mp4",
        source_mtime=1234567890.0,
        cached_path="/cache/abc123.mp4",
        cached_at=1700000000.0,
        last_accessed=1700000000.0,
        size_bytes=1000000,
    )

    assert entry.duration_seconds is None


def test_cache_stats_dataclass():
    """Test CacheStats dataclass works correctly."""
    stats = CacheStats(
        total_entries=10,
        total_size_bytes=1073741824,  # 1 GB
        total_size_gb=1.0,
        oldest_entry_age_hours=24.0,
        hit_rate=0.75,
        hits=75,
        misses=25,
    )

    assert stats.total_entries == 10
    assert stats.total_size_gb == 1.0
    assert stats.hit_rate == 0.75
    assert stats.hits == 75
    assert stats.misses == 25


# =============================================================================
# Configuration Tests
# =============================================================================


def test_transcode_cache_settings_defaults():
    """Test TranscodeCacheSettings has correct defaults."""
    config = TranscodeCacheSettings()

    assert config.cache_dir == "data/transcode_cache"
    assert config.max_cache_size_gb == 10.0
    assert config.max_file_age_days == 7
    assert config.cleanup_threshold_percent == 0.9
    assert config.cleanup_target_percent == 0.8
    assert config.lock_timeout_seconds == 30
    assert config.enabled is True


def test_transcode_cache_settings_custom_values():
    """Test TranscodeCacheSettings accepts custom values."""
    config = TranscodeCacheSettings(
        cache_dir="/custom/cache",
        max_cache_size_gb=50.0,
        max_file_age_days=30,
        cleanup_threshold_percent=0.95,
        cleanup_target_percent=0.85,
        lock_timeout_seconds=60,
        enabled=False,
    )

    assert config.cache_dir == "/custom/cache"
    assert config.max_cache_size_gb == 50.0
    assert config.max_file_age_days == 30
    assert config.cleanup_threshold_percent == 0.95
    assert config.cleanup_target_percent == 0.85
    assert config.lock_timeout_seconds == 60
    assert config.enabled is False


# =============================================================================
# Concurrent Access Tests
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_get_operations(cache, source_video):
    """Test concurrent get operations are safe."""
    await cache.initialize()

    # Multiple concurrent get operations
    results = await asyncio.gather(
        cache.get(source_video),
        cache.get(source_video),
        cache.get(source_video),
    )

    # All should return None (cache miss) without errors
    assert all(r is None for r in results)
    assert cache._misses == 3


@pytest.mark.asyncio
async def test_concurrent_put_operations(cache, temp_dir):
    """Test concurrent put operations are safe."""
    await cache.initialize()

    # Create multiple source and transcoded files
    async def create_and_put(index: int) -> None:
        source = Path(temp_dir) / "sources" / f"video{index}.mp4"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(f"source content {index}".encode())

        transcoded = Path(temp_dir) / "transcoded" / f"output{index}.mp4"
        transcoded.parent.mkdir(parents=True, exist_ok=True)
        transcoded.write_bytes(f"transcoded content {index}".encode())

        return await cache.put(source, transcoded)

    # Run concurrent puts
    results = await asyncio.gather(
        create_and_put(0),
        create_and_put(1),
        create_and_put(2),
    )

    # All should complete without errors
    assert len(results) == 3
    assert all(r.exists() for r in results)
    assert len(cache._metadata) == 3


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cache_handles_unicode_paths(cache, temp_dir):
    """Test cache handles unicode characters in paths."""
    await cache.initialize()

    source = Path(temp_dir) / "sources" / "video_\u00e9\u00e8\u00ea.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source content")

    transcoded = Path(temp_dir) / "transcoded" / "output_\u00e9\u00e8\u00ea.mp4"
    transcoded.parent.mkdir(parents=True, exist_ok=True)
    transcoded.write_bytes(b"transcoded content")

    result = await cache.put(source, transcoded)
    assert result.exists()

    # Get should also work
    cached = await cache.get(source)
    assert cached == result


@pytest.mark.asyncio
async def test_cache_handles_large_metadata(cache, temp_dir):
    """Test cache handles large number of entries."""
    await cache.initialize()

    # Create many entries
    now = time.time()
    for i in range(100):
        cache._metadata[f"entry{i}"] = CacheEntry(
            source_path=f"/video/{i}.mp4",
            source_mtime=1234567890.0 + i,
            cached_path=f"/tmp/cache/{i}.mp4",  # noqa: S108
            cached_at=now,
            last_accessed=now,
            size_bytes=1000000,
        )

    # Save and reload
    await cache._save_metadata()

    cache2 = TranscodeCache(config=cache.config)
    await cache2._load_metadata()

    assert len(cache2._metadata) == 100
