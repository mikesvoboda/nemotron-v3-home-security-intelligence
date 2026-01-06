"""Add covering indexes for API pagination queries

Revision ID: add_covering_indexes_pagination
Revises: add_composite_indexes_filters
Create Date: 2026-01-06 12:30:00.000000

This migration adds covering indexes using PostgreSQL 11+ INCLUDE clause
to enable index-only scans for common pagination queries.

Current state: Pagination queries require heap fetches after index scan
because the indexes don't contain all columns needed by the SELECT clause.

Query patterns optimized by these indexes:

1. Events list pagination:
   SELECT id, camera_id, started_at, risk_score, risk_level, summary, reviewed
   FROM events WHERE camera_id = X ORDER BY started_at DESC LIMIT 50

2. Detections list pagination:
   SELECT id, camera_id, detected_at, object_type, confidence
   FROM detections WHERE camera_id = X ORDER BY detected_at DESC LIMIT 50

3. Alerts list pagination:
   SELECT id, event_id, severity, status, created_at
   FROM alerts ORDER BY created_at DESC LIMIT 50

PostgreSQL INCLUDE syntax:
CREATE INDEX idx_name ON table (key_columns) INCLUDE (covered_columns);

Benefits:
- Index-only scans for pagination queries (no heap fetches)
- Significantly faster API response times for list endpoints
- Reduced I/O load on database

Trade-offs:
- Larger index sizes due to included columns
- Only include columns actually returned by list APIs

Related issues:
- NEM-1497: Add covering indexes for API pagination queries
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_covering_indexes_pagination"
down_revision: str | Sequence[str] | None = "add_composite_indexes_filters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add covering indexes for pagination queries."""
    # Events: Covering index for list_events pagination
    # Key columns: camera_id (filter), started_at DESC (sort)
    # Included columns: id (PK), risk_score, risk_level, summary, reviewed
    # This enables index-only scans for the most common event list query
    op.create_index(
        "idx_events_pagination_covering",
        "events",
        ["camera_id", "started_at"],
        unique=False,
        postgresql_include=["id", "risk_score", "risk_level", "summary", "reviewed"],
    )

    # Detections: Covering index for list_detections pagination
    # Key columns: camera_id (filter), detected_at DESC (sort)
    # Included columns: id (PK), object_type, confidence
    # This enables index-only scans for detection list queries
    op.create_index(
        "idx_detections_pagination_covering",
        "detections",
        ["camera_id", "detected_at"],
        unique=False,
        postgresql_include=["id", "object_type", "confidence"],
    )

    # Alerts: Covering index for alert list pagination
    # Key columns: created_at DESC (sort order for alert lists)
    # Included columns: id (PK), event_id, severity, status
    # This enables index-only scans for alert list queries
    op.create_index(
        "idx_alerts_pagination_covering",
        "alerts",
        ["created_at"],
        unique=False,
        postgresql_include=["id", "event_id", "severity", "status"],
    )

    # Logs: Covering index for log list pagination
    # Key columns: timestamp DESC (sort order for log lists)
    # Included columns: id (PK), level, component, camera_id, message
    # Note: message can be large, so this index will be bigger
    # but enables index-only scans for dashboard log queries
    op.create_index(
        "idx_logs_pagination_covering",
        "logs",
        ["timestamp"],
        unique=False,
        postgresql_include=["id", "level", "component", "camera_id"],
    )


def downgrade() -> None:
    """Remove covering indexes for pagination."""
    op.drop_index("idx_logs_pagination_covering", table_name="logs")
    op.drop_index("idx_alerts_pagination_covering", table_name="alerts")
    op.drop_index("idx_detections_pagination_covering", table_name="detections")
    op.drop_index("idx_events_pagination_covering", table_name="events")
