"""Tests for OpenTelemetry distributed tracing setup.

NEM-1629: Tests for the telemetry module that provides OpenTelemetry
instrumentation for distributed tracing across services.
NEM-3380: Tests for ParentBased composite sampler.
NEM-3382: Tests for Baggage cross-service context propagation.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from backend.core.telemetry import (
    _NoOpSpan,
    _NoOpTracer,
    add_span_attributes,
    clear_baggage,
    extract_context_from_headers,
    get_all_baggage,
    get_baggage,
    get_current_span,
    get_span_id,
    get_trace_context,
    get_trace_id,
    get_tracer,
    is_telemetry_enabled,
    record_exception,
    set_baggage,
    set_request_baggage,
    setup_telemetry,
    shutdown_telemetry,
    trace_function,
    trace_span,
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

        assert settings.otel_enabled is True  # OTEL enabled by default
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


class TestSetupTelemetrySuccess:
    """Tests for setup_telemetry success path with real OpenTelemetry imports."""

    def test_setup_telemetry_success_initializes_all_instrumentations(self) -> None:
        """Should successfully initialize all OpenTelemetry instrumentations."""
        import backend.core.telemetry as telemetry_module

        # Reset module state
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True
        mock_settings.otel_service_name = "test-service"
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4317"
        mock_settings.otel_exporter_otlp_insecure = True
        mock_settings.otel_trace_sample_rate = 1.0
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        # Add new sampling settings for priority-based sampler (NEM-3793)
        mock_settings.otel_sampling_error_rate = 1.0
        mock_settings.otel_sampling_high_risk_rate = 1.0
        mock_settings.otel_sampling_high_priority_rate = 1.0
        mock_settings.otel_sampling_medium_priority_rate = 0.5
        mock_settings.otel_sampling_background_rate = 0.1
        mock_settings.otel_sampling_default_rate = 0.1
        # Add batch processor settings
        mock_settings.otel_batch_max_queue_size = 8192
        mock_settings.otel_batch_max_export_batch_size = 1024
        mock_settings.otel_batch_schedule_delay_ms = 2000
        mock_settings.otel_batch_export_timeout_ms = 30000

        # Mock all the imports inside setup_telemetry
        with (
            patch("opentelemetry.sdk.resources.Resource") as mock_resource,
            patch("opentelemetry.sdk.resources.get_aggregated_resources") as mock_get_aggregated,
            patch("opentelemetry.sdk.resources.ProcessResourceDetector"),
            patch("opentelemetry.sdk.resources.OsResourceDetector"),
            patch("opentelemetry.sdk.trace.TracerProvider") as mock_tracer_provider,
            patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
            ) as mock_exporter,
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor") as mock_processor,
            patch("opentelemetry.sdk.trace.sampling.TraceIdRatioBased") as mock_sampler,
            patch("opentelemetry.trace") as mock_trace,
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
            # Mock the priority-based sampler module (NEM-3793)
            patch("backend.core.sampling.create_otel_sampler") as mock_create_sampler,
        ):
            # Setup mocks
            mock_service_resource = MagicMock()
            mock_resource.create.return_value = mock_service_resource
            mock_detected_resource = MagicMock()
            mock_get_aggregated.return_value = mock_detected_resource
            mock_provider = MagicMock()
            mock_tracer_provider.return_value = mock_provider
            mock_priority_sampler = MagicMock()
            mock_create_sampler.return_value = mock_priority_sampler

            result = setup_telemetry(mock_app, mock_settings)

            # Verify successful initialization
            assert result is True
            assert telemetry_module._is_initialized is True

            # Verify resource was created with correct attributes
            # Use assert_any_call because resource detectors may also call create()
            mock_resource.create.assert_any_call(
                {
                    "service.name": "test-service",
                    "service.version": "1.0.0",
                    "deployment.environment": "production",
                }
            )

            # Verify priority-based sampler was created (NEM-3793)
            mock_create_sampler.assert_called_once_with(mock_settings)

            # Verify TracerProvider was created
            mock_tracer_provider.assert_called_once()

            # Verify OTLP exporter was created
            mock_exporter.assert_called_once_with(endpoint="http://localhost:4317", insecure=True)

            # Verify instrumentations were called
            mock_fastapi.instrument_app.assert_called_once_with(mock_app)
            mock_httpx.return_value.instrument.assert_called_once()
            mock_sqlalchemy.return_value.instrument.assert_called_once()
            mock_redis.return_value.instrument.assert_called_once()

            # Cleanup
            telemetry_module._is_initialized = False
            telemetry_module._tracer_provider = None

    def test_setup_telemetry_handles_import_error(self) -> None:
        """Should handle ImportError gracefully when OpenTelemetry is not installed."""
        import backend.core.telemetry as telemetry_module

        # Reset module state
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True

        # Simulate ImportError by making the import statement fail
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry.trace" or name.startswith("opentelemetry"):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = setup_telemetry(mock_app, mock_settings)

            assert result is False
            assert telemetry_module._is_initialized is False

        # Cleanup
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

    def test_setup_telemetry_handles_general_exception(self) -> None:
        """Should handle general exceptions during initialization."""
        import backend.core.telemetry as telemetry_module

        # Reset module state
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True
        mock_settings.otel_service_name = "test"
        mock_settings.app_version = "1.0"
        mock_settings.debug = False
        mock_settings.otel_trace_sample_rate = 1.0

        with (
            patch("opentelemetry.sdk.resources.Resource") as mock_resource,
            patch(
                "opentelemetry.sdk.trace.TracerProvider",
                side_effect=Exception("Initialization failed"),
            ),
        ):
            mock_resource.create.return_value = MagicMock()

            result = setup_telemetry(mock_app, mock_settings)

            assert result is False
            assert telemetry_module._is_initialized is False

        # Cleanup
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None


class TestShutdownTelemetrySuccess:
    """Tests for shutdown_telemetry success path."""

    def test_shutdown_telemetry_uninstruments_all(self) -> None:
        """Should uninstrument all libraries and shutdown tracer provider."""
        from opentelemetry.sdk.trace import TracerProvider as RealTracerProvider

        import backend.core.telemetry as telemetry_module

        # Setup initialized state
        mock_provider = MagicMock(spec=RealTracerProvider)
        mock_provider.shutdown = MagicMock()
        telemetry_module._is_initialized = True
        telemetry_module._tracer_provider = mock_provider

        with (
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
        ):
            shutdown_telemetry()

            # Verify all uninstrument calls
            mock_fastapi.uninstrument.assert_called_once()
            mock_httpx.return_value.uninstrument.assert_called_once()
            mock_sqlalchemy.return_value.uninstrument.assert_called_once()
            mock_redis.return_value.uninstrument.assert_called_once()

            # Verify tracer provider shutdown
            mock_provider.shutdown.assert_called_once()

            # Verify state was reset
            assert telemetry_module._is_initialized is False
            assert telemetry_module._tracer_provider is None

    def test_shutdown_telemetry_handles_exception(self) -> None:
        """Should handle exceptions during shutdown gracefully."""
        import backend.core.telemetry as telemetry_module

        # Setup initialized state
        telemetry_module._is_initialized = True
        telemetry_module._tracer_provider = MagicMock()

        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise Exception("Shutdown failed")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should not raise
            shutdown_telemetry()

        # Cleanup
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None


class TestGetTracerImportError:
    """Tests for get_tracer ImportError path."""

    def test_get_tracer_returns_noop_on_import_error(self) -> None:
        """Should return no-op tracer when OpenTelemetry is not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            tracer = get_tracer("test_module")

            # Verify it's a no-op tracer
            assert isinstance(tracer, _NoOpTracer)


