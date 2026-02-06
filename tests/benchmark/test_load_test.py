"""TDD Tests for load testing module.

Phase 5: Batching and Scheduling Optimization
Tests written BEFORE implementation (Red Phase).

The load_test.py module provides sustained load and burst testing:
- Sustained load: Steady stream of requests over time
- Burst testing: Sudden spikes to measure queue behavior
- Measures throughput improvements from batching/priority
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLoadConfig:
    """Test LoadConfig dataclass."""

    def test_load_config_creation(self) -> None:
        """LoadConfig should hold test parameters."""
        from scripts.benchmark.load_test import LoadConfig

        config = LoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=60,
            requests_per_second=5.0,
        )

        assert config.target_url == "http://localhost:8000"
        assert config.duration_seconds == 60
        assert config.requests_per_second == 5.0

    def test_load_config_defaults(self) -> None:
        """LoadConfig should have sensible defaults."""
        from scripts.benchmark.load_test import LoadConfig

        config = LoadConfig(target_url="http://localhost:8000")

        assert config.duration_seconds > 0
        assert config.requests_per_second > 0
        assert config.timeout_seconds > 0


class TestSustainedLoadConfig:
    """Test SustainedLoadConfig for steady load patterns."""

    def test_sustained_config_ramp_up(self) -> None:
        """Sustained load can have ramp-up period."""
        from scripts.benchmark.load_test import SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=300,
            requests_per_second=10.0,
            ramp_up_seconds=30,
        )

        assert config.ramp_up_seconds == 30

    def test_sustained_config_steady_state(self) -> None:
        """Sustained load should track steady-state metrics."""
        from scripts.benchmark.load_test import SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=120,
            requests_per_second=5.0,
            steady_state_start=30,  # Metrics after 30s warmup
        )

        assert config.steady_state_start == 30


class TestBurstConfig:
    """Test BurstConfig for spike load patterns."""

    def test_burst_config_creation(self) -> None:
        """BurstConfig should define burst parameters."""
        from scripts.benchmark.load_test import BurstConfig

        config = BurstConfig(
            target_url="http://localhost:8000",
            burst_size=10,
            burst_interval_seconds=5.0,
            total_bursts=6,
        )

        assert config.burst_size == 10
        assert config.burst_interval_seconds == 5.0
        assert config.total_bursts == 6

    def test_burst_calculates_total_requests(self) -> None:
        """Burst config should calculate total request count."""
        from scripts.benchmark.load_test import BurstConfig

        config = BurstConfig(
            target_url="http://localhost:8000",
            burst_size=10,
            burst_interval_seconds=5.0,
            total_bursts=6,
        )

        assert config.total_requests == 60  # 10 * 6


class TestLoadTestMetrics:
    """Test LoadTestMetrics result dataclass."""

    def test_metrics_captures_latency(self) -> None:
        """Metrics should capture latency percentiles."""
        from scripts.benchmark.load_test import LoadTestMetrics

        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latency_p50_ms=150.0,
            latency_p95_ms=500.0,
            latency_p99_ms=1200.0,
            throughput_rps=8.5,
            test_duration_seconds=60.0,
        )

        assert metrics.latency_p50_ms == 150.0
        assert metrics.latency_p95_ms == 500.0
        assert metrics.latency_p99_ms == 1200.0

    def test_metrics_calculates_success_rate(self) -> None:
        """Metrics should calculate success rate."""
        from scripts.benchmark.load_test import LoadTestMetrics

        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latency_p50_ms=150.0,
            latency_p95_ms=500.0,
            latency_p99_ms=1200.0,
            throughput_rps=8.5,
            test_duration_seconds=60.0,
        )

        assert metrics.success_rate == 0.95

    def test_metrics_captures_error_breakdown(self) -> None:
        """Metrics should categorize errors."""
        from scripts.benchmark.load_test import LoadTestMetrics

        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=90,
            failed_requests=10,
            latency_p50_ms=150.0,
            latency_p95_ms=500.0,
            latency_p99_ms=1200.0,
            throughput_rps=8.5,
            test_duration_seconds=60.0,
            error_breakdown={"timeout": 5, "5xx": 3, "connection_error": 2},
        )

        assert metrics.error_breakdown["timeout"] == 5
        assert metrics.error_breakdown["5xx"] == 3


class TestLoadTestRunner:
    """Test LoadTestRunner class."""

    def test_runner_initialization(self) -> None:
        """Runner initializes with config."""
        from scripts.benchmark.load_test import LoadConfig, LoadTestRunner

        config = LoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=60,
        )
        runner = LoadTestRunner(config)

        assert runner.config == config

    @pytest.mark.asyncio
    async def test_runner_runs_sustained_load(self) -> None:
        """Runner can execute sustained load test."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=5,  # Short for testing
            requests_per_second=2.0,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(status_code=200)
            )

            metrics = await runner.run_sustained()

            assert metrics.total_requests > 0
            assert metrics.test_duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_runner_runs_burst_test(self) -> None:
        """Runner can execute burst test."""
        from scripts.benchmark.load_test import BurstConfig, LoadTestRunner

        config = BurstConfig(
            target_url="http://localhost:8000",
            burst_size=5,
            burst_interval_seconds=1.0,
            total_bursts=2,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(status_code=200)
            )

            metrics = await runner.run_burst()

            assert metrics.total_requests == 10  # 5 * 2


