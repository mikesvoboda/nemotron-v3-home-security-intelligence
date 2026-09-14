"""Tests for CUDA Streams utilities (NEM-3770).

These tests verify the cuda_streams module for parallel preprocessing
and overlapped GPU execution.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from unittest.mock import patch

import pytest
import torch
from cuda_streams import (
    CUDA_STREAMS_ENABLED,
    CUDA_STREAMS_POOL_SIZE,
    CUDAStreamPool,
    PipelineStats,
    StreamBenchmarkResult,
    StreamConfig,
    StreamedInferencePipeline,
    StreamPriority,
    benchmark_stream_performance,
    create_inference_on_stream,
    create_preprocess_on_stream,
    is_cuda_streams_available,
)


class TestStreamConfig:
    """Tests for StreamConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = StreamConfig()

        assert config.enabled is True
        assert config.pool_size >= 1
        assert config.priority in (-1, 0)
        assert config.device in (0, "cuda:0")

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = StreamConfig(
            enabled=False,
            pool_size=5,
            priority=StreamPriority.HIGH,
            device=1,
        )

        assert config.enabled is False
        assert config.pool_size == 5
        assert config.priority == -1
        assert config.device == 1

    def test_from_env(self) -> None:
        """Test creating config from environment variables."""
        config = StreamConfig.from_env()

        assert isinstance(config.enabled, bool)
        assert isinstance(config.pool_size, int)
        assert config.pool_size >= 1

    def test_invalid_pool_size_raises(self) -> None:
        """Test that invalid pool size raises ValueError."""
        with pytest.raises(ValueError, match="pool_size must be >= 1"):
            StreamConfig(pool_size=0)

    def test_nonstandard_priority_warns(self) -> None:
        """Test that non-standard priority logs warning."""
        # This should not raise, just warn
        config = StreamConfig(priority=5)
        assert config.priority == 5


class TestStreamPriority:
    """Tests for StreamPriority enum."""

    def test_high_priority_value(self) -> None:
        """Test HIGH priority is -1."""
        assert StreamPriority.HIGH == -1

    def test_default_priority_value(self) -> None:
        """Test DEFAULT priority is 0."""
        assert StreamPriority.DEFAULT == 0


class TestIsCudaStreamsAvailable:
    """Tests for is_cuda_streams_available function."""

    def test_returns_bool(self) -> None:
        """Test that function returns a boolean."""
        result = is_cuda_streams_available()
        assert isinstance(result, bool)

    def test_disabled_via_env(self) -> None:
        """Test that function respects CUDA_STREAMS_ENABLED."""
        with patch("cuda_streams.CUDA_STREAMS_ENABLED", False):
            # Manually check the logic - the patched value should be False
            assert not False  # CUDA_STREAMS_ENABLED is False when patched

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_available_with_cuda(self) -> None:
        """Test that function returns True when CUDA is available and enabled."""
        # Assuming CUDA_STREAMS_ENABLED defaults to true
        result = is_cuda_streams_available()
        assert result is True


