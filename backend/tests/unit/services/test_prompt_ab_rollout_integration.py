"""Unit tests for Prompt A/B Rollout Integration (NEM-3338), analyzer half removed by R8 S2b.

Phase 7.2 wired the A/B rollout to the per-event analyzer: the analyzer held
an ABRolloutManager, assigned each camera its experiment group, recorded its
own analysis metrics into that group, asked for the rollback check on a timer
and mapped the group to a prompt version. R8 S2 deletes NemotronAnalyzer and
those six wrapper methods (set_rollout_manager / get_rollout_manager /
get_experiment_group / record_rollout_analysis / check_rollout_rollback /
execute_rollout_rollback / get_rollout_summary / get_prompt_version_for_rollout
exist in no shipped module any more -- grep finds only the config-level
originals they delegated to). So this file's analyzer-driven classes went:

- ENDED: TestNemotronAnalyzerABRolloutIntegration (manager hand-off, group
  assignment, per-analysis metric routing -- all through the deleted wrapper)
  and TestRollbackTriggerDuringAnalysis (the periodic check inside the
  analysis path). The rollback LOGIC they reached through the analyzer is live
  and pinned where it lives: backend/config/prompt_ab_rollout.py's
  check_rollback_needed in tests/unit/config/test_prompt_ab_rollout.py
  ::TestRollbackCheckLogic, and the production wrapper check_and_handle_rollback
  (which stops the experiment) in test_ab_rollout_production.py
  ::TestRollbackDetection.
- STILL SHIPPED, repointed to that code rather than deleted, because the
  behavior is real and was pinned nowhere else: the metrics summary's
  ``experiment`` section (now asserted on ABRolloutManager.get_metrics_summary
  directly -- the analyzer's get_rollout_summary was a pass-through) and the
  group -> prompt-version mapping (now asserted on ab_rollout_production's
  live get_camera_assignment, which is what a caller uses instead of the
  analyzer's get_prompt_version_for_rollout).
- KEPT AS-IS: TestFeedbackRecordingForExperiment -- it drives the config
  singleton's feedback recording, never the analyzer.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def rollout_manager():
    """Create a configured rollout manager for testing."""
    from backend.config.prompt_ab_rollout import (
        ABRolloutConfig,
        ABRolloutManager,
        AutoRollbackConfig,
    )

    rollout_config = ABRolloutConfig(
        treatment_percentage=0.5,
        test_duration_hours=48,
    )
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


@pytest.fixture
def global_manager():
    """A live production manager on the module singleton, torn down after.

    Replaces the analyzer the deleted tests here used to hold: the shipped
    callers reach the experiment through the singleton (get_rollout_manager /
    get_camera_assignment), not through a per-analyzer attribute.
    """
    from backend.config.ab_rollout_production import start_production_ab_rollout
    from backend.config.prompt_ab_rollout import reset_rollout_manager

    reset_rollout_manager()
    try:
        yield start_production_ab_rollout()
    finally:
        reset_rollout_manager()


# =============================================================================
# Test: Feedback Recording
# =============================================================================


class TestFeedbackRecordingForExperiment:
    """Tests for recording feedback with experiment group tracking."""

    @pytest.fixture
    def mock_event_with_camera(self):
        """Create a mock event with camera_id."""
        event = MagicMock()
        event.id = 1
        event.camera_id = "front_door"
        event.risk_score = 50
        return event

    @pytest.mark.asyncio
    async def test_feedback_processor_records_to_experiment_group(
        self, rollout_manager, mock_event_with_camera
    ):
        """Test FeedbackProcessor records feedback to correct experiment group."""
        from backend.config.prompt_ab_rollout import (
            ExperimentGroup,
            configure_rollout_manager,
            reset_rollout_manager,
        )

        # Configure global rollout manager
        reset_rollout_manager()
        manager = configure_rollout_manager(
            rollout_config=rollout_manager.rollout_config,
            rollback_config=rollout_manager.rollback_config,
        )
        manager.start()

        # Determine expected group for the camera
        camera_id = mock_event_with_camera.camera_id
        expected_group = manager.get_group_for_camera(camera_id)

        # Simulate recording feedback
        if expected_group == ExperimentGroup.CONTROL:
            manager.record_control_feedback(is_false_positive=True)
            assert manager.control_metrics.total_feedback_count == 1
            assert manager.control_metrics.false_positive_count == 1
        else:
            manager.record_treatment_feedback(is_false_positive=True)
            assert manager.treatment_metrics.total_feedback_count == 1
            assert manager.treatment_metrics.false_positive_count == 1

        # Cleanup
        reset_rollout_manager()

    @pytest.mark.asyncio
    async def test_feedback_type_determines_fp_count(self, rollout_manager):
        """Test different feedback types correctly update FP count."""
        # Record various feedback types for control
        rollout_manager.record_control_feedback(is_false_positive=True)  # FP
        rollout_manager.record_control_feedback(is_false_positive=False)  # Correct
        rollout_manager.record_control_feedback(is_false_positive=True)  # FP
        rollout_manager.record_control_feedback(is_false_positive=False)  # Severity wrong

        assert rollout_manager.control_metrics.total_feedback_count == 4
        assert rollout_manager.control_metrics.false_positive_count == 2
        assert rollout_manager.control_metrics.fp_rate == 0.5


# =============================================================================
# Test: Metrics Summary
# =============================================================================


class TestExperimentMetricsSummary:
    """Tests for getting experiment metrics summary."""

    def test_get_experiment_summary(self, rollout_manager):
        """Test getting experiment metrics summary from the manager itself.

        R8 S2b repoint: the analyzer's get_rollout_summary was a pass-through
        to ABRolloutManager.get_metrics_summary, so the assertions are
        unchanged -- only the (deleted) middleman is gone. The ``experiment``
        section below is the only pin on that part of the summary shape.
        """
        for _ in range(5):
            rollout_manager.record_control_feedback(is_false_positive=False)
            rollout_manager.record_control_analysis(latency_ms=100.0, risk_score=50)

        for _ in range(5):
            rollout_manager.record_treatment_feedback(is_false_positive=False)
            rollout_manager.record_treatment_analysis(latency_ms=120.0, risk_score=40)

        summary = rollout_manager.get_metrics_summary()

        assert "control" in summary
        assert "treatment" in summary
        assert "experiment" in summary

        assert summary["control"]["sample_count"] == 5
        assert summary["treatment"]["sample_count"] == 5


# =============================================================================
# Test: Prompt Version Selection Based on Group
# =============================================================================


class TestPromptVersionSelection:
    """Tests for selecting prompt version based on experiment group.

    R8 S2b repoint: ``get_camera_assignment`` in ab_rollout_production is the
    shipped answer to the question the deleted analyzer wrapper answered --
    which prompt version does this camera's experiment group get? The mapping
    was asserted nowhere else, so it moves here rather than dying with the
    wrapper.
    """

    def test_control_group_uses_v1_prompt(self, global_manager):
        """Test control group uses V1 (original) prompt."""
        from backend.config.ab_rollout_production import get_camera_assignment
        from backend.config.prompt_ab_rollout import ExperimentGroup
        from backend.config.prompt_experiment import PromptVersion

        for i in range(100):
            camera_id = f"camera_{i}"
            if global_manager.get_group_for_camera(camera_id) == ExperimentGroup.CONTROL:
                assignment = get_camera_assignment(camera_id)
                assert assignment["group"] == ExperimentGroup.CONTROL.value
                assert assignment["prompt_version"] == PromptVersion.V1_ORIGINAL.value
                return
        pytest.fail("no control-group camera found in 100 cameras at a 50% split")

    def test_treatment_group_uses_v2_prompt(self, global_manager):
        """Test treatment group uses V2 (calibrated) prompt."""
        from backend.config.ab_rollout_production import get_camera_assignment
        from backend.config.prompt_ab_rollout import ExperimentGroup
        from backend.config.prompt_experiment import PromptVersion

        for i in range(100):
            camera_id = f"camera_{i}"
            if global_manager.get_group_for_camera(camera_id) == ExperimentGroup.TREATMENT:
                assignment = get_camera_assignment(camera_id)
                assert assignment["group"] == ExperimentGroup.TREATMENT.value
                assert assignment["prompt_version"] == PromptVersion.V2_CALIBRATED.value
                return
        pytest.fail("no treatment-group camera found in 100 cameras at a 50% split")
