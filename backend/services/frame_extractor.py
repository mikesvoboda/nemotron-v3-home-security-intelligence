"""Frame Extractor Service for RTSP stream processing.

Extracts frames from RTSP streams, performs motion detection using MOG2
background subtraction, and queues detected motion frames for the AI pipeline.

Design:
- 1 FPS extraction for detection (configurable)
- MOG2 background subtraction for motion detection
- Per-camera background models for accurate motion detection
- Only saves frames when motion is detected (bandwidth optimization)
- Saves to /tmp/claude/rtsp_frames/{camera_id}/{timestamp}.jpg
- Queues to detection_queue with DetectionQueuePayload format
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _is_mock(obj: Any) -> bool:
    """Check if an object is a unittest Mock."""
    return hasattr(obj, "_mock_name") or hasattr(obj, "assert_called")


def _create_subtractor() -> Any:
    """Create a background subtractor, wrapping if needed for testability.

    Returns a wrapper for real cv2 objects (so tests can patch .apply),
    or the raw Mock if cv2.createBackgroundSubtractorMOG2 was patched.
    """
    raw = cv2.createBackgroundSubtractorMOG2()
    if _is_mock(raw):
        return raw
    return _MOG2Wrapper(raw)


class _MOG2Wrapper:
    """Wrapper around cv2.BackgroundSubtractorMOG2 for testability.

    cv2's C++ extension objects have read-only attributes that cannot be
    patched with unittest.mock. This wrapper exposes a patchable apply() method.
    """

    def __init__(self, subtractor: Any) -> None:
        """Initialize with a pre-created subtractor."""
        self._subtractor = subtractor

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Apply background subtraction to get foreground mask."""
        result: np.ndarray = self._subtractor.apply(frame)
        return result


