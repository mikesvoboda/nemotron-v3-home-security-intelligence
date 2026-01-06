"""Async utility functions for non-blocking I/O operations.

This module provides async wrappers for common blocking operations that would
otherwise block the event loop in an async application:

- async_sleep: Non-blocking replacement for time.sleep
- async_open_image: Non-blocking PIL Image.open
- async_subprocess_run: Non-blocking subprocess.run
- AsyncTaskGroup: Structured concurrency with Python 3.11+ TaskGroup
- bounded_gather: asyncio.gather with concurrency limits
- async_read_bytes/text: Non-blocking file reading
- async_write_bytes/text: Non-blocking file writing

Usage:
    from backend.core.async_utils import (
        async_sleep,
        async_open_image,
        async_subprocess_run,
        AsyncTaskGroup,
        bounded_gather,
    )

    # Instead of: time.sleep(1.0)
    await async_sleep(1.0)

    # Instead of: img = Image.open(path)
    img = await async_open_image(path)

    # Instead of: result = subprocess.run([...])
    result = await async_subprocess_run([...])

    # Structured concurrency with automatic cancellation
    async with AsyncTaskGroup() as tg:
        tg.create_task(operation_a())
        tg.create_task(operation_b())

    # Concurrent operations with limit
    results = await bounded_gather(
        [operation(i) for i in range(100)],
        limit=10,
    )
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Awaitable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from PIL import Image

from backend.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


async def async_sleep(seconds: float) -> None:
    """Non-blocking sleep that yields to the event loop.

    Use this instead of time.sleep() in async code to avoid blocking
    the event loop.

    Args:
        seconds: Number of seconds to sleep. Can be fractional.

    Example:
        # Instead of:
        # import time
        # time.sleep(1.0)  # BLOCKS the event loop!

        # Use:
        from backend.core.async_utils import async_sleep
        await async_sleep(1.0)  # Yields to other tasks
    """
    await asyncio.sleep(seconds)


async def async_open_image(
    path: str | Path,
) -> Image.Image | None:
    """Open an image file asynchronously without blocking the event loop.

    This runs PIL's Image.open in a thread pool executor to avoid
    blocking disk I/O on the main thread.

    Args:
        path: Path to the image file (string or Path object)

    Returns:
        PIL Image object if successful, None if the file doesn't exist
        or is not a valid image.

    Example:
        from backend.core.async_utils import async_open_image

        # Instead of:
        # from PIL import Image
        # img = Image.open(path)  # BLOCKS on disk I/O!

        # Use:
        img = await async_open_image(path)
        if img is not None:
            # Process image
            img.close()
    """
    from PIL import Image

    def _open_image() -> Image.Image | None:
        try:
            return Image.open(path)
        except FileNotFoundError:
            logger.debug(f"Image file not found: {path}")
            return None
        except Exception as e:
            logger.debug(f"Failed to open image {path}: {e}")
            return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _open_image)


async def async_subprocess_run(
    args: list[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    check: bool = False,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str | bytes]:
    """Run a subprocess asynchronously without blocking the event loop.

    This wraps subprocess.run in asyncio.to_thread to avoid blocking
    the event loop during subprocess execution.

    Args:
        args: Command and arguments to execute
        capture_output: If True, capture stdout and stderr
        text: If True, decode stdout/stderr as text
        timeout: Timeout in seconds (None for no timeout)
        check: If True, raise CalledProcessError on non-zero exit
        cwd: Working directory for the command
        env: Environment variables for the command

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Raises:
        FileNotFoundError: If the command is not found
        subprocess.TimeoutExpired: If the command times out
        subprocess.CalledProcessError: If check=True and returncode != 0

    Example:
        from backend.core.async_utils import async_subprocess_run

        # Instead of:
        # import subprocess
        # result = subprocess.run(['ls', '-la'], capture_output=True)  # BLOCKS!

        # Use:
        result = await async_subprocess_run(
            ['ls', '-la'],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
    """

    def _run_subprocess() -> subprocess.CompletedProcess[str | bytes]:
        # S603: args is validated by the caller - this is an internal utility function
        return subprocess.run(  # noqa: S603  # nosemgrep
            args,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            check=check,
            cwd=cwd,
            env=env,
        )

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_subprocess)


class AsyncTaskGroup:
    """Structured concurrency helper using Python 3.11+ TaskGroup.

    Provides automatic cancellation of all tasks if any task fails,
    ensuring clean shutdown and preventing task leakage.

    Usage:
        async with AsyncTaskGroup() as tg:
            tg.create_task(operation_a())
            tg.create_task(operation_b())
        # Both tasks are guaranteed to complete or be cancelled

    Note:
        If any task raises an exception, all other tasks are cancelled
        and an ExceptionGroup is raised containing all exceptions.
    """

    def __init__(self) -> None:
        """Initialize the task group."""
        self._tg: asyncio.TaskGroup | None = None

    async def __aenter__(self) -> AsyncTaskGroup:
        """Enter the async context manager."""
        self._tg = asyncio.TaskGroup()
        await self._tg.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the async context manager."""
        if self._tg is not None:
            await self._tg.__aexit__(exc_type, exc_val, exc_tb)

    def create_task(self, coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        """Create a task within this group.

        Args:
            coro: Coroutine to run as a task

        Returns:
            The created Task object

        Raises:
            RuntimeError: If called outside the async context manager
        """
        if self._tg is None:
            raise RuntimeError("AsyncTaskGroup must be used as async context manager")
        return self._tg.create_task(coro)


async def bounded_gather(  # noqa: UP047 - Using TypeVar for broader compatibility
    coros: list[Awaitable[T]],
    *,
    limit: int = 10,
    return_exceptions: bool = False,
) -> list[T]:
    """Execute awaitables concurrently with a limit on parallelism.

    Similar to asyncio.gather but limits the number of concurrent tasks
    using a semaphore. Results are returned in the same order as input.

    Args:
        coros: List of awaitables to execute
        limit: Maximum number of concurrent tasks (default: 10)
        return_exceptions: If True, exceptions are returned as results
            instead of being raised

    Returns:
        List of results in the same order as input awaitables

    Raises:
        Exception: Re-raises the first exception if return_exceptions=False

    Example:
        from backend.core.async_utils import bounded_gather

        # Run 100 HTTP requests with max 10 concurrent
        results = await bounded_gather(
            [fetch_url(url) for url in urls],
            limit=10,
        )
    """
    semaphore = asyncio.Semaphore(limit)

    async def with_semaphore(index: int, coro: Awaitable[T]) -> tuple[int, T]:
        async with semaphore:
            result = await coro
            return (index, result)

    # Create tasks with index to preserve order
    tasks = [with_semaphore(i, coro) for i, coro in enumerate(coros)]

    # Execute with gather
    results = await asyncio.gather(*tasks, return_exceptions=return_exceptions)

    # Handle exceptions in results
    if not return_exceptions:
        for result in results:
            if isinstance(result, Exception):
                raise result

    # Sort by index to restore original order and extract results
    # Cast to expected type since we know the structure at this point
    typed_results = [r for r in results if isinstance(r, tuple)]
    sorted_results = sorted(typed_results, key=lambda x: x[0])

    # Extract just the results (not the indices)
    return [result[1] for result in sorted_results]


async def async_read_bytes(path: str | Path) -> bytes | None:
    """Read file bytes asynchronously without blocking.

    Args:
        path: Path to the file

    Returns:
        File contents as bytes, or None if file doesn't exist or error occurs
    """

    def _read() -> bytes | None:
        try:
            return Path(path).read_bytes()  # nosemgrep: path-traversal-open
        except Exception as e:
            logger.debug(f"Failed to read file {path}: {e}")
            return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _read)


async def async_read_text(
    path: str | Path,
    encoding: str = "utf-8",
) -> str | None:
    """Read file text asynchronously without blocking.

    Args:
        path: Path to the file
        encoding: Text encoding (default: utf-8)

    Returns:
        File contents as string, or None if file doesn't exist or error occurs
    """

    def _read() -> str | None:
        try:
            return Path(path).read_text(encoding=encoding)  # nosemgrep: path-traversal-open
        except Exception as e:
            logger.debug(f"Failed to read file {path}: {e}")
            return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _read)


async def async_write_bytes(path: str | Path, content: bytes) -> bool:
    """Write bytes to file asynchronously without blocking.

    Args:
        path: Path to the file
        content: Bytes to write

    Returns:
        True if successful, False otherwise
    """

    def _write() -> bool:
        try:
            Path(path).write_bytes(content)
            return True
        except Exception as e:
            logger.debug(f"Failed to write file {path}: {e}")
            return False

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _write)


async def async_write_text(
    path: str | Path,
    content: str,
    encoding: str = "utf-8",
) -> bool:
    """Write text to file asynchronously without blocking.

    Args:
        path: Path to the file
        content: Text to write
        encoding: Text encoding (default: utf-8)

    Returns:
        True if successful, False otherwise
    """

    def _write() -> bool:
        try:
            Path(path).write_text(content, encoding=encoding)
            return True
        except Exception as e:
            logger.debug(f"Failed to write file {path}: {e}")
            return False

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _write)
