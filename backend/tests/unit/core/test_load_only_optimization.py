"""Unit tests for load_only() query optimization utilities.

NEM-3351: Tests for query_optimization module that provides load_only()
patterns to optimize API response queries by fetching only needed columns.
"""

from __future__ import annotations

from sqlalchemy import Select, select

from backend.core.query_optimization import (
    CameraColumns,
    DetectionColumns,
    EventColumns,
    apply_camera_list_columns,
    apply_camera_summary_columns,
    apply_detection_list_columns,
    apply_event_list_columns,
    apply_event_summary_columns,
    apply_event_timeline_columns,
)


class TestEventColumns:
    """Tests for EventColumns column sets."""

    def test_list_view_names_contains_required_columns(self) -> None:
        """Test LIST_VIEW_NAMES contains essential list view columns."""
        required = ["id", "started_at", "camera_id", "risk_score", "reviewed"]
        for col in required:
            assert col in EventColumns.LIST_VIEW_NAMES

    def test_timeline_view_names_is_minimal(self) -> None:
        """Test TIMELINE_VIEW_NAMES contains minimal columns for timeline."""
        # Timeline should be minimal for fast scrolling
        assert len(EventColumns.TIMELINE_VIEW_NAMES) <= len(EventColumns.LIST_VIEW_NAMES)
        # Should still have essential columns
        assert "id" in EventColumns.TIMELINE_VIEW_NAMES
        assert "started_at" in EventColumns.TIMELINE_VIEW_NAMES
        assert "risk_score" in EventColumns.TIMELINE_VIEW_NAMES

    def test_summary_names_for_aggregation(self) -> None:
        """Test SUMMARY_NAMES contains columns needed for summary/stats."""
        required = ["id", "risk_score", "risk_level", "camera_id"]
        for col in required:
            assert col in EventColumns.SUMMARY_NAMES

    def test_detail_view_names_is_comprehensive(self) -> None:
        """Test DETAIL_VIEW_NAMES is more comprehensive than list view."""
        assert len(EventColumns.DETAIL_VIEW_NAMES) > len(EventColumns.LIST_VIEW_NAMES)
        # Detail should include reasoning which list doesn't need
        assert "reasoning" in EventColumns.DETAIL_VIEW_NAMES

    def test_list_view_excludes_large_columns(self) -> None:
        """Test LIST_VIEW_NAMES excludes large text columns."""
        # List view should not include full text blobs
        assert "reasoning" not in EventColumns.LIST_VIEW_NAMES
        assert "llm_prompt" not in EventColumns.LIST_VIEW_NAMES

    def test_list_view_method_returns_columns(self) -> None:
        """Test list_view() method returns column attributes."""
        columns = EventColumns.list_view()
        assert len(columns) == len(EventColumns.LIST_VIEW_NAMES)
        # Verify they are InstrumentedAttribute instances
        for col in columns:
            assert hasattr(col, "key")

    def test_timeline_view_method_returns_columns(self) -> None:
        """Test timeline_view() method returns column attributes."""
        columns = EventColumns.timeline_view()
        assert len(columns) == len(EventColumns.TIMELINE_VIEW_NAMES)

    def test_summary_method_returns_columns(self) -> None:
        """Test summary() method returns column attributes."""
        columns = EventColumns.summary()
        assert len(columns) == len(EventColumns.SUMMARY_NAMES)

    def test_detail_view_method_returns_columns(self) -> None:
        """Test detail_view() method returns column attributes."""
        columns = EventColumns.detail_view()
        assert len(columns) == len(EventColumns.DETAIL_VIEW_NAMES)


class TestCameraColumns:
    """Tests for CameraColumns column sets."""

    def test_list_view_names_contains_required_columns(self) -> None:
        """Test LIST_VIEW_NAMES contains essential camera list columns."""
        required = ["id", "name", "status"]
        for col in required:
            assert col in CameraColumns.LIST_VIEW_NAMES

    def test_summary_names_is_minimal(self) -> None:
        """Test SUMMARY_NAMES contains minimal columns for dropdowns."""
        # Summary should be minimal for selectors/dropdowns
        assert len(CameraColumns.SUMMARY_NAMES) <= len(CameraColumns.LIST_VIEW_NAMES)
        # Should have essential columns
        assert "id" in CameraColumns.SUMMARY_NAMES
        assert "name" in CameraColumns.SUMMARY_NAMES

    def test_detail_view_names_is_comprehensive(self) -> None:
        """Test DETAIL_VIEW_NAMES is comprehensive for detail page."""
        assert len(CameraColumns.DETAIL_VIEW_NAMES) >= len(CameraColumns.LIST_VIEW_NAMES)
        # Detail should include all columns
        assert "created_at" in CameraColumns.DETAIL_VIEW_NAMES

    def test_list_view_method_returns_columns(self) -> None:
        """Test list_view() method returns column attributes."""
        columns = CameraColumns.list_view()
        assert len(columns) == len(CameraColumns.LIST_VIEW_NAMES)

    def test_summary_method_returns_columns(self) -> None:
        """Test summary() method returns column attributes."""
        columns = CameraColumns.summary()
        assert len(columns) == len(CameraColumns.SUMMARY_NAMES)


