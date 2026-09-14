"""Unit tests for A/B Rollout Lifecycle (NEM-3338).

Phase 7.2 of Nemotron Prompt Improvements: A/B Testing for Prompt Rollout.

These tests cover the complete A/B rollout lifecycle:
1. Experiment initialization and startup
2. Traffic splitting during active experiment
3. Metrics accumulation over time
4. Rollback condition evaluation
5. Experiment completion (expiry or manual stop)

This file focuses on lifecycle transitions and state management,
complementing the configuration tests in test_ab_rollout_production.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: Experiment Initialization
# =============================================================================


class TestExperimentInitialization:
    """Tests for experiment initialization state."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the global rollout manager before and after each test."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_new_manager_is_not_active(self):
        """Test newly created manager is not active until started."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(),
        )

        assert manager.is_active is False
        assert manager.rollout_config.started_at is None

    def test_new_manager_has_empty_metrics(self):
        """Test newly created manager has empty metrics."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(),
        )

        assert manager.control_metrics.total_feedback_count == 0
        assert manager.control_metrics.total_analyses == 0
        assert manager.treatment_metrics.total_feedback_count == 0
        assert manager.treatment_metrics.total_analyses == 0

    def test_starting_experiment_sets_active_and_timestamp(self):
        """Test starting experiment sets is_active and started_at."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(),
        )

        before_start = datetime.now(UTC)
        manager.start()
        after_start = datetime.now(UTC)

        assert manager.is_active is True
        assert manager.rollout_config.started_at is not None
        assert before_start <= manager.rollout_config.started_at <= after_start


# =============================================================================
# Test: Traffic Splitting During Active Experiment
# =============================================================================


class TestTrafficSplittingDuringExperiment:
    """Tests for traffic splitting behavior during active experiment."""

    @pytest.fixture
    def active_manager(self):
        """Create an active rollout manager."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
            reset_rollout_manager,
        )

        reset_rollout_manager()
        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(treatment_percentage=0.5),
            rollback_config=AutoRollbackConfig(),
        )
        manager.start()
        yield manager
        reset_rollout_manager()

    def test_group_assignment_is_deterministic(self, active_manager):
        """Test camera group assignment is deterministic based on hash."""
        from backend.config.prompt_ab_rollout import ExperimentGroup

        camera_id = "test_camera_deterministic"

        # Get assignment multiple times
        assignments = [active_manager.get_group_for_camera(camera_id) for _ in range(100)]

        # All should be the same
        assert all(a == assignments[0] for a in assignments)
        assert assignments[0] in (ExperimentGroup.CONTROL, ExperimentGroup.TREATMENT)

    def test_group_assignment_varies_by_camera(self, active_manager):
        """Test different cameras get different (but consistent) assignments."""
        from backend.config.prompt_ab_rollout import ExperimentGroup

        groups = set()
        for i in range(100):
            group = active_manager.get_group_for_camera(f"camera_{i}")
            groups.add(group)

        # With 50% split and 100 cameras, we should see both groups
        assert ExperimentGroup.CONTROL in groups
        assert ExperimentGroup.TREATMENT in groups


# =============================================================================
# Test: Metrics Accumulation Over Time
# =============================================================================


