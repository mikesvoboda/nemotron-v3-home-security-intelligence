"""Add time-series partitioning for high-volume tables

Revision ID: add_time_series_partitioning
Revises: add_event_detections_junction
Create Date: 2026-01-06 16:00:00.000000

This migration adds PostgreSQL native partitioning for high-volume tables:
- detections
- events
- logs
- gpu_stats
- audit_logs

Partitioning Strategy:
- Monthly partitions for detections, events, logs, audit_logs
- Weekly partitions for gpu_stats (higher frequency)
- Range partitioning on timestamp columns

Benefits:
1. Partition pruning for time-range queries (query only relevant partitions)
2. Efficient data retention (DROP PARTITION vs DELETE)
3. Parallel query execution across partitions
4. Reduced index maintenance overhead
5. Better vacuum performance (per-partition)

Migration Strategy:
For tables WITH existing data, we use a safe migration approach:
1. Create new partitioned table with _partitioned suffix
2. Copy data from old table to new partitioned table
3. Rename tables (old -> _old, new -> original name)
4. Drop old table (data preserved in partitioned table)

For tables WITHOUT data or new installations:
1. Drop and recreate as partitioned table directly

Note: This is a potentially long-running migration for tables with large amounts
of existing data. Consider running during maintenance windows.

Related Linear issues: NEM-1489, NEM-1624
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "add_time_series_partitioning"
down_revision: str | Sequence[str] | None = "add_event_detections_junction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_current_month_partition_bounds() -> tuple[str, str]:
    """Get start and end dates for current month partition."""
    now = datetime.now(UTC)
    start = f"{now.year}-{now.month:02d}-01"
    end = f"{now.year + 1}-01-01" if now.month == 12 else f"{now.year}-{now.month + 1:02d}-01"
    return start, end


def _get_partition_bounds_for_months(months_from_now: int) -> tuple[str, str]:
    """Get partition bounds for a month offset from now."""
    now = datetime.now(UTC)
    year = now.year
    month = now.month + months_from_now

    # Handle year rollover
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12

    start = f"{year}-{month:02d}-01"

    # Calculate end date
    end_month = month + 1
    end_year = year
    if end_month > 12:
        end_year += 1
        end_month = 1

    end = f"{end_year}-{end_month:02d}-01"
    return start, end


def _create_partitions_for_table(table_name: str, num_future_months: int = 2) -> None:
    """Create current and future month partitions for a table."""
    # Create partitions for current month and future months
    for offset in range(num_future_months + 1):
        start, end = _get_partition_bounds_for_months(offset)
        now = datetime.now(UTC)
        year = now.year
        month = now.month + offset
        while month > 12:
            year += 1
            month -= 12

        partition_name = f"{table_name}_y{year}m{month:02d}"

        # DDL for partition creation requires dynamic SQL - values are from code, not user input
        op.execute(  # nosemgrep: avoid-sqlalchemy-text,sqlalchemy-raw-text-injection
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {partition_name}
                PARTITION OF {table_name}
                FOR VALUES FROM ('{start}') TO ('{end}')
                """
            )
        )


def _table_has_data(table_name: str) -> bool:
    """Check if a table has any data."""
    conn = op.get_bind()
    result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)"))  # noqa: S608  # nosemgrep
    return bool(result.scalar())


def _is_partitioned(conn: object, table_name: str) -> bool:
    """Check if a table is already partitioned."""
    result = conn.execute(  # type: ignore[union-attr, attr-defined]
        text(f"SELECT relkind FROM pg_class WHERE relname = '{table_name}'")  # noqa: S608  # nosemgrep
    )
    return bool(result.scalar() == "p")


def _upgrade_detections(conn: object) -> None:
    """Convert detections table to partitioned table."""
    if _is_partitioned(conn, "detections"):
        return

    has_data = _table_has_data("detections")

    if has_data:
        _upgrade_detections_with_data()
    else:
        _upgrade_detections_empty()


