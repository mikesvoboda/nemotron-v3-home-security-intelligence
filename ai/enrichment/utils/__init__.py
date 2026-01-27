"""Video processing utilities for the AI Enrichment Service.

This module provides video analytics utilities built on the Supervision library
from Roboflow, including object tracking with ByteTrack, annotation tools,
and heatmap generation for security analytics.
"""

from __future__ import annotations

from ai.enrichment.utils.video_processing import (
    AnnotatorConfig,
    ByteTrackConfig,
    HeatmapConfig,
    TrackingResult,
    VideoAnnotator,
    VideoProcessor,
    create_bytetrack_tracker,
    create_video_annotator,
    create_video_processor,
)

__all__ = [
    "AnnotatorConfig",
    "ByteTrackConfig",
    "HeatmapConfig",
    "TrackingResult",
    "VideoAnnotator",
    "VideoProcessor",
    "create_bytetrack_tracker",
    "create_video_annotator",
    "create_video_processor",
]