class TestDetectionColumns:
    """Tests for DetectionColumns column sets."""

    def test_list_view_names_contains_required_columns(self) -> None:
        """Test LIST_VIEW_NAMES contains essential detection list columns."""
        required = ["id", "detected_at", "camera_id", "object_type", "confidence"]
        for col in required:
            assert col in DetectionColumns.LIST_VIEW_NAMES

    def test_list_view_includes_bbox(self) -> None:
        """Test LIST_VIEW_NAMES includes bounding box columns."""
        # Detection list typically needs bbox for visualization
        bbox_cols = ["bbox_x", "bbox_y", "bbox_width", "bbox_height"]
        for col in bbox_cols:
            assert col in DetectionColumns.LIST_VIEW_NAMES

    def test_summary_names_excludes_bbox(self) -> None:
        """Test SUMMARY_NAMES excludes bounding box columns."""
        # Summary for aggregation doesn't need bbox
        bbox_cols = ["bbox_x", "bbox_y", "bbox_width", "bbox_height"]
        for col in bbox_cols:
            assert col not in DetectionColumns.SUMMARY_NAMES

    def test_list_view_method_returns_columns(self) -> None:
        """Test list_view() method returns column attributes."""
        columns = DetectionColumns.list_view()
        assert len(columns) == len(DetectionColumns.LIST_VIEW_NAMES)

    def test_summary_method_returns_columns(self) -> None:
        """Test summary() method returns column attributes."""
        columns = DetectionColumns.summary()
        assert len(columns) == len(DetectionColumns.SUMMARY_NAMES)


class TestApplyEventColumns:
    """Tests for apply_event_* helper functions."""

    def test_apply_event_list_columns_returns_statement(self) -> None:
        """Test apply_event_list_columns returns modified statement."""
        from backend.models.event import Event

        stmt = select(Event)
        result = apply_event_list_columns(stmt)

        # Should return a Select statement
        assert isinstance(result, Select)

    def test_apply_event_timeline_columns_returns_statement(self) -> None:
        """Test apply_event_timeline_columns returns modified statement."""
        from backend.models.event import Event

        stmt = select(Event)
        result = apply_event_timeline_columns(stmt)

        assert isinstance(result, Select)

    def test_apply_event_summary_columns_returns_statement(self) -> None:
        """Test apply_event_summary_columns returns modified statement."""
        from backend.models.event import Event

        stmt = select(Event)
        result = apply_event_summary_columns(stmt)

        assert isinstance(result, Select)


class TestApplyCameraColumns:
    """Tests for apply_camera_* helper functions."""

    def test_apply_camera_list_columns_returns_statement(self) -> None:
        """Test apply_camera_list_columns returns modified statement."""
        from backend.models.camera import Camera

        stmt = select(Camera)
        result = apply_camera_list_columns(stmt)

        assert isinstance(result, Select)

    def test_apply_camera_summary_columns_returns_statement(self) -> None:
        """Test apply_camera_summary_columns returns modified statement."""
        from backend.models.camera import Camera

        stmt = select(Camera)
        result = apply_camera_summary_columns(stmt)

        assert isinstance(result, Select)


class TestApplyDetectionColumns:
    """Tests for apply_detection_* helper functions."""

    def test_apply_detection_list_columns_returns_statement(self) -> None:
        """Test apply_detection_list_columns returns modified statement."""
        from backend.models.detection import Detection

        stmt = select(Detection)
        result = apply_detection_list_columns(stmt)

        assert isinstance(result, Select)


class TestColumnSetDocumentation:
    """Tests to verify column sets are properly documented."""

    def test_event_columns_has_class_docstring(self) -> None:
        """Test EventColumns has class documentation."""
        assert EventColumns.__doc__ is not None
        assert len(EventColumns.__doc__) > 0

    def test_camera_columns_has_class_docstring(self) -> None:
        """Test CameraColumns has class documentation."""
        assert CameraColumns.__doc__ is not None
        assert len(CameraColumns.__doc__) > 0

    def test_detection_columns_has_class_docstring(self) -> None:
        """Test DetectionColumns has class documentation."""
        assert DetectionColumns.__doc__ is not None
        assert len(DetectionColumns.__doc__) > 0
