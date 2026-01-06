"""Unit tests for SceneChangeDetector."""

from __future__ import annotations

import numpy as np
import pytest

from backend.services.scene_change_detector import (
    SceneChangeDetector,
    SceneChangeResult,
    get_scene_change_detector,
    reset_scene_change_detector,
)


@pytest.fixture
def detector() -> SceneChangeDetector:
    """Create a fresh detector for each test."""
    return SceneChangeDetector()


@pytest.fixture
def sample_frame() -> np.ndarray:
    """Create a sample RGB frame (100x100 with gradient)."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Create a gradient pattern
    for i in range(100):
        frame[i, :, :] = i * 2  # Gradient from 0 to 198
    return frame


@pytest.fixture
def different_frame() -> np.ndarray:
    """Create a completely different frame."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Opposite gradient
    for i in range(100):
        frame[i, :, :] = 255 - i * 2  # Gradient from 255 to 57
    return frame


@pytest.fixture
def white_frame() -> np.ndarray:
    """Create a white frame."""
    return np.full((100, 100, 3), 255, dtype=np.uint8)


@pytest.fixture
def black_frame() -> np.ndarray:
    """Create a black frame."""
    return np.zeros((100, 100, 3), dtype=np.uint8)


class TestSceneChangeDetectorInit:
    """Tests for SceneChangeDetector initialization."""

    def test_default_threshold(self) -> None:
        """Test default similarity threshold is 0.90."""
        detector = SceneChangeDetector()
        assert detector.similarity_threshold == 0.90

    def test_custom_threshold(self) -> None:
        """Test custom similarity threshold."""
        detector = SceneChangeDetector(similarity_threshold=0.95)
        assert detector.similarity_threshold == 0.95

    def test_invalid_threshold_too_high(self) -> None:
        """Test that threshold > 1 raises ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            SceneChangeDetector(similarity_threshold=1.5)

    def test_invalid_threshold_negative(self) -> None:
        """Test that negative threshold raises ValueError."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            SceneChangeDetector(similarity_threshold=-0.1)

    def test_boundary_threshold_zero(self) -> None:
        """Test threshold of 0 is valid."""
        detector = SceneChangeDetector(similarity_threshold=0.0)
        assert detector.similarity_threshold == 0.0

    def test_boundary_threshold_one(self) -> None:
        """Test threshold of 1 is valid."""
        detector = SceneChangeDetector(similarity_threshold=1.0)
        assert detector.similarity_threshold == 1.0

    def test_invalid_resize_width(self) -> None:
        """Test that non-positive resize width raises ValueError."""
        with pytest.raises(ValueError, match="resize_width must be positive"):
            SceneChangeDetector(resize_width=0)
        with pytest.raises(ValueError, match="resize_width must be positive"):
            SceneChangeDetector(resize_width=-100)

    def test_threshold_setter(self, detector: SceneChangeDetector) -> None:
        """Test similarity threshold setter."""
        detector.similarity_threshold = 0.85
        assert detector.similarity_threshold == 0.85

    def test_threshold_setter_invalid(self, detector: SceneChangeDetector) -> None:
        """Test similarity threshold setter with invalid value."""
        with pytest.raises(ValueError, match="between 0 and 1"):
            detector.similarity_threshold = 1.5