class TestMetricsAccumulation:
    """Tests for metrics accumulation during experiment."""

    @pytest.fixture
    def manager_with_data(self):
        """Create a manager with some recorded data."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
            reset_rollout_manager,
        )

        reset_rollout_manager()
        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(treatment_percentage=0.5),
            rollback_config=AutoRollbackConfig(min_samples=10),
        )
        manager.start()

        # Simulate data collection
        for i in range(20):
            # Control: 20% FP rate, 100ms latency
            manager.record_control_feedback(is_false_positive=(i < 4))
            manager.record_control_analysis(latency_ms=100.0, risk_score=50)

            # Treatment: 10% FP rate, 110ms latency (slightly slower but fewer FPs)
            manager.record_treatment_feedback(is_false_positive=(i < 2))
            manager.record_treatment_analysis(latency_ms=110.0, risk_score=40)

        yield manager
        reset_rollout_manager()

    def test_feedback_count_increments(self, manager_with_data):
        """Test feedback counts increment correctly."""
        assert manager_with_data.control_metrics.total_feedback_count == 20
        assert manager_with_data.treatment_metrics.total_feedback_count == 20

    def test_fp_rate_calculated_correctly(self, manager_with_data):
        """Test FP rate is calculated correctly from feedback."""
        # Control: 4/20 = 20%
        assert manager_with_data.control_metrics.fp_rate == 0.2

        # Treatment: 2/20 = 10%
        assert manager_with_data.treatment_metrics.fp_rate == 0.1

    def test_latency_average_calculated_correctly(self, manager_with_data):
        """Test average latency is calculated correctly."""
        assert manager_with_data.control_metrics.avg_latency_ms == 100.0
        assert manager_with_data.treatment_metrics.avg_latency_ms == 110.0

    def test_risk_score_average_calculated_correctly(self, manager_with_data):
        """Test average risk score is calculated correctly."""
        assert manager_with_data.control_metrics.avg_risk_score == 50.0
        assert manager_with_data.treatment_metrics.avg_risk_score == 40.0

    def test_metrics_summary_includes_all_data(self, manager_with_data):
        """Test metrics summary includes all relevant data."""
        summary = manager_with_data.get_metrics_summary()

        assert summary["control"]["fp_rate"] == 0.2
        assert summary["control"]["avg_latency_ms"] == 100.0
        assert summary["control"]["sample_count"] == 20
        assert summary["control"]["analysis_count"] == 20

        assert summary["treatment"]["fp_rate"] == 0.1
        assert summary["treatment"]["avg_latency_ms"] == 110.0
        assert summary["treatment"]["sample_count"] == 20
        assert summary["treatment"]["analysis_count"] == 20


# =============================================================================
# Test: Rollback Condition Evaluation
# =============================================================================


class TestRollbackConditionEvaluation:
    """Tests for rollback condition evaluation."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the global rollout manager before and after each test."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_no_rollback_with_insufficient_samples(self):
        """Test no rollback triggered when samples below threshold."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(min_samples=100),
        )
        manager.start()

        # Add only 50 samples (below 100 threshold)
        for _ in range(50):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=True)  # 100% FP rate

        result = manager.check_rollback_needed()

        assert result.should_rollback is False
        assert "insufficient" in result.reason.lower()

    def test_no_rollback_when_disabled(self):
        """Test no rollback when auto-rollback is disabled."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(enabled=False, min_samples=10),
        )
        manager.start()

        # Add terrible treatment performance
        for _ in range(20):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=True)

        result = manager.check_rollback_needed()

        assert result.should_rollback is False
        assert "disabled" in result.reason.lower()

    def test_rollback_on_fp_rate_increase(self):
        """Test rollback triggered when treatment FP rate increases significantly."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(
                max_fp_rate_increase=0.05,  # 5%
                min_samples=10,
                enabled=True,
            ),
        )
        manager.start()

        # Control: 10% FP rate
        for i in range(20):
            manager.record_control_feedback(is_false_positive=(i < 2))

        # Treatment: 25% FP rate (15% increase > 5% threshold)
        for i in range(20):
            manager.record_treatment_feedback(is_false_positive=(i < 5))

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "fp rate" in result.reason.lower()

    def test_rollback_on_latency_increase(self):
        """Test rollback triggered when treatment latency increases significantly."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(
                max_latency_increase_pct=50.0,
                min_samples=10,
                enabled=True,
            ),
        )
        manager.start()

        # Record feedback to meet threshold
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=False)

        # Control: 100ms latency
        for _ in range(20):
            manager.record_control_analysis(latency_ms=100.0)

        # Treatment: 200ms latency (100% increase > 50% threshold)
        for _ in range(20):
            manager.record_treatment_analysis(latency_ms=200.0)

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "latency" in result.reason.lower()

    def test_rollback_on_error_rate_increase(self):
        """Test rollback triggered when treatment error rate increases significantly."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(
                max_error_rate_increase=0.05,  # 5%
                min_samples=10,
                enabled=True,
            ),
        )
        manager.start()

        # Record feedback to meet threshold
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=False)

        # Control: 0% error rate
        for _ in range(20):
            manager.record_control_analysis(has_error=False)

        # Treatment: 15% error rate (15% increase > 5% threshold)
        for i in range(20):
            manager.record_treatment_analysis(has_error=(i < 3))

        result = manager.check_rollback_needed()

        assert result.should_rollback is True
        assert "error" in result.reason.lower()

    def test_no_rollback_when_treatment_is_better(self):
        """Test no rollback when treatment outperforms control."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(
                max_fp_rate_increase=0.05,
                max_latency_increase_pct=50.0,
                min_samples=10,
                enabled=True,
            ),
        )
        manager.start()

        # Control: 30% FP rate, 150ms latency
        for i in range(20):
            manager.record_control_feedback(is_false_positive=(i < 6))
            manager.record_control_analysis(latency_ms=150.0)

        # Treatment: 10% FP rate, 100ms latency (BETTER on both metrics)
        for i in range(20):
            manager.record_treatment_feedback(is_false_positive=(i < 2))
            manager.record_treatment_analysis(latency_ms=100.0)

        result = manager.check_rollback_needed()

        assert result.should_rollback is False
        assert "acceptable" in result.reason.lower()


