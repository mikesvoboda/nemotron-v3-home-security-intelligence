"""Unit tests for the SQL lexing and registry-consistency handles in `backend/migrations`.

These are the parts of the upgrade runner that can be wrong without any database noticing:

  * `split_statements` decides what "one statement" means. A lexer that splits inside a string
    literal executes half a DDL statement; one that fails to split leaves asyncpg a
    multi-statement string it refuses to prepare.
  * `checksum_text` decides what counts as "someone edited a shipped upgrade". Normalize too
    little and a CRLF checkout reddens every database; normalize too much and a real edit slips
    past the record.
  * the registry/CHECKS pins decide whether an upgrade silently loses its check.

No database needed, which is the point: the migration runner's failure modes include "the SQL
never reaches the database at all", and only a text-level test can see those.
"""

from __future__ import annotations

import re

import pytest

from backend.migrations import checks, registry
from backend.migrations.errors import UpgradeError

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------------------
# split_statements
# --------------------------------------------------------------------------------------


def test_plain_statements_split_on_semicolons():
    sql = "CREATE TABLE a (id int); CREATE INDEX i ON a (id);"
    assert registry.split_statements(sql) == [
        "CREATE TABLE a (id int)",
        "CREATE INDEX i ON a (id)",
    ]


def test_final_statement_without_trailing_semicolon_is_kept():
    assert registry.split_statements("SELECT 1") == ["SELECT 1"]


def test_file_level_transaction_control_is_dropped():
    """The runner owns the transaction, so a BEGIN/COMMIT from the file must not be executed.

    This is not cosmetic: executing `COMMIT` inside a savepoint-based upgrade would end the
    caller's transaction mid-run, which in `init_db()` means committing `create_all`'s work
    before the advisory lock is released.
    """
    sql = "BEGIN; ALTER TABLE t ADD COLUMN c int; COMMIT;"
    assert registry.split_statements(sql) == ["ALTER TABLE t ADD COLUMN c int"]


def test_line_comment_semicolon_does_not_split():
    sql = "SELECT 1; -- a note; with a semicolon\nSELECT 2;"
    assert registry.split_statements(sql) == ["SELECT 1", "SELECT 2"]


def test_block_comment_is_removed_and_nests():
    sql = "SELECT 1; /* outer /* inner */ still comment */ SELECT 2;"
    assert registry.split_statements(sql) == ["SELECT 1", "SELECT 2"]


def test_semicolon_inside_string_literal_does_not_split():
    """The case ruling 254's data upgrade will actually hit.

    An `UPDATE prompt_versions SET model = 'florence2' WHERE ...` carries quoted values; a split
    on `;` that ignores quoting would cut the statement in half and run the halves.
    """
    sql = "UPDATE t SET v = 'a;b' WHERE id = 1;"
    assert registry.split_statements(sql) == ["UPDATE t SET v = 'a;b' WHERE id = 1"]


def test_escaped_quote_inside_string():
    sql = "UPDATE t SET v = 'it''s; here' WHERE id = 1;"
    assert registry.split_statements(sql) == ["UPDATE t SET v = 'it''s; here' WHERE id = 1"]


def test_e_string_with_backslash_escape_and_semicolon():
    sql = r"UPDATE t SET v = E'a\';b' WHERE id = 1;"
    assert registry.split_statements(sql) == [r"UPDATE t SET v = E'a\';b' WHERE id = 1"]


def test_e_string_letter_is_not_confused_with_an_identifier():
    """`... FROM table_e 'x'` is not an E-string; `E'x'` is.

    The lexer checks the preceding character, so a name ending in e must not swallow the quote.
    """
    sql = "SELECT * FROM table_e WHERE n = 'a;b';"
    assert registry.split_statements(sql) == ["SELECT * FROM table_e WHERE n = 'a;b'"]


def test_quoted_identifier_with_semicolon_does_not_split():
    sql = 'ALTER TABLE "we;ird" ADD COLUMN c int;'
    assert registry.split_statements(sql) == ['ALTER TABLE "we;ird" ADD COLUMN c int']


def test_dollar_quoted_body_keeps_its_semicolons():
    """A function body is one statement however many semicolons it contains."""
    sql = "$function$ BEGIN INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); END; $function$;"
    assert registry.split_statements(sql) == [
        "$function$ BEGIN INSERT INTO t VALUES (1); INSERT INTO t VALUES (2); END; $function$"
    ]


def test_unterminated_string_raises():
    with pytest.raises(UpgradeError, match="unterminated string"):
        registry.split_statements("SELECT 'oops")


def test_unterminated_block_comment_raises():
    with pytest.raises(UpgradeError, match="unterminated block comment"):
        registry.split_statements("SELECT 1; /* never closed")


def test_unterminated_dollar_quote_raises():
    with pytest.raises(UpgradeError, match="unterminated dollar-quoted"):
        registry.split_statements("SELECT $body$ nothing")


