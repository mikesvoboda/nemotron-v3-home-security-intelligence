"""Unit tests for benchmark metrics collector.

This test suite follows TDD principles - tests are written first and will FAIL
until the implementation is completed in scripts/benchmark/metrics.py.

Test coverage:
1. Latency metrics: P50, P95, P99, time-to-first-token calculation
2. VRAM metrics: Peak usage, steady-state via nvidia-smi polling
3. Throughput metrics: Requests/min, tokens/sec from sustained load tests
4. Edge cases: GPU not present, service unavailable, timeout handling
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from scripts.benchmark.metrics import (
    GPUNotAvailableError,
    LatencyMetrics,
    MetricsCollector,
    ServiceUnavailableError,
    ThroughputMetrics,
    VRAMMetrics,
)


@pytest.fixture
def service_url() -> str:
    """LLM service URL for testing."""
    return "http://localhost:8000"


@pytest.fixture
def metrics_collector(service_url: str) -> MetricsCollector:
    """Create a MetricsCollector instance."""
    return MetricsCollector(service_url)


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {
        "response": "This is a test response.",
        "tokens": 6,
        "time_to_first_token_ms": 120.5,
        "total_time_ms": 450.2,
    }
    return response


@pytest.fixture
def sample_prompts() -> list[str]:
    """Sample prompts for load testing."""
    return [
        "What is the capital of France?",
        "Explain quantum computing in simple terms.",
        "Write a haiku about programming.",
    ]


def test_metrics_collector_initialization(service_url: str):
    """Test MetricsCollector can be initialized with service URL."""
    collector = MetricsCollector(service_url)
    assert collector is not None


def test_metrics_collector_stores_service_url(service_url: str):
    """Test MetricsCollector stores the service URL."""
    collector = MetricsCollector(service_url)
    assert hasattr(collector, "service_url")
    assert collector.service_url == service_url


@pytest.mark.asyncio
async def test_record_request_sends_http_post(
    metrics_collector: MetricsCollector,
    mock_http_response,
):
    """Test record_request sends HTTP POST to service."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response) as mock_post:
        result = await metrics_collector.record_request("Test prompt")

        mock_post.assert_called_once()
        assert result is not None


@pytest.mark.asyncio
async def test_record_request_returns_response_data(
    metrics_collector: MetricsCollector,
    mock_http_response,
):
    """Test record_request returns response data including timing."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        result = await metrics_collector.record_request("Test prompt")

        assert "response" in result
        assert "time_to_first_token_ms" in result
        assert "total_time_ms" in result


@pytest.mark.asyncio
async def test_record_request_tracks_latency_internally(
    metrics_collector: MetricsCollector,
    mock_http_response,
):
    """Test record_request tracks latency for later calculation."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        await metrics_collector.record_request("Test prompt")

        # Collector should have internal state tracking latencies
        assert hasattr(metrics_collector, "_latencies") or hasattr(metrics_collector, "latencies")


@pytest.mark.asyncio
async def test_record_request_raises_on_connection_error(metrics_collector: MetricsCollector):
    """Test record_request raises ServiceUnavailableError on connection failure."""
    with (
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        pytest.raises(ServiceUnavailableError),
    ):
        await metrics_collector.record_request("Test prompt")


@pytest.mark.asyncio
async def test_record_request_raises_on_timeout(metrics_collector: MetricsCollector):
    """Test record_request raises TimeoutError on timeout."""
    with (
        patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")),
        pytest.raises(TimeoutError),
    ):
        await metrics_collector.record_request("Test prompt")


