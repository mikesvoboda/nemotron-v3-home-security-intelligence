"""Tests for correlation ID middleware and propagation (NEM-1472).

This module tests:
- Correlation ID generation and extraction from X-Correlation-ID header
- Context variable storage for thread-safe access
- Propagation to outgoing HTTP requests
"""

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core import redis as redis_module
from backend.core.logging import set_request_id
from backend.main import app


async def _no_redis_dependency():
    """``get_redis_optional`` replacement that yields the degraded client.

    Same shape as ``backend/tests/unit/api/routes/test_debug_api.py``'s
    ``_mock_redis_none``: every other test of ``/api/debug/pipeline-state``
    already answers the dependency this way.
    """
    yield None


async def _get_pipeline_state(*, skip_redis: bool) -> tuple[int, dict]:
    """Drive ``GET /api/debug/pipeline-state`` once with a correlation ID.

    Shared by the propagation test and the two connection pins below so the
    pins audit the very request the subject test makes, not a copy of it.
    ``skip_redis=False`` keeps the real ``get_redis_optional`` dependency,
    which is the cold-start path that cost this test 3.3 s.
    """
    from unittest.mock import AsyncMock, patch

    from backend.core.config import Settings, get_settings
    from backend.tests.unit.conftest import UNIT_TEST_API_KEY

    test_correlation_id = "context-test-456"

    # Ensure API key auth is enabled and settings cache is cleared
    os.environ["API_KEY_ENABLED"] = "true"  # pragma: allowlist secret
    os.environ["API_KEYS"] = f'["{UNIT_TEST_API_KEY}"]'  # pragma: allowlist secret
    get_settings.cache_clear()

    # Enable debug mode for this test (required for debug endpoints)
    mock_settings = Settings(debug=True, database_url="postgresql+asyncpg://test")

    # Mock setup guard to return True (setup complete)
    mock_check_setup = AsyncMock(return_value=True)

    if skip_redis:
        app.dependency_overrides[redis_module.get_redis_optional] = _no_redis_dependency

    try:
        with (
            patch(
                "backend.api.routes.debug.get_settings", return_value=mock_settings, autospec=True
            ),
            patch(
                "backend.api.middleware.setup_guard.SetupGuardMiddleware._check_setup_complete",
                mock_check_setup,
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"X-API-Key": UNIT_TEST_API_KEY},
            ) as client:
                response = await client.get(
                    "/api/debug/pipeline-state",
                    headers={"X-Correlation-ID": test_correlation_id},
                )
        return response.status_code, response.json()
    finally:
        if skip_redis:
            app.dependency_overrides.pop(redis_module.get_redis_optional, None)


@pytest.fixture
def redis_connect_sentinel(monkeypatch):
    """List of ``RedisClient.connect()`` calls made during the test.

    Forces the cold path (``_redis_client`` is a module global a previous
    test may have filled, which would make a zero-count assertion vacuous)
    and zeroes connect's backoff so a surviving live attempt costs
    milliseconds instead of the 1 s + 2 s the real path sleeps — the same
    zeroing commit ``99394f95d`` applied to the ``get_redis_optional``
    failure tests.
    """
    calls: list[str] = []
    real_connect = redis_module.RedisClient.connect

    async def counting_connect(self):
        calls.append(self._redis_url)
        return await real_connect(self)

    monkeypatch.setattr(redis_module.RedisClient, "connect", counting_connect)
    # Underscore-prefixed args are required by the call site's signature, not used.
    monkeypatch.setattr(
        redis_module.RedisClient,
        "_calculate_backoff_delay",
        lambda _self, _attempt: 0.0,
    )
    monkeypatch.setattr(redis_module, "_redis_client", None, raising=True)
    return calls


