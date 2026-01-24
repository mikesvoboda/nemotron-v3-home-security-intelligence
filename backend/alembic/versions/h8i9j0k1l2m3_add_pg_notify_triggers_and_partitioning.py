"""Add PostgreSQL LISTEN/NOTIFY triggers and table partitioning infrastructure.

This migration adds:
1. LISTEN/NOTIFY triggers on events and detections tables
2. Partition management functions for time-series data
3. Views and helper functions for partition maintenance

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-01-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h8i9j0k1l2m3"
down_revision: str | None = "g7h8i9j0k1l2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply LISTEN/NOTIFY triggers and partition management infrastructure."""
    # =========================================================================
    # 1. CREATE NOTIFY TRIGGER FUNCTION
    # =========================================================================
    # This function is called by table triggers to send NOTIFY events
    # with the row data as JSON payload

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION notify_table_change()
            RETURNS TRIGGER AS $$
            DECLARE
                payload JSON;
                channel_name TEXT;
            BEGIN
                -- Determine channel name based on table and operation
                IF TG_OP = 'INSERT' THEN
                    channel_name := TG_TABLE_NAME || '_new';
                ELSIF TG_OP = 'UPDATE' THEN
                    channel_name := TG_TABLE_NAME || '_update';
                ELSIF TG_OP = 'DELETE' THEN
                    channel_name := TG_TABLE_NAME || '_delete';
                END IF;

                -- Build payload with operation type and row data
                IF TG_OP = 'DELETE' THEN
                    payload := json_build_object(
                        'operation', TG_OP,
                        'table', TG_TABLE_NAME,
                        'data', row_to_json(OLD)
                    );
                ELSE
                    payload := json_build_object(
                        'operation', TG_OP,
                        'table', TG_TABLE_NAME,
                        'data', row_to_json(NEW)
                    );
                END IF;

                -- Send notification (max 8000 bytes payload)
                -- Truncate large payloads to prevent errors
                IF length(payload::text) > 7500 THEN
                    -- For large payloads, send minimal info
                    IF TG_OP = 'DELETE' THEN
                        payload := json_build_object(
                            'operation', TG_OP,
                            'table', TG_TABLE_NAME,
                            'data', json_build_object('id', OLD.id)
                        );
                    ELSE
                        payload := json_build_object(
                            'operation', TG_OP,
                            'table', TG_TABLE_NAME,
                            'data', json_build_object('id', NEW.id)
                        );
                    END IF;
                END IF;

                PERFORM pg_notify(channel_name, payload::text);

                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                ELSE
                    RETURN NEW;
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # =========================================================================
    # 2. CREATE TRIGGERS ON EVENTS TABLE
    # =========================================================================

    # Trigger for new events (INSERT)
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS events_notify_insert ON events;
            CREATE TRIGGER events_notify_insert
                AFTER INSERT ON events
                FOR EACH ROW
                EXECUTE FUNCTION notify_table_change();
            """
        )
    )

    # Trigger for event updates (UPDATE)
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS events_notify_update ON events;
            CREATE TRIGGER events_notify_update
                AFTER UPDATE ON events
                FOR EACH ROW
                WHEN (OLD.* IS DISTINCT FROM NEW.*)
                EXECUTE FUNCTION notify_table_change();
            """
        )
    )

    # =========================================================================
    # 3. CREATE TRIGGERS ON DETECTIONS TABLE
    # =========================================================================

    # Trigger for new detections (INSERT)
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS detections_notify_insert ON detections;
            CREATE TRIGGER detections_notify_insert
                AFTER INSERT ON detections
                FOR EACH ROW
                EXECUTE FUNCTION notify_table_change();
            """
        )
    )

    # =========================================================================
    # 4. CREATE TRIGGERS ON ALERTS TABLE
    # =========================================================================

    # Trigger for new alerts (INSERT)
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS alerts_notify_insert ON alerts;
            CREATE TRIGGER alerts_notify_insert
                AFTER INSERT ON alerts
                FOR EACH ROW
                EXECUTE FUNCTION notify_table_change();
            """
        )
    )

    # Trigger for alert updates (UPDATE)
    op.execute(
        sa.text(
            """
            DROP TRIGGER IF EXISTS alerts_notify_update ON alerts;
            CREATE TRIGGER alerts_notify_update
                AFTER UPDATE ON alerts
                FOR EACH ROW
                WHEN (OLD.* IS DISTINCT FROM NEW.*)
                EXECUTE FUNCTION notify_table_change();
            """
        )
    )

    # =========================================================================
    # 5. CREATE PARTITION MANAGEMENT FUNCTIONS
    # =========================================================================

    # Function to create a partition for a specific month
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION create_monthly_partition(
                parent_table TEXT,
                partition_column TEXT,
                partition_date DATE
            )
            RETURNS TEXT AS $$
            DECLARE
                partition_name TEXT;
                start_date DATE;
                end_date DATE;
            BEGIN
                -- Calculate partition bounds (first and last day of month)
                start_date := date_trunc('month', partition_date);
                end_date := start_date + INTERVAL '1 month';

                -- Generate partition name: tablename_yYYYYmMM
                partition_name := parent_table || '_y' ||
                    to_char(start_date, 'YYYY') || 'm' ||
                    to_char(start_date, 'MM');

                -- Check if partition already exists
                IF EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = partition_name
                    AND relkind = 'r'
                ) THEN
                    RETURN 'EXISTS:' || partition_name;
                END IF;

                -- Create the partition
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                     FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    parent_table,
                    start_date,
                    end_date
                );

                RETURN 'CREATED:' || partition_name;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # Function to create partitions for a date range
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION ensure_partitions_exist(
                parent_table TEXT,
                partition_column TEXT,
                months_ahead INTEGER DEFAULT 2
            )
            RETURNS TABLE(partition_name TEXT, status TEXT) AS $$
            DECLARE
                current_month DATE;
                i INTEGER;
            BEGIN
                current_month := date_trunc('month', CURRENT_DATE);

                FOR i IN 0..months_ahead LOOP
                    SELECT
                        split_part(
                            create_monthly_partition(
                                parent_table,
                                partition_column,
                                current_month + (i || ' month')::interval
                            ),
                            ':',
                            2
                        ),
                        split_part(
                            create_monthly_partition(
                                parent_table,
                                partition_column,
                                current_month + (i || ' month')::interval
                            ),
                            ':',
                            1
                        )
                    INTO partition_name, status;

                    RETURN NEXT;
                END LOOP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # Function to drop old partitions beyond retention
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION drop_old_partitions(
                parent_table TEXT,
                retention_months INTEGER DEFAULT 12
            )
            RETURNS TABLE(partition_name TEXT, dropped BOOLEAN) AS $$
            DECLARE
                rec RECORD;
                cutoff_date DATE;
                partition_date DATE;
            BEGIN
                cutoff_date := CURRENT_DATE - (retention_months || ' months')::interval;

                -- Find all partitions of the parent table
                FOR rec IN
                    SELECT c.relname AS partition_name,
                           pg_get_expr(c.relpartbound, c.oid) AS bounds
                    FROM pg_class c
                    JOIN pg_inherits i ON c.oid = i.inhrelid
                    JOIN pg_class p ON i.inhparent = p.oid
                    WHERE p.relname = parent_table
                    AND c.relkind = 'r'
                LOOP
                    -- Extract date from partition bounds
                    -- Format: FOR VALUES FROM ('YYYY-MM-DD') TO ('YYYY-MM-DD')
                    BEGIN
                        partition_date := (
                            regexp_match(rec.bounds, E'TO \\(''([^'']+)''\\)')
                        )[1]::date;

                        IF partition_date < cutoff_date THEN
                            EXECUTE format('DROP TABLE IF EXISTS %I', rec.partition_name);
                            partition_name := rec.partition_name;
                            dropped := TRUE;
                            RETURN NEXT;
                        END IF;
                    EXCEPTION WHEN OTHERS THEN
                        -- Skip partitions with unparseable bounds
                        CONTINUE;
                    END;
                END LOOP;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # Function to get partition statistics
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION get_partition_stats(parent_table TEXT)
            RETURNS TABLE(
                partition_name TEXT,
                start_date DATE,
                end_date DATE,
                row_count BIGINT,
                size_bytes BIGINT
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    c.relname::TEXT AS partition_name,
                    (regexp_match(
                        pg_get_expr(c.relpartbound, c.oid),
                        E'FROM \\(''([^'']+)''\\)'
                    ))[1]::DATE AS start_date,
                    (regexp_match(
                        pg_get_expr(c.relpartbound, c.oid),
                        E'TO \\(''([^'']+)''\\)'
                    ))[1]::DATE AS end_date,
                    c.reltuples::BIGINT AS row_count,
                    pg_relation_size(c.oid) AS size_bytes
                FROM pg_class c
                JOIN pg_inherits i ON c.oid = i.inhrelid
                JOIN pg_class p ON i.inhparent = p.oid
                WHERE p.relname = parent_table
                AND c.relkind = 'r'
                ORDER BY start_date;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )

    # =========================================================================
    # 6. CREATE VIEW FOR PARTITION MONITORING
    # =========================================================================

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE VIEW v_partition_summary AS
            SELECT
                p.relname AS parent_table,
                COUNT(c.relname) AS partition_count,
                SUM(c.reltuples)::BIGINT AS total_rows,
                pg_size_pretty(SUM(pg_relation_size(c.oid))) AS total_size,
                MIN((regexp_match(
                    pg_get_expr(c.relpartbound, c.oid),
                    E'FROM \\(''([^'']+)''\\)'
                ))[1])::DATE AS oldest_partition,
                MAX((regexp_match(
                    pg_get_expr(c.relpartbound, c.oid),
                    E'TO \\(''([^'']+)''\\)'
                ))[1])::DATE AS newest_partition_end
            FROM pg_class p
            JOIN pg_inherits i ON p.oid = i.inhparent
            JOIN pg_class c ON i.inhrelid = c.oid
            WHERE p.relkind = 'p'  -- partitioned table
            AND c.relkind = 'r'    -- regular table (partition)
            GROUP BY p.relname
            ORDER BY p.relname;
            """
        )
    )

    # =========================================================================
    # 7. CREATE SCHEDULED PARTITION MAINTENANCE PROCEDURE
    # =========================================================================
    # This can be called by pg_cron or application scheduler

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE PROCEDURE maintain_partitions(
                retention_months INTEGER DEFAULT 12,
                months_ahead INTEGER DEFAULT 2
            )
            LANGUAGE plpgsql
            AS $$
            DECLARE
                partitioned_tables TEXT[] := ARRAY['events', 'detections'];
                tbl TEXT;
            BEGIN
                FOREACH tbl IN ARRAY partitioned_tables LOOP
                    -- Only process if table is partitioned
                    IF EXISTS (
                        SELECT 1 FROM pg_class
                        WHERE relname = tbl AND relkind = 'p'
                    ) THEN
                        -- Create future partitions
                        PERFORM * FROM ensure_partitions_exist(tbl, 'started_at', months_ahead);

                        -- Drop old partitions
                        PERFORM * FROM drop_old_partitions(tbl, retention_months);

                        RAISE NOTICE 'Maintained partitions for table: %', tbl;
                    END IF;
                END LOOP;
            END;
            $$;
            """
        )
    )


def downgrade() -> None:
    """Remove LISTEN/NOTIFY triggers and partition management infrastructure."""
    # Drop triggers
    op.execute(sa.text("DROP TRIGGER IF EXISTS events_notify_insert ON events;"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS events_notify_update ON events;"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS detections_notify_insert ON detections;"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS alerts_notify_insert ON alerts;"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS alerts_notify_update ON alerts;"))

    # Drop views
    op.execute(sa.text("DROP VIEW IF EXISTS v_partition_summary;"))

    # Drop procedures and functions
    op.execute(sa.text("DROP PROCEDURE IF EXISTS maintain_partitions;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS get_partition_stats;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS drop_old_partitions;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS ensure_partitions_exist;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS create_monthly_partition;"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS notify_table_change;"))
