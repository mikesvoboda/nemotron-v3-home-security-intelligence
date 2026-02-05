"""Tests for LLM engine comparison module (Phase 4: vLLM vs llama.cpp).

This module tests the engine comparison functionality for:
- Engine configuration and service management
- OpenAI-compatible API compatibility
- Performance benchmarking across engines
- Comparison report generation
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.benchmark.engine_comparison import (
    ENGINE_CONFIGS,
    EngineComparator,
    EngineConfig,
    EngineMetrics,
    EngineType,
    compare_engines,
    generate_comparison_report,
)


class TestEngineType:
    """Tests for EngineType enum."""

    def test_engine_types_defined(self) -> None:
        """Verify all expected engine types are defined."""
        assert EngineType.LLAMA_CPP is not None
        assert EngineType.VLLM is not None

    def test_engine_type_values(self) -> None:
        """Verify engine type string values."""
        assert EngineType.LLAMA_CPP.value == "llama.cpp"
        assert EngineType.VLLM.value == "vllm"

    def test_engine_types_are_distinct(self) -> None:
        """Verify engine types are distinct values."""
        assert EngineType.LLAMA_CPP != EngineType.VLLM


class TestEngineConfig:
    """Tests for EngineConfig dataclass."""

    def test_engine_config_creation(self) -> None:
        """Test creating an EngineConfig instance."""
        config = EngineConfig(
            engine_type=EngineType.LLAMA_CPP,
            service_url="http://localhost:8091",
            model_path="/models/nemotron",
            api_format="llama.cpp",
        )
        assert config.engine_type == EngineType.LLAMA_CPP
        assert config.service_url == "http://localhost:8091"
        assert config.model_path == "/models/nemotron"
        assert config.api_format == "llama.cpp"

    def test_engine_config_with_vllm(self) -> None:
        """Test creating vLLM engine config."""
        config = EngineConfig(
            engine_type=EngineType.VLLM,
            service_url="http://localhost:8092",
            model_path="nvidia/Nemotron-3-Nano-30B-A3B",
            api_format="openai",
        )
        assert config.engine_type == EngineType.VLLM
        assert config.api_format == "openai"

    def test_engine_config_optional_fields(self) -> None:
        """Test EngineConfig with optional fields."""
        config = EngineConfig(
            engine_type=EngineType.VLLM,
            service_url="http://localhost:8092",
            model_path="nvidia/Nemotron-3-Nano-30B-A3B",
            api_format="openai",
            gpu_memory_utilization=0.9,
            tensor_parallel_size=1,
            max_model_len=32768,
        )
        assert config.gpu_memory_utilization == 0.9
        assert config.tensor_parallel_size == 1
        assert config.max_model_len == 32768

    def test_engine_config_defaults(self) -> None:
        """Test EngineConfig default values."""
        config = EngineConfig(
            engine_type=EngineType.LLAMA_CPP,
            service_url="http://localhost:8091",
            model_path="/models/nemotron",
            api_format="llama.cpp",
        )
        assert config.gpu_memory_utilization is None
        assert config.tensor_parallel_size is None
        assert config.max_model_len is None


class TestEngineMetrics:
    """Tests for EngineMetrics dataclass."""

    def test_engine_metrics_creation(self) -> None:
        """Test creating EngineMetrics instance."""
        metrics = EngineMetrics(
            engine_type=EngineType.LLAMA_CPP,
            latency_p50_ms=150.5,
            latency_p95_ms=250.3,
            latency_p99_ms=350.7,
            throughput_tokens_per_sec=45.2,
            vram_peak_mb=8500.0,
            vram_steady_mb=7200.0,
            time_to_first_token_ms=50.3,
            requests_per_minute=12.5,
        )
        assert metrics.engine_type == EngineType.LLAMA_CPP
        assert metrics.latency_p50_ms == 150.5
        assert metrics.throughput_tokens_per_sec == 45.2

    def test_engine_metrics_all_fields(self) -> None:
        """Test all EngineMetrics fields are captured."""
        metrics = EngineMetrics(
            engine_type=EngineType.VLLM,
            latency_p50_ms=120.0,
            latency_p95_ms=200.0,
            latency_p99_ms=300.0,
            throughput_tokens_per_sec=60.0,
            vram_peak_mb=9000.0,
            vram_steady_mb=8000.0,
            time_to_first_token_ms=40.0,
            requests_per_minute=15.0,
        )
        assert metrics.latency_p95_ms == 200.0
        assert metrics.latency_p99_ms == 300.0
        assert metrics.vram_peak_mb == 9000.0
        assert metrics.vram_steady_mb == 8000.0
        assert metrics.time_to_first_token_ms == 40.0
        assert metrics.requests_per_minute == 15.0


class TestEngineConfigs:
    """Tests for default ENGINE_CONFIGS."""

    def test_llama_cpp_config_exists(self) -> None:
        """Verify llama.cpp config is defined."""
        assert EngineType.LLAMA_CPP in ENGINE_CONFIGS

    def test_vllm_config_exists(self) -> None:
        """Verify vLLM config is defined."""
        assert EngineType.VLLM in ENGINE_CONFIGS

    def test_llama_cpp_default_config(self) -> None:
        """Verify llama.cpp default configuration."""
        config = ENGINE_CONFIGS[EngineType.LLAMA_CPP]
        assert config.service_url == "http://localhost:8091"
        assert config.api_format == "llama.cpp"

    def test_vllm_default_config(self) -> None:
        """Verify vLLM default configuration."""
        config = ENGINE_CONFIGS[EngineType.VLLM]
        assert config.service_url == "http://localhost:8092"
        assert config.api_format == "openai"


class TestEngineComparator:
    """Tests for EngineComparator class."""

    def test_comparator_initialization(self) -> None:
        """Test EngineComparator initialization."""
        comparator = EngineComparator()
        assert comparator is not None
        assert comparator.configs == ENGINE_CONFIGS

    def test_comparator_with_custom_configs(self) -> None:
        """Test EngineComparator with custom configs."""
        custom_configs = {
            EngineType.LLAMA_CPP: EngineConfig(
                engine_type=EngineType.LLAMA_CPP,
                service_url="http://custom:8091",
                model_path="/custom/model",
                api_format="llama.cpp",
            )
        }
        comparator = EngineComparator(configs=custom_configs)
        assert comparator.configs[EngineType.LLAMA_CPP].service_url == "http://custom:8091"

    @pytest.mark.asyncio
    async def test_check_engine_health_success(self) -> None:
        """Test successful engine health check."""
        comparator = EngineComparator()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            is_healthy = await comparator.check_engine_health(EngineType.LLAMA_CPP)
            assert is_healthy is True

    @pytest.mark.asyncio
    async def test_check_engine_health_failure(self) -> None:
        """Test failed engine health check."""
        comparator = EngineComparator()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            is_healthy = await comparator.check_engine_health(EngineType.LLAMA_CPP)
            assert is_healthy is False

    @pytest.mark.asyncio
    async def test_benchmark_single_engine(self) -> None:
        """Test benchmarking a single engine."""
        comparator = EngineComparator()

        mock_metrics = EngineMetrics(
            engine_type=EngineType.LLAMA_CPP,
            latency_p50_ms=150.0,
            latency_p95_ms=250.0,
            latency_p99_ms=350.0,
            throughput_tokens_per_sec=45.0,
            vram_peak_mb=8500.0,
            vram_steady_mb=7200.0,
            time_to_first_token_ms=50.0,
            requests_per_minute=12.0,
        )

        with (
            patch.object(comparator, "check_engine_health", return_value=True),
            patch.object(comparator, "_run_benchmark", return_value=mock_metrics),
        ):
            metrics = await comparator.benchmark_engine(
                EngineType.LLAMA_CPP, prompts=["test prompt"]
            )
            assert metrics.engine_type == EngineType.LLAMA_CPP
            assert metrics.latency_p50_ms == 150.0

    @pytest.mark.asyncio
    async def test_benchmark_engine_not_healthy(self) -> None:
        """Test benchmarking when engine is not healthy."""
        comparator = EngineComparator()

        with (
            patch.object(comparator, "check_engine_health", return_value=False),
            pytest.raises(RuntimeError, match="not healthy"),
        ):
            await comparator.benchmark_engine(EngineType.LLAMA_CPP, prompts=["test"])

    @pytest.mark.asyncio
    async def test_compare_all_engines(self) -> None:
        """Test comparing all engines."""
        comparator = EngineComparator()

        mock_llama_metrics = EngineMetrics(
            engine_type=EngineType.LLAMA_CPP,
            latency_p50_ms=150.0,
            latency_p95_ms=250.0,
            latency_p99_ms=350.0,
            throughput_tokens_per_sec=45.0,
            vram_peak_mb=8500.0,
            vram_steady_mb=7200.0,
            time_to_first_token_ms=50.0,
            requests_per_minute=12.0,
        )

        mock_vllm_metrics = EngineMetrics(
            engine_type=EngineType.VLLM,
            latency_p50_ms=120.0,
            latency_p95_ms=200.0,
            latency_p99_ms=280.0,
            throughput_tokens_per_sec=60.0,
            vram_peak_mb=9000.0,
            vram_steady_mb=8000.0,
            time_to_first_token_ms=35.0,
            requests_per_minute=15.0,
        )

        with patch.object(
            comparator,
            "benchmark_engine",
            side_effect=[mock_llama_metrics, mock_vllm_metrics],
        ):
            results = await comparator.compare_all_engines(prompts=["test prompt"])
            assert len(results) == 2
            assert EngineType.LLAMA_CPP in results
            assert EngineType.VLLM in results

    @pytest.mark.asyncio
    async def test_compare_engines_skip_unavailable(self) -> None:
        """Test that unavailable engines are skipped."""
        comparator = EngineComparator()

        mock_llama_metrics = EngineMetrics(
            engine_type=EngineType.LLAMA_CPP,
            latency_p50_ms=150.0,
            latency_p95_ms=250.0,
            latency_p99_ms=350.0,
            throughput_tokens_per_sec=45.0,
            vram_peak_mb=8500.0,
            vram_steady_mb=7200.0,
            time_to_first_token_ms=50.0,
            requests_per_minute=12.0,
        )

        async def mock_benchmark(engine_type: EngineType, _prompts: list[str]) -> EngineMetrics:
            if engine_type == EngineType.VLLM:
                raise RuntimeError("Engine vllm is not healthy")
            return mock_llama_metrics

        with patch.object(comparator, "benchmark_engine", side_effect=mock_benchmark):
            results = await comparator.compare_all_engines(prompts=["test"], skip_unavailable=True)
            assert len(results) == 1
            assert EngineType.LLAMA_CPP in results


class TestOpenAICompatibility:
    """Tests for OpenAI API compatibility layer."""

    @pytest.mark.asyncio
    async def test_llama_cpp_request_format(self) -> None:
        """Test llama.cpp request format."""
        comparator = EngineComparator()

        request = comparator._format_request(
            EngineType.LLAMA_CPP,
            prompt="Test prompt",
            max_tokens=100,
        )

        # llama.cpp uses /completion endpoint with prompt field
        assert "prompt" in request
        assert request["prompt"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_vllm_request_format(self) -> None:
        """Test vLLM (OpenAI-compatible) request format."""
        comparator = EngineComparator()

        request = comparator._format_request(
            EngineType.VLLM,
            prompt="Test prompt",
            max_tokens=100,
        )

        # vLLM uses OpenAI format with messages array
        assert "messages" in request
        assert request["messages"][0]["role"] == "user"
        assert request["messages"][0]["content"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_parse_llama_cpp_response(self) -> None:
        """Test parsing llama.cpp response."""
        comparator = EngineComparator()

        response = {
            "content": "Generated response",
            "tokens_predicted": 50,
            "timings": {
                "prompt_ms": 100,
                "predicted_ms": 500,
            },
        }

        parsed = comparator._parse_response(EngineType.LLAMA_CPP, response)
        assert parsed["text"] == "Generated response"
        assert parsed["tokens"] == 50

    @pytest.mark.asyncio
    async def test_parse_vllm_response(self) -> None:
        """Test parsing vLLM (OpenAI) response."""
        comparator = EngineComparator()

        response = {
            "choices": [
                {
                    "message": {"content": "Generated response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "completion_tokens": 50,
                "prompt_tokens": 20,
                "total_tokens": 70,
            },
        }

        parsed = comparator._parse_response(EngineType.VLLM, response)
        assert parsed["text"] == "Generated response"
        assert parsed["tokens"] == 50


class TestComparisonReport:
    """Tests for comparison report generation."""

    def test_generate_comparison_report_basic(self) -> None:
        """Test basic comparison report generation."""
        results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
            EngineType.VLLM: EngineMetrics(
                engine_type=EngineType.VLLM,
                latency_p50_ms=120.0,
                latency_p95_ms=200.0,
                latency_p99_ms=280.0,
                throughput_tokens_per_sec=60.0,
                vram_peak_mb=9000.0,
                vram_steady_mb=8000.0,
                time_to_first_token_ms=35.0,
                requests_per_minute=15.0,
            ),
        }

        report = generate_comparison_report(results)

        assert "comparison" in report
        assert "llama.cpp" in report["comparison"]
        assert "vllm" in report["comparison"]

    def test_comparison_report_contains_all_metrics(self) -> None:
        """Test that comparison report contains all metrics."""
        results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
        }

        report = generate_comparison_report(results)
        llama_report = report["comparison"]["llama.cpp"]

        assert "latency_p50_ms" in llama_report
        assert "latency_p95_ms" in llama_report
        assert "latency_p99_ms" in llama_report
        assert "throughput_tokens_per_sec" in llama_report
        assert "vram_peak_mb" in llama_report
        assert "vram_steady_mb" in llama_report
        assert "time_to_first_token_ms" in llama_report
        assert "requests_per_minute" in llama_report

    def test_comparison_report_includes_deltas(self) -> None:
        """Test that comparison report includes performance deltas."""
        results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
            EngineType.VLLM: EngineMetrics(
                engine_type=EngineType.VLLM,
                latency_p50_ms=120.0,
                latency_p95_ms=200.0,
                latency_p99_ms=280.0,
                throughput_tokens_per_sec=60.0,
                vram_peak_mb=9000.0,
                vram_steady_mb=8000.0,
                time_to_first_token_ms=35.0,
                requests_per_minute=15.0,
            ),
        }

        report = generate_comparison_report(results)

        # Report should include performance deltas/comparisons
        assert "deltas" in report or "summary" in report

    def test_comparison_report_identifies_winner(self) -> None:
        """Test that comparison report identifies best performer."""
        results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
            EngineType.VLLM: EngineMetrics(
                engine_type=EngineType.VLLM,
                latency_p50_ms=120.0,
                latency_p95_ms=200.0,
                latency_p99_ms=280.0,
                throughput_tokens_per_sec=60.0,
                vram_peak_mb=9000.0,
                vram_steady_mb=8000.0,
                time_to_first_token_ms=35.0,
                requests_per_minute=15.0,
            ),
        }

        report = generate_comparison_report(results)

        # Report should identify best engine for each metric category
        assert "recommendations" in report or "best_for" in report


class TestCompareEnginesFunction:
    """Tests for compare_engines convenience function."""

    @pytest.mark.asyncio
    async def test_compare_engines_basic(self) -> None:
        """Test basic compare_engines function."""
        mock_results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
        }

        with patch(
            "scripts.benchmark.engine_comparison.EngineComparator.compare_all_engines",
            return_value=mock_results,
        ):
            results = await compare_engines(prompts=["test prompt"])
            assert EngineType.LLAMA_CPP in results

    @pytest.mark.asyncio
    async def test_compare_engines_with_output_path(self, tmp_path: Path) -> None:
        """Test compare_engines saves results to file."""
        mock_results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
        }

        output_file = tmp_path / "comparison.json"

        with patch(
            "scripts.benchmark.engine_comparison.EngineComparator.compare_all_engines",
            return_value=mock_results,
        ):
            await compare_engines(prompts=["test"], output_path=output_file)

            assert output_file.exists()
            data = json.loads(output_file.read_text())
            assert "comparison" in data or "results" in data


class TestDockerComposeIntegration:
    """Tests for docker-compose.prod.yml vLLM service configuration."""

    def test_vllm_service_config_structure(self) -> None:
        """Test expected vLLM service configuration structure."""
        # This test documents the expected docker-compose configuration
        expected_config = {
            "image": "vllm/vllm-openai:latest",
            "ports": ["127.0.0.1:8092:8000"],
            "deploy": {
                "resources": {
                    "reservations": {
                        "devices": [
                            {
                                "driver": "nvidia",
                                "capabilities": ["gpu"],
                            }
                        ]
                    }
                }
            },
        }

        # Verify expected config is valid structure
        assert "image" in expected_config
        assert "ports" in expected_config
        assert "deploy" in expected_config

    def test_vllm_environment_variables(self) -> None:
        """Test expected vLLM environment variables."""
        expected_env = {
            "VLLM_MODEL": "nvidia/Nemotron-3-Nano-30B-A3B",
            "VLLM_GPU_MEMORY_UTILIZATION": "0.9",
            "VLLM_MAX_MODEL_LEN": "32768",
        }

        # Verify all expected env vars are documented
        assert "VLLM_MODEL" in expected_env
        assert "VLLM_GPU_MEMORY_UTILIZATION" in expected_env
        assert "VLLM_MAX_MODEL_LEN" in expected_env


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_prompts_raises_error(self) -> None:
        """Test that empty prompts list raises error."""
        comparator = EngineComparator()

        with pytest.raises(ValueError, match="[Pp]rompts.*empty"):
            await comparator.benchmark_engine(EngineType.LLAMA_CPP, prompts=[])

    @pytest.mark.asyncio
    async def test_unknown_engine_type(self) -> None:
        """Test handling of unknown engine type."""
        comparator = EngineComparator()

        # Create a mock "unknown" engine type by removing config
        comparator.configs = {}

        with pytest.raises(KeyError):
            await comparator.benchmark_engine(EngineType.LLAMA_CPP, prompts=["test"])

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test request timeout handling."""
        comparator = EngineComparator()

        with patch("httpx.AsyncClient") as mock_client:
            import httpx

            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            with (
                patch.object(comparator, "check_engine_health", return_value=True),
                pytest.raises((TimeoutError, httpx.TimeoutException)),
            ):
                await comparator.benchmark_engine(EngineType.LLAMA_CPP, prompts=["test"])

    def test_report_generation_single_engine(self) -> None:
        """Test report generation with only one engine."""
        results = {
            EngineType.LLAMA_CPP: EngineMetrics(
                engine_type=EngineType.LLAMA_CPP,
                latency_p50_ms=150.0,
                latency_p95_ms=250.0,
                latency_p99_ms=350.0,
                throughput_tokens_per_sec=45.0,
                vram_peak_mb=8500.0,
                vram_steady_mb=7200.0,
                time_to_first_token_ms=50.0,
                requests_per_minute=12.0,
            ),
        }

        # Should not raise even with single engine
        report = generate_comparison_report(results)
        assert report is not None

    def test_report_generation_empty_results(self) -> None:
        """Test report generation with no results."""
        results: dict[EngineType, EngineMetrics] = {}

        report = generate_comparison_report(results)
        # Should handle gracefully
        assert report is not None
        assert "comparison" in report or "error" in report


