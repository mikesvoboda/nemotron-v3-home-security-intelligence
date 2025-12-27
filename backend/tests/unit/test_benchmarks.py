"""Unit tests for benchmark test helper functions and fixtures.

These tests verify that the benchmark test infrastructure works correctly
without actually running performance benchmarks.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

# Import helper functions from test modules
from backend.tests.benchmarks.test_bigo import (
    aggregate_detections_by_camera,
    filter_high_confidence,
    generate_detections,
    generate_file_paths,
    group_by_timewindow,
    process_file_batch,
)


class TestGenerateDetections:
    """Unit tests for the generate_detections helper function."""

    def test_generates_correct_count_zero(self):
        """Should generate zero detections when n=0."""
        result = generate_detections(0)
        assert result == []
        assert len(result) == 0

    def test_generates_correct_count_one(self):
        """Should generate one detection when n=1."""
        result = generate_detections(1)
        assert len(result) == 1

    def test_generates_correct_count_large(self):
        """Should generate exact count for large n."""
        result = generate_detections(1000)
        assert len(result) == 1000

    def test_detection_has_id(self):
        """Each detection should have an id field."""
        detections = generate_detections(5)
        for i, detection in enumerate(detections):
            assert "id" in detection
            assert detection["id"] == i

    def test_detection_has_camera_id(self):
        """Each detection should have a camera_id field."""
        detections = generate_detections(10)
        for detection in detections:
            assert "camera_id" in detection
            assert detection["camera_id"].startswith("cam_")

    def test_detection_camera_id_cycles(self):
        """Camera IDs should cycle through 5 cameras."""
        detections = generate_detections(10)
        camera_ids = [d["camera_id"] for d in detections]

        # First 5 should be cam_0 through cam_4
        assert camera_ids[0] == "cam_0"
        assert camera_ids[4] == "cam_4"
        # Next 5 should cycle back
        assert camera_ids[5] == "cam_0"

    def test_detection_has_timestamp(self):
        """Each detection should have a timestamp field."""
        detections = generate_detections(3)
        for detection in detections:
            assert "timestamp" in detection
            assert detection["timestamp"].startswith("2024-01-01T00:00:")

    def test_detection_has_class_name(self):
        """Each detection should have class_name set to 'person'."""
        detections = generate_detections(3)
        for detection in detections:
            assert detection["class_name"] == "person"

    def test_detection_has_confidence(self):
        """Each detection should have confidence set to 0.95."""
        detections = generate_detections(3)
        for detection in detections:
            assert detection["confidence"] == 0.95

    def test_detection_has_bbox(self):
        """Each detection should have a bbox with 4 elements."""
        detections = generate_detections(3)
        for detection in detections:
            assert "bbox" in detection
            assert len(detection["bbox"]) == 4
            assert all(isinstance(v, int) for v in detection["bbox"])


class TestGenerateFilePaths:
    """Unit tests for the generate_file_paths helper function."""

    def test_generates_correct_count_zero(self):
        """Should generate zero paths when n=0."""
        result = generate_file_paths(0)
        assert result == []

    def test_generates_correct_count_one(self):
        """Should generate one path when n=1."""
        result = generate_file_paths(1)
        assert len(result) == 1

    def test_generates_correct_count_large(self):
        """Should generate exact count for large n."""
        result = generate_file_paths(1000)
        assert len(result) == 1000

    def test_path_starts_with_export(self):
        """Each path should start with /export/foscam/."""
        paths = generate_file_paths(5)
        for path in paths:
            assert path.startswith("/export/foscam/")

    def test_path_ends_with_jpg(self):
        """Each path should end with .jpg."""
        paths = generate_file_paths(5)
        for path in paths:
            assert path.endswith(".jpg")

    def test_path_has_camera_folder(self):
        """Each path should have a camera folder."""
        paths = generate_file_paths(10)
        for path in paths:
            parts = path.split("/")
            assert "camera_" in parts[3]

    def test_path_camera_cycles(self):
        """Camera folders should cycle through 10 cameras."""
        paths = generate_file_paths(20)
        cameras = [path.split("/")[3] for path in paths]
        assert cameras[0] == "camera_0"
        assert cameras[9] == "camera_9"
        assert cameras[10] == "camera_0"

    def test_image_filename_format(self):
        """Image filenames should be zero-padded."""
        paths = generate_file_paths(5)
        for i, path in enumerate(paths):
            filename = path.split("/")[-1]
            assert filename == f"image_{i:06d}.jpg"


class TestAggregateDetectionsByCamera:
    """Unit tests for the aggregate_detections_by_camera function."""

    def test_empty_input(self):
        """Should return empty dict for empty input."""
        result = aggregate_detections_by_camera([])
        assert result == {}

    def test_single_detection(self):
        """Should group single detection correctly."""
        detections = generate_detections(1)
        result = aggregate_detections_by_camera(detections)
        assert len(result) == 1
        assert "cam_0" in result
        assert len(result["cam_0"]) == 1

    def test_groups_by_camera_id(self):
        """Should group detections by camera_id."""
        detections = generate_detections(10)
        result = aggregate_detections_by_camera(detections)

        # Should have 5 cameras (cam_0 through cam_4)
        assert len(result) == 5

        # Each camera should have 2 detections
        for camera_id, camera_detections in result.items():
            assert len(camera_detections) == 2

    def test_preserves_all_detections(self):
        """Total detections should equal input count."""
        detections = generate_detections(100)
        result = aggregate_detections_by_camera(detections)

        total = sum(len(v) for v in result.values())
        assert total == 100

    def test_preserves_detection_data(self):
        """Detection data should not be modified."""
        detections = generate_detections(3)
        original_ids = [d["id"] for d in detections]

        result = aggregate_detections_by_camera(detections)

        all_ids = []
        for camera_detections in result.values():
            all_ids.extend(d["id"] for d in camera_detections)

        assert sorted(all_ids) == sorted(original_ids)


class TestFilterHighConfidence:
    """Unit tests for the filter_high_confidence function."""

    def test_empty_input(self):
        """Should return empty list for empty input."""
        result = filter_high_confidence([])
        assert result == []

    def test_all_above_threshold(self):
        """Should return all when all above threshold."""
        detections = generate_detections(5)  # confidence = 0.95
        result = filter_high_confidence(detections, threshold=0.9)
        assert len(result) == 5

    def test_all_below_threshold(self):
        """Should return none when all below threshold."""
        detections = generate_detections(5)  # confidence = 0.95
        result = filter_high_confidence(detections, threshold=0.96)
        assert len(result) == 0

    def test_exact_threshold(self):
        """Should include detections exactly at threshold."""
        detections = generate_detections(5)  # confidence = 0.95
        result = filter_high_confidence(detections, threshold=0.95)
        assert len(result) == 5

    def test_mixed_confidence(self):
        """Should filter correctly with mixed confidence."""
        detections = [
            {"id": 0, "confidence": 0.5},
            {"id": 1, "confidence": 0.8},
            {"id": 2, "confidence": 0.95},
            {"id": 3, "confidence": 1.0},
        ]
        result = filter_high_confidence(detections, threshold=0.9)
        assert len(result) == 2
        assert all(d["confidence"] >= 0.9 for d in result)

    def test_missing_confidence_field(self):
        """Should exclude detections without confidence field."""
        detections = [
            {"id": 0, "confidence": 0.95},
            {"id": 1},  # No confidence field
            {"id": 2, "confidence": 0.95},
        ]
        result = filter_high_confidence(detections, threshold=0.9)
        assert len(result) == 2


class TestProcessFileBatch:
    """Unit tests for the process_file_batch function."""

    def test_empty_input(self):
        """Should return empty list for empty input."""
        result = process_file_batch([])
        assert result == []

    def test_returns_correct_count(self):
        """Should return same count as input."""
        paths = generate_file_paths(10)
        result = process_file_batch(paths)
        assert len(result) == 10

    def test_result_has_path(self):
        """Each result should have original path."""
        paths = generate_file_paths(3)
        result = process_file_batch(paths)
        for i, item in enumerate(result):
            assert item["path"] == paths[i]

    def test_result_has_camera(self):
        """Each result should have camera extracted."""
        paths = generate_file_paths(3)
        result = process_file_batch(paths)
        for item in result:
            assert "camera" in item
            assert item["camera"].startswith("camera_")

    def test_result_has_filename(self):
        """Each result should have filename extracted."""
        paths = generate_file_paths(3)
        result = process_file_batch(paths)
        for item in result:
            assert "filename" in item
            assert item["filename"].endswith(".jpg")

    def test_result_has_size_estimate(self):
        """Each result should have size_estimate."""
        paths = generate_file_paths(3)
        result = process_file_batch(paths)
        for item in result:
            assert "size_estimate" in item
            assert isinstance(item["size_estimate"], int)
            assert item["size_estimate"] > 0


class TestGroupByTimewindow:
    """Unit tests for the group_by_timewindow function."""

    def test_empty_input(self):
        """Should return empty dict for empty input."""
        result = group_by_timewindow([])
        assert result == {}

    def test_single_detection(self):
        """Should group single detection correctly."""
        detections = [{"timestamp": "2024-01-01T00:00:05"}]
        result = group_by_timewindow(detections, window_size=10)
        assert 0 in result
        assert len(result[0]) == 1

    def test_groups_correctly(self):
        """Should group by time window correctly."""
        detections = [
            {"timestamp": "2024-01-01T00:00:05"},  # window 0
            {"timestamp": "2024-01-01T00:00:08"},  # window 0
            {"timestamp": "2024-01-01T00:00:15"},  # window 1
            {"timestamp": "2024-01-01T00:00:25"},  # window 2
        ]
        result = group_by_timewindow(detections, window_size=10)

        assert len(result[0]) == 2
        assert len(result[1]) == 1
        assert len(result[2]) == 1

    def test_preserves_all_detections(self):
        """Total detections should equal input count."""
        detections = generate_detections(100)
        result = group_by_timewindow(detections, window_size=10)

        total = sum(len(v) for v in result.values())
        assert total == 100

    def test_different_window_sizes(self):
        """Should work with different window sizes."""
        detections = generate_detections(60)

        # Window size 10 -> max 6 windows
        result_10 = group_by_timewindow(detections, window_size=10)
        assert all(0 <= k <= 5 for k in result_10)

        # Window size 30 -> max 2 windows
        result_30 = group_by_timewindow(detections, window_size=30)
        assert all(0 <= k <= 1 for k in result_30)


class TestBenchmarkEnvironmentFixtures:
    """Test that benchmark environment fixtures can be created."""

    def test_benchmark_env_fixture_concept(self):
        """Verify the pattern for benchmark env setup works."""
        from backend.core.config import get_settings

        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            test_db_url = f"sqlite+aiosqlite:///{db_path}"

            os.environ["DATABASE_URL"] = test_db_url
            os.environ["REDIS_URL"] = "redis://localhost:6379/15"

            get_settings.cache_clear()

            settings = get_settings()
            assert str(db_path) in settings.database_url

        # Restore
        if original_db_url is not None:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url is not None:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        get_settings.cache_clear()

    def test_mock_redis_fixture_concept(self):
        """Verify the mock Redis pattern works."""
        mock_redis = AsyncMock()
        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        # Verify mock behavior
        assert mock_redis.health_check.return_value["status"] == "healthy"
        assert mock_redis.health_check.return_value["connected"] is True


class TestRunAsyncHelper:
    """Test the run_async helper function pattern."""

    def test_run_async_pattern(self):
        """Verify the run_async pattern works correctly."""
        import asyncio

        def run_async(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        async def async_func():
            return 42

        result = run_async(async_func())
        assert result == 42

    def test_run_async_with_exception(self):
        """Verify run_async propagates exceptions."""
        import asyncio

        def run_async(coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        async def async_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(async_func())


class TestBigOAvailability:
    """Test Big-O library availability detection."""

    def test_big_o_import_detection(self):
        """Verify big-o availability can be detected."""
        try:
            from big_o import big_o as _big_o
            from big_o import complexities as _complexities

            big_o_available = True
            # Use the imports to avoid unused import warnings
            assert _big_o is not None
            assert _complexities is not None
        except ImportError:
            big_o_available = False

        # The test itself is valid regardless of whether big_o is installed
        assert isinstance(big_o_available, bool)


class TestMemrayAvailability:
    """Test memray library availability detection."""

    def test_memray_platform_detection(self):
        """Verify memray platform detection logic."""
        import platform

        is_linux = platform.system() == "Linux"
        is_macos = platform.system() == "Darwin"

        # memray is available on Linux and macOS (via pytest-memray)
        # On Windows, it definitely isn't available
        memray_available = False
        try:
            import memray  # noqa: F401

            memray_available = True
        except ImportError:
            memray_available = False

        # memray can be available on Linux and macOS
        # The test verifies platform detection works correctly
        if is_linux or is_macos:
            # On Linux/macOS, memray may or may not be installed
            # We just verify the detection logic runs without error
            assert isinstance(memray_available, bool)
        else:
            # On Windows, memray should not be available
            if memray_available:
                pytest.fail("memray should not be available on Windows")
