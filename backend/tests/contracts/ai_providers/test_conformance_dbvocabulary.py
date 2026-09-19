"""WP8.5 — vocabulary conformance: server emitters vs the database CHECKs (red-first).

Plan: docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.5 (L1027-1075).
The DB is the de-facto conformance spec — enforced too late (at INSERT) and nowhere
in unit tests. This module makes the server-emitted vocabularions assert against
the ORM CheckConstraints they must satisfy.

INTEGRATED (2026-09-19): first in-tree contact 16 passed / 7 failed — all
seven the module's own section-1 prediction (line "Expected RED: 7 subset
assertions"; the draft harness under /tmp showed only 3 reds because four AST
legs read REPO_ROOT-relative files that only resolve in-tree — the in-tree
count IS the finding the header predicts). Per the goal rule (branch stays
GREEN; a RULING-blocked finding is pinned as a characterization, never left
red) the seven subset assertions now pin the EXACT illegal sets as DATA —
each names the parked alignment ruling and flips red the day behavior
changes, which is the tripwire, not a defect escaping. NO xfail / skip /
importorskip anywhere (goal rule).

===========================================================================
CITE-CORRECTION NOTES (plan line numbers drifted; corrected cites verified
against this tree; executed-DB evidence already in L at 88215286..a8c25c5e):
===========================================================================
  1. The plan cites the DB CHECKs as `api/schemas/enrichment.py` — the file
     is actually backend/models/enrichment.py (pose L77-78, threat L139,
     gender L193-194, age L197-199). backend/api/schemas/alerts.py carries a
     PARITY COPY of two of the sets (VALID_POSE_CLASSES L74-77,
     VALID_THREAT_TYPES L81) — TestSchemaParity below pins that copy.
  2. The plan's "12 threat values" at threat_detector.py:66,76 is the
     STRING-keyed THREAT_CLASSES_BY_NAME map (L76-88); the int-keyed
     THREAT_CLASSES at L66-73 is a DIFFERENT, 6-value COCO-style set.
     Both are checked here; the "9 of 12 rejected" line belongs to BY_NAME.
  3. The `ai/gateway` cite from the WP8.3 draft note is n/a here — this
     module compares ai/ enrichment servers against backend/models/ only;
     no gateway adapter vocabulary participates.
  4. Plan says "Four will fail" (one per vocabulary row). This module finds
     SEVEN failing subset assertions — 4 pose emitters (the plan names one
     table) x 1 age + 2 threat maps — and those are a *floor*: AST
     extraction of the
     other pose classifiers in the tree (F1/F2 below) shows a much larger
     illegal alphabet (crawling / reaching_up / aggressive / fallen /
     lying) than the plan's vitpose-only example. That is a finding.

DB-TOUCHING TEST — CHOICE (stated per plan bullet 4): this module does NOT
connect to Postgres. The executed-INSERT evidence the plan asks for is
already captured in L (a8c25c5e: 8/8 values rejected vs host Postgres
16.15, each in its own SAVEPOINT, zero persistence). A CI-parity-safe
executable check lives instead in test_conformance_numeric.py's
DB_CONSTRAINT_CONTRACTS tier (backend/tests/contracts/ai_providers/),
where the repo's own integration harness owns DB provisioning. Everything
here is a pure static/ORM/AST assert.
===========================================================================

IMPORTS-THAT-HALT SURVEY (this .venv, Python 3.14.2 — all clean, no torch
halt; ai/conftest.py triton slot hygiene does NOT apply to a /tmp path):
  ai.enrichment.models.demographics  -> importable (torch present; 2nd import cached)
  ai.enrichment.vitpose              -> importable
  ai.enrichment.models.threat_detector -> importable
  ai/enrichment-light/**             -> NOT importable (hyphenated dir, not a package)
                                        -> AST literals for the light twin
  backend.services.vitpose_loader / age_classifier_loader / models.*  -> importable
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from backend.api.schemas import llm_response as llm_schema
from backend.models.detection import Detection
from backend.models.enrichment import DemographicsResult, PoseResult, ThreatDetection
from backend.models.entity import Entity
from backend.models.event import Event


def _import_enrichment_vocab_tables() -> tuple[Any, Any, Any]:
    """Import the two heavy-server vocab tables + POSTURE_LABELS, then undo
    the flat-name slot damage those modules do on import.

    WHY THIS IS SCOPED HERE (house slot-hygiene pattern, ai/conftest.py:
    triton block is the precedent): ai/enrichment/models/threat_detector.py
    :42-43 inserts ``ai/`` into ``sys.path`` (it must, for the container's
    flat /app layout), which leaves the name ``triton`` resolving to the
    DIRECTORY ``ai/triton/`` as a namespace package. pip triton is NOT
    installed in this venv, so that stub poisons every later ``import
    triton`` — torch._dynamo dies on ``triton.language`` and transformers'
    lazy CLIPModel import then fails for whatever module collects AFTER this
    file (proved: bare-dir runs reddened two clip legs of
    test_client_conformance.py; the pair run and this module alone were
    green — the order signature). Removing ``ai/`` from ``sys.path`` and
    evicting the stub restores the pre-import state for the rest of the
    session."""
    import sys
    from pathlib import Path as _P

    # THIS file is backend/tests/contracts/ai_providers/x.py -> parents[4] is
    # the repo root; parents[3] is backend/ (a first draft used it and the
    # hygiene silently removed a nonexistent path — the dir-alone reds stayed).
    ai_dir = str(_P(__file__).resolve().parents[4] / "ai")
    from ai.enrichment.models.threat_detector import (
        THREAT_CLASSES as threat_int,
    )
    from ai.enrichment.models.threat_detector import (
        THREAT_CLASSES_BY_NAME as threat_by_name,
    )
    from ai.enrichment.vitpose import POSTURE_LABELS as posture_labels

    while ai_dir in sys.path:
        sys.path.remove(ai_dir)
    for name in [m for m in list(sys.modules) if m == "triton" or m.startswith("triton.")]:
        mod = sys.modules[name]
        # evict ONLY the namespace-package stub (no __file__); a real pip
        # triton installed by some other tier stays untouched
        if getattr(mod, "__file__", None) is None and hasattr(mod, "__path__"):
            del sys.modules[name]
    return threat_int, threat_by_name, posture_labels


THREAT_CLASSES_INT, THREAT_CLASSES_BY_NAME_HEAVY, POSTURE_LABELS = _import_enrichment_vocab_tables()


def _find_repo_root() -> Path:
    """Walk up from this file to the directory carrying BOTH the backend and
    ai trees (the draft's /tmp copy could not resolve this — one reason its
    four AST legs were vacuously green there). Portable on purpose: no
    machine-specific literal, because the CI checkout path is not this one."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "backend" / "models" / "enrichment.py").is_file() and (
            candidate / "ai"
        ).is_dir():
            return candidate
    raise AssertionError("test_conformance_dbvocabulary.py sits outside a repo root")


