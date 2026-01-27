"""Unit tests for video processing utilities with Supervision library.

Tests validate ByteTrack tracker integration, annotator configuration,
heatmap generation, and video processing utilities without requiring
actual video files or GPU.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

if TYPE_CHECKING:
    from numpy.typing import NDArray


# =============================================================================
# ByteTrackConfig Tests
# =============================================================================


class TestByteTrackConfig:
    """Tests for ByteTrack configuration dataclass."""

    def test_default_config_values(self) -> None:
        """ByteTrackConfig has sensible defaults for security tracking."""
        from ai.enrichment.utils.video_processing import ByteTrackConfig

        config = ByteTrackConfig()

        # Track buffer should allow for brief occlusions (30 frames ~ 1 second at 30fps)
        assert config.lost_track_buffer == 30
        # Track activation threshold should be moderate to avoid false positives
        assert 0.2 <= config.track_activation_threshold <= 0.5
        # Minimum matching threshold for IoU matching
        assert 0.7 <= config.minimum_matching_threshold <= 0.9
        # Minimum consecutive frames before confirming a track
        assert config.minimum_consecutive_frames >= 1

    def test_config_from_dict(self) -> None:
        """ByteTrackConfig can be created from dictionary."""
        from ai.enrichment.utils.video_processing import ByteTrackConfig

        config_dict = {
            "lost_track_buffer": 60,
            "track_activation_threshold": 0.3,
            "minimum_matching_threshold": 0.85,
            "minimum_consecutive_frames": 3,
        }
        config = ByteTrackConfig(**config_dict)

        assert config.lost_track_buffer == 60
        assert config.track_activation_threshold == 0.3
        assert config.minimum_matching_threshold == 0.85
        assert config.minimum_consecutive_frames == 3

    def test_config_to_dict(self) -> None:
        """ByteTrackConfig can be serialized to dictionary."""
        from ai.enrichment.utils.video_processing import ByteTrackConfig

        config = ByteTrackConfig(lost_track_buffer=45)
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["lost_track_buffer"] == 45

    def test_config_validation_rejects_negative_buffer(self) -> None:
        """ByteTrackConfig rejects negative lost_track_buffer."""
        from ai.enrichment.utils.video_processing import ByteTrackConfig

        with pytest.raises(ValueError, match="lost_track_buffer"):
            ByteTrackConfig(lost_track_buffer=-1)

    def test_config_validation_rejects_invalid_threshold(self) -> None:
        """ByteTrackConfig rejects thresholds outside [0, 1] range."""
        from ai.enrichment.utils.video_processing import ByteTrackConfig

        with pytest.raises(ValueError, match="track_activation_threshold"):
            ByteTrackConfig(track_activation_threshold=1.5)

        with pytest.raises(ValueError, match="minimum_matching_threshold"):
            ByteTrackConfig(minimum_matching_threshold=-0.1)


# =============================================================================
# TrackingResult Tests
# =============================================================================


class TestTrackingResult:
    """Tests for tracking result dataclass."""

    def test_tracking_result_creation(self) -> None:
        """TrackingResult can be created with required fields."""
        from ai.enrichment.utils.video_processing import TrackingResult

        result = TrackingResult(
            tracker_id=1,
            class_id=0,
            class_name="person",
            confidence=0.95,
            bbox=np.array([100, 150, 200, 300]),
        )

        assert result.tracker_id == 1
        assert result.class_id == 0
        assert result.class_name == "person"
        assert result.confidence == 0.95
        assert np.allclose(result.bbox, [100, 150, 200, 300])

    def test_tracking_result_with_optional_fields(self) -> None:
        """TrackingResult supports optional mask and metadata."""
        from ai.enrichment.utils.video_processing import TrackingResult

        mask = np.zeros((100, 100), dtype=np.uint8)
        metadata = {"camera_id": "front_door", "timestamp": "2026-01-26T10:00:00Z"}

        result = TrackingResult(
            tracker_id=2,
            class_id=2,
            class_name="car",
            confidence=0.88,
            bbox=np.array([50, 60, 250, 300]),
            mask=mask,
            metadata=metadata,
        )

        assert result.mask is not None
        assert result.mask.shape == (100, 100)
        assert result.metadata["camera_id"] == "front_door"

    def test_tracking_result_to_dict(self) -> None:
        """TrackingResult can be serialized to dictionary."""
        from ai.enrichment.utils.video_processing import TrackingResult

        result = TrackingResult(
            tracker_id=5,
            class_id=1,
            class_name="dog",
            confidence=0.92,
            bbox=np.array([10, 20, 100, 150]),
        )
        result_dict = result.to_dict()

        assert result_dict["tracker_id"] == 5
        assert result_dict["class_name"] == "dog"
        assert result_dict["bbox"] == [10, 20, 100, 150]


# =============================================================================
# AnnotatorConfig Tests
# =============================================================================


class TestAnnotatorConfig:
    """Tests for annotator configuration dataclass."""

    def test_default_annotator_config(self) -> None:
        """AnnotatorConfig has sensible defaults for security visualization."""
        from ai.enrichment.utils.video_processing import AnnotatorConfig

        config = AnnotatorConfig()

        # Box annotator should be enabled by default
        assert config.box_enabled is True
        # Label annotator should be enabled by default
        assert config.label_enabled is True
        # Trace annotator off by default (performance)
        assert config.trace_enabled is False
        # Heatmap annotator off by default (performance)
        assert config.heatmap_enabled is False

    def test_annotator_config_colors(self) -> None:
        """AnnotatorConfig supports custom color schemes."""
        from ai.enrichment.utils.video_processing import AnnotatorConfig

        # Security-focused color scheme: red for threats, green for normal
        config = AnnotatorConfig(
            box_color=(255, 0, 0),  # Red
            label_text_color=(255, 255, 255),  # White
        )

        assert config.box_color == (255, 0, 0)
        assert config.label_text_color == (255, 255, 255)

    def test_annotator_config_thickness(self) -> None:
        """AnnotatorConfig supports custom line thickness."""
        from ai.enrichment.utils.video_processing import AnnotatorConfig

        config = AnnotatorConfig(box_thickness=3, trace_thickness=2)

        assert config.box_thickness == 3
        assert config.trace_thickness == 2


# =============================================================================
# HeatmapConfig Tests
# =============================================================================


class TestHeatmapConfig:
    """Tests for heatmap configuration dataclass."""

    def test_default_heatmap_config(self) -> None:
        """HeatmapConfig has sensible defaults for activity visualization."""
        from ai.enrichment.utils.video_processing import HeatmapConfig

        config = HeatmapConfig()

        # Radius should be reasonable for typical video resolution
        assert 10 <= config.radius <= 50
        # Opacity should be between 0 and 1
        assert 0 < config.opacity <= 1.0
        # Color map should be a valid option
        assert config.color_map in ["hot", "jet", "turbo", "inferno"]

    def test_heatmap_config_position_anchor(self) -> None:
        """HeatmapConfig supports different position anchors for detections."""
        from ai.enrichment.utils.video_processing import HeatmapConfig

        config = HeatmapConfig(position_anchor="bottom_center")
        assert config.position_anchor == "bottom_center"

        config2 = HeatmapConfig(position_anchor="center")
        assert config2.position_anchor == "center"

    def test_heatmap_config_decay_factor(self) -> None:
        """HeatmapConfig supports decay factor for temporal heatmaps."""
        from ai.enrichment.utils.video_processing import HeatmapConfig

        config = HeatmapConfig(decay_factor=0.95)
        assert config.decay_factor == 0.95


# =============================================================================
# create_bytetrack_tracker Tests
# =============================================================================


class TestCreateByteTrackTracker:
    """Tests for ByteTrack tracker factory function."""

    def test_create_tracker_with_default_config(self) -> None:
        """create_bytetrack_tracker creates tracker with default config."""
        from ai.enrichment.utils.video_processing import create_bytetrack_tracker

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_tracker = MagicMock()
            mock_sv.ByteTrack.return_value = mock_tracker

            tracker = create_bytetrack_tracker()

            assert tracker == mock_tracker
            mock_sv.ByteTrack.assert_called_once()

    def test_create_tracker_with_custom_config(self) -> None:
        """create_bytetrack_tracker applies custom configuration."""
        from ai.enrichment.utils.video_processing import (
            ByteTrackConfig,
            create_bytetrack_tracker,
        )

        config = ByteTrackConfig(
            lost_track_buffer=60,
            track_activation_threshold=0.4,
        )

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_tracker = MagicMock()
            mock_sv.ByteTrack.return_value = mock_tracker

            tracker = create_bytetrack_tracker(config)

            assert tracker == mock_tracker
            call_kwargs = mock_sv.ByteTrack.call_args[1]
            assert call_kwargs["lost_track_buffer"] == 60
            assert call_kwargs["track_activation_threshold"] == 0.4

    def test_create_tracker_reset_functionality(self) -> None:
        """Created tracker supports reset for multi-video processing."""
        from ai.enrichment.utils.video_processing import create_bytetrack_tracker

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_tracker = MagicMock()
            mock_sv.ByteTrack.return_value = mock_tracker

            tracker = create_bytetrack_tracker()
            tracker.reset()

            mock_tracker.reset.assert_called_once()


# =============================================================================
# VideoAnnotator Tests
# =============================================================================


class TestVideoAnnotator:
    """Tests for VideoAnnotator class."""

    @pytest.fixture
    def sample_detections(self) -> MagicMock:
        """Create sample Supervision detections mock."""
        mock_detections = MagicMock()
        mock_detections.xyxy = np.array([[100, 150, 200, 300], [250, 100, 350, 250]])
        mock_detections.confidence = np.array([0.95, 0.88])
        mock_detections.class_id = np.array([0, 2])
        mock_detections.tracker_id = np.array([1, 2])
        mock_detections.__len__ = lambda self: 2
        return mock_detections

    @pytest.fixture
    def sample_frame(self) -> NDArray[np.uint8]:
        """Create sample video frame."""
        return np.zeros((480, 640, 3), dtype=np.uint8)

    def test_video_annotator_initialization(self) -> None:
        """VideoAnnotator initializes with default configuration."""
        from ai.enrichment.utils.video_processing import VideoAnnotator

        with patch("ai.enrichment.utils.video_processing.sv"):
            annotator = VideoAnnotator()

            assert annotator.config is not None
            assert annotator.box_annotator is not None
            assert annotator.label_annotator is not None

    def test_video_annotator_with_custom_config(self) -> None:
        """VideoAnnotator accepts custom AnnotatorConfig."""
        from ai.enrichment.utils.video_processing import AnnotatorConfig, VideoAnnotator

        config = AnnotatorConfig(
            box_enabled=True,
            trace_enabled=True,
            box_thickness=3,
        )

        with patch("ai.enrichment.utils.video_processing.sv"):
            annotator = VideoAnnotator(config)

            assert annotator.config.box_thickness == 3
            assert annotator.config.trace_enabled is True

    def test_annotate_frame_with_boxes(
        self, sample_frame: NDArray[np.uint8], sample_detections: MagicMock
    ) -> None:
        """annotate_frame draws bounding boxes on frame."""
        from ai.enrichment.utils.video_processing import VideoAnnotator

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_box = MagicMock()
            mock_box.annotate.return_value = sample_frame
            mock_sv.BoxAnnotator.return_value = mock_box
            mock_sv.LabelAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=sample_frame)
            )

            annotator = VideoAnnotator()
            result = annotator.annotate_frame(
                sample_frame, sample_detections, labels=["person", "car"]
            )

            assert result.shape == sample_frame.shape
            mock_box.annotate.assert_called()

    def test_annotate_frame_with_trace(
        self, sample_frame: NDArray[np.uint8], sample_detections: MagicMock
    ) -> None:
        """annotate_frame draws traces when enabled."""
        from ai.enrichment.utils.video_processing import AnnotatorConfig, VideoAnnotator

        config = AnnotatorConfig(trace_enabled=True)

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_trace = MagicMock()
            mock_trace.annotate.return_value = sample_frame
            mock_sv.TraceAnnotator.return_value = mock_trace
            mock_sv.BoxAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=sample_frame)
            )
            mock_sv.LabelAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=sample_frame)
            )

            annotator = VideoAnnotator(config)
            annotator.annotate_frame(sample_frame, sample_detections, labels=["person", "car"])

            mock_trace.annotate.assert_called()

    def test_generate_labels_from_detections(self, sample_detections: MagicMock) -> None:
        """generate_labels creates formatted labels with tracker IDs."""
        from ai.enrichment.utils.video_processing import VideoAnnotator

        class_names = {0: "person", 2: "car"}

        with patch("ai.enrichment.utils.video_processing.sv"):
            annotator = VideoAnnotator()
            labels = annotator.generate_labels(sample_detections, class_names)

            assert len(labels) == 2
            # Labels should include tracker ID and class name
            assert "#1" in labels[0] or "person" in labels[0]


# =============================================================================
# VideoProcessor Tests
# =============================================================================


class TestVideoProcessor:
    """Tests for VideoProcessor class integrating tracker and annotator."""

    @pytest.fixture
    def mock_supervision(self) -> MagicMock:
        """Create mock supervision module."""
        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            # Mock ByteTrack
            mock_tracker = MagicMock()
            mock_sv.ByteTrack.return_value = mock_tracker

            # Mock Detections
            mock_detections = MagicMock()
            mock_detections.tracker_id = np.array([1, 2])
            mock_detections.xyxy = np.array([[100, 100, 200, 200], [300, 300, 400, 400]])
            mock_detections.confidence = np.array([0.9, 0.85])
            mock_detections.class_id = np.array([0, 0])
            mock_detections.__len__ = lambda self: 2
            mock_tracker.update_with_detections.return_value = mock_detections
            mock_sv.Detections.from_ultralytics.return_value = mock_detections

            # Mock annotators
            mock_sv.BoxAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=np.zeros((480, 640, 3), dtype=np.uint8))
            )
            mock_sv.LabelAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=np.zeros((480, 640, 3), dtype=np.uint8))
            )

            yield mock_sv

    def test_video_processor_initialization(self, mock_supervision: MagicMock) -> None:
        """VideoProcessor initializes with tracker and annotator."""
        from ai.enrichment.utils.video_processing import VideoProcessor

        processor = VideoProcessor()

        assert processor.tracker is not None
        assert processor.annotator is not None

    def test_process_frame_updates_tracker(self, mock_supervision: MagicMock) -> None:
        """process_frame updates tracker with detections."""
        from ai.enrichment.utils.video_processing import VideoProcessor

        processor = VideoProcessor()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Mock YOLO detections
        mock_yolo_result = MagicMock()
        mock_yolo_result.names = {0: "person"}

        results = processor.process_frame(frame, mock_yolo_result)

        # Tracker should be updated
        processor.tracker.update_with_detections.assert_called()
        assert len(results) == 2

    def test_process_frame_returns_tracking_results(self, mock_supervision: MagicMock) -> None:
        """process_frame returns list of TrackingResult objects."""
        from ai.enrichment.utils.video_processing import TrackingResult, VideoProcessor

        processor = VideoProcessor()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_yolo_result = MagicMock()
        mock_yolo_result.names = {0: "person"}

        results = processor.process_frame(frame, mock_yolo_result)

        assert all(isinstance(r, TrackingResult) for r in results)
        assert results[0].tracker_id == 1
        assert results[0].class_name == "person"

    def test_process_frame_with_annotation(self, mock_supervision: MagicMock) -> None:
        """process_frame can return annotated frame."""
        from ai.enrichment.utils.video_processing import VideoProcessor

        processor = VideoProcessor()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_yolo_result = MagicMock()
        mock_yolo_result.names = {0: "person"}

        results, annotated_frame = processor.process_frame(frame, mock_yolo_result, annotate=True)

        assert annotated_frame is not None
        assert annotated_frame.shape == frame.shape

    def test_reset_tracker(self, mock_supervision: MagicMock) -> None:
        """reset() clears tracker state for new video."""
        from ai.enrichment.utils.video_processing import VideoProcessor

        processor = VideoProcessor()
        processor.reset()

        processor.tracker.reset.assert_called_once()

    def test_get_active_tracks(self, mock_supervision: MagicMock) -> None:
        """get_active_tracks returns current tracked objects."""
        from ai.enrichment.utils.video_processing import VideoProcessor

        processor = VideoProcessor()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_yolo_result = MagicMock()
        mock_yolo_result.names = {0: "person"}

        # Process a frame to populate tracks
        processor.process_frame(frame, mock_yolo_result)

        active_tracks = processor.get_active_tracks()

        assert len(active_tracks) == 2
        assert 1 in active_tracks
        assert 2 in active_tracks


# =============================================================================
# create_video_annotator Tests
# =============================================================================


class TestCreateVideoAnnotator:
    """Tests for video annotator factory function."""

    def test_create_video_annotator_default(self) -> None:
        """create_video_annotator creates annotator with defaults."""
        from ai.enrichment.utils.video_processing import create_video_annotator

        with patch("ai.enrichment.utils.video_processing.sv"):
            annotator = create_video_annotator()
            assert annotator is not None

    def test_create_video_annotator_with_config(self) -> None:
        """create_video_annotator accepts custom config."""
        from ai.enrichment.utils.video_processing import (
            AnnotatorConfig,
            create_video_annotator,
        )

        config = AnnotatorConfig(box_thickness=5)

        with patch("ai.enrichment.utils.video_processing.sv"):
            annotator = create_video_annotator(config)
            assert annotator.config.box_thickness == 5


# =============================================================================
# create_video_processor Tests
# =============================================================================


class TestCreateVideoProcessor:
    """Tests for video processor factory function."""

    def test_create_video_processor_default(self) -> None:
        """create_video_processor creates processor with defaults."""
        from ai.enrichment.utils.video_processing import create_video_processor

        with patch("ai.enrichment.utils.video_processing.sv"):
            processor = create_video_processor()
            assert processor is not None
            assert processor.tracker is not None
            assert processor.annotator is not None

    def test_create_video_processor_with_configs(self) -> None:
        """create_video_processor accepts tracker and annotator configs."""
        from ai.enrichment.utils.video_processing import (
            AnnotatorConfig,
            ByteTrackConfig,
            create_video_processor,
        )

        tracker_config = ByteTrackConfig(lost_track_buffer=45)
        annotator_config = AnnotatorConfig(trace_enabled=True)

        with patch("ai.enrichment.utils.video_processing.sv"):
            processor = create_video_processor(
                tracker_config=tracker_config,
                annotator_config=annotator_config,
            )

            assert processor.annotator.config.trace_enabled is True


# =============================================================================
# Heatmap Integration Tests
# =============================================================================


class TestHeatmapAnnotator:
    """Tests for heatmap annotation functionality."""

    def test_heatmap_annotator_creation(self) -> None:
        """HeatMapAnnotator can be created from config."""
        from ai.enrichment.utils.video_processing import (
            AnnotatorConfig,
            HeatmapConfig,
            VideoAnnotator,
        )

        config = AnnotatorConfig(heatmap_enabled=True)
        heatmap_config = HeatmapConfig(radius=25, opacity=0.6)

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_heatmap = MagicMock()
            mock_sv.HeatMapAnnotator.return_value = mock_heatmap
            mock_sv.BoxAnnotator.return_value = MagicMock()
            mock_sv.LabelAnnotator.return_value = MagicMock()

            annotator = VideoAnnotator(config, heatmap_config=heatmap_config)

            assert annotator.heatmap_annotator is not None

    def test_heatmap_update_with_detections(self) -> None:
        """Heatmap annotator updates with detection positions."""
        from ai.enrichment.utils.video_processing import (
            AnnotatorConfig,
            HeatmapConfig,
            VideoAnnotator,
        )

        config = AnnotatorConfig(heatmap_enabled=True)
        heatmap_config = HeatmapConfig()

        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            mock_heatmap = MagicMock()
            mock_heatmap.annotate.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
            mock_sv.HeatMapAnnotator.return_value = mock_heatmap
            mock_sv.BoxAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=np.zeros((480, 640, 3), dtype=np.uint8))
            )
            mock_sv.LabelAnnotator.return_value = MagicMock(
                annotate=MagicMock(return_value=np.zeros((480, 640, 3), dtype=np.uint8))
            )

            annotator = VideoAnnotator(config, heatmap_config=heatmap_config)

            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            mock_detections = MagicMock()
            mock_detections.xyxy = np.array([[100, 100, 200, 200]])
            mock_detections.confidence = np.array([0.9])
            mock_detections.class_id = np.array([0])
            mock_detections.tracker_id = np.array([1])
            mock_detections.__len__ = lambda self: 1

            annotator.annotate_frame(frame, mock_detections, labels=["person"])

            # Heatmap should be updated
            mock_heatmap.annotate.assert_called()


# =============================================================================
# Integration with YOLO Detections Tests
# =============================================================================


class TestSupervisionYOLOIntegration:
    """Tests for Supervision integration with YOLO detections."""

    def test_detections_from_ultralytics(self) -> None:
        """Supervision can convert Ultralytics YOLO results."""
        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            from ai.enrichment.utils.video_processing import VideoProcessor

            mock_yolo_result = MagicMock()
            mock_yolo_result.boxes.xyxy = np.array([[100, 100, 200, 200]])
            mock_yolo_result.boxes.conf = np.array([0.95])
            mock_yolo_result.boxes.cls = np.array([0])
            mock_yolo_result.names = {0: "person"}

            mock_detections = MagicMock()
            mock_detections.xyxy = np.array([[100, 100, 200, 200]])
            mock_detections.confidence = np.array([0.95])
            mock_detections.class_id = np.array([0])
            mock_detections.tracker_id = np.array([1])
            mock_detections.__len__ = lambda self: 1

            mock_sv.Detections.from_ultralytics.return_value = mock_detections
            mock_sv.ByteTrack.return_value = MagicMock(
                update_with_detections=MagicMock(return_value=mock_detections)
            )
            mock_sv.BoxAnnotator.return_value = MagicMock()
            mock_sv.LabelAnnotator.return_value = MagicMock()

            processor = VideoProcessor()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            results = processor.process_frame(frame, mock_yolo_result)

            mock_sv.Detections.from_ultralytics.assert_called_with(mock_yolo_result)
            assert len(results) == 1
            assert results[0].class_name == "person"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in video processing utilities."""

    def test_empty_detections_handling(self) -> None:
        """VideoProcessor handles empty detections gracefully."""
        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            from ai.enrichment.utils.video_processing import VideoProcessor

            # Empty detections
            mock_detections = MagicMock()
            mock_detections.xyxy = np.array([]).reshape(0, 4)
            mock_detections.confidence = np.array([])
            mock_detections.class_id = np.array([])
            mock_detections.tracker_id = np.array([])
            mock_detections.__len__ = lambda self: 0

            mock_sv.Detections.from_ultralytics.return_value = mock_detections
            mock_sv.ByteTrack.return_value = MagicMock(
                update_with_detections=MagicMock(return_value=mock_detections)
            )
            mock_sv.BoxAnnotator.return_value = MagicMock()
            mock_sv.LabelAnnotator.return_value = MagicMock()

            processor = VideoProcessor()
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            mock_yolo_result = MagicMock()
            mock_yolo_result.names = {}

            results = processor.process_frame(frame, mock_yolo_result)

            assert len(results) == 0

    def test_invalid_frame_raises_error(self) -> None:
        """VideoProcessor raises error for invalid frame input."""
        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            from ai.enrichment.utils.video_processing import VideoProcessor

            mock_sv.ByteTrack.return_value = MagicMock()
            mock_sv.BoxAnnotator.return_value = MagicMock()
            mock_sv.LabelAnnotator.return_value = MagicMock()

            processor = VideoProcessor()

            # 2D array instead of 3D
            invalid_frame = np.zeros((480, 640), dtype=np.uint8)

            with pytest.raises(ValueError, match="frame"):
                processor.process_frame(invalid_frame, MagicMock())

    def test_none_frame_raises_error(self) -> None:
        """VideoProcessor raises error for None frame."""
        with patch("ai.enrichment.utils.video_processing.sv") as mock_sv:
            from ai.enrichment.utils.video_processing import VideoProcessor

            mock_sv.ByteTrack.return_value = MagicMock()
            mock_sv.BoxAnnotator.return_value = MagicMock()
            mock_sv.LabelAnnotator.return_value = MagicMock()

            processor = VideoProcessor()

            with pytest.raises(ValueError, match="frame"):
                processor.process_frame(None, MagicMock())
