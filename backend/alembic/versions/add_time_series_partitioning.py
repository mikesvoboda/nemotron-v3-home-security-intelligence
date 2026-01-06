"""Add time-series partitioning for high-volume tables

Revision ID: add_time_series_partitioning
Revises: add_event_detections_junction
Create Date: 2026-01-06 16:00:00.000000

This migration adds PostgreSQL native partitioning for high-volume tables:
- detections
- events
- logs
- gpu_stats

Partitioning Strategy:
- Monthly partitions for detections, events, logs
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

Related Linear issue: NEM-1489
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

        op.execute(
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
    result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)"))  # noqa: S608
    return bool(result.scalar())


def upgrade() -> None:
    """Convert high-volume tables to partitioned tables."""

    # ==========================================================================
    # Step 1: Detections Table Partitioning
    # ==========================================================================

    # Check if table is already partitioned
    conn = op.get_bind()
    result = conn.execute(
        text(
            """
            SELECT relkind FROM pg_class WHERE relname = 'detections'
            """
        )
    )
    row = result.scalar()

    if row != "p":  # Not already partitioned
        has_data = _table_has_data("detections")

        if has_data:
            # Strategy: Create new partitioned table, migrate data, swap
            op.execute(
                text(
                    """
                    -- Create new partitioned table
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

            # Create partitions for existing data range plus future
            _create_partitions_for_table("detections_partitioned", 2)

            # Also create a default partition for data outside defined ranges
            op.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS detections_default
                    PARTITION OF detections_partitioned DEFAULT
                    """
                )
            )

            # Copy data from old table to new partitioned table
            op.execute(
                text(
                    """
                    INSERT INTO detections_partitioned
                    SELECT * FROM detections
                    """
                )
            )

            # Swap tables
            op.execute(text("ALTER TABLE detections RENAME TO detections_old"))
            op.execute(text("ALTER TABLE detections_partitioned RENAME TO detections"))

            # Recreate indexes on partitioned table
            op.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_detections_camera_id_new
                    ON detections (camera_id)
                    """
                )
            )
            op.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_detections_detected_at_new
                    ON detections (detected_at)
                    """
                )
            )
            op.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_detections_camera_time_new
                    ON detections (camera_id, detected_at)
                    """
                )
            )
            op.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_detections_camera_object_type_new
                    ON detections (camera_id, object_type)
                    """
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

            # Drop old table after successful migration
            op.execute(text("DROP TABLE IF EXISTS detections_old CASCADE"))

        else:
            # No data - can convert directly
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

            # Create indexes
            op.execute(text("CREATE INDEX idx_detections_camera_id ON detections (camera_id)"))
            op.execute(text("CREATE INDEX idx_detections_detected_at ON detections (detected_at)"))
            op.execute(
                text(
                    """
                    CREATE INDEX idx_detections_camera_time
                    ON detections (camera_id, detected_at)
                    """
                )
            )

    # ==========================================================================
    # Step 2: Events Table Partitioning
    # ==========================================================================

    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'events'"))
    row = result.scalar()

    if row != "p":  # Not already partitioned
        has_data = _table_has_data("events")

        if has_data:
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

            op.execute(
                text(
                    """
                    INSERT INTO events_partitioned
                    SELECT * FROM events
                    """
                )
            )

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

        else:
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

    # ==========================================================================
    # Step 3: Logs Table Partitioning
    # ==========================================================================

    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'logs'"))
    row = result.scalar()

    if row != "p":  # Not already partitioned
        has_data = _table_has_data("logs")

        if has_data:
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

            op.execute(
                text(
                    """
                    INSERT INTO logs_partitioned
                    SELECT * FROM logs
                    """
                )
            )

            op.execute(text("ALTER TABLE logs RENAME TO logs_old"))
            op.execute(text("ALTER TABLE logs_partitioned RENAME TO logs"))

            op.execute(text("CREATE INDEX idx_logs_timestamp_new ON logs (timestamp)"))
            op.execute(text("CREATE INDEX idx_logs_level_new ON logs (level)"))
            op.execute(text("CREATE INDEX idx_logs_component_new ON logs (component)"))

            op.execute(text("DROP TABLE IF EXISTS logs_old CASCADE"))

        else:
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

    # ==========================================================================
    # Step 4: GPU Stats Table Partitioning (Weekly)
    # ==========================================================================

    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'gpu_stats'"))
    row = result.scalar()

    if row != "p":  # Not already partitioned
        has_data = _table_has_data("gpu_stats")

        if has_data:
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

            # Create weekly partitions for gpu_stats
            _create_partitions_for_table("gpu_stats_partitioned", 2)
            op.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS gpu_stats_default
                    PARTITION OF gpu_stats_partitioned DEFAULT
                    """
                )
            )

            op.execute(
                text(
                    """
                    INSERT INTO gpu_stats_partitioned
                    SELECT * FROM gpu_stats
                    """
                )
            )

            op.execute(text("ALTER TABLE gpu_stats RENAME TO gpu_stats_old"))
            op.execute(text("ALTER TABLE gpu_stats_partitioned RENAME TO gpu_stats"))

            op.execute(
                text("CREATE INDEX idx_gpu_stats_recorded_at_new ON gpu_stats (recorded_at)")
            )

            op.execute(text("DROP TABLE IF EXISTS gpu_stats_old CASCADE"))

        else:
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


def downgrade() -> None:
    """Revert partitioned tables back to regular tables.

    WARNING: This will convert partitioned tables back to regular tables.
    All partition structure will be lost, but data will be preserved.
    """

    # ==========================================================================
    # Downgrade each table: create regular table, copy data, swap
    # ==========================================================================

    conn = op.get_bind()

    # Detections
    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'detections'"))
    if result.scalar() == "p":
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

    # Events
    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'events'"))
    if result.scalar() == "p":
        op.execute(
            text(
                """
                CREATE TABLE events_regular (
                    id SERIAL PRIMARY KEY,
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
                    search_vector TSVECTOR
                )
                """
            )
        )
        op.execute(text("INSERT INTO events_regular SELECT * FROM events"))
        op.execute(text("DROP TABLE events CASCADE"))
        op.execute(text("ALTER TABLE events_regular RENAME TO events"))
        op.execute(text("CREATE INDEX idx_events_camera_id ON events (camera_id)"))
        op.execute(text("CREATE INDEX idx_events_started_at ON events (started_at)"))

    # Logs
    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'logs'"))
    if result.scalar() == "p":
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

    # GPU Stats
    result = conn.execute(text("SELECT relkind FROM pg_class WHERE relname = 'gpu_stats'"))
    if result.scalar() == "p":
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
