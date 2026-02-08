"""Skeleton-based action recognition service using ST-GCN++.

This service replaces X-CLIP video-based action recognition (NEM-5563) with
skeleton-based classification that reuses pose keypoints already extracted
by ViTPose or YOLOv8n-Pose.

Key advantages over X-CLIP:
- VRAM: ~14MB vs ~2GB (saves 1,986MB)
- Speed: Runs on pre-extracted keypoints, no image processing needed
- Input: 17 COCO keypoints per person (already available from pose estimation)

The service buffers keypoints per tracked person_id across frames and runs
ST-GCN++ inference on the buffered temporal sequence when enough frames
have been accumulated.

Buffer design:
- Per-person circular buffer of keypoints keyed by tracking_id
- Window: 30-60 frames (configurable)
- Inference triggered when buffer has >= min_frames keypoints
- Old buffers cleaned up after max_age_seconds
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from backend.core.logging import get_logger
from backend.services.stgcn_loader import (
    COCO_KEYPOINT_NAMES,
    SkeletonActionResult,
    classify_skeleton_action,
)

logger = get_logger(__name__)

# Default configuration
DEFAULT_BUFFER_SIZE = 60  # Max frames to buffer per person
DEFAULT_MIN_FRAMES = 30  # Minimum frames before running inference
DEFAULT_MAX_AGE_SECONDS = 60  # Evict person buffers older than this


@dataclass(slots=True)
class KeypointFrame:
    """A single frame of keypoints for one person.

    Attributes:
        keypoints: Array of shape (17, 3) — x, y, confidence for each COCO joint
        timestamp: Unix timestamp when the frame was captured
    """

    keypoints: np.ndarray  # (17, 3)
    timestamp: float


class SkeletonActionService:
    """Service that buffers pose keypoints and classifies actions via ST-GCN++.

    Usage:
        service = SkeletonActionService(model_dict)

        # Feed keypoints from each frame
        result = await service.add_keypoints(
            person_id="track_42",
            keypoints={"nose": Keypoint(x=0.5, y=0.3, confidence=0.9), ...},
        )
        if result is not None:
            print(f"Action: {result.action_label} ({result.confidence:.1%})")
    """

    def __init__(
        self,
        model_dict: dict[str, Any],
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        min_frames: int = DEFAULT_MIN_FRAMES,
        max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
        inference_interval: int = 15,
    ) -> None:
        """Initialize the skeleton action service.

        Args:
            model_dict: Loaded ST-GCN++ model from load_stgcn_model
            buffer_size: Maximum frames to buffer per person
            min_frames: Minimum frames required before inference
            max_age_seconds: Maximum age of person buffer before eviction
            inference_interval: Run inference every N frames per person
        """
        self.model_dict = model_dict
        self.buffer_size = buffer_size
        self.min_frames = min_frames
        self.max_age_seconds = max_age_seconds
        self.inference_interval = inference_interval

        # Per-person keypoint buffers: person_id -> deque of KeypointFrame
        self._buffers: dict[str, deque[KeypointFrame]] = defaultdict(
            lambda: deque(maxlen=buffer_size)
        )
        # Frame count per person since last inference
        self._frame_counts: dict[str, int] = defaultdict(int)
        # Last inference result per person (cached)
        self._last_results: dict[str, SkeletonActionResult] = {}
        self._lock = asyncio.Lock()

    def _keypoints_dict_to_array(
        self,
        keypoints: dict[str, Any],
    ) -> np.ndarray:
        """Convert keypoints dict to numpy array (17, 3).

        Args:
            keypoints: Dictionary mapping keypoint names to objects with
                       x, y, confidence attributes (Keypoint from vitpose_loader)

        Returns:
            Array of shape (17, 3) with x, y, confidence per joint
        """
        arr = np.zeros((17, 3), dtype=np.float32)
        for idx, name in enumerate(COCO_KEYPOINT_NAMES):
            kp = keypoints.get(name)
            if kp is not None:
                arr[idx, 0] = getattr(kp, "x", 0.0)
                arr[idx, 1] = getattr(kp, "y", 0.0)
                arr[idx, 2] = getattr(kp, "confidence", 0.0)
        return arr

    async def add_keypoints(
        self,
        person_id: str,
        keypoints: dict[str, Any] | np.ndarray,
        timestamp: float | None = None,
    ) -> SkeletonActionResult | None:
        """Add a frame of keypoints for a tracked person.

        Buffers the keypoints and runs inference if enough frames have
        been accumulated since the last inference.

        Args:
            person_id: Unique identifier for the tracked person (tracking_id)
            keypoints: Either a dict mapping keypoint names to Keypoint objects,
                      or a numpy array of shape (17, 3)
            timestamp: Unix timestamp (defaults to current time)

        Returns:
            SkeletonActionResult if inference was run, None otherwise
        """
        if timestamp is None:
            timestamp = time.time()

        # Convert dict to array if needed
        if isinstance(keypoints, dict):
            kp_array = self._keypoints_dict_to_array(keypoints)
        else:
            kp_array = keypoints

        if kp_array.shape != (17, 3):
            logger.warning(
                f"Invalid keypoint shape {kp_array.shape} for person {person_id}, expected (17, 3)"
            )
            return None

        async with self._lock:
            # Add to buffer
            self._buffers[person_id].append(KeypointFrame(keypoints=kp_array, timestamp=timestamp))
            self._frame_counts[person_id] += 1

            # Check if we should run inference
            buf = self._buffers[person_id]
            frames_since_last = self._frame_counts[person_id]

            if len(buf) >= self.min_frames and frames_since_last >= self.inference_interval:
                self._frame_counts[person_id] = 0
                # Build input from buffer
                kp_sequence = np.stack([f.keypoints for f in buf])  # (T, 17, 3)
                # Add person dimension: (1, T, 17, 3)
                kp_sequence = kp_sequence[np.newaxis]
            else:
                return self._last_results.get(person_id)

        # Run inference outside lock
        try:
            result = await classify_skeleton_action(
                self.model_dict,
                kp_sequence,
                top_k=5,
            )
            async with self._lock:
                self._last_results[person_id] = result
            return result
        except Exception as e:
            logger.error(f"Skeleton action classification failed for person {person_id}: {e}")
            return self._last_results.get(person_id)

    async def cleanup_stale(self) -> int:
        """Remove stale person buffers older than max_age_seconds.

        Returns:
            Number of person buffers removed
        """
        now = time.time()
        removed = 0

        async with self._lock:
            stale_ids = []
            for person_id, buf in self._buffers.items():
                if buf and (now - buf[-1].timestamp) > self.max_age_seconds:
                    stale_ids.append(person_id)

            for person_id in stale_ids:
                del self._buffers[person_id]
                self._frame_counts.pop(person_id, None)
                self._last_results.pop(person_id, None)
                removed += 1

        if removed > 0:
            logger.debug(f"Cleaned up {removed} stale skeleton action buffers")
        return removed

    def get_last_result(self, person_id: str) -> SkeletonActionResult | None:
        """Get the most recent action result for a person.

        Args:
            person_id: Tracked person identifier

        Returns:
            Most recent SkeletonActionResult or None
        """
        return self._last_results.get(person_id)

    def get_buffer_status(self) -> dict[str, Any]:
        """Get status of all person buffers.

        Returns:
            Dictionary with buffer statistics
        """
        return {
            "active_persons": len(self._buffers),
            "total_frames_buffered": sum(len(buf) for buf in self._buffers.values()),
            "persons_with_results": len(self._last_results),
        }


# Global service instance
_skeleton_action_service: SkeletonActionService | None = None


def get_skeleton_action_service() -> SkeletonActionService | None:
    """Get the global skeleton action service instance.

    Returns:
        SkeletonActionService if initialized, None otherwise
    """
    return _skeleton_action_service


def set_skeleton_action_service(service: SkeletonActionService) -> None:
    """Set the global skeleton action service instance.

    Args:
        service: SkeletonActionService to use globally
    """
    global _skeleton_action_service  # noqa: PLW0603
    _skeleton_action_service = service


def reset_skeleton_action_service() -> None:
    """Reset the global skeleton action service (for testing)."""
    global _skeleton_action_service  # noqa: PLW0603
    _skeleton_action_service = None
