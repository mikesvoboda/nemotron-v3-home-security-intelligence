"""Unit tests for TaskGroup-based concurrent operations (NEM-1656).

These tests verify the modern Python 3.11+ TaskGroup and ExceptionGroup patterns
for safer concurrent task handling with automatic cancellation and structured
concurrency.
"""

import asyncio

import pytest


# Test basic TaskGroup functionality
class TestTaskGroupBasics:
    """Tests for basic TaskGroup functionality."""

    @pytest.mark.asyncio
    async def test_taskgroup_runs_tasks_concurrently(self):
        """Test that TaskGroup runs multiple tasks concurrently."""
        results = []
        start_time = asyncio.get_event_loop().time()

        async def task1():
            await asyncio.sleep(0.05)
            results.append("task1")

        async def task2():
            await asyncio.sleep(0.05)
            results.append("task2")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(task1())
            tg.create_task(task2())

        elapsed = asyncio.get_event_loop().time() - start_time

        # Both tasks should complete
        assert len(results) == 2
        assert "task1" in results
        assert "task2" in results
        # Should run concurrently (< 0.1s if sequential would be > 0.1s)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_taskgroup_automatic_cancellation_on_failure(self):
        """Test that TaskGroup cancels remaining tasks when one fails."""
        cancelled = []
        completed = []

        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Task failed")

        async def long_task():
            try:
                await asyncio.sleep(1.0)  # cancelled - TaskGroup cancels on first failure
                completed.append("long_task")
            except asyncio.CancelledError:
                cancelled.append("long_task")
                raise

        with pytest.raises(ExceptionGroup) as exc_info:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(failing_task())
                tg.create_task(long_task())

        # The long task should have been cancelled
        assert "long_task" in cancelled
        assert "long_task" not in completed

        # Exception group should contain the ValueError
        eg = exc_info.value
        assert len(eg.exceptions) == 1
        assert isinstance(eg.exceptions[0], ValueError)

    @pytest.mark.asyncio
    async def test_taskgroup_collects_all_exceptions(self):
        """Test that TaskGroup collects all exceptions from multiple failing tasks."""

        async def fail_with_value():
            await asyncio.sleep(0.01)
            raise ValueError("Value error")

        async def fail_with_type():
            await asyncio.sleep(0.02)
            raise TypeError("Type error")

        with pytest.raises(ExceptionGroup) as exc_info:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fail_with_value())
                tg.create_task(fail_with_type())

        eg = exc_info.value
        # At least one exception should be collected
        # (the second may or may not complete before cancellation)
        assert len(eg.exceptions) >= 1

        # Check exception types
        exc_types = [type(e) for e in eg.exceptions]
        assert ValueError in exc_types


class TestExceptionGroupHandling:
    """Tests for ExceptionGroup handling patterns."""

    @pytest.mark.asyncio
    async def test_except_star_catches_specific_exceptions(self):
        """Test except* syntax for catching specific exception types."""

        async def fail_with_value():
            raise ValueError("Value error")

        async def fail_with_runtime():
            raise RuntimeError("Runtime error")

        value_errors = []
        runtime_errors = []

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fail_with_value())
                tg.create_task(fail_with_runtime())
        except* ValueError as eg:
            value_errors.extend(eg.exceptions)
        except* RuntimeError as eg:
            runtime_errors.extend(eg.exceptions)

        assert len(value_errors) == 1
        assert len(runtime_errors) == 1

    @pytest.mark.asyncio
    async def test_exception_group_filtering(self):
        """Test filtering exceptions from an ExceptionGroup."""

        async def fail_with_value(msg):
            raise ValueError(msg)

        async def fail_with_type(msg):
            raise TypeError(msg)

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(fail_with_value("val1"))
                tg.create_task(fail_with_type("type1"))
        except ExceptionGroup as eg:
            # Split by type
            value_eg, rest = eg.split(ValueError)
            type_eg, _other = rest.split(TypeError) if rest else (None, None)

            assert value_eg is not None
            assert len(value_eg.exceptions) == 1
            assert str(value_eg.exceptions[0]) == "val1"

            if type_eg:
                assert len(type_eg.exceptions) == 1


class TestTaskGroupVsGather:
    """Tests comparing TaskGroup vs asyncio.gather behavior."""

    @pytest.mark.asyncio
    async def test_gather_with_return_exceptions_continues_on_failure(self):
        """Test that gather with return_exceptions=True continues on failure."""
        completed = []

        async def failing_task():
            raise ValueError("Failed")

        async def successful_task():
            await asyncio.sleep(0.01)
            completed.append("success")
            return "done"

        results = await asyncio.gather(
            failing_task(),
            successful_task(),
            return_exceptions=True,
        )

        # Both tasks run to completion
        assert "success" in completed
        # Results include exception and return value
        assert isinstance(results[0], ValueError)
        assert results[1] == "done"

    @pytest.mark.asyncio
    async def test_taskgroup_cancels_on_first_failure(self):
        """Test that TaskGroup cancels other tasks on first failure."""
        completed = []

        async def failing_task():
            raise ValueError("Failed")

        async def slow_task():
            await asyncio.sleep(0.1)
            completed.append("success")
            return "done"

        with pytest.raises(ExceptionGroup):
            async with asyncio.TaskGroup() as tg:
                tg.create_task(failing_task())
                tg.create_task(slow_task())

        # The slow task should be cancelled
        assert "success" not in completed


