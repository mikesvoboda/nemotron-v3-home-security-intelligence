"""Unit tests for frame buffer service.

Tests for the FrameBuffer service that stores recent frames per camera
for temporal action recognition with X-CLIP.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest


class TestFrameBuffer:
    """Tests for FrameBuffer initialization and basic operations."""

    def test_init_default_values(self) -> None:
        """FrameBuffer should initialize with default buffer_size=16 and max_age=30s."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        assert buffer.buffer_size == 16
        assert buffer.max_age_seconds == 30.0

    def test_init_custom_values(self) -> None:
        """FrameBuffer should accept custom buffer_size and max_age_seconds."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=32, max_age_seconds=60.0)
        assert buffer.buffer_size == 32
        assert buffer.max_age_seconds == 60.0

    def test_init_creates_empty_buffers(self) -> None:
        """FrameBuffer should start with no buffers."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        assert buffer.camera_count == 0


class TestFrameBufferAddFrame:
    """Tests for adding frames to the buffer."""

    @pytest.mark.anyio
    async def test_add_frame_creates_buffer_for_new_camera(self) -> None:
        """Adding a frame for a new camera should create a buffer."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        frame_data = b"test_frame_data"
        timestamp = datetime.now(UTC)

        await buffer.add_frame("camera_1", frame_data, timestamp)

        assert buffer.camera_count == 1
        assert buffer.frame_count("camera_1") == 1

    @pytest.mark.anyio
    async def test_add_multiple_frames_same_camera(self) -> None:
        """Adding multiple frames to the same camera should accumulate."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_1", b"frame_2", now + timedelta(seconds=1))
        await buffer.add_frame("camera_1", b"frame_3", now + timedelta(seconds=2))

        assert buffer.frame_count("camera_1") == 3

    @pytest.mark.anyio
    async def test_add_frames_multiple_cameras(self) -> None:
        """Adding frames for different cameras should create separate buffers."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_2", b"frame_2", now)
        await buffer.add_frame("camera_3", b"frame_3", now)

        assert buffer.camera_count == 3
        assert buffer.frame_count("camera_1") == 1
        assert buffer.frame_count("camera_2") == 1
        assert buffer.frame_count("camera_3") == 1

    @pytest.mark.anyio
    async def test_add_frame_respects_buffer_size_limit(self) -> None:
        """Buffer should not exceed buffer_size (oldest frames evicted)."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=4)
        now = datetime.now(UTC)

        # Add 6 frames (more than buffer_size)
        for i in range(6):
            await buffer.add_frame("camera_1", f"frame_{i}".encode(), now + timedelta(seconds=i))

        # Should only keep 4 most recent
        assert buffer.frame_count("camera_1") == 4

    @pytest.mark.anyio
    async def test_add_frame_evicts_old_frames_by_age(self) -> None:
        """Buffer should evict frames older than max_age_seconds."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=16, max_age_seconds=10.0)
        now = datetime.now(UTC)

        # Add old frames (15 seconds ago - should be evicted)
        await buffer.add_frame("camera_1", b"old_frame_1", now - timedelta(seconds=15))
        await buffer.add_frame("camera_1", b"old_frame_2", now - timedelta(seconds=12))

        # Add recent frames (should remain)
        await buffer.add_frame("camera_1", b"recent_frame_1", now - timedelta(seconds=5))
        await buffer.add_frame("camera_1", b"recent_frame_2", now)

        # Only the 2 recent frames should remain after adding a new frame that triggers eviction
        # The eviction happens when we add a new frame
        assert buffer.frame_count("camera_1") == 2


class TestFrameBufferGetSequence:
    """Tests for retrieving frame sequences."""

    @pytest.mark.anyio
    async def test_get_sequence_returns_none_when_not_enough_frames(self) -> None:
        """get_sequence should return None if buffer has fewer frames than requested."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_1", b"frame_2", now + timedelta(seconds=1))

        # Request 8 frames but only have 2
        result = buffer.get_sequence("camera_1", num_frames=8)
        assert result is None

    @pytest.mark.anyio
    async def test_get_sequence_returns_none_for_unknown_camera(self) -> None:
        """get_sequence should return None for cameras with no buffer."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        result = buffer.get_sequence("unknown_camera", num_frames=8)
        assert result is None

    @pytest.mark.anyio
    async def test_get_sequence_returns_exact_frames_when_count_matches(self) -> None:
        """get_sequence should return all frames when count matches exactly."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        # Add exactly 8 frames
        for i in range(8):
            await buffer.add_frame("camera_1", f"frame_{i}".encode(), now + timedelta(seconds=i))

        result = buffer.get_sequence("camera_1", num_frames=8)
        assert result is not None
        assert len(result) == 8
        # All frames should be included
        assert result[0] == b"frame_0"
        assert result[7] == b"frame_7"

    @pytest.mark.anyio
    async def test_get_sequence_samples_evenly_from_larger_buffer(self) -> None:
        """get_sequence should sample evenly when buffer has more frames than requested."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=16)
        now = datetime.now(UTC)

        # Add 16 frames
        for i in range(16):
            await buffer.add_frame("camera_1", f"frame_{i}".encode(), now + timedelta(seconds=i))

        # Request 8 frames from 16
        result = buffer.get_sequence("camera_1", num_frames=8)
        assert result is not None
        assert len(result) == 8

        # Should sample evenly: indices 0, 2, 4, 6, 8, 10, 12, 15 (approximately)
        # The first frame should be from the beginning
        assert result[0] == b"frame_0"
        # The last frame should be from the end
        assert result[7] == b"frame_15"

    @pytest.mark.anyio
    async def test_get_sequence_with_custom_num_frames(self) -> None:
        """get_sequence should work with different num_frames values."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=16)
        now = datetime.now(UTC)

        # Add 10 frames
        for i in range(10):
            await buffer.add_frame("camera_1", f"frame_{i}".encode(), now + timedelta(seconds=i))

        # Request 4 frames
        result = buffer.get_sequence("camera_1", num_frames=4)
        assert result is not None
        assert len(result) == 4


