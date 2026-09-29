"""Integration tests for Shadow Mode Deployment (NEM-3337).

These tests verify the complete shadow mode deployment flow:
1. Configuration of shadow mode for prompt A/B comparison
2. Parallel execution of control and treatment prompts
3. Metrics recording for risk distribution comparison
4. Statistics tracking for aggregate analysis

R8 S2b: the analyzer-side shadow execution (run_shadow_analysis /
_call_llm_with_version on the retired NemotronAnalyzer) is gone with the
legacy path, and VlmAnalyzer has no shadow-execution surface to repoint to -
so those three tests went with their subject. Everything here drives the
SURVIVING shadow-mode machinery: the deployment config, the stats tracker
and the Prometheus metrics recorded by record_and_track_shadow_comparison.

These are integration tests because they test the interaction between
multiple components:
- ShadowModeDeploymentConfig
- ShadowModeStatsTracker
- Prometheus metrics
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def shadow_mode_config():
    """Create a shadow mode deployment configuration for testing."""
    from backend.config.shadow_mode_deployment import ShadowModeDeploymentConfig

    return ShadowModeDeploymentConfig(
        enabled=True,
        control_prompt_name="v1_original",
        treatment_prompt_name="v2_calibrated",
        latency_warning_threshold_pct=50.0,
        experiment_name="test_shadow_experiment",
    )


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton state before each test."""
    from backend.config.shadow_mode_deployment import (
        reset_shadow_mode_deployment_config,
        reset_shadow_mode_stats_tracker,
    )

    reset_shadow_mode_deployment_config()
    reset_shadow_mode_stats_tracker()
    yield
    reset_shadow_mode_deployment_config()
    reset_shadow_mode_stats_tracker()


# =============================================================================
# Test: Shadow Mode Deployment Configuration
# =============================================================================


class TestShadowModeDeploymentConfiguration:
    """Integration tests for shadow mode deployment configuration."""

    def test_config_integrates_with_prompt_experiment(self):
        """Test shadow mode config integrates with PromptExperimentConfig."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            ShadowModeDeploymentConfig,
            create_deployment_from_experiment_config,
        )

        # Create experiment config with shadow mode enabled
        experiment_config = PromptExperimentConfig(
            shadow_mode=True,
            treatment_percentage=0.0,
            max_latency_increase_pct=30.0,
            experiment_name="prompt_v2_shadow",
        )

        # Create deployment config from experiment
        deployment_config = create_deployment_from_experiment_config(experiment_config)

        # Verify integration
        assert isinstance(deployment_config, ShadowModeDeploymentConfig)
        assert deployment_config.enabled is True
        assert deployment_config.experiment_name == "prompt_v2_shadow"
        assert deployment_config.latency_warning_threshold_pct == 30.0

    def test_config_disabled_when_experiment_not_shadow_mode(self):
        """Test deployment config is disabled when experiment is A/B mode."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            create_deployment_from_experiment_config,
        )

        # Create experiment config with A/B mode (not shadow)
        experiment_config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.5,
        )

        # Deployment config should be disabled
        deployment_config = create_deployment_from_experiment_config(experiment_config)
        assert deployment_config.enabled is False


# =============================================================================
# Test: Parallel Prompt Execution Flow
# =============================================================================


# =============================================================================
# Test: Risk Distribution Comparison Metrics
# =============================================================================


