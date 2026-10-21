-- Retire the write-only `scheduled_reports` table (B3.1, R2a row 43: F-252, F-253, F-255).
-- Ruling 89 retired Scheduled Reports; no scheduler or generator reads `scheduled_reports`.

BEGIN;

DROP TABLE IF EXISTS scheduled_reports CASCADE;

COMMIT;
