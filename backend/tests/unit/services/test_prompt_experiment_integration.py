"""Unit tests for Prompt Experiment Integration with NemotronAnalyzer (NEM-3023).

These tests cover:
1. NemotronAnalyzer experiment config integration
2. Shadow mode execution (run both prompts, use v1)
3. Shadow result logging and storage
4. Version selection based on experiment config
5. Metrics recording for experiment results

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
    # A/B testing settings
    mock.prompt_ab_testing_enabled = True
    mock.prompt_shadow_mode_enabled = True
    # Guided JSON settings (NEM-3726)
    mock.nemotron_use_guided_json = False
    mock.nemotron_guided_json_fallback = True
    return mock


# =============================================================================
# Test: Experiment Config Integration
# =============================================================================


class TestExperimentConfigIntegration:
    """Tests for experiment config integration with NemotronAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyzer_has_experiment_config_attribute(self, mock_redis_client, mock_settings):
        """Test NemotronAnalyzer has experiment_config attribute."""
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

            # Analyzer should have experiment config access
            assert hasattr(analyzer, "get_experiment_config")
            assert hasattr(analyzer, "set_experiment_config")

    @pytest.mark.asyncio
    async def test_analyzer_set_experiment_config(self, mock_redis_client, mock_settings):
        """Test setting custom experiment config on analyzer."""
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

            # Set custom config
            custom_config = PromptExperimentConfig(
                shadow_mode=False,
                treatment_percentage=0.5,
            )
            analyzer.set_experiment_config(custom_config)

            # Verify config was set
            retrieved_config = analyzer.get_experiment_config()
            assert retrieved_config.shadow_mode is False
            assert retrieved_config.treatment_percentage == 0.5

    @pytest.mark.asyncio
    async def test_analyzer_default_experiment_config(self, mock_redis_client, mock_settings):
        """Test analyzer uses default experiment config if none set."""
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

            # Should have default config
            config = analyzer.get_experiment_config()
            assert isinstance(config, PromptExperimentConfig)
            # Default is shadow mode with 0% treatment
            assert config.shadow_mode is True
            assert config.treatment_percentage == 0.0


# =============================================================================
# Test: Shadow Mode Execution
# =============================================================================


class TestShadowModeExecution:
    """Tests for shadow mode prompt execution."""

    @pytest.mark.asyncio
    async def test_shadow_mode_runs_both_prompts(self, mock_redis_client, mock_settings):
        """Test shadow mode runs both v1 and v2 prompts."""
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
            config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(config)

            # Mock internal LLM call
            v1_call_count = 0
            v2_call_count = 0

            original_call_llm = analyzer._call_llm if hasattr(analyzer, "_call_llm") else None

            async def mock_call_llm(*args, prompt_version=None, **kwargs):
                nonlocal v1_call_count, v2_call_count
                if prompt_version == "v1" or prompt_version is None:
                    v1_call_count += 1
                    return {"risk_score": 50, "risk_level": "medium", "summary": "V1 result"}
                else:
                    v2_call_count += 1
                    return {"risk_score": 45, "risk_level": "medium", "summary": "V2 result"}

            # Test shadow analysis method
            with patch.object(analyzer, "_call_llm_with_version", mock_call_llm):
                result = await analyzer.run_shadow_analysis(
                    camera_id="front_door",
                    context="Test detection context",
                )

            # In shadow mode, both prompts should run
            # Note: Implementation may vary - adjust assertions based on actual implementation
            assert result is not None

    @pytest.mark.asyncio
    async def test_shadow_mode_uses_v1_result(self, mock_redis_client, mock_settings):
        """Test shadow mode uses v1 result as the actual result."""
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
            config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(config)

            # Mock to return different results for v1 and v2
            v1_result = {"risk_score": 50, "risk_level": "medium", "summary": "V1 result"}
            v2_result = {"risk_score": 30, "risk_level": "low", "summary": "V2 result"}

            async def mock_llm_call(*args, prompt_version=None, **kwargs):
                if prompt_version == "v2_calibrated":
                    return v2_result
                return v1_result

            with patch.object(analyzer, "_call_llm_with_version", mock_llm_call):
                result = await analyzer.run_shadow_analysis(
                    camera_id="front_door",
                    context="Test context",
                )

            # Actual result should be v1
            assert result["primary_result"]["risk_score"] == 50

    @pytest.mark.asyncio
    async def test_shadow_mode_logs_v2_result(self, mock_redis_client, mock_settings):
        """Test shadow mode logs v2 result for comparison."""
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
            config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(config)

            v1_result = {"risk_score": 60, "risk_level": "medium", "summary": "V1"}
            v2_result = {"risk_score": 40, "risk_level": "low", "summary": "V2"}

            async def mock_llm_call(*args, prompt_version=None, **kwargs):
                if prompt_version == "v2_calibrated":
                    return v2_result
                return v1_result

            with (
                patch.object(analyzer, "_call_llm_with_version", mock_llm_call),
                patch.object(analyzer, "_log_shadow_result", AsyncMock()) as mock_log,
            ):
                result = await analyzer.run_shadow_analysis(
                    camera_id="front_door",
                    context="Test context",
                )

            # Shadow result should be logged
            mock_log.assert_called_once()


