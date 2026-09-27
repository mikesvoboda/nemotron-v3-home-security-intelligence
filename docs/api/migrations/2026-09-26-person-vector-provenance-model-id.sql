-- F11 ruling 2, extended to person vectors (owner ruling, ledger item 20:
-- the full re-ID swap — OSNet-AIN x1.0 is the ONE person-vector space).
--
-- The household re-ID gallery was CLIP-768 while the resident re-ID model
-- is OSNet-512, so a probe and a gallery could sit in different embedding
-- spaces with nothing in the row saying so: the score just looked wrong and
-- got reported as a similarity. Every stored person vector now names the
-- weights that computed it, and a cross-space comparison answers
-- "unavailable (re-enroll)" instead of scoring.
--
-- The default is the sentinel 'legacy-unknown-provenance', NOT a model id
-- and deliberately not '@'-shaped: a row that never says who computed it
-- is untrusted by default. There is no backfill and no legacy shim (the
-- ruling is explicit about backwards incompatibility) — the existing
-- vectors are CLIP bytes, they KEEP their bytes and gain the sentinel, and
-- every comparison refuses them until the household re-enrolls under the
-- pinned OSNet weights. That refusal IS drop-and-re-enroll, expressed
-- honestly in the data rather than by a destructive migration.
--
-- Idempotent (add-column-if-not-exists, the same shape the test-fixture
-- schema drift repair uses) and non-destructive.
--
-- Run with: psql -d <database> -f 2026-09-26-person-vector-provenance-model-id.sql

BEGIN;

ALTER TABLE person_embeddings
    ADD COLUMN IF NOT EXISTS model_id VARCHAR(128) NOT NULL
        DEFAULT 'legacy-unknown-provenance';

COMMIT;

-- Verification (expect every pre-existing row to read the sentinel):
--   SELECT model_id, count(*) FROM person_embeddings GROUP BY model_id;
--
-- Rows written by the swapped producer carry
-- 'osnet-ain-x1-0@osnet_ain_x1_0_msmt17@<sha[:12]>' instead.