def test_unterminated_quoted_identifier_raises():
    with pytest.raises(UpgradeError, match="unterminated quoted identifier"):
        registry.split_statements('SELECT "oops')


@pytest.mark.parametrize(
    ("upgrade_id", "expected_statements"),
    [
        # Census of the shipped files, from the boot log of a real run: NEM-5051 is
        # BEGIN + 2 ALTERs + COMMIT + a trailing verification SELECT, so 3 executable statements
        # after the control words go. The rest are the ALTER/UPDATE/DROP statements their files
        # carry. Pinned as numbers because "the lexer found some statements" is not a claim.
        ("0001-nem-5051-alert-json-to-jsonb", 3),
        ("0002-face-vector-provenance-model-id", 2),
        ("0003-person-vector-provenance-model-id", 1),
        ("0004-retire-demographics-reid-tables", 2),
        # 0005 is one statement per column, 12 of them, measured off the file with
        # `grep -v '^--' docs/api/migrations/2026-10-18-add-unrecorded-model-columns.sql
        #  | grep -c 'ADD COLUMN IF NOT EXISTS'` = 12. The `grep -v` is load-bearing, not fussiness:
        # the file's own header prose names that phrase, so a bare `grep -c` returns 13 -- the exact
        # wrong number this line nearly got, before the lexer count is what settled it. BEGIN/COMMIT
        # are control words and drop out before the count. Pinned here as well as in checks.py's
        # derivation because the two read the file differently -- this one through the lexer,
        # that one through a regex -- and a lexer that swallowed a statement would otherwise
        # show up only as a missing column at boot.
        ("0005-add-unrecorded-model-columns", 12),
        ("0006-retire-user-calibration-table", 1),
        ("0007-retire-action-events-table", 1),
        ("0008-retire-alert-rule-pose-action-smoke-columns", 1),
        ("0009-retire-gpu-devices-table", 1),
        ("0010-retire-scheduled-reports-table", 1),
        # 0011 is DELETE (the four retired models' rows) + ALTER COLUMN ... TYPE + DROP TYPE:
        # three statements. The DELETE runs before the ALTER so the IN-list is still
        # validated against the native aimodel enum labels.
        ("0011-retire-vision-model-prompts", 3),
    ],
)
def test_shipped_files_lex_to_the_expected_statement_count(upgrade_id, expected_statements):
    upgrade = next(u for u in registry.UPGRADES if u.id == upgrade_id)
    statements = upgrade.statements()
    assert len(statements) == expected_statements, statements


def test_no_shipped_statement_is_empty_or_a_control_word():
    for upgrade in registry.UPGRADES:
        for statement in upgrade.statements():
            assert statement.strip() == statement
            assert statement.upper() not in registry._CONTROL_WORDS


# --------------------------------------------------------------------------------------
# checksum_text
# --------------------------------------------------------------------------------------


def test_checksum_ignores_line_endings_and_trailing_space():
    """A CRLF checkout or a trailing-whitespace formatter is not an edited upgrade."""
    unix = "ALTER TABLE t\n    ADD COLUMN c int;\n"
    dos = unix.replace("\n", "\r\n")
    trailing = "ALTER TABLE t    \n    ADD COLUMN c int;  \n"
    digest = registry.checksum_text(unix)
    assert registry.checksum_text(dos) == digest
    assert registry.checksum_text(trailing) == digest


def test_checksum_catches_a_real_edit():
    assert registry.checksum_text("ALTER TABLE t ADD COLUMN c int;") != registry.checksum_text(
        "ALTER TABLE t ADD COLUMN c text;"
    )


def test_checksum_is_stable_across_calls():
    assert registry.checksum_text("SELECT 1") == registry.checksum_text("SELECT 1")


# --------------------------------------------------------------------------------------
# Registry / CHECKS consistency
# --------------------------------------------------------------------------------------


def test_upgrade_ids_are_unique_and_ordered():
    ids = registry.ids()
    assert len(ids) == len(set(ids))
    assert list(ids) == [u.id for u in registry.UPGRADES]


def test_every_registered_upgrade_has_its_file_on_disk():
    """`missing_files` is the deploy-time sanity handle; here it must be empty."""
    assert registry.missing_files() == ()


def test_every_sql_file_in_the_directory_is_registered():
    """The half that makes registration mandatory (see AGENTS.md): an unlisted file is drift.

    A file that no `UPGRADES` entry names is never applied, which is exactly the silent skip
    this package exists to remove.
    """
    assert registry.unlisted_files() == ()


