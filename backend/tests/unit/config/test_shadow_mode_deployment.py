"""Unit tests for Shadow Mode Deployment Configuration (NEM-3337).

These tests cover Phase 7.1 of the Nemotron Prompt Improvements epic:
1. Shadow mode configuration for prompt comparison
2. Parallel execution configuration for old and new prompts
3. Comparison metrics logging configuration
4. Latency monitoring with threshold warnings

TDD: Write tests first (RED), then implement to make them GREEN.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: Shadow Mode Deployment Configuration
# =============================================================================


class TestShadowModeDeploymentConfig:
    """Tests for shadow mode deployment configuration."""

    def test_create_shadow_mode_deployment_config(self):
        """Test creating a shadow mode deployment configuration."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig()

        # Default values for deployment
        assert config.enabled is True
        assert config.control_prompt_name == "v1_original"
        assert config.treatment_prompt_name == "v2_calibrated"
        assert config.log_comparisons is True
        assert config.latency_warning_threshold_pct == 50.0
        assert config.experiment_name == "nemotron_prompt_v2_shadow"

    def test_shadow_mode_deployment_with_custom_values(self):
        """Test shadow mode deployment config with custom values."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(
            enabled=True,
            control_prompt_name="baseline_v1",
            treatment_prompt_name="improved_v2",
            log_comparisons=True,
            latency_warning_threshold_pct=30.0,
            experiment_name="custom_experiment",
        )

        assert config.control_prompt_name == "baseline_v1"
        assert config.treatment_prompt_name == "improved_v2"
        assert config.latency_warning_threshold_pct == 30.0
        assert config.experiment_name == "custom_experiment"

    def test_shadow_mode_deployment_can_be_disabled(self):
        """Test shadow mode deployment can be disabled."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(enabled=False)
        assert config.enabled is False


# =============================================================================
# Test: Parallel Prompt Execution Configuration
# =============================================================================


class TestParallelPromptExecutionConfig:
    """Tests for parallel prompt execution configuration."""

    def test_parallel_execution_enabled_by_default_in_shadow_mode(self):
        """Test parallel execution is enabled by default in shadow mode."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(enabled=True)

        # In shadow mode, both prompts should run
        assert config.run_both_prompts is True

    def test_control_prompt_result_is_primary(self):
        """Test control prompt result is used as primary result."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(enabled=True)
        assert config.primary_result_source == "control"

    def test_treatment_result_is_shadow_only(self):
        """Test treatment result is logged but not used as primary."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(enabled=True)
        assert config.treatment_result_usage == "comparison_only"


# =============================================================================
# Test: Comparison Metrics Logging Configuration
# =============================================================================


class TestComparisonMetricsLoggingConfig:
    """Tests for comparison metrics logging configuration."""

    def test_risk_score_comparison_enabled(self):
        """Test risk score comparison is enabled by default."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig()
        assert config.track_risk_score_diff is True

    def test_latency_comparison_enabled(self):
        """Test latency comparison is enabled by default."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig()
        assert config.track_latency_diff is True

    def test_memory_usage_tracking_optional(self):
        """Test memory usage tracking is configurable."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        # Default may be disabled for performance
        config = ShadowModeDeploymentConfig()
        assert hasattr(config, "track_memory_usage")

        # Can be enabled explicitly
        config_with_memory = ShadowModeDeploymentConfig(track_memory_usage=True)
        assert config_with_memory.track_memory_usage is True

    def test_error_rate_tracking_enabled(self):
        """Test error rate tracking is enabled by default."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig()
        assert config.track_error_rate is True


# =============================================================================
# Test: Latency Monitoring Configuration
# =============================================================================


class TestLatencyMonitoringConfig:
    """Tests for latency monitoring configuration with warning thresholds."""

    def test_default_latency_warning_threshold_is_50_percent(self):
        """Test default latency warning threshold is 50% slower."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig()
        assert config.latency_warning_threshold_pct == 50.0

    def test_custom_latency_warning_threshold(self):
        """Test custom latency warning threshold can be set."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=25.0)
        assert config.latency_warning_threshold_pct == 25.0

    def test_latency_warning_threshold_validation(self):
        """Test latency warning threshold validates positive values."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        # Should accept reasonable thresholds
        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=100.0)
        assert config.latency_warning_threshold_pct == 100.0

        # Should reject negative thresholds
        with pytest.raises(ValueError, match="latency_warning_threshold_pct"):
            ShadowModeDeploymentConfig(latency_warning_threshold_pct=-10.0)

    def test_check_latency_warning_triggers_above_threshold(self):
        """Test latency warning is triggered when treatment is slower than threshold."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=50.0)

        # Control: 100ms, Treatment: 160ms (60% slower - above 50% threshold)
        warning = config.check_latency_warning(
            control_latency_ms=100.0,
            treatment_latency_ms=160.0,
        )

        assert warning is not None
        assert warning.triggered is True
        assert warning.percentage_increase == pytest.approx(60.0, rel=0.01)
        assert "exceeds" in warning.message.lower()

    def test_check_latency_warning_not_triggered_below_threshold(self):
        """Test latency warning is not triggered when treatment is within threshold."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=50.0)

        # Control: 100ms, Treatment: 130ms (30% slower - below 50% threshold)
        warning = config.check_latency_warning(
            control_latency_ms=100.0,
            treatment_latency_ms=130.0,
        )

        assert warning is not None
        assert warning.triggered is False

    def test_check_latency_warning_handles_faster_treatment(self):
        """Test latency warning handles case when treatment is faster."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=50.0)

        # Control: 100ms, Treatment: 80ms (treatment is faster)
        warning = config.check_latency_warning(
            control_latency_ms=100.0,
            treatment_latency_ms=80.0,
        )

        # Should not trigger warning when treatment is faster
        assert warning is not None
        assert warning.triggered is False
        assert warning.percentage_increase < 0  # Negative means faster

    def test_check_latency_warning_handles_zero_control_latency(self):
        """Test latency warning handles edge case of zero control latency."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(latency_warning_threshold_pct=50.0)

        # Control: 0ms (edge case)
        warning = config.check_latency_warning(
            control_latency_ms=0.0,
            treatment_latency_ms=100.0,
        )

        # Should handle gracefully without division by zero
        assert warning is not None
        # When control is 0, any treatment time could be considered significant
        # Implementation may trigger or not based on design decision