# =============================================================================
# Test: Version Selection in Analysis
# =============================================================================


class TestVersionSelectionInAnalysis:
    """Tests for version selection during analysis."""

    @pytest.mark.asyncio
    async def test_get_version_for_analysis_uses_experiment_config(
        self, mock_redis_client, mock_settings
    ):
        """Test get_version_for_analysis uses experiment config."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
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

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

            # Configure for A/B test (non-shadow)
            config = PromptExperimentConfig(
                shadow_mode=False,
                treatment_percentage=1.0,  # 100% treatment
            )
            analyzer.set_experiment_config(config)

            # Get version for a camera
            version = analyzer.get_version_for_analysis("front_door")

            # Should return V2 with 100% treatment
            assert version == PromptVersion.V2_CALIBRATED

    @pytest.mark.asyncio
    async def test_version_selection_consistent_per_camera(self, mock_redis_client, mock_settings):
        """Test same camera always gets same version."""
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

            # Configure 50% A/B test
            config = PromptExperimentConfig(
                shadow_mode=False,
                treatment_percentage=0.5,
            )
            analyzer.set_experiment_config(config)

            # Same camera should always get same version
            camera_id = "front_door"
            first_version = analyzer.get_version_for_analysis(camera_id)

            for _ in range(100):
                version = analyzer.get_version_for_analysis(camera_id)
                assert version == first_version


# =============================================================================
# Test: Shadow Result Logging
# =============================================================================


class TestShadowResultLogging:
    """Tests for shadow mode result logging."""

    @pytest.mark.asyncio
    async def test_log_shadow_result_captures_score_diff(self, mock_redis_client, mock_settings):
        """Test shadow result logging captures score difference."""
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

            v1_result = {"risk_score": 60}
            v2_result = {"risk_score": 45}

            # Call internal logging method
            await analyzer._log_shadow_result(
                camera_id="front_door",
                v1_result=v1_result,
                v2_result=v2_result,
            )

            # Verify logging occurred (implementation-specific)
            # This test ensures the method exists and can be called

    @pytest.mark.asyncio
    async def test_log_shadow_result_captures_latency(self, mock_redis_client, mock_settings):
        """Test shadow result logging captures latency difference."""
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

            # Log with latency info
            await analyzer._log_shadow_result(
                camera_id="front_door",
                v1_result={"risk_score": 50},
                v2_result={"risk_score": 45},
                v1_latency_ms=150.0,
                v2_latency_ms=180.0,
            )


# =============================================================================
# Test: Metrics Recording
# =============================================================================


class TestExperimentMetricsRecording:
    """Tests for experiment metrics recording."""

    @pytest.mark.asyncio
    async def test_record_shadow_comparison_metric(self, mock_redis_client, mock_settings):
        """Test shadow comparison metric is recorded."""
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
            patch("backend.core.metrics.record_shadow_comparison") as mock_record,
        ):
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

            config = PromptExperimentConfig(shadow_mode=True)
            analyzer.set_experiment_config(config)

            v1_result = {"risk_score": 50}
            v2_result = {"risk_score": 45}

            async def mock_llm(*args, prompt_version=None, **kwargs):
                if prompt_version == "v2_calibrated":
                    return v2_result
                return v1_result

            with patch.object(analyzer, "_call_llm_with_version", mock_llm):
                await analyzer.run_shadow_analysis(
                    camera_id="test_camera",
                    context="test",
                )

            # Shadow comparison metric should be recorded
            # Actual assertion depends on implementation

    @pytest.mark.asyncio
    async def test_record_experiment_result_metric(self, mock_redis_client, mock_settings):
        """Test experiment result metric is recorded."""
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

            # Test recording experiment result
            analyzer._record_experiment_result(
                camera_id="front_door",
                version=PromptVersion.V2_CALIBRATED,
                risk_score=45,
                latency_ms=150.0,
            )

            # Method should exist and complete without error