# =============================================================================
# Test: Experiment Completion
# =============================================================================


class TestExperimentCompletion:
    """Tests for experiment completion scenarios."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the global rollout manager before and after each test."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_experiment_expiry_detection(self):
        """Test experiment is marked expired after duration elapses."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(test_duration_hours=48),
            rollback_config=AutoRollbackConfig(),
        )
        manager.start()

        # Simulate started 50 hours ago
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=50)

        assert manager.is_expired is True
        assert manager.remaining_hours == 0

    def test_experiment_not_expired_within_duration(self):
        """Test experiment not expired while within duration."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(test_duration_hours=48),
            rollback_config=AutoRollbackConfig(),
        )
        manager.start()

        # Simulate started 24 hours ago
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=24)

        assert manager.is_expired is False
        assert 23 <= manager.remaining_hours <= 25  # ~24 hours remaining

    def test_manual_stop_deactivates_experiment(self):
        """Test manual stop deactivates the experiment."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(),
        )
        manager.start()
        assert manager.is_active is True

        manager.stop()

        assert manager.is_active is False
        # Note: started_at is preserved for historical records

    def test_metrics_preserved_after_stop(self):
        """Test metrics are preserved after experiment stops."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
        )

        manager = ABRolloutManager(
            rollout_config=ABRolloutConfig(),
            rollback_config=AutoRollbackConfig(),
        )
        manager.start()

        # Record some data
        for i in range(10):
            manager.record_control_feedback(is_false_positive=(i < 3))
            manager.record_treatment_feedback(is_false_positive=(i < 1))

        manager.stop()

        # Metrics should still be accessible
        assert manager.control_metrics.total_feedback_count == 10
        assert manager.treatment_metrics.total_feedback_count == 10
        assert manager.control_metrics.fp_rate == 0.3
        assert manager.treatment_metrics.fp_rate == 0.1


# =============================================================================
# Test: Full Lifecycle Scenario
# =============================================================================


class TestFullLifecycleScenario:
    """Integration-style tests for complete A/B rollout lifecycle."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the global rollout manager before and after each test."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_successful_experiment_lifecycle(self):
        """Test successful experiment that runs to completion."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            get_experiment_status,
            start_production_ab_rollout,
            stop_production_ab_rollout,
        )

        # Phase 1: Start experiment
        manager = start_production_ab_rollout()
        status = get_experiment_status()
        assert status["is_active"] is True

        # Phase 2: Collect data (simulated)
        manager.rollback_config.min_samples = 10

        for _ in range(50):
            # Both groups performing well
            manager.record_control_feedback(is_false_positive=False)
            manager.record_control_analysis(latency_ms=100.0, risk_score=50)
            manager.record_treatment_feedback(is_false_positive=False)
            manager.record_treatment_analysis(latency_ms=105.0, risk_score=45)

        # Phase 3: Check rollback (should not trigger)
        result = check_and_handle_rollback()
        assert result.should_rollback is False
        assert manager.is_active is True

        # Phase 4: Complete experiment
        stopped = stop_production_ab_rollout(reason="Experiment completed successfully")
        assert stopped is True

        # Phase 5: Verify final state
        status = get_experiment_status()
        assert status["is_active"] is False
        assert status["metrics"]["control"]["sample_count"] == 50
        assert status["metrics"]["treatment"]["sample_count"] == 50

    def test_experiment_with_auto_rollback(self):
        """Test experiment that triggers auto-rollback due to degradation."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            get_experiment_status,
            start_production_ab_rollout,
        )

        # Phase 1: Start experiment
        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Phase 2: Collect data showing treatment degradation
        for i in range(30):
            # Control: 10% FP rate
            manager.record_control_feedback(is_false_positive=(i < 3))
            manager.record_control_analysis(latency_ms=100.0)

            # Treatment: 30% FP rate (significant degradation)
            manager.record_treatment_feedback(is_false_positive=(i < 9))
            manager.record_treatment_analysis(latency_ms=100.0)

        # Phase 3: Check rollback (should trigger)
        result = check_and_handle_rollback()
        assert result.should_rollback is True

        # Phase 4: Verify experiment stopped
        status = get_experiment_status()
        assert status["is_active"] is False

        # Phase 5: Verify we can see the degradation in metrics
        assert status["metrics"]["control"]["fp_rate"] == 0.1
        assert status["metrics"]["treatment"]["fp_rate"] == 0.3