class TestGetCurrentSpanImportError:
    """Tests for get_current_span ImportError path."""

    def test_get_current_span_returns_noop_on_import_error(self) -> None:
        """Should return no-op span when OpenTelemetry is not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            span = get_current_span()

            # Verify it's a no-op span
            assert isinstance(span, _NoOpSpan)


class TestRecordExceptionWithStatus:
    """Tests for record_exception with status setting."""

    def test_record_exception_sets_error_status(self) -> None:
        """Should record exception and set error status on span."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        mock_span.set_status = MagicMock()

        with (
            patch("backend.core.telemetry.get_current_span", return_value=mock_span),
            patch("opentelemetry.trace.StatusCode") as mock_status_code,
        ):
            mock_status_code.ERROR = "ERROR"
            test_exception = ValueError("Test error")
            record_exception(test_exception)

            mock_span.record_exception.assert_called_once_with(test_exception, attributes={})
            mock_span.set_status.assert_called_once_with("ERROR", "Test error")


class TestGetTraceId:
    """Tests for get_trace_id function."""

    def test_get_trace_id_returns_hex_string(self) -> None:
        """Should return 32-character hex string trace ID."""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.trace_id = 12345678901234567890123456789012
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            trace_id = get_trace_id()

            assert trace_id is not None
            assert len(trace_id) == 32
            assert trace_id == format(12345678901234567890123456789012, "032x")

    def test_get_trace_id_returns_none_when_invalid_context(self) -> None:
        """Should return None when span context is invalid."""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            trace_id = get_trace_id()

            assert trace_id is None

    def test_get_trace_id_returns_none_when_no_span_context(self) -> None:
        """Should return None when span doesn't have get_span_context method."""
        mock_span = MagicMock(spec=[])  # No get_span_context method

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            trace_id = get_trace_id()

            assert trace_id is None

    def test_get_trace_id_handles_exception(self) -> None:
        """Should return None and log at debug level when exception occurs."""
        mock_span = MagicMock()
        mock_span.get_span_context.side_effect = Exception("Test error")

        with (
            patch("backend.core.telemetry.get_current_span", return_value=mock_span),
            patch("backend.core.telemetry.logger") as mock_logger,
        ):
            trace_id = get_trace_id()

            assert trace_id is None
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args
            assert "Failed to get trace_id" in call_args[0][0]


class TestGetSpanId:
    """Tests for get_span_id function."""

    def test_get_span_id_returns_hex_string(self) -> None:
        """Should return 16-character hex string span ID."""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = True
        mock_span_context.span_id = 1234567890123456
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            span_id = get_span_id()

            assert span_id is not None
            assert len(span_id) == 16
            assert span_id == format(1234567890123456, "016x")

    def test_get_span_id_returns_none_when_invalid_context(self) -> None:
        """Should return None when span context is invalid."""
        mock_span = MagicMock()
        mock_span_context = MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            span_id = get_span_id()

            assert span_id is None

    def test_get_span_id_returns_none_when_no_span_context(self) -> None:
        """Should return None when span doesn't have get_span_context method."""
        mock_span = MagicMock(spec=[])  # No get_span_context method

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            span_id = get_span_id()

            assert span_id is None

    def test_get_span_id_handles_exception(self) -> None:
        """Should return None and log at debug level when exception occurs."""
        mock_span = MagicMock()
        mock_span.get_span_context.side_effect = Exception("Test error")

        with (
            patch("backend.core.telemetry.get_current_span", return_value=mock_span),
            patch("backend.core.telemetry.logger") as mock_logger,
        ):
            span_id = get_span_id()

            assert span_id is None
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args
            assert "Failed to get span_id" in call_args[0][0]


