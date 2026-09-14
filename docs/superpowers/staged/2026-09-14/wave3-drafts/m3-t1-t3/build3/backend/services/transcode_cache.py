"""Disk-based cache for transcoded videos with LRU eviction.

This service provides caching for transcoded video files to avoid repeated
transcoding of the same source files. Features:

- Disk-based storage with configurable size limits
- LRU eviction when cache exceeds size threshold
- Automatic invalidation when source file changes (based on mtime)
- Persistent metadata survives restarts
- Cache hit/miss logging for observability
- Thread-safe operations with async locking

Usage:
    cache = await get_transcode_cache()

    # Check cache for existing transcode
    cached_path = await cache.get(source_path)
    if cached_path:
        return cached_path  # Cache hit

    # Transcode and store in cache
    transcoded_path = await transcode_video(source_path)
    final_path = await cache.put(source_path, transcoded_path)
    return final_path
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.config import TranscodeCacheSettings

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Metadata for a cached transcode."""

    source_path: str
    source_mtime: float
    cached_path: str
    cached_at: float
    last_accessed: float
    size_bytes: int
    duration_seconds: float | None = None


@dataclass
class CacheStats:
    """Cache statistics."""

    total_entries: int
    total_size_bytes: int
    total_size_gb: float
    oldest_entry_age_hours: float
    hit_rate: float
    hits: int
    misses: int


