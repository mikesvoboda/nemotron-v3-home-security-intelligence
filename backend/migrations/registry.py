"""B3.3: the ordered upgrade registry and the SQL text handles.

The upgrade TEXT lives in ``docs/api/migrations/*.sql``; the ORDER lives here. The file set is
not self-ordering -- among the four folded-in runbooks a date prefix sorts three and ``NEM-5051``
has no date at all, so "sort the directory" is a guess, and a guess in a schema tool is the bug.
(Upgrades authored here since -- 0005 -- do carry a date and would sort into place, which only
proves the point: the rule cannot be "the filenames happen to work today.") Listing
an upgrade here is what makes it run, which also means **adding the file is not enough**: an
unlisted file is reported by ``python -m backend.migrations --status`` as drift, loudly, rather
than skipped in silence (``scripts/audit/AGENTS.md``: a silent skip turns a census into a fossil).

Why the text stays in ``docs/``: ``docs/uplevel/packages/backend.md`` -- this package's own
spec -- names ``docs/api/migrations/`` twice ("a small runner over ``docs/api/migrations/``",
"The four existing SQL files become its first recorded upgrades"), and the files are cited by
``backend/tests/unit/services/test_person_vector_provenance.py:39``,
``backend/tests/unit/models/test_r8_s4_demographics_reid_retirement.py:82``,
``backend/models/enrichment.py:14``, ``backend/services/vlm_specialists.py:478`` and the mutmut
``also_copy`` list (``pyproject.toml:862``). Moving them would cost all of those and buy
nothing: the runtime image is taught to carry the path instead (``COPY docs/api/migrations`` in
``backend/Dockerfile``, required because ``.dockerignore`` excludes ``docs/``), and
``Upgrade.read_sql`` below fails loud with that exact remedy if the COPY is ever dropped.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from backend.migrations.errors import UpgradeError

#: Where the upgrade text lives, relative to the repo root.
MIGRATION_DIR = Path("docs/api/migrations")

#: Repo root, resolved from this file (``backend/migrations/registry.py`` -> two parents up).
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Upgrade:
    """One recorded schema upgrade: its permanent id and the file that holds its SQL.

    ``id`` is written into ``schema_migrations.id`` and is therefore **permanent**: once a
    database has recorded it, renaming it is drift (the runner refuses, it does not renumber).
    ``source`` names where the upgrade came from, so a later reader can tell a folded-in
    historical runbook from one authored under this runner.
    """

    id: str
    filename: str
    source: str

    @property
    def path(self) -> Path:
        """Absolute path to the SQL file (may not exist -- see ``missing_files``)."""
        return REPO_ROOT / MIGRATION_DIR / self.filename

    def read_sql(self) -> str:
        """The file's text.

        Raises:
            UpgradeError: If the file is absent. The message names the Dockerfile remedy
                because the only way this fires in a container is an image that lost its
                ``COPY docs/api/migrations`` line.
        """
        if not self.path.is_file():
            raise UpgradeError(
                f"upgrade {self.id}: SQL file {MIGRATION_DIR / self.filename} is missing. "
                f"In a container this means the runtime image does not carry that path -- "
                f"backend/Dockerfile must COPY it (.dockerignore excludes docs/)."
            )
        return self.path.read_text(encoding="utf-8")

    def statements(self) -> list[str]:
        """This upgrade's executable statements (comments and file-level BEGIN/COMMIT removed)."""
        return split_statements(self.read_sql())

    def checksum(self) -> str:
        """This upgrade's current text digest (see `checksum_text`)."""
        return checksum_text(self.read_sql())


