"""Unit tests for Prompt A/B Testing and Performance Comparison Infrastructure.

These tests cover:
1. Traffic splitting configuration (90/10 split for new prompts)
2. Shadow mode - run both prompts and compare results
3. Prompt performance metrics (latency and risk score variance)
4. Automated evaluation using historical events
5. Rollback trigger based on performance degradation

TDD: Write tests first (RED), then implement to make them GREEN.
"""

import random
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: Traffic Splitting Configuration
# =============================================================================


class TestTrafficSplitting:
    """Tests for traffic splitting between prompt versions."""

    @pytest.fixture
    def ab_test_config(self):
        """Sample A/B test configuration."""
        from backend.services.prompt_service import ABTestConfig

        return ABTestConfig(
            control_version=1,
            treatment_version=2,
            traffic_split=0.1,  # 10% treatment
            enabled=True,
            model="nemotron",
        )

    def test_ab_test_config_creation(self):
        """Test ABTestConfig can be created with valid parameters."""
        from backend.services.prompt_service import ABTestConfig

        config = ABTestConfig(
            control_version=1,
            treatment_version=2,
            traffic_split=0.1,
            enabled=True,
            model="nemotron",
        )

        assert config.control_version == 1
        assert config.treatment_version == 2
        assert config.traffic_split == 0.1
        assert config.enabled is True
        assert config.model == "nemotron"

    def test_ab_test_config_traffic_split_validation(self):
        """Test traffic_split must be between 0 and 1."""
        from backend.services.prompt_service import ABTestConfig

        # Valid splits
        ABTestConfig(control_version=1, treatment_version=2, traffic_split=0.0, model="nemotron")
        ABTestConfig(control_version=1, treatment_version=2, traffic_split=1.0, model="nemotron")
        ABTestConfig(control_version=1, treatment_version=2, traffic_split=0.5, model="nemotron")

        # Invalid splits should raise ValueError
        with pytest.raises(ValueError, match="traffic_split"):
            ABTestConfig(
                control_version=1,
                treatment_version=2,
                traffic_split=-0.1,
                model="nemotron",
            )

        with pytest.raises(ValueError, match="traffic_split"):
            ABTestConfig(
                control_version=1,
                treatment_version=2,
                traffic_split=1.1,
                model="nemotron",
            )

    def test_select_prompt_version_returns_control_when_disabled(self, ab_test_config):
        """Test select_prompt_version returns control when A/B test disabled."""
        from backend.services.prompt_service import PromptABTester

        ab_test_config.enabled = False
        tester = PromptABTester(ab_test_config)

        # Should always return control when disabled
        for _ in range(100):
            version, is_treatment = tester.select_prompt_version()
            assert version == ab_test_config.control_version
            assert is_treatment is False

    def test_select_prompt_version_respects_traffic_split(self, ab_test_config):
        """Test select_prompt_version respects the traffic split ratio."""
        from backend.services.prompt_service import PromptABTester

        tester = PromptABTester(ab_test_config)

        # Run many selections and verify distribution
        treatment_count = 0
        total_runs = 10000
        random.seed(42)  # Deterministic for testing

        for _ in range(total_runs):
            _version, is_treatment = tester.select_prompt_version()
            if is_treatment:
                treatment_count += 1

        # With 10% split, expect ~10% treatment (allow 2% tolerance)
        treatment_ratio = treatment_count / total_runs
        assert 0.08 <= treatment_ratio <= 0.12, (
            f"Expected ~10% treatment, got {treatment_ratio * 100:.1f}%"
        )

    def test_select_prompt_version_returns_correct_versions(self, ab_test_config):
        """Test select_prompt_version returns the correct version numbers."""
        from backend.services.prompt_service import PromptABTester

        tester = PromptABTester(ab_test_config)

        # Force control selection (500/1000 = 0.5 > 0.1)
        with patch("secrets.randbelow", return_value=500):
            version, is_treatment = tester.select_prompt_version()
            assert version == 1  # control_version
            assert is_treatment is False

        # Force treatment selection (50/1000 = 0.05 <= 0.1)
        with patch("secrets.randbelow", return_value=50):
            version, is_treatment = tester.select_prompt_version()
            assert version == 2  # treatment_version
            assert is_treatment is True


# =============================================================================
# Test: Shadow Mode
# =============================================================================


