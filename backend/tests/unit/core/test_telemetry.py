"""Tests for OpenTelemetry distributed tracing setup.

NEM-1629: Tests for the telemetry module that provides OpenTelemetry
instrumentation for distributed tracing across services.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.telemetry import (
    _NoOpSpan,
    add_span_attributes,
    get_current_span,
    get_tracer,
    is_telemetry_enabled,
    record_exception,
    setup_telemetry,
    shutdown_telemetry,
)


class TestSetupTelemetry:
    """Tests for setup_telemetry function."""

    def test_setup_telemetry_disabled_by_default(self) -> None:
        """Telemetry should be disabled when otel_enabled=False."""
        # Reset module state
        import backend.core.telemetry as telemetry_module

        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = False

        result = setup_telemetry(mock_app, mock_settings)

        assert result is False
        assert is_telemetry_enabled() is False

    def test_setup_telemetry_skips_if_already_initialized(self) -> None:
        """Should skip initialization if already initialized."""
        import backend.core.telemetry as telemetry_module

        # Set as already initialized
        telemetry_module._is_initialized = True
        telemetry_module._tracer_provider = MagicMock()

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True

        result = setup_telemetry(mock_app, mock_settings)

        assert result is False

        # Cleanup
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None


class TestShutdownTelemetry:
    """Tests for shutdown_telemetry function."""

    def test_shutdown_when_not_initialized(self) -> None:
        """Should handle shutdown gracefully when not initialized."""
        import backend.core.telemetry as telemetry_module

        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        # Should not raise any exceptions
        shutdown_telemetry()


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_returns_tracer_when_otel_available(self) -> None:
        """Should return a tracer from the OpenTelemetry API."""
        # Since OpenTelemetry is installed, get_tracer should return a real tracer
        result = get_tracer("test_module")

        # Verify it's a tracer (has the expected methods)
        assert result is not None
        assert hasattr(result, "start_as_current_span") or hasattr(result, "start_span")

    def test_get_tracer_returns_value(self) -> None:
        """Should always return a tracer (real or no-op)."""
        result = get_tracer("test_module")
        assert result is not None


class TestGetCurrentSpan:
    """Tests for get_current_span function."""

    def test_get_current_span_returns_span_when_otel_available(self) -> None:
        """Should return the current span from OpenTelemetry context."""
        # Since OpenTelemetry is installed, get_current_span should return a span
        result = get_current_span()

        # Verify it's a span (real or no-op) with expected interface
        assert result is not None

    def test_get_current_span_returns_value(self) -> None:
        """Should return a span (real or no-op)."""
        result = get_current_span()
        assert result is not None


class TestAddSpanAttributes:
    """Tests for add_span_attributes function."""

    def test_add_span_attributes_sets_attributes(self) -> None:
        """Should add attributes to the current span."""
        mock_span = MagicMock()
        mock_span.set_attribute = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            add_span_attributes(camera_id="front_door", confidence=0.95, enabled=True)

        assert mock_span.set_attribute.call_count == 3
        mock_span.set_attribute.assert_any_call("camera_id", "front_door")
        mock_span.set_attribute.assert_any_call("confidence", 0.95)
        mock_span.set_attribute.assert_any_call("enabled", True)

    def test_add_span_attributes_handles_span_without_method(self) -> None:
        """Should handle spans that don't have set_attribute method."""
        mock_span = MagicMock(spec=[])  # Empty spec - no methods

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            # Should not raise
            add_span_attributes(key="value")


class TestRecordException:
    """Tests for record_exception function."""

    def test_record_exception_records_on_span(self) -> None:
        """Should record exception on the current span."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        mock_span.set_status = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            test_exception = ValueError("Test error")
            record_exception(test_exception, attributes={"custom": "value"})

        mock_span.record_exception.assert_called_once_with(
            test_exception, attributes={"custom": "value"}
        )
        mock_span.set_status.assert_called_once()

    def test_record_exception_handles_span_without_method(self) -> None:
        """Should handle spans that don't have record_exception method."""
        mock_span = MagicMock(spec=[])  # Empty spec - no methods

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            # Should not raise
            record_exception(ValueError("test"))


