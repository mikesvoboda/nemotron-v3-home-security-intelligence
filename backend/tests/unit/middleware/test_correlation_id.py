"""Tests for correlation ID middleware and propagation (NEM-1472).

This module tests:
- Correlation ID generation and extraction from X-Correlation-ID header
- Context variable storage for thread-safe access
- Propagation to outgoing HTTP requests
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.logging import set_request_id
from backend.main import app


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
    async def test_correlation_id_available_in_context(self) -> None:
        """Verify correlation ID is available via get_request_id() during request."""
        from unittest.mock import patch

        from backend.core.config import Settings

        # This is tested implicitly by the middleware setting request_id
        # We can verify by checking the debug endpoint response
        test_correlation_id = "context-test-456"

        # Enable debug mode for this test (required for debug endpoints)
        mock_settings = Settings(debug=True, database_url="postgresql+asyncpg://test")
        with patch("backend.api.routes.debug.get_settings", return_value=mock_settings):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/debug/pipeline-state",
                    headers={"X-Correlation-ID": test_correlation_id},
                )

        assert response.status_code == 200
        data = response.json()
        assert data.get("correlation_id") == test_correlation_id


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
