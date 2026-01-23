"""Unit tests for frame buffer integration into the detection pipeline.

Tests for NEM-3334: Pipeline Integration for Frame Buffering.

This module tests that:
1. DetectorClient buffers frames during detection processing
2. The frame buffer is accessible from the enrichment pipeline
3. Frames are properly buffered with camera_id and timestamp

The FrameBuffer service is used for X-CLIP temporal action recognition,
which requires sequences of frames (typically 8) to recognize actions.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDetectorClientFrameBufferIntegration:
    """Tests for DetectorClient frame buffer integration."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def mock_frame_buffer(self):
        """Create a mock FrameBuffer for testing."""
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer(buffer_size=16, max_age_seconds=30.0)
        return buffer

    @pytest.fixture(autouse=True)
    def mock_baseline_service(self):
        """Mock the baseline service to avoid database interactions."""
        mock_service = MagicMock()
        mock_service.update_baseline = AsyncMock()

        with patch(
            "backend.services.detector_client.get_baseline_service",
            return_value=mock_service,
        ):
            yield mock_service

    @pytest.mark.anyio
    async def test_detector_client_accepts_frame_buffer_parameter(self):
        """DetectorClient should accept a frame_buffer parameter."""
        from backend.services.detector_client import DetectorClient
        from backend.services.frame_buffer import FrameBuffer

        buffer = FrameBuffer()
        client = DetectorClient(frame_buffer=buffer)

        assert client._frame_buffer is buffer

    @pytest.mark.anyio
    async def test_detector_client_frame_buffer_defaults_to_none(self):
        """DetectorClient should have None frame_buffer by default."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient()

        assert client._frame_buffer is None

    @pytest.mark.anyio
    async def test_detect_objects_buffers_frame_when_buffer_provided(
        self, mock_session, mock_frame_buffer
    ):
        """detect_objects should buffer the frame when frame_buffer is provided."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        image_path = "/export/foscam/front_door/image_001.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data_for_buffering"

        sample_response = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": [100, 150, 300, 400],
                }
            ],
            "processing_time_ms": 125.5,
            "image_size": [1920, 1080],
        }

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(client, "_validate_image_for_detection_async", return_value=True),
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            await client.detect_objects(
                image_path=image_path,
                camera_id=camera_id,
                session=mock_session,
            )

        # Verify frame was buffered
        assert mock_frame_buffer.frame_count(camera_id) == 1

        # Verify we can retrieve the frame
        frames = mock_frame_buffer.get_sequence(camera_id, num_frames=1)
        assert frames is not None
        assert frames[0] == mock_image_data

    @pytest.mark.anyio
    async def test_detect_objects_does_not_buffer_when_no_buffer_provided(self, mock_session):
        """detect_objects should not fail when frame_buffer is not provided."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=None, max_retries=1)

        image_path = "/export/foscam/front_door/image_001.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        sample_response = {
            "detections": [
                {
                    "class": "person",
                    "confidence": 0.95,
                    "bbox": [100, 150, 300, 400],
                }
            ],
            "processing_time_ms": 125.5,
            "image_size": [1920, 1080],
        }

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(client, "_validate_image_for_detection_async", return_value=True),
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            # Should not raise
            detections = await client.detect_objects(
                image_path=image_path,
                camera_id=camera_id,
                session=mock_session,
            )

        # Detection should still work
        assert len(detections) == 1

    @pytest.mark.anyio
    async def test_detect_objects_buffers_frame_with_timestamp(
        self, mock_session, mock_frame_buffer
    ):
        """detect_objects should buffer frames with proper timestamps."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        image_path = "/export/foscam/front_door/image_001.jpg"
        camera_id = "front_door"
        mock_image_data = b"fake_image_data"

        sample_response = {
            "detections": [],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        before_time = datetime.now(UTC)

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_bytes", return_value=mock_image_data),
            patch("httpx.AsyncClient.post") as mock_post,
            patch.object(client, "_validate_image_for_detection_async", return_value=True),
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_response
            mock_post.return_value = mock_response

            await client.detect_objects(
                image_path=image_path,
                camera_id=camera_id,
                session=mock_session,
            )

        after_time = datetime.now(UTC)

        # Check timestamp is within reasonable range
        oldest_timestamp = mock_frame_buffer.get_oldest_timestamp(camera_id)
        assert oldest_timestamp is not None
        assert before_time <= oldest_timestamp <= after_time

    @pytest.mark.anyio
    async def test_detect_objects_does_not_buffer_on_file_not_found(
        self, mock_session, mock_frame_buffer
    ):
        """detect_objects should not buffer frame when file doesn't exist."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        image_path = "/export/foscam/front_door/nonexistent.jpg"
        camera_id = "front_door"

        with patch("pathlib.Path.exists", return_value=False):
            result = await client.detect_objects(
                image_path=image_path,
                camera_id=camera_id,
                session=mock_session,
            )

        # Should return empty list
        assert result == []

        # Should not buffer anything
        assert mock_frame_buffer.frame_count(camera_id) == 0

    @pytest.mark.anyio
    async def test_detect_objects_does_not_buffer_on_invalid_image(
        self, mock_session, mock_frame_buffer
    ):
        """detect_objects should not buffer frame when image validation fails."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        image_path = "/export/foscam/front_door/corrupted.jpg"
        camera_id = "front_door"

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch.object(client, "_validate_image_for_detection_async", return_value=False),
        ):
            result = await client.detect_objects(
                image_path=image_path,
                camera_id=camera_id,
                session=mock_session,
            )

        # Should return empty list
        assert result == []

        # Should not buffer anything
        assert mock_frame_buffer.frame_count(camera_id) == 0

    @pytest.mark.anyio
    async def test_multiple_detections_accumulate_in_buffer(self, mock_session, mock_frame_buffer):
        """Multiple detect_objects calls should accumulate frames in buffer."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        camera_id = "front_door"
        sample_response = {
            "detections": [],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        # Process 5 frames
        for i in range(5):
            image_path = f"/export/foscam/front_door/image_{i:03d}.jpg"
            mock_image_data = f"frame_data_{i}".encode()

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_bytes", return_value=mock_image_data),
                patch("httpx.AsyncClient.post") as mock_post,
                patch.object(client, "_validate_image_for_detection_async", return_value=True),
            ):
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = sample_response
                mock_post.return_value = mock_response

                await client.detect_objects(
                    image_path=image_path,
                    camera_id=camera_id,
                    session=mock_session,
                )

        # All 5 frames should be buffered
        assert mock_frame_buffer.frame_count(camera_id) == 5

    @pytest.mark.anyio
    async def test_different_cameras_buffered_separately(self, mock_session, mock_frame_buffer):
        """Frames from different cameras should be buffered separately."""
        from backend.services.detector_client import DetectorClient

        client = DetectorClient(frame_buffer=mock_frame_buffer, max_retries=1)

        sample_response = {
            "detections": [],
            "processing_time_ms": 50.0,
            "image_size": [1920, 1080],
        }

        cameras = ["front_door", "backyard", "garage"]

        for camera_id in cameras:
            for i in range(3):
                image_path = f"/export/foscam/{camera_id}/image_{i:03d}.jpg"
                mock_image_data = f"{camera_id}_frame_{i}".encode()

                with (
                    patch("pathlib.Path.exists", return_value=True),
                    patch("pathlib.Path.read_bytes", return_value=mock_image_data),
                    patch("httpx.AsyncClient.post") as mock_post,
                    patch.object(
                        client,
                        "_validate_image_for_detection_async",
                        return_value=True,
                    ),
                ):
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = sample_response
                    mock_post.return_value = mock_response

                    await client.detect_objects(
                        image_path=image_path,
                        camera_id=camera_id,
                        session=mock_session,
                    )

        # Each camera should have 3 frames
        for camera_id in cameras:
            assert mock_frame_buffer.frame_count(camera_id) == 3

        # Total of 3 cameras
        assert mock_frame_buffer.camera_count == 3


class TestEnrichmentPipelineFrameBufferAccess:
    """Tests for enrichment pipeline access to frame buffer."""

    @pytest.mark.anyio
    async def test_enrichment_pipeline_can_access_buffered_frames(self):
        """EnrichmentPipeline should be able to access frames buffered by DetectorClient."""
        from backend.services.enrichment_pipeline import EnrichmentPipeline
        from backend.services.frame_buffer import FrameBuffer

        # Create shared buffer
        buffer = FrameBuffer(buffer_size=16, max_age_seconds=30.0)

        # Simulate frames being added by detector (as would happen in real pipeline)
        camera_id = "front_door"
        now = datetime.now(UTC)
        for i in range(8):
            await buffer.add_frame(
                camera_id,
                f"frame_{i}".encode(),
                now,
            )

        # Create enrichment pipeline with the same buffer
        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(frame_buffer=buffer)

        # Pipeline should be able to get frame sequence
        assert pipeline._frame_buffer is not None
        assert pipeline._frame_buffer.has_enough_frames(camera_id, min_frames=8)

        frames = pipeline._frame_buffer.get_sequence(camera_id, num_frames=8)
        assert frames is not None
        assert len(frames) == 8


class TestFrameBufferSingletonIntegration:
    """Tests for singleton frame buffer integration."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset frame buffer singleton before and after each test."""
        from backend.services.frame_buffer import reset_frame_buffer

        reset_frame_buffer()
        yield
        reset_frame_buffer()

    def test_get_frame_buffer_returns_singleton(self):
        """get_frame_buffer should return a singleton instance."""
        from backend.services.frame_buffer import get_frame_buffer

        buffer1 = get_frame_buffer()
        buffer2 = get_frame_buffer()

        assert buffer1 is buffer2

    @pytest.mark.anyio
    async def test_detector_and_enrichment_can_share_singleton_buffer(self):
        """DetectorClient and EnrichmentPipeline should be able to share the singleton buffer."""
        from backend.services.detector_client import DetectorClient
        from backend.services.enrichment_pipeline import EnrichmentPipeline
        from backend.services.frame_buffer import get_frame_buffer

        # Get singleton buffer
        shared_buffer = get_frame_buffer()

        # Create detector with shared buffer
        detector = DetectorClient(frame_buffer=shared_buffer)

        # Create enrichment pipeline with same buffer
        with (
            patch("backend.services.enrichment_pipeline.get_model_manager"),
            patch("backend.services.enrichment_pipeline.get_vision_extractor"),
            patch("backend.services.enrichment_pipeline.get_reid_service"),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector"),
        ):
            pipeline = EnrichmentPipeline(frame_buffer=shared_buffer)

        # Both should reference the same buffer
        assert detector._frame_buffer is shared_buffer
        assert pipeline._frame_buffer is shared_buffer

        # Verify they can see each other's data
        camera_id = "test_camera"
        now = datetime.now(UTC)

        # Simulate detector buffering a frame
        await shared_buffer.add_frame(camera_id, b"test_frame", now)

        # Pipeline should see the frame
        assert pipeline._frame_buffer.frame_count(camera_id) == 1


