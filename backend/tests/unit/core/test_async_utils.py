"""Unit tests for async utility functions.

Tests for backend/core/async_utils.py which provides non-blocking wrappers
for common I/O operations that would otherwise block the event loop.

Tests cover:
- async_sleep: Non-blocking sleep replacement for time.sleep
- async_open_image: Non-blocking PIL Image.open wrapper
- async_subprocess_run: Non-blocking subprocess.run wrapper
- AsyncTaskGroup: Structured concurrency with proper error handling
"""

import asyncio
import subprocess
from pathlib import Path

import pytest
from PIL import Image


class TestAsyncSleep:
    """Tests for async_sleep function."""

    @pytest.mark.asyncio
    async def test_async_sleep_basic(self) -> None:
        """Test that async_sleep completes after the specified duration."""
        import time

        from backend.core.async_utils import async_sleep

        start = time.monotonic()
        await async_sleep(0.1)
        elapsed = time.monotonic() - start

        # Allow some tolerance for timing
        assert elapsed >= 0.09
        assert elapsed < 0.3

    @pytest.mark.asyncio
    async def test_async_sleep_zero_duration(self) -> None:
        """Test that async_sleep with zero duration completes immediately."""
        import time

        from backend.core.async_utils import async_sleep

        start = time.monotonic()
        await async_sleep(0)
        elapsed = time.monotonic() - start

        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_async_sleep_allows_other_tasks(self) -> None:
        """Test that async_sleep yields to other tasks."""
        from backend.core.async_utils import async_sleep

        results: list[int] = []

        async def task_a() -> None:
            await async_sleep(0.05)
            results.append(1)

        async def task_b() -> None:
            results.append(2)

        # task_b should complete before task_a
        await asyncio.gather(task_a(), task_b())

        assert results == [2, 1]