# =============================================================================
# Test: Shadow Mode Comparison Result
# =============================================================================


class TestShadowModeComparisonResult:
    """Tests for shadow mode comparison result data structure."""

    def test_create_comparison_result(self):
        """Test creating a shadow mode comparison result."""
        from backend.config.shadow_mode_deployment import ShadowModeComparisonResult

        result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=5,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        assert result.control_risk_score == 50
        assert result.treatment_risk_score == 45
        assert result.risk_score_diff == 5
        assert result.latency_warning_triggered is False

    def test_comparison_result_tracks_camera_id(self):
        """Test comparison result tracks camera ID for filtering."""
        from backend.config.shadow_mode_deployment import ShadowModeComparisonResult

        result = ShadowModeComparisonResult(
            camera_id="front_door",
            control_risk_score=50,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=5,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        assert result.camera_id == "front_door"

    def test_comparison_result_tracks_errors(self):
        """Test comparison result tracks control and treatment errors."""
        from backend.config.shadow_mode_deployment import ShadowModeComparisonResult

        result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=None,  # Treatment failed
            control_latency_ms=100.0,
            treatment_latency_ms=None,
            risk_score_diff=None,
            latency_diff_ms=None,
            latency_increase_pct=None,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
            treatment_error="Connection timeout",
        )

        assert result.treatment_error == "Connection timeout"
        assert result.treatment_risk_score is None


# =============================================================================
# Test: Shadow Mode Metrics Recording
# =============================================================================


