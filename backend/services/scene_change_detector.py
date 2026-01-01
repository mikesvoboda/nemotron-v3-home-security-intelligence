"""Scene change detection using Structural Similarity Index (SSIM).

This module provides CPU-based scene change detection that compares current
frames against stored baselines to identify significant visual changes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim


@dataclass(frozen=True, slots=True)
class SceneChangeResult:
    """Result of a scene change detection comparison.

    Attributes:
        change_detected: True if the scene has changed significantly.
        similarity_score: SSIM score between 0 and 1 (1 = identical).
        is_first_frame: True if this was the first frame for this camera.
    """

    change_detected: bool
    similarity_score: float
    is_first_frame: bool = False


class SceneChangeDetector:
    """Detects scene changes by comparing frames to stored baselines using SSIM.

    The detector maintains a baseline image per camera. When a new frame arrives,
    it computes the Structural Similarity Index (SSIM) between the frame and the
    baseline. If similarity drops below the threshold, a scene change is detected.

    Attributes:
        similarity_threshold: SSIM threshold below which changes are detected.
            Default 0.90 means >10% visual difference triggers detection.
    """

    DEFAULT_THRESHOLD: float = 0.90
    DEFAULT_RESIZE_WIDTH: int = 640

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_THRESHOLD,
        resize_width: int = DEFAULT_RESIZE_WIDTH,
    ) -> None:
        """Initialize the scene change detector.

        Args:
            similarity_threshold: SSIM threshold (0-1). Frames with similarity
                below this value are considered changed. Default is 0.90.
            resize_width: Width to resize frames to for comparison. Smaller
                sizes are faster but less accurate. Default is 640.
        """
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if resize_width <= 0:
            raise ValueError("resize_width must be positive")

        self._threshold = similarity_threshold
        self._resize_width = resize_width
        self._baselines: dict[str, np.ndarray] = {}

    @property
    def similarity_threshold(self) -> float:
        """Get the current similarity threshold."""
        return self._threshold

    @similarity_threshold.setter
    def similarity_threshold(self, value: float) -> None:
        """Set the similarity threshold."""
        if not 0 <= value <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        self._threshold = value

    def _to_grayscale(self, frame: np.ndarray) -> np.ndarray:
        """Convert frame to grayscale if needed.

        Args:
            frame: Input image (grayscale, RGB, or RGBA).

        Returns:
            Grayscale image as 2D numpy array.
        """
        if frame.ndim == 2:
            # Already grayscale
            return frame
        if frame.ndim == 3:
            if frame.shape[2] == 3:
                # RGB to grayscale using PIL
                img = Image.fromarray(frame, mode="RGB")
                gray_img = img.convert("L")
                return np.array(gray_img)
            if frame.shape[2] == 4:
                # RGBA to grayscale using PIL
                img = Image.fromarray(frame, mode="RGBA")
                gray_img = img.convert("L")
                return np.array(gray_img)
        raise ValueError(f"Unsupported frame shape: {frame.shape}")

    def _resize_frame(
        self, frame: np.ndarray, target_size: tuple[int, int] | None = None
    ) -> np.ndarray:
        """Resize frame to target size or default width maintaining aspect ratio.

        Args:
            frame: Input grayscale image (2D array).
            target_size: Optional exact (width, height) to resize to. If None,
                resizes to default width maintaining aspect ratio.

        Returns:
            Resized grayscale image.
        """
        h, w = frame.shape[:2]

        if target_size is not None:
            target_w, target_h = target_size
            img = Image.fromarray(frame, mode="L")
            resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            return np.array(resized)

        if w <= self._resize_width:
            return frame

        scale = self._resize_width / w
        new_h = int(h * scale)
        img = Image.fromarray(frame, mode="L")
        resized = img.resize((self._resize_width, new_h), Image.Resampling.LANCZOS)
        return np.array(resized)

    def _prepare_frame(
        self, frame: np.ndarray, target_size: tuple[int, int] | None = None
    ) -> np.ndarray:
        """Convert frame to grayscale and resize for comparison.

        Args:
            frame: Input image (any format).
            target_size: Optional exact size to resize to.

        Returns:
            Prepared grayscale image ready for SSIM comparison.
        """
        gray = self._to_grayscale(frame)
        return self._resize_frame(gray, target_size)

    def detect_changes(self, camera_id: str, current_frame: np.ndarray) -> SceneChangeResult:
        """Compare current frame to baseline and detect changes.

        If no baseline exists for this camera, the current frame becomes the
        baseline and no change is detected (first frame behavior).

        Args:
            camera_id: Unique identifier for the camera.
            current_frame: Current frame as numpy array (RGB, RGBA, or grayscale).

        Returns:
            SceneChangeResult with change detection status and similarity score.
        """
        if camera_id not in self._baselines:
            # First frame - set as baseline, no change detected
            prepared = self._prepare_frame(current_frame)
            self._baselines[camera_id] = prepared
            return SceneChangeResult(
                change_detected=False,
                similarity_score=1.0,
                is_first_frame=True,
            )

        baseline = self._baselines[camera_id]
        baseline_h, baseline_w = baseline.shape[:2]

        # Prepare current frame to match baseline size
        prepared = self._prepare_frame(current_frame, target_size=(baseline_w, baseline_h))

        # Compute SSIM
        # win_size must be odd and <= min(height, width)
        min_dim = min(baseline_h, baseline_w)
        # Default win_size is 7, but must be <= image dimensions
        win_size = min(7, min_dim)
        # win_size must be odd
        if win_size % 2 == 0:
            win_size -= 1
        win_size = max(win_size, 3)

        similarity = ssim(baseline, prepared, win_size=win_size, data_range=255)

        return SceneChangeResult(
            change_detected=similarity < self._threshold,
            similarity_score=float(similarity),
            is_first_frame=False,
        )

    def update_baseline(self, camera_id: str, frame: np.ndarray) -> None:
        """Update the baseline image for a camera.

        Call this when you want to reset what "normal" looks like for a camera,
        such as after a legitimate scene change has been acknowledged.

        Args:
            camera_id: Unique identifier for the camera.
            frame: New baseline image.
        """
        self._baselines[camera_id] = self._prepare_frame(frame)

    def reset_baseline(self, camera_id: str) -> None:
        """Remove the baseline for a camera.

        The next frame for this camera will become the new baseline.

        Args:
            camera_id: Unique identifier for the camera.
        """
        self._baselines.pop(camera_id, None)

    def reset_all_baselines(self) -> None:
        """Remove all stored baselines."""
        self._baselines.clear()

    def get_baseline(self, camera_id: str) -> np.ndarray | None:
        """Get the current baseline for a camera.

        Args:
            camera_id: Unique identifier for the camera.

        Returns:
            The stored baseline image or None if no baseline exists.
        """
        return self._baselines.get(camera_id)

    def has_baseline(self, camera_id: str) -> bool:
        """Check if a baseline exists for a camera.

        Args:
            camera_id: Unique identifier for the camera.

        Returns:
            True if a baseline exists, False otherwise.
        """
        return camera_id in self._baselines

    def list_cameras(self) -> list[str]:
        """List all camera IDs with stored baselines.

        Returns:
            List of camera IDs.
        """
        return list(self._baselines.keys())


# Module-level singleton for convenience
_scene_change_detector: SceneChangeDetector | None = None


def get_scene_change_detector() -> SceneChangeDetector:
    """Get the global scene change detector singleton.

    Returns:
        The singleton SceneChangeDetector instance.
    """
    global _scene_change_detector  # noqa: PLW0603
    if _scene_change_detector is None:
        _scene_change_detector = SceneChangeDetector()
    return _scene_change_detector


def reset_scene_change_detector() -> None:
    """Reset the global scene change detector singleton.

    Useful for testing or when you need to reconfigure the detector.
    """
    global _scene_change_detector  # noqa: PLW0603
    _scene_change_detector = None