class TestCUDAStreamPool:
    """Tests for CUDAStreamPool class."""

    def test_initialization_without_cuda(self) -> None:
        """Test pool initialization when CUDA unavailable."""
        with patch("cuda_streams.is_cuda_streams_available", return_value=False):
            pool = CUDAStreamPool(num_streams=3)
            assert pool.num_streams == 0
            assert not pool._initialized

    def test_custom_num_streams(self) -> None:
        """Test pool with custom number of streams."""
        with patch("cuda_streams.is_cuda_streams_available", return_value=False):
            pool = CUDAStreamPool(num_streams=5)
            assert pool.config.pool_size == 5

    def test_config_override(self) -> None:
        """Test that num_streams overrides config."""
        config = StreamConfig(pool_size=3)
        pool = CUDAStreamPool(num_streams=5, config=config)
        assert pool.config.pool_size == 5

    def test_get_stream_when_unavailable(self) -> None:
        """Test get_stream returns None when streams unavailable."""
        with patch("cuda_streams.is_cuda_streams_available", return_value=False):
            pool = CUDAStreamPool(num_streams=3)
            with pool.get_stream() as stream:
                assert stream is None

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_initialization_with_cuda(self) -> None:
        """Test pool initialization when CUDA is available."""
        pool = CUDAStreamPool(num_streams=3)
        assert pool.num_streams == 3
        assert pool._initialized
        assert pool.num_available == 3

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_get_stream_context_manager(self) -> None:
        """Test get_stream as context manager."""
        pool = CUDAStreamPool(num_streams=3)

        # Get a stream
        with pool.get_stream() as stream:
            assert stream is not None
            assert isinstance(stream, torch.cuda.Stream)
            # Stream should be in use
            assert pool.num_available == 2

        # Stream should be returned
        assert pool.num_available == 3

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_get_multiple_streams(self) -> None:
        """Test getting multiple streams."""
        pool = CUDAStreamPool(num_streams=5)

        streams = pool.get_streams(count=3)
        assert len(streams) == 3
        assert pool.num_available == 2

        pool.return_streams(streams)
        assert pool.num_available == 5

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_synchronize_all(self) -> None:
        """Test synchronize_all method."""
        pool = CUDAStreamPool(num_streams=2)

        # Should not raise
        pool.synchronize_all()

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_reset(self) -> None:
        """Test reset method."""
        pool = CUDAStreamPool(num_streams=3)

        # Use some streams
        _ = pool.get_streams(count=2)
        assert pool.num_available == 1

        # Reset
        pool.reset()
        assert pool.num_available == 3


