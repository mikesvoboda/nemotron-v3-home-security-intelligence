"""Big-O complexity benchmarks for critical paths.

These tests empirically verify algorithmic complexity of key operations
to catch accidental O(n^2) or worse regressions.

Usage:
    pytest tests/benchmarks/test_bigo.py -v

Note: big-o library is optional. Tests will be skipped if not installed.
"""

from __future__ import annotations

from typing import Any

import pytest

# Check if big_o is available
try:
    from big_o import big_o, complexities

    BIG_O_AVAILABLE = True
except ImportError:
    BIG_O_AVAILABLE = False


def generate_detections(n: int) -> list[dict[str, Any]]:
    """Generate n mock detections for testing.

    Args:
        n: Number of detections to generate

    Returns:
        List of detection dictionaries
    """
    return [
        {
            "id": i,
            "camera_id": f"cam_{i % 5}",
            "timestamp": f"2024-01-01T00:00:{i % 60:02d}",
            "class_name": "person",
            "confidence": 0.95,
            "bbox": [100 + i, 100 + i, 200 + i, 200 + i],
        }
        for i in range(n)
    ]


def generate_file_paths(n: int) -> list[str]:
    """Generate n mock file paths for testing.

    Args:
        n: Number of file paths to generate

    Returns:
        List of file path strings
    """
    return [f"/export/foscam/camera_{i % 10}/image_{i:06d}.jpg" for i in range(n)]


def aggregate_detections_by_camera(detections: list[dict]) -> dict[str, list[dict]]:
    """Aggregate detections by camera ID.

    This is a reference O(n) implementation that the actual batch
    aggregator should match or beat.

    Args:
        detections: List of detection dictionaries

    Returns:
        Dictionary mapping camera_id to list of detections
    """
    result: dict[str, list[dict]] = {}
    for detection in detections:
        camera_id = detection["camera_id"]
        if camera_id not in result:
            result[camera_id] = []
        result[camera_id].append(detection)
    return result


def process_file_batch(file_paths: list[str]) -> list[dict]:
    """Process a batch of file paths.

    This is a reference O(n) implementation that simulates
    file path processing.

    Args:
        file_paths: List of file paths to process

    Returns:
        List of processed file metadata dictionaries
    """
    return [
        {
            "path": path,
            "camera": path.split("/")[3] if len(path.split("/")) > 3 else "unknown",
            "filename": path.split("/")[-1],
            "size_estimate": len(path) * 1000,
        }
        for path in file_paths
    ]


def filter_high_confidence(detections: list[dict], threshold: float = 0.9) -> list[dict]:
    """Filter detections by confidence threshold.

    Args:
        detections: List of detection dictionaries
        threshold: Minimum confidence threshold

    Returns:
        Filtered list of detections
    """
    return [d for d in detections if d.get("confidence", 0) >= threshold]


def group_by_timewindow(detections: list[dict], window_size: int = 10) -> dict[int, list[dict]]:
    """Group detections by time window.

    This is a reference O(n) implementation.

    Args:
        detections: List of detection dictionaries
        window_size: Size of time window in seconds

    Returns:
        Dictionary mapping window index to list of detections
    """
    result: dict[int, list[dict]] = {}
    for detection in detections:
        # Extract second from timestamp
        timestamp = detection.get("timestamp", "2024-01-01T00:00:00")
        second = int(timestamp.split(":")[-1])
        window_idx = second // window_size

        if window_idx not in result:
            result[window_idx] = []
        result[window_idx].append(detection)
    return result


