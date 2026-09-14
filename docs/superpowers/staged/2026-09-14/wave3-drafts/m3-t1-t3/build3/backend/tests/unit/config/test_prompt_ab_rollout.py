"""Unit tests for Prompt A/B Rollout Configuration (NEM-3338).

Phase 7.2 of Nemotron Prompt Improvements: A/B Testing for Prompt Rollout.

These tests cover:
1. A/B test configuration for 50/50 traffic split
2. Test duration configuration (48 hours)
3. Auto-rollback configuration based on metrics
4. FP rate tracking per experiment group
5. Risk score distribution tracking per group
6. Latency comparison metrics
7. Rollback trigger conditions

TDD: Write tests first (RED), then implement to make them GREEN.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: A/B Rollout Configuration
# =============================================================================


class TestABRolloutConfig:
    """Tests for A/B rollout configuration dataclass."""

    def test_ab_rollout_config_creation_with_defaults(self):
        """Test ABRolloutConfig can be created with default values."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        config = ABRolloutConfig()

        # Default: 50/50 split
        assert config.treatment_percentage == 0.5
        # Default: 48 hour duration
        assert config.test_duration_hours == 48
        # Default: not started
        assert config.started_at is None
        # Default: experiment name
        assert config.experiment_name == "nemotron_prompt_v2_rollout"

    def test_ab_rollout_config_creation_with_custom_values(self):
        """Test ABRolloutConfig can be created with custom values."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        started = datetime.now(UTC)
        config = ABRolloutConfig(
            treatment_percentage=0.3,
            test_duration_hours=72,
            experiment_name="custom_experiment",
            started_at=started,
        )

        assert config.treatment_percentage == 0.3
        assert config.test_duration_hours == 72
        assert config.experiment_name == "custom_experiment"
        assert config.started_at == started

    def test_ab_rollout_config_validates_treatment_percentage_bounds(self):
        """Test treatment_percentage must be between 0.0 and 1.0."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        # Valid boundary values
        config_zero = ABRolloutConfig(treatment_percentage=0.0)
        assert config_zero.treatment_percentage == 0.0

        config_one = ABRolloutConfig(treatment_percentage=1.0)
        assert config_one.treatment_percentage == 1.0

        # Invalid: below 0
        with pytest.raises(ValueError, match="treatment_percentage"):
            ABRolloutConfig(treatment_percentage=-0.1)

        # Invalid: above 1
        with pytest.raises(ValueError, match="treatment_percentage"):
            ABRolloutConfig(treatment_percentage=1.1)

    def test_ab_rollout_config_validates_test_duration(self):
        """Test test_duration_hours must be positive."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        # Valid: minimum 1 hour
        config = ABRolloutConfig(test_duration_hours=1)
        assert config.test_duration_hours == 1

        # Invalid: zero duration
        with pytest.raises(ValueError, match="test_duration_hours"):
            ABRolloutConfig(test_duration_hours=0)

        # Invalid: negative duration
        with pytest.raises(ValueError, match="test_duration_hours"):
            ABRolloutConfig(test_duration_hours=-1)


# =============================================================================
# Test: Auto-Rollback Configuration
# =============================================================================


class TestAutoRollbackConfig:
    """Tests for auto-rollback configuration."""

    def test_auto_rollback_config_creation_with_defaults(self):
        """Test AutoRollbackConfig defaults match task requirements."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        config = AutoRollbackConfig()

        # Default: rollback if FP rate increases (any increase is bad)
        assert config.max_fp_rate_increase == 0.05  # 5% tolerance
        # Default: rollback if latency increases >50%
        assert config.max_latency_increase_pct == 50.0
        # Default: rollback if error rate increases significantly
        assert config.max_error_rate_increase == 0.05  # 5% tolerance
        # Default: minimum samples before triggering
        assert config.min_samples == 100
        # Default: enabled
        assert config.enabled is True

    def test_auto_rollback_config_custom_thresholds(self):
        """Test AutoRollbackConfig with custom thresholds."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        config = AutoRollbackConfig(
            max_fp_rate_increase=0.10,
            max_latency_increase_pct=25.0,
            max_error_rate_increase=0.02,
            min_samples=50,
            enabled=False,
        )

        assert config.max_fp_rate_increase == 0.10
        assert config.max_latency_increase_pct == 25.0
        assert config.max_error_rate_increase == 0.02
        assert config.min_samples == 50
        assert config.enabled is False

    def test_auto_rollback_validates_min_samples(self):
        """Test min_samples must be non-negative."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        # Valid: zero samples
        config = AutoRollbackConfig(min_samples=0)
        assert config.min_samples == 0

        # Invalid: negative
        with pytest.raises(ValueError, match="min_samples"):
            AutoRollbackConfig(min_samples=-1)


# =============================================================================
# Test: Experiment Group Metrics
# =============================================================================


