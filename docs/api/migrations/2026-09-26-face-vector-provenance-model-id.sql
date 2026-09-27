-- F11 ruling 2: every stored face vector must say WHICH weights produced it.
--
-- The VLM face specialist compares a probe vector against the stored
-- gallery, and that comparison is only meaningful inside ONE embedding
-- space. Without provenance there is no way to know a gallery was built
-- by different weights than the probe (or, historically, by the
-- np.random.rand(512) enrollment placeholder at all) — the score just
-- looks wrong and gets reported as a similarity.
--
-- The default is the sentinel 'legacy-unknown-provenance', NOT a model id
-- and deliberately not '@'-shaped: a row that never says who computed it
-- is untrusted by default. The guard in the face specialist reads the
-- sentinel as "unavailable (re-enroll)" instead of scoring noise, so the
-- backfill default is what makes historical rows safe.
--
-- face_detection_events needs it too: identify_face_event and the
-- auto-enrollment queue COPY an event's vector into the gallery, and a
-- copy must inherit provenance it earned, never a fresh default.
--
-- Both statements are idempotent (add-column-if-not-exists is the same
-- shape the test-fixture schema drift repair uses) and non-destructive:
-- existing rows keep their vectors and gain the sentinel.
--
-- Run with: psql -d <database> -f 2026-09-26-face-vector-provenance-model-id.sql

BEGIN;

ALTER TABLE face_embeddings
    ADD COLUMN IF NOT EXISTS model_id VARCHAR(128) NOT NULL
        DEFAULT 'legacy-unknown-provenance';

ALTER TABLE face_detection_events
    ADD COLUMN IF NOT EXISTS model_id VARCHAR(128) NOT NULL
        DEFAULT 'legacy-unknown-provenance';

COMMIT;

-- Verification (expect every pre-existing row to read the sentinel):
--   SELECT model_id, count(*) FROM face_embeddings GROUP BY model_id;
--   SELECT model_id, count(*) FROM face_detection_events GROUP BY model_id;
--
-- Rows written by the current server-side extractor carry
-- 'face-recognizer@w600k_r50@<sha[:12]>' instead.
