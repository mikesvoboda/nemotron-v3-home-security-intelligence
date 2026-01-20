"""Frame buffer service for X-CLIP temporal action recognition.

This module provides the FrameBuffer service that stores recent frames per camera
for temporal action recognition with X-CLIP. X-CLIP needs sequences of frames
(typically 8 frames) to recognize actions like:
- loitering, approaching_door, running_away
- checking_car_doors, suspicious_behavior
- breaking_in, vandalism

The buffer automatically evicts frames that are too old or when capacity is exceeded.
"""

from __future__ import annotations

__all__ = [
    "FrameBuffer",
    "FrameData",
    "get_frame_buffer",
    "reset_frame_buffer",
]

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from backend.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class FrameData:
    """Container for a single frame with timestamp.

    Attributes:
        frame: Raw frame data as bytes (e.g., JPEG or PNG encoded)
        timestamp: When the frame was captured (timezone-aware datetime)
    """

    frame: bytes
    timestamp: datetime


class FrameBuffer:
    """Buffer for storing recent frames per camera for temporal analysis.

    This service maintains per-camera circular buffers of recent frames,
    enabling temporal action recognition with X-CLIP. The buffer handles:
    - Per-camera frame storage with configurable capacity
    - Automatic eviction of frames older than max_age_seconds
    - Even sampling of frames for X-CLIP (which expects 8 frames)
    - Thread-safe concurrent access

    Attributes:
        buffer_size: Maximum number of frames to store per camera
        max_age_seconds: Maximum age of frames in seconds before eviction

    Example:
        >>> buffer = FrameBuffer(buffer_size=16, max_age_seconds=30.0)
        >>> await buffer.add_frame("camera_1", frame_bytes, datetime.now(UTC))
        >>> frames = buffer.get_sequence("camera_1", num_frames=8)
        >>> if frames:
        ...     action_result = await classify_actions(model, frames)
    """

    def __init__(self, buffer_size: int = 16, max_age_seconds: float = 30.0) -> None:
        """Initialize the FrameBuffer.

        Args:
            buffer_size: Maximum number of frames to store per camera (default 16)
            max_age_seconds: Maximum age in seconds before frames are evicted (default 30.0)
        """
        self.buffer_size = buffer_size
        self.max_age_seconds = max_age_seconds
        self._buffers: dict[str, deque[FrameData]] = {}
        self._lock = asyncio.Lock()

    @property
    def camera_count(self) -> int:
        """Return the number of cameras with active buffers."""
        return len(self._buffers)

    def frame_count(self, camera_id: str) -> int:
        """Return the number of frames buffered for a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            Number of frames in the buffer, or 0 if camera has no buffer
        """
        buffer = self._buffers.get(camera_id)
        return len(buffer) if buffer else 0

    def has_enough_frames(self, camera_id: str, min_frames: int = 8) -> bool:
        """Check if the buffer has enough frames for action recognition.

        Args:
            camera_id: Camera identifier
            min_frames: Minimum number of frames required (default 8)

        Returns:
            True if buffer has at least min_frames frames
        """
        return self.frame_count(camera_id) >= min_frames

    def get_camera_ids(self) -> list[str]:
        """Return list of all camera IDs with active buffers.

        Returns:
            List of camera ID strings
        """
        return list(self._buffers.keys())

    async def add_frame(self, camera_id: str, frame: bytes, timestamp: datetime) -> None:
        """Add a frame to the buffer for a camera.

        This method:
        1. Creates a buffer for the camera if it doesn't exist
        2. Evicts frames older than max_age_seconds
        3. Adds the new frame (oldest frames are evicted if at capacity)

        The eviction is performed based on the timestamp parameter, so frames
        older than (timestamp - max_age_seconds) are removed.

        Args:
            camera_id: Camera identifier
            frame: Raw frame data as bytes
            timestamp: When the frame was captured (should be timezone-aware)
        """
        async with self._lock:
            # Create buffer if needed
            if camera_id not in self._buffers:
                self._buffers[camera_id] = deque(maxlen=self.buffer_size)
                logger.debug(f"Created frame buffer for camera {camera_id}")

            buffer = self._buffers[camera_id]

            # Evict frames older than max_age
            cutoff = timestamp - timedelta(seconds=self.max_age_seconds)
            while buffer and buffer[0].timestamp < cutoff:
                buffer.popleft()

            # Add new frame (deque maxlen handles capacity eviction)
            buffer.append(FrameData(frame=frame, timestamp=timestamp))

    def get_sequence(self, camera_id: str, num_frames: int = 8) -> list[bytes] | None:
        """Get a sequence of frames for X-CLIP analysis.

        Samples frames evenly across the buffer to get the requested number
        of frames. If the buffer has fewer frames than requested, returns None.

        X-CLIP works best with 8 frames spanning the action. This method
        samples uniformly to capture the temporal progression.

        Args:
            camera_id: Camera identifier
            num_frames: Number of frames to return (default 8)

        Returns:
            List of frame bytes evenly sampled from buffer, or None if
            the buffer has fewer than num_frames frames
        """
        buffer = self._buffers.get(camera_id)
        if not buffer or len(buffer) < num_frames:
            return None

        # Sample evenly across buffer using numpy linspace
        indices = np.linspace(0, len(buffer) - 1, num_frames, dtype=int)
        return [buffer[i].frame for i in indices]

    def clear(self, camera_id: str | None = None) -> None:
        """Clear frame buffer(s).

        Args:
            camera_id: Camera identifier to clear, or None to clear all
        """
        if camera_id is not None:
            if camera_id in self._buffers:
                del self._buffers[camera_id]
                logger.debug(f"Cleared frame buffer for camera {camera_id}")
        else:
            self._buffers.clear()
            logger.debug("Cleared all frame buffers")


# Module-level singleton container (avoids PLW0603 global statement warnings)
_singleton: dict[str, FrameBuffer | None] = {"instance": None}


def get_frame_buffer(buffer_size: int = 16, max_age_seconds: float = 30.0) -> FrameBuffer:
    """Get the global FrameBuffer singleton instance.

    Creates the instance on first call with the specified parameters.
    Subsequent calls return the same instance (parameters are ignored).

    Args:
        buffer_size: Maximum frames per camera (default 16)
        max_age_seconds: Maximum frame age in seconds (default 30.0)

    Returns:
        The global FrameBuffer instance
    """
    instance = _singleton["instance"]
    if instance is None:
        instance = FrameBuffer(buffer_size=buffer_size, max_age_seconds=max_age_seconds)
        _singleton["instance"] = instance
        logger.info(
            f"Initialized global FrameBuffer: buffer_size={buffer_size}, "
            f"max_age_seconds={max_age_seconds}"
        )
    return instance


def reset_frame_buffer() -> None:
    """Reset the global FrameBuffer singleton (for testing)."""
    if _singleton["instance"] is not None:
        _singleton["instance"].clear()
        _singleton["instance"] = None
        logger.debug("Reset global FrameBuffer")
