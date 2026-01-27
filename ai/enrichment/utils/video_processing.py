"""Video processing utilities for the AI Enrichment Service.

This module provides video analytics utilities built on the Supervision library
from Roboflow, including:

- Object tracking with ByteTrack
- Frame annotation with bounding boxes, labels, and traces
- Heatmap generation for activity visualization
- Integration with YOLO/Ultralytics detection models

Usage:
    from ai.enrichment.utils.video_processing import (
        create_video_processor,
        ByteTrackConfig,
        AnnotatorConfig,
    )

    # Create processor with default settings
    processor = create_video_processor()

    # Process frames from video
    for frame in video_frames:
        results = model(frame)
        tracking_results = processor.process_frame(frame, results[0])
        for track in tracking_results:
            print(f"Track #{track.tracker_id}: {track.class_name}")

References:
    - Supervision docs: https://supervision.roboflow.com/
    - ByteTrack: https://supervision.roboflow.com/trackers/
    - Annotators: https://supervision.roboflow.com/annotators/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

# Import supervision lazily to allow mocking in tests
try:
    import supervision as sv
except ImportError:
    sv = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from numpy.typing import NDArray


# =============================================================================
# Configuration Dataclasses
# =============================================================================


@dataclass
class ByteTrackConfig:
    """Configuration for ByteTrack object tracker.

    ByteTrack is a multi-object tracking algorithm that assigns unique IDs
    to detected objects and tracks them across video frames.

    Attributes:
        lost_track_buffer: Number of frames to keep a track alive after
            it's no longer detected. Higher values handle brief occlusions
            better but may cause ID switches. Default: 30 (~1 second at 30fps).
        track_activation_threshold: Minimum detection confidence to start
            a new track. Lower values track more objects but may include
            false positives. Range: [0, 1]. Default: 0.25.
        minimum_matching_threshold: Minimum IoU overlap for matching detections
            to existing tracks. Higher values are stricter. Range: [0, 1].
            Default: 0.8.
        minimum_consecutive_frames: Minimum frames a detection must appear
            consecutively before confirming it as a valid track. Helps filter
            spurious detections. Default: 1.
    """

    lost_track_buffer: int = 30
    track_activation_threshold: float = 0.25
    minimum_matching_threshold: float = 0.8
    minimum_consecutive_frames: int = 1

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.lost_track_buffer < 0:
            msg = f"lost_track_buffer must be non-negative, got {self.lost_track_buffer}"
            raise ValueError(msg)

        if not 0 <= self.track_activation_threshold <= 1:
            msg = (
                f"track_activation_threshold must be in [0, 1], "
                f"got {self.track_activation_threshold}"
            )
            raise ValueError(msg)

        if not 0 <= self.minimum_matching_threshold <= 1:
            msg = (
                f"minimum_matching_threshold must be in [0, 1], "
                f"got {self.minimum_matching_threshold}"
            )
            raise ValueError(msg)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "lost_track_buffer": self.lost_track_buffer,
            "track_activation_threshold": self.track_activation_threshold,
            "minimum_matching_threshold": self.minimum_matching_threshold,
            "minimum_consecutive_frames": self.minimum_consecutive_frames,
        }


@dataclass
class AnnotatorConfig:
    """Configuration for video frame annotation.

    Controls which visual annotations are applied to video frames and
    their appearance (colors, thickness, etc.).

    Attributes:
        box_enabled: Draw bounding boxes around detections. Default: True.
        label_enabled: Draw labels with class names and confidence. Default: True.
        trace_enabled: Draw movement traces for tracked objects. Default: False.
        heatmap_enabled: Overlay activity heatmap. Default: False.
        box_color: RGB color tuple for bounding boxes. Default: (0, 255, 0) green.
        box_thickness: Line thickness for boxes in pixels. Default: 2.
        label_text_color: RGB color for label text. Default: (255, 255, 255) white.
        label_text_scale: Font scale for labels. Default: 0.5.
        trace_thickness: Line thickness for traces. Default: 2.
        trace_length: Number of past positions to show in trace. Default: 30.
    """

    box_enabled: bool = True
    label_enabled: bool = True
    trace_enabled: bool = False
    heatmap_enabled: bool = False
    box_color: tuple[int, int, int] = (0, 255, 0)
    box_thickness: int = 2
    label_text_color: tuple[int, int, int] = (255, 255, 255)
    label_text_scale: float = 0.5
    trace_thickness: int = 2
    trace_length: int = 30


@dataclass
class HeatmapConfig:
    """Configuration for activity heatmap generation.

    Heatmaps visualize areas of high detection activity over time,
    useful for understanding movement patterns and identifying
    frequently visited areas.

    Attributes:
        radius: Gaussian blur radius for heatmap points. Larger values
            create smoother heatmaps. Default: 25.
        opacity: Heatmap overlay opacity. Range: [0, 1]. Default: 0.5.
        color_map: Color mapping scheme. Options: "hot", "jet", "turbo",
            "inferno". Default: "turbo".
        position_anchor: Where on the bounding box to place the heat point.
            Options: "center", "bottom_center", "top_center". Default: "bottom_center".
        decay_factor: Temporal decay factor for fading old detections.
            Range: [0, 1]. Default: 0.99.
    """

    radius: int = 25
    opacity: float = 0.5
    color_map: str = "turbo"
    position_anchor: str = "bottom_center"
    decay_factor: float = 0.99


@dataclass
class TrackingResult:
    """Result of tracking a single object across frames.

    Contains all information about a tracked detection including its
    unique ID, classification, location, and optional metadata.

    Attributes:
        tracker_id: Unique identifier assigned by ByteTrack.
        class_id: Integer class ID from the detection model.
        class_name: Human-readable class name.
        confidence: Detection confidence score [0, 1].
        bbox: Bounding box as [x1, y1, x2, y2] array.
        mask: Optional segmentation mask.
        metadata: Optional dictionary for additional data (camera_id, timestamp, etc.).
    """

    tracker_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: NDArray[np.floating[Any]]
    mask: NDArray[np.uint8] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "tracker_id": self.tracker_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "bbox": self.bbox.tolist() if isinstance(self.bbox, np.ndarray) else list(self.bbox),
            "mask": self.mask.tolist() if self.mask is not None else None,
            "metadata": self.metadata,
        }


# =============================================================================
# VideoAnnotator Class
# =============================================================================


class VideoAnnotator:
    """Annotates video frames with detection visualizations.

    Combines multiple Supervision annotators (box, label, trace, heatmap)
    into a unified interface for drawing detections on video frames.

    Example:
        annotator = VideoAnnotator(AnnotatorConfig(trace_enabled=True))
        annotated_frame = annotator.annotate_frame(
            frame, detections, labels=["person #1", "car #2"]
        )
    """

    def __init__(
        self,
        config: AnnotatorConfig | None = None,
        heatmap_config: HeatmapConfig | None = None,
    ) -> None:
        """Initialize annotator with configuration.

        Args:
            config: Annotator configuration. Uses defaults if None.
            heatmap_config: Heatmap configuration. Only used if heatmap_enabled.
        """
        self.config = config or AnnotatorConfig()
        self.heatmap_config = heatmap_config

        # Initialize annotators based on configuration
        self.box_annotator = sv.BoxAnnotator(
            thickness=self.config.box_thickness,
        )
        self.label_annotator = sv.LabelAnnotator(
            text_scale=self.config.label_text_scale,
        )

        # Optional trace annotator
        self.trace_annotator: Any | None = None
        if self.config.trace_enabled:
            self.trace_annotator = sv.TraceAnnotator(
                thickness=self.config.trace_thickness,
                trace_length=self.config.trace_length,
            )

        # Optional heatmap annotator
        self.heatmap_annotator: Any | None = None
        if self.config.heatmap_enabled and heatmap_config:
            self.heatmap_annotator = sv.HeatMapAnnotator(
                radius=heatmap_config.radius,
                opacity=heatmap_config.opacity,
            )

    def annotate_frame(
        self,
        frame: NDArray[np.uint8],
        detections: Any,
        labels: list[str] | None = None,
    ) -> NDArray[np.uint8]:
        """Annotate a video frame with detections.

        Args:
            frame: Video frame as numpy array (H, W, 3).
            detections: Supervision Detections object.
            labels: Optional list of labels for each detection.

        Returns:
            Annotated frame as numpy array.
        """
        annotated = frame.copy()

        # Apply heatmap first (background layer)
        if self.heatmap_annotator is not None:
            annotated = self.heatmap_annotator.annotate(annotated, detections)

        # Apply trace (behind boxes)
        if self.trace_annotator is not None:
            annotated = self.trace_annotator.annotate(annotated, detections)

        # Apply bounding boxes
        if self.config.box_enabled:
            annotated = self.box_annotator.annotate(annotated, detections)

        # Apply labels
        if self.config.label_enabled and labels is not None:
            annotated = self.label_annotator.annotate(annotated, detections, labels=labels)

        return annotated

    def generate_labels(
        self,
        detections: Any,
        class_names: dict[int, str],
    ) -> list[str]:
        """Generate formatted labels for detections.

        Args:
            detections: Supervision Detections object.
            class_names: Mapping from class ID to class name.

        Returns:
            List of formatted label strings.
        """
        labels = []
        for i in range(len(detections)):
            class_id = int(detections.class_id[i])
            class_name = class_names.get(class_id, f"class_{class_id}")
            confidence = float(detections.confidence[i])

            tracker_id = None
            if detections.tracker_id is not None:
                tracker_id = int(detections.tracker_id[i])

            if tracker_id is not None:
                label = f"#{tracker_id} {class_name} {confidence:.2f}"
            else:
                label = f"{class_name} {confidence:.2f}"

            labels.append(label)

        return labels


# =============================================================================
# VideoProcessor Class
# =============================================================================


class VideoProcessor:
    """Processes video frames with object detection and tracking.

    Integrates ByteTrack tracking with YOLO detection models to provide
    frame-by-frame object tracking with optional annotation.

    Example:
        processor = create_video_processor()

        for frame in video:
            results = yolo_model(frame)
            tracking_results = processor.process_frame(frame, results[0])

            for track in tracking_results:
                print(f"Track #{track.tracker_id}: {track.class_name}")

        # Reset between videos
        processor.reset()
    """

    def __init__(
        self,
        tracker_config: ByteTrackConfig | None = None,
        annotator_config: AnnotatorConfig | None = None,
        heatmap_config: HeatmapConfig | None = None,
    ) -> None:
        """Initialize processor with tracker and annotator.

        Args:
            tracker_config: ByteTrack configuration. Uses defaults if None.
            annotator_config: Annotator configuration. Uses defaults if None.
            heatmap_config: Heatmap configuration. Only used if heatmap enabled.
        """
        self.tracker_config = tracker_config or ByteTrackConfig()
        self.annotator_config = annotator_config or AnnotatorConfig()
        self.heatmap_config = heatmap_config

        # Initialize ByteTrack tracker
        self.tracker = sv.ByteTrack(
            lost_track_buffer=self.tracker_config.lost_track_buffer,
            track_activation_threshold=self.tracker_config.track_activation_threshold,
            minimum_matching_threshold=self.tracker_config.minimum_matching_threshold,
            minimum_consecutive_frames=self.tracker_config.minimum_consecutive_frames,
        )

        # Initialize annotator
        self.annotator = VideoAnnotator(
            config=self.annotator_config,
            heatmap_config=heatmap_config,
        )

        # Track active tracks for querying
        self._active_tracks: dict[int, TrackingResult] = {}

    def process_frame(
        self,
        frame: NDArray[np.uint8] | None,
        yolo_result: Any,
        annotate: bool = False,
    ) -> list[TrackingResult] | tuple[list[TrackingResult], NDArray[np.uint8]]:
        """Process a single video frame.

        Converts YOLO detections to Supervision format, updates the tracker,
        and optionally annotates the frame.

        Args:
            frame: Video frame as numpy array (H, W, 3).
            yolo_result: Ultralytics YOLO result object.
            annotate: If True, return annotated frame as second value.

        Returns:
            If annotate=False: List of TrackingResult objects.
            If annotate=True: Tuple of (results, annotated_frame).

        Raises:
            ValueError: If frame is None or has invalid shape.
        """
        # Validate frame
        if frame is None:
            msg = "frame cannot be None"
            raise ValueError(msg)

        if frame.ndim != 3:
            msg = f"frame must be 3D array (H, W, C), got shape {frame.shape}"
            raise ValueError(msg)

        # Convert YOLO results to Supervision Detections
        detections = sv.Detections.from_ultralytics(yolo_result)

        # Update tracker with detections
        detections = self.tracker.update_with_detections(detections)

        # Get class names from YOLO result
        class_names = yolo_result.names if hasattr(yolo_result, "names") else {}

        # Convert to TrackingResult objects
        results = []
        self._active_tracks.clear()

        for i in range(len(detections)):
            class_id = int(detections.class_id[i])  # type: ignore[index]
            tracker_id = (
                int(detections.tracker_id[i])  # type: ignore[index]
                if detections.tracker_id is not None
                else i
            )

            result = TrackingResult(
                tracker_id=tracker_id,
                class_id=class_id,
                class_name=class_names.get(class_id, f"class_{class_id}"),
                confidence=float(detections.confidence[i]),  # type: ignore[index]
                bbox=detections.xyxy[i],
            )
            results.append(result)
            self._active_tracks[tracker_id] = result

        if annotate:
            labels = self.annotator.generate_labels(detections, class_names)
            annotated_frame = self.annotator.annotate_frame(frame, detections, labels)
            return results, annotated_frame

        return results

    def reset(self) -> None:
        """Reset tracker state for processing a new video.

        Call this between videos to ensure clean tracking state
        and avoid ID carryover between unrelated videos.
        """
        self.tracker.reset()
        self._active_tracks.clear()

    def get_active_tracks(self) -> dict[int, TrackingResult]:
        """Get currently active tracked objects.

        Returns:
            Dictionary mapping tracker IDs to their TrackingResult objects.
        """
        return self._active_tracks.copy()


# =============================================================================
# Factory Functions
# =============================================================================


def create_bytetrack_tracker(config: ByteTrackConfig | None = None) -> Any:
    """Create a ByteTrack tracker with configuration.

    Args:
        config: ByteTrack configuration. Uses defaults if None.

    Returns:
        Supervision ByteTrack tracker instance.
    """
    config = config or ByteTrackConfig()

    return sv.ByteTrack(
        lost_track_buffer=config.lost_track_buffer,
        track_activation_threshold=config.track_activation_threshold,
        minimum_matching_threshold=config.minimum_matching_threshold,
        minimum_consecutive_frames=config.minimum_consecutive_frames,
    )


def create_video_annotator(
    config: AnnotatorConfig | None = None,
    heatmap_config: HeatmapConfig | None = None,
) -> VideoAnnotator:
    """Create a video annotator with configuration.

    Args:
        config: Annotator configuration. Uses defaults if None.
        heatmap_config: Heatmap configuration. Only used if heatmap enabled.

    Returns:
        VideoAnnotator instance.
    """
    return VideoAnnotator(config=config, heatmap_config=heatmap_config)


def create_video_processor(
    tracker_config: ByteTrackConfig | None = None,
    annotator_config: AnnotatorConfig | None = None,
    heatmap_config: HeatmapConfig | None = None,
) -> VideoProcessor:
    """Create a video processor with tracker and annotator.

    Convenience factory function for creating a fully configured
    VideoProcessor instance.

    Args:
        tracker_config: ByteTrack configuration. Uses defaults if None.
        annotator_config: Annotator configuration. Uses defaults if None.
        heatmap_config: Heatmap configuration. Only used if heatmap enabled.

    Returns:
        VideoProcessor instance.

    Example:
        # Create with defaults
        processor = create_video_processor()

        # Create with custom tracking for longer occlusions
        processor = create_video_processor(
            tracker_config=ByteTrackConfig(lost_track_buffer=60)
        )

        # Create with activity heatmap
        processor = create_video_processor(
            annotator_config=AnnotatorConfig(heatmap_enabled=True),
            heatmap_config=HeatmapConfig(radius=30, opacity=0.7),
        )
    """
    return VideoProcessor(
        tracker_config=tracker_config,
        annotator_config=annotator_config,
        heatmap_config=heatmap_config,
    )