def _upgrade_detections_with_data() -> None:
    """Convert detections table with existing data."""
    op.execute(
        text(
            """
            CREATE TABLE detections_partitioned (
                id SERIAL,
                camera_id VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                file_type VARCHAR,
                detected_at TIMESTAMPTZ NOT NULL,
                object_type VARCHAR,
                confidence FLOAT,
                bbox_x INTEGER,
                bbox_y INTEGER,
                bbox_width INTEGER,
                bbox_height INTEGER,
                thumbnail_path VARCHAR,
                media_type VARCHAR DEFAULT 'image',
                duration FLOAT,
                video_codec VARCHAR,
                video_width INTEGER,
                video_height INTEGER,
                enrichment_data JSONB,
                PRIMARY KEY (id, detected_at)
            ) PARTITION BY RANGE (detected_at)
            """
        )
    )
    _create_partitions_for_table("detections_partitioned", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS detections_default
            PARTITION OF detections_partitioned DEFAULT
            """
        )
    )
    op.execute(text("INSERT INTO detections_partitioned SELECT * FROM detections"))
    op.execute(text("ALTER TABLE detections RENAME TO detections_old"))
    op.execute(text("ALTER TABLE detections_partitioned RENAME TO detections"))
    # Recreate indexes
    op.execute(
        text("CREATE INDEX IF NOT EXISTS idx_detections_camera_id_new ON detections (camera_id)")
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_detections_detected_at_new ON detections (detected_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_detections_camera_time_new ON detections (camera_id, detected_at)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX IF NOT EXISTS idx_detections_camera_object_type_new ON detections (camera_id, object_type)"
        )
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_detections_enrichment_data_gin_new
            ON detections USING gin (enrichment_data jsonb_path_ops)
            """
        )
    )
    op.execute(text("DROP TABLE IF EXISTS detections_old CASCADE"))


def _upgrade_detections_empty() -> None:
    """Convert empty detections table to partitioned."""
    op.execute(text("DROP TABLE IF EXISTS detections CASCADE"))
    op.execute(
        text(
            """
            CREATE TABLE detections (
                id SERIAL,
                camera_id VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                file_type VARCHAR,
                detected_at TIMESTAMPTZ NOT NULL,
                object_type VARCHAR,
                confidence FLOAT,
                bbox_x INTEGER,
                bbox_y INTEGER,
                bbox_width INTEGER,
                bbox_height INTEGER,
                thumbnail_path VARCHAR,
                media_type VARCHAR DEFAULT 'image',
                duration FLOAT,
                video_codec VARCHAR,
                video_width INTEGER,
                video_height INTEGER,
                enrichment_data JSONB,
                PRIMARY KEY (id, detected_at)
            ) PARTITION BY RANGE (detected_at)
            """
        )
    )
    _create_partitions_for_table("detections", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS detections_default
            PARTITION OF detections DEFAULT
            """
        )
    )
    op.execute(text("CREATE INDEX idx_detections_camera_id ON detections (camera_id)"))
    op.execute(text("CREATE INDEX idx_detections_detected_at ON detections (detected_at)"))
    op.execute(
        text("CREATE INDEX idx_detections_camera_time ON detections (camera_id, detected_at)")
    )


def _upgrade_events(conn: object) -> None:
    """Convert events table to partitioned table."""
    if _is_partitioned(conn, "events"):
        return

    has_data = _table_has_data("events")

    if has_data:
        _upgrade_events_with_data()
    else:
        _upgrade_events_empty()


def _upgrade_events_with_data() -> None:
    """Convert events table with existing data."""
    op.execute(
        text(
            """
            CREATE TABLE events_partitioned (
                id SERIAL,
                batch_id VARCHAR NOT NULL,
                camera_id VARCHAR NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ,
                risk_score INTEGER,
                risk_level VARCHAR,
                summary TEXT,
                reasoning TEXT,
                llm_prompt TEXT,
                detection_ids TEXT,
                reviewed BOOLEAN NOT NULL DEFAULT false,
                notes TEXT,
                is_fast_path BOOLEAN NOT NULL DEFAULT false,
                object_types TEXT,
                clip_path VARCHAR,
                search_vector TSVECTOR,
                deleted_at TIMESTAMPTZ,
                PRIMARY KEY (id, started_at)
            ) PARTITION BY RANGE (started_at)
            """
        )
    )
    _create_partitions_for_table("events_partitioned", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS events_default
            PARTITION OF events_partitioned DEFAULT
            """
        )
    )
    op.execute(text("INSERT INTO events_partitioned SELECT * FROM events"))
    op.execute(text("ALTER TABLE events RENAME TO events_old"))
    op.execute(text("ALTER TABLE events_partitioned RENAME TO events"))
    # Recreate indexes
    op.execute(text("CREATE INDEX idx_events_camera_id_new ON events (camera_id)"))
    op.execute(text("CREATE INDEX idx_events_started_at_new ON events (started_at)"))
    op.execute(text("CREATE INDEX idx_events_risk_score_new ON events (risk_score)"))
    op.execute(text("CREATE INDEX idx_events_reviewed_new ON events (reviewed)"))
    op.execute(text("CREATE INDEX idx_events_batch_id_new ON events (batch_id)"))
    op.execute(
        text(
            """
            CREATE INDEX idx_events_search_vector_new
            ON events USING gin (search_vector)
            """
        )
    )
    op.execute(text("DROP TABLE IF EXISTS events_old CASCADE"))