class TestShadowModeMetricsRecording:
    """Tests for shadow mode metrics recording functions."""

    def test_record_shadow_mode_comparison_metrics(self):
        """Test recording shadow mode comparison metrics."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        result = ShadowModeComparisonResult(
            camera_id="front_door",
            control_risk_score=50,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=5,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Should not raise
        with patch("backend.core.metrics.record_shadow_comparison") as mock_metric:
            record_shadow_mode_comparison(result)
            mock_metric.assert_called_once()

    def test_record_latency_warning_metric(self):
        """Test recording latency warning metric when threshold exceeded."""
        from backend.config.shadow_mode_deployment import record_latency_warning

        # Should not raise and should record metric
        # Patch at the import location in the function
        with patch("backend.core.metrics.record_prompt_latency") as mock_record:
            record_latency_warning(
                camera_id="front_door",
                control_latency_ms=100.0,
                treatment_latency_ms=160.0,
                threshold_pct=50.0,
            )
            # Latency should be recorded for both versions
            assert mock_record.call_count == 2
            # First call for control (v1)
            mock_record.assert_any_call("v1_control", 0.1)  # 100ms = 0.1s
            # Second call for treatment (v2)
            mock_record.assert_any_call("v2_treatment", 0.16)  # 160ms = 0.16s


# =============================================================================
# Test: Integration with Existing Infrastructure
# =============================================================================


class TestShadowModeDeploymentIntegration:
    """Tests for shadow mode deployment integration with existing infrastructure."""

    def test_shadow_mode_deployment_uses_prompt_experiment_config(self):
        """Test shadow mode deployment integrates with PromptExperimentConfig."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            create_deployment_from_experiment_config,
        )

        experiment_config = PromptExperimentConfig(
            shadow_mode=True,
            treatment_percentage=0.0,
            experiment_name="nemotron_prompt_v2",
        )

        deployment_config = create_deployment_from_experiment_config(experiment_config)

        assert deployment_config.enabled is True
        assert deployment_config.experiment_name == "nemotron_prompt_v2"

    def test_shadow_mode_deployment_respects_experiment_shadow_mode_flag(self):
        """Test deployment config respects experiment's shadow_mode flag."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            create_deployment_from_experiment_config,
        )

        # When shadow_mode is False in experiment, deployment should be disabled
        experiment_config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.5,
        )

        deployment_config = create_deployment_from_experiment_config(experiment_config)

        # Deployment for shadow mode should be disabled
        assert deployment_config.enabled is False

    def test_shadow_mode_deployment_uses_experiment_latency_threshold(self):
        """Test deployment config uses experiment's latency threshold."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            create_deployment_from_experiment_config,
        )

        experiment_config = PromptExperimentConfig(
            shadow_mode=True,
            max_latency_increase_pct=30.0,  # Custom threshold
        )

        deployment_config = create_deployment_from_experiment_config(experiment_config)

        assert deployment_config.latency_warning_threshold_pct == 30.0


# =============================================================================
# Test: Serialization
# =============================================================================


class TestShadowModeDeploymentSerialization:
    """Tests for shadow mode deployment configuration serialization."""

    def test_to_dict_returns_complete_config(self):
        """Test to_dict returns all configuration fields."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        config = ShadowModeDeploymentConfig(
            enabled=True,
            control_prompt_name="v1_original",
            treatment_prompt_name="v2_calibrated",
            latency_warning_threshold_pct=50.0,
        )

        result = config.to_dict()

        assert "enabled" in result
        assert "control_prompt_name" in result
        assert "treatment_prompt_name" in result
        assert "latency_warning_threshold_pct" in result
        assert "log_comparisons" in result
        assert "experiment_name" in result

    def test_from_dict_creates_config(self):
        """Test from_dict creates config from dictionary."""
        from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

        data = {
            "enabled": True,
            "control_prompt_name": "baseline",
            "treatment_prompt_name": "improved",
            "latency_warning_threshold_pct": 40.0,
            "log_comparisons": True,
            "experiment_name": "test_deployment",
        }

        config = ShadowModeDeploymentConfig.from_dict(data)

        assert config.enabled is True
        assert config.control_prompt_name == "baseline"
        assert config.latency_warning_threshold_pct == 40.0


# =============================================================================
# Test: Singleton/Factory Pattern
# =============================================================================


class TestShadowModeDeploymentFactory:
    """Tests for getting shadow mode deployment configuration."""

    def test_get_shadow_mode_deployment_config_returns_config(self):
        """Test get_shadow_mode_deployment_config returns a config instance."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeDeploymentConfig,
            get_shadow_mode_deployment_config,
            reset_shadow_mode_deployment_config,
        )

        # Reset to ensure clean state
        reset_shadow_mode_deployment_config()

        config = get_shadow_mode_deployment_config()
        assert isinstance(config, ShadowModeDeploymentConfig)

    def test_get_shadow_mode_deployment_config_singleton(self):
        """Test get_shadow_mode_deployment_config returns same instance."""
        from backend.config.shadow_mode_deployment import (
            get_shadow_mode_deployment_config,
            reset_shadow_mode_deployment_config,
        )

        # Reset to ensure clean state
        reset_shadow_mode_deployment_config()

        config1 = get_shadow_mode_deployment_config()
        config2 = get_shadow_mode_deployment_config()

        assert config1 is config2

    def test_reset_shadow_mode_deployment_config(self):
        """Test reset_shadow_mode_deployment_config clears singleton."""
        from backend.config.shadow_mode_deployment import (
            get_shadow_mode_deployment_config,
            reset_shadow_mode_deployment_config,
        )

        config1 = get_shadow_mode_deployment_config()
        reset_shadow_mode_deployment_config()
        config2 = get_shadow_mode_deployment_config()

        # After reset, should be a new instance
        assert config1 is not config2


