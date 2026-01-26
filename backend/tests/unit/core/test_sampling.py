"""Tests for priority-based trace sampling.

NEM-3793: Tests for the sampling module that provides intelligent trace sampling
based on priority rules (errors, high-risk events, endpoint importance).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.sampling import (
    DEFAULT_BACKGROUND_PATHS,
    DEFAULT_HIGH_PRIORITY_PATHS,
    DEFAULT_MEDIUM_PRIORITY_PATHS,
    ParentBasedPrioritySampler,
    PriorityBasedSampler,
    SamplingConfig,
    create_otel_sampler,
    create_priority_sampler,
)


class TestSamplingConfig:
    """Tests for SamplingConfig class."""

    def test_default_values(self) -> None:
        """SamplingConfig should have sensible defaults."""
        config = SamplingConfig()

        assert config.error_rate == 1.0
        assert config.high_risk_rate == 1.0
        assert config.high_priority_rate == 1.0
        assert config.medium_priority_rate == 0.5
        assert config.background_rate == 0.1
        assert config.default_rate == 0.1

        assert config.high_priority_paths == DEFAULT_HIGH_PRIORITY_PATHS
        assert config.medium_priority_paths == DEFAULT_MEDIUM_PRIORITY_PATHS
        assert config.background_paths == DEFAULT_BACKGROUND_PATHS

    def test_custom_rates(self) -> None:
        """SamplingConfig should accept custom rates."""
        config = SamplingConfig(
            error_rate=0.9,
            high_risk_rate=0.8,
            high_priority_rate=0.7,
            medium_priority_rate=0.6,
            background_rate=0.2,
            default_rate=0.15,
        )

        assert config.error_rate == 0.9
        assert config.high_risk_rate == 0.8
        assert config.high_priority_rate == 0.7
        assert config.medium_priority_rate == 0.6
        assert config.background_rate == 0.2
        assert config.default_rate == 0.15

    def test_rate_clamping(self) -> None:
        """SamplingConfig should clamp rates to [0.0, 1.0]."""
        config = SamplingConfig(
            error_rate=1.5,  # Above max
            high_risk_rate=-0.5,  # Below min
            default_rate=2.0,  # Above max
        )

        assert config.error_rate == 1.0
        assert config.high_risk_rate == 0.0
        assert config.default_rate == 1.0

    def test_custom_paths(self) -> None:
        """SamplingConfig should accept custom path lists."""
        custom_high = ["/api/custom", "/api/special"]
        custom_medium = ["/api/other"]
        custom_background = ["/internal"]

        config = SamplingConfig(
            high_priority_paths=custom_high,
            medium_priority_paths=custom_medium,
            background_paths=custom_background,
        )

        assert config.high_priority_paths == custom_high
        assert config.medium_priority_paths == custom_medium
        assert config.background_paths == custom_background

    def test_from_env_defaults(self) -> None:
        """SamplingConfig.from_env should use defaults when env vars not set."""
        with patch.dict("os.environ", {}, clear=True):
            config = SamplingConfig.from_env()

        assert config.error_rate == 1.0
        assert config.default_rate == 0.1

    def test_from_env_with_values(self) -> None:
        """SamplingConfig.from_env should read from environment variables."""
        env_vars = {
            "OTEL_SAMPLING_ERROR_RATE": "0.9",
            "OTEL_SAMPLING_HIGH_RISK_RATE": "0.8",
            "OTEL_SAMPLING_HIGH_PRIORITY_RATE": "0.7",
            "OTEL_SAMPLING_MEDIUM_PRIORITY_RATE": "0.4",
            "OTEL_SAMPLING_BACKGROUND_RATE": "0.05",
            "OTEL_SAMPLING_DEFAULT_RATE": "0.2",
            "OTEL_SAMPLING_HIGH_PRIORITY_PATHS": "/api/v1/events,/api/v1/alerts",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = SamplingConfig.from_env()

        assert config.error_rate == 0.9
        assert config.high_risk_rate == 0.8
        assert config.high_priority_rate == 0.7
        assert config.medium_priority_rate == 0.4
        assert config.background_rate == 0.05
        assert config.default_rate == 0.2
        assert config.high_priority_paths == ["/api/v1/events", "/api/v1/alerts"]

    def test_from_env_invalid_rate(self) -> None:
        """SamplingConfig.from_env should handle invalid rate values."""
        env_vars = {
            "OTEL_SAMPLING_ERROR_RATE": "not_a_number",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = SamplingConfig.from_env()

        # Should fall back to default
        assert config.error_rate == 1.0

    def test_from_env_empty_paths(self) -> None:
        """SamplingConfig.from_env should handle empty paths gracefully."""
        env_vars = {
            "OTEL_SAMPLING_HIGH_PRIORITY_PATHS": "",
        }

        with patch.dict("os.environ", env_vars, clear=True):
            config = SamplingConfig.from_env()

        # Should fall back to defaults
        assert config.high_priority_paths == DEFAULT_HIGH_PRIORITY_PATHS


class TestPriorityBasedSampler:
    """Tests for PriorityBasedSampler class."""

    def test_initialization(self) -> None:
        """PriorityBasedSampler should initialize with config."""
        config = SamplingConfig()
        sampler = PriorityBasedSampler(config)

        assert sampler.config == config
        assert "PriorityBasedSampler" in sampler.get_description()

    def test_initialization_without_config(self) -> None:
        """PriorityBasedSampler should load config from env when not provided."""
        sampler = PriorityBasedSampler()
        assert sampler.config is not None

    def test_error_trace_sampling(self) -> None:
        """Error traces should be sampled at error_rate."""
        config = SamplingConfig(error_rate=1.0)
        sampler = PriorityBasedSampler(config)

        # Test various error indicators
        error_attrs = [
            {"error": True},
            {"otel.status_code": "ERROR"},
            {"http.status_code": 500},
            {"http.status_code": 503},
            {"exception.type": "ValueError"},
        ]

        for attrs in error_attrs:
            decision, _ = sampler.should_sample(None, 12345, "test_span", attributes=attrs)
            # Check that it's a RECORD_AND_SAMPLE decision
            from opentelemetry.sdk.trace.sampling import Decision

            assert decision == Decision.RECORD_AND_SAMPLE, f"Expected RECORD_AND_SAMPLE for {attrs}"

    def test_high_risk_event_sampling(self) -> None:
        """High-risk events should be sampled at high_risk_rate."""
        config = SamplingConfig(high_risk_rate=1.0)
        sampler = PriorityBasedSampler(config)

        # Test high-risk indicators
        high_risk_attrs = [
            {"risk_score": 70},
            {"risk_score": 100},
            {"event.risk_score": 75},
            {"alert.created": True},
            {"alert.triggered": True},
            {"ai.operation": "analyze"},
            {"ai.operation": "detect"},
            {"ai.operation": "alert"},
        ]

        for attrs in high_risk_attrs:
            decision, _ = sampler.should_sample(None, 12345, "test_span", attributes=attrs)
            from opentelemetry.sdk.trace.sampling import Decision

            assert decision == Decision.RECORD_AND_SAMPLE, f"Expected RECORD_AND_SAMPLE for {attrs}"

    def test_high_priority_path_sampling(self) -> None:
        """High-priority paths should be sampled at high_priority_rate."""
        config = SamplingConfig(high_priority_rate=1.0, default_rate=0.0)
        sampler = PriorityBasedSampler(config)

        high_priority_paths = [
            "/api/events",
            "/api/events/123",
            "/api/alerts",
            "/api/alerts/456",
            "/api/detections",
        ]

        for path in high_priority_paths:
            decision, _ = sampler.should_sample(
                None, 12345, f"GET {path}", attributes={"http.route": path}
            )
            from opentelemetry.sdk.trace.sampling import Decision

            assert decision == Decision.RECORD_AND_SAMPLE, f"Expected RECORD_AND_SAMPLE for {path}"

    def test_background_path_sampling(self) -> None:
        """Background paths should be sampled at background_rate."""
        # Use rate of 0 to ensure DROP decision
        config = SamplingConfig(background_rate=0.0)
        sampler = PriorityBasedSampler(config)

        background_paths = ["/health", "/metrics", "/api/health"]

        for path in background_paths:
            decision, _ = sampler.should_sample(
                None, 12345, f"GET {path}", attributes={"http.route": path}
            )
            from opentelemetry.sdk.trace.sampling import Decision

            assert decision == Decision.DROP, f"Expected DROP for background path {path}"

    def test_default_sampling(self) -> None:
        """Unclassified spans should use default_rate."""
        # Use rate of 0 to ensure DROP decision
        config = SamplingConfig(default_rate=0.0)
        sampler = PriorityBasedSampler(config)

        decision, _ = sampler.should_sample(
            None, 12345, "custom_operation", attributes={"http.route": "/api/unknown"}
        )
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.DROP

    def test_path_extraction_from_attributes(self) -> None:
        """Should extract path from http.route attribute."""
        config = SamplingConfig(high_priority_rate=1.0)
        sampler = PriorityBasedSampler(config)

        # http.route takes precedence
        decision, _ = sampler.should_sample(
            None, 12345, "some_operation", attributes={"http.route": "/api/events"}
        )
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE

    def test_path_extraction_from_url_path(self) -> None:
        """Should extract path from url.path attribute."""
        config = SamplingConfig(high_priority_rate=1.0)
        sampler = PriorityBasedSampler(config)

        decision, _ = sampler.should_sample(
            None, 12345, "some_operation", attributes={"url.path": "/api/events"}
        )
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE

    def test_path_extraction_from_span_name(self) -> None:
        """Should extract path from span name like 'GET /api/events'."""
        config = SamplingConfig(high_priority_rate=1.0)
        sampler = PriorityBasedSampler(config)

        decision, _ = sampler.should_sample(None, 12345, "GET /api/events", attributes={})
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE

    def test_query_string_removal(self) -> None:
        """Should remove query strings from paths."""
        config = SamplingConfig(high_priority_rate=1.0)
        sampler = PriorityBasedSampler(config)

        decision, _ = sampler.should_sample(
            None, 12345, "GET /api/events?page=1", attributes={"http.route": "/api/events?filter=x"}
        )
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE

    def test_sampling_attributes_included(self) -> None:
        """Should include sampling metadata in attributes when sampled."""
        config = SamplingConfig(error_rate=1.0)
        sampler = PriorityBasedSampler(config)

        decision, attrs = sampler.should_sample(
            None, 12345, "test_span", attributes={"error": True}
        )
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE
        assert attrs["sampling.rate"] == 1.0
        assert attrs["sampling.priority"] == "error"

    def test_priority_classification(self) -> None:
        """Should correctly classify span priorities."""
        config = SamplingConfig()
        sampler = PriorityBasedSampler(config)

        # Test priority classifications
        test_cases = [
            ({"error": True}, "error"),
            ({"risk_score": 80}, "high_risk"),
            ({"http.route": "/api/events"}, "high_priority"),
            ({"http.route": "/api/timeline"}, "medium_priority"),
            ({"http.route": "/health"}, "background"),
            ({"http.route": "/api/unknown"}, "default"),
        ]

        for attrs, expected_priority in test_cases:
            decision, result_attrs = sampler.should_sample(
                None, 12345, "test_span", attributes=attrs
            )
            # Check priority if sampled
            if result_attrs:
                assert result_attrs.get("sampling.priority") == expected_priority, (
                    f"Expected {expected_priority} for {attrs}"
                )


class TestParentBasedPrioritySampler:
    """Tests for ParentBasedPrioritySampler class."""

    def test_initialization(self) -> None:
        """ParentBasedPrioritySampler should wrap root sampler."""
        root_sampler = PriorityBasedSampler()
        sampler = ParentBasedPrioritySampler(root_sampler)

        assert sampler.root_sampler == root_sampler
        assert "ParentBasedPrioritySampler" in sampler.get_description()

    def test_no_parent_uses_root_sampler(self) -> None:
        """Should use root sampler when no parent context."""
        config = SamplingConfig(error_rate=1.0)
        root_sampler = PriorityBasedSampler(config)
        sampler = ParentBasedPrioritySampler(root_sampler)

        decision, _ = sampler.should_sample(None, 12345, "test_span", attributes={"error": True})
        from opentelemetry.sdk.trace.sampling import Decision

        assert decision == Decision.RECORD_AND_SAMPLE

    def test_sampled_parent_always_samples(self) -> None:
        """Should always sample when parent is sampled."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace.sampling import Decision
        from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

        config = SamplingConfig(default_rate=0.0)  # Would drop without parent
        root_sampler = PriorityBasedSampler(config)
        sampler = ParentBasedPrioritySampler(root_sampler)

        # Create a sampled parent context
        parent_span_context = SpanContext(
            trace_id=123456789,
            span_id=987654321,
            is_remote=False,
            trace_flags=TraceFlags(0x01),  # SAMPLED
        )
        parent_span = NonRecordingSpan(parent_span_context)

        with trace.use_span(parent_span):
            parent_context = trace.get_current_span().get_span_context()
            # Create a mock context that returns our parent
            mock_context = MagicMock()

            with patch("opentelemetry.trace.get_current_span") as mock_get_span:
                mock_span = MagicMock()
                mock_span.get_span_context.return_value = parent_span_context
                mock_get_span.return_value = mock_span

                decision, attrs = sampler.should_sample(
                    mock_context, 12345, "child_span", attributes={}
                )

                assert decision == Decision.RECORD_AND_SAMPLE
                assert attrs.get("sampling.inherited") is True

    def test_non_sampled_parent_drops(self) -> None:
        """Should drop when parent is not sampled."""
        from opentelemetry.sdk.trace.sampling import Decision
        from opentelemetry.trace import SpanContext, TraceFlags

        config = SamplingConfig(error_rate=1.0)  # Would sample errors
        root_sampler = PriorityBasedSampler(config)
        sampler = ParentBasedPrioritySampler(root_sampler)

        # Create a non-sampled parent context
        parent_span_context = SpanContext(
            trace_id=123456789,
            span_id=987654321,
            is_remote=False,
            trace_flags=TraceFlags(0x00),  # NOT SAMPLED
        )

        mock_context = MagicMock()

        with patch("opentelemetry.trace.get_current_span") as mock_get_span:
            mock_span = MagicMock()
            mock_span.get_span_context.return_value = parent_span_context
            mock_get_span.return_value = mock_span

            decision, _ = sampler.should_sample(
                mock_context,
                12345,
                "child_span",
                attributes={"error": True},  # Error but parent not sampled
            )

            assert decision == Decision.DROP


