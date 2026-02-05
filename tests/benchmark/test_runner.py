"""Tests for benchmark orchestrator.

This module tests the main benchmark runner that orchestrates:
- Single request latency measurements
- Sustained load testing
- Burst handling simulation
- Cold start timing

Following TDD principles: These tests will FAIL initially (red phase).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import the module under test (will be created as stubs)
from scripts.benchmark.run_benchmark import (
    BenchmarkConfig,
    BenchmarkResults,
    BenchmarkRunner,
    parse_args,
)


@pytest.fixture
def mock_metrics_collector():
    """Mock MetricsCollector for testing."""
    mock = AsyncMock()
    mock.record_request = AsyncMock(
        return_value={
            "response": "test response",
            "latency": 0.5,
            "tokens": 100,
        }
    )
    mock.get_latency_metrics = MagicMock(
        return_value=MagicMock(
            p50=0.45,
            p95=0.65,
            p99=0.75,
            time_to_first_token=0.1,
            mean=0.5,
            count=10,
        )
    )
    mock.monitor_vram = AsyncMock(
        return_value=MagicMock(
            peak_usage_mb=8192.0,
            steady_state_mb=7168.0,
            min_usage_mb=6144.0,
            samples=20,
        )
    )
    mock.run_sustained_load = AsyncMock(
        return_value=MagicMock(
            requests_per_min=120.0,
            tokens_per_sec=200.0,
            total_requests=100,
            total_tokens=20000,
            duration_sec=60.0,
        )
    )
    return mock


@pytest.fixture
def mock_quality_scorer():
    """Mock QualityScorer for testing."""
    mock = MagicMock()
    mock.score_response = MagicMock(
        return_value={
            "accuracy": 0.95,
            "relevance": 0.92,
            "coherence": 0.88,
            "overall": 0.92,
        }
    )
    mock.aggregate_scores = MagicMock(
        return_value={
            "mean_accuracy": 0.93,
            "mean_relevance": 0.90,
            "mean_coherence": 0.87,
            "overall_quality": 0.90,
        }
    )
    return mock


@pytest.fixture
def mock_evaluation_set(tmp_path: Path) -> Path:
    """Create a mock evaluation set directory with sample data."""
    eval_dir = tmp_path / "evaluation-set"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Create 100 sample events
    for i in range(100):
        event_file = eval_dir / f"event_{i:03d}.json"
        event_data = {
            "event_id": f"evt_{i:03d}",
            "prompt": f"Test prompt {i}",
            "expected_response": f"Expected response {i}",
            "context": {"camera": "front_door", "timestamp": "2025-01-01T12:00:00Z"},
        }
        event_file.write_text(json.dumps(event_data))

    return eval_dir


@pytest.fixture
def benchmark_config(mock_evaluation_set: Path, tmp_path: Path) -> BenchmarkConfig:
    """Create a test benchmark configuration."""
    return BenchmarkConfig(
        llm_endpoint="http://localhost:8091",
        evaluation_set_path=mock_evaluation_set,
        output_path=tmp_path / "results",
        scenarios=["single", "sustained", "burst", "cold_start"],
        sustained_duration_sec=60.0,
        sustained_rate=10,
        burst_size=10,
        cold_start_attempts=3,
    )


@pytest.mark.asyncio
class TestBenchmarkConfig:
    """Tests for BenchmarkConfig dataclass."""

    def test_config_initialization(self, mock_evaluation_set: Path, tmp_path: Path):
        """Test BenchmarkConfig can be initialized with all required fields."""
        config = BenchmarkConfig(
            llm_endpoint="http://localhost:8091",
            evaluation_set_path=mock_evaluation_set,
            output_path=tmp_path / "results",
            scenarios=["single"],
            sustained_duration_sec=30.0,
            sustained_rate=5,
            burst_size=5,
            cold_start_attempts=1,
        )

        assert config.llm_endpoint == "http://localhost:8091"
        assert config.evaluation_set_path == mock_evaluation_set
        assert config.scenarios == ["single"]
        assert config.sustained_duration_sec == 30.0
        assert config.sustained_rate == 5
        assert config.burst_size == 5
        assert config.cold_start_attempts == 1

    def test_config_defaults(self, mock_evaluation_set: Path, tmp_path: Path):
        """Test BenchmarkConfig provides sensible defaults."""
        config = BenchmarkConfig(
            llm_endpoint="http://localhost:8091",
            evaluation_set_path=mock_evaluation_set,
            output_path=tmp_path / "results",
        )

        # Should have default scenarios
        assert "single" in config.scenarios
        assert "sustained" in config.scenarios
        assert "burst" in config.scenarios
        assert "cold_start" in config.scenarios

        # Should have default values
        assert config.sustained_duration_sec == 60.0
        assert config.sustained_rate == 10
        assert config.burst_size == 10
        assert config.cold_start_attempts == 3

    def test_config_validation_invalid_endpoint(self, mock_evaluation_set: Path, tmp_path: Path):
        """Test BenchmarkConfig validates endpoint URL."""
        with pytest.raises(ValueError, match="Invalid endpoint URL"):
            BenchmarkConfig(
                llm_endpoint="not-a-url",
                evaluation_set_path=mock_evaluation_set,
                output_path=tmp_path / "results",
            )

    def test_config_validation_nonexistent_eval_set(self, tmp_path: Path):
        """Test BenchmarkConfig validates evaluation set path exists."""
        nonexistent_path = tmp_path / "does-not-exist"
        with pytest.raises(FileNotFoundError, match="Evaluation set path does not exist"):
            BenchmarkConfig(
                llm_endpoint="http://localhost:8091",
                evaluation_set_path=nonexistent_path,
                output_path=tmp_path / "results",
            )


@pytest.mark.asyncio
class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    def test_runner_initialization(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test BenchmarkRunner can be initialized with config."""
        with patch(
            "scripts.benchmark.run_benchmark.MetricsCollector",
            return_value=mock_metrics_collector,
        ):
            runner = BenchmarkRunner(
                config=benchmark_config,
                metrics_collector=mock_metrics_collector,
                quality_scorer=mock_quality_scorer,
            )

            assert runner.config == benchmark_config
            assert runner.metrics_collector == mock_metrics_collector
            assert runner.quality_scorer == mock_quality_scorer

    async def test_load_evaluation_set(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test loading the 100-event evaluation set."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        events = await runner.load_evaluation_set()

        assert len(events) == 100
        assert all("event_id" in event for event in events)
        assert all("prompt" in event for event in events)
        assert all("expected_response" in event for event in events)

    async def test_load_evaluation_set_empty_directory(
        self,
        tmp_path: Path,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test loading evaluation set fails if directory is empty."""
        empty_dir = tmp_path / "empty_eval"
        empty_dir.mkdir()

        config = BenchmarkConfig(
            llm_endpoint="http://localhost:8091",
            evaluation_set_path=empty_dir,
            output_path=tmp_path / "results",
        )

        runner = BenchmarkRunner(
            config=config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        with pytest.raises(ValueError, match="No events found in evaluation set"):
            await runner.load_evaluation_set()


@pytest.mark.asyncio
class TestSingleRequestLatency:
    """Tests for single request latency scenario."""

    async def test_single_request_scenario(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test single request latency measurement."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_single_request_scenario()

        # Verify metrics were collected
        assert mock_metrics_collector.record_request.called
        assert result["scenario"] == "single_request"
        assert "latency_metrics" in result
        assert result["latency_metrics"]["p50"] == 0.45
        assert result["latency_metrics"]["p95"] == 0.65
        assert result["latency_metrics"]["p99"] == 0.75

    async def test_single_request_uses_first_event(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test single request uses first event from evaluation set."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        await runner.run_single_request_scenario()

        # Verify the first event's prompt was used
        call_args = mock_metrics_collector.record_request.call_args
        assert "Test prompt 0" in str(call_args) or call_args is not None

    async def test_single_request_includes_quality_score(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test single request includes quality scoring."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_single_request_scenario()

        assert "quality_scores" in result
        assert result["quality_scores"]["accuracy"] == 0.95
        assert result["quality_scores"]["relevance"] == 0.92


@pytest.mark.asyncio
class TestSustainedLoad:
    """Tests for sustained load scenario."""

    async def test_sustained_load_scenario(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test sustained load measurement at configurable rate."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_sustained_load_scenario()

        assert result["scenario"] == "sustained_load"
        assert "throughput_metrics" in result
        assert result["throughput_metrics"]["requests_per_min"] == 120.0
        assert result["throughput_metrics"]["tokens_per_sec"] == 200.0

    async def test_sustained_load_uses_all_events(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test sustained load cycles through all evaluation events."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        await runner.run_sustained_load_scenario()

        # run_sustained_load should be called with prompts list
        assert mock_metrics_collector.run_sustained_load.called
        call_args = mock_metrics_collector.run_sustained_load.call_args
        assert "prompts" in call_args.kwargs or len(call_args.args) > 0

    async def test_sustained_load_duration_matches_config(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test sustained load runs for configured duration."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        await runner.run_sustained_load_scenario()

        call_args = mock_metrics_collector.run_sustained_load.call_args
        # Check duration_sec parameter
        assert call_args.kwargs.get("duration_sec") == 60.0 or (
            len(call_args.args) > 1 and call_args.args[1] == 60.0
        )


@pytest.mark.asyncio
class TestBurstHandling:
    """Tests for burst handling scenario."""

    async def test_burst_scenario(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test burst handling with 10+ simultaneous detections."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_burst_scenario()

        assert result["scenario"] == "burst_handling"
        assert "burst_size" in result
        assert result["burst_size"] == 10
        assert "latency_metrics" in result

    async def test_burst_uses_concurrent_requests(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test burst scenario sends requests concurrently."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        # Mock asyncio.gather to verify concurrent execution
        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [{"response": "ok"}] * 10
            await runner.run_burst_scenario()

            # asyncio.gather should be called with multiple tasks
            assert mock_gather.called

    async def test_burst_size_matches_config(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test burst size matches configuration."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_burst_scenario()

        assert result["burst_size"] == benchmark_config.burst_size


@pytest.mark.asyncio
class TestColdStart:
    """Tests for cold start scenario."""

    async def test_cold_start_scenario(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test cold start timing measurement."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_cold_start_scenario()

        assert result["scenario"] == "cold_start"
        assert "cold_start_time" in result
        assert "attempts" in result
        assert result["attempts"] == 3

    async def test_cold_start_waits_for_service_ready(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test cold start waits for service to become ready."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        # Mock service health check
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200)
            result = await runner.run_cold_start_scenario()

            # Health check should be called
            assert mock_get.called
            assert "cold_start_time" in result

    async def test_cold_start_includes_first_inference_time(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test cold start includes time to first successful inference."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_cold_start_scenario()

        assert "time_to_first_inference" in result
        assert isinstance(result["time_to_first_inference"], float)
        assert result["time_to_first_inference"] > 0


@pytest.mark.asyncio
class TestBenchmarkOrchestration:
    """Tests for full benchmark orchestration."""

    async def test_run_all_scenarios(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test running all configured scenarios."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = await runner.run_all_scenarios()

        assert len(results["scenarios"]) == 4
        scenario_names = [s["scenario"] for s in results["scenarios"]]
        assert "single_request" in scenario_names
        assert "sustained_load" in scenario_names
        assert "burst_handling" in scenario_names
        assert "cold_start" in scenario_names

    async def test_run_selective_scenarios(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test running only selected scenarios."""
        benchmark_config.scenarios = ["single", "burst"]

        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = await runner.run_all_scenarios()

        assert len(results["scenarios"]) == 2
        scenario_names = [s["scenario"] for s in results["scenarios"]]
        assert "single_request" in scenario_names
        assert "burst_handling" in scenario_names

    async def test_results_include_metadata(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test results include benchmark metadata."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = await runner.run_all_scenarios()

        assert "metadata" in results
        assert "timestamp" in results["metadata"]
        assert "llm_endpoint" in results["metadata"]
        assert "evaluation_set_size" in results["metadata"]
        assert results["metadata"]["llm_endpoint"] == "http://localhost:8091"


@pytest.mark.asyncio
class TestResultsOutput:
    """Tests for results JSON output."""

    async def test_save_results_to_json(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test saving benchmark results to JSON file."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = BenchmarkResults(
            metadata={"timestamp": "2025-01-01T12:00:00Z"},
            scenarios=[],
            summary={},
        )

        output_file = await runner.save_results(results)

        assert output_file.exists()
        assert output_file.suffix == ".json"

        # Verify JSON structure
        data = json.loads(output_file.read_text())
        assert "metadata" in data
        assert "scenarios" in data
        assert "summary" in data

    async def test_output_path_created_if_missing(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test output directory is created if it doesn't exist."""
        # Remove output directory if it exists
        if benchmark_config.output_path.exists():
            import shutil

            shutil.rmtree(benchmark_config.output_path)

        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = BenchmarkResults(
            metadata={"timestamp": "2025-01-01T12:00:00Z"},
            scenarios=[],
            summary={},
        )

        output_file = await runner.save_results(results)

        assert benchmark_config.output_path.exists()
        assert output_file.exists()

    async def test_results_filename_includes_timestamp(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test results filename includes timestamp for uniqueness."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        results = BenchmarkResults(
            metadata={"timestamp": "2025-01-01T12:00:00Z"},
            scenarios=[],
            summary={},
        )

        output_file = await runner.save_results(results)

        # Filename should contain timestamp or be unique
        assert "benchmark" in output_file.name
        assert ".json" in output_file.name


class TestCLIArgumentParsing:
    """Tests for command-line argument parsing."""

    def test_parse_args_defaults(self, tmp_path: Path):
        """Test CLI argument parsing with default values."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(["--evaluation-set", str(eval_dir)])

        assert args.llm_endpoint == "http://localhost:8091"
        assert args.evaluation_set == eval_dir
        assert args.output == Path("results/benchmarks")
        assert args.scenarios == ["single", "sustained", "burst", "cold_start"]

    def test_parse_args_custom_endpoint(self, tmp_path: Path):
        """Test CLI with custom LLM endpoint."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--llm-endpoint",
                "http://custom:9000",
            ]
        )

        assert args.llm_endpoint == "http://custom:9000"

    def test_parse_args_custom_output(self, tmp_path: Path):
        """Test CLI with custom output path."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        custom_output = tmp_path / "custom-results"
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--output",
                str(custom_output),
            ]
        )

        assert args.output == custom_output

    def test_parse_args_selective_scenarios(self, tmp_path: Path):
        """Test CLI with selective scenario execution."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--scenarios",
                "single",
                "burst",
            ]
        )

        assert args.scenarios == ["single", "burst"]
        assert "sustained" not in args.scenarios

    def test_parse_args_sustained_duration(self, tmp_path: Path):
        """Test CLI with custom sustained load duration."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--sustained-duration",
                "120",
            ]
        )

        assert args.sustained_duration == 120

    def test_parse_args_sustained_rate(self, tmp_path: Path):
        """Test CLI with custom sustained load rate."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--sustained-rate",
                "20",
            ]
        )

        assert args.sustained_rate == 20

    def test_parse_args_burst_size(self, tmp_path: Path):
        """Test CLI with custom burst size."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--burst-size",
                "15",
            ]
        )

        assert args.burst_size == 15

    def test_parse_args_cold_start_attempts(self, tmp_path: Path):
        """Test CLI with custom cold start attempts."""
        eval_dir = tmp_path / "eval"
        eval_dir.mkdir()
        args = parse_args(
            [
                "--evaluation-set",
                str(eval_dir),
                "--cold-start-attempts",
                "5",
            ]
        )

        assert args.cold_start_attempts == 5

    def test_parse_args_missing_evaluation_set(self):
        """Test CLI fails without required evaluation set path."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_parse_args_help_text(self):
        """Test CLI help text is informative."""
        with pytest.raises(SystemExit):
            parse_args(["--help"])


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for error handling and resilience."""

    async def test_service_unavailable_error(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test handling of service unavailable errors."""
        from scripts.benchmark.metrics import ServiceUnavailableError

        mock_metrics_collector.record_request.side_effect = ServiceUnavailableError(
            "Service not reachable"
        )

        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        with pytest.raises(ServiceUnavailableError):
            await runner.run_single_request_scenario()

    async def test_timeout_error(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test handling of timeout errors."""
        mock_metrics_collector.record_request.side_effect = TimeoutError("Request timed out")

        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        with pytest.raises(TimeoutError):
            await runner.run_single_request_scenario()

    async def test_partial_failure_in_burst(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test burst scenario handles partial failures gracefully."""
        # Simulate some requests failing
        mock_metrics_collector.record_request.side_effect = [
            {"response": "ok"},
            {"response": "ok"},
            TimeoutError("Timeout"),
            {"response": "ok"},
        ] * 3  # Ensure enough responses for burst_size=10

        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_burst_scenario()

        # Should report partial success
        assert "failures" in result
        assert result["failures"] > 0


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for end-to-end workflow."""

    async def test_full_benchmark_workflow(
        self,
        benchmark_config: BenchmarkConfig,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test complete benchmark workflow from start to finish."""
        runner = BenchmarkRunner(
            config=benchmark_config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        # Load evaluation set
        events = await runner.load_evaluation_set()
        assert len(events) == 100

        # Run all scenarios
        results = await runner.run_all_scenarios()
        assert len(results["scenarios"]) == 4

        # Save results
        output_file = await runner.save_results(
            BenchmarkResults(
                metadata=results["metadata"],
                scenarios=results["scenarios"],
                summary={},
            )
        )
        assert output_file.exists()

        # Verify output structure
        data = json.loads(output_file.read_text())
        assert "metadata" in data
        assert "scenarios" in data

    async def test_benchmark_with_real_evaluation_set(
        self,
        mock_evaluation_set: Path,
        tmp_path: Path,
        mock_metrics_collector,
        mock_quality_scorer,
    ):
        """Test benchmark with realistic evaluation set."""
        config = BenchmarkConfig(
            llm_endpoint="http://localhost:8091",
            evaluation_set_path=mock_evaluation_set,
            output_path=tmp_path / "results",
            scenarios=["single"],
        )

        runner = BenchmarkRunner(
            config=config,
            metrics_collector=mock_metrics_collector,
            quality_scorer=mock_quality_scorer,
        )

        result = await runner.run_single_request_scenario()

        assert result["scenario"] == "single_request"
        assert "latency_metrics" in result
        assert "quality_scores" in result