class TestDetectionQueueWorkerFrameBufferIntegration:
    """Tests for DetectionQueueWorker frame buffer integration."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset frame buffer singleton before and after each test."""
        from backend.services.frame_buffer import reset_frame_buffer

        reset_frame_buffer()
        yield
        reset_frame_buffer()

    def test_detection_queue_worker_accepts_frame_buffer(self):
        """DetectionQueueWorker should accept a frame_buffer parameter."""
        from backend.services.frame_buffer import FrameBuffer
        from backend.services.pipeline_workers import DetectionQueueWorker

        buffer = FrameBuffer()
        mock_redis = MagicMock()

        worker = DetectionQueueWorker(
            redis_client=mock_redis,
            frame_buffer=buffer,
        )

        assert worker._frame_buffer is buffer

    def test_detection_queue_worker_uses_singleton_when_no_buffer_provided(self):
        """DetectionQueueWorker should use singleton when frame_buffer not provided."""
        from backend.services.frame_buffer import get_frame_buffer
        from backend.services.pipeline_workers import DetectionQueueWorker

        mock_redis = MagicMock()

        worker = DetectionQueueWorker(redis_client=mock_redis)

        # Should use the singleton
        singleton = get_frame_buffer()
        assert worker._frame_buffer is singleton

    def test_detection_queue_worker_passes_buffer_to_detector_client(self):
        """DetectionQueueWorker should pass frame_buffer to DetectorClient."""
        from backend.services.frame_buffer import FrameBuffer
        from backend.services.pipeline_workers import DetectionQueueWorker

        buffer = FrameBuffer()
        mock_redis = MagicMock()

        # Don't provide detector_client - let worker create one
        worker = DetectionQueueWorker(
            redis_client=mock_redis,
            frame_buffer=buffer,
        )

        # The internally created detector should have the frame_buffer
        assert worker._detector._frame_buffer is buffer


