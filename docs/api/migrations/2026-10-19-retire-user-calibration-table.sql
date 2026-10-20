-- B3.1 (R2a row 11, F-131): retire `user_calibration`.
--
-- OD-29 ruled the per-camera alert floor as the single threshold mechanism,
-- and R2a row 11 retired F-131 (Calibration settings page, CalibrationService,
-- SeverityService.classify_risk, and the user_calibration table).
--
-- Idempotent (DROP TABLE IF EXISTS). On a fresh create_all database the model
-- is gone so the table is never created and the runner's table_absent check
-- records this upgrade as verified without running SQL.

BEGIN;

DROP TABLE IF EXISTS user_calibration;

COMMIT;
