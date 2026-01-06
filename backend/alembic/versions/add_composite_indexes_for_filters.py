"""Add composite indexes for common filter combinations

Revision ID: add_composite_indexes_filters
Revises: add_detections_camera_object_idx
Create Date: 2026-01-06 12:00:00.000000

This migration adds composite indexes to optimize common API query patterns
that filter on multiple columns simultaneously.

Current state: Most indexes are single-column, causing PostgreSQL to use
bitmap scans or index intersection for multi-column filters.

Query patterns optimized by these indexes:

1. Events table:
   - camera_id + started_at: Event timeline filtered by camera
   - camera_id + started_at + reviewed: Unreviewed events for a camera

2. Alerts table:
   - status + created_at: Alert queue processing
   - severity + created_at: Priority alert retrieval

3. Logs table:
   - timestamp + level + component: Log dashboard filtering
   - timestamp + level: Error/warning log retrieval

Benefits:
- Single index scan instead of bitmap intersection
- Sorted output for pagination without additional sort operation
- Reduced I/O and improved query latency

Related issues:
- NEM-1491: Add composite indexes for common filter combinations
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_composite_indexes_filters"
down_revision: str | Sequence[str] | None = "add_detections_camera_object_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite indexes for common filter combinations."""
    # Events: camera + time range filter (most common list_events query pattern).
    # Optimizes queries filtering by camera and date range.
    # Column order: camera_id (equality) first, then started_at (range/sort).
    op.create_index(
        "idx_events_camera_started",
        "events",
        ["camera_id", "started_at"],
        unique=False,
    )

    # Events: camera + time + reviewed filter (unreviewed events dashboard)
    # Supports: list_events(camera_id=X, reviewed=False, ORDER BY started_at)
    # This also covers the camera+started query as a prefix
    op.create_index(
        "idx_events_camera_time_reviewed",
        "events",
        ["camera_id", "started_at", "reviewed"],
        unique=False,
    )

    # Detections: camera + time + object_type filter (detection timeline).
    # Optimizes queries filtering by camera, date range, and object type.
    # Extends existing idx_detections_camera_time with object_type.
    op.create_index(
        "idx_detections_camera_time_type",
        "detections",
        ["camera_id", "detected_at", "object_type"],
        unique=False,
    )

    # Alerts: status + created_at for alert queue processing
    # Supports: Querying pending alerts sorted by creation time
    op.create_index(
        "idx_alerts_status_created",
        "alerts",
        ["status", "created_at"],
        unique=False,
    )

    # Alerts: severity + created_at for priority alert retrieval
    # Supports: Getting high-priority alerts sorted by time
    op.create_index(
        "idx_alerts_severity_created",
        "alerts",
        ["severity", "created_at"],
        unique=False,
    )

    # Logs: timestamp + level + component for dashboard filtering.
    # Optimizes queries filtering by time range, log level, and component.
    # Column order: timestamp (range) first for time-series queries.
    op.create_index(
        "idx_logs_time_level_component",
        "logs",
        ["timestamp", "level", "component"],
        unique=False,
    )

    # Logs: timestamp + level for error/warning retrieval.
    # Optimizes queries filtering by time range and log level.
    op.create_index(
        "idx_logs_time_level",
        "logs",
        ["timestamp", "level"],
        unique=False,
    )


def downgrade() -> None:
    """Remove composite filter indexes."""
    op.drop_index("idx_logs_time_level", table_name="logs")
    op.drop_index("idx_logs_time_level_component", table_name="logs")
    op.drop_index("idx_alerts_severity_created", table_name="alerts")
    op.drop_index("idx_alerts_status_created", table_name="alerts")
    op.drop_index("idx_detections_camera_time_type", table_name="detections")
    op.drop_index("idx_events_camera_time_reviewed", table_name="events")
    op.drop_index("idx_events_camera_started", table_name="events")
