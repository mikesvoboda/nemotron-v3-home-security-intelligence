"""Unit tests for OpenTelemetry tracing in pipeline workers (NEM-1467).

Tests cover:
- Tracer initialization in pipeline_workers
- Telemetry function imports
- Code structure verification for span creation

Note: Integration tests for actual span creation require database setup.
These unit tests verify the instrumentation code is in place.

R8 (2026-09-29) retired nemotron_analyzer, so the analyzer-side tracer and
LLM-inference pins went with it — the module no longer exists to instrument.
"""

import inspect

# =============================================================================
# Pipeline Workers Tracing Tests
# =============================================================================


class TestPipelineWorkersTracerInitialization:
    """Test tracer initialization in pipeline_workers module."""

    def test_tracer_is_initialized(self):
        """Test that the tracer is initialized at module level."""
        from backend.services import pipeline_workers

        assert hasattr(pipeline_workers, "tracer")
        # Tracer should be either a real tracer or NoOpTracer
        assert pipeline_workers.tracer is not None

    def test_get_tracer_returns_tracer(self):
        """Test that get_tracer returns a valid tracer."""
        from backend.core.telemetry import get_tracer

        tracer = get_tracer("test_module")
        assert tracer is not None
        # Should have start_as_current_span method
        assert hasattr(tracer, "start_as_current_span")


class TestDetectionProcessingSpan:
    """Test OpenTelemetry span creation for detection processing."""

    def test_detection_processing_span_code_exists(self):
        """Test that _process_detection_item has tracing instrumentation code."""
        from backend.services import pipeline_workers

        source = inspect.getsource(pipeline_workers.DetectionQueueWorker._process_detection_item)

        # Check for span creation
        assert "start_as_current_span" in source
        assert "detection_processing" in source

        # Check for span attributes
        assert "add_span_attributes" in source
        assert "camera_id" in source
        assert "pipeline_stage" in source

    def test_detection_processing_has_exception_recording(self):
        """Test that detection processing records exceptions on span."""
        from backend.services import pipeline_workers

        source = inspect.getsource(pipeline_workers.DetectionQueueWorker._process_detection_item)

        # Check for exception recording
        assert "record_exception" in source


class TestAnalysisProcessingSpan:
    """Test OpenTelemetry span creation for analysis processing."""

    def test_analysis_processing_span_code_exists(self):
        """Test that _process_analysis_item has tracing instrumentation code."""
        from backend.services import pipeline_workers

        source = inspect.getsource(pipeline_workers.AnalysisQueueWorker._process_analysis_item)

        # Check for span creation
        assert "start_as_current_span" in source
        assert "analysis_processing" in source

        # Check for span attributes
        assert "add_span_attributes" in source
        assert "batch_id" in source
        assert "detection_count" in source
        assert "pipeline_stage" in source

    def test_analysis_processing_has_exception_recording(self):
        """Test that analysis processing records exceptions on span."""
        from backend.services import pipeline_workers

        source = inspect.getsource(pipeline_workers.AnalysisQueueWorker._process_analysis_item)

        # Check for exception recording
        assert "record_exception" in source


class TestTelemetryImports:
    """Test that telemetry functions are properly imported."""

    def test_pipeline_workers_imports_telemetry(self):
        """Test that pipeline_workers imports telemetry functions."""
        from backend.services import pipeline_workers

        assert hasattr(pipeline_workers, "add_span_attributes")
        assert hasattr(pipeline_workers, "get_tracer")
        assert hasattr(pipeline_workers, "record_exception")
        assert hasattr(pipeline_workers, "tracer")
