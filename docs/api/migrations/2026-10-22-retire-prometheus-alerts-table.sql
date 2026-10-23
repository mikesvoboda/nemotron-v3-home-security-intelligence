-- Retire the unused `prometheus_alerts` table and its enum (`B4.11`, R2a row 9: F-293).
-- Alertmanager posts to `/api/webhooks/alerts`, not `/api/v1/alertmanager/webhook`.

BEGIN;

DROP TABLE IF EXISTS prometheus_alerts CASCADE;
DROP TYPE IF EXISTS prometheus_alert_status_enum CASCADE;

COMMIT;
