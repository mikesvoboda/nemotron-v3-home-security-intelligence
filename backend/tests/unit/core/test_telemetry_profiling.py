"""Tests for Pyroscope profiling with trace context correlation.

NEM-4127: Tests for the profile_with_trace_context() context manager that
enables correlation between distributed traces and continuous profiles.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestProfileWithTraceContext:
    """Tests for profile_with_trace_context context manager."""

    def test_profile_with_trace_context_tags_profiling_data(self) -> None:
        """Should tag profiling data with trace_id and span_id when valid trace exists."""
        from backend.core.telemetry import profile_with_trace_context

        # Create mock span context with valid trace
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x0123456789ABCDEF0123456789ABCDEF
        mock_span_context.span_id = 0x0123456789ABCDEF
        mock_span.get_span_context.return_value = mock_span_context

        mock_tag_wrapper = MagicMock()
        mock_tag_wrapper.__enter__ = MagicMock(return_value=None)
        mock_tag_wrapper.__exit__ = MagicMock(return_value=None)

        with (
            patch("opentelemetry.trace.get_current_span", return_value=mock_span, autospec=True),
            patch(
                "pyroscope.tag_wrapper", return_value=mock_tag_wrapper, autospec=True
            ) as mock_pyroscope,
        ):
            with profile_with_trace_context():
                pass

            # Verify pyroscope.tag_wrapper was called with correct tags
            mock_pyroscope.assert_called_once()
            call_args = mock_pyroscope.call_args
            tags = call_args[0][0]
            assert "trace_id" in tags
            assert "span_id" in tags
            assert tags["trace_id"] == "0123456789abcdef0123456789abcdef"
            assert tags["span_id"] == "0123456789abcdef"

    def test_profile_with_trace_context_handles_invalid_trace_context(self) -> None:
        """Should yield without tagging when span context is invalid."""
        from backend.core.telemetry import profile_with_trace_context

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span, autospec=True):
            # Should not raise
            executed = False
            with profile_with_trace_context():
                executed = True

            assert executed is True

    def test_profile_with_trace_context_handles_pyroscope_import_error(self) -> None:
        """Should yield without tagging when pyroscope is not installed."""
        from backend.core.telemetry import profile_with_trace_context

        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 0x0123456789ABCDEF0123456789ABCDEF
        mock_span_context.span_id = 0x0123456789ABCDEF
        mock_span.get_span_context.return_value = mock_span_context

        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pyroscope":
                raise ImportError("pyroscope not installed")
            return original_import(name, *args, **kwargs)

        with (
            patch("opentelemetry.trace.get_current_span", return_value=mock_span, autospec=True),
            patch("builtins.__import__", side_effect=mock_import, autospec=True),
        ):
            # Should not raise
            executed = False
            with profile_with_trace_context():
                executed = True

            assert executed is True

    def test_profile_with_trace_context_handles_otel_import_error(self) -> None:
        """Should yield without tagging when opentelemetry is not installed."""
        import builtins

        from backend.core.telemetry import profile_with_trace_context

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("opentelemetry not installed")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import, autospec=True):
            # Should not raise
            executed = False
            with profile_with_trace_context():
                executed = True

            assert executed is True

    def test_profile_with_trace_context_handles_unexpected_exception(self) -> None:
        """Should yield and log when unexpected exception occurs."""
        from backend.core.telemetry import profile_with_trace_context

        with (
            patch(
                "opentelemetry.trace.get_current_span",
                side_effect=Exception("Unexpected error"),
                autospec=True,
            ),
            patch("backend.core.telemetry.logger", autospec=True) as mock_logger,
        ):
            # Should not raise
            executed = False
            with profile_with_trace_context():
                executed = True

            assert executed is True
            mock_logger.debug.assert_called_once()

    def test_profile_with_trace_context_preserves_code_execution(self) -> None:
        """Should execute code block regardless of tracing/profiling state."""
        from backend.core.telemetry import profile_with_trace_context

        result = []

        with profile_with_trace_context():
            result.append("executed")

        assert result == ["executed"]

    def test_profile_with_trace_context_propagates_exceptions(self) -> None:
        """Should propagate exceptions from the code block."""
        from backend.core.telemetry import profile_with_trace_context

        with pytest.raises(ValueError, match="Test error"):
            with profile_with_trace_context():
                raise ValueError("Test error")


class TestProfilingMiddleware:
    """Tests for ProfilingMiddleware."""

    @pytest.mark.asyncio
    async def test_profiling_middleware_wraps_request(self) -> None:
        """Should wrap request in profile_with_trace_context."""
        from starlette.testclient import TestClient

        from backend.api.middleware.profiling import ProfilingMiddleware

        # Track if profile_with_trace_context was called
        context_entered = []

        def mock_profile_context():
            from contextlib import contextmanager

            @contextmanager
            def _mock():
                context_entered.append(True)
                yield

            return _mock()

        with patch(
            "backend.api.middleware.profiling.profile_with_trace_context",
            side_effect=mock_profile_context,
            autospec=True,
        ):
            from fastapi import FastAPI

            app = FastAPI()
            app.add_middleware(ProfilingMiddleware)

            @app.get("/test")
            async def test_route():
                return {"status": "ok"}

            client = TestClient(app)
            response = client.get("/test")

            assert response.status_code == 200
            assert context_entered == [True]

    @pytest.mark.asyncio
    async def test_profiling_middleware_returns_response(self) -> None:
        """Should return response from downstream handler."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from backend.api.middleware.profiling import ProfilingMiddleware

        app = FastAPI()
        app.add_middleware(ProfilingMiddleware)

        @app.get("/test")
        async def test_route():
            return {"message": "hello"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "hello"}

    @pytest.mark.asyncio
    async def test_profiling_middleware_handles_errors(self) -> None:
        """Should propagate errors from downstream handler."""
        from fastapi import FastAPI, HTTPException
        from starlette.testclient import TestClient

        from backend.api.middleware.profiling import ProfilingMiddleware

        app = FastAPI()
        app.add_middleware(ProfilingMiddleware)

        @app.get("/test")
        async def test_route():
            raise HTTPException(status_code=500, detail="Internal error")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test")

        assert response.status_code == 500


