-- B4.1: Alert pipeline core additive schema upgrade (docs/uplevel/4n-alerting.md).
--
-- Adds:
--   * alerts: verdict_source, match_count, last_seen_at, last_event_id
--   * alerts.status: adds 'open' to alert_status and migrates existing
--     'pending' and 'delivered' rows to 'open'
--   * alert_rules: alert_on_rejected, excluded_camera_ids
--   * alert_events: join table (alert_id, event_id) for created and folded events
--   * activity_snoozes: same-activity snooze table (camera_id, object_type, until)

BEGIN;

ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS verdict_source VARCHAR(32);
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS match_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS last_event_id INTEGER;

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS alert_on_rejected BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS excluded_camera_ids JSONB;

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id UUID NOT NULL,
    event_id INTEGER NOT NULL,
    PRIMARY KEY (alert_id, event_id)
);

CREATE TABLE IF NOT EXISTS activity_snoozes (
    id SERIAL PRIMARY KEY,
    camera_id VARCHAR(255) NOT NULL,
    object_type VARCHAR(100) NOT NULL,
    until TIMESTAMP WITH TIME ZONE NOT NULL,
    source_event_id INTEGER,
    source_alert_id UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT timezone('utc', now())
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alert_status') THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'alert_status' AND e.enumlabel = 'open'
        ) THEN
            ALTER TYPE alert_status RENAME TO alert_status_pre_0012;
            CREATE TYPE alert_status AS ENUM (
                'open', 'pending', 'delivered', 'acknowledged', 'dismissed'
            );
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'alerts' AND column_name = 'status'
            ) THEN
                ALTER TABLE alerts
                    ALTER COLUMN status DROP DEFAULT,
                    ALTER COLUMN status TYPE alert_status USING (
                        CASE
                            WHEN status::text IN ('pending', 'delivered') THEN 'open'::alert_status
                            ELSE status::text::alert_status
                        END
                    ),
                    ALTER COLUMN status SET DEFAULT 'open'::alert_status;
            END IF;
            DROP TYPE alert_status_pre_0012;
        ELSIF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'alerts' AND column_name = 'status'
        ) THEN
            UPDATE alerts
            SET status = 'open'::alert_status
            WHERE status::text IN ('pending', 'delivered');
        END IF;
    END IF;
END $$;

COMMIT;