class TestGetTraceContext:
    """Tests for get_trace_context function."""

    def test_get_trace_context_returns_dict(self) -> None:
        """Should return dictionary with trace_id and span_id."""
        with (
            patch("backend.core.telemetry.get_trace_id", return_value="trace123"),
            patch("backend.core.telemetry.get_span_id", return_value="span456"),
        ):
            context = get_trace_context()

            assert context == {"trace_id": "trace123", "span_id": "span456"}

    def test_get_trace_context_handles_none_values(self) -> None:
        """Should return dictionary with None values when IDs are not available."""
        with (
            patch("backend.core.telemetry.get_trace_id", return_value=None),
            patch("backend.core.telemetry.get_span_id", return_value=None),
        ):
            context = get_trace_context()

            assert context == {"trace_id": None, "span_id": None}


class TestTraceSpan:
    """Tests for trace_span context manager."""

    def test_trace_span_creates_span_with_attributes(self) -> None:
        """Should create span with provided attributes."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("backend.core.telemetry.get_tracer", return_value=mock_tracer),
            trace_span("test_span", camera_id="front_door", confidence=0.95) as span,
        ):
            assert span == mock_span

        mock_tracer.start_as_current_span.assert_called_once_with("test_span")
        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call("camera_id", "front_door")
        mock_span.set_attribute.assert_any_call("confidence", 0.95)

    def test_trace_span_records_exception_on_error(self) -> None:
        """Should record exception when error occurs."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("backend.core.telemetry.get_tracer", return_value=mock_tracer),
            patch("backend.core.telemetry.record_exception") as mock_record,
            pytest.raises(ValueError),
        ):
            with trace_span("test_span"):
                raise ValueError("Test error")

        mock_record.assert_called_once()

    def test_trace_span_skips_exception_recording_when_disabled(self) -> None:
        """Should not record exception when record_exception_on_error is False."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("backend.core.telemetry.get_tracer", return_value=mock_tracer),
            patch("backend.core.telemetry.record_exception") as mock_record,
            pytest.raises(ValueError),
        ):
            with trace_span("test_span", record_exception_on_error=False):
                raise ValueError("Test error")

        mock_record.assert_not_called()


class TestTraceFunctionDecorator:
    """Tests for trace_function decorator."""

    def test_trace_function_wraps_sync_function(self) -> None:
        """Should wrap synchronous functions with tracing."""

        @trace_function("test_operation")
        def sync_func(x: int, y: int) -> int:
            return x + y

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("backend.core.telemetry.get_tracer", return_value=mock_tracer):
            result = sync_func(2, 3)

        assert result == 5
        mock_tracer.start_as_current_span.assert_called_once_with("test_operation")

    def test_trace_function_uses_function_name_when_no_name_provided(self) -> None:
        """Should use function name when span name is not provided."""

        @trace_function()
        def my_function() -> str:
            return "result"

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("backend.core.telemetry.get_tracer", return_value=mock_tracer):
            result = my_function()

        assert result == "result"
        mock_tracer.start_as_current_span.assert_called_once_with("my_function")

    @pytest.mark.asyncio
    async def test_trace_function_wraps_async_function(self) -> None:
        """Should wrap asynchronous functions with tracing."""

        @trace_function("async_operation")
        async def async_func(x: int) -> int:
            return x * 2

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("backend.core.telemetry.get_tracer", return_value=mock_tracer):
            result = await async_func(5)

        assert result == 10
        mock_tracer.start_as_current_span.assert_called_once_with("async_operation")

    def test_trace_function_adds_static_attributes(self) -> None:
        """Should add static attributes to the span."""

        @trace_function("operation", service="test-service", version=1)
        def func_with_attrs() -> str:
            return "done"

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("backend.core.telemetry.get_tracer", return_value=mock_tracer):
            result = func_with_attrs()

        assert result == "done"
        assert mock_span.set_attribute.call_count == 2
        mock_span.set_attribute.assert_any_call("service", "test-service")
        mock_span.set_attribute.assert_any_call("version", 1)

    def test_trace_function_records_exception_in_sync_function(self) -> None:
        """Should record exception when sync function raises."""

        @trace_function("failing_operation")
        def failing_func() -> None:
            raise ValueError("Test error")

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("backend.core.telemetry.get_tracer", return_value=mock_tracer),
            patch("backend.core.telemetry.record_exception") as mock_record,
            pytest.raises(ValueError),
        ):
            failing_func()

        mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_function_records_exception_in_async_function(self) -> None:
        """Should record exception when async function raises."""

        @trace_function("failing_async_operation")
        async def failing_async_func() -> None:
            raise ValueError("Async test error")

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with (
            patch("backend.core.telemetry.get_tracer", return_value=mock_tracer),
            patch("backend.core.telemetry.record_exception") as mock_record,
            pytest.raises(ValueError),
        ):
            await failing_async_func()

        mock_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_function_handles_coroutine_result(self) -> None:
        """Should properly await coroutine results from decorated functions."""

        @trace_function("coroutine_operation")
        def func_returning_coroutine() -> int:
            # This function returns a coroutine but is not async
            async def inner():
                return 42

            return inner()  # Returns coroutine object

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span

        with patch("backend.core.telemetry.get_tracer", return_value=mock_tracer):
            result = await func_returning_coroutine()

        assert result == 42


class TestShutdownTelemetryNonTracerProvider:
    """Tests for shutdown_telemetry with non-TracerProvider objects."""

    def test_shutdown_telemetry_skips_shutdown_for_non_tracer_provider(self) -> None:
        """Should skip shutdown call when _tracer_provider is not a TracerProvider instance."""
        import backend.core.telemetry as telemetry_module

        # Setup initialized state with non-TracerProvider object
        telemetry_module._is_initialized = True
        telemetry_module._tracer_provider = "not_a_tracer_provider"  # Not a TracerProvider

        with (
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
        ):
            shutdown_telemetry()

            # Verify uninstrument calls still happened
            mock_fastapi.uninstrument.assert_called_once()
            mock_httpx.return_value.uninstrument.assert_called_once()
            mock_sqlalchemy.return_value.uninstrument.assert_called_once()
            mock_redis.return_value.uninstrument.assert_called_once()

            # Verify state was reset
            assert telemetry_module._is_initialized is False
            assert telemetry_module._tracer_provider is None


class TestRecordExceptionWithoutSetStatus:
    """Tests for record_exception when span doesn't have set_status method."""

    def test_record_exception_handles_missing_set_status(self) -> None:
        """Should handle span without set_status method gracefully."""
        mock_span = MagicMock()
        mock_span.record_exception = MagicMock()
        # Simulate span without set_status method
        delattr(mock_span, "set_status")

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            test_exception = ValueError("Test error")
            record_exception(test_exception)

            # Should still record the exception
            mock_span.record_exception.assert_called_once_with(test_exception, attributes={})


