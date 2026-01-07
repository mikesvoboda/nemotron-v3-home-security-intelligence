"""Unit tests for async testing utilities module.

These tests verify that the async testing helpers work correctly
and can be used to simplify other tests.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.tests.async_utils import (
    AsyncClientMock,
    AsyncTimeoutError,
    async_timeout,
    create_async_mock_client,
    create_async_session_mock,
    create_mock_db_context,
    create_mock_redis_client,
    create_mock_response,
    mock_async_context_manager,
    run_concurrent_tasks,
    simulate_concurrent_requests,
    with_timeout,
)

# Mark all tests as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# mock_async_context_manager Tests
# =============================================================================


class TestMockAsyncContextManager:
    """Tests for mock_async_context_manager helper."""

    @pytest.mark.asyncio
    async def test_yields_return_value(self) -> None:
        """Test that the context manager yields the specified return value."""
        expected = MagicMock(name="test_value")
        async with mock_async_context_manager(return_value=expected) as value:
            assert value is expected

    @pytest.mark.asyncio
    async def test_yields_mock_when_no_return_value(self) -> None:
        """Test that a MagicMock is yielded when no return_value is specified."""
        async with mock_async_context_manager() as value:
            assert isinstance(value, MagicMock)

    @pytest.mark.asyncio
    async def test_raises_enter_side_effect(self) -> None:
        """Test that enter_side_effect raises on entry."""
        with pytest.raises(ValueError, match="entry error"):
            async with mock_async_context_manager(enter_side_effect=ValueError("entry error")):
                pass

    @pytest.mark.asyncio
    async def test_raises_exit_side_effect(self) -> None:
        """Test that exit_side_effect raises on exit."""
        with pytest.raises(RuntimeError, match="exit error"):
            async with mock_async_context_manager(exit_side_effect=RuntimeError("exit error")):
                pass


# =============================================================================
# AsyncClientMock Tests
# =============================================================================


class TestAsyncClientMock:
    """Tests for AsyncClientMock helper."""

    @pytest.mark.asyncio
    async def test_get_request_returns_configured_response(self) -> None:
        """Test GET request returns configured response data."""
        mock = AsyncClientMock(
            get_responses={"/health": {"status": "healthy"}},
        )

        async with mock.client() as client:
            response = await client.get("/health")

        assert response.json() == {"status": "healthy"}
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_post_request_returns_configured_response(self) -> None:
        """Test POST request returns configured response data."""
        mock = AsyncClientMock(
            post_responses={"/detect": {"detections": ["person", "car"]}},
        )

        async with mock.client() as client:
            response = await client.post("/detect", json={"image": "base64data"})

        assert response.json() == {"detections": ["person", "car"]}

    @pytest.mark.asyncio
    async def test_tracks_calls(self) -> None:
        """Test that calls are tracked for verification."""
        mock = AsyncClientMock(
            get_responses={"/api/test": {"result": "ok"}},
        )

        async with mock.client() as client:
            await client.get("/api/test", params={"id": 123})

        assert len(mock.calls) == 1
        method, url, kwargs = mock.calls[0]
        assert method == "GET"
        assert "/api/test" in url
        assert kwargs["params"] == {"id": 123}

    @pytest.mark.asyncio
    async def test_raises_exception_when_configured(self) -> None:
        """Test that configured exceptions are raised."""
        import httpx

        mock = AsyncClientMock(
            get_responses={"/health": httpx.ConnectError("Connection refused")},
        )

        async with mock.client() as client:
            with pytest.raises(httpx.ConnectError):
                await client.get("/health")

    @pytest.mark.asyncio
    async def test_returns_empty_dict_for_unknown_url(self) -> None:
        """Test that unknown URLs return empty dict by default."""
        mock = AsyncClientMock()

        async with mock.client() as client:
            response = await client.get("/unknown/url")

        assert response.json() == {}

    @pytest.mark.asyncio
    async def test_raises_on_missing_when_configured(self) -> None:
        """Test raise_on_missing option."""
        mock = AsyncClientMock(raise_on_missing=True)

        async with mock.client() as client:
            with pytest.raises(KeyError, match="No mock response"):
                await client.get("/unknown")

    @pytest.mark.asyncio
    async def test_custom_status_code(self) -> None:
        """Test custom default status code."""
        mock = AsyncClientMock(
            get_responses={"/error": {"error": "not found"}},
            default_status_code=404,
        )

        async with mock.client() as client:
            response = await client.get("/error")

        assert response.status_code == 404


class TestCreateAsyncMockClient:
    """Tests for create_async_mock_client factory function."""

    @pytest.mark.asyncio
    async def test_creates_configured_mock(self) -> None:
        """Test factory creates properly configured mock."""
        mock = create_async_mock_client(
            get_responses={"/health": {"status": "ok"}},
            post_responses={"/api": {"result": True}},
        )

        async with mock.client() as client:
            get_response = await client.get("/health")
            post_response = await client.post("/api")

        assert get_response.json() == {"status": "ok"}
        assert post_response.json() == {"result": True}


# =============================================================================
# create_async_session_mock Tests
# =============================================================================


class TestCreateAsyncSessionMock:
    """Tests for create_async_session_mock helper."""

    @pytest.mark.asyncio
    async def test_execute_returns_results_in_sequence(self) -> None:
        """Test that execute() returns results in sequence."""
        result1 = MagicMock(name="result1")
        result2 = MagicMock(name="result2")

        mock_session = create_async_session_mock(
            execute_results=[result1, result2],
        )

        first = await mock_session.execute("query1")
        second = await mock_session.execute("query2")

        assert first is result1
        assert second is result2

    @pytest.mark.asyncio
    async def test_has_common_session_methods(self) -> None:
        """Test that common session methods are available."""
        mock_session = create_async_session_mock()

        # Verify all common methods exist and are callable
        mock_session.add(MagicMock())
        await mock_session.commit()
        await mock_session.rollback()
        await mock_session.refresh(MagicMock())
        await mock_session.close()
        await mock_session.flush()

        # No assertions needed - just verify they don't raise


class TestCreateMockDbContext:
    """Tests for create_mock_db_context helper."""

    @pytest.mark.asyncio
    async def test_yields_session(self) -> None:
        """Test that context yields the provided session."""
        mock_session = create_async_session_mock()
        mock_context = create_mock_db_context(mock_session)

        async with mock_context as session:
            assert session is mock_session


# =============================================================================
# Timeout Utilities Tests
# =============================================================================


class TestAsyncTimeout:
    """Tests for async_timeout context manager."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self) -> None:
        """Test that operations completing within timeout succeed."""
        async with async_timeout(1.0):
            await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self) -> None:
        """Test that timeout raises AsyncTimeoutError."""
        with pytest.raises(AsyncTimeoutError) as exc_info:
            async with async_timeout(0.01, operation="test operation"):
                await asyncio.sleep(1.0)  # cancelled by timeout context manager

        assert exc_info.value.timeout == 0.01
        assert exc_info.value.operation == "test operation"
        assert "test operation timed out" in str(exc_info.value)