def _upgrade_events_empty() -> None:
    """Convert empty events table to partitioned."""
    op.execute(text("DROP TABLE IF EXISTS events CASCADE"))
    op.execute(
        text(
            """
            CREATE TABLE events (
                id SERIAL,
                batch_id VARCHAR NOT NULL,
                camera_id VARCHAR NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ,
                risk_score INTEGER,
                risk_level VARCHAR,
                summary TEXT,
                reasoning TEXT,
                llm_prompt TEXT,
                detection_ids TEXT,
                reviewed BOOLEAN NOT NULL DEFAULT false,
                notes TEXT,
                is_fast_path BOOLEAN NOT NULL DEFAULT false,
                object_types TEXT,
                clip_path VARCHAR,
                search_vector TSVECTOR,
                deleted_at TIMESTAMPTZ,
                PRIMARY KEY (id, started_at)
            ) PARTITION BY RANGE (started_at)
            """
        )
    )
    _create_partitions_for_table("events", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS events_default
            PARTITION OF events DEFAULT
            """
        )
    )
    op.execute(text("CREATE INDEX idx_events_camera_id ON events (camera_id)"))
    op.execute(text("CREATE INDEX idx_events_started_at ON events (started_at)"))


def _upgrade_logs(conn: object) -> None:
    """Convert logs table to partitioned table."""
    if _is_partitioned(conn, "logs"):
        return

    has_data = _table_has_data("logs")

    if has_data:
        _upgrade_logs_with_data()
    else:
        _upgrade_logs_empty()


def _upgrade_logs_with_data() -> None:
    """Convert logs table with existing data."""
    op.execute(
        text(
            """
            CREATE TABLE logs_partitioned (
                id SERIAL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                level VARCHAR(10) NOT NULL,
                component VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                camera_id VARCHAR(100),
                event_id INTEGER,
                request_id VARCHAR(36),
                detection_id INTEGER,
                duration_ms INTEGER,
                extra JSONB,
                source VARCHAR(10) NOT NULL DEFAULT 'backend',
                user_agent TEXT,
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )
    _create_partitions_for_table("logs_partitioned", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS logs_default
            PARTITION OF logs_partitioned DEFAULT
            """
        )
    )
    op.execute(text("INSERT INTO logs_partitioned SELECT * FROM logs"))
    op.execute(text("ALTER TABLE logs RENAME TO logs_old"))
    op.execute(text("ALTER TABLE logs_partitioned RENAME TO logs"))
    op.execute(text("CREATE INDEX idx_logs_timestamp_new ON logs (timestamp)"))
    op.execute(text("CREATE INDEX idx_logs_level_new ON logs (level)"))
    op.execute(text("CREATE INDEX idx_logs_component_new ON logs (component)"))
    op.execute(text("DROP TABLE IF EXISTS logs_old CASCADE"))


def _upgrade_logs_empty() -> None:
    """Convert empty logs table to partitioned."""
    op.execute(text("DROP TABLE IF EXISTS logs CASCADE"))
    op.execute(
        text(
            """
            CREATE TABLE logs (
                id SERIAL,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                level VARCHAR(10) NOT NULL,
                component VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                camera_id VARCHAR(100),
                event_id INTEGER,
                request_id VARCHAR(36),
                detection_id INTEGER,
                duration_ms INTEGER,
                extra JSONB,
                source VARCHAR(10) NOT NULL DEFAULT 'backend',
                user_agent TEXT,
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )
    _create_partitions_for_table("logs", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS logs_default
            PARTITION OF logs DEFAULT
            """
        )
    )
    op.execute(text("CREATE INDEX idx_logs_timestamp ON logs (timestamp)"))
    op.execute(text("CREATE INDEX idx_logs_level ON logs (level)"))


def _upgrade_gpu_stats(conn: object) -> None:
    """Convert gpu_stats table to partitioned table."""
    if _is_partitioned(conn, "gpu_stats"):
        return

    has_data = _table_has_data("gpu_stats")

    if has_data:
        _upgrade_gpu_stats_with_data()
    else:
        _upgrade_gpu_stats_empty()


def _upgrade_gpu_stats_with_data() -> None:
    """Convert gpu_stats table with existing data."""
    op.execute(
        text(
            """
            CREATE TABLE gpu_stats_partitioned (
                id SERIAL,
                recorded_at TIMESTAMPTZ NOT NULL,
                gpu_name VARCHAR(255),
                gpu_utilization FLOAT,
                memory_used INTEGER,
                memory_total INTEGER,
                temperature FLOAT,
                power_usage FLOAT,
                inference_fps FLOAT,
                PRIMARY KEY (id, recorded_at)
            ) PARTITION BY RANGE (recorded_at)
            """
        )
    )
    _create_partitions_for_table("gpu_stats_partitioned", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS gpu_stats_default
            PARTITION OF gpu_stats_partitioned DEFAULT
            """
        )
    )
    op.execute(text("INSERT INTO gpu_stats_partitioned SELECT * FROM gpu_stats"))
    op.execute(text("ALTER TABLE gpu_stats RENAME TO gpu_stats_old"))
    op.execute(text("ALTER TABLE gpu_stats_partitioned RENAME TO gpu_stats"))
    op.execute(text("CREATE INDEX idx_gpu_stats_recorded_at_new ON gpu_stats (recorded_at)"))
    op.execute(text("DROP TABLE IF EXISTS gpu_stats_old CASCADE"))


def _upgrade_gpu_stats_empty() -> None:
    """Convert empty gpu_stats table to partitioned."""
    op.execute(text("DROP TABLE IF EXISTS gpu_stats CASCADE"))
    op.execute(
        text(
            """
            CREATE TABLE gpu_stats (
                id SERIAL,
                recorded_at TIMESTAMPTZ NOT NULL,
                gpu_name VARCHAR(255),
                gpu_utilization FLOAT,
                memory_used INTEGER,
                memory_total INTEGER,
                temperature FLOAT,
                power_usage FLOAT,
                inference_fps FLOAT,
                PRIMARY KEY (id, recorded_at)
            ) PARTITION BY RANGE (recorded_at)
            """
        )
    )
    _create_partitions_for_table("gpu_stats", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS gpu_stats_default
            PARTITION OF gpu_stats DEFAULT
            """
        )
    )
    op.execute(text("CREATE INDEX idx_gpu_stats_recorded_at ON gpu_stats (recorded_at)"))


def _upgrade_audit_logs(conn: object) -> None:
    """Convert audit_logs table to partitioned table."""
    if _is_partitioned(conn, "audit_logs"):
        return

    has_data = _table_has_data("audit_logs")

    if has_data:
        _upgrade_audit_logs_with_data()
    else:
        _upgrade_audit_logs_empty()


def _upgrade_audit_logs_with_data() -> None:
    """Convert audit_logs table with existing data."""
    op.execute(
        text(
            """
            CREATE TABLE audit_logs_partitioned (
                id SERIAL,
                timestamp TIMESTAMPTZ NOT NULL,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id VARCHAR(255),
                actor VARCHAR(100) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                details JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'success',
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )
    _create_partitions_for_table("audit_logs_partitioned", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_logs_default
            PARTITION OF audit_logs_partitioned DEFAULT
            """
        )
    )
    op.execute(text("INSERT INTO audit_logs_partitioned SELECT * FROM audit_logs"))
    op.execute(text("ALTER TABLE audit_logs RENAME TO audit_logs_old"))
    op.execute(text("ALTER TABLE audit_logs_partitioned RENAME TO audit_logs"))
    # Recreate indexes
    op.execute(text("CREATE INDEX idx_audit_logs_timestamp_new ON audit_logs (timestamp)"))
    op.execute(text("CREATE INDEX idx_audit_logs_action_new ON audit_logs (action)"))
    op.execute(text("CREATE INDEX idx_audit_logs_resource_type_new ON audit_logs (resource_type)"))
    op.execute(text("CREATE INDEX idx_audit_logs_actor_new ON audit_logs (actor)"))
    op.execute(text("CREATE INDEX idx_audit_logs_status_new ON audit_logs (status)"))
    op.execute(
        text(
            """
            CREATE INDEX idx_audit_logs_resource_new
            ON audit_logs (resource_type, resource_id)
            """
        )
    )
    op.execute(text("DROP TABLE IF EXISTS audit_logs_old CASCADE"))


def _upgrade_audit_logs_empty() -> None:
    """Convert empty audit_logs table to partitioned."""
    op.execute(text("DROP TABLE IF EXISTS audit_logs CASCADE"))
    op.execute(
        text(
            """
            CREATE TABLE audit_logs (
                id SERIAL,
                timestamp TIMESTAMPTZ NOT NULL,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id VARCHAR(255),
                actor VARCHAR(100) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                details JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'success',
                PRIMARY KEY (id, timestamp)
            ) PARTITION BY RANGE (timestamp)
            """
        )
    )
    _create_partitions_for_table("audit_logs", 2)
    op.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS audit_logs_default
            PARTITION OF audit_logs DEFAULT
            """
        )
    )
    op.execute(text("CREATE INDEX idx_audit_logs_timestamp ON audit_logs (timestamp)"))
    op.execute(text("CREATE INDEX idx_audit_logs_action ON audit_logs (action)"))
    op.execute(text("CREATE INDEX idx_audit_logs_resource_type ON audit_logs (resource_type)"))
    op.execute(text("CREATE INDEX idx_audit_logs_actor ON audit_logs (actor)"))


def upgrade() -> None:
    """Convert high-volume tables to partitioned tables."""
    conn = op.get_bind()

    # Step 1: Detections Table Partitioning
    _upgrade_detections(conn)

    # Step 2: Events Table Partitioning
    _upgrade_events(conn)

    # Step 3: Logs Table Partitioning
    _upgrade_logs(conn)

    # Step 4: GPU Stats Table Partitioning
    _upgrade_gpu_stats(conn)

    # Step 5: Audit Logs Table Partitioning
    _upgrade_audit_logs(conn)


def _downgrade_detections(conn: object) -> None:
    """Revert detections table to non-partitioned."""
    if not _is_partitioned(conn, "detections"):
        return

    op.execute(
        text(
            """
            CREATE TABLE detections_regular (
                id SERIAL PRIMARY KEY,
                camera_id VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                file_type VARCHAR,
                detected_at TIMESTAMPTZ NOT NULL,
                object_type VARCHAR,
                confidence FLOAT,
                bbox_x INTEGER,
                bbox_y INTEGER,
                bbox_width INTEGER,
                bbox_height INTEGER,
                thumbnail_path VARCHAR,
                media_type VARCHAR DEFAULT 'image',
                duration FLOAT,
                video_codec VARCHAR,
                video_width INTEGER,
                video_height INTEGER,
                enrichment_data JSONB
            )
            """
        )
    )
    op.execute(text("INSERT INTO detections_regular SELECT * FROM detections"))
    op.execute(text("DROP TABLE detections CASCADE"))
    op.execute(text("ALTER TABLE detections_regular RENAME TO detections"))
    op.execute(text("CREATE INDEX idx_detections_camera_id ON detections (camera_id)"))
    op.execute(text("CREATE INDEX idx_detections_detected_at ON detections (detected_at)"))


def _downgrade_events(conn: object) -> None:
    """Revert events table to non-partitioned."""
    if not _is_partitioned(conn, "events"):
        return

    # Check which columns exist in the current partitioned table
    result = conn.execute(  # type: ignore[union-attr, attr-defined]
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'events'
            AND table_schema = 'public'
            """
        )
    )
    existing_columns = {row[0] for row in result.fetchall()}

    # Build CREATE TABLE statement with only columns that exist
    # Note: deleted_at was added in a later migration and may not exist yet
    base_columns = [
        "id SERIAL PRIMARY KEY",
        "batch_id VARCHAR NOT NULL",
        "camera_id VARCHAR NOT NULL",
        "started_at TIMESTAMPTZ NOT NULL",
        "ended_at TIMESTAMPTZ",
        "risk_score INTEGER",
        "risk_level VARCHAR",
        "summary TEXT",
        "reasoning TEXT",
        "llm_prompt TEXT",
        "detection_ids TEXT",
        "reviewed BOOLEAN NOT NULL DEFAULT false",
        "notes TEXT",
        "is_fast_path BOOLEAN NOT NULL DEFAULT false",
        "object_types TEXT",
        "clip_path VARCHAR",
        "search_vector TSVECTOR",
    ]

    # Only add deleted_at if it exists in the source table
    if "deleted_at" in existing_columns:
        base_columns.append("deleted_at TIMESTAMPTZ")

    create_table_sql = f"""
        CREATE TABLE events_regular (
            {", ".join(base_columns)}
        )
    """

    # DDL operation using schema-defined columns, safe from SQL injection
    op.execute(text(create_table_sql))  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text

    # Build INSERT statement with only existing columns
    column_list = [
        "id",
        "batch_id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "llm_prompt",
        "detection_ids",
        "reviewed",
        "notes",
        "is_fast_path",
        "object_types",
        "clip_path",
        "search_vector",
    ]
    select_list = [
        "id",
        "batch_id",
        "camera_id",
        "started_at",
        "ended_at",
        "risk_score",
        "risk_level",
        "summary",
        "reasoning",
        "llm_prompt",
        "detection_ids",
        "reviewed::boolean",
        "notes",
        "is_fast_path::boolean",
        "object_types",
        "clip_path",
        "search_vector",
    ]

    if "deleted_at" in existing_columns:
        column_list.append("deleted_at")
        select_list.append("deleted_at")

    # Column names from schema, not user input - safe from SQL injection
    insert_sql = f"""
        INSERT INTO events_regular ({", ".join(column_list)})
        SELECT {", ".join(select_list)}
        FROM events
    """  # noqa: S608

    op.execute(text(insert_sql))  # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
    op.execute(text("DROP TABLE events CASCADE"))
    op.execute(text("ALTER TABLE events_regular RENAME TO events"))
    op.execute(text("CREATE INDEX idx_events_camera_id ON events (camera_id)"))
    op.execute(text("CREATE INDEX idx_events_started_at ON events (started_at)"))


def _downgrade_logs(conn: object) -> None:
    """Revert logs table to non-partitioned."""
    if not _is_partitioned(conn, "logs"):
        return

    op.execute(
        text(
            """
            CREATE TABLE logs_regular (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
                level VARCHAR(10) NOT NULL,
                component VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                camera_id VARCHAR(100),
                event_id INTEGER,
                request_id VARCHAR(36),
                detection_id INTEGER,
                duration_ms INTEGER,
                extra JSONB,
                source VARCHAR(10) NOT NULL DEFAULT 'backend',
                user_agent TEXT
            )
            """
        )
    )
    op.execute(text("INSERT INTO logs_regular SELECT * FROM logs"))
    op.execute(text("DROP TABLE logs CASCADE"))
    op.execute(text("ALTER TABLE logs_regular RENAME TO logs"))
    op.execute(text("CREATE INDEX idx_logs_timestamp ON logs (timestamp)"))


def _downgrade_gpu_stats(conn: object) -> None:
    """Revert gpu_stats table to non-partitioned."""
    if not _is_partitioned(conn, "gpu_stats"):
        return

    op.execute(
        text(
            """
            CREATE TABLE gpu_stats_regular (
                id SERIAL PRIMARY KEY,
                recorded_at TIMESTAMPTZ NOT NULL,
                gpu_name VARCHAR(255),
                gpu_utilization FLOAT,
                memory_used INTEGER,
                memory_total INTEGER,
                temperature FLOAT,
                power_usage FLOAT,
                inference_fps FLOAT
            )
            """
        )
    )
    op.execute(text("INSERT INTO gpu_stats_regular SELECT * FROM gpu_stats"))
    op.execute(text("DROP TABLE gpu_stats CASCADE"))
    op.execute(text("ALTER TABLE gpu_stats_regular RENAME TO gpu_stats"))
    op.execute(text("CREATE INDEX idx_gpu_stats_recorded_at ON gpu_stats (recorded_at)"))


def _downgrade_audit_logs(conn: object) -> None:
    """Revert audit_logs table to non-partitioned."""
    if not _is_partitioned(conn, "audit_logs"):
        return

    op.execute(
        text(
            """
            CREATE TABLE audit_logs_regular (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMPTZ NOT NULL,
                action VARCHAR(50) NOT NULL,
                resource_type VARCHAR(50) NOT NULL,
                resource_id VARCHAR(255),
                actor VARCHAR(100) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                details JSONB,
                status VARCHAR(20) NOT NULL DEFAULT 'success'
            )
            """
        )
    )
    op.execute(text("INSERT INTO audit_logs_regular SELECT * FROM audit_logs"))
    op.execute(text("DROP TABLE audit_logs CASCADE"))
    op.execute(text("ALTER TABLE audit_logs_regular RENAME TO audit_logs"))
    op.execute(text("CREATE INDEX idx_audit_logs_timestamp ON audit_logs (timestamp)"))
    op.execute(text("CREATE INDEX idx_audit_logs_action ON audit_logs (action)"))
    op.execute(text("CREATE INDEX idx_audit_logs_resource_type ON audit_logs (resource_type)"))
    op.execute(text("CREATE INDEX idx_audit_logs_actor ON audit_logs (actor)"))


def downgrade() -> None:
    """Revert partitioned tables back to regular tables.

    WARNING: This will convert partitioned tables back to regular tables.
    All partition structure will be lost, but data will be preserved.
    """
    conn = op.get_bind()

    # Downgrade each table
    _downgrade_detections(conn)
    _downgrade_events(conn)
    _downgrade_logs(conn)
    _downgrade_gpu_stats(conn)
    _downgrade_audit_logs(conn)