# =============================================================================
# NEM-3380: ParentBased Composite Sampler Tests
# NEM-3793: Updated to test priority-based sampling
# =============================================================================


class TestParentBasedSampler:
    """Tests for ParentBased composite sampler configuration."""

    def test_setup_telemetry_configures_parent_based_sampler(self) -> None:
        """Should configure ParentBased sampler with priority-based sampling (NEM-3793)."""
        import backend.core.telemetry as telemetry_module

        # Reset module state
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True
        mock_settings.otel_service_name = "test-service"
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4317"
        mock_settings.otel_exporter_otlp_insecure = True
        mock_settings.otel_trace_sample_rate = 0.1  # 10% sampling
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        # Add new sampling settings for priority-based sampler (NEM-3793)
        mock_settings.otel_sampling_error_rate = 1.0
        mock_settings.otel_sampling_high_risk_rate = 1.0
        mock_settings.otel_sampling_high_priority_rate = 1.0
        mock_settings.otel_sampling_medium_priority_rate = 0.5
        mock_settings.otel_sampling_background_rate = 0.1
        mock_settings.otel_sampling_default_rate = 0.1
        # Add batch processor settings
        mock_settings.otel_batch_max_queue_size = 8192
        mock_settings.otel_batch_max_export_batch_size = 1024
        mock_settings.otel_batch_schedule_delay_ms = 2000
        mock_settings.otel_batch_export_timeout_ms = 30000

        with (
            patch("opentelemetry.sdk.resources.Resource") as mock_resource,
            patch("opentelemetry.sdk.trace.TracerProvider") as mock_tracer_provider,
            patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
            ) as mock_exporter,
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor") as mock_processor,
            patch("opentelemetry.sdk.trace.sampling.TraceIdRatioBased") as mock_ratio_sampler,
            patch("opentelemetry.sdk.trace.sampling.ParentBased") as mock_parent_based,
            patch("opentelemetry.sdk.trace.sampling.ALWAYS_ON") as mock_always_on,
            patch("opentelemetry.sdk.trace.sampling.ALWAYS_OFF") as mock_always_off,
            patch("opentelemetry.trace") as mock_trace,
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
            patch("opentelemetry.propagate.set_global_textmap") as mock_set_textmap,
            patch("opentelemetry.propagators.composite.CompositePropagator") as mock_composite,
            patch(
                "opentelemetry.trace.propagation.tracecontext.TraceContextTextMapPropagator"
            ) as mock_trace_prop,
            patch("opentelemetry.baggage.propagation.W3CBaggagePropagator") as mock_baggage_prop,
            # Mock the priority-based sampler module (NEM-3793)
            patch("backend.core.sampling.create_otel_sampler") as mock_create_sampler,
        ):
            # Setup mocks
            mock_resource.create.return_value = MagicMock()
            mock_ratio_sampler.return_value = MagicMock()
            mock_parent_based.return_value = MagicMock()
            mock_provider = MagicMock()
            mock_tracer_provider.return_value = mock_provider
            mock_priority_sampler = MagicMock()
            mock_create_sampler.return_value = mock_priority_sampler

            result = setup_telemetry(mock_app, mock_settings)

            # Verify successful initialization
            assert result is True

            # Verify priority-based sampler was created (NEM-3793)
            mock_create_sampler.assert_called_once_with(mock_settings)

            # Cleanup
            telemetry_module._is_initialized = False
            telemetry_module._tracer_provider = None


# =============================================================================
# NEM-3382: Baggage Cross-Service Context Tests
# =============================================================================


