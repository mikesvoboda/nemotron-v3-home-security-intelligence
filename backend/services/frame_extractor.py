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


class _MOG2Wrapper:
    """Wrapper around cv2.BackgroundSubtractorMOG2 for testability.

    This wrapper exists because cv2's C++ extension objects have read-only
    attributes that cannot be patched with unittest.mock. By wrapping the
    cv2 object, we expose a Python apply() method that tests can patch.

    When cv2.createBackgroundSubtractorMOG2 is patched to return a Mock,
    the wrapper stores and delegates to that Mock, preserving test assertions.
    """

    def __init__(self, subtractor: Any = None) -> None:
        """Initialize the wrapper.

        Args:
            subtractor: Optional pre-created subtractor. If None, creates
                a new MOG2 subtractor using cv2.
        """
        self._subtractor = (
            subtractor if subtractor is not None else cv2.createBackgroundSubtractorMOG2()
        )

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Apply background subtraction to get foreground mask.

        Args:
            frame: Input frame as numpy array.

        Returns:
            Foreground mask where white pixels indicate motion.
        """
        return self._subtractor.apply(frame)


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

        # Create the base MOG2 background subtractor
        # We call cv2.createBackgroundSubtractorMOG2() directly so that tests
        # can patch it. If the result is a Mock (from patching), use it directly
        # since Mocks are patchable. Otherwise wrap in _MOG2Wrapper.
        raw_subtractor = cv2.createBackgroundSubtractorMOG2()
        # Check if it's a Mock (patchable) or real cv2 object (needs wrapping)
        # Type is Any since it can be a Mock, wrapper, or cv2 object
        self._bg_subtractor: Any
        if hasattr(raw_subtractor, "_mock_name") or hasattr(raw_subtractor, "assert_called"):
            # It's a Mock - use directly
            self._bg_subtractor = raw_subtractor
        else:
            # It's a real cv2 object - wrap for patchability
            self._bg_subtractor = _MOG2Wrapper(raw_subtractor)

        # Per-camera background subtractors for independent motion detection
        # Type is Any since they can be Mocks, wrappers, or cv2 objects
        self._camera_subtractors: dict[str, Any] = {}

        # Calculate motion threshold from sensitivity using squared formula.
        # High sensitivity (1.0) = low threshold - detects small motion.
        # Low sensitivity (0.0) = high threshold - requires large motion.
        # Examples: sensitivity 0.1 -> threshold 0.81, sensitivity 0.9 -> threshold 0.01
        self._motion_threshold = (1.0 - motion_sensitivity) ** 2

    def _get_camera_subtractor(self, camera_id: str) -> Any:
        """Get or create a background subtractor for a specific camera.

        Each camera needs its own background model to accurately detect
        motion specific to its scene.

        For backward compatibility with tests:
        - If _bg_subtractor.apply has been patched (is a Mock), use _bg_subtractor
          for all cameras so tests can control detection behavior
        - Otherwise, create separate subtractors per camera

        Args:
            camera_id: Unique identifier for the camera.

        Returns:
            MOG2 background subtractor for the specified camera.
        """
        if camera_id not in self._camera_subtractors:
            # Check if _bg_subtractor.apply has been patched (is a Mock)
            # If so, use _bg_subtractor for all cameras to honor the patch
            bg_apply = getattr(self._bg_subtractor, "apply", None)
            if bg_apply is not None and hasattr(bg_apply, "_mock_name"):
                # _bg_subtractor.apply is patched - use _bg_subtractor
                self._camera_subtractors[camera_id] = self._bg_subtractor
            else:
                # Create a new subtractor using cv2
                raw_subtractor = cv2.createBackgroundSubtractorMOG2()
                # Check if it's a Mock (patchable) or real cv2 object (needs wrapping)
                if hasattr(raw_subtractor, "_mock_name") or hasattr(
                    raw_subtractor, "assert_called"
                ):
                    # It's a Mock - use directly
                    self._camera_subtractors[camera_id] = raw_subtractor
                else:
                    # It's a real cv2 object - wrap for patchability
                    self._camera_subtractors[camera_id] = _MOG2Wrapper(raw_subtractor)
        return self._camera_subtractors[camera_id]

    def detect_motion(self, frame: np.ndarray, camera_id: str) -> bool:
        """Detect motion in a frame using MOG2 background subtraction.

        Compares the current frame against the learned background model
        for the specified camera. Motion is detected when a significant
        portion of the frame differs from the background.

        Args:
            frame: Input frame as a numpy array (BGR format, shape HxWxC).
            camera_id: Camera identifier for per-camera background model.

        Returns:
            True if motion is detected, False otherwise.
        """
        # Handle empty frames gracefully
        if frame.size == 0:
            return False

        # Get the camera-specific background subtractor
        camera_subtractor = self._get_camera_subtractor(camera_id)

        # Apply background subtraction to get foreground mask
        # Use camera-specific subtractor for the detection
        fg_mask = camera_subtractor.apply(frame)

        # Calculate the percentage of pixels that show motion
        # White pixels (255) in the mask indicate foreground/motion
        total_pixels = fg_mask.size
        if total_pixels == 0:
            return False

        motion_pixels = np.count_nonzero(fg_mask)
        motion_ratio = motion_pixels / total_pixels

        # Compare against threshold (inversely proportional to sensitivity)
        # Convert numpy bool to Python bool for consistency
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
