-- B3.3: a SAVED pre-upgrade schema, with rows. This is the database that existed on a box before
-- the four upgrades in backend/migrations/registry.py were written, and it is what
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
-- under test -- none of the four upgrades reads or rewrites a vector column -- and leaving it out
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
    id           SERIAL PRIMARY KEY,
    name         TEXT,
    object_types JSON,
    camera_ids   JSON,
    zone_ids     JSON,
    schedule     JSON,
    conditions   JSON,
    channels     JSON
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
