-- B3.3 box 6: the columns `backend/models/` declared in January 2026 that NO upgrade ever
-- recorded, and that `create_all` therefore cannot deliver to a database that already existed.
--
-- Why this file exists (the finding, not the cleanup):
--   init_db() builds the schema with create_all, which creates missing TABLES and never alters
--   an existing one. So when events.llm_prompt (b84d05bd5, 2026-01-02), detections.enrichment_data
--   (229fd4890, 2026-01-03), the soft-delete pair cameras.deleted_at / events.deleted_at
--   (431d1832d, NEM-1652, 2026-01-07), events.snooze_until and the user_calibration counts
--   (4b3c8a72e, 18d2f8aaf, 2026-01-12) and the search/labels/feedback columns (194c1a547,
--   2026-01-10) were added to the models, a fresh database got them and a nine-month-old box
--   did not. Nothing noticed, because the TEST FIXTURES quietly added all of them at boot:
--   backend/tests/integration/conftest.py runs 7 ALTER TABLE ... ADD COLUMN statements and
--   backend/tests/conftest.py runs 15 in each of its two twins (sync and async). The union of
--   those sites is 15 columns; 3 of them (the model_id provenance trio) are already recorded
--   upgrades, which leaves the 12 below. The suite was green on a schema that only tests had.
--   That is the exact state this package exists to remove, and the fixture union is a MEASURED
--   list -- not a guess at "what changed recently".
--
-- The three `model_id` ALTERs at the same fixture sites are NOT here: they are already recorded
-- upgrades (0002/0003), which is the proof by contrast that the other thirteen were forgotten.
--
-- Idempotent by construction (ADD COLUMN IF NOT EXISTS) and non-destructive: no type change, no
-- row rewrite, no drop. Per PG 11+ an ADD COLUMN with no default (the nullable ones here) is
-- metadata-only, so unlike NEM-5051's ALTER COLUMN TYPE this takes no long lock.
--
-- It DOES have a CHECK in checks.py, and not because the file is unsafe to re-run -- it is safe.
-- Because on every database `create_all` built fresh, all twelve columns already exist, and
-- without a predicate the runner would fire twelve statements at each of those boots to discover
-- it has nothing to do. Each takes ACCESS EXCLUSIVE on events/detections briefly for a no-op.
-- So the CHECK is all_present(column_present(...)) over the twelve pairs, which are DERIVED from
-- this file's own text at import (checks._add_column_pairs) rather than hand-transcribed. That is
-- the same "is the effect already in place?" question NEM-5051 asks, at lower amplitude.
--
-- The user_calibration counts are NOT NULL DEFAULT 0 to match the model
-- (backend/models/user_calibration.py:54-57, nullable=False) rather than the fixture's nullable
-- version: an old database is supposed to end up shaped like a fresh one, and a fresh one has
-- them NOT NULL. Existing rows get 0, which is what the model's default means anyway.
--
-- NOT included, on purpose -- each is a separate decision with a different failure profile, and
-- bundling them here would hide a destructive lock behind a metadata-only ALTER:
--   * idx_events_active (partial, event.py:250) and idx_events_search_vector (GIN, event.py:224)
--     and ix_detections_enrichment_data_gin (detection.py:135): model-declared indexes create_all
--     cannot add to an existing table either. A GIN/partial build on a populated events table
--     takes minutes, and CREATE INDEX CONCURRENTLY cannot run inside a transaction at all -- and
--     the runner wraps every upgrade in one. So "build these indexes at boot" is a startup
--     lifetime decision, not a fixture cleanup.
--   * idx_cameras_name_unique / idx_cameras_folder_path_unique (camera.py:82-83): these need the
--     duplicate-camera DELETEs the fixture runs first (conftest.py:906-940). On a box that has
--     accumulated two cameras named "Front Door" since 2026-01-02 the index cannot be created
--     without deleting rows, and deleting rows is owner-tier (UR-98).
--   * the CHECK constraints the models declare on the same tables, for the same index reason.
--
-- Run with: python -m backend.migrations            (recorded; do not hand-apply)
--       or: psql -d <database> -f 2026-10-18-add-unrecorded-model-columns.sql

BEGIN;

-- events: analysis prompt, full-text target, snooze, soft delete
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS llm_prompt TEXT;
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS snooze_until TIMESTAMP WITH TIME ZONE;
ALTER TABLE events
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- detections: enrichment payload, full-text target, labels
ALTER TABLE detections
    ADD COLUMN IF NOT EXISTS enrichment_data JSONB;
ALTER TABLE detections
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;
ALTER TABLE detections
    ADD COLUMN IF NOT EXISTS labels JSONB;

-- cameras: soft delete
ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

-- user_calibration: the three counters (model: NOT NULL DEFAULT 0)
ALTER TABLE user_calibration
    ADD COLUMN IF NOT EXISTS correct_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_calibration
    ADD COLUMN IF NOT EXISTS missed_threat_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_calibration
    ADD COLUMN IF NOT EXISTS severity_wrong_count INTEGER NOT NULL DEFAULT 0;

-- event_feedback: what the user expected when severity was wrong
ALTER TABLE event_feedback
    ADD COLUMN IF NOT EXISTS expected_severity VARCHAR;

COMMIT;

-- Verification (expect 12 rows, one per column; 13 statements because detections.enrichment_data
-- and detections.search_vector are both on detections):
--   SELECT table_name, column_name FROM information_schema.columns
--    WHERE (table_name, column_name) IN (
--      ('events','llm_prompt'), ('events','search_vector'), ('events','snooze_until'),
--      ('events','deleted_at'), ('detections','enrichment_data'), ('detections','search_vector'),
--      ('detections','labels'), ('cameras','deleted_at'), ('user_calibration','correct_count'),
--      ('user_calibration','missed_threat_count'), ('user_calibration','severity_wrong_count'),
--      ('event_feedback','expected_severity'))
--    ORDER BY table_name, column_name;
-- (12 rows: the two search_vector columns share a name, so the pair form counts them once each.)