class TestTaskGroupPatterns:
    """Tests for common TaskGroup usage patterns."""

    @pytest.mark.asyncio
    async def test_taskgroup_result_collection(self):
        """Test pattern for collecting results from TaskGroup tasks."""
        results = {}

        async def fetch_data(key: str, value: str):
            await asyncio.sleep(0.01)
            results[key] = value

        async with asyncio.TaskGroup() as tg:
            tg.create_task(fetch_data("a", "value_a"))
            tg.create_task(fetch_data("b", "value_b"))
            tg.create_task(fetch_data("c", "value_c"))

        assert results == {"a": "value_a", "b": "value_b", "c": "value_c"}

    @pytest.mark.asyncio
    async def test_taskgroup_with_timeout(self):
        """Test TaskGroup combined with asyncio.timeout."""

        async def slow_task():
            await asyncio.sleep(10.0)
            return "done"

        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.05):
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(slow_task())
                    tg.create_task(slow_task())

    @pytest.mark.asyncio
    async def test_taskgroup_nested(self):
        """Test nested TaskGroups."""
        results = []

        async def inner_task(name: str):
            await asyncio.sleep(0.01)
            results.append(f"inner_{name}")

        async def outer_task(group_name: str):
            async with asyncio.TaskGroup() as inner_tg:
                inner_tg.create_task(inner_task(f"{group_name}_1"))
                inner_tg.create_task(inner_task(f"{group_name}_2"))
            results.append(f"outer_{group_name}")

        async with asyncio.TaskGroup() as outer_tg:
            outer_tg.create_task(outer_task("A"))
            outer_tg.create_task(outer_task("B"))

        # All inner and outer tasks should complete
        assert len(results) == 6
        assert "outer_A" in results
        assert "outer_B" in results

    @pytest.mark.asyncio
    async def test_taskgroup_graceful_error_handling(self):
        """Test graceful error handling with TaskGroup and logging."""
        errors = []

        async def maybe_fail(should_fail: bool, name: str):
            if should_fail:
                raise ValueError(f"Task {name} failed")
            await asyncio.sleep(0.01)
            return f"success_{name}"

        try:
            async with asyncio.TaskGroup() as tg:
                # Create tasks that mix success and failure
                tg.create_task(maybe_fail(False, "task1"))
                tg.create_task(maybe_fail(True, "task2"))
        except* ValueError as eg:
            for exc in eg.exceptions:
                errors.append(str(exc))

        assert len(errors) == 1
        assert "task2 failed" in errors[0]


class TestBatchAggregatorTaskGroupPatterns:
    """Tests specific to BatchAggregator TaskGroup usage patterns."""

    @pytest.mark.asyncio
    async def test_parallel_redis_operations_all_succeed(self):
        """Test pattern for parallel Redis operations - all succeed case."""
        results = {}

        async def redis_set(key: str, value: str):
            await asyncio.sleep(0.01)
            results[key] = value
            return True

        async with asyncio.TaskGroup() as tg:
            tg.create_task(redis_set("key1", "value1"))
            tg.create_task(redis_set("key2", "value2"))
            tg.create_task(redis_set("key3", "value3"))

        # All operations should complete
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_parallel_redis_operations_one_fails(self):
        """Test pattern for parallel Redis operations - one fails case."""

        async def redis_set_success(key: str):
            await asyncio.sleep(0.01)
            return True

        async def redis_set_failure():
            await asyncio.sleep(0.01)
            raise ConnectionError("Redis connection lost")

        with pytest.raises(ExceptionGroup) as exc_info:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(redis_set_success("key1"))
                tg.create_task(redis_set_failure())
                tg.create_task(redis_set_success("key3"))

        # Should contain the ConnectionError
        assert any(isinstance(e, ConnectionError) for e in exc_info.value.exceptions)

    @pytest.mark.asyncio
    async def test_batch_close_parallel_fetch_pattern(self):
        """Test pattern for fetching batch data in parallel."""

        async def fetch_detections():
            await asyncio.sleep(0.01)
            return [1, 2, 3]

        async def fetch_started_at():
            await asyncio.sleep(0.01)
            return "1735123456.789"

        async def fetch_pipeline_start_time():
            await asyncio.sleep(0.01)
            return "2025-12-25T10:00:00.000000"

        detections = None
        started_at = None
        pipeline_start_time = None

        async def capture_detections():
            nonlocal detections
            detections = await fetch_detections()

        async def capture_started_at():
            nonlocal started_at
            started_at = await fetch_started_at()

        async def capture_pipeline_time():
            nonlocal pipeline_start_time
            pipeline_start_time = await fetch_pipeline_start_time()

        async with asyncio.TaskGroup() as tg:
            tg.create_task(capture_detections())
            tg.create_task(capture_started_at())
            tg.create_task(capture_pipeline_time())

        assert detections == [1, 2, 3]
        assert started_at == "1735123456.789"
        assert pipeline_start_time == "2025-12-25T10:00:00.000000"


