-- B3.1 R2a row 32 (F-220): retire pose, action, and smoke/fire condition columns on alert_rules
--
-- Owner ruling 89 (R2a row 32) retired the pose, action, and smoke/fire alert rule conditions
-- (keeping the threat condition for OD-7 part 1).
--
-- Run with: python -m backend.migrations            (recorded; do not hand-apply)
--       or: psql -d <database> -f 2026-10-20-retire-alert-rule-pose-action-smoke-columns.sql

BEGIN;

ALTER TABLE alert_rules
    DROP COLUMN IF EXISTS pose_types,
    DROP COLUMN IF EXISTS pose_confidence_threshold,
    DROP COLUMN IF EXISTS action_types,
    DROP COLUMN IF EXISTS action_confidence_threshold,
    DROP COLUMN IF EXISTS smoke_fire_detection_enabled,
    DROP COLUMN IF EXISTS smoke_fire_consecutive_required,
    DROP COLUMN IF EXISTS smoke_fire_confidence_threshold;

COMMIT;
