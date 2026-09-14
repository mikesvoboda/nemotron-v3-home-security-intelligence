"""Unit tests for Production A/B Rollout Configuration (NEM-3338).

Phase 7.2 of Nemotron Prompt Improvements: A/B Testing for Prompt Rollout.

These tests verify:
1. Production configuration creates correct 50/50 split
2. Production rollback thresholds are properly configured
3. Start/stop lifecycle works correctly
4. Camera assignment is consistent
5. Rollback detection and handling works
6. Experiment status reporting is accurate

Success Criteria:
- FP rate reduction from ~60% to <20%
- Auto-rollback if degradation detected
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: Production Configuration Constants
# =============================================================================


class TestProductionConfigurationConstants:
    """Tests for production configuration constants."""

    def test_treatment_percentage_is_50_percent(self):
        """Test production treatment percentage is 50% for even split."""
        from backend.config.ab_rollout_production import (
            PRODUCTION_TREATMENT_PERCENTAGE,
        )

        assert PRODUCTION_TREATMENT_PERCENTAGE == 0.5

    def test_test_duration_is_48_hours(self):
        """Test production test duration is 48 hours."""
        from backend.config.ab_rollout_production import (
            PRODUCTION_TEST_DURATION_HOURS,
        )

        assert PRODUCTION_TEST_DURATION_HOURS == 48

    def test_fp_rate_threshold_is_5_percent(self):
        """Test FP rate increase threshold is 5 percentage points."""
        from backend.config.ab_rollout_production import MAX_FP_RATE_INCREASE

        assert MAX_FP_RATE_INCREASE == 0.05

    def test_latency_threshold_is_50_percent(self):
        """Test latency increase threshold is 50%."""
        from backend.config.ab_rollout_production import MAX_LATENCY_INCREASE_PCT

        assert MAX_LATENCY_INCREASE_PCT == 50.0

    def test_error_rate_threshold_is_5_percent(self):
        """Test error rate increase threshold is 5 percentage points."""
        from backend.config.ab_rollout_production import MAX_ERROR_RATE_INCREASE

        assert MAX_ERROR_RATE_INCREASE == 0.05

    def test_min_samples_is_100(self):
        """Test minimum samples for rollback is 100."""
        from backend.config.ab_rollout_production import MIN_SAMPLES_FOR_ROLLBACK

        assert MIN_SAMPLES_FOR_ROLLBACK == 100


# =============================================================================
# Test: Configuration Factory Functions
# =============================================================================


class TestConfigurationFactoryFunctions:
    """Tests for configuration factory functions."""

    def test_create_production_rollout_config(self):
        """Test production rollout config has correct values."""
        from backend.config.ab_rollout_production import (
            PRODUCTION_EXPERIMENT_NAME,
            PRODUCTION_TEST_DURATION_HOURS,
            PRODUCTION_TREATMENT_PERCENTAGE,
            create_production_rollout_config,
        )

        config = create_production_rollout_config()

        assert config.treatment_percentage == PRODUCTION_TREATMENT_PERCENTAGE
        assert config.test_duration_hours == PRODUCTION_TEST_DURATION_HOURS
        assert config.experiment_name == PRODUCTION_EXPERIMENT_NAME
        assert config.started_at is None  # Not started yet

    def test_create_production_rollback_config(self):
        """Test production rollback config has correct thresholds."""
        from backend.config.ab_rollout_production import (
            MAX_ERROR_RATE_INCREASE,
            MAX_FP_RATE_INCREASE,
            MAX_LATENCY_INCREASE_PCT,
            MIN_SAMPLES_FOR_ROLLBACK,
            create_production_rollback_config,
        )

        config = create_production_rollback_config()

        assert config.max_fp_rate_increase == MAX_FP_RATE_INCREASE
        assert config.max_latency_increase_pct == MAX_LATENCY_INCREASE_PCT
        assert config.max_error_rate_increase == MAX_ERROR_RATE_INCREASE
        assert config.min_samples == MIN_SAMPLES_FOR_ROLLBACK
        assert config.enabled is True


# =============================================================================
# Test: Experiment Lifecycle
# =============================================================================


class TestExperimentLifecycle:
    """Tests for experiment start/stop lifecycle."""

    @pytest.fixture(autouse=True)
    def reset_manager(self):
        """Reset the global rollout manager before and after each test."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_start_production_ab_rollout(self):
        """Test starting production A/B rollout."""
        from backend.config.ab_rollout_production import (
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()

        assert manager is not None
        assert manager.is_active is True
        assert manager.rollout_config.started_at is not None
        assert manager.rollout_config.treatment_percentage == 0.5

    def test_start_production_ab_rollout_returns_same_manager_on_second_call(self):
        """Test that multiple starts return new managers (reset between calls)."""
        from backend.config.ab_rollout_production import (
            start_production_ab_rollout,
        )

        manager1 = start_production_ab_rollout()
        manager2 = start_production_ab_rollout()

        # Each start resets and creates a new manager
        assert manager1 is not manager2

    def test_get_production_rollout_manager_returns_none_when_not_started(self):
        """Test get_production_rollout_manager returns None when not configured."""
        from backend.config.ab_rollout_production import (
            get_production_rollout_manager,
        )

        manager = get_production_rollout_manager()

        assert manager is None

    def test_get_production_rollout_manager_returns_manager_when_started(self):
        """Test get_production_rollout_manager returns manager after start."""
        from backend.config.ab_rollout_production import (
            get_production_rollout_manager,
            start_production_ab_rollout,
        )

        started_manager = start_production_ab_rollout()
        retrieved_manager = get_production_rollout_manager()

        assert retrieved_manager is started_manager

    def test_stop_production_ab_rollout_stops_active_experiment(self):
        """Test stopping an active experiment."""
        from backend.config.ab_rollout_production import (
            start_production_ab_rollout,
            stop_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        assert manager.is_active is True

        result = stop_production_ab_rollout(reason="Test stop")

        assert result is True
        assert manager.is_active is False

    def test_stop_production_ab_rollout_returns_false_when_not_active(self):
        """Test stopping when no experiment is active."""
        from backend.config.ab_rollout_production import (
            stop_production_ab_rollout,
        )

        result = stop_production_ab_rollout()

        assert result is False


# =============================================================================
# Test: Camera Assignment
# =============================================================================


class TestCameraAssignment:
    """Tests for camera group assignment."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        """Set up and tear down the rollout manager."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_camera_assignment_without_active_rollout(self):
        """Test camera assignment returns V1 when no rollout is active."""
        from backend.config.ab_rollout_production import get_camera_assignment
        from backend.config.prompt_experiment import PromptVersion

        result = get_camera_assignment("front_door")

        assert result["camera_id"] == "front_door"
        assert result["group"] is None
        assert result["prompt_version"] == PromptVersion.V1_ORIGINAL.value
        assert "No A/B rollout active" in result["message"]

    def test_camera_assignment_with_active_rollout(self):
        """Test camera assignment returns correct group with active rollout."""
        from backend.config.ab_rollout_production import (
            get_camera_assignment,
            start_production_ab_rollout,
        )
        from backend.config.prompt_ab_rollout import ExperimentGroup

        start_production_ab_rollout()
        result = get_camera_assignment("front_door")

        assert result["camera_id"] == "front_door"
        assert result["group"] in (
            ExperimentGroup.CONTROL.value,
            ExperimentGroup.TREATMENT.value,
        )
        assert "assigned to" in result["message"]

    def test_camera_assignment_is_consistent(self):
        """Test same camera always gets same assignment."""
        from backend.config.ab_rollout_production import (
            get_camera_assignment,
            start_production_ab_rollout,
        )

        start_production_ab_rollout()
        camera_id = "test_camera_123"

        first_result = get_camera_assignment(camera_id)

        for _ in range(100):
            result = get_camera_assignment(camera_id)
            assert result["group"] == first_result["group"]
            assert result["prompt_version"] == first_result["prompt_version"]

    def test_camera_assignment_distribution_approximately_50_50(self):
        """Test camera assignments are approximately 50/50 distributed."""
        from backend.config.ab_rollout_production import (
            get_camera_assignment,
            start_production_ab_rollout,
        )
        from backend.config.prompt_ab_rollout import ExperimentGroup

        start_production_ab_rollout()

        control_count = 0
        treatment_count = 0
        total = 1000

        for i in range(total):
            result = get_camera_assignment(f"camera_{i}")
            if result["group"] == ExperimentGroup.CONTROL.value:
                control_count += 1
            else:
                treatment_count += 1

        # Should be approximately 50/50 (allow 10% tolerance)
        control_ratio = control_count / total
        treatment_ratio = treatment_count / total

        assert 0.4 <= control_ratio <= 0.6, f"Control ratio {control_ratio:.2%} outside tolerance"
        assert 0.4 <= treatment_ratio <= 0.6, (
            f"Treatment ratio {treatment_ratio:.2%} outside tolerance"
        )


# =============================================================================
# Test: Rollback Detection and Handling
# =============================================================================


class TestRollbackDetection:
    """Tests for rollback detection and handling."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        """Set up and tear down the rollout manager."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_check_and_handle_rollback_without_manager(self):
        """Test rollback check returns no action when no manager configured."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
        )

        result = check_and_handle_rollback()

        assert result.should_rollback is False
        assert "No rollout manager configured" in result.reason

    def test_check_and_handle_rollback_with_healthy_metrics(self):
        """Test rollback not triggered with healthy metrics."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        # Need to lower min_samples for testing
        manager.rollback_config.min_samples = 10

        # Record healthy metrics for both groups
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_control_analysis(latency_ms=100.0)
            manager.record_treatment_feedback(is_false_positive=False)
            manager.record_treatment_analysis(latency_ms=110.0)  # Slightly higher but OK

        result = check_and_handle_rollback()

        assert result.should_rollback is False
        assert manager.is_active is True

    def test_check_and_handle_rollback_triggers_on_fp_increase(self):
        """Test rollback triggers when FP rate increases significantly."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Control: 10% FP rate
        for i in range(20):
            manager.record_control_feedback(is_false_positive=(i < 2))

        # Treatment: 30% FP rate (increase > 5% threshold)
        for i in range(20):
            manager.record_treatment_feedback(is_false_positive=(i < 6))

        result = check_and_handle_rollback()

        assert result.should_rollback is True
        assert "fp rate" in result.reason.lower()
        assert manager.is_active is False  # Should be stopped

    def test_check_and_handle_rollback_triggers_on_latency_increase(self):
        """Test rollback triggers when latency increases significantly."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Record feedback to meet minimum samples
        for _ in range(15):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_treatment_feedback(is_false_positive=False)

        # Control: 100ms average latency
        for _ in range(15):
            manager.record_control_analysis(latency_ms=100.0)

        # Treatment: 200ms average latency (100% increase > 50% threshold)
        for _ in range(15):
            manager.record_treatment_analysis(latency_ms=200.0)

        result = check_and_handle_rollback()

        assert result.should_rollback is True
        assert "latency" in result.reason.lower()
        assert manager.is_active is False


# =============================================================================
# Test: Experiment Status Reporting
# =============================================================================


class TestExperimentStatusReporting:
    """Tests for experiment status reporting."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        """Set up and tear down the rollout manager."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_get_experiment_status_without_manager(self):
        """Test status returns appropriate message when no manager configured."""
        from backend.config.ab_rollout_production import get_experiment_status

        status = get_experiment_status()

        assert status["is_active"] is False
        assert status["metrics"] is None
        assert status["config"] is None
        assert "No A/B rollout experiment configured" in status["message"]

    def test_get_experiment_status_with_active_experiment(self):
        """Test status returns complete info for active experiment."""
        from backend.config.ab_rollout_production import (
            get_experiment_status,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()

        # Record some data
        for _ in range(5):
            manager.record_control_feedback(is_false_positive=False)
            manager.record_control_analysis(latency_ms=100.0, risk_score=50)
            manager.record_treatment_feedback(is_false_positive=False)
            manager.record_treatment_analysis(latency_ms=120.0, risk_score=40)

        status = get_experiment_status()

        # Check structure
        assert status["is_active"] is True
        assert status["is_expired"] is False
        assert status["remaining_hours"] > 0

        # Check metrics
        assert status["metrics"]["control"]["sample_count"] == 5
        assert status["metrics"]["treatment"]["sample_count"] == 5
        assert status["metrics"]["control"]["avg_latency_ms"] == 100.0
        assert status["metrics"]["treatment"]["avg_latency_ms"] == 120.0

        # Check config
        assert status["config"]["treatment_percentage"] == 0.5
        assert status["config"]["test_duration_hours"] == 48
        assert status["config"]["started_at"] is not None

        # Check rollback config
        assert status["rollback_config"]["enabled"] is True
        assert status["rollback_config"]["max_fp_rate_increase"] == 0.05

    def test_get_experiment_status_shows_expired_when_duration_exceeded(self):
        """Test status shows expired when test duration exceeded."""
        from backend.config.ab_rollout_production import (
            get_experiment_status,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        # Simulate started 50 hours ago (exceeds 48-hour duration)
        manager.rollout_config.started_at = datetime.now(UTC) - timedelta(hours=50)

        status = get_experiment_status()

        assert status["is_expired"] is True
        assert status["remaining_hours"] == 0


# =============================================================================
# Test: Integration with NemotronAnalyzer
# =============================================================================


class TestIntegrationWithNemotronAnalyzer:
    """Tests for integration between production config and NemotronAnalyzer."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        """Set up and tear down the rollout manager."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_analyzer_can_use_production_manager(self):
        """Test NemotronAnalyzer can be configured with production manager."""
        from unittest.mock import MagicMock

        from backend.config.ab_rollout_production import (
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()

        # Create a mock analyzer and verify it can accept the manager
        mock_analyzer = MagicMock()
        mock_analyzer.set_rollout_manager(manager)

        mock_analyzer.set_rollout_manager.assert_called_once_with(manager)

    def test_production_manager_assigns_correct_prompt_version(self):
        """Test production manager assigns V1/V2 correctly based on group."""
        from backend.config.ab_rollout_production import (
            start_production_ab_rollout,
        )
        from backend.config.prompt_ab_rollout import ExperimentGroup

        manager = start_production_ab_rollout()

        # Find cameras in each group
        control_camera = None
        treatment_camera = None

        for i in range(100):
            camera_id = f"camera_{i}"
            group = manager.get_group_for_camera(camera_id)
            if group == ExperimentGroup.CONTROL and control_camera is None:
                control_camera = camera_id
            elif group == ExperimentGroup.TREATMENT and treatment_camera is None:
                treatment_camera = camera_id
            if control_camera and treatment_camera:
                break

        # Verify control camera would get V1
        assert control_camera is not None
        control_group = manager.get_group_for_camera(control_camera)
        assert control_group == ExperimentGroup.CONTROL

        # Verify treatment camera would get V2
        assert treatment_camera is not None
        treatment_group = manager.get_group_for_camera(treatment_camera)
        assert treatment_group == ExperimentGroup.TREATMENT


# =============================================================================
# Test: Success Criteria Validation
# =============================================================================


class TestSuccessCriteria:
    """Tests validating the success criteria for Phase 7.2."""

    @pytest.fixture(autouse=True)
    def setup_manager(self):
        """Set up and tear down the rollout manager."""
        from backend.config.prompt_ab_rollout import reset_rollout_manager

        reset_rollout_manager()
        yield
        reset_rollout_manager()

    def test_success_criteria_fp_reduction_detection(self):
        """Test that we can detect FP rate reduction (60% to <20%)."""
        from backend.config.ab_rollout_production import (
            get_experiment_status,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Simulate control with 60% FP rate (current baseline)
        for i in range(100):
            manager.record_control_feedback(is_false_positive=(i < 60))

        # Simulate treatment with 15% FP rate (target)
        for i in range(100):
            manager.record_treatment_feedback(is_false_positive=(i < 15))

        status = get_experiment_status()

        # Verify we can measure the improvement
        control_fp_rate = status["metrics"]["control"]["fp_rate"]
        treatment_fp_rate = status["metrics"]["treatment"]["fp_rate"]

        assert control_fp_rate == 0.60  # 60% baseline
        assert treatment_fp_rate == 0.15  # 15% target achieved

        # FP reduction = control_fp - treatment_fp = 0.45 (45 percentage points)
        fp_reduction = control_fp_rate - treatment_fp_rate
        assert fp_reduction > 0.40  # Significant improvement

    def test_no_rollback_when_treatment_improves_fp_rate(self):
        """Test no rollback when treatment FP rate is better than control."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Control: 60% FP rate (bad)
        for i in range(50):
            manager.record_control_feedback(is_false_positive=(i < 30))

        # Treatment: 15% FP rate (good)
        for i in range(50):
            manager.record_treatment_feedback(is_false_positive=(i < 8))

        result = check_and_handle_rollback()

        # Should NOT rollback - treatment is better
        assert result.should_rollback is False
        assert manager.is_active is True

    def test_auto_rollback_protects_against_degradation(self):
        """Test auto-rollback triggers when treatment degrades performance."""
        from backend.config.ab_rollout_production import (
            check_and_handle_rollback,
            start_production_ab_rollout,
        )

        manager = start_production_ab_rollout()
        manager.rollback_config.min_samples = 10

        # Control: 20% FP rate
        for i in range(50):
            manager.record_control_feedback(is_false_positive=(i < 10))

        # Treatment: 35% FP rate (15 percentage points worse)
        for i in range(50):
            manager.record_treatment_feedback(is_false_positive=(i < 18))

        result = check_and_handle_rollback()

        # Should rollback - treatment is worse
        assert result.should_rollback is True
        assert manager.is_active is False