#: Every database gets these, in this order, exactly once.
#:
#: Ordered by when each change shipped, taken from `git log --diff-filter=A` rather than from
#: the filenames: NEM-5051 was added 2026-02-02 (`55e266a8d`), the two provenance files
#: 2026-09-27 (`4bfd6fa40`), the retirement 2026-09-30 (`cafad9107`).
#:
#: Be precise about what that order buys: measured, these four touch DISJOINT objects
#: (alerts + alert_rules / face_embeddings + face_detection_events / person_embeddings /
#: demographics_results + reid_embeddings), so none of them must precede another for the result
#: to be right. The order's job is a stable RECORD, not a dependency graph: `schema_migrations`
#: says every database received these in this sequence, so a future upgrade that DOES read what
#: an earlier one wrote (ruling 254's enum retirement, B3.1's drops per ruling 203 -- they land
#: here as 0005+) has a defined position to depend on. A filename sort would run NEM-5051 last:
#: same result today, wrong story, and wrong the first time an upgrade cares.
UPGRADES: tuple[Upgrade, ...] = (
    Upgrade(
        id="0001-nem-5051-alert-json-to-jsonb",
        filename="NEM-5051-convert-alert-json-to-jsonb.sql",
        source="NEM-5051 (hand-applied runbook, folded in by B3.3)",
    ),
    Upgrade(
        id="0002-face-vector-provenance-model-id",
        filename="2026-09-26-face-vector-provenance-model-id.sql",
        source="F11 ruling 2 (hand-applied runbook, folded in by B3.3)",
    ),
    Upgrade(
        id="0003-person-vector-provenance-model-id",
        filename="2026-09-26-person-vector-provenance-model-id.sql",
        source="F11 ruling 2 extended, ledger item 20 (folded in by B3.3)",
    ),
    Upgrade(
        id="0004-retire-demographics-reid-tables",
        filename="2026-09-30-retire-demographics-reid-tables.sql",
        source="R8 S4 owner ruling 2026-09-30 (folded in by B3.3)",
    ),
    Upgrade(
        id="0005-add-unrecorded-model-columns",
        filename="2026-10-18-add-unrecorded-model-columns.sql",
        source="B3.3 box 6 (the 12 January-2026 model columns no upgrade ever recorded)",
    ),
    Upgrade(
        id="0006-retire-user-calibration-table",
        filename="2026-10-19-retire-user-calibration-table.sql",
        source="B3.1 R2a row 11 (retire F-131 user_calibration table)",
    ),
    Upgrade(
        id="0007-retire-action-events-table",
        filename="2026-10-20-retire-action-events-table.sql",
        source="B3.1 R2a row 32 (retire F-068 action_events table)",
    ),
    Upgrade(
        id="0008-retire-alert-rule-pose-action-smoke-columns",
        filename="2026-10-20-retire-alert-rule-pose-action-smoke-columns.sql",
        source="B3.1 R2a row 32 (retire F-220 alert_rules pose, action, and smoke/fire columns)",
    ),
    Upgrade(
        id="0009-retire-gpu-devices-table",
        filename="2026-10-20-retire-gpu-devices-table.sql",
        source="B3.1 R2a row 36 (retire F-177 gpu_devices table)",
    ),
    Upgrade(
        id="0010-retire-scheduled-reports-table",
        filename="2026-10-20-retire-scheduled-reports-table.sql",
        source="B3.1 R2a row 43 (retire F-252/F-253/F-255 scheduled_reports table)",
    ),
    Upgrade(
        id="0011-retire-vision-model-prompts",
        filename="2026-10-21-retire-vision-model-prompts.sql",
        source="B3.3 R2a row 27 (retire the four vision models' prompt_versions rows and the native aimodel enum)",
    ),
    Upgrade(
        id="0012-alert-pipeline-core",
        filename="2026-10-22-alert-pipeline-core.sql",
        source="B4.1 (alert pipeline core additive columns, open status, alert_events, activity_snoozes)",
    ),
)


def ids() -> tuple[str, ...]:
    """The recorded ids, in apply order."""
    return tuple(upgrade.id for upgrade in UPGRADES)


def missing_files() -> tuple[str, ...]:
    """Listed upgrades whose SQL file is not on disk (a deploy-time sanity handle)."""
    return tuple(upgrade.id for upgrade in UPGRADES if not upgrade.path.is_file())


def unlisted_files() -> tuple[str, ...]:
    """``.sql`` files in the migrations directory that no upgrade lists.

    This is the half that makes registration mandatory: a file added to the directory without a
    registry entry is drift and `--status` says so, instead of the runner quietly never applying
    the change the file describes.
    """
    if not (REPO_ROOT / MIGRATION_DIR).is_dir():
        return ()
    listed = {upgrade.filename for upgrade in UPGRADES}
    return tuple(
        sorted(p.name for p in (REPO_ROOT / MIGRATION_DIR).glob("*.sql") if p.name not in listed)
    )


# --------------------------------------------------------------------------------------
# SQL lexing
# --------------------------------------------------------------------------------------

#: Transaction control words the files carry themselves. The runner owns the transaction (see
#: `split_statements`), so these are dropped rather than executed -- a `COMMIT;` taken from the
#: file would otherwise commit the runner's own transaction mid-upgrade.
_CONTROL_WORDS = {"BEGIN", "COMMIT", "ROLLBACK", "START TRANSACTION", "END"}