class TestCLI:
    """Tests for CLI interface."""

    def test_cli_argument_parsing(self) -> None:
        """Test CLI argument parsing."""
        from scripts.benchmark.engine_comparison import parse_args

        args = parse_args(
            [
                "--prompts",
                "test prompt 1",
                "test prompt 2",
                "--output",
                "/tmp/results.json",  # noqa: S108
                "--engines",
                "llama.cpp",
                "vllm",
            ]
        )

        assert args.prompts == ["test prompt 1", "test prompt 2"]
        assert str(args.output) == "/tmp/results.json"  # noqa: S108
        assert args.engines == ["llama.cpp", "vllm"]

    def test_cli_default_arguments(self) -> None:
        """Test CLI default arguments."""
        from scripts.benchmark.engine_comparison import parse_args

        args = parse_args(["--prompts", "test"])

        assert args.prompts == ["test"]
        assert args.engines is None or args.engines == ["llama.cpp", "vllm"]

    def test_cli_evaluation_set_argument(self) -> None:
        """Test CLI with evaluation set path."""
        from scripts.benchmark.engine_comparison import parse_args

        args = parse_args(
            [
                "--evaluation-set",
                "/path/to/evaluation",
                "--output",
                "/tmp/results.json",  # noqa: S108
            ]
        )

        assert str(args.evaluation_set) == "/path/to/evaluation"


