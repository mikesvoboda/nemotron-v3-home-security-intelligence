-- NEM-5051: Convert JSON columns to JSONB in Alert models
--
-- This migration converts all JSON columns in alerts and alert_rules tables
-- to JSONB for better indexing and query performance.
--
-- Benefits of JSONB over JSON:
-- - Supports GIN indexes for fast containment queries (@>, ?, ?|, ?&)
-- - Supports btree indexes on specific paths
-- - Stores data in decomposed binary format (slightly smaller, much faster to query)
-- - Removes duplicate keys and whitespace during storage
--
-- Note: This is a non-destructive change - existing JSON data is automatically
-- converted to JSONB. The conversion preserves all data.
--
-- Run this migration with: psql -d <database> -f NEM-5051-convert-alert-json-to-jsonb.sql

BEGIN;

-- Convert alerts table columns
ALTER TABLE alerts
    ALTER COLUMN channels TYPE JSONB USING channels::jsonb,
    ALTER COLUMN metadata TYPE JSONB USING metadata::jsonb;

-- Convert alert_rules table columns
ALTER TABLE alert_rules
    ALTER COLUMN object_types TYPE JSONB USING object_types::jsonb,
    ALTER COLUMN camera_ids TYPE JSONB USING camera_ids::jsonb,
    ALTER COLUMN zone_ids TYPE JSONB USING zone_ids::jsonb,
    ALTER COLUMN schedule TYPE JSONB USING schedule::jsonb,
    ALTER COLUMN conditions TYPE JSONB USING conditions::jsonb,
    ALTER COLUMN channels TYPE JSONB USING channels::jsonb;

-- Optional: Add GIN indexes for common JSONB queries
-- Uncomment these if you need fast containment queries on these columns

-- CREATE INDEX CONCURRENTLY idx_alerts_metadata_gin ON alerts USING GIN (metadata);
-- CREATE INDEX CONCURRENTLY idx_alerts_channels_gin ON alerts USING GIN (channels);
-- CREATE INDEX CONCURRENTLY idx_alert_rules_object_types_gin ON alert_rules USING GIN (object_types);
-- CREATE INDEX CONCURRENTLY idx_alert_rules_camera_ids_gin ON alert_rules USING GIN (camera_ids);
-- CREATE INDEX CONCURRENTLY idx_alert_rules_zone_ids_gin ON alert_rules USING GIN (zone_ids);

COMMIT;

-- Verify the changes
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('alerts', 'alert_rules')
    AND data_type = 'jsonb'
ORDER BY table_name, column_name;
