-- R8 S4 (owner ruling 2026-09-30): retire `demographics_results` and
-- `reid_embeddings`.
--
-- WHY THESE TWO AND NOT THE OTHER THREE ENRICHMENT CHILD TABLES
-- ---------------------------------------------------------------------------
-- `backend/models/enrichment.py` shipped five per-detection child tables.
-- Measurement (recorded in ledger items 52-53) established two facts the
-- scope doc had wrong:
--
--   * NO shipped code writes ANY of the five. The only writer ever was
--     `backend/services/enrichment_pipeline.py` (deleted in R8 S2b); after
--     that, only `scripts/seed-events.py` constructed rows, and shipped code
--     never invokes that script. So "legacy-only" was never a discriminator.
--   * `pose_results` and `action_results` ARE read on a shipped path:
--     `alert_engine._evaluate_rule` -> `_check_pose_type` / `_check_action_type`
--     -> `POST /api/alerts/rules/{rule_id}/test` -- the identical reader that
--     is the sole stated reason `threat_detections` is KEPT. The owner ruling
--     therefore keeps all three of those tables (retiring pose/action later
--     must null stored rule values + drop the rule columns + drop the tables +
--     retarget the contract oracles in ONE commit, or a stored rule 500s on a
--     missing table forever).
--
-- `demographics_results` and `reid_embeddings` have ZERO live readers and zero
-- shipped writers -- unambiguously janitorial, which is what this slice is for.
--
-- NAME TRAPS THIS DROP DOES NOT TOUCH (do not "tidy" them later):
--   * `person_embeddings` (household.PersonEmbedding) -- the LIVE VLM re-ID
--     gallery; the closest name-twin of the table dropped here.
--   * `detections.enrichment_data -> 'reid_embedding'` -- a JSONB key with a
--     live write path (POST/PATCH /api/detections/bulk); a key, not a table.
--   * `tracks.reid_embedding`, `registered_vehicles.reid_embedding` --
--     LargeBinary columns on other, live models.
--
-- Neither table is read by any shipped query (measured: zero selects outside
-- tests/archive), so dropping them cannot 500 a route. Existing rows are
-- per-detection analysis output with no surviving consumer and no provenance
-- requirement; they go with the tables.
--
-- Both statements are idempotent (IF EXISTS, the same shape as the face/person
-- provenance files) and wrapped in one transaction, so a fresh DB (tables never
-- created) and a twice-applied runbook both succeed.
--
-- This repo has no Alembic (schema ships from backend/scripts/init_schema.py +
-- create_all); nothing in-repo applies files from this directory. THIS FILE IS
-- THE OPERATOR RUNBOOK for databases that predate the retirement: on a fresh
-- deploy it is a no-op, and create_all will not recreate the tables because
-- their model classes are gone from backend/models/enrichment.py.
--
-- Run with: psql -d <database> -f 2026-09-30-retire-demographics-reid-tables.sql

BEGIN;

-- CASCADE to detections is defined on the child FKs, so no orphan rows are
-- left behind when the children go; detections themselves are untouched.
DROP TABLE IF EXISTS reid_embeddings;
DROP TABLE IF EXISTS demographics_results;

COMMIT;

-- Verification (expect both counts to fail with "relation does not exist"):
--   SELECT count(*) FROM demographics_results;
--   SELECT count(*) FROM reid_embeddings;
-- And the three surviving enrichment tables must still answer:
--   SELECT count(*) FROM pose_results;
--   SELECT count(*) FROM threat_detections;
--   SELECT count(*) FROM action_results;