class TestAsyncOpenImage:
    """Tests for async_open_image function."""

    @pytest.mark.asyncio
    async def test_async_open_image_basic(self, tmp_path: Path) -> None:
        """Test that async_open_image loads a valid image file."""
        from backend.core.async_utils import async_open_image

        # Create a test image
        test_image_path = tmp_path / "test.jpg"
        img = Image.new("RGB", (100, 100), color="red")
        img.save(test_image_path, "JPEG")

        # Load it asynchronously
        loaded = await async_open_image(str(test_image_path))

        assert loaded is not None
        assert loaded.size == (100, 100)
        loaded.close()

    @pytest.mark.asyncio
    async def test_async_open_image_with_path_object(self, tmp_path: Path) -> None:
        """Test that async_open_image works with Path objects."""
        from backend.core.async_utils import async_open_image

        test_image_path = tmp_path / "test.png"
        img = Image.new("RGBA", (50, 50), color="blue")
        img.save(test_image_path, "PNG")

        loaded = await async_open_image(test_image_path)

        assert loaded is not None
        assert loaded.size == (50, 50)
        loaded.close()

    @pytest.mark.asyncio
    async def test_async_open_image_nonexistent_file(self) -> None:
        """Test that async_open_image returns None for nonexistent files."""
        from backend.core.async_utils import async_open_image

        result = await async_open_image("/nonexistent/path/image.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_async_open_image_invalid_file(self, tmp_path: Path) -> None:
        """Test that async_open_image returns None for invalid image files."""
        from backend.core.async_utils import async_open_image

        # Create a non-image file
        invalid_file = tmp_path / "not_an_image.txt"
        invalid_file.write_text("This is not an image")

        result = await async_open_image(str(invalid_file))

        assert result is None


class TestAsyncSubprocessRun:
    """Tests for async_subprocess_run function."""

    @pytest.mark.asyncio
    async def test_async_subprocess_run_basic(self) -> None:
        """Test that async_subprocess_run executes a command."""
        from backend.core.async_utils import async_subprocess_run

        result = await async_subprocess_run(
            ["echo", "hello"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_async_subprocess_run_with_timeout(self) -> None:
        """Test that async_subprocess_run respects timeout."""
        from backend.core.async_utils import async_subprocess_run

        # Command that should complete quickly
        result = await async_subprocess_run(
            ["echo", "test"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )

        assert result.returncode == 0

    @pytest.mark.asyncio
    async def test_async_subprocess_run_timeout_expires(self) -> None:
        """Test that async_subprocess_run handles timeout expiration."""
        from backend.core.async_utils import async_subprocess_run

        # Command that takes too long
        with pytest.raises(subprocess.TimeoutExpired):
            await async_subprocess_run(
                ["sleep", "10"],
                timeout=0.1,
            )

    @pytest.mark.asyncio
    async def test_async_subprocess_run_nonexistent_command(self) -> None:
        """Test that async_subprocess_run handles nonexistent commands."""
        from backend.core.async_utils import async_subprocess_run

        with pytest.raises(FileNotFoundError):
            await async_subprocess_run(["nonexistent_command_12345"])

    @pytest.mark.asyncio
    async def test_async_subprocess_run_allows_other_tasks(self) -> None:
        """Test that async_subprocess_run yields to other tasks."""
        from backend.core.async_utils import async_subprocess_run

        results: list[str] = []

        async def run_command() -> None:
            await async_subprocess_run(
                ["sleep", "0.05"],
                timeout=5.0,
            )
            results.append("command_done")

        async def quick_task() -> None:
            await asyncio.sleep(0.01)
            results.append("quick_done")

        await asyncio.gather(run_command(), quick_task())

        # quick_task should complete before run_command
        assert results[0] == "quick_done"
        assert results[1] == "command_done"


class TestAsyncTaskGroup:
    """Tests for AsyncTaskGroup structured concurrency helper."""

    @pytest.mark.asyncio
    async def test_async_task_group_basic(self) -> None:
        """Test basic AsyncTaskGroup usage."""
        from backend.core.async_utils import AsyncTaskGroup

        results: list[int] = []

        async with AsyncTaskGroup() as tg:
            tg.create_task(self._append_after_delay(results, 1, 0.01))
            tg.create_task(self._append_after_delay(results, 2, 0.02))

        # Both tasks should complete
        assert sorted(results) == [1, 2]

    @pytest.mark.asyncio
    async def test_async_task_group_cancellation_on_error(self) -> None:
        """Test that AsyncTaskGroup cancels pending tasks on error."""
        from backend.core.async_utils import AsyncTaskGroup

        results: list[str] = []

        async def failing_task() -> None:
            await asyncio.sleep(0.01)
            raise ValueError("Task failed")

        async def slow_task() -> None:
            await asyncio.sleep(1.0)
            results.append("slow_completed")

        with pytest.raises(ExceptionGroup):
            async with AsyncTaskGroup() as tg:
                tg.create_task(failing_task())
                tg.create_task(slow_task())

        # Slow task should be cancelled
        assert "slow_completed" not in results

    @pytest.mark.asyncio
    async def test_async_task_group_empty(self) -> None:
        """Test that empty AsyncTaskGroup works correctly."""
        from backend.core.async_utils import AsyncTaskGroup

        async with AsyncTaskGroup():
            pass  # No tasks created

        # Should complete without error

    @pytest.mark.asyncio
    async def test_async_task_group_preserves_results(self) -> None:
        """Test that task results can be collected via shared state."""
        from backend.core.async_utils import AsyncTaskGroup

        results: dict[str, int] = {}

        async def compute(name: str, value: int) -> None:
            await asyncio.sleep(0.01)
            results[name] = value * 2

        async with AsyncTaskGroup() as tg:
            tg.create_task(compute("a", 5))
            tg.create_task(compute("b", 10))

        assert results == {"a": 10, "b": 20}

    async def _append_after_delay(self, results: list[int], value: int, delay: float) -> None:
        """Helper: Append value to list after delay."""
        await asyncio.sleep(delay)
        results.append(value)


class TestConcurrencyLimit:
    """Tests for concurrency limiting utilities."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Test that Semaphore properly limits concurrent operations."""
        from backend.core.async_utils import bounded_gather

        concurrent_count = 0
        max_concurrent = 0
        semaphore_limit = 2

        async def tracked_operation(n: int) -> int:
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.02)
            concurrent_count -= 1
            return n * 2

        # Run 5 operations with limit of 2
        results = await bounded_gather(
            [tracked_operation(i) for i in range(5)],
            limit=semaphore_limit,
        )

        assert results == [0, 2, 4, 6, 8]
        assert max_concurrent <= semaphore_limit

    @pytest.mark.asyncio
    async def test_bounded_gather_preserves_order(self) -> None:
        """Test that bounded_gather preserves result order."""
        from backend.core.async_utils import bounded_gather

        async def delayed_return(value: int, delay: float) -> int:
            await asyncio.sleep(delay)
            return value

        # Different delays but results should be in order
        results = await bounded_gather(
            [
                delayed_return(1, 0.03),
                delayed_return(2, 0.01),
                delayed_return(3, 0.02),
            ],
            limit=3,
        )

        assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_bounded_gather_handles_exceptions(self) -> None:
        """Test that bounded_gather propagates exceptions."""
        from backend.core.async_utils import bounded_gather

        async def failing_operation() -> int:
            raise ValueError("Operation failed")

        async def succeeding_operation() -> int:
            return 42

        with pytest.raises(ValueError, match="Operation failed"):
            await bounded_gather(
                [succeeding_operation(), failing_operation()],
                limit=2,
            )


class TestAsyncReadFile:
    """Tests for async file reading utilities."""

    @pytest.mark.asyncio
    async def test_async_read_bytes(self, tmp_path: Path) -> None:
        """Test reading file bytes asynchronously."""
        from backend.core.async_utils import async_read_bytes

        test_file = tmp_path / "test.bin"
        content = b"Hello, World!"
        test_file.write_bytes(content)

        result = await async_read_bytes(str(test_file))

        assert result == content

    @pytest.mark.asyncio
    async def test_async_read_bytes_nonexistent(self) -> None:
        """Test reading nonexistent file returns None."""
        from backend.core.async_utils import async_read_bytes

        result = await async_read_bytes("/nonexistent/file.bin")

        assert result is None

    @pytest.mark.asyncio
    async def test_async_read_text(self, tmp_path: Path) -> None:
        """Test reading file text asynchronously."""
        from backend.core.async_utils import async_read_text

        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content)

        result = await async_read_text(str(test_file))

        assert result == content

    @pytest.mark.asyncio
    async def test_async_read_text_with_encoding(self, tmp_path: Path) -> None:
        """Test reading file text with specific encoding."""
        from backend.core.async_utils import async_read_text

        test_file = tmp_path / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content, encoding="utf-8")

        result = await async_read_text(str(test_file), encoding="utf-8")

        assert result == content


class TestAsyncWriteFile:
    """Tests for async file writing utilities."""

    @pytest.mark.asyncio
    async def test_async_write_bytes(self, tmp_path: Path) -> None:
        """Test writing bytes to file asynchronously."""
        from backend.core.async_utils import async_write_bytes

        test_file = tmp_path / "output.bin"
        content = b"Test content"

        result = await async_write_bytes(str(test_file), content)

        assert result is True
        assert test_file.read_bytes() == content

    @pytest.mark.asyncio
    async def test_async_write_text(self, tmp_path: Path) -> None:
        """Test writing text to file asynchronously."""
        from backend.core.async_utils import async_write_text

        test_file = tmp_path / "output.txt"
        content = "Test content"

        result = await async_write_text(str(test_file), content)

        assert result is True
        assert test_file.read_text() == content