@pytest.mark.asyncio
async def test_record_request_raises_on_http_error(metrics_collector: MetricsCollector):
    """Test record_request raises ServiceUnavailableError on HTTP error."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error",
        request=MagicMock(spec=httpx.Request),
        response=mock_response,
    )

    with (
        patch("httpx.AsyncClient.post", return_value=mock_response),
        pytest.raises(ServiceUnavailableError),
    ):
        await metrics_collector.record_request("Test prompt")


def test_get_latency_metrics_raises_when_no_requests(metrics_collector: MetricsCollector):
    """Test get_latency_metrics raises ValueError when no requests recorded."""
    with pytest.raises(ValueError, match="No requests have been recorded"):
        metrics_collector.get_latency_metrics()


@pytest.mark.asyncio
async def test_get_latency_metrics_calculates_percentiles(
    metrics_collector: MetricsCollector,
    mock_http_response,  # noqa: ARG001
):
    """Test get_latency_metrics calculates P50, P95, P99 correctly."""
    # Record multiple requests with varying latencies
    latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 1000]

    for latency_ms in latencies:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "Test",
            "tokens": 5,
            "time_to_first_token_ms": latency_ms * 0.3,
            "total_time_ms": latency_ms,
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            await metrics_collector.record_request("Test")

    metrics = metrics_collector.get_latency_metrics()

    assert isinstance(metrics, LatencyMetrics)
    assert metrics.p50 > 0
    assert metrics.p95 > 0
    assert metrics.p99 > 0
    assert metrics.p95 > metrics.p50
    assert metrics.p99 > metrics.p95


@pytest.mark.asyncio
async def test_get_latency_metrics_includes_ttft(
    metrics_collector: MetricsCollector,
    mock_http_response,
):
    """Test get_latency_metrics includes time-to-first-token."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        await metrics_collector.record_request("Test")

    metrics = metrics_collector.get_latency_metrics()

    assert metrics.time_to_first_token > 0
    assert metrics.time_to_first_token < metrics.mean  # TTFT should be less than total time


@pytest.mark.asyncio
async def test_get_latency_metrics_includes_count(
    metrics_collector: MetricsCollector,
    mock_http_response,
):
    """Test get_latency_metrics includes request count."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        await metrics_collector.record_request("Test 1")
        await metrics_collector.record_request("Test 2")
        await metrics_collector.record_request("Test 3")

    metrics = metrics_collector.get_latency_metrics()

    assert metrics.count == 3


@pytest.mark.asyncio
async def test_monitor_vram_polls_nvidia_smi(metrics_collector: MetricsCollector):
    """Test monitor_vram calls nvidia-smi to collect GPU memory usage."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (
        b"1024 MiB\n1536 MiB\n2048 MiB\n1800 MiB\n",
        b"",
    )
    mock_process.returncode = 0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        metrics = await metrics_collector.monitor_vram(duration_sec=2.0, interval_sec=0.5)

        assert isinstance(metrics, VRAMMetrics)
        assert mock_process.communicate.called


@pytest.mark.asyncio
async def test_monitor_vram_calculates_peak_usage(metrics_collector: MetricsCollector):
    """Test monitor_vram correctly identifies peak VRAM usage."""
    # Simulate varying VRAM usage over time
    vram_samples = [1024, 1536, 2048, 1800, 1900]
    mock_outputs = [f"{vram} MiB\n".encode() for vram in vram_samples]

    async def mock_subprocess(*_args, **_kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_outputs.pop(0), b"")
        mock_proc.returncode = 0
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
        metrics = await metrics_collector.monitor_vram(duration_sec=2.0, interval_sec=0.5)

        assert metrics.peak_usage_mb == 2048.0


@pytest.mark.asyncio
async def test_monitor_vram_calculates_steady_state(metrics_collector: MetricsCollector):
    """Test monitor_vram calculates steady-state VRAM (median or mean)."""
    vram_samples = [1024, 1536, 2048, 1800, 1900]
    mock_outputs = [f"{vram} MiB\n".encode() for vram in vram_samples]

    async def mock_subprocess(*_args, **_kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_outputs.pop(0), b"")
        mock_proc.returncode = 0
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
        metrics = await metrics_collector.monitor_vram(duration_sec=2.0, interval_sec=0.5)

        # Steady state should be near the median (1800 or 1536)
        assert 1500 <= metrics.steady_state_mb <= 2000


@pytest.mark.asyncio
async def test_monitor_vram_includes_sample_count(metrics_collector: MetricsCollector):
    """Test monitor_vram includes number of samples collected."""
    vram_samples = [1024, 1536, 2048, 1800]
    mock_outputs = [f"{vram} MiB\n".encode() for vram in vram_samples]

    async def mock_subprocess(*_args, **_kwargs):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_outputs.pop(0), b"")
        mock_proc.returncode = 0
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess):
        metrics = await metrics_collector.monitor_vram(duration_sec=2.0, interval_sec=0.5)

        assert metrics.samples == 4


@pytest.mark.asyncio
async def test_monitor_vram_raises_when_gpu_not_available(metrics_collector: MetricsCollector):
    """Test monitor_vram raises GPUNotAvailableError when nvidia-smi fails."""
    mock_process = AsyncMock()
    mock_process.communicate.return_value = (b"", b"nvidia-smi: command not found\n")
    mock_process.returncode = 1

    with (
        patch("asyncio.create_subprocess_exec", return_value=mock_process),
        pytest.raises(GPUNotAvailableError),
    ):
        await metrics_collector.monitor_vram()