class TestShadowMode:
    """Tests for shadow mode - running both prompts and comparing results."""

    @pytest.fixture
    def shadow_config(self):
        """Shadow mode configuration."""
        from backend.services.prompt_service import ShadowModeConfig

        return ShadowModeConfig(
            enabled=True,
            control_version=1,
            shadow_version=2,
            model="nemotron",
            log_comparisons=True,
        )

    @pytest.mark.asyncio
    async def test_shadow_mode_config_creation(self):
        """Test ShadowModeConfig can be created."""
        from backend.services.prompt_service import ShadowModeConfig

        config = ShadowModeConfig(
            enabled=True,
            control_version=1,
            shadow_version=2,
            model="nemotron",
            log_comparisons=True,
        )

        assert config.enabled is True
        assert config.control_version == 1
        assert config.shadow_version == 2
        assert config.model == "nemotron"
        assert config.log_comparisons is True

    @pytest.mark.asyncio
    async def test_run_shadow_comparison_executes_both_prompts(self, shadow_config):
        """Test shadow mode runs both control and shadow prompts."""
        from backend.services.prompt_service import PromptShadowRunner

        runner = PromptShadowRunner(shadow_config)

        # Mock the LLM calls
        mock_run_prompt = AsyncMock(
            side_effect=[
                {"risk_score": 50, "reasoning": "Control response"},
                {"risk_score": 55, "reasoning": "Shadow response"},
            ]
        )

        with patch.object(runner, "_run_single_prompt", mock_run_prompt):
            result = await runner.run_shadow_comparison(
                context="Test detection context",
            )

        # Both prompts should have been called
        assert mock_run_prompt.call_count == 2
        assert result.control_result["risk_score"] == 50
        assert result.shadow_result["risk_score"] == 55
        assert result.risk_score_diff == 5

    @pytest.mark.asyncio
    async def test_shadow_comparison_calculates_metrics(self, shadow_config):
        """Test shadow comparison calculates latency and score differences."""
        from backend.services.prompt_service import PromptShadowRunner

        runner = PromptShadowRunner(shadow_config)

        # Mock with timing information
        async def mock_prompt_with_timing(version, context):
            await AsyncMock()()
            if version == 1:
                return {"risk_score": 60, "latency_ms": 150}
            else:
                return {"risk_score": 70, "latency_ms": 200}

        with patch.object(runner, "_run_single_prompt", mock_prompt_with_timing):
            result = await runner.run_shadow_comparison(context="Test context")

        assert result.risk_score_diff == 10
        assert result.control_latency_ms >= 0
        assert result.shadow_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_shadow_mode_disabled_skips_shadow(self, shadow_config):
        """Test shadow mode disabled only runs control prompt."""
        from backend.services.prompt_service import PromptShadowRunner

        shadow_config.enabled = False
        runner = PromptShadowRunner(shadow_config)

        mock_run_prompt = AsyncMock(return_value={"risk_score": 50, "reasoning": "Control only"})

        with patch.object(runner, "_run_single_prompt", mock_run_prompt):
            result = await runner.run_shadow_comparison(context="Test context")

        # Only control should run when disabled
        assert mock_run_prompt.call_count == 1
        assert result.control_result["risk_score"] == 50
        assert result.shadow_result is None

    @pytest.mark.asyncio
    async def test_shadow_comparison_handles_shadow_failure(self, shadow_config):
        """Test shadow comparison continues if shadow prompt fails."""
        from backend.services.prompt_service import PromptShadowRunner

        runner = PromptShadowRunner(shadow_config)

        async def mock_with_failure(version, context):
            if version == 1:
                return {"risk_score": 50}
            else:
                raise RuntimeError("Shadow prompt failed")

        with patch.object(runner, "_run_single_prompt", mock_with_failure):
            result = await runner.run_shadow_comparison(context="Test context")

        # Should still have control result
        assert result.control_result["risk_score"] == 50
        assert result.shadow_error == "Shadow prompt failed"


# =============================================================================
# Test: Prompt Performance Metrics
# =============================================================================


