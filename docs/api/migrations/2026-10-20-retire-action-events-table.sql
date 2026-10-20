-- B3.1 R2a row 32 (F-068): retire the action_events table.
-- The X-CLIP / ST-GCN++ action recognition chain and /api/action-events routes are retired.

DROP TABLE IF EXISTS action_events CASCADE;