class TestPipelineWorkerManagerFrameBufferIntegration:
    """Tests for PipelineWorkerManager frame buffer integration."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset frame buffer singleton before and after each test."""
        from backend.services.frame_buffer import reset_frame_buffer

        reset_frame_buffer()
        yield
        reset_frame_buffer()

    def test_pipeline_worker_manager_accepts_frame_buffer(self):
        """PipelineWorkerManager should accept a frame_buffer parameter."""
        from backend.services.frame_buffer import FrameBuffer
        from backend.services.pipeline_workers import PipelineWorkerManager

        buffer = FrameBuffer()
        mock_redis = MagicMock()

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            frame_buffer=buffer,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        assert manager._frame_buffer is buffer

    def test_pipeline_worker_manager_passes_buffer_to_detection_worker(self):
        """PipelineWorkerManager should pass frame_buffer to DetectionQueueWorker."""
        from backend.services.frame_buffer import FrameBuffer
        from backend.services.pipeline_workers import PipelineWorkerManager

        buffer = FrameBuffer()
        mock_redis = MagicMock()

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            frame_buffer=buffer,
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        # Detection worker should have the frame_buffer
        assert manager._detection_worker is not None
        assert manager._detection_worker._frame_buffer is buffer

    def test_pipeline_worker_manager_detection_worker_uses_singleton_by_default(self):
        """DetectionQueueWorker should use singleton when PipelineWorkerManager doesn't provide buffer."""
        from backend.services.frame_buffer import get_frame_buffer
        from backend.services.pipeline_workers import PipelineWorkerManager

        mock_redis = MagicMock()

        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            # No frame_buffer provided
            enable_analysis_worker=False,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )

        # Detection worker should use the singleton
        singleton = get_frame_buffer()
        assert manager._detection_worker is not None
        assert manager._detection_worker._frame_buffer is singleton