class TestRiskDistributionComparisonMetrics:
    """Integration tests for risk distribution comparison metrics."""

    def test_record_shadow_comparison_creates_distribution_metrics(self):
        """Test that shadow comparison records risk distribution metrics."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        result = ShadowModeComparisonResult(
            control_risk_score=70,
            treatment_risk_score=40,
            control_latency_ms=100.0,
            treatment_latency_ms=120.0,
            risk_score_diff=30,
            latency_diff_ms=20.0,
            latency_increase_pct=20.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
            camera_id="test_camera",
        )

        # Track all metric calls
        metric_calls = {
            "comparison": [],
            "risk_score": [],
            "diff": [],
            "shift": [],
            "latency": [],
        }

        with (
            patch(
                "backend.core.metrics.record_shadow_comparison",
                side_effect=lambda m: metric_calls["comparison"].append(m),
                autospec=True,
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_score",
                side_effect=lambda v, s: metric_calls["risk_score"].append((v, s)),
                autospec=True,
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_score_diff",
                side_effect=lambda d: metric_calls["diff"].append(d),
                autospec=True,
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_level_shift",
                side_effect=lambda d: metric_calls["shift"].append(d),
                autospec=True,
            ),
            patch(
                "backend.core.metrics.record_shadow_latency_diff",
                side_effect=lambda d: metric_calls["latency"].append(d),
                autospec=True,
            ),
            patch("backend.core.metrics.record_shadow_comparison_error", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_warning", autospec=True),
        ):
            record_shadow_mode_comparison(result)

        # Verify all expected metrics were recorded
        assert metric_calls["comparison"] == ["nemotron"]
        assert ("control", 70) in metric_calls["risk_score"]
        assert ("treatment", 40) in metric_calls["risk_score"]
        assert metric_calls["diff"] == [30]
        assert metric_calls["shift"] == ["lower"]  # treatment < control
        assert metric_calls["latency"] == [0.02]  # 20ms in seconds

    def test_metrics_track_risk_level_shift_directions(self):
        """Test that metrics correctly track risk level shift directions."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            record_shadow_mode_comparison,
        )

        # Create results with different shift directions
        results = [
            # Lower (treatment < control)
            ShadowModeComparisonResult(
                control_risk_score=70,
                treatment_risk_score=40,
                control_latency_ms=100.0,
                treatment_latency_ms=100.0,
                risk_score_diff=30,
                latency_diff_ms=0.0,
                latency_increase_pct=0.0,
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            # Higher (treatment > control)
            ShadowModeComparisonResult(
                control_risk_score=30,
                treatment_risk_score=60,
                control_latency_ms=100.0,
                treatment_latency_ms=100.0,
                risk_score_diff=30,
                latency_diff_ms=0.0,
                latency_increase_pct=0.0,
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            # Same
            ShadowModeComparisonResult(
                control_risk_score=50,
                treatment_risk_score=50,
                control_latency_ms=100.0,
                treatment_latency_ms=100.0,
                risk_score_diff=0,
                latency_diff_ms=0.0,
                latency_increase_pct=0.0,
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        ]

        shift_calls = []

        with (
            patch("backend.core.metrics.record_shadow_comparison", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_score", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_score_diff", autospec=True),
            patch(
                "backend.core.metrics.record_shadow_risk_level_shift",
                side_effect=lambda d: shift_calls.append(d),
                autospec=True,
            ),
            patch("backend.core.metrics.record_shadow_latency_diff", autospec=True),
            patch("backend.core.metrics.record_shadow_comparison_error", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_warning", autospec=True),
        ):
            for result in results:
                record_shadow_mode_comparison(result)

        # Verify all shift directions recorded correctly
        assert shift_calls == ["lower", "higher", "same"]


# =============================================================================
# Test: Statistics Tracking Integration
# =============================================================================


class TestStatisticsTrackingIntegration:
    """Integration tests for statistics tracking across components."""

    def test_stats_tracker_aggregates_multiple_comparisons(self):
        """Test stats tracker correctly aggregates multiple comparisons."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            get_shadow_mode_stats_tracker,
        )

        tracker = get_shadow_mode_stats_tracker()

        # Simulate multiple comparisons
        results = [
            ShadowModeComparisonResult(
                control_risk_score=80,
                treatment_risk_score=50,
                control_latency_ms=100.0,
                treatment_latency_ms=120.0,
                risk_score_diff=30,
                latency_diff_ms=20.0,
                latency_increase_pct=20.0,
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            ShadowModeComparisonResult(
                control_risk_score=60,
                treatment_risk_score=40,
                control_latency_ms=100.0,
                treatment_latency_ms=110.0,
                risk_score_diff=20,
                latency_diff_ms=10.0,
                latency_increase_pct=10.0,
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
            ),
            ShadowModeComparisonResult(
                control_risk_score=40,
                treatment_risk_score=60,
                control_latency_ms=100.0,
                treatment_latency_ms=180.0,
                risk_score_diff=20,
                latency_diff_ms=80.0,
                latency_increase_pct=80.0,
                latency_warning_triggered=True,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        ]

        with patch("backend.core.metrics.update_shadow_avg_risk_score", autospec=True):
            for result in results:
                tracker.record(result)

        stats = tracker.get_stats()

        # Verify aggregation
        assert stats.total_comparisons == 3
        assert stats.control_avg_score == pytest.approx(60.0)  # (80+60+40)/3
        assert stats.treatment_avg_score == 50.0  # (50+40+60)/3
        assert stats.avg_score_diff == pytest.approx(23.33, rel=0.01)  # (30+20+20)/3
        assert stats.lower_count == 2  # First two: treatment < control
        assert stats.higher_count == 1  # Third: treatment > control
        assert stats.latency_warnings == 1

    def test_record_and_track_updates_both_metrics_and_stats(self):
        """Test convenience function updates both metrics and stats."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            get_shadow_mode_stats_tracker,
            record_and_track_shadow_comparison,
        )

        result = ShadowModeComparisonResult(
            control_risk_score=70,
            treatment_risk_score=45,
            control_latency_ms=100.0,
            treatment_latency_ms=130.0,
            risk_score_diff=25,
            latency_diff_ms=30.0,
            latency_increase_pct=30.0,
            latency_warning_triggered=False,
            timestamp=datetime.now(UTC).isoformat(),
        )

        metric_recorded = False

        def mock_record_comparison(model):
            nonlocal metric_recorded
            metric_recorded = True

        with (
            patch(
                "backend.core.metrics.record_shadow_comparison",
                mock_record_comparison,
            ),
            patch("backend.core.metrics.record_shadow_risk_score", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_score_diff", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_level_shift", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_diff", autospec=True),
            patch("backend.core.metrics.record_shadow_comparison_error", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_warning", autospec=True),
            patch("backend.core.metrics.update_shadow_avg_risk_score", autospec=True),
        ):
            record_and_track_shadow_comparison(result)

        # Verify metrics were recorded
        assert metric_recorded is True

        # Verify stats were tracked
        tracker = get_shadow_mode_stats_tracker()
        stats = tracker.get_stats()
        assert stats.total_comparisons == 1
        assert stats.control_avg_score == 70.0
        assert stats.treatment_avg_score == 45.0


# =============================================================================
# Test: Latency Warning Integration
# =============================================================================


class TestLatencyWarningIntegration:
    """Integration tests for latency warning functionality."""

    def test_latency_warning_triggers_on_threshold_exceeded(self, shadow_mode_config):
        """Test latency warning triggers when threshold is exceeded."""
        # Control: 100ms, Treatment: 160ms (60% increase > 50% threshold)
        warning = shadow_mode_config.check_latency_warning(
            control_latency_ms=100.0,
            treatment_latency_ms=160.0,
        )

        assert warning.triggered is True
        assert warning.percentage_increase == pytest.approx(60.0)
        assert "exceeds" in warning.message.lower()

    def test_latency_warning_records_metric(self):
        """Test latency warning records prometheus metric."""
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

        warning_recorded = False

        def mock_warning(model):
            nonlocal warning_recorded
            warning_recorded = True

        with (
            patch("backend.core.metrics.record_shadow_comparison", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_score", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_score_diff", autospec=True),
            patch("backend.core.metrics.record_shadow_risk_level_shift", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_diff", autospec=True),
            patch("backend.core.metrics.record_shadow_comparison_error", autospec=True),
            patch("backend.core.metrics.record_shadow_latency_warning", mock_warning),
        ):
            record_shadow_mode_comparison(result)

        assert warning_recorded is True


# =============================================================================
# Test: End-to-End Shadow Mode Flow
# =============================================================================


class TestEndToEndShadowModeFlow:
    """End-to-end integration tests for complete shadow mode flow."""

    def test_stats_summary_for_reporting(self):
        """Test stats summary provides useful data for reporting."""
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            get_shadow_mode_stats_tracker,
        )

        tracker = get_shadow_mode_stats_tracker()

        # Simulate a series of comparisons showing V2 improvement
        for i in range(10):
            control_score = 60 + (i % 20)
            treatment_score = 40 + (i % 15)

            result = ShadowModeComparisonResult(
                control_risk_score=control_score,
                treatment_risk_score=treatment_score,
                control_latency_ms=100.0,
                treatment_latency_ms=105.0 + i,
                risk_score_diff=abs(control_score - treatment_score),
                latency_diff_ms=5.0 + i,
                latency_increase_pct=5.0 + i,
                latency_warning_triggered=i > 7,  # Last 2 trigger warnings
                timestamp=datetime.now(UTC).isoformat(),
            )

            with patch("backend.core.metrics.update_shadow_avg_risk_score", autospec=True):
                tracker.record(result)

        stats = tracker.get_stats()
        stats_dict = stats.to_dict()

        # Verify summary structure
        assert stats_dict["total_comparisons"] == 10
        assert stats_dict["latency_warnings"] == 2
        assert "risk_shift_distribution" in stats_dict
        assert "lower_percentage" in stats_dict
        assert stats_dict["lower_percentage"] > 0  # Treatment was consistently lower