def test_every_upgrade_that_rewrites_or_drops_has_a_check():
    """A file that is not safe to re-run must have a predicate, or startup can take a lock.

    The rule from `checks.py`: no CHECK means "assume not in place, run it". Correct for an
    `IF NOT EXISTS` file, and a boot-time `ACCESS EXCLUSIVE` for NEM-5051's `ALTER COLUMN ...
    TYPE jsonb`. So any file that changes a type, rewrites rows, or drops something must be
    checked -- detected here from the file text, not from a hand-maintained list.
    """
    risky = re.compile(r"\b(ALTER COLUMN|UPDATE\s|DROP TABLE)", re.IGNORECASE)
    for upgrade in registry.UPGRADES:
        if risky.search(upgrade.read_sql()):
            assert upgrade.id in checks.CHECKS, (
                f"{upgrade.id} has type/row/drop statements but no CHECK: startup would re-run it"
            )


def test_checks_covers_every_alter_column_in_the_nem_5051_file():
    """The transcription in `checks._NEM_5051_COLUMNS` must match the file's own statements.

    `checks.py` names this test as the thing that keeps its column list honest. Without it the
    drift direction is a column the runner never looks at, and an unrecorded database gets
    `executed = false` for a conversion it did not verify.
    """
    upgrade = next(u for u in registry.UPGRADES if u.id == "0001-nem-5051-alert-json-to-jsonb")
    from_file: dict[str, set[str]] = {}
    seen_alter = 0
    for statement in upgrade.statements():
        # Not every statement is a conversion: the file ends with a verification SELECT, which is
        # harmless to run and belongs in statements(). Only `ALTER TABLE ... ALTER COLUMN ...`
        # contributes a column to the census.
        match = re.match(r"ALTER TABLE\s+(\w+)(.*)", statement, re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        seen_alter += 1
        columns = re.findall(r"ALTER COLUMN\s+(\w+)", match.group(2), re.IGNORECASE)
        from_file.setdefault(match.group(1), set()).update(columns)

    assert seen_alter == 2, f"expected the file's two ALTER TABLE statements, got {seen_alter}"
    transcribed = {table: set(columns) for table, columns in checks._NEM_5051_COLUMNS.items()}
    assert transcribed == from_file, f"file says {from_file}, checks.py says {transcribed}"
    assert sum(len(v) for v in transcribed.values()) == 8, "the 8-column census moved"


def test_check_keys_are_registered_ids():
    """`checks.py` asserts this at import; asserted here so the failure names the rule."""
    assert set(checks.CHECKS) <= set(registry.ids())


def test_missing_sql_file_error_names_the_dockerfile_remedy():
    """The only way this fires in production is an image that lost its COPY line.

    So the message must carry the remedy -- an operator staring at a boot failure in a container
    cannot be expected to deduce that `.dockerignore` excludes `docs/`.
    """
    upgrade = registry.Upgrade(id="x", filename="does-not-exist.sql", source="test")
    with pytest.raises(UpgradeError) as excinfo:
        upgrade.read_sql()
    message = str(excinfo.value)
    assert "backend/Dockerfile" in message
    assert ".dockerignore" in message


def test_registry_directory_is_the_path_the_owner_named():
    """The package text names `docs/api/migrations/` twice; a move is a spec change, not a refactor.

    Pinned because several tests and model docstrings cite files under that path, and the runtime
    image COPYs it by name.
    """
    assert registry.MIGRATION_DIR.as_posix() == "docs/api/migrations"
    assert (registry.REPO_ROOT / registry.MIGRATION_DIR).is_dir()


def test_0007_retire_action_events_table_registered():
    """R2a row 32 (F-068) registers 0007-retire-action-events-table with a table_absent check."""
    assert "0007-retire-action-events-table" in registry.ids()
    assert "0007-retire-action-events-table" in checks.CHECKS


def test_0008_retire_alert_rule_pose_action_smoke_columns_registered():
    """R2a row 32 (F-220) registers 0008-retire-alert-rule-pose-action-smoke-columns with a CHECK."""
    assert "0008-retire-alert-rule-pose-action-smoke-columns" in registry.ids()
    assert "0008-retire-alert-rule-pose-action-smoke-columns" in checks.CHECKS


def test_0009_retire_gpu_devices_table_registered():
    """R2a row 36 (F-177) registers 0009-retire-gpu-devices-table with a table_absent check."""
    assert "0009-retire-gpu-devices-table" in registry.ids()
    assert "0009-retire-gpu-devices-table" in checks.CHECKS


def test_0010_retire_scheduled_reports_table_registered():
    """R2a row 43 (F-252/F-253/F-255) registers 0010-retire-scheduled-reports-table with a table_absent check."""
    assert "0010-retire-scheduled-reports-table" in registry.ids()
    assert "0010-retire-scheduled-reports-table" in checks.CHECKS


def test_0011_retire_vision_model_prompts_registered():
    """B3.3 box 4 (R2a row 27) registers 0011-retire-vision-model-prompts with a CHECK --
    mandatory, not stylistic: the file's ALTER COLUMN trips the risky-statement gate above."""
    assert "0011-retire-vision-model-prompts" in registry.ids()
    assert "0011-retire-vision-model-prompts" in checks.CHECKS