class TestExperimentGroupMetrics:
    """Tests for metrics tracking per experiment group."""

    def test_group_metrics_tracks_fp_rate(self):
        """Test GroupMetrics tracks false positive rate."""
        from backend.config.prompt_ab_rollout import GroupMetrics

        metrics = GroupMetrics()

        # Record some samples
        metrics.record_feedback(is_false_positive=True)
        metrics.record_feedback(is_false_positive=False)
        metrics.record_feedback(is_false_positive=True)
        metrics.record_feedback(is_false_positive=False)

        # FP rate should be 50%
        assert metrics.false_positive_count == 2
        assert metrics.total_feedback_count == 4
        assert metrics.fp_rate == 0.5

    def test_group_metrics_tracks_risk_score_distribution(self):
        """Test GroupMetrics tracks risk score distribution."""
        from backend.config.prompt_ab_rollout import GroupMetrics

        metrics = GroupMetrics()

        # Record some scores
        metrics.record_risk_score(30)
        metrics.record_risk_score(50)
        metrics.record_risk_score(70)
        metrics.record_risk_score(90)

        assert metrics.total_analyses == 4
        assert metrics.avg_risk_score == 60.0
        assert metrics.min_risk_score == 30
        assert metrics.max_risk_score == 90

    def test_group_metrics_tracks_latency(self):
        """Test GroupMetrics tracks latency statistics."""
        from backend.config.prompt_ab_rollout import GroupMetrics

        metrics = GroupMetrics()

        # Record latencies (in milliseconds)
        metrics.record_latency(100.0)
        metrics.record_latency(200.0)
        metrics.record_latency(150.0)

        assert metrics.latency_count == 3
        assert metrics.avg_latency_ms == 150.0

    def test_group_metrics_tracks_errors(self):
        """Test GroupMetrics tracks error count."""
        from backend.config.prompt_ab_rollout import GroupMetrics

        metrics = GroupMetrics()

        # Record analyses with errors
        metrics.record_analysis(has_error=False)
        metrics.record_analysis(has_error=True)
        metrics.record_analysis(has_error=False)
        metrics.record_analysis(has_error=False)
        metrics.record_analysis(has_error=True)

        assert metrics.error_count == 2
        assert metrics.total_analyses == 5
        assert metrics.error_rate == 0.4

    def test_group_metrics_fp_rate_handles_zero_samples(self):
        """Test FP rate is 0 when no samples."""
        from backend.config.prompt_ab_rollout import GroupMetrics

        metrics = GroupMetrics()

        assert metrics.fp_rate == 0.0
        assert metrics.error_rate == 0.0
        assert metrics.avg_latency_ms is None
        assert metrics.avg_risk_score is None


# =============================================================================
# Test: Rollout Manager
# =============================================================================


class TestRolloutManager:
    """Tests for ABRolloutManager that orchestrates the A/B test."""

    @pytest.fixture
    def rollout_config(self):
        """Standard rollout configuration for tests."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        return ABRolloutConfig(
            treatment_percentage=0.5,
            test_duration_hours=48,
        )

    @pytest.fixture
    def rollback_config(self):
        """Standard rollback configuration for tests."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        return AutoRollbackConfig(
            max_fp_rate_increase=0.05,
            max_latency_increase_pct=50.0,
            max_error_rate_increase=0.05,
            min_samples=100,
            enabled=True,
        )

    def test_rollout_manager_creation(self, rollout_config, rollback_config):
        """Test ABRolloutManager can be created."""
        from backend.config.prompt_ab_rollout import ABRolloutManager

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        assert manager.rollout_config == rollout_config
        assert manager.rollback_config == rollback_config
        assert manager.is_active is False

    def test_rollout_manager_start_experiment(self, rollout_config, rollback_config):
        """Test starting the A/B experiment."""
        from backend.config.prompt_ab_rollout import ABRolloutManager

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        manager.start()

        assert manager.is_active is True
        assert manager.rollout_config.started_at is not None

    def test_rollout_manager_stop_experiment(self, rollout_config, rollback_config):
        """Test stopping the A/B experiment."""
        from backend.config.prompt_ab_rollout import ABRolloutManager

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        manager.start()
        manager.stop()

        assert manager.is_active is False

    def test_rollout_manager_get_group_for_camera(self, rollout_config, rollback_config):
        """Test consistent group assignment for cameras."""
        from backend.config.prompt_ab_rollout import ABRolloutManager, ExperimentGroup

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        # Same camera should always get same group
        camera_id = "front_door"
        first_group = manager.get_group_for_camera(camera_id)

        for _ in range(100):
            group = manager.get_group_for_camera(camera_id)
            assert group == first_group
            assert group in (ExperimentGroup.CONTROL, ExperimentGroup.TREATMENT)

    def test_rollout_manager_group_distribution(self, rollout_config, rollback_config):
        """Test group distribution roughly matches treatment percentage."""
        from backend.config.prompt_ab_rollout import ABRolloutManager, ExperimentGroup

        manager = ABRolloutManager(
            rollout_config=rollout_config,  # 50% treatment
            rollback_config=rollback_config,
        )

        # Assign groups for many cameras
        treatment_count = 0
        total = 1000

        for i in range(total):
            group = manager.get_group_for_camera(f"camera_{i}")
            if group == ExperimentGroup.TREATMENT:
                treatment_count += 1

        # Should be approximately 50% (allow 10% tolerance)
        treatment_ratio = treatment_count / total
        assert 0.4 <= treatment_ratio <= 0.6, (
            f"Expected ~50% treatment, got {treatment_ratio * 100:.1f}%"
        )