class TestSetBaggage:
    """Tests for set_baggage function."""

    def test_set_baggage_calls_otel_baggage(self) -> None:
        """Should call OpenTelemetry baggage.set_baggage with correct parameters."""
        mock_ctx = MagicMock()

        with (
            patch("opentelemetry.baggage.set_baggage", return_value=mock_ctx) as mock_set,
            patch("opentelemetry.context.attach") as mock_attach,
        ):
            set_baggage("camera_id", "front_door")

            mock_set.assert_called_once_with("camera_id", "front_door")
            mock_attach.assert_called_once_with(mock_ctx)

    def test_set_baggage_handles_import_error(self) -> None:
        """Should handle ImportError gracefully when OpenTelemetry is not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should not raise
            set_baggage("key", "value")

    def test_set_baggage_handles_exception(self) -> None:
        """Should handle exceptions gracefully."""
        with (
            patch("opentelemetry.baggage.set_baggage", side_effect=Exception("Test error")),
            patch("backend.core.telemetry.logger") as mock_logger,
        ):
            set_baggage("key", "value")

            mock_logger.debug.assert_called_once()


class TestGetBaggage:
    """Tests for get_baggage function."""

    def test_get_baggage_returns_value(self) -> None:
        """Should return baggage value from OpenTelemetry context."""
        with patch("opentelemetry.baggage.get_baggage", return_value="front_door") as mock_get:
            result = get_baggage("camera_id")

            assert result == "front_door"
            mock_get.assert_called_once_with("camera_id")

    def test_get_baggage_returns_none_when_not_set(self) -> None:
        """Should return None when baggage is not set."""
        with patch("opentelemetry.baggage.get_baggage", return_value=None):
            result = get_baggage("nonexistent_key")

            assert result is None

    def test_get_baggage_handles_import_error(self) -> None:
        """Should return None when OpenTelemetry is not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = get_baggage("key")

            assert result is None

    def test_get_baggage_handles_exception(self) -> None:
        """Should return None and log on exception."""
        with (
            patch("opentelemetry.baggage.get_baggage", side_effect=Exception("Test error")),
            patch("backend.core.telemetry.logger") as mock_logger,
        ):
            result = get_baggage("key")

            assert result is None
            mock_logger.debug.assert_called_once()


class TestGetAllBaggage:
    """Tests for get_all_baggage function."""

    def test_get_all_baggage_returns_dict(self) -> None:
        """Should return dictionary of all baggage entries."""
        mock_baggage = {"camera_id": "front_door", "batch_id": "batch-123"}

        with patch("opentelemetry.baggage.get_all", return_value=mock_baggage):
            result = get_all_baggage()

            assert result == {"camera_id": "front_door", "batch_id": "batch-123"}

    def test_get_all_baggage_returns_empty_dict_when_no_baggage(self) -> None:
        """Should return empty dict when no baggage is set."""
        with patch("opentelemetry.baggage.get_all", return_value={}):
            result = get_all_baggage()

            assert result == {}

    def test_get_all_baggage_handles_import_error(self) -> None:
        """Should return empty dict when OpenTelemetry is not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = get_all_baggage()

            assert result == {}


class TestClearBaggage:
    """Tests for clear_baggage function."""

    def test_clear_baggage_removes_entry(self) -> None:
        """Should remove baggage entry from context."""
        mock_ctx = MagicMock()

        with (
            patch("opentelemetry.baggage.remove_baggage", return_value=mock_ctx) as mock_remove,
            patch("opentelemetry.context.attach") as mock_attach,
        ):
            clear_baggage("camera_id")

            mock_remove.assert_called_once_with("camera_id")
            mock_attach.assert_called_once_with(mock_ctx)

    def test_clear_baggage_handles_import_error(self) -> None:
        """Should handle ImportError gracefully."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should not raise
            clear_baggage("key")


class TestSetRequestBaggage:
    """Tests for set_request_baggage convenience function."""

    def test_set_request_baggage_sets_all_provided_entries(self) -> None:
        """Should set all provided baggage entries."""
        with patch("backend.core.telemetry.set_baggage") as mock_set:
            set_request_baggage(
                request_id="req-123",
                correlation_id="corr-456",
                camera_id="front_door",
                batch_id="batch-789",
            )

            assert mock_set.call_count == 4
            mock_set.assert_any_call("request_id", "req-123")
            mock_set.assert_any_call("correlation_id", "corr-456")
            mock_set.assert_any_call("camera_id", "front_door")
            mock_set.assert_any_call("batch_id", "batch-789")

    def test_set_request_baggage_skips_none_values(self) -> None:
        """Should skip None values."""
        with patch("backend.core.telemetry.set_baggage") as mock_set:
            set_request_baggage(camera_id="front_door")

            mock_set.assert_called_once_with("camera_id", "front_door")

    def test_set_request_baggage_with_no_values(self) -> None:
        """Should not set any baggage when no values provided."""
        with patch("backend.core.telemetry.set_baggage") as mock_set:
            set_request_baggage()

            mock_set.assert_not_called()