class TestPromptPerformanceMetrics:
    """Tests for Prometheus metrics tracking prompt performance."""

    def test_prompt_version_latency_metric_exists(self):
        """Test hsi_prompt_version_latency_seconds metric is defined."""
        from backend.core.metrics import prompt_version_latency_seconds

        assert prompt_version_latency_seconds is not None
        # Verify it's a Histogram with version label
        assert hasattr(prompt_version_latency_seconds, "labels")

    def test_prompt_version_risk_score_variance_metric_exists(self):
        """Test hsi_prompt_version_risk_score_variance metric is defined."""
        from backend.core.metrics import prompt_version_risk_score_variance

        assert prompt_version_risk_score_variance is not None
        assert hasattr(prompt_version_risk_score_variance, "labels")

    def test_record_prompt_latency(self):
        """Test recording latency for a prompt version."""
        from backend.core.metrics import record_prompt_latency

        # Should not raise
        record_prompt_latency(version="v1", latency_seconds=0.5)
        record_prompt_latency(version="v2", latency_seconds=1.2)

    def test_record_risk_score_variance(self):
        """Test recording risk score variance between versions."""
        from backend.core.metrics import record_risk_score_variance

        # Should not raise
        record_risk_score_variance(control_version="v1", treatment_version="v2", variance=5.0)

    @pytest.mark.asyncio
    async def test_prompt_ab_tester_records_metrics(self):
        """Test PromptABTester records latency metrics when running prompts."""
        from backend.services.prompt_service import ABTestConfig, PromptABTester

        config = ABTestConfig(
            control_version=1,
            treatment_version=2,
            traffic_split=0.5,
            enabled=True,
            model="nemotron",
        )
        tester = PromptABTester(config)

        with patch("backend.core.metrics.record_prompt_latency") as mock_record:
            # Simulate running a prompt
            await tester.record_prompt_execution(
                version=1,
                latency_seconds=0.25,
                risk_score=50,
            )

            mock_record.assert_called_once()


# =============================================================================
# Test: Automated Evaluation Using Historical Events
# =============================================================================