class TestProfileWithTraceContextIntegration:
    """Integration tests for profile_with_trace_context with real OTEL."""

    def test_with_real_otel_no_active_span(self) -> None:
        """Should work correctly when no active span exists."""
        from backend.core.telemetry import profile_with_trace_context

        # No active span, should still execute without error
        executed = False
        with profile_with_trace_context():
            executed = True

        assert executed is True

    def test_with_real_otel_active_span(self) -> None:
        """Should work correctly with a real OTEL span."""
        from backend.core.telemetry import profile_with_trace_context, trace_span

        executed = False
        with trace_span("test_span"):
            with profile_with_trace_context():
                executed = True

        assert executed is True


class TestInitProfilingPytestGuard:
    """R-T7-CRASH: pyroscope's native sampler crashes pytest-xdist workers on
    aarch64/64k-page hosts when the FastAPI lifespan boots. The test session
    must run with profiling disabled while prod keeps the 'true' default."""

    def test_test_session_env_disables_profiling(self) -> None:
        """Under pytest, PYROSCOPE_ENABLED must already be set to 'false'
        (conftest setdefault guard) and init_profiling must not touch the
        pyroscope SDK."""
        import os
        from unittest.mock import patch

        import pytest

        if os.environ.get("PYROSCOPE_ENABLED") is None:
            pytest.fail(
                "PYROSCOPE_ENABLED guard missing: conftest must setdefault it "
                "to 'false' before app import (R-T7-CRASH)"
            )
        assert os.environ["PYROSCOPE_ENABLED"].lower() == "false"

        from backend.core.telemetry import init_profiling

        with patch("pyroscope.configure", autospec=True) as mock_configure:
            init_profiling()
        mock_configure.assert_not_called()

    def test_env_gate_honors_explicit_false(self, monkeypatch) -> None:
        """Explicit PYROSCOPE_ENABLED=false must skip configure()."""
        import sys
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("PYROSCOPE_ENABLED", "false")
        fake = MagicMock()
        with patch.dict(sys.modules, {"pyroscope": fake}):
            from backend.core.telemetry import init_profiling

            init_profiling()
        fake.configure.assert_not_called()

    def test_env_gate_honors_explicit_true(self, monkeypatch) -> None:
        """Explicit PYROSCOPE_ENABLED=true must still call configure()
        (prod behavior; SDK faked so no native library loads in-test)."""
        import sys
        from unittest.mock import MagicMock, patch

        monkeypatch.setenv("PYROSCOPE_ENABLED", "true")
        monkeypatch.setenv("PYROSCOPE_URL", "http://pyroscope.invalid:4040")
        fake = MagicMock()
        with patch.dict(sys.modules, {"pyroscope": fake}):
            from backend.core.telemetry import init_profiling

            init_profiling()
        fake.configure.assert_called_once()