class TestExtractContextFromHeaders:
    """Tests for extract_context_from_headers function."""

    def test_extract_context_from_headers_calls_propagate(self) -> None:
        """Should call OpenTelemetry propagate.extract with headers."""
        mock_ctx = MagicMock()
        headers = {"traceparent": "00-trace-span-01", "baggage": "camera_id=front_door"}

        with (
            patch("opentelemetry.propagate.extract", return_value=mock_ctx) as mock_extract,
            patch("opentelemetry.context.attach") as mock_attach,
        ):
            extract_context_from_headers(headers)

            mock_extract.assert_called_once_with(headers)
            mock_attach.assert_called_once_with(mock_ctx)

    def test_extract_context_from_headers_handles_import_error(self) -> None:
        """Should handle ImportError gracefully."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry" or name.startswith("opentelemetry."):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        headers = {"traceparent": "00-trace-span-01"}

        with patch("builtins.__import__", side_effect=mock_import):
            # Should not raise
            extract_context_from_headers(headers)

    def test_extract_context_from_headers_handles_exception(self) -> None:
        """Should handle exceptions gracefully."""
        headers = {"traceparent": "00-trace-span-01"}

        with (
            patch("opentelemetry.propagate.extract", side_effect=Exception("Test error")),
            patch("backend.core.telemetry.logger") as mock_logger,
        ):
            extract_context_from_headers(headers)

            mock_logger.debug.assert_called_once()


class TestCompositePropagatorConfiguration:
    """Tests for composite propagator configuration with W3C Trace Context and Baggage."""

    def test_setup_telemetry_configures_composite_propagator(self) -> None:
        """Should configure composite propagator with both trace context and baggage."""
        import backend.core.telemetry as telemetry_module

        # Reset module state
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None

        mock_app = MagicMock()
        mock_settings = MagicMock()
        mock_settings.otel_enabled = True
        mock_settings.otel_service_name = "test-service"
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4317"
        mock_settings.otel_exporter_otlp_insecure = True
        mock_settings.otel_trace_sample_rate = 1.0
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        # Add new sampling settings for priority-based sampler (NEM-3793)
        mock_settings.otel_sampling_error_rate = 1.0
        mock_settings.otel_sampling_high_risk_rate = 1.0
        mock_settings.otel_sampling_high_priority_rate = 1.0
        mock_settings.otel_sampling_medium_priority_rate = 0.5
        mock_settings.otel_sampling_background_rate = 0.1
        mock_settings.otel_sampling_default_rate = 0.1
        # Add batch processor settings
        mock_settings.otel_batch_max_queue_size = 8192
        mock_settings.otel_batch_max_export_batch_size = 1024
        mock_settings.otel_batch_schedule_delay_ms = 2000
        mock_settings.otel_batch_export_timeout_ms = 30000

        with (
            patch("opentelemetry.sdk.resources.Resource") as mock_resource,
            patch("opentelemetry.sdk.trace.TracerProvider") as mock_tracer_provider,
            patch(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
            ) as mock_exporter,
            patch("opentelemetry.sdk.trace.export.BatchSpanProcessor") as mock_processor,
            patch("opentelemetry.sdk.trace.sampling.TraceIdRatioBased") as mock_sampler,
            patch("opentelemetry.sdk.trace.sampling.ParentBased") as mock_parent_based,
            patch("opentelemetry.sdk.trace.sampling.ALWAYS_ON"),
            patch("opentelemetry.sdk.trace.sampling.ALWAYS_OFF"),
            patch("opentelemetry.trace") as mock_trace,
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
            patch("opentelemetry.propagate.set_global_textmap") as mock_set_textmap,
            patch("opentelemetry.propagators.composite.CompositePropagator") as mock_composite,
            patch(
                "opentelemetry.trace.propagation.tracecontext.TraceContextTextMapPropagator"
            ) as mock_trace_prop,
            patch("opentelemetry.baggage.propagation.W3CBaggagePropagator") as mock_baggage_prop,
            # Mock the priority-based sampler module (NEM-3793)
            patch("backend.core.sampling.create_otel_sampler") as mock_create_sampler,
        ):
            # Setup mocks
            mock_resource.create.return_value = MagicMock()
            mock_provider = MagicMock()
            mock_tracer_provider.return_value = mock_provider
            mock_composite_instance = MagicMock()
            mock_composite.return_value = mock_composite_instance
            mock_priority_sampler = MagicMock()
            mock_create_sampler.return_value = mock_priority_sampler

            result = setup_telemetry(mock_app, mock_settings)

            # Verify successful initialization
            assert result is True

            # Verify CompositePropagator was created with both propagators
            mock_composite.assert_called_once()
            call_args = mock_composite.call_args
            propagators = call_args[0][0]
            assert len(propagators) == 2

            # Verify set_global_textmap was called with composite propagator
            mock_set_textmap.assert_called_once_with(mock_composite_instance)

            # Cleanup
            telemetry_module._is_initialized = False
            telemetry_module._tracer_provider = None


# =============================================================================
# Span Events Tests (NEM-3434)
# =============================================================================


class TestAddSpanEvent:
    """Tests for add_span_event function."""

    def test_add_span_event_calls_span_add_event(self) -> None:
        """Should call add_event on the current span."""
        from backend.core.telemetry import add_span_event

        mock_span = MagicMock()
        mock_span.add_event = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            add_span_event("test.event", {"key": "value"})

        mock_span.add_event.assert_called_once_with("test.event", attributes={"key": "value"})

    def test_add_span_event_with_timestamp(self) -> None:
        """Should pass timestamp to add_event when provided."""
        from backend.core.telemetry import add_span_event

        mock_span = MagicMock()
        mock_span.add_event = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            add_span_event("test.event", {"key": "value"}, timestamp_ns=1234567890)

        mock_span.add_event.assert_called_once_with(
            "test.event", attributes={"key": "value"}, timestamp=1234567890
        )

    def test_add_span_event_handles_span_without_method(self) -> None:
        """Should handle spans that don't have add_event method."""
        from backend.core.telemetry import add_span_event

        mock_span = MagicMock(spec=[])  # Empty spec - no methods

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            # Should not raise
            add_span_event("test.event")


class TestRecordPipelineMilestone:
    """Tests for record_pipeline_milestone function."""

    def test_record_pipeline_milestone_with_all_attributes(self) -> None:
        """Should record milestone with all provided attributes."""
        from backend.core.telemetry import record_pipeline_milestone

        mock_span = MagicMock()
        mock_span.add_event = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            record_pipeline_milestone(
                "detection_complete",
                stage="detect",
                camera_id="front_door",
                batch_id="batch-123",
                detection_count=5,
                duration_ms=245.3,
                custom_attr="custom_value",
            )

        mock_span.add_event.assert_called_once()
        call_args = mock_span.add_event.call_args
        assert call_args[0][0] == "pipeline.detection_complete"
        attrs = call_args[1]["attributes"]
        assert attrs["pipeline.stage"] == "detect"
        assert attrs["camera.id"] == "front_door"
        assert attrs["batch.id"] == "batch-123"
        assert attrs["pipeline.detection_count"] == 5
        assert attrs["pipeline.duration_ms"] == 245.3
        assert attrs["custom_attr"] == "custom_value"

    def test_record_pipeline_milestone_with_minimal_attributes(self) -> None:
        """Should record milestone with minimal attributes."""
        from backend.core.telemetry import record_pipeline_milestone

        mock_span = MagicMock()
        mock_span.add_event = MagicMock()

        with patch("backend.core.telemetry.get_current_span", return_value=mock_span):
            record_pipeline_milestone("started")

        mock_span.add_event.assert_called_once()
        call_args = mock_span.add_event.call_args
        assert call_args[0][0] == "pipeline.started"
        assert call_args[1]["attributes"] == {}