class TestCreatePrioritySampler:
    """Tests for create_priority_sampler function."""

    def test_creates_sampler_without_settings(self) -> None:
        """Should create sampler from environment when no settings."""
        sampler = create_priority_sampler()
        assert isinstance(sampler, ParentBasedPrioritySampler)

    def test_creates_sampler_with_settings(self) -> None:
        """Should create sampler using Settings values."""
        mock_settings = MagicMock()
        mock_settings.otel_sampling_error_rate = 0.9
        mock_settings.otel_sampling_high_risk_rate = 0.8
        mock_settings.otel_sampling_high_priority_rate = 0.7
        mock_settings.otel_sampling_medium_priority_rate = 0.6
        mock_settings.otel_sampling_background_rate = 0.3
        mock_settings.otel_sampling_default_rate = 0.2
        mock_settings.otel_trace_sample_rate = 1.0

        sampler = create_priority_sampler(mock_settings)

        assert isinstance(sampler, ParentBasedPrioritySampler)
        assert sampler.root_sampler.config.error_rate == 0.9
        assert sampler.root_sampler.config.high_risk_rate == 0.8

    def test_applies_global_scaling_factor(self) -> None:
        """Should scale rates when otel_trace_sample_rate < 1.0."""
        mock_settings = MagicMock()
        mock_settings.otel_sampling_error_rate = 1.0
        mock_settings.otel_sampling_high_risk_rate = 1.0
        mock_settings.otel_sampling_high_priority_rate = 1.0
        mock_settings.otel_sampling_medium_priority_rate = 0.5
        mock_settings.otel_sampling_background_rate = 0.2
        mock_settings.otel_sampling_default_rate = 0.3
        mock_settings.otel_trace_sample_rate = 0.1  # Global scaling factor

        sampler = create_priority_sampler(mock_settings)

        # Error/high-risk/high-priority should remain unchanged
        assert sampler.root_sampler.config.error_rate == 1.0
        assert sampler.root_sampler.config.high_risk_rate == 1.0
        assert sampler.root_sampler.config.high_priority_rate == 1.0

        # Medium, background, default should be scaled down
        assert sampler.root_sampler.config.medium_priority_rate == 0.1  # min(0.5, 0.1)
        assert sampler.root_sampler.config.background_rate == 0.1  # min(0.2, 0.1)
        assert sampler.root_sampler.config.default_rate == 0.1  # min(0.3, 0.1)


