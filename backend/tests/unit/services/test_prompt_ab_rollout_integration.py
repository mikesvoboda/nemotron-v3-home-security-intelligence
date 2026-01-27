"""Unit tests for Prompt A/B Rollout Integration with NemotronAnalyzer (NEM-3338).

Phase 7.2: A/B Testing for Prompt Rollout.

These tests cover:
1. Integration of ABRolloutManager with NemotronAnalyzer
2. Automatic group assignment during analysis
3. Metrics recording based on group assignment
4. Feedback recording for experiment groups
5. Rollback check triggering during analysis pipeline

TDD: Write tests first (RED), then implement to make them GREEN.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    return mock_client


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
    mock.prompt_shadow_mode_enabled = False
    # Guided JSON settings (NEM-3726)
    mock.nemotron_use_guided_json = False
    mock.nemotron_guided_json_fallback = True
    return mock


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


# =============================================================================
# Test: NemotronAnalyzer Integration
# =============================================================================


class TestNemotronAnalyzerABRolloutIntegration:
    """Tests for A/B rollout integration in NemotronAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyzer_accepts_rollout_manager(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test NemotronAnalyzer can be configured with ABRolloutManager."""
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

            # Set rollout manager
            analyzer.set_rollout_manager(rollout_manager)

            # Verify it's set
            assert analyzer.get_rollout_manager() is rollout_manager

    @pytest.mark.asyncio
    async def test_analyzer_uses_rollout_manager_for_group_assignment(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test analyzer uses rollout manager to determine experiment group."""
        from backend.config.prompt_ab_rollout import ExperimentGroup
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
            analyzer.set_rollout_manager(rollout_manager)

            # Get experiment group for a camera
            camera_id = "front_door"
            group = analyzer.get_experiment_group(camera_id)

            # Should be one of the valid groups
            assert group in (ExperimentGroup.CONTROL, ExperimentGroup.TREATMENT)

            # Same camera should get same group
            for _ in range(10):
                assert analyzer.get_experiment_group(camera_id) == group

    @pytest.mark.asyncio
    async def test_analyzer_records_metrics_to_correct_group(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test analyzer records metrics to the correct experiment group."""
        from backend.config.prompt_ab_rollout import ExperimentGroup
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
            analyzer.set_rollout_manager(rollout_manager)

            # Find cameras for each group
            control_camera = None
            treatment_camera = None

            for i in range(100):
                camera_id = f"camera_{i}"
                group = analyzer.get_experiment_group(camera_id)
                if group == ExperimentGroup.CONTROL and control_camera is None:
                    control_camera = camera_id
                elif group == ExperimentGroup.TREATMENT and treatment_camera is None:
                    treatment_camera = camera_id
                if control_camera and treatment_camera:
                    break

            # Record analysis for control camera
            analyzer.record_rollout_analysis(
                camera_id=control_camera,
                latency_ms=100.0,
                risk_score=50,
            )

            # Record analysis for treatment camera
            analyzer.record_rollout_analysis(
                camera_id=treatment_camera,
                latency_ms=150.0,
                risk_score=40,
            )

            # Verify metrics were recorded to correct groups
            assert rollout_manager.control_metrics.total_analyses == 1
            assert rollout_manager.treatment_metrics.total_analyses == 1


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
# Test: Rollback Trigger During Analysis
# =============================================================================


class TestRollbackTriggerDuringAnalysis:
    """Tests for rollback condition checking during analysis pipeline."""

    @pytest.mark.asyncio
    async def test_rollback_check_called_periodically(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test rollback check is called during analysis pipeline."""
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
            analyzer.set_rollout_manager(rollout_manager)

            # Check rollback result
            result = analyzer.check_rollout_rollback()

            # Should have a valid result
            assert hasattr(result, "should_rollback")
            assert hasattr(result, "reason")

    @pytest.mark.asyncio
    async def test_rollback_triggers_experiment_stop(self, mock_redis_client, mock_settings):
        """Test rollback trigger stops the experiment."""
        from backend.config.prompt_ab_rollout import (
            ABRolloutConfig,
            ABRolloutManager,
            AutoRollbackConfig,
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

            # Create manager with low threshold for testing
            rollout_config = ABRolloutConfig(treatment_percentage=0.5)
            rollback_config = AutoRollbackConfig(
                max_fp_rate_increase=0.05,
                min_samples=5,
                enabled=True,
            )
            manager = ABRolloutManager(rollout_config, rollback_config)
            manager.start()

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)
            analyzer.set_rollout_manager(manager)

            # Simulate bad treatment performance
            for _ in range(10):
                manager.record_control_feedback(is_false_positive=False)
            for _ in range(10):
                manager.record_treatment_feedback(is_false_positive=True)  # 100% FP

            # Check rollback
            result = analyzer.check_rollout_rollback()

            assert result.should_rollback is True

            # Execute rollback
            analyzer.execute_rollout_rollback()

            # Experiment should be stopped
            assert manager.is_active is False


# =============================================================================
# Test: Metrics Summary
# =============================================================================


class TestExperimentMetricsSummary:
    """Tests for getting experiment metrics summary."""

    @pytest.mark.asyncio
    async def test_get_experiment_summary(self, mock_redis_client, mock_settings, rollout_manager):
        """Test getting experiment metrics summary."""
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
            analyzer.set_rollout_manager(rollout_manager)

            # Record some data
            for _ in range(5):
                rollout_manager.record_control_feedback(is_false_positive=False)
                rollout_manager.record_control_analysis(latency_ms=100.0, risk_score=50)

            for _ in range(5):
                rollout_manager.record_treatment_feedback(is_false_positive=False)
                rollout_manager.record_treatment_analysis(latency_ms=120.0, risk_score=40)

            # Get summary through analyzer
            summary = analyzer.get_rollout_summary()

            assert "control" in summary
            assert "treatment" in summary
            assert "experiment" in summary

            assert summary["control"]["sample_count"] == 5
            assert summary["treatment"]["sample_count"] == 5


# =============================================================================
# Test: Prompt Version Selection Based on Group
# =============================================================================


class TestPromptVersionSelection:
    """Tests for selecting prompt version based on experiment group."""

    @pytest.mark.asyncio
    async def test_control_group_uses_v1_prompt(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test control group uses V1 (original) prompt."""
        from backend.config.prompt_ab_rollout import ExperimentGroup
        from backend.config.prompt_experiment import PromptVersion
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
            analyzer.set_rollout_manager(rollout_manager)

            # Find a control camera
            for i in range(100):
                camera_id = f"camera_{i}"
                if rollout_manager.get_group_for_camera(camera_id) == ExperimentGroup.CONTROL:
                    # Get prompt version for control camera
                    version = analyzer.get_prompt_version_for_rollout(camera_id)
                    assert version == PromptVersion.V1_ORIGINAL
                    break

    @pytest.mark.asyncio
    async def test_treatment_group_uses_v2_prompt(
        self, mock_redis_client, mock_settings, rollout_manager
    ):
        """Test treatment group uses V2 (calibrated) prompt."""
        from backend.config.prompt_ab_rollout import ExperimentGroup
        from backend.config.prompt_experiment import PromptVersion
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
            analyzer.set_rollout_manager(rollout_manager)

            # Find a treatment camera
            for i in range(100):
                camera_id = f"camera_{i}"
                if rollout_manager.get_group_for_camera(camera_id) == ExperimentGroup.TREATMENT:
                    # Get prompt version for treatment camera
                    version = analyzer.get_prompt_version_for_rollout(camera_id)
                    assert version == PromptVersion.V2_CALIBRATED
                    break
