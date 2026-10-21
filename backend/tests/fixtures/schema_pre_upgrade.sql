-- B3.3: a SAVED pre-upgrade schema, with rows. This is the database that existed on a box before
-- the upgrades in backend/migrations/registry.py were written, and it is what
-- backend/tests/integration/test_schema_upgrade_path.py upgrades.
--
-- Why it is a file and not a Python string: the package's Done-when is "a database saved from
-- today's main upgrades with its rows intact in CI". A .sql file is that saved database in the
-- only form that survives a repo, is diffable, and can be loaded by a test or by hand with psql.
--
-- The shapes below are the ones the upgrades act on, transcribed from the upgrade files' own
-- assumptions: JSON (not JSONB) columns per NEM-5051, no model_id column per the two provenance
-- files, and reid_embeddings/demographics_results still present per the retirement file.
--
-- Deliberately omitted: the `vector(...)` columns those tables also had. pgvector is not what is
-- under test -- no upgrade reads or rewrites a vector column -- and leaving it out
-- keeps this fixture loadable on any PostgreSQL, including a plain one. The columns are named
-- with their real column names so the checks see real tables, and the rows carry the values the
-- test asserts survived.

-- ---------------------------------------------------------------------------------------
-- alerts / alert_rules: the shape BEFORE NEM-5051 (channels and metadata are plain json)
-- ---------------------------------------------------------------------------------------
CREATE TABLE alerts (
    id          SERIAL PRIMARY KEY,
    camera_id   TEXT,
    channels    JSON,
    metadata    JSON
);

CREATE TABLE alert_rules (
    id                              SERIAL PRIMARY KEY,
    name                            TEXT,
    object_types                    JSON,
    camera_ids                      JSON,
    zone_ids                        JSON,
    schedule                        JSON,
    conditions                      JSON,
    channels                        JSON,
    pose_types                      TEXT,
    pose_confidence_threshold       NUMERIC,
    action_types                    TEXT,
    action_confidence_threshold     NUMERIC,
    smoke_fire_detection_enabled    BOOLEAN DEFAULT FALSE,
    smoke_fire_consecutive_required INTEGER DEFAULT 2,
    smoke_fire_confidence_threshold NUMERIC
);

INSERT INTO alerts (camera_id, channels, metadata) VALUES
    ('cam-front', '{"k": 1}',       '{"note": "one"}'),
    ('cam-back',  '{"k": 2}',       '{"note": "two"}'),
    ('cam-door',  '["email", "sms"]', '{"nested": {"deep": true}}');

INSERT INTO alert_rules (name, object_types, camera_ids, zone_ids, schedule, conditions, channels)
VALUES ('front-person', '["person"]', '["cam-front"]', '["porch"]', '{"days": ["mon"]}',
        '{"min_confidence": 0.7}', '{"email": true}');

-- ---------------------------------------------------------------------------------------
-- face/person vectors: the shape BEFORE the two provenance files (no model_id column)
-- ---------------------------------------------------------------------------------------
CREATE TABLE face_embeddings (
    id       SERIAL PRIMARY KEY,
    image_id TEXT
);

CREATE TABLE face_detection_events (
    id       SERIAL PRIMARY KEY,
    camera_id TEXT
);

CREATE TABLE person_embeddings (
    id       SERIAL PRIMARY KEY,
    person_id TEXT
);

INSERT INTO face_embeddings (image_id) VALUES ('img-1'), ('img-2');
INSERT INTO face_detection_events (camera_id) VALUES ('cam-front');
INSERT INTO person_embeddings (person_id) VALUES ('p-1'), ('p-2'), ('p-3');

-- ---------------------------------------------------------------------------------------
-- reid_embeddings / demographics_results: present, as they were BEFORE the retirement file
-- ---------------------------------------------------------------------------------------
CREATE TABLE reid_embeddings (
    id      SERIAL PRIMARY KEY,
    blob    TEXT
);

CREATE TABLE demographics_results (
    id      SERIAL PRIMARY KEY,
    result  TEXT
);

