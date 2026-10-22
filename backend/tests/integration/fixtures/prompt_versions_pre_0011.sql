-- B3.3 box 4 (R2a row 27): a SAVED pre-0011 `prompt_versions` shape, with rows for all
-- five models. This is what upgrade `0011-retire-vision-model-prompts` acts on, loaded by
-- backend/tests/integration/test_0011_prompt_versions_upgrade.py the way
-- schema_pre_upgrade.sql is loaded by its sibling: as a file, diffable, loadable by hand.
--
-- The shapes are transcribed from what create_all built at the PRE-0011 head (the model
-- column as the native enum type `aimodel` carrying all five labels), and the rows carry
-- the values the test asserts survived: the four retired models' rows must vanish and the
-- nemotron rows must survive byte-identical.
--
-- Deliberately omitted: nothing. The whole table is the upgrade's subject.

-- ---------------------------------------------------------------------------------------
-- the native enum, with all five labels in enum order
-- ---------------------------------------------------------------------------------------
CREATE TYPE aimodel AS ENUM ('nemotron', 'florence2', 'yolo_world', 'xclip', 'fashion_clip');

-- ---------------------------------------------------------------------------------------
-- prompt_versions in the pre-0011 shape (model: enum, created_at NOT NULL, is_active with
-- server_default 'false', row_version with server_default '1')
-- ---------------------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------------------
-- rows for ALL five models -- the census is only non-vacuous if every model has rows.
-- nemotron rows must survive; the other four models' rows must be exactly what the
-- upgrade removes. The configs are the defaults the services seed (prompt_service's
-- DEFAULT_CONFIGS, prompt_storage's).
-- ---------------------------------------------------------------------------------------
INSERT INTO prompt_versions (model, version, config_json, is_active) VALUES
    ('nemotron',     1, '{"system_prompt": "You are a home security AI assistant analyzing camera detections. Report risks concisely.", "temperature": 0.7, "max_tokens": 2048}', TRUE),
    ('nemotron',     2, '{"system_prompt": "You are a home security AI assistant. v2: cite zones.", "temperature": 0.7, "max_tokens": 2048}', FALSE),
    ('florence2',    1, '{"vqa_queries": ["What is the person doing?", "What objects are they carrying?", "Describe the environment", "Is there anything unusual in this scene?"]}', TRUE),
    ('yolo_world',   1, '{"classes": ["knife", "gun", "package", "crowbar", "spray paint", "Amazon box", "FedEx package", "suspicious bag"], "confidence_threshold": 0.35}', TRUE),
    ('xclip',        1, '{"action_classes": ["loitering", "running away", "fighting", "breaking in", "climbing fence", "hiding", "normal walking"]}', TRUE),
    ('fashion_clip', 1, '{"clothing_categories": ["dark hoodie", "face mask", "gloves", "all black", "delivery uniform", "high-vis vest", "business attire"], "suspicious_indicators": ["all black", "face mask", "hoodie up", "gloves at night"]}', TRUE);
