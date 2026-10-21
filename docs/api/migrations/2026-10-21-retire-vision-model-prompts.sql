-- Retire the four vision models' prompt surface (B3.3 box 4, R2a row 27): florence2,
-- yolo_world, xclip and fashion_clip leave the prompt data as well as the code.
--
-- `prompt_versions.model` is a NATIVE Postgres enum (`aimodel`, five labels). The runner
-- executes each upgrade in ONE transaction, and `ALTER TYPE ... DROP VALUE` cannot run
-- inside a transaction block at all -- so the enum cannot be shrunk in place. The recorded
-- upgrade instead deletes the four models' rows, converts the column to varchar, and drops
-- the now-unused type; backend/models/prompt_version.py moves its column to a plain String
-- in the same change, so create_all and migrated databases agree (the schema-twins property
-- test_schema_upgrade_path.py pins).
--
-- The row census (Done-when: "changed rows are exactly those four models' rows"):
-- statement 1 removes exactly those rows; statements 2 and 3 change no row values.

BEGIN;

DELETE FROM prompt_versions WHERE model IN ('florence2', 'yolo_world', 'xclip', 'fashion_clip');

ALTER TABLE prompt_versions ALTER COLUMN model TYPE varchar USING model::varchar;

DROP TYPE IF EXISTS aimodel;

COMMIT;
