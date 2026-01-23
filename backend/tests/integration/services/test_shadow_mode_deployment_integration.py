"""Integration tests for Shadow Mode Deployment (NEM-3337).

These tests verify the complete shadow mode deployment flow:
1. Configuration of shadow mode for prompt A/B comparison
2. Parallel execution of control and treatment prompts
3. Metrics recording for risk distribution comparison
4. Statistics tracking for aggregate analysis
5. Integration with NemotronAnalyzer

These are integration tests because they test the interaction between
multiple components:
- ShadowModeDeploymentConfig
- ShadowModeStatsTracker
- Prometheus metrics
- NemotronAnalyzer (mocked LLM calls)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture
def mock_settings():
    """Create mock settings for NemotronAnalyzer."""
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
    mock.nemotron_url = "http://localhost:8091"
    mock.nemotron_api_key = None
    mock.ai_connect_timeout = 10.0
    mock.nemotron_read_timeout = 120.0
    mock.ai_health_timeout = 5.0
    mock.nemotron_max_retries = 1
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    mock.nemotron_context_window = 4096
    mock.nemotron_max_output_tokens = 1536
    mock.context_utilization_warning_threshold = 0.80
    mock.context_truncation_enabled = True
    mock.llm_tokenizer_encoding = "cl100k_base"
    mock.image_quality_enabled = False
    mock.ai_warmup_enabled = False
    mock.ai_cold_start_threshold_seconds = 300.0
    mock.nemotron_warmup_prompt = "Test warmup prompt"
    mock.prompt_ab_testing_enabled = True
    mock.prompt_shadow_mode_enabled = True
    return mock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    return mock_client


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


class TestParallelPromptExecutionFlow:
    """Integration tests for parallel prompt execution in shadow mode."""

    @pytest.mark.asyncio
    async def test_shadow_analysis_executes_both_prompts(self, mock_redis_client, mock_settings):
        """Test shadow mode analysis runs both control and treatment prompts."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.token_counter.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.core.config.get_settings",
                return_value=mock_settings,
            ),
        ):
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

            # Configure shadow mode
            experiment_config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(experiment_config)

            # Track which versions were called
            call_versions = []

            async def mock_llm_call(*args, prompt_version=None, **kwargs):
                call_versions.append(prompt_version)
                if prompt_version == "v2_calibrated":
                    return {"risk_score": 35, "risk_level": "medium", "summary": "V2"}
                return {"risk_score": 55, "risk_level": "medium", "summary": "V1"}

            with patch.object(analyzer, "_call_llm_with_version", mock_llm_call):
                result = await analyzer.run_shadow_analysis(
                    camera_id="test_camera",
                    context="Test context",
                )

            # Both versions should have been called
            assert "v1_original" in call_versions
            assert "v2_calibrated" in call_versions

            # Primary result should be from V1
            assert result["primary_result"]["risk_score"] == 55

            # Shadow result should be from V2
            assert result["shadow_result"]["risk_score"] == 35

    @pytest.mark.asyncio
    async def test_shadow_analysis_continues_on_treatment_failure(
        self, mock_redis_client, mock_settings
    ):
        """Test shadow mode continues with V1 result when V2 fails."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.token_counter.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.core.config.get_settings",
                return_value=mock_settings,
            ),
        ):
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

            experiment_config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(experiment_config)

            async def mock_llm_call(*args, prompt_version=None, **kwargs):
                if prompt_version == "v2_calibrated":
                    raise Exception("V2 prompt failed")
                return {"risk_score": 50, "risk_level": "medium", "summary": "V1"}

            with patch.object(analyzer, "_call_llm_with_version", mock_llm_call):
                result = await analyzer.run_shadow_analysis(
                    camera_id="test_camera",
                    context="Test context",
                )

            # Should still have primary result from V1
            assert result["primary_result"]["risk_score"] == 50

            # Shadow result should be None due to failure
            assert result["shadow_result"] is None


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
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_score",
                side_effect=lambda v, s: metric_calls["risk_score"].append((v, s)),
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_score_diff",
                side_effect=lambda d: metric_calls["diff"].append(d),
            ),
            patch(
                "backend.core.metrics.record_shadow_risk_level_shift",
                side_effect=lambda d: metric_calls["shift"].append(d),
            ),
            patch(
                "backend.core.metrics.record_shadow_latency_diff",
                side_effect=lambda d: metric_calls["latency"].append(d),
            ),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning"),
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
            patch("backend.core.metrics.record_shadow_comparison"),
            patch("backend.core.metrics.record_shadow_risk_score"),
            patch("backend.core.metrics.record_shadow_risk_score_diff"),
            patch(
                "backend.core.metrics.record_shadow_risk_level_shift",
                side_effect=lambda d: shift_calls.append(d),
            ),
            patch("backend.core.metrics.record_shadow_latency_diff"),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning"),
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

        with patch("backend.core.metrics.update_shadow_avg_risk_score"):
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
            patch("backend.core.metrics.record_shadow_risk_score"),
            patch("backend.core.metrics.record_shadow_risk_score_diff"),
            patch("backend.core.metrics.record_shadow_risk_level_shift"),
            patch("backend.core.metrics.record_shadow_latency_diff"),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning"),
            patch("backend.core.metrics.update_shadow_avg_risk_score"),
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
            patch("backend.core.metrics.record_shadow_comparison"),
            patch("backend.core.metrics.record_shadow_risk_score"),
            patch("backend.core.metrics.record_shadow_risk_score_diff"),
            patch("backend.core.metrics.record_shadow_risk_level_shift"),
            patch("backend.core.metrics.record_shadow_latency_diff"),
            patch("backend.core.metrics.record_shadow_comparison_error"),
            patch("backend.core.metrics.record_shadow_latency_warning", mock_warning),
        ):
            record_shadow_mode_comparison(result)

        assert warning_recorded is True


# =============================================================================
# Test: End-to-End Shadow Mode Flow
# =============================================================================


class TestEndToEndShadowModeFlow:
    """End-to-end integration tests for complete shadow mode flow."""

    @pytest.mark.asyncio
    async def test_complete_shadow_mode_analysis_flow(self, mock_redis_client, mock_settings):
        """Test complete shadow mode analysis flow from config to metrics."""
        from backend.config.prompt_experiment import PromptExperimentConfig
        from backend.config.shadow_mode_deployment import (
            ShadowModeComparisonResult,
            get_shadow_mode_stats_tracker,
            record_and_track_shadow_comparison,
        )
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.services.token_counter.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "backend.core.config.get_settings",
                return_value=mock_settings,
            ),
        ):
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()

            # 1. Configure analyzer with shadow mode
            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)
            experiment_config = PromptExperimentConfig(
                shadow_mode=True,
                experiment_name="e2e_shadow_test",
            )
            analyzer.set_experiment_config(experiment_config)

            # 2. Mock LLM responses (simulates real analysis)
            async def mock_llm_call(*args, prompt_version=None, **kwargs):
                if prompt_version == "v2_calibrated":
                    # V2 produces lower risk scores (goal of new prompt)
                    return {
                        "risk_score": 35,
                        "risk_level": "medium",
                        "summary": "Treatment result",
                    }
                return {
                    "risk_score": 65,
                    "risk_level": "high",
                    "summary": "Control result",
                }

            # 3. Run shadow analysis
            with patch.object(analyzer, "_call_llm_with_version", mock_llm_call):
                result = await analyzer.run_shadow_analysis(
                    camera_id="front_door",
                    context="Detection context for analysis",
                )

            # 4. Verify analysis result structure
            assert result["primary_result"]["risk_score"] == 65
            assert result["shadow_result"]["risk_score"] == 35
            assert result["score_diff"] == 30

            # 5. Create comparison result and record it
            comparison_result = ShadowModeComparisonResult(
                control_risk_score=result["primary_result"]["risk_score"],
                treatment_risk_score=result["shadow_result"]["risk_score"],
                control_latency_ms=result["v1_latency_ms"],
                treatment_latency_ms=result["v2_latency_ms"],
                risk_score_diff=result["score_diff"],
                latency_diff_ms=result["v2_latency_ms"] - result["v1_latency_ms"],
                latency_increase_pct=0.0,  # Would be calculated
                latency_warning_triggered=False,
                timestamp=datetime.now(UTC).isoformat(),
                camera_id="front_door",
            )

            # 6. Record and track the comparison
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
                record_and_track_shadow_comparison(comparison_result)

            # 7. Verify statistics were tracked
            stats = get_shadow_mode_stats_tracker().get_stats()
            assert stats.total_comparisons == 1
            assert stats.control_avg_score == 65.0
            assert stats.treatment_avg_score == 35.0
            assert stats.lower_count == 1  # Treatment was lower

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

            with patch("backend.core.metrics.update_shadow_avg_risk_score"):
                tracker.record(result)

        stats = tracker.get_stats()
        stats_dict = stats.to_dict()

        # Verify summary structure
        assert stats_dict["total_comparisons"] == 10
        assert stats_dict["latency_warnings"] == 2
        assert "risk_shift_distribution" in stats_dict
        assert "lower_percentage" in stats_dict
        assert stats_dict["lower_percentage"] > 0  # Treatment was consistently lower