REPO_ROOT = _find_repo_root()

# ---------------------------------------------------------------------------
# Source helpers (repo precedent: backend/tests/contracts/ai_providers/
# test_conformance_vocabulary.py:146-161 `_ast_assign`).
# ---------------------------------------------------------------------------


def _ast_assign(path: Path, name: str) -> Any:
    """literal_eval the module-level assignment of `name` (Assign or
    AnnAssign) — a rename must redden here, not silently in a fake."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as a module-level literal in {path}")


def _ast_in_membership(path: Path, var_endswith: str) -> tuple[str, ...]:
    """Extract the literal tuple of the first `X in (<str>, <str>, ...)`
    Compare whose LEFT side ends with `var_endswith` (e.g. 'age_range in')."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not (
            len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and isinstance(node.comparators[0], ast.Tuple)
        ):
            continue
        left = ast.unparse(node.left)
        if not left.endswith(var_endswith):
            continue
        elts = node.comparators[0].elts
        if all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in elts):
            return tuple(e.value for e in elts)  # type: ignore[union-attr]
    raise AssertionError(f"no `... {var_endswith} in (<literals>)` in {path}")


def _ast_dict_keys_within(path: Path, var: str, func: str) -> frozenset[str]:
    """String keys of the dict literal assigned to `var` inside `func` —
    vitpose_loader's winning-label return is dict-INDEXED (`best_pose[0]`,
    L417), so the candidate table IS its output alphabet."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == func]:
        for node in ast.walk(fn):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            if any(isinstance(t, ast.Name) and t.id == var for t in targets) and isinstance(
                getattr(node, "value", None), ast.Dict
            ):
                keys = [
                    k.value
                    for k in node.value.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                ]
                if keys:
                    return frozenset(keys)
    raise AssertionError(f"dict literal {var} not found in {func} of {path}")


def _ast_return_literals(path: Path, func: str) -> frozenset[str]:
    """All string literals appearing in `return` statements of top-level or
    method `func` — literals only (a dict-indexed return like vitpose_loader's
    `best_pose[0]` is NOT captured; that emitter is pinned via its pose_scores
    table separately). Captures tuple and ternary returns."""

    def parts(n: ast.AST) -> list[str]:
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            return [n.value]
        if isinstance(n, ast.Tuple):
            return [x for e in n.elts for x in parts(e)]
        if isinstance(n, ast.IfExp):
            return parts(n.body) + parts(n.orelse)
        return []

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            return frozenset(
                x
                for r in ast.walk(node)
                if isinstance(r, ast.Return) and r.value is not None
                for x in parts(r.value)
            )
    raise AssertionError(f"function {func} not found in {path}")


def _check_sql(model: Any, name: str) -> str:
    """The SQL text of an ORM CheckConstraint, by name."""
    for c in model.__table__.constraints:
        if getattr(c, "name", None) == name:
            return str(c.sqltext)
    raise AssertionError(f"{name} not found on {model.__name__}")


def _check_values(model: Any, name: str) -> frozenset[str]:
    """Values from a `col IN ('a','b',...)` CHECK, parsed off the ORM
    constraint text — the DB spec as a set, no live connection needed."""
    sql = _check_sql(model, name)
    start = sql.index("IN (") + 4
    end = sql.index(")", start)  # values contain no parens
    return frozenset(ast.literal_eval(f"({sql[start:end]})"))


# ---------------------------------------------------------------------------
# DB spec (read from the ORM CheckConstraints — backend/models/enrichment.py)
# ---------------------------------------------------------------------------

DB_POSE = _check_values(PoseResult, "ck_pose_results_pose_class")
DB_THREAT = _check_values(ThreatDetection, "ck_threat_detections_threat_type")
DB_GENDER = _check_values(DemographicsResult, "ck_demographics_results_gender")
DB_AGE = _check_values(DemographicsResult, "ck_demographics_results_age_range")

# Server emitters
AGE_RANGES_SERVER = _ast_assign(REPO_ROOT / "ai/enrichment/models/demographics.py", "AGE_RANGES")
GENDER_LABELS_SERVER = _ast_assign(
    REPO_ROOT / "ai/enrichment/models/demographics.py", "GENDER_LABELS"
)
THREAT_BY_NAME_LIGHT = _ast_assign(
    REPO_ROOT / "ai/enrichment-light/models/threat_detector.py", "THREAT_CLASSES_BY_NAME"
)
THREAT_INT_LIGHT = _ast_assign(
    REPO_ROOT / "ai/enrichment-light/models/threat_detector.py", "THREAT_CLASSES"
)

# is_minor — the THREE spellings (AST-extracted safety predicate literals)
PIPELINE = REPO_ROOT / "backend/services/enrichment_pipeline.py"
AGE_LOADER = REPO_ROOT / "backend/services/age_classifier_loader.py"
IS_MINOR_PIPELINE_3868 = _ast_in_membership(PIPELINE, "demographics.age_range")
IS_MINOR_PIPELINE_5324 = _ast_in_membership(PIPELINE, "remote_result.age_range")
IS_MINOR_LOADER_94 = _ast_in_membership(AGE_LOADER, "self.age_group")

# Pose classifier alphabets beyond the plan's single vitpose example (F1/F2)
ENRICH_PE = REPO_ROOT / "ai/enrichment/models/pose_estimator.py"
ENRICH_LT_PE = REPO_ROOT / "ai/enrichment-light/models/pose_estimator.py"
YOLO26_POSE = REPO_ROOT / "ai/yolo26/pose_estimation.py"
VITPOSE_LOADER = REPO_ROOT / "backend/services/vitpose_loader.py"

PE_RETURNS_HEAVY = _ast_return_literals(ENRICH_PE, "_classify_pose")
PE_RETURNS_LIGHT = _ast_return_literals(ENRICH_LT_PE, "_classify_pose")
YOLO26_RETURNS = _ast_return_literals(YOLO26_POSE, "classify_pose")
VITPOSE_LOADER_TABLE = _ast_dict_keys_within(VITPOSE_LOADER, "pose_scores", "classify_pose") | {
    "unknown"
}

EXPECTED_RED_MARK = "WP8.5 discovery red — RULING parked"


# ===========================================================================
# 1. STATIC CROSS-CHECK (plan bullet 1) — every server emitter vs its DB
#    CHECK. The 7 subset assertions ALL failed at first contact (plan
#    predicted 4; the 7-vs-4 delta is a finding, module docstring note 4)
#    and each now pins its EXACT illegal set as DATA — shipped-behavior
#    characterizations, each naming the parked WP8.5-vocab-alignment ruling.
# ===========================================================================


class TestStaticSubset:
    def test_db_checks_parse_as_expected(self) -> None:
        """Spec sanity (GREEN): each DB CHECK parses to exactly the legal set
        captured live at 88215286..a8c25c5e (Postgres 16.15 pg_constraint)."""
        assert (
            frozenset(
                {
                    "standing",
                    "crouching",
                    "bending_over",
                    "arms_raised",
                    "sitting",
                    "lying_down",
                    "unknown",
                }
            )
            == DB_POSE
        )
        assert frozenset({"gun", "knife", "grenade", "explosive", "weapon", "other"}) == DB_THREAT
        assert frozenset({"male", "female", "unknown"}) == DB_GENDER
        assert (
            frozenset(
                {
                    "0-10",
                    "11-20",
                    "21-30",
                    "31-40",
                    "41-50",
                    "51-60",
                    "61-70",
                    "71-80",
                    "81+",
                    "unknown",
                }
            )
            == DB_AGE
        )

    def test_pose_vitpose_labels_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1034): widen CHECK vs normalize at client boundary.

        ai/enrichment/vitpose.py:44-51 POSTURE_LABELS (standing, walking,
        sitting, crouching, lying_down, running) vs ck_pose_results_pose_class
        (backend/models/enrichment.py:77-78). `walking` + `running` ILLEGAL.
        Executed vs host Postgres 16.15: both RAISED
        ck_pose_results_pose_class violations (a8c25c5e transcript).

        LANDED AS CHARACTERIZATION (goal rule): pins the exact illegal delta.
        RULING `WP8.5-vocab-alignment` parked — widen the CHECK or normalize
        at the client boundary. When either lands this equality reddens and
        this docstring tells the next reader why that is expected.
        """
        assert set(POSTURE_LABELS) - DB_POSE == frozenset({"walking", "running"}), (
            f"vitpose POSTURE_LABELS delta vs the CHECK moved to {sorted(set(POSTURE_LABELS) - DB_POSE)} "
            "— the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_pose_enrichment_estimator_classifier_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1034 extension, F1): widen CHECK vs normalize at client boundary.

        The enrichment server's ACTUAL runtime classifier is
        ai/enrichment/models/pose_estimator.py::_classify_pose — NOT the
        vitpose.py POSTURE_LABELS table the plan cites (which is dead data:
        grep finds zero readers). AST return-literals add `crawling` and
        `reaching_up` to the illegal alphabet.

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact illegal return set as shipped.
        """
        assert frozenset({"crawling", "reaching_up", "running"}) == PE_RETURNS_HEAVY - DB_POSE, (
            f"_classify_pose delta moved to {sorted(PE_RETURNS_HEAVY - DB_POSE)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_pose_yolo26_classifier_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (F1): widen CHECK vs normalize at client boundary.

        ai/yolo26/pose_estimation.py:502 classify_pose (imported by
        ai/yolo26/pose_estimation.py:800's own pipeline) emits
        `fallen`, `reaching_up`, `aggressive` — all rejected by
        ck_pose_results_pose_class; `aggressive` collides semantically with
        the DB's `arms_raised` slot.

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact illegal return set as shipped.
        """
        assert frozenset({"fallen", "reaching_up", "aggressive"}) == YOLO26_RETURNS - DB_POSE, (
            f"yolo26 classify_pose delta moved to {sorted(YOLO26_RETURNS - DB_POSE)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_pose_vitpose_loader_table_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (F1): widen CHECK vs normalize at client boundary.

        backend/services/vitpose_loader.py:354-360 pose_scores table:
        standing/crouching/running/sitting/`lying` (+ 'unknown' early return,
        L299/L415). `lying` ≠ legal `lying_down` — a near-miss spelling, the
        kind that survives a rename refactor. (Its winning-label return is
        dict-indexed, so the table literal is the pin.)

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact illegal table set as shipped.
        """
        assert frozenset({"lying", "running"}) == VITPOSE_LOADER_TABLE - DB_POSE, (
            f"vitpose_loader delta moved to {sorted(VITPOSE_LOADER_TABLE - DB_POSE)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_age_ranges_server_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1035): widen CHECK vs normalize at client boundary.

        demographics.py:44-51 AGE_RANGES vs ck_demographics_results_age_range
        (:197-199): server's 21-35 / 36-50 / 51-65 / 65+ all illegal —
        4 of 6 rejected. All four RAISED live (a8c25c5e).

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact illegal bucket set as shipped.
        """
        assert set(AGE_RANGES_SERVER) - DB_AGE == frozenset({"21-35", "36-50", "51-65", "65+"}), (
            f"AGE_RANGES delta moved to {sorted(set(AGE_RANGES_SERVER) - DB_AGE)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_threat_by_name_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1036): widen CHECK vs normalize at client boundary.

        THREAT_CLASSES_BY_NAME (threat_detector.py:76-88, 12 names) vs
        ck_threat_detections_threat_type (:139, 6 values) → 9 of 12 rejected:
        rifle, pistol, firearm, bat, crowbar, hammer, sword, machete, axe.
        rifle + hammer EXECUTED live (a8c25c5e).

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact rejected 9-of-12 as shipped.
        """
        assert set(THREAT_CLASSES_BY_NAME_HEAVY) - DB_THREAT == frozenset(
            {"rifle", "pistol", "firearm", "bat", "crowbar", "hammer", "sword", "machete", "axe"}
        ), (
            f"BY_NAME delta moved to {sorted(set(THREAT_CLASSES_BY_NAME_HEAVY) - DB_THREAT)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )

    def test_threat_int_classes_subset_of_db_check(self) -> None:
        """WP8.5 discovery red — RULING parked (L1036): widen CHECK vs normalize at client boundary.

        The int-keyed COCO-style map THREAT_CLASSES (:66-73) — a DIFFERENT
        6-value vocabulary the plan conflated with BY_NAME (correction note 2):
        knife, gun, rifle, pistol, bat, crowbar → 4 of 6 rejected.

        LANDED AS CHARACTERIZATION (goal rule; RULING `WP8.5-vocab-alignment`
        parked): pins the exact rejected 4-of-6 as shipped.
        """
        emitted = {v[0] for v in THREAT_CLASSES_INT.values()}
        assert emitted - DB_THREAT == frozenset({"rifle", "pistol", "bat", "crowbar"}), (
            f"THREAT_CLASSES delta moved to {sorted(emitted - DB_THREAT)} — "
            "the WP8.5-vocab-alignment ruling landed; rewrite to the new shape"
        )


# ===========================================================================
# 2. CHARACTERIZATION (GREEN pins of today's behaviour — the plan's
#    "Pin today's behaviour" bullet; remediation stays RULING-blocked).
# ===========================================================================


class TestCharacterization:
    def test_threat_twins_identical(self) -> None:
        """Both threat_detector twins carry byte-identical vocabularies —
        drift between them would itself be a finding (the TensorRT/Engine
        machinery around them already differs; the vocab must not)."""
        assert THREAT_CLASSES_BY_NAME_HEAVY == THREAT_BY_NAME_LIGHT
        assert THREAT_CLASSES_INT == THREAT_INT_LIGHT

    def test_illegal_threat_sets_are_data(self) -> None:
        """Illegal-by-name sets asserted AS DATA (not just non-empty)."""
        assert set(THREAT_CLASSES_BY_NAME_HEAVY) - DB_THREAT == frozenset(
            {"rifle", "pistol", "firearm", "bat", "crowbar", "hammer", "sword", "machete", "axe"}
        )
        assert {v[0] for v in THREAT_CLASSES_INT.values()} - DB_THREAT == frozenset(
            {"rifle", "pistol", "bat", "crowbar"}
        )

    def test_legal_but_unproduced_threats(self) -> None:
        """`grenade` + `explosive` are legal in the CHECK and produced by
        NOTHING in either threat vocabulary (plan sentence, verified)."""
        produced = set(THREAT_CLASSES_BY_NAME_HEAVY) | {v[0] for v in THREAT_CLASSES_INT.values()}
        assert DB_THREAT - produced == frozenset({"grenade", "explosive", "other"})

    def test_illegal_age_intersection_is_data(self) -> None:
        """Age: 2 of 6 server buckets legal, 4 rejected — exact set as data."""
        assert set(AGE_RANGES_SERVER) & DB_AGE == frozenset({"0-10", "11-20"})
        assert set(AGE_RANGES_SERVER) - DB_AGE == frozenset({"21-35", "36-50", "51-65", "65+"})

    def test_gender_labels_ordering_is_load_bearing(self) -> None:
        """demographics.py:54 GENDER_LABELS = ['female','male'] — the list
        INDEX is the class id (consumed positionally at :283
        `GENDER_LABELS[: num_labels]`, HF id2label convention). A provider
        reordering labels INVERTS every prediction while staying fully
        schema-valid: both orders are subsets of the DB CHECK. Pin the
        ordering; the inversion scenario is asserted as DATA."""
        assert GENDER_LABELS_SERVER == ["female", "male"]
        # schema-validity of the inverted order (the hazard, as data):
        assert {"male", "female"} <= DB_GENDER

    def test_gender_emitter_coverage(self) -> None:
        """Server emits {female, male} ⊆ DB {male, female, unknown}; the third
        legal value is produced by _normalize_gender_label's fallback
        (demographics.py:641-644) — legal, but NOT via GENDER_LABELS."""
        assert set(GENDER_LABELS_SERVER) <= DB_GENDER
        assert DB_GENDER - set(GENDER_LABELS_SERVER) == frozenset({"unknown"})

    def test_is_minor_three_spellings_pinned(self) -> None:
        """The child-safety predicate exists in THREE literal spellings
        (plan missed the third). Equality pins on the AST-extracted tuples —
        any edit of any spelling reddens this and forces the owner to look."""
        assert IS_MINOR_PIPELINE_3868 == ("0-10", "11-20", "child", "teenager")
        assert IS_MINOR_PIPELINE_5324 == ("0-10", "11-20", "child", "teenager")
        assert IS_MINOR_LOADER_94 == ("infant", "child", "teenager")

    def test_is_minor_safety_property_characterized(self) -> None:
        """SAFETY characterization: the loader alphabet and the pipeline
        alphabets share only {child, teenager} — and a server emitting
        AGE_RANGES-style buckets (the ONLY thing enrichment_pipeline feeds
        them: pipeline :3875 `age_group=unified.demographics.age_range`) can
        intersect the child set only at '0-10'/'11-20'. Loader spelling +
        server bucket ⇒ is_minor False for EVERY child — asserted as the
        membership expression itself."""
        assert set(IS_MINOR_LOADER_94) & set(AGE_RANGES_SERVER) == frozenset()
        assert set(IS_MINOR_PIPELINE_3868) & set(AGE_RANGES_SERVER) == frozenset({"0-10", "11-20"})
        for server_bucket in AGE_RANGES_SERVER:
            # loader spelling: False for EVERY server-emitted value, child
            # buckets included — the full false-negative hazard:
            assert server_bucket not in IS_MINOR_LOADER_94
            # pipeline spelling: True only at the two numeric child buckets:
            assert (server_bucket in IS_MINOR_PIPELINE_3868) == (server_bucket in {"0-10", "11-20"})

    def test_schema_parity_mirrors_exist(self) -> None:
        """backend/api/schemas/alerts.py carries a hand-maintained PARITY COPY
        of two DB sets (cited by name as 'Based on ... CHECK'). Pin the copy
        against the ORM — the second enforcement point must not drift."""
        from backend.api.schemas import alerts

        assert alerts.VALID_POSE_CLASSES == DB_POSE
        assert alerts.VALID_THREAT_TYPES == DB_THREAT


# ===========================================================================
# 3. MISSING INVARIANTS (plan bullet 3: is_minor membership [above],
#    embedding dimensionality + unit norm, risk_score integrality).
#    The first unit-norm assertion anywhere is N1a in
#    backend/tests/contracts/ai_providers/test_conformance_numeric.py:434
#    (WP8.3 N1b: zero unit-norm asserts existed before it). This is the
#    BACKEND-side companion.
# ===========================================================================


def _l2_norm(v: list[float]) -> float:
    return sum(x * x for x in v) ** 0.5


class TestMissingInvariants:
    def test_embedding_dim_constant_pinned(self) -> None:
        """EMBEDDING_DIMENSION == 768 pinned at BOTH definitions (services)
        and cross-checked against the scene_baseline gate that enforces it."""
        from backend.services import clip_client, scene_baseline

        assert scene_baseline.EMBEDDING_DIMENSION == 768
        assert clip_client.EMBEDDING_DIMENSION == 768

    @pytest.mark.asyncio
    async def test_scene_baseline_normalizes_unit_norm(self) -> None:
        """GREEN invariant: the ONLY backend-side normalizer on the baseline
        path is scene_baseline's L2 normalization (scene_baseline.py:337-339
        in set_baseline). EXECUTED through the real code path with a mocked
        Redis — a non-unit input emerges unit-normalized in the stored
        payload. The first backend-side unit-norm assertion (N1a owns the
        provider side; repo precedent for the mock: test_scene_baseline.py
        create_mock_redis_with_pipeline)."""
        import json
        from unittest.mock import AsyncMock

        from backend.services.scene_baseline import SceneBaselineService

        stored: dict[str, str] = {}

        class FakePipeline:
            def setex(self, key, ttl, value):
                stored[key] = value

            async def execute(self):
                return [True, True, True]

        from unittest.mock import MagicMock

        redis = AsyncMock()
        client = MagicMock()  # _client.pipeline() is SYNC in set_baseline (:345)
        client.pipeline.return_value = FakePipeline()
        redis._client = client
        service = SceneBaselineService(redis)

        embedding = [3.0] + [4.0] * 767  # non-unit by construction
        assert _l2_norm(embedding) != pytest.approx(1.0)
        await service.set_baseline("cam_1", embedding, sample_count=1)

        vectors: list[list[float]] = []
        for raw in stored.values():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError, TypeError:
                continue  # count/timestamp payloads
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], float):
                vectors.append(parsed)
        assert vectors, f"no vector payload captured in {sorted(stored)}"
        assert len(vectors[0]) == 768
        assert _l2_norm(vectors[0]) == pytest.approx(1.0, abs=1e-9)

    def test_entities_embedding_vector_unconstrained(self) -> None:
        """MISSING invariant characterization (plan: 'no enforcement
        anywhere'): entities.embedding_vector is free JSONB with NO CHECK,
        and the ORM helper accepts any dimension — including a 512 vector
        tagged dimension=768, with no validation error (probe-verified)."""
        import sqlalchemy as sa

        col = Entity.__table__.c.embedding_vector
        assert isinstance(col.type, sa.dialects.postgresql.JSONB)
        checks = [
            getattr(c, "name", "")
            for c in Entity.__table__.constraints
            if "ck_" in str(getattr(c, "name", ""))
        ]
        assert not any("embed" in str(n) for n in checks)
        e = Entity()
        e.set_embedding([0.1] * 512, model="clip", dimension=768)  # lies, silently accepted
        assert len(e.get_embedding_vector()) == 512
        assert e.embedding_vector["dimension"] == 768

    def test_detections_object_type_unconstrained(self) -> None:
        """MISSING invariant characterization: detections.object_type is
        unconstrained String (no length) with NO CHECK — the trigram index
        (idx_detections_object_type_trgm) is only a comment here
        (detection.py:163-164; the index lives in an Alembic migration)."""
        import sqlalchemy as sa

        col = Detection.__table__.c.object_type
        assert isinstance(col.type, sa.String)
        assert col.type.length is None
        checks = sorted(
            str(getattr(c, "name", ""))
            for c in Detection.__table__.constraints
            if "ck_" in str(getattr(c, "name", ""))
        )
        assert not any("object_type" in n for n in checks)
        assert (REPO_ROOT / "backend/models/detection.py").read_text().count(
            "idx_detections_object_type_trgm"
        ) == 1

    def test_risk_score_integrality_pins(self) -> None:
        """risk_score integrality (GREEN pins of today's coercions — the
        validators that make the Integer column + 0-100 CHECK reachable):
        strict schema ge/le bounds, before-mode truncation, and the raw
        path's clamp + default-to-50."""
        import pydantic

        ok = llm_schema.LLMRiskResponse(
            risk_score=75, risk_level="high", summary="s", reasoning="r"
        )
        assert ok.risk_score == 75
        for bad in (-1, 101):
            with pytest.raises(pydantic.ValidationError):
                llm_schema.LLMRiskResponse(
                    risk_score=bad, risk_level="high", summary="s", reasoning="r"
                )
        # float input truncates toward zero (int() semantics), 74.9 -> 74
        t = llm_schema.LLMRiskResponse(
            risk_score=74.9, risk_level="high", summary="s", reasoning="r"
        )
        assert t.risk_score == 74 and isinstance(t.risk_score, int)
        # raw/lenient path: clamp + infer level; None -> 50
        raw = llm_schema.LLMRawResponse(risk_score=150, risk_level="EXTREME")
        assert raw.to_validated_response().risk_score == 100
        raw2 = llm_schema.LLMRawResponse(risk_score=None, risk_level="EXTREME")
        assert raw2.to_validated_response().risk_score == 50

    def test_risk_score_integrality_db_divergence(self) -> None:
        """DB-side integrality: events.risk_score is sa.Integer (DB-enforced
        rounding, half away from zero) inside ck_events_risk_score_range
        (event.py:242-243). Characterizes the ROUNDING DIVERGENCE: pydantic
        truncates 74.9 -> 74, Postgres rounds to 75 (live probe on host
        PG 16.15: select 74.9::integer == 75; -0.5::integer == -1). Same
        float in, two legal-but-different ints out."""
        import sqlalchemy as sa

        col = Event.__table__.c.risk_score
        assert isinstance(col.type, sa.Integer)
        assert "risk_score >= 0 AND risk_score <= 100" in _check_sql(
            Event, "ck_events_risk_score_range"
        )
        # divergence as DATA (Python truncation side; PG side from the probe):
        assert int(74.9) == 74 and int(-0.5) == 0


# NOTE: expected-red roster for the serial lane (7, all TestStaticSubset):
#   test_pose_vitpose_labels_subset_of_db_check            (walking, running)
#   test_pose_enrichment_estimator_classifier_subset_of_db_check (crawling, reaching_up, running)
#   test_pose_yolo26_classifier_subset_of_db_check         (fallen, reaching_up, aggressive)
#   test_pose_vitpose_loader_table_subset_of_db_check      (lying, running)
#   test_age_ranges_server_subset_of_db_check              (21-35, 36-50, 51-65, 65+)
#   test_threat_by_name_subset_of_db_check                 (9 of 12)
#   test_threat_int_classes_subset_of_db_check             (rifle, pistol, bat, crowbar)