INSERT INTO reid_embeddings (blob) VALUES ('vector-bytes-1'), ('vector-bytes-2');
INSERT INTO demographics_results (result) VALUES ('{"age": 30}');

-- ---------------------------------------------------------------------------------------
-- events / detections / cameras / user_calibration / event_feedback: the shape BEFORE January
-- 2026, i.e. WITHOUT the twelve columns upgrade 0005 adds.
--
-- These tables are here for upgrade 0005 specifically. The four original upgrades act on the
-- tables above; 0005's subject matter is the January model columns that no upgrade ever recorded
-- (see its own file header), so a pre-upgrade database has to contain their tables *minus* the
-- columns or the upgrade has nothing to do. Without this block 0005 would fail here with
-- `relation "events" does not exist` -- and, worse, the fixture would keep asserting the old
-- narrow claim ("the four recorded upgrades work") while reading like it covered the whole path.
--
-- Only the columns the upgrades and create_all leave alone are spelled out. The models declare
-- many more, and spelling today's full column list would recreate the exact problem 0005 fixes:
-- a database that already has the columns proves nothing. Id types DO match the models
-- (cameras.id TEXT per `String`, events/detections/event_feedback ids INTEGER per `Integer`)
-- because the boot test's create_all builds the OTHER tables against these, and a type
-- mismatch there is a confusing FK error rather than a finding. No FKs are declared here on
-- purpose: create_all does not add constraints to a table that already exists, so an FK in this
-- file would be testing the fixture, not the upgrade path.
-- ---------------------------------------------------------------------------------------
CREATE TABLE cameras (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    folder_path TEXT,
    status      TEXT,
    created_at  TIMESTAMP
);

CREATE TABLE events (
    id          SERIAL PRIMARY KEY,
    camera_id   TEXT,
    started_at  TIMESTAMP,
    risk_score  NUMERIC,
    summary     TEXT
);

CREATE TABLE detections (
    id          SERIAL PRIMARY KEY,
    camera_id   TEXT,
    detected_at TIMESTAMP,
    object_type TEXT,
    confidence  NUMERIC
);

CREATE TABLE user_calibration (
    id      SERIAL PRIMARY KEY,
    user_id TEXT
);

CREATE TABLE event_feedback (
    id             SERIAL PRIMARY KEY,
    event_id       INTEGER,
    feedback_type  TEXT,
    notes          TEXT
);

INSERT INTO cameras (id, name, folder_path, status, created_at) VALUES
    ('cam-front', 'Front Door', '/export/front',  'online',  TIMESTAMP '2025-11-01 09:00:00'),
    ('cam-back',  'Back Yard',  '/export/back',   'offline', TIMESTAMP '2025-11-02 09:00:00');

INSERT INTO events (camera_id, started_at, risk_score, summary) VALUES
    ('cam-front', TIMESTAMP '2025-11-03 10:00:00', 7.5, 'person at door'),
    ('cam-back',  TIMESTAMP '2025-11-03 11:30:00', 2.0, 'vehicle in yard'),
    ('cam-front', TIMESTAMP '2025-11-04 08:15:00', 9.0, 'unknown motion');

INSERT INTO detections (camera_id, detected_at, object_type, confidence) VALUES
    ('cam-front', TIMESTAMP '2025-11-03 10:00:05', 'person',  0.91),
    ('cam-back',  TIMESTAMP '2025-11-03 11:30:20', 'vehicle', 0.66);

INSERT INTO user_calibration (user_id) VALUES ('owner'), ('guest');

INSERT INTO event_feedback (event_id, feedback_type, notes) VALUES (1, 'confirmed', 'looked right');

-- ---------------------------------------------------------------------------------------
-- action_events: present before 0007-retire-action-events-table (B3.1 R2a row 32 F-068)
-- ---------------------------------------------------------------------------------------
CREATE TABLE action_events (
    id        SERIAL PRIMARY KEY,
    camera_id TEXT,
    action    TEXT
);

INSERT INTO action_events (camera_id, action) VALUES ('cam-front', 'walking normally');