class TestCorrelationIdMiddleware:
    """Tests for correlation ID middleware."""

    @pytest.mark.asyncio
    async def test_middleware_generates_correlation_id_when_not_provided(self) -> None:
        """Verify middleware generates a correlation ID when not in headers."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")

        # Response should have a correlation ID header
        assert "X-Correlation-ID" in response.headers
        # Should be a valid UUID format
        correlation_id = response.headers["X-Correlation-ID"]
        # Should be a non-empty string that looks like a UUID
        assert len(correlation_id) > 0
        try:
            uuid.UUID(correlation_id)
        except ValueError:
            pytest.fail(f"Invalid UUID format: {correlation_id}")

    @pytest.mark.asyncio
    async def test_middleware_preserves_existing_correlation_id(self) -> None:
        """Verify middleware preserves correlation ID from request headers."""
        test_correlation_id = "test-correlation-123"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/",
                headers={"X-Correlation-ID": test_correlation_id},
            )

        # Response should echo back the same correlation ID
        assert response.headers.get("X-Correlation-ID") == test_correlation_id

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_correlation_id_available_in_context(self) -> None:
        """Verify correlation ID is available via get_request_id() during request."""
        # This is tested implicitly by the middleware setting request_id
        # We can verify by checking the debug endpoint response
        status_code, data = await _get_pipeline_state(skip_redis=True)

        assert status_code == 200
        assert data.get("correlation_id") == "context-test-456"

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_pipeline_state_propagation_never_opens_a_redis_connection(
        self, redis_connect_sentinel
    ) -> None:
        """[r122]: the degraded-Redis path must be cheap, for the right reason.

        This request answers a correlation-ID question, but its route resolves
        the fail-soft ``get_redis_optional``, which on a machine without a
        reachable Redis drives ``RedisClient.connect()`` through all three
        attempts and sleeps connect's real backoff (1 s, then 2 s, plus
        jitter) before reporting degraded status. That is 3.0-3.75 s per cold
        request, and because a failed connect leaves ``_redis_client`` as
        ``None``, the next request pays it again: 3.322 s measured here against
        0.133 s with a live Redis on the default port, while the sibling
        request to ``/`` on the same app costs 0.302 s. Neither the retry
        schedule nor the degraded status is what this test is about, so the
        dependency is answered the way ``test_debug_api.py`` already answers it
        for every other test of this endpoint.
        """
        status_code, data = await _get_pipeline_state(skip_redis=True)

        assert status_code == 200
        assert data.get("correlation_id") == "context-test-456"
        assert redis_connect_sentinel == [], (
            "a correlation-ID assertion must not pay for a Redis connect; "
            f"connect() was called for: {redis_connect_sentinel}"
        )

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_the_sentinel_sees_a_real_dependency_connection(self, redis_connect_sentinel):
        """The zero above is a measurement, not a blind spot.

        Same fixture, same request, real dependency left in place: the
        sentinel must record the attempt. If this goes quiet, the pin above
        proves nothing and both tests have to be rethought.
        """
        status_code, _data = await _get_pipeline_state(skip_redis=False)

        assert status_code == 200
        assert len(redis_connect_sentinel) == 1, (
            "the un-overridden dependency must reach connect() once, or the "
            "sentinel is blind and the == [] pin above is vacuous"
        )


class TestCorrelationIdPropagation:
    """Tests for correlation ID propagation to outgoing HTTP requests."""

    @pytest.mark.asyncio
    async def test_get_correlation_headers_returns_headers_with_correlation_id(
        self,
    ) -> None:
        """Verify get_correlation_headers includes correlation ID when set."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id

        set_correlation_id("test-prop-789")
        try:
            headers = get_correlation_headers()
            assert headers.get("X-Correlation-ID") == "test-prop-789"
        finally:
            set_correlation_id(None)

    @pytest.mark.asyncio
    async def test_get_correlation_headers_returns_empty_when_no_correlation_id(
        self,
    ) -> None:
        """Verify get_correlation_headers returns empty dict when no ID set."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id

        set_correlation_id(None)
        set_request_id(None)
        headers = get_correlation_headers()
        # Should be empty or have X-Correlation-ID as None/not present
        assert headers.get("X-Correlation-ID") is None

    @pytest.mark.asyncio
    async def test_correlation_id_isolated_between_async_contexts(self) -> None:
        """Verify correlation IDs don't leak between concurrent async tasks."""
        from backend.api.middleware.request_id import (
            get_correlation_id,
            set_correlation_id,
        )

        results: dict[str, str | None] = {}

        async def task_with_correlation_id(name: str, correlation_id: str) -> None:
            set_correlation_id(correlation_id)
            await asyncio.sleep(0.01)  # Simulate async work
            results[name] = get_correlation_id()

        # Run concurrent tasks with different correlation IDs
        await asyncio.gather(
            task_with_correlation_id("task1", "corr-id-1"),
            task_with_correlation_id("task2", "corr-id-2"),
            task_with_correlation_id("task3", "corr-id-3"),
        )

        # Each task should have its own correlation ID
        assert results["task1"] == "corr-id-1"
        assert results["task2"] == "corr-id-2"
        assert results["task3"] == "corr-id-3"


class TestHttpClientCorrelationPropagation:
    """Tests for correlation ID propagation in HTTP client calls."""

    @pytest.mark.asyncio
    async def test_merge_headers_with_correlation_adds_correlation_id(self) -> None:
        """Verify merge_headers_with_correlation adds correlation ID."""
        from backend.api.middleware.correlation import merge_headers_with_correlation
        from backend.api.middleware.request_id import set_correlation_id

        set_correlation_id("merge-test-123")
        try:
            headers = merge_headers_with_correlation({"Content-Type": "application/json"})
            assert headers.get("X-Correlation-ID") == "merge-test-123"
            assert headers.get("Content-Type") == "application/json"
        finally:
            set_correlation_id(None)

    @pytest.mark.asyncio
    async def test_merge_headers_with_correlation_handles_none_input(self) -> None:
        """Verify merge_headers_with_correlation handles None input."""
        from backend.api.middleware.correlation import merge_headers_with_correlation
        from backend.api.middleware.request_id import set_correlation_id

        set_correlation_id("merge-none-456")
        try:
            headers = merge_headers_with_correlation(None)
            assert headers.get("X-Correlation-ID") == "merge-none-456"
        finally:
            set_correlation_id(None)

    @pytest.mark.asyncio
    async def test_get_correlation_headers_includes_request_id(self) -> None:
        """Verify get_correlation_headers includes both correlation and request ID."""
        from backend.api.middleware.correlation import get_correlation_headers
        from backend.api.middleware.request_id import set_correlation_id

        set_request_id("req-789")
        set_correlation_id("corr-789")
        try:
            headers = get_correlation_headers()
            assert headers.get("X-Correlation-ID") == "corr-789"
            assert headers.get("X-Request-ID") == "req-789"
        finally:
            set_request_id(None)
            set_correlation_id(None)