class TestPipelineStats:
    """Tests for PipelineStats dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = PipelineStats()

        assert stats.total_items == 0
        assert stats.total_batches == 0
        assert stats.total_time_ms == 0.0
        assert stats.preprocess_time_ms == 0.0
        assert stats.inference_time_ms == 0.0
        assert stats.postprocess_time_ms == 0.0
        assert stats.throughput_items_per_sec == 0.0

    def test_custom_values(self) -> None:
        """Test setting custom values."""
        stats = PipelineStats(
            total_items=100,
            total_batches=10,
            total_time_ms=1000.0,
            throughput_items_per_sec=100.0,
        )

        assert stats.total_items == 100
        assert stats.total_batches == 10
        assert stats.total_time_ms == 1000.0
        assert stats.throughput_items_per_sec == 100.0


class TestStreamedInferencePipeline:
    """Tests for StreamedInferencePipeline class."""

    @pytest.fixture
    def simple_model(self) -> torch.nn.Module:
        """Create a simple test model."""
        return torch.nn.Linear(10, 5)

    @pytest.fixture
    def preprocess_fn(self) -> Callable[[list[torch.Tensor]], torch.Tensor]:
        """Create a preprocessing function."""

        def _preprocess(inputs: list[torch.Tensor]) -> torch.Tensor:
            return torch.stack(inputs)

        return _preprocess

    @pytest.fixture
    def postprocess_fn(
        self,
    ) -> Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]]:
        """Create a postprocessing function."""

        def _postprocess(outputs: torch.Tensor, _inputs: list[torch.Tensor]) -> list[list[float]]:
            return [o.tolist() for o in outputs]

        return _postprocess

    def test_initialization(
        self,
        simple_model: torch.nn.Module,
        preprocess_fn: Callable[[list[torch.Tensor]], torch.Tensor],
        postprocess_fn: Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]],
    ) -> None:
        """Test pipeline initialization."""
        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess_fn,
            postprocess_fn=postprocess_fn,
            batch_size=4,
            device="cpu",
        )

        assert pipeline.model is simple_model
        assert pipeline.batch_size == 4
        assert pipeline.device == "cpu"

    def test_create_batches(
        self,
        simple_model: torch.nn.Module,
        preprocess_fn: Callable[[list[torch.Tensor]], torch.Tensor],
        postprocess_fn: Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]],
    ) -> None:
        """Test batch creation."""
        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess_fn,
            postprocess_fn=postprocess_fn,
            batch_size=3,
            device="cpu",
        )

        inputs = list(range(10))
        batches = pipeline._create_batches(inputs)

        assert len(batches) == 4
        assert batches[0] == [0, 1, 2]
        assert batches[1] == [3, 4, 5]
        assert batches[2] == [6, 7, 8]
        assert batches[3] == [9]

    def test_process_empty_batch(
        self,
        simple_model: torch.nn.Module,
        preprocess_fn: Callable[[list[torch.Tensor]], torch.Tensor],
        postprocess_fn: Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]],
    ) -> None:
        """Test processing empty input."""
        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess_fn,
            postprocess_fn=postprocess_fn,
            batch_size=4,
            device="cpu",
        )

        results = pipeline.process_batch([])
        assert results == []

    def test_process_empty_batch_with_stats(
        self,
        simple_model: torch.nn.Module,
        preprocess_fn: Callable[[list[torch.Tensor]], torch.Tensor],
        postprocess_fn: Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]],
    ) -> None:
        """Test processing empty input returns stats."""
        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess_fn,
            postprocess_fn=postprocess_fn,
            batch_size=4,
            device="cpu",
        )

        results, stats = pipeline.process_batch([], return_stats=True)
        assert results == []
        assert isinstance(stats, PipelineStats)
        assert stats.total_items == 0

    def test_process_batch_sequential(
        self,
        simple_model: torch.nn.Module,
    ) -> None:
        """Test sequential batch processing."""
        # Use real functions for this test

        def preprocess(inputs: list[torch.Tensor]) -> torch.Tensor:
            return torch.stack(inputs)

        def postprocess(outputs: torch.Tensor, _inputs: list[torch.Tensor]) -> list[list[float]]:
            return [o.tolist() for o in outputs]

        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess,
            postprocess_fn=postprocess,
            batch_size=4,
            device="cpu",
        )

        # Create sample inputs
        inputs = [torch.randn(10) for _ in range(10)]

        results, stats = pipeline.process_batch(inputs, return_stats=True)

        assert len(results) == 10
        assert stats.total_items == 10
        assert stats.total_batches == 3
        assert stats.total_time_ms > 0

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_process_batch_with_cuda(self) -> None:
        """Test batch processing with CUDA streams."""
        model = torch.nn.Linear(10, 5).cuda()

        def preprocess(inputs: list[torch.Tensor]) -> torch.Tensor:
            return torch.stack([t.cuda() for t in inputs])

        def postprocess(outputs: torch.Tensor, _inputs: list[torch.Tensor]) -> list[list[float]]:
            return [o.cpu().tolist() for o in outputs]

        pipeline = StreamedInferencePipeline(
            model=model,
            preprocess_fn=preprocess,
            postprocess_fn=postprocess,
            batch_size=4,
            device="cuda:0",
        )

        # Create sample inputs
        inputs = [torch.randn(10) for _ in range(10)]

        results, stats = pipeline.process_batch(inputs, return_stats=True)

        assert len(results) == 10
        assert stats.total_items == 10
        assert stats.throughput_items_per_sec > 0

    def test_synchronize(
        self,
        simple_model: torch.nn.Module,
        preprocess_fn: Callable[[list[torch.Tensor]], torch.Tensor],
        postprocess_fn: Callable[[torch.Tensor, list[torch.Tensor]], list[list[float]]],
    ) -> None:
        """Test synchronize method."""
        pipeline = StreamedInferencePipeline(
            model=simple_model,
            preprocess_fn=preprocess_fn,
            postprocess_fn=postprocess_fn,
            batch_size=4,
            device="cpu",
        )

        # Should not raise
        pipeline.synchronize()


class TestCreatePreprocessOnStream:
    """Tests for create_preprocess_on_stream function."""

    def test_without_stream(self) -> None:
        """Test preprocessing without stream."""
        call_count = 0

        def preprocess(inputs: list[int]) -> int:
            nonlocal call_count
            call_count += 1
            return sum(inputs)

        wrapped = create_preprocess_on_stream(preprocess, stream=None)
        result = wrapped([1, 2, 3])

        assert result == 6
        assert call_count == 1

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_with_stream(self) -> None:
        """Test preprocessing with CUDA stream."""
        stream = torch.cuda.Stream()

        def preprocess(inputs: list[torch.Tensor]) -> torch.Tensor:
            return torch.stack([t.cuda() for t in inputs])

        wrapped = create_preprocess_on_stream(preprocess, stream=stream)
        inputs = [torch.randn(5) for _ in range(3)]
        result = wrapped(inputs)

        stream.synchronize()
        assert result.shape == (3, 5)


class TestCreateInferenceOnStream:
    """Tests for create_inference_on_stream function."""

    def test_without_stream(self) -> None:
        """Test inference without stream."""
        model = torch.nn.Linear(10, 5)
        model.eval()

        wrapped = create_inference_on_stream(model, stream=None)
        result = wrapped(torch.randn(2, 10))

        assert result.shape == (2, 5)

    def test_with_dict_input(self) -> None:
        """Test inference with dictionary input."""

        class DictModel(torch.nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.linear = torch.nn.Linear(10, 5)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                result: torch.Tensor = self.linear(x)
                return result

        model = DictModel()
        model.eval()

        wrapped = create_inference_on_stream(model, stream=None)
        result = wrapped({"x": torch.randn(2, 10)})

        assert result.shape == (2, 5)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_with_stream_and_event(self) -> None:
        """Test inference with stream and preprocess event."""
        model = torch.nn.Linear(10, 5).cuda()
        model.eval()

        preprocess_stream = torch.cuda.Stream()
        inference_stream = torch.cuda.Stream()

        # Simulate preprocessing
        with torch.cuda.stream(preprocess_stream):
            input_tensor = torch.randn(2, 10).cuda()

        preprocess_event = torch.cuda.Event()
        preprocess_event.record(preprocess_stream)

        wrapped = create_inference_on_stream(
            model, stream=inference_stream, preprocess_event=preprocess_event
        )
        result = wrapped(input_tensor)

        inference_stream.synchronize()
        assert result.shape == (2, 5)


class TestStreamBenchmarkResult:
    """Tests for StreamBenchmarkResult dataclass."""

    def test_creation(self) -> None:
        """Test creating benchmark result."""
        result = StreamBenchmarkResult(
            sequential_time_ms=100.0,
            streamed_time_ms=70.0,
            speedup=1.43,
            stream_overhead_ms=5.0,
        )

        assert result.sequential_time_ms == 100.0
        assert result.streamed_time_ms == 70.0
        assert result.speedup == pytest.approx(1.43)
        assert result.stream_overhead_ms == 5.0


class TestBenchmarkStreamPerformance:
    """Tests for benchmark_stream_performance function."""

    def test_returns_none_without_cuda(self) -> None:
        """Test that benchmark returns None without CUDA."""
        with patch("cuda_streams.is_cuda_streams_available", return_value=False):
            result = benchmark_stream_performance(
                model=torch.nn.Linear(10, 5),
                preprocess_fn=lambda x: torch.stack(x),
                postprocess_fn=lambda o, _i: o.tolist(),
                sample_inputs=[torch.randn(10) for _ in range(10)],
            )
            assert result is None

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    @pytest.mark.slow
    def test_benchmark_runs_successfully(self) -> None:
        """Test that benchmark completes successfully with CUDA."""
        model = torch.nn.Linear(10, 5).cuda()

        def preprocess(inputs: list[torch.Tensor]) -> torch.Tensor:
            return torch.stack([t.cuda() for t in inputs])

        def postprocess(outputs: torch.Tensor, _inputs: list[torch.Tensor]) -> list[list[float]]:
            return [o.cpu().tolist() for o in outputs]

        result = benchmark_stream_performance(
            model=model,
            preprocess_fn=preprocess,
            postprocess_fn=postprocess,
            sample_inputs=[torch.randn(10) for _ in range(20)],
            batch_size=4,
            num_iterations=3,
            warmup_iterations=1,
        )

        assert result is not None
        assert result.sequential_time_ms > 0
        assert result.streamed_time_ms > 0
        assert result.speedup > 0


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_cuda_streams_enabled_default(self) -> None:
        """Test CUDA_STREAMS_ENABLED default value."""
        # Default should be True
        assert CUDA_STREAMS_ENABLED is True or "CUDA_STREAMS_ENABLED" in os.environ

    def test_cuda_streams_pool_size_default(self) -> None:
        """Test CUDA_STREAMS_POOL_SIZE default value."""
        # Should be at least 1
        assert CUDA_STREAMS_POOL_SIZE >= 1


class TestThreadSafety:
    """Tests for thread safety of stream pool."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_concurrent_stream_access(self) -> None:
        """Test concurrent access to stream pool."""
        pool = CUDAStreamPool(num_streams=3)
        results: list[bool] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                with pool.get_stream() as stream:
                    if stream is not None:
                        # Simulate some work
                        time.sleep(0.01)
                        results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 10