@pytest.mark.asyncio
async def test_monitor_vram_raises_when_subprocess_fails(metrics_collector: MetricsCollector):
    """Test monitor_vram raises GPUNotAvailableError on subprocess failure."""
    with (
        patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("nvidia-smi not found"),
        ),
        pytest.raises(GPUNotAvailableError),
    ):
        await metrics_collector.monitor_vram()


@pytest.mark.asyncio
async def test_run_sustained_load_raises_on_empty_prompts(metrics_collector: MetricsCollector):
    """Test run_sustained_load raises ValueError when prompts list is empty."""
    with pytest.raises(ValueError, match="Prompts list cannot be empty"):
        await metrics_collector.run_sustained_load(prompts=[])


@pytest.mark.asyncio
async def test_run_sustained_load_sends_concurrent_requests(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test run_sustained_load sends concurrent requests."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response) as mock_post:
        metrics = await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=2.0,
            concurrent_requests=2,
        )

        # Should have sent multiple requests concurrently
        assert mock_post.call_count >= 2
        assert isinstance(metrics, ThroughputMetrics)


@pytest.mark.asyncio
async def test_run_sustained_load_calculates_requests_per_min(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test run_sustained_load calculates requests per minute."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        metrics = await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=2.0,
            concurrent_requests=1,
        )

        assert metrics.requests_per_min > 0
        # Should be reasonable: if we send N requests in 2 seconds,
        # that's N/2 * 60 = 30N requests per minute
        assert metrics.total_requests > 0
        expected_rpm = (metrics.total_requests / metrics.duration_sec) * 60
        assert abs(metrics.requests_per_min - expected_rpm) < 1.0


@pytest.mark.asyncio
async def test_run_sustained_load_calculates_tokens_per_sec(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
):
    """Test run_sustained_load calculates tokens per second."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Test response",
        "tokens": 10,
        "time_to_first_token_ms": 50.0,
        "total_time_ms": 200.0,
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        metrics = await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=2.0,
            concurrent_requests=1,
        )

        assert metrics.tokens_per_sec > 0
        assert metrics.total_tokens > 0
        expected_tps = metrics.total_tokens / metrics.duration_sec
        assert abs(metrics.tokens_per_sec - expected_tps) < 1.0


@pytest.mark.asyncio
async def test_run_sustained_load_respects_duration(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test run_sustained_load runs for approximately the specified duration."""
    import time

    start_time = time.time()

    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        metrics = await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=1.0,
            concurrent_requests=1,
        )

    elapsed = time.time() - start_time

    # Should complete within reasonable time (allow 50% overhead for test execution)
    assert elapsed < 2.0
    # Duration in metrics should match requested duration
    assert 0.8 <= metrics.duration_sec <= 1.5


@pytest.mark.asyncio
async def test_run_sustained_load_cycles_through_prompts(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test run_sustained_load cycles through prompts list."""
    called_prompts = []

    async def capture_prompt(*_args, **kwargs):
        # Capture the prompt from the request
        if "json" in kwargs and "prompt" in kwargs["json"]:
            called_prompts.append(kwargs["json"]["prompt"])
        return mock_http_response

    with patch("httpx.AsyncClient.post", side_effect=capture_prompt):
        await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=1.0,
            concurrent_requests=1,
        )

    # Should have cycled through prompts (may repeat if duration is long enough)
    assert len(called_prompts) >= len(sample_prompts) or len(called_prompts) > 0


@pytest.mark.asyncio
async def test_run_sustained_load_raises_on_service_unavailable(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
):
    """Test run_sustained_load raises ServiceUnavailableError if service goes down."""
    with (
        patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")),
        pytest.raises(ServiceUnavailableError),
    ):
        await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=1.0,
            concurrent_requests=1,
        )


@pytest.mark.asyncio
async def test_run_sustained_load_handles_concurrent_requests(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test run_sustained_load handles multiple concurrent requests correctly."""
    call_times = []

    async def track_call_time(*_args, **_kwargs):
        call_times.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.1)  # Simulate processing time
        return mock_http_response

    with patch("httpx.AsyncClient.post", side_effect=track_call_time):
        await metrics_collector.run_sustained_load(
            prompts=sample_prompts,
            duration_sec=1.0,
            concurrent_requests=3,
        )

    # With concurrency=3, should have overlapping requests
    # Check that we got concurrent execution (multiple calls within small time window)
    assert len(call_times) >= 3