# =============================================================================
# Span Links Tests (NEM-3435)
# =============================================================================


class TestSpanLinkContext:
    """Tests for SpanLinkContext class."""

    def test_span_link_context_init(self) -> None:
        """Should initialize with trace_id and span_id."""
        from backend.core.telemetry import SpanLinkContext

        ctx = SpanLinkContext("0123456789abcdef0123456789abcdef", "0123456789abcdef")
        assert ctx.trace_id == "0123456789abcdef0123456789abcdef"
        assert ctx.span_id == "0123456789abcdef"

    def test_span_link_context_to_dict(self) -> None:
        """Should convert to dictionary."""
        from backend.core.telemetry import SpanLinkContext

        ctx = SpanLinkContext("trace123", "span456")
        result = ctx.to_dict()
        assert result == {"trace_id": "trace123", "span_id": "span456"}

    def test_span_link_context_from_dict(self) -> None:
        """Should create from dictionary."""
        from backend.core.telemetry import SpanLinkContext

        data = {"trace_id": "trace123", "span_id": "span456"}
        ctx = SpanLinkContext.from_dict(data)
        assert ctx is not None
        assert ctx.trace_id == "trace123"
        assert ctx.span_id == "span456"

    def test_span_link_context_from_dict_missing_keys(self) -> None:
        """Should return None when keys are missing."""
        from backend.core.telemetry import SpanLinkContext

        assert SpanLinkContext.from_dict({}) is None
        assert SpanLinkContext.from_dict({"trace_id": "trace123"}) is None
        assert SpanLinkContext.from_dict({"span_id": "span456"}) is None


class TestCaptureSpanContext:
    """Tests for capture_span_context function."""

    def test_capture_span_context_returns_context(self) -> None:
        """Should return SpanLinkContext with trace_id and span_id."""
        from backend.core.telemetry import capture_span_context

        with (
            patch("backend.core.telemetry.get_trace_id", return_value="trace123"),
            patch("backend.core.telemetry.get_span_id", return_value="span456"),
        ):
            ctx = capture_span_context()

        assert ctx is not None
        assert ctx.trace_id == "trace123"
        assert ctx.span_id == "span456"

    def test_capture_span_context_returns_none_when_no_trace(self) -> None:
        """Should return None when trace_id is not available."""
        from backend.core.telemetry import capture_span_context

        with (
            patch("backend.core.telemetry.get_trace_id", return_value=None),
            patch("backend.core.telemetry.get_span_id", return_value="span456"),
        ):
            ctx = capture_span_context()

        assert ctx is None

    def test_capture_span_context_returns_none_when_no_span(self) -> None:
        """Should return None when span_id is not available."""
        from backend.core.telemetry import capture_span_context

        with (
            patch("backend.core.telemetry.get_trace_id", return_value="trace123"),
            patch("backend.core.telemetry.get_span_id", return_value=None),
        ):
            ctx = capture_span_context()

        assert ctx is None


class TestCreateSpanWithLinks:
    """Tests for create_span_with_links function."""

    def test_create_span_with_links_returns_span(self) -> None:
        """Should create a span with links."""
        from backend.core.telemetry import SpanLinkContext, create_span_with_links

        links = [
            SpanLinkContext("0123456789abcdef0123456789abcdef", "0123456789abcdef"),
        ]

        span = create_span_with_links("test_span", links=links, test_attr="value")
        assert span is not None
        # The span should have set_attribute method
        assert hasattr(span, "set_attribute")

    def test_create_span_with_links_handles_no_links(self) -> None:
        """Should create span without links when none provided."""
        from backend.core.telemetry import create_span_with_links

        span = create_span_with_links("test_span", links=None)
        assert span is not None

    def test_create_span_with_links_handles_dict_links(self) -> None:
        """Should handle links provided as dictionaries."""
        from backend.core.telemetry import create_span_with_links

        links = [
            {"trace_id": "0123456789abcdef0123456789abcdef", "span_id": "0123456789abcdef"},
        ]

        span = create_span_with_links("test_span", links=links)
        assert span is not None

    def test_create_span_with_links_handles_invalid_links(self) -> None:
        """Should skip invalid links gracefully."""
        from backend.core.telemetry import create_span_with_links

        links = [
            None,  # None link
            {"trace_id": "invalid"},  # Missing span_id
            {"trace_id": "not-hex", "span_id": "also-not-hex"},  # Invalid hex
        ]

        # Should not raise
        span = create_span_with_links("test_span", links=links)
        assert span is not None


