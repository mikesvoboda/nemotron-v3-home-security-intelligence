"""R8 slice S4 (first half): two enrichment child tables retire — `demographics_results`
and `reid_embeddings`. ABOUTME: this file is S4's red-first guard -- it pins the END
STATE the owner's ruling of 2026-09-30 mandates, written (and proven red) BEFORE any
deletion, per the goal prompt's "TDD red-first" hard rule.

The owner ruling this file encodes (S4 = SPLIT, chosen after a measured adjudication
corrected the scope doc's premise):

  The scope doc §6 called all four of `pose_results`/`demographics_results`/
  `action_results`/`reid_embeddings` "legacy-only" and kept `threat_detections`
  because it is "read by `services/alert_engine.py`". Measurement broke that
  framing twice over:
    * NO shipped writer exists for ANY of the five tables -- the only writer is
      `scripts/seed-events.py`, which shipped code never invokes (measured: every
      ORM construction site outside tests/archive is a class def or a __repr__).
      The scope's own evidence for retiring `reid_embeddings` cited
      `enrichment_pipeline.py:5848` -- a file S2b already deleted.
    * `pose_results`/`action_results` are READ on a shipped path -- the same
      `alert_engine._evaluate_rule` -> `POST /api/alerts/rules/{id}/test` that is
      the sole stated reason `threat_detections` is kept. So pose/action share the
      keeper's reachability class.
  Ruling: retire ONLY `demographics_results` + `reid_embeddings` here -- they have
  zero live readers AND zero shipped writers, unambiguously janitorial. `pose_
  results`/`action_results` and their `pose_types`/`action_types` rule fields STAY
  with `threat_detections`; any future retirement of them must null stored rule
  values + drop the columns + drop the tables + retarget the contract oracles in
  ONE commit (dropping the tables while the rule columns survive makes a stored
  rule hit a missing table with no try/except on that route -- a permanent 500 a
  user can aim at).

Why pins rather than greps, per this repo's recurring lesson (S3's guard, the file
this one is modeled on): prose is allowed to name the dead. Every "X is gone" check
here reads source TEXT for LIVE forms only (imports, class definitions, relationship
attributes, DROP statements) or uses an import failure, so a tombstone comment naming
a retired table cannot fail this file -- and every scan pins its own non-vacuity (an
absence test over an empty list passes happily on nothing).

Negative space, pinned so a reviewer cannot widen the slice:
  * `threat_detections` STAYS (owner keeper; it is a DB lookup, not a table this
    ruling retires). So do `pose_results`, `action_results`, their rule fields, and
    the two `alert_engine._check_*` methods that read them.
  * `household.py:155 PersonEmbedding` STAYS -- the live VLM re-ID leg loads its
    gallery through it; it is the name-trap twin of the legacy `reid_embeddings`.
  * The JSONB key `detections.enrichment_data["reid_embedding"]` (written/read by
    `services/reid_matcher.py`, `reid_service.py`, `detections.py` bulk paths) STAYS
    -- a JSONB key is not a table, and this slice touches zero of that lane.
  * `Track.reid_embedding` and `RegisteredVehicle.reid_embedding` (LargeBinary
    columns on OTHER models) STAYS -- the name `reid_embedding` is heavily overloaded;
    this slice prunes only `Detection.reid_embedding`, the one ORM relationship whose
    target class is being deleted.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path
from typing import ClassVar

# This file sits one level deeper than S3's guard (backend/tests/unit/models/, not
# backend/tests/unit/), so the repo root is parents[4]. The first draft copied
# parents[3] from the S3 file and every REPO_ROOT read then silently pointed at
# backend/ -- reader scans came back empty VACUOUSLY. The depth is asserted, not
# assumed, so moving this file reddens it loudly instead of quietly.
REPO_ROOT = Path(__file__).resolve().parents[4]
assert (REPO_ROOT / "pyproject.toml").is_file() and (REPO_ROOT / "backend").is_dir()
assert not (REPO_ROOT / "services").is_dir(), "REPO_ROOT landed on backend/, not the repo root"

# The two classes this half-slice retires.
RETIRED_CLASSES: ClassVar[list[str]] = ["DemographicsResult", "ReIDEmbedding"]
# The two tables their __tablename__ names, which the DROP SQL must remove.
RETIRED_TABLES: ClassVar[list[str]] = ["demographics_results", "reid_embeddings"]

# Keepers, pinned as SURVIVORS so "the import worked" cannot mean "the module was
# gutted". These are every other class in backend/models/enrichment.py.
ENRICHMENT_KEEPERS: ClassVar[list[str]] = ["PoseResult", "ThreatDetection", "ActionResult"]

# The dated migration this slice must add. Named to the directory's de-facto
# convention (the two face/person provenance files), NOT README.md's ".md" claim --
# item 53 records that the README contradicts every file it documents.
MIGRATION = "docs/api/migrations/2026-09-30-retire-demographics-reid-tables.sql"


def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


# `scripts/seed-events.py` cannot be IMPORTED here, and the obvious reason is a
# trap worth recording: it is hyphenated (not importable by name), but the real
# blocker is that importing it EXECUTES `_load_env_and_fix_database_url()`, which
# calls `load_dotenv(.env)` and may rewrite `os.environ["DATABASE_URL"]` for the
# rest of the pytest session -- a guard that perturbs the environment of the suite
# it lives in is worse than the gap it closes. So the reference check below is
# done on the AST: it catches exactly the failure mode that matters (a surviving
# `from backend.models import <deleted name>`, i.e. an ImportError at the moment
# an operator runs the seed) with zero side effects.
SEED_EVENTS_PATH = REPO_ROOT / "scripts/seed-events.py"


def _seed_model_imports() -> list[tuple[str, str]]:
    """[(module, name)] for every `from backend.models[.x] import <name>` in
    scripts/seed-events.py, resolved through any `as` alias to the real symbol."""
    tree = ast.parse(SEED_EVENTS_PATH.read_text(encoding="utf-8"), filename=str(SEED_EVENTS_PATH))
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("backend.models")
        ):
            for alias in node.names:
                found.append((node.module, alias.name))
    return found


class TestS4SurfaceIsRealBeforeItIsGone:
    """Vacuity guard, written FIRST (S3's discipline). Every absence pin below only
    means something if the surface it removes exists and is non-empty BEFORE the
    change. This class must be GREEN on the pre-retirement tree -- a pin that cannot
    observe the thing it removes is the vacuity failure S3's guard names."""

    def test_the_two_classes_exist_before_they_are_gone(self) -> None:
        """The two-sided witness, in the shape S3's guard uses: one pin, both
        halves named, so it is GREEN on the pre-retirement tree (the classes and
        their table names exist -- the surface this slice removes is real) and
        still MEANINGFUL after it (a half-deleted module reddens the else branch
        instead of laundering the slice). A plain "they exist" assertion cannot
        live in a file that is committed green, and a pin that cannot observe the
        thing it removes is the vacuity failure S3's guard names."""
        mod = importlib.import_module("backend.models.enrichment")
        present = [c for c in RETIRED_CLASSES if hasattr(mod, c)]
        if present:
            assert present == RETIRED_CLASSES, f"half-retired module state: {present}"
            # Pre-slice: they carry the table names the DROP file must later name.
            for cls in present:
                tbl = getattr(mod, cls).__tablename__
                assert tbl in RETIRED_TABLES, f"{cls}.__tablename__ == {tbl!r}"
        else:
            # Post-slice: "gone" is only real if the runbook that drops those
            # tables from existing databases landed in the same commit; a class
            # deletion with no DROP leaves the table live and orphaned.
            assert (REPO_ROOT / MIGRATION).is_file(), (
                "classes deleted but the dated DROP SQL is missing -- the tables "
                "survive in every existing database"
            )

    def test_the_shipped_reader_it_lacks_is_the_point(self) -> None:
        """The reason THIS pair is safe to drop and pose/action is not: a shipped
        reader would make a DROP a 500. Measured pre-slice -- neither class is
        selected anywhere in `backend/` outside tests/archive. That asymmetry is the
        ruling's whole basis, so it is pinned structurally, not remembered."""
        readers: list[str] = []
        for py in (REPO_ROOT / "backend").rglob("*.py"):
            # O1.5 (UR-19) removed a third disjunct here: it tested the slash
            # form against str(py.parts), which can never match — a tuple's str
            # has no slashes, so the skip never fired. An archived tree named by
            # UR-19 reappearing is the retired-paths gate's failure, not this
            # scan's.
            if "__pycache__" in py.parts or "/tests/" in str(py):
                continue
            if py.name == "enrichment.py":
                continue  # the model module itself defines them
            src = py.read_text(encoding="utf-8")
            for cls in RETIRED_CLASSES:
                # A live ORM read shape: select(cls)/delete(cls)/from backend import cls.
                if re.search(rf"\b(select|delete)\({cls}\)", src) or re.search(
                    rf"import[^\n]*\b{cls}\b", src
                ):
                    readers.append(f"{py.relative_to(REPO_ROOT)}: {cls}")
        assert readers == [], f"a shipped reader appeared -- re-ask the DROP: {readers}"


class TestClassesRetired:
    """The two classes leave `backend.models.enrichment` and its barrel."""

    def test_classes_removed_from_the_enrichment_module(self) -> None:
        mod = importlib.import_module("backend.models.enrichment")
        importlib.invalidate_caches()
        for cls in RETIRED_CLASSES:
            assert not hasattr(mod, cls), f"{cls} still defined"
        # Non-vacuity: the module survived and keeps its other classes.
        for keep in ENRICHMENT_KEEPERS:
            assert hasattr(mod, keep), f"collateral-deleted a keeper: {keep}"

    def test_classes_removed_from_the_models_barrel(self) -> None:
        from backend import models

        for cls in RETIRED_CLASSES:
            assert cls not in models.__all__, f"{cls} still exported"
            assert not hasattr(models, cls), f"{cls} still bound on the package"
        # Non-vacuity: the barrel still ships the keepers (an emptied __all__ would
        # pass the absence loop for the wrong reason).
        for keep in [*ENRICHMENT_KEEPERS, "Detection"]:
            assert keep in models.__all__, keep

    def test_module_import_source_no_longer_names_them_as_a_live_import(self) -> None:
        """The barrel's `from .enrichment import (...)` must drop the two names:
        an import line that pulls a nonexistent symbol is an ImportError at boot,
        and no __all__ edit fixes that. Full absence is the right pin for THESE two
        files (measured pre-slice): in `__init__.py` the names occur only in the
        from-import and the __all__ entries, and in `detection.py` only in the
        TYPE_CHECKING import and the two relationship definitions -- i.e. every
        occurrence is a live shape, so a tombstone comment cannot hide behind this
        check either (and neither file carries prose about these tables)."""
        for rel in ("backend/models/__init__.py", "backend/models/detection.py"):
            src = _src(rel)
            for cls in RETIRED_CLASSES:
                assert cls not in src, f"{rel} still names {cls} in a live shape"


class TestDetectionRelationshipsPruned:
    """`Detection` carried two relationships whose back_populates pointed at the
    deleted classes. A class-deleted-but-relationship-prune-missed passes every
    import check and dies at the FIRST mapper configure / DB query (dangling string
    relationship). This is the slice's nastiest failure mode, so it is pinned
    directly."""

    def test_detection_no_longer_declares_the_two_relationships(self) -> None:
        from backend.models.detection import Detection

        rels = Detection.__mapper__.relationships.keys()
        for gone in ("demographics_result", "reid_embedding"):
            assert gone not in rels, f"Detection.{gone} still mapped (dangling relationship)"
        # Non-vacuity: the surviving enrichment relationships on Detection stay.
        for keep in ("pose_result", "threat_detections", "action_result"):
            assert keep in rels, f"collateral-pruned Detection.{keep}"

    def test_mapper_configures_without_a_dangling_target(self) -> None:
        """The end-to-end form of the above: the whole registry configures. A string
        relationship naming a deleted class raises here, not in a green unit test."""
        from sqlalchemy.orm import configure_mappers

        configure_mappers()  # raises InvalidRequestError on a dangling relationship

    def test_detection_source_drops_the_two_type_imports(self) -> None:
        src = _src("backend/models/detection.py")
        for cls in RETIRED_CLASSES:
            # The TYPE_CHECKING import + the Mapped[...] annotation both name it.
            assert cls not in src, f"detection.py still references {cls}"


class TestDatedDropSqlAdded:
    """No Alembic in this repo; schema comes from init_schema.py + create_all, and
    a hand-authored dated SQL file is the runbook artifact for existing DBs (scope
    §6; precedents: the two face/person provenance .sql files)."""

    def test_migration_file_exists_and_is_dated(self) -> None:
        path = REPO_ROOT / MIGRATION
        assert path.is_file(), f"missing dated DROP SQL: {MIGRATION}"
        assert re.match(r"^\d{4}-\d{2}-\d{2}-", path.name), path.name

    def test_migration_drops_exactly_the_two_retired_tables(self) -> None:
        sql = _src(MIGRATION).upper()
        for tbl in RETIRED_TABLES:
            assert f"DROP TABLE IF EXISTS {tbl.upper()}" in sql, f"{tbl} not dropped"
        # Negative space: the file must NOT drop the keeper or the kept pair.
        for keep in ("THREAT_DETECTIONS", "POSE_RESULTS", "ACTION_RESULTS", "PERSON_EMBEDDINGS"):
            assert f"DROP TABLE IF EXISTS {keep}" not in sql, f"{keep} wrongly dropped"

    def test_migration_is_idempotent_and_bounded(self) -> None:
        """Every house .sql here is `IF EXISTS` + wrapped in BEGIN/COMMIT (the face
        provenance precedent) -- a DROP that errors on a fresh DB (no table yet)
        would halt a runbook mid-apply. Non-vacuity: both tables named."""
        sql = _src(MIGRATION)
        assert "BEGIN;" in sql and "COMMIT;" in sql
        assert sql.count("DROP TABLE IF EXISTS") == 2, "expected exactly the two idempotent drops"


class TestSeedEventsPruned:
    """`scripts/seed-events.py` is the ONLY writer of either table in the repo. If it
    keeps importing/constructing the deleted classes the seed script ImportErrors --
    and the retired_providers-style dead-reference check would catch it late. Prune
    the import, both seed functions, the two cascade `delete()` calls, and the count
    bookkeeping. (seed-events is not shipped-invoked, but it is a maintained op that
    imports backend.models at module scope.)"""

    def test_seed_no_longer_imports_or_constructs_the_retired_classes(self) -> None:
        src = _src("scripts/seed-events.py")
        for cls in RETIRED_CLASSES:
            assert not re.search(rf"\b{cls}\b", src), f"seed still references {cls}"
        # Non-vacuity: the seed still seeds the KEEPERS (a gutted file passes the loop).
        for keep in ENRICHMENT_KEEPERS:
            assert keep in src, f"seed lost a keeper: {keep}"

    def test_seed_still_imports_only_symbols_that_exist(self) -> None:
        """The text grep above is a proxy for the one failure that actually bites:
        a `from backend.models import DemographicsResult` left in the seed script is
        an ImportError the moment an operator runs it, and the string scan only
        catches it if the name is spelled exactly. So this resolves the real thing:
        every `from backend.models[.x] import <name>` in the seed script, checked
        against the live module. The AST (not an import) is used because importing
        the script executes `_load_env_and_fix_database_url()` and rewrites the test
        session's DATABASE_URL -- see the note at SEED_EVENTS_PATH.

        Non-vacuity: the scan must have found a non-empty set of imports to check,
        so an empty scan cannot pass it, and at least one checked name must be a
        keeper class (proof it is really resolving the enrichment lane)."""
        pairs = _seed_model_imports()
        assert pairs, "the seed script imports nothing from backend.models -- scan is vacuous"
        unresolved = [
            f"{mod}.{name}"
            for mod, name in pairs
            if not hasattr(importlib.import_module(mod), name)
        ]
        assert not unresolved, f"seed imports symbols that no longer exist: {unresolved}"
        checked = {name for _, name in pairs}
        assert ENRICHMENT_KEEPERS[0] in checked or "Detection" in checked, (
            f"resolved {sorted(checked)} -- none is an enrichment/keeper class, so "
            "this check is not actually exercising the pruned lane"
        )

    def test_seed_still_prunes_the_keeper_on_reseed(self) -> None:
        """`seed-events.py` deletes each enrichment table before re-seeding. It must
        still clear the three keepers; it must no longer try to clear the dropped
        ones (that would be a `delete()` on a nonexistent table)."""
        src = _src("scripts/seed-events.py")
        for keep in ENRICHMENT_KEEPERS:
            assert f"delete({keep})" in src, f"re-seed no longer clears {keep}"
        for gone in RETIRED_CLASSES:
            assert f"delete({gone})" not in src, f"re-seed still deletes a dropped table: {gone}"


class TestDocsTrackTheDrop:
    """Docs a future agent reads (scope §9) describe these two tables as LIVE storage.
    After the DROP that is a map to a country that no longer exists. Pinned as the
    LIVE shapes (mermaid edges, inventory rows, retention rows), not incidental prose."""

    def test_data_model_readme_drops_the_two_edges_and_rows(self) -> None:
        src = _src("docs/architecture/data-model/README.md")
        for tbl in RETIRED_TABLES:
            assert f"||--o{{ {tbl}" not in src, f"mermaid still edges {tbl}"
            assert f"| `{tbl}`" not in src, f"inventory table still rows {tbl}"
        # Non-vacuity: the keeper edges/rows stay.
        for keep in ("pose_results", "threat_detections"):
            assert f"||--o{{ {keep}" in src, f"mermaid lost the keeper {keep}"

    def test_face_recognition_retention_table_stops_naming_the_two(self) -> None:
        src = _src("docs/guides/face-recognition.md")
        # The LIVE shape here is a Markdown table ROW ("| Data | Retention |
        # Where it lives |") -- a row says a thing is stored today. Prose is
        # allowed to name the dead, and the file now carries a tombstone
        # paragraph that does, so the pin keys on the row grammar rather than a
        # bare substring (a substring check would fail the very tombstone this
        # slice is required to leave, which is how a doc pin turns into a mute).
        for tbl in (*RETIRED_TABLES, "demographics_results", "reid_embeddings"):
            rows = [ln for ln in src.splitlines() if ln.lstrip().startswith("|") and tbl in ln]
            assert not rows, f"retention table still rows {tbl}: {rows}"
        # Non-vacuity: PersonEmbedding's OWN retention row (the live one) stays --
        # it is the name-trap twin and must not be conflated with the dropped table.
        live_rows = [
            ln for ln in src.splitlines() if ln.lstrip().startswith("|") and "PersonEmbedding" in ln
        ]
        assert live_rows, "the LIVE PersonEmbedding retention row must remain"

    def test_architecture_docs_do_not_claim_the_two_are_live_storage(self) -> None:
        """auxiliary-tables.md carries a full column spec for each dropped table and
        core-entities.md lists both relationship lines. Neither may keep a live
        section for a dropped table; a tombstone line is allowed (prose)."""
        aux = _src("docs/architecture/data-model/auxiliary-tables.md")
        for tbl in RETIRED_TABLES:
            assert f"**Table Name:** `{tbl}`" not in aux, f"auxiliary doc still specs {tbl}"
        core = _src("docs/architecture/data-model/core-entities.md")
        assert "DemographicsResult | None" not in core
        assert "reid_embedding: Mapped[ReIDEmbedding" not in core


class TestKeepersIntact:
    """Negative space, pinned so a reviewer cannot quietly widen the slice. These are
    the live surfaces the ruling protects; a collateral deletion reddens one of them."""

    def test_household_person_embedding_is_live_and_untouched(self) -> None:
        """The name-trap: `reid_embeddings` (dropped) vs `household.PersonEmbedding`
        (the live VLM re-ID gallery). The DROP must not reach the latter."""
        from backend.models.household import PersonEmbedding

        assert PersonEmbedding.__tablename__ == "person_embeddings"
        # The live reader the design names: the gallery loader.
        assert "PersonEmbedding" in _src("backend/services/household_matcher.py")

    def test_the_jsonb_reid_lane_is_untouched(self) -> None:
        """`reid_matcher.py` reads the JSONB key `enrichment_data["reid_embedding"]`
        -- a key, not a table. This slice prunes zero of it, and the key literal must
        still be there (it is not what 'retire reid_embeddings' means)."""
        src = _src("backend/services/reid_matcher.py")
        assert '"reid_embedding"' in src, "the JSONB re-ID key lane was collateral-edited"

    def test_overloaded_reid_embedding_columns_on_other_models_stay(self) -> None:
        from backend.models.household import RegisteredVehicle
        from backend.models.track import Track

        assert "reid_embedding" in Track.__table__.columns
        assert "reid_embedding" in RegisteredVehicle.__table__.columns

    def test_pose_action_threat_rule_fields_are_the_later_slice_not_this_one(self) -> None:
        """The owner ruling keeps pose_types/action_types executable. If a reviewer
        'finishes' S4 by dropping them here, this pin reddens -- their retirement is
        a separate atomic commit that must null stored rule values first."""
        from backend.models.alert import AlertRule

        for keep in ("pose_types", "action_types", "threat_detection_enabled"):
            assert keep in AlertRule.__table__.columns, f"{keep} retired early"
        # And the shipped reader they feed is still wired (alert_engine selects them).
        engine = _src("backend/services/alert_engine.py")
        assert "select(PoseResult)" in engine and "select(ActionResult)" in engine
