-- B3.1 R2a row 36 (F-177): retire gpu_devices table
--
-- Owner ruling 89 (R2a row 36) retired F-177 (Rescan GPUs / POST /api/system/gpu-config/detect),
-- which was the sole writer and reader of the gpu_devices table.
--
-- Run with: python -m backend.migrations            (recorded; do not hand-apply)
--       or: psql -d <database> -f 2026-10-20-retire-gpu-devices-table.sql

BEGIN;

DROP TABLE IF EXISTS gpu_devices CASCADE;

COMMIT;