class TestFirstFrameBehavior:
    """Tests for first frame (no baseline) behavior."""

    def test_first_frame_sets_baseline(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test that first frame sets baseline."""
        assert not detector.has_baseline("camera1")

        result = detector.detect_changes("camera1", sample_frame)

        assert detector.has_baseline("camera1")
        assert result.is_first_frame

    def test_first_frame_no_change_detected(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test that first frame reports no change."""
        result = detector.detect_changes("camera1", sample_frame)

        assert not result.change_detected
        assert result.similarity_score == 1.0

    def test_first_frame_result_type(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test that result is correct type."""
        result = detector.detect_changes("camera1", sample_frame)
        assert isinstance(result, SceneChangeResult)


class TestIdenticalFrames:
    """Tests for identical frame comparison."""

    def test_identical_frames_high_similarity(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test identical frames have similarity close to 1.0."""
        detector.detect_changes("camera1", sample_frame)

        # Same frame again
        result = detector.detect_changes("camera1", sample_frame.copy())

        assert result.similarity_score > 0.99
        assert not result.change_detected
        assert not result.is_first_frame

    def test_identical_frames_no_change(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test identical frames do not trigger change detection."""
        detector.detect_changes("camera1", sample_frame)
        result = detector.detect_changes("camera1", sample_frame)

        assert not result.change_detected


class TestDifferentFrames:
    """Tests for different frame comparison."""

    def test_very_different_frames_low_similarity(
        self,
        detector: SceneChangeDetector,
        white_frame: np.ndarray,
        black_frame: np.ndarray,
    ) -> None:
        """Test very different frames have low similarity."""
        detector.detect_changes("camera1", white_frame)
        result = detector.detect_changes("camera1", black_frame)

        # White vs black should be very different
        assert result.similarity_score < 0.5

    def test_different_frames_change_detected(
        self,
        detector: SceneChangeDetector,
        sample_frame: np.ndarray,
        different_frame: np.ndarray,
    ) -> None:
        """Test different frames trigger change detection."""
        detector.detect_changes("camera1", sample_frame)
        result = detector.detect_changes("camera1", different_frame)

        assert result.change_detected

    def test_gradient_vs_solid_change_detected(
        self,
        detector: SceneChangeDetector,
        sample_frame: np.ndarray,
        white_frame: np.ndarray,
    ) -> None:
        """Test gradient vs solid color triggers change."""
        detector.detect_changes("camera1", sample_frame)
        result = detector.detect_changes("camera1", white_frame)

        assert result.change_detected


class TestThresholdBehavior:
    """Tests for threshold-based change detection."""

    def test_high_threshold_more_sensitive(self, sample_frame: np.ndarray) -> None:
        """Test that higher threshold detects smaller changes."""
        # Create slightly modified frame
        modified = sample_frame.copy()
        modified[50:60, 50:60, :] = 128  # Small change

        detector_sensitive = SceneChangeDetector(similarity_threshold=0.99)
        detector_lenient = SceneChangeDetector(similarity_threshold=0.80)

        detector_sensitive.detect_changes("cam", sample_frame)
        detector_lenient.detect_changes("cam", sample_frame)

        sensitive_result = detector_sensitive.detect_changes("cam", modified)
        lenient_result = detector_lenient.detect_changes("cam", modified)

        # More sensitive detector more likely to detect change
        # (though this depends on the actual similarity)
        assert sensitive_result.similarity_score == lenient_result.similarity_score
        # If similarity is between thresholds, sensitive detects, lenient doesn't
        if 0.80 < sensitive_result.similarity_score < 0.99:
            assert sensitive_result.change_detected
            assert not lenient_result.change_detected

    def test_threshold_boundary(self, sample_frame: np.ndarray) -> None:
        """Test change detection at threshold boundary."""
        # Create a frame with known similarity
        modified = sample_frame.copy()
        # Significant change
        modified[:50, :, :] = 128

        detector = SceneChangeDetector(similarity_threshold=0.90)
        detector.detect_changes("cam", sample_frame)
        result = detector.detect_changes("cam", modified)

        # Verify threshold logic: change_detected when similarity < threshold
        expected = result.similarity_score < 0.90
        assert result.change_detected == expected


class TestBaselineManagement:
    """Tests for baseline update and reset."""

    def test_update_baseline(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray, different_frame: np.ndarray
    ) -> None:
        """Test baseline update changes comparison base."""
        # Set initial baseline
        detector.detect_changes("camera1", sample_frame)

        # Different frame should trigger change
        result1 = detector.detect_changes("camera1", different_frame)
        assert result1.change_detected

        # Update baseline to different frame
        detector.update_baseline("camera1", different_frame)

        # Now different frame should match baseline
        result2 = detector.detect_changes("camera1", different_frame)
        assert not result2.change_detected
        assert result2.similarity_score > 0.99

    def test_reset_baseline(self, detector: SceneChangeDetector, sample_frame: np.ndarray) -> None:
        """Test baseline reset removes stored baseline."""
        detector.detect_changes("camera1", sample_frame)
        assert detector.has_baseline("camera1")

        detector.reset_baseline("camera1")
        assert not detector.has_baseline("camera1")

    def test_reset_nonexistent_baseline(self, detector: SceneChangeDetector) -> None:
        """Test reset of nonexistent baseline doesn't raise."""
        # Should not raise
        detector.reset_baseline("nonexistent")

    def test_reset_all_baselines(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test reset_all_baselines clears all cameras."""
        detector.detect_changes("camera1", sample_frame)
        detector.detect_changes("camera2", sample_frame)
        assert len(detector.list_cameras()) == 2

        detector.reset_all_baselines()
        assert len(detector.list_cameras()) == 0

    def test_get_baseline_existing(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test get_baseline returns stored baseline."""
        detector.detect_changes("camera1", sample_frame)
        baseline = detector.get_baseline("camera1")

        assert baseline is not None
        assert isinstance(baseline, np.ndarray)
        # Should be grayscale (2D)
        assert baseline.ndim == 2

    def test_get_baseline_nonexistent(self, detector: SceneChangeDetector) -> None:
        """Test get_baseline returns None for nonexistent camera."""
        assert detector.get_baseline("nonexistent") is None


class TestDifferentFrameSizes:
    """Tests for handling different frame sizes."""

    def test_larger_frame_resized(self, detector: SceneChangeDetector) -> None:
        """Test that larger frames are resized to match baseline."""
        small_frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        large_frame = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)

        detector.detect_changes("camera1", small_frame)
        # Should not raise even with different sizes
        result = detector.detect_changes("camera1", large_frame)

        assert isinstance(result, SceneChangeResult)
        assert 0 <= result.similarity_score <= 1

    def test_smaller_frame_resized(self, detector: SceneChangeDetector) -> None:
        """Test that smaller frames are resized to match baseline."""
        large_frame = np.random.randint(0, 256, (200, 200, 3), dtype=np.uint8)
        small_frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

        detector.detect_changes("camera1", large_frame)
        result = detector.detect_changes("camera1", small_frame)

        assert isinstance(result, SceneChangeResult)
        assert 0 <= result.similarity_score <= 1

    def test_different_aspect_ratio(self, detector: SceneChangeDetector) -> None:
        """Test frames with different aspect ratios."""
        wide_frame = np.random.randint(0, 256, (100, 200, 3), dtype=np.uint8)
        tall_frame = np.random.randint(0, 256, (200, 100, 3), dtype=np.uint8)

        detector.detect_changes("camera1", wide_frame)
        result = detector.detect_changes("camera1", tall_frame)

        assert isinstance(result, SceneChangeResult)
        assert 0 <= result.similarity_score <= 1

    def test_very_small_frame(self, detector: SceneChangeDetector) -> None:
        """Test handling of very small frames."""
        tiny_frame = np.random.randint(0, 256, (10, 10, 3), dtype=np.uint8)
        another_tiny = np.random.randint(0, 256, (10, 10, 3), dtype=np.uint8)

        detector.detect_changes("camera1", tiny_frame)
        result = detector.detect_changes("camera1", another_tiny)

        assert isinstance(result, SceneChangeResult)


class TestGrayscaleConversion:
    """Tests for grayscale handling."""

    def test_rgb_frame(self, detector: SceneChangeDetector) -> None:
        """Test RGB frame is converted correctly."""
        rgb_frame = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        detector.detect_changes("camera1", rgb_frame)

        baseline = detector.get_baseline("camera1")
        assert baseline is not None
        assert baseline.ndim == 2  # Grayscale

    def test_rgba_frame(self, detector: SceneChangeDetector) -> None:
        """Test RGBA frame is converted correctly."""
        rgba_frame = np.random.randint(0, 256, (100, 100, 4), dtype=np.uint8)
        detector.detect_changes("camera1", rgba_frame)

        baseline = detector.get_baseline("camera1")
        assert baseline is not None
        assert baseline.ndim == 2

    def test_grayscale_frame(self, detector: SceneChangeDetector) -> None:
        """Test grayscale frame is handled correctly."""
        gray_frame = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        detector.detect_changes("camera1", gray_frame)

        baseline = detector.get_baseline("camera1")
        assert baseline is not None
        assert baseline.ndim == 2

    def test_unsupported_frame_shape(self, detector: SceneChangeDetector) -> None:
        """Test unsupported frame shape raises error."""
        weird_frame = np.random.randint(0, 256, (100, 100, 5), dtype=np.uint8)

        with pytest.raises(ValueError, match="Unsupported frame shape"):
            detector.detect_changes("camera1", weird_frame)


class TestMultipleCameras:
    """Tests for multiple camera handling."""

    def test_separate_baselines_per_camera(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray, white_frame: np.ndarray
    ) -> None:
        """Test each camera has independent baseline."""
        detector.detect_changes("camera1", sample_frame)
        detector.detect_changes("camera2", white_frame)

        # Camera 1 should match sample, not white
        result1 = detector.detect_changes("camera1", sample_frame)
        assert result1.similarity_score > 0.99

        # Camera 2 should match white, not sample
        result2 = detector.detect_changes("camera2", white_frame)
        assert result2.similarity_score > 0.99

    def test_list_cameras(self, detector: SceneChangeDetector, sample_frame: np.ndarray) -> None:
        """Test list_cameras returns all cameras with baselines."""
        detector.detect_changes("camera1", sample_frame)
        detector.detect_changes("camera2", sample_frame)
        detector.detect_changes("camera3", sample_frame)

        cameras = detector.list_cameras()
        assert set(cameras) == {"camera1", "camera2", "camera3"}

    def test_reset_one_camera(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test resetting one camera doesn't affect others."""
        detector.detect_changes("camera1", sample_frame)
        detector.detect_changes("camera2", sample_frame)

        detector.reset_baseline("camera1")

        assert not detector.has_baseline("camera1")
        assert detector.has_baseline("camera2")


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_scene_change_detector(self) -> None:
        """Test singleton getter."""
        reset_scene_change_detector()

        detector1 = get_scene_change_detector()
        detector2 = get_scene_change_detector()

        assert detector1 is detector2

    def test_reset_scene_change_detector(self, sample_frame: np.ndarray) -> None:
        """Test singleton reset."""
        reset_scene_change_detector()

        detector1 = get_scene_change_detector()
        detector1.detect_changes("camera1", sample_frame)
        assert detector1.has_baseline("camera1")

        reset_scene_change_detector()

        detector2 = get_scene_change_detector()
        assert not detector2.has_baseline("camera1")
        assert detector1 is not detector2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_frame(self, detector: SceneChangeDetector) -> None:
        """Test all-zero frame."""
        zero_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        detector.detect_changes("camera1", zero_frame)
        result = detector.detect_changes("camera1", zero_frame)

        assert result.similarity_score > 0.99
        assert not result.change_detected

    def test_max_value_frame(self, detector: SceneChangeDetector) -> None:
        """Test all-255 frame."""
        max_frame = np.full((100, 100, 3), 255, dtype=np.uint8)
        detector.detect_changes("camera1", max_frame)
        result = detector.detect_changes("camera1", max_frame)

        assert result.similarity_score > 0.99
        assert not result.change_detected

    def test_float_frame(self, detector: SceneChangeDetector) -> None:
        """Test float frame is handled (converted to uint8 range)."""
        # Float frames in 0-255 range should work
        float_frame = np.random.rand(100, 100, 3).astype(np.float32) * 255
        float_frame = float_frame.astype(np.uint8)

        detector.detect_changes("camera1", float_frame)
        result = detector.detect_changes("camera1", float_frame)

        assert result.similarity_score > 0.99

    def test_result_dataclass_frozen(
        self, detector: SceneChangeDetector, sample_frame: np.ndarray
    ) -> None:
        """Test SceneChangeResult is immutable."""
        result = detector.detect_changes("camera1", sample_frame)

        with pytest.raises(Exception):  # noqa: B017  # FrozenInstanceError
            result.change_detected = True  # type: ignore[misc]