class TestFrameBufferClear:
    """Tests for clearing buffers."""

    @pytest.mark.anyio
    async def test_clear_specific_camera(self) -> None:
        """clear(camera_id) should only clear the specified camera's buffer."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_2", b"frame_2", now)

        buffer.clear("camera_1")

        assert buffer.frame_count("camera_1") == 0
        assert buffer.frame_count("camera_2") == 1
        assert buffer.camera_count == 1

    @pytest.mark.anyio
    async def test_clear_all_cameras(self) -> None:
        """clear() without arguments should clear all buffers."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_2", b"frame_2", now)
        await buffer.add_frame("camera_3", b"frame_3", now)

        buffer.clear()

        assert buffer.camera_count == 0

    def test_clear_nonexistent_camera_is_safe(self) -> None:
        """clear(camera_id) should not raise for nonexistent cameras."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        # Should not raise
        buffer.clear("nonexistent_camera")


class TestFrameBufferHelpers:
    """Tests for helper methods."""

    @pytest.mark.anyio
    async def test_frame_count_returns_zero_for_unknown_camera(self) -> None:
        """frame_count should return 0 for cameras with no buffer."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        assert buffer.frame_count("unknown") == 0

    @pytest.mark.anyio
    async def test_has_enough_frames_returns_false_when_insufficient(self) -> None:
        """has_enough_frames should return False when buffer is too small."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)

        assert buffer.has_enough_frames("camera_1", min_frames=8) is False

    @pytest.mark.anyio
    async def test_has_enough_frames_returns_true_when_sufficient(self) -> None:
        """has_enough_frames should return True when buffer has enough frames."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        for i in range(10):
            await buffer.add_frame("camera_1", f"frame_{i}".encode(), now + timedelta(seconds=i))

        assert buffer.has_enough_frames("camera_1", min_frames=8) is True

    @pytest.mark.anyio
    async def test_get_camera_ids_returns_all_cameras(self) -> None:
        """get_camera_ids should return list of all camera IDs with buffers."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_2", b"frame_2", now)

        camera_ids = buffer.get_camera_ids()
        assert set(camera_ids) == {"camera_1", "camera_2"}


class TestFrameData:
    """Tests for the FrameData dataclass."""

    def test_frame_data_stores_data_and_timestamp(self) -> None:
        """FrameData should store frame bytes and timestamp."""
        from backend.services.frame_buffer import FrameData

        now = datetime.now(UTC)
        frame = FrameData(frame=b"test_data", timestamp=now)

        assert frame.frame == b"test_data"
        assert frame.timestamp == now


class TestFrameBufferEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.anyio
    async def test_empty_frame_data_is_allowed(self) -> None:
        """Buffer should accept empty frame bytes."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"", now)
        assert buffer.frame_count("camera_1") == 1

    @pytest.mark.anyio
    async def test_frames_with_same_timestamp_are_all_kept(self) -> None:
        """Multiple frames with identical timestamps should all be stored."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_1", b"frame_2", now)
        await buffer.add_frame("camera_1", b"frame_3", now)

        assert buffer.frame_count("camera_1") == 3

    @pytest.mark.anyio
    async def test_buffer_size_one(self) -> None:
        """Buffer with size 1 should only keep the most recent frame."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=1)
        now = datetime.now(UTC)

        await buffer.add_frame("camera_1", b"frame_1", now)
        await buffer.add_frame("camera_1", b"frame_2", now + timedelta(seconds=1))

        assert buffer.frame_count("camera_1") == 1
        result = buffer.get_sequence("camera_1", num_frames=1)
        assert result == [b"frame_2"]

    @pytest.mark.anyio
    async def test_max_age_zero_evicts_all_old_frames(self) -> None:
        """With max_age=0, all frames older than current timestamp are evicted."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(max_age_seconds=0.0)
        now = datetime.now(UTC)

        # Add frame 1 second in the past
        await buffer.add_frame("camera_1", b"old_frame", now - timedelta(seconds=1))
        # Add current frame - this should evict the old one
        await buffer.add_frame("camera_1", b"current_frame", now)

        assert buffer.frame_count("camera_1") == 1
        result = buffer.get_sequence("camera_1", num_frames=1)
        assert result == [b"current_frame"]


class TestFrameBufferConcurrency:
    """Tests for concurrent access patterns."""

    @pytest.mark.anyio
    async def test_concurrent_add_frames_to_same_camera(self) -> None:
        """Buffer should handle concurrent adds to the same camera safely."""
        import asyncio

        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=100)
        now = datetime.now(UTC)

        async def add_frames(start: int) -> None:
            for i in range(10):
                await buffer.add_frame(
                    "camera_1",
                    f"frame_{start + i}".encode(),
                    now + timedelta(milliseconds=start + i),
                )

        # Add frames concurrently
        await asyncio.gather(
            add_frames(0),
            add_frames(10),
            add_frames(20),
        )

        # All 30 frames should be stored (within buffer_size)
        assert buffer.frame_count("camera_1") == 30

    @pytest.mark.anyio
    async def test_concurrent_add_frames_to_different_cameras(self) -> None:
        """Buffer should handle concurrent adds to different cameras safely."""
        import asyncio

        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        now = datetime.now(UTC)

        async def add_to_camera(camera_id: str) -> None:
            for i in range(5):
                await buffer.add_frame(camera_id, f"frame_{i}".encode(), now + timedelta(seconds=i))

        await asyncio.gather(
            add_to_camera("camera_1"),
            add_to_camera("camera_2"),
            add_to_camera("camera_3"),
        )

        assert buffer.camera_count == 3
        assert buffer.frame_count("camera_1") == 5
        assert buffer.frame_count("camera_2") == 5
        assert buffer.frame_count("camera_3") == 5


class TestFrameBufferSingleton:
    """Tests for the global singleton functions."""

    def test_get_frame_buffer_creates_singleton(self) -> None:
        """get_frame_buffer should create a singleton instance."""
        from backend.services.frame_buffer import get_frame_buffer, reset_frame_buffer

        reset_frame_buffer()  # Ensure clean state

        buffer1 = get_frame_buffer()
        buffer2 = get_frame_buffer()

        assert buffer1 is buffer2
        reset_frame_buffer()

    def test_get_frame_buffer_with_custom_params(self) -> None:
        """get_frame_buffer should accept custom parameters on first call."""
        from backend.services.frame_buffer import get_frame_buffer, reset_frame_buffer

        reset_frame_buffer()  # Ensure clean state

        buffer = get_frame_buffer(buffer_size=32, max_age_seconds=60.0)

        assert buffer.buffer_size == 32
        assert buffer.max_age_seconds == 60.0
        reset_frame_buffer()

    def test_reset_frame_buffer_clears_singleton(self) -> None:
        """reset_frame_buffer should clear the singleton so next get creates new instance."""
        from backend.services.frame_buffer import get_frame_buffer, reset_frame_buffer

        reset_frame_buffer()
        buffer1 = get_frame_buffer(buffer_size=16)

        reset_frame_buffer()
        buffer2 = get_frame_buffer(buffer_size=32)

        # After reset, should be a different instance with different params
        assert buffer1 is not buffer2
        assert buffer2.buffer_size == 32
        reset_frame_buffer()


class TestEnrichmentPipelineFrameBufferIntegration:
    """Tests for EnrichmentPipeline frame buffer integration."""

    def test_enrichment_pipeline_accepts_frame_buffer(self) -> None:
        """EnrichmentPipeline should accept a frame_buffer parameter."""
        from backend.services.enrichment_pipeline import EnrichmentPipeline
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()

        # Should not raise
        with patch("backend.services.enrichment_pipeline.get_model_manager"):
            with patch("backend.services.enrichment_pipeline.get_vision_extractor"):
                with patch("backend.services.enrichment_pipeline.get_reid_service"):
                    with patch("backend.services.enrichment_pipeline.get_scene_change_detector"):
                        pipeline = EnrichmentPipeline(frame_buffer=buffer)

        assert pipeline._frame_buffer is buffer

    def test_enrichment_pipeline_none_frame_buffer_is_default(self) -> None:
        """EnrichmentPipeline should have None frame_buffer by default."""
        from backend.services.enrichment_pipeline import EnrichmentPipeline

        with patch("backend.services.enrichment_pipeline.get_model_manager"):
            with patch("backend.services.enrichment_pipeline.get_vision_extractor"):
                with patch("backend.services.enrichment_pipeline.get_reid_service"):
                    with patch("backend.services.enrichment_pipeline.get_scene_change_detector"):
                        pipeline = EnrichmentPipeline()

        assert pipeline._frame_buffer is None
