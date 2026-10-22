-- B4.2: Alert delivery additive schema upgrade (docs/uplevel/4n-alerting.md).
--
-- Adds columns to EXISTING tables only. The new tables (recipients,
-- recipient_channels, notification_deliveries) and their enum types are owned by
-- create_all, mirroring how 0012's alert_events/activity_snoozes tables were
-- shipped (0012 carried them inline; the delivery tables are modelled in
-- backend/models/alert_delivery.py and are created by create_all).
--
-- Adds:
--   * quiet_hours_periods: recipient_id (nullable FK to recipients.id)
--     -- the "Household" recipient owns the existing quiet-hours rows; the seed
--     below creates that recipient once and points existing rows at it
--   * outbound_webhooks: on_local_network (ruling 310: the same destination
--     policy that alerts use applies to outbound webhooks, with a per-channel
--     local-network allowance)

BEGIN;

ALTER TABLE quiet_hours_periods
    ADD COLUMN IF NOT EXISTS recipient_id UUID;

ALTER TABLE outbound_webhooks
    ADD COLUMN IF NOT EXISTS on_local_network BOOLEAN NOT NULL DEFAULT FALSE;

-- Seed the "Household" recipient (idempotent) and hand it the existing
-- quiet-hours rows. No user link, browser channel added later by create_all-era
-- setup; the recipient has no settings-derived state, so plain SQL suffices.
-- id is a native uuid column (the model marshals strings through the driver),
-- so the generated key is cast to uuid here.
INSERT INTO recipients (id, name, enabled, critical_breaks_quiet, created_at, updated_at)
SELECT gen_random_uuid(), 'Household', TRUE, TRUE,
       timezone('utc', now()), timezone('utc', now())
WHERE NOT EXISTS (SELECT 1 FROM recipients WHERE name = 'Household');

UPDATE quiet_hours_periods
SET recipient_id = (SELECT id FROM recipients WHERE name = 'Household')
WHERE recipient_id IS NULL;

COMMIT;