# =============================================================================
# Test: Rollback Check Logic
# =============================================================================


class TestRollbackCheckLogic:
    """Tests for rollback trigger condition checking."""

    @pytest.fixture
    def manager_with_metrics(self):
        """Create manager with some baseline metrics."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        rollout_config = ABRolloutConfig(treatment_percentage=0.5)
        rollback_config = AutoRollbackConfig(
            max_fp_rate_increase=0.05,
            max_latency_increase_pct=50.0,
            max_error_rate_increase=0.05,
            min_samples=10,  # Low for testing
            enabled=True,
        )

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )
        manager.start()
        return manager

    def test_no_rollback_with_insufficient_samples(self, manager_with_metrics):
        """Test rollback not triggered with insufficient samples."""
        manager = manager_with_metrics
        manager.rollback_config.min_samples = 100

        # Only 5 samples in each group
        for _ in range(5):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=True)

        result = manager.check_rollback_needed()

        assert result.should_rollback is False
        assert "insufficient samples" in result.reason.lower()

    def test_rollback_triggered_by_fp_rate_increase(self, manager_with_metrics):
        """Test rollback triggered when treatment FP rate exceeds control."""
        manager = manager_with_metrics

        # Control: 10% FP rate
        for i in range(20):
            manager.record_control_feedback(is_false_positive=(i < 2))

        # Treatment: 25% FP rate (increase > 5% threshold)
        for i in range(20):
            manager.record_treatment_feedback(is_false_positive=(i < 5))

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "fp rate" in result.reason.lower() or "false positive" in result.reason.lower()

    def test_rollback_triggered_by_latency_increase(self, manager_with_metrics):
        """Test rollback triggered when treatment latency exceeds threshold."""
        manager = manager_with_metrics

        # Need feedback for minimum samples check
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=False)

        # Control: avg 100ms latency
        for _ in range(15):
            manager.record_control_analysis(latency_ms=100.0)

        # Treatment: avg 200ms latency (100% increase > 50% threshold)
        for _ in range(15):
            manager.record_treatment_analysis(latency_ms=200.0)

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "latency" in result.reason.lower()

    def test_rollback_triggered_by_error_rate_increase(self, manager_with_metrics):
        """Test rollback triggered when treatment error rate exceeds control."""
        manager = manager_with_metrics

        # Need feedback for minimum samples check
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=False)

        # Control: 0% error rate
        for _ in range(15):
            manager.record_control_analysis(has_error=False)

        # Treatment: 10% error rate (increase > 5% threshold)
        for i in range(20):
            manager.record_treatment_analysis(has_error=(i < 2))

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "error" in result.reason.lower()

    def test_no_rollback_when_treatment_performs_better(self, manager_with_metrics):
        """Test no rollback when treatment outperforms control."""
        manager = manager_with_metrics

        # Control: 30% FP rate
        for i in range(20):
            manager.record_control_feedback(is_false_positive=(i < 6))

        # Treatment: 10% FP rate (better!)
        for i in range(20):
            manager.record_treatment_feedback(is_false_positive=(i < 2))

        result = manager.check_rollback_needed()

        assert result.should_rollback is False

    def test_no_rollback_when_disabled(self, manager_with_metrics):
        """Test no rollback when auto-rollback is disabled."""
        manager = manager_with_metrics
        manager.rollback_config.enabled = False

        # Even with terrible treatment metrics
        for _ in range(20):
            manager.record_control_feedback(is_false_positive=False)
        for _ in range(20):
            manager.record_treatment_feedback(is_false_positive=True)

        result = manager.check_rollback_needed()

        assert result.should_rollback is False
        assert "disabled" in result.reason.lower()


# =============================================================================
# Test: Experiment Duration
# =============================================================================


class TestExperimentDuration:
    """Tests for experiment duration tracking."""

    def test_experiment_expired_after_duration(self):
        """Test experiment is marked expired after duration elapses."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        rollout_config = ABRolloutConfig(
            treatment_percentage=0.5,
            test_duration_hours=48,
        )
        rollback_config = AutoRollbackConfig()

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        # Start experiment in the past (49 hours ago)
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=49)

        assert manager.is_expired is True

    def test_experiment_not_expired_within_duration(self):
        """Test experiment not expired while within duration."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        rollout_config = ABRolloutConfig(
            treatment_percentage=0.5,
            test_duration_hours=48,
        )
        rollback_config = AutoRollbackConfig()

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        # Start experiment 24 hours ago
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=24)

        assert manager.is_expired is False

    def test_experiment_remaining_hours(self):
        """Test remaining hours calculation."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        rollout_config = ABRolloutConfig(
            treatment_percentage=0.5,
            test_duration_hours=48,
        )
        rollback_config = AutoRollbackConfig()

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )

        # Start 12 hours ago
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=12)

        remaining = manager.remaining_hours
        assert 35 <= remaining <= 37  # Allow 1 hour tolerance for test execution