@pytest.mark.asyncio
async def test_metrics_collector_handles_malformed_response(
    metrics_collector: MetricsCollector,
):
    """Test metrics collector handles malformed JSON responses gracefully."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with (
        patch("httpx.AsyncClient.post", return_value=mock_resp),
        pytest.raises((ServiceUnavailableError, ValueError)),
    ):
        await metrics_collector.record_request("Test")


@pytest.mark.asyncio
async def test_metrics_collector_handles_missing_timing_fields(
    metrics_collector: MetricsCollector,
):
    """Test metrics collector handles responses missing timing fields."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Test",
        # Missing time_to_first_token_ms and total_time_ms
    }

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        # Should either raise ValueError or use fallback values
        result = await metrics_collector.record_request("Test")
        assert result is not None  # Should handle gracefully


def test_latency_metrics_dataclass_structure():
    """Test LatencyMetrics dataclass has correct structure."""
    metrics = LatencyMetrics(
        p50=0.5,
        p95=0.95,
        p99=0.99,
        time_to_first_token=0.1,
        mean=0.6,
        count=100,
    )

    assert metrics.p50 == 0.5
    assert metrics.p95 == 0.95
    assert metrics.p99 == 0.99
    assert metrics.time_to_first_token == 0.1
    assert metrics.mean == 0.6
    assert metrics.count == 100


def test_vram_metrics_dataclass_structure():
    """Test VRAMMetrics dataclass has correct structure."""
    metrics = VRAMMetrics(
        peak_usage_mb=2048.0,
        steady_state_mb=1536.0,
        min_usage_mb=1024.0,
        samples=20,
    )

    assert metrics.peak_usage_mb == 2048.0
    assert metrics.steady_state_mb == 1536.0
    assert metrics.min_usage_mb == 1024.0
    assert metrics.samples == 20


def test_throughput_metrics_dataclass_structure():
    """Test ThroughputMetrics dataclass has correct structure."""
    metrics = ThroughputMetrics(
        requests_per_min=120.0,
        tokens_per_sec=25.5,
        total_requests=100,
        total_tokens=1500,
        duration_sec=60.0,
    )

    assert metrics.requests_per_min == 120.0
    assert metrics.tokens_per_sec == 25.5
    assert metrics.total_requests == 100
    assert metrics.total_tokens == 1500
    assert metrics.duration_sec == 60.0


@pytest.mark.asyncio
async def test_full_benchmark_workflow(
    metrics_collector: MetricsCollector,
    sample_prompts: list[str],
    mock_http_response,
):
    """Test complete benchmark workflow: record requests, get metrics."""
    with patch("httpx.AsyncClient.post", return_value=mock_http_response):
        # Record some requests
        for prompt in sample_prompts:
            await metrics_collector.record_request(prompt)

        # Get latency metrics
        latency = metrics_collector.get_latency_metrics()

        assert latency.count == len(sample_prompts)
        assert latency.p50 > 0
        assert latency.p95 > 0
        assert latency.p99 > 0


@pytest.mark.asyncio
async def test_benchmark_with_vram_monitoring(metrics_collector: MetricsCollector):
    """Test benchmark can monitor VRAM during load test."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "response": "Test",
        "tokens": 10,
        "time_to_first_token_ms": 50.0,
        "total_time_ms": 200.0,
    }

    # Mock VRAM monitoring
    vram_samples = [1024, 1536, 2048, 1800]
    mock_outputs = [f"{vram} MiB\n".encode() for vram in vram_samples]

    async def mock_subprocess(*_args, **_kwargs):
        mock_proc = AsyncMock()
        if mock_outputs:
            mock_proc.communicate.return_value = (mock_outputs.pop(0), b"")
        else:
            mock_proc.communicate.return_value = (b"1024 MiB\n", b"")
        mock_proc.returncode = 0
        return mock_proc

    with (
        patch("httpx.AsyncClient.post", return_value=mock_resp),
        patch("asyncio.create_subprocess_exec", side_effect=mock_subprocess),
    ):
        # Run VRAM monitoring in parallel with load test
        vram_task = asyncio.create_task(
            metrics_collector.monitor_vram(duration_sec=1.0, interval_sec=0.25)
        )

        await metrics_collector.record_request("Test prompt")

        vram_metrics = await vram_task

        assert vram_metrics.peak_usage_mb > 0
        assert vram_metrics.samples > 0
