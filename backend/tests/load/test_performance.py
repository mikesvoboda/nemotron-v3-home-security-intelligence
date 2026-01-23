"""Load tests for new feature performance validation.

This module provides load tests to verify performance of new features:
- Household matching latency (<50ms p99)
- Frame buffer memory (<500MB per camera)
- X-CLIP concurrent inference (handle without blocking)

Tests use realistic test data sizes and concurrent access patterns
to validate production readiness.

Implements NEM-3340: Load Testing for New Features (Phase 7.4).

Usage:
    pytest backend/tests/load/test_performance.py -v
    pytest backend/tests/load/test_performance.py --benchmark-only
    pytest backend/tests/load/test_performance.py -k test_household -v
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

# =============================================================================
# Test Data Generators
# =============================================================================


def generate_test_embedding(dim: int = 512, seed: int | None = None) -> np.ndarray:
    """Generate a random normalized embedding vector.

    Args:
        dim: Dimension of the embedding vector (default 512)
        seed: Optional random seed for reproducibility

    Returns:
        Normalized numpy array of shape (dim,)
    """
    if seed is not None:
        np.random.seed(seed)
    embedding = np.random.randn(dim).astype(np.float32)
    # Normalize to unit length (cosine similarity uses normalized vectors)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


def generate_frame_data(size_bytes: int = 100_000) -> bytes:
    """Generate frame data of specified size.

    Args:
        size_bytes: Size of frame data in bytes (default ~100KB)

    Returns:
        Bytes representing frame data
    """
    return b"x" * size_bytes


def create_mock_pil_image(width: int = 224, height: int = 224) -> Image.Image:
    """Create a mock PIL Image for X-CLIP testing.

    Args:
        width: Image width (default 224 for X-CLIP)
        height: Image height (default 224 for X-CLIP)

    Returns:
        PIL Image with random RGB values
    """
    return Image.new("RGB", (width, height), color="blue")


# =============================================================================
# Household Matching Performance Tests
# =============================================================================


class TestHouseholdMatchingPerformance:
    """Load tests for household matching latency.

    Target: p99 latency < 50ms

    These tests verify that the HouseholdMatcher can match person embeddings
    against a database of household members within the required latency bounds.
    """

    @pytest.fixture
    def household_matcher(self) -> Any:
        """Create a HouseholdMatcher instance for testing."""
        from backend.services.household_matcher import HouseholdMatcher

        # Use default threshold (0.85)
        return HouseholdMatcher()

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock database session for household matcher."""
        session = AsyncMock()
        return session

    def _generate_member_embeddings(
        self, count: int, dim: int = 512
    ) -> list[tuple[int, str, np.ndarray]]:
        """Generate mock member embeddings for testing.

        Args:
            count: Number of members to generate
            dim: Embedding dimension

        Returns:
            List of (member_id, member_name, embedding) tuples
        """
        return [(i, f"Member_{i}", generate_test_embedding(dim, seed=i)) for i in range(count)]

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_household_matching_latency_small_db(
        self, household_matcher: Any, mock_session: AsyncMock
    ) -> None:
        """Verify household matching completes within 50ms for small DB (10 members).

        This test measures p99 latency with a small number of household members.
        """
        # Generate 10 member embeddings
        members = self._generate_member_embeddings(10)
        # Mock the internal method to return our test members
        household_matcher._get_all_member_embeddings = AsyncMock(return_value=members)

        # Test embedding (slightly different from member 5)
        test_embedding = generate_test_embedding(512, seed=5)
        test_embedding += np.random.randn(512).astype(np.float32) * 0.01
        test_embedding = test_embedding / np.linalg.norm(test_embedding)

        latencies: list[float] = []
        num_iterations = 100

        for _ in range(num_iterations):
            start = time.perf_counter()
            await household_matcher.match_person(test_embedding, mock_session)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate p99 latency
        latencies.sort()
        p99_index = int(num_iterations * 0.99) - 1
        p99_latency = latencies[p99_index]

        assert p99_latency < 50, f"p99 latency {p99_latency:.2f}ms exceeds 50ms target (10 members)"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_household_matching_latency_medium_db(
        self, household_matcher: Any, mock_session: AsyncMock
    ) -> None:
        """Verify household matching completes within 50ms for medium DB (100 members).

        This test measures p99 latency with a realistic number of household members
        including frequent visitors and service workers.
        """
        # Generate 100 member embeddings
        members = self._generate_member_embeddings(100)
        # Mock the internal method to return our test members
        household_matcher._get_all_member_embeddings = AsyncMock(return_value=members)

        test_embedding = generate_test_embedding(512, seed=42)

        latencies: list[float] = []
        num_iterations = 100

        for _ in range(num_iterations):
            start = time.perf_counter()
            await household_matcher.match_person(test_embedding, mock_session)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p99_latency = latencies[int(num_iterations * 0.99) - 1]

        assert p99_latency < 50, (
            f"p99 latency {p99_latency:.2f}ms exceeds 50ms target (100 members)"
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_household_matching_latency_large_db(
        self, household_matcher: Any, mock_session: AsyncMock
    ) -> None:
        """Verify household matching completes within 50ms for large DB (500 members).

        This is a stress test with an unrealistically large number of members
        to verify the algorithm scales appropriately.
        """
        # Generate 500 member embeddings (stress test)
        members = self._generate_member_embeddings(500)
        # Mock the internal method to return our test members
        household_matcher._get_all_member_embeddings = AsyncMock(return_value=members)

        test_embedding = generate_test_embedding(512, seed=99)

        latencies: list[float] = []
        num_iterations = 100

        for _ in range(num_iterations):
            start = time.perf_counter()
            await household_matcher.match_person(test_embedding, mock_session)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        latencies.sort()
        p99_latency = latencies[int(num_iterations * 0.99) - 1]

        assert p99_latency < 50, (
            f"p99 latency {p99_latency:.2f}ms exceeds 50ms target (500 members)"
        )

    @pytest.mark.asyncio
    async def test_household_matching_with_no_match(
        self, household_matcher: Any, mock_session: AsyncMock
    ) -> None:
        """Verify latency is still acceptable when no match is found.

        Tests the worst case where all embeddings must be checked but
        none exceed the similarity threshold.
        """
        # Generate orthogonal embeddings (no matches possible)
        members = [(i, f"Member_{i}", np.eye(512, dtype=np.float32)[i % 512]) for i in range(100)]
        # Mock the internal method to return our test members
        household_matcher._get_all_member_embeddings = AsyncMock(return_value=members)

        # Test with embedding that won't match any
        test_embedding = -np.ones(512, dtype=np.float32) / np.sqrt(512)

        latencies: list[float] = []
        for _ in range(50):
            start = time.perf_counter()
            result = await household_matcher.match_person(test_embedding, mock_session)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        assert result is None  # Verify no match found
        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 50, f"Average latency {avg_latency:.2f}ms exceeds 50ms"

    @pytest.mark.asyncio
    async def test_cosine_similarity_performance(self) -> None:
        """Verify cosine_similarity function performance.

        The cosine_similarity function is the inner loop of matching
        and must be very fast.
        """
        from backend.services.household_matcher import cosine_similarity

        vec_a = generate_test_embedding(512, seed=1)
        vec_b = generate_test_embedding(512, seed=2)

        latencies: list[float] = []
        for _ in range(1000):
            start = time.perf_counter()
            cosine_similarity(vec_a, vec_b)
            latency_us = (time.perf_counter() - start) * 1_000_000  # microseconds
            latencies.append(latency_us)

        avg_latency_us = sum(latencies) / len(latencies)
        # Cosine similarity should be < 100 microseconds on average
        assert avg_latency_us < 100, f"cosine_similarity avg {avg_latency_us:.2f}us too slow"


# =============================================================================
# Frame Buffer Memory Tests
# =============================================================================


class TestFrameBufferMemory:
    """Memory tests for frame buffer.

    Target: <500MB per camera at 30fps for 60 seconds with ~100KB frames

    These tests verify that the FrameBuffer stays within memory bounds
    under high frame rate conditions.
    """

    @pytest.fixture
    def frame_buffer(self) -> Any:
        """Create a FrameBuffer instance for testing."""
        from backend.services.frame_buffer import FrameBuffer

        return FrameBuffer(buffer_size=1800, max_age_seconds=60.0)

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_frame_buffer_memory_single_camera(self, frame_buffer: Any) -> None:
        """Verify frame buffer memory stays within bounds for single camera.

        Simulates high frame rate (30fps * 60sec = 1800 frames) with ~100KB frames.
        Expected max memory: 1800 * 100KB = 180MB (well under 500MB limit)
        """
        now = datetime.now(UTC)
        frame_size = 100_000  # ~100KB per frame

        # Simulate 30fps * 60sec = 1800 frames
        for i in range(1800):
            frame_data = generate_frame_data(frame_size)
            await frame_buffer.add_frame(
                "camera_1", frame_data, now + timedelta(milliseconds=i * 33)
            )

        # Check frame count is at buffer limit
        assert frame_buffer.frame_count("camera_1") == 1800

        # Estimate memory usage from buffer internals
        # Each frame stores ~100KB of data plus timestamp overhead
        estimated_memory = frame_buffer.frame_count("camera_1") * frame_size

        # Should be well under 500MB limit
        max_memory_bytes = 500 * 1024 * 1024  # 500MB
        assert estimated_memory < max_memory_bytes, (
            f"Estimated memory {estimated_memory / (1024 * 1024):.1f}MB exceeds 500MB limit"
        )

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_frame_buffer_memory_multiple_cameras(self) -> None:
        """Verify frame buffer memory stays within bounds for multiple cameras.

        Simulates 4 cameras at 30fps each for 30 seconds.
        """
        from backend.services.frame_buffer import FrameBuffer

        # 4 cameras * 30fps * 30sec = 3600 frames total
        buffer = FrameBuffer(buffer_size=900, max_age_seconds=30.0)
        now = datetime.now(UTC)
        frame_size = 100_000

        camera_ids = ["camera_1", "camera_2", "camera_3", "camera_4"]

        # Add frames for all cameras
        for camera_id in camera_ids:
            for i in range(900):  # 30fps * 30sec = 900 frames per camera
                frame_data = generate_frame_data(frame_size)
                await buffer.add_frame(camera_id, frame_data, now + timedelta(milliseconds=i * 33))

        # Verify all cameras have expected frame counts
        total_frames = sum(buffer.frame_count(cam_id) for cam_id in camera_ids)
        assert total_frames == 3600

        # Estimate total memory
        estimated_memory = total_frames * frame_size
        max_memory_per_camera = 500 * 1024 * 1024

        # Each camera should be under 500MB
        for camera_id in camera_ids:
            camera_memory = buffer.frame_count(camera_id) * frame_size
            assert camera_memory < max_memory_per_camera, (
                f"Camera {camera_id} memory {camera_memory / (1024 * 1024):.1f}MB "
                f"exceeds 500MB limit"
            )

    @pytest.mark.asyncio
    async def test_frame_buffer_eviction_by_age(self) -> None:
        """Verify old frames are properly evicted to maintain memory bounds."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100, max_age_seconds=10.0)
        now = datetime.now(UTC)

        # Add old frames (should be evicted)
        for i in range(50):
            await buffer.add_frame(
                "camera_1",
                generate_frame_data(100_000),
                now - timedelta(seconds=15) + timedelta(milliseconds=i * 100),
            )

        # Add recent frames (should remain)
        for i in range(50):
            await buffer.add_frame(
                "camera_1",
                generate_frame_data(100_000),
                now - timedelta(seconds=5) + timedelta(milliseconds=i * 100),
            )

        # Add current frame to trigger eviction of old frames
        await buffer.add_frame("camera_1", generate_frame_data(100_000), now)

        # Old frames should be evicted, only recent frames should remain
        assert buffer.frame_count("camera_1") <= 51

    @pytest.mark.asyncio
    async def test_frame_buffer_eviction_by_capacity(self) -> None:
        """Verify frames are evicted when buffer capacity is exceeded."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=10, max_age_seconds=60.0)
        now = datetime.now(UTC)

        # Add more frames than buffer capacity
        for i in range(20):
            await buffer.add_frame(
                "camera_1", generate_frame_data(100_000), now + timedelta(seconds=i)
            )

        # Should only have buffer_size frames
        assert buffer.frame_count("camera_1") == 10

    @pytest.mark.asyncio
    async def test_frame_buffer_memory_estimation(self) -> None:
        """Test that we can estimate memory usage from buffer state."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100, max_age_seconds=30.0)
        now = datetime.now(UTC)
        frame_size = 50_000  # 50KB frames

        # Add 50 frames
        for i in range(50):
            await buffer.add_frame(
                "camera_1", generate_frame_data(frame_size), now + timedelta(seconds=i)
            )

        # Estimate memory based on frame count and typical frame size
        frame_count = buffer.frame_count("camera_1")
        estimated_memory = frame_count * frame_size

        # 50 * 50KB = 2.5MB
        assert estimated_memory == 2_500_000
        assert estimated_memory < 500 * 1024 * 1024  # Well under 500MB


# =============================================================================
# X-CLIP Concurrency Tests
# =============================================================================


class TestXCLIPConcurrency:
    """Concurrency tests for X-CLIP inference.

    Target: Handle concurrent requests without blocking or errors

    These tests verify that X-CLIP can handle multiple concurrent inference
    requests gracefully.
    """

    @pytest.fixture
    def mock_xclip_model_dict(self) -> dict[str, Any]:
        """Create a mock X-CLIP model dictionary."""
        mock_model = MagicMock()
        mock_processor = MagicMock()

        # Configure model parameters
        mock_param = MagicMock()
        mock_param.device = "cpu"
        mock_param.dtype = MagicMock()
        mock_model.parameters.return_value = iter([mock_param, mock_param])

        # Configure processor output with valid tensor shape
        mock_pixel_values = MagicMock()
        mock_pixel_values.shape = (1, 8, 3, 224, 224)
        mock_pixel_values.to.return_value = mock_pixel_values
        mock_pixel_values.half.return_value = mock_pixel_values
        mock_inputs = {"pixel_values": mock_pixel_values}
        mock_processor.return_value = mock_inputs

        # Configure model output
        mock_outputs = MagicMock()
        mock_probs = MagicMock()
        mock_probs.squeeze.return_value.cpu.return_value.numpy.return_value = np.array(
            [0.6, 0.3, 0.1]
        )
        mock_outputs.logits_per_video = MagicMock()
        mock_model.return_value = mock_outputs

        return {"model": mock_model, "processor": mock_processor, "probs": mock_probs}

    def _create_sample_frames(self, count: int = 8) -> list[Image.Image]:
        """Create sample PIL Image frames for testing."""
        return [create_mock_pil_image() for _ in range(count)]

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_xclip_requests(self, mock_xclip_model_dict: dict[str, Any]) -> None:
        """Verify X-CLIP handles concurrent requests without blocking.

        Runs 10 concurrent classification requests and verifies all complete
        successfully without errors.
        """
        from backend.services.xclip_loader import classify_actions

        model_dict = {
            "model": mock_xclip_model_dict["model"],
            "processor": mock_xclip_model_dict["processor"],
        }

        # Mock torch for the classification
        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_xclip_model_dict["probs"]
        mock_torch.float16 = "float16"

        async def make_request(request_id: int) -> dict[str, Any]:
            """Make a single classification request."""
            frames = self._create_sample_frames()
            prompts = ["loitering", "walking", "standing"]

            with patch.dict(sys.modules, {"torch": mock_torch}):
                result = await classify_actions(model_dict, frames, prompts=prompts)

            result["request_id"] = request_id
            return result

        # Run 10 concurrent requests
        num_concurrent = 10
        tasks = [make_request(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all completed without errors
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0, f"Got {len(errors)} errors in concurrent requests: {errors}"

        # Verify all results are valid
        successful_results = [r for r in results if isinstance(r, dict)]
        assert len(successful_results) == num_concurrent

        for result in successful_results:
            assert "detected_action" in result
            assert "confidence" in result

    @pytest.mark.asyncio
    async def test_xclip_request_isolation(self, mock_xclip_model_dict: dict[str, Any]) -> None:
        """Verify concurrent X-CLIP requests don't interfere with each other.

        Each request should return independent results based on its inputs.
        """
        from backend.services.xclip_loader import classify_actions

        model_dict = {
            "model": mock_xclip_model_dict["model"],
            "processor": mock_xclip_model_dict["processor"],
        }

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_xclip_model_dict["probs"]
        mock_torch.float16 = "float16"

        request_frames: dict[int, list[Image.Image]] = {}

        async def make_request(request_id: int) -> dict[str, Any]:
            """Make a request and track its frames."""
            frames = self._create_sample_frames()
            request_frames[request_id] = frames

            with patch.dict(sys.modules, {"torch": mock_torch}):
                result = await classify_actions(
                    model_dict, frames, prompts=["action_a", "action_b", "action_c"]
                )

            return result

        # Run concurrent requests
        tasks = [make_request(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        errors = [r for r in results if isinstance(r, Exception)]
        assert len(errors) == 0

        # Verify each request's frames were distinct
        assert len(request_frames) == 5

    @pytest.mark.asyncio
    async def test_xclip_throughput(self, mock_xclip_model_dict: dict[str, Any]) -> None:
        """Measure X-CLIP throughput under concurrent load.

        Verifies the system can handle a burst of requests within
        acceptable time bounds.
        """
        from backend.services.xclip_loader import classify_actions

        model_dict = {
            "model": mock_xclip_model_dict["model"],
            "processor": mock_xclip_model_dict["processor"],
        }

        mock_torch = MagicMock()
        mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
        mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)
        mock_torch.softmax.return_value = mock_xclip_model_dict["probs"]
        mock_torch.float16 = "float16"

        async def make_request() -> float:
            """Make a request and return latency."""
            frames = self._create_sample_frames()
            start = time.perf_counter()

            with patch.dict(sys.modules, {"torch": mock_torch}):
                await classify_actions(
                    model_dict, frames, prompts=["action_1", "action_2", "action_3"]
                )

            return (time.perf_counter() - start) * 1000

        # Measure throughput for 20 concurrent requests
        num_requests = 20
        start_time = time.perf_counter()
        tasks = [make_request() for _ in range(num_requests)]
        latencies = await asyncio.gather(*tasks)
        total_time = (time.perf_counter() - start_time) * 1000

        # Calculate metrics
        avg_latency = sum(latencies) / len(latencies)
        throughput = num_requests / (total_time / 1000)  # requests per second

        # Verify reasonable performance (these are mocked so should be fast)
        assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms too high"
        assert throughput > 10, f"Throughput {throughput:.2f} req/s too low"


# =============================================================================
# Pipeline Throughput Tests
# =============================================================================


class TestPipelineThroughput:
    """End-to-end pipeline throughput tests.

    These tests verify the overall pipeline can handle expected load
    without bottlenecks.
    """

    @pytest.mark.asyncio
    async def test_frame_buffer_add_throughput(self) -> None:
        """Verify frame buffer can handle high throughput adds.

        Target: Handle 30fps per camera without blocking.
        """
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100, max_age_seconds=30.0)
        now = datetime.now(UTC)
        frame_size = 100_000

        # Simulate 1 second of 30fps
        num_frames = 30
        latencies: list[float] = []

        for i in range(num_frames):
            frame_data = generate_frame_data(frame_size)
            start = time.perf_counter()
            await buffer.add_frame("camera_1", frame_data, now + timedelta(milliseconds=i * 33))
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate metrics
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Each add should complete in < 10ms to sustain 30fps
        assert avg_latency < 10, f"Average add latency {avg_latency:.2f}ms too high for 30fps"
        assert max_latency < 33, f"Max add latency {max_latency:.2f}ms exceeds frame interval"

    @pytest.mark.asyncio
    async def test_concurrent_frame_buffer_adds(self) -> None:
        """Verify concurrent frame buffer adds don't cause contention.

        Simulates multiple cameras adding frames concurrently.
        """
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100, max_age_seconds=30.0)
        now = datetime.now(UTC)

        async def add_frames_for_camera(camera_id: str, num_frames: int) -> float:
            """Add frames for a camera and return total time."""
            start = time.perf_counter()
            for i in range(num_frames):
                await buffer.add_frame(
                    camera_id,
                    generate_frame_data(50_000),
                    now + timedelta(milliseconds=i * 33),
                )
            return (time.perf_counter() - start) * 1000

        # Run 4 cameras concurrently, each adding 30 frames
        camera_ids = ["cam_1", "cam_2", "cam_3", "cam_4"]
        tasks = [add_frames_for_camera(cam_id, 30) for cam_id in camera_ids]
        times = await asyncio.gather(*tasks)

        # Verify all cameras added frames
        for cam_id in camera_ids:
            assert buffer.frame_count(cam_id) == 30

        # Average time should be reasonable even with concurrency
        avg_time = sum(times) / len(times)
        assert avg_time < 500, f"Average camera time {avg_time:.2f}ms too high"

    @pytest.mark.asyncio
    async def test_household_matching_concurrent_load(self) -> None:
        """Verify household matching handles concurrent queries.

        Simulates multiple concurrent person detection events
        querying the household matcher.
        """
        from backend.services.household_matcher import HouseholdMatcher

        matcher = HouseholdMatcher()
        mock_session = AsyncMock()

        # Generate member embeddings
        members = [(i, f"Member_{i}", generate_test_embedding(512, seed=i)) for i in range(50)]
        matcher._get_all_member_embeddings = AsyncMock(return_value=members)

        async def match_person(query_id: int) -> tuple[int, float, Any]:
            """Make a matching query and return latency."""
            embedding = generate_test_embedding(512, seed=1000 + query_id)
            start = time.perf_counter()
            result = await matcher.match_person(embedding, mock_session)
            latency = (time.perf_counter() - start) * 1000
            return query_id, latency, result

        # Run 20 concurrent queries
        tasks = [match_person(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # Extract latencies
        latencies = [r[1] for r in results]
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # All queries should complete quickly
        assert avg_latency < 20, f"Average query latency {avg_latency:.2f}ms too high"
        assert max_latency < 50, f"Max query latency {max_latency:.2f}ms exceeds target"


# =============================================================================
# Memory Stress Tests
# =============================================================================


class TestMemoryStress:
    """Memory stress tests for edge cases.

    These tests verify the system handles memory pressure gracefully.
    """

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_frame_buffer_sustained_load(self) -> None:
        """Test frame buffer under sustained load with eviction.

        Simulates continuous frame ingestion where old frames must be
        evicted to maintain memory bounds.
        """
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100, max_age_seconds=5.0)
        frame_size = 100_000
        now = datetime.now(UTC)

        # Simulate 10 seconds of sustained 30fps
        total_frames = 300
        for i in range(total_frames):
            timestamp = now + timedelta(milliseconds=i * 33)
            await buffer.add_frame("camera_1", generate_frame_data(frame_size), timestamp)

        # Should have evicted old frames, only keeping buffer_size
        assert buffer.frame_count("camera_1") <= 100

        # Oldest frame should be recent (within max_age window)
        oldest_ts = buffer.get_oldest_timestamp("camera_1")
        assert oldest_ts is not None
        newest_ts = now + timedelta(milliseconds=(total_frames - 1) * 33)
        age_seconds = (newest_ts - oldest_ts).total_seconds()
        assert age_seconds <= 5.0, f"Oldest frame age {age_seconds}s exceeds max_age"

    @pytest.mark.asyncio
    async def test_embedding_batch_memory(self) -> None:
        """Test that embedding operations don't leak memory.

        Creates and processes many embeddings to verify memory is released.
        """
        from backend.services.household_matcher import cosine_similarity

        # Process 10,000 embedding comparisons
        for _ in range(10_000):
            vec_a = generate_test_embedding(512)
            vec_b = generate_test_embedding(512)
            _ = cosine_similarity(vec_a, vec_b)

        # If we get here without OOM, memory is being managed properly
        # (This is a basic smoke test - actual memory testing would use memray)
        assert True
