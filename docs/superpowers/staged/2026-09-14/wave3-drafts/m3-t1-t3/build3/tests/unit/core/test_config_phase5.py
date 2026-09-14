"""TDD Tests for Phase 5 configuration additions.

Phase 5: Batching and Scheduling Optimization
Tests written BEFORE implementation (Red Phase).

Tests for new configuration options:
- Priority queue settings
- Batch coalescing settings
- Load test defaults
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestPriorityQueueSettings:
    """Test priority queue configuration options."""

    def test_priority_queue_enabled_default(self) -> None:
        """Priority queue should be disabled by default."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "priority_queue_enabled")
        assert settings.priority_queue_enabled is False

    def test_priority_queue_enabled_env_var(self) -> None:
        """Priority queue can be enabled via env var."""
        from backend.core.config import Settings

        with patch.dict(os.environ, {"PRIORITY_QUEUE_ENABLED": "true"}):
            settings = Settings()

            assert settings.priority_queue_enabled is True

    def test_priority_high_threshold(self) -> None:
        """High priority threshold configuration."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "priority_queue_high_threshold")
        # Default should prioritize high-confidence detections
        assert 0.0 <= settings.priority_queue_high_threshold <= 1.0

    def test_priority_high_threshold_env_var(self) -> None:
        """High threshold can be configured via env var."""
        from backend.core.config import Settings

        with patch.dict(os.environ, {"PRIORITY_QUEUE_HIGH_THRESHOLD": "0.85"}):
            settings = Settings()

            assert settings.priority_queue_high_threshold == 0.85

    def test_priority_critical_object_types(self) -> None:
        """Critical object types for P0 priority."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "priority_critical_object_types")
        # Weapons should be critical by default
        assert "gun" in settings.priority_critical_object_types
        assert "knife" in settings.priority_critical_object_types

    def test_priority_night_boost_enabled(self) -> None:
        """Night-time priority boost configuration."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "priority_night_boost_enabled")
        # Unknown persons at night should get priority boost by default
        assert settings.priority_night_boost_enabled is True


class TestBatchCoalescingSettings:
    """Test batch coalescing configuration options."""

    def test_coalescing_enabled_default(self) -> None:
        """Coalescing should be disabled by default."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "batch_coalescing_enabled")
        assert settings.batch_coalescing_enabled is False

    def test_coalescing_enabled_env_var(self) -> None:
        """Coalescing can be enabled via env var."""
        from backend.core.config import Settings

        with patch.dict(os.environ, {"BATCH_COALESCING_ENABLED": "true"}):
            settings = Settings()

            assert settings.batch_coalescing_enabled is True

    def test_coalesce_window_seconds(self) -> None:
        """Coalescing window duration configuration."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "coalesce_window_seconds")
        # Should have a reasonable default (e.g., 5-30 seconds)
        assert 1 <= settings.coalesce_window_seconds <= 60

    def test_coalesce_window_env_var(self) -> None:
        """Coalescing window can be configured via env var."""
        from backend.core.config import Settings

        with patch.dict(os.environ, {"COALESCE_WINDOW_SECONDS": "15"}):
            settings = Settings()

            assert settings.coalesce_window_seconds == 15

    def test_coalesce_max_batch_size(self) -> None:
        """Maximum batch size after coalescing."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "coalesce_max_batch_size")
        # Should not exceed existing batch_max_detections
        assert settings.coalesce_max_batch_size <= settings.batch_max_detections

    def test_coalesce_confidence_tolerance(self) -> None:
        """Confidence tolerance for compatibility."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "coalesce_confidence_tolerance")
        # Reasonable tolerance (e.g., 0.05-0.2)
        assert 0.0 < settings.coalesce_confidence_tolerance <= 0.5

    def test_coalesce_same_camera_required(self) -> None:
        """Whether same camera is required for coalescing."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "coalesce_same_camera_required")
        # Should require same camera by default for safety
        assert settings.coalesce_same_camera_required is True


class TestLoadTestSettings:
    """Test load test default configuration."""

    def test_load_test_default_duration(self) -> None:
        """Default duration for load tests."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "load_test_default_duration_seconds")
        assert settings.load_test_default_duration_seconds > 0

    def test_load_test_default_rps(self) -> None:
        """Default requests per second for load tests."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "load_test_default_rps")
        assert settings.load_test_default_rps > 0

    def test_load_test_burst_defaults(self) -> None:
        """Default burst test parameters."""
        from backend.core.config import Settings

        settings = Settings()

        assert hasattr(settings, "load_test_default_burst_size")
        assert hasattr(settings, "load_test_default_burst_interval")

        assert settings.load_test_default_burst_size > 0
        assert settings.load_test_default_burst_interval > 0


class TestConfigValidation:
    """Test configuration validation rules."""

    def test_coalesce_window_bounds(self) -> None:
        """Coalesce window must be within bounds."""
        from backend.core.config import Settings
        from pydantic import ValidationError

        # Should not allow negative
        with (
            patch.dict(os.environ, {"COALESCE_WINDOW_SECONDS": "-5"}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_priority_threshold_bounds(self) -> None:
        """Priority threshold must be 0-1."""
        from backend.core.config import Settings
        from pydantic import ValidationError

        # Should not allow > 1.0
        with (
            patch.dict(os.environ, {"PRIORITY_QUEUE_HIGH_THRESHOLD": "1.5"}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_coalesce_tolerance_bounds(self) -> None:
        """Confidence tolerance must be reasonable."""
        from backend.core.config import Settings
        from pydantic import ValidationError

        # Should not allow > 0.5 (50% tolerance is too loose)
        with (
            patch.dict(os.environ, {"COALESCE_CONFIDENCE_TOLERANCE": "0.8"}),
            pytest.raises(ValidationError),
        ):
            Settings()

    def test_coalesce_max_size_bounds(self) -> None:
        """Coalesce max size must not exceed batch limit."""
        from backend.core.config import Settings

        settings = Settings()

        # Validator should ensure coalesce_max_batch_size <= batch_max_detections
        assert settings.coalesce_max_batch_size <= settings.batch_max_detections


class TestConfigIntegration:
    """Test configuration integration with services."""

    def test_settings_accessible_via_get_settings(self) -> None:
        """New settings accessible via get_settings()."""
        from backend.core.config import get_settings

        settings = get_settings()

        # All Phase 5 settings should be accessible
        assert hasattr(settings, "priority_queue_enabled")
        assert hasattr(settings, "batch_coalescing_enabled")

    def test_settings_repr_safe(self) -> None:
        """Settings repr should not expose sensitive data."""
        from backend.core.config import Settings

        settings = Settings()
        repr_str = repr(settings)

        # Should not contain any password/secret values
        assert "password" not in repr_str.lower() or "***" in repr_str