class TestTraceSpanWithLinks:
    """Tests for trace_span_with_links context manager."""

    def test_trace_span_with_links_basic(self) -> None:
        """Should work as a context manager."""
        from backend.core.telemetry import trace_span_with_links

        with trace_span_with_links("test_span", attr="value") as span:
            assert span is not None

    def test_trace_span_with_links_with_links(self) -> None:
        """Should create span with links."""
        from backend.core.telemetry import SpanLinkContext, trace_span_with_links

        links = [
            SpanLinkContext("0123456789abcdef0123456789abcdef", "0123456789abcdef"),
        ]

        with trace_span_with_links("test_span", links=links) as span:
            assert span is not None

    def test_trace_span_with_links_records_exception(self) -> None:
        """Should record exception when error occurs."""
        from backend.core.telemetry import trace_span_with_links

        with (
            patch("backend.core.telemetry.record_exception") as mock_record,
            pytest.raises(ValueError),
        ):
            with trace_span_with_links("test_span"):
                raise ValueError("Test error")

        mock_record.assert_called_once()


# =============================================================================
# BatchSpanProcessor Configuration Tests (NEM-3433)
# =============================================================================


class TestBatchSpanProcessorSettings:
    """Tests for BatchSpanProcessor configuration settings."""

    def test_batch_settings_have_defaults(self) -> None:
        """BatchSpanProcessor settings should have sensible defaults."""
        from backend.core.config import Settings

        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test"
            },
        ):
            settings = Settings()

        # Verify new settings exist with defaults
        assert settings.otel_batch_max_queue_size == 8192
        assert settings.otel_batch_max_export_batch_size == 1024
        assert settings.otel_batch_schedule_delay_ms == 2000
        assert settings.otel_batch_export_timeout_ms == 30000

    def test_batch_settings_can_be_configured(self) -> None:
        """BatchSpanProcessor settings should be configurable via environment."""
        from backend.core.config import Settings

        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                "OTEL_BATCH_MAX_QUEUE_SIZE": "16384",
                "OTEL_BATCH_MAX_EXPORT_BATCH_SIZE": "2048",
                "OTEL_BATCH_SCHEDULE_DELAY_MS": "5000",
                "OTEL_BATCH_EXPORT_TIMEOUT_MS": "60000",
            },
        ):
            settings = Settings()

        assert settings.otel_batch_max_queue_size == 16384
        assert settings.otel_batch_max_export_batch_size == 2048
        assert settings.otel_batch_schedule_delay_ms == 5000
        assert settings.otel_batch_export_timeout_ms == 60000

    def test_batch_settings_validation(self) -> None:
        """BatchSpanProcessor settings should validate bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test max_queue_size below minimum
        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_BATCH_MAX_QUEUE_SIZE": "100",  # Below minimum (512)
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()

        # Test max_export_batch_size above maximum
        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_BATCH_MAX_EXPORT_BATCH_SIZE": "10000",  # Above maximum (8192)
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()


# =============================================================================
# NEM-3792: OTEL Logging Instrumentation Tests
# =============================================================================


class TestOTELLoggingSetup:
    """Tests for _setup_otel_logging function."""

    def test_setup_otel_logging_instruments_logging(self) -> None:
        """Should instrument Python logging when OTEL logging is available."""
        from backend.core.telemetry import _setup_otel_logging

        mock_instrumentor = MagicMock()

        with patch(
            "opentelemetry.instrumentation.logging.LoggingInstrumentor",
            return_value=mock_instrumentor,
        ):
            _setup_otel_logging("test-service")

            mock_instrumentor.instrument.assert_called_once_with(set_logging_format=False)

    def test_setup_otel_logging_handles_import_error(self) -> None:
        """Should handle ImportError gracefully when OTEL logging is not available."""
        import builtins

        from backend.core.telemetry import _setup_otel_logging

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "opentelemetry.instrumentation.logging":
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Should not raise
            _setup_otel_logging("test-service")

    def test_setup_otel_logging_handles_exception(self) -> None:
        """Should handle general exceptions gracefully."""
        from backend.core.telemetry import _setup_otel_logging

        mock_instrumentor = MagicMock()
        mock_instrumentor.instrument.side_effect = Exception("Instrumentation failed")

        with patch(
            "opentelemetry.instrumentation.logging.LoggingInstrumentor",
            return_value=mock_instrumentor,
        ):
            # Should not raise
            _setup_otel_logging("test-service")


class TestShutdownTelemetryWithLogging:
    """Tests for shutdown_telemetry including logging uninstrumentation."""

    def test_shutdown_telemetry_uninstruments_logging(self) -> None:
        """Should uninstrument logging along with other instrumentors."""
        from opentelemetry.sdk.trace import TracerProvider as RealTracerProvider

        import backend.core.telemetry as telemetry_module

        # Setup initialized state
        mock_provider = MagicMock(spec=RealTracerProvider)
        mock_provider.shutdown = MagicMock()
        telemetry_module._is_initialized = True
        telemetry_module._tracer_provider = mock_provider

        with (
            patch("opentelemetry.instrumentation.fastapi.FastAPIInstrumentor") as mock_fastapi,
            patch("opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor") as mock_httpx,
            patch(
                "opentelemetry.instrumentation.sqlalchemy.SQLAlchemyInstrumentor"
            ) as mock_sqlalchemy,
            patch("opentelemetry.instrumentation.redis.RedisInstrumentor") as mock_redis,
            patch("opentelemetry.instrumentation.logging.LoggingInstrumentor") as mock_logging,
        ):
            from backend.core.telemetry import shutdown_telemetry

            shutdown_telemetry()

            # Verify logging uninstrument was called
            mock_logging.return_value.uninstrument.assert_called_once()

            # Verify other uninstrument calls
            mock_fastapi.uninstrument.assert_called_once()
            mock_httpx.return_value.uninstrument.assert_called_once()
            mock_sqlalchemy.return_value.uninstrument.assert_called_once()
            mock_redis.return_value.uninstrument.assert_called_once()

        # Cleanup
        telemetry_module._is_initialized = False
        telemetry_module._tracer_provider = None
