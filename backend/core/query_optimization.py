"""Query optimization utilities using SQLAlchemy load_only() and other techniques.

NEM-3351: Implements load_only() patterns to fetch only needed columns
for API response optimization, reducing data transfer and memory usage.

This module provides:
1. Pre-defined column sets for common use cases
2. Helper functions to apply load_only() options
3. Query builders with optimized column selection

Usage:
    from backend.core.query_optimization import (
        apply_event_list_columns,
        apply_camera_summary_columns,
        EventColumns,
    )

    # Using column sets directly
    stmt = select(Event).options(load_only(*EventColumns.LIST_VIEW))

    # Using helper functions
    stmt = apply_event_list_columns(select(Event))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Final

from sqlalchemy import Select
from sqlalchemy.orm import load_only

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

__all__ = [
    "CameraColumns",
    "DetectionColumns",
    "EventColumns",
    "apply_camera_list_columns",
    "apply_camera_summary_columns",
    "apply_detection_list_columns",
    "apply_event_list_columns",
    "apply_event_summary_columns",
    "apply_event_timeline_columns",
]


class EventColumns:
    """Column sets for Event model queries.

    These sets are designed for specific use cases to minimize
    data transfer while providing all needed information.

    Event model columns:
    - id, batch_id, camera_id, started_at, ended_at
    - risk_score, risk_level, summary, reasoning
    - llm_prompt, reviewed, notes, is_fast_path
    - object_types, clip_path, search_vector
    - deleted_at, snooze_until
    """

    @staticmethod
    def _get_columns(column_names: list[str]) -> list[InstrumentedAttribute]:
        """Get column attributes by name (lazy import to avoid circular deps)."""
        from backend.models.event import Event

        return [getattr(Event, name) for name in column_names]

    # Columns for list view (event cards, tables)
    # Excludes large text fields like llm_prompt, reasoning
    LIST_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "batch_id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "object_types",
        "reviewed",
        "clip_path",
        "is_fast_path",
    ]

    # Columns for timeline view (minimal for fast scrolling)
    TIMELINE_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "camera_id",
        "started_at",
        "risk_score",
        "risk_level",
        "reviewed",
    ]

    # Columns for event summary/stats queries
    SUMMARY_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "started_at",
        "risk_score",
        "risk_level",
        "camera_id",
        "reviewed",
    ]

    # Columns for event detail view (includes reasoning but not llm_prompt)
    DETAIL_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "batch_id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "reviewed",
        "notes",
        "is_fast_path",
        "object_types",
        "clip_path",
        "deleted_at",
        "snooze_until",
    ]

    @classmethod
    def list_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for list view."""
        return cls._get_columns(cls.LIST_VIEW_NAMES)

    @classmethod
    def timeline_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for timeline view."""
        return cls._get_columns(cls.TIMELINE_VIEW_NAMES)

    @classmethod
    def summary(cls) -> list[InstrumentedAttribute]:
        """Get columns for summary queries."""
        return cls._get_columns(cls.SUMMARY_NAMES)

    @classmethod
    def detail_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for detail view."""
        return cls._get_columns(cls.DETAIL_VIEW_NAMES)


class CameraColumns:
    """Column sets for Camera model queries.

    Camera model columns:
    - id, name, folder_path, status
    - created_at, last_seen_at, deleted_at, property_id
    """

    @staticmethod
    def _get_columns(column_names: list[str]) -> list[InstrumentedAttribute]:
        """Get column attributes by name."""
        from backend.models.camera import Camera

        return [getattr(Camera, name) for name in column_names]

    # Columns for list view (camera cards)
    LIST_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "name",
        "folder_path",
        "status",
        "last_seen_at",
        "property_id",
    ]

    # Columns for camera summary (dropdowns, selectors)
    SUMMARY_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "name",
        "status",
    ]

    # Columns for camera detail view (all columns)
    DETAIL_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "name",
        "folder_path",
        "status",
        "created_at",
        "last_seen_at",
        "deleted_at",
        "property_id",
    ]

    @classmethod
    def list_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for list view."""
        return cls._get_columns(cls.LIST_VIEW_NAMES)

    @classmethod
    def summary(cls) -> list[InstrumentedAttribute]:
        """Get columns for summary queries."""
        return cls._get_columns(cls.SUMMARY_NAMES)

    @classmethod
    def detail_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for detail view."""
        return cls._get_columns(cls.DETAIL_VIEW_NAMES)


class DetectionColumns:
    """Column sets for Detection model queries.

    Detection model columns:
    - id, camera_id, file_path, file_type, detected_at
    - object_type, confidence
    - bbox_x, bbox_y, bbox_width, bbox_height
    - thumbnail_path
    - media_type, duration, video_codec, video_width, video_height
    - enrichment_data, search_vector, labels
    """

    @staticmethod
    def _get_columns(column_names: list[str]) -> list[InstrumentedAttribute]:
        """Get column attributes by name."""
        from backend.models.detection import Detection

        return [getattr(Detection, name) for name in column_names]

    # Columns for list view (detection table)
    # Excludes large JSONB fields like enrichment_data
    LIST_VIEW_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "detected_at",
        "camera_id",
        "object_type",
        "confidence",
        "bbox_x",
        "bbox_y",
        "bbox_width",
        "bbox_height",
        "thumbnail_path",
        "file_path",
    ]

    # Columns for summary/aggregation queries
    SUMMARY_NAMES: Final[ClassVar[list[str]]] = [
        "id",
        "detected_at",
        "camera_id",
        "object_type",
        "confidence",
    ]

    @classmethod
    def list_view(cls) -> list[InstrumentedAttribute]:
        """Get columns for list view."""
        return cls._get_columns(cls.LIST_VIEW_NAMES)

    @classmethod
    def summary(cls) -> list[InstrumentedAttribute]:
        """Get columns for summary queries."""
        return cls._get_columns(cls.SUMMARY_NAMES)


# Helper functions to apply load_only to queries


def apply_event_list_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for event list view columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*EventColumns.list_view()))


def apply_event_timeline_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for event timeline view columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*EventColumns.timeline_view()))


def apply_event_summary_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for event summary columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*EventColumns.summary()))


def apply_camera_list_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for camera list view columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*CameraColumns.list_view()))


def apply_camera_summary_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for camera summary columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*CameraColumns.summary()))


def apply_detection_list_columns(stmt: Select[Any]) -> Select[Any]:
    """Apply load_only for detection list view columns.

    Args:
        stmt: SQLAlchemy select statement

    Returns:
        Statement with load_only options applied
    """
    return stmt.options(load_only(*DetectionColumns.list_view()))