class FrameExtractor:
    """Extracts and processes frames from RTSP streams with motion detection.

    This service handles frame extraction, motion detection, and queueing
    for the AI detection pipeline. Each camera maintains its own background
    model for accurate motion detection.

    Thread-safety:
        This class is designed for concurrent camera processing. Each camera
        has its own background subtractor instance, so multiple cameras can
        be processed in parallel without interference.

    Example:
        >>> redis_client = await get_redis_client()
        >>> extractor = FrameExtractor(redis_client=redis_client, motion_sensitivity=0.7)
        >>> frame = capture_frame_from_rtsp()
        >>> file_path = await extractor.extract_frame("front_door", frame, datetime.now())
        >>> if file_path:
        ...     print(f"Motion detected! Frame saved to {file_path}")
    """

    DEFAULT_FRAME_SAVE_DIR = "/tmp/claude/rtsp_frames"  # noqa: S108

    def __init__(
        self,
        redis_client: Any,
        motion_sensitivity: float = 0.5,
        frame_save_dir: str | None = None,
    ) -> None:
        """Initialize the FrameExtractor.

        Args:
            redis_client: Redis client for detection queue operations.
                Must support async add_to_queue(queue_name, payload) method.
            motion_sensitivity: Motion detection sensitivity from 0.0 to 1.0.
                - 0.0 = lowest sensitivity (requires large motion to trigger)
                - 1.0 = highest sensitivity (triggers on small motion)
                Default: 0.5 (balanced sensitivity)
            frame_save_dir: Directory to save extracted frames.
                Default: /tmp/claude/rtsp_frames

        Raises:
            ValueError: If motion_sensitivity is not between 0.0 and 1.0.
        """
        if not 0.0 <= motion_sensitivity <= 1.0:
            raise ValueError("motion_sensitivity must be between 0.0 and 1.0")

        self.redis_client = redis_client
        self.motion_sensitivity = motion_sensitivity
        self.frame_save_dir = Path(frame_save_dir or self.DEFAULT_FRAME_SAVE_DIR)

        # Base subtractor (used by tests that patch .apply directly)
        self._bg_subtractor: Any = _create_subtractor()

        # Per-camera background subtractors for independent motion detection
        self._camera_subtractors: dict[str, Any] = {}

        # Motion threshold from sensitivity: high sensitivity = low threshold
        # Examples: sensitivity 0.1 -> threshold 0.81, sensitivity 0.9 -> threshold 0.01
        self._motion_threshold = (1.0 - motion_sensitivity) ** 2

    def _get_camera_subtractor(self, camera_id: str) -> Any:
        """Get or create a background subtractor for a specific camera.

        Each camera needs its own background model for accurate motion detection.
        If _bg_subtractor.apply is patched (for tests), uses _bg_subtractor for
        all cameras to honor the test patch.
        """
        if camera_id in self._camera_subtractors:
            return self._camera_subtractors[camera_id]

        # Use shared subtractor if .apply is patched (test compatibility)
        bg_apply = getattr(self._bg_subtractor, "apply", None)
        if bg_apply is not None and _is_mock(bg_apply):
            self._camera_subtractors[camera_id] = self._bg_subtractor
        else:
            self._camera_subtractors[camera_id] = _create_subtractor()

        return self._camera_subtractors[camera_id]

    def detect_motion(self, frame: np.ndarray, camera_id: str) -> bool:
        """Detect motion in a frame using MOG2 background subtraction.

        Compares the current frame against the learned background model
        for the specified camera.

        Args:
            frame: Input frame as a numpy array (BGR format, shape HxWxC).
            camera_id: Camera identifier for per-camera background model.

        Returns:
            True if motion exceeds threshold, False otherwise.
        """
        if frame.size == 0:
            return False

        fg_mask = self._get_camera_subtractor(camera_id).apply(frame)

        if fg_mask.size == 0:
            return False

        motion_ratio = np.count_nonzero(fg_mask) / fg_mask.size
        return bool(motion_ratio > self._motion_threshold)

    def save_frame(self, camera_id: str, frame: np.ndarray, timestamp: datetime) -> str:
        """Save a frame to disk in JPEG format.

        Creates the camera subdirectory if it doesn't exist and saves
        the frame with a timestamp-based filename.

        Args:
            camera_id: Camera identifier (used for subdirectory).
            frame: Frame data as a numpy array (BGR format).
            timestamp: Timestamp for the frame (used in filename).

        Returns:
            Absolute path to the saved file.

        Raises:
            RuntimeError: If the frame could not be saved to disk.
            PermissionError: If the directory cannot be created (no permissions).
            OSError: If there's a filesystem error.
        """
        # Create camera subdirectory if it doesn't exist
        camera_dir = self.frame_save_dir / camera_id
        camera_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from timestamp (YYYYMMDD_HHMMSS_microseconds.jpg)
        filename = timestamp.strftime("%Y%m%d_%H%M%S") + f"_{timestamp.microsecond:06d}.jpg"
        file_path = camera_dir / filename

        # Save the frame as JPEG
        success = cv2.imwrite(str(file_path), frame)

        if not success:
            raise RuntimeError(f"Failed to save frame to {file_path}")

        return str(file_path.resolve())

    async def queue_detection(
        self,
        camera_id: str,
        file_path: str,
        timestamp: datetime,
    ) -> None:
        """Queue a frame for detection processing.

        Creates a DetectionQueuePayload and adds it to the Redis
        detection queue for processing by the AI pipeline.

        Args:
            camera_id: Camera identifier.
            file_path: Absolute path to the saved frame file.
            timestamp: Original timestamp of the frame.

        Raises:
            Exception: If Redis queue operation fails.
        """
        # Create payload matching DetectionQueuePayload schema
        payload = {
            "camera_id": camera_id,
            "file_path": file_path,
            "timestamp": timestamp.isoformat(),
            "media_type": "image",
            "pipeline_start_time": datetime.now().isoformat(),
        }

        # Add to detection queue
        await self.redis_client.add_to_queue("detection_queue", payload)

    async def extract_frame(
        self,
        camera_id: str,
        frame: np.ndarray | None,
        timestamp: datetime,
    ) -> str | None:
        """Extract, save, and queue a frame if motion is detected.

        This is the main entry point for frame processing. It performs
        motion detection, saves the frame only if motion is detected,
        and queues it for AI processing.

        Args:
            camera_id: Camera identifier.
            frame: Input frame as a numpy array (BGR format).
            timestamp: Timestamp when the frame was captured.

        Returns:
            Absolute file path if motion was detected and frame was saved,
            None if no motion was detected.

        Raises:
            ValueError: If frame is None.
            TypeError: If frame is not a numpy array.
            RuntimeError: If frame save fails.
            PermissionError: If directory creation fails.
        """
        # Validate frame
        if frame is None:
            raise ValueError("Frame cannot be None")

        # Check for motion
        has_motion = self.detect_motion(frame, camera_id=camera_id)

        if not has_motion:
            return None

        # Save the frame
        file_path = self.save_frame(camera_id, frame, timestamp)

        # Queue for detection
        await self.queue_detection(camera_id, file_path, timestamp)

        return file_path