class TestSystemBroadcasterTaskGroupPatterns:
    """Tests specific to SystemBroadcaster TaskGroup usage patterns."""

    @pytest.mark.asyncio
    async def test_health_check_parallel_pattern(self):
        """Test pattern for parallel health checks that collect partial results."""
        yolo26_healthy = False
        nemotron_healthy = False

        async def check_yolo26():
            nonlocal yolo26_healthy
            await asyncio.sleep(0.01)
            yolo26_healthy = True

        async def check_nemotron():
            nonlocal nemotron_healthy
            await asyncio.sleep(0.01)
            nemotron_healthy = True

        async with asyncio.TaskGroup() as tg:
            tg.create_task(check_yolo26())
            tg.create_task(check_nemotron())

        assert yolo26_healthy is True
        assert nemotron_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_partial_failure_pattern(self):
        """Test health check pattern where one service fails.

        For health checks, we want to collect partial results even if one
        service fails. This requires using gather with return_exceptions=True
        OR handling the ExceptionGroup and continuing.
        """
        yolo26_healthy = False

        async def check_yolo26():
            nonlocal yolo26_healthy
            await asyncio.sleep(0.01)
            yolo26_healthy = True
            return True

        async def check_nemotron_failing():
            await asyncio.sleep(0.01)
            raise ConnectionError("Nemotron unavailable")

        # For health checks, gather with return_exceptions is still appropriate
        # because we want partial results even when some checks fail
        results = await asyncio.gather(
            check_yolo26(),
            check_nemotron_failing(),
            return_exceptions=True,
        )

        # yolo26 check succeeded
        assert yolo26_healthy is True
        assert results[0] is True
        # nemotron check failed
        assert isinstance(results[1], ConnectionError)

    @pytest.mark.asyncio
    async def test_health_check_with_taskgroup_and_exception_handling(self):
        """Test health check using TaskGroup with exception handling for partial results."""
        results = {"yolo26": False, "nemotron": False}

        async def check_yolo26():
            await asyncio.sleep(0.01)
            results["yolo26"] = True

        async def check_nemotron():
            await asyncio.sleep(0.01)
            # This one fails
            raise ConnectionError("Nemotron unavailable")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(check_yolo26())
                tg.create_task(check_nemotron())
        except* ConnectionError:
            # Handle the connection error but results already updated
            pass

        # Note: With TaskGroup, yolo26 may or may not have completed before
        # the exception was raised. This is why gather with return_exceptions
        # is often better for health checks where partial results are desired.


class TestMixedPatterns:
    """Tests for deciding when to use TaskGroup vs gather."""

    @pytest.mark.asyncio
    async def test_use_taskgroup_for_dependent_operations(self):
        """TaskGroup is better when all operations must succeed together.

        Example: Creating batch metadata - if any SET fails, the batch is invalid.
        """
        batch_valid = False

        async def create_batch_metadata():
            nonlocal batch_valid

            async def set_current():
                await asyncio.sleep(0.01)
                return True

            async def set_camera_id():
                await asyncio.sleep(0.01)
                return True

            async def set_started_at():
                await asyncio.sleep(0.01)
                return True

            # All must succeed for batch to be valid
            async with asyncio.TaskGroup() as tg:
                tg.create_task(set_current())
                tg.create_task(set_camera_id())
                tg.create_task(set_started_at())

            batch_valid = True

        await create_batch_metadata()
        assert batch_valid is True

    @pytest.mark.asyncio
    async def test_use_gather_for_independent_results(self):
        """gather with return_exceptions is better when we want all results.

        Example: Health checks - we want to know the status of each service
        even if some fail.
        """

        async def check_service_a():
            await asyncio.sleep(0.01)
            return "healthy"

        async def check_service_b():
            await asyncio.sleep(0.01)
            raise ConnectionError("Service B unavailable")

        async def check_service_c():
            await asyncio.sleep(0.01)
            return "healthy"

        results = await asyncio.gather(
            check_service_a(),
            check_service_b(),
            check_service_c(),
            return_exceptions=True,
        )

        # We have results for all services
        assert results[0] == "healthy"
        assert isinstance(results[1], ConnectionError)
        assert results[2] == "healthy"