-- ---------------------------------------------------------------------------------------
-- gpu_devices: present before 0009-retire-gpu-devices-table (B3.1 R2a row 36 F-177)
-- ---------------------------------------------------------------------------------------
CREATE TABLE gpu_devices (
    id        SERIAL PRIMARY KEY,
    gpu_index INTEGER,
    name      TEXT
);

INSERT INTO gpu_devices (gpu_index, name) VALUES (0, 'RTX A5500');

-- ---------------------------------------------------------------------------------------
-- 0010 target: scheduled_reports table (retired by B3.1 R2a row 43: F-252, F-253, F-255).
-- ---------------------------------------------------------------------------------------
CREATE TABLE scheduled_reports (
    id        SERIAL PRIMARY KEY,
    name      TEXT,
    frequency TEXT
);

INSERT INTO scheduled_reports (name, frequency) VALUES ('Daily Summary', 'daily');

-- ---------------------------------------------------------------------------------------
-- 0011 target: prompt_versions in the PRE-0011 shape (B3.3 box 4, R2a row 27) -- the model
-- column is the NATIVE enum `aimodel` carrying all five labels, and rows exist for all five
-- models. Without it the upgrade-path run would record 0011 as "verified" (the table's
-- absence reads as "nothing left to migrate"), leaving the enum→varchar conversion and the
-- four-models DELETE unexecuted in these theses. Same shape transcription as the sibling
-- fixture prompt_versions_pre_0011.sql, which is loaded into a DIFFERENT database by
-- backend/tests/integration/test_0011_prompt_versions_upgrade.py -- the two files must not
-- share a database or the CREATE TYPE collides.
-- ---------------------------------------------------------------------------------------
CREATE TYPE aimodel AS ENUM ('nemotron', 'florence2', 'yolo_world', 'xclip', 'fashion_clip');

CREATE TABLE prompt_versions (
    id                 SERIAL PRIMARY KEY,
    model              aimodel         NOT NULL,
    version            INTEGER         NOT NULL,
    created_at         TIMESTAMPTZ     NOT NULL DEFAULT timezone('utc', now()),
    created_by         VARCHAR(255),
    config_json        TEXT            NOT NULL,
    change_description TEXT,
    is_active          BOOLEAN         NOT NULL DEFAULT FALSE,
    row_version        INTEGER         NOT NULL DEFAULT 1,
    CONSTRAINT uq_prompt_version_model_version UNIQUE (model, version)
);

CREATE INDEX idx_prompt_versions_model         ON prompt_versions (model);
CREATE INDEX idx_prompt_versions_model_version ON prompt_versions (model, version);
CREATE INDEX idx_prompt_versions_model_active  ON prompt_versions (model, is_active);
CREATE INDEX idx_prompt_versions_created_at    ON prompt_versions (created_at);

INSERT INTO prompt_versions (model, version, config_json, is_active) VALUES
    ('nemotron',     1, '{"system_prompt": "You are a home security AI assistant analyzing camera detections. Report risks concisely.", "temperature": 0.7, "max_tokens": 2048}', TRUE),
    ('nemotron',     2, '{"system_prompt": "You are a home security AI assistant. v2: cite zones.", "temperature": 0.7, "max_tokens": 2048}', FALSE),
    ('florence2',    1, '{"vqa_queries": ["What is the person doing?", "What objects are they carrying?", "Describe the environment", "Is there anything unusual in this scene?"]}', TRUE),
    ('yolo_world',   1, '{"classes": ["knife", "gun", "package", "crowbar", "spray paint", "Amazon box", "FedEx package", "suspicious bag"], "confidence_threshold": 0.35}', TRUE),
    ('xclip',        1, '{"action_classes": ["loitering", "running away", "fighting", "breaking in", "climbing fence", "hiding", "normal walking"]}', TRUE),
    ('fashion_clip', 1, '{"clothing_categories": ["dark hoodie", "face mask", "gloves", "all black", "delivery uniform", "high-vis vest", "business attire"], "suspicious_indicators": ["all black", "face mask", "hoodie up", "gloves at night"]}', TRUE);