class TestCreateOtelSampler:
    """Tests for create_otel_sampler function."""

    def test_creates_otel_sampler(self) -> None:
        """Should create an OpenTelemetry SDK-compatible sampler."""
        from opentelemetry.sdk.trace.sampling import ParentBased

        sampler = create_otel_sampler()
        assert isinstance(sampler, ParentBased)

    def test_creates_otel_sampler_with_settings(self) -> None:
        """Should create sampler using Settings values."""
        from opentelemetry.sdk.trace.sampling import ParentBased

        mock_settings = MagicMock()
        mock_settings.otel_sampling_error_rate = 1.0
        mock_settings.otel_sampling_high_risk_rate = 1.0
        mock_settings.otel_sampling_high_priority_rate = 1.0
        mock_settings.otel_sampling_medium_priority_rate = 0.5
        mock_settings.otel_sampling_background_rate = 0.1
        mock_settings.otel_sampling_default_rate = 0.1
        mock_settings.otel_trace_sample_rate = 1.0

        sampler = create_otel_sampler(mock_settings)
        assert isinstance(sampler, ParentBased)

    def test_otel_sampler_handles_import_error(self) -> None:
        """Should return None when OpenTelemetry SDK not available."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("opentelemetry.sdk"):
                raise ImportError("Module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = create_otel_sampler()
            assert result is None


class TestSettingsIntegration:
    """Integration tests for sampling with Settings."""

    def test_settings_has_sampling_fields(self) -> None:
        """Settings should have all sampling configuration fields."""
        from backend.core.config import Settings

        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test"
            },
        ):
            settings = Settings()

        # Verify all sampling settings exist with defaults
        assert hasattr(settings, "otel_sampling_error_rate")
        assert hasattr(settings, "otel_sampling_high_risk_rate")
        assert hasattr(settings, "otel_sampling_high_priority_rate")
        assert hasattr(settings, "otel_sampling_medium_priority_rate")
        assert hasattr(settings, "otel_sampling_background_rate")
        assert hasattr(settings, "otel_sampling_default_rate")

        # Check default values
        assert settings.otel_sampling_error_rate == 1.0
        assert settings.otel_sampling_high_risk_rate == 1.0
        assert settings.otel_sampling_high_priority_rate == 1.0
        assert settings.otel_sampling_medium_priority_rate == 0.5
        assert settings.otel_sampling_background_rate == 0.1
        assert settings.otel_sampling_default_rate == 0.1

    def test_settings_sampling_validation(self) -> None:
        """Settings should validate sampling rate bounds."""
        from pydantic import ValidationError

        from backend.core.config import Settings

        # Test above maximum
        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_SAMPLING_ERROR_RATE": "1.5",  # Invalid - > 1.0
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()

        # Test below minimum
        with (
            patch.dict(
                "os.environ",
                {
                    # pragma: allowlist nextline secret
                    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                    "OTEL_SAMPLING_DEFAULT_RATE": "-0.1",  # Invalid - < 0.0
                },
            ),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_settings_sampling_can_be_configured(self) -> None:
        """Settings sampling rates should be configurable via environment."""
        from backend.core.config import Settings

        with patch.dict(
            "os.environ",
            {
                # pragma: allowlist nextline secret
                "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
                "OTEL_SAMPLING_ERROR_RATE": "0.95",
                "OTEL_SAMPLING_HIGH_RISK_RATE": "0.9",
                "OTEL_SAMPLING_HIGH_PRIORITY_RATE": "0.85",
                "OTEL_SAMPLING_MEDIUM_PRIORITY_RATE": "0.4",
                "OTEL_SAMPLING_BACKGROUND_RATE": "0.05",
                "OTEL_SAMPLING_DEFAULT_RATE": "0.08",
            },
        ):
            settings = Settings()

        assert settings.otel_sampling_error_rate == 0.95
        assert settings.otel_sampling_high_risk_rate == 0.9
        assert settings.otel_sampling_high_priority_rate == 0.85
        assert settings.otel_sampling_medium_priority_rate == 0.4
        assert settings.otel_sampling_background_rate == 0.05
        assert settings.otel_sampling_default_rate == 0.08