# =============================================================================
# Test: Metrics Summary
# =============================================================================


class TestMetricsSummary:
    """Tests for generating metrics summary for both groups."""

    def test_get_metrics_summary(self):
        """Test getting a summary of metrics for both groups."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        rollout_config = ABRolloutConfig(treatment_percentage=0.5)
        rollback_config = AutoRollbackConfig()

        manager = ABRolloutManager(
            rollout_config=rollout_config,
            rollback_config=rollback_config,
        )
        manager.start()

        # Record some data
        for i in range(10):
            manager.record_control_feedback(is_false_positive=(i < 3))
            manager.record_control_analysis(latency_ms=100.0, risk_score=50)

            manager.record_treatment_feedback(is_false_positive=(i < 2))
            manager.record_treatment_analysis(latency_ms=120.0, risk_score=45)

        summary = manager.get_metrics_summary()

        assert "control" in summary
        assert "treatment" in summary

        assert summary["control"]["fp_rate"] == 0.3
        assert summary["control"]["avg_latency_ms"] == 100.0
        assert summary["control"]["avg_risk_score"] == 50.0
        assert summary["control"]["sample_count"] == 10

        assert summary["treatment"]["fp_rate"] == 0.2
        assert summary["treatment"]["avg_latency_ms"] == 120.0
        assert summary["treatment"]["avg_risk_score"] == 45.0
        assert summary["treatment"]["sample_count"] == 10


# =============================================================================
# Test: Serialization
# =============================================================================


class TestSerialization:
    """Tests for config serialization."""

    def test_ab_rollout_config_to_dict(self):
        """Test ABRolloutConfig serialization to dict."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        started = datetime.now(UTC)
        config = ABRolloutConfig(
            treatment_percentage=0.5,
            test_duration_hours=48,
            experiment_name="test",
            started_at=started,
        )

        data = config.to_dict()

        assert data["treatment_percentage"] == 0.5
        assert data["test_duration_hours"] == 48
        assert data["experiment_name"] == "test"
        assert data["started_at"] == started.isoformat()

    def test_ab_rollout_config_from_dict(self):
        """Test ABRolloutConfig deserialization from dict."""
        from backend.config.prompt_ab_rollout import ABRolloutConfig

        data = {
            "treatment_percentage": 0.5,
            "test_duration_hours": 48,
            "experiment_name": "test",
            "started_at": "2024-01-15T10:00:00+00:00",
        }

        config = ABRolloutConfig.from_dict(data)

        assert config.treatment_percentage == 0.5
        assert config.test_duration_hours == 48
        assert config.experiment_name == "test"
        assert config.started_at is not None

    def test_auto_rollback_config_to_dict(self):
        """Test AutoRollbackConfig serialization to dict."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        config = AutoRollbackConfig(
            max_fp_rate_increase=0.1,
            max_latency_increase_pct=75.0,
            max_error_rate_increase=0.1,
            min_samples=50,
            enabled=False,
        )

        data = config.to_dict()

        assert data["max_fp_rate_increase"] == 0.1
        assert data["max_latency_increase_pct"] == 75.0
        assert data["max_error_rate_increase"] == 0.1
        assert data["min_samples"] == 50
        assert data["enabled"] is False

    def test_auto_rollback_config_from_dict(self):
        """Test AutoRollbackConfig deserialization from dict."""
        from backend.config.prompt_ab_rollout import AutoRollbackConfig

        data = {
            "max_fp_rate_increase": 0.1,
            "max_latency_increase_pct": 75.0,
            "max_error_rate_increase": 0.1,
            "min_samples": 50,
            "enabled": False,
        }

        config = AutoRollbackConfig.from_dict(data)

        assert config.max_fp_rate_increase == 0.1
        assert config.max_latency_increase_pct == 75.0
        assert config.max_error_rate_increase == 0.1
        assert config.min_samples == 50
        assert config.enabled is False