class TestWithTimeout:
    """Tests for with_timeout function."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self) -> None:
        """Test that successful coroutines return their result."""

        async def quick_operation() -> str:
            return "success"

        result = await with_timeout(quick_operation(), timeout=1.0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_raises_on_timeout(self) -> None:
        """Test that slow operations raise AsyncTimeoutError."""

        async def slow_operation() -> str:
            await asyncio.sleep(10.0)
            return "never"

        with pytest.raises(AsyncTimeoutError):
            await with_timeout(slow_operation(), timeout=0.01)


# =============================================================================
# Concurrent Testing Utilities Tests
# =============================================================================


class TestRunConcurrentTasks:
    """Tests for run_concurrent_tasks helper."""

    @pytest.mark.asyncio
    async def test_runs_tasks_concurrently(self) -> None:
        """Test that tasks run concurrently."""
        call_times: list[float] = []

        async def track_time(delay: float) -> float:
            import time

            start = time.monotonic()
            await asyncio.sleep(delay)
            call_times.append(time.monotonic() - start)
            return delay

        # Run 3 tasks with 0.01s each - should complete in ~0.01s total, not 0.03s
        result = await run_concurrent_tasks(
            track_time(0.01),
            track_time(0.01),
            track_time(0.01),
        )

        assert result.all_succeeded
        assert result.success_count == 3
        # Total duration should be close to the longest task, not sum of all
        assert result.duration_seconds < 0.1  # Generous margin for test flakiness

    @pytest.mark.asyncio
    async def test_collects_exceptions(self) -> None:
        """Test that exceptions are collected when return_exceptions=True."""

        async def failing_task() -> str:
            raise ValueError("task failed")

        async def passing_task() -> str:
            return "success"

        result = await run_concurrent_tasks(
            passing_task(),
            failing_task(),
            passing_task(),
        )

        assert not result.all_succeeded
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], ValueError)


class TestSimulateConcurrentRequests:
    """Tests for simulate_concurrent_requests helper."""

    @pytest.mark.asyncio
    async def test_makes_correct_number_of_requests(self) -> None:
        """Test that the correct number of requests are made."""
        call_count = 0

        async def make_request() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        result = await simulate_concurrent_requests(
            make_request,
            count=5,
        )

        assert call_count == 5
        assert len(result.results) == 5


# =============================================================================
# Mock Response Tests
# =============================================================================


class TestCreateMockResponse:
    """Tests for create_mock_response helper."""

    def test_creates_response_with_json_data(self) -> None:
        """Test creating response with JSON data."""
        response = create_mock_response(
            json_data={"key": "value"},
            status_code=201,
        )

        assert response.json() == {"key": "value"}
        assert response.status_code == 201

    def test_raises_on_raise_for_status_when_configured(self) -> None:
        """Test that raise_for_status raises when configured."""
        import httpx

        error = httpx.HTTPStatusError(
            "Server error",
            request=MagicMock(),
            response=MagicMock(),
        )
        response = create_mock_response(raise_for_status_error=error)

        with pytest.raises(httpx.HTTPStatusError):
            response.raise_for_status()


# =============================================================================
# Redis Mock Tests
# =============================================================================


class TestCreateMockRedisClient:
    """Tests for create_mock_redis_client helper."""

    @pytest.mark.asyncio
    async def test_get_returns_configured_values(self) -> None:
        """Test that get() returns configured values."""
        mock = create_mock_redis_client(
            get_values={
                "key1": "value1",
                "key2": {"nested": "data"},
            }
        )

        result1 = await mock.get("key1")
        result2 = await mock.get("key2")
        result3 = await mock.get("nonexistent")

        assert result1 == "value1"
        assert result2 == {"nested": "data"}
        assert result3 is None

    @pytest.mark.asyncio
    async def test_has_common_redis_methods(self) -> None:
        """Test that common Redis methods are available."""
        mock = create_mock_redis_client()

        # All should return without error
        await mock.set("key", "value")
        await mock.delete("key")
        await mock.publish("channel", "message")
        health = await mock.health_check()

        assert health["status"] == "healthy"


# =============================================================================
# Integration Tests (using the utilities)
# =============================================================================


class TestUtilitiesIntegration:
    """Integration tests demonstrating real-world usage of async utilities."""

    @pytest.mark.asyncio
    async def test_mock_http_client_with_database(self) -> None:
        """Test combining HTTP client mock with database session mock."""
        # Setup HTTP client mock
        http_mock = AsyncClientMock(
            get_responses={"/api/data": {"items": [1, 2, 3]}},
        )

        # Setup database session mock
        db_result = MagicMock()
        db_result.scalars.return_value.all.return_value = ["row1", "row2"]
        db_session = create_async_session_mock(execute_results=[db_result])
        db_context = create_mock_db_context(db_session)

        # Use both in a test scenario
        async with http_mock.client() as client:
            api_response = await client.get("/api/data")

        async with db_context as session:
            db_result = await session.execute("SELECT * FROM table")
            rows = db_result.scalars().all()

        assert api_response.json() == {"items": [1, 2, 3]}
        assert rows == ["row1", "row2"]

    @pytest.mark.asyncio
    async def test_concurrent_requests_with_timeout(self) -> None:
        """Test combining concurrent requests with timeout protection."""

        async def slow_request(delay: float) -> str:
            await asyncio.sleep(delay)
            return f"completed after {delay}s"

        # Run with generous timeout
        async with async_timeout(5.0, operation="concurrent requests"):
            result = await run_concurrent_tasks(
                slow_request(0.01),
                slow_request(0.02),
                slow_request(0.01),
            )

        assert result.all_succeeded
        assert len(result.results) == 3
