-- B4.7: Arming core additive schema upgrade (docs/uplevel/4n-arming.md).
--
-- Adds:
--   * arming_state: single-row current mode, source, set_at, schedule_updated_at
--   * arming_mode_exclusions: (mode, camera_id) exclusions with ON DELETE CASCADE
--   * arming_schedule: weekly schedule entries (days, time, mode)
--   * arming_changes: 365-day audit log of mode and camera exclusion changes
--     carrying every mode's exclusions after each change
--   * alert_rules: alert_on_rejected_modes, sources, and seeded "External alerts" rule
--   * alerts: raised_while_unarmed
--   * events: source ('camera' | 'external'), external_source

BEGIN;

CREATE TABLE IF NOT EXISTS arming_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    mode VARCHAR(32) NOT NULL DEFAULT 'home',
    set_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT timezone('utc', now()),
    source_kind VARCHAR(32) NOT NULL DEFAULT 'system',
    source_name VARCHAR(255) NOT NULL DEFAULT 'system',
    schedule_updated_at TIMESTAMP WITH TIME ZONE
);

INSERT INTO arming_state (id, mode, set_at, source_kind, source_name)
VALUES (1, 'home', timezone('utc', now()), 'system', 'system')
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS arming_mode_exclusions (
    mode VARCHAR(32) NOT NULL,
    camera_id VARCHAR(255) NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    PRIMARY KEY (mode, camera_id)
);

CREATE INDEX IF NOT EXISTS idx_arming_mode_exclusions_mode ON arming_mode_exclusions (mode);

CREATE TABLE IF NOT EXISTS arming_schedule (
    id SERIAL PRIMARY KEY,
    days JSONB NOT NULL,
    time VARCHAR(16) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT timezone('utc', now())
);

CREATE TABLE IF NOT EXISTS arming_changes (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(32) NOT NULL,
    from_value JSONB,
    to_value JSONB NOT NULL,
    mode_after VARCHAR(32) NOT NULL DEFAULT 'home',
    exclusions_after JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_kind VARCHAR(32) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_arming_changes_changed_at ON arming_changes (changed_at);

ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS alert_on_rejected_modes JSONB;
ALTER TABLE alert_rules
    ADD COLUMN IF NOT EXISTS sources JSONB NOT NULL DEFAULT '["camera"]'::jsonb;

ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS raised_while_unarmed BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE events
    ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'camera';
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS external_source VARCHAR(100);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'alert_rules'
          AND column_name = 'id'
          AND data_type = 'uuid'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'alert_rules'
          AND column_name = 'severity'
    ) THEN
        INSERT INTO alert_rules (
            id,
            name,
            description,
            enabled,
            severity,
            risk_threshold,
            object_types,
            camera_ids,
            excluded_camera_ids,
            zone_ids,
            min_confidence,
            schedule,
            dwell_time_enabled,
            exclude_household_members,
            threat_detection_enabled,
            dedup_key_template,
            cooldown_seconds,
            channels,
            alert_on_rejected,
            alert_on_rejected_modes,
            sources,
            created_at,
            updated_at
        )
        VALUES (
            '00000000-0000-4000-8000-00000000e470',
            'External alerts',
            'Seeded rule for external webhook alerts (B4.7)',
            TRUE,
            'low',
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            FALSE,
            FALSE,
            FALSE,
            '{camera_id}:{object_type}:{rule_id}',
            300,
            '[]'::jsonb,
            FALSE,
            NULL,
            '["external"]'::jsonb,
            timezone('utc', now()),
            timezone('utc', now())
        )
        ON CONFLICT (id) DO NOTHING;
    END IF;
END $$;

COMMIT;