def split_statements(sql: str) -> list[str]:
    """Split a ``.sql`` file into executable statements, comments and control words removed.

    Hand-rolled because there is no way to ask for this: asyncpg refuses multiple statements in
    one prepared execution, and splitting on ``;`` alone would cut inside a string literal, a
    dollar-quoted body, or a comment. These four files happen to contain no such case -- the
    function is written for the fifth file, which will have one (ruling 254's data upgrade is
    likely to carry an ``UPDATE ... WHERE model IN ('florence2', ...)`` whose quoted names land
    in exactly the paths a naive split misses).

    Raises:
        UpgradeError: On an unterminated comment, string, identifier or dollar-quoted body.
            A lexer that guesses past an unbalanced quote would execute half a DDL statement on
            a real database, so it refuses instead.
    """
    raw_statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    line = 1

    def unterminated(what: str) -> UpgradeError:
        return UpgradeError(f"unterminated {what} starting at line {line}")

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        # -- line comment (and SQL's /* */ block comments, which nest in PostgreSQL)
        if ch == "-" and nxt == "-":
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == "/" and nxt == "*":
            # Enter with depth 1 and the opener already consumed. The first version set depth = 0
            # and looped `while depth > 0`, so the body never ran, `i` never advanced, and any
            # file containing a block comment hung the runner forever -- invisible for these four
            # files, which use only `--` comments, and caught by the unit test.
            started_at = line
            depth = 1
            i += 2
            while i < n and depth > 0:
                if sql.startswith("/*", i):
                    depth += 1
                    i += 2
                elif sql.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    if sql[i] == "\n":
                        line += 1
                    i += 1
            if depth > 0:
                raise UpgradeError(f"unterminated block comment starting at line {started_at}")
            continue

        # E'...' escaped string (checked BEFORE the plain-quote branch below)
        if (
            ch in "eE"
            and nxt == "'"
            and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_"))
        ):
            buf.append("E'")
            i += 2
            closed = False
            while i < n:
                c = sql[i]
                if c == "\n":
                    line += 1
                if c == "\\" and i + 1 < n:
                    buf.append(sql[i : i + 2])
                    i += 2
                    continue
                if c == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append("''")
                        i += 2
                        continue
                    buf.append("'")
                    i += 1
                    closed = True
                    break
                buf.append(c)
                i += 1
            if not closed:
                raise unterminated("string literal")
            continue

        # 'plain string' ('' escapes; newlines legal inside)
        if ch == "'":
            buf.append(ch)
            i += 1
            closed = False
            while i < n:
                c = sql[i]
                if c == "\n":
                    line += 1
                if c == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        buf.append("''")
                        i += 2
                        continue
                    buf.append("'")
                    i += 1
                    closed = True
                    break
                buf.append(c)
                i += 1
            if not closed:
                raise unterminated("string literal")
            continue

        # "quoted identifier"
        if ch == '"':
            buf.append(ch)
            i += 1
            closed = False
            while i < n:
                if sql[i] == '"':
                    if i + 1 < n and sql[i + 1] == '"':
                        buf.append('""')
                        i += 2
                        continue
                    buf.append('"')
                    i += 1
                    closed = True
                    break
                if sql[i] == "\n":
                    line += 1
                buf.append(sql[i])
                i += 1
            if not closed:
                raise unterminated("quoted identifier")
            continue

        # $tag$ dollar-quoted body $tag$ (function bodies; no semicolon-splitting inside)
        if ch == "$":
            tag = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if tag:
                delim = tag.group(0)
                end = sql.find(delim, i + len(delim))
                if end == -1:
                    raise unterminated(f"dollar-quoted body ({delim})")
                buf.append(sql[i : end + len(delim)])
                line += sql[i:end].count("\n")
                i = end + len(delim)
                continue

        if ch == "\n":
            line += 1

        if ch == ";":
            raw_statements.append("".join(buf))
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    raw_statements.append("".join(buf))  # trailing statement without a final semicolon

    cleaned: list[str] = []
    for raw in raw_statements:
        stmt = raw.strip().rstrip(";").strip()
        if not stmt:
            continue
        if stmt.upper() in _CONTROL_WORDS:
            continue
        cleaned.append(stmt)
    return cleaned


def checksum_text(sql: str) -> str:
    """Stable short digest of an upgrade's SQL text.

    Line endings and trailing whitespace are normalized away first: a CRLF checkout or a
    formatter touching trailing space must not read as "someone edited a shipped upgrade". What
    IS caught is any change to the SQL itself, which is the record's whole purpose (see
    `UpgradeDriftError`).
    """
    normalized = "\n".join(line.rstrip() for line in sql.replace("\r\n", "\n").split("\n"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
