"""Performance profiling utilities for deep debugging (NEM-1644).

This module provides profiling infrastructure including:
- profile_if_enabled decorator for function/method profiling
- ProfilingManager for state management (start/stop/stats)
- Integration with cProfile for detailed performance analysis

Usage:
    # Decorator for automatic profiling
    @profile_if_enabled
    async def my_endpoint_handler():
        ...

    # Manual profiling control
    manager = get_profiling_manager()
    manager.start()
    # ... do work ...
    manager.stop()
    print(manager.get_stats_text())

Profile files can be analyzed with:
    - snakeviz: `snakeviz data/profiles/my_function.prof`
    - py-spy: `py-spy top --pid <PID>`
"""

from __future__ import annotations

__all__ = [
    "ProfilingManager",
    "get_profiling_manager",
    "profile_if_enabled",
    "reset_profiling_manager",
]

import cProfile
import io
import pstats
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path

from backend.core.logging import get_logger

logger = get_logger(__name__)


class ProfilingManager:
    """Manages cProfile profiling state and statistics.

    This class provides thread-safe profiling management including:
    - Starting/stopping profiling sessions
    - Saving profile data to disk
    - Generating human-readable statistics

    Attributes:
        output_dir: Directory for storing .prof files
        is_profiling: Whether profiling is currently active
    """

    def __init__(self, output_dir: str | Path | None = None) -> None:
        """Initialize the profiling manager.

        Args:
            output_dir: Directory for storing .prof files.
                       Defaults to settings.profiling_output_dir.
        """
        if output_dir is None:
            from backend.core.config import get_settings

            output_dir = get_settings().profiling_output_dir

        self._output_dir = Path(output_dir)
        self._profiler: cProfile.Profile | None = None
        self._last_profile_path: str | None = None
        self._last_stats: pstats.Stats | None = None
        self._started_at: datetime | None = None

    @property
    def is_profiling(self) -> bool:
        """Check if profiling is currently active."""
        return self._profiler is not None

    @property
    def last_profile_path(self) -> str | None:
        """Get the path to the last saved profile file."""
        return self._last_profile_path

    def start(self) -> None:
        """Start profiling.

        Creates a new profiler and begins collecting statistics.
        If already profiling, this is a no-op.
        """
        if self._profiler is not None:
            logger.warning("Profiling already started, ignoring start request")
            return

        # Ensure output directory exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._profiler = cProfile.Profile()
        self._profiler.enable()
        self._started_at = datetime.now(UTC)

        logger.info(
            "Profiling started",
            extra={"output_dir": str(self._output_dir), "started_at": self._started_at.isoformat()},
        )

    def stop(self) -> pstats.Stats | None:
        """Stop profiling and save results.

        Returns:
            pstats.Stats object if profiling was active, None otherwise.
        """
        if self._profiler is None:
            logger.debug("Profiling not running, ignoring stop request")
            return None

        self._profiler.disable()

        # Generate timestamp-based filename
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        profile_filename = f"profile_{timestamp}.prof"
        profile_path = self._output_dir / profile_filename

        # Save profile to disk
        self._profiler.dump_stats(str(profile_path))
        self._last_profile_path = str(profile_path)

        # Create stats object for analysis
        self._last_stats = pstats.Stats(self._profiler)

        logger.info(
            "Profiling stopped",
            extra={"profile_path": str(profile_path)},
        )

        # Clean up
        self._profiler = None
        self._started_at = None

        return self._last_stats

    def get_stats_text(self, sort_by: str = "cumulative", limit: int = 30) -> str:
        """Get human-readable profiling statistics.

        Args:
            sort_by: Sort order for stats (cumulative, time, calls)
            limit: Maximum number of entries to include

        Returns:
            Formatted statistics text, or empty string if no stats available.
        """
        if self._last_stats is None:
            return ""

        # Capture stats output to string
        output = io.StringIO()
        # Create a new Stats object from the last profile path (Stats.copy() doesn't exist)
        if self._last_profile_path:
            stats = pstats.Stats(self._last_profile_path, stream=output)
            stats.sort_stats(sort_by)
            stats.print_stats(limit)
            return output.getvalue()

        return ""

    def get_started_at(self) -> datetime | None:
        """Get the timestamp when profiling was started."""
        return self._started_at


# Global profiling manager instance
_profiling_manager: ProfilingManager | None = None


def get_profiling_manager() -> ProfilingManager:
    """Get the global profiling manager instance.

    Returns:
        Singleton ProfilingManager instance.
    """
    global _profiling_manager  # noqa: PLW0603
    if _profiling_manager is None:
        _profiling_manager = ProfilingManager()
    return _profiling_manager


def reset_profiling_manager() -> None:
    """Reset the global profiling manager.

    Useful for testing to ensure clean state.
    """
    global _profiling_manager  # noqa: PLW0603
    if _profiling_manager is not None and _profiling_manager.is_profiling:
        _profiling_manager.stop()
    _profiling_manager = None


def profile_if_enabled[**P, R](
    func: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Decorator to profile async functions when profiling is enabled.

    This decorator wraps async functions to automatically profile them
    when PROFILING_ENABLED=true in settings. When profiling is disabled,
    the function runs with minimal overhead.

    Args:
        func: Async function to profile

    Returns:
        Wrapped function that profiles when enabled

    Usage:
        @profile_if_enabled
        async def my_handler():
            ...
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        from backend.core.config import get_settings

        settings = get_settings()

        if not settings.profiling_enabled:
            return await func(*args, **kwargs)

        # Create a function-specific profiler
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            profiler.disable()

            # Save profile to disk
            output_dir = Path(settings.profiling_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
            profile_path = output_dir / f"{func.__name__}_{timestamp}.prof"
            profiler.dump_stats(str(profile_path))

            logger.debug(
                "Function profiled",
                extra={"function": func.__name__, "profile_path": str(profile_path)},
            )

    return wrapper