class TestAutomatedEvaluation:
    """Tests for automated evaluation using historical events."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def sample_historical_events(self):
        """Create sample historical events for evaluation."""
        now = datetime.now(UTC)
        return [
            MagicMock(
                id=1,
                camera_id="front_door",
                risk_score=50,
                llm_prompt="Detection context 1",
                started_at=now - timedelta(hours=1),
            ),
            MagicMock(
                id=2,
                camera_id="back_yard",
                risk_score=75,
                llm_prompt="Detection context 2",
                started_at=now - timedelta(hours=2),
            ),
            MagicMock(
                id=3,
                camera_id="driveway",
                risk_score=30,
                llm_prompt="Detection context 3",
                started_at=now - timedelta(hours=3),
            ),
        ]

    @pytest.mark.asyncio
    async def test_create_evaluation_batch(self, mock_session, sample_historical_events):
        """Test creating an evaluation batch from historical events."""
        from backend.services.prompt_service import PromptEvaluator

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=sample_historical_events))
        )
        mock_session.execute.return_value = mock_result

        evaluator = PromptEvaluator()
        batch = await evaluator.create_evaluation_batch(
            session=mock_session,
            hours_back=24,
            sample_size=10,
        )

        assert len(batch.events) == 3
        assert batch.created_at is not None

    @pytest.mark.asyncio
    async def test_evaluate_prompt_version_against_batch(
        self, mock_session, sample_historical_events
    ):
        """Test evaluating a prompt version against a batch of events."""
        from backend.services.prompt_service import EvaluationBatch, PromptEvaluator

        evaluator = PromptEvaluator()
        batch = EvaluationBatch(
            events=sample_historical_events,
            created_at=datetime.now(UTC),
        )

        # Mock the LLM calls
        mock_run_prompt = AsyncMock(
            side_effect=[
                {"risk_score": 52},  # Close to original 50
                {"risk_score": 70},  # Close to original 75
                {"risk_score": 35},  # Close to original 30
            ]
        )

        with patch.object(evaluator, "_run_prompt_for_event", mock_run_prompt):
            results = await evaluator.evaluate_prompt_version(
                session=mock_session,
                prompt_version=2,
                batch=batch,
            )

        assert results.total_events == 3
        assert results.average_score_diff is not None
        assert results.score_correlation is not None

    @pytest.mark.asyncio
    async def test_compare_prompt_versions(self, mock_session, sample_historical_events):
        """Test comparing two prompt versions on the same batch."""
        from backend.services.prompt_service import EvaluationBatch, PromptEvaluator

        evaluator = PromptEvaluator()
        batch = EvaluationBatch(
            events=sample_historical_events,
            created_at=datetime.now(UTC),
        )

        # Mock results for both versions
        v1_results = MagicMock(
            average_score_diff=2.5,
            score_variance=10.0,
            average_latency_ms=150,
        )
        v2_results = MagicMock(
            average_score_diff=8.0,
            score_variance=25.0,
            average_latency_ms=200,
        )

        with patch.object(
            evaluator,
            "evaluate_prompt_version",
            AsyncMock(side_effect=[v1_results, v2_results]),
        ):
            comparison = await evaluator.compare_prompt_versions(
                session=mock_session,
                version_a=1,
                version_b=2,
                batch=batch,
            )

        assert comparison.version_a_results == v1_results
        assert comparison.version_b_results == v2_results
        assert comparison.recommended_version == 1  # Lower variance/diff is better


# =============================================================================
# Test: Rollback Trigger Based on Performance Degradation
# =============================================================================


class TestRollbackTrigger:
    """Tests for automatic rollback on performance degradation."""

    @pytest.fixture
    def rollback_config(self):
        """Rollback configuration."""
        from backend.services.prompt_service import RollbackConfig

        return RollbackConfig(
            enabled=True,
            max_latency_increase_pct=50.0,  # 50% latency increase triggers rollback
            max_score_variance=15.0,  # Risk score variance > 15 triggers rollback
            min_samples=100,  # Need 100 samples before triggering
            evaluation_window_hours=1,
        )

    @pytest.mark.asyncio
    async def test_rollback_config_creation(self, rollback_config):
        """Test RollbackConfig creation with valid parameters."""
        assert rollback_config.enabled is True
        assert rollback_config.max_latency_increase_pct == 50.0
        assert rollback_config.max_score_variance == 15.0
        assert rollback_config.min_samples == 100
        assert rollback_config.evaluation_window_hours == 1

    @pytest.mark.asyncio
    async def test_check_rollback_not_triggered_below_threshold(self, rollback_config):
        """Test rollback not triggered when metrics are below threshold."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        # Good metrics - no rollback needed
        metrics = MagicMock(
            latency_increase_pct=20.0,  # Below 50% threshold
            score_variance=10.0,  # Below 15 threshold
            sample_count=150,  # Above 100 minimum
        )

        result = await checker.check_rollback_needed(metrics)

        assert result.should_rollback is False
        assert result.reason is None

    @pytest.mark.asyncio
    async def test_check_rollback_triggered_by_latency(self, rollback_config):
        """Test rollback triggered when latency exceeds threshold."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        # High latency - should trigger rollback
        metrics = MagicMock(
            latency_increase_pct=75.0,  # Above 50% threshold
            score_variance=5.0,  # Below threshold
            sample_count=150,
        )

        result = await checker.check_rollback_needed(metrics)

        assert result.should_rollback is True
        assert "latency" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_rollback_triggered_by_score_variance(self, rollback_config):
        """Test rollback triggered when score variance exceeds threshold."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        # High score variance - should trigger rollback
        metrics = MagicMock(
            latency_increase_pct=10.0,  # Below threshold
            score_variance=25.0,  # Above 15 threshold
            sample_count=150,
        )

        result = await checker.check_rollback_needed(metrics)

        assert result.should_rollback is True
        assert "variance" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_check_rollback_insufficient_samples(self, rollback_config):
        """Test rollback not triggered with insufficient samples."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        # Bad metrics but not enough samples
        metrics = MagicMock(
            latency_increase_pct=100.0,  # Very high
            score_variance=50.0,  # Very high
            sample_count=50,  # Below 100 minimum
        )

        result = await checker.check_rollback_needed(metrics)

        assert result.should_rollback is False
        assert "insufficient" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_execute_rollback(self, rollback_config):
        """Test executing a rollback to previous prompt version."""
        from backend.services.prompt_service import PromptRollbackChecker

        checker = PromptRollbackChecker(rollback_config)

        mock_session = AsyncMock()
        mock_ab_config = MagicMock(
            control_version=1,
            treatment_version=2,
            enabled=True,
        )

        with (
            patch.object(checker, "_disable_ab_test", AsyncMock()) as mock_disable,
            patch.object(checker, "_log_rollback", MagicMock()) as mock_log,
        ):
            result = await checker.execute_rollback(
                session=mock_session,
                ab_config=mock_ab_config,
                reason="High latency detected",
            )

        assert result.success is True
        mock_disable.assert_called_once()
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_disabled_no_action(self, rollback_config):
        """Test no rollback action when rollback is disabled."""
        from backend.services.prompt_service import PromptRollbackChecker

        rollback_config.enabled = False
        checker = PromptRollbackChecker(rollback_config)

        metrics = MagicMock(
            latency_increase_pct=100.0,
            score_variance=50.0,
            sample_count=1000,
        )

        result = await checker.check_rollback_needed(metrics)

        assert result.should_rollback is False


# =============================================================================
# Test: Integration with NemotronAnalyzer
# =============================================================================


class TestNemotronAnalyzerABIntegration:
    """Tests for A/B testing integration in NemotronAnalyzer."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        from backend.core.redis import RedisClient

        mock_client = MagicMock(spec=RedisClient)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock(return_value=True)
        return mock_client

    @pytest.fixture
    def mock_settings(self):
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
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0
        mock.nemotron_warmup_prompt = "Test warmup prompt"
        # A/B testing settings
        mock.prompt_ab_testing_enabled = True
        mock.prompt_shadow_mode_enabled = False
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        return mock

    @pytest.mark.asyncio
    async def test_nemotron_analyzer_uses_ab_tester(self, mock_redis_client, mock_settings):
        """Test NemotronAnalyzer integrates with PromptABTester."""
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

            # Check analyzer has A/B testing support
            assert hasattr(analyzer, "get_prompt_version")
            assert hasattr(analyzer, "_ab_tester")

    @pytest.mark.asyncio
    async def test_get_prompt_version_selects_from_ab_test(self, mock_redis_client, mock_settings):
        """Test get_prompt_version uses A/B tester when enabled."""
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

            # Set up A/B test
            from backend.services.prompt_service import ABTestConfig

            ab_config = ABTestConfig(
                control_version=1,
                treatment_version=2,
                traffic_split=0.5,
                enabled=True,
                model="nemotron",
            )
            analyzer.set_ab_test_config(ab_config)

            # Get prompt version
            version, is_treatment = await analyzer.get_prompt_version()

            assert version in [1, 2]
            assert isinstance(is_treatment, bool)