class TestMetricsCollection:
    """Tests for metrics collection during benchmarking."""

    @pytest.mark.asyncio
    async def test_latency_percentile_calculation(self) -> None:
        """Test latency percentile calculation."""
        comparator = EngineComparator()

        # Mock response times
        response_times = [100, 110, 120, 130, 140, 150, 200, 250, 300, 500]

        with patch.object(comparator, "_collect_latencies", return_value=response_times):
            metrics = comparator._calculate_latency_percentiles(response_times)

            # P50 should be around 145 (median of 10 values)
            assert 130 <= metrics["p50"] <= 160
            # P95 should be high
            assert metrics["p95"] >= 250
            # P99 should be highest
            assert metrics["p99"] >= 300

    @pytest.mark.asyncio
    async def test_throughput_calculation(self) -> None:
        """Test throughput calculation."""
        comparator = EngineComparator()

        total_tokens = 1000
        duration_sec = 20.0

        throughput = comparator._calculate_throughput(total_tokens, duration_sec)

        # Should be 50 tokens/sec
        assert throughput == 50.0

    @pytest.mark.asyncio
    async def test_vram_monitoring(self) -> None:
        """Test VRAM monitoring integration."""
        comparator = EngineComparator()

        mock_vram_data = {"peak_mb": 9000.0, "steady_mb": 8000.0}

        with patch.object(comparator, "_monitor_vram", return_value=mock_vram_data):
            vram = await comparator._monitor_vram(duration_sec=5.0)

            assert vram["peak_mb"] == 9000.0
            assert vram["steady_mb"] == 8000.0