# =============================================================================
# Test: Shadow Mode Stats Tracker (NEM-3337)
# =============================================================================


class TestShadowModeStatsTracker:
    """Tests for shadow mode statistics tracking."""

    def test_create_stats_tracker(self):
        """Test creating a stats tracker instance."""
        from backend.config.shadow_mode_deployment import ShadowModeStatsTracker

        tracker = ShadowModeStatsTracker()
        stats = tracker.get_stats()

        assert stats.total_comparisons == 0
        assert stats.control_avg_score == 0.0
        assert stats.treatment_avg_score == 0.0

    def test_record_comparison_updates_count(self):
        """Test recording a comparison increments total count."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=5,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        tracker.record(result)
        stats = tracker.get_stats()

        assert stats.total_comparisons == 1

    def test_record_updates_average_scores(self):
        """Test recording comparisons updates average risk scores."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        # Record two comparisons
        result1 = ShadowModeComparisonResult(
            control_risk_score=60,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=100.0,
            risk_score_diff=20,
            latency_diff_ms=0.0,
            latency_increase_pct=0.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        result2 = ShadowModeComparisonResult(
            control_risk_score=40,
            treatment_risk_score=30,
            control_latency_ms=100.0,
            treatment_latency_ms=100.0,
            risk_score_diff=10,
            latency_diff_ms=0.0,
            latency_increase_pct=0.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(result1)
            tracker.record(result2)

        stats = tracker.get_stats()

        # Control: (60 + 40) / 2 = 50
        assert stats.control_avg_score == 50.0
        # Treatment: (40 + 30) / 2 = 35
        assert stats.treatment_avg_score == 35.0

    def test_record_tracks_risk_level_shifts(self):
        """Test recording comparisons tracks risk level shift directions."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        # Lower risk (treatment < control)
        lower_result = ShadowModeComparisonResult(
            control_risk_score=60,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=100.0,
            risk_score_diff=20,
            latency_diff_ms=0.0,
            latency_increase_pct=0.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Higher risk (treatment > control)
        higher_result = ShadowModeComparisonResult(
            control_risk_score=30,
            treatment_risk_score=50,
            control_latency_ms=100.0,
            treatment_latency_ms=100.0,
            risk_score_diff=20,
            latency_diff_ms=0.0,
            latency_increase_pct=0.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        # Same risk
        same_result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=50,
            control_latency_ms=100.0,
            treatment_latency_ms=100.0,
            risk_score_diff=0,
            latency_diff_ms=0.0,
            latency_increase_pct=0.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(lower_result)
            tracker.record(higher_result)
            tracker.record(same_result)

        stats = tracker.get_stats()

        assert stats.lower_count == 1
        assert stats.higher_count == 1
        assert stats.same_count == 1

    def test_record_tracks_latency_warnings(self):
        """Test recording comparisons tracks latency warning counts."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        result_with_warning = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=50,
            control_latency_ms=100.0,
            treatment_latency_ms=200.0,
            risk_score_diff=0,
            latency_diff_ms=100.0,
            latency_increase_pct=100.0,
            latency_warning_triggered=True,
            timestamp=datetime.now(UTC).isoformat(),
        )

        result_no_warning = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=50,
            control_latency_ms=100.0,
            treatment_latency_ms=110.0,
            risk_score_diff=0,
            latency_diff_ms=10.0,
            latency_increase_pct=10.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(result_with_warning)
            tracker.record(result_no_warning)

        stats = tracker.get_stats()

        assert stats.latency_warnings == 1

    def test_record_tracks_errors(self):
        """Test recording comparisons tracks error counts."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        # Control error
        control_error = ShadowModeComparisonResult(
            control_risk_score=None,
            treatment_risk_score=50,
            control_latency_ms=None,
            treatment_latency_ms=100.0,
            risk_score_diff=None,
            latency_diff_ms=None,
            latency_increase_pct=None,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
            control_error="Connection timeout",
        )

        # Treatment error
        treatment_error = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=None,
            control_latency_ms=100.0,
            treatment_latency_ms=None,
            risk_score_diff=None,
            latency_diff_ms=None,
            latency_increase_pct=None,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
            treatment_error="Parse error",
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(control_error)
            tracker.record(treatment_error)

        stats = tracker.get_stats()

        assert stats.control_errors == 1
        assert stats.treatment_errors == 1

    def test_reset_clears_stats(self):
        """Test reset clears all statistics."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=5,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(result)

        # Verify not empty
        assert tracker.get_stats().total_comparisons == 1

        # Reset
        tracker.reset()

        # Verify cleared
        stats = tracker.get_stats()
        assert stats.total_comparisons == 0
        assert stats.control_avg_score == 0.0

    def test_to_dict_returns_complete_stats(self):
        """Test to_dict returns all statistics in dictionary form."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            ShadowModeStatsTracker,
        )

        tracker = ShadowModeStatsTracker()

        result = ShadowModeComparisonResult(
            control_risk_score=60,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=20,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
            tracker.record(result)

        stats = tracker.get_stats()
        stats_dict = stats.to_dict()

        assert "total_comparisons" in stats_dict
        assert "control_avg_score" in stats_dict
        assert "treatment_avg_score" in stats_dict
        assert "avg_score_diff" in stats_dict
        assert "risk_shift_distribution" in stats_dict
        assert "lower_percentage" in stats_dict
        assert "latency_warnings" in stats_dict
        assert "error_rates" in stats_dict

        assert stats_dict["total_comparisons"] == 1
        assert stats_dict["lower_percentage"] == 100.0  # 1 lower out of 1 total


# =============================================================================
# Test: Shadow Mode Stats Tracker Singleton (NEM-3337)
# =============================================================================


class TestShadowModeStatsTrackerSingleton:
    """Tests for shadow mode stats tracker singleton functions."""

    def test_get_shadow_mode_stats_tracker_returns_tracker(self):
        """Test get_shadow_mode_stats_tracker returns a tracker instance."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeStatsTracker,
            get_shadow_mode_stats_tracker,
            reset_shadow_mode_stats_tracker,
        )

        # Reset to ensure clean state
        reset_shadow_mode_stats_tracker()

        tracker = get_shadow_mode_stats_tracker()
        assert isinstance(tracker, ShadowModeStatsTracker)

    def test_get_shadow_mode_stats_tracker_singleton(self):
        """Test get_shadow_mode_stats_tracker returns same instance."""
        from backend.config.shadow_mode_deployment import (
            get_shadow_mode_stats_tracker,
            reset_shadow_mode_stats_tracker,
        )

        # Reset to ensure clean state
        reset_shadow_mode_stats_tracker()

        tracker1 = get_shadow_mode_stats_tracker()
        tracker2 = get_shadow_mode_stats_tracker()

        assert tracker1 is tracker2

    def test_reset_shadow_mode_stats_tracker(self):
        """Test reset_shadow_mode_stats_tracker clears singleton."""
        from backend.config.shadow_mode_deployment import (
            get_shadow_mode_stats_tracker,
            reset_shadow_mode_stats_tracker,
        )

        tracker1 = get_shadow_mode_stats_tracker()
        reset_shadow_mode_stats_tracker()
        tracker2 = get_shadow_mode_stats_tracker()

        # After reset, should be a new instance
        assert tracker1 is not tracker2

    def test_get_shadow_mode_stats_convenience_function(self):
        """Test get_shadow_mode_stats convenience function."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonStats,
            get_shadow_mode_stats,
            reset_shadow_mode_stats_tracker,
        )

        # Reset to ensure clean state
        reset_shadow_mode_stats_tracker()

        stats = get_shadow_mode_stats()
        assert isinstance(stats, ShadowModeComparisonStats)
        assert stats.total_comparisons == 0


# =============================================================================
# Test: Enhanced Shadow Mode Metrics Recording (NEM-3337)
# =============================================================================


class TestEnhancedShadowModeMetricsRecording:
    """Tests for enhanced shadow mode metrics recording."""

    def test_record_shadow_mode_comparison_records_risk_distributions(self):
        """Test recording shadow comparison records risk score distributions."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        result = ShadowModeComparisonResult(
            control_risk_score=60,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=20,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with (
            patch("backend.core.metrics.record_shadow_comparison") as mock_comparison,
            patch("backend.core.metrics.record_shadow_risk_score") as mock_risk_score,
            patch("backend.core.metrics.record_shadow_risk_score_diff") as mock_diff,
            patch("backend.core.metrics.record_shadow_risk_level_shift") as mock_shift,
            patch("backend.core.metrics.record_shadow_latency_diff") as mock_latency,
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning"),
        ):
            record_shadow_mode_comparison(result)

            # Should record comparison counter
            mock_comparison.assert_called_once_with("nemotron")

            # Should record risk scores for both versions
            assert mock_risk_score.call_count == 2
            mock_risk_score.assert_any_call("control", 60)
            mock_risk_score.assert_any_call("treatment", 40)

            # Should record risk score diff
            mock_diff.assert_called_once_with(20)

            # Should record risk level shift (lower since treatment < control)
            mock_shift.assert_called_once_with("lower")

            # Should record latency diff
            mock_latency.assert_called_once_with(0.02)  # 20ms in seconds

    def test_record_shadow_mode_comparison_handles_latency_warning(self):
        """Test recording shadow comparison handles latency warning."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        result = ShadowModeComparisonResult(
            control_risk_score=50,
            treatment_risk_score=50,
            control_latency_ms=100.0,
            treatment_latency_ms=200.0,
            risk_score_diff=0,
            latency_diff_ms=100.0,
            latency_increase_pct=100.0,
            latency_warning_triggered=True,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with (
            patch("backend.core.metrics.record_shadow_comparison"),
            patch("backend.core.metrics.record_shadow_risk_score"),
            patch("backend.core.metrics.record_shadow_risk_score_diff"),
            patch("backend.core.metrics.record_shadow_risk_level_shift"),
            patch("backend.core.metrics.record_shadow_latency_diff"),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning") as mock_warning,
        ):
            record_shadow_mode_comparison(result)

            # Should record latency warning
            mock_warning.assert_called_once_with("nemotron")

    def test_record_shadow_mode_comparison_handles_errors(self):
        """Test recording shadow comparison handles error cases."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        # Both failed
        result = ShadowModeComparisonResult(
            control_risk_score=None,
            treatment_risk_score=None,
            control_latency_ms=None,
            treatment_latency_ms=None,
            risk_score_diff=None,
            latency_diff_ms=None,
            latency_increase_pct=None,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
            control_error="Error 1",
            treatment_error="Error 2",
        )

        with (
            patch("backend.core.metrics.record_shadow_comparison"),
            patch("backend.core.metrics.record_shadow_comparison_error") as mock_error,
            patch("backend.core.metrics.record_shadow_latency_warning"),
        ):
            record_shadow_mode_comparison(result)

            # Should record both_failed error
            mock_error.assert_called_once_with("both_failed")

    def test_record_and_track_shadow_comparison(self):
        """Test convenience function that records and tracks comparison."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            get_shadow_mode_stats_tracker,
            record_and_track_shadow_comparison,
            reset_shadow_mode_stats_tracker,
        )

        reset_shadow_mode_stats_tracker()

        result = ShadowModeComparisonResult(
            control_risk_score=60,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=20,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        with (
            patch("backend.core.metrics.record_shadow_comparison"),
            patch("backend.core.metrics.record_shadow_risk_score"),
            patch("backend.core.metrics.record_shadow_risk_score_diff"),
            patch("backend.core.metrics.record_shadow_risk_level_shift"),
            patch("backend.core.metrics.record_shadow_latency_diff"),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning"),
            patch("backend.core.metrics.update_shadow_avg_risk_score"),
        ):
            record_and_track_shadow_comparison(result)

        # Stats should be tracked
        tracker = get_shadow_mode_stats_tracker()
        stats = tracker.get_stats()
        assert stats.total_comparisons == 1