class TestNoOpSpan:
    """Tests for _NoOpSpan class."""

    def test_noop_span_methods_do_nothing(self) -> None:
        """No-op span methods should not raise exceptions."""
        span = _NoOpSpan()

        # All methods should work without raising
        span.set_attribute("key", "value")
        span.record_exception(ValueError("test"))
        span.set_status("OK")

    def test_noop_span_context_manager(self) -> None:
        """No-op span should work as a context manager."""
        span = _NoOpSpan()

        with span as s:
            assert s is span


class TestNoOpTracer:
    """Tests for _NoOpTracer class."""

    def test_noop_tracer_returns_noop_spans(self) -> None:
        """No-op tracer should return no-op spans."""
        from backend.core.telemetry import _NoOpSpan as NoOpSpanClass
        from backend.core.telemetry import _NoOpTracer as NoOpTracerClass

        tracer = NoOpTracerClass()

        span1 = tracer.start_as_current_span("test")
        assert isinstance(span1, NoOpSpanClass)

        span2 = tracer.start_span("test")
        assert isinstance(span2, NoOpSpanClass)

    def test_noop_tracer_span_context_manager(self) -> None:
        """No-op tracer spans should work as context managers."""
        from backend.core.telemetry import _NoOpSpan as NoOpSpanClass
        from backend.core.telemetry import _NoOpTracer as NoOpTracerClass

        tracer = NoOpTracerClass()

        with tracer.start_as_current_span("test") as span:
            assert isinstance(span, NoOpSpanClass)
            span.set_attribute("key", "value")


class TestIsTelemetryEnabled:
    """Tests for is_telemetry_enabled function."""

    def test_returns_false_when_not_initialized(self) -> None:
        """Should return False when telemetry is not initialized."""
        import backend.core.telemetry as telemetry_module

        telemetry_module._is_initialized = False
        assert is_telemetry_enabled() is False

    def test_returns_true_when_initialized(self) -> None:
        """Should return True when telemetry is initialized."""
        import backend.core.telemetry as telemetry_module

        original_value = telemetry_module._is_initialized
        telemetry_module._is_initialized = True

        assert is_telemetry_enabled() is True

        # Cleanup
        telemetry_module._is_initialized = original_value


class TestConfigSettings:
    """Tests for OpenTelemetry configuration settings."""

    def test_otel_settings_have_defaults(self) -> None:
        """OTEL settings should have sensible defaults."""
        from backend.core.config import Settings

        # Create settings with minimal required config (DATABASE_URL is required)
        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test"
            },
        ):
            settings = Settings()

        assert settings.otel_enabled is False
        assert settings.otel_service_name == "nemotron-backend"
        assert settings.otel_exporter_otlp_endpoint == "http://localhost:4317"
        assert settings.otel_exporter_otlp_insecure is True
        assert settings.otel_trace_sample_rate == 1.0

    def test_otel_settings_can_be_configured(self) -> None:
        """OTEL settings should be configurable via environment."""
        from backend.core.config import Settings

        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                "OTEL_ENABLED": "true",
                "OTEL_SERVICE_NAME": "my-service",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://jaeger:4317",
                "OTEL_EXPORTER_OTLP_INSECURE": "false",
                "OTEL_TRACE_SAMPLE_RATE": "0.5",
            },
        ):
            settings = Settings()

        assert settings.otel_enabled is True
        assert settings.otel_service_name == "my-service"
        assert settings.otel_exporter_otlp_endpoint == "http://jaeger:4317"
        assert settings.otel_exporter_otlp_insecure is False
        assert settings.otel_trace_sample_rate == 0.5

    def test_otel_sample_rate_validation(self) -> None:
        """Sample rate should be validated to be between 0 and 1."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_TRACE_SAMPLE_RATE": "1.5",  # Invalid - > 1.0
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()

        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_TRACE_SAMPLE_RATE": "-0.1",  # Invalid - < 0.0
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()