class TranscodeCache:
    """Disk-based cache for transcoded videos with LRU eviction.

    This class manages a cache of transcoded video files on disk. It uses
    LRU (Least Recently Used) eviction to stay within configured size limits.

    Cache keys are generated from source file path and modification time,
    ensuring automatic invalidation when source files change.

    Attributes:
        config: Configuration settings for the cache
        cache_dir: Path to the cache directory
    """

    def __init__(self, config: TranscodeCacheSettings | None = None) -> None:
        """Initialize the transcode cache.

        Args:
            config: Cache configuration settings. If None, loads from app settings.
        """
        if config is None:
            from backend.core.config import get_settings

            config = get_settings().transcode_cache
        self.config = config
        self.cache_dir = Path(config.cache_dir)
        self.metadata_file = self.cache_dir / "metadata.json"
        self._metadata: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize cache directory and load metadata.

        Creates the cache directory if it doesn't exist and loads
        existing metadata from disk.
        """
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            # Create cache directory
            await asyncio.to_thread(self.cache_dir.mkdir, parents=True, exist_ok=True)

            # Load existing metadata
            await self._load_metadata()

            self._initialized = True
            logger.info(
                f"TranscodeCache initialized: {len(self._metadata)} entries, "
                f"cache_dir={self.cache_dir}"
            )

    def _get_cache_key(self, source_path: Path) -> str:
        """Generate unique cache key for a source file.

        Key is based on file path and modification time to invalidate
        cache when source file changes.

        Args:
            source_path: Path to the source video file

        Returns:
            16-character hex string cache key
        """
        try:
            mtime = source_path.stat().st_mtime
        except OSError:
            mtime = 0

        key_data = f"{source_path}:{mtime}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    async def get(self, source_path: Path) -> Path | None:
        """Get cached transcode if available and valid.

        Checks the cache for an existing transcode of the source file.
        Updates last_accessed time on cache hit.

        Args:
            source_path: Path to the original video file

        Returns:
            Path to cached transcoded file if found and valid, None otherwise
        """
        if not self.config.enabled:
            logger.debug("Cache disabled, returning None")
            self._misses += 1
            return None

        await self.initialize()

        cache_key = self._get_cache_key(source_path)

        async with self._lock:
            entry = self._metadata.get(cache_key)

            if entry is None:
                self._misses += 1
                logger.debug(f"Cache miss (not found): {source_path}")
                return None

            cached_path = Path(entry.cached_path)

            # Verify cached file still exists
            if not cached_path.exists():
                logger.warning(f"Cache entry missing file: {cached_path}")
                del self._metadata[cache_key]
                await self._save_metadata()
                self._misses += 1
                return None

            # Verify source hasn't changed
            try:
                current_mtime = source_path.stat().st_mtime
                if current_mtime != entry.source_mtime:
                    logger.info(f"Cache invalidated (source modified): {source_path}")
                    await self._remove_entry(cache_key)
                    self._misses += 1
                    return None
            except OSError:
                pass  # Source might be gone, but cache is still valid

            # Update last accessed time
            entry.last_accessed = time.time()
            await self._save_metadata()

            self._hits += 1
            logger.debug(f"Cache hit: {source_path} -> {cached_path}")
            return cached_path

    async def put(
        self,
        source_path: Path,
        transcoded_path: Path,
        duration_seconds: float | None = None,
    ) -> Path:
        """Store transcoded file in cache.

        Moves the transcoded file to the cache directory and records
        metadata. May trigger cleanup if cache exceeds size threshold.

        Args:
            source_path: Path to the original video file
            transcoded_path: Path to the transcoded output file
            duration_seconds: Optional video duration for statistics

        Returns:
            Final path of the cached file
        """
        if not self.config.enabled:
            logger.debug("Cache disabled, returning original path")
            return transcoded_path

        await self.initialize()

        cache_key = self._get_cache_key(source_path)

        # Determine final cache path
        cached_filename = f"{cache_key}.mp4"
        cached_path = self.cache_dir / cached_filename

        async with self._lock:
            # Move transcoded file to cache directory
            if transcoded_path != cached_path:
                await asyncio.to_thread(shutil.move, str(transcoded_path), str(cached_path))

            # Get file size
            size_bytes = cached_path.stat().st_size

            # Create cache entry
            try:
                source_mtime = source_path.stat().st_mtime
            except OSError:
                source_mtime = 0

            entry = CacheEntry(
                source_path=str(source_path),
                source_mtime=source_mtime,
                cached_path=str(cached_path),
                cached_at=time.time(),
                last_accessed=time.time(),
                size_bytes=size_bytes,
                duration_seconds=duration_seconds,
            )

            self._metadata[cache_key] = entry
            await self._save_metadata()

            size_mb = size_bytes / 1024 / 1024
            logger.info(f"Cached transcode: {source_path} -> {cached_path} ({size_mb:.1f}MB)")

        # Check if cleanup needed (outside lock to avoid holding it too long)
        await self._maybe_cleanup()

        return cached_path

    async def _maybe_cleanup(self) -> None:
        """Run cleanup if cache size exceeds threshold."""
        stats = await self.get_stats()
        threshold_gb = self.config.max_cache_size_gb * self.config.cleanup_threshold_percent

        if stats.total_size_gb > threshold_gb:
            logger.info(
                f"Cache cleanup triggered: {stats.total_size_gb:.2f}GB > "
                f"{threshold_gb:.2f}GB threshold"
            )
            await self.cleanup()

    async def cleanup(self) -> int:
        """Remove old entries using LRU eviction until under size limit.

        Evicts entries starting with the least recently accessed until
        cache size is below target threshold.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            # Sort by last accessed (oldest first)
            sorted_entries = sorted(
                self._metadata.items(),
                key=lambda x: x[1].last_accessed,
            )

            current_size = sum(e.size_bytes for e in self._metadata.values())
            target_size_bytes = int(
                self.config.max_cache_size_gb
                * self.config.cleanup_target_percent
                * 1024
                * 1024
                * 1024
            )

            removed = 0
            for cache_key, entry in sorted_entries:
                if current_size <= target_size_bytes:
                    break

                # Remove file
                try:
                    await asyncio.to_thread(Path(entry.cached_path).unlink, missing_ok=True)
                except OSError as e:
                    logger.warning(f"Failed to remove cached file {entry.cached_path}: {e}")

                current_size -= entry.size_bytes
                del self._metadata[cache_key]
                removed += 1

            if removed > 0:
                await self._save_metadata()
                logger.info(f"Cache cleanup: removed {removed} entries")

            return removed

    async def _remove_entry(self, cache_key: str) -> None:
        """Remove a single cache entry.

        Args:
            cache_key: Key of the entry to remove
        """
        entry = self._metadata.get(cache_key)
        if entry:
            try:
                await asyncio.to_thread(Path(entry.cached_path).unlink, missing_ok=True)
            except OSError as e:
                logger.warning(f"Failed to remove cached file {entry.cached_path}: {e}")
            del self._metadata[cache_key]
            await self._save_metadata()

    async def _load_metadata(self) -> None:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:

                def _read_metadata() -> dict[str, Any]:
                    # nosemgrep: path-traversal-open - metadata_file is from trusted config
                    with open(self.metadata_file) as f:
                        result: dict[str, Any] = json.load(f)
                        return result

                data = await asyncio.to_thread(_read_metadata)
                self._metadata = {k: CacheEntry(**v) for k, v in data.items()}
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to load cache metadata: {e}")
                self._metadata = {}

    async def _save_metadata(self) -> None:
        """Save metadata to disk."""
        data = {k: asdict(v) for k, v in self._metadata.items()}

        def _write_metadata() -> None:
            # Write to temp file first, then rename for atomicity
            temp_file = self.metadata_file.with_suffix(".tmp")
            # nosemgrep: path-traversal-open - metadata_file is from trusted config
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            temp_file.rename(self.metadata_file)

        await asyncio.to_thread(_write_metadata)

    async def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object with current cache metrics
        """
        await self.initialize()

        total_size = sum(e.size_bytes for e in self._metadata.values())

        oldest_age = 0.0
        if self._metadata:
            oldest = min(e.last_accessed for e in self._metadata.values())
            oldest_age = (time.time() - oldest) / 3600

        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return CacheStats(
            total_entries=len(self._metadata),
            total_size_bytes=total_size,
            total_size_gb=total_size / 1024 / 1024 / 1024,
            oldest_entry_age_hours=oldest_age,
            hit_rate=hit_rate,
            hits=self._hits,
            misses=self._misses,
        )

    async def clear(self) -> None:
        """Clear all cached files."""
        await self.initialize()

        async with self._lock:
            for entry in self._metadata.values():
                try:
                    await asyncio.to_thread(Path(entry.cached_path).unlink, missing_ok=True)
                except OSError as e:
                    logger.warning(f"Failed to remove cached file {entry.cached_path}: {e}")

            self._metadata = {}
            await self._save_metadata()
            logger.info("Cache cleared")

    async def invalidate(self, source_path: Path) -> bool:
        """Invalidate cache entry for a specific source file.

        Args:
            source_path: Path to the source file to invalidate

        Returns:
            True if entry was found and removed, False otherwise
        """
        await self.initialize()

        cache_key = self._get_cache_key(source_path)

        async with self._lock:
            if cache_key in self._metadata:
                await self._remove_entry(cache_key)
                logger.info(f"Cache invalidated for: {source_path}")
                return True
            return False


# Singleton instance
_cache: TranscodeCache | None = None


async def get_transcode_cache() -> TranscodeCache:
    """Get singleton TranscodeCache instance.

    Returns:
        Initialized TranscodeCache instance
    """
    global _cache  # noqa: PLW0603
    if _cache is None:
        _cache = TranscodeCache()
        await _cache.initialize()
    return _cache


async def reset_transcode_cache() -> None:
    """Reset the transcode cache singleton (for testing)."""
    global _cache  # noqa: PLW0603
    _cache = None