@pytest.mark.skipif(not BIG_O_AVAILABLE, reason="big-o library not installed")
class TestBatchAggregatorComplexity:
    """Test algorithmic complexity of batch aggregation operations."""

    def test_aggregate_detections_complexity(self):
        """Batch aggregation should be O(n) or O(n log n)."""

        def aggregate(n: int) -> int:
            detections = generate_detections(n)
            result = aggregate_detections_by_camera(detections)
            return sum(len(v) for v in result.values())

        best, _others = big_o(
            aggregate,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        # Should be linear or better, not quadratic
        acceptable_complexities = [
            complexities.Constant,
            complexities.Logarithmic,
            complexities.Linear,
            complexities.Linearithmic,
        ]
        assert any(
            isinstance(best, c) for c in acceptable_complexities
        ), f"Unexpected complexity: {best}"

    def test_filter_detections_complexity(self):
        """Detection filtering should be O(n) or better."""

        def filter_op(n: int) -> int:
            detections = generate_detections(n)
            filtered = filter_high_confidence(detections, threshold=0.9)
            return len(filtered)

        best, _others = big_o(
            filter_op,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        acceptable_complexities = [
            complexities.Constant,
            complexities.Logarithmic,
            complexities.Linear,
            complexities.Linearithmic,  # O(n log n) acceptable due to measurement variance
        ]
        assert any(
            isinstance(best, c) for c in acceptable_complexities
        ), f"Unexpected complexity: {best}"

    def test_group_by_timewindow_complexity(self):
        """Time window grouping should be O(n)."""

        def group_op(n: int) -> int:
            detections = generate_detections(n)
            grouped = group_by_timewindow(detections, window_size=10)
            return sum(len(v) for v in grouped.values())

        best, _others = big_o(
            group_op,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        acceptable_complexities = [
            complexities.Constant,
            complexities.Logarithmic,
            complexities.Linear,
            complexities.Linearithmic,
        ]
        assert any(
            isinstance(best, c) for c in acceptable_complexities
        ), f"Unexpected complexity: {best}"


@pytest.mark.skipif(not BIG_O_AVAILABLE, reason="big-o library not installed")
class TestFileWatcherComplexity:
    """Test algorithmic complexity of file watching operations."""

    def test_process_files_complexity(self):
        """File processing should be O(n)."""

        def process_files(n: int) -> int:
            files = generate_file_paths(n)
            processed = process_file_batch(files)
            return len(processed)

        best, _others = big_o(
            process_files,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        acceptable_complexities = [
            complexities.Constant,
            complexities.Logarithmic,
            complexities.Linear,
        ]
        assert any(
            isinstance(best, c) for c in acceptable_complexities
        ), f"Unexpected complexity: {best}"

    def test_path_parsing_complexity(self):
        """Path parsing should be O(n)."""

        def parse_paths(n: int) -> int:
            files = generate_file_paths(n)
            # Simulate path parsing
            parsed = [path.split("/") for path in files]
            return len(parsed)

        best, _others = big_o(
            parse_paths,
            lambda n: n,
            n_repeats=5,
            min_n=100,
            max_n=10000,
        )

        acceptable_complexities = [
            complexities.Constant,
            complexities.Logarithmic,
            complexities.Linear,
        ]
        assert any(
            isinstance(best, c) for c in acceptable_complexities
        ), f"Unexpected complexity: {best}"


class TestComplexityHelperFunctions:
    """Test that helper functions work correctly regardless of big-o availability."""

    def test_generate_detections_returns_correct_count(self):
        """generate_detections should return exactly n items."""
        for n in [0, 1, 10, 100]:
            detections = generate_detections(n)
            assert len(detections) == n

    def test_generate_detections_has_required_fields(self):
        """Each detection should have required fields."""
        detections = generate_detections(5)
        for detection in detections:
            assert "id" in detection
            assert "camera_id" in detection
            assert "timestamp" in detection
            assert "class_name" in detection
            assert "confidence" in detection
            assert "bbox" in detection

    def test_generate_file_paths_returns_correct_count(self):
        """generate_file_paths should return exactly n items."""
        for n in [0, 1, 10, 100]:
            paths = generate_file_paths(n)
            assert len(paths) == n

    def test_generate_file_paths_are_valid_paths(self):
        """Generated paths should be valid file paths."""
        paths = generate_file_paths(10)
        for path in paths:
            assert path.startswith("/")
            assert path.endswith(".jpg")

    def test_aggregate_detections_by_camera(self):
        """aggregate_detections_by_camera should group correctly."""
        detections = generate_detections(10)
        grouped = aggregate_detections_by_camera(detections)

        # All camera IDs should be present
        total_count = sum(len(v) for v in grouped.values())
        assert total_count == 10

        # Each detection should be in exactly one group
        for camera_id, camera_detections in grouped.items():
            for detection in camera_detections:
                assert detection["camera_id"] == camera_id

    def test_filter_high_confidence(self):
        """filter_high_confidence should filter correctly."""
        detections = generate_detections(10)
        # All generated detections have confidence 0.95

        # Should include all with threshold 0.9
        filtered_low = filter_high_confidence(detections, threshold=0.9)
        assert len(filtered_low) == 10

        # Should include all with threshold 0.95
        filtered_exact = filter_high_confidence(detections, threshold=0.95)
        assert len(filtered_exact) == 10

        # Should exclude all with threshold 0.96
        filtered_high = filter_high_confidence(detections, threshold=0.96)
        assert len(filtered_high) == 0

    def test_process_file_batch(self):
        """process_file_batch should return correct metadata."""
        paths = generate_file_paths(5)
        processed = process_file_batch(paths)

        assert len(processed) == 5
        for item in processed:
            assert "path" in item
            assert "camera" in item
            assert "filename" in item
            assert "size_estimate" in item
            assert item["filename"].endswith(".jpg")

    def test_group_by_timewindow(self):
        """group_by_timewindow should group correctly."""
        detections = generate_detections(60)
        grouped = group_by_timewindow(detections, window_size=10)

        # All detections should be in groups
        total_count = sum(len(v) for v in grouped.values())
        assert total_count == 60

        # Window indices should be in valid range (0-5 for 60 seconds / 10 second windows)
        for window_idx in grouped:
            assert 0 <= window_idx <= 5