# =============================================================================
# Test: Metrics Collection During Analysis
# =============================================================================


class TestMetricsCollectionDuringAnalysis:
    """Tests for metrics collection during prompt analysis."""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis client."""
        from backend.core.redis import RedisClient

        mock_client = MagicMock(spec=RedisClient)
        mock_client.get = AsyncMock(return_value=None)
        mock_client.set = AsyncMock(return_value=True)
        mock_client.delete = AsyncMock(return_value=1)
        mock_client.lrange = AsyncMock(return_value=[b"1", b"2", b"3"])
        return mock_client

    @pytest.mark.asyncio
    async def test_analysis_records_latency_metric(self, mock_redis_client):
        """Test that analysis records latency metrics."""
        from backend.services.nemotron_analyzer import NemotronAnalyzer

        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.nemotron_url = "http://localhost:8091"
        mock_settings.nemotron_api_key = None
        mock_settings.ai_connect_timeout = 10.0
        mock_settings.nemotron_read_timeout = 120.0
        mock_settings.ai_health_timeout = 5.0
        mock_settings.nemotron_max_retries = 1
        mock_settings.severity_low_max = 29
        mock_settings.severity_medium_max = 59
        mock_settings.severity_high_max = 84
        mock_settings.nemotron_context_window = 4096
        mock_settings.nemotron_max_output_tokens = 1536
        mock_settings.context_utilization_warning_threshold = 0.80
        mock_settings.context_truncation_enabled = True
        mock_settings.llm_tokenizer_encoding = "cl100k_base"
        mock_settings.image_quality_enabled = False
        mock_settings.ai_warmup_enabled = False
        mock_settings.prompt_ab_testing_enabled = False
        mock_settings.prompt_shadow_mode_enabled = False

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
            patch("backend.core.metrics.record_prompt_latency") as mock_record_latency,
        ):
            from backend.services.severity import reset_severity_service
            from backend.services.token_counter import reset_token_counter

            reset_severity_service()
            reset_token_counter()

            analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

            # Mock the internal _call_llm method
            with patch.object(
                analyzer,
                "_call_llm",
                AsyncMock(
                    return_value={
                        "risk_score": 50,
                        "risk_level": "medium",
                        "summary": "Test",
                        "reasoning": "Test reasoning",
                    }
                ),
            ):
                # Simulate recording latency (this would happen inside analyze_batch)
                analyzer._record_analysis_metrics(
                    prompt_version=1,
                    latency_seconds=0.5,
                    risk_score=50,
                )

            # Verify latency was recorded
            mock_record_latency.assert_called()