class TestRequestGeneration:
    """Test request payload generation."""

    def test_generates_detection_payload(self) -> None:
        """Generate realistic detection payloads."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
        )
        runner = LoadTestRunner(config)

        payload = runner.generate_detection_payload()

        assert "camera_id" in payload
        assert "detections" in payload
        assert len(payload["detections"]) >= 1

    def test_generates_varied_priorities(self) -> None:
        """Generated payloads should have varied priorities."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
        )
        runner = LoadTestRunner(config)

        # Generate multiple payloads
        payloads = [runner.generate_detection_payload() for _ in range(20)]

        # Should have variety in object types (affecting priority)
        object_types = set()
        for p in payloads:
            for det in p["detections"]:
                object_types.add(det.get("label", "unknown"))

        assert len(object_types) >= 2  # At least 2 different types

    def test_generates_from_evaluation_set(self) -> None:
        """Can generate payloads from evaluation set."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
            evaluation_set_path=Path("data/benchmark/evaluation-set"),
        )
        runner = LoadTestRunner(config)

        # Should load from evaluation set if exists
        assert hasattr(runner, "_evaluation_payloads")


class TestSustainedLoadBehavior:
    """Test sustained load test behavior."""

    @pytest.mark.asyncio
    async def test_maintains_steady_rate(self) -> None:
        """Sustained load maintains target request rate."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=5,
            requests_per_second=2.0,  # 2 RPS = 10 requests in 5s
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_resp = MagicMock(status_code=200)
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )

            metrics = await runner.run_sustained()

            # Should be approximately 10 requests (±2 for timing variance)
            assert 8 <= metrics.total_requests <= 12

    @pytest.mark.asyncio
    async def test_ramp_up_increases_rate(self) -> None:
        """Ramp-up period gradually increases request rate."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
            requests_per_second=5.0,
            ramp_up_seconds=5,  # First 5s ramp up
        )
        runner = LoadTestRunner(config)

        # Ramp-up should start at lower rate
        rate_at_start = runner._calculate_rate_at_time(0)
        rate_at_end = runner._calculate_rate_at_time(10)

        assert rate_at_start < rate_at_end
        assert rate_at_end == 5.0


class TestBurstBehavior:
    """Test burst test behavior."""

    @pytest.mark.asyncio
    async def test_burst_sends_concurrent_requests(self) -> None:
        """Burst sends all requests in burst simultaneously."""
        from scripts.benchmark.load_test import BurstConfig, LoadTestRunner

        config = BurstConfig(
            target_url="http://localhost:8000",
            burst_size=10,
            burst_interval_seconds=2.0,
            total_bursts=1,
        )
        runner = LoadTestRunner(config)

        request_times: list[float] = []

        async def mock_post(*_args, **_kwargs):
            request_times.append(datetime.now(tz=UTC).timestamp())
            return MagicMock(status_code=200)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = mock_post

            await runner.run_burst()

            # All 10 requests should be within ~100ms of each other
            if len(request_times) >= 2:
                time_spread = max(request_times) - min(request_times)
                assert time_spread < 0.5  # All within 500ms

    @pytest.mark.asyncio
    async def test_burst_respects_interval(self) -> None:
        """Bursts are separated by interval."""
        from scripts.benchmark.load_test import BurstConfig, LoadTestRunner

        config = BurstConfig(
            target_url="http://localhost:8000",
            burst_size=3,
            burst_interval_seconds=1.0,
            total_bursts=3,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(status_code=200)
            )

            metrics = await runner.run_burst()

            # 3 bursts with 1s interval = ~2s total
            assert metrics.test_duration_seconds >= 2.0


class TestPriorityQueueMeasurement:
    """Test measurement of priority queue behavior."""

    @pytest.mark.asyncio
    async def test_measures_priority_latency(self) -> None:
        """Measure latency differences by priority."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
            measure_priority_latency=True,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(status_code=200)
            )

            metrics = await runner.run_sustained()

            # Should have per-priority metrics
            assert hasattr(metrics, "latency_by_priority")

    @pytest.mark.asyncio
    async def test_measures_coalescing_effect(self) -> None:
        """Measure effect of batch coalescing on throughput."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=10,
            measure_coalescing=True,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=MagicMock(status_code=200)
            )

            metrics = await runner.run_sustained()

            # Should track coalescing metrics
            assert hasattr(metrics, "batches_coalesced")


class TestReportGeneration:
    """Test load test report generation."""

    def test_generates_json_report(self) -> None:
        """Generate JSON report from metrics."""
        from scripts.benchmark.load_test import LoadTestMetrics, generate_report

        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latency_p50_ms=150.0,
            latency_p95_ms=500.0,
            latency_p99_ms=1200.0,
            throughput_rps=8.5,
            test_duration_seconds=60.0,
        )

        report = generate_report(metrics)

        assert "summary" in report
        assert "latency" in report
        assert "throughput" in report

    def test_saves_report_to_file(self, tmp_path: Path) -> None:
        """Save report to specified path."""
        from scripts.benchmark.load_test import LoadTestMetrics, save_report

        metrics = LoadTestMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            latency_p50_ms=150.0,
            latency_p95_ms=500.0,
            latency_p99_ms=1200.0,
            throughput_rps=8.5,
            test_duration_seconds=60.0,
        )

        output_path = tmp_path / "load_test_results.json"
        save_report(metrics, output_path)

        assert output_path.exists()


class TestCLI:
    """Test CLI argument parsing."""

    def test_parse_sustained_args(self) -> None:
        """Parse sustained load test arguments."""
        from scripts.benchmark.load_test import parse_args

        args = parse_args(
            [
                "--mode",
                "sustained",
                "--duration",
                "60",
                "--rps",
                "5",
                "--url",
                "http://localhost:8000",
            ]
        )

        assert args.mode == "sustained"
        assert args.duration == 60
        assert args.rps == 5

    def test_parse_burst_args(self) -> None:
        """Parse burst test arguments."""
        from scripts.benchmark.load_test import parse_args

        args = parse_args(
            [
                "--mode",
                "burst",
                "--burst-size",
                "10",
                "--burst-interval",
                "5",
                "--total-bursts",
                "6",
            ]
        )

        assert args.mode == "burst"
        assert args.burst_size == 10
        assert args.burst_interval == 5

    def test_default_mode_is_sustained(self) -> None:
        """Default mode is sustained load."""
        from scripts.benchmark.load_test import parse_args

        args = parse_args([])

        assert args.mode == "sustained"


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_connection_errors(self) -> None:
        """Gracefully handle connection errors."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=2,
            requests_per_second=2.0,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=ConnectionError("Connection refused")
            )

            metrics = await runner.run_sustained()

            assert metrics.failed_requests > 0
            assert "connection_error" in metrics.error_breakdown

    @pytest.mark.asyncio
    async def test_handles_timeouts(self) -> None:
        """Gracefully handle request timeouts."""
        import httpx

        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=2,
            requests_per_second=2.0,
            timeout_seconds=1,
        )
        runner = LoadTestRunner(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )

            metrics = await runner.run_sustained()

            assert metrics.failed_requests > 0
            assert "timeout" in metrics.error_breakdown

    @pytest.mark.asyncio
    async def test_zero_duration_returns_empty(self) -> None:
        """Zero duration returns empty metrics."""
        from scripts.benchmark.load_test import LoadTestRunner, SustainedLoadConfig

        config = SustainedLoadConfig(
            target_url="http://localhost:8000",
            duration_seconds=0,
        )
        runner = LoadTestRunner(config)

        metrics = await runner.run_sustained()

        assert metrics.total_requests == 0
